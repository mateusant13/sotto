# AS DUAS COISAS QUE A LANE S2 ACHOU ERAM MINHAS -- e as duas estao fechadas

A lane S2 fechou e entregou tres achados. Dois deles sao regressoes MINHAS, de hoje.

## 1. O F4 do `three-overlays-oracle.js` -- e a causa nao era o valor

O F4 falhava no pristine E nos 11 mutantes, portanto tinha perdido a discriminacao, e o
`NEG-ARM VERDICT: PASS` deles passou a assentar nos outros 31 checks. A lane atribuiu-o
ao contrato antigo (`caption top:34px`) contra o novo (`top: auto`). **Esta certo -- mas a
causa imediata era mais pequena e mais estupida:**

    /body\[data-surface="strip"\]\[data-float="on"\] \.caption-float \{\s*top:/

`\{\s*top:` exige que `top:` seja a PRIMEIRA coisa dentro do bloco. **Eu pus um
comentario entre o `{` e a declaracao** (o comentario que explica a mudanca), e a regex
deixou de casar. O valor estava certo e a expectativa falhava pelo comentario.

E havia um defeito MAIS FUNDO na mesma linha, que a lane nao podia ver daqui: a
assertiva era `top:` com QUALQUER valor. **Uma verificacao que aceita qualquer valor nao
distingue o contrato antigo do novo** -- foi isso que a deixou falhar nas duas pontas.

Rebaseado para `[^}]*?top:\s*auto`: aceita prosa e exige o valor NOVO.

MEDIDO: `ok F4 ... panel inset:0 0 auto 0 + caption top:auto` -> **32 checks, 0 failed,
VERDICT: PASS**, e o `--neg-arm` volta a por os mutantes a VERMELHO.

## 2. Os LF puros no `panel.html`

A lane contou 9. **Contei 10:** linhas 71 e 467-474 -- e a linha 71 e a do comentario que
eu la escrevi quando tirei o rotulo do transcript. Regressao minha, da edicao de hoje.

Normalizado: **10 LF puros -> 0**, 70608 -> 70617 B. `panel.css` e `panel.js` continuam
0 bare LF, como a lane mediu.

## E uma licao que vale registar, porque e a terceira vez hoje

Duas ferramentas minhas falharam hoje pelo mesmo motivo: **uma expressao que procura um
padrao sensivel a POSICAO, contra um ficheiro que eu proprio mudei.** A entrada do
`L.splice` com uma string em vez de array partiu um ficheiro inteiro; esta regex partiu
um gate. Nos dois casos o `py_compile`/`node --check` nao apanharia -- so a CORRIDA
apanha. A regra que fica: **depois de mudar um ficheiro, correr o gate que o le, na mesma
rodada.**
