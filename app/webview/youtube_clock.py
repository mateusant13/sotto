"""A TOLERANCIA DA ADIVINHA DO RELOGIO -- governada pelo que o player NOS DISSE.

O DEFEITO (dono, 2026-11-07, verbatim): *"e ridiculo o fato que um stutter
qualquer do meu pc, faca a legenda dessincronizar ... se a porra da legenda do
youtube ta se movendo, mesmo com o stutter acontecendo, a NOSSA legenda que
pegamos do youtube, TAMBEM."*

O QUE SE MEDIU, e e' o que decide o numero. `_main/fixtures/
yt-paint-freeze-20261104.json` tem 745 amostras REAIS do Chrome do dono
(`video.currentTime` + relogio de parede, 50 ms, 40 s de reproducao). Para cada
par de amostras a uma distancia de 3-5 s, o erro de extrapolar o relogio do
player com o relogio de parede e':

    janela 3-5 s: n=25155  |erro| mediana 1 ms  p95 4 ms  maximo 34 ms
    janela 5-8 s: n=35103  |erro| mediana 1 ms  p95 4 ms  maximo 34 ms

(re-medir: `python _main/stutter-caption-oracle.py --drift`). O relogio do
player E' um relogio de media: anda 1 s por 1 s de parede, com a deriva de 4,25
ms/s acima. Ou seja: extrapolar 35 s ainda cabe no orcamento de 150 ms. O TETO
NAO E' A DERIVA DO RELOGIO -- e' o risco de o player ter mudado de estado
(pausa, seek, fim) durante a janela em que ninguem o leu, e esse numero quem
marca e' o CONTRATO do dono (1-5 s de stutter), nao a fisica do relogio:

    HOLD_S = 8.0  ==  5 s (o pior stutter nomeado no contrato) x 1,6

e o custo medido desse teto inteiro e' 34 ms -- 23 % do orcamento de 150 ms.

A REGRA, em tres estados e nenhum numero redondo:

  * O PLAYER DISSE QUE ESTA A ANDAR (`paused=false`, `ended=false`) --
    conta-se, ate' `HOLD_S`. O player continua a andar enquanto nos nao o
    lemos; parar de contar e' inventar uma pausa que ninguem viu.
  * O PLAYER DISSE QUE ESTA PARADO (`paused`/`ended` verdadeiros) -- nao anda
    um milissegundo. `t` e' a amostra.
  * O PLAYER NAO DISSE NADA (campo ausente, ou nenhuma amostra) --
    NAO se anda por inercia: serve-se a ultima amostra conhecida. Uma adivinha
    que ninguem autorizou e' pior que uma legenda parada: a parada o dono ve',
    a adiantada ele nao sabe de onde veio.

E o que NOS adiantamos e' NOSSO para desfazer: a primeira amostra autoritativa
que chegue depois de uma extrapolacao descarta-a (`rebase`). Sem isso um stutter
durante o qual o video pausou deixava a legenda a' frente do video por todo o
tempo que a extrapolacao durou -- o mesmo defeito, do outro lado.
"""
from __future__ import annotations

#: O estado do player. As tres palavras que o resto do ficheiro testa.
PLAYING = 'playing'
PAUSED = 'paused'
ENDED = 'ended'
UNKNOWN = 'unknown'

#: Uma amostra mais nova que isto e' AUTORITATIVA: o que nos extrapolamos desde
#: a ultima pode ser retirado. A fonte CDP publica a ~12 Hz (medido), portanto
#: 0,30 s sao quatro publicacoes -- muito acima do passo, muito abaixo de um
#: stutter de 1 s.
FRESH_S = 0.30

#: Ate' onde se conta com o ultimo "estou a andar". Ver o cabecalho: e' o
#: stutter que o contrato nomeia (5 s) com folga, e custa 34 ms dos 150 ms.
HOLD_S = 8.0

#: A deriva MEDIDA do relogio do player contra o relogio de parede, e a janela
#: em que foi medida (as duas saem da mesma corrida; ver o cabecalho).
DRIFT_MEASURED_S = 0.034
DRIFT_WINDOW_S = 8.0

#: O orcamento de erro que o contrato do dono pede ("dentro de 150 ms").
BUDGET_S = 0.15

#: A deriva por segundo de parede, e o quanto o relogio SOZINHO permitiria
#: extrapolar dentro do orcamento. Nao e' o teto (ver HOLD_S) -- e' o numero que
#: mostra que o teto nao tem nada a ver com a precisao do relogio.
DRIFT_RATE_S = DRIFT_MEASURED_S / DRIFT_WINDOW_S
MAX_HOLD_BY_DRIFT_S = BUDGET_S / DRIFT_RATE_S


