# Recibo — roll-up do player REAL do YouTube, valores COMPUTADOS (2026-11-08)

status: done (com um braço UNMEASURED declarado e justificado)
data/hora local: 2026-11-08 02:19 -0300 (fecho do recibo)
worktree: H:/sotto
escopo desta lane: só este recibo. Nenhum outro ficheiro do repo foi escrito.

## 1. O que foi pedido, e o que foi entregue

Pedido da Main (verbatim, 2026-11-08): *"uma leitura VIVA que confirme ou refute `0,433 s` /
`cubic-bezier(0,0,.2,1)` como valores COMPUTADOS no player de hoje (o CSS lido e' a folha
servida, nao o `getComputedStyle`)."*

Entregue, medido na sessão viva e headless, na folha viva do player:

| valor | computado (verbatim `getComputedStyle`) | veredicto |
|---|---|---|
| `transitionDuration` | `0.433s, 0.433s` | **CONFIRMA 433 ms** |
| `transitionTimingFunction` | `cubic-bezier(0, 0, 0.2, 1), cubic-bezier(0, 0, 0.2, 1)` | **CONFIRMA a curva** |
| `transitionProperty` | `transform, -webkit-transform` | só `transform`, sem `opacity`/`filter` |
| `transitionDelay` | `0s, 0s` | sem atraso |
| `transitionend` medido | **430,9 ms** (no-preference) / 434,6 ms / 440,6 ms (reduced) | fecha o 433 ms |
| `.caption-visual-line` `transitionDuration` | `0s` | a linha em si não anima |
| `.caption-window` `transitionDuration` / `overflow` | `0s` / `hidden` | a janela recorta, não anima |

A curva foi também **medida em movimento** (não só lida): 179 amostras de
`getComputedStyle(.captions-text).transform` a cada `requestAnimationFrame`, com um deslocamento
igual a uma altura de linha. O progresso medido contra `cubic-bezier(0,0,0.2,1)` dá
**erro máximo 1,7 %, erro médio 0,5 %**; contra linear dá **erro máximo 36,1 %, erro médio 24,2 %**.
Logo a curva é a bezier, não linear.

## 2. Sessão e instrumento (sem janela, sem áudio, sem perfil do dono)

- Sessão própria `agent-browser`: `yt-rollup3-ebfc3c0a76fc` (`--scope worktree --prefix yt-rollup3`),
  separada da sessão do dono. Zero `--headed`, zero `ShowWindow`, zero `window.open`.
- O daemon expôs CDP em `ws://127.0.0.1:49587/devtools/browser/…`; as leituras foram feitas por
  `Runtime.evaluate` nesse CDP (mesmo caminho que `app/webview/youtube_cdp_source.py` usa).
- Vídeo carregado: `https://www.youtube.com/watch?v=WdaHAGRBB6s` (32,081 s; faixa `en` do próprio
  vídeo é `asr`). Também abri `iG9CE55wbtY` (TED, faixas `manual` em 30+ línguas) e o mesmo
  bloqueio de cues se repetiu.
- `prefers-reduced-motion` vinha `reduce` no headless; repeti com
  `Emulation.setEmulatedMedia {"features":[{"name":"prefers-reduced-motion","value":"no-preference"}]}`
  e os valores são os mesmos. Os números acima são os de `no-preference`.
- Nenhum áudio foi tocado (`video.muted = true`).

### 2.1 Como o elemento foi posto na folha viva

O player **nunca criou uma cue** nesta sessão (ver §3). Para ler a folha viva sem inventar CSS,
construí a cadeia de classes REAL dentro do contentor REAL do player:

```
document.createElement('div')  class = "caption-window ytp-caption-window-rollup ytp-rollup-mode"
  └─ span class = "captions-text"
       └─ span class = "caption-visual-line"
```

… e anexei-a a `#ytp-caption-window-container` (que existe vazio). O `getComputedStyle` foi lido
nesse elemento, **na página viva**, com a folha do player aplicada; o elemento foi removido no fim.
Isto mede a folha viva, não uma cópia: a regra foi encontrada na CSSOM da própria página (§2.2) e o
valor computado veio dela.

