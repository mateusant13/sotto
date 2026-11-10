# RECIBO - o arrasto do painel que NAO ANDA, e a linha que faltava (2026-11-10)

## 1. A ordem, verbatim

Dono, 2026-11-09 18:06Z: *"os paineis nao sao draggable em 240hz. e eu quero APERTAR meu scroll e
descer rapidamente pra cima ou pra baixo no historico. e o sotto performa mal em carga alta"*.

A metade do scroll ja' estava entregue no codigo com a frase dele ao lado
(`historyWheelStep` + `wireHistoryMiddleDrag`, `app/panel/panel.js:1780-1870`). O arrasto entrou
nesta rodada pelo lado que faltava: **nao havia como saber se o gesto dele falhou**, e essa e' a
unica metade que uma lane pode entregar sem a mao dele no rato.

## 2. O que o log VIVO mediu (39 h, `_main/webview-run.log`, 2026-11-08 18:23 -> 2026-11-10 09:37)

| token | ocorrencias |
|---|---|
| `WINDOW_DRAG_BEGIN` | **6** |
| `WINDOW_DRAG_DONE` | **6** |
| `WINDOW_DRAG_FOLLOW_END` (o seguidor novo, a 240 Hz) | **1** |

A unica medida com o seguidor novo, 2026-11-09 17:15:29:

```
WINDOW_DRAG_BEGIN surface=strip hwnd=131132 anchor=(1029,982) at=(770,948) ceiling_hz=240
WINDOW_DRAG_DONE  surface=strip to=(770,948) size=380x40 from=(770,948)
WINDOW_DRAG_FOLLOW_END surface=strip updates=0 samples=4 hz=0.0 max_gap_ms=4.38 elapsed_ms=17 ceiling_hz=240
```

## 3. O que essa linha NAO diz -- e por isso a queixa nao era atribuivel

`updates=0` tem duas causas que o log imprimia **identicas**:

1. o pixel nao mudou (o dedo nao mexeu) -- o desfecho NORMAL de um clique; ou
2. **a janela nao pode ser movida** -- `window_drag_to` devolve `False` tambem quando nao ha ancora
   (`no-anchor`), nao ha hwnd (`no-hwnd`) ou a geometria esta' a zero (`no-size`).

Com as duas no mesmo `updates=0`, um arrasto partido e um clique de 17 ms ficam indistinguiveis no
log, e um portao que nao consegue distinguir nao pode cobrar cura nenhuma. A classe e' a mesma que o
`instrument-vs-prose` (§1-§3) chama pelo nome: uma AUSENCIA precisa do instrumento que a poderia ter
visto.

## 4. A cura (medida, nao afirmada)

* `window_drag_to` escreve o motivo num canal de UMA atribuicao (`self._window_drag_refusal`):
  `no-anchor` / `no-hwnd` / `no-size`, e **limpa** o canal no caminho "o pixel nao mudou" -- senao um
  clique parado entraria na contagem como arrasto partido.
* `WindowDragFollower` conta `refused` e guarda a ultima causa; o fim do gesto passa a imprimir
  `refused=<n> cause=<motivo|->`.
* `WINDOW_DRAG_STUCK surface=.. cause=.. refused=.. samples=.. elapsed_ms=..` sai **so'** quando
  `samples >= WINDOW_DRAG_STUCK_SAMPLES (8)` **e** `updates == 0` **e** `refused > 0`. Abaixo do
  piso o gesto e' um clique e nao publica nada -- um alarme que dispara em todo clique e' ruido.

## 5. As arms (`python _main/window-drag-oracle.py`)

| arm | medido | veredicto |
|---|---|---|
| A1-A4 | delta / escala / clamp / identidade | GREEN |
| A5 | sem laco do Windows, seguidor armado, ancora presente | GREEN |
| A6 taxa entregue | **239,6 Hz**, 72 amostras em 300 ms, max_gap 6,59 ms | GREEN |
| A7 | zero `log` por amostra | GREEN |
| A8 | `persist` uma vez no fim | GREEN |
| A9 | 0,052 de um nucleo durante o gesto | GREEN |
| **A10 recusa-nomeada** | `samples=19 updates=0 refused=19` -> `WINDOW_DRAG_STUCK ... cause=no-anchor` | GREEN |
| **A11 clique-nao-alarma** | clique parado: `refused=0`, **zero** `WINDOW_DRAG_STUCK` | GREEN |
| **A12 piso-de-amostras** | gesto de 1 amostra com recusa: **zero** `WINDOW_DRAG_STUCK` | GREEN |

`VERDICT: PASS (12/12)`.

Braco negativo (`--neg-arm`), **dois** mutantes, cada um derrubado pela sua arm:
o laco do Windows reposto no `_begin_window_drag` (A5) e o emissor de `WINDOW_DRAG_STUCK` apagado
(A10). Medido: `NEG-ARM: PASS -- A5 rc=1 (caught) / A10 rc=1 (caught)`.

## 6. O QUE NAO ESTA' MEDIDO (e nao pode ser, por esta lane)

**Se o arrasto do dedo dele move a janela.** Isso exige um rato real na tela dele: a casa proibe
evento sintetico como evidencia (`AGENTS.md`, 2026-10-23 -- os quatro `err=0` do pressionador e zero
linhas no log do Sotto). O que esta' entregue e' a atribuicao: o proximo gesto dele que nao andar
deixa `WINDOW_DRAG_STUCK` com o motivo, em vez de mais um `updates=0` ambiguo.
