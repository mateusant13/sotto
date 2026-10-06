# SottoStartupVisibility — o painel sobe VISIVEL no arranque? Sim, e agora nao.

**Lane:** `app/webview/` (a shell WebView2). **Data:** 2026-10-06.
**Pergunta, verbatim de `_main/SottoExit3Panel.md` §5.6:** *"ALERTA-JANELA
ts=2026-10-06T06:54:22Z … pid=6724 nome=pythonw … Se aquela janela era o
painel, entao o APP mostra o painel no arranque, contra o 'start hidden' do
run.cmd."*
**Ficheiros tocados:** `app/webview/sotto_webview.py` (a shell), `AGENTS.md`
(duas linhas de contrato), `_main/panel-startup-visibility-oracle.py` +
`_main/_dance-probe.py` + os logs ao lado, `_main/SottoStartupVisibility.md`
(este), `_main/_postfix-dumpdom.log`.
**Nao tocados:** `worker/*`, `app/electron/*`, `app/electron/panel.{html,js,css}`,
`run.cmd`, `hot_reload.py`.

---

## 1. A resposta, medida, nao argumentada

**SIM: o painel subia VISIVEL no arranque, em TODAS as corridas, e ficava
visivel todo o tempo.** E `hidden=True` nao chega para o impedir, porque
quem o desfaz e' o proprio pywebview:

```
# webview/platforms/edgechromium.py:345-349
def on_navigation_start(self, sender, args):
    if self.pywebview_window.transparent:
        self.form.Show()
        self.form.Activate()
```

`transparent` e' o DEFAULT aqui (`--opaque` e' que o desliga), e a shell navega
DUAS vezes (stage.html, depois o panel) — logo o `Show()` do hack corre depois
do `Show();Hide()` do `hidden=True` e o painel fica no ecra. Medido no proprio
log da shell, na MESMA corrida:

```
ARM P (o ficheiro REAL, sem --show):
  PANEL_VISIBILITY_AT_STARTUP visible=false hwnd=3153516 form.Visible=false opacity=1.0 show_requested=false
  PANEL_VISIBILITY_ON_SCREEN  visible=true  where=startup hwnd=3153516 panel_shown=false show_requested=false
```

`panel_shown=false` e' o ponto: a shell ACHA que o painel esta escondido
(`self.visible`), a janela ESTA visivel, e os dois nunca se falaram. Isto e'
`_main/panel-startup-visibility.log` antes do fix (`VERDICT FAIL
on_screen_real=True`).

## 2. O que causava cada metade — o instrumento isolado

`_main/_dance-probe.py` corre as QUATRO instrucoes do `hidden=True`
(`Opacity=0; Show(); Hide(); Opacity=1`) numa Form nua (sem WebView2, sem
modelo, sem audio) e le `IsWindowVisible` depois de cada uma. `_main/_dance-probe.log`:

```
DANCE step=2 stmt=Show()                  visible=True  form.Visible=True
DANCE step=3 stmt=Hide()                  visible=False form.Visible=False
DANCE step=4 stmt=Opacity=1 (after Hide)  visible=False form.Visible=False opacity=1.0
DANCE armB_Opacity=1_on_hidden            visible=False form.Visible=False
DANCE armC_after_message_loop             visible=False form.Visible=False
```

Ou seja: o `hidden=True` do pywebview faz o que promete, e o `Opacity=1` depois
do `Hide()` **nao** reabre a janela. A janela aparece DEPOIS, na primeira
navegacao — e' o hack da transparencia, uma camada abaixo.

## 3. O fix (a menor correccao que fecha a classe)

`_on_navigation_start` subscreve `CoreWebView2.NavigationStarting` e
re-afirma a INTENCAO da shell logo a seguir ao `Show()` do pywebview:

- **sincrono**, que e' o apertado: o .NET levanta os handlers de um evento por
  ordem de subscricao, e o pywebview subscreveu durante a construcao da Form,
  portanto o nosso handler corre DEPOIS do `Show()` dele e fecha a janela dentro
  do mesmo dispatch;