def player_state(paused, ended, playing=None):
    """O que o player DISSE, numa palavra. Ausencia de resposta e' `UNKNOWN`."""
    if paused:
        return PAUSED
    if ended:
        return ENDED
    return PLAYING if playing is True else UNKNOWN


def state_of(player):
    """`player_state` das tres bandeiras que o observador publica.

    As bandeiras vem do snapshot (`paused`/`ended` do DOM e `yt_cdp_playing`,
    que e' `None` quando o payload nao falou de pausa). Ler aqui e nao em cada
    chamador e' o que impede as tres chamadas de divergirem -- elas divergiam:
    `_yt_payload` congelava em `paused` e o relogio extrapolava na mesma.
    """
    return player_state(getattr(player, 'yt_cdp_paused', False),
                        getattr(player, 'yt_cdp_ended', False),
                        getattr(player, 'yt_cdp_playing', None))


def sample_instant(player, base_t, age):
    """`(instante, esgotou)` de UMA amostra -- e o chao da monotonia tratado.

    E' o que o relogio vivo (`_youtube_time`) faz com a amostra da CDP, num
    sitio so': le as bandeiras publicadas, aplica o teto (ou a pausa, ou a
    ausencia de resposta), e -- porque o que NOS adiantamos e' nosso para
    desfazer -- baixa o chao quando a amostra e' AUTORITATIVA (`rebase`).
    Devolve `esgotou=True` quando a amostra ja' nao e' adivinha nenhuma e quem
    chama tem de procurar outra testemunha (a UIA).
    """
    t, moved, spent = instant(base_t, age, getattr(player, 'yt_cdp_rate', 1.0),
                              state_of(player))
    if not spent:
        if age <= FRESH_S:
            player.yt_serve_floor = rebase(
                getattr(player, 'yt_serve_floor', None), base_t,
                getattr(player, '_yt_guess_s', 0.0))
        player._yt_guess_s = moved
    return t, spent


def instant(base_t, age, rate=1.0, state=PLAYING, hold=HOLD_S):
    """`(instante, quanto_nos_adiantamos, esgotou)` a partir da ultima amostra.

    `base_t`/`age` sao a amostra e a idade dela. O instante devolvido NUNCA e'
    anterior a' amostra: parado nao anda, e sem resposta volta-se a' amostra.
    """
    if base_t is None:
        return None, 0.0, False
    try:
        base = float(base_t)
    except (TypeError, ValueError):
        return None, 0.0, False
    try:
        age = float(age)
    except (TypeError, ValueError):
        age = 0.0
    try:
        cap = float(hold)
    except (TypeError, ValueError):
        cap = HOLD_S
    if state in (PAUSED, ENDED):
        # PARADO NAO ANDA.
        return base, 0.0, False
    if state != PLAYING:
        # "NAO SEI" TAMBEM NAO ANDA: a amostra e' o que ha', e `esgotou` diz ao
        # chamador que ja' nao ha' ancora nenhuma para desenhar.
        return base, 0.0, age > max(0.0, cap)
    if age <= 0.0:
        return base, 0.0, False
    try:
        rate = float(rate)
    except (TypeError, ValueError):
        rate = 1.0
    if not (0.05 <= rate <= 16.0):
        rate = 1.0
    moved = min(age, max(0.0, cap)) * rate
    return base + moved, moved, age > cap


def rebase(floor, t, invented, eps=0.05):
    """O chao depois de uma amostra AUTORITATIVA em `t`.

    `invented` e' quanto NOS adiantamos desde a amostra anterior. Uma diferenca
    que cabe nesse adiantamento e' nossa, logo desfaz-se e serve-se `t`
    ("parado nao anda" aplicado a serie toda, e nao so' a' ultima leitura). Uma
    diferenca MAIOR nao e' nossa -- e' um seek -- e o chao fica onde esta', que
    e' a pintura a decidir (`youtube_monotonic.advance`). Sem esta separacao o
    chao tanto prendia a legenda a' frente do video (pausa dentro do stutter)
    como oscilava ao ritmo da pintura (o cue comeca antes do relogio o alcancar).
    """
    if floor is None or t is None:
        return floor
    try:
        base = float(floor)
        now = float(t)
    except (TypeError, ValueError):
        return floor
    if now >= base - eps:
        return base
    try:
        ours = max(0.0, float(invented or 0.0))
    except (TypeError, ValueError):
        ours = 0.0
    return now if (base - now) <= ours + eps else base


