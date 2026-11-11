"""A LEGENDA QUE PINTA TEM DE SER DO AUDIO QUE ESTA' A TOCAR AGORA.

O DEFEITO, MEDIDO no log do dono (`_main/webview-run.log`, sessao pid 54524,
2026-11-11; sonda `_main/_live-route-measure.py`):

    CAPTION_IN start=381.84 end=383.84 final=true tap_ms=None age_ms=None
    text="replanement of code water, shows a level of leadership dingases."

A captura comecou 17:34:42.8, portanto `end=383.84` e' audio de 17:41:06.7; a
linha foi ENTREGUE a' shell (e pintada, `CAPTION_APPLIED ... aged_kind=final-close`)
as 17:46:05.8 -- **299 s de atraso** (o piso medido pela ancora do relogio do lote
e' 184 s; os dois estao >> 2,5 s). A linha e' do motor de LOTE
(`route=redux-batch`, `tap_ms=None`), que re-transcreve o audio acumulado em
janelas de 3 s: ele existe para o HISTORICO, e o unico caminho que ele tinha para
o ecra era o mesmo `emit` das linhas ao vivo -- sem etiqueta de rota e sem idade.

Duas rotas pintavam no MESMO intervalo (medido 17:45:57-17:46:18): a faixa do
proprio YouTube (`src=external:youtube:track`) e o lote local. O dono, verbatim:
*"a legenda do ctrl space fica aparecendo na tela de forma aleatoria so' por que
ta tocando um audio, que nem speaker e'"* e *"e ta dando replay em audios que ja
tocaram a minutos atras"*. As duas frases sao o mesmo defeito: nada comparava a
ROTA da linha com a rota DECIDIDA, nem a IDADE do audio com o presente.

A REGRA, num so' sitio e sem segundo caminho:

  1. `redux-batch` / `producer=redux` NUNCA pinta. E' historico por construcao:
     o audio que ele transcreve ja' foi dito, e a melhoria de texto que ele traz
     pertence ao arquivo, nao ao ecra.
  2. Rota decidida = `player` (o shell publica `park=captions` no ficheiro que o
     interruptor ja' le' todo o tick) -> a legenda local NAO pinta o mesmo audio
     que o player esta' a pintar. O texto continua a ir para o historico.
  3. Caso contrario, a IDADE decide: `age_s <= LIVE_MAX_AGE_S` pinta; acima
     disso e' recusa (`reason=stale`) com o numero no log.

A IDADE HONESTA vem do produtor, nunca de uma estimativa daqui: `tap_ms` (o
relogio de parede do bloco que FECHOU a linha, que o caminho ao vivo ja' carimba)
ou `audio_age_s`, carimbado por quem tem o relogio do audio (`engine_switch`
`drain_captions`, `_audio_clock_s - end`). Sem nenhum dos dois a idade e'
DESCONHECIDA e a linha pinta -- recusar no escuro calaria o unico transcritor
desta arvore, que e' a coisa que a HARD RULE proibe; a idade desconhecida e'
contada e dita (`LIVE_ROUTE_UNKNOWN_AGE`) para nao voltar a ser um buraco mudo.

A RECUSA NAO PERDE TEXTO. O consumidor da shell (a ponte) trata
`history_only` como "entra no historico e nao pinta" desde 2026-11-04
(`WARM_REPLAY_TO_HISTORY`, `sotto_webview.py` `on_worker_caption`), por isso a
recusa MARCA a linha em vez de a deitar fora: o transcript do dono fica completo.
"""
from __future__ import annotations

import time

#: O `Mmm` puro ja' tinha regra (`worker/caption_noise.py`, medido: 93 de 680
#: linhas do historico, TODAS `Mmm`, todas `producer=redux`). O que faltava nao
#: era a regra, era o SITIO: `is_noise_caption` so' era chamado no caminho de
#: LOTE (`admit_batch_caption`), e o caminho ao vivo pintava o `Mmm` que o audio
#: nao-falado (musica, ruido de sala) produz. A regra entra AQUI, na porta de
#: pintura, e o texto continua a ir para o historico -- nunca se perde uma linha.
try:
    from caption_noise import is_noise_caption as _is_noise_caption
