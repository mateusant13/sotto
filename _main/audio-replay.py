"""audio-replay - reouvir e cortar o audio do ring de 12 horas.

ORDEM DO DONO (2026-11-11, verbatim): *"MANTENHA o audio INTEIRO das ultimas 12
horas pra benchmark/replay pra gente melhorar a taxa de acerto de palavras"* e
*"o trecho de audio 'que nao fez sentido' [vai] ate passar por modelo melhor,
depois o audio e deletado"*.

Este e' o LEITOR desse ring. Ele responde as duas perguntas que o benchmark
faz e nada mais:

  --list                os segmentos que existem, com hora e tamanho
  --lines               as linhas fechadas que tem ancora de audio
  --line N              o WAV do audio da linha N (`--lines` numera)
  --from A --to B       o WAV do intervalo (epoch OU `HH:MM:SS` de hoje)
  --corpus OUT          UM wav com todas as linhas ancoradas, em sequencia,
                        para um benchmark rodar de uma vez
  --selftest            prova o ring E este leitor contra uma senoide conhecida

Nada aqui abre janela, toca em dispositivo de audio ou altera o ring: le' o
indice, decodifica o opus com o ffmpeg (`CREATE_NO_WINDOW`) e escreve WAV.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if os.path.join(ROOT, 'worker') not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, 'worker'))

CREATE_NO_WINDOW = 0x08000000
_FFMPEG = os.environ.get('SOTTO_FFMPEG') or 'ffmpeg'


def _hidden():
    si = None
    if os.name == 'nt':
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
    return {'creationflags': CREATE_NO_WINDOW if os.name == 'nt' else 0,
            'startupinfo': si}


def _decode(path, rate, start_s=None, dur_s=None):
    """Opus -> PCM s16le mono. Devolve `bytes`; vazio quando o ficheiro morreu."""
    argv = [_FFMPEG, '-v', 'error', '-nostdin']
    if start_s is not None:
        argv += ['-ss', '%.3f' % max(0.0, start_s)]
    argv += ['-i', path]
    if dur_s is not None:
        argv += ['-t', '%.3f' % max(0.001, dur_s)]
    argv += ['-f', 's16le', '-ac', '1', '-ar', str(rate), 'pipe:1']
    try:
        proc = subprocess.run(argv, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, **_hidden())
    except OSError:
        return b''
    return proc.stdout if proc.returncode == 0 else b''


def _segments(root):
    p = os.path.join(root, 'history', 'audio', 'index.jsonl')
    out = []
    try:
        with open(p, encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                rec['abs'] = os.path.join(root, rec.get('file', ''))
                out.append(rec)
    except OSError:
        return []
    out.sort(key=lambda r: float(r.get('t0', 0)))
    return out


def _lines(root):
    p = os.path.join(root, 'history', 'audio', 'lines.jsonl')
    out = []
    try:
        with open(p, encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        return []
    out.sort(key=lambda r: float(r.get('t0', 0)))
    return out


def _cut(segments, t0, t1):
    """PCM s16le do intervalo [t0, t1] (epoch). Junta o que os segmentos cobrem.

    Os segmentos sao cortados POR AMOSTRA, nao por ficheiro: `t0` cai a meio de
    um segmento na maioria dos pedidos e entregar o segmento inteiro seria
    entregar audio que a linha nao cobre.
    """
    rate = 16000
    chunks = []
    for rec in segments:
        s0, s1 = float(rec.get('t0', 0)), float(rec.get('t1', 0))
        if s1 <= t0 or s0 >= t1:
            continue
        rel0 = max(0.0, t0 - s0)
        rel1 = min(s1 - s0, t1 - s0)
        if rel1 - rel0 <= 0.001:
            continue
        pcm = _decode(rec['abs'], int(rec.get('rate', rate)), rel0, rel1 - rel0)
        if not pcm:
            print('AVISO segmento mudo/degenerado: %s' % rec.get('file'), file=sys.stderr)
            continue
        # ffmpeg corta no sample mais proximo; a diferenca entra como meio
        # sample de silencio no pad, nunca como um deslocamento que se acumula.
        want = int(round((rel1 - rel0) * int(rec.get('rate', rate)))) * 2
        if len(pcm) < want:
            pcm = pcm + b'\x00' * (want - len(pcm))
        chunks.append(pcm[:want])
    return b''.join(chunks), rate


def _write_wav(path, pcm, rate):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or '.', exist_ok=True)
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return path


def _parse_time(text, now=None):
    """`epoch` cru, ou `HH:MM:SS` de HOJE (o dono le' o relogio, nao um epoch)."""
    text = str(text).strip()
    if ':' not in text:
        return float(text)
    now = time.time() if now is None else now
    base = time.mktime(time.strptime(time.strftime('%Y-%m-%d', time.localtime(now)),
                                     '%Y-%m-%d'))
    parts = [float(p) for p in text.split(':')]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    return base + parts[0] * 3600 + parts[1] * 60 + parts[2]


def cmd_list(root):
    segs = _segments(root)
    if not segs:
        print('sem segmentos em %s' % os.path.join(root, 'history', 'audio'))
        return 2
    total = sum(int(s.get('bytes', 0)) for s in segs)
    print('segmentos=%d bytes=%d (%.1f MB)'
          % (len(segs), total, total / 1e6))
    for s in segs[-20:]:
        print('  %s  %s -> %s  %d B'
              % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(float(s['t0']))),
                 time.strftime('%H:%M:%S', time.localtime(float(s['t0']))),
                 time.strftime('%H:%M:%S', time.localtime(float(s.get('t1', 0)))),
                 int(s.get('bytes', 0))))
    return 0


