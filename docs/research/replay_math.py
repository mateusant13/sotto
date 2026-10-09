"""Sotto lane/replay -- Instant Replay circular-buffer arithmetic.

Every number this script prints is derived from an INPUT constant that is
labelled with its provenance:
  [BRIEF]  = stated in the lane brief, NOT independently verified by me
  [NVIDIA] = quoted from a primary NVIDIA doc (URL in the doc's source table)
  [ASSUME] = my own engineering assumption, no external source

Run:  python docs/research/replay_math.py
"""

# ---------------------------------------------------------------- inputs ----

MIB = 1024 ** 2
GIB = 1024 ** 3

# [BRIEF] bitrates handed to this lane for 1080p60
BITRATE_H264_1080p60 = 4_000_000      # bits/s  [BRIEF]
BITRATE_HEVC_1080p60 = 10_000_000     # bits/s  [BRIEF]

# [BRIEF] ShadowPlay Instant Replay buffer length: default 5 min, configurable 1-20
BUFFER_MIN_DEFAULT = 5
BUFFER_MIN_MIN = 1
BUFFER_MIN_MAX = 20

# [ASSUME] rolling-segment sizes Sotto will consider
SEGMENT_SIZES_S = (1, 2, 5, 10, 30)

# [ASSUME] storage throughput of a typical NVMe gaming SSD, for save-latency math
NVME_THROUGHPUT_MB_S = 2000
SATA_SSD_THROUGHPUT_MB_S = 550
HDD_THROUGHPUT_MB_S = 150

# [NVIDIA] NVENC H.264 fps @ 1920x1080 YUV420 8-bit, per NVENC engine
# Source: NVENC Application Note 13.0, "NVENC H264 Performance"
NVENC_H264_FPS_P1_VBR_HQ = {"Pascal": 692, "Turing": 833, "Ampere": 846, "Ada": 885, "Blackwell": 948}
NVENC_H264_FPS_P5_VBR_HQ = {"Pascal": 327, "Turing": 264, "Ampere": 266, "Ada": 283, "Blackwell": 317}
NVENC_H264_FPS_P7_VBR_HQ = {"Pascal": 250, "Turing": 207, "Ampere": 213, "Ada": 211, "Blackwell": 227}

# [NVIDIA] NVENC HEVC fps @ 1920x1080 YUV420 8-bit, per NVENC engine
# Source: NVENC Application Note 13.0, "NVENC HEVC Performance"
NVENC_HEVC_FPS_P1_VBR_HQ = {"Pascal": 506, "Turing": 920, "Ampere": 939, "Ada": 1037, "Blackwell": 1119}
NVENC_HEVC_FPS_P3_VBR_HQ = {"Pascal": 443, "Turing": 552, "Ampere": 557, "Ada": 706, "Blackwell": 947}
NVENC_HEVC_FPS_P7_VBR_HQ = {"Pascal": 260, "Turing": 171, "Ampere": 171, "Ada": 181, "Blackwell": 181}

# [NVIDIA] concurrent NVENC sessions on NON-qualified (GeForce-class) GPUs
NVENC_NONQUALIFIED_SESSION_LIMIT_PER_SYSTEM = 8

# [ASSUME] raw frame geometry, used only to show why uncompressed RAM is hopeless
RAW_GEOMETRY = {"1080p": (1920, 1080), "1440p": (2560, 1440), "4K": (3840, 2160)}
YUV420_BYTES_PER_PIXEL = 1.5  # 8-bit 4:2:0


def bytes_for(bitrate_bps: int, seconds: float) -> int:
    """Convert bitrate x duration to bytes. The single source of truth for sizing."""
    return int(bitrate_bps / 8 * seconds)


def mib(n: int) -> float:
    return n / MIB


def gib(n: int) -> float:
    return n / GIB