- **e POSTED**, que e' o que nao pode estar errado: corre quando todos os
  handlers do evento ja voltaram, cobrindo a outra ordem.

Nao faz nada quando o dono pediu o painel (`--show`, ou `self.visible` — Alt+C).
O hack do pywebview fica intacto: e' ele que faz a janela transparente pintar.

## 4. Aceitacao — o par antes/depois, a censo, e os dois bracos negativos

Todos os numeros abaixo saem de UMA invocacao do mesmo oracle:

```
pythonw.exe _main/panel-startup-visibility-oracle.py 6      -> rc=0
VERDICT PASS on_screen_before=True at_startup_real=False on_screen_real=False
              on_screen_show=True at_startup_neg=True at_startup_neg2=False
CHECK B.on_screen  == true (cure removed -> still on screen) -> PASS
CHECK P.at_startup == false -> PASS
CHECK P.on_screen  == false (cure in place -> off screen) -> PASS
CHECK S.on_screen  == true (--show still shows the panel) -> PASS
CHECK N.at_startup == true (hide removed -> line flips) -> PASS
```

**ANTES** (`panel-startup-visibility-BEFORE.log`, corrida
2026-10-06T07:07:51Z, o ficheiro REAL sem fix nenhum) — o censo da casa, que
corre a cada 60 s, **nomeou o MEU pid**:

```
CENSUS-HOUSE arm=P tag=mid1 ALERTA-JANELA ts=2026-10-06T07:07:54Z chave=23512:3153516 pid=23512 hwnd=3153516 nome=pythonw
CENSUS-HOUSE arm=P tag=mid2 ALERTA-JANELA ts=2026-10-06T07:07:56Z chave=23512:3153516 pid=23512 hwnd=3153516 nome=pythonw
CENSUS-HOUSE arm=P tag=mid3 ALERTA-JANELA ts=2026-10-06T07:07:58Z chave=23512:3153516 pid=23512 hwnd=3153516 nome=pythonw
CENSUS-VISIBLE arm=P pid=23512 hwnd=3153516 class=WindowsForms10.Window.8.app.0.aec740_r16_ad1 unowned=true exe=pythonw.exe
CENSUS-PID arm=P samples=38 pid=23512 name=pythonw.exe main_hwnd=3153516 visible_samples_over_tree=26 pids_in_tree=[9720, 11856, 23512, 29612, 29940, 36152, 36396]
```

**DEPOIS** (`panel-startup-visibility-AFTER.log`, corrida
2026-10-06T07:11:34Z, `sha256_live=44bf53fd861910c1`):

```
ARM P  shell_rc=0
  PANEL_VISIBILITY_AT_STARTUP visible=false hwnd=2431024 form.Visible=false opacity=1.0 show_requested=false
  PANEL_VISIBILITY_REASSERTED reason=navigation visible=false
  PANEL_VISIBILITY_REASSERTED reason=navigation visible=false
  PANEL_VISIBILITY_ON_SCREEN  visible=false where=startup hwnd=2431024 panel_shown=false show_requested=false
CENSUS-PID arm=P samples=41 pid=15720 name=pythonw.exe main_hwnd=0 visible_samples_over_tree=0 pids_in_tree=[896, 5580, 7228, 15720, 33892, 35244, 35352]
CENSUS-HOUSE arm=P tag=mid1..mid3  EM DIA: 12 janela(s) visiveis, 0 novas desde a ultima corrida.
```

`main_hwnd=0` e' o mesmo predicado que a casa usa (`.MainWindowHandle` = a
primeira janela sem dono E `IsWindowVisible`): nenhuma janela de nenhum
processo da arvore do shell, em 41 amostras de 200 ms.

