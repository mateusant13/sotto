"""O relogio do player NUNCA faz a legenda recuar.

A QUEIXA DO DONO, verbatim (2026-10-30): *"a legenda nao ta sincronizada
direito. e parece que repete a legenda de instantes atras no ao vivo, depois
desbuga, e mostra ao vivo"*.

O QUE FOI MEDIDO (`_main/webview-run.log`, 2126 linhas `YOUTUBE_CAPTION`):
**129** linhas sao um cue cujo INICIO e' anterior ao da linha servida antes --
37,6 s atras, 40,4 s atras, e uma 359,0 s atras. A cue `start=34.239`
(`"economista formada pela USP,"`) foi servida **tres vezes em 24 s** enquanto
a faixa servida avancava 50 s -> 74 s. Nao era lentidao: era um **relogio
congelado** que o ramo `painted-other-track` confia e usa para escolher a cue.

A CAUSA, no codigo (`sotto_webview.py`): o ramo aceita a leitura enquanto
`moved or key == self.yt_foreign_key`. A segunda metade e' o buraco -- quando a
pintura E o relogio estao os dois parados, `key` e' igual e o ramo serve a
MESMA cue antiga para sempre. A intencao escrita no comentario ao lado (*"a
prova do congelamento e' uma pintura que MUDA com o relogio parado"*) e' o
inverso do que a condicao faz.

## A regra

Duas fontes de tempo, e uma so' pode recuar:

*  O **RELIGIO** (o UIA do player) so' tem licenca para ANDAR PARA A FRENTE.
   Ele e' grosso: le casas inteiras (`t=1206.0`), atrasa-se, e mediu-se a
   SALTAR PARA TRAS em 1 s, 4 s e 5 s -- jitter de leitura, nao seeks (o video
   estava em ~1170 e a leitura fez 1175 -> 1170 -> 1171). Nunca escolhe uma
   cue atras do chao.
*  A **PINTURA** (as palavras que o player esta' a desenhar agora) e' o
   relogio mais adiantado que existe, e e' tambem o UNICO sinal capaz de
   provar um seek a serio: o player a desenhar palavras de outro sitio E' o
   facto. Ela sobe o chao sempre, e so' o DESCE quando salta para tras o
   bastante para nao ser um cue repetido (`SEEK_BACK_S`).

Assim o relogio nunca arrasta o ecra para tras, e um seek a serio continua a
funcionar -- porque quem o declara e' a pintura e nao a leitura.

A regra e' do TEMPO: nao le nenhum dicionario e nao depende da lingua.
"""
from __future__ import annotations

#: Abaixo disto o relogio esta' PARADO (o player le a mesma casa decimal).
FREEZE_EPS_S = 0.05

#: Um salto para tras da PINTURA maior que isto e' um seek, nao um cue repetido.
SEEK_BACK_S = 2.0


def decide(now_t, floor, freeze_eps=FREEZE_EPS_S):
    """A decisao inteira do RELOGIO: `(instante a servir, chao novo)`.

    `floor` -- o inicio da cue mais avancada ja' servida (None = nada).

    `(None, floor)` quando nao ha leitura nenhuma. Fora disso o instante
    servido nunca fica atras do chao -- e' o defeito do dono, e por isso aqui
    nao ha excepcao nenhuma: o relogio NAO tem voto sobre recuar.
    """
    if now_t is None:
        return None, floor
    t = float(now_t)
    if floor is None:
        return t, t
    base = float(floor)
    if t >= base - freeze_eps:
        return t, (t if t > base else base)
    return base, base


def advance(floor, position, seek_back=SEEK_BACK_S):
    """O chao depois de a PINTURA servir em `position`.

    Sobe sempre que a pintura esteja' a frente. Desce apenas quando a pintura
    salta para tras mais do que `seek_back` -- ai e' um seek a serio, e o chao
    tem de descer com ele, senao a legenda ficava presa no ponto antigo para
    sempre (o mesmo defeito ao contrario).
    """
    if position is None:
        return floor
    try:
        pos = float(position)
    except (TypeError, ValueError):
        return floor
    if floor is None:
        return pos
    base = float(floor)
    if pos > base:
        return pos
    if base - pos > seek_back:
        return pos
    return base


