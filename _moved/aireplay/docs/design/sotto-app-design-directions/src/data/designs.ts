export type DesignId = "tele" | "bcast" | "mano" | "cine" | "inst";

export interface DesignDef {
  id: DesignId;
  num: string;
  name: string;
  model: string;
  spec: string;
  accent: string;
  fontClass: string;
  impact: string;
  reco: string;
  risk: string;
}

export const DESIGNS: DesignDef[] = [
  {
    id: "tele",
    num: "01",
    name: "Teleprompter",
    model: "A legenda como fluxo contínuo de leitura",
    spec: "Barlow Condensed · quase-branco · alinhamento rígido à esquerda",
    accent: "#f2e9d8",
    fontClass: "font-tele",
    impact:
      "Excelente leitura periférica e baixíssima interferência sobre o conteúdo original. O histórico recua em cinza; só o agora brilha.",
    reco: "A linha ativa parece viva sem piscar — brilho, peso e um leve deslocamento óptico bastam para mantê-la acesa.",
    risk: "Pode parecer uma legenda convencional e não comunicar que o texto está sendo corrigido em tempo real.",
  },
  {
    id: "bcast",
    num: "02",
    name: "Broadcast",
    model: "Uma transmissão acontecendo agora",
    spec: "IBM Plex Mono · timecode · pequenos marcadores de estado",
    accent: "#ff6a55",
    fontClass: "font-bcast",
    impact:
      "Torna evidente a diferença entre “o sistema está ouvindo” e “isto já foi dito”. O rodapé participa da linguagem, como status técnico.",
    reco: "Manter a instrumentação extremamente sutil — timecode e confiança existem, mas nunca viram dashboard.",
    risk: "Pode parecer ferramenta profissional de áudio e criar distância de quem só queria ler.",
  },
  {
    id: "mano",
    num: "03",
    name: "Manuscrito",
    model: "A legenda nasce diante dos seus olhos",
    spec: "Newsreader · cursor textual · estabilidade progressiva palavra a palavra",
    accent: "#a9c1d9",
    fontClass: "font-mano",
    impact:
      "Explica intuitivamente por que uma palavra pode mudar, sem sugerir erro no histórico. Um documento sendo escrito, não uma transmissão.",
    reco: "Mudança de estado gradual, sem animações chamativas: cada palavra recém-chegada ganha contraste aos poucos.",
    risk: "Podem ler a linha provisória como “rascunho” pouco confiável — e passar a ignorá-la.",
  },
  {
    id: "cine",
    num: "04",
    name: "Cartão de Cinema",
    model: "Presença editorial mínima",
    spec: "Fraunces · entrelinha larga · névoa tipográfica na fala em formação",
    accent: "#e4b363",
    fontClass: "font-cine",
    impact:
      "A mais elegante e menos “software” das cinco; pode desaparecer visualmente sobre o conteúdo, como uma legenda de festival.",
    reco: "Priorizar contraste e tamanho sobre refinamento tipográfico — a frase fechada é sólida; a em curso vive na névoa.",
    risk: "A elegância cobra velocidade de leitura, sobretudo em jogos e falas rápidas.",
  },
  {
    id: "inst",
    num: "05",
    name: "Instrumento",
    model: "Está ligado, não é uma janela aberta",
    spec: "Space Grotesk · indicador contínuo à esquerda · coluna estável",
    accent: "#5fd3a7",
    fontClass: "font-inst",
    impact:
      "Excelente para uso recorrente e periférico — depois de aprendido, quase não exige interpretação. O LED diz tudo.",
    reco: "O indicador da linha ativa é o principal elemento dinâmico da interface; todo o resto fica subordinado a ele.",
    risk: "Pode ficar austero demais e perder a personalidade de produto.",
  },
];

/** Roteiro simulado — uma narração que fala do próprio produto. */
export const SCRIPT: string[][] = [
  ["O som chega antes da imagem."],
  ["Antes da primeira cena, já existe um rumor de sala."],
  ["A legenda nasce enquanto a frase ainda está em formação."],
  ["Cada palavra provisória carrega uma pequena dúvida."],
  ["Quando a frase fecha, ela ganha peso — e fica."],
  ["Ninguém lê uma legenda: as pessoas apenas acompanham."],
  ["O painel escuta tudo, mas não interrompe nada."],
  ["No escuro do filme, o texto precisa brilhar sem gritar."],
  ["A correção em tempo real é quase invisível."],
  ["O que era hipótese, vira registro."],
  ["No fim, sobra apenas o que foi dito."],
];

export interface Scene {
  id: string;
  label: string;
  src: string;
}

export const SCENES: Scene[] = [
  { id: "noir", label: "Noite", src: "scenes/noir.jpg" },
  { id: "stage", label: "Palco", src: "scenes/stage.jpg" },
  { id: "deep", label: "Abismo", src: "scenes/deep.jpg" },
];
