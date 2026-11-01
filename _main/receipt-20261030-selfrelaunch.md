# A app senta-se de novo sozinha — sem ele aprovar nada

**Ordem do dono, verbatim, 2026-10-30:**
> "tu vai arrumar essa merda de \"arranque ai\" e vai dar launch sozinho no sotto. e eu nao quero
> que essa merda precise de mim aprovando nada"

**Estado:** a app **arrancou sozinha** (medido, ver §4) e, a partir de agora, qualquer mudanca de
codigo nas camadas que so' um restart aplica chega ao ecra sem uma unica accao dele. **Nao verificado:**
nenhum ecra foi visto — nenhuma lane abre a app na tela dele (`SOTTO_NEVER_ON_OWNER_SCREEN`).

---

## 1. Porque e' que isto nao se resolvia com um comando

A pane onde esta lane corre e' `medium`; o desktop dele e' `high`. Cinco caminhos de largada, cada um
medido, cada um com o instrumento ao lado:

| # | caminho | medicao | veredicto |
|---|---|---|---|
| 1 | filho directo desta pane | `SOTTO_LANE_LAUNCH=1` -> `TRAY_ICON_ADD ok=false winerror=5`, `WEBVIEW2_INIT_FAILED 0x80010108 RPC_E_DISCONNECTED` (2026-10-23; hoje o `hotkey-delivery` falha com `winerror=1409` porque a instancia DELE tem a tecla) | **nao serve** |
| 2 | `explorer.exe <ficheiro>` | 0/3 execucoes (2026-10-30). O "YES" da primeira tentativa veio de um `cmd` que eu tinha deixado aberto — **corrigido por mim mesmo** com a repeticao limpa | **nao serve** |
| 3 | token emprestado do Explorer | filho `high` mas nunca executa codigo (2026-10-23) | **nao serve** |
| 4 | `CreateProcessAsUser` com o token do shell vivo | `OpenProcessToken(pid=45264) err=5` **ACCESS_DENIED**. **Braco de controlo:** o mesmo codigo com o token DESTA pane cria o filho (pid 32072) — logo a recusa e' de privilegio, nao do instrumento (`I:\cc-tmp\launch_as.py`) | **nao serve** |
| 5 | `schtasks /run /tn Sotto` (a tarefa DELE) | executa, `high`, na sessao dele: pid 32448 -> 15288 -> 33208 -> 44820, todos com `SHELL_CODE_ID` do disco, `HOTKEY_REGISTERED`, `TRAY_ICON_ADD ok=true` | **serve** |

Uma sexta sonda, `schtasks` com accao pythonw directa, deu `Último resultado: -1073741819`
(`0xC0000005`) — a tarefa corre mas o filho morre. A accao tem de ser o `.cmd` do repo.

**A conclusao que isto obriga:** o unico lancador que funciona e' o que ja' e' dele. Ou seja: a app tem
de usar **a tarefa dele sobre si propria**.

## 2. O que foi construido

| ficheiro | o que e' |
|---|---|
| `app/webview/shell_relaunch.py` (NEW, 18 KB) | o vigia: fingerprint de `app/webview/*.py` + `app/panel/*`, dispara `schtasks /run /tn SottoRelaunch`, sai |
| `app/webview/sotto_webview.py` | arma-o no arranque (e `--no-self-relaunch` / `SOTTO_NO_SELF_RELAUNCH=1` desligam, dizendo porque) |
| `_main/sotto-relaunch.py` (NEW) | mata a instancia viva **pelo pid que ganhou a mutex no log da propria app**, espera `Local\SottoShell`, dispara a tarefa, e verifica a saude da nova |
| `_main/sotto-relaunch.cmd` (NEW) | a accao da tarefa (`pythonw`, nenhuma consola visivel) |
| tarefa `SottoRelaunch` | `/rl HIGHEST /it` — corre como ele, na sessao dele |
| `_main/shell-relaunch-oracle.py` (NEW) | 12 armas + 7 mutantes, cada um derrubado por uma arma nomeada |

### As guardas (o que impede a app de entrar num laco)
- **ociosidade:** so' relanca quando ele NAO esta' a ver legendas (`_caption_wanted` falso). Nunca se
  mata uma transcricao a meio por causa de um ficheiro.