# ══════════════════════════════════════════════════════════════════════════════
# A PINTURA CONGELADA -- quando o DOM do player para e o relogio nao
#
# O DEFEITO MEDIDO (2026-11-04, na Chrome do dono pela CDP 9222, video
# `r-AsGBMDI6c`): com a aba do YouTube em SEGUNDO PLANO
# (`document.visibilityState === 'hidden'`) o Chrome deixa de REPINTAR a caixa
# de legenda. Em 40 s de reproducao, `video.currentTime` andou 523,9 -> 563,0
# enquanto as DUAS linhas pintadas NUNCA mudaram (uma unica assinatura em 790
# amostras a 50 ms); o mesmo se mediu depois de um seek para t=300 e depois de
# um `location.reload()` (legenda certa por segundos, congela outra vez).
# `#movie_player.setOption('captions','track', ...)` nao cura: a lista volta
# `[]` e so' a recarga da pagina devolve a pintura, por segundos.
#
# O QUE O DONO VE: a legenda repete *"a legenda de instantes atras"* (as
# palavras dele, 2026-10-30) -- porque a fonte que o Sotto le' (as linhas do
# DOM, `_main/youtube-cdp-source-oracle.py`) parou no tempo e continua a ser
# servida como se fosse o presente.
#
# A REGRA -- a PINTURA so' perde a autoridade para a FAIXA quando HA' PROVA, e
# a prova tem DOIS lados (nunca um temporizador):
#
#   1. a pintura esta' PARADA: o mesmo texto pintado, e `video.currentTime`
#      andou mais de `STALE_S` desde a primeira vez que essa assinatura foi
#      vista;
#   2. a FAIXA SERVIDA diz outra coisa: o cue que cobre `video.currentTime`
#      neste instante NAO e' o cue que a pintura alinha.
#
# Os dois lados sao obrigatorios porque um so' mente:
#   * sem (2), um cue longo (8 s) seria chamado "congelado" so' porque o tempo
#     andou -- e' a histerese que a ordem do dono exige;
#   * sem (1), a primeira leitura de cada cue (`align` a meio do cue) seria
#     "diferente" e a faixa roubava a pintura que esta' certa.
#
# Quando a pintura volta -- uma linha DIFERENTE, o relogio a andar ou nao --
# ela recupera a autoridade no mesmo tick, sem memoria nenhuma do passado.
# ══════════════════════════════════════════════════════════════════════════════

#: Quanto o RELOGIO do video tem de andar com a MESMA pintura no ecra para a
#: suspeita abrir. A pintura muda a cada 100-300 ms (`youtube_cdp_source.POLL_S`
#: e a medicao de 2026-11-03): 1,5 s sao ~5 mudancas perdidas. NAO e' o
#: criterio -- e' so' o limiar que manda pedir a FAIXA como segunda testemunha
#: (o criterio e' a faixa).
STALE_S = 1.5

#: Duas cues com o mesmo `start` sao a MESMA cue (o JSON da faixa tem casas
#: decimais fixas).
CUE_SAME_EPS = 0.001


def paint_signature(rows):
    """A assinatura do que o player esta' a pintar -- espaco normalizado.

    Duas leituras com a mesma assinatura sao a MESMA pintura; uma linha a mais,
    a menos, ou um caracter diferente, e' uma pintura nova. E' a mesma
    normalizacao que `youtube_cdp_source.parse_snapshot` faz nas linhas, para
    nao haver duas definicoes de "a mesma pintura".
    """
    return "\n".join(" ".join(str(row).split()) for row in (rows or ())
                     if str(row).strip())


