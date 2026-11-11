"""audio_ring — o AUDIO INTEIRO das ultimas 12 horas, para replay e benchmark.

ORDEM DO DONO (2026-11-11, verbatim): *"MANTENHA o audio INTEIRO das ultimas 12
horas pra benchmark/replay pra gente melhorar a taxa de acerto de palavras"*, e
depois *"o trecho de audio 'que nao fez sentido' fica guardado ate ele passar por
um modelo melhor com maior precisao, e depois o audio e deletado"*.

POR QUE UM RING E NAO UM FICHEIRO POR SEGUNDO: o tap entrega blocos de 10-100 ms
e escrever um ficheiro por bloco e' a classe de defeito que este repo ja' pagou
(`HISTORY` a crescer, log a crescer com o audio). O ring escreve SEGMENTOS de 10
minutos (72 ficheiros para 12 h) e apaga os velhos: o espaco e' limitado por
construcao, nao por um cron que pode morrer.

NUMEROS MEDIDOS NESTA MAQUINA (`_main/_cache/audio-ring-encode-probe.py`,
2026-11-11): `libopus` presente; 16 kHz mono a 24 kbps codifica a **94,6x
tempo real** (0,16 s de CPU para 15 s de audio, = ~1 % de um nucleo) e custa
**168,0 MB para 12 h** -- contra 1,15 GB do PCM cru. O arranque do `ffmpeg` custa
**7-8 ms**, logo o processo por segmento (72 por 12 h) e' ruido.

O QUE ELE **NAO** FAZ: nao abre dispositivo de audio (recebe os blocos de quem ja'
os tem), nao toca em volume/mute, e nao bloqueia o tap -- a fila tem tecto em
SEGUNDOS de audio e transbordar e' CONTADO, nunca uma espera no fio do audio.

FORMATO NO DISCO: `history/audio/<AAAA-MM-DD>/<HHMMSS>.<kbps>k.opus` (Ogg Opus,
16 kHz mono) + `index.jsonl` (uma linha por segmento FECHADO: `file`, `t0`, `t1`,
`samples`, `rate`, `kbps`, `bytes`) + `lines.jsonl` (as linhas do historico, com
o instante do audio que as produziu, escrito pelo worker: e' o que deixa cortar
o trecho EXACTO de uma frase).
"""
from __future__ import annotations

import collections
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time

DEFAULT_HOURS = 12.0
DEFAULT_KBPS = 24
DEFAULT_SEGMENT_S = 600.0
#: Tecto da fila em SEGUNDOS de audio. 120 s de 16 kHz float32 = 7,7 MB: um tap
#: que produza mais do que isso enquanto o `ffmpeg` esta' ocupado nao e' audio em
#: tempo real, e' uma pausa do processo (a fila diz isso com o contador
#: `dropped_s` em vez de crescer sem limite).
DEFAULT_QUEUE_S = 120.0
DEFAULT_CAP_MB = 600.0

ENV_ENABLED = 'SOTTO_AUDIO_RING'
ENV_HOURS = 'SOTTO_AUDIO_RING_HOURS'
ENV_KBPS = 'SOTTO_AUDIO_RING_KBPS'
ENV_DIR = 'SOTTO_AUDIO_RING_DIR'
ENV_CAP_MB = 'SOTTO_AUDIO_RING_CAP_MB'


def _env_float(name, default):
    try:
        return float(os.environ.get(name, '') or default)
    except (TypeError, ValueError):
        return float(default)


def _env_int(name, default):
    try:
        return int(os.environ.get(name, '') or default)
    except (TypeError, ValueError):
        return int(default)


def ffmpeg_path():
    """O `ffmpeg` que esta' nesta maquina, procurado como o resto do repo faz.

    `shutil.which` primeiro (PATH), depois o atalho do WinGet que esta' medido
    aqui -- um binario que so' existe num sitio e' um instrumento que morre em
    silencio na proxima sessao.
    """
    found = shutil.which('ffmpeg')
    if found:
        return found
    cand = os.path.join(os.environ.get('LOCALAPPDATA', ''),
                        'Microsoft', 'WinGet', 'Links', 'ffmpeg.exe')
    return cand if os.path.exists(cand) else None


def _hidden_kwargs():
    """CREATE_NO_WINDOW + STARTF_USESHOWWINDOW: a guarda desta casa.

    Sem ela o `ffmpeg` de um pai sem consola faz o Windows alocar uma consola
    NOVA -- a janela na tela do dono, medida sete vezes neste repo.
    """
    if os.name != 'nt':
        return {}
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0
    return {'creationflags': 0x08000000, 'startupinfo': si}


