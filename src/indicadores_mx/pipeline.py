"""Fetch, cross-check and merge the official values.

Two modes share the same logic:

* ``backfill`` rebuilds every daily and monthly series from the start of its
  official record (caching responses on disk, so it can be resumed).
* ``update`` re-reads a short recent window, appends what is new and verifies
  every new value against the text of its DOF note.

Nothing is written while any problem is open: a SIDOF value that disagrees with
its DOF note, a value that changed after publication, a gap in the UDI calendar, a
printed INPC variation that does not match the indexes. The run fails with exit
code 1 and the scheduled workflow commits nothing.

The minimum wage and UMA series are curated by hand (one value a year) and checked
against the text of their DOF notes by :func:`verify_steps`.
"""

from __future__ import annotations

import csv
import io
import re
import subprocess
import zipfile
from bisect import bisect_left, bisect_right
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import httpx

from . import dof
from .catalog import BY_ID, INEGI_INPC_CSV
from .dates import add_months, from_sidof, iter_days
from .sidof import USER_AGENT, NoteRow, Sidof
from .store import DofRef, Obs, normalize_value

UDIS_START = date(1995, 4, 4)
FIRST_DOF_INPC_MONTH = "2018-08"  # first month published in the DOF on the 2018 base
INEGI_CONCEPT = (
    "Índice nacional de precios al consumidor (mensual), Resumen, Subíndices subyacente y "
    "complementarios, Precios al Consumidor (INPC)"
)
INPC_DAYS = [10, 9, 11, 8, 12, 7, 13, 6, 14, 15]  # CFF art. 20: within the first ten days

DAILY_IDS = ("fix", "tiie-28", "tiie-91", "tiie-182", "tiie-fondeo")
TIIE_TERMS = {"tiie-28": 28, "tiie-91": 91, "tiie-182": 182}
# Terms Banco de México has printed for each nominal TIIE when a maturity fell on a holiday.
TIIE_FAMILIES = {28: range(26, 31), 91: range(88, 94), 182: range(178, 186)}


# Series whose DOF notes predate SIDOF's indicator record and are worth reading: SIDOF
# has the 28-day TIIE from 2004 and the 91-day TIIE from 1997, the DOF from 1995.
READ_BEFORE_SIDOF = {"tiie-28", "tiie-91"}


def family(term: int) -> int | None:
    return next((nominal for nominal, terms in TIIE_FAMILIES.items() if term in terms), None)


# Disagreements between SIDOF and the DOF note, investigated one by one during the backfill
# (docs/fuentes.md, section 5). KNOWN: the DOF note is right and SIDOF is not; the value
# printed in the note is used. CORRECTIONS: the note printed a wrong figure and a later DOF
# note (fe de erratas, aclaración, nota aclaratoria) fixed it; the corrected value is used
# and both notes are kept.
KNOWN: dict[tuple[str, str], str] = {
    ("tiie-91", "2002-05-02"): (
        "El SIDOF registra 7.12; la nota del DOF de ese día imprime 6.8500 y ninguna nota "
        "posterior lo corrige. Se usa el valor de la nota."
    ),
}


@dataclass(frozen=True, slots=True)
class Correction:
    value: str
    ref: DofRef
    remark: str


CORRECTIONS: dict[tuple[str, str], Correction] = {
    ("fix", "1995-08-01"): Correction(
        "6.1142",
        DofRef(date(1995, 8, 2), 4878907),
        "La nota del DOF imprimió N$6.1146; una aclaración del Banco de México publicada el "
        "2 de agosto de 1995 lo corrigió a N$6.1142.",
    ),
    ("tiie-28", "2024-02-21"): Correction(
        "11.4925",
        DofRef(date(2024, 2, 23), 5717861),
        "La nota del DOF imprimió 11.9425%; una nota aclaratoria del 23 de febrero de 2024 lo "
        "corrigió a 11.4925%.",
    ),
    ("udis", "2005-12-22"): Correction(
        "3.631552",
        DofRef(date(2005, 12, 13), 2101984),
        "La nota del DOF del 9 de diciembre de 2005 imprimió 3.621552; una fe de erratas del 13 "
        "de diciembre de 2005 lo corrigió a 3.631552.",
    ),
}

