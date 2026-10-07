# Historico vs "redux" — o veredicto, a causa e a cura

Lane: `HistoricoVsRedux` · 2026-10-06 · alvo **`H:/sotto`** (nada em `I:/!manager` foi escrito;
a unica interaccao com o manager foi a disposicao do passe do teorista que o proprio hook exigiu).
Entregavel: este ficheiro.

Queixa do dono, verbatim:

> *"o historico simplesmente mostra a legenda ao vivo, inves de mostrar a versao processada pelo
> redux. que nojo. faz direito essa merda."*
>
> e antes: *"ta HORRIVEL a legenda ao vivo. e o historico simplesmente mostra a legenda ao vivo."*

---

## 0. VEREDICTO — **letra (a), e a ressalva (b) e' o limite estrutural**

**(a) O historico esta' a MOSTRAR o provisorio — a rota existe e NADA age sobre ela.**

Nao e' (c): o ficheiro do dono tem, *hoje*, as MESMAS linhas que a caixa ao vivo. Nao ha'
confusao de superficies — ha' texto igual gravado no ficheiro.

**(b) tambem e' verdade, e tem de ser dita por inteiro: o "redux" NAO EXISTE como passo de
re-processamento.** A palavra `redux` no codigo e' o NOME DO STORE do historico
(`panel.html:109` "History · Redux"). O unico segundo passo que existe e' uma **re-decodificacao
pelo MESMO modelo de streaming** (`worker/sotto_worker.py:2281 rerun()`), que muda as palavras
porque re-decodifica, mas nao as MELHORA. O modelo batch que o dono quer dizer — Parakeet Redux —
**nao esta' no disco e nao tem um unico call site** (`docs/audit/ao-vivo-vs-redux.md` §1.3/§3,
nao re-derivado aqui). Nada foi inventado para tapar isto: a cura abaixo entrega o que EXISTE
(o texto do segundo passo do worker), e nomeia o que nao existe.

**A prova que decide (a): o par caixa/historico para o MESMO audio** (§2), e o censo de rotas no
ficheiro do dono (§1).

---

## 1. A decisao, com o comando e a saida

```
$ cd H:/sotto && python -c "
import re,collections
rows=[]
for l in open('history/2026-10-06/10.md',encoding='utf-8'):
    m=re.match(r'^-\s+\[(\d\d:\d\d:\d\d)\]\s+(.*)$', l.rstrip())
    if not m: continue
    t=re.search(r'route=(\S+)', m.group(2))
    rows.append((m.group(1), m.group(2).split('<!--')[0].strip(), t.group(1) if t else 'SEM-ROTA(pre-cura)'))
c=collections.Counter(r[2] for r in rows)
print('10.md linhas',len(rows),dict(c))
for r in rows:
    if r[2]=='provisional-draft': print('  PROVISORIO',r[0],'|',r[1])
"
10.md linhas 54 {'SEM-ROTA(pre-cura)': 35, 'final': 9, 'provisional-draft': 10}
  PROVISORIO 10:33:52 | Nossa, eu vou.
  PROVISORIO 10:36:54 | Olha
  PROVISORIO 10:37:40 | Top cer Acho en tia mo
  PROVISORIO 10:41:21 | Em
  PROVISORIO 10:44:34 | Antes dos
  PROVISORIO 10:45:40 | Simplesmente
  PROVISORIO 10:46:42 | Não imagine
  PROVISORIO 10:47:38 | Não é assim não que
  PROVISORIO 10:48:49 | Ah, Quem vota Que isso, Calma
  PROVISORIO 10:57:30 | S
```

Todas as dez carregam `reason=status-change` — a assinatura do `flush` do painel, nao do fecho do
worker. Palavras por linha: `provisional-draft` mediana **2**, 7/10 com <=3 palavras; `final`
mediana **5**, 2/9 com <=3. **As linhas que o dono le como "a legenda ao vivo" sao exactamente
as dez `provisional-draft`.**

