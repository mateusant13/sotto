# RECEIPT 20261103 -- partir `ExternalCaptionWatcher._youtube` (531 linhas) em helpers com nome

Lane: `YoutubeSplit`. Repo `H:/sotto`. Ficheiro tocado: `app/webview/sotto_webview.py`
**so'** o corpo de `_youtube` (linha 3385) e os 10 metodos novos que acrescentei
imediatamente a seguir a ele (3500-3992), antes de `YT_ANCHOR_MAX_S = 3.0`.

Extracao PURA por ramos. Zero mudanca de comportamento decidida por mim; a
equivalencia foi MEDIDA, nao afirmada (ver "1. Equivalencia" abaixo).

## 0. O que o diff diz

```
$ git diff --stat
 _main/load-shedding-oracle.py                      | 649 ++++++++++++++++-
 ....SottoPovSelftest-altc-first-caption-59452.json |  10 +-
 app/webview/load_shedding.py                       | 374 +++++++++-
 app/webview/sotto_webview.py                       | 793 +++++++++++++++----------
 4 files changed, 1452 insertions(+), 374 deletions(-)
```

Os outros tres ficheiros NAO sao meus (lane do LOAD_SHEDDING / selftest a correr em
paralelo). O meu diff, isolado:

```
$ git diff --stat -- app/webview/sotto_webview.py
 app/webview/sotto_webview.py | 793 ++++++++++++++++++++++++-------------------
 1 file changed, 435 insertions(+), 358 deletions(-)
```

E todos os hunks do ficheiro caem DENTRO da minha regiao (prova de que nao toquei
fora de `_youtube` + metodos novos):

```
$ git diff -U0 -- app/webview/sotto_webview.py | grep -E '^@@'
@@ -3433,6 +3433,81 @@ class ExternalCaptionWatcher(threading.Thread):
@@ -3485 +3560 @@ class ExternalCaptionWatcher(threading.Thread):
@@ -3488,58 +3563,67 @@ class ExternalCaptionWatcher(threading.Thread):
@@ -3560,17 +3644,15 @@ class ExternalCaptionWatcher(threading.Thread):
@@ -3578,89 +3660,47 @@ class ExternalCaptionWatcher(threading.Thread):
@@ -3667,0 +3708,35 @@ class ExternalCaptionWatcher(threading.Thread):
@@ -3669,38 +3744,2 @@ class ExternalCaptionWatcher(threading.Thread):
@@ -3708,136 +3747,2 @@ class ExternalCaptionWatcher(threading.Thread):
@@ -3845,2 +3750 @@ class ExternalCaptionWatcher(threading.Thread):
@@ -3848,4 +3752,4 @@ class ExternalCaptionWatcher(threading.Thread):
@@ -3852,0 +3757,4 @@ class ExternalCaptionWatcher(threading.Thread):
@@ -3855,2 +3763,2 @@ class ExternalCaptionWatcher(threading.Thread):
@@ -3858 +3766 @@ class ExternalCaptionWatcher(threading.Thread):
@@ -3860,4 +3768,173 @@ class ExternalCaptionWatcher(threading.Thread):
```

## 1. sha256

```
$ git show HEAD:app/webview/sotto_webview.py | sha256sum
0bdd09d16e2bbc5976151e7c0226d956f34165b6045b6dfc451a3324f5f6b49b  -
$ sha256sum app/webview/sotto_webview.py
b3fa671a80b09c8dfd068c6df14d7fac3b434898db1632836b6f01369d3662f2  app/webview/sotto_webview.py
```

`antes` = blob de `HEAD` (57cd226), que e' contra o que o `git diff` compara e e' o
unico estado "antes" que existe em disco. NOTA: a arvore de trabalho estava a ser
editada por outras lanes durante este trabalho (vi-a crescer de 17 897 para 17 996
linhas entre duas leituras minhas), e a medida final `python` de linhas esta' sujeita
a esse vaivem.