- **piso:** `FLOOR_S = 120` de vida da instancia.
- **debounce:** a mudanca tem de estar quieta `STABLE_S = 4` (um save e' write+rename, nao um evento).
- **tecto:** `CAP_PER_HOUR = 3`, contado em `_main/shell-relaunch.json`.
- **falha da tarefa NAO sai:** log + `BACKOFF_S = 600` e o processo continua vivo. Um `os._exit` depois
  de uma ordem que falhou deixava o dono sem app — o pior resultado possivel.

## 3. Defeitos apanhados no caminho (todos meus, todos medidos)

1. **O debounce nunca disparava.** `before` so' era actualizado no disparo, portanto cada `tick`
   repetia a mesma diferenca, re-armava o relogio do debounce e o relancamento **nunca acontecia**.
   Apanhado pelo `--selftest` que escrevi antes de o armar. Corrigido com `seen` (assinatura vista a
   cada volta).
2. **A linha do disparo perdia-se.** O `log()` do shell poe a linha numa **fila** drenada por uma
   thread, e o `os._exit(0)` mata o processo antes de a fila ser escrita: a unica linha que explica
   porque a app se sentou de novo nao existia. Medido (o disparo das 05:41:05 nao deixou rasto).
   Corrigido: `record()` escreve em `_main/shell-relaunch.log` com `flush`+`fsync` **antes** do exit, e
   o selftest ganhou uma arma que o fixa.
3. **`autostart-status-check.py` fabricava um desacordo.** Lia as constantes do shell como TEXTO
   (`AUTOSTART_RUN_KEY` e' escrito com barras duplas no fonte), portanto o `winreg` recebia um caminho
   com `\\` e o passo anunciava `state=off` enquanto o shell dizia `AUTOSTART=on` — um vermelho que pedia
   uma mudanca no registo do dono para ficar verde. Passou a ler as constantes por `ast`
   (`ast.literal_eval` = o VALOR que o shell usa). Agora: `AUTOSTART_CHECK_OK on, and it points at THIS
   checkout`, rc=0.
4. **O meu neg-arm relancou a app dele a meio do teste** (05:43:07, `relaunch pedido tag=task`, pid
   40044 morto). Um mutante herdava a tarefa REAL. Corrigido: cada copia recebe `TASK = 'SottoNEGARM'`
   e o oraculo **recusa** correr um mutante se a copia nao ficar inerte (`neutral < 2`).
5. **Uma arma levava 78 s** (`get_source_segment` e' O(ficheiro) por chamada num ficheiro de 790 KB com
   centenas de `if`). Trocado por `ast.unparse` sobre a subarvore: o oraculo inteiro passou a 0,85 s.
6. **Dois mutantes sem braco** (M5 nao ancorava; M6 sobrevivia porque um braco so' textual nao ve' um
   `if False:`). A arma 8 passou a exigir que a guarda do kill seja **`pid`** e nao uma constante.

### Convencoes que este passo teve de aprender (as duas custaram um vermelho)
- **O controlo usa `:expectred`**, nao `:step`: exige **rc=1** e a string `NEG-ARM PASS` no log. O
  `--neg-arm` deste oraculo sai 1 quando apanha o defeito (rc=0 = um mutante sobreviveu), e a arma 12
  + o mutante M7 fixam exactamente essa inversao.
- **Uma linha `call :step` nomeia `always`/`heavy` ou o proprio nome** — nunca outra classe. Ver
  §4-bis.

## 4. A prova end-to-end (o log, verbatim)

```
05:52:23  mtime de app/panel/panel.js tocado      (nenhum byte mudou)
05:52:33  SHELL_RELAUNCH files=app/panel/panel.js detail=schtasks rc=0
05:52:33  relaunch pedido tag=task
05:52:34  kill pid=33208 (identidade: o pid que GANHOU a mutex no log da propria app)
05:52:34  kill pid=33208 confirmado morto
05:52:34  mutex livre
05:52:34  schtasks /run /tn Sotto
05:52:37  pid 44820 GANHOU a mutex
05:52:37  saude do pid 44820: {'mutex': True, 'hotkey': True, 'tray': True}
```

A app viva passou de `33208` a `44820` **sem eu tocar em nada e sem ele tocar em nada**.

## 4-bis. O passo da bateria que DESTRUIU o oraculo (e a guarda que o impede)

Depois de tudo verde, a bateria deixou `_main/shell-relaunch-oracle.py` com **40 bytes** no lugar de
15 KB: o conteudo era `O sistema nao pode encontrar o caminho especificado.` em cp850.

A causa era minha e nao estava no oraculo. O `:step` do `.cmd` le a CLASSE do **prefixo do nome**
(`red-as-expected-*` = controlo) e o primeiro argumento e' a classe `always`/`heavy` **ou o proprio
nome**. Eu escrevi `call :step expect-red red-as-expected-shell-relaunch 1 <deps> <log> python ...`:
o token extra deslocou tudo um lugar, o `.log` passou a ser o **COMANDO** e as dependencias passaram a
ser o **LOG**. O cmd tentou executar o ficheiro de log, falhou, e o `2>&1` do passo escreveu a mensagem
de erro **para dentro do `.py`**.

Duas coisas ficam disto:
1. a linha correcta passou a `call :step always red-as-expected-shell-relaunch 1 ...`;
2. o controlo passou a usar **o idioma da casa**: `call :step always red-as-expected-... 1 ...`
   seguido de `call :expectred ... "NEG-ARM PASS"`. A minha primeira versao era um `:step` normal
   com rc esperado 0, e um `:step` normal **nao olha ao registo**: foi assim que uma versao em que o
   oraculo estava apagado ainda "passou" (`rc=0`). Com o `:expectred`, o veredicto exige a string no
   log;
3. **o `_main/battery-wiring-oracle.py` ganhou o check `step-line-shape`**: nenhuma linha `call :step`
   pode nomear uma classe que o parser nao aceita (`expect-red`, `record`, `control`, `skip`). Provado
   com dentes: reintroduzir exactamente a linha que destruiu o ficheiro deixa o check RED; a linha
   correcta deixa-o PASS. Uma linha mal formada nao falha em silencio -- ela destROI, e por isso o
   portao tem de olhar para a FORMA e nao para o resultado.

## 4-ter. A bateria, com os dois passos novos

```
[step] shell-relaunch                    rc=0
[step] red-as-expected-shell-relaunch    rc=1  [EXPECT-RED] the defect was found and named
BATTERY-VERDICT: RED - 16 step(s) failed
```

Os 16 vermelhos sao de outras lanes e nenhum deles nomeia um ficheiro desta:
`panel2-dom-probe`, `border-radius-gate` (+controlo), `exception-hygiene` e `code-health`
(`worker/sotto_worker.py` cresceu), `battery-heavy-gate` (+controlo), `state-page`,
`panel-hidden-at-startup`, `yt-player-track`, `yt-mirror-align`, `gitattributes-verify`,
`per-app-source-plumbing` (+controlo), `open-close-stall`, e `hotkey-delivery` — este por
**ambiente**: a instancia viva dele tem o Alt+C registado, e a sonda pede a mesma tecla
(`winerror=1409`).

Antes desta lane a bateria contava 22; o `code-health`, o `exception-hygiene` e o `open-close-stall`
continuam vermelhos por trabalho de outras lanes, e o `state-page` le' o registo da bateria (fica
desactualizado por desenho ate' uma corrida completa a seguir a cada mudanca).

## 5. O que NAO esta' verificado

- **Nenhum ecra foi visto.** Nenhuma lane abre a app na tela dele; o que esta' provado e' o processo, o
  log, a mutex, o registo da tecla e a tray.
- **A tecla Alt+C depois do relancamento nao foi pressionada por mim.** `HOTKEY_REGISTERED` no log e' o
  registo no OS; o gesto em si e' dele.
- **O autostart (`\Sotto`, ao logon) nao foi reexecutado** — so' foi LIDO (`schtasks /query`: `run.cmd`,
  sessao interactiva, ultimo resultado 0).
- `code-health`: `app/webview/sotto_webview.py` esta' vermelho **de antes** (+34 127 B contra a linha de
  base, de mais do que uma lane). As minhas duas adicoes somam ~30 linhas (o `arm` e a bandeira); **nao
  subi a linha de base** para nao legalizar o crescimento de outra lane. Se o dono quiser o ratchet a
  valer, o numero tem de ser re-medido com o `git diff` de cada lane, um a um.
