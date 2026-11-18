"""Command line: ``indicadores-mx backfill | update | verify-steps | annual | build | stats``."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Sequence
from datetime import date, timedelta
from pathlib import Path

from . import __version__, annual, api, pipeline, store
from .catalog import BY_ID, SERIES
from .dates import today_mx
from .sidof import Sidof
from .store import DATA_DIR, ROOT, Obs

CACHE_DIR = ROOT / ".cache" / "sidof"
SUMMARY_FILE = ROOT / ".cache" / "data-summary.txt"
STEP_IDS = tuple(s.id for s in SERIES if s.kind == "step")


def make_client(args: argparse.Namespace, today: date) -> Sidof:
    """The SIDOF client (tests replace this to inject a recorded transport)."""
    cache = None if args.no_cache else Path(args.cache)
    return Sidof(cache_dir=cache, delay=args.delay, today=today)


def _run(args: argparse.Namespace) -> pipeline.Run:
    today = date.fromisoformat(args.today) if args.today else today_mx()
    return pipeline.Run(sidof=make_client(args, today), today=today)


def _finish(
    run: pipeline.Run,
    results: dict[str, list[Obs]],
    data_dir: Path,
    started: float,
    summary_file: Path = SUMMARY_FILE,
) -> int:
    elapsed = time.monotonic() - started
    run.log(
        f"{run.sidof.requests} SIDOF requests, {run.sidof.cache_hits} cache hits, {elapsed:.0f} s"
    )
    for key in sorted(run.stats):
        run.log(f"  {key}: {run.stats[key]}")
    if run.problems:
        print(f"\n{len(run.problems)} problem(s); nothing was written.", file=sys.stderr)
        for message in run.problems[:50]:
            print(f"  - {message}", file=sys.stderr)
        return 1
    changed = [sid for sid, obs in results.items() if store.write(sid, obs, data_dir)]
    run.log(f"written: {', '.join(changed)}" if changed else "no changes")
    summary = summarize(store.load_all(data_dir))
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    summary_file.write_text(summary + "\n", encoding="utf-8")
    run.log(summary)
    return 0


def summarize(data: dict[str, list[Obs]]) -> str:
    """One line for the commit message of the scheduled workflow."""
    parts = []
    for sid in ("fix", "udis", "tiie-28", "inpc"):
        if data.get(sid):
            parts.append(f"{sid} {data[sid][-1].key}")
    return "data through " + ", ".join(parts)


# ---------------------------------------------------------------- backfill


def cmd_backfill(args: argparse.Namespace) -> int:
    started = time.monotonic()
    run = _run(args)
    data_dir = Path(args.data)
    today = run.today
    ids = args.series or [*pipeline.DAILY_IDS, "udis", "inpc"]
    results: dict[str, list[Obs]] = {}

    daily = [sid for sid in ids if sid in pipeline.DAILY_IDS]
    values: dict[str, dict[date, set[str]]] = {}
    for sid in pipeline.DAILY_IDS:
        values[sid] = pipeline.sidof_values(run, sid, date(1991, 1, 1), today)
        run.log(f"{sid}: {sum(len(v) for v in values[sid].values())} SIDOF values")
    scan = set().union(*(set(v) for v in values.values()))
    scan |= set(pipeline.iter_days(today - timedelta(days=7), today))
    scan |= {d for d in _cached_days() if d <= today}
    scan_days = sorted(scan)
    run.log(f"{len(scan_days)} DOF days to scan")
    plan = pipeline.DailyPlan(
        verify_all_after=date.fromisoformat(args.verify_all_after),
        verify_all=args.verify_all,
        verify_all_before=date.fromisoformat(args.verify_all_before),
    )
    for sid in daily:
        results[sid] = pipeline.build_daily(run, sid, values[sid], scan_days, plan)
        run.log(f"{sid}: {len(results[sid])} observations")

    if "udis" in ids:
        results["udis"] = pipeline.build_udis(
            run, pipeline.UDIS_START, today + timedelta(days=45), scan_days
        )
        run.log(f"udis: {len(results['udis'])} observations")

    if "inpc" in ids:
        csv_values = pipeline.inegi_csv(CACHE_DIR.parent)
        inpc = pipeline.build_inpc(run, csv_values)
        results["inpc"] = inpc
        monthly, yearly = pipeline.derive_inflation(inpc)
        results["inflacion-mensual"] = monthly
        results["inflacion-anual"] = yearly
        _check_printed_variations(run, inpc, monthly)
        run.log(f"inpc: {len(inpc)} months")

    return _finish(run, results, data_dir, started)


def _cached_days() -> list[date]:
    folder = CACHE_DIR / "notas"
    if not folder.exists():
        return []
    return [date.fromisoformat(p.stem) for p in folder.glob("*.json")]


def _check_printed_variations(run: pipeline.Run, inpc: list[Obs], monthly: list[Obs]) -> None:
    """The derived monthly inflation must equal the variation printed in each DOF note."""
    derived = {o.key: o.value for o in monthly}
    for obs in inpc:
        if obs.dof is None:
            continue
        note = run.sidof.note((obs.correction or obs.dof).note)
        parsed = pipeline.dof.parse_inpc_monthly(note.text)
        if parsed is None or parsed.variation is None:
            continue
        if obs.key in derived and pipeline.Decimal(derived[obs.key]) != pipeline.Decimal(
            parsed.variation
        ):
            run.problem(
                f"inflacion-mensual {obs.key}: computed {derived[obs.key]}, "
                f"DOF note prints {parsed.variation}"
            )
        else:
            run.count("inflacion-mensual:checked")


# ---------------------------------------------------------------- update


def cmd_update(args: argparse.Namespace) -> int:
    started = time.monotonic()
    run = _run(args)
    data_dir = Path(args.data)
    today = run.today
    old = store.load_all(data_dir)
    groups = set(args.group or ["daily", "udis", "inpc"])
    results: dict[str, list[Obs]] = {}
    window_start = today - timedelta(days=args.days - 1)

    if "daily" in groups:
        scan_days = list(pipeline.iter_days(window_start, today))
        plan = pipeline.DailyPlan(verify_all_after=window_start, verify_all=True)
        for sid in pipeline.DAILY_IDS:
            values = pipeline.sidof_values(run, sid, window_start, today)
            fresh = pipeline.build_daily(run, sid, values, scan_days, plan)
            results[sid] = merge(run, sid, old.get(sid, []), fresh)

    if "udis" in groups:
        previous = old.get("udis", [])
        last = date.fromisoformat(previous[-1].key) if previous else pipeline.UDIS_START
        start = max(pipeline.UDIS_START, last - timedelta(days=45))
        pub_days = list(pipeline.iter_days(window_start, today))
        fresh = pipeline.build_udis(run, start, today + timedelta(days=60), pub_days)
        results["udis"] = merge(run, "udis", previous, fresh)

    if "inpc" in groups:
        inpc = pipeline.build_inpc(run, {}, existing=old.get("inpc", []))
        results["inpc"] = inpc
        monthly, yearly = pipeline.derive_inflation(inpc)
        results["inflacion-mensual"] = monthly
        results["inflacion-anual"] = yearly
        new_months = [o for o in inpc if o.key not in {x.key for x in old.get("inpc", [])}]
        _check_printed_variations(run, new_months, monthly)

    return _finish(run, results, data_dir, started, Path(args.summary))


def merge(run: pipeline.Run, sid: str, old: list[Obs], fresh: list[Obs]) -> list[Obs]:
    """Append new observations; a published value must never change."""
    by_key = {o.key: o for o in old}
    added = 0
    for obs in fresh:
        before = by_key.get(obs.key)
        if before is None:
            by_key[obs.key] = obs
            added += 1
        elif not pipeline.same(before.value, obs.value):
            run.problem(f"{sid} {obs.key} changed after publication: {before.value} -> {obs.value}")
        elif (before.dof is None and obs.dof is not None) or (obs.checked and not before.checked):
            by_key[obs.key] = before.with_(dof=before.dof or obs.dof, checked=True)
    if added:
        run.log(f"{sid}: {added} new")
    return sorted(by_key.values(), key=lambda o: o.key)


# ---------------------------------------------------------------- steps


def cmd_verify_steps(args: argparse.Namespace) -> int:
    started = time.monotonic()
    run = _run(args)
    data_dir = Path(args.data)
    data = store.load_all(data_dir)
    results = pipeline.verify_steps(run, data, STEP_IDS)
    return _finish(run, results, data_dir, started)


def cmd_annual(args: argparse.Namespace) -> int:
    started = time.monotonic()
    run = _run(args)
    data_dir = Path(args.data)
    data = store.load_all(data_dir)
    results, report = annual.detect(run, data, args.kind, args.since)
    Path(args.report).write_text(report, encoding="utf-8")
    run.log(report)
    return _finish(run, results, data_dir, started)


# ---------------------------------------------------------------- build


def cmd_build(args: argparse.Namespace) -> int:
    out = Path(args.out)
    data = store.load_all(Path(args.data))
    report = api.build(
        data,
        out,
        site_dir=ROOT / "site",
        generated=args.generated,
        data_updated=args.data_updated or pipeline.git_head_date(ROOT),
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    data = store.load_all(Path(args.data))
    for series in SERIES:
        obs = data.get(series.id, [])
        if not obs:
            print(f"{series.id:24} (empty)")
            continue
        linked = sum(1 for o in obs if o.dof is not None)
        checked = sum(1 for o in obs if o.checked)
        print(
            f"{series.id:24} {len(obs):6} values  {obs[0].key} .. {obs[-1].key}  "
            f"dof {linked:6}  checked {checked:6}"
        )
    return 0


# ---------------------------------------------------------------- main


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="indicadores-mx", description=__doc__)
    parser.add_argument("--version", action="version", version=f"indicadores-mx {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--data", default=str(DATA_DIR), help="data directory")
        p.add_argument("--cache", default=str(CACHE_DIR), help="SIDOF response cache")
        p.add_argument("--no-cache", action="store_true", help="do not read or write the cache")
        p.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
        p.add_argument("--today", help="pin today (YYYY-MM-DD, Mexico City)")
        p.add_argument("--summary", default=str(SUMMARY_FILE), help="one-line summary output")

    p = sub.add_parser("backfill", help="rebuild the daily and monthly series from the start")
    common(p)
    p.add_argument("--series", nargs="*", choices=[*pipeline.DAILY_IDS, "udis", "inpc"])
    p.add_argument("--verify-all-after", default="2025-01-01")
    p.add_argument("--verify-all-before", default="1996-01-01")
    p.add_argument("--verify-all", action="store_true", help="compare every value with its note")
    p.set_defaults(func=cmd_backfill)

    p = sub.add_parser("update", help="append new values (what the scheduled workflow runs)")
    common(p)
    p.add_argument("--days", type=int, default=10, help="days to re-read, including today")
    p.add_argument("--group", nargs="*", choices=["daily", "udis", "inpc"])
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("verify-steps", help="check minimum wages and UMA against their notes")
    common(p)
    p.set_defaults(func=cmd_verify_steps)

    p = sub.add_parser("annual", help="look for a new minimum wage resolution or UMA value")
    common(p)
    p.add_argument("--kind", choices=["salario-minimo", "uma"], required=True)
    p.add_argument("--since", help="first DOF date to scan (default: 75 days ago)")
    p.add_argument("--report", default=str(ROOT / ".cache" / "annual-report.md"))
    p.set_defaults(func=cmd_annual)

    p = sub.add_parser("build", help="build the static API and site into a folder")
    p.add_argument("--data", default=str(DATA_DIR))
    p.add_argument("--out", default=str(ROOT / "_site"))
    p.add_argument("--generated", help="ISO timestamp to stamp (default: now, UTC)")
    p.add_argument("--data-updated", help="date of the last data change (default: from git)")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("stats", help="coverage of each series")
    p.add_argument("--data", default=str(DATA_DIR))
    p.set_defaults(func=cmd_stats)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["BY_ID", "main"]