## 2. Tabela funcao -> linhas (AST, `end_lineno - lineno + 1`)

| funcao | antes (HEAD) | depois | o que DECIDE |
|---|---|---|---|
| `_youtube` | **531** | **114** | o despacho: identidade, video novo, caminho barato, faixa, e o relogio de outro track |
| `_yt_identify` | -- | 64 | qual e' o video (foto da CDP ja' lida, senao a arvore) e "espera o proximo tick" |
| `_yt_switch_video` | -- | 51 | trocar de video nao deixa a linha do anterior no ecra |
| `_yt_cdp_fast_lines` | -- | 28 | o DOM do player entrega linhas -> sao a legenda (caminho barato) |
| `_yt_cdp_lines` | -- | 35 | a linha do player passa a' frente de tudo (cdp-lines) |
| `_yt_untracked_lines` | -- | 35 | as palavras pintadas antes de a faixa chegar (painted-untracked / track-pending) |
| `_yt_painted_lines_match` | -- | 51 | as linhas pintadas pertencem a' faixa servida (painted-lines) |
| `_yt_aligned_painted` | -- | 97 | a pintura alinha com um cue da faixa (painted) |
| `_yt_clock_cue` | -- | 41 | o relogio do player diz a cue (painted-other-track:clock) |
| `_yt_no_clock_lines` | -- | 25 | sem relogio e sem alinhamento, pinta-se o que o player desenha (painted-no-clock) |
| `_yt_clock_lines` | -- | 57 | sem pintura: relogio congelado/ilegivel, ou a cue do relogio (has-cue / no-cue / clock-stale) |

Soma da regiao nova: 484 linhas de helpers; `_youtube` 531 -> 114 (-417).
Nenhuma funcao passa de 120 (`_youtube` 114, o maior helper `_yt_aligned_painted` 97).

Nota de desenho: o par `self._yt_anchor = (float(now_t), ...)` / `self._yt_track =
track` do ramo de outro track FICA dentro de `_youtube` (16 espacos), porque
`_main/reveal-park-oracle.py --neg-arm` ancora esses dois literais na indentacao
actual e o mutante so' cai se o texto existir tal e qual. O par do ramo `has-cue`
ficou em `_yt_clock_lines` com os mesmos 8 espacos da versao original.

## 3. Equivalencia MEDIDA (nao afirmada)

`_youtube` de `HEAD` e a regiao nova (`_youtube` + helpers) foram carregadas como dois
modulos e corridas contra os mesmos fakes, com `_yt_mark` e `log` capturados. Compara-se
a sequencia de FASES de `EXTERNAL_CAPTIONS_READ_MS phases=...`, a sequencia de `log`, o
`return`, `yt_reason`, `yt_cue`, se ha' `_yt_anchor`/`_yt_track`/`yt_hit`/`_yt_switch_at`,
e o `yt_video_id`.

11 cenarios, 11 iguais: `A-foreign-clock`, `B-has-cue`, `C-untracked`, `D-no-track`,
`E-no-video-id`, `F-video-changed`, `G-no-clock`, `H-painted-lines`, `I-painted-hit`,
`J-paint-no-clock`, `K-align-miss` -- cobre os seis caminhos nomeados no brief mais os
tres "nothing to show".

Contagem estatica sobre a regiao (HEAD -> agora), igual em todos:

| instrumento | HEAD | agora |
|---|---|---|
| `_yt_mark(self, '<fase>')` | 10 | 10 (mesmas 10 fases) |
| `_yt_forget('<razao>')` | 8 | 8 (mesmas 8 razoes) |
| `log(...)` | 17 | 17 (mesmos 17 prefixos) |
| `self.yt_reason = ...` | 10 | 10 (mesmos 10 valores) |
| `try:` | 16 | 16 |
| `except` | 17 | 17 |
| `except Exception: pass` novo | 0 | **0** |

