"""The three probe types: ping, HTTPS (or HTTP) and TCP port.

Each probe returns a ``Result`` and never raises: a failure is a result too.
"""
from __future__ import annotations

import platform
import re
import socket
import ssl
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse


@dataclass
class Result:
    name: str
    kind: str                 # ping | https | tcp
    target: str
    up: bool
    latency_ms: float | None = None
    detail: str = ""
    extra: dict = field(default_factory=dict)


def ping(name: str, host: str, count: int = 3, timeout_s: int = 2) -> Result:
    """Uses the system ping, so it needs no root privileges."""
    system = platform.system().lower()
    if system == "windows":
        cmd = ["ping", "-n", str(count), "-w", str(timeout_s * 1000), host]
    elif system == "darwin":
        cmd = ["ping", "-c", str(count), "-W", str(timeout_s * 1000), host]
    else:
        cmd = ["ping", "-c", str(count), "-W", str(timeout_s), host]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=count * timeout_s + 5)
        text = out.stdout + out.stderr
    except (OSError, subprocess.TimeoutExpired) as exc:
        return Result(name, "ping", host, False, detail=f"ping failed to run: {exc}")
    return parse_ping(name, host, text, out.returncode)


def parse_ping(name: str, host: str, text: str, returncode: int) -> Result:
    loss = re.search(r"(\d+(?:\.\d+)?)% (?:packet )?loss", text)
    loss_pct = float(loss.group(1)) if loss else (0.0 if returncode == 0 else 100.0)
    avg = re.search(r"= [\d.]+/([\d.]+)/", text) or re.search(r"Average = (\d+)ms", text)
    latency = float(avg.group(1)) if avg else None
    up = returncode == 0 and loss_pct < 100
    return Result(name, "ping", host, up, latency, f"{loss_pct:.0f}% loss", {"loss_pct": loss_pct})


def _cert_days_left(host: str, port: int, timeout: float) -> int | None:
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as tls:
                not_after = tls.getpeercert().get("notAfter")
        expires = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        return (expires - datetime.now(timezone.utc)).days
    except Exception:
        return None


def https(name: str, url: str, expect: list[int] | None = None, contains: str | None = None,
          timeout_s: float = 8, insecure: bool = False) -> Result:
    expect = expect or [200, 301, 302, 303, 307, 308, 401, 403]
    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": "svccheck/0.1"})
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s, context=ctx) as resp:
            status, body = resp.status, resp.read(200_000).decode("utf-8", "replace")
            final = resp.geturl()
    except urllib.error.HTTPError as exc:  # a 4xx/5xx is still an answer from the service
        status, body, final = exc.code, "", url
    except Exception as exc:
        return Result(name, "https", url, False, detail=f"{type(exc).__name__}: {exc}"[:160])
    latency = (time.perf_counter() - start) * 1000
    ok = status in expect and (contains is None or contains in body)
    detail = f"HTTP {status}" + ("" if contains is None else (" + text found" if contains in body else " but text missing"))
    extra = {"status": status, "final_url": final}
    parsed = urlparse(url)
    if parsed.scheme == "https" and not insecure:
        extra["cert_days_left"] = _cert_days_left(parsed.hostname, parsed.port or 443, timeout_s)
    return Result(name, "https", url, ok, round(latency, 1), detail, extra)


def tcp(name: str, host: str, port: int, timeout_s: float = 4) -> Result:
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            pass
    except Exception as exc:
        return Result(name, "tcp", f"{host}:{port}", False, detail=f"{type(exc).__name__}")
    return Result(name, "tcp", f"{host}:{port}", True, round((time.perf_counter() - start) * 1000, 1), "port open")
