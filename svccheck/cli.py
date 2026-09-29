"""svccheck run | compare | demo"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .report import console_compare, console_run, html_compare, write_html
from .runner import compare, load, load_targets, run, save

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def _compare_and_report(before_path: Path, after_path: Path, out: Path, title: str) -> int:
    before, after = load(before_path), load(after_path)
    rows = compare(before, after)
    print(console_compare(rows))
    html_path = write_html(html_compare(rows, before, after, title), out / "before-after.html")
    print(f"\n  report {html_path}")
    return 1 if any(r["change"] == "DOWN after work" for r in rows) else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="svccheck", description="Before/after reachability checks: ping, HTTPS and TCP.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run every check once and save a snapshot")
    r.add_argument("--targets", type=Path, default=Path("targets.yml"))
    r.add_argument("--label", default="check", help="e.g. before, after")
    r.add_argument("--out", type=Path, default=Path("snapshots"))
    r.add_argument("--compare", type=Path, help="a previous snapshot to compare this run against")
    r.add_argument("--title", default="Change window")

    c = sub.add_parser("compare", help="compare two saved snapshots")
    c.add_argument("before", type=Path)
    c.add_argument("after", type=Path)
    c.add_argument("--out", type=Path, default=Path("snapshots"))
    c.add_argument("--title", default="Change window")

    d = sub.add_parser("demo", help="compare the two bundled sample snapshots (offline)")
    d.add_argument("--out", type=Path, default=Path("output"))

    args = ap.parse_args(argv)

    if args.cmd == "demo":
        return _compare_and_report(EXAMPLES / "snapshots" / "before.json", EXAMPLES / "snapshots" / "after.json",
                                   args.out, "Sample change window (fictional)") and 0

    if args.cmd == "compare":
        return _compare_and_report(args.before, args.after, args.out, args.title)

    if not args.targets.exists():
        print(f"{args.targets} not found. Copy targets.example.yml to targets.yml and edit it.", file=sys.stderr)
        return 2
    targets = load_targets(args.targets)
    results = run(targets)
    print(console_run(results))
    snap = save(results, args.label, args.out)
    print(f"\n  snapshot {snap}")
    if args.compare:
        print()
        return _compare_and_report(args.compare, snap, args.out, args.title)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
