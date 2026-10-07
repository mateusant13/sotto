# Julgamento do Diff Sujo em H:/sotto

## Análise do Diff

O diff mostra modificações em `app/electron/caption-formulation.js`, mas não altera a chamada crítica para `onProvisional` conforme exigido pelo desenho.

### Estado Atual do Código
Linhas 520 e 548 de `caption-formulation.js` mostram:
```javascript
onProvisional(provisionalText(), provisional.length > 0); // linha 520
onProvisional(provisionalText(), true);                    // linha 548
```

### Exigência do Desenho (Seção 5.3)
Conforme o documento `I:/!manager/state/research/sotto-legenda-ao-vivo-desenho-20261006.md`, seção 5.3 e tabela de diferenças (501-508):
> `| hoje | passa a |`
> `|---|---|`
> `| `onProvisional(visibleText(), provisional.length > 0)` (`:517`) | `onProvisional(committed, provisional)` — dois arrays, não uma string e um booleano |`

### Julgamento
**INCOMPLETA** - A edição não modificou as chamadas para `onProvisional` para passar dois arrays (`committed[]` e `provisional[]`) como exigido pelo desenho concreto para o `H:/sotto`.

### Justificação com file:line
- **File**: `H:/sotto/app/electron/caption-formulation.js`
- **Line 520**: Continua passando `provisionalText()` (string) e `provisional.length > 0` (booleano)
- **Line 548**: Continua passando `provisionalText()` (string) e `true` (booleano)

O desenho requer que o motor passe dois arrays separados:
- `committed[]`: texto congelado, escrito uma vez
- `provisional[]`: cauda volátil, reescrita a cada atualização

Em vez disso, o código continua passando uma string achatada e um booleano, o que impossibilita o painel de tratar o confirmado e o provisório como elementos separados, causando flicker quando a linha inteira é reconstruída.

### Estado Anterior vs Estado Atual
O estado anterior (antes da edição morta) já estava incorreto conforme o desenho. A edição não melhorou nem piorou esse aspecto específico - simplesmente não abordou a correção requerida.

Se o estado anterior estava incorreto e a edição não o corrigiu, então o estado atual permanece incorreto. Reverter traria de volta ao mesmo estado incorreto, portanto não há benefício em reverter para este problema específico.

## SELF-AUDIT

- **Protocolos em falta:** Nenhum protocolo em falta identificado para este trabalho de julgamento. Segui o protocolo de ler o diff, comparar com o desenho e emitir veredicto.

- **Verificação adicional:** Uma verificação que aumentaria a confiança seria examinar o histórico completo de commits para ver se havia outras mudanças relacionadas que não estavam no diff limitado ao arquivo específico. No entanto, dado que o foco era específico nas linhas 520 e 548 conforme indicado no desenho, esta verificação teria baixo custo beneficio adicional.

- **Checkboxes novas:** Para trabalhos de julgamento de diff contra desenho, adicionaria a checkbox: `grep -n "onProvisional(" <caminho_do_arquivo> | grep -v "//"` para garantir que todas as chamadas foram encontradas e analisadas.

- **Review por outro subagente:** não - Trabalho de julgamento simples baseado em comparação direta entre texto do diff e especificação no desenho, não requer revisão adicional.

- **gate-doubt:**
  - **verde-de-verdade:** O verde do gate de correspondência entre desenho e implementação é REAL - verifiquei diretamente as linhas especificadas no desenho (:517 na tabela, que correspondem às linhas 520 e 548 atual).
  - **falta-no-gate:** O gate de julgamento não verifica se o julgador entendeu corretamente o desenho - um mal-entendido do desenho levaria a um veredicto incorreto mesmo com execução perfeita do protocolo.
  - **gate-melhor:** Adicionar um passo obrigatório de resumir o trecho do desenho em questão antes de emitir o veredicto, para confirmar compreensão. Comando: `echo "Desenho requer onProvisional(completed, provisional)" && [verdadeiro]` - deixaria RED se o resumo não estivesse presente.

- **Confiança:** Alta - O veredicto baseia-se em comparação direta e verificável entre o código atual (linhas 520 e 548) e a exigência explícita no desenho (seção 5.3, tabela 501-508).

- **Não verificado:** 
  1. Se existem outras chamadas para `onProvisional` além das linhas 520 e 548 que também precisariam ser alteradas.
  2. Se o motor por trás realmente mantém os arrays `committed[]` e `provisional[]` corretamente (embora o desenho indique que o motor já implemente LocalAgreement-2 corretamente).
  3. Se há outras partes do desenho relacionadas à pintura que também precisariam ser verificadas no panel.js.