except Exception:                                   # noqa: BLE001
    _is_noise_caption = None

#: A idade MAXIMA do audio que ainda pode pintar, em segundos. 2,5 s e' o
#: orcamento declarado: acima disto o dono le' uma frase que ja' passou, e a
#: legenda deixa de ser uma legenda. Medido contra o defeito: as linhas de lote
#: pintaram com 184-299 s.
LIVE_MAX_AGE_S = 2.5

#: A TOLERANCIA DO RELOGIO, em ms. Um carimbo dentro desta janela e' "agora"
#: (arredondamento entre dois relogios); um carimbo ALEM dela esta' no FUTURO, e
#: ai' a idade nao e' medivel. A casa ja' pagou a lei: uma medicao ausente nunca
#: e' uma afirmacao (`docs/factos-medidos.md`), e `max(0.0, negativo)` afirmava
#: "fresco" com um instrumento que nao conseguia ver o audio.
CLOCK_JITTER_MS = 250.0
BATCH_ROUTE = "redux-batch"
BATCH_PRODUCER = "redux"

#: Quem manda no ecra. `local` = o transcritor desta arvore; `player` = o shell
#: decidiu que o player fornece as legendas (`park=captions`).
OWNER_LOCAL = "local"
OWNER_PLAYER = "player"

#: Os motivos de recusa, um por porta -- o log diz QUAL porta fechou.
REASON_FRESH = "fresh"
REASON_STALE = "stale"
REASON_BATCH = "batch-route"
REASON_NOISE = "noise"
REASON_PLAYER = "player-owns-route"
REASON_UNKNOWN = "unknown-age"

#: O estado que o interruptor mantem (rota decidida) e o proprio log por episodio.
_STATE = {
    "owner": OWNER_LOCAL,
    "device": None,
    #: `(reason, producer)` -> True enquanto o episodio de recusa esta' aberto.
    "open": {},
    "refused": 0,
    "admitted": 0,
    "unknown_age": 0,
    "last_owner_line": None,
}


def note_route_owner(owner, device=None):
    """O interruptor diz QUEM manda no ecra. Devolve o dono que estava em vigor.

    Devolver o ANTERIOR (e nao o novo) e' o que deixa o chamador dizer a
    transicao com uma comparacao honesta -- `if previous != owner` -- em vez de
    re-logar o estado a cada tick ou de guardar uma segunda copia da verdade.
    """
    previous = _STATE["owner"]
    if owner in (OWNER_LOCAL, OWNER_PLAYER):
        if previous != owner:
            _STATE["open"].clear()
            _STATE["last_owner_line"] = owner
        _STATE["owner"] = owner
    if device:
        _STATE["device"] = str(device)
    return previous


def note_device(device):
    """O dispositivo do tap, para a linha de recusa levar a rota E o aparelho."""
    if device:
        _STATE["device"] = str(device)


def state():
    """Uma copia dos numeros, para o WORKER_STATS e para os oraculos."""
    return {k: (dict(v) if isinstance(v, dict) else v) for k, v in _STATE.items()}


def caption_producer(payload):
    """`'redux'` para uma linha de lote, `'live'` para o transcritor ao vivo.

    A classificacao e' por ROTA quando ela existe e pela origem quando nao:
    `route=redux-batch` e' o carimbo dos dois ingressos do lote, `producer=redux`
    o do executor externo. Qualquer outra coisa e' o caminho ao vivo.
    """
    if not isinstance(payload, dict):
        return "live"
    route = str(payload.get("route") or "")
    producer = str(payload.get("producer") or "")
    if route == BATCH_ROUTE or producer == BATCH_PRODUCER:
        return BATCH_PRODUCER
    return "live"


def _caption_is_noise(payload):
    """True so' quando a linha INTEIRA e' `m`/`hm`/`mhm` com pontuacao.

    Uma linha com uma palavra real nunca e' ruido (a regra do
    `caption_noise`), e o predicado nunca levanta nem custa um decode.
    """
    if _is_noise_caption is None or not isinstance(payload, dict):
        return False
    text = payload.get("text")
    if not isinstance(text, str) or not text:
        return False
    try:
        return bool(_is_noise_caption(text))
    except Exception:                               # noqa: BLE001
        return False


