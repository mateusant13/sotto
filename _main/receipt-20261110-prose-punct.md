# RECIBO — a marca que o motor não deu: fecho de linha por prosa + pausa

Medido nesta árvore em 2026-11-10. Todo número tem o comando ao lado.

## 1. O card e o defeito medido

Card do dono: *"historicos desde as 15h de hoje: melhorar a qualidade da transcricao a
custo barato"* e *"pontuacao pt-BR: NENHUMA das 37 linhas stable de 17.md fecha com marca"*.

Verificado hoje em `history/2026-11-09/17.md`:

| | medida |
|---|---|
| linhas no arquivo | 63 |
| `reason=stable` | **37** |
| `stable` com marca terminal | **0** |
| linhas sem marca terminal | 43/63 |

Causa: `worker/punctuation_model.py:supported_lang` só aceita `en*`, e o modelo
multilíngue foi **recusado por medição** (2,4 GB + torch, `I:` a 4,8 % livre). Ou seja: a
marca não vem de um modelo — tem de vir de outra coisa.

## 2. A cura: `app/webview/prose_punct.py`

Função pura `close_line(text, gap_s)`. Acrescenta `.` **somente** quando as duas evidências
concordam:

* **PROSA** — a linha foi FECHADA pela política do worker, logo é unidade fechada; e a
  última palavra **não** é conector (artigo, preposição, conjunção, auxiliar). As listas
  são pt-BR **e** inglês porque o arquivo dele é bilíngue na mesma hora de transcrição
  (medido: `17.md` tem as duas línguas).
* **PAUSA** — a diferença de relógio até a linha **seguinte** alcança o piso de frase que
  esta casa já mediu: `SENTENCE_MIN_MS = 600 ms`
  (`worker/punctuation_prosody.py`, 2026-11-05: a menor pausa de fim de frase mediu
  **773 ms**, a maior de fim de oração **440 ms**). O oráculo **B** lê esse número por
  `ast` e exige que os dois ficheiros concordem.

Nunca se inventa: `?` e `!` (nenhuma fixture desta casa tem pergunta, e a direção do F0
mediu 3 subidas / 2 descidas — moeda ao ar), nem marca depois de parênteses/colchetes
aberto, nem depois de aspas que continuam abertas.

## 3. Onde corre, e por que NÃO na legenda ao vivo

No caminho de **leitura** do histórico (`SottoShell._history_entries`), que alimenta o
painel, a busca e o export.

O stream anda do **mais novo para o mais antigo**, portanto quando entrega uma linha já viu
a seguinte — a pausa está medida **sem esperar nada**. Na legenda ao vivo seria preciso
esperar a linha seguinte para saber a pausa, e um texto que espera é exatamente o atraso
que o dono proíbe.

O arquivo em disco continua o **registo cru** do que o motor disse: a marca é de leitura,
e por isso vale também para as linhas já gravadas (retroativo, sem reescrever nada).

## 4. Efeito medido no arquivo dele

Mesma passagem, mesmo ficheiro (`history/2026-11-09/17.md`), função real:

| | antes | depois |
|---|---|---|
| linhas com marca terminal | 18 | **57** |

Amostra do resultado: `'Mmm.'` · `'Nossa, bate na parede.'` ·
`'De sacanagem com seu computadorum de reparo no FUFA.'` ·
`'Que agora é show.'`

As 6 linhas que continuam sem marca são as que a regra **recusa** — cauda num conector
(`"...com o"`, `"...like I'm just a"`) ou sem pausa medida (a linha mais nova de cada
bloco). Recusar é a resposta: um ponto ali seria uma afirmação que o áudio não fez.

## 5. O portão

`_main/prose-punct-oracle.py` — 16 arms sobre o código REAL:

| arm | o que exige |
|---|---|
| A1 | marca terminal existente → identidade |
| A2 | vírgula na cauda → substituída pelo ponto |
| A3/A4 | pausa curta (300 ms) / pausa ausente → **sem** marca |
| A5/A6 | conector na cauda (pt / en) → **sem** marca |
| A7 | parênteses aberto no fim → identidade |
| A8 | o ponto entra antes de aspas a fechar |
| A9 | vazio → identidade |
| A10 | pausa exatamente no piso (600 ms) já fecha |
| B | o piso é o mesmo número dos dois ficheiros (`ast`) |
| C1-C4 | o stream REAL (`_history_entries` extraído por `ast`) sobre um root TEMPORÁRIO |
| D | o arquivo em disco não foi tocado |

```
$ python _main/prose-punct-oracle.py            -> 16 arm(s), 0 failure(s)   rc=0
$ python _main/prose-punct-oracle.py --neg-arm  -> 16 arm(s), 8 failure(s)   rc=1
   NEG-ARM: PASS -- 8 arm(s) vermelhas: A3, A4, A5, A6, A7, A9, C2, C4
```

O negativo **muta o código** (repõe um fecho que não olha a pausa), não a expectativa — a
classe que esta casa já pagou uma vez nesta mesma rodada.

## 6. Pins e portões de apoio

* `_main\_audit-verify-all.cmd` = **342605 B**, **3990 CRLF** / 0 bare LF,
  sha256 `84375166E142874EA74437002B63406E33D2BCD32C2A96D12B263FEDBA7DDF8E`.
* `battery-wiring` PASS `ligados=181 sem_passo=108 populacao=289` (`new-unwired PASS`).
* `battery-record-pairing` 446 passos / 446 nomes com registo / 0 achados.
* `battery-class` PASS arms=3.
* `undefined-names` GREEN — 19 ficheiros de produção, 0 nomes usados e nunca definidos.

## 7. O que NÃO está verificado

* **A tela do dono.** A prova é o stream real sobre um root temporário e o arquivo dele
  lido pela função real; a app aberta por ele não foi tocada. `fixed, NOT verified`.
* A pausa é medida pelo **relógio de fecho da linha** (o único que o arquivo carrega), não
  pelo fim do áudio — logo é um **teto** do silêncio, e infla com a latência de escrita.
  Um teto só pode produzir marca onde havia pausa real; a leitura conservadora (identidade)
  é que protege o resto.