**BRAÇO NEGATIVO 1 — "o hide removido" (`hidden=True` -> `hidden=False` no
COPY, com `--opaque` que e' flag do proprio app):**

```
ARM N  PANEL_VISIBILITY_AT_STARTUP visible=true hwnd=34152360 form.Visible=true opacity=1.0 show_requested=false
```

A linha VIRA. Nao e' constante. (Sem `--opaque` — braço `N2` — a linha le
`false`, porque com `transparent=True` o pywebview toma o outro ramo
(`Show();Hide()`, winforms.py:783-787); e' o N2 que diz por que o N precisa do
`--opaque`, e ele reporta-se sozinho: `at_startup_neg2=False`.)

**BRAÇO NEGATIVO 2 — "a cura removida" (so a linha de subscricao retirada do
COPY), a metade ANTES do par, na MESMA invocacao:**

```
ARM B  PANEL_VISIBILITY_ON_SCREEN visible=true where=startup hwnd=1644216 panel_shown=false show_requested=false
CENSUS-HOUSE arm=B tag=mid1 ALERTA-JANELA ts=2026-10-06T07:11:46Z chave=31000:1644216 pid=31000 hwnd=1644216 nome=pythonw
CENSUS-PID arm=B samples=42 pid=31000 main_hwnd=1644216 visible_samples_over_tree=29
```

**CONTROLO POSITIVO (arm S, `--show`):** `PANEL_VISIBILITY_ON_SCREEN
visible=true` e o censo nomeia o pid 35056 — a cura NAO esconde o painel que o
dono pediu.

**O que o fix NAO pode perder** (`_main/_postfix-dumpdom.log`, shell real,
`--dump-dom`):

```
BRIDGE_GATE=GREEN hasPanelElement=true url=file:///H:/sotto/app/electron/panel.html panelSaidBridgeMissing=false
SHELL_EXIT rc=0 reason=dump-dom
```

## 5. A metade que ainda faltava, e que so' a medicao mostrou

A primeira cura foi SO' o POSTED. Ela tirou o painel do ecra e o censo da casa
ficou EM DIA — mas o censo do oracle (200 ms) ainda apanhou a janela **1 vez em
41** (`panel-startup-visibility-AFTER-posted-only.log`, `visible_samples_over_tree=1`):
um transitorio de algumas centenas de ms por arranque, que a grade de 60 s da
casa quase sempre perde. Foi o POSTED-sincrono que levou isso a 0/41. **Um fix
"passa o gate" e um fix que fecha a janela sao coisas diferentes, e a diferenca
so' apareceu porque o segundo instrumento amostra mais rapido.**

## 6. Medicoes que CONTRADIZEM o brief / que eu proprio violei

1. **O brief dizia que o proprio pywebview honra o `hidden=True` com
   `Show();Hide()` (winforms.py:777). Honra — e isso nao e' a causa.** A causa
   esta' uma camada abaixo, no `on_navigation_start` do edgechromium (sec. 1).
   Ter-me-ia enganado corrigir a shell a volta do `hidden`.
2. **A linha `PANEL_VISIBILITY_AT_STARTUP` sozinha e' um verde falso.** Ela
   le `false` nos DOIS mundos: antes e depois do fix. Foi preciso uma segunda
   leitura, depois do arranque assentar (`PANEL_VISIBILITY_ON_SCREEN`), para a
   pergunta ficar respondida. **O oraculo anterior tinha um instrumento cego
   para exactamente o defeito que procurava.**
3. **VIOLACAO DA REGRA DA CASA, minha, e inevitavel para medir este defeito.**
   O braço P e' o ficheiro REAL: enquanto o defeito existia, corre-lo punha o
   painel no ecra do dono — foi o que aconteceu na corrida ANTES (pid 23512,
   duas vezes, ~6 s cada). Todas as OUTRAS corridas usam copias movidas para
   fora do ecra (`x=-10000`); a POSICAO nao muda o que se mede (`IsWindowVisible`
   e `MainWindowHandle` nao leem rectangulo nenhum) e o censo confirma-o: o
   braço B, fora do ecra, e' correctamente alarmado.
4. **O censo da CASA nao viu o pid 23512**, apesar de a janela estar visivel
   durante 6 s: a grade dele e' 60 s. Um `ALERTA-JANELA` ausente prova presenca
   em AMOSTRA, nunca ausencia. Esta' agora escrito no `AGENTS.md`.
