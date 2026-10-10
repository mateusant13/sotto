"""mp4fix.py -- a FIXTURE-side minimal mp4 builder.

Arm A of the ODS instrument needs containers whose box bytes are REAL: the same box names, the
same version-0 full boxes and the same field order as the product writer
src/capture/mp4_writer.cpp, including the three facts the design preserved:

  * mvhd / tkhd / mdhd creation_time and modification_time are written as LITERAL 0
    (mp4_writer.cpp:293, :272, :257).  A reader that converts those zeroes into a timestamp
    prints 1904-01-01 (the mp4 epoch) and calls that a start time.
  * stts is run-length (count, delta) (mp4_writer.cpp:86-87, :169-173) and the movie timescale
    is 1000 (:115), so mdhd.duration and mvhd.duration are DIFFERENT units, each divided by
    its OWN timescale.
  * stss is OMITTED when every sample is sync (mp4_writer.cpp:175-184), so its absence means
    "all sync", never "no duration".

NOT a product writer: every byte it produces belongs to a fixture.  The SPS/PPS bytes are
fake on purpose, because the instrument REFUSES to read them (lane 17's receipt: a clip that
declared 1920x1080 in tkhd carried a 3840x2160 SPS).
Pure stdlib, ASCII only.
"""

import struct


def _u32(v):
    return struct.pack(">I", v & 0xFFFFFFFF)


def _u16(v):
    return struct.pack(">H", v & 0xFFFF)


def _full(version, flags):
    return bytes([version & 0xFF, (flags >> 16) & 0xFF, (flags >> 8) & 0xFF, flags & 0xFF])


def _box(t, body):
    return _u32(len(body) + 8) + t + body


_MATRIX = [0x00010000, 0, 0, 0, 0x00010000, 0, 0, 0, 0x40000000]


def _matrix():
    return b"".join(_u32(m) for m in _MATRIX)


def ftyp():
    return _box(b"ftyp", b"isom" + _u32(512) + b"isom" + b"iso2" + b"avc1" + b"mp41")


def _hdlr(handler_type, name):
    return _box(b"hdlr", _full(0, 0) + _u32(0) + handler_type + _u32(0) * 3
                + name + b"\x00")


def _avc1(width, height, sps, pps):
    body = (
        b"\x00" * 6 + _u16(1) + _u16(0) + _u16(0) + _u32(0) * 3
        + _u16(width) + _u16(height) + _u32(0x00480000) + _u32(0x00480000)
        + _u32(0) + _u16(1) + b"\x00" * 32 + _u16(0x0018) + _u16(0xFFFF)
    )
    avcC = (b"\x01" + bytes([sps[1] if len(sps) > 1 else 0])
            + bytes([sps[2] if len(sps) > 2 else 0])
            + bytes([sps[3] if len(sps) > 3 else 0])
            + b"\xFF" + b"\xE1" + _u16(len(sps)) + sps
            + b"\x01" + _u16(len(pps)) + pps)
    return _box(b"avc1", body + _box(b"avcC", avcC))


def _mp4a():
    # a STRUCTURAL audio entry.  esds is specified-not-written in this tree, so there is none.
    body = (b"\x00" * 6 + _u16(1) + _u32(0) + _u16(2) + _u16(16) + _u16(0)
            + _u32(0) + _u32(48000))
    return _box(b"mp4a", body)


def _tkhd(track_id, duration, width, height, is_audio=False):
    vol = (_u16(0x0100) + _u16(0)) if is_audio else (_u16(0) + _u16(0))
    body = (_full(0, 0x000007) + _u32(0) + _u32(0) + _u32(track_id) + _u32(0)
            + _u32(duration) + _u32(0) * 2 + _u16(0) + _u16(0) + vol
            + _matrix() + _u32(width << 16) + _u32(height << 16))
    return _box(b"tkhd", body)


