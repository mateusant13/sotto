---
name: postmortem-sotto
description: Camada DESTE repo sobre a skill canonica de postmortem, com a mecanica de debug obrigatoria para defeito nao-trivial. Usa-se depois de um incidente contido ou de um quase-acidente; com o bug activo manda o bug-hunt.
---

# Postmortem e mecânica de debug — a camada do Sotto

O **método** é o da skill canónica:

```
I:\!manager\.agents\skills\postmortem\SKILL.md
```

Este ficheiro não a repete. Carrega só o que é decisão deste repo — e é aqui que vive o detalhe que o
`AGENTS.md` não deve carregar (ele é auto-carregado em todas as sessões).

## Gatilho

Pelo **estado**, não pela gravidade:

- **Sim:** incidente contido/resolvido, ou quase-acidente que ia chegar ao dono e foi apanhado.
- **Não:** bug activo -> `docs/bug-hunt.md` (11 passos) e a skill `diagnosing-bugs`. Diagnóstico vivo
  não se mistura com postmortem: um postmortem escrito no meio do incidente é um palpite com timestamps.
- **Não:** edição trivial (typo, uma linha, um número). Sem cerimónia.

## Mecânica de debug obrigatória (defeito não-trivial)

Vale quando o sintoma não aponta para a linha, ou quando a correcção pode estar a esconder outra coisa.
Sete passos, cada um com o que o recusa:

1. **Repro vermelho no invocador REAL** — o método que a app chama, não uma imitação. Teste que chama
   uma função que a app não chama não prova nada. *(Recusa: "reproduzi num script que imita".)*
2. **3 a 5 hipóteses ranqueadas e falsificáveis ANTES das sondas** — cada uma com a medição que a
   derrubaria. Uma hipótese sem o que a mata é conversa.
3. **Uma variável por sonda** — duas mudanças ao mesmo tempo não dizem qual delas mudou o resultado.
4. **Minimizar (delta-debug)** — reduzir entrada/mudança até à mais pequena que ainda falha, e **provar**
   que tirar uma peça mata a reprodução.
5. **Replay diferencial** — o mesmo caso com e sem a correcção, **no mesmo instrumento**.
6. **Mutação focal** — tirar a guarda e exigir que o teste fique **vermelho**. Detector que não apanha o
   mutante não é detector. Quando a mutação real não é admissível (gate da frota RED), uma prova lógica
   do comparador vale, mas **declara-se que é só isso**.
7. **Um registo único** — scope, invocador exacto, controlo positivo, controlo negativo, rollback e
   evidência em FICHEIRO. Vive no recibo (`_main/receipt-*.md`), não numa mensagem de chat.

Exemplo a copiar: `_main/caption-dup-repro.py` (mede o histórico real, minimiza um par real, corre o
`history_append` verdadeiro, mute a guarda e exige vermelho; e faz o mesmo na camada do painel).

## Onde vai o trabalho correctivo (não criar backlog paralelo)

O tracker **já existe**: `.opencode/complaints-closure.md`, uma secção por reclamação:

```
## R<n> — <título>
status: closed|open
evidence: `<comando>` -> <resultado>
```

O portão é `_main/complaints-closure-gate.py` e verifica a **forma** — **não executa nada**.

1. **Quem não é dono do ficheiro não o edita.** O bloco propõe-se no recibo e quem é dono do tracker
   integra-o.
2. **Um id novo só nasce se o dono do tracker o atribuir.** Um "R32" inventado por uma lane colide.

## Fecho mecânico

1. A evidência tem de ser **re-corrida hoje**, não citada:
   `python _main\closure-evidence-replay.py --run --section R<n>` — re-executa e compara o `rc` e o
   marcador (`VERDICT: PASS`) com o que a secção afirma. Sem isso, `status: closed` é uma afirmação de ontem.
2. `python _main\closure-evidence-replay.py --explain` mostra o que o instrumento **espera** de cada
   evidência, sem correr nada: `rc` esperado, marcador, e se o ficheiro citado existe.
3. `--self` prova a **comparação** sem correr nada (admissível com o gate RED); a prova de ponta a ponta
   (`--neg-arm`) precisa de gate verde.
4. Cada acção nomeia **instrumento + invocador exacto + braço negativo** (`NEG-ARM PASS`).
5. `fixed` != `verified`; `UNKNOWN` != `PASS`; **um skip não conta como aprovado**.

## Antes de qualquer acção pesada

O gate central da frota manda (HARD RULES do `AGENTS.md`): `performance-gate.py` primeiro, lease `heavy`
exclusivo, e com **RED** não se larga build, bateria completa, indexação, benchmark nem mutação.

## O que este repo recusa num postmortem

- Fechar por prosa ("revisto e correcto") em vez de `rc=0` + negativo `rc=1`.
- Cronologia da memória em vez do log, com a linha citada.
- Número sem **relação declarada** e sem **data** — o caso real: "517 de 2077" não se reproduzia com
  nenhuma das três relações que o instrumento mede; foi retirado.
- Confundir camadas: o store (`history_append`, igualdade) e o painel (`collapse_growth`, crescimento)
  curam coisas diferentes.

## Sem culpa

Neste repo isso é literal: **culpa o portão que faltava, não a lane**. *"faz gates ou agents.md"* — é
assim que o dono o disse. Uma acção que termina em "não voltar a fazer" não é acção; uma que termina em
"este portão passa a viver aqui" é.