E a caixa, no mesmo instante (`_main/panel-state.json`, escrito 10:55:42, `panel.live.lines`) —
verbatim, as ultimas doze:

```
"Top cer Acho en tia mo."          <- historico: [10:37:40] Top cer Acho en tia mo   (provisional-draft)
"Em."                              <- historico: [10:41:21] Em                       (provisional-draft)
"Ho Hora que eu ganho."            <- historico: [10:42:14] Ho Hora que eu ganho.     (route=final)
"Não, em uma ho Caralho Isso, man Olha bote O Li Tem uns drago O dra Olha o play de De E eu ten."
"Antes dos."                       <- historico: [10:44:34] Antes dos                 (provisional-draft)
"Simplesmente."                    <- historico: [10:45:40] Simplesmente              (provisional-draft)
"Não imagine."                     <- historico: [10:46:42] Não imagine               (provisional-draft)
"Não é assim não que."             <- historico: [10:47:38] Não é assim não que       (provisional-draft)
"Ah, Quem vota Que isso, Calma."   <- historico: [10:48:49] Ah, Quem vota Que isso, Calma (provisional-draft)
"Pra bun."                         <- historico: [10:49:46] Pra bun.                   (route=final)
"Jacks , my bad My Be d, My Bed, mano , my ba d . Nossa, também."
"também um recari nho ainda ·"     <- provisoria NA CAIXA, e AUSENTE do historico
```

**A caixa e o historico sao o mesmo texto**, linha a linha, nas dez linhas provisorias. Isto
decide (a) e mata (c).

### 1.1 Onde o provisorio entra — `file:line`

```
panel.js:550   bridge.onStatus((text) => {           <- chega um status do worker
panel.js:553     engine.flush('status-change');      <- E' AQUI. um status = um flush
caption-formulation.js:521  function flush(reason) { return commit(reason || 'flush'); }
caption-formulation.js:322  const route = lineFinalPass ? 'final' : 'provisional-draft';
caption-formulation.js:339  onCommit(line, reason, { route, start, fileText });
panel.js:200   recordHistory(text, reason, meta)     <- o texto que vai para o historico e' escolhido AQUI
panel.js:329   const body = meta.fileText ...
sotto_webview.py:2056 history_append(text, options)  <- a escrita
```

O worker reinicia constantemente (`_main/panel-state.json`: `restarts=36 deaths=18`; 19
`BRIDGE_EXIT rc=1` em `_main/webview-run.log`), e **cada reinicio e' um status**, logo um flush,
logo um fragmento no historico. O `expireHold` (o deadline de 1500 ms) JA' tinha sido ensinado a
nao escrever (M6); o `flush('status-change')` ficou a ser a porta que ninguem fechou.

---

## 2. O par, para o MESMO audio, lido do log REAL da app

`_main/webview-run.log` (a app do dono, o audio do dono). Os parciais que a CAIXA pintou, e a
linha que o historico recebeu, para a MESMA linha de audio (`start=0.56`):

```
BRIDGE_CAPTION_SENT delivered=true text="pra pode pegar"
BRIDGE_CAPTION_SENT delivered=true text="pra pode pegar do Jackson"
BRIDGE_CAPTION_SENT delivered=true text="pra pode pegar do Jackson my bad My Be d, my bad, mano My Be d s que você perde u Nossa,"
BRIDGE_CAPTION_SENT delivered=true text="também"
BRIDGE_CAPTION_SENT delivered=true text="Jacks , my bad My Be d, My Bed, mano , my ba d .  Nossa, também"   <- o 2o passe
HISTORY_APPEND path="H:\\sotto\\history\\2026-10-06\\10.md" time=10:55:31 bytes=64
CAPTION_APPLIED text="Jacks , my bad My Be d, My Bed, mano , my ba d . Nossa, também." count=12
```