def _mdhd(timescale, duration):
    return _box(b"mdhd", _full(0, 0) + _u32(0) + _u32(0) + _u32(timescale)
                + _u32(duration) + _u16(0x55C4) + _u16(0))


def _mvhd(timescale, duration):
    return _box(b"mvhd", _full(0, 0) + _u32(0) + _u32(0) + _u32(timescale)
                + _u32(duration) + _u32(0x00010000) + _u16(0x0100) + _u16(0)
                + _u32(0) * 2 + _matrix() + _u32(0) * 6 + _u32(2))


def _stsd(*entries):
    return _box(b"stsd", _full(0, 0) + _u32(len(entries)) + b"".join(entries))


def _stbl_video(sample_ticks, sizes, offsets, width, height, sps, pps, with_stts,
                all_sync):
    runs = []
    for t in sample_ticks:
        if runs and runs[-1][1] == t:
            runs[-1][0] += 1
        else:
            runs.append([1, t])
    parts = [_stsd(_avc1(width, height, sps, pps))]
    if with_stts:
        b = _full(0, 0) + _u32(len(runs))
        for c, d in runs:
            b += _u32(c) + _u32(d)
        parts.append(_box(b"stts", b))
        if not all_sync:
            nums = [i + 1 for i in range(0, len(sizes), 2)]
            b = _full(0, 0) + _u32(len(nums)) + b"".join(_u32(n) for n in nums)
            parts.append(_box(b"stss", b))
    parts.append(_box(b"stsc", _full(0, 0) + _u32(1) + _u32(1) + _u32(1) + _u32(1)))
    b = _full(0, 0) + _u32(0) + _u32(len(sizes)) + b"".join(_u32(s) for s in sizes)
    parts.append(_box(b"stsz", b))
    b = _full(0, 0) + _u32(len(offsets)) + b"".join(_u32(o) for o in offsets)
    parts.append(_box(b"stco", b))
    return _box(b"stbl", b"".join(parts))


def _stbl_audio(sample_ticks, sizes, offsets, with_stts):
    parts = [_stsd(_mp4a())]
    if with_stts:
        runs = []
        for t in sample_ticks:
            if runs and runs[-1][1] == t:
                runs[-1][0] += 1
            else:
                runs.append([1, t])
        b = _full(0, 0) + _u32(len(runs))
        for c, d in runs:
            b += _u32(c) + _u32(d)
        parts.append(_box(b"stts", b))
    parts.append(_box(b"stsc", _full(0, 0) + _u32(1) + _u32(1) + _u32(1) + _u32(1)))
    b = _full(0, 0) + _u32(0) + _u32(len(sizes)) + b"".join(_u32(s) for s in sizes)
    parts.append(_box(b"stsz", b))
    b = _full(0, 0) + _u32(len(offsets)) + b"".join(_u32(o) for o in offsets)
    parts.append(_box(b"stco", b))
    return _box(b"stbl", b"".join(parts))


def _trak_video(track_id, timescale, duration, sample_ticks, sizes, offsets,
                width, height, sps, pps, with_stts=True, all_sync=True):
    stbl = _stbl_video(sample_ticks, sizes, offsets, width, height, sps, pps,
                       with_stts, all_sync)
    minf = _box(b"minf", _box(b"vmhd", _full(0, 1) + _u16(0) * 4)
                + _box(b"dinf", _box(b"dref", _full(0, 0) + _u32(1)
                                     + _box(b"url ", _full(0, 1))))
                + stbl)
    mdia = _box(b"mdia", _mdhd(timescale, duration)
                + _hdlr(b"vide", b"VideoHandler") + minf)
    return _box(b"trak", _tkhd(track_id, duration, width, height) + mdia)