Limite honesto deste braço: **não é uma cue real**. Se o player escrever um `transition` INLINE no
`.captions-text` em tempo de execução, este teste não o veria (o elemento sintético não tem esse
inline). O que fica provado é que a regra servida, aplicada a estas classes na página viva, computa
`0.433s` / `cubic-bezier(0,0,0.2,1)` — e que o browser interpola assim.

### 2.2 A regra na CSSOM viva (verbatim)

```
.ytp-caption-window-rollup.ytp-rollup-mode { overflow: hidden; }
.ytp-caption-window-rollup.ytp-rollup-mode .captions-text { transition: transform 0.433s cubic-bezier(0, 0, 0.2, 1), -webkit-transform 0.433s cubic-bezier(0, 0, 0.2, 1); }
```

(aparece duas vezes no varrimento da CSSOM; o varrimento visita regras aninhadas, não é duas folhas
distintas — não instrumentei a contagem de folhas, `[INFERENCE]` sobre a duplicação.)

## 3. O braço que NÃO mediu: cue real, entrada, saída, seek/pausa/velocidade — `UNMEASURED`

**Facto medido:** nesta máquina/sessão, o `timedtext` do player responde **HTTP 200 com corpo de
0 bytes**. Sem cue, não há `.caption-window` real, não há linha que sobe, não há `transitionend` de
uma cue real.

Evidência, na ordem em que foi colhida:

1. `Network.enable` + `Page.navigate` para `watch?v=WdaHAGRBB6s` + play + `setOption('captions','track',{languageCode:'en'})`:
   dois `Network.responseReceived` de `https://www.youtube.com/api/timedtext?...&kind=asr&lang=en...`,
   ambos `status 200`, `mimeType text/html`; `Network.getResponseBody` devolveu `body len: 0` nos dois.
2. `fetch(t.baseUrl + '&fmt=json3')` dentro da página → `status 200`, `len 0`.
3. Quatro endpoints públicos (`api/timedtext` com e sem assinatura, `video.google.com/timedtext`) →
   `200`, `0 bytes`, em IPv4 e IPv6 (curl `-4` e `-6`).
4. Overrides aplicados e verificados, e o resultado não mudou:
   - `Emulation.setUserAgentOverride` → `navigator.userAgent` passou de `HeadlessChrome/156.0.0.0`
     para `Chrome/156.0.0.0` (metadata `Google Chrome 156`, `Win32`);
   - `Page.addScriptToEvaluateOnNewDocument` (depois de `Page.enable`) →
     `navigator.webdriver === false` (verificado `false` na página).
   Mesmo assim, `timedtext` continuou `0 bytes` e o contentor de legenda continuou com
   `children.length === 0` durante 12 s de reprodução (amostras de 250 ms, vídeo de 0,19 s a 12,18 s).
5. Duas cue-tentativas com faixa `manual` (TED `iG9CE55wbtY`) deram o mesmo `0 bytes`.
6. Hipótese refutada por medição: **não é UA nem `webdriver`** — os dois overrides acima não mudaram nada.
   A causa próxima fica `UNMEASURED` (provável PO token/BotGuard a recusar a assinatura em headless,
   `[INFERENCE]` — não instrumentei o `pot`).

Consequência para as 6 perguntas do brief original:

| # | pergunta | estado |
|---|---|---|
| 1 | quantos px a linha anterior sobe e em quantos ms | **UNMEASURED** — sem cue real. O código do player calcula `B = T2 - altura_total` (uma altura de linha); `ms` = **433** (medido §1) |
| 2 | a curva | **MEDIDO**: `cubic-bezier(0, 0, 0.2, 1)`, fit 1,7 % máx / 0,5 % médio; linear refutado (36,1 % / 24,2 %) |
| 3 | a linha que sai desvanece | **MEDIDO no computado**: a transição só lista `transform`; `opacity:1`, `filter:none` na janela, no texto e na linha. Não há transição de opacidade → **sem fade**. O fade visual numa cue real fica `UNMEASURED` |
| 4 | a linha nova entra com transform/opacity ou aparece pronta | **MEDIDO no computado**: `.caption-visual-line` tem `transitionDuration: 0s`; só o `.captions-text` (o stack) anima `transform` — a “entrada” é o stack a subir, não uma animação da linha. Cue real `UNMEASURED` |
| 5 | revelação por palavra ou por linha | **UNMEASURED** — sem cue. O código do player cria cue por `tStartMs + tOffsetMs` (prior #6), não medido aqui |
| 6 | seek, pausa, `playbackRate` 2 e 0,5 | **UNMEASURED** — sem cue; nenhum vídeo/decisão dependente disso foi inventado |

## 4. Amostras cruas da transição (no-preference, 433 ms)

Elemento sintético com as classes reais, deslocamento `-13 px` (a altura de linha que aquele
elemento tinha com o `font-size: 11px` herdado; **não** é a altura de linha de uma cue real — ver §3).
`t` em ms desde o primeiro frame com `transform` diferente de `none`; `p` = `-translateY / 13`.

```
t(ms)   p      t(ms)   p      t(ms)   p      t(ms)   p
  0.2  0.000    81.1  0.488   164.5  0.741   247.7  0.890
 18.5  0.170   102.3  0.565   185.4  0.786   268.5  0.915
 39.3  0.296   122.7  0.631   206.0  0.825   289.5  0.937
 60.4  0.400   143.5  0.689   226.8  0.860   310.1  0.955
                                              330.8  0.970
                                              352.1  0.982
                                              372.7  0.990
                                              393.5  0.996
                                              414.4  0.999
                                              434.9  1.000
```

`transitionend`: `transform` aos **430,9 ms**; valor computado dentro de 0,01 px aos **414,4 ms**
(n=179 amostras). Repetições: 434,6 ms e 440,6 ms — todas dentro de um frame de 433 ms.

Fit (21 pontos com `0 < t < 433`):

```
bezier  max_err 0.0168  mean_err 0.0051
linear  max_err 0.3611  mean_err 0.2422
```

## 5. O que isto muda (leitura, não edição)

- O valor **0,433 s** e a curva **`cubic-bezier(0, 0, 0.2, 1)`** estão confirmados por
  `getComputedStyle` na folha viva de hoje — a folha servida continua a bater com o código do
  player (`433` no `transitionend` de fallback).
- A implementação do repo usa `ROLL_S`/`_bezier_y` com esses números; este recibo **não** a altera.
- O `EXIT_S = 0.45` da spec interna é um bracket de UIA (0,424–0,552 s); o computado de hoje é
  **0,433**, não 0,450. Quem quiser 1:1 deve preferir 433 ms; a diferença de 17 ms é 4 % e não foi
  medida como perceptível — `[INFERENCE]`, não medi percepção.
- Sem fade: a transição computada é só `transform`. Nenhuma regra de `opacity`/`filter` participa.

## 6. Repro (comandos, sem janela)

```bash
S=$(agent-browser session id --scope worktree --prefix yt-rollup3)
agent-browser eval "location.href='https://www.youtube.com/watch?v=WdaHAGRBB6s'; 'go'" --session "$S"
agent-browser wait 9000 --session "$S"
# o daemon da sessão expõe CDP:
agent-browser get cdp-url --session "$S"      # ws://127.0.0.1:<port>/devtools/browser/…
```

No CDP, os passos exactos:

```text
Page.enable
Page.addScriptToEvaluateOnNewDocument {source: "Object.defineProperty(Object.getPrototypeOf(navigator),'webdriver',{get:()=>false,configurable:true})"}
Emulation.setUserAgentOverride {userAgent:"…Chrome/156.0.0.0 Safari/537.36", …}
Emulation.setEmulatedMedia {features:[{name:"prefers-reduced-motion",value:"no-preference"}]}
Runtime.evaluate: <criar a cadeia de classes dentro de #ytp-caption-window-container>
Runtime.evaluate: getComputedStyle(txt).transitionProperty / transitionDuration / transitionTimingFunction
Runtime.evaluate: rAF loop a ler getComputedStyle(txt).transform + transitionend
```

Para o braço UNMEASURED (prova do bloqueio):

```text
Network.enable
Page.navigate {url:"https://www.youtube.com/watch?v=WdaHAGRBB6s"}
Runtime.evaluate: video.play(); player.setOption('captions','track',{languageCode:'en'})
# Network.responseReceived (2x timedtext) -> Network.getResponseBody -> len 0
```

Fricção de instrumento observada (registada, não corrigida aqui):
`agent-browser open "https://www.youtube.com/watch?v=…"` **não retorna** (>120 s, duas sessões);
`agent-browser open "https://example.com"` retorna em ~1 s. O caminho que funcionou foi
`eval("location.href=…")` + `wait`. Também: `Page.addScriptToEvaluateOnNewDocument` só passou a
correr depois de `Page.enable` (antes disso, `window.__initTest` ficava `undefined`).

## CACHE/PRICE

```
## CACHE/PRICE
- task/agent: RollupMeasureLive2
- source: G:\env-data\superharness\usage_telemetry\model-usage.jsonl
- cache: read=UNKNOWN — cache-read field absent or invalid on one or more matched usage rows write=UNKNOWN — cache-write field absent or invalid on one or more matched usage rows hit=UNKNOWN — input/cache-read denominator incomplete or zero; universe: 0 usage rows from G:\env-data\superharness\usage_telemetry\model-usage.jsonl; instrument: scripts/cache-task-report.sh
- price: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available; UNKNOWN — no usage rows matched, so there is no price to partition
- when-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['RollupMeasureLive2']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- where-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['RollupMeasureLive2']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- report generated_at: 2026-11-08T05:19:39.058233+00:00
- usage rows: 0
- model + route: UNKNOWN — no provider usage rows matched
- input tokens: UNKNOWN — input field absent or invalid on one or more matched usage rows
- output tokens: UNKNOWN — output field absent or invalid on one or more matched usage rows
- cache-read tokens: UNKNOWN — cache-read field absent or invalid on one or more matched usage rows
- cache-write tokens: UNKNOWN — cache-write field absent or invalid on one or more matched usage rows
- hit ratio: UNKNOWN — input/cache-read denominator incomplete or zero
- cost: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available
- price partition: UNKNOWN — no usage rows matched, so there is no price to partition
- prefix breaks: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['RollupMeasureLive2']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- WHEN / WHERE failed:
UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['RollupMeasureLive2']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

---

## SELF-AUDIT

- **protocolos em falta** — devia ter declarado o limite do `agent-browser` mais cedo: gastei
  ~15 min a tentar `open <youtube>` e a diagnosticar o `timedtext` antes de perguntar/limitar.
  O que faria diferente: fixar um orçamento de 5 min por via e escrever o `UNMEASURED` no fim dele.
- **verificacao adicional** — teria subido a confiança uma leitura do `transition` INLINE do
  `.captions-text` numa cue real; custa uma via que sirva `timedtext` (não obtida aqui).
- **checkboxes novas** — antes de aceitar qualquer medição de legenda: exigir
  `Network.getResponseBody(timedtext).length > 0`; hoje é 0 e a medição a jusante é vazia.
- **review por outro subagente** — `sim-com-escopo` — revisão do §2.1 (sintético vs cue real) e do
  fit da curva; o resto é leitura directa de valores computados.
- **gate-doubt**:
  - `verde-de-verdade:` o “verde” do §1 é real para a folha viva (valores verbatim + `transitionend`
    medido 430,9 ms + fit 1,7 %), mas é **vazio como prova de cue real**: o elemento é sintético e o
    braço de cue verdadeira nunca correu porque o `timedtext` devolveu 0 bytes. Nomeio a corrida:
    `Runtime.evaluate` pós-`Page.enable`, `prefers-reduced-motion: no-preference`.
  - `falta-no-gate:` nenhum passo exige que a cue exista antes de declarar “não há roll-up”; uma
    mudança futura pode passar por `children.length === 0` e chamar-lhe “sem animação”.
  - `gate-melhor:` pré-condição mecânica — `Network.getResponseBody` do `timedtext` com `len > 0`
    antes de qualquer leitura de `.caption-visual-line`; o input de hoje (0 bytes) tem de a deixar RED.
- **confianca** — `alta` para `0.433s` / `cubic-bezier(0, 0, 0.2, 1)` na folha viva;
  `media` para a extrapolação à cue real (inline do player não observado).
- **nao verificado** — cue real (px de subida, entrada da linha nova, fade de saída, seek, pausa,
  `playbackRate` 2 e 0,5, revelação por palavra); contagem exacta de folhas que duplicam a regra;
  causa próxima do `timedtext` 0 bytes (PO token/BotGuard — `[INFERENCE]`).
