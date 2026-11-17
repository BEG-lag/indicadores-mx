"""A small, polite client for the public SIDOF API (Secretaría de Gobernación).

SIDOF serves the Diario Oficial de la Federación as JSON, with no account or token.
The endpoints and their quirks were verified in the sibling project mcp-dof
(``docs/api.md``) and are summarized in ``docs/fuentes.md``:

* ``Accept: application/json`` alone answers HTTP 406, so the wildcard is kept.
* An invalid date answers HTTP 500; dates are built from ``date`` objects only.
* A day without an edition answers 200 with empty lists; an indicator range with
  no values answers 404 with a JSON body (treated as "no values").

The client is synchronous on purpose (it runs unattended in GitHub Actions):
one request at a time, a fixed pause between requests, retries with exponential
backoff on network errors, 429 and 5xx, and a descriptive User-Agent. An optional
disk cache keeps past responses so a backfill can be resumed without hitting the
server again. Only immutable answers are cached: past day indexes, indicator
ranges that ended before today, and note texts.
"""

from __future__ import annotations

import json
import random
import re
import time
import unicodedata
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx

from . import __version__
from .dates import from_sidof, to_sidof, today_mx
from .dof import html_to_text

BASE_URL = "https://sidof.segob.gob.mx/dof/sidof"
USER_AGENT = f"indicadores-mx/{__version__} (+https://github.com/BEG-lag/indicadores-mx)"
RETRY_STATUS = {429, 500, 502, 503, 504}
EDITION_KEYS = {
    "NotasMatutinas": "matutina",
    "NotasVespertinas": "vespertina",
    "NotasExtraordinarias": "extraordinaria",
}

# Issuers whose notes this project reads. Matching is done on the upper-case,
# accent-free issuing agency (``codOrgaDos``).
ISSUERS = (
    "BANCO DE MEXICO",
    "ESTADISTICA Y GEOGRAFIA",
    "SALARIOS MINIMOS",
    "TRABAJO Y PREVISION SOCIAL",
)
TITLE_HINTS = ("SALARIO", "UNIDAD DE MEDIDA", "PRECIOS AL CONSUMIDOR", "UNIDAD DE INVERSI")


class SidofError(RuntimeError):
    """SIDOF could not be reached or answered with an error."""


def fold(text: str | None) -> str:
    """Upper case without accents, for robust matching of agency names and titles."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).upper()


@dataclass(frozen=True, slots=True)
class NoteRow:
    """One relevant row of a day's table of contents."""

    code: int
    title: str
    day: date
    edition: str
    agency: str

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        data["day"] = self.day.isoformat()
        return data

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> NoteRow:
        return cls(
            code=int(data["code"]),
            title=data["title"],
            day=date.fromisoformat(data["day"]),
            edition=data["edition"],
            agency=data["agency"],
        )


@dataclass(frozen=True, slots=True)
class Note:
    """A note's title and plain text."""

    code: int
    title: str
    day: date
    agency: str
    text: str


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return None if text in {"", "null", "None"} else text


def relevant(agency: str | None, title: str | None) -> bool:
    folded_agency, folded_title = fold(agency), fold(title)
    return any(i in folded_agency for i in ISSUERS) or any(h in folded_title for h in TITLE_HINTS)


def parse_day(payload: dict[str, Any], day: date) -> list[NoteRow]:
    """Relevant titled rows of a ``/notas/{fecha}`` payload, in edition order."""
    rows: list[NoteRow] = []
    for key, edition in EDITION_KEYS.items():
        for raw in payload.get(key) or []:
            title = _clean(raw.get("titulo"))
            code = _clean(raw.get("codNota"))
            agency = _clean(raw.get("codOrgaDos")) or ""
            if not title or not code or not relevant(agency, title):
                continue
            raw_day = _clean(raw.get("fecha"))
            rows.append(
                NoteRow(
                    code=int(float(code)),
                    title=" ".join(title.split()),
                    day=from_sidof(raw_day) if raw_day else day,
                    edition=edition,
                    agency=agency,
                )
            )
    return rows


