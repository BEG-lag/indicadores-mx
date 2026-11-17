"""Readers for the DOF notes behind each indicator.

Every parser works on the plain text of a note (``html_to_text`` of SIDOF's
``cadenaContenido``) and is tested against real notes in ``tests/fixtures``. The
INPC and UDI readers are ports of the ones written and verified in the sibling
project aumento-renta (``src/data/dof.ts``), including the formats Banco de
México has used over the years.

Pure functions only: the network lives in ``sidof.py``.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date

from .dates import month_number

_STYLE = re.compile(r"<(style|script)\b.*?</\1\s*>", re.S | re.I)
_TAG = re.compile(r"<[^>]*>")
_SPACE = re.compile(r"\s+")


def html_to_text(markup: str) -> str:
    """Strips tags, styles and scripts, decodes entities and collapses whitespace."""
    text = _STYLE.sub(" ", markup)
    text = _TAG.sub(" ", text)
    text = html.unescape(text).replace("\xa0", " ")
    return _SPACE.sub(" ", text).strip()


def dof_note_url(note: int, day: date) -> str:
    """Official page of a note. The bare domain is used: www. served a wrong certificate."""
    return f"https://dof.gob.mx/nota_detalle.php?codigo={note}&fecha={day.strftime('%d/%m/%Y')}"


def is_correction_title(title: str) -> bool:
    return bool(re.search(r"aclarat|aclaraci|fe de erratas", title, re.I))


# ----------------------------------------------------------------- titles

# Titles are matched from their start, so notes that only mention an indicator ("Participantes
# en la determinación de las tasas de interés interbancarias de equilibrio", "Fe de erratas
# a las Tasas ...") are not taken for it.
_FIX_TITLE = re.compile(r"^\s*tipo de cambio para solventar obligaciones", re.I)
_TIIE_TITLE = re.compile(r"^\s*tasas? de inter[eé]s interbancarias? de equilibrio", re.I)
_FONDEO = re.compile(r"fondeo", re.I)
_UDI_TITLE = re.compile(r"^\s*valor de la unidad de inversi", re.I)
_INPC_TITLE = re.compile(r"precios al consumidor", re.I)
_INPC_MONTHLY_TITLE = re.compile(r"^\s*[íi]ndice nacional de precios al consumidor\.?\s*$", re.I)


def is_fix_title(title: str) -> bool:
    return bool(_FIX_TITLE.search(title))


def is_tiie_title(title: str) -> bool:
    """TIIE 28, 91 and 182 (one note since 2008; one note per term before)."""
    return bool(_TIIE_TITLE.search(title)) and not _FONDEO.search(title)


def is_fondeo_title(title: str) -> bool:
    return bool(_TIIE_TITLE.search(title)) and bool(_FONDEO.search(title))


def is_udi_title(title: str) -> bool:
    return bool(_UDI_TITLE.search(title))


def is_inpc_title(title: str) -> bool:
    """Any INPC note, corrections included."""
    return bool(_INPC_TITLE.search(title))


def is_inpc_monthly_title(title: str) -> bool:
    """The monthly publication itself ("Índice nacional de precios al consumidor.")."""
    return bool(_INPC_MONTHLY_TITLE.search(title))


# ---------------------------------------------------------------- numbers


def _number(raw: str) -> str:
    """Remove thousands separators and stray spaces inside a printed number."""
    return re.sub(r"[\s,]", "", raw)


# ----------------------------------------------------------------- FIX

_FIX_VALUE = re.compile(
    r"tipo de cambio\b.{0,400}?fue de\s*(?:N\s?\$|\$)\s*(\d{1,3}(?:,\d{3})*\.\s?\d{2,4})(?!\d)",
    re.I | re.S,
)


def parse_fix(text: str) -> str | None:
    """The peso-dollar rate printed in a "Tipo de cambio para solventar obligaciones" note.

    Returns the number as printed (``"18.6188"``; ``"4.9950"`` for the nuevos pesos of
    1993 to 1995, printed as ``N$ 4.9950``).
    """
    match = _FIX_VALUE.search(text)
    return _number(match.group(1)) if match else None


# ----------------------------------------------------------------- TIIE

# The value may come split across text runs ("11.6 394 por ciento", DOF 2024-01-08).
_RATE = r"(\d{1,3}\.(?:\s?\d){1,6})\s*(?:%|por\s*ciento)"
_TIIE_TERM = re.compile(
    r"plazo de\s+(\d{2,3})\s+d[ií]as[^%]{0,160}?fue(?:\s+de)?\s+" + _RATE,
    re.I,
)
_TIIE_SINGLE = re.compile(r"\b(\d{2,3})\s+d[ií]as[^%]{0,200}?fue(?:\s+de)?\s+" + _RATE, re.I)


# "a plazos de 28 y 91 días obtenidas el día de hoy, fueron de 11.5025 y 11.4750 por ciento,
# respectivamente" (DOF 2024-01-02).
_NUM = r"\d{1,3}\.(?:\s?\d){1,6}"
_TIIE_LIST = re.compile(
    r"plazos de\s+((?:\d{2,3}\s*(?:,|\by\b)\s*)+\d{2,3})\s+d[ií]as[^%]{0,200}?fueron(?:\s+de)?\s+"
    r"((?:" + _NUM + r"\s*%?\s*(?:,|\by\b)\s*)+" + _NUM + r")\s*(?:%|por\s*ciento)",
    re.I,
)


def parse_tiie(text: str) -> dict[int, str]:
    """TIIE values by term in days, as printed (``{28: "6.5147"}``).

    Banco de México shortens or extends the term when the maturity falls on a holiday,
    so a note may print 29 days instead of 28, or 180 instead of 182; the caller maps
    those to the nominal term.
    """
    found: dict[int, str] = {}
    for term, value in _TIIE_TERM.findall(text):
        found.setdefault(int(term), _number(value))
    for terms, values in _TIIE_LIST.findall(text):
        days = re.findall(r"\d{2,3}", terms)
        rates = re.findall(_NUM, values)
        if len(days) == len(rates):
            for term, value in zip(days, rates, strict=True):
                found.setdefault(int(term), _number(value))
    if not found:
        for term, value in _TIIE_SINGLE.findall(text):
            found.setdefault(int(term), _number(value))
    return found


_FONDEO_VALUE = re.compile(r"fondeo[^%]{0,240}?fue(?:\s+de)?\s+" + _RATE, re.I)


def parse_fondeo(text: str) -> str | None:
    match = _FONDEO_VALUE.search(text)
    return _number(match.group(1)) if match else None


# ----------------------------------------------------------------- dates

_SIGNED_ON = re.compile(r"\ba\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})", re.I)


def signed_on(text: str) -> date | None:
    """The date in the closing "Ciudad de México, a 12 de noviembre de 2026" line."""
    matches = _SIGNED_ON.findall(text)
    for day, month_name, year in reversed(matches):
        month = month_number(month_name)
        if month is None:
            continue
        try:
            return date(int(year), month, int(day))
        except ValueError:
            continue
    return None


# ----------------------------------------------------------------- INPC


@dataclass(frozen=True, slots=True)
class InpcMonthly:
    month: str
    value: str
    variation: str | None = None
    previous_month: str | None = None
    previous_value: str | None = None


_MONTHLY = re.compile(
    r"segunda quincena de julio de 2018\s*=\s*100,?\s+el [ÍI]ndice Nacional de Precios al "
    r"Consumidor del mes de ([a-záéíóú]+)\s+de\s+(\d{4})\s*,?\s+es(?:\s+de)?\s+(\d{2,3}\.\d{3})",
    re.I,
)
_VARIATION = re.compile(
    r"variaci[óo]n de\s+(-?\d+\.\d+)\s+por ciento respecto del [íi]ndice correspondiente al mes "
    r"de ([a-záéíóú]+)\s+de\s+(\d{4})\s*,?\s+que fue de\s+(\d{2,3}\.\d{3})",
    re.I,
)


def parse_inpc_monthly(text: str) -> InpcMonthly | None:
    """Monthly INPC from an INEGI note. For a "Nota aclaratoria", the "Debe decir" text wins."""
    body = re.split(r"Debe decir\s*:?", text, flags=re.I)[-1]
    matches = list(_MONTHLY.finditer(body))
    if not matches:
        return None
    m = matches[-1]
    month = month_number(m.group(1))
    if month is None:
        return None
    result = InpcMonthly(month=f"{int(m.group(2)):04d}-{month:02d}", value=m.group(3))
    rest = body[m.end() :]
    v = _VARIATION.search(rest)
    if v and v.start() < 400:
        prev = month_number(v.group(2))
        return InpcMonthly(
            month=result.month,
            value=result.value,
            variation=v.group(1),
            previous_month=f"{int(v.group(3)):04d}-{prev:02d}" if prev else None,
            previous_value=v.group(4),
        )
    return result


# ----------------------------------------------------------------- UDIS

# Banco de México has printed the dates as "11-noviembre-2026", "12- noviembre-2009",
# "11-julio-20", "11 de agosto de 2022" and "26/02/2020", and a few notes split a value
# across text runs ("6.4 51423"), so single spaces inside the decimals are tolerated.
_VALUE = r"(\d{1,2}\.(?:\s?\d){6})(?!\d)"
_NAMED_ROW = re.compile(
    r"\b(\d{1,2})\s*(?:-|\s+de\s+)\s*([a-záéíóú]+)\s*(?:-|\s+de\s+)\s*(\d{4}|\d{2})\s+" + _VALUE,
    re.I,
)
_NUMERIC_ROW = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\s+" + _VALUE)


def _full_year(text: str) -> int:
    year = int(text)
    if len(text) == 4:
        return year
    return 2000 + year if year < 95 else 1900 + year


def parse_udi_table(text: str) -> dict[date, str]:
    """The daily table of a Banco de México "Valor de la unidad de inversión" note."""
    rows: dict[date, str] = {}

    def add(year: int, month: int | None, day: int, raw: str) -> None:
        if month is None:
            return
        try:
            rows[date(year, month, day)] = re.sub(r"\s", "", raw)
        except ValueError:
            return

    for d, mon, y, value in _NAMED_ROW.findall(text):
        add(_full_year(y), month_number(mon), int(d), value)
    for d, mon, y, value in _NUMERIC_ROW.findall(text):
        add(int(y), int(mon), int(d), value)
    return dict(sorted(rows.items()))


# ----------------------------------------------------------------- UMA

_MONEY = r"\$\s*([\d,]+\.\d{2})"
_UMA = re.compile(
    r"diario[^$]{0,160}?"
    + _MONEY
    + r"[^$]{0,160}?mensual[^$]{0,80}?"
    + _MONEY
    + r"[^$]{0,160}?anual[^$]{0,80}?"
    + _MONEY,
    re.I,
)
_IN_FORCE = re.compile(
    r"(?:vigentes?|vigencia|regir(?:[aá]n)?)\s+a partir del\s+(\d{1,2})\s*[º°o]?\.?\s+de\s+"
    r"([a-záéíóú]+)\s+(?:de|del año)\s+(\d{4})",
    re.I,
)


@dataclass(frozen=True, slots=True)
class UmaValues:
    in_force: date
    daily: str
    monthly: str
    annual: str


def _in_force(text: str) -> date | None:
    """The latest "vigentes a partir del 1o. de febrero de 2026" date in the text.

    Notes also cite the previous period ("se publicaron los valores vigentes a partir del
    1 de febrero de 2025"), so the latest date is the one the note sets.
    """
    found: list[date] = []
    for day, month_name, year in _IN_FORCE.findall(text):
        month = month_number(month_name)
        if month is None:
            continue
        try:
            found.append(date(int(year), month, int(day)))
        except ValueError:
            continue
    return max(found) if found else None


def parse_uma(text: str) -> UmaValues | None:
    """Daily, monthly and annual UMA from INEGI's "Unidad de medida y actualización" note."""
    match = _UMA.search(text)
    start = _in_force(text)
    if not match or start is None:
        return None
    daily, monthly, annual = (_number(g) for g in match.groups())
    return UmaValues(in_force=start, daily=daily, monthly=monthly, annual=annual)


# ----------------------------------------------------------------- minimum wage

# How CONASAMI has worded the amounts since the Northern Border Free Zone was created:
#   2019: "...Zona libre de la Frontera Norte será de 176.72 pesos diarios ... para el área
#          de Salarios Mínimos Generales será de 102.68 pesos diarios"
#   2020 to 2024: "será de 213.39 pesos diarios por jornada diaria de trabajo en el área
#          geográfica de la Zona Libre de la Frontera Norte ... y para el Resto del país el
#          salario mínimo general será de 141.70 pesos diarios"
#   2025: "... y para La Zona del Salario Mínimo General (ZSMG) el salario mínimo será de 278.80"
#   2026: "Zona del Salario Mínimo General (ZSMG), con lo que será de 315.04 pesos ... Zona Libre
#          de la Frontera Norte (ZLFN), con lo que será de 440.87 pesos"
_ZONE_GENERAL = re.compile(
    r"(?:Resto del pa[ií]s|Zona del Salario M[ií]nimo General|[áa]rea de Salarios M[ií]nimos "
    r"Generales)[^.;$]{0,70}?ser[áa] de\s+\$?\s*(\d{2,3}\.\d{2})\s*pesos",
    re.I,
)
_ZONE_ZLFN = (
    re.compile(
        r"(\d{2,3}\.\d{2})\s*pesos diarios por jornada diaria de trabajo en el [áa]rea "
        r"geogr[áa]fica de la Zona Libre de la Frontera Norte",
        re.I,
    ),
    re.compile(
        r"Zona Libre de la Frontera Norte(?:\s*\(ZLFN\))?(?:,\s*con lo que)?\s+ser[áa] de\s+"
        r"\$?\s*(\d{2,3}\.\d{2})\s*pesos",
        re.I,
    ),
)


@dataclass(frozen=True, slots=True)
class MinimumWage:
    in_force: date
    general: str
    zlfn: str | None


def parse_minimum_wage(text: str) -> MinimumWage | None:
    """General and ZLFN daily minimum wage from a CONASAMI resolution (2019 format onward).

    Older resolutions (geographic areas A, B and C) are curated by hand and checked
    with ``pipeline.value_in_text`` instead.
    """
    general = _ZONE_GENERAL.search(text)
    start = _in_force(text)
    if not general or start is None:
        return None
    zlfn = next((m for p in _ZONE_ZLFN if (m := p.search(text))), None)
    return MinimumWage(
        in_force=start, general=general.group(1), zlfn=zlfn.group(1) if zlfn else None
    )


# Geographic areas (until September 2015): "...serán los que se señalan a continuación:
# Pesos Área geográfica "A" Área geográfica "B" Área geográfica "C" $ 59.82 $ 58.13 $ 56.70".
# The text export sometimes splits the accented capital ("A rea geográfica").
_AREAS = re.compile(
    r"se[ñn]alan a continuaci[óo]n:?\s*Pesos\s*((?:[ÁA]\s?rea geogr[áa]fica\s*\"\s*[ABC]\s*\"\s*)+)"
    r"((?:\$\s*\d{1,3}(?:,\d{3})*\.\d{2}\s*)+)",
    re.I,
)


def parse_minimum_wage_areas(text: str) -> tuple[date, dict[str, str]] | None:
    """In-force date and general minimum wage by geographic area (resolutions to 2015)."""
    match = _AREAS.search(text)
    start = _in_force(text)
    if not match or start is None:
        return None
    letters = re.findall(r"\"\s*([ABC])\s*\"", match.group(1))
    values = [_number(v) for v in re.findall(r"\$\s*([\d,]+\.\d{2})", match.group(2))]
    if len(letters) != len(values):
        return None
    return start, dict(zip(letters, values, strict=True))