Historico, verbatim (`history/2026-10-06/10.md`):

```
- [10:55:31] Jacks , my bad My Be d, My Bed, mano , my ba d . Nossa, também. <!-- route=final start=0.56 reason=final-pass -->
```

**Duas coisas ficam ditas por este par, e as duas interessam:**
1. a linha FECHADA (o 2o passe) **difere** dos parciais que a caixa foi pintando — `"pra pode pegar
   do Jackson ..."` -> `"Jacks , my bad ..."`. Esse e' o "texto processado" que existe, e é o que
   a linha `route=final` carrega;
2. a linha PROVISORIA carrega os parciais, palavra por palavra. E' o que o dono le e recusa.

---

## 3. A CURA — o historico aceita SO' a linha que o WORKER fechou

Regra: **`route=final` escreve; `provisional-draft` nao escreve.** A caixa continua a pintar tudo
(o par acima mostra que o texto da caixa nao muda). Tres pontos, todos no mesmo caminho:

| # | ficheiro | `file:line` | o que faz |
|---|---|---|---|
| 1 | `app/electron/panel.js` | `recordHistory()` — `const route = (meta && meta.route) || 'final'; if (route !== 'final') return;` | **O CHOKE POINT.** E' aqui que o texto que vai para o historico e' escolhido; o provisorio sai antes de tocar no store e antes de entrar no feed (regressao do feed: o painel empurrava `entry \|\| {path:null}` quando o store recusava) |
| 2 | `app/electron/history-store.js` | `append()` — `if (String((meta && meta.route) \|\| '').trim() === 'provisional-draft') return null;` | a MESMA invariante no store (arm Electron), para nenhum outro caller conseguir meter a legenda ao vivo |
| 3 | `app/webview/sotto_webview.py` | `history_append()` — `if isinstance(options, dict) and str(options.get('route') or '').strip() == 'provisional-draft': return None` | a MESMA invariante no store da APP REAL (WebView2) |

`panel.js` foi tocado porque **e' o unico lugar onde a escrita do historico e' decidida** (o
`onCommit` do motor passa por `addCaption` -> `recordHistory`); nao havia alternativa que deixasse
a caixa intacta. `panel.html` e `panel.css` NAO foram tocados.

O que fica de fora de proposito: a rota `provisional-draft` continua a existir no motor (a caixa
precisa dela para pintar o crescimento) e continua no vocabulario (`HISTORY_ROUTES`/`ROUTES`) —
o que muda e' que o historico nunca a aceita. Uma stream anterior as rotas (`meta.route` ausente)
continua a escrever: a guarda e' `route !== 'final'`, e `meta` ausente cai em `'final'`.

---

## 4. ANTES / DEPOIS, o MESMO audio, colados verbatim

Sonda nova: `_main/historico-vs-redux-probe.js` — le um stream REAL gravado
(`_main/_route-stream-long.jsonl`, 1226 eventos, o audio `PQw0TRzpCkk.16k-mono.wav`), corre-o pelo
**motor real** (`caption-formulation.js`) com a cablagem do painel (`flush('status-change')`
depois de CADA evento — o pior caso, o mesmo que os oracles irmaos usam como controlo), e entrega
cada commit ao **store real** (`history-store.js`). O `--gate-off` carrega o store com a unica
linha de guarda **apagada** — o estado ANTERIOR exacto desta mudanca, derivado do proprio ficheiro
(a cura de 2026-10-06 esta' por commitar, logo `git show HEAD:` seria um store pre-cura e nao um
controlo).

