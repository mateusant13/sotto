# RETRACTION: there is NO header overlap. I misread the render.

2026-10-13. Retracts `receipt-20261013-header-overlap.md` and
`receipt-20261013-header-overlap-3-refuted.md` in their central claim.

## What I claimed

That the header painted EM ESPERA twice, overlapping, on the base panel and so on every theme.
I called it a real defect and spent three rounds hunting it, refuting three candidates.

## What the COMPUTED STYLE shows

Read over the paint probe `--readback` seam, which uses `exec_js`, so the panel CSP does not
block it. `PAGE_READBACK_JS` was extended to report `getComputedStyle` for the header children
and for every `.chrome__state` pair.

Header children:

- `wordmark` -- display flex
- `chrome chrome--tele` -- display **flex**, THE ONLY ONE VISIBLE
- `chrome chrome--bcast`, `--mano`, `--cine`, `--inst` -- display **none**
- `panel__controls` -- display flex

And inside the visible chrome: `parent=flex self=flex on=NONE off=block`.

So `chrome__on` is display none, only `chrome__off` paints, and exactly ONE chrome is visible.

## The cause of my sighting is mundane

The earlier `--dump-dom` printed the visible chrome textContent as LENDO EM ESPERA run together,
and `textContent` RETURNS TEXT FROM `display:none` CHILDREN TOO. The hidden word and the visible
one sit adjacent in that string, and in a 380x900 image scaled to a preview I read the adjacency
as two painted copies.

The DOM never showed an overlap. The computed style never showed one. The image did not either.
I did.

## Two rules

1. `textContent` is not what is painted. It includes hidden subtrees, and using it as evidence
   of what a user sees is the same class of error as reading a file on disk as evidence of what
   a browser received -- which this session already made with the 350 KB `cinematic.css` served
   as an EMPTY body.
2. A scaled screenshot of small text is an instrument with a resolution limit. Before calling
   something a rendering defect, read the COMPUTED style -- the instrument was two lines away.

## What survives

Nothing about this defect. The chrome mechanism is healthy: inert by default, exactly one
claimed by its theme, `__on`/`__off` toggled correctly against `data-state`. **No change was made
to the product in any of the three rounds, which is the only reason this retraction costs
nothing but time.** The probe gained a permanent computed-style readback.
