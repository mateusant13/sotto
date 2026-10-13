# Rendering a zip mockup: the fidelity instrument, end to end

2026-10-13. Follows `receipt-20261013-zip-mockups-buildable.md`. That one proved the
reference can be BUILT. This one proves it can be RENDERED, and states what the render
does and does not give.

## The chain, all three steps measured

```
# 1. BUILD -- the zip ships its own toolchain; no install
cd _moved/aireplay/docs/design/sotto-transcription-panel-designs
NODE_ENV=production node node_modules/vite/bin/vite.js build
#   -> dist/index.html 263.89 kB, JS and CSS inlined by vite-plugin-singlefile

# 2. RENDER -- Edge is on this box, and headless needs one command
"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" --headless=new \
  --disable-gpu --hide-scrollbars --window-size=1280,800 \
  --screenshot=I:/cc-tmp/zipE.png file:///.../zip-E-panels.html
#   -> 406698 bytes written, rc=0, ZERO stray processes

# 3. READ THE DOM -- the rendered tree, not the source
"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" --headless=new \
  --disable-gpu --dump-dom file:///.../zip-E-panels.html
#   -> 276192 B of RENDERED DOM
```

Chrome is also present (`C:/Program Files/Google/Chrome/Application/chrome.exe`), and the
WebView2 runtime this product uses is at `EdgeWebView/Application/154.0.4258.62/`.

## What the first render already shows

Grepping the rendered DOM for the five zip-E panel names gives: Teleprompter 5,
**Broadcast 2, Cinema 2, Instrument 8, Manuscript 0**. Manuscript at ZERO is not a missing
design -- the mockup is an INTERACTIVE app that shows ONE panel at a time, and `--dump-dom`
captures the default state. Reaching each design means driving the selector, which is a
click, not a flag.

## What this does NOT give, and I must not be read as claiming it

* **I CANNOT SEE THE PNG.** This model has no image input: `read_image` refuses with
  `model "deepseek-v4.1-flash" does not declare image input`. So the render is a real
  artefact and I have never looked at it. Any claim that a design LOOKS like the zip
  still needs eyes, and they are the owner\u2019s.
* **Nothing has been COMPARED yet.** No metric has been computed between the mockup and any
  live theme. The three steps above are each measured; the comparison is not begun.
* The DOM dump is the DEFAULT panel only. Contrasting pd-tele/pd-bcast/pd-mano/pd-cine/
  pd-instr against the five zip-E panels needs the selector driven.

## What IS now available that was not

A renderable, self-contained reference for a zip design, producible in about two seconds
with tools already on the box, **with no install and without touching the product or the
owner app** -- the render runs in its own headless process, and the measured stray-process
count after the run is 0.

The comparison that becomes possible: pixel and DOM metrics between the mockup and the
painted panel, since both can be produced by the same engine. The part that still cannot be
automated away is the judgement of whether the result is RIGHT, and that is the owner\u2019s.
