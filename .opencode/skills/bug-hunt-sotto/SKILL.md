---
name: bug-hunt-sotto
description: Use when the owner reports a defect in Sotto, or something is broken, failing, slow or lying. Routes ACTIVE debugging to the 11-step protocol in docs/bug-hunt.md plus the minimized-repro example, and hands off to postmortem-sotto only after containment.
---

# bug-hunt-sotto — a porta do MODO BUG-HUNT

Adaptador fino. **Nao tem protocolo proprio**: aponta as fontes, diz em que estado se carrega cada
uma, e o que nunca se afirma. Se este ficheiro e `docs/bug-hunt.md` discordarem, vale o doc — e a
discordancia e um bug aqui.

## Quando carrega

- O dono reporta um defeito, ou diz que algo esta quebrado, lento, a falhar ou a mentir.
- Ha um sintoma **ACTIVO** — reproduzivel ou nao — e o incidente ainda **nao esta contido**.
- Um quase-acidente que precisa de mecanica de debug para se saber se e incidente.

Incidente **contido ou resolvido** -> a skill e `postmortem-sotto`, nao esta.

## As fontes, por ordem

1. **O protocolo: `docs/bug-hunt.md`.** Os 11 passos e os quatro portoes que os tornam obrigatorios
   na bateria (`input-path`, `seam-coverage`, `bug-ledger`, `tooling-intent`). Um campo em falta e um
   passo vermelho, nao uma nota de rodape. **Ler o doc**, nao um resumo dele.
2. **A mecanica de verificacao:** `.opencode/skills/postmortem-sotto/SKILL.md` §Mecanica — sete
   passos (repro no invocador real, 3 a 5 hipoteses falsificaveis antes das sondas, uma variavel por
   sonda, minimizar, replay diferencial, mutacao focal, um registo unico) com o que recusa cada um.
   Vivem la porque servem o bug **e** o postmortem; nao se copiam para aqui.
3. **O exemplo a copiar:** `_main/caption-dup-repro.py` — repro minimo com fases, numeros medidos e
   a prova do detector (o negativo tem de derrubar aquele braco). E o modelo dos passos 3 e 8.

## A lei do estado

`reported` e `fixed` **nunca** se apresentam como `verified`. `UNKNOWN` nao e `PASS`. Um passo
saltado nao e um portao que passou. Sem verificador != autor, o estado maximo e `fixed`.

## Trabalho pesado pede licenca a frota

Antes de build, bateria completa, indexacao, benchmark ou campanha de mutacao: consultar
`I:\!manager\tools\performance-gate.py` e obter o lease `heavy` exclusivo. Com o gate RED nada disso
se larga — continua-se por inspecao de codigo, edicao de docs e diff estatico. `unknown` tambem nao
e `green`, e um skip nao e aprovacao.

## O fecho

Bug contido ou resolvido, ou quase-acidente apanhado -> passar a `postmortem-sotto` (metodo canonico
em `I:\!manager\.agents\skills\postmortem\SKILL.md`). **Com o bug ACTIVO nao ha postmortem.**

## Como isto e vigiado

`scripts/check-bug-hunt-wiring.py` prova por leitura de bytes que este adaptador existe, que aponta
as duas fontes, e que o `AGENTS.md` roteia para ele. Os bracos negativos removem essa ligacao numa
copia temporaria e exigem que o mesmo check fique RED; o braco positivo exige que a copia intacta
passe primeiro, senao a recusa viria de um ficheiro em falta e nao da ligacao removida.
