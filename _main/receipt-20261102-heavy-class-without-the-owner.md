# Receipt — the heavy class, run without the owner: 8 of 12 measured, 2 defects, 1 refusal

**Data:** 2026-11-02, 12:40–13:5x. **Árvore:** `H:/sotto`, `feat/speaker-attribution-20261019`.
**Pedido do dono:** *"do the rest"* (fechar os 12 passos que a bateria publicou como SKIPPED) e, ao
mesmo tempo, *"testa o sotto SEM eu ouvir os audios de teste"*.

## 1. O que se mediu, e com que instrumento

| passo (classe heavy) | instrumento | veredicto desta ronda |
|---|---|---|
| `panel-exit3` (`--unit --neg-arm`) | `_main/panel-exit3-oracle.py` | **PASS**, `failures: []` |
| `altc-first-caption` | `_main/altc-first-caption-oracle.py` | **GREEN**, `sessoes=1 fora_do_orcamento=0` — press `12:50:24.118 -> HOTKEY_TOGGLE 12:50:24.119` (**1 ms**), press `12:50:24.519 -> HOTKEY_LIVE_STEP 12:50:24.522` (**3 ms**), orçamento 1500 ms |
| `strip-stats-wave` | `_main/_strip-stats-probe.py` | **GREEN** — `level=live bars=10 emits.stats=154 pushes=1`, `ready_s(fed=2.065,unfed=1.9)` |
| `strip-stats-log-budget` | `_main/_strip-stats-log-probe.py` | **CONTROL PASS**, `ratio=364.4x` (443 linhas/amostra vs 1 agregada) |
| `strip-geometry-restore` | `_main/_strip-restore-probe.py` | **GREEN**, 6 checks, `file_restored=true`, rc=0 (o instrumento é MUDO: só o exit code fala — 0 = PASS, 3 = RED) |
| `strip-surface-runtime` | `_main/_strip-surface-probe.py` | **RED → corrigido → GREEN 26/26** (§2) |
| `shell-relaunch` | `_main/shell-relaunch-oracle.py` | **GREEN**, `arms=12 pass=12 fail=0`; o `--selftest` usa um STUB no disparo (não lança a app) |
| `paint-live-show` | `_main/paint-live-show-oracle.py` | **SKIPPED** — `shows=0`: o dono não deu um Alt+C na sessão viva. Sem show não há o que julgar, e o passo diz isso em vez de fingir verde |

**Não corridos, por decisão** (§3): `panel-paint-first-measure` (abre janela VISÍVEL de propósito),
`device-silence` + `red-as-expected-device-silence` (renderiza áudio audível), `mute-audio` (mexe no
mute do sistema dele).

## 2. DEFEITO 1 — a edição da faixa escondia a própria faixa (medido 12:55:09, corrigido 13:03:33)

O `_strip-surface-probe` deu **RED** com **um** check falhado: `D nothing closed the band once edit
mode was ON`. A cadeia, lida do log do próprio shell:

```
12:55:09.307  PANEL_SHOWN reason=edit-tray ... visible=true paint_ack=true wait_ms=156.0
12:55:09.307  OUTSIDE_CLICK source=foreground point=(758,478) decision=outside closed=true
12:55:09.311  PANEL_HIDDEN reason=click-outside visible=false
12:55:09.311  PANEL_EDIT_MODE on=true reason=tray ...     <- 4 ms TARDE DEMAIS
```

**Causa:** `set_edit_mode()` armava o guarda **depois** de `show_panel()`, e `show_panel()` custa o
paint ack (156 ms medidos). Nessa janela a faixa estava visível e o watcher, na sua própria thread,
ainda lia `edit_mode=false` — o pedido "editar a faixa" escondia a faixa.
**Correcção:** `app/webview/sotto_webview.py`, o guarda (`click_watcher.edit_mode = True`) passa a ser
armado **antes** do show. O comentário nomeia o número e a linha do log que o provam.
**Prova depois da correcção:** mesmo instrumento, **GREEN 26/26**, e o log do braço D mostra
`OUTSIDE_CLICK source=probe-edit-outside ... decision=edit-mode closed=false`.

## 3. DEFEITO 2 — o ARM3 do `device-silence` tinha um orçamento menor do que o carregamento do modelo

Primeira ronda: `verdict=captions-zero`, `blocks=56`, `peak=0.274963`, `speech_blocks=6`,
`captions=0`. Não era a transcrição que falhava: **`load_s=38.96`** e `--max-seconds` é tempo de
PAREDE desde o arranque do processo (`t_start = time.time()` no topo de `main`, antes do load). Uma
janela de 20 s é engolida inteira pelo carregamento.