# Before 1996 the dates in SIDOF and in the DOF do not always line up (in 1993 the notes
# were sometimes signed the day they were published and sometimes the day before). A
# disagreement in those years is documented on the value instead of stopping the run.
TOLERANT_BEFORE = date(1996, 1, 1)


@dataclass
class Run:
    """Shared state of one pipeline run."""

    sidof: Sidof
    today: date
    log: Callable[[str], None] = print
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)

    def problem(self, message: str) -> None:
        self.problems.append(message)
        self.log(f"  PROBLEM {message}")

    def warn(self, message: str) -> None:
        self.warnings.append(message)
        self.log(f"  warning {message}")

    def count(self, key: str, n: int = 1) -> None:
        self.stats[key] = self.stats.get(key, 0) + n


# ---------------------------------------------------------------- matching


def _term_in_title(title: str) -> int | None:
    match = re.search(r"\b(\d{2,3})\s*d[ií]as", title, re.I)
    return int(match.group(1)) if match else None


def is_banxico(row: NoteRow) -> bool:
    return "BANCO DE MEXICO" in row.agency.upper().replace("É", "E")


def is_inegi(row: NoteRow) -> bool:
    return bool(re.search(r"ESTAD[IÍ]STICA Y GEOGRAF", row.agency, re.I))


def rows_on(run: Run, day: date) -> list[NoteRow]:
    """The day's relevant notes, minus rows SIDOF lists under a date they do not carry.

    The index for 2000-02-02 and 2000-02-07 holds notes dated a year later (2001); those
    rows are skipped, so no value is linked to a note of another day.
    """
    rows = run.sidof.day_notes(day)
    kept = [r for r in rows if r.day == day]
    if len(kept) != len(rows):
        run.count("index:rows-with-another-date")
    return kept


def notes_for(series_id: str, rows: Iterable[NoteRow]) -> list[NoteRow]:
    """DOF notes of ``rows`` that publish ``series_id``; term-specific TIIE notes first."""
    rows = [r for r in rows if is_banxico(r)]
    if series_id == "fix":
        return [r for r in rows if dof.is_fix_title(r.title)]
    if series_id == "tiie-fondeo":
        return [r for r in rows if dof.is_fondeo_title(r.title)]
    term = TIIE_TERMS[series_id]
    tiie = [r for r in rows if dof.is_tiie_title(r.title) and not dof.is_correction_title(r.title)]
    specific = [r for r in tiie if family(_term_in_title(r.title) or 0) == term]
    generic = [r for r in tiie if _term_in_title(r.title) is None]
    return specific + generic


def _concerns(series_id: str, row: NoteRow) -> bool:
    title = row.title.lower()
    if series_id == "fix":
        return "tipo de cambio para solventar" in title
    if series_id == "tiie-fondeo":
        return "fondeo" in title
    return "interbancaria" in title and "equilibrio" in title and "fondeo" not in title


def parse_note_value(series_id: str, text: str) -> tuple[str, int | None] | None:
    """The value a note prints for a series and, for the TIIE, the term it states."""
    if series_id == "fix":
        value = dof.parse_fix(text)
        return (value, None) if value else None
    if series_id == "tiie-fondeo":
        value = dof.parse_fondeo(text)
        return (value, None) if value else None
    nominal = TIIE_TERMS[series_id]
    terms = dof.parse_tiie(text)
    if nominal in terms:
        return terms[nominal], nominal
    for term, value in terms.items():
        if family(term) == nominal:
            return value, term
    return None


def same(a: str, b: str) -> bool:
    return Decimal(a) == Decimal(b)


# ---------------------------------------------------------------- SIDOF values


