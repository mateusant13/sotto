# FUSION CORE — a decisão entre o stream e o finisher (2026-11-04)

**Ordem do dono, verbatim:** *"implementa agora. testa, aprova, troca toda nossa stack por essa"*,
e sobre o âmbito: *"nao queremos a implementacao de detectar falantes ou algo assim. so' o core"*.

**O que esta lane entrega:** `worker/fusion.py` (o core de decisão de texto) e
`_main/fusion-oracle.py` (14 arms + 4 mutantes). **Não** há detecção de falantes, não há modelo,
não há áudio e não há I/O: a fusão recebe duas hipóteses do MESMO áudio e devolve operações de
edição. Nenhum outro ficheiro do repo foi tocado.

| ficheiro | bytes | linhas | `except ...: pass` |
|---|---:|---:|---:|
| `worker/fusion.py` | 19 698 | 467 | 0 |
| `_main/fusion-oracle.py` | 19 326 | 435 | 0 |

---

## 1. A tabela de decisão, como código

A tabela do plano está em `decide_span()` — uma coluna de alinhamento entra, um registo alvo sai:

```python
if kind == 'match':                       # MODELOS CONCORDAM
    if shown differs from stream:         #   ... e ambos discordam do ecrã
        return _rec(stream, 'substitute', 'corrected', both_models=True,
                    note='both-models-against-shown')
    return _rec(stream, 'agree', 'confirmed', both_models=True)

if kind == 'sub':                         # MODELOS DISCORDAM
    if vocab term on either side:
        return _rec(base, 'substitute', NEEDS_CONTEXT)      # contexto decide
    if nothing on screen yet:
        return _rec(refined, 'substitute', 'corrected')     # finisher corrige
    if shown == refined:      -> 'corrected'                # já está corrigido
    if shown == stream:
        if shown confirmed-by-both and revealed:
            return _rec(shown, 'substitute', 'confirmed')   # ESTABILIDADE
        return _rec(refined, 'substitute', 'corrected')     # provisória: corrige
    # ecrã, stream e refined: TRÊS candidatos distintos
    return _rec(shown, 'substitute', NEEDS_AUDIO)           # o áudio decide
```

`stream-only` (o finisher omitiu a palavra) mantém a do stream como `provisional`, e uma palavra
revelada+confirmada pelos dois não é tocada. `refined-only` (o finisher ouviu uma palavra que o
stream não tem) é uma **inserção**, tratada em `Fusion.feed` (§3). Frase terminada
(`sentence_end=True`) passa `provisional` / `needs-audio` / `needs-context` a `offline-review`.

A regra da estabilidade é uma constante nomeada, com a razão escrita ao lado:

```python
REVEALED_REPLACE_RULE = 'REVEALED-REPLACE-ONLY-IF-FINISHER-DISAGREES-AND-NEVER-BOTH-CONFIRMED'
REVEALED_REPLACE_REASON = (... o dono lê a frase a meio e o texto a mudar debaixo dos olhos
  é pior que uma palavra errada ... mas quando stream e refined concordam contra o ecrã,
  há duas fontes independentes contra uma, e o ecrã perde.)
```

## 2. API

```python
f = Fusion(vocab=['Sotto', 'nemotron'])          # gancho de contexto (opcional)
r = f.feed(stream_text, refined_text)            # -> ops, words, stability, held, review
f.reveal()                                       # o que já foi pintado (liga a estabilidade)
f.reveal(upto=7)                                 # só as 7 primeiras
f.text(); f.words(); f.history                   # estado
```

`feed` devolve: `ops` (ordenadas, `{'op':'replace','span':[i,j],'text':X}` ou
`{'op':'append','text':X}`), `words` (`index`, `word`, `decision` ∈ {agree, stream-only,
refined-only, substitute}, `stability` ∈ {confirmed, provisional, corrected, needs-audio,
needs-context, offline-review}, `both_models`, `revealed`, `changed`, `note`), `text`,
`stability` (veredicto da linha, o estado mais fraco), `needs_audio`, `needs_context`,
`held` (inserções seguradas, §3), `review`, `rule`, `vocab`.

Duas chamadas `feed` iguais devolvem `ops == []` — a idempotência é uma arm (A1, A10, A13).

## 3. Duas decisões de desenho que a medição obrigou

1. **O alinhamento não é um diff de índice.** `align_pair()` é Needleman–Wunsch determinístico
   (match +2, substituição −1, buraco −1; empate resolvido sempre do mesmo lado). Com um diff por
   índice, um buraco no meio desloca tudo o que vem depois — o mutante M4 (§5) é exatamente isso e
   a arm `gap` apanha-o.
