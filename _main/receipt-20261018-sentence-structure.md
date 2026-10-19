# Por que a legenda não tem estrutura de frase — e o que NÃO é a causa

Data: 2026-10-18. Pergunta do dono: *"nao to vendo a legenda ao vivo ter, ou palavras
q começam com letra maiuscula e etc. ou estrutura de frase correta. pesquisa como
fazer direito"*.

## A conclusão, primeiro

**O formatador está vivo e a funcionar.** A hipótese óbvia — "a passagem de
formulação nunca é chamada" — é **FALSA**, e prová-lo poupou umarewrite inútil.

## O que está medido

| pergunta | resposta | como |
|---|---|---|
| `formulate()` é chamado pelo painel? | **SIM**, via `SottoFormulation.createEngine` | `panel.js:748` |
| `commit()` existe e formula? | **SIM** — `formulateTokens(all)` | `caption-formulation.js:706` |
| O caminho do player (YouTube) também formula? | **SIM**, no `final` | `panel.js:1020` `engine.flush('external-final')` |
| As linhas ficam capitalizadas? | **SIM** | 3 das 4 linhas do screenshot começam por maiúscula |

## O que o screenshot realmente mostra

```
each while keeping their mos and environments.          <- recorta no topo do viewport
In sync interestingly the researchers only train the model with four players, but.
They demonstrated that it scale up to ten players withoutautional training so it kind of.
Learned the mechanisms of you know these multiplayer systems and they used something called.
```

Quatro defeitos, **um só dos quais é de formatação**:

1. `withoutautional` — o modelo colou duas palavras. **Erro de ASR.** Nenhuma
   regra de formatação pode corrigir isto sem inventar texto.
2. `their mos and` — palavra truncada (`mos`, provavelmente `most`). **Erro de
   segmentação** do worker, não de formatação.
3. `so it kind of.` — fragmento pendurado. **Erro de ASR**: o modelo não fechou a frase.
4. `..., but.` — vírgula antes de conjunção e ponto final num `but` solto. **Isto
   é de formatação** e é a única correcção honesta disponível sem inventar palavras.

O cabeçalho de `caption-formulation.js` já fixa o princípio certo:

> *"They invent no words: casing and one terminal mark are added; nothing is
> inserted mid-sentence."*

Logo: **não se escreve uma regra que "conserte" `withoutautional`.** Isso seria
mentir ao dono sobre o que ele está a ver.

## O que resolve 1, 2 e 3

Trocar o motor. `DEFAULT_WORKER_PATH` aponta para `worker/sotto_worker.py` (o
Nemotron, ~2 GB de RSS medidos). O Parakeet é `worker/redux_live.py`, tem caminho
ao vivo (`run_device`, `_candidates`), e foi medido a correr: **70 legendas, exit 0,
586 MB, `overruns=0` a janela/passo 3/3**. É uma flag, não uma reescrita.

## O que falta mesmo (único item de formatação)

Uma regra de **partícula terminal**: não emitir marca final quando a linha
termina numa conjunção ou partícula pendurada (`but`, `and`, `so`, `kind of`,
`you know`, `because`, `que`). `TERMINAL` (`caption-formulation.js:53`) só testa
`[.!?…]$` — não sabe que a linha *não* devia ter terminado.

Estado: **POR FAZER**, com oráculo e braço negativo. Registado aqui para que a
próxima volta não ataque o motor à procura de um bug de CSS.

## Por que isto importa para o resto

O dono naturalmente vai suspectar da formatação porque o defeito **parece** de formatação.
Duas vezes nesta sessão um instrumento meu deu a resposta errada com muita
convicção (o censo de designs que andou por `_fonts/node_modules`, e o oráculo da
rotação que afirmava `True` em todas as linhas). Este ficheiro existe para que
esta investigação não se repita.