def sidof_values(run: Run, series_id: str, start: date, end: date) -> dict[date, set[str]]:
    """Every SIDOF value of a series between two dates, normalized; conflicts kept as sets."""
    series = BY_ID[series_id]
    assert series.sidof_code is not None
    out: dict[date, set[str]] = {}
    year = start.year
    while year <= end.year:
        chunk_start = max(start, date(year, 1, 1))
        chunk_end = min(end, date(year, 12, 31))
        for row in run.sidof.indicator_range(series.sidof_code, chunk_start, chunk_end):
            day = from_sidof(row["fecha"])
            try:
                value = normalize_value(row["valor"], series.decimals)
            except ValueError:
                run.problem(f"{series_id} {day}: SIDOF value {row['valor']!r} is not a number")
                continue
            if row["valor"].strip() != value and not row["valor"].strip().startswith(value):
                run.count(f"{series_id}:normalized")
            out.setdefault(day, set()).add(value)
        year += 1
    return out


# ---------------------------------------------------------------- daily series


@dataclass
class DailyPlan:
    """Which dates to compare against the note text."""

    verify_all_after: date
    verify_first_of_month: bool = True
    verify_all: bool = False
    verify_all_before: date | None = None

    def wants(self, day: date, first_in_month: bool) -> bool:
        if self.verify_all or day >= self.verify_all_after:
            return True
        if self.verify_all_before is not None and day < self.verify_all_before:
            return True
        return self.verify_first_of_month and first_in_month