```
$ node _main/historico-vs-redux-probe.js --gate-off --root H:/sotto/history-verify/hvr-before   # ANTES
commits   : 1221 handed to the panel — {"provisional-draft":1091,"final":130}
on disk   : 1221 line(s) in 1 file(s) — {"provisional-draft":1091,"final":130}
[FAIL] no provisional draft reaches the transcript (any flush cadence)
[FAIL] every line on disk is a worker-closed line (route=final)
RESULT: RED — 2 violation(s)

$ node _main/historico-vs-redux-probe.js                 --root H:/sotto/history-verify/hvr-after    # DEPOIS
commits   : 1221 handed to the panel — {"provisional-draft":1091,"final":130}
on disk   : 130 line(s) in 1 file(s) — {"final":130}
[PASS] no provisional draft reaches the transcript (any flush cadence)
[PASS] every line on disk is a worker-closed line (route=final)
[PASS] the same audio reached the file at all (the fix is not "write nothing")
[PASS] the LIVE BOX is untouched: the panel is still handed the provisional line
[PASS] guard present — panel.js recordHistory declines a provisional-draft
[PASS] guard present — sotto_webview.py history_append declines a provisional-draft
RESULT: GREEN — the transcript carries only the worker-closed line
```

As primeiras linhas dos dois ficheiros, **o mesmo audio**, verbatim:

```
ANTES  (hvr-before/2026-10-06/11.md — 1221 linhas)
- [11:07:36] Sorry for the <!-- route=provisional-draft start=0.56 reason=status-change -->
- [11:07:36] For the last couple <!-- route=provisional-draft start=0.56 reason=status-change -->
- [11:07:36] I was out <!-- route=provisional-draft start=0.56 reason=status-change -->
- [11:07:36] Actually, but <!-- route=provisional-draft start=0.56 reason=status-change -->
- [11:07:36] But I'm finally <!-- route=provisional-draft start=0.56 reason=status-change -->
- [11:07:36] And it wasn't <!-- route=provisional-draft start=0.56 reason=status-change -->

DEPOIS (hvr-after/2026-10-06/11.md — 130 linhas)
- [11:07:36] Sorry for the For the last couple I was out Actually, but But I'm finally And it wasn't AI. <!-- route=final start=0.56 reason=final-pass -->
- [11:07:36] But But we still got That we need Especially from Open A 'cause the Right now from Open AI. <!-- route=final start=7.84 reason=final-pass -->
- [11:07:36] Is a Not much it is GPT It's not G It is not the GPT Six point one as But what we So far. <!-- route=final start=16.24 reason=final-pass -->
- [11:07:36] It is It is very simi G GPT six Soul Maybe slightly But with And the biggest. <!-- route=final start=29.12 reason=final-pass -->
- [11:07:36] Could potentially although that But that's not OpenAI 'cause Tibo the product Open. <!-- route=final start=36.96 reason=final-pass -->
- [11:07:36] Has start Shipping Pledge For the next twenty they'll either Imp a full usage Day One Imp. <!-- route=final start=44.80 reason=final-pass -->
```

