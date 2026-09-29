"""Load targets, run every probe in parallel, save and compare snapshots."""
from __future__ import annotations

import json
import socket
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import yaml

from . import probes
from .probes import Result


def load_targets(path: Path) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    targets = []
    for group, items in (data.get("groups") or {}).items():
        for t in items or []:
            t = dict(t)
            t.setdefault("group", group)
            targets.append(t)
    return targets


def _probe(t: dict) -> list[Result]:
    name = t.get("name") or t.get("host") or t.get("url")
    out = []
    if t.get("ping"):
        out.append(probes.ping(name, t["ping"] if isinstance(t["ping"], str) else t["host"]))
    if t.get("url"):
        out.append(probes.https(name, t["url"], t.get("expect"), t.get("contains"),
                                insecure=bool(t.get("insecure"))))
    for port in t.get("tcp", []) or []:
        out.append(probes.tcp(name, t["host"], int(port)))
    for r in out:
        r.extra["group"] = t.get("group", "")
    return out


def run(targets: list[dict], workers: int = 16) -> list[Result]:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = [r for batch in pool.map(_probe, targets) for r in batch]
    return results


def save(results: list[Result], label: str, folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    now = datetime.now().astimezone()
    path = folder / f"{now:%Y%m%d-%H%M%S}-{label}.json"
    path.write_text(json.dumps({
        "label": label,
        "taken_at": now.isoformat(timespec="seconds"),
        "from_host": socket.gethostname(),
        "results": [asdict(r) for r in results],
    }, indent=2), encoding="utf-8")
    return path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def key(r: dict) -> tuple:
    return (r["name"], r["kind"], r["target"])


def compare(before: dict, after: dict) -> list[dict]:
    """One row per check with its state before and after."""
    b = {key(r): r for r in before["results"]}
    a = {key(r): r for r in after["results"]}
    rows = []
    for k in sorted(set(b) | set(a), key=lambda k: (k[0], k[1])):
        rb, ra = b.get(k), a.get(k)
        if rb and ra:
            change = ("still up" if rb["up"] and ra["up"] else
                      "DOWN after work" if rb["up"] and not ra["up"] else
                      "recovered" if not rb["up"] and ra["up"] else "down before and after")
        elif ra:
            change = "new check"
        else:
            change = "not checked after"
        rows.append({"name": k[0], "kind": k[1], "target": k[2], "before": rb, "after": ra, "change": change,
                     "group": (ra or rb)["extra"].get("group", "")})
    order = {"DOWN after work": 0, "down before and after": 1, "not checked after": 2, "recovered": 3,
             "new check": 4, "still up": 5}
    return sorted(rows, key=lambda r: (order[r["change"]], r["group"], r["name"]))
