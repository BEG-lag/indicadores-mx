"""Yearly detection of a new UMA or minimum wage note (no network)."""

from __future__ import annotations

from datetime import date

from indicadores_mx import annual, pipeline
from indicadores_mx.sidof import Note, NoteRow
from indicadores_mx.store import DofRef, Obs

from .conftest import note_text

INEGI = "INSTITUTO NACIONAL DE ESTADISTICA Y GEOGRAFIA"
CONASAMI = "COMISION NACIONAL DE LOS SALARIOS MINIMOS"


class Days:
    def __init__(self, rows: dict[date, list[NoteRow]], texts: dict[int, str]) -> None:
        self.rows = rows
        self.texts = texts

    def day_notes(self, day: date) -> list[NoteRow]:
        return self.rows.get(day, [])

    def note(self, code: int) -> Note:
        return Note(code=code, title="", day=date(2026, 1, 9), agency="", text=self.texts[code])


def run_for(rows, texts, today) -> pipeline.Run:
    return pipeline.Run(sidof=Days(rows, texts), today=today, log=lambda _: None)  # type: ignore[arg-type]


def test_new_uma_is_proposed_from_the_note():
    day = date(2026, 1, 9)
    row = NoteRow(5778072, "Unidad de medida y actualización.", day, "matutina", INEGI)
    run = run_for({day: [row]}, {5778072: note_text(5778072)}, date(2026, 1, 12))
    data = {"uma-diaria": [Obs(key="2025-02-01", value="113.14")]}
    touched, report = annual.detect(run, data, "uma", "2026-01-01")
    assert run.problems == []
    assert touched["uma-diaria"][-1] == Obs(
        key="2026-02-01", value="117.31", dof=DofRef(day, 5778072), checked=True
    )
    assert touched["uma-mensual"][-1].value == "3566.22"
    assert touched["uma-anual"][-1].value == "42794.64"
    assert "UMA in force from 2026-02-01 (new)" in report


def test_unreadable_resolution_stops_for_a_person():
    day = date(2026, 12, 10)
    title = "Resolución ... que fija los salarios mínimos generales y profesionales"
    row = NoteRow(1, title, day, "matutina", CONASAMI)
    run = run_for({day: [row]}, {1: "texto con un formato nuevo"}, date(2026, 12, 28))
    touched, _ = annual.detect(run, {}, "salario-minimo", "2026-12-01")
    assert touched == {}
    assert len(run.problems) == 1


def test_nothing_new():
    run = run_for({}, {}, date(2026, 12, 28))
    touched, report = annual.detect(run, {}, "salario-minimo", "2026-12-20")
    assert touched == {}
    assert "Nothing new." in report
