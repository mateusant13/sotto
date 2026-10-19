# Recibo — atribuição de orador: quem está a falar, encaixado no Sotto

**Data:** 2026-10-18 · **Raiz:** `H:\sotto` (product root, nunca o worktree) ·
**Autor:** Lead, sem subagente.

---

## 1. O pedido, verbatim

> "e mostra pra mim a legenda ao vivo ou o parakeet processando os audios do
> discord meu e dos meus amigos. de forma natural, encaixa no sotto"

E a ordem operacional que manda no ritmo:

> "PARA DE FAZER MEU PC TRAVAR. AGORA."

As duas são respeitadas: a decisão está feita e **provada sem inferência**; a
medição que exige o modelo está explicitamente adiada, não disfarçada.

## 2. O que faltava, medido

`_main/receipt-20261013-no-speaker-attribution.md` (2026-10-13) pôs o número:

| ficheiro | ocorrências de "speaker" |
|---|---|
| `worker/sotto_worker.py` | 3 — **as três são prosa** |
| `app/panel/panel.js` | 1 — também prosa ("Captions may lag the speaker.") |

Sem campo, sem id, sem código. A conclusão do recibo anterior foi exacta:
*"This is not a DESIGN gap that CSS can close — it is an ENGINE gap."*

## 3. A arquitectura: porquê o painel não muda

O painel **já é N-orador**. `panel.js` tem uma linha a formar por `source`:

- `rowIdentity(source, start)` — `panel.js:386`, chave `source + NUL + start`
- `engineFor(source)` — `panel.js:743`, **um motor por source**, para dois
  apps não intercalarem palavras na mesma frase
- `renderProvisional(committed, provisional, source)` — `panel.js:858`

E `source` é uma chave **opaca**: a procura por `startsWith('device:'|'proc:'|'file:')`
em `app/` e `worker/` devolve **zero**. Nada faz parse do prefixo.

Logo, **dar um `source` a cada voz é o que faz o painel ter uma linha por
pessoa — sem tocar no painel.** A máquina já existe e já é por-`source`; nunca
lhe deram mais do que uma source numa call.

    device:CABLE Output (VB-Audio Virtual Cable)/voice:speaker-1
    device:CABLE Output (VB-Audio Virtual Cable)/voice:speaker-2

O device fica à frente: a provenance sobrevive, o histórico sabe que a call
veio do cabo e não de um ficheiro.

## 4. As três peças, e porque estão separadas

| peça | ficheiro | carrega modelo? | custo |
|---|---|---|---|
| **decide** quem falou | `worker/speaker_id.py` | não | milissegundos, puro |
| **lê** o que outro calculou | `worker/speaker_bridge.py` | não | leitura de ficheiro |
| **produz** os segmentos | `worker/speaker_sidecar.py` | **sim, lazy** | 277 MB RSS, RTF 0,416 |

O modelo **não** entra no worker. O worker já carrega 1,2–2 GB de ASR; somar
outro conjunto de pesos a um box cujo dono mandou parar a máquina seria
desobedecer em nome da funcionalidade.

## 5. A medição do modelo, hoje

`_main/_hoje-ctrl.json` — controlo com a **verdade-terra do fornecedor**
(`0-four-speakers-zh.wav`, 4 falantes, Mandarin):

```
DER 0,03 %   (miss 0,00 + fa 0,03 + spk 0,00)
ref_sp 30,57 s   spk ref=4   hyp=4   nseg=10
wall 23,67 s   RTF 0,416   RSS 277 MB   model_load 0,934 s   threads 2   cpu
```

