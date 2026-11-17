"""Yearly series: detect a new minimum wage resolution or UMA value in the DOF.

The scheduled workflow runs this in December (minimum wage) and January (UMA).
It scans the recent DOF tables of contents, reads the new note, appends the
values it finds and writes a Markdown report. The values are committed only
after a person approves the ``annual-review`` environment in GitHub Actions,
so a format change in the note cannot slip in unnoticed.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from . import dof
from .dof import dof_note_url
from .pipeline import Run, is_inegi
from .sidof import NoteRow, fold
from .store import DofRef, Obs

_RESOLUTION = re.compile(r"fija los salarios m[ií]nimos generales", re.I)
_UMA_TITLE = re.compile(r"^unidad de medida y actualizaci", re.I)


def _is_conasami(row: NoteRow) -> bool:
    return "SALARIOS MINIMOS" in fold(row.agency) or "TRABAJO" in fold(row.agency)


def _append(data: dict[str, list[Obs]], series_id: str, obs: Obs) -> bool:
    current = data.setdefault(series_id, [])
    if any(o.key == obs.key for o in current):
        return False
    current.append(obs)
    current.sort(key=lambda o: o.key)
    return True


def detect(
    run: Run, data: dict[str, list[Obs]], kind: str, since: str | None
) -> tuple[dict[str, list[Obs]], str]:
    start = date.fromisoformat(since) if since else run.today - timedelta(days=75)
    lines = [f"# {kind}: DOF {start.isoformat()} to {run.today.isoformat()}", ""]
    touched: dict[str, list[Obs]] = {}
    day = start
    while day <= run.today:
        for row in run.sidof.day_notes(day):
            if dof.is_correction_title(row.title):
                if (kind == "uma" and is_inegi(row) and "medida" in row.title.lower()) or (
                    kind == "salario-minimo" and _is_conasami(row)
                ):
                    run.problem(f"correction note {row.code} ({row.day}): review it by hand")
                continue
            if kind == "uma" and is_inegi(row) and _UMA_TITLE.search(row.title):
                _uma(run, data, touched, row, lines)
            if kind == "salario-minimo" and _is_conasami(row) and _RESOLUTION.search(row.title):
                _wage(run, data, touched, row, lines)
        day += timedelta(days=1)
    if len(lines) == 2:
        lines.append("Nothing new.")
    return touched, "\n".join(lines) + "\n"


def _uma(run: Run, data: dict, touched: dict, row: NoteRow, lines: list[str]) -> None:
    note = run.sidof.note(row.code)
    parsed = dof.parse_uma(note.text)
    url = dof_note_url(row.code, row.day)
    if parsed is None:
        run.problem(f"UMA note {row.code} ({row.day}) could not be read: {url}")
        return
    ref = DofRef(day=row.day, note=row.code)
    key = parsed.in_force.isoformat()
    added = False
    for sid, value in (
        ("uma-diaria", parsed.daily),
        ("uma-mensual", parsed.monthly),
        ("uma-anual", parsed.annual),
    ):
        if _append(data, sid, Obs(key=key, value=value, dof=ref, checked=True)):
            touched[sid] = data[sid]
            added = True
    status = "new" if added else "already in the data"
    lines.append(
        f"- UMA in force from {key} ({status}): daily {parsed.daily}, monthly "
        f"{parsed.monthly}, annual {parsed.annual}. DOF {row.day}, note {row.code}: {url}"
    )


def _wage(run: Run, data: dict, touched: dict, row: NoteRow, lines: list[str]) -> None:
    note = run.sidof.note(row.code)
    parsed = dof.parse_minimum_wage(note.text)
    url = dof_note_url(row.code, row.day)
    if parsed is None:
        run.problem(f"Minimum wage note {row.code} ({row.day}) could not be read: {url}")
        return
    ref = DofRef(day=row.day, note=row.code)
    key = parsed.in_force.isoformat()
    added = False
    if _append(
        data, "salario-minimo-general", Obs(key=key, value=parsed.general, dof=ref, checked=True)
    ):
        touched["salario-minimo-general"] = data["salario-minimo-general"]
        added = True
    if parsed.zlfn and _append(
        data, "salario-minimo-zlfn", Obs(key=key, value=parsed.zlfn, dof=ref, checked=True)
    ):
        touched["salario-minimo-zlfn"] = data["salario-minimo-zlfn"]
        added = True
    status = "new" if added else "already in the data"
    lines.append(
        f"- Minimum wage in force from {key} ({status}): general {parsed.general}, ZLFN "
        f"{parsed.zlfn or 'n/a'}. DOF {row.day}, note {row.code}: {url}"
    )
