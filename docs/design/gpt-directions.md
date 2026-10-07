# Cinco direções de design (de outra IA, via `gpt` / consultgpt)

Pedido feito: direções de design distintas para o painel do Sotto, com nome, ideia central,
aparência, como distinguem a linha **em curso** da **fechada**, e o risco de cada uma. Resposta
recebida em 2026-10-07, transcrita aqui sem edição de conteúdo.

> **Contexto dado:** legendas ao vivo de qualquer áudio do PC, painel 380×900 à direita, escuro e
> transparente, sempre no topo, nunca rouba foco; lido de relance a ~1 m, por cima de um filme que
> não é seu.

**Resumo dela:** o painel deve se comportar menos como um aplicativo e mais como uma **camada de
percepção** — algo que a pessoa consulta sem deslocar a atenção do filme, jogo ou reunião. As
cinco direções são deliberadamente diferentes no modelo mental (teleprompter, transmissão, edição,
papel, instrumento) e tratam a diferença entre **fala em formação** e **fala consolidada** como
parte central da linguagem do produto.

---

## 1. Teleprompter — *a legenda como fluxo contínuo de leitura*

Tipografia sans-serif grande, estreita e extremamente legível; texto quase branco, histórico em
cinza mais recuado. Poucos elementos, muito espaço vertical, alinhamento rígido à esquerda. A linha
em curso fica **ligeiramente maior e mais luminosa**; ao fechar, perde brilho e ganha estabilidade.
Quase um teleprompter lateral, sem caixas nem balões.

- **Impacto:** excelente leitura periférica, baixa interferência sobre o conteúdo original.
- **Recomendação:** fazer a linha ativa parecer "viva" sem piscar — brilho, peso ou um leve
  deslocamento óptico bastam.
- **Risco:** pode ficar parecido com uma legenda convencional e não comunicar que o texto está
  sendo corrigido em tempo real.

## 2. Broadcast — *uma transmissão acontecendo agora*

Monospaçada ou semi-mono, números e pequenos marcadores de estado, composição de monitor de
transmissão. A linha em curso recebe um **marcador vertical** ou um "LIVE" discreto; as fechadas
tornam-se visualmente neutras. O rodapé participa da mesma linguagem, como status técnico.

- **Impacto:** torna muito evidente a diferença entre "o sistema está ouvindo" e "isto já foi dito".
- **Recomendação:** manter a instrumentação extremamente sutil, para não virar dashboard.
- **Risco:** pode parecer ferramenta profissional de áudio e criar distância de quem só quer ler.

## 3. Manuscrito — *a legenda nasce diante dos seus olhos*

Texto fechado com peso normal e cor estável; texto em formação com aparência provisória — menor
contraste, cursor textual, sublinhado fino, ou palavras recém-confirmadas ganhando estabilidade
progressivamente. A composição lembra **um documento sendo escrito**, não uma transmissão.

- **Impacto:** explica intuitivamente por que uma palavra pode mudar, sem sugerir erro no histórico.
- **Recomendação:** mudança de estado gradual, sem animações chamativas.
- **Risco:** podem ler a linha provisória como "rascunho" pouco confiável e ignorá-la.

## 4. Cartão de Cinema — *presença editorial mínima*

Serifada contemporânea, linhas relativamente largas, grande entrelinha, blocos sem borda. A frase
fechada é sólida; a em curso tem uma "névoa" tipográfica: contraste menor e talvez uma linha-guia
lateral.

- **Impacto:** a mais elegante e menos "software"; pode desaparecer visualmente sobre o conteúdo.
- **Recomendação:** priorizar contraste e tamanho sobre refinamento tipográfico.
- **Risco:** elegância pode custar velocidade de leitura, sobretudo em jogos ou falas rápidas.

## 5. Instrumento — *está ligado, não é uma janela aberta*

Texto grande e direto, quase nenhuma decoração; a linha ativa tem um **pequeno indicador contínuo
à esquerda**, e as fechadas formam uma coluna visual estável. O estado inferior e o Alt+C são
tratados como instrumentos de operação; histórico e botões ficam subordinados.

- **Impacto:** excelente para uso recorrente e periférico — depois de aprendido, quase não exige
  interpretação.
- **Recomendação:** fazer do indicador da linha ativa o principal elemento dinâmico da interface.
- **Risco:** pode ficar austero demais e perder personalidade de produto.

---

## O que ela não conseguiu determinar

- Não é possível decidir **estaticamente** qual direção tem melhor legibilidade a 1 m, sobretudo
  sobre imagem em movimento: isso exige teste visual real.
- O maior *trade-off* é entre **clareza de estado** e **discrição**: quanto mais evidente for "esta
  linha ainda está mudando", maior a chance de o painel disputar atenção com o fundo.

**A aposta dela:** *Teleprompter* é a direção mais forte para o produto; *Manuscrito* é a mais
interessante se a correção em tempo real for uma característica que se quer tornar perceptível.