def build_daily(
    run: Run,
    series_id: str,
    values: dict[date, set[str]],
    scan_days: Iterable[date],
    plan: DailyPlan,
) -> list[Obs]:
    """Merge SIDOF values with their DOF notes for one daily series.

    A value normally appears in the DOF on the day it applies, which is also its SIDOF
    date. When the DOF does not publish on a banking day (5 May 2025 and 2026, for
    example), the value for that day appears in the next edition next to the following
    day's, so that edition holds two notes: each one is matched to its SIDOF date by
    the value it prints.
    """
    decimals = BY_ID[series_id].decimals
    scan_days = list(scan_days)
    notes_by_day: dict[date, list[NoteRow]] = {}
    for day in scan_days:
        found = notes_for(series_id, rows_on(run, day))
        if found:
            notes_by_day[day] = found

    for day in scan_days:
        for row in run.sidof.day_notes(day):
            if is_banxico(row) and dof.is_correction_title(row.title) and _concerns(series_id, row):
                run.warn(f"{series_id}: correction note {row.code} ({row.day}): {row.title[:90]}")

    printed_cache: dict[int, str | None] = {}
    terms: dict[int, int] = {}

    misfiled: dict[int, date] = {}

    def printed_of(row: NoteRow) -> str | None:
        if row.code not in printed_cache:
            text = run.sidof.note(row.code).text
            signed = dof.signed_on(text)
            if signed is not None and not row.day - timedelta(days=12) <= signed <= row.day:
                # SIDOF filed the note under a date it does not belong to: 2016-03-01 lists
                # a note signed on 2017-02-28.
                misfiled[row.code] = signed
                printed_cache[row.code] = None
                return None
            parsed = parse_note_value(series_id, text)
            value = None
            if parsed is not None:
                value = normalize_value(parsed[0], decimals)
                if series_id == "fix" and Decimal(value) > 100:  # old pesos, before 1993
                    value = normalize_value(str(Decimal(value) / 1000), 4)
                if parsed[1] is not None and parsed[1] != TIIE_TERMS.get(series_id):
                    terms[row.code] = parsed[1]
            else:
                run.count(f"{series_id}:unparsed")
            printed_cache[row.code] = value
        return printed_cache[row.code]

    assigned: dict[date, NoteRow] = {}
    orphans: list[NoteRow] = []
    for day in sorted(notes_by_day):
        rows = notes_by_day[day]
        if len(rows) == 1:
            assigned[day] = rows[0]
            continue
        sidof = values.get(day, set())
        if sidof:
            match = next((r for r in rows if printed_of(r) in sidof), None)
        else:
            # No SIDOF value to match (TIIE before 2004): take the one note that prints this
            # term, if exactly one value is printed among the day's notes.
            printing = [r for r in rows if printed_of(r) is not None]
            distinct = {printed_of(r) for r in printing}
            match = printing[0] if len(distinct) == 1 else None
        if match is not None:
            assigned[day] = match
        orphans.extend(r for r in rows if r is not match)
    for day in sorted(values):
        if day in notes_by_day:
            continue
        for row in orphans:
            if day < row.day <= day + timedelta(days=7) and printed_of(row) in values[day]:
                assigned[day] = row
                orphans.remove(row)
                run.count(f"{series_id}:published-later")
                break
    for row in orphans:
        if printed_cache.get(row.code) is not None:
            run.warn(f"{series_id}: note {row.code} ({row.day}) matches no SIDOF value")

    # Days with a note but no SIDOF value: read the note when the series has no SIDOF
    # record yet (TIIE 28 before 2004, for example) or when SIDOF publishes the series
    # daily around that day (a gap). In weekly periods (TIIE 91 to 2008, TIIE 182 to 2023)
    # the shared daily note usually lacks the term, so it is not read.
    known_days = sorted(values)
    first_sidof = known_days[0] if known_days else None

    def dense(day: date) -> bool:
        lo = bisect_left(known_days, day - timedelta(days=7))
        hi = bisect_right(known_days, day + timedelta(days=7))
        return hi - lo >= 6

    all_days = sorted(set(values) | {d for d in assigned if d not in values})
    seen_months: set[tuple[int, int]] = set()
    out: list[Obs] = []
    for day in all_days:
        sidof = values.get(day, set())
        month = (day.year, day.month)
        first_in_month = month not in seen_months
        seen_months.add(month)
        row = assigned.get(day)
        ref = DofRef(day=row.day, note=row.code) if row is not None else None
        if not sidof and row is not None:
            before_sidof = series_id in READ_BEFORE_SIDOF and (
                first_sidof is None or day < first_sidof
            )
            if not (before_sidof or dense(day)):
                continue
            printed = printed_of(row)
            if printed is None:
                if not before_sidof:
                    run.warn(f"{series_id} {day}: note {row.code} has no readable value")
                continue
        else:
            need_note = len(sidof) != 1 or plan.wants(day, first_in_month)
            printed = printed_of(row) if row is not None and need_note else None
            if row is not None and row.code in misfiled:
                run.count(f"{series_id}:misfiled-note")
                run.warn(
                    f"{series_id} {day}: note {row.code} is signed {misfiled[row.code]}; "
                    "SIDOF filed it under the wrong date"
                )
                obs = _merge_daily(run, series_id, day, sidof, None, None)
                if obs is not None:
                    remark = (
                        f"La nota que el SIDOF lista ese día ({row.code}) está firmada el "
                        f"{misfiled[row.code].isoformat()}: es de otra fecha. El valor viene "
                        "del SIDOF."
                    )
                    out.append(obs.with_(remark=remark))
                continue
            if row is not None and need_note and printed is None:
                run.warn(f"{series_id} {day}: could not read the value in note {row.code}")
        obs = _merge_daily(run, series_id, day, sidof, ref, printed)
        if obs is not None and row is not None and row.code in terms:
            # The note states a shorter or longer term than the nominal one (holiday).
            obs = obs.with_(extra={"term_days": terms[row.code]})
            run.count(f"{series_id}:other-term")
        if obs is not None:
            out.append(obs)
    return out