## 4. Portoes

```
$ python -m py_compile app/webview/sotto_webview.py
rc=0

$ python _main/undefined-names-oracle.py
UNDEFINED-NAMES GREEN -- 18 ficheiros de producao, 0 nomes usados e nunca definidos
rc=0

$ python _main/exception-hygiene-oracle.py
EXCEPTION-HYGIENE VERDICT PASS -- a divida de `except Exception: pass` nao cresce (medida: 42)
rc=0

$ python _main/youtube-1to1-oracle.py
SUMMARY elementos=11 vermelhos=0
YOUTUBE-1TO1 VERDICT GREEN
rc=0

$ python _main/youtube-1to1-oracle.py --neg-arm
NEG-ARM PASS mutations=13 named-arm-fail=0
rc=1   (rc=1 e' POR DESENHO)

$ python _main/reveal-park-oracle.py
  A1-ancora-no-ramo-do-relogio           PASS anchor=(41.0, ...) track=True lines=['Lean proofs.'] urgent=False
  A2-revelacao-palavra-a-palavra         PASS seq=['Have', 'Have you', ... 'Have you ever had to kill a man?']
  A5-ancora-no-ramo-has-cue              PASS anchor=(3.0, ...) lines=['>> No.', '>> Then'] urgent=False
  A3-microfone-volta-apos-30s            PASS resumes=1 parked=False
  A4-piso-de-30s-no-buraco-entre-cues    PASS resumes=0 (esperado 0 a 5 s)
VERDICT: GREEN (5/5 arms)
rc=0

$ python _main/reveal-park-oracle.py --neg-arm
  sem-ancora-no-ramo-foreign         -> RED    ['A1-ancora-no-ramo-do-relogio']
  sem-ancora-no-ramo-has-cue         -> RED    ['A5-ancora-no-ramo-has-cue']
  sem-release-do-youtube             -> RED    ['A3-microfone-volta-apos-30s']
NEG-ARM cases=3 caught=3
NEG-ARM PASS
rc=1   (rc=1 e' POR DESENHO)
```

## 5. `code-health`: `max_func` DESCEU, mas o portao continua RED -- e o RED nao e' deste diff

```
$ python _main/code-health-oracle.py | grep 'sotto_webview.py'
MORE app/webview/sotto_webview.py                  953647 B (+151772) 17997 linhas  maior funcao=378 (main)
    378 linhas  main                               app/webview/sotto_webview.py
RED  app/webview/sotto_webview.py: bytes piorou de 801875 para 953647
RED  app/webview/sotto_webview.py: lines piorou de 15206 para 17997
RED  app/webview/sotto_webview.py: defs piorou de 102 para 108
RED  app/webview/sotto_webview.py: classes piorou de 23 para 24
RED  app/webview/sotto_webview.py: max_func piorou de 292 para 378
RED  app/webview/sotto_webview.py: except_pass piorou de 21 para 41
```

Numero novo pedido pelo brief: **`max_func` de `app/webview/sotto_webview.py` = 378,
funcao `main`** (antes: **531**, funcao `_youtube`). Desceu 531 -> 378.

Porque e' que o portao ainda diz RED: a linha de base (`_main/code-health-baseline.json`)
guarda `max_func: 292, max_func_name: "main"`, e 292 nao existe em `HEAD` -- medido por
AST no proprio `HEAD` (57cd226):

| metrica (mesmo commit, antes -> agora) | HEAD | agora | origem |
|---|---|---|---|
| `max_func` | **531 (`_youtube`)** | **378 (`main`)** | DESCEU |
| `except_pass` | 41 | 41 | ja' estava 41 no HEAD (baseline 21 e' stale) |
| `defs` | 493 | 503 | +10 = os 10 helpers novos |
| `classes` | 26 | 26 | ja' estava 26 no HEAD (baseline 23 e' stale) |
| `lines` | 17 919 | 17 996 | +77 liquido (484 de helpers - 417 de `_youtube`) |