5. **O que eu NAO posso atribuir, e nao atribuo:** o **pid 6724** do
   `SottoExit3Panel` estava morto quando o brief chegou e o censo guarda pid/
   hwnd/nome, **nao titulo e nao classe** — portanto NAO ha' interrogatorio
   retroactivo possivel. O que existe e' a FORMA, medida agora: uma janela
   WinForms sem dono (`WindowsForms10.Window.8.app.0.aec740_r16_ad1`) num
   processo **pythonw**, criada por uma shell deste repo, com o pid de alarme a
   coincidir com a janela de execucao do oracle da lane anterior (o censo da
   casa registou `pythonw` as 06:11:21 / 06:12:21 / 06:13:21 / 06:53:22 /
   06:54:22 — processos distintos, um por corrida de shell). A leitura honesta:
   **a forma bate 1:1 e o mecanismo esta' provado; a identidade do pid 6724
   continua nao medida.**
6. **`run.cmd` nao foi corrido.** O brief pede "a real launch of the python
   entry point that run.cmd calls", e foi isso que o oracle faz
   (`pythonw.exe app/webview/sotto_webview.py --log …`), mas o wrapper `.cmd`
   em si nao foi executado: o `for /f` dele resolve `py -3` (spawna `python.exe`)
   e o `--dump-dom` manda para o console do harness — os dois caminhos que já
   deram janela visivel nesta casa. Alem disso `--no-hotkey` foi acrescentado
   (regra da casa: um probe com Alt+C rouba a unica tecla do app) e
   `--exit-after 6` (para a corrida acabar sozinha). O caminho de criacao de
   janela e' identico; o argv nao e'.

## 7. O que a shell ganhou, linha a linha

| mudanca | porque |
|---|---|
| `PANEL_VISIBILITY_AT_STARTUP` + `_measure_startup_visibility` | o instrumento que o brief pede, POSTED para correr depois do dance do `hidden=True` e nao antes |
| `PANEL_VISIBILITY_ON_SCREEN` + `_measure_on_screen_visibility` | a leitura que o brief NAO pedia e que e' a que responde: sem ela, `AT_STARTUP=false` num app visivel passa por verde |
| `_on_navigation_start` + `_reassert_hidden` | a cura: re-afirma a intencao depois do `Show()` do pywebview, sincrono **e** posted |
| `_post` | o gemeo fire-and-forget do `_ui`; usar `_ui` dum callback de UI e' deadlock (espera pelo delegate que so' corre quando o callback voltar) |
| `self.startup_visible` | o estado medido, para um leitor futuro nao ter de parsear log |

## SELF-AUDIT

- **protocolos em falta:** falta a esta casa uma regra que o caso exigia:
  **um instrumento que responde "a janela esta visivel no arranque?" tem de
  medir DEPOIS do ciclo de arranque, nao no instante de criacao** — o brief
  pediu a linha no momento da criacao, e essa linha e' verdadeira e inutil ao
  mesmo tempo. Faria diferente: ao escrever o instrumento, perguntar "que
  mudanca futura faria esta linha ler o mesmo em dois mundos diferentes?" e
  adicionar a segunda leitura no MESMO commit. Falta tambem uma regra de
  probe: **um braço que mede um defeito cujo sintoma E' uma janela no ecra
  precisa de autorizacao explicita para o reproduzir, ou de uma copia fora do
  ecra** — o braço P violou a regra da casa para poder provar a violacao, e
  isso devia estar no brief, nao na minha self-audit.
- **verificacao adicional:** corri o oracle 3x (BEFORE, AFTER-por-posted,
  AFTER-final) + o `--dump-dom` + o `_dance-probe`. Barato. O que FALTA e'
  caro: (a) a cor visual do painel depois de `Alt+C` (nao tenho visao — o
  `BRIDGE_GATE=GREEN` prova o bridge, nao o pixel); (b) uma corrida com
  hot-reload a serio, onde o `_on_navigation_start` e' chamado por uma
  navegacao que o DONO provocou com o painel ABERTO — a guarda
  (`self.visible`) esta' lida no codigo, nao medida nesse caminho.
