"""The static API built from data/: every file type validated against its JSON Schema.

Run against an existing build (the Pages workflow does this before deploying):

    uv run pytest tests/test_api.py --built _site
"""

from __future__ import annotations

import csv
import io
import json
import random
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from indicadores_mx import api, store
from indicadores_mx.catalog import BY_ID

BASE = "https://beg-lag.github.io/indicadores-mx/schema/v1/"


@pytest.fixture(scope="session")
def site(request, tmp_path_factory) -> Path:
    built = request.config.getoption("--built")
    if built:
        return Path(built)
    data = store.load_all()
    if not any(data.values()):
        pytest.skip("data/ is empty")
    out = tmp_path_factory.mktemp("site")
    api.build(data, out, site_dir=None, generated="2026-11-17T18:00:00Z", data_updated="2026-11-17")
    return out


def validator(registry, name: str) -> Draft202012Validator:
    schema = registry.contents(f"{BASE}{name}.schema.json")
    return Draft202012Validator(schema, registry=registry, format_checker=FormatChecker())


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_index(site, registry):
    index = load(site / "v1" / "index.json")
    validator(registry, "index").validate(index)
    ids = [s["id"] for s in index["series"]]
    assert len(ids) == len(set(ids))
    assert set(ids) <= set(BY_ID)
    for entry in index["series"]:
        assert (site / entry["endpoints"]["latest"]).exists()
        assert (site / entry["endpoints"]["all_csv"]).exists()


def test_every_series_file(site, registry):
    index = load(site / "v1" / "index.json")
    series_v = validator(registry, "series")
    point_v = validator(registry, "point")
    compact_v = validator(registry, "compact")
    rng = random.Random(17)
    for entry in index["series"]:
        folder = site / "v1" / entry["id"]
        everything = load(folder / "all.json")
        series_v.validate(everything)
        assert everything["count"] == entry["coverage"]["count"] == len(everything["observations"])
        point_v.validate(load(folder / "latest.json"))
        compact = load(folder / "compact.json")
        compact_v.validate(compact)
        assert len(compact["dates"]) == len(compact["values"]) == everything["count"]
        years = 0
        for year in entry["coverage"]["years"]:
            payload = load(folder / f"{year}.json")
            series_v.validate(payload)
            assert all(o["date"].startswith(str(year)) for o in payload["observations"])
            years += payload["count"]
        assert years == everything["count"]
        if entry["kind"] in ("daily", "monthly"):
            sample = rng.sample(everything["observations"], min(25, everything["count"]))
            for obs in [everything["observations"][0], everything["observations"][-1], *sample]:
                point = load(folder / f"{obs['date']}.json")
                point_v.validate(point)
                assert point["value"] == obs["value"]


def test_numbers_keep_their_published_text(site):
    for sid in ("udis", "fix", "inpc"):
        folder = site / "v1" / sid
        if not folder.exists():
            continue
        text = (folder / "compact.json").read_text()
        data = store.load(sid)
        assert f'"values":[{data[0].value},' in text
        assert text.rstrip().endswith(f"{data[-1].value}]}}")


def test_csv(site):
    index = load(site / "v1" / "index.json")
    for entry in index["series"]:
        rows = list(csv.DictReader(io.StringIO((site / entry["endpoints"]["all_csv"]).read_text())))
        assert list(rows[0].keys()) == api.CSV_COLUMNS
        assert len(rows) == entry["coverage"]["count"]
        assert all(r["checked"] in ("true", "false") for r in rows)


def test_source_links_point_to_the_dof(site):
    payload = load(site / "v1" / "fix" / "latest.json")
    source = payload["source"]
    assert source["url"].startswith("https://dof.gob.mx/nota_detalle.php?codigo=")
    assert str(source["dof_note"]) in source["url"]