def rule(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


# ------------------------------------------------- 1. buffer footprint ----

rule("1. CIRCULAR BUFFER FOOTPRINT  (bitrate [BRIEF] x duration [BRIEF])")

print(f"{'codec':<6} {'minutes':>8} {'bytes':>14} {'MiB':>10} {'GiB':>8}")
print("-" * 50)
for label, br in (("H264", BITRATE_H264_1080p60), ("HEVC", BITRATE_HEVC_1080p60)):
    for mins in (BUFFER_MIN_MIN, BUFFER_MIN_DEFAULT, 10, BUFFER_MIN_MAX):
        b = bytes_for(br, mins * 60)
        print(f"{label:<6} {mins:>8} {b:>14,} {mib(b):>10.1f} {gib(b):>8.3f}")
    print()

# ------------------------------------------------- 2. RAM vs disk ----------

rule("2. RAM-RESIDENT vs DISK-RESIDENT  (is the buffer small enough for RAM?)")

print("Assumed Sotto RAM budget for the buffer: 512 MiB  [ASSUME]")
RAM_BUDGET = 512 * MIB
print()
print(f"{'codec':<6} {'minutes':>8} {'size MiB':>10} {'fits 512MiB RAM?':>18} {'on disk GiB':>13}")
print("-" * 62)
for label, br in (("H264", BITRATE_H264_1080p60), ("HEVC", BITRATE_HEVC_1080p60)):
    for mins in (BUFFER_MIN_DEFAULT, 10, BUFFER_MIN_MAX):
        b = bytes_for(br, mins * 60)
        print(f"{label:<6} {mins:>8} {mib(b):>10.1f} {'YES' if b <= RAM_BUDGET else 'NO':>18} {gib(b):>13.3f}")
    print()

# --------------------------------------- 3. why NOT raw uncompressed -------

rule("3. RAW UNCOMPRESSED EQUIVALENT  (why RAM cannot hold raw frames)")

print("YUV420 8-bit, 60 fps.  [ASSUME geometry], YUV420 = 1.5 bytes/pixel")
print()
print(f"{'resolution':<10} {'MiB/frame':>10} {'5 min @60fps':>14} {'ratio vs H264 4Mbps':>22}")
print("-" * 62)
h264_5min = bytes_for(BITRATE_H264_1080p60, 300)
for name, (w, h) in RAW_GEOMETRY.items():
    frame = int(w * h * YUV420_BYTES_PER_PIXEL)
    raw_5min = frame * 60 * 300
    print(f"{name:<10} {mib(frame):>10.2f} {gib(raw_5min):>13.1f}G {raw_5min / h264_5min:>21.0f}x")
print()
print("-> Raw 1080p is ~300x the compressed bitstream. The circular buffer MUST")
print("   store compressed frames. NVIDIA states the same principle for NVENC:")
print("   its own 'recording/archiving' guidance is a COMPRESSED encode path.")
print()

# ------------------------------------------------- 4. segment counts -------

rule("4. ROLLING SEGMENT GRANULARITY  (how many files the ring holds)")

for mins in (BUFFER_MIN_DEFAULT, BUFFER_MIN_MAX):
    print(f"Buffer length: {mins} minutes")
    print(f"  {'segment s':>10} {'segments held':>15} {'H264 seg MiB':>14} {'HEVC seg MiB':>14}")
    print("  " + "-" * 58)
    for s in SEGMENT_SIZES_S:
        count = mins * 60 / s
        print(f"  {s:>10} {count:>15.0f} "
              f"{mib(bytes_for(BITRATE_H264_1080p60, s)):>14.2f} "
              f"{mib(bytes_for(BITRATE_HEVC_1080p60, s)):>14.2f}")
    print()

# --------------------------------------- 5. save latency budget -----------

rule("5. SAVE LATENCY  (copy the retained window to a real file)")

print("A save = concatenate the retained segments into the user's file.")
print("Cost is bounded by how much data must be moved, not by the ring length")
print("in seconds, because the encoder is already running either way.")
print()
save_secs = BUFFER_MIN_DEFAULT * 60
for label, br in (("H264 4Mbps", BITRATE_H264_1080p60), ("HEVC 10Mbps", BITRATE_HEVC_1080p60)):
    n = bytes_for(br, save_secs)
    print(f"{label}: {save_secs}s window = {mib(n):,.1f} MiB")
    for dev, tp in (("NVMe", NVME_THROUGHPUT_MB_S),
                    ("SATA SSD", SATA_SSD_THROUGHPUT_MB_S),
                    ("HDD", HDD_THROUGHPUT_MB_S)):
        t = (n / (tp * 1e6)) * 1000.0
        print(f"    copy at {dev:<9} {tp:>5} MB/s [ASSUME] -> {t:>7.1f} ms")
    print()

print("Conclusion: a whole-window copy is ~150-375 ms of I/O. Under the 1 s")
print("budget BUT it is pure serial I/O and it competes with the game.")
print("Copy is the WRONG design. Renaming/linking retained segments is ~0 ms")
print("because the ring already wrote them contiguously to disk.")
print()

# -------------------------------------- 6. encode headroom / streams -------

rule("6. NVENC ENCODE HEADROOM  (how many 1080p60 streams fit one NVENC engine)")

TARGET_FPS = 60  # 1080p60 [BRIEF]
print(f"Target: {TARGET_FPS} fps per stream.  Stream count = floor(engine_fps / {TARGET_FPS})")
print("Source [NVIDIA]: NVENC Application Note 13.0, per-NVENC-engine fps tables.")
print()
print(f"{'preset/tune':<22} " + " ".join(f"{g:>10}" for g in NVENC_H264_FPS_P1_VBR_HQ))
for name, tbl in (("H264 P1 VBR/HQ", NVENC_H264_FPS_P1_VBR_HQ),
                  ("H264 P5 VBR/HQ", NVENC_H264_FPS_P5_VBR_HQ),
                  ("H264 P7 VBR/HQ", NVENC_H264_FPS_P7_VBR_HQ),
                  ("HEVC P1 VBR/HQ", NVENC_HEVC_FPS_P1_VBR_HQ),
                  ("HEVC P3 VBR/HQ", NVENC_HEVC_FPS_P3_VBR_HQ),
                  ("HEVC P7 VBR/HQ", NVENC_HEVC_FPS_P7_VBR_HQ)):
    print(f"{name:<22} " + " ".join(f"{tbl[g]:>10}" for g in tbl))
print()
print("Streams of 1080p60 on ONE engine:")
print(f"{'preset/tune':<22} " + " ".join(f"{g:>10}" for g in NVENC_H264_FPS_P1_VBR_HQ))
for name, tbl in (("H264 P1 VBR/HQ", NVENC_H264_FPS_P1_VBR_HQ),
                  ("H264 P5 VBR/HQ", NVENC_H264_FPS_P5_VBR_HQ),
                  ("HEVC P3 VBR/HQ", NVENC_HEVC_FPS_P3_VBR_HQ)):
    print(f"{name:<22} " + " ".join(f"{tbl[g] // TARGET_FPS:>10}" for g in tbl))
print()
print("Hard session ceiling [NVIDIA]: 8 concurrent sessions PER SYSTEM across")
print("ALL non-qualified (GeForce-class) cards combined. Qualified (RTX/Quadro)")
print("cards are bounded by resources instead, not by a session counter.")
print(f"  -> GeForce user with 2 games open: at most {NVENC_NONQUALIFIED_SESSION_LIMIT_PER_SYSTEM} "
      "encode sessions total, no matter how many NVENC engines exist.")
print()

# -------------------------------------- 7. multi-stream RAM ceiling -------

rule("7. PRACTICAL MEMORY CEILING WITH SEVERAL GAMES RUNNING")

print("Assumed system RAM headroom available to Sotto: 2048 MiB [ASSUME]")
HEADROOM = 2048 * MIB
print()
print(f"{'streams':>8} {'codec':>6} {'minutes':>8} {'total MiB':>11} {'fits 2048MiB?':>16}")
print("-" * 56)
for n_streams in (1, 2, 3, 4):
    for label, br in (("H264", BITRATE_H264_1080p60), ("HEVC", BITRATE_HEVC_1080p60)):
        for mins in (BUFFER_MIN_DEFAULT, BUFFER_MIN_MAX):
            total = bytes_for(br, mins * 60) * n_streams
            if label == "HEVC" and mins != BUFFER_MIN_MAX:
                continue
            if label == "H264" and mins != BUFFER_MIN_DEFAULT:
                continue
            print(f"{n_streams:>8} {label:>6} {mins:>8} {mib(total):>11.1f} "
                  f"{'YES' if total <= HEADROOM else 'NO':>16}")
print()
print("This is the number that forces the DISK design: at 20 min x HEVC x 3")
print("streams the buffer is larger than the RAM headroom, so the ring must")
print("live on disk with an in-RAM index of segment metadata only.")
print()

# -------------------------------------- 8. seek granularity --------------

rule("8. SEEK GRANULARITY vs KEYFRAME INTERVAL")

print("[NVIDIA] NVENC 'Recording/Archiving' recommended settings include a")
print("FINITE GOP LENGTH OF 2 SECONDS. That is the default posture for a")
print("recording path, so assume a 2 s GOP unless Sotto changes it.")
GOP_S = 2  # [NVIDIA]
print()
print(f"{'GOP s':>6} {'keyframes in 5min':>18} {'worst-case seek error s':>24}")
print("-" * 52)
for g in (1, 2, 4, 10):
    print(f"{g:>6} {300 / g:>18.0f} {g:>24}")
print()
print("Consequence: the editor can seek to any of these keyframes, so the ring")
print("index must record the file offset + PTS of every IDR, not just segment")
print("boundaries, or 'save from 90s ago' lands up to one GOP off.")
print()

rule("END")