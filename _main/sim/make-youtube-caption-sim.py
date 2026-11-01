#!/usr/bin/env python
"""Gera `_main/sim/youtube-caption-sim.html` -- o payload REAL pelo MESMO motor.

O QUE ESTA PAGINA E', E O QUE NAO E'. O dono pediu para julgar a animacao da
legenda sem abrir a app (e sem a ver no ecra dele). Uma segunda implementacao em
JavaScript julgaria a segunda implementacao, nao a app. Por isso a pagina NAO
tem regra nenhuma: este gerador importa `app/webview/youtube_reveal.py` e
`app/webview/word_fade.py` -- os mesmos ficheiros que a app carrega --, constroi
as linhas do payload com `rows_from_cues` (o produtor do YouTube) e passa o
tempo por `frame(rows, t)`. O que a pagina mostra em cada instante E' o que
`frame` devolveu naquele instante, com os TEXTOS e os ALFAS que ele devolveu.

OS INSTANTES DE AMOSTRAGEM NAO SAO UM COMPASSO FIXO: sao os instantes em que o
motor pode mudar de desenho (o `start` de uma palavra, o `start`/`end` de uma
linha, o comeco e o fim de um *exit*), mais 1/60 s DENTRO de um *exit*, que e' o
unico intervalo em que o alfa muda entre dois instantes destes. Fora de um
*exit* o texto e' constante entre duas palavras e o alfa e' 255: amostrar mais
seria gravar a mesma coisa.

DUAS FONTES, UM MOTOR, NA MESMA PAGINA. O segundo modo entrega as MESMAS palavras
ao `LiveRows` (o produtor do ASR) -- uma frase por `push` no instante em que a
linha do payload nasce, que e' o que o ASR faz (entrega frases a crescer) -- e
replaya-a pelo mesmo `frame`. Se a legenda ao vivo nao se parecer com a do
YouTube, ve-se aqui, lado a lado, sem abrir a app.

    python _main\\sim\\make-youtube-caption-sim.py
    python _main\\sim\\make-youtube-caption-sim.py --out outro.html

Exit: 0 escrito; 2 fixture ausente.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.dirname(HERE)
ROOT = os.path.dirname(MAIN)
PAYLOAD = os.path.join(MAIN, "fixtures", "yt-WdaHAGRBB6s.en-orig.json3")
OUT = os.path.join(HERE, "youtube-caption-sim.html")
WEBVIEW = os.path.join(ROOT, "app", "webview")

#: 1/60 s: dentro de um *exit* o alfa desce 255 -> 0 ao longo de 0,45 s, logo
#: este e' o unico passo que faz a descida parecer uma descida.
STEP_S = 1.0 / 60.0

#: O `">>"` e' o MARCADOR DE MUDANCA DE INTERLOCUTOR do YouTube, nao palavra dita:
#: a transcricao da Google nao o produz. Entrega-lo ao caminho do ASR poria o mesmo
#: `">>"` a abrir duas frases seguidas e o `LiveRows` (que decide a fronteira pelo
#: PREFIXO ESTAVEL) juntava duas frases numa linha so -- um artefacto do payload, e
#: nao um comportamento da app. O modo ao vivo alimenta o motor com o que o ASR de
#: facto entrega: as palavras ditas.
SPEAKER_MARK = ">>"


def asr_text(text):
    """O texto da linha como o ASR o diria -- sem os marcadores do YouTube."""
    words = [w for w in str(text or "").split() if w != SPEAKER_MARK]
    return " ".join(words)


def asr_wrap(text):
    """A quebra do `caption_wrap` com o tecto MEDIDO de 42 caracteres por linha.

    `measure=len` porque aqui nao ha' GDI+: a pagina nao depende de Windows para
    julgar a animacao. O numero que a quebra usa e' o medido (`MAX_CHARS`), e a
    regra (nunca parte uma palavra, re-abre na costura natural, equilibra as duas
    linhas) e' a MESMA funcao que a app chama -- so' a medida da fonte e' que muda.
    """
    import caption_wrap
    import youtube_reveal
    lines, _overflow = caption_wrap.wrap(text, len, youtube_reveal.MAX_CHARS,
                                         max_lines=caption_wrap.UNBOUNDED_LINES)
    return lines


def engine():
    """Os modulos da app, importados do ficheiro -- nao copiados."""
    if WEBVIEW not in sys.path:
        sys.path.insert(0, WEBVIEW)
    import youtube_reveal
    import word_fade
    return youtube_reveal, word_fade


def cues_from_payload(path):
    """`parse_json3` sobre o payload, com a MESMA funcao que a app usa.

    Importa-se `youtube_captions` (o parser da app) e nao se reimplementa o payload:
    se o parser mudar, esta pagina muda com ele -- e e' isso que a torna um
    instrumento em vez de uma maquete. `parse_json3` recebe o TEXTO do documento (e
    nao um `dict`): passar-lhe o objecto devolve `[]` em silencio, que e' o defeito
    que esta funcao existe para nao repetir.
    """
    import youtube_captions
    text = io.open(path, encoding="utf-8").read()
    cues = youtube_captions.parse_json3(text)
    if not cues:
        raise ValueError("parse_json3 devolveu zero cues: %s" % path)
    return cues


def sample_times(rows, capacity, rollup, exit_s):
    """Os instantes em que o DESENHO pode mudar, sem compasso fixo."""
    marks = set()
    for row in rows:
        start = float(row.get("start") or 0.0)
        marks.add(round(start, 4))
        for word in row.get("words") or ():
            marks.add(round(float(word["start"]), 4))
        end = row.get("end")
        if end is not None:
            marks.add(round(float(end), 4))
            marks.add(round(float(end) + exit_s, 4))
    ordered = sorted(marks)
    out = []
    import youtube_reveal
    for left, right in zip(ordered, ordered[1:]):
        out.append(left)
        # DENTRO DE UM EXIT o alfa muda entre dois instantes destes: amostra-se
        # ao ritmo de um quadro. `frame` diz se ha' uma linha a sair.
        if right - left <= STEP_S:
            continue
        mid = (left + right) / 2.0
        if any(mark["exiting"]
               for mark in youtube_reveal.frame(rows, mid, capacity, rollup,
                                                exit_s)):
            t = left + STEP_S
            while t < right:
                out.append(round(t, 4))
                t += STEP_S
    if ordered:
        out.append(ordered[-1])
    return out


def replay(rows, capacity, rollup, exit_s, start_at=0.0):
    """`[{t, rows: [[texto, alfa, a_sair], ...]}]` -- SO' o que `frame` devolveu.

    O alfa vai arredondado a inteiro porque e' um byte no `UpdateLayeredWindow`:
    a pagina mostra o byte que a app escreveria, nao um flutuante mais fino do que
    o ecra.
    """
    import youtube_reveal
    times = sample_times(rows, capacity, rollup, exit_s)
    out = []
    for t in times:
        if t < start_at:
            continue
        marks = youtube_reveal.frame(rows, t, capacity, rollup, exit_s)
        out.append({"t": round(float(t), 4),
                    "rows": [[mark["text"], int(mark["alpha"]),
                              1 if mark["exiting"] else 0] for mark in marks]})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--payload", default=PAYLOAD)
    ap.add_argument("--json", default=None,
                    help="escreve o replay em JSON em vez de julgar nada")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.payload):
        sys.stderr.write("FIXTURE AUSENTE: %s\n" % args.payload)
        return 2
    youtube_reveal, word_fade = engine()
    cues = cues_from_payload(args.payload)
    rows = youtube_reveal.rows_from_cues(cues)
    if not rows:
        sys.stderr.write("SEM LINHAS: o payload nao produziu um cue servivel\n")
        return 2

    cap = youtube_reveal.CAPACITY
    rollup = youtube_reveal.ROLLUP_ROWS
    exit_s = youtube_reveal.EXIT_S
    frames = replay(rows, cap, rollup, exit_s)
    total = frames[-1]["t"] if frames else 0.0

    # O MODO AO VIVO, ao lado: as mesmas frases entregues ao `LiveRows`, amostradas
    # pelo mesmo `frame`. Cada push fecha o estado anterior, logo replaya-se por
    # segmento: um `LiveRows` novo com os pushes ate' `k` e amostragem de
    # `[start_k, start_{k+1})`.
    live_frames = []
    for index in range(len(rows)):
        chunk = youtube_reveal.LiveRows(wrap=asr_wrap, capacity=cap,
                                        rollup=rollup)
        for row in rows[:index + 1]:
            chunk.push(asr_text(row["text"]), float(row["start"]))
        begin = float(rows[index]["start"])
        end = (float(rows[index + 1]["start"]) if index + 1 < len(rows)
               else begin + 3.0)
        step = begin
        while step < min(end, begin + 4.0):
            marks = chunk.frame(step)
            live_frames.append({"t": round(step, 4),
                                "rows": [[mark["text"], int(mark["alpha"]),
                                          1 if mark["exiting"] else 0]
                                         for mark in marks]})
            step += STEP_S
    # Um `t` continuo para o modo ao vivo (as amostras acima repetem-se entre
    # segmentos; o leitor escolhe a ultima amostra com `t <= agora`).
    live_frames.sort(key=lambda item: item["t"])

    payload = {
        "source": os.path.relpath(args.payload, MAIN).replace("\\", "/"),
        "cues": len(cues),
        "rows": len(rows),
        "capacity": cap,
        "rollup": rollup,
        "exit_s": exit_s,
        "gap_s": youtube_reveal.WORD_GAP_S,
        "max_lag_s": youtube_reveal.MAX_LAG_S,
        "word_gap_measured_median_s": 0.24,
        "fade_in_s": getattr(word_fade, "FADE_IN_S", None),
        "fade_frame_s": word_fade.FRAME_S,
        "total_s": round(total, 3),
        "youtube": frames,
        "live": live_frames,
        "live_span_s": round(live_frames[-1]["t"], 3) if live_frames else 0.0,
    }
    if args.json:
        io.open(args.json, "w", encoding="utf-8").write(
            json.dumps(payload, ensure_ascii=False, indent=1))
        print("JSON %s frames=%d live=%d" % (args.json, len(frames),
                                             len(live_frames)))
        return 0

    html = TEMPLATE.replace("__DATA__", json.dumps(payload, ensure_ascii=False,
                                                   separators=(",", ":")))
    io.open(args.out, "w", encoding="utf-8", newline="\n").write(html)
    print("SIM %s" % os.path.relpath(args.out, ROOT).replace("\\", "/"))
    print("  linhas=%d  quadros(youtube)=%d  quadros(live)=%d  duracao=%.2fs"
          % (len(rows), len(frames), len(live_frames), total))
    print("  janela=%d+%d  exit=%.2fs  gap=%.2fs  lag=%.2fs"
          % (cap, rollup, exit_s, youtube_reveal.WORD_GAP_S,
             youtube_reveal.MAX_LAG_S))
    return 0


TEMPLATE = r"""<!doctype html>
<html lang="pt">
<head>
<meta charset="utf-8">
<title>legenda do YouTube -- replay pelo motor do Sotto</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin: 0; background: #101214; color: #e8eaed;
         font: 14px/1.4 "Segoe UI", system-ui, sans-serif; }
  header { padding: 14px 18px 0; }
  h1 { margin: 0 0 4px; font-size: 15px; font-weight: 600; letter-spacing: .01em; }
  .sub { color: #9aa0a6; font-size: 12px; }
  .sub code { color: #bdc1c6; }
  main { display: grid; grid-template-columns: 1fr 320px; gap: 16px; padding: 14px 18px 22px; }
  /* A CAIXA DO VIDEO. 16:9 preto, a legenda em baixo, como no player. */
  .stage { position: relative; aspect-ratio: 16/9; background: #000; border-radius: 10px;
           overflow: hidden; border: 1px solid #2a2d31; }
  .stage .hint { position: absolute; inset: 0; display: grid; place-items: center;
                 color: #3c4043; font-size: 13px; letter-spacing: .08em; text-transform: uppercase; }
  /* A JANELA: 2 linhas do ecra + a que sai. `bottom` sobe quando ha' 3 linhas -- e' o
     mesmo que a app faz ao crescer o bitmap para cima. */
  .window { position: absolute; left: 6%; right: 6%; bottom: 5%;
            display: flex; flex-direction: column; align-items: center; gap: 2px; }
  .row { color: #fff; text-shadow: 0 0 3px #000, 0 0 6px #000;
         font-size: clamp(13px, 2.15vw, 30px); line-height: 1.25;
         font-weight: 600; text-align: center; white-space: pre; }
  .row.exit { color: #fff; }
  .readout { font: 12px/1.5 ui-monospace, Consolas, monospace; color: #bdc1c6; }
  .readout b { color: #e8eaed; font-weight: 600; }
  .bar { display: flex; gap: 10px; align-items: center; margin-top: 10px; flex-wrap: wrap; }
  button { background: #1f2226; color: #e8eaed; border: 1px solid #34383d;
           border-radius: 6px; padding: 6px 12px; font: inherit; cursor: pointer; }
  button:hover { background: #282c31; }
  input[type=range] { flex: 1 1 240px; accent-color: #8ab4f8; }
  .modes { display: flex; gap: 6px; }
  .modes button[aria-pressed=true] { border-color: #8ab4f8; color: #8ab4f8; }
  table { border-collapse: collapse; width: 100%; font: 12px ui-monospace, Consolas, monospace; }
  td { padding: 2px 4px; border-bottom: 1px solid #22252a; vertical-align: top; }
  td.k { color: #9aa0a6; white-space: nowrap; }
  .note { color: #9aa0a6; font-size: 12px; margin-top: 8px; }
</style>
</head>
<body>
<header>
  <h1>legenda do YouTube jogada pelo motor do Sotto</h1>
  <div class="sub">fonte: <code>__SOURCE__</code> &middot; <code>youtube_reveal.frame()</code> amostrado
    &middot; janela <code>__CAP__+__ROLLUP__</code> linhas &middot; exit <code>__EXIT__ s</code></div>
</header>
<main>
  <section>
    <div class="stage">
      <div class="hint">video</div>
      <div class="window" id="window"></div>
    </div>
    <div class="bar">
      <button id="play">play</button>
      <input id="seek" type="range" min="0" max="1" step="0.001" value="0">
      <button id="speed">1x</button>
      <div class="modes">
        <button id="m-youtube" aria-pressed="true">YouTube (payload)</button>
        <button id="m-live" aria-pressed="false">ASR ao vivo</button>
      </div>
    </div>
    <div class="note" id="note"></div>
  </section>
  <aside>
    <div class="readout" id="readout"></div>
    <table id="marks"></table>
    <div class="note">
      Cada letra desta caixa vem do <b>mesmo</b> <code>frame()</code> que a app desenha:
      o texto revelado por linha, o alfa por linha (255 vivo, a descer na que sai) e a
      contagem de linhas. Nada aqui recalcula um relogio.
    </div>
  </aside>
</main>
<script id="sim-data" type="application/json">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('sim-data').textContent);
const $ = (id) => document.getElementById(id);
const win = $('window'), seek = $('seek'), playBtn = $('play'),
      speedBtn = $('speed'), note = $('note'), readout = $('readout'),
      marksTable = $('marks');

let mode = 'youtube', playing = false, speed = 1, t = 0, last = 0;

function frames() { return mode === 'youtube' ? D.youtube : D.live; }
function span() { return mode === 'youtube' ? D.total_s : D.live_span_s; }

/* O FRAME em `t`: a ULTIMA amostra com tempo <= t. E' a propria definicao de
   "amostrar o motor" -- o texto entre duas palavras e' constante, o alfa entre
   dois instantes de um exit nao (logo esses instantes foram amostrados a 1/60 s). */
function frameAt(list, when) {
  let lo = 0, hi = list.length - 1, hit = null;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (list[mid].t <= when + 1e-9) { hit = list[mid]; lo = mid + 1; }
    else hi = mid - 1;
  }
  return hit;
}

function paint() {
  const list = frames();
  const f = frameAt(list, t);
  win.innerHTML = '';
  const rows = f ? f.rows : [];
  for (const [text, alpha, exiting] of rows) {
    const div = document.createElement('div');
    div.className = 'row' + (exiting ? ' exit' : '');
    div.textContent = text;
    /* O ALFA E' DA LINHA, nao da janela: e' o byte que a app escreve na cor da
       linha que sai (o `SourceConstantAlpha` do UpdateLayeredWindow e' um numero
       por janela -- por isso o desvanecimento tem de caber no bitmap). */
    div.style.opacity = (alpha / 255).toFixed(3);
    win.appendChild(div);
  }
  const shown = f ? f.t : 0;
  readout.innerHTML =
    '<b>t</b> ' + shown.toFixed(3) + ' s / ' + span().toFixed(2) + ' s<br>' +
    '<b>modo</b> ' + (mode === 'youtube' ? 'YouTube (payload)' : 'ASR ao vivo') + '<br>' +
    '<b>linhas</b> ' + rows.length + ' (janela ' + D.capacity + ' + ' + D.rollup + ')<br>' +
    '<b>a sair</b> ' + rows.filter(r => r[2]).length + '<br>' +
    '<b>amostras</b> ' + list.length;
  let html = '';
  rows.forEach(([text, alpha, exiting], i) => {
    html += '<tr><td class="k">#' + i + (exiting ? ' out' : '') + '</td>' +
            '<td>' + alpha + '</td><td>' + text.replace(/</g, '&lt;') + '</td></tr>';
  });
  marksTable.innerHTML = html;
  seek.value = String(span() ? t / span() : 0);
}

function tick(now) {
  if (!playing) return;
  const dt = Math.min(0.25, (now - last) / 1000);
  last = now;
  t += dt * speed;
  if (t > span()) { t = span(); playing = false; playBtn.textContent = 'play'; }
  paint();
  if (playing) requestAnimationFrame(tick);
}

function setMode(next) {
  mode = next;
  t = 0;
  $('m-youtube').setAttribute('aria-pressed', String(next === 'youtube'));
  $('m-live').setAttribute('aria-pressed', String(next === 'live'));
  note.textContent = next === 'youtube'
    ? 'O caminho do YouTube: o payload revela palavra a palavra pelo `tOffsetMs`, e a janela \u00e9 2 linhas + a que sai.'
    : 'O caminho do ASR: as MESMAS frases, entregues como o ASR as entrega (uma por linha, no instante em que a linha nasce). O `LiveRows` estaga cada lote pelo intervalo medido (0,24 s) com atraso limitado a 0,36 s.';
  paint();
}

playBtn.onclick = () => {
  playing = !playing;
  playBtn.textContent = playing ? 'pause' : 'play';
  if (playing) { last = performance.now(); requestAnimationFrame(tick); }
};
seek.oninput = () => { t = Number(seek.value) * span(); paint(); };
speedBtn.onclick = () => {
  speed = speed === 1 ? 0.5 : speed === 0.5 ? 0.25 : speed === 0.25 ? 2 : 1;
  speedBtn.textContent = speed + 'x';
};
$('m-youtube').onclick = () => setMode('youtube');
$('m-live').onclick = () => setMode('live');
addEventListener('keydown', (e) => {
  if (e.key === ' ') { e.preventDefault(); playBtn.click(); }
  if (e.key === 'ArrowRight') { t = Math.min(span(), t + 0.25); paint(); }
  if (e.key === 'ArrowLeft') { t = Math.max(0, t - 0.25); paint(); }
});
setMode('youtube');
</script>
</body>
</html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
