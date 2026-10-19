#!/usr/bin/env python
"""speaker_bridge.py -- READ a diarization somebody else already computed.

WHY A BRIDGE AND NOT A MODEL IN HERE. The owner, 2026-10-18, verbatim:
    "PARA DE FAZER MEU PC TRAVAR. AGORA."
and the acceptance:
    "e mostra pra mim a legenda ao vivo ou o parakeet processando os audios do
     discord meu e dos meus amigos. de forma natural, encaixa no sotto"

Putting a diarizer inside the worker would mean a second set of weights in the
same process that already holds 1,2-2 GB of ASR. Measured today on this box
(`_main/_hoje-ctrl.json`): the diarizer alone costs **277 MB RSS**, 0,9 s to
load, **RTF 0,416** -- it is not free, and on a two-core box fighting a Discord
call the owner is the one who pays.

So the split is: SOMETHING ELSE runs the model and writes a JSON payload; this
file, and `speaker_id`, only ever READ it. That keeps three promises:

  * the worker gains a file read, not a model
  * with no payload the behaviour is EXACTLY what it was -- same captions, same
    `source`, same bytes on the wire
  * the expensive part can be started, stopped and re-run on a recording without
    the app ever noticing

THE ONE DANGER, and it is why this file exists rather than four lines inline.
A payload that is STALE is worse than no payload at all: it will confidently
label a stranger's voice as "speaker-1" for as long as the app runs. So a
payload is only honoured while it is FRESH, and "fresh" is measured against the
file's own mtime. When the diarizer stops -- or crashes, or the owner closes the
call -- attribution goes quiet on its own, with no flag and no timeout thread.

ALSO: the file is written by another process WHILE this one reads it. A partial
read must be an ordinary answer here, not an exception. Every failure path below
returns `None`, never raises, because the caller's alternative is a transcription
that dies because a neighbour was halfway through writing a file.
"""
from __future__ import annotations

import json
import os
import time

from speaker_id import attribute_from_payload, summarize

# Where the sidecar writes. Relative to the WORKER, so a worktree without
# `_main/` simply finds nothing and carries on -- see `payload_if_fresh`.
DEFAULT_PAYLOAD = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), os.pardir, "_main", "diar-live.json"))

#: How old a payload may be before it is treated as a lie. The diarizer's own
#: cadence is a few seconds; anything older means the sidecar stopped.
DEFAULT_MAX_AGE_S = 30.0

#: Refuse to even parse a file bigger than this. A payload is kilobytes; if the
#: path is wrong it is probably a WAV, and `json.loads` on one would cost the
#: owner a gigabyte of his RAM for nothing.
MAX_PAYLOAD_BYTES = 4 * 1024 * 1024


def payload_if_fresh(path: str = DEFAULT_PAYLOAD,
                     max_age_s: float = DEFAULT_MAX_AGE_S,
                     now: float = None) -> object:
    """The payload dict, or `None` for every reason there is to refuse one.

    `None` means "carry on exactly as before". It is returned for: the file is
    absent; it is empty; it is being written right now and caught mid-flush; it
    is not JSON; it is missing the `segments` a caller would need; it is older
    than `max_age_s`; or it is too big to be a payload. Each of those is a normal
    condition on a machine with another process writing to it.
    """
    try:
        if now is None:
            now = time.time()
        stat = os.stat(path)
    except OSError:
        return None
    try:
        age = float(now) - stat.st_mtime
    except (TypeError, ValueError):
        return None
    if age > max_age_s:
        return None
    if stat.st_size <= 0 or stat.st_size > MAX_PAYLOAD_BYTES:
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("segments"), list):
        return None
    return payload


def apply_to_lines(lines, base_source=None, payload=None,
                   min_overlap: float = 0.30, epoch=None):
    """Caption lines in, caption lines out. The `speaker` field rides along.

    With `payload=None` this is a pass-through that stamps `speaker: None` and
    leaves `source` alone, which is the OFF behaviour and the one the rest of
    the app already sees today.

    `epoch` is the worker's capture start on the WALL CLOCK. Pass it and the
    lookup window is moved into the payload's frame; the line's own `start`/`end`
    are NOT rewritten, because those travel on to the panel, the history and the
    transcript. See `speaker_id.attribute_from_payload` for why this cannot be
    left implicit.
    """
    return attribute_from_payload(payload, lines, base_source=base_source,
                                  min_overlap=min_overlap,
                                  window_offset=epoch or 0.0)


