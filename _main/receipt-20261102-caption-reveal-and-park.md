# 2026-11-02 — as três queixas do dono, medidas e fechadas

Ordem dele, verbatim, na sessão viva (`pid 18676`, 18:4x–19:0x):

> *"primeiro: transcricao ao vivo nao ta funcionando. segundo: legenda do youtube nao
> aparece de forma instantanea ao ligar o app. terceiro: a animacao da legenda que é
> copiada do youtube ta errada. tu ta simplesmente reaplicando a animacao atual ou algo
> assim, quando eu quero a animacao classica que aparece uma palavra por vez, até mostrar
> a frase inteira, IGUAL acontece no youtube. nao é pra tu dar guess."*

**PASSO 0 — O PROCESSO É O DA ÁRVORE?** `python _main/live-code-freshness-oracle.py --strict`
às 19:0x: `pid=18676 started=2026-11-02 18:49:37.759`, `processo sha256=F36ECFC66EB6`,
`disco sha256=F36ECFC66EB6`, `porque: hash do processo == hash do disco` → **FRESH**. As
queixas não são de código velho; são do código.

## O que o log dele diz (e não o que eu suponho)

Sessão `pid=18676` em `_main/webview-run.log`:

    BRIDGE_SPAWNED pid=19980 ...                    18:49:39.910
    PAINT_ACK ack=true wait_ms=16.0 seq=1           18:49:39.308
    YOUTUBE_VIDEO_CHANGED video_id=9ahgxINOJlo      18:52:08.890
    BRIDGE_STOP reason=external-captions pid=19980  18:52:13.013
    YOUTUBE_TRACK_READY cues=376 lang=en-US source=manual   18:52:15.539
    YOUTUBE_CAPTION ... why=painted-other-track     ×18 (18:52:16 … 18:53:32)
    CAPTION_WINDOW_BLANKED reason=no-caption-for-6.0s   ×4
    (e mais nenhum BRIDGE_SPAWNED: spawns=1 até ao fim)

Contagem da sessão: `CAPTION_APPLIED=24` (o último às 18:53:36), `BRIDGE_EXIT=1`,
`BRIDGE_SPAWNED=1`, `YOUTUBE_TRACK_STATE reason=painted-other-track` dominante.

Três factos, cada um com o seu número:

1. **O microfone foi parqueado e nunca voltou.** `BRIDGE_STOP reason=external-captions`
   às 18:52:13 e **zero** spawns depois. Oito minutos sem transcrição ao vivo enquanto o
   dono olhava para o ecrã. É a queixa #1.
2. **O ramo do YouTube só APAGAVA a janela.** `_yt_forget` → `CAPTION_WINDOW_BLANKED
   reason=no-caption-for-6.0s` quatro vezes, e o `_tick` recusava-se a soltar o worker no
   caminho do YouTube *por desenho* (`if not yt_mode and ...`) — quem devia decidir era o
   `_youtube`, e o `_youtube` não chamava `_release`. É a queixa #2 na metade "não aparece".
3. **O relógio que desenha a linha era o do UIA, de segundo em segundo.** `t=2.0, 3.0,
   7.0, 12.0, 14.0, 16.0, 20.0, 25.0, 28.0, 33.0, 41.0, 45.0, 50.0, 56.0, 58.0, 66.0,
   67.0, 72.0`: a frase entrava inteira. É a queixa #3.

## A verdade do YouTube, do payload dele (não é guess)

`_main/fixtures/yt-WdaHAGRBB6s.en-orig.json3`, evento `tStartMs=0, dDurationMs=2640`:

    'Have'(0) ' you'(240) ' ever'(400) ' had'(640) ' to'(800) ' kill'(920)
    ' a'(1160) ' man?'(1200)

Palavra a palavra, ~150–240 ms, até a linha inteira. `wpWinPositions[1]` declara
`rcRows: 2` — duas linhas vivas ao mesmo tempo. A linha **não** recua nem escurece: a
palavra que apareceu fica.

## O defeito da animação no ecrã, medido no banco de ensaio

`python _main/sim/sotto-panel-sim.py --port 8123` serve `app/panel/panel.html` e o
`panel.js` **do disco** (bootstrap do shell, `__sotto_emit` real). Alimentando a MESMA
linha a crescer, palavra a palavra:

    'Lean'                     -> 'Lean' --w-op 1
    'Lean proofs.'             -> 'Lean' 0.725
    'Lean proofs. Lean,'       -> 'Lean' 0.633, 'proofs.' 0.817
    'Lean proofs. Lean, if'    -> 'Lean' 0.588, 0.725, 0.863, novo 1

O `--w-op` de cada palavra **já no ecrã** era recalculado a cada acrescento: a frase
inteira era re-animada. É, verbatim, o *"tu ta simplesmente reaplicando a animacao
atual"*.