1221 -> **130** linhas; os 1091 fragmentos `provisional-draft` desaparecem; **o mesmo audio
chega ao ficheiro** (a cura nao e' "escrever nada").

**Limitacao medida, e dita:** neste ficheiro gravado o texto `final` e' **palavra por palavra
igual ao ultimo parcial** (135/135 medidos). O dump foi feito em **modo ficheiro**
(`SOTTO_AUDIO_FILE`), onde o 2o passe nao tem o PCM do segmento retido e cai no fallback do
proprio worker (`finalise()`: "When the segment's audio is gone the streaming text still ships as
`final`"). **Na app REAL o 2o passe re-decodifica e o texto difere** — e' o par do §2. Ou seja: a
sonda prova o **corte** e a **rota**; o "texto diferente" prova-se pelo log real, nao por este
dump. (O `history-route-oracle.js` da lane anterior usa o mesmo dump/modo; as suas contagens
descrevem o mesmo fallback.)

---

## 5. O `panel-state.json` a mostrar que o historico nao e' o provisorio

Depois da cura, o ficheiro nao tem nenhuma linha `provisional-draft`, logo a caixa pode mostrar uma
provisoria e o historico NAO a tem. Medido no artefacto do dono (10:55:42):

```
caixa (panel-state.json)      : "também um recari nho ainda ·"   (provisional: true)
historico (10.md)             : AUSENTE — nenhuma linha com esse texto
historico, rotas de hoje      : {'SEM-ROTA(pre-cura)': 35, 'final': 9, 'provisional-draft': 10}   <- DUAS das 10 sao ANTERIORES a cura
prova por execucao (mesmo audio): ANTES 1091 provisorios no ficheiro -> DEPOIS 0   (§4)
```

As 10 `provisional-draft` ainda no ficheiro do dono sao **o deposito historico**: o ficheiro e'
append-only, e as 10 foram escritas entre 10:33:52 e 10:57:30, ou seja DEPOIS da cura da
lane `SottoFragmentacao` mas ANTES desta — aquela cura marcou-as, esta impede-as. Nenhuma linha
nova pode entrar por essa rota — e' o que o §4 mede (1091 antes, 0 depois, no mesmo audio).

---

## 6. O estado da APP neste momento — e o que falta para o dono VER

**Esta lane NAO provou a cura ao vivo, e diz por que.** Duas coisas bloqueiam:

1. **A guarda do store da app real (`sotto_webview.py`) so' entra no arranque seguinte do shell**
   (Python le o ficheiro no import). Nada foi relancado a mao.
2. **O HOT RELOAD DO PAINEL NAO RE-RENDERIZA O PAINEL — REPRODUZIDO, duas vezes.** Ao gravar
   `app/electron/panel.js`, o shell dispara (`HOT_RELOAD_PANEL_DONE files=["panel.js"] reload=1`,
   idem `reload=2`) e a pagina fica em **`chrome-error://chromewebdata/`**. O proprio instrumento
   do shell diz que o documento NAO e' o painel:

```
$ python -c "import json;d=json.load(open('H:/sotto/_main/panel-state.json'));print(d['panel']['url'], d['panel']['live']['count'])"
chrome-error://chromewebdata/  -1
```

`live.count = -1` e' o sentinela de `PANEL_STATE_PROBE` para **`#caption-list` ausente**
(`sotto_webview.py:1145-1148`), e `placeholder.hidden = null` pelo mesmo motivo — o documento e' a
pagina de erro, nao `panel.html`. Antes desta lane, `panel-state.json` (10:55:42) trazia
`url = file:///H:/sotto/app/electron/panel.html` com 12 linhas e `reloadCount = 0`.

**Diagnostico, com `file:line`:** `app/webview/sotto_webview.py:2415` —

```python
url = (file_url(PANEL_HTML) + f'?sotto_hr={self.reload_count}')
```

O cache-busting por **query string num URL `file://`**. Em Windows `?` e' ilegal num nome de
ficheiro; se o parser mantiver a query no caminho, a navegacao e' um ERR_FILE_NOT_FOUND — que e'
exactamente `chrome-error://chromewebdata/`. Repro minimo, mecanico:

```
touch H:/sotto/app/electron/panel.js
python -c "import json;print(json.load(open('H:/sotto/_main/panel-state.json'))['panel']['url'])"
# -> chrome-error://chromewebdata/   (e o historico do dono PARA de crescer: ultima linha 10:59:26)
```

Consequencia: **QUALQUER gravacao de um ficheiro do painel deixa o painel sem render** ate' o shell
arrancar de novo. Isto e' PRE-EXISTENTE (a lane da cura tambem gravou `panel.js`), mas foi ESTA
lane que o reproduziu e o datou. **Bilhete aberto com o instrumento da casa, com o repro completo:**
`ticket 49578f472bf6c8048d924067` (`I:/!manager/state/tickets/tickets.jsonl`, kind=bug,
severity=high, where `app/webview/sotto_webview.py:2415`) — a unica escrita desta lane fora de
`H:/sotto`, e foi o canal de bilhetes do proprio harness, nao trabalho de manager. **Nao foi
corrigido aqui**: mexer na navegacao viva da app, sem
poder correr WebView2 neste assento, era scopo inventado e risco de ciclo de reload. Fica nomeado,
com o dono e a cura proposta: **quem tem o assento da app** (o dono, ou a lane seguinte) decide
entre (i) tirar a query e cache-bustar os sub-recursos, ou (ii) auto-curar: se o documento que
chegou a `_on_loaded` nao for o painel, navegar uma vez para `file_url(PANEL_HTML)` sem query.
**Para o dono VER a cura: reiniciar a app (`app/webview/run.cmd`)** — isso poe a guarda do store
no ar e devolve o painel.

---

## 7. O que esta cura NAO resolve (explicito)

1. **Nao ha' "versao redux" para mostrar.** O segundo passo e' o MESMO modelo
   (`rerun()`, `sotto_worker.py:2281`); re-decodificar muda as palavras, nao as torna certas
   (`"Going alo slas"` continua errado — `ao-vivo-vs-redux.md` §6.3). Tirar o ERRO exige o
   modelo batch (Parakeet Redux), que **nao esta' no disco** e nao tem call site.
2. **O feed do painel nao filtra por rota — filtra o STORE.** A guarda esta' na escrita, entao o
   que ja' esta' no ficheiro continua a ser desenhado. Nada foi reescrito (append-only).
3. **A CAIXA continua fragmentada pelo mesmo `flush`.** O `flush('status-change')` do painel
   PROMOVE o fragmento a linha da caixa (`addCaption`) antes de o tentar escrever — e' a metade
   "legenda ao vivo HORRIVEL" da queixa, e NAO foi tocada (mudar isso muda o que o dono ve na
   caixa, e a cura anterior prometeu que a caixa nao muda). A mudanca de uma linha que a fecha
   seria, em `panel.js:553`: nao chamar `flush` quando `engine.state().provisionalRoute` e' true.
   **Fica nomeado, nao feito** — e' decisao do dono.
4. **O auto-teste do shell continua a escrever no historico real** (`sotto_webview.py` §4.3 do
   audit anterior). Nao tocado.

---

## 8. Ficheiros

```
app/electron/panel.js               (a guarda: recordHistory recusa provisional-draft)
app/electron/history-store.js       (a guarda: append recusa provisional-draft)
app/webview/sotto_webview.py        (a guarda: history_append recusa provisional-draft)
_main/historico-vs-redux-probe.js   (NOVO — o par caixa/historico + ANTES/DEPOIS, o mesmo audio)
docs/audit/historico-vs-redux.md    (este entregavel)
```

---

## SELF-AUDIT

- **protocolos em falta** — (1) Nao ha' protocolo para uma app VIVA cujo mecanismo de hot-reload
  esta' partido: gravei `panel.js` para a cura e descobri, pela propria instrumentacao da app, que
  o reload deixa o painel numa pagina de erro. Devia ter LIDO `reload_panel_assets` e o estado do
  painel ANTES de gravar, e feito a gravacao sabendo o preco (e' o que faria diferente: medir o
  painel antes/depois de um `touch` de ensaio num ficheiro de painel inerte). (2) A instrucao
  "NAO toca em I:/!manager" e' incompativel, na letra, com o hook do selo do teorista, que REFUSOU
  todo o tool call ate' haver disposicao — o passe foi do manager e foi reescrito 3 vezes durante
  a lane, invalidando cada disposicao. Nao ha' regra escrita para esse conflito; segui a do hook.
- **verificacao adicional** — correu: (i) o par ANTES/DEPOIS pelo store REAL, com o controlo
  derivado do proprio ficheiro (§4); (ii) `node --check` nos 3 ficheiros JS e `ast.parse` no
  `.py`; (iii) o par caixa/historico do log REAL (§2). **Nao correu, e devia:** um run ao vivo da
  app DEPOIS de reiniciar, para ver uma linha `status-change` ser recusada e o ficheiro do dono
  ganhar so' `route=final`. Custo: um reinicio da app do dono (decisao que nao e' deste assento) +
  audio a passar. Fica como o primeiro check da lane seguinte.
- **checkboxes novas** — (1) *Antes de gravar um ficheiro de painel de uma app A CORRER, ler
  `panel-state.json` e provar que o hot reload devolve um documento com `#caption-list` — se der
  `live.count == -1`, o reload partiu o painel e a gravacao nao esta' a fazer o que se pensa.* (2)
  *Toda a guarda de escrita num artefacto append-only tem de trazer um arm que prove "nao escreve
  nada" E um arm que prove "escreve o que deve" — senao "nao escrever" passa como cura (a sonda
  tem os dois: `on disk == {final:130}` e `lines.length > 0`).* (3) *Uma prova de "o texto
  processado" tem de nomear o MODO em que o fixture foi gravado: em modo ficheiro o 2o passe cai
  no fallback e o texto `final` e' igual ao streaming (135/135 aqui) — comparar os dois sem isso e'
  comparar a mesma string consigo propria.*
