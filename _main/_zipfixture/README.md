# A strip/caption FIXTURE, and what it proved and did not

2026-10-13. `_main/_zipfixture/fixture.html` links the REAL `panel.css` and the REAL
`zip-overlay.css` and carries a hand-written minimum of the markup: the caption bar, an
`<ol class="captions__list">` with five `li.caption`, and a `section.stripbar` with the brand,
the grip, a toggle button and the state pill. Rendered with headless Edge.

## Why it exists

Step 3 (the caption column: right-aligned, unframed, older lines faded) was applied but its
render was **byte-identical** to the previous one, because the strip probe has no audio, so the
caption list is empty and there is nothing to align or fade. The `--caption TEXT` probe flag is
documented in its own source as broken. The fixture is the way to put text in front of the
rules without launching the owner app.

## What it PROVED

The shared chrome of the two earlier steps renders correctly against the real stylesheets in a
plain document: the **light slab**, **`SOTTO` dark**, the grip, the **boxed dark controls** and
the dark state pill with its dot. So steps 1 and 2 are not artefacts of the shell or of a
particular surface attribute.

## What it did NOT prove, and this is the honest part

**The captions did not render.** The five `li.caption` rows are absent from the image, so the
fade and the right-alignment are STILL UNVERIFIED. The likely reason is that the real product
builds its caption rows through `panel.js`, which sets state and classes this fixture does not
reproduce -- and some rule in `panel.css` hides the list in the state the fixture leaves it in.
Chasing that means reading the caption rules, and it was not done here.

**So the fixture proved the CHROME and failed at the CAPTION.** That is a useful split: the two
steps that were already verified by render stay verified, and step 3 keeps the status it had --
APPLIED, NOT VISUALLY VERIFIED. Nothing in this file upgrades it.

## The next step, named

Find which `panel.css` rule hides `.captions__list` in the fixture state (candidates: a
`[hidden]` the fixture omits, a `data-*` attribute the product sets, or a `.captions` display
rule), add it to the fixture, and re-render. Then the fade is either visible or it is not.
