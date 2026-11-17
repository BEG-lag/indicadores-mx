"""Date helpers.

The DOF is published in Mexico City, so "today" always means today in
``America/Mexico_City`` (UTC-6 all year since 2022), wherever the code runs. The
``INDICADORES_TODAY`` environment variable pins it (tests, reproducible builds).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

MX_TZ = ZoneInfo("America/Mexico_City")

MONTHS_ES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def today_mx() -> date:
    pinned = os.environ.get("INDICADORES_TODAY")
    if pinned:
        return date.fromisoformat(pinned)
    return datetime.now(MX_TZ).date()


def to_sidof(day: date) -> str:
    """SIDOF URLs take ``DD-MM-YYYY``."""
    return day.strftime("%d-%m-%Y")


def from_sidof(text: str) -> date:
    return datetime.strptime(text.strip(), "%d-%m-%Y").date()


def dof_url_date(day: date) -> str:
    """dof.gob.mx note pages take ``DD/MM/YYYY``."""
    return day.strftime("%d/%m/%Y")


def iter_days(start: date, end: date) -> Iterator[date]:
    for offset in range((end - start).days + 1):
        yield start + timedelta(days=offset)


def add_months(month: str, n: int) -> str:
    """``"2026-10"`` plus ``n`` months."""
    year, mon = (int(p) for p in month.split("-"))
    index = year * 12 + (mon - 1) + n
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def month_number(name: str) -> int | None:
    return MONTHS_ES.get(name.strip().lower())
