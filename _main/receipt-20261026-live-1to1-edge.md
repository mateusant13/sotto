# Receipt — the live 1:1 is measurable, and it matched 16/16

Lane `sotto-lane-task-resolver-continuation` · date 2026-10-26 · route measured: `providerID=opencode-go-3`
(see `_main/receipt-20261026-receipt-provenance.md` §2 for the instrument) · **no commit, no push**.

State claimed: the lane's own blocker was **wrong**, and the live half of the owner's 1:1 is now measured.
`MATCH 16/16` is `measured by the author`, **not** `verified`.

## 1. The claim this receipt retracts (mine, from an earlier receipt)

Two earlier receipts said the live half could not be measured:

> *"metade viva NAO medida (relay 9224 DOWN, yt-dlp com bot-check, lease heavy recusado commit 86.2%)"*

It is half true and half self-imposed. **Measured now:** `Test-NetConnection 127.0.0.1:9224` → `False`,
`Get-NetTCPConnection -State Listen -LocalPort 9224` → **0 listeners**. The relay *is* down. But
`_main/yt-1to1-live-compare.py` does not need it: `--browser` defaults to **`edge`**, and `start_edge()` opens
its own Edge on a private profile (`I:\cc-tmp\edge-1to1`) with `--mute-audio` and
`--remote-debugging-port=9333`. The relay is only the `--browser relay` path, i.e. the owner's own tab.

So the blocker recorded twice was **the wrong instrument being treated as the only instrument**. The
correction is not that the relay came back; it is that nothing was waiting for it.

**Authorisation, quoted because it is the reason a browser window may open at all** — the owner,
2026-10-23, verbatim in the file: *"abre essa merda no edge e muta o edge de algum jeito q eu nao escute
mas o sistema sim. eu nao to usando o edge entao tu pode fazer mais oq tu quiser."* The window is **visible**
on his desktop for the duration (1280x800, no `--headless`), muted, and the Edge tree is killed by **PID**
at the end — `LIVE_1TO1 edge fechado (a arvore do PID que abrimos)`.

## 2. The measurement

| fact | value |
|---|---|
| video | `WdaHAGRBB6s` — "Yamato Says Apollo's Sword Is Useless" · `dur=32.0s` |
| tracks offered / painted / served | `20` offered · player paints **`en`** · Sotto serves **`en-orig`** |
| captions on | `cc=True`, `track_lang=en`, `visibility=visible`, `tries=0` |
| painted cues read from the player | **19** |
| samples | **16**, `matches=16`, `fails=[]` |
| verdict | **`MATCH`**, rc=0 |

What is compared, exactly: the text the player is **drawing** at instants read off the player's own clock
(`getCurrentTime`), against the window Sotto's `live_lines` model builds over the **served** cues
(`_cache/youtube-captions/WdaHAGRBB6s.jsonl`, not a fresh parse). Both sides kept (§3).

The language rule holds on this case: the painted track is `en`, Sotto serves `en-orig` — original language,
no translation. (One English case; the Spanish-never-translated case is **not** covered here.)

## 3. Artefacts kept (acceptance 1's "both captures")

