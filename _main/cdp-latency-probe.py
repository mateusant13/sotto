# -*- coding: utf-8 -*-
"""Measure every hop of the caption hot path against the owner's live Chrome.

READ-ONLY: GET /json/version and GET /json/list only. Never createTarget,
never navigate, never close a tab.

Reports, per hop:
  * wall time (ms) per call, N samples
  * bytes on the wire
  * calls per second the app makes on that hop (from source constants)
  * the mechanism, when a localhost call is slow (raw socket vs urllib vs
    keep-alive vs a separate process)

Usage: python _main/cdp-latency-probe.py [port] [samples]
"""

from __future__ import annotations

import http.client
import json
import os
import socket
import sys
import time
import urllib.request

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 9222
N = int(sys.argv[2]) if len(sys.argv) > 2 else 12
HOST = "127.0.0.1"


def _ms(t0):
    return (time.perf_counter() - t0) * 1000.0


def _stat(vals):
    s = sorted(vals)
    n = len(s)
    return {
        "n": n,
        "min": round(s[0], 2),
        "median": round(s[n // 2], 2),
        "mean": round(sum(s) / n, 2),
        "p95": round(s[min(n - 1, int(n * 0.95))], 2),
        "max": round(s[-1], 2),
    }


def raw_connect():
    out = []
    for _ in range(N):
        t = time.perf_counter()
        s = socket.socket()
        s.settimeout(3.0)
        s.connect((HOST, PORT))
        out.append(_ms(t))
        s.close()
    return out


def urllib_get(path, timeout=3.0):
    out, sizes = [], []
    for _ in range(N):
        t = time.perf_counter()
        with urllib.request.urlopen("http://%s:%d%s" % (HOST, PORT, path),
                                    timeout=timeout) as h:
            body = h.read()
        out.append(_ms(t))
        sizes.append(len(body))
    return out, sizes


def httpclient_keepalive(path, timeout=3.0):
    out, sizes = [], []
    conn = http.client.HTTPConnection(HOST, PORT, timeout=timeout)
    for _ in range(N):
        t = time.perf_counter()
        conn.request("GET", path)
        r = conn.getresponse()
        body = r.read()
        out.append(_ms(t))
        sizes.append(len(body))
    conn.close()
    return out, sizes


def main():
    print("probe host=%s port=%d samples=%d pid=%d"
          % (HOST, PORT, N, os.getpid()))
    for label, fn in (("raw-tcp-connect", raw_connect),):
        print(label, json.dumps(_stat(fn())))
    for path in ("/json/version", "/json/list"):
        vals, sizes = urllib_get(path)
        print("urllib %s" % path, json.dumps(_stat(vals)),
              "bytes=%d..%d" % (min(sizes), max(sizes)))
        vals, sizes = httpclient_keepalive(path)
        print("keepalive %s" % path, json.dumps(_stat(vals)),
              "bytes=%d..%d" % (min(sizes), max(sizes)))
    # What the app sees, using the app's own function, in THIS process.
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app",
                                    "webview"))
    try:
        import youtube_cdp_source as ycs
        vals = []
        for _ in range(N):
            t = time.perf_counter()
            tabs, others = ycs.list_targets(PORT)
            vals.append(_ms(t))
        print("app list_targets", json.dumps(_stat(vals)),
              "watch_tabs=%d others=%d" % (len(tabs), others))
        tabs, others = ycs.list_targets(PORT)
        blob = json.dumps(tabs)
        print("payload watch_tabs_bytes=%d total_tabs=%d"
              % (len(blob), len(tabs) + others))
    except Exception as exc:  # noqa: BLE001
        print("app list_targets FAILED", repr(exc))


if __name__ == "__main__":
    main()
