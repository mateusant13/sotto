# 03 — NVENC sessions on THIS box: engines, formats, and the concurrent limit

**Question:** the capture lane got status 5 from *every* `NvEncOpenEncodeSessionEx`, so the engine count and
the driver's refusal point were UNKNOWN. Settled with a C++ probe on real headers. `MEASURED` = a command on
this box produced it · `READ` = vendor doc, URL given · `UNKNOWN` = nobody has shown it.
Host: Win11 26200 · RTX 5080 (`0x2C02`) · driver **617.14** / `nvEncodeAPI64.dll` `32.0.16.1714`.

## Headers — what and from where

**MEASURED** — **`nv-codec-headers` 13.1** from FFmpeg's mirror, **no account needed**
(`raw.githubusercontent.com/FFmpeg/nv-codec-headers/master/include/ffnvcodec/nvEncodeAPI.h`): **313554 B,
sha256 `8776FDDCB8FEBC6AEC4D73989B1F21831EB30306BC583DA55B4BF0C14A1DC228`**, master commit
`eddcea9e27f6b772057c9b3f87de2cc1737faffc` (2026-07-14), newest tag `n13.1.15.0`. The copy already in
`_main/sdkref/nvEncodeAPI.h` is **byte-identical**. **NVIDIA's Video Codec SDK was NOT used** — its zip URL
returns **404** anonymously (landing page 200), i.e. it wants a login; the FFmpeg header is the same file.
**MEASURED — the compiler is its own finding:** no MSVC and no CUDA toolkit on this box (`cl.exe` absent, no
`nvcc`). It builds with **MSYS2 mingw-w64 g++ 15.2.0**; the CUDA *driver* API is resolved from `nvcuda.dll`
at run time, so no `cuda.h` is needed.

## The status 5 is GONE — it was the probe's parameter block, not the machine

| arm | device | result |
|---|---|---|
| `DEVICE_TYPE_CUDA` (real `cuCtxCreate_v2`) | RTX 5080 | **status 0** `NV_ENC_SUCCESS` |
| `DEVICE_TYPE_DIRECTX` (`ID3D11Device` on vendor `0x10DE`) | RTX 5080 | **status 0** `NV_ENC_SUCCESS` |

**MEASURED** — both then **initialise** (`NvEncInitializeEncoder`, H.264 P3, 1920×1080, NV12, 60 fps) and
release cleanly. The capture lane's identical `status 5` on two *valid* devices was its own hand-built ctypes
block: **this box never refused NVENC.** The status-5 hypothesis, one variable at a time:
`version=0` → **15** `NV_ENC_ERR_INVALID_VERSION`, and a bogus struct version → **15** (a wrong *struct*
version is a different code than ctypes saw). `apiVersion=0` → **0**; `12.0` → **0**; `14.0` → **0** — the
driver **ignores `apiVersion`** on open and validates only `version`, so `apiVersion` is *not* the cause.
**READ** — NVIDIA documents `NV_ENC_ERR_OUT_OF_MEMORY` for exceeding the limit (ProgGuide, link in `01-`).
**MEASURED — wrong on this driver:** the refusal is **21**, this header's `NV_ENC_ERR_INCOMPATIBLE_CLIENT_KEY`,
and `nvEncGetLastErrorString` says `"EncodeAPI Internal Error."`, naming nothing. **Never dispatch on the
documented code.**

## Capabilities — MEASURED, all three codecs

| cap | H.264 | HEVC | AV1 |
|---|---|---|---|
| **`NUM_ENCODER_ENGINES`** | **2** | **2** | **2** |
| `WIDTH_MAX` / `HEIGHT_MAX` | 4096 / 4096 | 8192 / 8192 | 8192 / 8192 |
| `WIDTH_MIN` / `HEIGHT_MIN` | 145 / 49 | 129 / 33 | 192 / 128 |
| `RATECONTROL_MODES` / `SUPPORT_10BIT` | 3 / 1 | 3 / 1 | 3 / 1 |

