"""storage -- the rolling clip store: WHERE a clip lives, HOW LONG it stays, and what
happens when the disk fills.

  layout.py     the deterministic on-disk layout.  Paths derive from a `clip_id` by PARSING
                it; the index key (`key.json`) is written last and atomically, so a
                half-written clip is identifiable by its `.partial` marker and nothing in
                the store claims it exists.
  retention.py  age- and count-based eviction under an explicit byte budget, plus
                reconciliation and the disk-full decision.

The three questions this package answers, in the order they bite:

  1. where does a clip live            -> `layout.clip_dir()`
  2. how much disk does the store take -> `retention.RetentionPolicy.max_bytes`
  3. the disk is full, what now         -> `retention.admit_write()` REFUSES and ALARMS

(3) is the interesting one and it is a PRODUCT DECISION, not an implementation detail: this
store keeps its library and loses the NEXT clip, loudly, rather than evicting everything to
stay alive or filling the volume.  The trade-off is written out in `retention.py`'s module
docstring and in `receipts/receipt-30-clip-storage-retention.md`; a caller that wants the
other behaviour must change `DEFAULT_ON_DISK_FULL` in one named place.

MEASURED, and the reason the byte budget is a backstop rather than the primary rule: this
box's 1080p60 clip is 98 099 914 B / 16.733333 s = 5.86 MB/s (`_main/_lane17-run/
clip-speech.mp4`, ffprobe, rc=0), so **19.65 GiB per hour**.  A 4 GiB budget is 12 minutes of
capture, not four hours.  Age is the primary retention key; bytes is the floor that stops the
failure from being a slow one.

Imports only the stdlib.
"""

__version__ = "0.1.0"

__all__ = ["__version__", "layout", "retention"]