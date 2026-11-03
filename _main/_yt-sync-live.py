"""COMPARA A LEGENDA DO SOTTO COM A DO PLAYER, DE 5 EM 5 SEGUNDOS.

Ordem do dono (2026-11-03): *"eu falei pra tu controlar e esqueci de avisar que
e' pra tu mesmo ir testando. roda de 5 a 5 segundos e compara as legendas. e nao
faz som me incomodando."*

O QUE ESTE INSTRUMENTO FAZ, e o que ele NAO faz:

  * LE' a pagina do YouTube pela arvore do DOM (`.ytp-caption-segment`) e o
    `currentTime` do `<video>`. Nao clica, nao da play, nao mexe no volume: som
    nenhum sai desta maquina por causa deste ficheiro.
  * LE' o ultimo quadro que o Sotto DECIDIU (`YT_FRAME` / `EXTERNAL_CAPTION_DRAWN`)
    do log vivo.
  * COMPARA os dois e escreve uma linha por ciclo. O veredicto por ciclo e' um
    dos quatro: `SAME`, `OURS-AHEAD` (mostramos o que o player ainda nao
    desenhou -- o *"fora de sync"* de 2026-11-03), `OURS-BEHIND`, `TEXT-DIFF`.

Só a janela de legendas que o PLAYER mostra conta. A comparacao normaliza
espacos e pontuacao de borda, porque a pintura do YouTube parte a linha em
segmentos por estilo (negrito, italico) e o texto visivel e' a juncao deles.

USO:
    python _main/_yt-sync-live.py             # 40 ciclos de 5 s (200 s)
    python _main/_yt-sync-live.py --cycles 12
    python _main/_yt-sync-live.py --tab t5    # a aba do video (default t5)
"""
from __future__ import annotations

import argparse
import base64
import datetime
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LOG = os.path.join(HERE, 'webview-run.log')
OUT = os.path.join(HERE, '_yt-sync-live.txt')
SESSION = 'sotto-yt-tabs'


def _cli():
    """O caminho REAL do `agent-browser` (no Windows e' um `.cmd`).

    Medido 2026-11-03: `subprocess.run(['agent-browser', ...])` levanta
    `FileNotFoundError [WinError 2]` -- o shell resolve o `.cmd` pelo PATH e o
    `CreateProcess` nao. `shutil.which` acha os dois.
    """
    for name in ('agent-browser', 'agent-browser.cmd', 'agent-browser.exe'):
        found = shutil.which(name)
        if found:
            return found
    return 'agent-browser'

PROBE = """(() => {
  try {
    const v = document.querySelector('video');
    const segs = Array.from(document.querySelectorAll('.ytp-caption-segment'))
      .map(e => e.textContent.trim()).filter(Boolean);
    return JSON.stringify({t: v ? Math.round(v.currentTime*1000)/1000 : null,
      paused: v ? v.paused : null, muted: v ? v.muted : null, rows: segs});
  } catch (e) { return JSON.stringify({error: String(e)}); }
})()"""

FRAME = re.compile(r'^(?:\d{4}-\d{2}-\d{2} )?(\d{2}:\d{2}:\d{2}\.\d{3}) .*?'
                   r'(?:YT_FRAME src=\S+ rows=\d+|EXTERNAL_CAPTION_DRAWN rows=\d+) '
                   r'lines=(\[.*\])')


def norm(text):
    text = re.sub(r'\s+', ' ', str(text or '')).strip().lower()
    return text.strip('.,!?;:')


def norm_rows(rows):
    out = []
    for row in rows or ():
        text = norm(row)
        if text and (not out or out[-1] != text):
            out.append(text)
    return out


def read_frame_log():
    """(quando, linhas) do ultimo quadro do Sotto no log vivo."""
    last = None
    if not os.path.exists(LOG):
        return None
    with io.open(LOG, encoding='utf-8', errors='replace') as handle:
        for line in handle:
            match = FRAME.search(line)
            if not match:
                continue
            try:
                lines = json.loads(match.group(2).replace("'", '"'))
            except Exception:
                continue
            last = (match.group(1), [str(x) for x in lines])
    return last


def probe(tab):
    script = base64.b64encode(PROBE.encode('utf-8')).decode('ascii')
    try:
        out = subprocess.run(
            [_cli(), '--session', SESSION, 'eval', '-b', script],
            capture_output=True, text=True, timeout=25)
    except Exception as exc:  # noqa: BLE001
        return {'error': repr(exc)}
    raw = (out.stdout or '').strip()
    if not raw:
        return {'error': (out.stderr or 'sem saida').strip()[:200]}
    try:
        value = json.loads(raw)
        if isinstance(value, str):
            value = json.loads(value)
        return value
    except Exception as exc:  # noqa: BLE001
        return {'error': 'parse %r: %r' % (exc, raw[:160])}


def classify(page_rows, ours):
    """SAME | OURS-AHEAD | OURS-BEHIND | TEXT-DIFF."""
    page = norm_rows(page_rows)
    mine = norm_rows(ours)
    if not page and not mine:
        return 'SAME'
    if page == mine:
        return 'SAME'
    if not page:
        return 'OURS-AHEAD'
    if not mine:
        return 'OURS-BEHIND'
    # A nossa ultima linha pode ser a do player a crescer (palavra incompleta).
    if mine[:-1] == page[:-1] and page[-1].startswith(mine[-1]):
        return 'SAME'
    if mine[-1] and page[-1].startswith(mine[-1].rstrip('.')) and len(mine) >= len(page):
        return 'SAME'
    page_text = ' '.join(page)
    mine_text = ' '.join(mine)
    if page_text.startswith(mine_text):
        return 'OURS-BEHIND'
    if mine_text.startswith(page_text):
        return 'OURS-AHEAD'
    # A linha que sai no player ainda esta' na nossa: comparar sem a primeira.
    if len(mine) > 1 and mine[1:] == page:
        return 'SAME'
    return 'TEXT-DIFF'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--cycles', type=int, default=40)
    ap.add_argument('--period', type=float, default=5.0)
    ap.add_argument('--tab', default='t5')
    args = ap.parse_args(argv)

    subprocess.run([_cli(), '--session', SESSION, 'tab', args.tab],
                   capture_output=True, text=True, timeout=40)
    tally = {}
    with io.open(OUT, 'a', encoding='utf-8') as sink:
        sink.write('\n== %s ==\n'
                   % datetime.datetime.now().isoformat(timespec='seconds'))
        for i in range(args.cycles):
            page = probe(args.tab)
            frame = read_frame_log()
            rows = page.get('rows') or []
            ours = frame[1] if frame else []
            verdict = ('ERROR' if page.get('error')
                       else classify(rows, ours))
            tally[verdict] = tally.get(verdict, 0) + 1
            line = ('%s t=%s paused=%s %-12s player=%r sotto=%r'
                    % (datetime.datetime.now().strftime('%H:%M:%S'),
                       page.get('t'), page.get('paused'), verdict,
                       rows, ours))
            print(line)
            sink.write(line + '\n')
            sink.flush()
            if page.get('error'):
                sink.write('   probe_error=%s\n' % page['error'])
            if i + 1 < args.cycles:
                time.sleep(args.period)
    print('TALLY %r' % (tally,))
    with io.open(OUT, 'a', encoding='utf-8') as sink:
        sink.write('TALLY %r\n' % (tally,))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
