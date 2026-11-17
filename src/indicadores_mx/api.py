"""Build the static, versioned API (``/v1``) and the site into one folder.

Layout (every path relative to https://beg-lag.github.io/indicadores-mx/):

    v1/index.json                    catalog: metadata, coverage, latest value of each series
    v1/<series>/latest.json          the most recent observation
    v1/<series>/<YYYY>.json          observations of one calendar year
    v1/<series>/all.json             every observation
    v1/<series>/all.csv              every observation, CSV (UTF-8, comma, header row)
    v1/<series>/compact.json         {"dates": [...], "values": [...]}, for charts
    v1/<series>/<YYYY-MM-DD>.json    one day (daily series)
    v1/<series>/<YYYY-MM>.json       one month (monthly series)
    schema/v1/*.schema.json          JSON Schemas of the files above

Numbers are written with the exact decimal text published (``8.904621``), so a
JSON parser gets the nearest double and the file keeps the official precision.
"""

from __future__ import annotations

import csv
import io
import json
import re
import shutil
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from . import __version__
from .catalog import BY_ID, SERIES, SIDOF_INDICATORS, Series
from .dates import to_sidof
from .dof import dof_note_url
from .store import ROOT, DofRef, Obs

BASE_URL = "https://beg-lag.github.io/indicadores-mx/"
API_VERSION = "v1"
SCHEMA_DIR = ROOT / "schema"

DISCLAIMER = {
    "es": (
        "Espejo no oficial. Solo el Diario Oficial de la Federación y las instituciones que "
        "emiten cada indicador tienen validez oficial. No constituye opinión legal ni asesoría "
        "fiscal."
    ),
    "en": (
        "Unofficial mirror. Only the DOF and the issuing institutions are authoritative. Not "
        "legal or tax advice."
    ),
}

FORMULAS = {
    "inflacion-mensual": "(INPC[t] / INPC[t-1] - 1) * 100, two decimals, half up",
    "inflacion-anual": "(INPC[t] / INPC[t-12] - 1) * 100, two decimals, half up",
}


class RawNumber:
    """A number that serializes with its exact published decimal text."""

    __slots__ = ("text",)

    def __init__(self, text: str) -> None:
        float(text)  # validate
        self.text = text

    def __eq__(self, other: object) -> bool:
        return isinstance(other, RawNumber) and other.text == self.text

    def __hash__(self) -> int:
        return hash(self.text)

    def __repr__(self) -> str:
        return self.text


_MARK = re.compile(r'"\\u0000N([-0-9.]+)\\u0000"')


def _default(value: Any) -> Any:
    if isinstance(value, RawNumber):
        return f"\x00N{value.text}\x00"
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def dumps(payload: Any, *, pretty: bool = False) -> str:
    """JSON with ``RawNumber`` written verbatim (compact unless ``pretty``)."""
    text = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2 if pretty else None,
        separators=(",", ": ") if pretty else (",", ":"),
        default=_default,
    )
    return _MARK.sub(r"\1", text) + "\n"


# ------------------------------------------------------------------ observations


def _ref(ref: DofRef) -> dict[str, Any]:
    return {
        "dof_date": ref.day.isoformat(),
        "dof_note": ref.note,
        "url": dof_note_url(ref.note, ref.day),
    }


def source_of(series: Series, obs: Obs) -> dict[str, Any]:
    origin = obs.origin or series.default_origin
    source: dict[str, Any] = {"origin": origin}
    if obs.dof is not None:
        source.update(_ref(obs.dof))
    elif origin == "sidof" and series.sidof_code is not None:
        day = to_sidof(date.fromisoformat(obs.key))
        source["url"] = f"{SIDOF_INDICATORS}/{series.sidof_code}/{day}/{day}"
    elif origin == "inegi":
        source["url"] = next(s["url"] for s in series.sources if s["id"] == "inegi")
    elif origin == "derived":
        source["from"] = series.derived_from
        source["formula"] = FORMULAS[series.id]
    source["checked"] = obs.checked
    if obs.correction is not None:
        source["correction"] = _ref(obs.correction)
    if obs.remark:
        source["remark"] = obs.remark
    return source


def valid_to(series: Series, observations: list[Obs], index: int) -> str | None:
    if index + 1 < len(observations):
        nxt = date.fromisoformat(observations[index + 1].key)
        return (nxt - timedelta(days=1)).isoformat()
    return series.ended


def observation(series: Series, observations: list[Obs], index: int) -> dict[str, Any]:
    obs = observations[index]
    data: dict[str, Any] = {"date": obs.key, "value": RawNumber(obs.value)}
    if series.kind == "step":
        data["valid_to"] = valid_to(series, observations, index)
    if "term_days" in obs.extra:
        data["term_days"] = obs.extra["term_days"]
    data["source"] = source_of(series, obs)
    return data


def _year(obs: Obs) -> int:
    return int(obs.key[:4])


# ------------------------------------------------------------------ files


def _meta(series: Series) -> dict[str, Any]:
    return {
        "series": series.id,
        "name": series.name.to_json(),
        "unit": series.unit_code,
        "unit_label": series.unit.to_json(),
    }


