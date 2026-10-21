# Receipt — 2026-10-21 — the demo leftovers, translated to ONE stream

## Why

Two owner screenshots, verbatim:

> *"e por algum motivo os designs tem coisas a mais que nao deveriam, da demo anterior.
> como algo escrito 'filed' em uma parte do painel. tambem tem uma linha esquisita que nao
> faz sentido, mal design."*

> *"olha isso. tem design da demo q ainda ta BURRO. a gente nao ta fazendo conversacao entre
> duas pessoas, ou simulando um bate papo. por que isso ta assim? se o design original era
> assim, era pra tu traduzir pro nosso caso."*

> *"tem design com uma bola a esquerda das transcricoes como se a bola fosse de uma foto de
> um personagem. completamente ridiculo. arruma"*

## The rule applied to every generated design

The mockups are **two-voice demo panels**: they carry a fake multi-speaker transcript, avatars
with initials, speaker chips, left/right chat alternation and mock chrome. Sotto is **one
stream**. Every mock metaphor whose meaning depends on *more than one voice* is removed; the
design's genuine single-stream decoration (rules, cards, type, the timeline node, the quote
glyph) stays.

## What changed, per design (`_main/_design-lane/gen_zipc.py`)

| design | removed | was |
|---|---|---|
| Paper | the `filed` stamp, the `— continued, please don't brake on the gravel —` sign-off, the `left:52px` accent rail | `::after` / `::before` generated text + an absolute hairline the owner called *"uma linha esquisita"* |
| GlassCards | the 3-circle avatar cluster and the 28px empty avatar disc; card is now full width | `-space-x-2` avatar row + `grid h-7 w-7 rounded-full` slot → an empty profile photo per row |
| Hairline | the 4px speaker dot before every line | singular voice marker |
| Ledger | the `time / voice / transcript` band and the 8px `.caption__led` voice disc; time + transcript only | a speaker column that held nothing |
| Bubbles | the two speaker chips, the left/right alternation, the 5px bubble tail, the three "speaking" dots; one left-aligned card | a two-person chat |
| Chips | the fake `search this session…` pill (a `content:` string, never an input) | mock search chrome (owner asked the search box out regardless) |
| Gutter | the 24px gutter avatar disc and the `rec` pill | an initials avatar + a fake status word |

## Correction that did NOT touch the generator: the skin's live plate

`app/panel/skin-host.js` `renderLive()` copied the vendor's own fallback
(`partial?.words ?? previous.text.split(' ')`). In THIS composition the previous line is already
a row in the transcript list, so the plate painted it a second time (**the duplicate the owner
saw: "Estamos aqui já…" twice**) and, on commit, shrank from the long forming line to the short
closed one (*"foi sumindo"*). The fallback is gone; the plate is the FORMING line only and hides
when empty.

## What changed in the app bar

`app/panel/panel.html`: removed `<svg class="wordmark__mark">` (the app icon) and
`<p class="wordmark__tag">live captions</p>`, per *"retira o icone do app dos paineis. deixa só
escrito sotto"* and *"tambem retira 'live captions' do painel."* Only `sotto` remains.

## The gate

`gen-proof.py` → **PASS** — every shipped output reproduces byte for byte from its generator
(including `zipc-panels.css`, sha256 `8A4611613651DFDC92A9251779BF964CE8426C644AEA42BDB6FB10AAED24EB71`).
No generated CSS was hand-edited; the generator was changed and the output regenerated.

## NOT done yet (declared, not forgotten)

- the other two generators (`gen_themes.py` 5 directions, `gen_cinematic.py`) and the
  `skin-*` vendor fragments have not had the same sweep;
- the app-bar redesign (order `[dot][theme][3-dot][close]`, stable geometry, transparent
  borders, the 3-dot menu, `ready` / `not ready`, the worker cause moved into the menu);
- the translation policy + selector and the YouTube line-break timing;
- the duplicate committed line in the ENGINE (Bubbles showed the same sentence at
  18:26:13 and 18:26:21 — a worker/engine double-commit, not the plate), and the `,.`
  trailing-punctuation bug.