def _merge_daily(
    run: Run,
    series_id: str,
    day: date,
    sidof: set[str],
    ref: DofRef | None,
    printed: str | None,
) -> Obs | None:
    key = day.isoformat()
    known = KNOWN.get((series_id, key))
    fix = CORRECTIONS.get((series_id, key))
    if fix is not None and sidof == {fix.value}:
        run.count(f"{series_id}:corrected")
        return Obs(
            key=key, value=fix.value, dof=ref, checked=True, correction=fix.ref, remark=fix.remark
        )
    if len(sidof) == 1:
        (value,) = sidof
        if printed is None:
            return Obs(key=key, value=value, dof=ref)
        if same(value, printed):
            run.count(f"{series_id}:checked")
            return Obs(key=key, value=value, dof=ref, checked=True)
        if known is not None:
            run.count(f"{series_id}:fixed")
            return Obs(key=key, value=printed, dof=ref, checked=True, origin="dof", remark=known)
        note = ref.note if ref else "?"
        if day < TOLERANT_BEFORE:
            run.count(f"{series_id}:early-mismatch")
            remark = (
                f"La nota del DOF de esa fecha ({note}) imprime {printed}; el SIDOF registra "
                f"{value}. Antes de 1996 las fechas del SIDOF y del DOF no siempre coinciden."
            )
            return Obs(key=key, value=value, remark=remark)
        run.problem(f"{series_id} {key}: SIDOF {value} but DOF note {note} prints {printed}")
        return Obs(key=key, value=value, dof=ref)
    if len(sidof) > 1:
        listed = " y ".join(sorted(sidof))
        if printed is not None and printed in sidof:
            run.count(f"{series_id}:fixed")
            remark = f"SIDOF devolvió {listed}; se usa el valor de la nota del DOF."
            return Obs(key=key, value=printed, dof=ref, checked=True, origin="dof", remark=remark)
        if printed is not None and known is not None:
            run.count(f"{series_id}:fixed")
            return Obs(key=key, value=printed, dof=ref, checked=True, origin="dof", remark=known)
        run.problem(
            f"{series_id} {key}: SIDOF returned {listed} and the DOF note could not settle it"
        )
        return None
    # Not in SIDOF: only the DOF note has it.
    if printed is not None:
        run.count(f"{series_id}:from-dof")
        remark = "Sin valor en el SIDOF; se tomó de la nota del DOF."
        return Obs(key=key, value=printed, dof=ref, checked=True, origin="dof", remark=remark)
    if ref is not None:
        run.warn(f"{series_id} {key}: note {ref.note} found but its value could not be read")
    return None


# ---------------------------------------------------------------- UDIS


def udi_publication_targets(day: date) -> date:
    """Banco de México publishes on the 10th (days 11 to 25) and the 25th (days 26 to 10)."""
    if 11 <= day.day <= 25:
        return day.replace(day=10)
    if day.day >= 26:
        return day.replace(day=25)
    previous = day.replace(day=1) - timedelta(days=1)
    return previous.replace(day=25)


def udi_notes_on(run: Run, day: date) -> list[NoteRow]:
    return [r for r in rows_on(run, day) if is_banxico(r) and dof.is_udi_title(r.title)]


def udi_from_dof(run: Run, day: date) -> tuple[str, DofRef] | None:
    target = udi_publication_targets(day)
    for offset in (0, -1, -2, -3, 1, -4, -5):
        when = target + timedelta(days=offset)
        if when >= run.today:
            continue
        for row in udi_notes_on(run, when):
            table = dof.parse_udi_table(run.sidof.note(row.code).text)
            if day in table:
                return table[day], DofRef(day=row.day, note=row.code)
    return None


