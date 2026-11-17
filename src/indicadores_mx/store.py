"""Canonical data files: ``data/<series>.json``, one observation per line.

The files hold no timestamps and are written in a deterministic order, so a
scheduled run that finds nothing new leaves the working tree clean and a commit
appears only when a value is added or corrected. Values are kept as the decimal
text the DOF prints (normalized: no spaces, no percent sign), never as floats.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .catalog import BY_ID, Series

SCHEMA_VERSION = 1
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"


@dataclass(frozen=True, slots=True)
class DofRef:
    """A DOF note: publication date and SIDOF ``codNota``."""

    day: date
    note: int

    def to_json(self) -> dict[str, Any]:
        return {"date": self.day.isoformat(), "note": self.note}

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> DofRef:
        return cls(day=date.fromisoformat(data["date"]), note=int(data["note"]))


@dataclass(frozen=True, slots=True)
class Obs:
    """One observation.

    ``key`` is an ISO date (daily and step series) or ``YYYY-MM`` (monthly series).
    ``checked`` means the value was compared with the text of its DOF note and matched.
    ``origin`` is where the number was read when it differs from the series default:
    ``sidof`` (SIDOF indicator API), ``dof`` (the note text), ``inegi`` (INEGI open data)
    or ``derived``.
    """

    key: str
    value: str
    dof: DofRef | None = None
    checked: bool = False
    correction: DofRef | None = None
    origin: str | None = None
    remark: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        data: dict[str, Any] = {"date": self.key, "value": self.value}
        if self.dof is not None:
            data["dof"] = self.dof.to_json()
        if self.checked:
            data["checked"] = True
        if self.correction is not None:
            data["correction"] = self.correction.to_json()
        if self.origin is not None:
            data["origin"] = self.origin
        if self.remark is not None:
            data["remark"] = self.remark
        data.update(self.extra)
        return data

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Obs:
        known = {"date", "value", "dof", "checked", "correction", "origin", "remark"}
        return cls(
            key=data["date"],
            value=data["value"],
            dof=DofRef.from_json(data["dof"]) if data.get("dof") else None,
            checked=bool(data.get("checked", False)),
            correction=DofRef.from_json(data["correction"]) if data.get("correction") else None,
            origin=data.get("origin"),
            remark=data.get("remark"),
            extra={k: v for k, v in data.items() if k not in known},
        )

    def with_(self, **changes: Any) -> Obs:
        return replace(self, **changes)


def normalize_value(raw: str, decimals: int | None = None) -> str:
    """``" 7. 8425 %."`` to ``"7.8425"``; optionally pad trailing zeros to ``decimals``.

    Raises ``ValueError`` if what remains is not a plain non-negative decimal.
    """
    text = raw.strip().rstrip(".").replace("%", "").replace(" ", "").replace(",", "")
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"not a number: {raw!r}") from exc
    if not number.is_finite() or number < 0 or "e" in text.lower():
        raise ValueError(f"not a plain non-negative decimal: {raw!r}")
    if decimals is not None and "." in text:
        whole, frac = text.split(".")
        if len(frac) < decimals:
            text = f"{whole}.{frac.ljust(decimals, '0')}"
    elif decimals is not None and decimals > 0:
        text = f"{text}.{'0' * decimals}"
    return text


def path_for(series_id: str, data_dir: Path = DATA_DIR) -> Path:
    return data_dir / f"{series_id}.json"


def load(series_id: str, data_dir: Path = DATA_DIR) -> list[Obs]:
    path = path_for(series_id, data_dir)
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [Obs.from_json(o) for o in payload["observations"]]


def load_all(data_dir: Path = DATA_DIR) -> dict[str, list[Obs]]:
    return {s: load(s, data_dir) for s in BY_ID}


def serialize(series: Series, observations: list[Obs]) -> str:
    lines = [
        json.dumps(o.to_json(), ensure_ascii=False, separators=(",", ":")) for o in observations
    ]
    body = ",\n    ".join(lines)
    head = (
        "{\n"
        f'  "schema_version": {SCHEMA_VERSION},\n'
        f'  "series": "{series.id}",\n'
        '  "observations": [\n'
    )
    return f"{head}    {body}\n  ]\n}}\n" if lines else f"{head.rstrip()}\n  ]\n}}\n"


def write(series_id: str, observations: list[Obs], data_dir: Path = DATA_DIR) -> bool:
    """Write the file only if its content changes. Returns True when it did."""
    series = BY_ID[series_id]
    ordered = sorted(observations, key=lambda o: o.key)
    keys = [o.key for o in ordered]
    if len(keys) != len(set(keys)):
        raise ValueError(f"{series_id}: duplicate dates")
    text = serialize(series, ordered)
    path = path_for(series_id, data_dir)
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    if old == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True