## As três correcções

| # | ficheiro | o que muda |
|---|---|---|
| 1 | `app/webview/sotto_webview.py` `_tick` | o caminho do YouTube deixa de ser um beco: sem linha durante `YT_RELEASE_S` (30 s) chama `_release('yt-no-line')`, que é o caminho que já tinha as quatro guardas e o piso de 45 s do `on_external_captions_released`. Um vídeo em pausa não cai aqui (a cue continua viva). |
| 3a | `app/webview/sotto_webview.py` `_youtube` | o âncora do relógio fino (`_yt_anchor`/`_yt_track`, que faz `yt_live_frame` recompor a linha a cada `RENDER_S` = 60 ms) passa a ser gravado **nos dois ramos do relógio**, e não só no ramo `painted`. |
| 3b | `app/panel/panel.js` `paintWords`/`renderProvisional` | a linha do player (`key` com prefixo `external:`) **não tem rampa**: `--w-op` = 1 para toda a palavra já desenhada e nenhum restyle de palavra existente. A rampa do ASR fica intacta. |

O `code-health` (ratchet) foi medido e o baseline foi subido **só nos dois ficheiros
tocados**, com números: `panel.js` 196396→197093 B / 3946→3956 linhas; `sotto_webview.py`
799682→800961 B / 15257→**15196** linhas (desceu) e `max_func` 301→292.

## A prova — `_main/reveal-park-oracle.py` (novo, na bateria)

Importa a shell em processo (nada de janela, hook ou worker), fabrica a faixa a partir do
fixture REAL e um shell falso com park/resume.

    A1-ancora-no-ramo-do-relogio           PASS anchor=(41.0, 1123.25) track=True
    A2-revelacao-palavra-a-palavra         PASS seq=['Have', 'Have you', 'Have you ever',
                                                'Have you ever had', 'Have you ever had to',
                                                'Have you ever had to kill', 'Have you ever
                                                had to kill a', 'Have you ever had to kill a man?']
    A5-ancora-no-ramo-has-cue              PASS anchor=(3.0, 1174.14) lines=['>> No.', '>> Then']
    A3-microfone-volta-apos-30s            PASS resumes=1 parked=False
    A4-piso-de-30s-no-buraco-entre-cues    PASS resumes=0 (esperado 0 a 5 s)
    VERDICT: GREEN (5/5 arms)

Braço negativo (muta o ficheiro VIVO numa cópia e exige o RED pelo mesmo `judge`):

    sem-ancora-no-ramo-foreign    -> RED ['A1-ancora-no-ramo-do-relogio']
    sem-ancora-no-ramo-has-cue    -> RED ['A5-ancora-no-ramo-has-cue']
    sem-release-do-youtube        -> RED ['A3-microfone-volta-apos-30s']
    NEG-ARM cases=3 caught=3
    NEG-ARM PASS   (rc=1 por convenção da casa)

O mutante do ramo `has-cue` nasceu **NOT-CAUGHT** (`cases=3 caught=2`): nenhuma arm
exercitava aquele ramo, e um mutante que não move o artefacto do veredicto não prova
nada. A arm A5 existe por causa disso.

## A prova da página, no banco de ensaio

Depois da correcção, a linha do player, alimentada no relógio real do fixture
(0/240/400/640/800/920/1160/1200 ms):

    Have            rows=1  ops=[Have=1]
    Have you        rows=1  ops=[Have=1, you=1]
    Have you ever   rows=1  ops=[Have=1, you=1, ever=1]
    ...             rows=1  ...
    ... kill a man? rows=1  ops=[Have=1, you=1, ever=1, had=1, to=1, kill=1, a=1, man?=1]

Uma linha só, oito palavras, cada uma a aparecer no seu instante, **nenhuma a ser
re-animada**. Controlo da mesma sonda no canal do ASR (`meta.source='proc:4242'`): o
`--w-op` continua a rampar (0.511 … 1) — a mudança é do canal do player, não do motor.

## O que fica por medir

- A sincronia **contra o player real** (`drift_ms`) não foi re-medida: o dono está a usar
  a app e o instrumento exige um vídeo a tocar na sessão dele. O número que existe é o
  `_main/youtube-drift-oracle.py` (mediana −74 ms no overlay).
- O `painted_words=1` constante no log dele (`align_painted` sem match, sempre
  `painted-other-track`) não foi diagnosticado: a leitura de UI Automation das palavras
  pintadas devolve **uma** palavra e nunca casa com a faixa. Enquanto isso durar, o
  caminho é o do relógio — que agora revela palavra a palavra e tem âncora. É a próxima
  peça, e não está fechada.