class PayloadCache:
    """Re-read the payload only when the file actually CHANGED.

    WHY THIS EXISTS, measured on the shape of the live path rather than
    guessed: the caption path calls `_event` on every partial, and this
    worker emits partials at a rate the panel drives. Re-opening and re-parsing
    a JSON file dozens of times a second to discover it has not changed is work
    the owner pays for and gets nothing from.

    The cache key is the file's own `mtime`. An `os.stat` is cheap; the parse
    is not, and it only happens when the sidecar has published something new.

    THE FAILURE THIS IS CAREFUL ABOUT. A payload that is cached must still be
    allowed to DIE: if the sidecar stops, the file stops moving, and a cache
    that only ever compared mtimes would serve the last payload FOREVER. So
    staleness is re-checked on every call, and a payload past `max_age_s`
    returns None and is dropped. Attribution going quiet by itself is the
    behaviour that makes this safe to leave enabled.
    """
    def __init__(self, path: str = DEFAULT_PAYLOAD,
                 max_age_s: float = DEFAULT_MAX_AGE_S):
        self.path = path
        self.max_age_s = max_age_s
        self._mtime = None
        self._payload = None

    def __call__(self):
        try:
            mtime = os.stat(self.path).st_mtime
        except OSError:
            self._mtime, self._payload = None, None
            return None
        if mtime != self._mtime:
            self._mtime = mtime
            self._payload = payload_if_fresh(self.path, self.max_age_s)
        if self._payload is not None:
            try:
                if (time.time() - mtime) > self.max_age_s:
                    self._payload = None
            except (TypeError, ValueError):
                self._payload = None
        return self._payload


def voices(payload=None) -> dict:
    """What the status strip may say: how many voices, and which is which."""
    if payload is None:
        return {"n_speakers": 0, "n_segments": 0, "speech_s": 0.0, "labels": {}}
    return summarize(payload)


# ===========================================================================
# FASE A -- "havia duas vozes ao mesmo tempo?", lido de UM OUTRO ficheiro.
# ===========================================================================
#
# A Fase A (o sidecar com `--watch-only`) escreve `_main/diar-watch.json`. E'
# um ficheiro SEPARADO, com uma chave SEPARADA, e um leitor SEPARADO, por uma
# razao que nao e' de estilo:
#
#   `payload_if_fresh` acima devolve `None` quando falta `segments`. Logo um
#   payload de watch -- que por desenho NAO tem `segments` -- nunca pode ser
#   tomado por uma lista de vozes. Nao ha nenhuma combinacao de estado em que o
#   caminho das legendas veja um payload de watch: ele pede `segments`, nao a
#   encontra, e segue em frente como se nada tivesse sido medido. Isso e' o que
#   torna a Fase A segura de ter ligada enquanto a separacao esta desligada --
#   "nao medido" nunca pode aparecer no painel como "medido: zero vozes".
#
# O que o leitor NAO faz, deliberadamente: nao decide nada sozinho. Ele devolve o
# que foi observado e quem quiser decide. A politica de "quando e' seguro processar
# as vozes" e' do dono, e nao se adivinha aqui.

DEFAULT_WATCH_PAYLOAD = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), os.pardir, "_main", "diar-watch.json"))

#: A chave que separa as duas metades. O payload de watch nunca a traz; o
#: payload de fala nunca tem `multivoice`. Um leitor que trocasse os ficheiros
#: devolveria `None` duas vezes, e nao um resultado falso.
WATCH_KEY = "multivoice"


def watch_payload_if_fresh(path: str = DEFAULT_WATCH_PAYLOAD,
                           max_age_s: float = DEFAULT_MAX_AGE_S,
                           now: float = None) -> object:
    """O payload da Fase A, ou `None` por qualquer razao para recusar um.

    Mesma politica de `payload_if_fresh` -- um ficheiro em ausencia, vazio, a
    meio de uma escrita, que nao e' JSON, velho demais ou grande demais dao
    `None`, e `None` significa "nada mudou, continua como antes" -- com uma
    exigencia acrescida: a lista `multivoice` tem de existir E ser lista. Um
    payload de watch sem spans e' um payload de watch legitimo (o detector
    disparou zero vezes nessa janela), e por isso NAO e' `None`: seria
    indistinguivel de "o sidecar morreu", que e' a unica coisa que `None` tem de
    significar aqui.
    """
    try:
        if now is None:
            now = time.time()
        stat = os.stat(path)
    except OSError:
        return None
    try:
        age = float(now) - stat.st_mtime
    except (TypeError, ValueError):
        return None
    if age > max_age_s:
        return None
    if stat.st_size <= 0 or stat.st_size > MAX_PAYLOAD_BYTES:
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get(WATCH_KEY), list):
        return None
    # A Guarantee, verificada aqui e nao apenas comentada: este payload nao
    # pode ser lido como uma lista de vozes.
    if isinstance(payload.get("segments"), list):
        return None
    return payload


def multivoice(payload=None) -> dict:
    """O que a Fase A tem a dizer, em forma curta.

    `None` significa "nada foi observado" e devolve `measured=False`, para que
    quem ler possa distinguir "o detector corria e nao viu nada" de "o detector
    nao esta a correr" -- que sao situacoes que pedem reaccoes opostas.
    """
    if payload is None:
        return {"measured": False, "multivoice": False, "n_spans": 0,
                "multivoice_s": 0.0, "spans": [], "written_at": 0.0}
    spans = payload.get(WATCH_KEY) or []
    n = len(spans)
    total = 0.0
    for s in spans:
        try:
            total += float(s.get("s") or 0.0)
        except (TypeError, ValueError, AttributeError):
            continue
    return {"measured": True, "multivoice": n > 0, "n_spans": n,
            "multivoice_s": round(total, 3), "spans": spans,
            "written_at": float(payload.get("written_at") or 0.0)}