def caption_age_s(payload, now_ms=None, clock_s=None):
    """A idade HONESTA do audio da linha, em segundos, ou `None` se nao se sabe.

    Duas fontes, nesta ordem:

      * `tap_ms` -- relogio de parede (ms) do bloco que FECHOU a linha. E' o que
        o caminho ao vivo carimba, e e' o unico numero que ja' e' uma idade.
      * `audio_age_s` -- carimbado por quem tem o relogio do AUDIO
        (`engine_switch.drain_captions`), porque uma linha de lote nao tem
        `tap_ms` e o `end` dela so' faz sentido contra esse relogio.
      * `end` + `clock_s` -- o mesmo calculo, feito aqui quando o chamador passa
        o relogio (o oraculo conduz este ramo sem um motor).

    `None` significa DESCONHECIDA, e nao zero: uma idade inventada e' o defeito
    que este modulo existe para fechar. E um RELOGIO QUE ANDA PARA TRAS (um
    carimbo no FUTURO, uma diferenca negativa) tambem e' `None`: `max(0.0, x)`
    transformava "nao consigo medir" em "fresco", que e' a afirmacao que o
    instrumento nao pode fazer. Dentro de `CLOCK_JITTER_MS` o carimbo e' "agora".
    """
    if not isinstance(payload, dict):
        return None
    tap = payload.get("tap_ms")
    if isinstance(tap, (int, float)) and tap > 0:
        now = time.time() * 1000.0 if now_ms is None else float(now_ms)
        return _measured_age_s(now - float(tap), ms=True)
    stamped = payload.get("audio_age_s")
    if isinstance(stamped, (int, float)):
        return _measured_age_s(float(stamped), ms=False)
    end = payload.get("end")
    if isinstance(end, (int, float)) and isinstance(clock_s, (int, float)):
        return _measured_age_s(float(clock_s) - float(end), ms=False)
    return None


def _measured_age_s(delta, ms=False):
    """A idade, ou `None` quando o numero diz que nao houve medicao.

    `ms=True` quando a diferenca veio em milissegundos. Uma diferenca NEGATIVA
    alem da tolerancia e' um relogio para tras (carimbo no futuro) e devolve
    `None`; dentro da tolerancia e' "agora" (0,0 s).
    """
    try:
        delta = float(delta)
    except (TypeError, ValueError):
        return None
    if delta != delta or delta in (float("inf"), float("-inf")):   # NaN/inf
        return None
    limit = -CLOCK_JITTER_MS if ms else -CLOCK_JITTER_MS / 1000.0
    if delta < limit:
        return None
    delta = max(0.0, delta)
    return delta / 1000.0 if ms else delta


def live_route_verdict(payload, now_ms=None, clock_s=None,
                       max_age_s=LIVE_MAX_AGE_S, route_owner=OWNER_LOCAL):
    """A decisao, PURA: `{'paint', 'reason', 'age_s', 'producer'}`.

    A ordem das portas e' a ordem em que cada uma pode calar a linha, e a
    primeira que fecha e' a que o log nomeia:

      1. `batch-route`     -- o lote nunca pinta (historico por construcao).
      2. `player-owns-route` -- o shell decidiu que o player pinta; a legenda
         local do MESMO audio nao pinta por cima.
      3. `stale`           -- idade conhecida acima de `max_age_s`.
      4. `fresh`           -- idade conhecida dentro do limite.
      5. `unknown-age`     -- sem idade: pinta (recusar no escuro calaria o
         unico transcritor), e o chamador CONTA o buraco.
    """
    producer = caption_producer(payload)
    age = caption_age_s(payload, now_ms=now_ms, clock_s=clock_s)
    if producer == BATCH_PRODUCER:
        return {"paint": False, "reason": REASON_BATCH, "age_s": age,
                "producer": BATCH_PRODUCER}
    if route_owner == OWNER_PLAYER:
        return {"paint": False, "reason": REASON_PLAYER, "age_s": age,
                "producer": producer}
    if _caption_is_noise(payload):
        return {"paint": False, "reason": REASON_NOISE, "age_s": age,
                "producer": producer}
    if age is None:
        return {"paint": True, "reason": REASON_UNKNOWN, "age_s": None,
                "producer": producer}
    if age <= float(max_age_s):
        return {"paint": True, "reason": REASON_FRESH, "age_s": age,
                "producer": producer}
    return {"paint": False, "reason": REASON_STALE, "age_s": age,
            "producer": producer}


