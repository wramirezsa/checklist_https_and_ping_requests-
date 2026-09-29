"""Console tables and the HTML before/after report."""
from __future__ import annotations

import html
from pathlib import Path

COLORS = {"DOWN after work": "#991b1b", "down before and after": "#a16207", "not checked after": "#a16207",
          "recovered": "#166534", "new check": "#1d4ed8", "still up": "#166534"}


def _e(v) -> str:
    return html.escape("" if v is None else str(v))


def _state(r: dict | None) -> str:
    if r is None:
        return "-"
    lat = f" {r['latency_ms']:.0f} ms" if r.get("latency_ms") is not None else ""
    return ("UP" if r["up"] else "DOWN") + lat + (f" ({r['detail']})" if r.get("detail") else "")


def console_run(results) -> str:
    lines = [f"{'CHECK':<24} {'TYPE':<6} {'TARGET':<34} {'STATE':<6} DETAIL"]
    for r in sorted(results, key=lambda r: (r.up, r.name)):
        lat = f"{r.latency_ms:.0f} ms " if r.latency_ms is not None else ""
        lines.append(f"{r.name[:24]:<24} {r.kind:<6} {r.target[:34]:<34} {'UP' if r.up else 'DOWN':<6} {lat}{r.detail}")
    up = sum(r.up for r in results)
    lines.append(f"\n{up}/{len(results)} checks up")
    return "\n".join(lines)


def console_compare(rows) -> str:
    lines = [f"{'CHANGE':<22} {'CHECK':<24} {'TYPE':<6} TARGET"]
    for r in rows:
        lines.append(f"{r['change']:<22} {r['name'][:24]:<24} {r['kind']:<6} {r['target']}")
    regress = sum(r["change"] == "DOWN after work" for r in rows)
    lines.append(f"\n{regress} regression(s) out of {len(rows)} checks")
    return "\n".join(lines)


def html_compare(rows, before: dict, after: dict, title: str) -> str:
    counts = {}
    for r in rows:
        counts[r["change"]] = counts.get(r["change"], 0) + 1
    order = ["DOWN after work", "down before and after", "not checked after", "recovered", "new check", "still up"]
    cards = "".join(f'<div class="card"><b style="color:{COLORS[c]}">{counts.get(c, 0)}</b><span>{_e(c)}</span></div>'
                    for c in order if counts.get(c) or c in ("DOWN after work", "still up"))
    body = "".join(
        f'<tr><td style="color:{COLORS[r["change"]]};font-weight:600">{_e(r["change"])}</td>'
        f"<td>{_e(r['group'])}</td><td>{_e(r['name'])}</td><td>{_e(r['kind'])}</td><td><code>{_e(r['target'])}</code></td>"
        f"<td>{_e(_state(r['before']))}</td><td>{_e(_state(r['after']))}</td></tr>" for r in rows)
    verdict = ("Everything that was up before the work is still up."
               if not counts.get("DOWN after work") else
               f"{counts['DOWN after work']} service(s) that were up before the work are down now.")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Service check - {_e(title)}</title>
<style>
 body{{font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;max-width:1100px;margin:0 auto;padding:40px 24px;color:#1f2937}}
 h1{{font-size:26px;margin:0 0 4px}} h2{{font-size:18px;margin:32px 0 12px;border-bottom:2px solid #e5e7eb;padding-bottom:6px}}
 table{{width:100%;border-collapse:collapse;font-size:13px}} th{{text-align:left;background:#f9fafb;padding:8px;border-bottom:2px solid #e5e7eb}}
 td{{padding:6px 8px;border-bottom:1px solid #f3f4f6;vertical-align:top}} code{{font-size:12px}}
 .meta{{color:#6b7280;font-size:14px}} .cards{{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0}}
 .card{{border:1px solid #e5e7eb;border-radius:6px;padding:10px 16px;min-width:150px}} .card b{{display:block;font-size:26px;line-height:1.1}}
 .card span{{font-size:13px;color:#374151}} .verdict{{font-size:17px;font-weight:600}}
</style></head><body>
<h1>Service check: before and after</h1>
<p class="meta">{_e(title)}<br>Before: {_e(before['taken_at'])} from {_e(before.get('from_host'))} &middot;
After: {_e(after['taken_at'])} from {_e(after.get('from_host'))}</p>
<p class="verdict">{_e(verdict)}</p>
<div class="cards">{cards}</div>
<h2>Every check</h2>
<table><thead><tr><th>Change</th><th>Group</th><th>Check</th><th>Type</th><th>Target</th><th>Before</th><th>After</th></tr></thead>
<tbody>{body}</tbody></table>
</body></html>"""


def write_html(text: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