class PaintStall:
    """A decisao "a pintura esta' congelada?" -- estado, um tick de cada vez.

    O ESTADO E' A ASSINATURA, e nada mais: `key` e o instante do RELOGIO DO
    VIDEO em que ela apareceu (`key_t`). Nao ha' temporizador de parede em
    decisao nenhuma -- `stamp` so' viaja no veredicto para quem quiser medir a
    idade, nunca decide. A razao e' a medicao: com a aba escondida o Chrome
    continua a pintar o DOM com o MESMO texto enquanto `currentTime` anda, e um
    relogio de parede nao distingue "a pintura esta' parada" de "a leitura esta'
    parada".
    """

    def __init__(self, stale_s=STALE_S):
        self.stale_s = float(stale_s)
        self.key = None
        self.key_t = None
        self.key_stamp = None
        self.asked = None
        self.stale = False
        self.served = 'paint'

    # -- a leitura do tick ------------------------------------------------
    def observe(self, rows, t, stamp=None, cues=()):
        """Um tick: `(linhas pintadas, currentTime, stamp, cues da faixa)`.

        Devolve o veredicto (ver `PaintStall.verdict`). `cues` vazio = a faixa
        ainda nao chegou: ai' a unica coisa que se pode dizer e' "suspeita", e o
        chamador paga o pedido da faixa (ver `ask`).
        """
        key = paint_signature(rows)
        if not key:
            # SEM PINTURA NAO HA' NADA PARA CONGELAR. A fonte que decide passa a
            # ser outra (`_yt_clock_lines`), e a proxima pintura e' uma pintura
            # nova por definicao.
            self.key = None
            self.key_t = None
            self.stale = False
            return self.verdict(False, 'no-paint', rows=rows, t=t)
        try:
            t = None if t is None else float(t)
        except (TypeError, ValueError):
            t = None
        if key != self.key:
            # A PINTURA MUDOU: ela recupera a autoridade AGORA, tenha estado
            # congelada 1 s ou 30. Uma linha distinta e' a prova de que o Chrome
            # voltou a pintar.
            first = self.key is None
            self.key = key
            self.key_t = t
            self.key_stamp = stamp
            self.asked = None
            self.stale = False
            self.served = 'paint'
            return self.verdict(False, 'paint-changed' if not first
                                else 'paint-first', rows=rows, t=t)
        if self.key_t is None or t is None:
            return self.verdict(False, 'no-clock', rows=rows, t=t)
        age = t - self.key_t
        if self.stale:
            # CONGELADA DE VEZ: fica a faixa ate a pintura provar o contrario
            # (o ramo de cima). Sem esta memoria, uma lacuna de cues devolvia a
            # autoridade a' pintura parada.
            cue = self._cue_at(cues, t)
            return self.verdict(cue is not None, 'stale' if cue is not None
                                else 'stale-gap', rows=rows, t=t, age=age,
                                cue=cue)
        if age <= self.stale_s:
            return self.verdict(False, 'recent-paint', rows=rows, t=t, age=age)
        # SUSPEITA: a pintura nao muda ha' mais de `STALE_S` de video. O que
        # falta e' a segunda testemunha -- a faixa. Pede-se uma vez por
        # assinatura (nunca uma vez por tick).
        ask = self.asked != self.key
        self.asked = self.key
        cue = self._cue_at(cues, t)
        if cue is None:
            return self.verdict(False, 'no-cue-at-clock', rows=rows, t=t,
                                age=age, ask=ask)
        hit = self._aligned(cues, rows)
        if hit is None:
            # A pintura nao esta' na faixa servida: ela pode ser de OUTRO track
            # (o caso `painted-other-track`, tratado pelo shell) -- por isso nao
            # ha' testemunha e nao se declara congelamento.
            return self.verdict(False, 'paint-not-in-track', rows=rows, t=t,
                                age=age, ask=ask)
        if self._same_cue(hit.get('cue'), cue):
            # A HISTERESE: e' o cue LONGO. O relogio andou, a pintura esta' no
            # mesmo cue que a faixa diz estar -- logo nao esta' congelada.
            return self.verdict(False, 'same-cue', rows=rows, t=t, age=age,
                                cue=cue, painted_cue=hit.get('cue'))
        self.stale = True
        self.served = 'track'
        return self.verdict(True, 'stale', rows=rows, t=t, age=age, cue=cue,
                            painted_cue=hit.get('cue'))

    # -- helpers ----------------------------------------------------------
    @staticmethod
    def _same_cue(a, b):
        """As duas cues sao a MESMA (por inicio, e por texto como desempate)."""
        try:
            sa = float((a or {}).get('start'))
            sb = float((b or {}).get('start'))
            if abs(sa - sb) <= CUE_SAME_EPS:
                return True
        except (TypeError, ValueError):
            return (' '.join(str((a or {}).get('text') or '').split())
                    == ' '.join(str((b or {}).get('text') or '').split()))
        return False

    @staticmethod
    def _cue_at(cues, t):
        if not cues or t is None:
            return None
        try:
            import youtube_captions
            return youtube_captions.cue_at(cues, t)
        except Exception:                 # noqa: BLE001
            return None

    @staticmethod
    def _aligned(cues, rows):
        if not cues:
            return None
        try:
            import youtube_captions
            return youtube_captions.align_painted(
                cues, " ".join(str(r) for r in (rows or ())).split())
        except Exception:                 # noqa: BLE001
            return None

    def verdict(self, stale, why, rows=None, t=None, age=None, cue=None,
                painted_cue=None, ask=False):
        return {'stale': bool(stale), 'why': str(why),
                'served': 'track' if stale else 'paint',
                'painted_age_s': (None if age is None else round(float(age), 3)),
                'cue': cue, 'painted_cue': painted_cue,
                'painted': paint_signature(rows), 't': t, 'ask': bool(ask)}
