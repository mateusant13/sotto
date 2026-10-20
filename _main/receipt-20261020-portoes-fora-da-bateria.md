# Recibo 2026-10-20 — o censo dos portões que estão FORA da bateria

## O que este recibo é

O `AGENTS.md` nomeia **instrumentos como a PROVA** das suas próprias
afirmações ("oracle: `_main/xxx-oracle.py`", "Gate for the whole directory:
`node _main/scope-leak-oracle.js`"). A regra do repo, escrita no próprio
`AGENTS.md`, é:

> *"um portão fora da bateria apodrece em silêncio — foi assim que o braço
> `head` do primeiro apodreceu"*

Este recibo mede **quantos** desses portões estão fora da bateria. Não é uma
opinião: é um censo, com o instrumento e a data.

## Instrumento

O censo é feito por código, não a olho:

1. `AGENTS.md` é lido e extrai-se a lista de instrumentos nomeados
   (`_main/<ficheiro>`);
2. `git ls-files` diz quais desses ficheiros existem de facto;
3. o conteúdo de `_main/_audit-verify-all.cmd` é lido e diz quais estão
   **registados na bateria** (o nome do ficheiro aparece lá);
4. cada instrumento ausente é classificado como **PURO** (só lê ficheiros) ou
   **LANCA** (lança o shell, o browser, ou toca áudio) por leitura do código.

Data da medição: **2026-10-20**. Instrumento: leitura directa do `AGENTS.md`,
do `.cmd` e dos instrumentos.

## O resultado

    instrumentos nomeados pelo AGENTS.md que EXISTEM : 40
      dentro da bateria                                :  8
      FORA da bateria                                  : 32

    dos 32 que faltam:
      PUROS  (leem ficheiros; cabem na bateria)        : 10
      LANCA  (abrem o shell/browser/audio)             : 22

**Os 22 que lançam estão legitimamente fora**: a bateria não pode abrir o
shell do dono nem renderizar áudio. O que falta é dizer isso — hoje não está
dito em lado nenhum, e por isso parece uma omissão.

**Os 10 puros é que são a lacuna real.** Nove deles são portões (o décimo,
`_main/mute-audio.py`, é a *biblioteca* — o portão é `mute-audio-oracle.py`, e
esse já está na bateria):

    _main/_pythonnet-show-shadow-test.py
    _main/lang-id-oracle.py
    _main/model-spec-oracle.py
    _main/panel-flash-contradiction-oracle.py
    _main/per-app-source-plumbing-oracle.py
    _main/redux-live-contract-oracle.js
    _main/scope-leak-oracle.js
    _main/vad-option-probe.py
    _main/word-split-oracle.py

O caso mais gritante é o `scope-leak-oracle.js`: o `AGENTS.md` (regra 10)
chama-lhe **"Gate for the whole directory"** das folhas de tema — e não
corria em nenhuma bateria. É o portão que apanhou o vazamento de `--font-serif`
e `--w-op` para os temas 1/2/4/5.

## O que se fez

A lane C (`_main/lang-id-oracle.py`, `_main/model-spec-oracle.py`,
`_main/scope-leak-oracle.js`, `_main/panel-flash-contradiction-oracle.py`,
`_main/per-app-source-plumbing-oracle.py`, `_main/redux-live-contract-oracle.js`,
`_main/word-split-oracle.py`, `_main/vad-option-probe.py`) deu a cada um deles
um `--neg-arm` **executado** — mutantes textuais de âncoras únicas, com o
protocolo de honestidade: uma âncora que não existe ou que existe mais do que
uma vez é **decorativa** e o portão recusa-se a contá-la; um mutante que
carrega mas não muda nada é reportado como **SURVIVED**; o `--neg-arm` só dá
PASS se *todos* os mutantes declarados foram aplicados **e** vistos.

O registo na bateria é do Lead, porque o `.cmd` é CRLF puro e é um ficheiro
com muitos escritores.

## A regra que fica

* Um portão que julga **ficheiros** entra na bateria.
* Um portão que **lança** o shell, o browser ou o áudio, não entra — e passa a
  estar nomeado no `AGENTS.md` como "fora da bateria, e porquê", para deixar
  de parecer uma omissão.
* Um portão fora da bateria **precisa de um `--neg-arm` executado** na mesma
  altura em que é criado. É o que distingue um portão de uma decoração.

## Verificação

`AGENTS.md` foi relido depois de escrever este recibo (regra 1 do próprio
`AGENTS.md`: *"a 'grep returned ZERO matches' é uma afirmação com prazo de
validade"*). Os números acima são desta medição, não de uma anterior.
