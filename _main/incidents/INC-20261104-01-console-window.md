# INC-20261104-01 — janela de consola / pop-up no ecrã do dono

Estado: **fixed** (o portão existe e mede; `verified` continua a exigir corrida real da app por
verificador independente).

## 1. O que ele viu, verbatim

2026-11-04, durante esta sessão: **"PARA DE MOSTRA POP UP"**.
Ordem anterior, 2026-11-02: *"para de abrir janela de terminal em foreground. é tu? ou um .vbs?"* /
*"anota no agents.md pra tu nunca mais fazer nada em foreground ou ter scripts q façam isso"*.

## 2. Observado vs esperado

- **Esperado:** nenhum script desta árvore abre nada no ecrã dele.
- **Observado:** duas classes diferentes, as duas medidas hoje.
  1. **Instrumento meu:** para provar o vigia de consolas larguei um `cmd.exe` sem flags de um pai
     **sem** consola. Apareceram **três** janelas em 1,6 s:
     `CASCADIA_HOSTING_WINDOW_CLASS` (`windowsterminal.exe`, t=0,52 s),
     `PseudoConsoleWindow` (`cmd.exe`, t=0,63 s), `Xaml_WindowedPopupClass` (t=1,63 s).
     Isto é a prova de que o detector vê a janela **e** a violação da lei: o controlo de um
     instrumento nunca pode abrir janela real.
  2. **Código da árvore:** o censo AST encontrou **2 sítios `WINDOW`** (`app/panel/history-store.js:247`
     e `_main/_historico-vs-redux-control-store.js:247`, os dois a largar `explorer` sem flags) e
     depois da cura converteu **833 chamadas** de `subprocess`/`os.system` para
     `_main/hidden-launch.py` / `CREATE_NO_WINDOW`.

## 3. A hipótese, e o que a refutaria

**Hipótese:** a janela é a consola que o Windows **aloca** ao filho quando o pai **não** tem consola.
O mesmo script não abre nada quando um agente o corre de um terminal, e abre quando a app o corre em
`pythonw` — não é o código a pedir uma janela, é a herança a faltar.
**Refutação:** se o mesmo script produzir uma janela de consola a partir de um pai **com** consola,
a hipótese cai. Medido: pai com consola → o filho **herda** e nenhuma janela aparece (`novas
janelas: 0` na enumeração). Hipótese não refutada.

## 4. Porque é que o instrumento mentiu duas vezes

- `ast.dump(Name(id='os'))` termina em `ctx=Load())`, **não** em `id='os')`: a comparação nunca
  casava e o censo estava **cego** a `os.system` / `os.popen`, a classe mais directa de janela.
  Medido com um ficheiro de uma linha (`os.system("echo ola")`): o censo devolvia **0 achados**.
- No JS, o grupo do regex lia o `child_process.` **opcional** como nome da função
  (`fn.startswith` sobre `None`), e o sítio era publicado como `PARSE`.

As duas correcções estão no ficheiro; a decisão de fundo foi trocar **regex por AST** e resolver o
`creationflags` **no escopo** (`creationflags=flags` de um parâmetro, `=0x08000000 if os.name=="nt"
else 0`).

## 5. A cura, e o portão que a prende

| instrumento | o que prova | medido |
|---|---|---|
| `_main/console-window-audit.py` | lê o **código**: 1139 ficheiros `.py/.js/.mjs` por AST | `WINDOW 0`, `NO-FLAG 0`, `STRING 0`, `GUARD-EXTERNAL 4`, `SCRIPT 313`, `USER-GESTURE 2`, `PARSE 0` |
| `_main/console-window-audit.py --neg-arm` | um `os.system` num ficheiro temporário **tem** de ser recusado | rc=1, `NEG-ARM PASS` |
| `_main/console-window-watch.py` | lê o **ecrã**: `EnumWindows` a 40 ms + `SetWinEventHook`, três classes de consola e quatro exes de consola | `--run` dos três oráculos de canal/landmine → **PASS, 0 janelas** |
| `_main/console-window-watch.py --neg-arm` | controlo **puro**: classifica uma fotografia falsa | 5/5 casos, nenhum processo, nenhum pixel |
| `_main/owner-screen-gate.py` | a outra metade: `webbrowser`/`os.startfile`/`tkinter`/`MessageBox`/`window.open` | 987 ficheiros, 0 achados |

O `console-window-gate.py` de regex e o seu baseline foram **aposentados**: era o mesmo critério lido
pior, com um baseline de contagem **0** (ou seja, nada a provar).

## 6. O que continua fora de alcance

- Um `.cmd` que o **dono** abre por duplo-clique abre consola — é a acção dele, não um script nosso.
- Uma janela que apareça e morra entre duas amostras do censo de 40 ms (o hook cobre a maior parte; o
  pior caso é uma janela de <40 ms que o hook perca. Não medido.)
- `verified` para esta entrada: precisa de uma corrida real da app por um verificador que não seja o
  autor. Fica **fixed, not verified**.
