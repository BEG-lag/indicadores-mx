"""End to end: the scheduled ``update`` against recorded SIDOF responses (no network)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from indicadores_mx import cli, store
from indicadores_mx.sidof import Sidof
from indicadores_mx.store import Obs

from .conftest import FIXTURES

CODES = {"fix": 158, "tiie-28": 165, "tiie-91": 166, "tiie-182": 174, "tiie-fondeo": 175}
DECIMALS = {"fix": 4, "tiie-28": 4, "tiie-91": 4, "tiie-182": 4, "tiie-fondeo": 2}


def _rows(code: int) -> list[tuple[str, str]]:
    rows = json.loads((FIXTURES / "indicadores" / f"{code}.json").read_text())["ListaIndicadores"]
    out = []
    for row in rows:
        d, m, y = row["fecha"].split("-")
        out.append((f"{y}-{m}-{d}", row["valor"]))
    return sorted(out)


def seed(data_dir: Path) -> None:
    """Data as it stood on 9 Nov 2026: daily series through the 9th, UDIS through the 10th."""
    for sid, code in CODES.items():
        obs = [
            Obs(key=k, value=store.normalize_value(v, DECIMALS[sid]))
            for k, v in _rows(code)
            if k <= "2026-11-09"
        ]
        store.write(sid, obs, data_dir)
    udis = [
        Obs(key=k, value=store.normalize_value(v, 6))
        for k, v in _rows(159)
        if "2026-09-26" <= k <= "2026-11-10"
    ]
    store.write("udis", udis, data_dir)
    store.write(
        "inpc", [Obs(key="2026-08", value="145.462"), Obs(key="2026-09", value="146.075")], data_dir
    )


@pytest.fixture
def data_dir(tmp_path: Path, transport, monkeypatch) -> Path:
    folder = tmp_path / "data"
    seed(folder)

    def client(args, today):
        return Sidof(cache_dir=None, delay=0, today=today, transport=transport)

    monkeypatch.setattr(cli, "make_client", client)
    return folder


def run_update(data_dir: Path, *extra: str) -> int:
    return cli.main(
        [
            "update",
            "--data",
            str(data_dir),
            "--today",
            "2026-11-13",
            "--days",
            "4",
            "--summary",
            str(data_dir.parent / "summary.txt"),
            *extra,
        ]
    )


def snapshot(data_dir: Path) -> dict[str, str]:
    return {p.name: p.read_text() for p in sorted(data_dir.glob("*.json"))}


def test_update_appends_and_verifies(data_dir: Path):
    assert run_update(data_dir) == 0
    fix = {o.key: o for o in store.load("fix", data_dir)}
    new = fix["2026-11-13"]
    assert new.value == "18.6188"
    assert new.checked
    assert new.dof is not None
    assert new.dof.note == 5803775
    assert new.dof.day == date(2026, 11, 13)
    assert all(fix[d].checked for d in ("2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13"))

    tiie = {o.key: o for o in store.load("tiie-28", data_dir)}
    assert tiie["2026-11-13"].value == "6.5147"
    assert tiie["2026-11-13"].checked
    fondeo = {o.key: o for o in store.load("tiie-fondeo", data_dir)}
    assert fondeo["2026-11-13"].value == "6.26"
    assert fondeo["2026-11-13"].dof.note == 5803777

    udis = store.load("udis", data_dir)
    assert udis[-1].key == "2026-11-25"
    by_day = {o.key: o for o in udis}
    assert by_day["2026-11-13"].value == "8.904621"
    assert by_day["2026-11-13"].dof.note == 5803350
    assert by_day["2026-11-13"].checked

    inpc = store.load("inpc", data_dir)
    assert inpc[-1].key == "2026-10"
    assert inpc[-1].value == "147.026"
    assert inpc[-1].dof.note == 5803352
    assert inpc[-1].checked
    monthly = {o.key: o.value for o in store.load("inflacion-mensual", data_dir)}
    assert monthly["2026-10"] == "0.65"  # as printed in the INEGI note

    summary = (data_dir.parent / "summary.txt").read_text()
    assert "fix 2026-11-13" in summary
    assert "inpc 2026-10" in summary


def test_second_run_changes_nothing(data_dir: Path):
    assert run_update(data_dir) == 0
    before = snapshot(data_dir)
    assert run_update(data_dir) == 0
    assert snapshot(data_dir) == before


def test_disagreement_with_the_dof_note_stops_without_writing(data_dir: Path, fake_sidof):
    fake_sidof.overrides[(158, "12-11-2026")] = "18.7000"
    before = snapshot(data_dir)
    assert run_update(data_dir) == 1
    assert snapshot(data_dir) == before


def test_a_published_value_must_not_change(data_dir: Path, fake_sidof):
    assert run_update(data_dir) == 0
    before = snapshot(data_dir)
    fake_sidof.overrides[(159, "20-11-2026")] = "8.999999"
    assert run_update(data_dir) == 1
    assert snapshot(data_dir) == before


def test_bare_json_accept_header_is_refused(transport):
    import httpx

    with httpx.Client(transport=transport) as client:
        response = client.get(
            "https://sidof.segob.gob.mx/dof/sidof/notas/13-11-2026",
            headers={"Accept": "application/json"},
        )
    assert response.status_code == 406
