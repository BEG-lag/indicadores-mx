"""Record the SIDOF responses the offline tests replay (network; run by hand).

    uv run python scripts/record_fixtures.py

Writes ``tests/fixtures/sidof/``:

* ``indicadores/<code>.json``: real indicator rows for a window around 13 Nov 2026.
  The test transport filters them by the requested range, like SIDOF does.
* ``notas/<DD-MM-YYYY>.json``: real day indexes, trimmed to the Banco de México and
  INEGI rows plus one separator row and one aviso (the full indexes weigh 100 to
  200 KB each and the rest is irrelevant to this project).
* ``nota/<code>.json``: real notes, untrimmed (5 to 10 KB each).
* ``nota/<code>.json`` for a few historical notes used by the parser tests.
"""

from __future__ import annotations

import json
import time
from datetime import date, timedelta
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "fixtures" / "sidof"
BASE = "https://sidof.segob.gob.mx/dof/sidof"
HEADERS = {
    "User-Agent": "indicadores-mx/1.0.0 (+https://github.com/BEG-lag/indicadores-mx)",
    "Accept": "application/json, */*;q=0.8",
}
WINDOW = (date(2026, 11, 10), date(2026, 11, 13))
INDICATORS = {
    158: (date(2026, 10, 26), date(2026, 11, 13)),
    159: (date(2026, 9, 20), date(2026, 11, 25)),
    165: (date(2026, 10, 26), date(2026, 11, 13)),
    166: (date(2026, 10, 26), date(2026, 11, 13)),
    174: (date(2026, 10, 26), date(2026, 11, 13)),
    175: (date(2026, 10, 26), date(2026, 11, 13)),
}
HISTORICAL_NOTES = [
    4865462,  # FIX 1995-01-02, printed in nuevos pesos (N$ 4.9950)
    2049214,  # FIX 2000-01-10
    4884436,  # TIIE 28, 1996-05-15, "por ciento"
    755580,  # TIIE 28, 2005-01-06, one note per term
    755581,  # TIIE 91, 2005-01-06
    2049217,  # UDI table, 2000-01-10, "11-enero-2000" rows
    5537424,  # INPC August 2018, published with a typo (100.942)
    5537585,  # INPC August 2018, nota aclaratoria (100.492)
    5778072,  # UMA 2026
    5713424,  # TIIE 2024-01-02: "a plazos de 28 y 91 días ... fueron de X y Y por ciento"
    5713935,  # TIIE 2024-01-08: 29-day term, value split across runs ("11.6 394")
    5741355,  # TIIE 2024-10-18: 180-day term instead of 182
    5756456,  # FIX determined 2025-05-02 for Monday 5 May, published on the 6th
    5756459,  # FIX determined 2025-05-05, published on the 6th
    5420747,  # Nota aclaratoria: the 2016 minimum wage resolution omitted the amount
]
KEEP = ("BANCO DE MEXICO", "ESTADISTICA Y GEOGRAFIA")


def dmy(day: date) -> str:
    return day.strftime("%d-%m-%Y")


def get(client: httpx.Client, path: str) -> dict:
    time.sleep(1.0)
    response = client.get(f"{BASE}/{path}")
    response.raise_for_status()
    return response.json()


def trim_day(payload: dict) -> dict:
    out = dict(payload)
    for key in ("NotasMatutinas", "NotasVespertinas", "NotasExtraordinarias"):
        rows = payload.get(key) or []
        kept = [r for r in rows if any(k in str(r.get("codOrgaDos", "")).upper() for k in KEEP)]
        separator = next((r for r in rows if not r.get("titulo")), None)
        aviso = next((r for r in rows if r.get("tipoNota") == "AVISO"), None)
        out[key] = [r for r in (separator, aviso) if r] + kept
    return out


def main() -> None:
    with httpx.Client(headers=HEADERS, timeout=30) as client:
        for code, (start, end) in INDICATORS.items():
            payload = get(client, f"indicadores/{code}/{dmy(start)}/{dmy(end)}")
            write(OUT / "indicadores" / f"{code}.json", payload)
        codes: list[int] = []
        day = WINDOW[0]
        while day <= WINDOW[1]:
            payload = trim_day(get(client, f"notas/{dmy(day)}"))
            write(OUT / "notas" / f"{dmy(day)}.json", payload)
            for key in ("NotasMatutinas", "NotasVespertinas", "NotasExtraordinarias"):
                for row in payload.get(key) or []:
                    title = str(row.get("titulo") or "").lower()
                    if any(
                        k in title
                        for k in (
                            "tipo de cambio",
                            "interbancaria",
                            "unidad de inversi",
                            "precios al consumidor",
                        )
                    ):
                        codes.append(int(row["codNota"]))
            day += timedelta(days=1)
        for code in [*codes, *HISTORICAL_NOTES]:
            write(OUT / "nota" / f"{code}.json", get(client, f"notas/nota/{code}"))
    print(f"wrote fixtures under {OUT.relative_to(ROOT)}")


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
