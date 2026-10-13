# ALL FIVE ZIPS VIEWED — and they are FIVE DIFFERENT CAPTION MODELS

2026-10-13. Closes the gap left by every earlier receipt: A, B, C, D and E have now been
built, rendered AND looked at. This is the synthesis.

## The five, side by side

| zip | where the LIVE caption lives | the history | notes |
|---|---|---|---|
| **A** `directions` | a right-hand panel listing ~10 lines, each dimmer than the one below | the same panel | a directions EXPLORER: 5 tabs, a hero headline |
| **B** `themes` | **ONE BIG LINE at the bottom**, full width, **speaker name above it** | a SEPARATE right panel, `time + SPEAKER + text` per row, plus search and a library | a whole media-player app |
| **C** `panels` | bottom: the previous line faded, the current bright, **`-- MARA` under it** | a right panel `LIVE TRANSCRIPT` with speaker BADGES (`M`, `T`) and times | has a DESIGNS list with 10 entries |
| **D** `themes` | **a FLOATING ROUNDED CARD**: speaker name, a serif line, a caret, and metadata (`TRANSCRIBING MARLOW . ON-DEVICE . 240 MS`) | the RICHEST: search, SPEAKER FILTER CHIPS, badges, timestamps, an `IN PROGRESS` row, export | this is the closest to OUR overlay |
| **E** `panels` | a right-hand COLUMN, older lines faded, no speaker | the same column | bare panel; the one whose chrome steps 1-2 already applied |

## THE ANSWER THIS PRODUCES, and it was not derivable before

**Zip D floating card IS our `#caption-float`.** A rounded card holding a speaker name, one
serif line, a caret, and a metadata strip is exactly the element our overlay already is --
dot, previous line, current line, meter. **So D is the model to follow for the overlay, not E.**

And the history panel is a SEPARATE thing: B, C and D all put the transcript in a right-hand
panel with **speaker attribution per row**, which our `.captions` box does NOT have.

## So "make it look like the zip" resolves into TWO decisions, not one

1. **The live caption** (our `#caption-float`): zip D card, or zip E column, or zip B big line.
   **D is the closest to what we already have** and the least structural change.
2. **The history** (our `.captions` on the panel surface): all three of B, C, D agree on
   `time + SPEAKER + text`, which we do not have today.

**These are still decisions for the owner.** What has changed is that they are now decidable
from five images instead of guessed at from one description.

## What this does NOT establish

* Colours are described from renders; NO eyedropper was run, so no hex is quoted anywhere.
* Only the DEFAULT state of each zip was captured. C has a 10-entry DESIGNS list, D has a
  20-theme list, A has 5 tabs -- **none of those alternates was driven**, so the five models
  above are the five DEFAULT states.
* Nothing in the product was changed by this file.
