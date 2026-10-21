export type ScenarioId = "filme" | "jogo" | "reuniao";

export interface Scenario {
  id: ScenarioId;
  label: string;
  chrome: string;
  image: string;
  /** Cada utterance é a sequência de resultados parciais do STT; o último é o texto consolidado. */
  utterances: string[][];
}

export interface Direction {
  id: number;
  key: "teleprompter" | "broadcast" | "manuscript" | "cinema" | "instrument";
  name: string;
  model: string;
  font: string;
  tag?: { text: string; tone: "accent" | "amberx" };
  impacto: string;
  recomendacao: string;
  risco: string;
}

export const SCENARIOS: Scenario[] = [
  {
    id: "filme",
    label: "Filme",
    chrome: "reproduzindo · áudio original",
    image:
      "https://images.pexels.com/photos/16158304/pexels-photo-16158304.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
    utterances: [
      [
        "O problema",
        "O problema não é o",
        "O problema não é o dinheiro.",
      ],
      [
        "É a confiança que você",
        "É a confiança que você quebro",
        "É a confiança que você quebrou ontem à noite.",
      ],
      [
        "Eu estava lá,",
        "Eu estava lá na hora",
        "Eu estava lá na hora errada.",
      ],
      [
        "Ela disse que o concerto",
        "Ela disse que o conserto",
        "Ela disse que o conserto sairia caro.",
      ],
      [
        "Ninguém sai daqui",
        "Ninguém sai daqui até a",
        "Ninguém sai daqui até a verdade aparecer.",
      ],
      [
        "Você escolheu o lado",
        "Você escolheu o lado errado da história.",
      ],
      [
        "Amanhã, às sete,",
        "Amanhã, às sete, no cais.",
        "Amanhã, às sete, no cais. Sozinho.",
      ],
    ],
  },
  {
    id: "jogo",
    label: "Jogo",
    chrome: "duo · ranqueada · voz do esquadrão",
    image:
      "https://images.pexels.com/photos/12660514/pexels-photo-12660514.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
    utterances: [
      [
        "Ele tá na esquerda,",
        "Ele tá na esquerda, atrás da caça",
        "Ele tá na esquerda, atrás da caixa!",
      ],
      [
        "Cuidado, tem um",
        "Cuidado, tem um cara no telhado.",
      ],
      [
        "Recarregando, me cobre!",
        "Recarregando, me cobre! Três segundos.",
      ],
      [
        "A zona tá fechando",
        "A zona tá fechando pelo norte.",
      ],
      [
        "Boa! Pegou o",
        "Boa! Pegou o loadout completo?",
      ],
      [
        "Último círculo,",
        "Último círculo, joga a granada agora.",
      ],
      [
        "GG. Bora de novo",
        "GG. Bora de novo em dois minutos.",
      ],
    ],
  },
  {
    id: "reuniao",
    label: "Reunião",
    chrome: "chamada semanal · 6 participantes",
    image:
      "https://images.pexels.com/photos/15399855/pexels-photo-15399855.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
    utterances: [
      [
        "Bom dia a todos,",
        "Bom dia a todos, obrigado por entrar.",
      ],
      [
        "A meta do trimestre",
        "A meta do trimestre segue em vinte",
        "A meta do trimestre segue em 23%.",
      ],
      [
        "O relatório da sessão",
        "O relatório da seção de vendas",
        "O relatório da seção de vendas fica pronto até sexta.",
      ],
      [
        "Alguém tem alguma dúvida",
        "Alguém tem alguma dúvida antes de fechar?",
      ],
      [
        "Perfeito. Então",
        "Perfeito. Então fica combinado assim.",
      ],
      [
        "A próxima chamada",
        "A próxima chamada é terça, às 10h.",
      ],
    ],
  },
];

export const DIRECTIONS: Direction[] = [
  {
    id: 1,
    key: "teleprompter",
    name: "Teleprompter",
    model: "a legenda como fluxo contínuo de leitura",
    font: "Barlow Condensed",
    tag: { text: "a aposta mais forte", tone: "accent" },
    impacto:
      "Excelente leitura periférica, baixa interferência sobre o conteúdo original.",
    recomendacao:
      "A linha ativa parece viva sem piscar — brilho, peso e um leve deslocamento óptico bastam.",
    risco:
      "Pode parecer legenda convencional e não comunicar que o texto é corrigido em tempo real.",
  },
  {
    id: 2,
    key: "broadcast",
    name: "Broadcast",
    model: "uma transmissão acontecendo agora",
    font: "IBM Plex Mono",
    impacto:
      "Torna evidente a diferença entre “o sistema está ouvindo” e “isto já foi dito”.",
    recomendacao:
      "Instrumentação extremamente sutil, para não virar um dashboard.",
    risco:
      "Pode parecer ferramenta profissional de áudio e criar distância de quem só quer ler.",
  },
  {
    id: 3,
    key: "manuscript",
    name: "Manuscrito",
    model: "a legenda nasce diante dos seus olhos",
    font: "Instrument Sans",
    tag: { text: "correção em tempo real visível", tone: "amberx" },
    impacto:
      "Explica intuitivamente por que uma palavra pode mudar, sem sugerir erro no histórico.",
    recomendacao:
      "Mudança de estado gradual — palavras recém-confirmadas ganham estabilidade aos poucos.",
    risco:
      "A linha provisória pode ser lida como rascunho pouco confiável e acabar ignorada.",
  },
  {
    id: 4,
    key: "cinema",
    name: "Cartão de Cinema",
    model: "presença editorial mínima",
    font: "Fraunces",
    impacto:
      "A mais elegante e menos “software”; pode desaparecer visualmente sobre o conteúdo.",
    recomendacao:
      "Priorizar contraste e tamanho antes de refinamento tipográfico.",
    risco:
      "A elegância pode custar velocidade de leitura, sobretudo em jogos ou falas rápidas.",
  },
  {
    id: 5,
    key: "instrument",
    name: "Instrumento",
    model: "está ligado, não é uma janela aberta",
    font: "Space Grotesk",
    impacto:
      "Excelente para uso recorrente e periférico — depois de aprendido, quase não exige interpretação.",
    recomendacao:
      "O indicador da linha ativa é o principal elemento dinâmico da interface.",
    risco: "Pode ficar austero demais e perder personalidade de produto.",
  },
];

export function fmtTC(totalSec: number): string {
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return `${String(h).padStart(2, "0")}:${mm}:${ss}`;
}