def series_files(series: Series, observations: list[Obs]) -> dict[str, str]:
    """Relative path (inside v1/<id>/) to file content."""
    files: dict[str, str] = {}
    rendered = [observation(series, observations, i) for i in range(len(observations))]
    meta = _meta(series)

    years: dict[int, list[dict[str, Any]]] = {}
    for obs, item in zip(observations, rendered, strict=True):
        years.setdefault(_year(obs), []).append(item)
    for year, items in years.items():
        files[f"{year}.json"] = dumps(
            {**meta, "year": year, "count": len(items), "observations": items}
        )
    files["all.json"] = dumps(
        {
            **meta,
            "count": len(rendered),
            "first": observations[0].key,
            "last": observations[-1].key,
            "observations": rendered,
        }
    )
    files["compact.json"] = dumps(
        {
            "series": series.id,
            "unit": series.unit_code,
            "dates": [o.key for o in observations],
            "values": [RawNumber(o.value) for o in observations],
        }
    )
    latest = dict(rendered[-1])
    if len(rendered) > 1:
        previous = rendered[-2]
        latest["previous"] = {"date": previous["date"], "value": previous["value"]}
    files["latest.json"] = dumps({**meta, **latest})
    if series.kind in ("daily", "monthly"):
        for item in rendered:
            files[f"{item['date']}.json"] = dumps({**meta, **item})
    files["all.csv"] = to_csv(series, rendered)
    return files


CSV_COLUMNS = [
    "date",
    "value",
    "valid_to",
    "term_days",
    "origin",
    "dof_date",
    "dof_note",
    "url",
    "checked",
    "correction_dof_date",
    "correction_dof_note",
    "remark",
]


def to_csv(series: Series, rendered: list[dict[str, Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for item in rendered:
        src = item["source"]
        corr = src.get("correction") or {}
        writer.writerow(
            [
                item["date"],
                item["value"].text,
                item.get("valid_to") or "",
                item.get("term_days", ""),
                src["origin"],
                src.get("dof_date", ""),
                src.get("dof_note", ""),
                src.get("url", ""),
                "true" if src["checked"] else "false",
                corr.get("dof_date", ""),
                corr.get("dof_note", ""),
                src.get("remark", ""),
            ]
        )
    return buffer.getvalue()


def catalog_entry(series: Series, observations: list[Obs]) -> dict[str, Any]:
    latest = observations[-1]
    years = sorted({_year(o) for o in observations})
    path = f"{API_VERSION}/{series.id}/"
    endpoints = {
        "latest": f"{path}latest.json",
        "all_json": f"{path}all.json",
        "all_csv": f"{path}all.csv",
        "compact": f"{path}compact.json",
        "year": f"{path}{{YYYY}}.json",
    }
    if series.kind == "daily":
        endpoints["date"] = f"{path}{{YYYY-MM-DD}}.json"
    elif series.kind == "monthly":
        endpoints["month"] = f"{path}{{YYYY-MM}}.json"
    entry: dict[str, Any] = {
        "id": series.id,
        "name": series.name.to_json(),
        "short": series.short.to_json(),
        "group": series.group,
        "kind": series.kind,
        "frequency": series.frequency.to_json(),
        "unit": series.unit_code,
        "unit_label": series.unit.to_json(),
        "decimals": series.decimals,
        "issuer": series.issuer,
        "description": series.description.to_json(),
        "date_meaning": series.date_meaning.to_json(),
        "legal_basis": series.legal_basis.to_json(),
        "status": series.status,
        "coverage": {
            "first": observations[0].key,
            "last": latest.key,
            "count": len(observations),
            "years": years,
            "with_dof_note": sum(1 for o in observations if o.dof is not None),
            "checked_against_note": sum(1 for o in observations if o.checked),
        },
        "latest": {"date": latest.key, "value": RawNumber(latest.value)},
        "sources": list(series.sources),
        "endpoints": endpoints,
    }
    if series.derived_from:
        entry["derived_from"] = series.derived_from
    if series.ended:
        entry["ended"] = series.ended
    return entry


def build(
    data: dict[str, list[Obs]],
    out: Path,
    *,
    site_dir: Path | None = None,
    generated: str | None = None,
    data_updated: str | None = None,
) -> dict[str, Any]:
    """Write the API (and copy the site) into ``out``. Returns a size report."""
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    if site_dir is not None and site_dir.exists():
        shutil.copytree(site_dir, out, dirs_exist_ok=True)
    generated = generated or datetime.now(UTC).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    api = out / API_VERSION
    files = 0
    entries = []
    for series in SERIES:
        observations = data.get(series.id) or []
        if not observations:
            continue
        folder = api / series.id
        folder.mkdir(parents=True, exist_ok=True)
        for name, content in series_files(series, observations).items():
            (folder / name).write_text(content, encoding="utf-8")
            files += 1
        entries.append(catalog_entry(series, observations))
    index = {
        "name": "indicadores-mx",
        "version": __version__,
        "api_version": API_VERSION,
        "generated": generated,
        "data_updated": data_updated or generated[:10],
        "base_url": BASE_URL,
        "repository": "https://github.com/BEG-lag/indicadores-mx",
        "license": {"code": "MIT", "data": "CC0-1.0"},
        "disclaimer": DISCLAIMER,
        "total_observations": sum(e["coverage"]["count"] for e in entries),
        "series": entries,
    }
    (api / "index.json").write_text(dumps(index, pretty=True), encoding="utf-8")
    files += 1
    schema_out = out / "schema"
    shutil.copytree(SCHEMA_DIR, schema_out, dirs_exist_ok=True)
    (out / ".nojekyll").write_text("", encoding="utf-8")
    size = sum(p.stat().st_size for p in api.rglob("*") if p.is_file())
    return {"series": len(entries), "api_files": files, "api_bytes": size}


__all__ = ["BY_ID", "build", "dumps"]