class Sidof:
    def __init__(
        self,
        *,
        base_url: str = BASE_URL,
        cache_dir: Path | None = None,
        delay: float = 0.4,
        timeout: float = 30.0,
        max_retries: int = 4,
        backoff: float = 2.0,
        transport: httpx.BaseTransport | None = None,
        today: date | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.cache_dir = cache_dir
        self.delay = delay
        self.max_retries = max_retries
        self.backoff = backoff
        self.today = today or today_mx()
        self.requests = 0
        self.cache_hits = 0
        self._last = 0.0
        self._memo: dict[str, Any] = {}
        self._http = httpx.Client(
            timeout=httpx.Timeout(timeout, connect=10.0),
            # SIDOF answers 406 to a bare "Accept: application/json".
            headers={"User-Agent": USER_AGENT, "Accept": "application/json, */*;q=0.8"},
            transport=transport,
            follow_redirects=True,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Sidof:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ HTTP

    def _pause(self) -> None:
        wait = self._last + self.delay - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()

    def get_json(self, path: str, *, missing_ok: bool = False) -> dict[str, Any] | None:
        """GET ``{base_url}/{path}``. ``None`` for a 404 when ``missing_ok``."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        error = "unknown error"
        for attempt in range(self.max_retries + 1):
            if attempt:
                time.sleep(self.backoff * 2 ** (attempt - 1) + random.uniform(0, self.backoff))
            self._pause()
            try:
                response = self._http.get(url)
                self.requests += 1
            except httpx.TransportError as exc:
                error = f"{type(exc).__name__}: {exc}"
                continue
            if response.status_code in RETRY_STATUS:
                error = f"HTTP {response.status_code}"
                continue
            if response.status_code == 404 and missing_ok:
                return None
            if response.status_code >= 400:
                raise SidofError(f"SIDOF answered HTTP {response.status_code} for {url}")
            try:
                payload = response.json()
            except ValueError as exc:
                raise SidofError(f"SIDOF returned invalid JSON for {url}") from exc
            if not isinstance(payload, dict):
                raise SidofError(f"Unexpected SIDOF payload for {url}")
            return payload
        raise SidofError(
            f"SIDOF is not responding ({error}) after {self.max_retries + 1} tries: {url}"
        )

    # ----------------------------------------------------------------- cache

    def _cache_file(self, kind: str, key: str) -> Path | None:
        if self.cache_dir is None:
            return None
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", key)
        return self.cache_dir / kind / f"{safe}.json"

    def _cached(self, kind: str, key: str) -> Any | None:
        memo_key = f"{kind}/{key}"
        if memo_key in self._memo:
            return self._memo[memo_key]
        path = self._cache_file(kind, key)
        if path is not None and path.exists():
            self.cache_hits += 1
            value = json.loads(path.read_text(encoding="utf-8"))
            self._memo[memo_key] = value
            return value
        return None

    def _store(self, kind: str, key: str, value: Any, *, persist: bool) -> None:
        self._memo[f"{kind}/{key}"] = value
        path = self._cache_file(kind, key)
        if persist and path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def _settled(self, day: date) -> bool:
        """Past enough that late editions and corrections are unlikely to change it."""
        return day < self.today - timedelta(days=3)

    # ------------------------------------------------------------- endpoints

    def indicator_range(self, code: int, start: date, end: date) -> list[dict[str, str]]:
        """Raw values of one SIDOF indicator between two DOF dates (inclusive).

        Returns ``[{"fecha": "DD-MM-YYYY", "valor": "..."}]`` filtered to ``code``,
        in the order SIDOF sends them (not always sorted).
        """
        key = f"{code}_{start.isoformat()}_{end.isoformat()}"
        cached = self._cached("indicadores", key)
        if cached is not None:
            return cached
        payload = self.get_json(
            f"indicadores/{code}/{to_sidof(start)}/{to_sidof(end)}", missing_ok=True
        )
        rows = [
            {"fecha": str(r.get("fecha", "")), "valor": str(r.get("valor", ""))}
            for r in (payload or {}).get("ListaIndicadores") or []
            if int(r.get("codTipoIndicador", -1)) == code
        ]
        self._store("indicadores", key, rows, persist=self._settled(end))
        return rows

    def day_notes(self, day: date) -> list[NoteRow]:
        """Relevant notes (Banco de México, INEGI, CONASAMI, STPS) published on ``day``."""
        key = day.isoformat()
        cached = self._cached("notas", key)
        if cached is not None:
            return [NoteRow.from_json(r) for r in cached]
        payload = self.get_json(f"notas/{to_sidof(day)}") or {}
        rows = parse_day(payload, day)
        self._store("notas", key, [r.to_json() for r in rows], persist=self._settled(day))
        return rows

    def note(self, code: int) -> Note:
        """Title and plain text of one note (immutable once published, so always cached)."""
        key = str(code)
        cached = self._cached("nota", key)
        if cached is None:
            payload = self.get_json(f"notas/nota/{code}") or {}
            raw = payload.get("Nota")
            if not isinstance(raw, dict) or not raw.get("codNota"):
                raise SidofError(f"There is no DOF note with code {code}")
            cached = {
                "code": int(raw["codNota"]),
                "title": " ".join(str(raw.get("titulo") or "").split()),
                "day": from_sidof(str(raw["fecha"])).isoformat(),
                "agency": _clean(raw.get("codOrgaDos")) or "",
                "text": html_to_text(str(raw.get("cadenaContenido") or "")),
            }
            self._store("nota", key, cached, persist=True)
        return Note(
            code=int(cached["code"]),
            title=cached["title"],
            day=date.fromisoformat(cached["day"]),
            agency=cached["agency"],
            text=cached["text"],
        )