2. **A inserção do finisher é montada por BOUNDARY, não por posição na lista.** Cada palavra guarda
   o `src` (índice na hipótese do stream) e cada inserção guarda o `boundary` (o próximo índice do
   stream). Sem isso uma inserção aprovada deslocava a decisão de todas as palavras seguintes (foi
   medido: `vai`/`ser`/`interditada` passavam a `substitute` sem razão) e o `feed` seguinte
   duplicava a inserção.

## 4. As arms — `python _main/fusion-oracle.py`

Saída real da corrida desta lane:

```
identicas              PASS  texto='hoje o dia ta lindo' ops2=0
substituicao-fim       PASS  texto='nao sei se ele vai'
substituicao-meio      PASS  ops=[{'op': 'replace', 'span': [3, 4], 'text': 'ao'}]
revelado               PASS  a=True b=True c=True
tres-candidatos        PASS  stability='needs-audio'
vocabulario            PASS  context=[1] score=True
duplicadas             PASS  texto='nao nao vou'
vazio-curto            PASS  a=True b=True c=True d=True
unicode                PASS  texto='coração de mãe'
duzentas               PASS  ops=5 spans_ordenados=True idem=True
gap                    PASS  decisoes=['agree', 'agree', 'stream-only', 'agree']
fim-de-frase           PASS  stability='offline-review' review=True
insercao               PASS  ops=[{'op': 'replace', 'span': [6, 6], 'text': 'o rio'},
                                  {'op': 'replace', 'span': [19, 20], 'text': 'para'}] idem=True
insercao-segurada      PASS  ops=[{'op': 'replace', 'span': [19, 20], 'text': 'para'}] held=['o', 'rio']
VERDICT: PASS (14/14)
rc=0
```

O que cada arm exige, e não o texto que procura:

| arm | exige |
|---|---|
| `identicas` | 5/5 `agree`+`confirmed`, primeiro `feed` = `append`, segundo = `ops []` |
| `substituicao-fim` | a troca é a ÚLTIMA palavra e as 4 anteriores ficam intactas |
| `substituicao-meio` | `replace [3:4] 'ao'`, vizinhos intactos |
| `revelado` | (a) confirmada pelos dois + no ecrã → **não** muda (`stability-lock`); (b) revelada mas provisória → o finisher corrige (`finisher-corrects-revealed`); (c) os DOIS contra o ecrã → o ecrã perde (`both-models-against-shown`) |
| `tres-candidatos` | ecrã/stream/refined todos diferentes → `needs-audio`, `ops == []`, nenhum vencedor, `rule` citado |
| `vocabulario` | termo do `vocab` num span em disputa → `needs-context`, a palavra do stream fica, e um termo que NENHUM modelo produziu nunca aparece |
| `duplicadas` | `nao nao` sobrevive; o finisher a omitir uma repetição não apaga a que está no ecrã |
| `vazio-curto` | `('','')`, `('oi','')`, `('','')` a seguir e `('','tudo bem')` |
| `unicode` | `reunião/começa/às/três` intactos; `nao` vs `não` é substituição; `coração de mãe` confirmed |
| `duzentas` | 200 palavras, 5 edições dispersas → 5 `replace`, spans ASCENDENTES, texto certo, 2.º `feed` `ops []` |
| `gap` | `eu vi ele ontem` vs `eu vi ontem`: `ele` = `stream-only` provisória e `ontem` continua `agree` |
| `fim-de-frase` | `sentence_end=True` → a provisória passa `offline-review`, veredicto `offline-review` |
| `insercao` | `o rio` entra por `replace [6,6]`, `vai` continua `agree`, 2.º `feed` `ops []` |
| `insercao-segurada` | com o texto no ecrã a inserção é SEGURADA (`held == ['o','rio']`), o texto não é empurrado, e `pra → para` (substituição numa provisória) continua a ser corrigida |

## 5. O braço negativo — `python _main/fusion-oracle.py --neg-arm`

Cada mutante é escrito numa **cópia** do módulo (diretório temporário, apagado no fim); a tabela
exige que a arm DESIGNADA caia. Contagem medida: **4/4**.

```
NEG-ARM estabilidade-removida    CAUGHT
NEG-ARM refinado-ganha-ao-ecra   CAUGHT
NEG-ARM escolhe-vencedor         CAUGHT
NEG-ARM sem-alinhamento          CAUGHT
NEG-ARM VERDICT: PASS (4/4)
NEG-ARM: PASS
rc=1
```

| mutante | o que faz | arm que cai |
|---|---|---|
| `estabilidade-removida` | apaga o `if shown_ok and shown_up:` do ramo `substitute` | `revelado` |
| `refinado-ganha-ao-ecra` | no ramo `needs-audio`, escolhe o token do refined | `tres-candidatos` |
| `escolhe-vencedor` | no ramo de vocabulário, escolhe o refined em vez de etiquetar | `vocabulario` |
| `sem-alinhamento` | troca `align_pair` por emparelhamento por índice | `gap` |