**Correcção (instrumento, não produto):** `_main/device-silence-oracle.py` ganhou `load_seconds()`,
que lê o `load_s` do **próprio registo da corrida**, e o ARM3 repete **uma única vez** com
`load_s + max(secs,20) + 10` segundos — e **só** quando o registo prova que o load comeu a janela
(`captions=0`, `blocks>0`, `load_s >= janela`). Qualquer outra forma é julgada tal como cai, por isso
uma regressão real continua a dar RED. Medido na 2ª ronda: `load_s=23.09` → `window_s=54`, e o
orçamento aparece no veredicto como `retry`.

**Estado:** o ARM3 foi **interrompido por ordem do dono** e não se voltou a correr — ver §4.

## 4. A RECUSA, e o instrumento que nasceu dela

Ordem do dono, verbatim: *"testa o sotto sem eu ouvir os audios de teste"* / *"PRA TU MATAR ESSE
SCRIPT ... QUE TOCA UM AUDIO Q EU ESCUTO"* / *"tu literalmente mutou o meu sistema inves de ser o
audio que tu tava tocando"*.

**O facto medido que explica tudo:** `_main/mute-audio.py --mute` muta **um** endpoint — o papel de
saída *default*. O áudio do teste não passa por lá: o `feed_cable` renderiza para
`CABLE Input (VB-Audio Virtual Cable)` e o VoiceMeeter encaminha-o para uma saída de hardware que
**não** é a default. Mutar a default não prova nada sobre o que o dono ouve; mutar **todos** os
endpoints cala a máquina dele inteira, que é pior e foi o que aconteceu (desfeito: 21 endpoints
repostos, `muted=false`, `scalar=1.0`).

**O que ficou no repo:** `_main/mute-audio.py --status-all` — censo **read-only** que imprime
`name/muted/scalar/inactive` de cada endpoint (41 nesta máquina). Um passo que renderiza áudio tem de
nomear o endpoint em que renderiza e mostrá-lo mudo **aqui**; uma lane não volta a tocar no mute do
sistema.

**Regra operacional que passa a valer nesta árvore:** instrumentos que RENDERIZAM áudio (o ARM3 do
`device-silence`, o `feed_cable`) não correm numa lane desta máquina — não são silenciáveis sem calar
o dono ou sem lhe tocar no áudio. Os que só LÊEM (log, DOM, unit arms, e os que importam o shell sem
abrir dispositivo) correm.

## 5. O que continua por medir, e por quem

| passo | porque não correu aqui | o que o fecha |
|---|---|---|
| `panel-paint-first-measure` | abre uma janela **visível** de propósito (mede o primeiro frame no ecrã) — `SOTTO_NEVER_ON_OWNER_SCREEN` | o dono abre a app, ou autoriza explicitamente uma janela nesta sessão |
| `device-silence` (ARM3) · `red-as-expected-device-silence` | renderiza áudio que ele ouve (§4) | uma sessão em que ele autorize o áudio, ou um endpoint que não chegue a nenhuma saída de hardware |
| `mute-audio` (21 arms) | mexe no mute do sistema dele | idem |
| `paint-live-show` | exige um Alt+C na instância viva | ele dá um Alt+C numa sessão com a app aberta |

**Nada disto é um verde.** São quatro janelas fechadas por regra, e ficam nomeadas.

## 6. Custo

`_strip-*` 275,95 s (4 sondas) · `_strip-surface` 199,31 s (depois da cura) e ~5 min antes ·
`device-silence` 310,99 s (1ª), 197,00 s + 186,97 s (interrompida) · `shell-relaunch` 4,22 s ·
`altc-first-caption` ~1 s · `panel-exit3 --unit --neg-arm` ~1 s.

## 7. O DONO AUTORIZOU A JANELA: `panel-paint-first-measure` medido (14:0x)

*"pode fazer isso ai. ta permitido. só agora. vai. tudo."* — a janela visível passou a estar
autorizada NESTA sessão, e o censo correu de verdade.

**Primeira corrida: `ok=false`.** `app[cured]` e `app[uncured]` publicaram `no-show-measured`, e o
controlo também falhou. Lido do log da instância privada: `PANEL_SHOW_REFUSED reason=not-asked`
(duas vezes, o `_gate_form_show` a fazer o seu trabalho), `UI_THREAD_STALL begin-invoke not run in
0.25s fn=_run`, `PAINT_ACK ack=false wait_ms=750.0 why=ui-thread-busy`, e por fim
`UI_WATCHDOG_EXIT code=9 -- a UI estava presa`. A página ainda estava a carregar quando o censo
pediu o primeiro show.