def cmd_lines(root):
    lines = _lines(root)
    if not lines:
        print('sem ancoras em %s' % os.path.join(root, 'history', 'audio', 'lines.jsonl'))
        return 2
    print('linhas=%d' % len(lines))
    for i, rec in enumerate(lines[-40:], start=max(1, len(lines) - 39)):
        print('%4d  %s  %5.1fs  %s'
              % (i, time.strftime('%H:%M:%S', time.localtime(float(rec['t0']))),
                 max(0.0, float(rec.get('t1', rec['t0'])) - float(rec['t0'])),
                 (rec.get('text') or '')[:90]))
    return 0


def cmd_line(root, n, out):
    lines = _lines(root)
    if not lines:
        print('sem ancoras', file=sys.stderr)
        return 2
    if not (1 <= n <= len(lines)):
        print('linha %d fora de 1..%d' % (n, len(lines)), file=sys.stderr)
        return 2
    rec = lines[n - 1]
    pcm, rate = _cut(_segments(root), float(rec['t0']), float(rec['t1']))
    if not pcm:
        print('sem audio para a linha %d' % n, file=sys.stderr)
        return 3
    print(_write_wav(out, pcm, rate))
    print('linha %d  %.2fs  %s' % (n, len(pcm) / 2.0 / rate, (rec.get('text') or '')[:100]))
    return 0


def cmd_range(root, a, b, out):
    t0, t1 = _parse_time(a), _parse_time(b)
    if t1 <= t0:
        print('intervalo vazio: %s..%s' % (a, b), file=sys.stderr)
        return 2
    pcm, rate = _cut(_segments(root), t0, t1)
    if not pcm:
        print('sem audio nesse intervalo', file=sys.stderr)
        return 3
    print(_write_wav(out, pcm, rate))
    print('%.2fs' % (len(pcm) / 2.0 / rate))
    return 0


def cmd_corpus(root, out):
    """Um wav com todas as linhas ancoradas, em sequencia, com 250 ms de pausa.

    A pausa e' o que separa duas linhas no corpus: um benchmark que les um wav
    continuo precisa de saber onde uma frase acaba, e 250 ms e' um silencio que
    o proprio VAD ja' corta (o piso medido da casa: 600 ms para fim de frase).
    """
    segs = _segments(root)
    lines = _lines(root)
    pieces, rate = [], 16000
    used = 0
    for rec in lines:
        pcm, rate = _cut(segs, float(rec['t0']), float(rec['t1']))
        if not pcm:
            continue
        pieces.append(pcm)
        pieces.append(b'\x00' * int(0.25 * rate) * 2)
        used += 1
    if not pieces:
        print('sem linhas com audio', file=sys.stderr)
        return 3
    pcm = b''.join(pieces)
    print(_write_wav(out, pcm, rate))
    print('linhas=%d audio=%.1fs' % (used, len(pcm) / 2.0 / rate))
    return 0


