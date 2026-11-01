# RECIBO — FALSIFICADOR DA CLAIM DO ALT+C (SPAM COM O ALT EM BAIXO)

**Data:** 2026-11-01
**Agente:** `FalsifyHotkeySpam`
**Arvore medida:** `H:/sotto` @ `8832468` (o PRODUTO, sem uma linha tocada)
**Instrumento:** `I:/cc-tmp/hotkey-spam-falsify/driver.py` (novo, este trabalho) — driver de
press-trace HEADLESS
**VEREDITO: `NOT-REFUTED`** — a claim sobrevive ao falsificador.

---

## A CLAIM (uma so')

> **"faz os paineis alternarem mesmo se eu deixar alt apertado o tempo inteiro e spammando c.
> alterna entre show e hide."**

Julgada como: **com o Alt apertado continuamente e o `c` martelado N vezes, o painel alterna N
vezes — cada pressao vira show->hide ou hide->show, nenhuma engolida, nenhuma repetida.**

**RISK-CLASS: T3** — o par lei/verificador do Alt+C (o gate `_main/altc-gesture-oracle.py` e a
app). Um falsificador e' MANDATORIO, e este e' um.

---

## A OBSERVACAO QUE REFUTARIA A CLAIM (escrita ANTES de correr nada)

> **Se, com o Alt em baixo durante toda a corrida, uma pressao de `c` NAO produzisse uma mudanca
> de visibilidade — ou produzisse DUAS — a claim cai.** Concretamente, o que derrubaria a claim
> e' ver, na serie de estados do painel, qualquer um destes:
>
> - `flips < N` (uma pressao engolida: o `c` martelado nao avanca o ciclo);
> - `flips > N` (uma pressao a mais: o mesmo `c` a造 dois passos);
> - dois estados visiveis **consecutivos** (dois `show` seguidos, ou dois `hide` seguidos) — a
>   alternancia(show/hide) que a frase do dono pede;
> - uma pressao que mudasse a **legenda** em vez do painel (o `c` virando HOLD).

Esta observacao e' falsificadora porque a frase do dono afirma **as duas** coisas ao mesmo tempo:
o **numero** de mudancas (N) e a **alternancia** (show/hide). Se qualquer uma das duas falhar, a
claim e' falsa. E' o criterio de julgamento do braco `pos` — e o criterio de julgamento **nao**
inclui nada mais (nem a docstring do modulo, nem o ciclo `strip/panel` descrito no fonte): o
julgador so' conhece a frase do dono.

---

## O INSTRUMENTO DO AUTOR (que este trabalho NAO usa)

`_main/altc-gesture-oracle.py` — a propria docstring diz o que e':

> *"Os corpos de `hotkey_pressed`, `hotkey_live`, `_hotkey_resolve` e `_on_press` sao EXTRACTOS DO
> FICHEIRO QUE VAI CORRER com `ast` e exec'd contra um shell falso, um relogio-ESPIAO ... e um
> `threading`-espiao (um Timer significa adiamento). Nenhuma janela e' aberta, nenhum ctypes e'
> tocado, nada e' posto no ecra do dono."*

E' um oraculo **ESTATICO**: mede o **CODIGO** re-executado contra um shell **fabricado** pelo
proprio teste, com o estado do painel a' ser um dicionario do teste. Nao corre a cadeia de
producao: nao ha thread, nao ha fila, nao ha pump, nao ha `WM_HOTKEY`. Comando do autor:
`python _main/altc-gesture-oracle.py`.

---

## O MEU INSTRUMENTO (diferente)

`I:/cc-tmp/hotkey-spam-falsify/driver.py` — importa a arvore e **corre a cadeia de producao
inteira**, sem janela e sem ecra:

```
HotkeyThread.run()                 thread Win32 real + fila de mensagens real
  -> PostThreadMessageW(WM_HOTKEY)  <- a pressao (o mesmo caminho que o `simulate_press` do
                                       proprio produto usa)
  -> HotkeyThread._on_press()       corpo de producao
  -> SottoShell.hotkey_pressed()    corpo de producao
  -> SottoShell._hotkey_dispatch('panels')   corpo de producao (FILA FIFO)
  -> SottoShell._hotkey_worker_loop()        corpo de producao (worker)
  -> SottoShell._hotkey_resolve('panels')    corpo de producao
  -> hotkey_gesture.next_surface()          a REGRA shipped
  -> show_strip / show_side / hide_panel     corpos de producao
```

**O QUE E' FALSO, E O QUE NAO E'** (a honestidade do instrumento, declarada):

| | |
|---|---|
| **FALSO** (folhas de SO / da PAGINA) | `window_visible`, `hide_window`, `foreground_unlock`, `show_webview_children`, `transparency_hack`, `set_topmost`, `show_without_activating`, `user32.SetWindowPos`, `exec_js`, `exec_js_post`, `_post`, `_post_metrics_refresh` |
| **REAL (shipped, sem edicao)** | o `HotkeyThread` (thread + fila + pump + `MOD_NOREPEAT`), `_on_press`, `hotkey_pressed`, `_hotkey_dispatch`, `_hotkey_worker_loop`, `_hotkey_resolve`, `show_strip`, `show_side`, `hide_panel`, `set_panel_surface`, `hotkey_gesture.next_surface`, e a memoria `surface_applied` |