**Segunda corrida: `ok=false` outra vez, mas por outra razão** — `app[uncured] reported
blank_frames=0 on EVERY show`. O braço `uncured` (shell do `git show HEAD`, cópia fria) levou
**158,7 s** até ao primeiro show; com `--exit-after 170` a instância saiu a meio do driver e só
1 de 3 shows entrou. O controlo perdeu a força sem nada estar errado na app.

**Correcção do instrumento:** `--exit-after` 170 → **360 s**, `--seconds` 200 → **400 s**, com a
medição escrita no help ("a instância saiu a meio do driver, ficou 1 show de 3").

**Corrida boa (`ok=true`, `fails=[]`):**

| braço | shows | `blank_frames` | `first_content_ms` | `first_std` |
|---|---|---|---|---|
| `cured` (worktree) | 3 | **[0, 0, 0]** | **[0.0, 0.0, 0.0]** | 31.25 / 16.59 / 31.25 |
| `uncured` (HEAD) | 3 | **[17, 0, 0]** | **[308.3, 0.0, 0.0]** | 0.0 (chapado) na 1ª |
| controlo `blank_first` | — | 54 | 928.7 | 0.0 |
| controlo `content_first` | — | 0 | 0.0 | 71.2 |

O defeito do dono está reproduzido no controlo (17 frames chapadas, 308 ms) e a cura está provada
no worktree (**zero** frames em branco, conteúdo desde a primeira frame). `--judge` REJULGA a
leitura e dá PASS; `--neg-arm` apanha as **quatro** mutações (`cured-show-1-blank`,
`cured-never-content`, `classifier-blind-on-uncured`, `control-blank-first-silent`).

## 8. DEFEITO 3 — `--show` mostrava e escondia a si própria em 12 ms (corrigido)

Instância lançada pela via da casa (`launch-as-token` de um `explorer.exe`, porque o lançamento
directo desta pane dá o já documentado `WEBVIEW2_INIT_FAILED 0x80010108`):

```
14:09:46.724  PANEL_SHOWN reason=startup ... paint_ack=true wait_ms=16.0
14:09:46.736  PANEL_HIDDEN reason=click-outside visible=false      <- 12 ms
```

**Causa:** o vigia do outside-click só reage a uma MUDANÇA de foreground, e o arranque produz uma
(consola → form → app). Armado no instante do show, o primeiro tick dele já via "fora".
**Correcção:** o show é dono dos seus primeiros **250 ms** (`OutsideClickWatcher._armed_at`,
escrito em `show_panel`; o guarda só se aplica a `source='foreground'`, portanto um clique REAL do
dono — `WM_LBUTTONDOWN` do hook — continua a fechar). **Prova:** instância nova, `PANEL_SHOWN
... wait_ms=0.0` **sem** `PANEL_HIDDEN` depois, e o `paint-live-show` passou de SKIPPED a
**gate** (`gate=106`, `skipped=11`).

**Observado, e registado como `[INFERENCE]`:** as DUAS instâncias que se esconderam 12 ms depois do
show acabaram em `UI_WATCHDOG_EXIT code=9` (UI presa, `evaluate_js` → `semaphore.acquire`); a
instância corrigida correu sem um único `UI_WATCHDOG_STRIKE`/`UI_HUNG_FRAME` e transcreveu
(`CAPTION_APPLIED ... "Do that. >> Yeah, well sometimes you need to do it."`). A ligação causal
entre o esconder-se e a prisão da UI **não** foi provada — só a correlação 2/2 contra 0/1.

## 9. DEFEITO 4 (do instrumento) — o braço negativo mutava a linha errada

`red-as-expected-paint-live-show` saiu **rc=2**: `cases=3 caught=2`, com `show-sem-ack` NOT-CAUGHT.
A mutação era `replace('paint_ack=true', 'paint_ack=false', 1)` — a PRIMEIRA ocorrência do log, que
agora pertence a uma sessão anterior; o julgador só lê a sessão viva, logo a mutação não movia o
artefacto do veredicto. Passou a `_last_ack_off` (a última ocorrência) — `cases=3 caught=3`,
rc=1 como o `:expectred` exige. A lição já estava escrita ao lado, no caso `show-lento`.

## 10. Estado final desta ronda

`failed: -none-`, **BATTERY-VERDICT: GREEN WITH 11 SKIPPED** (as 11 são a classe heavy),
`gate=106`, `expect-red=62`, `missing=0`. `code-health` PASS com `sotto_webview.py` em
**799 587 B** (baseline 799 682). Nenhuma instância da app ficou a deter `Local\SottoShell`
(pid 21828 fechado por `taskkill` elevado, censo = 0).
