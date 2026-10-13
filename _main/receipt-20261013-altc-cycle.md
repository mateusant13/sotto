# RECIBO — Alt+C é um CICLO de três estados, e o relógio acabou (2026-10-13)

**Lead.** Escopo de escrita exercido: `app/webview/sotto_webview.py`,
`_main/strip-geometry-oracle.py`, `_main/strip-first-frame.py`, um harness meu de
sondagem fora do repo (`I:\cc-tmp\altc-cycle.py`) e este recibo. Mais nada.
Sem `git add`, sem `git commit`.

---

## 1. A ordem do dono, verbatim

> *"o alt c ta meio ruim. quando o segundo painel aparece, o proximo alt c deve fazer ele sumir.
> ai, o proximo, independente do tempo, deve fazer o painel de baixo aparecer"*

**O ciclo, exactamente como ele o descreveu:**

| pressão | o que acontece |
|---|---|
| 1.ª | aparece o **painel de baixo** (a strip) |
| 2.ª | aparece o **segundo painel** (o da direita: histórico, pasta, detalhes) |
| 3.ª | o segundo painel **some** |
| 4.ª | o painel de baixo **aparece outra vez** |

e *"independente do tempo"* é a metade que manda apagar o relógio.

---

## 2. O que estava lá, e porque é que ele sentiu isso

`SottoShell.hotkey_pressed` classificava cada pressão com uma **janela de duplo-toque de
1500 ms** (`HOTKEY_DOUBLE_MS`):

* duas pressões DENTRO da janela = um DUPLO → ramo que escolhia o painel da direita;
* duas pressões FORA da janela = duas SIMPLES → `show_strip` / `hide_panel`.

Consequência medida: **quem prime devagar nunca chega ao painel da direita.** Cada pressão
simples só liga/desliga a strip, e o que a PRÓXIMA faz depende de há quanto tempo foi a
anterior — ou seja, o controlo dependia da velocidade da mão do dono. É isso o *"meio ruim"*.

---

## 3. O que passou a ser (o código que está a correr)

`app/webview/sotto_webview.py`, `hotkey_pressed`, **doze linhas e nenhum relógio**:

```python
live = window_visible(self.hwnd) if self.hwnd else False
if not live:
    return self.show_strip('hotkey')
if self.panel_mode == 'side':
    return self.hide_panel('hotkey')
return self.show_side('hotkey')
```

Duas entradas e nada mais: **a janela está à vista?** e **que painel é que está lá**
(`panel_mode`, escrito por `place_panel` em cada show). Apagados com o relógio:

* `HOTKEY_DOUBLE_MS = 1500` (o constante);
* `self._last_hotkey_press` (o carimbo de tempo);
* as três linhas de log `HOTKEY_DOUBLE dt_ms=… window_ms=… mode=side action=…`.

O `--selftest` deixou de derivar a expectativa do intervalo (`want_visible = presses_are_double`)
e passa a afirmar `want_visible = True`: duas pressões a partir de escondido são STRIP e depois
SIDE, e a janela está à vista nas duas — a qualquer velocidade.

---

## 4. MEDIDO — o ciclo, e a prova de que o tempo não decide nada

### 4.1 Em processo (`py -3 I:\cc-tmp\altc-cycle.py`, o módulo real importado, método real chamado)

```
six presses from hidden, immediato : ['strip', 'side', 'hide', 'strip', 'side', 'hide']
six presses from hidden, 1.6s gap  : ['strip', 'side', 'hide', 'strip', 'side', 'hide']
cycle (any timing): True
two back-to-back  : ['strip', 'side']   (want [strip, side])
two 1.6s apart    : ['strip', 'side']   (want [strip, side])
from visible+side : ['hide']            (want [hide])
from visible+strip: ['side']            (want [side])
from hidden       : ['strip']           (want [strip])
```

O `1.6 s` é de propósito **maior** que os 1500 ms da janela apagada: se o relógio ainda
decidisse alguma coisa, as duas corridas de seis pressões tinham de divergir. Não divergem.

### 4.2 O portão — `py -3 _main/strip-geometry-oracle.py`

```
PRISTINE : VERDICT: PASS -- 17 check(s), 0 fail
  ok B1 HIDDEN -> STRIP                          ['strip']
  ok B2 STRIP -> SIDE                            ['side']
  ok B3 SIDE -> HIDDEN                           ['hide']
  ok B4 six presses walk the whole cycle         ['strip','side','hide','strip','side','hide']
  ok B6 the SAME six presses 1.6 s apart are the SAME cycle
  ok B7 the two-press pair is strip-then-SIDE at any speed
NEG-ARM  : VERDICT: PASS -- 23 check(s), 0 fail   (6 mutantes, cada um RED na sua arm)
```

As arms B1-B4 antigas **PINAVAM a dependência do tempo**: punham `_last_hotkey_press` a 0,10 s
e a 5,0 s para escolher o ramo duplo e o simples. Substituídas por um ciclo conduzido pelo
estado, com B6 a ser exactamente o par que prova o *"independente do tempo"*.

O mutante M1 é o defeito que o dono nomeia: `M1 side-unreachable` troca
`return self.show_side('hotkey')` por `return self.hide_panel('hotkey')` — o ciclo colapsa num
liga/desliga da strip, que é o que ele tinha quando premia devagar. Vai RED em B2/B4/B6/B7.

---

## 5. UM BURACO DE PORTÃO QUE APANHEI E FECHEI (e que não era meu)

O `neg-arm` da primeira corrida imprimiu:

```
  FAIL neg-arm M6 dispatch-entry-removed anchor found  -- anchor missing -- the mutant would be INERT
VERDICT: PASS -- 22 check(s), 0 fail          <-- VERDE COM UM CONTROLO MORTO
```