def admit(payload, log=None, now_ms=None, clock_s=None):
    """O PONTO UNICO que o `emit` do worker chama. Devolve o payload a emitir.

    Regras do sitio:

      * NUNCA levanta e NUNCA perde a linha: qualquer falha devolve o payload
        intacto (um filtro que parte nao pode custar a legenda do dono).
      * Uma recusa MARCA (`history_only=True`) e acrescenta `route_refused` +
        `age_s`; o texto segue para o historico pela ponte da shell.
      * Uma admissao carimba `age_s` quando ele e' conhecido, para que a shell
        possa recusar sozinha o que ja' chega velho.
      * `LIVE_ROUTE_REFUSED` sai UMA vez por episodio `(motivo, produtor)`; o
        episodio fecha quando uma linha do mesmo produtor PINTA outra vez.
    """
    try:
        if not isinstance(payload, dict):
            return payload
        out = dict(payload)
        # A ROTA E O APARELHO NA MESMA LINHA (2026-11-11). Toda linha ao vivo ja'
        # carrega `source` (o dispositivo do tap), por isso a memoria do aparelho
        # e' alimentada pelo proprio fluxo que a precisa: uma recusa de LOTE nao
        # tem `source`, e sai com o ultimo aparelho que pintou.
        if out.get("source"):
            _STATE["device"] = str(out["source"])
        verdict = live_route_verdict(
            out, now_ms=now_ms, clock_s=clock_s, route_owner=_STATE["owner"])
        age = verdict["age_s"]
        if verdict["paint"]:
            _STATE["admitted"] += 1
            if age is not None:
                out["age_s"] = round(float(age), 3)
            if verdict["reason"] == REASON_UNKNOWN:
                _STATE["unknown_age"] += 1
                key = (REASON_UNKNOWN, verdict["producer"])
                if not _STATE["open"].get(key):
                    _STATE["open"][key] = True
                    _emit_log(log, f"LIVE_ROUTE_UNKNOWN_AGE producer="
                                   f"{verdict['producer']} route_owner="
                                   f"{_STATE['owner']} device={_STATE['device'] or 'unknown'} "
                                   f"— sem `tap_ms` e sem `audio_age_s`: a linha pinta e "
                                   f"o buraco fica contado (unknown_age={_STATE['unknown_age']})")
            else:
                _STATE["open"].pop((REASON_STALE, verdict["producer"]), None)
                _STATE["open"].pop((REASON_BATCH, verdict["producer"]), None)
                _STATE["open"].pop((REASON_PLAYER, verdict["producer"]), None)
                _STATE["open"].pop((REASON_NOISE, verdict["producer"]), None)
            return out
        _STATE["refused"] += 1
        out["history_only"] = True
        out["route_refused"] = verdict["reason"]
        if age is not None:
            out["age_s"] = round(float(age), 3)
        key = (verdict["reason"], verdict["producer"])
        if not _STATE["open"].get(key):
            _STATE["open"][key] = True
            age_txt = "unknown" if age is None else "%.2f" % float(age)
            source = str(out.get("source") or "")
            _emit_log(
                log,
                f"LIVE_ROUTE_REFUSED reason={verdict['reason']} age_s={age_txt} "
                f"producer={verdict['producer']} route={out.get('route') or 'live'} "
                f"route_owner={_STATE['owner']} "
                f"device={source or _STATE['device'] or 'unknown'} "
                f"text={str(out.get('text') or '')[:60]!r} "
                f"— entra no historico e NAO pinta (refused={_STATE['refused']})")
        return out
    except Exception:  # noqa: BLE001 -- um filtro que parte nao custa a legenda
        return payload


def _emit_log(log, message):
    """O log do worker (`err`) quando existe; silencio quando o chamador nao deu."""
    if log is None:
        return
    try:
        log(message)
    except Exception:  # noqa: BLE001
        pass
