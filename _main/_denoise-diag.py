# -*- coding: utf-8 -*-
"""Diagnose the live worker file: line endings, and this lane's four blocks."""
import hashlib
import sys

P = r"H:\sotto\worker\sotto_worker.py"
raw = open(P, "rb").read()
crlf = raw.count(b"\r\n")
lf = raw.count(b"\n")
print("bytes=%d crlf=%d bare_lf=%d lone_cr=%d" % (len(raw), crlf, lf - crlf, raw.count(b"\r") - crlf))
print("sha256(raw) = %s" % hashlib.sha256(raw).hexdigest())

norm = raw.replace(b"\r\n", b"\n")
print("sha256(norm) = %s  (%d B)" % (hashlib.sha256(norm).hexdigest(), len(norm)))

for pat in (
    b"self.denoiser = None",
    b"pcm_chunk = self.denoiser.process(pcm_chunk)",
    b"**_denoise_fields,",
    b'state="denoise"',
    b"def _denoise_gate_from_config",
):
    print("  %-50s %d" % (pat.decode(), norm.count(pat)))

k = norm.index(b'state="denoise"')
print("--- 200 B before .. 340 B after `state=\"denoise\"` ---")
print(repr(norm[k - 200 : k + 340]))