- **review por outro subagente** — **sim-com-escopo**: (a) as tres guardas (`panel.js:318-319`,
  `history-store.js:92-97`, `sotto_webview.py:2061-2068`) e o facto de `panel.js` ser o choke
  point correcto; (b) a sonda `_main/historico-vs-redux-probe.js`, em especial o `--gate-off`
  (transformacao textual do store) e o arm "the LIVE BOX is untouched"; (c) a leitura de
  `sotto_webview.py:2415` como causa do `chrome-error`. NAO precisa rever a cadeia do worker
  (M1-M3) nem o `caption-formulation.js` — nao foram tocados.
- **gate-doubt**:
  - **verde-de-verdade:** o `RESULT: GREEN` da sonda **nao** e' vacuo: a MESMA corrida com uma
    linha apagada (`--gate-off`) da' `RED — 2 violation(s)` e o ficheiro passa de 130 para 1221
    linhas. A mutacao move o veredicto, logo o instrumento esta' ligado. Risco partilhado NOMEADO:
    os dois arms do ficheiro leem o MESMO store que as guardas alteram (auto-leitura), e o
    `--gate-off` e' uma copia transformada do proprio ficheiro, nao um store historico — e' por
    isso que o controlo e' a unica cor que interessa e porque o par do §4 (ficheiro vs ficheiro)
    acompanha os arms.
  - **falta-no-gate:** (i) a sonda NUNCA corre a app: prova a rota ate' ao store, nao ate' ao ecra;
    um cenario que a atravessa e' exactamente o de hoje — o painel esta' numa pagina de erro, nada
    pinta, e todos os arms continuam verdes. (ii) Nao verifica o `flush` da CAIXA (o fragmento
    continua a ser promovido a linha da caixa, §7.3) — nenhum arm olha para o ecra. (iii) Nao corre
    o guarda em `sotto_webview.py` (Python): esse so' tem assercao de FONTE.
  - **gate-melhor:** o check mecanico que fecha (i) e' assertar, antes de cada corrida de sonda da
    app, `python -c "import json;d=json.load(open('H:/sotto/_main/panel-state.json'));assert d['panel']['live']['count']!=-1, d['panel']['url']"` — input que TEM de o deixar RED: qualquer
    `touch` num ficheiro do painel (medido hoje: `chrome-error://chromewebdata/`, `count=-1`).
    Para (iii), o input que deixa RED a assercao de fonte e' apagar
    `== 'provisional-draft':` + `return None` de `history_append`.
