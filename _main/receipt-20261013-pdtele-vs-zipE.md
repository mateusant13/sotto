# pd-tele against the zip E Teleprompter — the mapping, started

2026-10-13. First pair of the mapping the five-zip synthesis left open.

## The two, side by side

| | our `pd-tele` (rendered `--theme pd-tele`, 380x900) | zip E Teleprompter (380x900 crop) |
|---|---|---|
| top-LEFT | `EM ESPERA` with a dot -- **AND IT IS OVERLAPPED BY A SECOND COPY OF THE SAME TEXT** | a BORDERED monospace pill: `FUNDO: FILME . REPRODUZINDO . AUDIO ORIGINAL` |
| top-RIGHT | `Teleprompter . painel`, then theme/`A A`/pause/close icons | faint `SOTTO .` |
| body | a BORDERED transcript box with a centred error | the caption column, unframed, on the video |
| bottom | `HISTORICO` + `EM CURSO` | the LIGHT control bar: tabs, scrubber, boxed buttons, hint |

## THE DEFECT THIS RENDER SHOWS

**The top-left status text is painted TWICE, overlapping.** The render reads `EM ESPER` and then
a second `ESP` sitting on top of it. Two elements are drawing the same readout in the same
place.

**This is NOT a zip-fidelity issue** -- it is our own header, and it would be wrong under any
design. It was found by rendering `pd-tele` for the mapping, not by looking for it.

**NOT YET CAUSED OR FIXED.** The candidates -- a theme rule that positions `#strip-state` on
the panel surface where a second node also paints, or the `body[data-surface]` scoping -- have
not been read. Recorded so the next attempt starts from the picture instead of from a guess.

## What this says about the mapping

**The names pair up but the structures do not.** `pd-tele` is a 380x900 PANEL with a header, a
transcript box and a footer; the zip E Teleprompter is a caption surface over a video with a
light control bar. They share a name and a size and almost nothing else.

**So mapping by name is exactly the trap the synthesis warned about**, and the correct mapping
may well be that our `pd-*` correspond to the zip E FIVE caption columns, not to the five zip
names. That question is not settled here.

## Not established

* Only ONE pair was rendered. `pd-bcast`, `pd-mano`, `pd-cine`, `pd-instr` have NOT been
  rendered against their zip namesakes.
* Colours described from the render only; no eyedropper.
* The overlap was seen, not attributed. No rule was read.