A janela falsa **e' o ecra**: o flag `visible` dela e' a medicao, e cada transicao que ela regista
e' um `show` ou um `hide` de producao. A razao de falsificar a janela e' a lei do repo
(`SOTTO_NEVER_ON_OWNER_SCREEN`): uma janela real poria o painel no ecra do dono, e a pergunta
"esta visivel?" ficaria sem resposta sem ecra.

**O TECLADO.** O trace segura o ALT em baixo durante toda a corrida e entrega as pressoes de `c`
como `WM_HOTKEY`. O driver tambem envolve `user32.GetAsyncKeyState` e **CONTA** as leituras: se o
produto nunca pergunta o teclado, o ALT em baixo nao pode mudar nenhuma decisao, e o "alt apertado"
do trace e' um facto sobre a **ENTRADA**, nao sobre o produto. (Medido: **0 leituras** no braco
`pos`; **5/19/76** nos bracos que tem a costura de duracao.)

**A INTEGRIDADE DA CADEIA** e' medida, nao afirmada: o driver envolve os corpos de producao e
conta quantas vezes cada um correu.

**O JUIZ** vem **so' da frase do dono**: N pressoes -> N mudancas, e a serie visivel alterna
show/hide. Nada mais entra no julgamento.

**O PRODUTO NAO FOI TOCADO** (medido): `git diff --exit-code -- app/webview/` -> **0**; HEAD
`8832468`. As mutacoes vivem em `I:/cc-tmp/mutants/`, a copia da arvore historica em
`I:/cc-tmp/old-tree/` (extraida com `git archive 38ab1d6`).

---

## OS BRACOS E OS NUMEROS

Comando de tudo: `bash I:/cc-tmp/hotkey-spam-falsify/matrix.sh` (rc 0; cada braco escreve
`arm-<label>.json` + `log-<label>.txt`).

### BRACO `pos` — A ARVORE INTACTA (a claim) — **GREEN**

| braco | N | intervalo | posted | delivered | flips | serie visivel | veredicto |
|---|---|---|---|---|---|---|---|
| `prod-n3` | 3 | 30-120 ms | 3 | 3 | **3/3** | `show, hide, show` | GREEN |
| `prod-n5` | 5 | 30-120 ms | 5 | 5 | **5/5** | `show, hide, show, hide, show` | GREEN |
| `prod-n10` | 10 | 30-120 ms | 10 | 10 | **10/10** | `show, hide, show, hide, show, hide, show, hide, show, hide` | GREEN |
| `prod-n40` | 40 | 30-120 ms | 40 | 40 | **40/40** | 40 estados, `show/hide` a alternar sem uma unica repeticao | GREEN |
| `prod-wide` | 10 | 250-400 ms | 10 | 10 | **10/10** | alterna | GREEN |
| `prod-fast` | 10 | 30 ms fixo | 10 | 10 | **10/10** | alterna | GREEN |
| `prod-ultrafast` | 10 | 5-10 ms | 10 | 10 | **10/10** | alterna | GREEN |
| `prod-n30` | 30 | 120 ms | 30 | 30 | **30/30** | alterna | GREEN |

**Numeros crus do `prod-n10`** (`arm-prod-n10.json`):

```
verdict=GREEN  flips=10/10  posted=10  delivered=10  gas_reads=0
visible_sequence = ['show','hide','show','hide','show','hide','show','hide','show','hide']
surface_sequence = ['strip','strip','panel','panel','strip','strip','panel','panel','strip','strip']
chain_calls = {hotkey_pressed:10, _hotkey_dispatch:10, _hotkey_worker_loop:1,
               _hotkey_resolve:10, show_strip:3, hide_panel:5, show_side:2}
log_channel = {PANEL_SHOWN:5, PANEL_HIDDEN:5, HOTKEY_TOGGLE:10, HOTKEY_PRESSED:10,
               recorder_flips:10, channels_agree:true}
alt_held = {alt_down_at_ms:0.0, alt_up_at_ms:660.0,
            all_c_presses_inside_alt_held:true, c_presses_inside:10, c_presses_total:10}
property_present = true
reasons = []
```

**A INTEGRIDADE DA CADEIA, medida no `prod-n10`**: `hotkey_pressed` 10, `_hotkey_dispatch` 10,
`_hotkey_worker_loop` 1, `_hotkey_resolve` 10, `show_strip` 3, `hide_panel` 5, `show_side` 2.
A regra carregada e' a do disco: `gesture_module_file =
H:\sotto\app\webview\hotkey_gesture.py`, e `sha256(disco) == sha256(carregado)` =
`298ea9bb6b7f2280fa739a48`.

**DOIS CANOS INDEPENDENTES, A CONCORDAR EM TODOS OS BRACOS**: o registo da janela falsa
(`recorder_flips`) e as **linhas de log de producao** (`PANEL_SHOWN` + `PANEL_HIDDEN`, escritas
pelos corpos shipped). `channels_agree=true` em **todos** os 22 bracos da matriz. Um instrumento
que so' lesse o proprio registo podia ser enganado por um registo que mente; dois canos que
concordam nao podem.

### BRACO `null` — O CONTROLE NEGATIVO DA PROPRIEDADE (a propriedade CONHECIDAMENTE AUSENTE)

**ZERO pressoes** (o input onde a propriedade esta' ausente por construcao):

```
prod-null  verdict=GREEN  flips=0/0  posted=0  delivered=0
visible_sequence = []   property_present = false
chain_calls = {}   log_channel = {PANEL_SHOWN:0, PANEL_HIDDEN:0, HOTKEY_PRESSED:0,
                                   recorder_flips:0, channels_agree:true}
