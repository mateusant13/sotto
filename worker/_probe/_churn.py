"""Disk-churn generator for the boot A/B: reads the encoder weights in a loop.

    python worker/_probe/_churn.py <seconds>

Exists to put the box's disk in the state the OWNER's log shows (`owner gaming`:
65-206 s to `model-loaded`) so a boot change can be judged under that condition
instead of only on an idle disk. Read-only; deletes nothing.
"""
import sys
import time

REPO = "H:/sotto"
P = REPO + "/worker/models/nemotron-3.5-asr-ptbr-onnx-int4/encoder.onnx.data"
end = time.time() + float(sys.argv[1] if len(sys.argv) > 1 else 120)
while time.time() < end:
    with open(P, "rb", buffering=0) as fh:
        while fh.read(4 << 20):
            pass