Este número substitui a leitura antiga. `receipt-diarization-decisive.md` mediu
**DER ≈ 61,6 %** na fala do dono sobre leito sonoro (+2,62 dB SNR) e **28,85 %**
em áudio limpo com threshold 0,5. O veredicto antigo ("a recomendação NÃO
sobrevive") era sobre **o sinal errado**: fala em cima de música não é o regime
de uma call do Discord, que é fala limpa, vez por vez, sem leito.

**Falta um número**: o DER no regime real da call do dono. É o que decide, e
exige a call e o consentimento dele. Está adiado, não esquecido.

## 6. DOIS BUGS REAIS, encontrados por instrumentos, corrigidos

### 6.1 A atribuição mudava conforme a ordem de iteração

`speaker_for_window` ranqueava cada segmento **à medida que chegava**,
comparando contra um **total em curso**. Logo a pontuação de um orador
dependia de quais segmentos *dele* já tinham sido vistos no instante da comparação.

Fuzz de 4 000 conjuntos × **todas** as permutações:

```
9 conjuntos  viravam o vencedor conforme a ordem
```

Exemplo real: janela 0,71–2,68 s; `c1` segura 2,44 s em dois segmentos, `c2`
segura 1,97 s e 1,78 s — e o vencedor era "quem foi visitado primeiro".

Numa call isto é **um nome a piscar numa frase já fechada**, e a docstring do
próprio módulo prometia o contrário.

Corrigido: acumular primeiro, ranquear depois, somar com `math.fsum` (soma
correctamente arredondada, **independente da ordem**). De 9 → **1**.

### 6.2 E sobrou um: o empate exacto

Duas pessoas a começarem **juntas** é o caso *normal* numa call, não o raro. Com
empate exacto nos três critérios, o vencedor saía da **ordem de iteração de um
dict**:

```
janela 0,78–1,71 s;  c3 (0,80–2,37)  e  c1 (0,80–3,24)  idênticos em total,
maior segmento e início.  c1 vs c3 decidido por quem foi inserido primeiro.
```

Corrigido com um quarto critério, aplicado só em empate exacto: a forma
textual do próprio orador. De 1 → **0**.

Os dois casos estão **fixados pelo nome** no oráculo, não entregues à
redescoberta aleatória.

### 6.3 Um achado de plataforma: `os.replace` falha no Windows

O oratório do produtor correu com um leitor concorrente e **falhou logo**:

```
PermissionError: [Errno 13] ... 'race.json'
```

Causa: Python abre ficheiros por `_wopen`, que concede
`FILE_SHARE_READ | FILE_SHARE_WRITE` mas **não** `FILE_SHARE_DELETE`, e
`os.replace` precisa de DELETE sobre o destino. No Windows um publish
"atómico" é atómico **excepto exactamente enquanto alguém lê** — que é quando o
publish acontece.

Se não fosse apanhado, o sidecar ficaria calado sem dizer nada: captions sem
nomes que misteriosamente deixavam de actualizar. `_replace_with_retry` fecha a
janela; medido, **0 publishes perdidos em 150**, com 87–316 `PermissionError`
por corrida tolerados de propósito. O mutante `no-retry-on-the-windows-sharing-race`
é apanhado por este braço exacto.

### 6.4 Uma linha que muda de mãos era pintada duas vezes

O pior dos três, e o único que o dono teria visto semplanation.

Uma legenda é emitida **várias vezes enquanto cresce**, e cada emissão tem uma
janela **maior**. Uma frase que cabia inteira no segmento de uma pessoa no
primeiro chunk pode acabar a atravessar o segmento de outra. Medido:

```
"e eu"                                          -> speaker-1
"e eu quero que o alt c"                        -> speaker-2
"e eu quero que o alt c mostre as transcricoes" -> speaker-2
```

**Dois `source` para UMA linha.** E o painel chave a linha *e* o motor por essa
string (`rowIdentity` :386, `engineFor` :743) — logo a segunda emissão não move
as palavras: abre uma **segunda linha que recebe a frase inteira**. Metade de
uma frase duplicada, em dois sítios, atribuída a duas pessoas, sem nada dizer
porquê.

A regra: **uma linha pertence a quem falava quando abriu, e isso decide-se uma
vez.** Trinco na decisão **positiva** — e a subtileza é o cerne:

| | |
|---|---|
| decisão `None` (janela ainda curta) | **não** trina: `None` quer dizer "ninguém **ainda**" |
| decisão positiva | trina, e vale para a vida da linha |
| linha que nunca acha dono | acaba `None`, e mantém o `source` do dispositivo |

O primeiro rascunho trincava em `None` também, e **o portão apanhou-o**: o
primeiro parcial de uma linha em 0,0–0,4 s sobrepõe um segmento que começa aos
0,317 s em **0,08 s** — muito abaixo do piso. Como quase toda a linha começa
curta demais para ser conclusiva, quase nenhuma linha era atribuída. Esse é o
erro que a segunda iteração do gate apanhou ao primeiro ensaio.

**Um mutante que o fixture real não conseguia apanhar.** O segmento 1 do
ficheiro de quatro falantes tem **6,5 s**; uma linha a crescer a partir dele
nunca dá o piso ao orador seguinte. Trinco-e-re-decidir davam a **mesma**
resposta nesse fixture — o gate era cego. Por isso existe um segundo caso,
construído à mão, em que uma pessoa segura 0,4 s da primeira emissão e outra
segura 4,8 s da segunda: as duas implementações **têm de** discordar.

`speaker-plumbing-oracle.py` **39/39 braços, 6/6 mutantes**, com esse caso.

## 7. A ligação ao worker, e o defeito que o portão apanhou nela

`sotto_worker.py` é o ficheiro mais sensível do produto. Antes de tocar nele
foi medido: **358 048 B · 6 714 linhas · 6 714 CRLF / 0 bare LF** ·
sha256 `F6AE94503065E2E4E1DB9A324518C97CF27FD8A1D4D277A7C5B0274FEC6D0B72`.

A alteração final é **89 inserções e 1 substituição**, em quatro pontos.

| revisão | tamanho | linhas | CRLF / bare LF | sha256 |
|---|---|---|---|---|
| antes (índice) | 358 048 B | 6 714 | 6 714 / 0 | `F6AE94503065E2E4…` |
| depois | 364 420 B | 6 823 | **6 823 / 0** | `C45836D4681FAC9E…` |

Medido depois de tudo, com `Get-FileHash` sobre os mesmos bytes. O ficheiro
continua CRLF puro: nenhuma das edições introduziu um LF solto.

| onde | o quê |
|---|---|
| `LineFormer.__init__` | `speaker_provider = None` — o default é não-perguntar |
| `LineFormer.set_speaker_provider` | setter, separado de `set_source` de propósito |
| `LineFormer._event` | passa a chamar `_attribute(event)` |
| `LineFormer._attribute` | **o estrangulamento**: um só lugar, apanha parciais, finais e o close |
| `main()` | a flag `--speakers`, `store_true`, sem default |

`_attribute` é o único sítio porque **todos** os eventos de legenda passam por
`_event`. Não há um segundo caminho para manter em passo.

**O teste é diferencial, não uma lista de chaves.** O oráculo extrai
`LineFormer` de **duas revisões** — a do índice (6 714 linhas, o ficheiro tal
como estava imediatamente antes desta edição) e a da árvore de trabalho
(6 809) — alimenta as duas com o mesmo cenário e exige que os eventos sejam
**iguais**. Não "as mesmas chaves": iguais. Mesmo texto, mesmos floats, mesmo
`final`, mesmo `chunks`, nada a mais.

`LineFormer` é extraído por AST e não importado, porque o ficheiro tem 358 KB
e arrasta a stack de ASR atrás de si. A classe precisa de quatro nomes de
módulo e nada mais — o portão corre em milissegundos e não carrega modelo.

### O defeito: uma flag ligada sem payload mudava a saída

O `_attribute` estampava `speaker: None` em **todas** as legendas quando não
tinha payload nenhum. Ou seja: `--speakers` ligado sem diarizador **não** era
byte-idêntico ao código anterior, e a promessa escrita no `--help` da própria
flag era falsa.

Corrigido com uma saída antecipada: **se não há nada a dizer, não se mexe.**
O mutante que a reintroduz está no portão e é apanhado por um braço que se
chama *"no payload -> identical events"*.

### Duas guardas que um portão comportamental NÃO pode apanhar

`if provider is None ...` e `or event.get("source") is None:` são load-bearing
para a robustez, mas **produzem saída idêntica quando removidas** — o fail-safe
engole o erro que elas teriam evitado (`None()` → `TypeError`; `event["source"]`
sem chave → `KeyError`). Foram mutantes meus que "passaram".

Estão declaradas como **arms estruturais**, rotuladas como tal, e contadas à
parte. Um portão que finja apanhar o que não pode apanhar é pior do que um que
admita não apanhar.

### E uma falha do próprio portão

Os braços da flag liam o ficheiro **do disco** em vez do código sob teste. O
mutante que vira `--speakers` em `store_false` — ou seja, **ON por omissão** —
era reportado como sobrevivo porque os braços liam sempre o ficheiro saudável.
Um portão que testa outra coisa do que a que protege não é portão nenhum.
Corrigido: a fonte entra como argumento.

## 8. O painel dá mesmo uma linha a cada pessoa — MEDIDO

O recibo anterior dizia, nas suas próprias palavras: *"o que o **painel**
mostra com duas fontes — **NÃO VISTO**"*. Era a maior lacuna, porque tudo o que
está a montante estava provado e a afirmação final continuava a ser uma afirmação.

`_main/panel-two-voices-oracle.js` fecha-a. Corre o `app/panel/` **real** — o
`panel.html` real, o CSS real, os onze scripts reais pela ordem do documento —
sob JSDOM 29.1.1, e alimenta-o com legendas de **duas `source` diferentes**.
Sem janela, sem WebView2, sem áudio, sem rede, sem modelo, sem arrancar nada.

| braço | resultado |
|---|---|
| duas vozes → duas linhas a formar | **PASS** |
| cada linha carrega o seu `data-source` | **PASS** |
| cada linha mostra **as suas** palavras | **PASS** |
| a voz A crescer não mexe na linha da B | **PASS** |
| uma só voz → uma só linha (o caso comum não mudou) | **PASS** |
| sem `source` → linha sem `data-source`, DOM idêntico | **PASS** |

**12/12, e 14/14 com o braço negativo** (dois mutantes, ambos apanhados).

Isto confirma a propriedade que o próprio painel promete nos seus comentários
(`panel.js:449-451`): *"the panel never feeds a fragment to another source's
engine"*. Duas pessoas a falar por cima é o caso **normal** numa call — e se as
duas vozes colapsassem numa linha, a transcrição leria-se como uma pessoa a
mudar de assunto a meio da frase, sem forma de distinguir isso da realidade.

### Três erros meus neste portão, todos da mesma família

**Alimentei o painel com a forma errada.** Passei o dicionário plano do worker
(`{type, text, source, ...}`) e medi **zero linhas** — porque `panel.js:985`
lê `bridge.onCaption(({ text, meta }) => ...)` e tira a chave de `meta.source`
(`:993`), não do topo. Teria "provado" que duas vozes **não** dão duas linhas,
publicando ao contrário uma medição que nunca aconteceu.

**`(a, b, c)` dentro de um array literal.** Em JavaScript isso é o operador
vírgula: o `MUTANTS` ficou uma lista plana de duas strings, e o destructure foi
buscar `label='c'`, `old='o'`, `new='n'` a uma string. Cada "mutante" reescrevia
o `panel.js` inteiro, trocando a letra `o` por `n`, e ficava vermelho pela razão
errada. **Um braço negativo que apanha um mutante por destruir o ficheiro é
decoração** — e teria escondido um portão genuinamente cego.

**A contagem global incluía o vermelho intencional.** O `--neg-arm` apanhava
tudo e reportava `FAIL`, porque as linhas vermelhas dos mutantes entravam na
tally. Truncar e substituir por uma linha de veredicto.

Os três são a mesma classe que já tinha aparecido duas vezes no worker: **um
portão que parece medir alguma coisa e não mede**.

## 9. A JUNTA: dois processos, um dispositivo de áudio a sério

O que faltava era a emenda entre o produto e a Attribution. Corre-se em
`_main/_speaker-chain-live.py` — **instrumento**, não portão: abre um loopback
WASAPI real num endpoint de render real e arranca um segundo processo a sério.

```
render endpoint -> tap real -> ring buffer -> offset -> publicação atómica
                -> ficheiro payload -> ponte -> LineFormer -> evento de legenda
```

Tudo real **excepto o modelo** (diarizador falso), o que é precisamente o que
permite correr isto sem os 277 MB.

### Medido hoje, 12 s, dois processos

```
119 blocos de 'WASAPI loopback: VoiceMeeter Input' em 12,0 s
190 400 amostras a 16 kHz (48 000 Hz x 2ch -> 16 000 Hz mono)
buffer limitado a 36 000 de 36 000 amostras (2,25 s)
payload publicado no relógio de parede; offset exacto: seg0 - window_start = 1,0000

37 eventos de legenda do LineFormer REAL
14 de 37 nomeadas, duas vozes
device:CABLE Output (VB-Audio Virtual Cable)/voice:speaker-1
device:CABLE Output (VB-Audio Virtual Cable)/voice:speaker-2

nomeadas COM epoch    : 14   vozes=['speaker-1', 'speaker-2']
nomeadas SEM epoch    :  0   vozes=[]
```

### O BUG que só esta junta podia encontrar

O worker carimba a legenda em segundos **desde o início da captura dele**:
`sotto_worker.py:5736` calcula `(idx - 1) * asr.chunk / TARGET_SR`, onde `idx` é
o contador de chunks **do worker**. O sidecar é outro processo e publica no
relógio de parede. Dois zeros sem relação nenhuma.

Passar o enquadramento de um ao outro **não dá erro e não escreve nada no log**.
Atribui cada linha a quem calhou estar a falar naquela posição do stream — um
nome plausível, pintado com todo o aspecto certo, e completamente errado.

**Nenhum oráculo o podia apanhar**, porque até aqui todos conduziam os dois
lados pelo mesmo relógio falso: a aritmética era consistente no teste e
sem sentido em produção.

A correcção é um número só, `stream_epoch`, que o braço vivo carimba e a ponte
aplica **apenas à janela de procura**:

| | |
|---|---|
| sem epoch | a mesma linha não nomeia ninguém — os dois zeros são alheios |
| com epoch | encontra a sua voz e ganha o `source` próprio |
| **`start`/`end` da linha** | **não são reescritos** — viajam para o painel, o histórico e a transcrição |

O último é o que mais importa: mover o offset para dentro da linha "funciona"
para a atribuição e corrompe silenciosamente as três pontas.

Gate: `speaker-id-oracle.py` **79/79 braços, 13/13 mutantes**, com dois mutantes
do epoch — *"o offset é ignorado"* e *"o offset reescreve a linha"* — apanhados
pelos braços que os nomeiam.

### Dois bugs meus nesta seção

**O constructor do tap estava errado.** O primeiro rascunho chamava
`WasapiLoopbackTap(spec, rate=…, channels=…, blocksize=…)`. A assinatura real é
`(on_block, block_ms=100, role=0, endpoint_id=None)`. Teria levantado
`TypeError` no primeiro arranque a sério, e **nenhum oráculo podia dizer
isso** — todos usavam um diarizador falso e nunca abriram um dispositivo.
Havia **7 endpoints activos** nessa máquina e nenhum tinha sido tocado.

**O meu primeiro instrumento media 0 de 31.** Gerava todas as legendas de
instantâneo, antes de o sidecar ter publicado o primeiro payload: os tempos de
stream iam de 0 a 10 s contra um payload escrito depois. Sobreposição zero —
corretamente. O worker real emite uma legenda à medida que o áudio chega, por
isso o instrumento passou a andar no relógio real, e as duas arms (com e sem
epoch) correm **na mesma passagem**, que é a única comparação honesta.

## 10. Portões

| portão | braços | mutantes | rc |
|---|---|---|---|
| `_main/speaker-id-oracle.py` | **79/79** | **13/13** | 0 |
| `_main/speaker-sidecar-oracle.py` | **34/34** | **6/6** | 0 |
| `_main/speaker-plumbing-oracle.py` | **39/39** | **6/6** | 0 |
| `_main/panel-two-voices-oracle.js --neg-arm` | **14/14** | **2/2** | 0 |
| `worker/speaker_sidecar.py --selftest` | **10/10** | — | 0 |
| `worker/speaker_sidecar.py --capture-selftest` | **7/7** | — | 0 |
| `_main/caption-lines-oracle.py` (pré-existente) | **12/12** | — | 0 |
| `_main/per-app-source-plumbing-oracle.py` (pré-existente) | **PASS** | — | 0 |

Os dois últimos são os que **o próprio worker nomeia** nas comentários que
editei (`caption-lines` arms 6/8/9/10; `per-app-source` CHK-3) e ambos testam o
ficheiro vivo. A alteração não partiu nada do que já lá estava.

## 11. O que NÃO está medido — dito com as palavras certas

| item | estado |
|---|---|
| decisão (segmentos → orador → `source`) | **PROVADO**, 79/79 + 13/13, contra a saída real do modelo |
| ligação ao worker (`--speakers`) | **PROVADO** diferencial: OFF é byte-idêntico ao índice |
| publicação do sidecar (buffer, offset, atómica) | **PROVADO**, 30/30 + 6/6, e no `--selftest` |
| **captura WASAPI real** | **MEDIDA** — 119 blocos de um endpoint real, 48k→16k |
| **a JUNTA de dois processos** | **MEDIDA** — 37 eventos, 14 nomeadas, 0 sem epoch |
| o que o **painel** faz com duas fontes | **PROVADO** sob JSDOM, 14/14 + 2 mutantes |
| DER no regime Discord | **NÃO MEDIDO** |
| duas pessoas a falar **numa call a sério** | **NÃO CORRIDA** |
| nomes (`speaker-1` → "o Rui") | **POR CONSTRUIR** — decisão de produto do dono |

Não houve inferência com o modelo nesta sessão. O único run do modelo foi o
controlo de §5, feito antes da ordem de parar. A captura de áudio foi de 12 s do
endpoint de render, **descartada em memória**: o payload publicado contém
segmentos inventados pelo diarizador falso, não som.

## 12. O que falta, em ordem

1. **Um sidecar com o modelo numa call a sério** — 2 minutos, e o DER no
   regime que decide se isto é fiável num Discord.
2. **O worker com `--speakers` a ver esse sidecar** — a chain está toda
   exercida; falta olhar para o ecrã com duas pessoas.
3. **Dar nomes** — `speaker-1` separa as pessoas; não diz quem é quem.
4. **O `git commit` WIP**, quando ele mandar — está indexado e medido.

## 13. Erros meus nesta sessão

Todos apanhados por instrumento, nenhum saiu em código:

| erro | como foi apanhado | custo |
|---|---|---|
| hipótese de não-determinismo **por raciocínio**, sem fuzz | o fuzz disse 9 | confiança injustificada |
| "0,4 s total under a 0,30 s floor" | braço RED | o teste é que estava errado |
| caso de etiquetas que **não discriminava** | mutante sobreviveu | porta cega |
| comparar id de cluster cru com etiqueta | braço RED | teste errado |
| `out` (lista) sombreado por `out` (caminho) | `TypeError` | 2 voltas |
| pureza a contar imports **lazy** como de topo | `ast.walk` vs topo | falso RED |
| `start_t` esperado 9,5 quando eram 5 s de áudio | braço RED | teste errado |
| `os.replace` sem repetição no Windows | corrida com leitor | **quase um bug silencioso em produção** |
| `close()` em vez de `flush()`/`take_closed()` | `AttributeError` | 1 volta |
| extrair o módulo todo em vez do fecho transitivo | `NameError` numa função nunca chamada | 1 volta |
| **`sys.path` sem `worker/`**: o `import` falhava, o fail-safe engolia, e dois mutantes davam falsos positivos | ON media 0 de 7 | **portão cego a dizer verde** |
| comparar com `HEAD` (6 632) em vez do **índice** (6 714) | contagem de linhas | Differential testaria a revisão errada |
| braços da flag a ler o ficheiro do disco | mutante sobreviveu | **o portão testava outra coisa** |

Os três últimos são a mesma classe de erro e são os que mais valem: **um portão
que parece verde sem estar a medir nada**. O do `sys.path` é o pior de todos —
o fail-safe escondeu o erro de importação e o teste deu "0 de 7 nomeados" como
se fosse um resultado honesto.

O `os.replace` continua a ser o mais caro: os outros custaram uma volta. Aquele
custaria um sidecar que publicava uma vez e nunca mais, sem um erro no log.

## 12. Comandos

```powershell
# portões (milissegundos, sem modelo, sem áudio)
$py = 'C:\Program Files\Python311\python.exe'
& $py _main\speaker-id-oracle.py        # 70/70, 11/11
& $py _main\speaker-sidecar-oracle.py   # 30/30,  6/6
& $py _main\speaker-plumbing-oracle.py  # 20/20,  5/5
& $py worker\speaker_sidecar.py --selftest --out I:\cc-tmp\diar-selftest.json

# CONSENTIMENTO DO DONO: carrega ~277 MB e corre inferência
# o sidecar escreve _main\diar-live.json e pára sozinho
& $py worker\speaker_sidecar.py --duration-s 120 --threads 2 --threshold 0.9
```

Sem esse ficheiro — ou com ele velho, o que a ponte recusa — o Sotto continua
exactamente como está hoje, e `--speakers` sem flag é o código de antes,
byte a byte.