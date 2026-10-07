"""READ-ONLY parity check: onnx-asr's text vs the Sotto reference transcripts.

The references are the ONNX-int4 oracle's own output, which the ternary runner
(`H:\\sotto\\worker\\redux_batch.py`) reproduced BYTE-FOR-BYTE. So a diff here is a diff
against both, and the interesting part is not "equal/not" but WHERE they differ.

`redux-ptbr.txt` is cp1252 on disk (a redirected stdout on a pt-BR box), so it is decoded
as cp1252 first and both sides are finally encoded to UTF-8 bytes for the comparison.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

CLIPS = {
    "pt-br-sample.wav": Path(r"H:\sotto\_main\redux-ptbr.txt"),
    "en-us-sample.wav": Path(r"H:\sotto\_main\redux-en.txt"),
}
SKIP_PREFIXES = ("model loaded",)


def reference(path: Path) -> str:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith(SKIP_PREFIXES)]
    return lines[-1]


def main() -> int:
    result = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    for row in result["parity"]:
        name = Path(row["wav"]).name
        mine = row["text"].strip()
        ref = reference(CLIPS[name])
        same = mine == ref
        print(f"=== {name} ===")
        print(f"  oracle/redux : {ref}")
        print(f"  onnx-asr     : {mine}")
        print(f"  IDENTICAL    : {same}")
        if not same:
            import difflib

            a, b = ref.split(), mine.split()
            sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == "equal":
                    continue
                print(f"  {tag:8s} oracle[{' '.join(a[i1:i2])!r}] -> onnx[{' '.join(b[j1:j2])!r}]")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