def pause_proven(clock_static, clock_moving, photo_fresh):
    """A PAUSA SO' E' VERDADEIRA QUANDO O RELOGIO NAO A DESMENTIU (2026-11-26).

    O DEFEITO, medido no log do dono (2026-11-26 02:38:01, pid 57008): no MESMO
    tick o `YOUTUBE_PAUSE_DISAGREED paused_flag=True clock_rate=0.58` dizia que
    o relogio andava e o `YOUTUBE_PAUSE_PROVEN witness=flag+clock-static
    held_s=0.25` dizia que ele estava parado -- as duas testemunhas medem
    janelas diferentes (a primeira desde a foto anterior, ~8 s; a segunda
    desde a ultima posicao DIFERENTE, 0,25 s). O apagar consultava so' a
    segunda, entao um buffer de 0,25 s numa maquina que engasga apagava a
    legenda de um video que estava a andar, e o espelho `yt_source_paused`
    ficava ligado, recusando CADA linha seguinte do player -- a legenda congelou
    e nao voltou ao despausar.

    A ordem e' a mesma lei do `_yt_clock_moving`, que ja' existia: a medida
    desmente a bandeira, nunca o contrario. Aqui ela tambem desmente a pausa
    curta. `clock_moving` ganha sempre que as duas discordam no mesmo tick.

    A FOTO VELHA TAMBEM NAO PROVA PAUSA (2026-11-26, o resto do mesmo episodio).
    `_yt_clock_static` compara a posicao com a ultima DIFERENTE: numa paragem de
    produtor de 5,9 s (`YOUTUBE_SNAPSHOT_STALE age_ms=5891` as 02:38:08.713) o
    relogio nao pode andar, logo "parado" e' o que uma foto velha sempre diz --
    e o portao apagou o ecra as 02:38:10.436 (`YOUTUBE_PAUSE_PROVEN
    held_s=0.6`) sem uma unica pintura ate' a shell sair, 13 s depois. Uma foto
    em cache nao e' uma medicao (a lei que ja' vale para `why='painted'`): sem
    foto do tick, a pausa e' DESCONHECIDA, e o desconhecido nao apaga nada.

    Devolve `bool`: a pausa vale (True) ou foi desmentida / nao medida (False).
    """
    return bool(photo_fresh) and bool(clock_static) and not bool(clock_moving)

def paint_proven(clock_moving, photo_fresh, paused_proven, rows_changed,
                 had_previous):
    """O ECRAN SO' SOBE UMA LINHA NOVA COM TESTEMUNHA DE QUE A FONTE ANDA (2026-11-28).

    O DEFEITO, medido na tela do dono. A shell reabriu, adoptou a aba do YouTube
    que ele tinha DEIXADO PAUSADA (`AumWSG4Crf0`, `YOUTUBE_CDP_PACED paused=True`),
    recebeu o primeiro quadro com 2 linhas e pintou-o 0,48 s antes de a pausa
    ficar provada:

        01:00:12.637 YT_FRAME src=external:youtube:track rows=2
        01:00:12.690 CAPTION_PAINT_SURFACE src=player rows=2 text="That's the vibe..."
        01:00:13.169 YOUTUBE_PAUSE_PROVEN witness=flag+clock-static held_s=0.6
        01:00:13.170 CAPTION_WINDOW_BLANKED reason=youtube-paused

    A causa nao e' a pausa -- essa ja' apagava. E' o portao de ecran perguntar
    SO' "a pausa foi PROVADA?", e o DESCONHECIDO passar como permissao. O estado
    inicial de qualquer adopcao de aba e' exactamente esse desconhecido.

    A LEI, simetrica do `pause_proven`: **apagar exige prova de paragem; pintar
    exige prova de movimento.** Nenhum dos dois aceita o desconhecido, e um quadro
    que chega antes de qualquer medida nao sobe ao ecra -- vai para o historico e
    espera o tique seguinte.

    Duas testemunhas de movimento. A segunda existe para o player cujo relogio nao
    se deixa ler (`_yt_no_clock_lines`, 2026-11-02 -- esse caminho continua a
    servir o que o PROPRIO player desenha): o relogio a andar numa foto fresca, ou
    as ROWS a mudar depois de ja' haver uma pintura nesta sessao. Um quadro
    identico ao que ja' esta no ecra nao e' movimento -- e' a pausa a repetir-se,
    que e' precisamente o que nao pode reacender o ecran.

    Devolve `bool`: sobe (True) ou retem (False).
    """
    if paused_proven:
        return False
    if clock_moving and photo_fresh:
        return True
    return bool(had_previous) and bool(rows_changed)
