# O rato, o input e a cobertura por invocador (ORDEM 5)

> Movido de `AGENTS.md` em 2026-10-23 (trim). Conteudo verbatim;
> a medicao e as ressalvas sao as que la estavam.

### 5. O RATO DO DONO NÃO PASSA PELO SOTTO QUANDO NÃO PRECISA (2026-10-23)

> *"MEU MOUSE TA TRAVANDO DEMAIS. O RESTO DO SISTEMA NAO"* · *"MEU MOUSE VOLTA AO NORMAL QUANDO EU
> ENTRO NO CONTROL ALT DEL, MAS VOLTA A TRAVAR DEPOIS Q EU SAIO"* · *"sotto e pra usuarios ate com pc
> fraco, isso e inadmissivel"* · *"nunca mais cometa esse erro"*.

**O QUE ESTAVA MEDIDO E ERRADO.** `_main/webview-run.log`, corrida do dono, 2026-10-23:

```
19:46:41.606  OUTSIDE_CLICK_HOOK installed=true hook=748365515 thread=34768 type=WH_MOUSE_LL
19:46:42.825  PANEL_VISIBILITY_ON_SCREEN visible=false ... panel_shown=false
```

22 ms depois de a app nascer — e o painel **nunca** foi mostrado — o Sotto instalou um hook global de
rato. Um `WH_MOUSE_LL` põe **todos** os eventos do rato (1000/s num rato de 1000 Hz) a passar pelo
callback **Python** da thread que o instalou, antes de chegarem a mais nada. O cursor soluça; o resto do
sistema, que não espera por esse callback, fica bom. Sob **Ctrl+Alt+Del** o Windows **não entrega hooks
de utilizador** (o secure desktop não os chama) ⇒ o cursor fica bom lá dentro e volta a travar ao sair.
Esse é o mecanismo inteiro, e é por isso que o sintoma era "só o rato".

**A LEI (endurecida em 2026-10-30).** Um hook global de input (`WH_MOUSE_LL`, `WH_KEYBOARD_LL`,
`SetWindowsHookEx` de qualquer tipo) **não existe em caminho nenhum do Sotto**. A versão anterior desta
lei dizia "só enquanto faz falta" — preguiçoso, libertado, com auto-cura de 5 s. Era a disciplina de um
mecanismo, e o dono cortou o nó, verbatim: *"se esses hooks sao burros ou desnecessarios, remove. nao
mantem nada q tu ta achando q e pior"*.

**O QUE SUBSTITUIU O HOOK** (`app/webview/sotto_webview.py`, `OutsideClickWatcher`) — zero eventos de
input a passar por Python:
1. **fechar com um clique fora → o FOREGROUND.** `GetForegroundWindow()` a cada **100 ms**, só com o
   painel visível. Se o foreground deixa de ser a nossa janela (ou uma que nos possuímos), o clique foi
   fora. É uma chamada de sistema por tick, não um callback por evento.
2. **arrastar a faixa em edit mode → `GetCursorPos` + `GetAsyncKeyState(VK_LBUTTON)`** a **25 ms**, só
   com o botão em baixo. O arrasto normal do painel nunca usou o hook: `_begin_window_drag` entra no
   loop de movimento do próprio Windows (`WM_NCLBUTTONDOWN`/`HTCAPTION`).
3. **o tick não arranca sozinho**: `_restart_timer` chama `KillTimer` primeiro e desiste quando
   `_wants_poll()` (`armed or edit_mode`) é falso. Escondido, não há tick.

**O PORTÃO:** `_main/input-path-oracle.py` — **10 braços, 10 mutantes**, e o braço negativo
`red-as-expected-input-path` (rc=1 por desenho). O invariante passou a ser **a AUSÊNCIA**: `C1` exige
**zero** `SetWindowsHookEx` (qualquer variante), **zero** constante `WH_*_LL` e **zero** struct
`MSLLHOOKSTRUCT` no AST da shell inteira. Julga **FICHEIROS** + o estado de um objecto: **não** instala
hook, **não** cria janela, **não** lança nada. Está na bateria, e `_main/seam-coverage-oracle.py` prova
**12/12 invocadores** com controlo positivo e negativo (`_main/seam-inventory.json`).

