"""Cross-checks and merge rules, with an in-memory stand-in for SIDOF."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from indicadores_mx import pipeline, store
from indicadores_mx.sidof import Note, NoteRow
from indicadores_mx.store import DofRef, Obs

FIX_TITLE = "Tipo de cambio para solventar obligaciones denominadas en moneda extranjera"
TIIE_TITLE = "Tasas de interés interbancarias de equilibrio."


def banxico_row(code: int, title: str, day: date) -> NoteRow:
    return NoteRow(code=code, title=title, day=day, edition="matutina", agency="BANCO DE MEXICO")


class MemorySidof:
    def __init__(self) -> None:
        self.indicators: dict[int, list[dict[str, str]]] = {}
        self.days: dict[date, list[NoteRow]] = {}
        self.notes: dict[int, str] = {}

    def indicator_range(self, code: int, start: date, end: date) -> list[dict[str, str]]:
        out = []
        for row in self.indicators.get(code, []):
            d, m, y = (int(p) for p in row["fecha"].split("-"))
            if start <= date(y, m, d) <= end:
                out.append(row)
        return out

    def day_notes(self, day: date) -> list[NoteRow]:
        return self.days.get(day, [])

    def note(self, code: int) -> Note:
        return Note(code=code, title="", day=date(2026, 1, 1), agency="", text=self.notes[code])

    def add_fix_note(self, day: date, code: int, printed: str) -> None:
        row = NoteRow(
            code=code, title=FIX_TITLE, day=day, edition="matutina", agency="BANCO DE MEXICO"
        )
        self.days.setdefault(day, []).append(row)
        self.notes[code] = (
            f"informa que el tipo de cambio obtenido el día de hoy fue de ${printed} M.N."
        )


@pytest.fixture
def memory() -> MemorySidof:
    return MemorySidof()


def make_run(memory: MemorySidof) -> pipeline.Run:
    return pipeline.Run(sidof=memory, today=date(2026, 11, 17), log=lambda _: None)  # type: ignore[arg-type]


ALL = pipeline.DailyPlan(verify_all_after=date(1990, 1, 1))


def test_value_matching_its_note_is_checked(memory):
    day = date(2026, 11, 13)
    memory.indicators[158] = [{"fecha": "13-11-2026", "valor": "18.6188"}]
    memory.add_fix_note(day, 5803775, "18.6188")
    run = make_run(memory)
    values = pipeline.sidof_values(run, "fix", day, day)
    obs = pipeline.build_daily(run, "fix", values, [day], ALL)
    assert obs == [Obs(key="2026-11-13", value="18.6188", dof=DofRef(day, 5803775), checked=True)]
    assert run.problems == []


def test_disagreement_is_a_problem(memory):
    day = date(2026, 11, 13)
    memory.indicators[158] = [{"fecha": "13-11-2026", "valor": "18.6188"}]
    memory.add_fix_note(day, 5803775, "18.6100")
    run = make_run(memory)
    pipeline.build_daily(run, "fix", pipeline.sidof_values(run, "fix", day, day), [day], ALL)
    assert len(run.problems) == 1
    assert "18.6100" in run.problems[0]


def test_two_sidof_values_are_settled_by_the_note(memory):
    day = date(2004, 9, 6)
    memory.indicators[158] = [
        {"fecha": "06-09-2004", "valor": "11.5279"},
        {"fecha": "06-09-2004", "valor": "11.5193"},
    ]
    memory.add_fix_note(day, 1, "11.5193")
    run = make_run(memory)
    obs = pipeline.build_daily(run, "fix", pipeline.sidof_values(run, "fix", day, day), [day], ALL)
    assert obs[0].value == "11.5193"
    assert obs[0].origin == "dof"
    assert obs[0].checked
    assert "11.5193 y 11.5279" in (obs[0].remark or "")
    assert run.problems == []


def test_gap_in_sidof_is_filled_from_the_note(memory):
    """A business day missing from SIDOF while its neighbours are there: read the note."""
    day = date(1998, 3, 2)
    memory.add_fix_note(day, 2, "8.5120")
    run = make_run(memory)
    values = {day + timedelta(days=d): {"8.5000"} for d in (-6, -5, -4, -3, 1, 2, 3)}
    obs = pipeline.build_daily(run, "fix", values, [day], ALL)
    filled = next(o for o in obs if o.key == "1998-03-02")
    assert filled.value == "8.5120"
    assert filled.origin == "dof"
    assert filled.checked


def test_isolated_note_without_sidof_value_is_not_read_for_weekly_series(memory):
    """TIIE 182 was weekly until 2023: the shared daily note is not read on other days."""
    day = date(2019, 3, 5)
    memory.days[day] = [banxico_row(7, TIIE_TITLE, day)]
    run = make_run(memory)
    values = {date(2019, 2, 28): {"8.6000"}}
    observations = pipeline.build_daily(run, "tiie-182", values, [day], ALL)
    assert [o.key for o in observations] == ["2019-02-28"]


def test_sidof_noise_is_normalized(memory):
    memory.indicators[165] = [
        {"fecha": "22-02-2006", "valor": "7. 8425%"},
        {"fecha": "14-09-2009", "valor": "4.8850 %"},
        {"fecha": "05-01-2005", "valor": "8.92%"},
    ]
    run = make_run(memory)
    values = pipeline.sidof_values(run, "tiie-28", date(2005, 1, 1), date(2009, 12, 31))
    assert values[date(2006, 2, 22)] == {"7.8425"}
    assert values[date(2009, 9, 14)] == {"4.8850"}
    assert values[date(2005, 1, 5)] == {"8.9200"}


def test_udi_gap_is_a_problem(memory):
    memory.indicators[159] = [
        {"fecha": "01-01-2020", "valor": "6.399018"},
        {"fecha": "03-01-2020", "valor": "6.401000"},
    ]
    run = make_run(memory)
    pipeline.build_udis(run, date(2020, 1, 1), date(2020, 1, 3), [])
    assert any("2020-01-02" in p for p in run.problems)


def test_udi_jump_is_a_problem(memory):
    memory.indicators[159] = [
        {"fecha": "01-01-2020", "valor": "6.399018"},
        {"fecha": "02-01-2020", "valor": "7.000000"},
    ]
    run = make_run(memory)
    pipeline.build_udis(run, date(2020, 1, 1), date(2020, 1, 2), [])
    assert any("jump" in p for p in run.problems)


def test_inflation_is_derived_with_half_up_rounding():
    inpc = [Obs(key=f"2025-{m:02d}", value="100.000") for m in range(1, 13)]
    inpc += [Obs(key="2026-01", value="100.005"), Obs(key="2026-02", value="99.500")]
    monthly, annual = pipeline.derive_inflation(inpc)
    by_month = {o.key: o.value for o in monthly}
    assert by_month["2026-01"] == "0.01"  # 0.005% rounds half up
    assert by_month["2026-02"] == "-0.50"
    assert {o.key: o.value for o in annual} == {"2026-01": "0.01", "2026-02": "-0.50"}


def test_pct_rounds_away_from_zero():
    assert pipeline.pct(Decimal("0.125")) == Decimal("0.13")
    assert pipeline.pct(Decimal("-0.125")) == Decimal("-0.13")


def test_value_in_text_handles_thousands_and_split_runs():
    text = "el mensual es de $3,566.22 pesos y el anual $42,794. 64 pesos; diario 117.31"
    assert pipeline.value_in_text("3566.22", text)
    assert pipeline.value_in_text("42794.64", text)
    assert pipeline.value_in_text("117.31", text)
    assert not pipeline.value_in_text("17.31", text)
    assert not pipeline.value_in_text("3566.2", text)


def test_normalize_value():
    assert store.normalize_value(" 6.5147% ") == "6.5147"
    assert store.normalize_value("11.5498%.") == "11.5498"
    assert store.normalize_value("4.995", 4) == "4.9950"
    assert store.normalize_value("1", 6) == "1.000000"
    with pytest.raises(ValueError, match="not a number"):
        store.normalize_value("5.0300%x")


def test_value_of_a_day_without_dof_is_matched_to_the_next_edition(memory):
    """5 May 2025 was a banking day without a DOF edition: its FIX appeared on the 6th."""
    memory.indicators[158] = [
        {"fecha": "05-05-2025", "valor": "19.6570"},
        {"fecha": "06-05-2025", "valor": "19.6365"},
    ]
    sixth = date(2025, 5, 6)
    memory.add_fix_note(sixth, 5756456, "19.6570")
    memory.add_fix_note(sixth, 5756459, "19.6365")
    run = make_run(memory)
    values = pipeline.sidof_values(run, "fix", date(2025, 5, 5), sixth)
    obs = pipeline.build_daily(run, "fix", values, [date(2025, 5, 5), sixth], ALL)
    assert [(o.key, o.value, o.dof, o.checked) for o in obs] == [
        ("2025-05-05", "19.6570", DofRef(sixth, 5756456), True),
        ("2025-05-06", "19.6365", DofRef(sixth, 5756459), True),
    ]
    assert run.problems == []


def test_tiie_with_a_holiday_term_is_kept_with_its_term(memory):
    """SIDOF files 29-day TIIEs under another code; the DOF note fills the 28-day series."""
    day = date(2024, 1, 8)
    title = "Tasas de interés interbancarias de equilibrio."
    memory.days[day] = [
        NoteRow(code=9, title=title, day=day, edition="matutina", agency="BANCO DE MEXICO")
    ]
    memory.notes[9] = (
        "la TIIE a plazo de 29 días obtenida el día de hoy, fue de 11.5025 por ciento ; a plazo "
        "de 91 días obtenida el día de hoy, fue de 11.6 394 por ciento"
    )
    memory.indicators[166] = [{"fecha": "08-01-2024", "valor": "11.6394%"}]
    run = make_run(memory)
    tiie28 = pipeline.build_daily(run, "tiie-28", {}, [day], ALL)
    assert tiie28[0].value == "11.5025"
    assert tiie28[0].extra == {"term_days": 29}
    assert tiie28[0].origin == "dof"
    values = pipeline.sidof_values(run, "tiie-91", day, day)
    tiie91 = pipeline.build_daily(run, "tiie-91", values, [day], ALL)
    assert tiie91[0].checked
    assert tiie91[0].extra == {}
