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
`samples`, `rate`, `kbps`, `bytes`, `wall_s`, `gap_s`, `dropped_s`) + `gaps.jsonl`
(os intervalos de PAREDE em que NENHUM bloco chegou) + `lines.jsonl` (as linhas
do historico, com o instante do audio que as produziu, escrito pelo worker: e' o
que deixa cortar o trecho EXACTO de uma frase).

DOIS RELOGIOS, E O QUE CADA UM PROVA (medido 2026-11-17 no corpus de 2026-11-16:
cobertura de 71,6 % -- 13 516,7 s de audio em 18 866,3 s de parede, com um buraco
de 2 325,2 s DENTRO de um ficheiro):

  * `t0`/`t1` sao o AUDIO: `first_epoch + amostras_guardadas / rate`. NUNCA a
    hora do relogio de parede -- e' isto que faz o corte de uma linha cair no
    sample certo. Eles dizem o que o ficheiro DECLARA, que e' exactamente o que
    o ffmpeg codificou (medido: `ffprobe` de cada segmento = `samples/rate`).
  * `wall_s`/`gap_s`/`dropped_s` sao a PERDA: quanto tempo de parede aquele
    segmento atravessou (`wall_s`), quanto desse tempo nao teve bloco nenhum
    (`gap_s`) e quantas amostras a fila recusou (`dropped_s`, exacto).
  * A identidade e' `wall_s - (t1-t0) == gap_s`: o segmento NAO ficou 600 s sem
    escrever, ficou 600 s sem RECEBER. A diferenca e' audio que nunca chegou ao
    `push` -- tap sem stream (endpoint deixou de render), worker parado,
    dispositivo trocado. `dropped_s` e' perda A MAIS: audio que chegou e a fila
    recusou, invisivel no relogio do audio (nao ocupa tempo no ficheiro).
    Foi essa a causa medida dos 5 347 s de buraco do corpus: `block_samples` do
    tap / 48000 = 12 037,3 s em 17 129 s de parede (70,3 %), e o ring guardou
    11 600 s disso -- a diferenca (~437 s) e' a fila, que agora se conta.
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

#: A partir de quantos segundos de PAREDE sem NENHUM bloco o ring considera que
#: perdeu audio (e nao que o tap fez jitter). 2 s sao ~50 blocos de 40 ms: um
#: atraso de escalonamento nao chega la', uma pausa do tap chega sempre. O valor
#: e' um limiar de DETECCAO, nao um tecto -- o que se grava e' o intervalo MEDIDO.
DEFAULT_GAP_MIN_S = 2.0
#: Marcadores que podem esperar na memoria antes do escritor os drenar. O
#: escritor drena a cada volta (<=1 s), logo a lista so' cresce se ele estiver
#: bloqueado; o tecto existe e CONTA o que largou (`gaps_dropped`), como o resto
#: desta casa.
GAP_PENDING_MAX = 64
#: Uma linha de log por cada N segundos com perda de fila, com o acumulado.
DROP_LOG_EVERY_S = 10.0
#: `gaps.jsonl` e' pequeno (uma linha por pausa do tap), mas nao cresce sem
#: tecto: acima disto a poda guarda as ultimas GAP_ROWS_KEEP linhas.
GAP_FILE_MAX_BYTES = 512 * 1024
GAP_ROWS_KEEP = 2000

