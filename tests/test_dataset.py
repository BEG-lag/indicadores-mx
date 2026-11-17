"""Integrity of the committed dataset: every data/*.json against the schema, plus invariants."""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from indicadores_mx import pipeline, store
from indicadores_mx.catalog import BY_ID, SERIES
from indicadores_mx.store import DATA_DIR

FILES = sorted(DATA_DIR.glob("*.json"))
pytestmark = pytest.mark.skipif(not FILES, reason="data/ is empty")


@pytest.fixture(scope="module")
def data():
    return store.load_all()


def test_files_match_the_catalog():
    assert {p.stem for p in FILES} == {s.id for s in SERIES}


@pytest.mark.parametrize("path", FILES, ids=[p.stem for p in FILES])
def test_schema(path, registry):
    schema = registry.contents("https://beg-lag.github.io/indicadores-mx/schema/data.schema.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)
    assert payload["series"] == path.stem


@pytest.mark.parametrize("path", FILES, ids=[p.stem for p in FILES])
def test_sorted_unique_and_canonical(path):
    observations = store.load(path.stem)
    keys = [o.key for o in observations]
    assert keys == sorted(keys)
    assert len(keys) == len(set(keys))
    # Written by store.serialize: re-serializing must give the same bytes.
    assert store.serialize(BY_ID[path.stem], observations) == path.read_text(encoding="utf-8")


def test_dates_have_the_right_shape(data):
    for series in SERIES:
        for obs in data[series.id]:
            if series.kind == "monthly":
                assert len(obs.key) == 7, (series.id, obs.key)
            else:
                date.fromisoformat(obs.key)


def test_checked_values_have_a_note(data):
    for sid, observations in data.items():
        for obs in observations:
            if obs.checked:
                assert obs.dof is not None, (sid, obs.key)
            if obs.dof is not None and BY_ID[sid].kind != "step":
                assert obs.dof.day <= date.fromisoformat(
                    f"{obs.key}-01" if len(obs.key) == 7 else obs.key
                ) + timedelta(days=60)


def test_udis_are_contiguous_and_smooth(data):
    run = pipeline.Run(sidof=None, today=date.today(), log=lambda _: None)  # type: ignore[arg-type]
    pipeline._check_udis(run, data["udis"])
    assert run.problems == []
    assert data["udis"][0].key == "1995-04-04"
    assert data["udis"][0].value == "1.000000"


def test_inflation_matches_the_inpc(data):
    monthly, annual = pipeline.derive_inflation(data["inpc"])
    assert [o.to_json() for o in monthly] == [o.to_json() for o in data["inflacion-mensual"]]
    assert [o.to_json() for o in annual] == [o.to_json() for o in data["inflacion-anual"]]


def test_inpc_august_2018_uses_the_corrected_value(data):
    august = {o.key: o for o in data["inpc"]}["2018-08"]
    assert august.value == "100.492"
    assert august.correction is not None
    assert august.correction.note == 5537585


def test_uma_monthly_and_annual_follow_the_law(data):
    """LDVUMA art. 4: monthly = daily x 30.4, annual = monthly x 12 (to the cent)."""
    monthly = {o.key: Decimal(o.value) for o in data["uma-mensual"]}
    annual = {o.key: Decimal(o.value) for o in data["uma-anual"]}
    for obs in data["uma-diaria"]:
        expected_month = (Decimal(obs.value) * Decimal("30.4")).quantize(Decimal("0.01"))
        assert abs(monthly[obs.key] - expected_month) <= Decimal("0.01"), obs.key
        assert annual[obs.key] == monthly[obs.key] * 12, obs.key


def test_step_series_are_checked_against_their_notes(data):
    for series in SERIES:
        if series.kind == "step":
            assert all(o.checked and o.dof is not None for o in data[series.id]), series.id


def test_rates_are_plausible(data):
    for sid, low, high in (
        ("fix", "2.5", "30"),
        ("tiie-28", "2", "120"),
        ("tiie-fondeo", "2", "15"),
        ("inpc", "10", "300"),
    ):
        for obs in data[sid]:
            assert Decimal(low) < Decimal(obs.value) < Decimal(high), (sid, obs.key, obs.value)