Duas coisas erradas, e a segunda é a grave:

1. **O M6 estava morto.** A âncora dele era `'setStripOffset': self._set_strip_offset,` — a
   forma ANTIGA do mapa de handlers, que a lane do lazy-asset reescreveu em tuplas
   `('shell', '_set_strip_offset')`. E a arm **C4** procurava essa mesma string antiga, que
   sobreviveu… **dentro de um COMENTÁRIO** (`:3841`): o C4 passava a medir nada, e o M6 não
   tinha âncora nenhuma. Dois instrumentos inertes a fingir de controlo.
2. **O veredicto contava só as linhas `goes RED`**, portanto a linha `anchor missing -- the
   mutant would be INERT` era impressa e ignorada. Um gate que diz "controlo morto" no
   output e VERDE no veredicto é o modo de falha que este repo já apanhou várias vezes.

**Corrigido, os dois:**

* `C4` re-baselinado para a rota REAL — `"'setStripOffset': ('shell', '_set_strip_offset')"`
  e o gémeo `sotto:setStripOffset`, os dois com receptor de shell;
* `M6` renomeado para `dispatch-entry-renamed`, com a âncora viva;
* o veredicto passa a **contar também as linhas `anchor found`**: um mutante inerte é uma
  FALHA, nunca um verde.

**Prova de que o buraco fechou** (mesma mutação de âncora, numa cópia em `_main/`):

```
  FAIL neg-arm M6 dispatch-entry-renamed anchor found  -- anchor missing -- the mutant would be INERT
VERDICT: FAIL -- 23 check(s), 1 fail      rc=1
```

Antes desta correcção, essa mesma corrida dava `VERDICT: PASS`.

---

## 6. O outro instrumento que assumia o duplo-toque

`_main/strip-first-frame.py --shows 2` mandava TRÊS pressões espaçadas de `gap=2.2 s`, com a
legenda *"press 1 shows, press 2 hides, press 3 shows again"* e o comentário *"spaced WIDER
than HOTKEY_DOUBLE_MS"*. Com o ciclo, press 2 é o painel da DIREITA e press 3 é o hide — a
segunda medição da strip passou a ser a **quarta** pressão. O instrumento foi re-apontado:
press 2 = SIDE, press 3 = HIDE, press 4 = SHOW outra vez (e é o `tpress2` que a segunda janela
mede). `gap` deixou de ter significado e é agora só a distância de assentamento entre gestos.
Não foi corrido (lança uma shell) — a mudança é de aritmética de pressões, verificada por
`py_compile` e por leitura.

---

## 7. A app do dono FOI reiniciada e tem o ciclo

Uma mudança de shell **não** entra por hot reload (`hot_reload.py` só vigia
`panel.html`/`panel.css`/`panel.js`). Só o Lead lança; foi o Lead:

```
Stop-Process (filtro por artefacto: sotto_webview\.py | sotto_worker\.py)  -> remaining=0
schtasks /Run /TN Sotto
```

Verificado depois do arranque (`_main/panel-state.json`):

```
loaded=d6799cc4268e8400 disk=d6799cc4268e8400 stale=False
worker=capture-started childPid=10484
SINGLE_INSTANCE already_running=false
PANEL_LAZY_GATE_ARMED registered=5 urls=5
RECEIVER_READY captions=0 hasBridge=True
PRELOAD_ACTIVE hasSotto=true methods=15 hotkey=Alt+C
```

Havia um segundo reinício a meio: o primeiro lançou a shell já com o ciclo, e depois disso só
mudou um docstring de `show_side` (que ainda dizia "double-press path"); reiniciei outra vez
para o invariante `loaded == disk` ficar verdadeiro, em vez de deixar a app a reportar
`stale: true` por causa de um comentário.

---

## 8. Portões

`node _main/instruments-battery.mjs` -> **89/89 instrument(s) rc=0; failed=0; launches=0**.
Inclui `selftest-focus` (que conduz `selftest_broken` com leituras sintéticas e não depende da
classificação das pressões), `handler-map` 6/0 + neg 8/0, `scope-leak` 9 folhas 0 fugas.

Pins do produto ao fim de tudo:

| ficheiro | bytes | sha256 (16) | CRLF |
|---|---|---|---|
| `app/webview/sotto_webview.py` | **505 554** | `D6799CC4268E8400…` | 0 bare LF |
| `_main/strip-geometry-oracle.py` | 18 545 | — | LF |
| `_main/strip-first-frame.py` | 22 155 | — | LF |

---

## 9. NÃO MEDIDO

1. **Nenhuma tecla Alt+C real foi premida por mim.** O ciclo está provado **em processo**, com o
   método real e o fake da janela, e a shell que o dono tem está carregada e é a que foi medida
   (`loaded == disk`). O que falta é a mão dele: a primeira pressão depois de ler isto. O
   `--selftest` **não podia** ser corrido — a app do dono tem o mutex `Local\SottoShell` e a
   hotkey, e o `--selftest` precisa exactamente dessa registo.
2. **O `reason=` mudou nos logs.** Antes: `HOTKEY_DOUBLE dt_ms=… mode=side action=…`. Agora:
   `PANEL_SHOWN reason=hotkey mode=side` (e `mode=strip`, e `PANEL_HIDDEN reason=hotkey`). Quem
   fizer grep a `HOTKEY_DOUBLE` não encontra nada — é a remoção, não uma perda.
3. Não re-corri o `_main/_audit-verify-all.cmd` (a bateria de 41 passos) nem qualquer coisa que
   abra uma janela.