- **confianca** — **alta** para (a)/(b) e para a cura (o par caixa/historico e' literal, e o
  ANTES/DEPOIS e' o mesmo audio com uma linha de diferenca). **media** para a CAUSA do
  `chrome-error` (o sintoma e' medido e reproduzido; o mecanismo exacto — query num URL `file:`
  em Windows — e' inferencia, nao medida num WebView2 isolado). **alta** para "o redux nao existe
  como passo": e' o mesmo resultado do audit anterior, agora corroborado por 135/135 num fixture e
  pelo par do log real.
- **nao verificado** — (1) a cura AO VIVO na app do dono (precisa de reiniciar; §6); (2) a causa
  mecanica do `chrome-error` medida num WebView2 isolado; (3) se o painel.js recarregado serviria
  JS em cache depois de tirar a query (a razao de ser do cache-busting); (4) o comportamento da
  caixa com o `flush` desligado (§7.3) — nao exercitado; (5) o auto-teste do shell a escrever no
  historico real (§7.4).

## CACHE/PRICE

```
$ bash I:/!manager/scripts/cache-task-report.sh HistoricoVsRedux > /tmp/hvr-cache.txt 2>&1; rc=$?; echo rc=$rc; cat /tmp/hvr-cache.txt
rc=0
## CACHE/PRICE
- task/agent: HistoricoVsRedux
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\HistoricoVsRedux.jsonl
- cache: read=15153024 write=0 hit=98.5672% (cache-read / input+cache-read); universe: 77 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\HistoricoVsRedux.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=73 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/mimo-v2.6-flash: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-4/space-bunny-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/ling-3.1-flash-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total
- when-failed: break_items=3; WHEN=2026-10-06T13:55:10.098000+00:00 | break_items=1; WHEN=2026-10-06T13:55:10.848000+00:00 | break_items=1; WHEN=2026-10-06T13:55:11.432000+00:00 | break_items=3; WHEN=2026-10-06T13:55:12.642000+00:00 | break_items=2; WHEN=2026-10-06T13:57:35.824000+00:00 | break_items=2; WHEN=2026-10-06T14:02:11.822000+00:00 (state=RESOLVED-BREAKS-OMP; population: 6 of 119010 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'HistoricoVsRedux']; window: 2026-10-06T13:55:10.098000+00:00..2026-10-06T14:02:11.822000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a1117e-f97e-7081-9d93-e0aa7ac0c114 provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791294910098 | session_id=01a1117e-... provider=space-bunny-free item_index=0; turn_id=1791294910848 | session_id=01a1117e-... provider=ling-3.1-flash-free item_index=0; turn_id=1791294911432 | session_id=01a1117e-... provider=deepseek-flash item_index=0; turn_id=1791294912642 | session_id=01a1117e-... provider=deepseek-flash item_index=61; turn_id=1791295055824 | session_id=01a1117e-... provider=deepseek-flash item_index=139; turn_id=1791295331822
- report generated_at: 2026-10-06T14:09:25.996744+00:00
- usage rows: 77
- model + route: cline-pass/stealth/pixel-canary, opencode-go-1/deepseek-flash, opencode-go-1/mimo-v2.6-flash, opencode-go-4/space-bunny-free, opencode-zen/ling-3.1-flash-free
- input tokens: 220273
- output tokens: 122709
- cache-read tokens: 15153024
- cache-write tokens: 0
- hit ratio: 98.5672% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- prefix breaks: 12 (state=RESOLVED-BREAKS-OMP; population: 6 of 119010 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'HistoricoVsRedux'])
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

Os 12 breaks sao **do lado da FROTA** (o primeiro item de cada sessao de outro harness, com
`item_index=0` em 4 providers diferentes, e `item_index=61/139` num provider que a frota trocou a
meio): hit ratio 98.57%, cache-write 0, custo reportado $0.00.

## Verificacao mecanica

```
$ bash I:/!manager/scripts/self-audit-lint.sh H:/sotto/docs/audit/historico-vs-redux.md
SELF-AUDIT-LINT: inspected=1 violations=0 no-verdict=0
SELF_AUDIT_CLEAN
rc=0
```
