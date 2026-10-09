"""pipeline -- THE CHAIN, and the interfaces it needs from the lanes that own them.

    contracts.py  the interfaces required of src/asr, src/index and src/capture,
                  declared exactly as those producers expose them and CHECKED at run
                  time (a renamed keyword is a chain that looks green)
    chain.py      the runner: clip -> audio -> transcript -> index row -> search,
                  with a `provenance` on every stage and a loud refusal at every step

There is no `src/pipeline/` code in the product path yet: capture is C++ and the
python side is three independent subsystems. This package is the piece that proves
they compose, and it is honest about which of its stages touched the real thing.

Import nothing heavy at module level. The ASR pins its thread pools before numpy
loads (`src/asr/__init__.py`), and `contracts` deliberately imports neither numpy nor
onnxruntime -- the index's own rule, kept.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]