def _trak_audio(track_id, timescale, duration, sample_ticks, sizes, offsets,
                with_stts=True):
    stbl = _stbl_audio(sample_ticks, sizes, offsets, with_stts)
    minf = _box(b"minf", _box(b"smhd", _full(0, 0) + _u16(0) + _u16(0))
                + _box(b"dinf", _box(b"dref", _full(0, 0) + _u32(1)
                                     + _box(b"url ", _full(0, 1))))
                + stbl)
    mdia = _box(b"mdia", _mdhd(timescale, duration)
                + _hdlr(b"soun", b"SoundHandler") + minf)
    return _box(b"trak", _tkhd(track_id, duration, 0, 0, is_audio=True) + mdia)


def build_mp4(sample_ticks, *, timescale=1000, width=1920, height=1080,
              chunk=b"\x00" * 16, audio_ticks=None, audio_timescale=1000,
              audio_chunk=b"\x00" * 8, sps=bytes([0x67, 0x42, 0x00, 0x1E]),
              pps=bytes([0x68, 0xCE, 0x3C, 0x80]), mode="full",
              with_stts=True, mdhd_duration_override=None,
              truncate_moov_at=None):
    """Build a real mp4.

    sample_ticks        one duration per video sample, in MEDIA timescale units.
    timescale           the media timescale (the writer's cfg_.timescale).
    mode                "full" | "crash" (ftyp+mdat only, no moov: a commit that never
                        landed) | "truncated" (moov cut at truncate_moov_at bytes).
    mdhd_duration_override  force the mdhd duration to another value (the no-duration trap is
                        expressed by mode="nodur" below instead).
    """
    n = len(sample_ticks)
    sizes = [len(chunk)] * n
    mdat_start = len(ftyp()) + 8
    offsets, pos = [], mdat_start
    for s in sizes:
        offsets.append(pos)
        pos += s
    media_duration = sum(sample_ticks)
    mdhd_duration = media_duration if mdhd_duration_override is None else mdhd_duration_override

    if mode == "crash":
        # open() writes ftyp then the mdat header (mp4_writer.cpp:65-69), and close() is what
        # writes moov.  A crash therefore leaves ftyp + an mdat header + some payload and NO
        # moov at all: exactly the shape layout.py:27-29 describes.
        return ftyp() + _u32(8) + b"mdat" + b"".join([chunk] * max(1, n // 2))

    trak = _trak_video(1, timescale, mdhd_duration, sample_ticks, sizes, offsets,
                       width, height, sps, pps, with_stts, True)
    traks = [trak]
    if audio_ticks is not None:
        a_sizes = [len(audio_chunk)] * len(audio_ticks)
        a_offsets, pos2 = [], mdat_start
        for s in a_sizes:
            a_offsets.append(pos2)
            pos2 += s
        a_dur = sum(audio_ticks)
        traks.append(_trak_audio(2, audio_timescale, a_dur, audio_ticks, a_sizes,
                                 a_offsets, with_stts))

    movie_duration = int(media_duration * 1000 // timescale) if timescale else 0
    moov = _box(b"moov", _mvhd(1000, movie_duration) + b"".join(traks))
    if mode == "truncated":
        whole = ftyp() + _box(b"mdat", b"".join([chunk] * n)) + moov
        return whole[:len(ftyp()) + 8 + len(chunk) * n + truncate_moov_at]
    return ftyp() + _box(b"mdat", b"".join([chunk] * n)) + moov


def build_nodur_mp4(*, width=1920, height=1080, chunk=b"\x00" * 16):
    """A moov whose mdhd duration is 0 AND whose stts is absent: no duration anywhere."""
    n = 1
    sizes = [len(chunk)] * n
    mdat_start = len(ftyp()) + 8
    offsets, pos = [], mdat_start
    for s in sizes:
        offsets.append(pos)
        pos += s
    trak = _trak_video(1, 1000, 0, [0], sizes, offsets, width, height,
                       bytes([0x67, 0x42, 0x00, 0x1E]),
                       bytes([0x68, 0xCE, 0x3C, 0x80]), with_stts=False, all_sync=True)
    moov = _box(b"moov", _mvhd(1000, 0) + trak)
    return ftyp() + _box(b"mdat", b"".join([chunk] * n)) + moov
