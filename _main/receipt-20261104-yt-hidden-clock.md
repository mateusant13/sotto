# A pintura congelada nao manda no ecra — `YOUTUBE_PAINT_STALE` (2026-11-04)

**Lane:** `YtHiddenClock` · **worktree:** `H:/sotto-wt/YtHiddenClock` · **branch:** `lane/yt-hidden-clock`
a partir de `8007032`. Nenhum ficheiro fora do worktree foi tocado; a app **nao** foi lancada.

O dono, verbatim (2026-10-30, a queixa que este defeito explica):
*"a legenda nao ta sincronizada direito. e parece que repete a legenda de instantes atras no ao vivo"*.

---

## 1. A MEDICAO (o fixture e' real, nao sintetico)

`_main/fixtures/yt-paint-freeze-20261104.json` — capturado nesta corrida, na Chrome do dono, pela
CDP `127.0.0.1:9222`, sem `Target.activateTarget`, sem foco, sem play/pause
(`I:/cc-tmp/yt-freeze-capture.py`, descartavel; a unica coisa que ficou e' o fixture):

| campo | valor medido |
|---|---|
| video | `r-AsGBMDI6c` ("Nobody is happy in Eternus") |
| amostras | **745** a ~50 ms, 40,0 s de janela |
| `document.visibilityState` | `hidden` em todas (aba em segundo plano) |
| `video.paused` | `false` |
| `video.currentTime` | **788,34 → 828,30** (+39,96 s) |
| pinturas distintas | **1** (a mesma nos 745 quadros) |
| a pintura | `['>> I am kind of impressed.', 'Are you E6 before the the rank up?']` |
| a faixa servida (`en-orig`, real, pedida ao `youtube_captions.fetch_track` no mesmo video) | 671 cues; a pintura alinha no cue **505,04 s**; o cue que cobre `currentTime` esta' em **786,72 s** |

Ou seja: **a pintura estava ~283 s atras do relogio do video** (`788,34 − 505,04`) e a fonte que o
Sotto le' (as linhas do DOM do player, `_main/youtube-cdp-source-oracle.py`) serviu-a como se fosse
o presente durante 40 s. E' exactamente *"repete a legenda de instantes atras"*.

O fixture guarda as DUAS testemunhas reais: as 745 amostras (`t`, `rows`, `vis`, `paused`) e as 671
cues da faixa. Nada nele foi inventado para o arm passar.

Uma segunda captura, ~6 min depois (§5), leu as MESMAS duas linhas com `currentTime` a
`1140,9..1176,9`: a pintura ficou parada **≥ 352 s de video** sem uma linha nova.

## 2. A MUDANCA

### `app/webview/youtube_monotonic.py` — `PaintStall` + `paint_signature` + `STALE_S` (novo)

O defeito e' a PINTURA a parar enquanto o RELOGIO anda; a decisao vive no modulo do relogio:

```
staleness := (assinatura da pintura inalterada) AND (video.currentTime − t[primeira vez
              que essa assinatura apareceu] > STALE_S = 1,5 s)
stale     := staleness AND (cue_at(faixa, t) existe) AND (align_painted(faixa, pintura).cue ∉ {cue_at(faixa, t)})
```

Os dois lados sao obrigatorios, e cada um nega uma falha do outro:

* sem `cue_at`/`align_painted` (segunda testemunha), um **cue de 8 s** seria chamado congelado so'
  porque o tempo andou — e' a histerese que a ordem exige (arm `A2`);
* sem a assinatura parada, a primeira leitura de cada cue seria "diferente" e a faixa roubava a
  pintura que esta' certa (`A3`, `A7`).

Sem `cue_at` no instante (uma lacuna da faixa) **nao** se declara congelamento: ausencia nao e'
prova, e a pintura mantem a autoridade (`why=no-cue-at-clock`). Uma vez provado, o veredicto FICA na
faixa ate' a pintura mudar (`stale`, `stale-gap`); uma linha distinta devolve-lhe a autoridade no
mesmo tick (`paint-changed`), sem memoria do passado (`A4`).

`STALE_S = 1,5 s` justifica-se pela medicao da propria fonte: a pintura muda a cada 100–300 ms
(`youtube_cdp_source.POLL_S` e a medicao de 2026-11-03), logo 1,5 s e' ~5 a 15 mudancas perdidas. O
limiar **nao decide** nada — so' manda pedir a faixa como segunda testemunha, uma vez por assinatura
(`A9`: 1 pedido em 745 ticks).

### `app/webview/sotto_webview.py` — `ExternalCaptionWatcher._yt_cdp_fast_lines` + `_yt_paint_stall`

O caminho CDP e' o PRIMEIRO `return` de `_youtube`: quando a foto traz linhas, ele servia-as e nao
consultava nem a faixa nem o relogio. Fica assim (4 linhas, no `if _fast_rows:`):

```python
_stalled = self._yt_paint_stall(_snap_fast, _fast_rows, vid)
if _stalled is not None:
    return _stalled
```

`_yt_paint_stall` (metodo novo, logo a seguir) alimenta o `PaintStall` com `(rows, snap['t'],
snap['stamp'], cues)`, pede a faixa UMA vez quando ha' suspeita (`thread.request`, fire-and-forget),
e quando o congelamento esta' provado serve a cue da faixa com o instante que passou por
`_yt_decide` (`youtube_monotonic.decide`) — a mesma forma do ramo `painted-other-track:clock`, com
`yt_reason='painted-stale:clock'` e a linha de log pedida:

```
YOUTUBE_PAINT_STALE t=789.91 painted_age_s=1.6 cue=786.72 text='>> All right. Well,'
```

O chao monotono NAO se mexe neste ramo: `advance()` existe para a PINTURA e desce o chao num salto
>2 s, e chamado com o INICIO da cue (o fundo de um cue longo) parecia um seek — medido no replay:
`794,37 → 792,40` no cue `792,399..797,8`. Foi corrigido antes de fechar (o servico passa so' por
`_yt_decide`; `A8` mede o chao monotono a cada tick).

Sem `Emulation.setFocusEmulationEnabled` (medido antes: 108 ms mediana / 5 s p90 contra 2–5 ms, e a
bateria tem um arm que o proibe). Este ramo nao muda foco, visibilidade nem o estado da pagina.

## 3. ANTES / DEPOIS (o mesmo fixture, os mesmos ticks)

| | ANTES (a pintura manda sempre) | DEPOIS (`_yt_paint_stall`) |
|---|---|---|
| janelas de legenda servidas na janela de 40 s | **1** (as duas linhas de t≈505, repetidas nos 745 quadros) | **12** distintas (786,7 → 824,6 s) |
| atraso da legenda no fim da janela | **~283 s** | ~0 (cue do instante) |
| ticks em que o relogio foi consultado | 0 | 535 stale + 182 lacunas (a faixa nao tem cue) |
| pedido da faixa | 0 (o DOM curto-circuitava) | 1 por assinatura congelada |

Oraculo (`_main/youtube-hidden-clock-oracle.py`, verde 12/12) — `A8` corre o **metodo vivo**
`_yt_paint_stall` sobre as 745 amostras: 535 ticks servidos pela faixa, todos com
`painted-stale:clock` e o texto da cue do instante, chao monotono `True`.

## 4. OS ARMS E O BRACO NEGATIVO

`python _main/youtube-hidden-clock-oracle.py` → **GREEN 12 PASS / 0 FAIL** (rc 0):

* `A1-frozen-clock-track-wins` — pintura congelada + relogio a andar + a faixa noutro cue → a faixa
  ganha, `why=stale`, cue `18.0` (a faixa) contra a pintura alinhada em `14.0`.
* `A2-long-cue-is-not-stall` — cue de 8 s com o relogio a andar 6,5 s → `same-cue`, nada muda.
* `A3-fresh-paint-wins-no-clock` — pintura fresca ganha; a faixa e' um `Tripwire` que **levanta** se
  for iterada — logo "o relogio nao e' consultado" e' medido, nao afirmado.
* `A4-paint-regains-after-30s` — 30 s congelada, linha distinta → `paint-changed`, e o tick seguinte
  continua da pintura.
* `A5-real-frozen-window` — as 745 amostras reais: 1 pintura, primeiro `stale` na amostra 28, 535
  amostras stale, todas com a cue da FAIXA.
* `A6-*` (4 arms, AST no shell) — o caminho CDP chama `self._yt_paint_stall`; o detector usa
  `PaintStall`; o instante servido passa por `_yt_decide`; a linha de log existe.
* `A8-real-method-serves-track` — o metodo vivo, 745 ticks (acima).
* `A9-asks-track-once-per-paint` — 1 pedido da faixa em 745 ticks.
* `A7-control-paint-follows` — a MESMA faixa com a pintura a acompanhar o relogio: **0 stale** em 184
  ticks. E' este arm que mata um detector que diga sempre "congelou".

`--neg-arm` → **rc=1**, 3/3 mutantes focais do proprio modulo apanhados (RED):

```
RED mutant=sem-detector            arm=A1-frozen-clock-track-wins   segundo=recent-paint
RED mutant=congelado-para-sempre   arm=A4-paint-regains-after-30s   seguinte=stale
RED mutant=faixa-sempre-a-frente   arm=A3-fresh-paint-wins-no-clock served=track
NEG-ARM PASS -- RED as designed: 3 de 3 mutantes apanhados
```

Um quarto resultado e' possivel e' deliberado: se um mutante ficar GREEN o oraculo imprime
`NEG-ARM FAIL -- o instrumento esta' CEGO` e devolve **rc=3** (um braco negativo cego nunca e' rc=1).

Os oraculos vizinhos continuam verdes, com o `--neg-arm` a devolver rc=1:

| oraculo | verde | `--neg-arm` |
|---|---|---|
| `youtube-monotonic-oracle --log H:/sotto/_main/webview-run.log` | GREEN 14/14 | rc=1 (`a regra ANTIGA recuou 227 vez(es)`) |
| `youtube-reveal-oracle` | rc=0 | rc=1 (`a janela ja nao batia com o atraso`) |
| `youtube-rows-oracle` | GREEN | rc=1 (13/16 amostras quebradas) |

(O `youtube-monotonic-oracle` le' `_main/webview-run.log`, que nao existe em worktree nenhum —
aponta-se para o log do dono `H:/sotto/_main/webview-run.log`. Sem ele o oraculo devolve NO-VERDICT
rc=2, que nao e' um PASS.)

Tambem corridos sem regressao: `youtube-cdp-source-oracle` (11/11), `youtube-paint-first-oracle`,
`youtube-window-oracle` (12 checks), `youtube-track-wiring-oracle` (12 arms/5 mutantes),
`youtube-foreign-paint-oracle`.

VARREDURA de todos os `_main/youtube-*-oracle.py` (21 ficheiros): 18 verdes, 1 NO-VERDICT (o
`monotonic` sem o log do dono em worktree), e **2 REDs que NAO sao desta lane** — provado por
`git stash` dos meus dois ficheiros: `youtube-1to1-oracle` (`source-is-youtube`) e
`youtube-sync-oracle` (3.5, `window_by_paint ausente`) ficam RED no HEAD **sem** a minha mudanca.

## 5. `Emulation.setIdleOverride` / `Page.setWebLifecycleState` — MEDIDO, NAO ADOPTADO

A ordem permite propor estas duas saidas se forem MEDIDAS. Foram, nesta ordem, na mesma aba
(`I:/cc-tmp/yt-emulation-measure.py`, 3 fases de 12 s, `Emulation.setIdleOverride
{isUserActive:true, isScreenUnlocked:true}` seguido de `clearIdleOverride`, depois
`Page.setWebLifecycleState {state:'active'}`; nada de foco, `activateTarget` ou play/pause):

| fase | resposta do Chrome | `visibilityState` | amostras | pinturas distintas |
|---|---|---|---|---|
| baseline | — | `hidden` | 215 | **1** |
| `Emulation.setIdleOverride` | `ok` | `hidden` | 219 | **1** (a mesma) |
| `Page.setWebLifecycleState('active')` | `ok` | `hidden` | 194 | **1** (a mesma) |

Os dois comandos sao ACEITES e nenhum cura: a aba continua `hidden` e a pintura continua parada.
Nao se adoptam. O que muda (e nao e' o `visibilityState`) e' o pedido de `Runtime.evaluate`, que
funciona sempre — por isso a fonte de verdade passou a ser o RELOGIO do video + a FAIXA, nao a
pintura.

O mesmo instrumento mediu, de caminho, a DURACAO do congelamento: a pintura vista na captura do
fixture (`t≈788`) e' a MESMA que este probe leu a `t=1140,9..1176,9` — a pintura esteve parada por
**≥ 352 s de video** (5m52s) sem uma unica linha nova. E' a razao pela qual um limiar de 1,5 s nao
esta' a inventar um defeito: o defeito e' longo e mensuravel.

## 6. FICHEIROS

```
 M app/webview/youtube_monotonic.py          (PaintStall, paint_signature, STALE_S)
 M app/webview/sotto_webview.py              (+4 linhas em _yt_cdp_fast_lines; +_yt_paint_stall)
?? _main/youtube-hidden-clock-oracle.py      (12 arms + 3 mutantes)
?? _main/fixtures/yt-paint-freeze-20261104.json  (745 amostras reais + 671 cues reais)
?? _main/receipt-20261104-yt-hidden-clock.md (este ficheiro)
```

`app/webview/youtube_window.py` e `app/webview/youtube_reveal.py`: **nao** precisaram de mudanca — o
detector usa as funcoes de producao que ja' existiam (`youtube_captions.cue_at`,
`youtube_captions.align_painted`, `youtube_monotonic.decide`, `_yt_lines`).

Nao foram tocadas as regioes do `YtSourceOnBoot` (attach CDP no arranque, `YOUTUBE_TICK_MS`); o hook
foi anunciado por `agent://YtSourceOnBoot`, que confirmou que os hunks sao disjuntos. O `_yt_diag`
deste ramo e' escrito com a forma combinada (`src/why`, `vid/age` ao vivo).

Nota: `_main/_ep-logs/dml-verbose*.txt` aparecem `M` no `git status` do worktree e **nao** sao desta
lane (nenhum comando meu lhes toca); ficam como estao.

## 7. O QUE NAO SE PROVOU (`[INFERENCE]`)

* **Nao houve corrida end-to-end da app** (a tela do dono nao e' banco de ensaio, e a app nao sobe
  nesta pane). O metodo vivo foi exercitado com o fixture real, nao com o laco a 16 Hz.
  `[INFERENCE]` o primeiro tick depois de congelar serve a pintura por ~1,5 s de video e so' depois
  passa a' faixa — e' o que `A5`/`A8` medem no fixture, e e' o comportamento desenhado.
* **O caminho UIA (sem foto CDP) nao foi tocado nem medido.** Se o snapshot faltar e a arvore de
  acessibilidade tambem estiver congelada, a mesma classe pode reaparecer por essa porta — o detector
  hoje vive so' no `_yt_cdp_fast_lines`.
* **Uma lacuna da faixa** com a pintura congelada serve NADA (`painted-stale-gap`), nao a cue
  anterior: e' o que o player faz (nada no ecra), mas nao foi medido no ecra do dono.
* **Risco residual**: se a pintura congelada coincidir textualmente com um cue FUTURO da faixa, o
  `same-cue` segura a pintura ate' esse cue acabar. Nao foi observado em 745 amostras.
* Os numeros de §5 medem as CURAS propostas (`setIdleOverride`, `setWebLifecycleState`), nao a cura
  adoptada.
