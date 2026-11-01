# Receipt — the relay path can no longer un-pause the owner's video, and a gate that could never pass now passes

Lane `sotto-lane-task-resolver-continuation` · 2026-10-27 · **no commit, no push** · no browser launched,
no app launch, no heavy lease (the heavy hold stays in force — the owner is gaming).

## 1. The risk this closes

`_main/yt-1to1-live-compare.py` has two modes. `edge` (the default) opens its **own** muted Edge on
`I:\cc-tmp\edge-1to1` and never touches an owner tab. `relay` does the opposite, and the module docstring
said the opposite:

| what relay mode does | where |
|---|---|
| navigates the **owner's** tab to the video URL | `driver([... "--navigate", url ...])` |
| brings his tab to the front | `Page.bringToFront` |
| seeks to 0 and starts playback | `PLAY_JS` — `mp.seekTo(0, true)`, `mp.playVideo()` |
| toggles subtitles and can play again | `CC_JS` — `mp.playVideo()` inside `if (!before && ccOn())` |
| reuses an **existing** tab, does not open one | `pick_tab()` — home page first, else `yt[0]` |
| restores playback only if `wasState === 1` | `RESTORE_JS` — read **after** `CC_JS` already started it |

So a video the owner had **paused** could end up playing: the state that decides restoration is captured
after the code that starts playback. That is not a theory about a loop — no loop exists — it is what one
deliberate `--browser relay` run would do to his screen.

## 2. The cure (a guard, not a wish)

`--browser relay` now requires `--allow-playback-control`, checked **before** any socket is opened:

```
if args.browser == "relay" and not args.allow_playback_control:
    print("LIVE_1TO1 REFUSED -- o modo relay controla a aba do DONO ...")
    return 2
```

| arm | command | rc | output |
|---|---|---|---|
| guard fires | `--browser relay` | **2** | `LIVE_1TO1 REFUSED -- o modo relay controla a aba do DONO (navega, Page.bringToFront, seekTo(0), playVideo(), toggleSubtitles).` |
| guard passes, relay down | `--browser relay --allow-playback-control` | **2** | `relay indisponivel (URLError(ConnectionRefusedError(10061 ...)))` |
| selfcheck | `--selfcheck` | **0** | `SELFCHECK amostragem_salta=True neg_arm_salta=False` → `SELFCHECK PASS` |

Arms 1 and 2 both exit 2 but print **different** lines, which is the proof the guard fires *before* the
connection attempt rather than the connection failing first.

The docstring paragraph that claimed relay "opens its own tab in the background" and "touches nothing the
owner is seeing" is replaced with what the code does, measured above.

## 3. A gate that was red by construction, found while testing the cure

`--selfcheck` reported `amostragem_salta=False neg_arm_salta=False` and `FAIL`, **pre-existing and not
caused by this change** — measured before and after the docstring edit, and the anchors it searches for do
not appear in anything I added.

Cause, measured: the detector located the sampling loop with `src.find("        samples = []")`. That literal
appears **three times** (offsets 23480, 23861, 31002) — twice because `_sampler_seeks` and `selfcheck` quote
the anchor in their **own source**. `find()` therefore landed inside the detector and sliced **43 characters**
(`ini = src.find(...)`), which contains no `SEEK_JS`; the gate could never pass, and its negative arm could
never fire either.

Cure: one definition, `_sampling_block(src)`, anchored on a marker unique to the loop
(`driver([... PLAY_JS])\n        samples = []` → `data["samples"] = samples`), with the anchor literals **split
by concatenation** so the detector cannot read itself. Both `_sampler_seeks` and `selfcheck` now call it.
Result: `amostragem_salta=True`, `neg_arm_salta=False`, `SELFCHECK PASS`, rc 0.

## 4. What this does NOT prove

- **No live relay run.** The relay is down (0 listeners on 9224), so the refusal path is proven and the
  torch-and-restore path is not exercised. `RESTORE_JS` still cannot un-play a video if someone passes
  `--allow-playback-control` — the consent flag is the only protection left there, and I did not add
  "capture state before any play" because it needs a live relay to be verified rather than asserted.
- **No battery step** runs either the selfcheck or the break-position probe yet: wiring them changes the
  `.cmd` pin, and I will not move a pin in the same turn as the change it would cover.
- `--selfcheck` proves the **sampling** jumps; it says nothing about the measurement matching the player.

## SELF-AUDIT

1. **claimed-state:** relay mode refuses without explicit consent (rc 2, proven by a distinct message);
   `--selfcheck` passes and its negative arm discriminates. Both measured today; neither `verified` by an
   independent party.
2. **what-changed:** `_main/yt-1to1-live-compare.py` only — guard + flag, docstring correction, and
   `_sampling_block` replacing two copy-pasted anchors. No product file, no `app/`, no `worker/`.
3. **commands-run:** `py_compile` (rc 0); `--browser relay` (rc 2, REFUSED); `--browser relay
   --allow-playback-control` (rc 2, relay down); `--selfcheck` (rc 0, PASS); `--help` shows the flag;
   three anchor-offset probes printed the 43-char slice.
4. **what-I-did-not-do:** no browser launch, no Edge, no relay probe request, no battery, no build, no heavy
   lease, no commit, no touch of the owner's Chrome.
5. **refuted-mine:** my earlier statement that "nothing calls relay mode" was true but incomplete — it was
   one operator flag away, and the restoration logic recorded `wasState` **after** playback started. Also
   refuted: the docstring's claim that relay opens its own background tab.
6. **red-I-did-not-cause:** `--selfcheck` was already FAIL (43-char slice, three anchor occurrences); the
   heavy hold; the earlier AMBER lease. Named, and the selfcheck red is now cured rather than excused.
7. **gate-doubt:**
   - *verde-de-verdade:* the guard is proven by message ordering (refusal beats connection failure), and the
     selfcheck by a positive **and** a negative arm in one run.
   - *falta-no-gate:* nothing in the battery runs `--selfcheck`, so a future edit could re-break the sampling
     and no wired gate would say so; and `RESTORE_JS` still assumes the state it recorded is the state it
     changed.
   - *gate-melhor:* wire `--selfcheck` next to the existing youtube steps, and make playback restoration
     capture `wasState` **before** `CC_JS`/`PLAY_JS` so even consented relay runs restore what they found.

## INTENT-PROGRESS

helps: the owner asked whether this lane un-pauses his YouTube. A grep is not an answer he can rely on
while the tool still *can* do it with one flag. Now the tool refuses by name, and the refusal is measured —
so "it wasn't us" holds even if someone else runs it, and his player is safe from the one script that could
have moved it. His 1:1 work is unaffected: nothing here touches captions.

todo: W-16

next: make consented relay runs capture playback state **before** any play and restore it, then wire
`--selfcheck` and `break-position-1to1` into the battery with the pin re-measured in that same edit — no
browser needed until the owner says gaming has stopped.
