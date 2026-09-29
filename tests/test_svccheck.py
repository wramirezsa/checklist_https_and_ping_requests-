import json
from pathlib import Path

from svccheck import probes, runner
from svccheck.cli import EXAMPLES, main
from svccheck.probes import Result, parse_ping

LINUX = """PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.
64 bytes from 8.8.8.8: icmp_seq=1 ttl=117 time=11.9 ms
--- 8.8.8.8 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2003ms
rtt min/avg/max/mdev = 11.702/11.853/11.990/0.118 ms
"""
WINDOWS = """Ping statistics for 1.1.1.1:
    Packets: Sent = 3, Received = 3, Lost = 0 (0% loss),
Approximate round trip times in milli-seconds:
    Minimum = 9ms, Maximum = 11ms, Average = 10ms
"""
DOWN = """--- 192.0.2.45 ping statistics ---
3 packets transmitted, 0 received, 100% packet loss, time 2040ms
"""


def test_parse_ping_linux_windows_and_down():
    r = parse_ping("g", "8.8.8.8", LINUX, 0)
    assert r.up and r.latency_ms == 11.853
    w = parse_ping("c", "1.1.1.1", WINDOWS, 0)
    assert w.up and w.latency_ms == 10.0
    d = parse_ping("p", "192.0.2.45", DOWN, 1)
    assert not d.up and d.extra["loss_pct"] == 100.0


def test_example_targets_load(tmp_path):
    targets = runner.load_targets(Path(__file__).resolve().parent.parent / "targets.example.yml")
    assert {t["host"] for t in targets} == {"www.google.com", "8.8.8.8", "1.1.1.1"}


def test_run_uses_every_probe_type(monkeypatch):
    monkeypatch.setattr(probes, "ping", lambda n, h, **k: Result(n, "ping", h, True, 1.0))
    monkeypatch.setattr(probes, "https", lambda n, u, *a, **k: Result(n, "https", u, True, 5.0))
    monkeypatch.setattr(probes, "tcp", lambda n, h, p, **k: Result(n, "tcp", f"{h}:{p}", False))
    res = runner.run([{"name": "x", "host": "192.0.2.1", "ping": True, "url": "https://x.example", "tcp": [22]}])
    assert sorted(r.kind for r in res) == ["https", "ping", "tcp"]


def test_compare_flags_regressions_and_recoveries():
    before = runner.load(EXAMPLES / "snapshots" / "before.json")
    after = runner.load(EXAMPLES / "snapshots" / "after.json")
    rows = {(r["name"], r["kind"]): r["change"] for r in runner.compare(before, after)}
    assert rows[("File server", "tcp")] == "DOWN after work"
    assert rows[("Print server", "ping")] == "recovered"
    assert rows[("New VLAN gateway", "ping")] == "new check"
    assert rows[("Google", "https")] == "still up"


def test_compare_exit_code_signals_regression(tmp_path):
    rc = main(["compare", str(EXAMPLES / "snapshots" / "before.json"),
               str(EXAMPLES / "snapshots" / "after.json"), "--out", str(tmp_path)])
    assert rc == 1
    assert "are down now" in (tmp_path / "before-after.html").read_text()


def test_snapshot_round_trip(tmp_path):
    p = runner.save([Result("a", "ping", "192.0.2.1", True, 1.0)], "before", tmp_path)
    assert json.loads(p.read_text())["results"][0]["target"] == "192.0.2.1"
