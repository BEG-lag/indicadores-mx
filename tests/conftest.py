"""Offline SIDOF: an httpx transport that replays recorded responses.

The fixtures under ``tests/fixtures/sidof`` were recorded from the real API with
``scripts/record_fixtures.py``. The transport behaves like SIDOF where it matters:
indicator ranges are filtered by date and answer 404 when empty, a day without an
edition answers 200 with empty lists, and a bare ``Accept: application/json``
answers 406.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "sidof"
SCHEMA_DIR = ROOT / "schema"


def _dmy(text: str) -> date:
    return datetime.strptime(text, "%d-%m-%Y").date()


class FakeSidof:
    """Serves the recorded fixtures; ``overrides`` patch indicator values by (code, DD-MM-YYYY)."""

    def __init__(self) -> None:
        self.overrides: dict[tuple[int, str], str] = {}
        self.requests: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(str(request.url))
        if request.headers.get("accept", "").strip() == "application/json":
            return httpx.Response(406)
        parts = request.url.path.removeprefix("/dof/sidof/").strip("/").split("/")
        if parts[0] == "indicadores" and len(parts) == 4:
            return self._indicators(int(parts[1]), _dmy(parts[2]), _dmy(parts[3]))
        if parts[:2] == ["notas", "nota"]:
            path = FIXTURES / "nota" / f"{parts[2]}.json"
            if path.exists():
                return httpx.Response(200, json=json.loads(path.read_text()))
            return httpx.Response(200, json={"messageCode": 200, "response": "OK", "Nota": []})
        if parts[0] == "notas" and len(parts) == 2:
            _dmy(parts[1])  # an invalid date would be a 500 on the real server
            path = FIXTURES / "notas" / f"{parts[1]}.json"
            if path.exists():
                return httpx.Response(200, json=json.loads(path.read_text()))
            empty = {"NotasMatutinas": [], "NotasVespertinas": [], "NotasExtraordinarias": []}
            return httpx.Response(200, json={"messageCode": 200, "response": "OK", **empty})
        return httpx.Response(404, json={"messageCode": 404, "response": "NOT_FOUND"})

    def _indicators(self, code: int, start: date, end: date) -> httpx.Response:
        path = FIXTURES / "indicadores" / f"{code}.json"
        rows: list[dict[str, Any]] = []
        if path.exists():
            for row in json.loads(path.read_text())["ListaIndicadores"]:
                if start <= _dmy(row["fecha"]) <= end:
                    value = self.overrides.get((code, row["fecha"]), row["valor"])
                    rows.append({**row, "valor": value})
        if not rows:
            return httpx.Response(404, json={"messageCode": 404, "response": "NOT_FOUND"})
        body = {"messageCode": 200, "response": "OK", "ListaIndicadores": rows}
        return httpx.Response(200, json={**body, "TotalIndicadores": len(rows)})


@pytest.fixture
def fake_sidof() -> FakeSidof:
    return FakeSidof()


@pytest.fixture
def transport(fake_sidof: FakeSidof) -> httpx.MockTransport:
    return httpx.MockTransport(fake_sidof)


def note_text(code: int) -> str:
    from indicadores_mx.dof import html_to_text

    payload = json.loads((FIXTURES / "nota" / f"{code}.json").read_text())
    return html_to_text(payload["Nota"]["cadenaContenido"])


@pytest.fixture
def text_of() -> Callable[[int], str]:
    return note_text


def schema_registry() -> Registry:
    resources = []
    for path in SCHEMA_DIR.rglob("*.schema.json"):
        schema = json.loads(path.read_text())
        resources.append((schema["$id"], Resource.from_contents(schema)))
    return Registry().with_resources(resources)


@pytest.fixture(scope="session")
def registry() -> Registry:
    return schema_registry()


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--built",
        default=None,
        help="validate an already built site folder (for example _site) instead of building one",
    )