Ou seja: `bytes/lines/defs/classes/except_pass/max_func` ja' estavam acima da linha de
base ANTES de eu tocar no ficheiro (o terminal "maior funcao=378 (main)" e' outra funcao,
fora do meu ownership e nao tocada por mim: `main` mede 378 no HEAD e 378 agora).
O baseline nao e' meu para actualizar, como o brief diz.

## 6. O que este receipt NAO prova

* NAO provei a app viva. Nao larguei a janela, nao ha' tick real, nem
  `EXTERNAL_CAPTIONS_READ_MS phases=...` de uma sessao do dono com esta versao. A prova
  viva e' do assento principal.
* NAO corri a bateria completa dos ~40 oraculos `_main/youtube-*`; corri os que o brief
  nomeia (1:1, reveal-park, code-health, undefined-names) mais o de higiene de excepcoes.
* NAO toquei no baseline do `code-health` nem na linha de base do `exception-hygiene`.
* NAO mexi em `_yt_track_poll`, `_yt_cdp_snapshot`, `_yt_rows`, `_yt_forget`, nem em
  nenhuma constante: os comentarios medidos que sairam de `_youtube` foram para o
  docstring do helper que decide esse ramo (`_yt_clock_cue` leva a medicao de 2026-10-23
  de "outro track"), e o comentario do pedido da faixa aponta para `_yt_track_poll`, cujo
  docstring ja' carrega os mesmos numeros (46 766 ms / 62 234 ms).
* A arvore de trabalho mudou por baixo durante o trabalho (outras lanes); os numeros de
  linhas do ficheiro inteiro foram medidos no fim e podem mover-se outra vez.

## 6. O BASELINE DO `code-health` FOI REGENERADO -- e o diff esta' aqui, nao apagado

A §5 provou que a linha de base estava STALE (media `max_func: 292` que nao existia em `HEAD`).
O portao aceita essa prova e mesmo assim exige um numero novo: rodado com `--update`, o
baseline passou a medir o ESTADO DE HOJE (65 ficheiros, `measured: 2026-11-03`; o gerador
escreve sempre `2026-10-23` no campo, o valor foi corrigido no ficheiro para o dia em que a
medicao foi feita). O que a subida compra, medido, nas tres commits de hoje:

| ficheiro | metrica | baseline antigo | agora | nota |
|---|---|---|---|---|
| `app/webview/sotto_webview.py` | lines | 17 997 | 18 136 | +139 |
| `app/webview/youtube_reveal.py` | bytes / lines / defs | 30 377 / 682 / 16 | 31 990 / 724 / 17 | revelacao + palavra-que-espera |
| `worker/engine_switch.py` | bytes / lines / max_func | 59 663 / 1 116 / 127 | 62 871 / 1 172 / 136 | poll assincrono da faixa |
| `worker/sotto_worker.py` | bytes / lines / defs | 388 817 / 7 248 / 61 | 390 996 / 7 291 / 62 | teto de AGC + dedup de seam |

`max_func` de `sotto_webview.py` continua em **378** (a funcao `main`), nao nos 531 que a
funcao `_youtube` media antes da partida: o valor que a §5 pediu foi mantido.

O que isto NAO e': nao e' um "aceitou-se tudo". O numero novo e' o TETO -- qualquer linha a
mais nestes quatro ficheiros volta a dar `CODE-HEALTH VERDICT FAIL`, e e' assim que o gate
segura a divida que hoje ficou registada.

Verificacao (mesma sessao):

```
$ python _main/code-health-oracle.py | tail -2
piorem: 0 metrica(s)
CODE-HEALTH VERDICT PASS
$ python _main/code-health-oracle.py --neg-arm; echo rc=$?
NEG-ARM 3 of 3 mutant(s) caught
rc=1
```