**MEASURED** — 3 codec GUIDs (H.264 `6BC82762…`, HEVC `790CDC88…`, AV1 `0A352289…`) and **13 input buffer
formats** for H.264, **NV12 `0x1`** among them. A 1920×1080 NV12 D3D11 texture **registers and maps**
(`NvEncRegisterResource`→0, `NvEncMapInputResource`→0): the zero-copy path works. **UNKNOWN:** sustained
fps/quality, and the per-frame BGRA→NV12 cost (`01-` §1).

## The concurrent-session limit — MEASURED, and it is not 8

**MEASURED** — **10** sessions opened **and held**; the **11th** refused with **status 21**. Releasing all 10
frees the budget immediately. **10 initialised** sessions (a live encoder each, not just an open handle) gave
the same refusal at #11, and it arrives at **OPEN**, not at init: not initialising buys nothing. Measured
twice, identically. `nvidia-smi` `encoder.stats.sessionCount` was **1 before and after every run**
(Broadcast/`nvcontainer`/Overlay/ShareX are up, ~7 GB VRAM in use), so **11 sessions total** were live at the
cap. **READ** — NVIDIA Application Note §3 says **8 concurrent sessions on non-qualified (GeForce) GPUs**;
**MEASURED 11 > 8**, so that "8" does **not** describe this driver/GPU. **Design consequence:** one session
per recording is far from the wall, but this box shares its GPU — refuse loudly at start-up and classify the
failure by **status 21**, not by the documented code.

## Configuration traps (each cost a probe run)

1. **`tuningInfo = 0` is invalid** — 0 is `NV_ENC_TUNING_INFO_UNDEFINED`, called *"Invalid value for
   encoding"* in the header; `memset(0)` walks into it → **status 12**. **MEASURED:** `LOW_LATENCY` and
   `HIGH_QUALITY` initialise, `UNDEFINED` does not.
2. **Do not hand-build `NV_ENC_CONFIG`.** A config with **only `version`** set is still refused with **status
   8** and the misleading text `"Unsupported color format."` — and `NV_ENC_CONFIG` has **no `bufferFormat`
   field** here, so that message is not about the format. Working pattern (**MEASURED** status 0): take the
   driver's own `nvEncGetEncodePresetConfigEx(P3, LOW_LATENCY)`, then override
   `gopLength`/`frameIntervalP`/`rcParams`. The driver's config is the contract.
3. **`NvEncGetEncodeCaps` on an opened-but-unINITIALISED session SEGFAULTS** (`0xC0000005`, first build of
   this probe): it needs an initialised session and returns no error status. Related —
   `NvEncRegisterResource` on an uninitialised session returns **5 `NV_ENC_ERR_DEVICE_NOT_EXIST`, the same
   status 5 the capture lane chased on OPEN.** A bare status 5 is ambiguous unless session state is printed.
4. `NvEncodeAPIGetMaxSupportedVersion` really returns **`0xD1`** (MEASURED); the driver packs it as
   `major<<24`, so the probe's printed `major=0 minor=209` is that artefact, not a 209.x API.

## MEASURED on this run — CONTRADICTS `01-capture-encode.md`

`D3D11CreateDevice(NULL, D3D_DRIVER_TYPE_HARDWARE, …)` returns feature level `0xB000` and its
`IDXGIDevice::GetAdapter` is the **NVIDIA RTX 5080, vendor `0x10DE`** — the default adapter **is** NVIDIA here.
`0xB000` on both adapters is about the feature level, not the vendor; matching the vendor stays correct
practice but is not a trap on this run. Inventory: idx 0 `0x10DE` (15979 MB) · idx 1 `0x8086` UHD 770
(128 MB) · idx 2 `0x1414` Basic Render Driver, `D3D11CreateDevice` fails `0x887A0004`.

## Housekeeping, and what stays UNKNOWN

**MEASURED** — every session destroyed, `cuCtxDestroy_v2`→0, `nvidia-smi` `sessionCount` **1 before and 1
after** each run: the box was left as found. ~**8 MiB** peak working set, ~**0.5 s** runtime, run under the
owner's other GPU load (~7 GB VRAM, 3–17 % utilisation) rather than on a quiet box.
**UNKNOWN:** whether any frame actually encodes and at what rate (no bitstream/throughput test); which process
holds the pre-existing session (`nvidia-smi` exposes only the count); and whether **older drivers** behave
the same — 11 is a measurement on **617.14**, not a general law.
