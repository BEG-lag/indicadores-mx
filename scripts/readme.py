"""Fill the generated blocks of README.md and README.es.md from the real data.

    uv run python scripts/readme.py           # rewrite the blocks
    uv run python scripts/readme.py --check   # exit 1 if a block is stale (used by the tests)

Blocks are delimited by HTML comments:

    <!-- gen:example fix/2026-11-13.json -->  the API file, pretty printed
    <!-- gen:csv tiie-28 3 -->                header and first rows of all.csv
    <!-- gen:coverage es -->                  coverage table (es or en)
    <!-- /gen -->

Examples use past dates on purpose: published values never change, so the README
stays true while the robot keeps adding new ones.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from indicadores_mx import api, store
from indicadores_mx.catalog import SERIES

ROOT = Path(__file__).resolve().parents[1]
READMES = [ROOT / "README.md", ROOT / "README.es.md"]
BLOCK = re.compile(r"(<!-- gen:(\w+) ([^>]*?) -->\n)(.*?)(<!-- /gen -->)", re.S)


def render_example(path: str, files: dict[str, dict[str, str]]) -> str:
    series, name = path.split("/", 1)
    # parse_float keeps each number's published text (8.904621, 1.000000).
    payload = json.loads(files[series][name], parse_float=api.RawNumber)
    text = api.dumps(payload, pretty=True).rstrip()
    return f"```json\n{text}\n```\n"


def render_csv(args: str, files: dict[str, dict[str, str]]) -> str:
    series, rows = args.split()
    lines = files[series]["all.csv"].splitlines()[: int(rows) + 1]
    return "```csv\n" + "\n".join(lines) + "\n```\n"


def render_coverage(lang: str, data: dict[str, list[store.Obs]]) -> str:
    head = {
        "es": "| Serie | `id` | Desde | Hasta | Valores | Con nota del DOF | Comparados con la nota | Estatus |",
        "en": "| Series | `id` | From | To | Values | With DOF note | Checked against the note | Status |",
    }[lang]
    lines = [head, "| --- | --- | --- | --- | ---: | ---: | ---: | --- |"]
    for series in SERIES:
        obs = data[series.id]
        if not obs:
            continue
        linked = sum(1 for o in obs if o.dof is not None)
        checked = sum(1 for o in obs if o.checked)
        name = series.short.es if lang == "es" else series.short.en
        lines.append(
            f"| {name} | `{series.id}` | {obs[0].key} | {obs[-1].key} | {len(obs):,} | "
            f"{linked:,} | {checked:,} | {series.status} |"
        )
    return "\n".join(lines) + "\n"


def generate(text: str, files, data, *, coverage: bool = True) -> str:
    def replace(match: re.Match[str]) -> str:
        kind, args = match.group(2), match.group(3).strip()
        if kind == "coverage" and not coverage:
            return match.group(0)
        if kind == "example":
            body = render_example(args, files)
        elif kind == "csv":
            body = render_csv(args, files)
        elif kind == "coverage":
            body = render_coverage(args, data)
        else:
            raise ValueError(f"unknown block {kind}")
        return f"{match.group(1)}{body}{match.group(5)}"

    return BLOCK.sub(replace, text)


def build_files(data) -> dict[str, dict[str, str]]:
    return {s.id: api.series_files(s, data[s.id]) for s in SERIES if data.get(s.id)}


def main(argv: list[str]) -> int:
    data = store.load_all()
    files = build_files(data)
    stale = []
    for path in READMES:
        old = path.read_text(encoding="utf-8")
        # The coverage table is a dated snapshot; only the examples must stay exact.
        new = generate(old, files, data, coverage="--check" not in argv)
        if new != old:
            if "--check" in argv:
                stale.append(path.name)
            else:
                path.write_text(new, encoding="utf-8")
                print(f"updated {path.name}")
    if stale:
        print(
            f"stale generated blocks in {', '.join(stale)}: run scripts/readme.py", file=sys.stderr
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
