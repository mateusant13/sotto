# Sotto — brief de design

## O que eu quero de você

**Um design inteiro, com um ponto de vista.** Não uma paleta, não uma lista de tokens, não um
"moodboard". Quero que você decida como este painel **deve parecer e se comportar**, invente uma
ideia que organize tudo (tipografia, cor, forma, movimento, voz dos textos) e a leve até ao fim —
até o estado em que a app morreu e o ecrã tem de dizer a verdade sobre isso.

Se o seu design puder ser descrito como "escuro, moderno, minimalista", ele falhou. Escolha um
lado, defenda-o, e assuma as consequências em cada canto do painel.

Onde eu fui específico, é porque o problema ou a plataforma obrigam. Onde fui vago, é seu. Em
qualquer caso, se você achar que o meu "fixo" está errado, **quebre-o e diga por quê e a que
custo** — mas diga.

## O problema

O Sotto mostra **legendas em tempo real de qualquer áudio do PC** — filme, reunião, jogo, música —
numa janela sobreposta que abre e fecha com **Alt+C**. Fica invisível durante horas (a app corre
sozinha, arranca com o Windows) e aparece só quando o dono pede. É uma ferramenta privada para
**uma** pessoa, que a usa enquanto faz outra coisa.

Três factos decidem tudo o resto. São o problema, não preferências minhas:

1. **Ele aparece POR CIMA do conteúdo de outra pessoa.** Está a pedir emprestado o ecrã de
   alguém — muitas vezes a cena mais escura de um filme ou a mais colorida de um jogo. O painel
   tem de vencer esse fundo sem o agredir.
2. **É lido de relance, de ~1 metro**, com o olho já ocupado. Uma coisa manda: a legenda.
3. **Tem de ser acreditado.** O painel diz o que está a acontecer, inclusive quando é mau
   (*"Worker stopped: CABLE Input in use"*, *"Nenhum worker a correr (--no-worker)"*). Um painel
   bonito que mente é pior que um feio que não mente: aqui, **cor e forma carregam informação** —
   vivo, a preparar, erro, inativo — e nunca são decoração.

O espírito que eu acho certo: *um instrumento do sistema, que só pede o ecrã quando tem algo
verdadeiro para dizer.* Mas a **expressão** disso é sua — e se encontrar um espírito melhor para
este problema, eu quero vê-lo.

## O que é fixo

**A superfície.** Uma coluna de **380 × 900 px**, encostada à direita do ecrã, cantos
arredondados, janela **transparente** e *always-on-top*. Nunca rouba o foco do que o dono está a
fazer, e é *click-through* até o rato entrar nela. É **escuro** — mas isso é consequência de viver
sobre conteúdo alheio, não um estilo: se propuser algo que brilhe de outra maneira, resolva o
problema de ofuscar sobre um filme escuro.

**O que existe dentro.** Só isto, e nada mais pode ser inventado:

- **a legenda viva** — várias linhas; a que está em curso é **reescrita no mesmo lugar** (as
  palavras aparecem e às vezes são corrigidas enquanto a frase se forma) e, quando a linha
  **fecha**, ela fica estável e o que vem a seguir nasce por baixo. Você desenha dois estados
  visuais muito diferentes: **em curso** (pode mudar) e **fechada** (já não muda).
- **uma frase de estado**, no fundo, mais o ponto de estado. É onde o atalho **Alt+C** é
  anunciado, porque é o único controlo que a app tem.
- **uma gaveta de transcript** (o arquivo pesquisável), hoje vazia por desenho, **recolhida**,
  com a busca desativada. Secundária; tem de saber estar calada.
- **três botões**: esconder, fechar, limpar. Desenhe-os de forma que *esconder* e *fechar* nunca
  se confundam — um é "agora não", o outro é "acabou".

**Estados que vão existir** (todos já acontecem hoje): a preparar o motor (10–20 s), a ouvir sem
fala, legenda viva, pausa longa, erro **com causa e dispositivo**, nada a tocar, sem worker,
transcript vazio. Desenhe-os como momentos de um mesmo instrumento — não como doze telas.

**Regras que a plataforma impõe** (quebrar = não implementa):

