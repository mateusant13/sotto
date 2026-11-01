# Cápsula de incidente — o rato do dono travava com o Sotto aberto

Formato (Superharness, `runs/workflow-quality-loop-findings.md` §2): resultado **esperado** e
**observado**, **invocador exacto**, **revisão**, **configuração**, **reprodução**, **fronteira do
efeito**, **primeiro ponto de divergência**, **condições contribuintes** (plural — não uma "causa
raiz" conveniente), e uma acção correctiva com **estado final mensurável** e **teste de escape**.

## Identidade

| campo | valor |
|---|---|
| revisão | `c21f8a7` (árvore de trabalho, **não** commitada; 657 caminhos sujos de várias lanes) |
| artefacto do defeito | `app/webview/sotto_webview.py` — 758 679 B, sha256 `489202AD3355…EC3BA8` **antes** da cura |
| invocador | `app/webview/run.cmd` → `sotto_webview.py` → `OutsideClickWatcher.run` (thread do hook) |
| configuração | app normal do dono (não uma lane, não `--dump-dom`); `SOTTO_NO_PRELOAD` não posto; painel **nunca** mostrado nesse arranque |
| quando | 2026-10-23, 19:46 |

## Esperado vs observado

- **Esperado:** com o painel escondido o Sotto não toca no caminho de input do Windows. Nenhum
  hook global instalado.
- **Observado:** `OUTSIDE_CLICK_HOOK installed=true hook=748365515 thread=34768 type=WH_MOUSE_LL`
  às 19:46:41.606 — 22 ms depois de a app nascer — e `PANEL_VISIBILITY_ON_SCREEN visible=false …
  panel_shown=false` às 19:46:42.825. O cursor do dono passou a soluçar; **o resto do sistema não**.

## Reprodução (mínima)

Ler o log real do dono e ordenar as duas linhas por tempo:

```
Select-String -Path _main\webview-run.log -Pattern 'OUTSIDE_CLICK_HOOK|PANEL_VISIBILITY_ON_SCREEN'
```

Qualquer arranque em que o painel não é mostrado reproduz o estado: o hook exigia um painel
visível para fazer sentido e era instalado de qualquer maneira. (A reprodução *do cursor a
soluçar* exige um rato humano e não foi instrumentada — ver "o que não ficou provado".)

## Fronteira do efeito

Só o **cursor**: o callback Python corre na thread que instalou o hook, e todos os eventos do rato
passam por ele antes de chegarem às outras aplicações. CPU, disco, GPU, áudio e o worker estavam
**normais** (a medição de `_main/sotto-perf-log.py` já tinha mostrado que o stutter da máquina é
pequeno e não é do Sotto). Sob **Ctrl+Alt+Del** o Windows não entrega hooks de utilizador ⇒ o
cursor fica bom no secure desktop e volta a travar ao sair — que é exactamente o sintoma que o dono
descreveu, e o que descartou "carga do sistema" como causa.

## Primeiro ponto de divergência

Não é o `SetWindowsHookExW` em si — é o **momento**: a chamada estava no arranque do
`OutsideClickWatcher.run`, sem nenhuma condição. O primeiro ponto onde o sistema podia ter dito
"não" é essa linha (`if self._wants_hook():`), e não havia nada a montante que a guardasse.

## Condições contribuintes (não uma causa só)

1. **O hook servia a funcionalidade (fechar o painel com um clique fora) e foi instalado como se a
   funcionalidade estivesse sempre activa.** O estado certo (`armed`) já existia; não governava a
   instalação.
2. **Os testes do seam eram de ficheiros e de comportamento de decisão** (`_consider`), não de
   *existência* do hook — nada perguntava "está instalado agora?".
3. **O sintoma era invisível nos logs normais:** `installed=true` é uma linha informativa, e a
   linha que a contradiz (`visible=false`) é outra, 1,2 s depois. Ninguém as cruzava.
4. **A máquina do dono está degradada** (discos quase cheios), o que tornou plausível a hipótese
   errada ("é carga do sistema") e atrasou o diagnóstico.
5. **O AGENTS.md não tinha nenhuma regra sobre o caminho de input.** As regras existentes eram
   sobre lançar a app, matar processos e áudio.

## Acção correctiva e estado final mensurável

| acção | estado final mensurável |
|---|---|
| hook preguiçoso (só sob `_wants_hook()`) | `_main/input-path-oracle.py` C1a/C1b verdes; mutante `arranque-instala` derruba-os |
| estado libertado por **propriedade** (nenhum escritor pode mudar `armed`/`edit_mode` sem sincronizar) | C8 verde; mutante `edit-mode-nao-liberta` derruba-o |
| auto-cura de 5 s na thread do hook | C4 verde; mutante `sem-auto-cura` derruba-o |
| encerramento liberta hook **e** relógio | C7 verde; mutante `stop-nao-liberta` derruba-o |
| nenhum outro tipo de hook | C6 verde; mutante `hook-de-teclado` derruba-o |
| **cobertura por invocador** (9 enumerados, positivo **e** negativo em cada) | `_main/seam-coverage-oracle.py`: **9/9 PROVED**; 3 mutantes do inventário apanhados |

## Teste de escape (o que impede o mesmo defeito de voltar por outro caminho)

O inventário enumera **nove** invocadores e exige, por cada um, um controlo positivo no código real
e um negativo que derrube **aquele** braço. Um invocador novo (por exemplo, uma terceira via que
escreva `armed`) obriga a acrescentar uma entrada: a cobertura é impressa como `n/9` e um invocador
sem par bloqueia a entrega. O censo é verificado por mecanismo; a nota avisa que um censo que se
desactualiza *"can itself create a false green"*.

## O que NÃO ficou provado (declarado)

1. **Não houve corrida real da app com a cura** (a app está fechada; só o LEAD a lança, via
   `schtasks /it`). A afirmação "o rato não trava" é **estrutural**: o hook não existe com o painel
   escondido. A medição do cursor exige um humano.
2. **O auto-cura nunca disparou em produção** — provado por AST e por mutante, não por incidente.
3. **A cobertura é de 9 invocadores que EU enumerei.** A nota é explícita: mutantes provam
   afirmações sobre mutações seleccionadas, não a completude do inventário. O inventário é o ponto
   mais frágil e está escrito como tal.

## ADENDA 2026-10-30 — a acção correctiva endureceu: o hook foi REMOVIDO

O dono, verbatim: *"se esses hooks sao burros ou desnecessarios, remove. nao mantem nada q tu ta
achando q e pior"*. As cinco linhas da tabela acima descrevem a **disciplina** de um mecanismo que
nao precisava de existir; nao havia nada a disciplinar.

**O que saiu:** `SetWindowsHookExW`, `UnhookWindowsHookEx`, `CallNextHookEx`, `MSLLHOOKSTRUCT`,
`WH_MOUSE_LL`, `_install_hook`, `_uninstall_hook`, `_sync_hook`, `_sync_hook_now`, `_on_mouse`,
`_on_mouse_edit`, `WM_HOOK_SYNC` e o auto-cura de 5 s. `_main/input-path-oracle.py` C1 falha se
qualquer um voltar (por AST, na shell inteira).

**O que ficou no lugar** (mesmo trabalho, zero eventos de input a passar por Python):
`OutsideClickWatcher` = um `SetTimer` de **100 ms** que lê `GetForegroundWindow()` (fechar com um
clique fora) e, em edit mode, `GetCursorPos` + `GetAsyncKeyState(VK_LBUTTON)` a **25 ms** (arrastar
a faixa). O tick nao arranca sem `armed or edit_mode` (`_restart_timer` chama `KillTimer` primeiro e
desiste), e a decisao continua a ser `_consider`, com as guardas que ja' tinha.

| acção (nova) | estado final mensuravel |
|---|---|
| nenhum hook global, de tipo nenhum | C1 verde; mutantes `hook-volta` e `hook-de-teclado` derrubam-no |
| o tick nao arranca sem nada para vigiar | C2/C4 verdes; mutantes `regra-sempre` e `timer-sempre` derrubam-nos |
| esconder desarma; mostrar arma | C3/C9 verdes; mutantes `esconder-nao-desarma` e `show-nao-arma` derrubam-nos |
| edit mode a 25 ms, vigia a 100 ms | C6 verde; mutante `ritmo-unico` derruba-o |
| o tick nao fecha por si | C10 verde; mutante `tick-fecha-direto` derruba-o |
| encerramento mata o tick | C7 verde; mutante `stop-nao-mata` derruba-o |
| **cobertura por invocador** (12 agora) | `_main/seam-coverage-oracle.py`: **12/12 PROVED** |

O custo medido do caminho do tick: `_main/hook-cost-oracle.py` (o nome e' historico) mede
**0,0648 ms** por decisao a p99 -- a 10 Hz isso e' **0,065 %** de um nucleo, contra os 1000
eventos/s que o hook punha no caminho de input da maquina inteira.

**O que continua a NAO estar provado:** nao houve corrida real da app. Na falta de um hook nao ha
nada a medir no cursor -- mas tambem nao ha nada a medir porque nao ha mecanismo. O clique-fora
agora depende de o foreground mudar, o que e' o comportamento de qualquer popover do Windows; o
caso em que **nao** fecha (uma janela que nao ganha foreground ao ser clicada) fica declarado como
limitacao conhecida desta via.