Cada mutante foi corrido e as arms que caem foram lidas uma a uma (não só a designada): `revelado`;
`tres-candidatos`; `vocabulario`; `gap` (e, com o alinhamento em índice, também `revelado`,
`duplicadas`, `fim-de-frase`, `insercao`, `insercao-segurada`). O `--neg-arm` devolve **rc=1** quando
apanha os quatro (a convenção da casa de 2026-11-03 para um `:expectred`) e imprime `NEG-ARM: PASS`;
um mutante que escape devolve rc=0 e a frase `NEG-ARM: FAIL`.

## 6. Exemplo trabalhado — par real de pt-BR

A frase é a do conjunto partilhado de 2026-11-04
(`_main/fixtures/stack-compare/reference.json`, 25 palavras, referência **PROVISÓRIA**) com as duas
hipóteses de uma engine que derruba o `rio`:

```python
ref = 'radio anunciou que a ponte sobre o rio vai ser interditada na proxima segunda-feira os moradores precisam de um caminho alternativo para chegar ao trabalho'
hyp = 'radio anunciou que a ponte sobre vai ser interditada na proxima segunda-feira os moradores precisam de um caminho alternativo pra chegar ao trabalho'
```

Corrida real, duas variantes (o stream primeiro; o finisher depois):

```
== não revelado                              == revelado
passo1 ops = [append <hyp inteira>]          passo1 ops = [append <hyp inteira>]
       verdict = provisional                        verdict = provisional
passo2 ops = [replace [6,6]  'o rio',        passo2 ops = [replace [19,20] 'para']
              replace [19,20] 'para']               held = ['o', 'rio']
       verdict = provisional                        verdict = corrected
       words[6..8] = o/refined-only/provisional,    words[6..8] = vai/agree/confirmed,
                      rio/refined-only/provisional,                ser/agree/confirmed,
                      vai/agree/confirmed                          interditada/agree/confirmed
       texto = <ref>, 25 palavras                   texto = <hyp com 'para'>, 24 palavras
terceiro feed ops = []                       terceiro feed ops = []
```

Leitura: com a linha ainda não pintada a fusão **insere** `o rio` (o finisher ouviu-o, o stream
não) e corrige `pra → para`, e o texto final é exatamente a referência. Com a linha já no ecrã, a
inserção é **segurada** — empurrar `vai ser interditada` para a direita seria mexer no que o dono
está a ler — mas `pra → para` continua a ser corrigido porque essa palavra era provisória e nunca
foi confirmada pelos dois, que é a exceção escrita em `REVEALED_REPLACE_RULE`. Os dois casos são
idempotentes: o `feed` seguinte não emite nada.

## 7. Portões da casa

- `python _main/undefined-names-oracle.py` → `UNDEFINED-NAMES GREEN -- 18 ficheiros de producao,
  0 nomes usados e nunca definidos`, rc=0.
- `python _main/code-health-oracle.py` → o ficheiro novo é medido como
  `NEW worker/fusion.py 19698 B 467 linhas (fora do baseline)`, abaixo de
  `MAX_NEW_BYTES = 120000`,
  `except ...: pass` **0** e `global` **0** no ficheiro novo. O `CODE-HEALTH VERDICT FAIL (rc=2)`
  desta corrida vem de `app/webview/sotto_webview.py` (`bytes 1092249 → 1100034`,
  `lines 20445 → 20592`, `defs 121 → 126`), um ficheiro que esta lane **não tocou** — `git status`
  mostra-o limpo, o `HEAD` tem `1079442 B` e a working tree `1100034 B` (CRLF), ou seja nenhum dos
  dois bate a baseline: ela é de um commit anterior ao `7744bb8`. Não é regressão desta lane e não
  foi "corrigida" por baixar o portão.
- `python -m py_compile worker/fusion.py _main/fusion-oracle.py` → OK.

## 8. O que NÃO está feito, e é de propósito

- **Não está ligado ao painel.** O ticket desta lane é o core (módulo + oráculo + recibo) e a ordem
  é "touch nothing else"; ligar `Fusion.feed` ao `caption-formulation.js` / `history-store.js` é o
  passo de integração de quem sustenta esse ficheiro. A superfície para isso são os `ops`, que já
  são um diff aplicável por cima do que o store tem.
- **Não há diarização** e não há caminho para a acrescentar aqui: a decisão é entre duas
  transcrições do mesmo áudio, sem noção de falante.
- `needs-audio` **não decide** nada: marca o span e devolve-o em `result['needs_audio']`. Quem tiver
  o áudio (o finisher, uma terceira passagem) é que escolhe; o módulo nunca escolhe por ele.
- `align_pair` é O(n·m) em memória; para uma linha de legenda (dezenas de palavras) é irrelevante,
  para um documento inteiro não é a ferramenta.
