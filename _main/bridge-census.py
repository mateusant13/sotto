#!/usr/bin/env python3
"""O CENSO DO BRIDGE -- o que esta' preso, no instante em que esta' preso.

PORQUE EXISTE. `exec_js TIMEOUT after 10.0s` apareceu 515 vezes no log vivo do
dono (`_main/webview-run.log`, contado com `grep -c`), e a linha NAO diz onde o
tempo foi: pode ter sido o UI thread a nao correr o callable, o renderer a nao
responder ao `ExecuteScriptAsync`, ou a continuacao .NET a nao entrar em Python.
Sao tres donos diferentes e dois deles exigem correccoes opostas. Um numero nao
e' um diagnostico.

`py-spy dump` esta' NEGADO nesta maquina (os error 5, medido hoje), portanto a
stack tem de sair de dentro do processo: `sys._current_frames()` por
`threading.enumerate()` no momento em que o orcamento estoura.

O QUE MEDE, e cada campo responde a um candidato:

  `status=`         o `System.Threading.Tasks.Task.Status` do
                    `ExecuteScriptAsync`. `RanToCompletion` com a espera a
                    estourar significa que o JS respondeu e a CONTINUACAO .NET
                    nao entrou em Python (scheduler/GIL). `Waiting*`/`Running`
                    significa que o renderer nunca devolveu nada.
  `continuation=`   `set` ou `unset` -- o `_complete` correu ou nao. Um
                    `RanToCompletion` acompanhado de `continuation=unset` e' a
                    prova directa de que o problema esta' do lado Python/.NET.
  `marshal_ms=`     quanto tempo o `_ui` levou a correr o callable no UI thread.
                    Alto = UI thread ocupado; baixo = o UI thread estava livre e
                    o suspeito nao e' ele.
  `gil_gap_ms=`     o maior intervalo que uma thread que dorme 5 ms viu. Uma
                    thread de tick que nao consegue re-adquirir o GIL durante N
                    segundos mede exactamente "o interpretador nao correu".
  `threads=`        o censo: nome, ident, daemon e a stack Python de cada
                    thread. Sem isto nao ha' "quem estava preso".

COMO SE LIGA. `SOTTO_BRIDGE_CENSUS=1` no ambiente da instancia de medicao. O
shell importa este ficheiro a' primeira chamada de `exec_js` (ver
`_bridge_census()` em `app/webview/sotto_webview.py`); sem a variavel nao ha'
import, nem thread, nem custo. Nenhuma linha de produto depende deste ficheiro.

USO DIRECTO (fora do shell): `python _main/bridge-census.py` imprime o censo do
processo actual -- so' serve para provar que a extracção de stacks funciona.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time

#: O intervalo da thread de tick. A 5 ms, uma pausa de 10 s aparece como
#: `gil_gap_ms=10000` em vez de se perder na media.
TICK_S = 0.005
#: Quantas frames por thread entram no censo. Tres chegam para ver a chamada
#: (`exec_js` -> `_ui` -> `Event.wait`) sem transformar o log numa parede.
FRAMES_PER_THREAD = 4
#: Acima disto uma chamada que RESPONDEU ainda e' digna de uma linha. Um log com
#: `exec_js_timeout=0` e zero chamadas escreve o mesmo que um canal saudavel;
#: este limiar e' o que separa os dois.
SLOW_MS = 1000.0
#: Uma linha de resumo a cada N respostas (e na primeira), para o log de um run
#: longo dizer quantas chamadas houve e qual foi a pior.
SUMMARY_EVERY = 250


def _where(frame, depth=FRAMES_PER_THREAD):
    """`ficheiro:linha:funcao` de uma frame e dos seus chamadores."""
    out = []
    while frame is not None and len(out) < depth:
        try:
            code = frame.f_code
            out.append('%s:%d:%s' % (os.path.basename(code.co_filename),
                                     frame.f_lineno, code.co_name))
        except Exception:  # noqa: BLE001 -- uma frame morta nao mata o censo
            out.append('?')
        frame = frame.f_back
    return '<-'.join(out)


class Census:
    """Um censo por processo. Construido quando o shell pede, nunca antes."""

    def __init__(self, log, tick_s=TICK_S):
        self._log = log
        self._tick_s = float(tick_s)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._started = time.monotonic()
        #: O maior intervalo entre dois despertares da thread de tick. E' o GIL
        #: preso, medido de dentro: o timer acorda, a thread nao volta a correr.
        self.gil_gap_ms = 0.0
        self.gil_gap_at = None
        self.calls = 0
        self.answered = 0
        self.noanswer = 0
        self.slow = 0
        self.max_marshal_ms = 0.0
        self.max_task_ms = 0.0
        self._ticker = threading.Thread(target=self._tick, name='bridge-census',
                                        daemon=True)
        self._ticker.start()

    # -- a thread de tick: mede o GIL de dentro ---------------------------
    def _tick(self):
        last = time.monotonic()
        while not self._stop.wait(self._tick_s):
            now = time.monotonic()
            gap = (now - last) * 1000.0
            last = now
            # `Event.wait` devolve o controlo ao interpretador; se o GIL estiver
            # tomado por outra thread, esta linha so' corre quando ele voltar --
            # e o intervalo medido e' exactamente o tempo em que Python NAO correu.
            if gap > self.gil_gap_ms:
                with self._lock:
                    self.gil_gap_ms = gap
                    self.gil_gap_at = time.strftime('%H:%M:%S') + '.%03d' % (
                        int((now % 1) * 1000))

    def stop(self):
        self._stop.set()

    # -- as fases de uma chamada de `exec_js` ----------------------------
    def call(self, script, timeout):
        """Marca o inicio. Devolve o token que as fases seguintes carregam."""
        self.calls += 1
        return {'t0': time.monotonic(), 'script': (script or '')[:90],
                'budget': float(timeout), 'marshal_ms': None}

    def phase(self, token, name, ms):
        """Uma fase da chamada. `name` e' `marshal` ou `task`."""
        token[name + '_ms'] = round(float(ms), 1)
        if name == 'marshal':
            with self._lock:
                if token['marshal_ms'] > self.max_marshal_ms:
                    self.max_marshal_ms = token['marshal_ms']

    def answer(self, token):
        """Uma resposta CHEGOU. Regista o tempo e, se foi lenta, escreve-o.

        `BRIDGE_CENSUS kind=slow` e' o outro lado da moeda: um `exec_js` que
        responde em 800 ms num renderer suspenso e' a prova de que o canal esta'
        vivo e de que o que estoura nao e' "o renderer" em geral -- e' o task que
        nao foi servido. Sem esta linha, um log com `exec_js_timeout=0` nao
        distingue "nao houve estouro" de "nao houve chamada nenhuma".
        """
        self.answered += 1
        elapsed = None
        if token and token.get('t0'):
            elapsed = (time.monotonic() - token['t0']) * 1000.0
            if token.get('task_ms') is None:
                token['task_ms'] = round(elapsed, 1)
            with self._lock:
                if elapsed > self.max_task_ms:
                    self.max_task_ms = elapsed
        if elapsed is not None and elapsed > SLOW_MS:
            self.dump('slow', token)
        if self.answered == 1 or self.answered % SUMMARY_EVERY == 0:
            self._emit(self.summary())

    def no_answer(self, token, debug=None):
        """O orcamento estourou (ou nao houve resposta). CENSO AQUI."""
        self.noanswer += 1
        self.slow += 1
        token['debug'] = debug or {}
        self.dump('timeout', token)

    # -- o censo ---------------------------------------------------------
    def dump(self, kind, token=None):
        token = token or {}
        debug = token.get('debug') or {}
        fields = {
            'kind': kind,
            'script': token.get('script'),
            'budget_ms': None if token.get('budget') is None
            else round(token['budget'] * 1000.0, 1),
            'marshal_ms': token.get('marshal_ms'),
            'task_ms': token.get('task_ms'),
            'elapsed_ms': None if not token.get('t0')
            else round((time.monotonic() - token['t0']) * 1000.0, 1),
            'status': debug.get('status'),
            'continuation': debug.get('continuation'),
            'gil_gap_ms': round(self.gil_gap_ms, 1),
            'gil_gap_at': self.gil_gap_at,
            'calls': self.calls,
            'answered': self.answered,
            'noanswer': self.noanswer,
            'uptime_s': round(time.monotonic() - self._started, 1),
        }
        self._emit('BRIDGE_CENSUS ' + ' '.join(
            '%s=%s' % (k, _v(v)) for k, v in fields.items() if v is not None))
        for line in self.threads():
            self._emit('BRIDGE_CENSUS_THREAD ' + line)

    def threads(self):
        """Uma linha por thread: nome, ident, daemon, stack Python."""
        out = []
        frames = sys._current_frames()
        try:
            alive = list(threading.enumerate())
        except Exception:  # noqa: BLE001
            alive = []
        by_ident = {}
        for t in alive:
            try:
                by_ident[t.ident] = t
            except Exception:  # noqa: BLE001
                pass
        if not frames:
            return ['#(none)']
        for ident, frame in sorted(frames.items(), key=lambda kv: str(kv[0])):
            t = by_ident.get(ident)
            if t is None:
                name, daemon, state = '?', '?', 'no-thread-object'
            else:
                name = t.name
                daemon = 'y' if t.daemon else 'n'
                try:
                    state = t._is_stopped and 'stopped' or 'alive'
                except Exception:  # noqa: BLE001
                    state = '?'
            out.append('name=%s ident=%s daemon=%s state=%s where=%s'
                       % (json.dumps(name), ident, daemon, state, _where(frame)))
        return out

    def summary(self):
        return ('BRIDGE_CENSUS_SUMMARY calls=%d answered=%d noanswer=%d '
                'max_marshal_ms=%.1f max_task_ms=%.1f gil_gap_ms=%.1f'
                % (self.calls, self.answered, self.noanswer,
                   self.max_marshal_ms, self.max_task_ms, self.gil_gap_ms))

    def _emit(self, line):
        try:
            self._log(line)
        except Exception:  # noqa: BLE001 -- um censo que cai nao derruba nada
            pass


def _v(value):
    """Um valor numa linha de log: sem espacos, sem quebras."""
    if isinstance(value, str):
        return json.dumps(value)
    return str(value)


#: O censo deste processo, ou None. `attach()` e' o que o shell chama.
_ACTIVE = None
_LOCK = threading.Lock()


def attach(log):
    """Liga o censo a este processo uma vez. Devolve-o (ou None)."""
    global _ACTIVE
    with _LOCK:
        if _ACTIVE is None:
            _ACTIVE = Census(log)
        return _ACTIVE


def active():
    return _ACTIVE