| artefact | bytes | sha256 |
|---|---|---|
| `_main/fixtures/yt-WdaHAGRBB6s.en-orig.json3` (YouTube's own payload) | 9304 | `9806E76A435A8AF8F8F6C98745579E5E14D08F57B6B85C23DC66286B461D67AB` |
| `_cache/youtube-captions/WdaHAGRBB6s.jsonl` (what the app serves) | — | `29CB0F9235DAD84D971DA9B2A54DEBF683EF2BFBD9045794B7C16B4327E7659D` |
| `_main/fixtures/yt-WdaHAGRBB6s.live-compare-20261026.json` (the comparison) | 5242 | `B8C397E42D281A5D060388BE62C84B29130F22A394C8E1D58B685737BB183ADF` |
| `_main/_audit-verify/yt-1to1-live-20261026.log` (transcript) | 543 | — |

The payload half was re-measured **today**, not quoted: `_main/youtube-1to1-oracle.py` → 7 elements green,
`words 0/677`, `linebreaks 0/677`, `timing 0/18 + 0/18`, `word-reveal 0/677`, `69` segments with `tOffsetMs`
in the payload, `88` words with a clock in the served cues, `reveal-wired 0/4` missing anchors.

## 4. Commands and exit codes (from `H:\sotto`)

| # | command | rc | verdict |
|---|---|---|---|
| 1 | `python _main\youtube-1to1-oracle.py` | 0 | `YOUTUBE-1TO1 VERDICT GREEN`, `elementos=7 vermelhos=0` |
| 2 | `python _main\yt-1to1-live-compare.py` (default browser, 12 samples) | 0 | `LIVE_1TO1 iguais=12/12 veredicto=MATCH` — transcript lost (§6) |
| 3 | `python _main\yt-1to1-live-compare.py --video WdaHAGRBB6s --samples 16 --json …` | 0 | `matches=16 fails=[] verdict=MATCH`, artefact written |
| 4 | `Test-NetConnection 127.0.0.1:9224` / `Get-NetTCPConnection -State Listen` | — | `False` / `0` listeners — the relay is down and was not needed |
| 5 | `python I:\!manager\tools\audit-sweep.py --sweep` | 1 | `open_P0=18`, **sotto paths = 0** (§6) |
| 6 | `python I:\!manager\tools\performance-gate.py status` | 4 | `AMBER commit-pct=81.1 heavy_allowed=False amber_light_allowed=True` |

## 5. What this does NOT prove

- **The pixels of the owner's own overlay are still unmeasured.** `caption_overlay.py` is what he *sees*
  (per `AGENTS.md`: *"a legenda que o dono VE e a NATIVA"*); this run compares his **player's** caption to
  our **window model**, not our native window's pixels. That gap is the same one §1 of the 1:1 oracle
  documents, and it is not closed here.
- **16 samples on a 32 s video.** Not the whole timeline, not a long video, not a 2-line↔3-line transition
  at a hard boundary.
- **Acceptance 4 (two cold starts, no white block) and 5 (Alt+C double-tap)** remain `NOT RUN`. Both need
  the app, which is heavy class and needs the owner's word.
- **No independent verifier.** `MATCH` here means *measured by the author*.
- **One language case**: English. The Spanish-never-translated rule has no case in this artefact.

## 6. Instrument defects found while doing this

1. **My own command lost its transcript.** Run #2 piped through `Tee-Object` *and* `Select-Object -First 8`,
   which cut the stream: the log holds 8 lines / 543 B and no verdict line, and the 12/12 result survives
   only in scrollback. Run #3 kept the JSON, so the evidence exists — but the lesson is that a transcript
   captured through a truncating pipeline is not a kept capture.
2. **`audit-sweep` cannot see this project.** `--sweep` → `documents=7`, `queue_records=16063`,
   `open_P0=18`, and **0** occurrences of either `H:\sotto` or any sotto receipt in `state/audit/queue.json`.
   Its population is the Manager's `runs/*.md`. So every `SELF-AUDIT` admission this lane has written —
   including the two protocol ones in this file — is outside the mechanism whose stated purpose is
   *"so an admission cannot evaporate"*. Reported, not silently worked around.
3. **A wrong blocker survived two receipts** (§1). It was not a lie; it was an instrument never tried.

## SELF-AUDIT

1. **claimed-state:** the live 1:1 half is measured (`MATCH 16/16`), and a blocker I had recorded twice is
   retracted. Not `verified`: no independent verifier.
2. **what-changed:** `_main/fixtures/yt-WdaHAGRBB6s.live-compare-20261026.json` (new artefact),
   `_main/_audit-verify/yt-1to1-live-20261026.log` (new transcript), this receipt, and the W-16 row in
   `I:\!manager\state\herdr\TODO.md` (blocked → doing, with the corrected reason). No product file touched.
3. **commands-run:** §4, six rows with rc; the two 1:1 verdicts quoted from their artefacts, not from memory.
4. **what-I-did-not-do:** no commit, no push, no app launch, no panel, no Alt+C, no cold start, no write in
   `app/` or `worker/`, no heavy lease requested.
5. **refuted-mine:** (a) "live half impossible without the relay" — false, the file has its own Edge mode;
   (b) my transcript pipeline truncated the very evidence it was capturing; (c) my earlier W-16 `blocked`
   was a miscalibrated *state*, not a missing input.
6. **red-I-did-not-cause:** `performance-gate` AMBER at `commit-pct=81.1`; `audit-sweep` green-but-blind for
   sotto. Both named, neither rounded up.
7. **gate-doubt:**
   - *verde-de-verdade:* the `MATCH` is a per-sample comparison against the player's own clock with the
     painted cues counted (19) and the fails list printed empty — not a summary string. The payload half has
     its own 7 named arms and 9 mutants from `youtube-1to1-oracle.py`, re-run today.
   - *falta-no-gate:* the live script has **no negative arm of its own** — nothing proves it would report
     `DIFF` if the player and our cues disagreed. `fails=[]` today is unfalsified; the oracle's mutants
     cover the data half, not the DOM half.
   - *gate-melhor:* give `yt-1to1-live-compare.py` a `--mutate <n>` that shifts one served cue by 300 ms in
     a temp cache and requires `verdict != MATCH` — the DOM half then has the same kind of proof the data
     half already has.

## INTENT-PROGRESS

helps: the owner's intention, in his words, is that the caption on his screen *"tem que bater timing,
linha/quebra de linha e etc, 1:1"* with YouTube's, and four days of it not happening is what he called
*"PATETICO E BUGADO"*. Until this turn the lane believed the screen half could not be measured at all —
that belief was the reason his complaint could sit open while payload gates went green. The live half is
measurable today with his own authorised muted Edge, and it came back `16/16 MATCH` on a real video: words
and window match the player at 16 instants. The honest remainder is now narrow and named — our **native
overlay's pixels**, cold starts, and Alt+C — instead of a vague "not measured".

## 7. SAMPLER-SEEK — o amostrador nao saltava (corrigido, nao medido depois)

O QUE ESTAVA ERRADO. `_main/yt-1to1-live-compare.py` promete no proprio cabecalho (linha 22)
*"percorre o video a saltos (`seekTo`) e le a janela de legendas depois de cada"* — e **nao
saltava**: o laco lia `READ_CAPTION_JS` e dormia `time.sleep(args.every)`, sem `seekTo` nenhum.
Medido 2026-10-26 **antes** da correcao: 40 amostras a 0,6 s = 24 s de parede, e o
`currentTime` do player andou de 3,33 s para 4,84 s — **1,5 s de video em 24 s de parede**
(buffering). Todas as amostras ficaram na entrada/anuncio, `cc=True` e janela vazia, e o
instrumento devolveu `nada medido` com rc=2.

CODIGOINTEL, escopo exato `_main/yt-1to1-live-compare.py`, **antes** da correcao:
- `seekTo` → **4** linhas: `22`, `213`, `221`, `228`; ripgrep no mesmo ficheiro: **4 = 4**.
  `:221` e o `SEEK_JS`; `:213` e `:228` sao `PLAY_JS`/`RESTORE_JS`. Ou seja o `SEEK_JS`
  existia e **nao era chamado pela amostragem** — codigo morto para este efeito.

A CORRECAO, no proprio ficheiro, sem segundo harness: grelha de instantes sobre `dur`
(`span = max(0.0, dur - 0.6)` e `step = span / (target - 1)` em `:649`), `SEEK_JS % {"t": at}`
em `:657`, `time.sleep(args.every)` para o contentor repintar em `:661`, e a leitura em `:662`.
Cada amostra passa a gravar `asked` (o instante **escolhido**) ao lado de `t` (o atingido).

CODIGOINTEL **depois** da correcao (mesmo escopo exato), com a paridade de ripgrep ao lado:
- `SEEK_JS` → **6** linhas: `220`, `499`, `509`, `524`, `549`, `657`; ripgrep **6 = 6**.
- `span = max` → **1** linha: `649`; ripgrep **1 = 1**.
- `selfcheck` → **8** linhas: `512`, `520`, `526`, `528`, `530`, `548`, `552`, `553`;
  ripgrep **8 = 8** com `-i`. As linhas `520/526/528/530` sao as cadeias `SELFCHECK`
  maiusculas; um ripgrep case-sensitive devolve 4 e a diferenca foi **resolvida**, nao
  escondida.

SHA256 do ficheiro corrigido:
`7AF92FE4DCB892C68527337AC4E001B400A81C8A44B2372B2A66380F95FD2B7B` (`py_compile` rc=0).

O QUE ISTO **NAO** PROVA.
- **Nao houve medicao depois da correcao.** Nenhum `MATCH` novo: o `16/16` da seccao 2 e
  **anterior** a este patch. A correcao esta no codigo, nao num numero.
- **O teste do instrumento esta DIFERIDO.** `python _main/yt-1to1-live-compare.py --selfcheck`
  — que traz o braco negativo: tirada a linha do salto, o detector tem de dizer que nao salta
  — **nao correu**, porque a regra em vigor proibe testes durante o Gaming. Fica nomeado, nao
  contado como portao que passou.
- Nada disto toca a metade **nativa** (os pixels do overlay do dono) nem as aceitacoes 4 e 5.

todo: W-16

next: **measure the overlay he actually looks at** — run the app hidden through the sanctioned lane path
(`SOTTO_LANE_LAUNCH=1` + `_main/keepalive.py`, nothing on his screen), navigate the same video
`WdaHAGRBB6s`, and capture the native `caption_overlay` window's own lines at the same instants as the
16-sample set, then diff them against the player's painted cues. That is the last unmeasured link between
"our cues match YouTube" and "what he sees matches YouTube", and it is what turns this receipt's `MATCH`
into a statement about his screen rather than about our model.