```

O probe **diz que a propriedade nao esta' la** quando ela nao esta' la.

### BRACO `invert` — A MESMA MEDICAO, A EXPECTATIVA INVERTIDA

A mesma corrida, a mesma serie, a expectativa oposta (N `show`, nenhum `hide`):

```
prod-invert  verdict=RED  flips=10/10
reasons = ["INVERTED claim expected ['show',...x10], got
            ['show','hide','show','hide','show','hide','show','hide','show','hide']"]
```

**O probe sabe dizer NAO.** Nao e' vacuo.

### BRACO NEGATIVO 1 — O DEFEITO QUE A CLAIM EXISTE PARA MATAR (edge-detect / janela de toques)

**MUTANTE A** (em `I:/cc-tmp/mutants/A-tap-window/`, **fora do produto**): a janela de toques
volta a `hotkey_pressed` — a segunda pressao dentro de 400 ms e' **engolida**:

```python
        # MUTANT A: TAP WINDOW (edge detect) -- a press inside the window
        # after the previous one is SWALLOWED.
        import time as _t
        now = _t.monotonic()
        prev = getattr(self, '_hotkey_last_tap', 0.0)
        if prev and (now - prev) * 1000.0 <= 400.0:
            return None   # swallowed: the second press inside the window
        self._hotkey_last_tap = now
        return self._hotkey_dispatch('panels')
```

| braco | N | intervalo | posted | delivered | flips | serie visivel | veredicto |
|---|---|---|---|---|---|---|---|
| `mutA-n3` | 3 | 30-120 ms | 3 | 3 | **1/3** | `['show']` | **RED** |
| `mutA-n10` | 10 | 30-120 ms | 10 | 10 | **2/10** | `['show','hide']` | **RED** |
| `mutA-n40` | 40 | 30-120 ms | 40 | 40 | **7/40** | 7 estados | **RED** |
| `mutA-wide` | 10 | 500-900 ms | 10 | 10 | 10/10 | alterna | GREEN |

O ultimo caso e' o **CONTROLE DE SENSIBILIDADE** do negativo: com as pressoes **fora** da janela
(500-900 ms > 400 ms), o mutante passa — o que mostra que o RED de cima vem da **janela**, e nao
de o mutante estar estragado por outra razao. E' a prova de que o probe mede a janela e nao
"alguma coisa".

`arm-mutA-n10.json`:

```
verdict=RED  flips=2/10  posted=10  delivered=10
visible_sequence = ['show','hide']
chain_calls = {hotkey_pressed:10, _hotkey_dispatch:2, _hotkey_worker_loop:1,
               _hotkey_resolve:2, show_strip:1, hide_panel:1}
log_channel = {PANEL_SHOWN:1, PANEL_HIDDEN:1, HOTKEY_TOGGLE:2, HOTKEY_PRESSED:10,
               recorder_flips:2, channels_agree:true}
property_present = false
reasons = ['flips=2 expected=10 (presses swallowed)', ...]
```

**A PROVA DE QUE O VERDE DO `pos` VEM DO PRODUTO**: as 10 pressoes chegaram (`HOTKEY_PRESSED:10`,
`hotkey_pressed:10`), e mesmo assim so 2 viraram passo. O `presses_delivered_by_pump` e' 10 nos
dois bracos: o que difere e' quantas viraram **mudanca de ecra**.

### BRACO NEGATIVO 2 — O GESTO APOSADO (duracao): o ALT em baixo decide

**MUTANTE D** (em `I:/cc-tmp/mutants/D-alt-only-duration/`, fora do produto): volta o gesto
aposado de 2026-10-30 — a medicao abre na primeira pressao e **nunca fecha** enquanto o ALT esta'
em baixo, e a duracao decide HOLD vs TOQUE com `GetAsyncKeyState(0x12)`.

| braco | N | intervalo | posted | delivered | flips | gas reads | veredicto |
|---|---|---|---|---|---|---|---|
| `mutD-n3` | 3 | 30-120 ms | 3 | 3 | **1/3** | 1 | **RED** |
| `mutD-n10` | 10 | 30-120 ms | 10 | 10 | **1/10** | 1 | **RED** |
| `mutD-n40` | 40 | 30-120 ms | 40 | 40 | **1/40** | 1 | **RED** |

`arm-mutD-n10.json`: `visible_sequence = ['show']`, `chain_calls = {hotkey_pressed:10,
_hotkey_dispatch:1, _hotkey_resolve:1, show_strip:1}`, `reasons = ['flips=1 expected=10 (presses
swallowed)']`. O `gas_reads=1` diz **onde** esta a costura: no `GetAsyncKeyState`. O produto
shipped, com o **mesmo** trace e o **mesmo** driver, faz **0** leituras.

### BRACO NEGATIVO 3 — A ARVORE REAL DE ANTES DA CORRECAO (git `38ab1d6`, 2026-10-30)

Este e' o negativo mais forte: **nao e' um mutante inventado**, e' a arvore que o dono tinha, com o
gesto de toques + duracao, extraida com `git archive 38ab1d6 app/webview app/panel`.

| braco | N | intervalo | posted | delivered | flips | gas reads | veredicto |
|---|---|---|---|---|---|---|---|
| `hist-n3` | 3 | 30-120 ms | 3 | 3 | 3/3 | 5 | **RED** |
| `hist-n10` | 10 | 30-120 ms | 10 | 10 | 10/10 | 19 | **RED** |
| `hist-n40` | 40 | 30-120 ms | 40 | 40 | 40/40 | 76 | **RED** |

`arm-hist-n10.json`:

```
verdict=RED  flips=10/10  posted=10  delivered=10  gas_reads=19
visible_sequence = ['show','show','hide','show','show','hide','show','show','hide','show']
surface_sequence = ['strip','panel','panel','strip','panel','panel','strip','panel','panel','strip']
chain_calls = {hotkey_pressed:10, _hotkey_dispatch:10, _hotkey_worker_loop:1,
               _hotkey_resolve:10, show_strip:4, show_side:3, hide_panel:3}
log_channel = {PANEL_SHOWN:7, PANEL_HIDDEN:3, HOTKEY_TOGGLE:3, HOTKEY_PRESSED:10,
               recorder_flips:10, channels_agree:true}
property_present = false
reasons = ["visible sequence does not alternate show/hide: got=['show','show','hide',...]
            expected=['show','hide','show','hide',...] first_divergence_at=1"]
```

**O MECANISMO, medido**: na arvore de 2026-10-30 as 10 pressoes chegam todas, mas o `HOTKEY_TOGGLE`
e' escrito **3 vezes** (nao 10) e a serie visivel e'
`show, show, hide, show, show, hide, ...` — **dois `show` seguidos**. E' exactamente o defeito que
a frase do dono descreve: *"alterna entre show e hide"* — a arvore de antes **nao** alternava, e
era por isso que a frase foi escrita. O log da corrida (`log-hist-n10.txt`) mostra a costura:

```
HOTKEY_PRESSED count=1 thread=54872
HOTKEY_RELEASED count=1 held_ms=0 hold_fired=false reason=release thread=54872
HOTKEY_PRESSED count=2 thread=54872
...
```

O `HOTKEY_RELEASED` com `held_ms=0` em cada pressao e' a leitura da duracao a fechar o gesto a
cada `c` — e o `HOTKEY_TOGGLE` (o passo do painel) a sair so 3 vezes em 10.

---

## A OBSERVACAO QUE REFUTARIA NAO DISPAROU

No braco `pos` (a arvore intacta), em **todos** os oito bracos:

- `flips == N` em todos (nenhuma pressao engolida, nenhuma a mais);
- a serie visivel **alterna** show/hide em todos (nenhum `show` seguido de `show`, nenhum `hide`
  seguido de `hide`);
- `getasynckeystate_reads_during_run == 0` — o produto **nunca pergunta o teclado**, portanto o
  ALT em baixo nao tem por ondeInfluence a decisao;
- `HOTKEY_PRESSED` == N e `HOTKEY_TOGGLE` == N (no shipped, `HOTKEY_TOGGLE:10` com
  `PANEL_SHOWN:5`/`PANEL_HIDDEN:5`).

---

## O QUE ESTA MEDICAO **NAO** PROVA (honestidade do veredicto)

- **O painel nao foi desenhado nem medido no ecra.** A janela e' falsa; o que esta medido e' a
  **cadeia de decisao** (que passo cada pressao pede e quantos passos sao dados), nao o pixel. Um
  `show` que o Windows recusasse (e que fizesse `IsWindowVisible` continuar `False`) seria visto
  pelo shipped como um **hide** no passo seguinte — o shipped le a janela a cada passo e continua
  de onde ela esta', e o driver mede essa leitura pela fake. **[INFERENCE]** uma falha de
  mapeamento do Windows mudaria a serie; mede-la exigiria uma janela real, que a lei proibe.
- **A pressao e' um `WM_HOTKEY` posto na fila**, nao o dedo do dono. O `AGENTS.md` e' explicito:
  *"nenhum evento sintetico e' evidencia sobre a app: `keybd_event`/`SendInput` medem o Windows"*.
  O que se mediu e' **a resposta da app a uma entrega de `WM_HOTKEY`** — a entrega de producao.
  Nenhum `keybd_event`, nenhum `SendInput`, nenhuma tecla global registada (o thread corre com
  `register=False`; e no braco historico o `RegisterHotKey` foi neutralizado para **nao** tomar a
  tecla global do dono).
- **O ALT em baixo e' um facto sobre o trace, nao sobre o produto.** E' exato porque o produto
  **nao le o teclado** (`gas_reads=0`, medido), e o `AGENTS.md` da propria app diz o mesmo: *"nao ha
  seam de duracao"*. Nao ha `VK_MENU` no `hotkey_gesture.py` (grep: 0).
- **O historico corre com o `RegisterHotKey` neutralizado** (para nao tomar a tecla do dono) e com
  o `hotkey_gesture` de 2026-10-30 — o resto do ficheiro e' o de `38ab1d6`, byte a byte.
- **A app viva do dono nao foi tocada.** Nenhum processo lancado, nenhuma janela aberta, nenhum
  registo de tecla global, `git diff --exit-code -- app/webview/` -> 0.

---

## O CONTRATO (o bloco exigido, verbatim)

```text
CLAIM: "faz os paineis alternarem mesmo se eu deixar alt apertado o tempo inteiro e spammando c. alterna entre show e hide." -> Com o Alt apertado continuamente e o `c` martelado N vezes, o painel alterna N vezes -- cada pressao vira show->hide ou hide->show, nenhuma engolida, nenhuma repetida.
RISK-CLASS: T3 -- gates/guards/hooks/admission scripts (o par lei/verificador do Alt+C) -- falsificador MANDATORIO
AUTHOR-INSTRUMENT: `_main/altc-gesture-oracle.py` -- oraculo ESTATICO: extrai com `ast` os corpos de `hotkey_pressed`, `hotkey_live`, `_hotkey_resolve` e `_on_press` do ficheiro que vai correr e exec'-os contra um shell FALSO, um relogio-ESPIAO e um `threading`-espiao; nenhuma janela aberta, nenhum ctypes tocado, nada no ecra do dono. Comando: `python _main/altc-gesture-oracle.py`
MY-INSTRUMENT: `I:/cc-tmp/hotkey-spam-falsify/driver.py` -- driver de press-trace HEADLESS: importa a arvore e corre a CADEIA DE PRODUCAO (HotkeyThread com fila Win32 real -> PostThreadMessageW(WM_HOTKEY) -> _on_press -> hotkey_pressed -> _hotkey_dispatch -> _hotkey_worker_loop -> _hotkey_resolve -> hotkey_gesture.next_surface -> show_strip/show_side/hide_panel), com o ALT em baixo durante toda a corrida e o `c` martelado; so' as FOLHAS de SO/PAGINA sao falsas (window_visible, hide_window, foreground_unlock, show_webview_children, transparency_hack, set_topmost, SetWindowPos, exec_js, exec_js_post, _post) porque a lei `SOTTO_NEVER_ON_OWNER_SCREEN` proibe uma janela no ecra do dono; o wrap de `GetAsyncKeyState` conta as leituras de teclado. Comandos: `bash I:/cc-tmp/hotkey-spam-falsify/matrix.sh` (rc 0) e `python I:/cc-tmp/hotkey-spam-falsify/driver.py --tree H:/sotto --n 10 --lo-ms 30 --hi-ms 120 --label prod-n10`
FALSIFYING-OBSERVATION: "Se, com o Alt em baixo durante toda a corrida, uma pressao de `c` NAO produzisse uma mudanca de visibilidade -- ou produzisse DUAS -- a claim cai. Concretamente: `flips < N` (uma pressao engolida), `flips > N` (uma pressao a mais), dois estados visiveis CONSECUTIVOS (dois `show` seguidos ou dois `hide` seguidos -- a alternancia show/hide que a frase pede), ou uma pressao que mudasse a LEGENDA em vez do painel (o `c` virando HOLD)."
NEGATIVE-CONTROL: a MESMA sonda, a MESMA corrida, a expectativa INVERTIDA (esperar N `show` e nenhum `hide`) => "prod-invert verdict=RED flips=10/10 posted=10 delivered=10 reasons=[\"INVERTED claim expected ['show','show','show','show','show','show','show','show','show','show'], got ['show','hide','show','hide','show','hide','show','hide','show','hide']\"]" (arm-prod-invert.json). Segunda forma, pelo DEFEITO QUE A CLAIM EXISTE PARA MATAR (janela de toques / edge-detect, mutado FORA do produto em I:/cc-tmp/mutants/A-tap-window): "mutA-n10 verdict=RED flips=2/10 posted=10 delivered=10 visible_sequence=['show','hide'] chain_calls={hotkey_pressed:10, _hotkey_dispatch:2, _hotkey_resolve:2, show_strip:1, hide_panel:1} reasons=['flips=2 expected=10 (presses swallowed)']" (arm-mutA-n10.json) -- e o CONTROLE DE SENSIBILIDADE do mesmo mutante, com as pressoes FORA da janela: "mutA-wide verdict=GREEN flips=10/10" (arm-mutA-wide.json). Terceira forma, pelo GESTO APOSADO de 2026-10-30 (mutante D, fora do produto): "mutD-n10 verdict=RED flips=1/10 posted=10 delivered=10 visible_sequence=['show'] gas_reads=1" (arm-mutD-n10.json). Quarta forma, pela ARVORE REAL DE ANTES DA CORRECAO (git 38ab1d6, extraida com `git archive`): "hist-n10 verdict=RED flips=10/10 posted=10 delivered=10 gas_reads=19 visible_sequence=['show','show','hide','show','show','hide','show','show','hide','show'] surface_sequence=['strip','panel','panel','strip','panel','panel','strip','panel','panel','strip'] reasons=[\"visible sequence does not alternate show/hide: got=['show','show','hide',...] expected=['show','hide',...] first_divergence_at=1\"]" (arm-hist-n10.json). E o BRAZO DE PROPRIEDADE AUSENTE (zero pressoes): "prod-null verdict=GREEN flips=0/0 posted=0 delivered=0 visible_sequence=[] property_present=false" (arm-prod-null.json)
POSITIVE-CONTROL: a MESMA sonda na arvore INTACTA (H:/sotto, HEAD 8832468), com a frase do dono tal como esta escrita => "prod-n3 verdict=GREEN flips=3/3 posted=3 delivered=3 visible_sequence=['show','hide','show']" | "prod-n5 verdict=GREEN flips=5/5 posted=5 delivered=5 visible_sequence=['show','hide','show','hide','show']" | "prod-n10 verdict=GREEN flips=10/10 posted=10 delivered=10 gas_reads=0 visible_sequence=['show','hide','show','hide','show','hide','show','hide','show','hide'] surface_sequence=['strip','strip','panel','panel','strip','strip','panel','panel','strip','strip'] chain_calls={hotkey_pressed:10, _hotkey_dispatch:10, _hotkey_worker_loop:1, _hotkey_resolve:10, show_strip:3, hide_panel:5, show_side:2} log_channel={PANEL_SHOWN:5, PANEL_HIDDEN:5, HOTKEY_TOGGLE:10, HOTKEY_PRESSED:10, recorder_flips:10, channels_agree:true} alt_held={all_c_presses_inside_alt_held:true, c_presses_inside:10, c_presses_total:10} property_present=true reasons=[]" | "prod-n40 verdict=GREEN flips=40/40 posted=40 delivered=40 log(S/H)=20/20 agree=true gas=0 prop=True" (arm-prod-n40.json) + os braços de intervalo "prod-wide verdict=GREEN flips=10/10" (250-400 ms), "prod-fast verdict=GREEN flips=10/10" (30 ms fixo), "prod-ultrafast verdict=GREEN flips=10/10" (5-10 ms), "prod-n30 verdict=GREEN flips=30/30" (120 ms) -- 22 bracos no total, `channels_agree=true` em todos
PROBE: `bash I:/cc-tmp/hotkey-spam-falsify/matrix.sh` (dentro: `python I:/cc-tmp/hotkey-spam-falsify/driver.py --tree H:/sotto --n 10 --lo-ms 30 --hi-ms 120 --label prod-n10`, que carrega `H:\sotto\app\webview\hotkey_gesture.py` e `H:\sotto\app\webview\sotto_webview.py` sem edicao) -- exit 0 -- "prod-n10 verdict=GREEN flips=10/10 posted=10 delivered=10 gas_reads=0 | visible_sequence=['show','hide','show','hide','show','hide','show','hide','show','hide'] | chain_calls={hotkey_pressed:10, _hotkey_dispatch:10, _hotkey_resolve:10, show_strip:3, hide_panel:5, show_side:2} | log_channel={PANEL_SHOWN:5, PANEL_HIDDEN:5, HOTKEY_TOGGLE:10, HOTKEY_PRESSED:10, channels_agree:true} | prod-invert verdict=RED | mutA-n10 verdict=RED flips=2/10 | mutD-n10 verdict=RED flips=1/10 | hist-n10 verdict=RED visible_sequence=['show','show','hide',...]" (a mutacao do tap-window vive em I:/cc-tmp/mutants/A-tap-window, e a arvore historica em I:/cc-tmp/old-tree, extraida com `git archive 38ab1d6`; `git diff --exit-code -- app/webview/` em H:/sotto -> 0, o PRODUTO NAO FOI TOCADO)
VERDICT: NOT-REFUTED
WHAT-WOULD-SETTLE: n/a
```

---

## STATUS: done

A claim foi atacada com um instrumento **diferente** do autor (a cadeia de producao a correr, com
trace de teclas e fila Win32 real, em vez de corpos re-execados contra um shell fabricado), com
**quatro** negativos da mesma forma — a expectativa invertida, o tap-window mutado, o gesto
aposado mutado, e a arvore **real** de antes da correcao — e com um braco de propriedade ausente.
**Sobreviveu**: N pressoes -> N mudancas, show/hide a alternar sem uma unica repeticao, em N = 3,
5, 10, 30 e 40, e com 0 leituras de teclado.

## CACHE/PRICE

```text
## CACHE/PRICE
- task/agent: FalsifyHotkeySpam
- source: G:\env-data\superharness\usage_telemetry\model-usage.jsonl
- cache: read=UNKNOWN — cache-read field absent or invalid on one or more matched usage rows write=UNKNOWN — cache-write field absent or invalid on one or more matched usage rows hit=UNKNOWN — input/cache-read denominator incomplete or zero; universe: 0 usage rows from G:\env-data\superharness\usage_telemetry\model-usage.jsonl; instrument: scripts/cache-task-report.sh
- price: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available; UNKNOWN — no usage rows matched, so there is no price to partition
- when-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['FalsifyHotkeySpam']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- where-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['FalsifyHotkeySpam']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- report generated_at: 2026-11-01T19:05:21.901096+00:00
- usage rows: 0
- model + route: UNKNOWN — no provider usage rows matched
- input tokens: UNKNOWN — input field absent or invalid on one or more matched usage rows
- output tokens: UNKNOWN — output field absent or invalid on one or more matched usage rows
- cache-read tokens: UNKNOWN — cache-read field absent or invalid on one or more matched usage rows
- cache-write tokens: UNKNOWN — cache-write field absent or invalid on one or more matched usage rows
- hit ratio: UNKNOWN — input/cache-read denominator incomplete or zero
- cost: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available
- price partition: UNKNOWN — no usage rows matched, so there is no price to partition
- prefix breaks: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['FalsifyHotkeySpam']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- WHEN / WHERE failed:
UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['FalsifyHotkeySpam']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

## SELF-AUDIT

- **protocolos em falta** — A lei `SOTTO_NEVER_ON_OWNER_SCREEN` obrigou a falsificar a janela: a
  medicao que fiz e' da **cadeia de decisao**, nao do pixel. Faltou-me uma convencao do repo para
  "falsificar a janela sem perder o juizo": construi uma (a janela falsa **e'** o ecra) e
  declarei-a no proprio recibo, mas devia ter pedido o padrao da casa antes. Tambem nao encontrei
  um nome canonico para o ficheiro do driver: pus em `I:/cc-tmp/`, que e' area de rascunho, e nao
  em `_main/_falsify/` (que existe e temceipts de falsificacao do outro lane). A razao: a regra
  do repo proibe `I:/!manager` de ser tocado por lanes, mas nao achei uma regra que obrigue o
  driver a ser Checked-in; deixo o caminho no recibo para o Main o mover se quiser.
- **verificacao extra** — Corri: (a) o braco `mutA-wide` (pressoes **fora** da janela), que e' o
  controle de sensibilidade do negativo: com 500-900 ms o mutante passa, o que prova que o RED
  vem da janela e nao de o mutante estar estragado por outra razao — este era o mais importante,
  porque sem ele um mutante RED poderia ser RED por um motivo errado; (b) `prod-invert` (a
  expectativa invertida na mesma corrida), que prova que o probe diz NAO; (c) `prod-null` (zero
  pressoes), que prova que o probe diz AUSENTE; (d) o cross-check de **dois canos** (o registo da
  janela e as linhas `PANEL_SHOWN`/`PANEL_HIDDEN` de producao), que concordaram em **todos** os 22
  bracos; (e) a **integridade da cadeia** (contar quantas vezes cada corpo de producao correu),
  que provou que o probe nao contorna o produto; (f) `sha256` do `hotkey_gesture.py` carregado vs
  o do disco, identico.
- **checkboxes novas** — Acrescentaria a esta classe de trabalho: (1) um check de **"o veredicto
  RED do mutante sobrevive ao controle de sensibilidade"** — ou seja, correr o mutante tambem com o
  input que o DEVERIA deixar passar, e exigir RED+GREEN no par; um mutante que e' sempre RED nao
  prova nada; (2) um check de **"o numero de leituras de teclado"** como metrica do proprio
  veredicto (`gas_reads`), para o recibo poder dizer *onde* esta a costura e nao so *que* ha uma
  costura; (3) um check de **"a cadeia de producao foi executada"** (contar chamadas aos corpos
  de producao) como pre-condicao do GREEN — um probe que responde GREEN sem tocar no produto
  passa a ser impossivel.
- **review por outro subagente** — sim, com escopo: a **tabela de VEREDITO por braco** e a
  correccao do **juiz** (a frase do dono sozinha). O resto (as arvores de scratch, os mutantes, o
  driver) e' instrumentacao com o resultado medido e as negative controls, e um revisor gastaria
  um turno a reexecutar 22 bracos sem decidir nada. Nao aceito que outro subagente escreva neste
  recibo (regra da casa: um veredicto, um autor).
- **gate-doubt:**
  - **verde-de-verdade:** O verde do `pos` podia ter passado **vacuamente** em tres sítios, e
    todos foram fechados mecanicamente. (i) *Sonda que responde GREEN sem tocar no produto*:
    fechado pela contagem da cadeia (`hotkey_pressed:10, _hotkey_resolve:10, show_strip:3,
    hide_panel:5, show_side:2` no `prod-n10`) — o GREEN so pode vir de 10 decisoes de producao.
    (ii) *Registrador que mente* (o meu proprio `FakeWindow` a contar o que eu quero que conte):
    fechado pelo segundo cano, as linhas `PANEL_SHOWN`/`PANEL_HIDDEN` escritas pelos corpos
    shipped — `channels_agree=true` em **todos** os 22 bracos, e o `mutA`/`mutD`/`hist` mostram os
    dois canos a contarem o mesmo numero **errado** (2, 1, 10 em vez de 10, 10, 10). (iii) *Um
    mutante RED pelo motivo errado*: fechado pelo `mutA-wide` (o mesmo mutante, input fora da
    janela, GREEN) e pelo `mutD`/`hist` (mecanismos **diferentes**, ambos RED). Havia ainda um
    quarto risco que fechei: o **instrumento partilhado/contaminado** — o driver corre contra
    varias arvores no mesmo processo Python e todas imported `sotto_webview` de `sys.path`; cada
    corrida e' um **processo novo** (`python driver.py ...` por braco), por isso nao ha
    contaminacao entre bracos. Medido: `arm-*.json` sao 22 ficheiros distintos, cada um com a
    sua arvore no campo `tree`.
  - **falta-no-gate:** O gate `_main/altc-gesture-oracle.py` **nao** mede a **entrega**: ele
    re-executa corpos contra um shell fabricado e nunca passa por `HotkeyThread`, pela fila, nem
    por um `WM_HOTKEY`. Um futuro defeito na **ordem** (a fila a reordenar dois passos, ou o
    `MOD_NOREPEAT` a ser tirado e o `WM_HOTKEY` a chegar em rajada) passaria o gate **verde** e
    quebraria a frase do dono — que e' uma claim sobre a **sequencia** do que o dono ve. Cenario
    concreto que atravessa: alguem muda `_hotkey_dispatch` para um `LIFO` (uma pilha em vez de
    uma fila) — `altc-gesture-oracle.py` continua verde (ele chama `_hotkey_resolve` diretamente,
    sem fila), e o dono ve os paineis a saltarem. E o segundo buraco: **o gate nao mede o
    `MOD_NOREPEAT`**, e sem ele o Windows entrega um `WM_HOTKEY` por repeticao da tecla — o
    painel passaria a oscilar sozinho.
  - **gate-melhor:** Um check MECANICO que feche os dois buracos, com o comando e o input que tem
    de o deixar RED: `python _main/altc-gesture-oracle.py` deve GANHAR um braco que corra a cadeia
    **real** (o `HotkeyThread` com `register=False` + `simulate_press`, como o `HotkeyThread`
    ja oferece) e exija, para N pressoes postadas, (a) `HOTKEY_PRESSED count == N`, (b) os
    `HOTKEY_TOGGLE` em ordem FIFO (a serie de `step=show|hide` tem de ser `show, hide, show,
    hide, ...` para N=10), e (c) `RegisterHotKey` chamado **com** `MOD_NOREPEAT`. O input que o
    deixa RED hoje: uma arvore com `_hotkey_dispatch` trocada por uma pilha (`q.get()` ->
    `q.get_nowait()` em LIFO) daria (b) RED com o log intacto — e uma arvore sem `MOD_NOREPEAT`
    daria (c) RED. O `--neg-arm` do proprio gate ja tem a forma (`_copy_tree` + mutacao + exigir
    RED), portanto o braco novo nao precisa de machinery nova. Este nao e' um patch pronto: e' o
    pedido, com o comando e o input que o tem de deixar RED.
- **confianca** — **alta** para o que a medicao diz (a cadeia de decisao alterna N vezes para N
  pressoes, com 0 leituras de teclado, e a mutacao de cada defeito possivel da RED). **media**
  para a extrapolar ao que o dono ve no ecra: a janela e' falsa, e um `ShowWindow` recusado pelo
  Windows mudaria a serie. O que a mudaria: uma corrida com a app **real** (que a lei proibe
  neste lane) ou um `panel-visibility.json` publicado durante uma corrida real.
- **nao verificado** — (a) que o `ShowWindow` do Windows aceitaria o mapa em cada pressao (a
  janela e' falsa); (b) o comportamento com o **teclado fisico** a verdade (o trace e' o que
  modelo de entrega; o `AGENTS.md` proibe input sintetico como evidencia); (c) que o
  `MOD_NOREPEAT` nao e' alterado por um `RegisterHotKey` posterior (o codigo mostra um unico
  registo, mas nao medi o registo real); (d) o comportamento do painel **fora** do ciclo (um
  `hide` vindo de outro caminho, p.ex. o watcher de clique fora, muda a serie) — nao exercitado;
  (e) o `hotkey_live` (Ctrl+Space) nao e' parte desta claim e nao foi medido.

---

## PRESERVACAO DO INSTRUMENTO (Main, 2026-11-01)

O driver citado acima vivia em `I:/cc-tmp/`, que e' scratch e pode ser limpo por
qualquer lane. Foi PRESERVADO no repo, sem uma linha alterada, em
`_main/_falsify/hotkey-spam-driver/` (`driver.py`, `show.py`, `MATRIX.txt`;
27 KB). Os comandos deste recibo que citam `I:/cc-tmp/hotkey-spam-falsify/`
correm a partir desse directorio com o mesmo nome de ficheiro; o `--tree H:/sotto`
e' o que fixa a arvore medida, e e' isso que faz a reproducao valer.
