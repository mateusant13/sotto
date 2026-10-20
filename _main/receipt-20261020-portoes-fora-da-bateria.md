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

## O resultado (medido 2026-10-20, **re-medido** depois dos registos do dia)

Primeira medição, de manhã:

    instrumentos nomeados pelo AGENTS.md que EXISTEM : 40
      dentro da bateria                                :  8
      FORA da bateria                                  : 32

**Re-medição depois de 11 portões entrarem na bateria (regra 1 do AGENTS.md: um
grep é uma afirmação com prazo de validade):**

    instrumentos nomeados pelo AGENTS.md que EXISTEM : 42
      dentro da bateria                                : 19
      FORA da batalha                                   : 23

    dos 23 que faltam:
      IN-PROCESS (corridos pela 2a bateria, que nao lanca nada) :  6
      criam um processo (shell/worker/browser/audio)           : 17

Os 6 in-process que faltam:

    _main/app-target-oracle.py
    _main/canonical-producer-oracle.py
    _main/emit-queue-bound-oracle.py
    _main/panel-hidden-at-startup-oracle.py
    _main/panel-row-identity-oracle.js
    _main/run-cmd-exit-oracle.py

**A prova de "in-process" e empirica, nao estatistica:** a segunda bateria
(`_main/instruments-battery.mjs`) corre esses instrumentos dentro do processo e o
seu proprio resumo diz `launches=0`. A lista completa da segunda bateria e o
que separa "corre sem lancar nada" de "lanca o shell".

Os 17 restantes criam um processo e ficam fora **por desenho** — a bateria nao
pode abrir o shell do dono nem renderizar audio. O que faltava era dizer isso —
agora esta escrito no `AGENTS.md` (regra 6), para deixar de parecer uma omissao.

## A CORRECAO INICIAL (a lane C)

A lane C deu a cada um dos 8 portoes puros um `--neg-arm` **executado** —
mutantes textuais de ancoras unicas, com o protocolo de honestidade: uma ancora
que nao existe ou que existe mais do que uma vez e **decorativa** e o portao
recusa-se a conta-la; um mutante que carrega mas nao muda nada e reportado como
**SURVIVED**; o `--neg-arm` so da PASS se *todos* os mutantes declarados foram
aplicados **e** vistos.

O registo na bateria e do Lead, porque o `.cmd` e CRLF puro e e um ficheiro
com muitos escritores.

## A SEGUNDA BATERIA ESTAVA VERMELHA -- E O RUIMO TAPAVA O SINAL

`node _main/instruments-battery.mjs` dava **`SUMMARY: 122/145 ... failed=23`**.
O runner (linha 227) tratava **qualquer** `rc != 0` como falha, e as **11**
entradas com `--neg-arm` que saem **rc=1 POR DESENHO** (o braco negativo tem de
falhar) eram contadas como vermelhas. Os falsos vermelhos **tapavam** os reais.

Corrigido: um braco negativo tem de sair rc=0 ou rc=1 (rc>=2 = partido), uma
entrada normal tem de sair rc=0, e um crash ou um braco que diz no proprio
veredicto que esta partido tambem conta. Resultado medido: **0 falsos
vermelhos**, e 3 dos reais eram **ancoras velhas** (o codigo moveu-se, o
instrumento ja nao provava nada) — corrigidas.

**A LECAO, e e a regra que fica:** *um portao vermelho tem de ser CLASSIFICADO
antes de ser acreditado.* Uma ancora velha e higiene de repo; um *claim* rojo
e um defeito do produto. As duas coisas sao iguais ate se ler o que o
instrumento imprimiu.

## Verificação

`AGENTS.md` foi relido depois de escrever este recibo (regra 1 do próprio
`AGENTS.md`: *"a 'grep returned ZERO matches' é uma afirmação com prazo de
validade"*). Os números acima são desta medição, não de uma anterior.
