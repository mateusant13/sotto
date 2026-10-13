# The zip history shows a SPEAKER per line. WE PRODUCE NO SPEAKER AT ALL.

2026-10-13. This stops a design change before it is attempted, which is the point of writing it.

## What the zips do

Zips **B, C and D all attribute every history row to a speaker**, and they agree on the shape:

* **B** -- `02:41 AM MARA Tonight we are talking about the quiet hours...`
* **C** -- a speaker BADGE (`M`, `T`) then the time and the line
* **D** -- a badge, the name, a TIMESTAMP, and a speaker FILTER ROW
  (`EVERYONE / JUNE / MARLOW / SOPHIA / TOMA / READER / HOST`)

D also counts them: `6 SPEAKERS . 17 LINES . 98% CONF.`, and its live card says
`TRANSCRIBING MARLOW`.

## What we have

**NOTHING.** Measured with `grep` over the two files that would carry it:

| file | `speaker` matches | what they are |
|---|---|---|
| `worker/sotto_worker.py` | **3** | all three are PROSE in comments -- "a real speaker endpoint lit up", "a speaker who never pauses", "with room for a slower speaker". **No field, no code.** |
| `app/panel/panel.js` | **1** | also prose -- "Captions may lag the speaker." |

There is no diarisation, no speaker field in the caption event, no speaker id anywhere on the
path from the worker to the panel.

## So the conclusion is not what I first wrote

In the five-zip synthesis I wrote that "the history with speaker per line is what we are
missing". **That was right about the zips and WRONG about the kind of gap.** This is not a
DESIGN gap that CSS can close -- it is an ENGINE gap. No amount of styling puts a name on a
line that does not carry one, and a speaker FILTER (zip D) cannot exist without stable speaker
ids to filter by.

**What that means concretely:**

* The **visual** part -- time, badge, layout -- is ours to do whenever it is wanted, and it
  would show a placeholder where the name goes.
* The **name** part needs diarisation added to the worker: a new model or a clustering pass, a
  speaker id in the caption event, and stability across a session. That is a real feature, not
  a restyle, and it is nowhere in the current engine.

## The rule this leaves

A design taken from a mockup can describe a capability the engine does not have. **Check the
data before building the view** -- otherwise the result is a beautifully styled column of
blanks, and the gap gets discovered after the work instead of before it.