def build_udis(run: Run, start: date, end: date, publication_days: Iterable[date]) -> list[Obs]:
    """UDI values from SIDOF, settled and verified against Banco de México's DOF notes."""
    values = sidof_values(run, "udis", start, end)
    resolved: dict[date, str] = {}
    remarks: dict[date, str] = {}
    for day, found in values.items():
        if len(found) == 1:
            resolved[day] = next(iter(found))
            continue
        official = udi_from_dof(run, day)
        listed = " y ".join(sorted(found))
        if official is not None and official[0] in found:
            resolved[day] = official[0]
            remarks[day] = f"SIDOF devolvió {listed}; se usa el valor de la nota del DOF."
            run.count("udis:fixed")
            run.log(f"  UDIS {day}: SIDOF returned {listed}; the DOF note says {official[0]}")
        else:
            run.problem(f"UDIS {day}: SIDOF returned {listed} and the DOF note could not settle it")
    if resolved:
        last = max(resolved)
        for day in iter_days(max(start, UDIS_START), last):
            if day in resolved:
                continue
            official = udi_from_dof(run, day)
            if official is None:
                run.problem(f"UDIS {day}: missing from SIDOF and from the DOF")
            else:
                resolved[day] = official[0]
                remarks[day] = "Sin valor en el SIDOF; se tomó de la nota del DOF."
                run.count("udis:from-dof")
                run.log(f"  UDIS {day}: missing from SIDOF; the DOF note says {official[0]}")

    # Publications: every Banco de México UDI note in the scanned days.
    refs: dict[date, DofRef] = {}
    checked: set[date] = set()
    corrected: dict[date, Correction] = {}
    seen: set[int] = set()
    for day in sorted(set(publication_days)):
        for row in udi_notes_on(run, day):
            if row.code in seen:
                continue
            seen.add(row.code)
            table = dof.parse_udi_table(run.sidof.note(row.code).text)
            if not table:
                run.warn(f"UDI note {row.code} ({row.day}) has no readable table")
                continue
            for when, printed in table.items():
                if when in refs:
                    continue
                refs[when] = DofRef(day=row.day, note=row.code)
                have = resolved.get(when)
                if have is None:
                    if when <= end and when >= UDIS_START:
                        run.problem(f"UDI {when} in DOF note {row.code} is missing from SIDOF")
                elif have != printed:
                    fix = CORRECTIONS.get(("udis", when.isoformat()))
                    if fix is not None and fix.value == have:
                        corrected[when] = fix
                        checked.add(when)
                        run.count("udis:corrected")
                    else:
                        run.problem(f"UDI {when}: SIDOF {have} vs DOF note {row.code} {printed}")
                else:
                    checked.add(when)
            run.count("udis:publications")

    out: list[Obs] = []
    for day in sorted(resolved):
        ref = refs.get(day)
        origin = "dof" if day in remarks else None
        fix = corrected.get(day)
        out.append(
            Obs(
                key=day.isoformat(),
                value=resolved[day],
                dof=ref,
                checked=day in checked,
                correction=fix.ref if fix else None,
                origin=origin,
                remark=fix.remark if fix else remarks.get(day),
            )
        )
    _check_udis(run, out)
    return out


def _check_udis(run: Run, observations: list[Obs]) -> None:
    """No gaps, and no day-to-day jump above 1% (the record is 0.33% in April 1995)."""
    previous: Obs | None = None
    for obs in observations:
        if previous is not None:
            gap = (date.fromisoformat(obs.key) - date.fromisoformat(previous.key)).days
            if gap != 1:
                run.problem(f"UDIS: gap between {previous.key} and {obs.key}")
            change = Decimal(obs.value) / Decimal(previous.value) - 1
            if abs(change) > Decimal("0.01"):
                run.problem(f"UDIS {obs.key}: jump of {change * 100:.3f}% from the previous day")
        previous = obs


# ---------------------------------------------------------------- INPC


