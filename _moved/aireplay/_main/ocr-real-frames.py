"""ocr-real-frames.py — extract real game frames (owner's own Fortnite clip) for OCR.

Reads:  I:\\importantes\\Videos\\Fortnite\\Fortnite 2024.01.03 - 20.57.10.07.DVR.mp4  (15.3 s, 1920x1080, 60 fps)
Writes: H:\\aireplay\\_main\\ocr-real\\NNN.png  (1 frame per second, 16 frames)
This does NOT capture the screen: it decodes a file.  No window, no downloads.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "ocr-real")
SRC = r"I:\importantes\Videos\Fortnite\Fortnite 2024.01.03 - 20.57.10.07.DVR.mp4"

os.makedirs(OUT, exist_ok=True)
for p in os.listdir(OUT):
    os.remove(os.path.join(OUT, p))

cmd = [
    "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
    "-i", SRC,
    "-vf", "fps=1",
    "-frames:v", "16",
    os.path.join(OUT, "%03d.png"),
]
print("RUN", " ".join(cmd), flush=True)
r = subprocess.run(cmd, capture_output=True, text=True, creationflags=0x08000000)
print("rc", r.returncode, flush=True)
print("stderr", r.stderr[-2000:], flush=True)
print("files", sorted(os.listdir(OUT)), flush=True)