**A REGRA GERAL QUE ISTO DEIXA:** qualquer coisa que o Sotto meta no **caminho de input ou de
composição** do Windows (hook, overlay layered, janela transparente, capture, timer de pintura) tem de
ser **medida pela ausência**: provar que não existe quando o produto está parado. "Não incomoda" não é
uma afirmação verificável; "não está instalado" é.


### 5-bis. A COBERTURA CONTA-SE POR INVOCADOR, E "FIXED" NÃO É "VERIFIED" (2026-10-23, segunda passagem)

> Do dono: *"nao me convenceu que tu leu oq tu deveria. veja os .md recentes de ate 5 dias atras de
> cada projeto."* E as notas frescas que ele mandou: `G:\superharness\runs\workflow-quality-loop-findings.md`
> (2026-10-23 20:20) e `I:\!manager\state\research\bug-hunt-workflow-approaches.md` (2026-10-23 20:12).

**A LIÇÃO QUE FALTAVA.** Um mutante apanhado **não diz qual invocador ficou desprotegido**. A
primeira passagem do §5 provava 6 braços e deixava **três** invocadores sem controlo nenhum:
o encerramento (`stop`), o canal de sincronização entre threads (`WM_HOOK_SYNC`) e um **segundo
tipo de hook** (teclado) que nada proibia. Foi um inquérito de invocadores — não um teste a mais —
que os encontrou.

**A REGRA.** A cobertura de um seam é
`invocadores com controlo positivo a passar E negativo a falhar NAQUELE braço / invocadores
enumerados`. Um invocador sem os dois **bloqueia a entrega** do seam.

**OS MECANISMOS (todos na bateria).**

| o que | onde | medido |
|---|---|---|
| inventário do seam: **9** invocadores (arranque, mostrar, esconder, edit-on, edit-off, stop, auto-cura, sync entre threads, outro tipo de hook) | `_main/seam-inventory.json` | — |
| cobertura: positivo no código real **e** o negativo tem de derrubar **aquele** braço | `_main/seam-coverage-oracle.py` | **9/9 PROVED**, 3 mutantes do inventário apanhados, `NEG-ARM PASS` |
| o oráculo do seam cresceu de 6 para **10 braços / 10 mutantes** (C6 outro hook, C7 stop, C8 propriedades sincronizam, C9 mostrar/esconder) | `_main/input-path-oracle.py` | 10/10 verdes, **10/10** mutantes |
| estados do bug: `reported → reproduced → cause-isolated → fixed → verified → recurrence-watch`; `fixed` cita um passo **da bateria** e o seu braço negativo; `verified` exige verificador ≠ autor | `_main/bug-ledger-oracle.py` + `_main/bug-ledger.json` | 5/5 mutantes do ledger apanhados |
| cápsula de incidente (esperado/observado, invocador, revisão, config, reprodução, fronteira, primeira divergência, condições contribuintes, acção com estado final + teste de escape) | `_main/incidents/INC-20261023-01-mouse-hook.md` | — |

**"FIXED, NOT VERIFIED" é o estado honesto deste repo hoje:** não há uma segunda lane a verificar
nem uma corrida real da app depois da cura. O `bug-ledger` imprime-o em letras grandes para
ninguém o poder ler como fecho. Um `verified` sem verificador independente **falha** — e o mutante
M5 do portão existe exactamente para essa auto-verificação não voltar.

**A REGRA GERAL:** um censo de invocadores que se desactualiza **cria um falso verde**. Por isso o
inventário é verificado por mecanismo (o portão importa o oráculo e corre o mutante nomeado), e um
invocador novo obriga a acrescentar uma entrada — a cobertura imprime-se como `n/9`.
