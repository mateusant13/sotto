#!/usr/bin/env python
# BLOCKS: "the caption froze" judged by reading a log AFTER the fact, with no
#         record of what the player actually did at each instant.
# NO-BUG: the external source must be CAPTURED as bytes and replayed offline;
#         observing it and then declaring CANNOT-MEASURE is not a measurement.
"""yt-snapshot-capture -- grava o comportamento EXATO do player por instante.

O DEFEITO QUE ISTO FECHA (medido 2026-11-26).

A queixa do dono -- *"subtitles worked for like 2 seconds and then froze, when I
unpaused it still did not work"* -- foi investigada sobre o log da shell, que
publica um TIQUE, nao o estado do player naquele instante. Sem a foto do player
(posicao, `paused`, `readyState`, a linha de legenda visivel) por instante, toda
hipotese sobre "pausou quando nao devia" e' uma leitura de segunda mao.

E a conclusao anterior desta lane -- "o playback de uma lane e' impossivel,
`LOGIN_REQUIRED`" -- era FALSA para o video errado. MEDIDO 2026-11-26 nesta
maquina, perfil de lane limpo, `--headless=new`: `dQw4w9WgXcQ` da'
`playabilityStatus=OK`, `readyState=4`, `currentTime` a avancar, **6 faixas de
legenda**. O `LOGIN_REQUIRED` era daquele video (um anime), nao do YouTube.

O QUE ESTE FICHEIRO FAZ
-----------------------
Abre a SuA Chrome (porta propria, perfil proprio), navega para o video e grava,
a cada `--interval-ms`, um registo com DOIS carimbos (epoch e perf_counter) e o
estado que o produto le': `currentTime`, `paused`, `readyState`, `duration`,
`playbackRate`, o texto do segmento de legenda visivel (`#ytp-caption-segment`),
as linhas da janela de legenda e o `state` que o player declara. Em paralelo ele
EXECUTA um guiao (`play`, `pause`, `seek`) e marca cada acao com o instante em
que a pediu -- e' isso que permite julgar depois "o ecra devia ter apagado ou
nao" contra o que o player FEZ, nao contra o que o log disse.

A saida e' um fixture JSON com `schema`, `video`, `interval_s`, `script`,
`samples` e `track`, na mesma familia dos que ja' vivem em `_main/fixtures/`
(`yt-caption-clock-replay-20261104.json`, `yt-paint-freeze-20261104.json`).

Uso:
    python _main/yt-snapshot-capture.py --video dQw4w9WgXcQ --seconds 40 \\
        --out _main/fixtures/yt-snapshot-<video>-<data>.json
    python _main/yt-snapshot-capture.py --port 9341 --no-launch   # Chrome ja' aberto

NUNCA toca na porta 9222, no perfil do dono, nos tabs dele ou no dispositivo de
audio: o Chrome e' largado escondido com `--mute-audio` e o perfil e' apagado no
fim pelo caminho exato que este processo criou.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
DEFAULT_PORT = 9340
FORBIDDEN_PORTS = {9222}
CHROME_CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
)
FLAGS = [
    "--headless=new", "--remote-debugging-address=127.0.0.1", "--mute-audio",
    "--autoplay-policy=no-user-gesture-required", "--no-first-run",
    "--no-default-browser-check", "--disable-background-timer-throttling",
    "--disable-renderer-backgrounding", "--disable-backgrounding-occluded-windows",
    "--window-size=1280,720",
]
#: O `state` que o produto consome sai do proprio player. Uma expressao, um leitor.
SAMPLE_JS = r"""(() => {
  const mp = document.querySelector('#movie_player');
  const v = document.querySelector('video');
  if (!mp || !v) return {missing: !mp ? 'player' : 'video'};
  const segs = Array.from(document.querySelectorAll('.ytp-caption-segment'))
    .map(e => e.textContent).filter(t => t && t.trim());
  const win = document.querySelector('.ytp-caption-window-container');
  const rows = win ? Array.from(win.querySelectorAll('.caption-visual-line'))
    .map(e => e.textContent.trim()).filter(Boolean) : [];
  let pr = null;
  try { pr = mp.getPlayerResponse ? mp.getPlayerResponse() : null; } catch (e) {}
  const tracks = ((pr && pr.captions && pr.captions.playerCaptionsTracklistRenderer &&
    pr.captions.playerCaptionsTracklistRenderer.captionTracks) || []).length;
  return {
    t: v.currentTime, paused: v.paused, ready: v.readyState, dur: v.duration,
    rate: v.playbackRate, muted: v.muted, vol: v.volume,
    seg: segs.length ? segs[segs.length - 1] : null, segs: segs.length,
    rows: rows.length, row_text: rows.length ? rows[rows.length - 1] : null,
    tracks: tracks
  };
})()"""


def find_chrome():
    for c in CHROME_CANDIDATES:
        if os.path.exists(c):
            return c
    return None


def http_json(url, timeout=5):
    return json.load(urllib.request.urlopen(url, timeout=timeout))


def port_up(port):
    try:
        http_json("http://127.0.0.1:%d/json/version" % port, timeout=1)
        return True
    except Exception:
        return False


def launch(port, profile):
    chrome = find_chrome()
    if not chrome:
        raise SystemExit("CANNOT-MEASURE why=no-chrome")
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0
    proc = subprocess.Popen(
        [chrome, "--user-data-dir=" + profile, "--remote-debugging-port=%d" % port] + FLAGS
        + ["about:blank"],
        creationflags=0x08000000 | 0x00000008, startupinfo=si,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(80):
        if port_up(port):
            return proc
        if proc.poll() is not None:
            break
        time.sleep(0.25)
    raise SystemExit("CANNOT-MEASURE why=chrome-did-not-answer port=%d" % port)


class Session:
    """Um alvo CDP. `Runtime.evaluate` e' o UNICO leitor do estado do player."""

    def __init__(self, ws_url):
        import websocket  # noqa: PLC0415 -- dependencia opcional, falha nomeada abaixo
        self.ws = websocket.create_connection(ws_url, timeout=30)
        self._id = 0

    def cmd(self, method, **params):
        self._id += 1
        self.ws.send(json.dumps({"id": self._id, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self._id:
                if "error" in msg:
                    raise RuntimeError("%s: %s" % (method, msg["error"]))
                return msg.get("result", {})

    def js(self, expr):
        r = self.cmd("Runtime.evaluate", expression=expr, returnByValue=True,
                     awaitPromise=True)
        return r.get("result", {}).get("value")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def free_target(port, timeout=30.0):
    """A primeira aba `page` cujo websocket responde."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            tabs = [t for t in http_json("http://127.0.0.1:%d/json/list" % port)
                    if t.get("type") == "page"]
            if tabs:
                return tabs[0]
        except Exception:
            pass
        time.sleep(0.25)
    raise SystemExit("CANNOT-MEASURE why=no-page-target port=%d" % port)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--video", default="dQw4w9WgXcQ")
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--interval-ms", type=float, default=50.0)
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-launch", action="store_true",
                    help="usa um Chrome JA' aberto na porta (nao larga nem apaga nada)")
    args = ap.parse_args(argv)

    if args.port in FORBIDDEN_PORTS:
        # A porta do DONO nao se toca. Recusa por nome, nunca por convencao.
        raise SystemExit("CANNOT-MEASURE why=forbidden-port port=%d (that is the owner's "
                         "Chrome; a lane uses its own)" % args.port)

    profile = None
    proc = None
    if not args.no_launch:
        profile = os.path.join(os.environ.get("TEMP", r"I:\cc-tmp"),
                               "sotto-snap-%d" % os.getpid())
        shutil.rmtree(profile, ignore_errors=True)
        if port_up(args.port):
            raise SystemExit("CANNOT-MEASURE why=port-busy port=%d" % args.port)
        proc = launch(args.port, profile)

    try:
        target = free_target(args.port)
        sess = Session(target["webSocketDebuggerUrl"])
        try:
            sess.cmd("Page.enable")
            sess.cmd("Runtime.enable")
            url = "https://www.youtube.com/watch?v=%s" % args.video
            sess.cmd("Page.navigate", url=url)
            # A CARGA e' um RELOGIO, nao uma espera fixa: pronto = readyState>=2.
            ready_deadline = time.monotonic() + 45.0
            status = None
            while time.monotonic() < ready_deadline:
                status = sess.js(SAMPLE_JS)
                if isinstance(status, dict) and status.get("ready", 0) >= 2:
                    break
                time.sleep(0.25)
            if not isinstance(status, dict) or status.get("ready", 0) < 2:
                raise SystemExit("CANNOT-MEASURE why=no-media readyState=%r"
                                 % (status or {}).get("ready"))

            # LIGAR A LEGENDA, senao o fixture mente que o produto nao desenhou
            # nada. MEDIDO 2026-11-26: sem isto o player publica 6 faixas e ZERO
            # segmento (`with_segment=0`), e um fixture sem cue nao julga um cue.
            # A faixa escolhida segue a politica do produto: pt-BR primeiro (um
            # video em pt-BR sai como esta'), depois `en`.
            picked = sess.js(
                "(()=>{const mp=document.querySelector('#movie_player');"
                "const r=mp&&mp.getPlayerResponse?mp.getPlayerResponse():null;"
                "const tr=((r&&r.captions&&r.captions.playerCaptionsTracklistRenderer)||{})"
                ".captionTracks||[];"
                "const pick=tr.find(t=>/^pt/i.test(t.languageCode||''))||"
                "tr.find(t=>t.kind==='asr')||tr[0];"
                "if(!pick)return null;"
                "try{mp.loadModule&&mp.loadModule('captions');}catch(e){}"
                "try{mp.setOption('captions','track',pick);}catch(e){}"
                "return {lang:pick.languageCode,kind:pick.kind||null}})()")
            cc_deadline = time.monotonic() + 10.0
            first_seg = None
            while time.monotonic() < cc_deadline:
                st = sess.js(SAMPLE_JS)
                if isinstance(st, dict) and st.get("seg"):
                    first_seg = st["seg"]
                    break
                time.sleep(0.25)
            if first_seg is None:
                print("YT-SNAP CC pressed lang=%r but no segment within 10 s"
                      % (picked or {}).get("lang"))
            else:
                print("YT-SNAP CC on lang=%r first_seg=%r"
                      % ((picked or {}).get("lang"), first_seg[:60]))

            script = [
                (0.0, "play", "(()=>{document.querySelector('video').play();return 1})()"),
                (6.0, "pause", "(()=>{document.querySelector('video').pause();return 1})()"),
                (10.0, "play", "(()=>{document.querySelector('video').play();return 1})()"),
                (15.0, "seek", "(()=>{const v=document.querySelector('video');v.currentTime=v.currentTime+8;return 1})()"),
            ]
            samples, actions = [], []
            t0 = time.monotonic()
            wall0 = time.time()
            step = args.interval_ms / 1000.0
            si = 0
            while True:
                now = time.monotonic() - t0
                if now >= args.seconds:
                    break
                while si < len(script) and now >= script[si][0]:
                    at, name, expr = script[si]
                    sess.js(expr)
                    actions.append({"at_s": round(now, 4), "action": name,
                                    "epoch_ms": int(time.time() * 1000)})
                    si += 1
                state = sess.js(SAMPLE_JS)
                if isinstance(state, dict) and not state.get("missing"):
                    state["at_s"] = round(now, 4)
                    state["perf_ms"] = round(now * 1000.0, 3)
                    state["epoch_ms"] = int(time.time() * 1000)
                    samples.append(state)
                time.sleep(step)

            track = sess.js(
                "(()=>{const mp=document.querySelector('#movie_player');"
                "const r=mp&&mp.getPlayerResponse?mp.getPlayerResponse():null;"
                "const tr=(r&&r.captions&&r.captions.playerCaptionsTracklistRenderer||{})"
                ".captionTracks||[];return tr.map(t=>({lang:t.languageCode,kind:t.kind||null,"
                "name:(t.name&&(t.name.simpleText||(t.name.runs||[]).map(x=>x.text).join('')))||null}))})()")
        finally:
            sess.close()

        out = args.out or os.path.join(
            HERE, "fixtures", "yt-snapshot-%s-%s.json"
            % (args.video, time.strftime("%Y%m%d-%H%M%S")))
        payload = {
            "schema": "sotto.yt-snapshot.v1",
            "measured_on": time.strftime("%Y-%m-%d"),
            "captured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "video": args.video,
            "url": url,
            "interval_s": step,
            "wall0_epoch_ms": int(wall0 * 1000),
            "script": [{"at_s": a, "action": n} for a, n, _ in script],
            "actions": actions,
            "track": track or [],
            "samples": samples,
            "counts": {
                "samples": len(samples),
                "with_segment": sum(1 for s in samples if s.get("seg")),
                "paused_samples": sum(1 for s in samples if s.get("paused")),
                # Um salto e' QUALQUER descontinuidade: para tras e' o mais
                # perigoso (`SEEK_BACK_S`) e a versao anterior so' contava os
                # para a frente -- medido 2026-11-26: o seek levou 10.84 -> 0.58
                # e o contador disse `seek_jumps=0`.
                "seek_jumps_fwd": sum(1 for a, b in zip(samples, samples[1:])
                                      if (b.get("t") or 0) - (a.get("t") or 0) > 1.0),
                "seek_jumps_back": sum(1 for a, b in zip(samples, samples[1:])
                                       if (b.get("t") or 0) - (a.get("t") or 0) < -0.5),
            },
        }
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
        c = payload["counts"]
        print("YT-SNAP OK video=%s samples=%d with_segment=%d paused=%d seek_fwd=%d "
              "track=%d interval_ms=%.0f -> %s"
              % (args.video, c["samples"], c["with_segment"], c["paused_samples"],
                 c["seek_jumps_fwd"], len(payload["track"]), args.interval_ms * 1000.0, out))
        print("YT-SNAP seek_back=%d" % c["seek_jumps_back"])
        # Um fixture SEM cue e' um fixture que nao testa a legenda. Nomeia-se.
        if not c["with_segment"]:
            print("YT-SNAP CANNOT-MEASURE why=no-caption-segment (the player never "
                  "painted a caption in this window; the fixture cannot judge a cue)")
        return 0
    finally:
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=10)
            except Exception:
                pass
        if profile and os.path.isdir(profile):
            shutil.rmtree(profile, ignore_errors=True)
            print("YT-SNAP teardown profile_removed=%s"
                  % (not os.path.isdir(profile)))


if __name__ == "__main__":
    sys.exit(main())