def inegi_csv(cache_dir: Path | None) -> dict[str, str]:
    """INEGI's open-data INPC file (base 2018, January 2003 to July 2024)."""
    raw: bytes | None = None
    cached = cache_dir / "inegi" / "inpc_indicador_mensual_csv.zip" if cache_dir else None
    if cached is not None and cached.exists():
        raw = cached.read_bytes()
    if raw is None:
        response = httpx.get(INEGI_INPC_CSV, headers={"User-Agent": USER_AGENT}, timeout=60)
        response.raise_for_status()
        raw = response.content
        if cached is not None:
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_bytes(raw)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        name = "conjunto_de_datos/conjunto_de_datos_inpc_mensual.csv"
        text = archive.read(name).decode("utf-8-sig")
    out: dict[str, str] = {}
    for row in csv.DictReader(io.StringIO(text)):
        if row["CONCEPTO"] != INEGI_CONCEPT:
            continue
        if row["UNIDAD_MEDIDA"] != "Índice":
            raise ValueError(f"INEGI CSV: unexpected unit {row['UNIDAD_MEDIDA']!r}")
        out[row["FECHA"][:7]] = row["VALOR"].strip()
    return dict(sorted(out.items()))


def _variation_ok(parsed: dof.InpcMonthly) -> bool:
    if parsed.variation is None or parsed.previous_value is None:
        return True
    computed = (Decimal(parsed.value) / Decimal(parsed.previous_value) - 1) * 100
    return pct(computed) == Decimal(parsed.variation).quantize(Decimal("0.01"))