def cmd_selftest():
    """Prova o ring E este leitor contra um sinal CONHECIDO.

    Cinco arms, e a ultima e' a que importa: o corte por amostra tem de
    devolver a janela pedida com o tom certo, senao o benchmark estaria a
    comparar audio deslocado.
    """
    import numpy as np
    import audio_ring

    ok = []

    def arm(name, cond, detail=''):
        ok.append(bool(cond))
        print('%s %s %s' % ('PASS' if cond else 'FAIL', name, detail))

    rate = 16000
    tmp = tempfile.mkdtemp(prefix='ring-selftest-')
    ring = audio_ring.AudioRing(tmp, hours=1.0, kbps=32, segment_s=5.0)
    arm('ring-on', ring.enabled)
    t0_epoch = time.time()
    # 20 s de um tom de 440 Hz, em blocos de 100 ms -- a forma real do tap.
    total = 20.0
    freq = 440.0
    blk = int(0.1 * rate)
    for i in range(int(total * 10)):
        t = np.arange(i * blk, (i + 1) * blk, dtype=np.float64) / rate
        ring.push((0.5 * np.sin(2 * math.pi * freq * t)).astype(np.float32))
        if i % 10 == 0:
            time.sleep(0.002)
    ring.close()
    segs = _segments(tmp)
    arm('segmentos-rotacionados', len(segs) >= 3, 'n=%d' % len(segs))
    written = sum(int(s.get('samples', 0)) for s in segs) / float(rate)
    arm('audio-inteiro-escrito', abs(written - total) < 0.6, '%.2fs de %.1fs' % (written, total))

    base = float(segs[0]['t0'])
    want = 3.0
    pcm, rate2 = _cut(segs, base + want, base + want + 2.0)
    got = len(pcm) / 2.0 / rate2
    arm('corte-comprimento', abs(got - 2.0) < 0.02, '%.3fs' % got)
    arr = np.frombuffer(pcm, dtype='<i2').astype(np.float64) / 32768.0
    rms = float(np.sqrt((arr ** 2).mean())) if arr.size else 0.0
    # 0.5 amplitude senoide -> RMS teorico 0.3536; opus a 32k preserva o nivel
    arm('nivel-preservado', 0.20 < rms < 0.45, 'rms=%.3f' % rms)
    spec = np.abs(np.fft.rfft(arr[:8192] * np.hanning(min(8192, arr.size))[:min(8192, arr.size)])) if arr.size >= 8192 else np.zeros(2)
    peak = int(np.argmax(spec)) * (rate2 / float(len(arr[:8192]))) if arr.size >= 8192 else 0
    arm('tom-certo', abs(peak - freq) < 12.0, 'peak=%.0fHz' % peak)

    # PODA POR IDADE: apagar audio velho e' a unica parte DESTRUTIVA deste
    # modulo, logo ela tem braco proprio -- um ring que nunca poda enche o
    # disco do dono, e um que poda demais apaga o audio que ele mandou guardar.
    day = os.path.join(tmp, 'history', 'audio',
                       time.strftime('%Y-%m-%d', time.localtime(time.time() - 7200)))
    os.makedirs(day, exist_ok=True)
    old_path = os.path.join(day, '000000.32k.opus')
    with open(old_path, 'wb') as fh:
        fh.write(b'x' * 1024)
    two_h_ago = time.time() - 7200
    os.utime(old_path, (two_h_ago, two_h_ago))
    fresh_path = os.path.join(day, '235959.32k.opus')
    with open(fresh_path, 'wb') as fh:
        fh.write(b'y' * 1024)
    res = ring._prune()
    arm('poda-por-idade', not os.path.exists(old_path) and os.path.exists(fresh_path),
        'deleted=%d' % res.get('deleted', -1))

    bad = ok.count(False)
    print('RING-SELFTEST %s -- %d/%d' % ('PASS' if not bad else 'FAIL', len(ok) - bad, len(ok)))
    return 0 if not bad else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description='Reouvir o audio do ring de 12h')
    ap.add_argument('--root', default=ROOT)
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--lines', action='store_true')
    ap.add_argument('--line', type=int, default=None)
    ap.add_argument('--from', dest='t_from', default=None)
    ap.add_argument('--to', dest='t_to', default=None)
    ap.add_argument('--corpus', default=None)
    ap.add_argument('--out', default=None)
    ap.add_argument('--selftest', action='store_true')
    args = ap.parse_args(argv)

    if args.selftest:
        return cmd_selftest()
    root = os.path.abspath(args.root)
    out = args.out or os.path.join(tempfile.gettempdir(), 'sotto-replay.wav')
    if args.list:
        return cmd_list(root)
    if args.lines:
        return cmd_lines(root)
    if args.line is not None:
        return cmd_line(root, args.line, out)
    if args.corpus:
        return cmd_corpus(root, args.corpus)
    if args.t_from and args.t_to:
        return cmd_range(root, args.t_from, args.t_to, out)
    ap.print_help()
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