ENV_ENABLED = 'SOTTO_AUDIO_RING'
ENV_HOURS = 'SOTTO_AUDIO_RING_HOURS'
ENV_KBPS = 'SOTTO_AUDIO_RING_KBPS'
ENV_DIR = 'SOTTO_AUDIO_RING_DIR'
ENV_CAP_MB = 'SOTTO_AUDIO_RING_CAP_MB'
ENV_GAP_MIN_S = 'SOTTO_AUDIO_RING_GAP_MIN_S'


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
                 queue_s=None, cap_mb=None, enabled=None, log=None,
                 gap_min_s=None):
        self.root = os.path.abspath(root)
        self.hours = _env_float(ENV_HOURS, DEFAULT_HOURS) if hours is None else float(hours)
        self.kbps = _env_int(ENV_KBPS, DEFAULT_KBPS) if kbps is None else int(kbps)
        self.segment_s = float(segment_s or DEFAULT_SEGMENT_S)
        self.queue_s = float(queue_s or DEFAULT_QUEUE_S)
        self.cap_mb = _env_float(ENV_CAP_MB, DEFAULT_CAP_MB) if cap_mb is None else float(cap_mb)
        #: Limiar de deteccao de buraco de CHEGADA (segundos de parede).
        self._gap_min_s = (_env_float(ENV_GAP_MIN_S, DEFAULT_GAP_MIN_S)
                           if gap_min_s is None else float(gap_min_s))
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
        #: A PERDA FORA DA FILA. `gaps`/`gap_s` sao intervalos de PAREDE em que
        #: nenhum bloco chegou (o tap parou); `_dropped_samples` sao as amostras
        #: que a fila recusou (o escritor ficou para tras). Os dois contam coisas
        #: diferentes e ambos eram invisiveis antes de 2026-11-17.
        self.gaps = 0
        self.gap_s = 0.0
        self.gaps_dropped = 0
        self._last_push = None
        self._pending_gaps = []
        self._dropped_samples = 0
        self._dropped_logged = 0
        self._dropped_log_at = 0.0
        self._thread = None
        self._stop = threading.Event()
        self._proc = None
        self._file = None
        self._t0 = 0.0
        self._seg_samples = 0
        self._seg_started = 0.0
        self._seg_started_mono = 0.0
        self._seg_audio_start = 0
        self._seg_first_wall = None
        self._seg_last_wall = None
        self._seg_dropped = 0
        self._seg_gap_s = 0.0
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
                'gaps': self.gaps, 'gap_s': round(self.gap_s, 1),
                'gaps_dropped': self.gaps_dropped,
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

        O OUTRO SILENCIO, medido a 2026-11-17 e ate' aqui INVISIVEL: o tempo de
        parede entre dois `push` consecutivos. Um intervalo sem NENHUM bloco nao
        e' o escritor lento (isso e' `dropped_s`) nem silencio do audio (isso
        chega como bloco de zeros, e o tap desta casa empurra zeros nos pacotes
        SILENT): e' audio que nunca existiu na entrada. Guardado como marcador
        contado (`gaps.jsonl` + `gap_s` do segmento) para nenhum leitor futuro
        confundir "o ficheiro declara 600 s" com "a maquina rendeu 600 s".
        """
        if not self.enabled or self._closed:
            return 0
        try:
            n = int(block.size)
        except AttributeError:
            return 0
        if not n:
            return 0
        now = time.time()
        with self._lock:
            if self._last_push is not None:
                gap = now - self._last_push
                if gap >= self._gap_min_s:
                    self.gaps += 1
                    self.gap_s += gap
                    self._seg_gap_s += gap
                    if len(self._pending_gaps) >= GAP_PENDING_MAX:
                        self._pending_gaps.pop(0)
                        self.gaps_dropped += 1
                    self._pending_gaps.append((self._last_push, now, gap))
            self._last_push = now
            if self._queued + n > self._q_max:
                self.dropped_s += n / float(self.rate)
                self._dropped_samples += n
                self._seg_dropped += n
                return 0
            self._queued += n
            if self._first_epoch is None:
                # O epoch do AUDIO ZERO e' o instante do primeiro bloco. Fixado
                # aqui, no mesmo `with` que aceita o bloco, para nenhum segundo
                # de audio existir sem um instante de parede ao lado.
                self._first_epoch = now
        # O carimbo de CHEGADA viaja COM o bloco: o escritor pode drena-lo
        # dezenas de segundos depois (fila cheia), e o `wall_s` de um segmento
        # tem de ser a hora em que o audio chegou, nao a hora em que o ffmpeg
        # o recebeu -- senao uma pausa do tap vira uma pausa do disco.
        self._q.put((now, block.copy()))
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
        #: `time.monotonic()` para a rotacao por PAREDE. Antes o ramo de ocioso
        #: comparava `time.monotonic()` com `_seg_started` (que e' `time.time()`,
        #: epoch): monotonic nesta maquina e' segundos desde o boot (~10^6) e
        #: epoch ~1,79x10^9, logo a diferenca era SEMPRE negativa e a rotacao por
        #: parede NUNCA disparava. Medido no corpus de 2026-11-16: o segmento
        #: `173532.24k.opus` atravessou 2 525 s de parede para 600 s declarados.
        self._seg_started_mono = time.monotonic()
        self._seg_samples = 0
        self._seg_first_wall = None
        self._seg_last_wall = None
        # A perda NAO e' zerada aqui: `_seg_dropped`/`_seg_gap_s` sao "a perda
        # desde o ultimo segmento ESCRITO", logo um buraco que cai entre dois
        # ficheiros (o anterior fechou pela parede, o tap so' voltou depois)
        # entra no ficheiro SEGUINTE em vez de desaparecer. Quem os zera e'
        # `_close_segment`, depois de os gravar.
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
            with self._lock:
                self._seg_dropped = 0
                self._seg_gap_s = 0.0
            return
        with self._lock:
            seg_dropped = self._seg_dropped
            seg_gap_s = self._seg_gap_s
        wall_s = None
        if self._seg_first_wall is not None and self._seg_last_wall is not None:
            wall_s = round(self._seg_last_wall - self._seg_first_wall, 3)
        rec = {'file': os.path.relpath(path, self.root).replace(os.sep, '/'),
               't0': round(self._t0, 3), 't1': round(t1, 3),
               'samples': self._seg_samples, 'rate': self.rate,
               'kbps': self.kbps, 'bytes': size,
               # AS TRES MEDIDAS DA PERDA, ao lado das duas do audio. `t1-t0` e'
               # o que o ficheiro DECLARA; `wall_s` e' o tempo de parede que os
               # samples dele atravessaram. `wall_s - (t1-t0)` e' o buraco; ele
               # desdobra-se em `gap_s` (nada chegou) e `dropped_s` (chegou e
               # nao entrou no ficheiro: fila cheia ou cano partido). Sem estes
               # campos um leitor so' tem o `mtime` do ficheiro, que e'
               # metadados e mente num `copy`/`touch`.
               'wall_s': wall_s,
               'gap_s': round(seg_gap_s, 3),
               'dropped_s': round(seg_dropped / float(self.rate), 3)}
        try:
            with open(os.path.join(self.dir, 'index.jsonl'), 'a',
                      encoding='utf-8') as fh:
                fh.write(json.dumps(rec, separators=(',', ':')) + '\n')
        except OSError as exc:
            self._log('index_write_failed error=%r' % (exc,))
        with self._lock:
            self._seg_dropped = 0
            self._seg_gap_s = 0.0
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
                item, pending = pending, None
            else:
                try:
                    item = self._q.get(timeout=1.0)
                except queue.Empty:
                    item = None
            if item is None:
                if self._stop.is_set():
                    break
                self._flush_loss()
                # um segmento vazio nao e' aberto: sem audio nao ha' ficheiro.
                # ROTACAO POR PAREDE quando NADA chega: sem isto um segmento
                # atravessa uma pausa de 40 min do tap e fica com 2 525 s de
                # parede para 600 s declarados (medido). `_seg_started_mono` e'
                # o MESMO relogio que esta comparacao -- ver `_open_segment`.
                if (self._proc is not None
                        and time.monotonic() - self._seg_started_mono >= self.segment_s):
                    self._close_segment()
                continue
            wall, block = item
            n = int(block.size)
            with self._lock:
                self._queued = max(0, self._queued - n)
            now = time.time()
            if self._proc is None:
                if not self._open_segment(now):
                    pending = item
                    time.sleep(0.5)
                    continue
            try:
                self._proc.stdin.write(block.astype('float32', copy=False).tobytes())
            except Exception as exc:  # noqa: BLE001 -- cano partido nao e' morte
                self.failed += 1
                # ESTE BLOCO NAO ENTROU NO FICHEIRO: conta-se no segmento que
                # vai fechar, senao e' a mesma perda invisivel que a fila tinha.
                with self._lock:
                    self._seg_dropped += n
                self._log('pipe_write_failed error=%r draining=%d lost=%d'
                          % (exc, int(self._seg_samples), n))
                self._close_segment()
                continue
            self._seg_samples += n
            self._audio_kept += n
            self.written_s += n / float(self.rate)
            # O TEMPO DE PAREDE DESTE AUDIO, medido na ENTRADA (`push`), nao no
            # `dequeue`: e' o que separa "o disco foi lento" de "o tap calou-se".
            if self._seg_first_wall is None:
                self._seg_first_wall = wall
            self._seg_last_wall = wall
            self._flush_loss()
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
        self._flush_loss(final=True)
        self._closed = True
        self._log('stopped status=%s' % (json.dumps(self.status(), separators=(',', ':')),))

    # ── a perda: fila e chegada ──────────────────────────────────────────────
    def _flush_loss(self, final=False):
        """Drena os marcadores de perda para `gaps.jsonl` e para o log.

        Corre no FIO DO ESCRITOR, nunca no do audio (`push` so' acumula debaixo
        do `lock`). Uma linha por buraco de chegada, com o intervalo exacto; e
        uma linha de log por cada `DROP_LOG_EVERY_S` com o acumulado da fila --
        a forma desta casa (`LOG_STDOUT_SUPPLIED dropped=N`), porque uma linha
        por bloco perdido seria um log a crescer com o defeito.
        """
        with self._lock:
            pending = self._pending_gaps
            self._pending_gaps = []
            dropped = self._dropped_samples
        if dropped > self._dropped_logged:
            now = time.time()
            if final or now - self._dropped_log_at >= DROP_LOG_EVERY_S:
                self._log('dropped samples=%d total_s=%.2f reason=queue-full rate=%d'
                          % (dropped - self._dropped_logged,
                             dropped / float(self.rate), self.rate))
                self._dropped_logged = dropped
                self._dropped_log_at = now
        if not pending:
            return 0
        rows = []
        for t_from, t_to, gap in pending:
            file_rec = (os.path.relpath(self._file, self.root).replace(os.sep, '/')
                        if self._file else None)
            rows.append({'t0': round(t_from, 3), 't1': round(t_to, 3),
                         'gap_s': round(gap, 3),
                         # A estimativa de amostras usa o rate DECLARADO; o
                         # ring nao conhece o rate real do tap (o defeito de
                         # 3x documentado no topo). O numero que vale e' `gap_s`.
                         'samples_missing': int(round(gap * self.rate)),
                         'rate': self.rate, 'file': file_rec})
            self._log('gap t0=%.3f t1=%.3f gap_s=%.3f samples_missing=%d file=%s'
                      % (t_from, t_to, gap, int(round(gap * self.rate)),
                         os.path.basename(file_rec) if file_rec else '-'))
        try:
            with open(os.path.join(self.dir, 'gaps.jsonl'), 'a',
                      encoding='utf-8') as fh:
                for row in rows:
                    fh.write(json.dumps(row, separators=(',', ':')) + '\n')
        except OSError as exc:
            self._log('gaps_write_failed error=%r' % (exc,))
        return len(rows)

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
        self._trim_gap_journal()
        return {'deleted': deleted, 'mb_left': round(total, 1)}

    def _trim_gap_journal(self):
        """`gaps.jsonl` tem tecto: acima de GAP_FILE_MAX_BYTES fica o mais novo.

        Um marcador por pausa do tap e' barato, mas um ficheiro que so' cresce e'
        a classe que esta casa ja' pagou. A leitura so' acontece acima do tecto.
        """
        p = os.path.join(self.dir, 'gaps.jsonl')
        try:
            size = os.path.getsize(p)
        except OSError:
            return 0
        if size <= GAP_FILE_MAX_BYTES:
            return 0
        try:
            with open(p, encoding='utf-8') as fh:
                rows = fh.readlines()
        except OSError:
            return 0
        keep = rows[-GAP_ROWS_KEEP:]
        try:
            with open(p, 'w', encoding='utf-8') as fh:
                fh.writelines(keep)
        except OSError as exc:
            self._log('gaps_trim_failed error=%r' % (exc,))
            return 0
        self._log('gaps_trimmed kept=%d of=%d' % (len(keep), len(rows)))
        return len(rows) - len(keep)

    def close(self, timeout=15.0):
        if not self.enabled:
            return
        self._stop.set()
        # acorda o escritor: um `get` parado nao ve' o `_stop`
        self._q.put(None)
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        # Se o escritor nao saiu a tempo (join com prazo), os marcadores que
        # ficaram na memoria sao drenados AQUI: perda contada nao se perde com o
        # processo. `_flush_loss` e' idempotente (lista drenada + contador).
        try:
            self._flush_loss(final=True)
        except Exception:  # noqa: BLE001 -- fechar nao pode levantar
            pass
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


def read_gaps(root):
    """Os buracos de CHEGADA que o ring viu: `[{t0, t1, gap_s, samples_missing}]`.

    Vazio num ring que nunca perdeu bloco (ou num indice escrito antes de
    2026-11-17, que nao os registava -- nesse caso a diferenca entre o `wall_s`
    e o `t1-t0` do segmento ainda a mostra, derivada).
    """
    p = os.path.join(root, 'history', 'audio', 'gaps.jsonl')
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
    out.sort(key=lambda r: float(r.get('t0', 0)))
    return out
