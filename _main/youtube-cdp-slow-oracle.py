# NO-BUG: Portao do PRAZO na fonte YouTube (CDP) -- `_main/youtube-cdp-slow-oracle.py`.
"""O PRAZO DE UMA LEITURA NAO DERRUBA A LIGACAO -- e a resposta atrasada nao passa.

O DEFEITO QUE ESTE FICHEIRO RECUSA (MEDIDO na instancia viva, pid 41764, 2026-11-05 17:52)

O laco da fonte CDP dizia, de 10 em 10 segundos:

    YOUTUBE_CDP_SOURCE state=attached
    YOUTUBE_CDP_SOURCE state=slow (WebSocketTimeoutException)
    YOUTUBE_CDP_SOURCE state=reconnect (ValueError)
    YOUTUBE_CDP_SOURCE state=port-closed

A guarda do `except` exterior -- escrita em 2026-11-03 exatamente para NAO fechar
a ligacao num prazo -- nunca era alcancada: o `recv` estourava o prazo e o ramo
fazia `break`, o que deixava `payload=None`, `parse_snapshot(None)` devolvia
None e o laco levantava `ValueError("payload sem forma")`, que NAO e' um
timeout. Resultado: `conn.close()`, `conn=None`, `reconnect`, e no tick seguinte
um `/json/list` que tambem estourava o prazo (maquina carregada) era publicado
como `port-closed` -- um nome que mente sobre a causa. Nos intervalos, a
legenda do YouTube ficava sem leitura.

E o id fixo em 1 deixava a resposta de um pedido cujo prazo estourou ser aceite
no tick seguinte como se fosse a deste: uma foto de um segundo antes publicada
como se fosse agora.

AS ARMS (todas EXECUTAM o laco REAL `CdpCaptionSource._run`; nenhuma procura texto no fonte)

  A1 prazo-nao-e-morte -- um `recv` estoura o prazo e o seguinte responde: a
     ligacao e' a MESMA (uma `create_connection`), o pedido seguinte tem id
     MAIOR, a foto publicada e' a do pedido corrente, e nenhuma linha diz
     `reconnect`.
  A2 atrasada-nao-passa -- a resposta do pedido cujo prazo estourou chega
     DEPOIS, com o id antigo: e' descartada, e a foto com o texto velho nunca e'
     publicada.
  A3 tres-prazos-e-cano-partido -- tres prazos seguidos no mesmo socket fecham a
     ligacao e dizem `slow-dead`, e o laco re-liga (segunda `create_connection`).
     CONTROLE: dois prazos NAO fecham nada.
  A4 nome-honesto      -- `_probe_reason`: recusa de ligacao -> `port-closed`;
     prazo -> `probe-timeout`; qualquer outra -> `probe-failed (<Name>)`.

`--neg-arm` muta uma COPIA do modulo em tres sitios (o `break` que anulava a
guarda, a comparacao de id que aceitava a resposta atrasada, e o nome que
mentia) e exige que AQUELE braco caia; rc=1 quando apanha os tres -- a
convencao `red-as-expected` da bateria. Sem Chrome, sem janela, sem audio: o
transporte e' uma fotografia local e o Chrome do dono nunca e' tocado.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.abspath(os.path.join(HERE, "..", "app", "webview"))
MODULE = os.path.join(APP, "youtube_cdp_source.py")

TAB = {"type": "page",
       "url": "https://www.youtube.com/watch?v=SLOWVID0001",
       "webSocketDebuggerUrl": "ws://127.0.0.1:1/devtools/page/SLOWVID0001"}


def _payload(row):
    return json.dumps({"videoId": "SLOWVID0001", "rs": 1, "paused": False,
                       "t": 1.0, "rate": 1.0,
                       "rows": [{"text": row,
                                 "items": [{"text": row, "left": 0, "top": 0,
                                            "right": 10, "bottom": 10}]}]})


class _Conn:
    """Um WebSocket de fotografia: cada `recv` consome um passo do guiao.

    Passos: `('timeout',)` estoura o prazo; `('reply', texto)` responde ao id
    CORRENTE com `texto`; `('reply-id', id, texto)` responde com um id EXPLICITO
    (e' a resposta atrasada do pedido anterior). Guiao esgotado = prazo.
    """

    def __init__(self, script):
        self.script = list(script)
        self.last_id = None
        self.ids = []
        self.closed = False

    def send(self, data):
        self.last_id = json.loads(data).get("id")
        self.ids.append(self.last_id)

    def recv(self):
        step = self.script.pop(0) if self.script else ("timeout",)
        if step[0] == "timeout":
            raise socket.timeout("the read timed out")
        if step[0] == "reply-id":
            return json.dumps({"id": step[1],
                               "result": {"result": {"value": _payload(step[2])}}})
        return json.dumps({"id": self.last_id,
                           "result": {"result": {"value": _payload(step[1])}}})

    def settimeout(self, _t):
        return

    def close(self):
        self.closed = True


class _Transport:
    def __init__(self, scripts):
        self.scripts = list(scripts)
        self.conns = []

    def create_connection(self, _url, timeout=None):
        script = self.scripts.pop(0) if self.scripts else []
        conn = _Conn(script)
        self.conns.append(conn)
        return conn


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _drive(mod, scripts, want, budget=6.0):
    """(notas, ids, linhas, fotos, conns) -- o laco REAL a correr com guiao."""
    old_tabs = mod.list_targets
    mod.list_targets = lambda port=None, timeout=3.0: ([dict(TAB)], 0)
    transport = _Transport(scripts)
    old_ws = sys.modules.get("websocket")
    sys.modules["websocket"] = transport
    lines = []
    seen = []
    hit = {}
    source = mod.CdpCaptionSource(port=1, poll_s=0.01, log=lines.append)
    source.set_video_id("SLOWVID0001")
    # A SONDA DE "QUEM TOCA" TAMBEM ABRE WEBSOCKETS (nota de instrumento): sem
    # esta linha cada attach consumia um passo do guiao numa ligacao de SONDA e
    # o guiao do laco nunca era o que se media. A escolha aqui e' por URL, pelo
    # `pick_target` real -- a sonda nao e' o que esta arm julga.
    source._playing_pick_for = lambda _tabs: (None, "", "probe-off")
    # O laco so' le enquanto alguem pede: `_last_use` e' o pedido.
    source._last_use = time.monotonic()
    source.start()
    try:
        deadline = time.monotonic() + budget
        while time.monotonic() < deadline:
            snap = source.snapshot(max_age=60.0)
            if snap is not None:
                for row in snap.get("rows") or ():
                    if row not in seen:
                        seen.append(row)
                if want and want in seen:
                    break
            if want is None and len(lines) >= 2:
                break
            time.sleep(0.02)
        # A FOTOGRAFIA NO INSTANTE DO HIT (nota de instrumento): julgar o estado
        # FINAL mede o que o laco fez DEPOIS de a arm ja' ter a sua resposta --
        # o controle de A3 fechava a ligacao nos prazos que vinham a seguir e
        # reprovava por um comportamento que nao e' o que ele julga.
        hit = {"conns": len(transport.conns),
               "closed": [bool(c.closed) for c in transport.conns],
               "lines": list(lines),
               "ids": [i for c in transport.conns for i in c.ids]}
    finally:
        source.stop()
        if source._thread is not None:
            source._thread.join(timeout=3.0)
        mod.list_targets = old_tabs
        if old_ws is None:
            sys.modules.pop("websocket", None)
        else:
            sys.modules["websocket"] = old_ws
    return hit, seen


# -- as arms ---------------------------------------------------------------

def arm_timeout_keeps(mod):
    hit, seen = _drive(mod, [[("timeout",), ("reply", "CURRENT")]], "CURRENT")
    ids = hit.get("ids") or []
    ok = (hit.get("conns") == 1 and len(ids) >= 2 and ids[1] > ids[0]
          and "CURRENT" in seen
          and not any("reconnect" in ln for ln in hit.get("lines") or [])
          and any("slow (" in ln for ln in hit.get("lines") or []))
    return ok, "conns=%r ids=%r seen=%r %r" % (
        hit.get("conns"), ids, seen, (hit.get("lines") or ["-"])[-1][:80])


def arm_stale_reply(mod):
    hit, seen = _drive(
        mod, [[("timeout",), ("reply-id", 1, "STALE"), ("reply", "CURRENT")]],
        "CURRENT")
    ok = "CURRENT" in seen and "STALE" not in seen and hit.get("conns") == 1
    return ok, "conns=%r seen=%r %r" % (hit.get("conns"), seen,
                                        (hit.get("lines") or ["-"])[-1][:80])


def arm_three_timeouts(mod):
    hit, seen = _drive(
        mod, [[("timeout",), ("timeout",), ("timeout",)],
              [("reply", "AFTER")]], "AFTER")
    ok = (hit.get("conns") == 2 and (hit.get("closed") or [False])[0]
          and any("slow-dead" in ln for ln in hit.get("lines") or [])
          and "AFTER" in seen)
    return ok, "conns=%r closed=%r seen=%r %r" % (
        hit.get("conns"), hit.get("closed"), seen,
        (hit.get("lines") or ["-"])[-1][:80])


def control_two_timeouts(mod):
    """CONTROLE de A3: DOIS prazos nao fecham nada -- o terceiro e' o limite."""
    hit, seen = _drive(
        mod, [[("timeout",), ("timeout",), ("reply", "OK")]], "OK")
    ok = (hit.get("conns") == 1 and not (hit.get("closed") or [True])[0]
          and "OK" in seen
          and not any("slow-dead" in ln for ln in hit.get("lines") or []))
    return ok, "conns=%r closed=%r seen=%r %r" % (
        hit.get("conns"), hit.get("closed"), seen,
        (hit.get("lines") or ["-"])[-1][:80])


def arm_probe_reason(mod):
    cases = [(ConnectionRefusedError("no listener"), "port-closed"),
             (socket.timeout("timed out"), "probe-timeout"),
             (RuntimeError("boom"), "probe-failed (RuntimeError)")]
    bad = []
    for exc, want in cases:
        got = mod._probe_reason(exc)
        if got != want:
            bad.append("%s -> %r (want %r)" % (type(exc).__name__, got, want))
    # `urlopen` embrulha o prazo dentro de `URLError.reason`: o nome tem de sair
    # de DENTRO, ou o caso mais comum desta maquina continua a mentir.
    wrapped = OSError("urlopen error")
    wrapped.reason = socket.timeout("timed out")
    if mod._probe_reason(wrapped) != "probe-timeout":
        bad.append("URLError(reason=timeout) -> %r" % mod._probe_reason(wrapped))
    return (not bad), "bad=%r" % (bad,)


def arm_unattached_no_spin(mod):
    """SEM LIGACAO O FIO NAO PODE BATER A PORTA SEM PARAR (2026-11-05, MEDIDO).

    Dois observaveis, ambos sobre o codigo REAL e ambos deterministas:
      (1) a espera entre tentativas DOBRA depois de uma falha (o custo medido na
          instancia viva era 1,5 s de prazo a cada 3,5 s -- 43 % de um fio);
      (2) com uma falha de attach RECENTE e nenhuma ligacao, `target_video_id`
          responde '' sem chamar `list_targets` (o log media 2000 ms por volta,
          de 10 em 10 s, a perguntar a um porto morto que abas existem).
    """
    old_tabs = mod.list_targets
    calls = {"n": 0}

    def _refused(port=None, timeout=3.0):
        calls["n"] += 1
        raise OSError("connection refused")

    mod.list_targets = _refused
    src = None
    try:
        src = mod.CdpCaptionSource(port=1, poll_s=0.01, log=lambda _m: None)
        src._last_use = time.monotonic()
        src.start()
        deadline = time.monotonic() + 6.0
        while (time.monotonic() < deadline
               and int(getattr(src, "_attach_tries", 0)) < 2):
            time.sleep(0.02)
        grew = float(getattr(src, "_retry_s", 0) or 0) >= 4.0
        calls["n"] = 0
        vid = src.target_video_id()
        gated = (vid == "" and calls["n"] == 0)
        # O CONTRARIO TAMBEM E' JULGADO: sem falha recente a sonda ACONTECE (a
        # guarda nao pode virar "nunca sonda") e o resultado dela e' usado.
        src._attach_failed_at = None
        calls["n"] = 0

        def _tabs(port=None, timeout=3.0):
            calls["n"] += 1
            return ([dict(TAB)], 0)

        mod.list_targets = _tabs
        vid2 = src.target_video_id()
        scanned = (calls["n"] == 1 and vid2 == "SLOWVID0001")
    finally:
        if src is not None:
            src.stop()
            if src._thread is not None:
                src._thread.join(timeout=3.0)
        mod.list_targets = old_tabs
    return (grew and gated and scanned), (
        "dobra=%s (retry_s=%r) gate=%s (vid=%r) sonda-livre=%s (%r calls=%d)"
        % (grew, getattr(src, "_retry_s", None), gated, vid, scanned, vid2,
           calls["n"]))


ARMS = [
    ("A1 prazo-nao-e-morte", True, arm_timeout_keeps),
    ("A2 atrasada-nao-passa", True, arm_stale_reply),
    ("A3 tres-prazos-e-cano-partido", True, arm_three_timeouts),
    ("inv controle: dois prazos nao fecham", False, control_two_timeouts),
    ("A4 nome-honesto", True, arm_probe_reason),
    ("A5 sem-ligacao-nao-vira-turbina", True, arm_unattached_no_spin),
]

#: mutacoes de uma COPIA do modulo -- cada uma derruba a arm que a julga.
MUTANTS = [
    ("o break que anulava a guarda do prazo",
     "                    self._stop.wait(min(0.05, self.poll_s))\n"
     "                    continue\n",
     "                    raise ValueError('payload sem forma')\n",
     (0, 1, 2)),
    ("a comparacao de id que aceitava a resposta atrasada",
     '                    if msg.get("id") == _want:\n',
     "                    if True:\n",
     (1,)),
    ("o nome que mentia sobre a causa",
     "    if isinstance(exc, ConnectionRefusedError):\n        return \"port-closed\"\n",
     "    return \"port-closed\"\n",
     (4,)),
    ("a espera que nao dobra (volta a bater a porta a 3,5 s)",
     "                    self._retry_s = min(ATTACH_RETRY_MAX_S, _wait * 2.0)\n",
     "                    self._retry_s = RETRY_S\n",
     (5,)),
    ("a sonda de alvos contra a porta morta (gate desarmado)",
     "        if (_failed is not None and not getattr(self, '_attached', False)\n",
     "        if (_failed is not None and False\n",
     (5,)),
]


def _mutant_module(text, tag):
    tmpdir = tempfile.mkdtemp(prefix="sotto-cdp-slow-")
    copy = os.path.join(tmpdir, "youtube_cdp_source.py")
    with io.open(copy, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    if APP not in sys.path:
        sys.path.insert(0, APP)
    return _load(copy, "sotto_cdp_slow_%s" % tag)


def main():
    neg = "--neg-arm" in sys.argv

    if neg:
        with io.open(MODULE, encoding="utf-8") as fh:
            text = fh.read()
        survived = []
        total = 0
        for idx, (name, old, new, judges) in enumerate(MUTANTS):
            if text.count(old) != 1:
                print("[UNMUTABLE] %s -- o sitio mudou (%d ocorrencias)"
                      % (name, text.count(old)))
                survived.append(name)
                continue
            W = _mutant_module(text.replace(old, new), "m%d" % idx)
            # CADA MUTANTE E' JULGADO PELA SUA ARM (a convencao da casa): julgar
            # o produto cartesiano inteiro acusa um mutante por arms que nao
            # medem o sitio que ele mutou, e esse "blind" e' do instrumento.
            for ai in judges:
                label, fix_arm, run = ARMS[ai]
                total += 1
                try:
                    ok, note = run(W)
                except Exception as exc:        # noqa: BLE001
                    ok, note = False, "EXC %s: %s" % (type(exc).__name__, exc)
                verdict = "SURVIVED" if ok else "RED"
                print("[%s] mutant %r vs %s: %s" % (verdict, name, label, note))
                if ok:
                    survived.append("%s (%s)" % (name, label))
        if survived:
            print("NEG-ARM: FAIL -- %d of %d (mutant, arm) pairs survived:"
                  % (len(survived), total))
            for s in survived:
                print("   blind: %s" % s)
            return 0
        print("NEG-ARM: PASS -- %d arms, %d mutants, every judged arm RED"
              % (total, len(MUTANTS)))
        return 1

    mod = _load(MODULE, "sotto_cdp_slow_fixed")
    failed = 0
    for label, fix_arm, run in ARMS:
        try:
            ok, note = run(mod)
        except Exception as exc:                # noqa: BLE001
            ok, note = False, "EXC %s: %s" % (type(exc).__name__, exc)
        print("[%s] %s arm: %s" % ("PASS" if ok else "FAIL",
                                   "fix" if fix_arm else "inv", label))
        print("       %s" % note)
        if not ok:
            failed += 1
    print("\n%d/%d arms green" % (len(ARMS) - failed, len(ARMS)))
    print("VERDICT: PASS" if not failed else "VERDICT: FAIL")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