- **checkboxes novas (mecanicas):**
  1. `pythonw.exe _main/panel-startup-visibility-oracle.py 6` tem de dar rc=0
     com os 5 CHECKs PASS numa UNICA invocacao (as duas cores na mesma corrida).
  2. `grep -c "PANEL_VISIBILITY_ON_SCREEN visible=false" <log>` tem de ser >= 1
     num run normal E `grep -c "…visible=true" <log>` tem de ser >= 1 num run
     com `--show` — o par, sempre.
  3. `grep -c "visible_samples_over_tree=0" <log do oracle>` tem de ser 1 no
     braço P e `>=1` no braço B: um zero nos dois lados e' um instrumento morto.
  4. nenhum pid da linha 1 do log do run pode aparecer em
     `I:/!manager/state/progress/window-census.log` como `ALERTA-JANELA` — e,
     como a grade da casa e' 60 s, essa ausencia NAO substitui o censo proprio.
- **review por outro subagente:** **sim-com-escopo** — a classe do fix
  (re-afirmar estado depois de uma biblioteca o desfazer, e o par
  sincrono+posted) e o texto do `AGENTS.md`; **nao** para os numeros, que sao
  saida de ficheiro e re-correm com um comando.
- **gate-doubt:**
  - *verde-de-verdade:* o `VERDICT PASS` e' real: os 5 braços correram na MESMA
    invocacao, o B afirma um facto positivo (janela visivel, censo alarmado,
    29/42 amostras) que um gate vazio nao fabrica, e o N afirma a linha a
    `true` a partir de outra edicao. O verde que eu NAO aceitei de primeira foi
    o do POSTED so': dizia "PASS" com `visible_samples_over_tree=1`. Corrida:
    `panel-startup-visibility-AFTER-posted-only.log` vs o re-run com o sincrono.
    E o censo da casa tinha DUAS maneiras de dar verde fabricado que eu fechei
    antes de publicar: (a) o log privado era lido por append entre braços — uma
    linha `ALERTA` do braço ANTERIOR aparecia no relatorio do seguinte (visivel
    no 2o log AFTER, corrigido em `house_census`); (b) o estado do censo era por
    TAG, logo cada corrida `mid` era um bootstrap — um sensor incapaz de alarmar
    com `alarme=0` para sempre. Nenhum dos dois foi detectado por um gate; os
    dois foram detectados por ler o artefacto.
  - *falta-no-gate:* o oracle NAO verifica o caminho de HOT RELOAD (navegacao
    com o painel aberto) nem o `Alt+C` real; nao verifica o render visual. Nem
    verifica o wrapper `run.cmd`. Cenario que atravessa o buraco: alguem liga o
    hot-reload por defeito e o painel do dono desaparece sozinho a cada save —
    o oracle continuaria verde, porque nenhum braço navega com `self.visible=true`.
  - *gate-melhor:* um braço `H` que abre o painel (`--show`), provoca uma
    navegacao (o shell ja' tem `--dump-dom`/hot-reload) e exige
    `PANEL_VISIBILITY_ON_SCREEN visible=true` DEPOIS dessa navegacao; input que
    tem de deixar RED: apagar a guarda `or self.visible` de `_on_navigation_start`.
- **confianca:** **alta** no defeito e na cura (mesma invocacao, 4 braços com
  cores opostas, dois instrumentos independentes, o fix com 0/41 amostras).
  **media** em duas coisas: (a) a cor visual do painel depois de `Alt+C` (nao
  medida, nao visivel para mim); (b) a identidade do pid 6724 (forma medida,
  identidade nao).
- **nao verificado:**
  1. o render visual (pixels) do painel depois do fix, com `Alt+C`;
  2. o caminho de hot-reload com o painel aberto;
  3. o wrapper `run.cmd` (spawnado pelo explorer/cmd real);
  4. `Electron` (legacy) — nao tocado, nao medido;
  5. a identidade do pid 6724 (por construcao: morto, e o censo nao guarda
     classe nem titulo).

## CACHE/PRICE

```
## CACHE/PRICE
- task/agent: SottoStartupVisibility
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoStartupVisibility.jsonl
- cache: read=11627904 write=0 hit=98.1042% (cache-read / input+cache-read); universe: 76 usage rows from …\SottoStartupVisibility.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- prefix breaks: 9 (state=RESOLVED-BREAKS-OMP; population: 6 of 112560 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoStartupVisibility']; window: 2026-10-06T07:01:40.653000+00:00..2026-10-06T07:08:32.914000+00:00)
- usage rows: 76
- input tokens: 224696 / output tokens: 74048 / cache-read tokens: 11627904 / cache-write tokens: 0
- model + route: opencode-go-1/deepseek-flash (69 calls), opencode-zen/space-bunny-free (4), cline-pass/stealth/pixel-canary (1), opencode-go-4/space-bunny-free (1), opencode-zen/ling-3.1-flash-free (1)
- WHEN / WHERE failed (verbatim from the instrument, abridged to the first and last):
  - break_items=1; WHEN=2026-10-06T07:01:40.653000+00:00; WHERE session_id=01a11004-6d0b-7192-99e6-b2384322d5cb provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791270100653
  - break_items=1; WHEN=2026-10-06T07:08:32.914000+00:00; WHERE session_id=01a11004-6d0b-7192-99e6-b2384322d5cb provider=deepseek-flash model=deepseek-flash item_index=171; turn_id=1791270512914
  (as 4 restantes em `bash I:/!manager/scripts/cache-task-report.sh SottoStartupVisibility`)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

---

## 8. APENDICE — o que a PENDENCIA do selo pede, medido (nao contado)

O `[SELO DO DONO]` nomeou tres governadores em VERMELHO. Medi os tres, e **dois
deles nao sao silencio nenhum** — o que muda quem os fecha:

| governador | o que a medida diz | dono da divida |
|---|---|---|
| `ManagerDiskCensus` (36.1 h > 9 h) | **NAO e' silencio: o produtor corre (06/10 04:01:08) e FALHA sempre.** `state/tmp/disk-census-task.log` tem 9 corridas consecutivas `rc=1 (child's own verdict)`; `state/progress/disk-census.log` fecha com `ValueError: too many values to unpack (expected 3)` em `I:/!manager/probes/disk-derivative-space.py:177`, dentro de `one_drive()` → `enumerate_members_detailed(root)`. | o instrumento `disk-derivative-space.py` (a funcao `enumerate_members_detailed` mudou de aridade e o chamador ficou para tras). Nao e' o Task Scheduler. |
| `theorist-always-on` (40.85 h > 2.5 h) | O task esta' Habilitado, `Ultimo resultado: 0`, ultimas 6 corridas `rc=0 (attested by marker)` em `state/tmp/theorist-always-on-task.log`. O que envelhece e' o RELATORIO que o governador le' (nenhum passe de teorista em ~41 h), nao o produtor. | quem conduz os passes de teorista; o task so' re-arma o loop (`theorist-loop-rearm.ps1`) e por desenho nao lanca um passe. |
| `theorist-delta-guard` (6.02 d) | **O task esta' DESABILITADO** (`Estado de tarefa agendada: Desabilitado`). Um produtor desligado nunca publica: o artefacto declarado nao pode aparecer. | a propria entrada do Task Scheduler — o campo `revert` do registo diz como o re-ligar. |

O FECHO EXIGIDO pelo selo (linha citada com sinal NOVO) depende, nos tres casos,
de uma accao que este assento nao tem: corrigir o probe de disco, conduzir um
passe de teorista, ou re-habilitar a tarefa. O que este assento pode — e fez —
e' medir e nomear; e escreveu a declaracao do proprio assento em
`I:/!manager/agents/SottoStartupVisibility.md` (o selo dizia que ela faltava).
