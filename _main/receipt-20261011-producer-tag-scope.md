# The T3 second-order finding (b): the producer tag cannot leak between the two arms (2026-10-11)

The T3 lane reported, unfixed: *"the tag is per BUFFER, not per line: a fragment declaring nothing
inherits it (sticky `bufferSawProducer`, no conflict). Measured: live fragment then redux fragment of the
same line -> `producer:"redux"` and the gate ACCEPTS it."* Measured against the shipped composition,
**that is not reachable by the shipped wiring** — the tag is per-buffer BY DESIGN, with an explicit reset,
and the two arms never share a buffer. Three anchors, all read off the live bytes (nothing launched):

1. **The reset exists and says why.** `app/panel/caption-formulation.js:542-546` — *"Same law for the
   producer tag: a `redux` batch line must not lend its tag to the live line that follows it in the same
   buffer slot."* — `bufferProducer = null; bufferSawProducer = false; bufferProducerConflict = false;`
   on every drain, and again at `:788-790` on reset. So the tag dies with its buffer.
2. **The tag lives in the ENGINE, never in the module.** `bufferProducer` (`:381`), `bufferSawProducer`
   (`:383`) and `bufferProducerConflict` (`:385`) are `let`s inside `createEngine`, read back only through
   `committedProducer()` (`:412-415`, which returns `null` on any conflict). One engine per source is
   `engines.set(key, engine)` (`panel.js:678`).
3. **The two arms are separated by SOURCE, so they never share a buffer.** A live caption carries
   `source` — `worker/sotto_worker.py:2893` adds the key *"ONLY when the former was given a source
   (every live tap has one; `--selftest` and the file arm have none)"* — while the Redux batch event
   carries `producer:"redux"` and **no `source` key at all** (measured by the T3 oracle against the real
   `_run_runner`). `engineFor(source)` therefore puts them in DIFFERENT engines with separate buffers, so
   the "live fragment then redux fragment of the same line" sequence the lane measured is a property of
   calling ONE engine with both kinds of fragment, which the shipped wiring does not do.

**The residual, stated honestly.** The only configuration where both kinds of fragment could reach one
buffer is a SOURCE-LESS live arm (the file arm or `--selftest`) running together with the batch arm — and
the batch arm is OFF by default, its checkpoint is absent, and `--selftest` does not run it. Even then the
reset at `:542-546` clears the tag at every buffer boundary; what survives is only an interleaving INSIDE
one open line. No shipped configuration produces it, and the per-source engines (STEP 4) make it
unreachable on the live path entirely.

## NOT MEASURED

- No live run: this is a code-path argument plus the T3 oracle's in-process measurement of the two event
  shapes, not an observation of a real interleaving.
- The gate's ACCEPT of a mixed-tag line is real at the unit level (T3 measured it); what is refuted here is
  that the shipped app can produce such a line.