- nada de conteúdo remoto: **CSP `default-src 'none'`**, ícones **inline** em SVG, e no máximo
  uma fonte — e só se vier **do repositório** (woff2 local; nenhum CDN);
- o painel corre em **`file://`**: sem query strings, sem `fetch` para fora;
- **ordem no DOM = ordem visual** (teclado e leitor de ecrã têm de concordar com o olho); a
  legenda viva é `aria-live="polite"`; foco visível; tudo acessível sem rato;
- **`prefers-reduced-motion`** respeitado;
- HTML/CSS/JS puro — o painel real é `app/electron/panel.{html,css,js}`, sem frameworks.

## O que é seu (é aqui que quero ambição)

- **A identidade:** a marca "Sotto" (marca + palavra; forma, peso, espaçamento), e a presença do
  painel quando está calado.
- **A tipografia:** a voz do instrumento. Como uma legenda lida de longe se comporta a 380 px
  de largura, com palavras que podem ter 20 caracteres; como o texto *que ainda pode mudar* se
  distingue do *já dito* sem piscar, sem saltar de largura, sem cansar.
- **A cor:** um sistema com significado, não uma paleta. Quanto de cor o painel merece?
- **A forma:** a placa, os fios, os raios, os vazios. O que separa zonas sem desenhar caixas.
- **O movimento:** o que se mexe, quando, e — mais importante — **o que nunca se mexe.** A app é
  um instrumento vivo: se houver sinal de vida, faça-o ser verdadeiro (o motor reporta nível de
  áudio e tempo real) e não um enfeite.
- **A voz dos textos:** as frases de estado e as vazias. Quantas palavras cabem antes de virar
  desculpa? Que tom — seco, técnico, humano?
- **Os detalhes que ninguém pede:** a aparência de hover quando o rato entra e o painel se torna
  clicável; a seleção de uma linha do transcript; o foco do teclado; a lista a encher-se.

## O que "um design inteiro" significa aqui

Será um design inteiro quando eu puder implementá-lo sem lhe perguntar nada:

1. **a ideia**, em um parágrafo, e 3–5 referências que a expliquem (não "minimalista"; de onde
   vem, o que toma emprestado);
2. **os fundamentos**: tipografia (família e escala com *weight* e line-height), cor (com o
   significado de cada uma), espaço, forma, e a opacidade/profundidade da placa sobre imagem;
3. **os componentes**: cada um dos itens do "o que existe dentro", especificado o suficiente para
   eu escrever o CSS — incluindo os quatro estados de botão e a linha **em curso** vs. **fechada**;
4. **o movimento**: durações e o que é intocável;
5. **os estados** da lista acima, como variações de um só sistema;
6. **um "fazer / não fazer"** curto — o que destruiria este design.

## Entregáveis

1. **`design.md`** — o design acima, em markdown, decisões com uma linha de justificação cada.
2. **`prototype.html`** — UM ficheiro, CSS embutido, sem dependências externas, que eu abra no
   browser e veja:
   - o painel à direita sobre **um fundo escuro e um fundo claro/corrido** (dois páragrafos de
     fundo, ou um `<img>` que eu troque);
   - a legenda em quatro momentos: a formar-se, fechada, pausa longa, erro com causa;
   - a gaveta fechada e aberta (vazia e com resultados);
   - o rodapé em `vivo`, `a preparar`, `erro`, `inativo` — **os quatro ao mesmo tempo**, para eu
     comparar a linguagem de cor num relance.

Se um dos meus "fixos" atrapalhar a ideia, entregue também a sua versão: eu implemento a que for
melhor (a superfície eu consigo mudar na shell).

## Como vou julgar

1. **O teste de 1 metro:** afasto-me e entrevejo. Só a legenda deve ser legível. Se eu ler o
   cabeçalho, o rodapé ou o rótulo do transcript à mesma distância, há ruído a mais.
2. **O teste da imagem por trás:** ponho o painel sobre um frame cheio de cor e sobre uma cena
   escura. Se o texto perder para o fundo, ou se a placa o agredir, está errado.
3. **O teste do cinzento:** desligo a cor. A hierarquia continua clara? E o erro continua a
   distinguir-se do vivo pelo **peso e pela forma**, não só pela matiz?