def pct(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _inpc_notes(run: Run, day: date, *, correction: bool) -> list[NoteRow]:
    rows = run.sidof.day_notes(day)
    if correction:
        return [
            r
            for r in rows
            if (is_inegi(r) or is_banxico(r))
            and dof.is_inpc_title(r.title)
            and dof.is_correction_title(r.title)
        ]
    return [
        r for r in rows if (is_inegi(r) or is_banxico(r)) and dof.is_inpc_monthly_title(r.title)
    ]


def find_inpc(run: Run, month: str) -> tuple[dof.InpcMonthly, DofRef] | None:
    following = add_months(month, 1)
    year, mon = (int(p) for p in following.split("-"))
    for day_number in INPC_DAYS:
        day = date(year, mon, day_number)
        if day > run.today:
            continue
        for row in _inpc_notes(run, day, correction=False):
            parsed = dof.parse_inpc_monthly(run.sidof.note(row.code).text)
            if parsed is not None and parsed.month == month:
                return parsed, DofRef(day=row.day, note=row.code)
    return None


def find_inpc_correction(
    run: Run, month: str, after: date
) -> tuple[dof.InpcMonthly, DofRef] | None:
    for offset in range(1, 31):
        day = after + timedelta(days=offset)
        if day > run.today:
            break
        for row in _inpc_notes(run, day, correction=True):
            parsed = dof.parse_inpc_monthly(run.sidof.note(row.code).text)
            if parsed is not None and parsed.month == month:
                return parsed, DofRef(day=row.day, note=row.code)
    return None


def inpc_from_dof(run: Run, month: str, known: dict[str, str]) -> Obs | None:
    found = find_inpc(run, month)
    if found is None:
        return None
    parsed, ref = found
    obs = Obs(key=month, value=parsed.value, dof=ref, checked=True)
    if parsed.previous_month and parsed.previous_value:
        before = known.get(parsed.previous_month)
        if before is not None and Decimal(before).quantize(Decimal("0.001")) != Decimal(
            parsed.previous_value
        ):
            run.problem(
                f"INPC {month}: DOF {ref.day} says {parsed.previous_month} was "
                f"{parsed.previous_value}, the data has {before}"
            )
    if not _variation_ok(parsed):
        run.log(f"  INPC {month}: note {ref.note} is inconsistent; looking for a correction")
        fix = find_inpc_correction(run, month, ref.day)
        if fix is not None and _variation_ok(fix[0]):
            run.count("inpc:fixed")
            obs = obs.with_(
                value=fix[0].value,
                correction=fix[1],
                remark=(
                    f"La nota del {ref.day.isoformat()} publicó {parsed.value} (variación "
                    f"{parsed.variation}%); la nota aclaratoria del {fix[1].day.isoformat()} lo "
                    f"corrigió a {fix[0].value}."
                ),
            )
        else:
            run.problem(f"INPC {month}: DOF value {parsed.value} fails the variation check")
    run.count("inpc:dof")
    return obs


def build_inpc(
    run: Run, csv_values: dict[str, str], existing: list[Obs] | None = None
) -> list[Obs]:
    """INEGI CSV before August 2018, DOF notes since; overlap compared value by value."""
    if existing:
        months = list(existing)
    else:
        months = [
            Obs(key=m, value=v, origin="inegi")
            for m, v in csv_values.items()
            if m < FIRST_DOF_INPC_MONTH
        ]
    known = {o.key: o.value for o in months} | {
        m: v for m, v in csv_values.items() if m not in {o.key for o in months}
    }
    month = add_months(months[-1].key, 1) if months else FIRST_DOF_INPC_MONTH
    while True:
        following = add_months(month, 1)
        if date.fromisoformat(f"{following}-06") > run.today:
            break
        obs = inpc_from_dof(run, month, known)
        if obs is None:
            run.log(f"  INPC {month}: not published yet")
            break
        if month in csv_values:
            run.count("inpc:cross-checked")
            if Decimal(csv_values[month]) != Decimal(obs.value):
                run.problem(f"INPC {month}: DOF {obs.value} vs INEGI CSV {csv_values[month]}")
        known[month] = obs.value
        months.append(obs)
        month = add_months(month, 1)
    return months


def derive_inflation(inpc: list[Obs]) -> tuple[list[Obs], list[Obs]]:
    """Monthly and annual percent changes, two decimals, half up (away from zero)."""
    by_month = {o.key: Decimal(o.value) for o in inpc}
    monthly: list[Obs] = []
    annual: list[Obs] = []
    for o in inpc:
        current = by_month[o.key]
        prev = by_month.get(add_months(o.key, -1))
        if prev is not None:
            monthly.append(Obs(key=o.key, value=str(pct((current / prev - 1) * 100))))
        year_ago = by_month.get(add_months(o.key, -12))
        if year_ago is not None:
            annual.append(Obs(key=o.key, value=str(pct((current / year_ago - 1) * 100))))
    return monthly, annual


# ---------------------------------------------------------------- step series


def _value_forms(value: str) -> list[str]:
    whole, _, frac = value.partition(".")
    grouped = f"{int(whole):,}"
    forms = {value, f"{grouped}.{frac}" if frac else grouped}
    return sorted(forms, key=len, reverse=True)


def value_in_text(value: str, text: str) -> bool:
    """True if the note prints ``value`` (with or without thousands separators)."""
    # Also try with spaces inside numbers removed: some notes split a figure across text
    # runs ("$42,794. 64"). The raw text is tried too, because joining can glue two
    # neighbouring figures ("$ 14,270 14.27", old and new pesos in 1993).
    compact = re.sub(r"(?<=\d)\s+(?=[\d.,])|(?<=[.,])\s+(?=\d)", "", text)
    for candidate in (text, compact):
        for form in _value_forms(value):
            if re.search(r"(?<![\d.,])" + re.escape(form) + r"(?![\d])", candidate):
                return True
    return False


def verify_steps(run: Run, data: dict[str, list[Obs]], ids: Iterable[str]) -> dict[str, list[Obs]]:
    """Check each hand-curated value against the text of its DOF note; mark it checked."""
    out: dict[str, list[Obs]] = {}
    for series_id in ids:
        updated: list[Obs] = []
        for obs in data.get(series_id, []):
            if obs.dof is None:
                run.problem(f"{series_id} {obs.key}: no DOF note")
                updated.append(obs)
                continue
            # When a nota aclaratoria fixed the published value, the value is in the correction.
            text = run.sidof.note((obs.correction or obs.dof).note).text
            if value_in_text(obs.value, text):
                run.count(f"{series_id}:checked")
                updated.append(obs.with_(checked=True))
            else:
                run.problem(f"{series_id} {obs.key}: {obs.value} not found in note {obs.dof.note}")
                updated.append(obs.with_(checked=False))
        out[series_id] = updated
    return out


def git_head_date(root: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", "data"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return out or None