class AudioRing:
    """O ring de 12 h: um fio escritor, segmentos de 10 min, poda por idade e MB."""

    def __init__(self, root, hours=None, kbps=None, segment_s=None,
                 queue_s=None, cap_mb=None, enabled=None, log=None):
        self.root = os.path.abspath(root)
        self.hours = _env_float(ENV_HOURS, DEFAULT_HOURS) if hours is None else float(hours)
        self.kbps = _env_int(ENV_KBPS, DEFAULT_KBPS) if kbps is None else int(kbps)
        self.segment_s = float(segment_s or DEFAULT_SEGMENT_S)
        self.queue_s = float(queue_s or DEFAULT_QUEUE_S)
        self.cap_mb = _env_float(ENV_CAP_MB, DEFAULT_CAP_MB) if cap_mb is None else float(cap_mb)
        if enabled is None:
            enabled = str(os.environ.get(ENV_ENABLED, '1')).strip() not in ('0', 'no', 'false', '')
        self.enabled = bool(enabled)
        self.rate = 16000
        self._log = log or (lambda msg: print('AUDIO_RING ' + msg, file=sys.stderr, flush=True))
        self._q = queue.Queue()
        self._q_max = int(self.queue_s * self.rate)
        self._queued = 0
        self._lock = threading.Lock()
        self.dropped_s = 0.0
        self.written_s = 0.0
        self.segments = 0
        self.failed = 0
        self._thread = None
        self._stop = threading.Event()
        self._proc = None
        self._file = None
        self._t0 = 0.0
        self._seg_samples = 0
        self._seg_started = 0.0
        self._seg_audio_start = 0
        self._audio_kept = 0
        self._ffmpeg = None
        self._closed = False
        #: O epoch de PAREDE do segundo de audio 0 do ring. Fixado no primeiro
        #: bloco: e' o que converte o `start`/`end` (segundos de audio) de uma
        #: linha do historico no instante do ficheiro -- duas escalas diferentes
        #: seriam um corte deslocado sempre que o relogio anda.
        self._first_epoch = None
        if not self.enabled:
            self._log('off reason=env %s=0' % ENV_ENABLED)
            return
        self._ffmpeg = ffmpeg_path()
        if not self._ffmpeg:
            self.enabled = False
            self._log('off reason=no-ffmpeg (PATH e WinGet ausentes)')
            return
        os.makedirs(self._dir_for(time.time()), exist_ok=True)
        self._prune()
        self._thread = threading.Thread(target=self._run, name='audio-ring',
                                        daemon=True)
        self._thread.start()
        self._log('on dir=%s hours=%.1f kbps=%d segment_s=%.0f cap_mb=%.0f ffmpeg=%s'
                  % (self.dir, self.hours, self.kbps, self.segment_s, self.cap_mb,
                     os.path.basename(self._ffmpeg)))

    # ── estado ───────────────────────────────────────────────────────────────
    @property
    def dir(self):
        return os.path.join(self.root, 'history', 'audio')

    def _dir_for(self, epoch):
        return os.path.join(self.dir, time.strftime('%Y-%m-%d', time.localtime(epoch)))

    def status(self):
        return {'enabled': self.enabled, 'hours': self.hours, 'kbps': self.kbps,
                'queued_s': round(self._queued / float(self.rate), 2),
                'dropped_s': round(self.dropped_s, 2),
                'written_s': round(self.written_s, 1),
                'segments': self.segments, 'failed': self.failed,
                'dir': self.dir}

    def epoch_for(self, audio_seconds):
        """Epoch de PAREDE do segundo de audio `audio_seconds` do ring.

        O worker conta o audio do tap a partir de zero; o ring fixa o epoch do
        seu primeiro bloco. As duas escalas encontram-se aqui, num lugar so',
        para que a ancora de uma linha do historico e o nome do segmento
        concordem. Sem nenhum bloco ainda, devolve o agora -- uma ancora
        aproximada e' melhor do que uma ancora negativa.
        """
        if self._first_epoch is None:
            return time.time()
        return self._first_epoch + float(audio_seconds)

    # ── a porta quente: chamada no fio do audio ──────────────────────────────
    def push(self, block):
        """Enfileira um bloco float32 mono @16 kHz. NUNCA bloqueia.

        A COBRA E' O CUSTO: isto corre no fio do tap, a cada 10-100 ms. Uma
        copia do bloco e um `put_nowait`; nada de I/O, nada de `json`, nada de
        esperar pelo escritor. Se a fila estourar, o audio DESTE bloco e'
        perdido e o contador diz quantos segundos -- perder audio em silencio
        seria pior do que perde-lo contado.
        """
        if not self.enabled or self._closed:
            return 0
        try:
            n = int(block.size)
        except AttributeError:
            return 0
        if not n:
            return 0
        with self._lock:
            if self._queued + n > self._q_max:
                self.dropped_s += n / float(self.rate)
                return 0
            self._queued += n
            if self._first_epoch is None:
                # O epoch do AUDIO ZERO e' o instante do primeiro bloco. Fixado
                # aqui, no mesmo `with` que aceita o bloco, para nenhum segundo
                # de audio existir sem um instante de parede ao lado.
                self._first_epoch = time.time()
        self._q.put(block.copy())
        return n

    # ── o escritor ───────────────────────────────────────────────────────────
    def _open_segment(self, now):
        d = self._dir_for(now)
        os.makedirs(d, exist_ok=True)
        name = time.strftime('%H%M%S', time.localtime(now)) + '.%dk.opus' % self.kbps
        path = os.path.join(d, name)
        argv = [self._ffmpeg, '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'f32le', '-ar', str(self.rate), '-ac', '1', '-i', 'pipe:0',
                '-c:a', 'libopus', '-b:a', '%dk' % self.kbps,
                '-application', 'voip', '-frame_duration', '20',
                '-f', 'ogg', path]
        try:
            proc = subprocess.Popen(argv, stdin=subprocess.PIPE,
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.PIPE, **_hidden_kwargs())
        except Exception as exc:  # noqa: BLE001 -- o ring nao pode matar o worker
            self.failed += 1
            self._log('segment_open_failed error=%r' % (exc,))
            return False
        self._proc = proc
        self._file = path
        self._t0 = now
        self._seg_started = now
        self._seg_samples = 0
        # O EPOCH DO SEGMENTO VEM DO RELOGIO DE AUDIO, NAO DO RELOGIO DE PAREDE.
        # `now` e' a hora em que o ficheiro abriu; o `t0` indexado e' o instante
        # do PRIMEIRO SAMPLE dele, que e' o que um corte por linha procura. Os
        # dois coincidem com a captura ao vivo e divergem sempre que o escritor
        # fica para tras -- e nesse caso e' o de audio que esta' certo, porque o
        # `start`/`end` de uma legenda tambem conta audio.
        self._seg_audio_start = self._audio_kept
        self._t0 = (self._first_epoch or now) + self._audio_kept / float(self.rate)
        return True

    def _close_segment(self):
        proc, path = self._proc, self._file
        self._proc = None
        self._file = None
        if proc is None:
            return
        try:
            if proc.stdin:
                proc.stdin.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            proc.wait(timeout=20)
        except Exception:  # noqa: BLE001
            try:
                proc.kill()
            except Exception:  # noqa: BLE001
                pass
        t1 = ((self._first_epoch or self._seg_started)
              + (self._seg_audio_start + self._seg_samples) / float(self.rate))
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        if size <= 0:
            self.failed += 1
            self._log('segment_empty file=%s' % (path,))
            return
        rec = {'file': os.path.relpath(path, self.root).replace(os.sep, '/'),
               't0': round(self._t0, 3), 't1': round(t1, 3),
               'samples': self._seg_samples, 'rate': self.rate,
               'kbps': self.kbps, 'bytes': size}
        try:
            with open(os.path.join(self.dir, 'index.jsonl'), 'a',
                      encoding='utf-8') as fh:
                fh.write(json.dumps(rec, separators=(',', ':')) + '\n')
        except OSError as exc:
            self._log('index_write_failed error=%r' % (exc,))
        self.segments += 1

    def _run(self):
        #: O BLOCO QUE AINDA NAO FOI ESCRITO. Se o `ffmpeg` falha a abrir um
        #: segmento, o bloco que estava na mao NAO pode ser deitado fora -- o
        #: `continue` do ramo de falha consumia-o, e um arranque lento de
        #: ffmpeg (medido: uma corrida do `--selftest` gravou 5 s de 20 s nesta
        #: arvore, com um segmento so') perdia audio em silencio. Agora ele fica
        #: aqui e a volta seguinte tenta-o outra vez.
        pending = None
        while True:
            if pending is not None:
                block, pending = pending, None
            else:
                try:
                    block = self._q.get(timeout=1.0)
                except queue.Empty:
                    block = None
            if block is None:
                if self._stop.is_set():
                    break
                # um segmento vazio nao e' aberto: sem audio nao ha' ficheiro
                if self._proc is not None and time.monotonic() - self._seg_started >= self.segment_s:
                    self._close_segment()
                continue
            n = int(block.size)
            with self._lock:
                self._queued = max(0, self._queued - n)
            now = time.time()
            if self._proc is None:
                if not self._open_segment(now):
                    pending = block
                    time.sleep(0.5)
                    continue
            try:
                self._proc.stdin.write(block.astype('float32', copy=False).tobytes())
            except Exception as exc:  # noqa: BLE001 -- cano partido nao e' morte
                self.failed += 1
                self._log('pipe_write_failed error=%r draining=%d'
                          % (exc, int(self._seg_samples)))
                self._close_segment()
                continue
            self._seg_samples += n
            self._audio_kept += n
            self.written_s += n / float(self.rate)
            # ROTACAO POR AUDIO, NAO POR RELOGIO. O nome do ficheiro e' a hora e
            # o conteudo e' audio; um escritor que fica para tras (fila cheia,
            # disco lento) tem de continuar a fechar segmentos do tamanho
            # DECLARADO em audio, senao o `t1` do indice deixa de bater com o
            # ficheiro e o corte de replay sai deslocado. Medido: 20 s de audio
            # empurrados em 1 s de parede davam UM segmento com a rotacao por
            # relogio; por audio dao quatro.
            if self._seg_samples / float(self.rate) >= self.segment_s:
                self._close_segment()
                self._prune()
        self._close_segment()
        self._prune()
        self._closed = True
        self._log('stopped status=%s' % (json.dumps(self.status(), separators=(',', ':')),))

    # ── a poda: idade E tamanho ──────────────────────────────────────────────
    def _prune(self):
        if not os.path.isdir(self.dir):
            return {'deleted': 0, 'mb_left': 0.0}
        cutoff = time.time() - self.hours * 3600.0
        entries = []
        for day in sorted(os.listdir(self.dir)):
            d = os.path.join(self.dir, day)
            if not os.path.isdir(d):
                continue
            for name in sorted(os.listdir(d)):
                p = os.path.join(d, name)
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                entries.append((st.st_mtime, st.st_size, p))
        deleted = 0
        freed = 0
        keep = []
        for mtime, size, p in entries:
            if mtime < cutoff:
                # O SEGMENTO ABERTO NUNCA E' PODADO, nem por idade: o `mtime`
                # dele fica parado enquanto o audio nao chega, e apagar um
                # ficheiro que o ffmpeg tem aberto perde o resto do segmento e
                # deixa o indice a apontar para um caminho que ja' nao existe.
                if self._file and os.path.abspath(p) == os.path.abspath(self._file):
                    keep.append((mtime, size, p))
                    continue
                try:
                    os.remove(p)
                    deleted += 1
                    freed += size
                except OSError:
                    pass
            else:
                keep.append((mtime, size, p))
        # TECTO EM MB: o mais VELHO sai primeiro, e nunca o segmento ABERTO.
        total = sum(s for _m, s, _p in keep) / (1024.0 * 1024.0)
        cap = self.cap_mb
        for mtime, size, p in sorted(keep):
            if total <= cap:
                break
            if self._file and os.path.abspath(p) == os.path.abspath(self._file):
                continue
            try:
                os.remove(p)
                deleted += 1
                freed += size
                total -= size / (1024.0 * 1024.0)
            except OSError:
                pass
        if deleted:
            self._log('pruned files=%d mb_freed=%.1f mb_left=%.1f'
                      % (deleted, freed / (1024.0 * 1024.0), total))
        return {'deleted': deleted, 'mb_left': round(total, 1)}

    def close(self, timeout=15.0):
        if not self.enabled:
            return
        self._stop.set()
        # acorda o escritor: um `get` parado nao ve' o `_stop`
        self._q.put(None)
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        self._closed = True


def append_line_anchor(root, t0, t1, text, extra=None):
    """Registra QUAL audio produziu ESTA linha (o que deixa cortar o trecho).

    Uma linha por legenda fechada, no `lines.jsonl` do ring. O `t0`/`t1` sao
    instantes de PAREDE (epoch), que e' o que o `index.jsonl` tambem usa -- duas
    escalas diferentes seriam um corte deslocado sempre que o relogio anda.
    """
    d = os.path.join(root, 'history', 'audio')
    try:
        os.makedirs(d, exist_ok=True)
        rec = {'t0': round(float(t0), 3), 't1': round(float(t1), 3),
               'text': text}
        if extra:
            rec.update(extra)
        with open(os.path.join(d, 'lines.jsonl'), 'a', encoding='utf-8') as fh:
            fh.write(json.dumps(rec, separators=(',', ':'), ensure_ascii=False) + '\n')
        return True
    except Exception:  # noqa: BLE001 -- um indice nao derruba a legenda
        return False


def read_index(root):
    p = os.path.join(root, 'history', 'audio', 'index.jsonl')
    out = []
    try:
        with open(p, encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        continue
    except OSError:
        return []
    return out
