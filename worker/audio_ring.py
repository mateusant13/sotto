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
`samples`, `rate`, `kbps`, `bytes`, `wall_t0`, `wall_t1`, `wall_s`, `stream_s`,
`gap_s`, `dropped_s`) + `gaps.jsonl`
(os intervalos de PAREDE em que NENHUM bloco chegou, com `scope: "span"` quando
cabem num segmento e `file: null` quando passam entre dois) + `lines.jsonl` (as linhas
do historico, com o instante do audio que as produziu, escrito pelo worker: e' o
que deixa cortar o trecho EXACTO de uma frase).

DOIS RELOGIOS, E O QUE CADA UM PROVA (medido 2026-11-17 no corpus de 2026-11-16:
cobertura de 71,6 % -- 13 516,7 s de audio em 18 866,3 s de parede, com um buraco
de 2 325,2 s DENTRO de um ficheiro):

  * `t0`/`t1` sao o AUDIO: `first_epoch + amostras_guardadas / rate`. NUNCA a
    hora do relogio de parede -- e' isto que faz o corte de uma linha cair no
    sample certo. Eles dizem o que o ficheiro DECLARA, que e' exactamente o que
    o ffmpeg codificou (medido: `ffprobe` de cada segmento = `samples/rate`).
  * `wall_s`/`stream_s`/`gap_s`/`dropped_s` sao a PERDA, e a identidade e'
    `wall_s == stream_s + gap_s`, exacta POR CONSTRUCAO: o intervalo de parede
    entre dois `push` consecutivos e' ou audio que chegou (`stream_s`) ou um
    buraco medido (`gap_s`), e `wall_s` e' a soma dos dois. `wall_t0`/`wall_t1`
    sao as duas chegadas que o delimitam, logo `wall_t1 - wall_t0 == wall_s`
    tambem se verifica so' com os campos do ficheiro.
  * `t1 - t0` NAO entra nessa identidade: e' o relogio do AUDIO, e o tap entrega
    48 kHz a um ring que declara 16 kHz (`worker/sotto_worker.py:4440`), logo
    `t1-t0` vale 3x a duracao real. Era essa a identidade publicada ate'
    2026-11-19 (`wall_s - (t1-t0) == gap_s`) e ela nao se pode verificar com os
    campos ao lado dela: no corpus de 2026-11-17 dava -36 289 s num dia de
    28 183 s. Quem quiser o rate REAL do segmento faz `samples/stream_s`.
  * ATRIBUICAO: um marcador pertence ao segmento cujo `[wall_t0, wall_t1]` o
    CONTEM. Uma pausa do tap que atravessa a rotacao nao pertence a nenhum --
    `file: null`, `scope: "between"` --, porque o ficheiro seguinte abre
    exactamente no instante em que ela ACABA. Atribui-la ao ficheiro aberto no
    momento do dreno foi o que pos 30 434,2 s num ficheiro com 558,7 s de
    `wall_s` (medido em `2026-11-17/162543.24k.opus`).
  * `dropped_s` e' perda A MAIS: audio que chegou e a fila recusou, invisivel no
    relogio do audio (nao ocupa tempo no ficheiro).
"""
from __future__ import annotations

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
#: OS DOIS INDICES DA RAIZ TAMBEM TEM TECTO (medido 2026-11-26): `_prune` so'
#: desce nas PASTAS de dia (`os.path.isdir(d)`), logo `index.jsonl` (115 KB) e
#: `lines.jsonl` (30 KB) ficavam na raiz e nunca eram visitados -- dois ficheiros
#: append-only sem tecto, exactamente a classe que esta casa ja' pagou. Eles
#: crescem a cada segmento (index) e a cada legenda fechada (lines), entao a
#: poda guarda as ultimas N linhas acima do tecto de bytes.
INDEX_FILE_MAX_BYTES = 512 * 1024
INDEX_ROWS_KEEP = 2000
LINES_FILE_MAX_BYTES = 1024 * 1024
LINES_ROWS_KEEP = 4000


def _trim_jsonl_file(path, cap_bytes, keep_rows, log=None):
    """Um journal append-only tem tecto: acima de `cap_bytes` fica o mais NOVO.

    Um marcador por pausa do tap e' barato, mas um ficheiro que so' cresce e' a
    classe que esta casa ja' pagou (`AGENTS.md`, "a store is a cache with
    retention"). A leitura so' acontece ACIMA do tecto, logo o custo normal e'
    um `getsize`; a escrita e' atomica (`os.replace` de um `.trim`), para um
    leitor que abra o ficheiro a meio nunca ver metade das linhas.

    Medido 2026-11-26: `_prune` so' desce nas PASTAS de dia, e `index.jsonl` /
    `lines.jsonl` vivem na raiz do ring -- dois ficheiros append-only sem tecto.
    Por isso a regra vive aqui, e nao dentro do `_prune`, para o escritor de
    `lines.jsonl` a poder chamar mesmo com o ring desligado.
    """
    try:
        size = os.path.getsize(path)
    except OSError:
        return 0
    if size <= cap_bytes:
        return 0
    try:
        with open(path, encoding='utf-8') as fh:
            rows = fh.readlines()
    except OSError:
        return 0
    keep = rows[-keep_rows:]
    tmp = path + '.trim'
    try:
        with open(tmp, 'w', encoding='utf-8') as fh:
            fh.writelines(keep)
        os.replace(tmp, path)
    except OSError as exc:
        try:
            os.remove(tmp)
        except OSError:
            pass
        if log is not None:
            log('%s_trim_failed error=%r' % (os.path.basename(path).split('.')[0], exc))
        return 0
    if log is not None:
        log('%s_trimmed kept=%d of=%d'
            % (os.path.basename(path).split('.')[0], len(keep), len(rows)))
    return len(rows) - len(keep)

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
        #: O INICIO DO INTERVALO DE PAREDE do segmento aberto: a chegada do
        #: ultimo bloco do segmento ANTERIOR (ou a do primeiro deste, quando nao
        #: ha' anterior). E' o que faz `wall_s` particionar o tempo em vez de
        #: saltar os buracos: o buraco que atravessa uma rotacao pertence ao
        #: ficheiro seguinte, porque e' exactamente nele que ele ACABA.
        self._seg_span_start = None
        #: A chegada do ultimo bloco GRAVADO no ultimo segmento fechado. Uma
        #: pausa que o escritor ocioso fechou tem o `t0` aqui -- nunca no ficheiro
        #: que ainda vai abrir (o defeito do corpus de 2026-11-17).
        self._last_closed_wall = None
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
                    # A ATRIBUICAO NAO ACONTECE AQUI: este fio nao sabe se o
                    # segmento que estava aberto ainda esta' aberto (quem o fecha
                    # e' o escritor), nem qual e' o ficheiro seguinte. O marcador
                    # guarda o INTERVALO; `_flush_loss` (o escritor) decide a que
                    # `[wall_t0, wall_t1]` ele pertence. Carimba-lo com
                    # `self._file` aqui ou no dreno foi o defeito: o buraco de
                    # 30 434,2 s de 2026-11-17 ficou no ficheiro que ABRE quando
                    # ele acaba.
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
        #: O intervalo de parede deste ficheiro COMECA onde o audio anterior
        #: acabou. Sem isto os buracos entre dois ficheiros nao pertencem a
        #: nenhum e a soma dos `wall_s` deixa de particionar o tempo.
        self._seg_span_start = self._last_closed_wall
        self._seg_last_wall = None
        # `_seg_dropped` NAO e' zerado aqui: sao as amostras que a fila recusou
        # desde o ultimo segmento ESCRITO, e uma recusa que cai entre dois
        # ficheiros entra no SEGUINTE em vez de desaparecer. Quem o zera e'
        # `_close_segment`, depois de o gravar. `_seg_gap_s` NAO e' mais desse
        # tipo: um buraco so' entra nele quando o seu `[t0,t1]` cabe no
        # `[wall_t0, wall_t1]` deste segmento (`_attribute_gap`); os que
        # atravessam uma rotacao ficam no `gaps.jsonl` com `file: null`.
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
        wall_t0, wall_t1 = self._seg_span_start, self._seg_last_wall
        wall_s = None
        if wall_t0 is not None and wall_t1 is not None:
            wall_s = round(wall_t1 - wall_t0, 3)
        #: `stream_s` e' a parede em que o tap ESTAVA a entregar: o intervalo
        #: menos os buracos medidos. E' a unica forma de a identidade fechar com
        #: um numero publicado, porque `t1-t0` e' relogio de audio (3x quando o
        #: tap entrega 48 kHz a um ring de 16 kHz) -- ver o topo do modulo.
        stream_s = round(wall_s - seg_gap_s, 3) if wall_s is not None else None
        rec = {'file': os.path.relpath(path, self.root).replace(os.sep, '/'),
               't0': round(self._t0, 3), 't1': round(t1, 3),
               'samples': self._seg_samples, 'rate': self.rate,
               'kbps': self.kbps, 'bytes': size,
               # AS MEDIDAS DA PERDA, ao lado das duas do audio. O segmento
               # OCUPA o intervalo de parede `[wall_t0, wall_t1]` -- que comeca
               # onde o audio anterior acabou -- e dentro dele cada segundo ou
               # chegou (`stream_s`) ou nao chegou (`gap_s`):
               # `wall_t1 - wall_t0 == wall_s == stream_s + gap_s`. `dropped_s`
               # e' perda A MAIS (chegou e a fila recusou). Sem estes campos um
               # leitor so' tem o `mtime` do ficheiro, que e' metadados e mente
               # num `copy`/`touch`.
               'wall_t0': round(wall_t0, 3) if wall_t0 is not None else None,
               'wall_t1': round(wall_t1, 3) if wall_t1 is not None else None,
               'wall_s': wall_s,
               'stream_s': stream_s,
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
        if wall_t1 is not None:
            self._last_closed_wall = wall_t1
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
            # No primeiro segmento da vida do ring nao ha' chegada anterior: o
            # intervalo dele comeca na primeira.
            if self._seg_span_start is None:
                self._seg_span_start = wall
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
    def _attribute_gap(self, t_from, t_to, final=False):
        """A QUE `[wall_t0, wall_t1]` pertence o buraco `[t_from, t_to]`.

        UMA regra, num sitio so': o buraco pertence ao segmento ABERTO cujo
        intervalo de parede o contem por inteiro. Se nenhum o contem, ele
        atravessou uma rotacao e nao pertence a ficheiro nenhum (`between`) --
        o ficheiro seguinte abre exactamente quando ele ACABA, e carimba-lo com
        esse ficheiro foi o defeito medido em 2026-11-17 (`162543.24k.opus`
        levou 30 434,2 s de um buraco que terminava na sua abertura).

        `hold`: o bloco que fecha o buraco ainda esta' na fila (o escritor vai
        para tras), logo `_seg_last_wall` ainda nao chega a `t_to`. Segurar o
        marcador e' mais honesto do que decidir com o intervalo incompleto; ele
        e' drenado na volta seguinte, e no dreno FINAL nada fica por decidir.
        """
        if (self._proc is not None and self._seg_span_start is not None
                and self._seg_last_wall is not None
                and t_from >= self._seg_span_start - 0.001
                and t_to <= self._seg_last_wall + 0.001):
            return 'span', self._file
        if (not final and self._proc is not None
                and self._seg_span_start is not None
                and self._seg_last_wall is not None
                and t_from >= self._seg_span_start - 0.001
                and t_to > self._seg_last_wall):
            return 'hold', None
        return 'between', None

    def _flush_loss(self, final=False):
        """Drena os marcadores de perda para `gaps.jsonl` e para o log.

        Corre no FIO DO ESCRITOR, nunca no do audio (`push` so' acumula debaixo
        do `lock`). Uma linha por buraco de chegada, com o intervalo exacto e o
        segmento que o CONTEM (`_attribute_gap`); e uma linha de log por cada
        `DROP_LOG_EVERY_S` com o acumulado da fila -- a forma desta casa
        (`LOG_STDOUT_SUPPLIED dropped=N`), porque uma linha por bloco perdido
        seria um log a crescer com o defeito.
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
        held = []
        for t_from, t_to, gap in pending:
            scope, path = self._attribute_gap(t_from, t_to, final)
            if scope == 'hold':
                held.append((t_from, t_to, gap))
                continue
            if scope == 'span':
                # O MESMO predicado que escolhe o ficheiro escolhe o contador:
                # a soma dos `gap_s` do indice e' a soma dos marcadores `span`.
                with self._lock:
                    self._seg_gap_s += gap
            file_rec = (os.path.relpath(path, self.root).replace(os.sep, '/')
                        if path else None)
            rows.append({'t0': round(t_from, 3), 't1': round(t_to, 3),
                         'gap_s': round(gap, 3),
                         # A estimativa de amostras usa o rate DECLARADO; o
                         # ring nao conhece o rate real do tap (o defeito de
                         # 3x documentado no topo). O numero que vale e' `gap_s`.
                         'samples_missing': int(round(gap * self.rate)),
                         'rate': self.rate, 'scope': scope, 'file': file_rec})
            self._log('gap t0=%.3f t1=%.3f gap_s=%.3f samples_missing=%d scope=%s file=%s'
                      % (t_from, t_to, gap, int(round(gap * self.rate)), scope,
                         os.path.basename(file_rec) if file_rec else '-'))
        if held:
            with self._lock:
                room = GAP_PENDING_MAX - len(self._pending_gaps)
                self._pending_gaps = held[:max(0, room)] + self._pending_gaps
                overflow = held[max(0, room):]
            for t_from, t_to, gap in overflow:
                # NUNCA perder um buraco CONTADO: sem espaco para o segurar, ele
                # sai como `between` e o log diz que a atribuicao foi sacrificada.
                rows.append({'t0': round(t_from, 3), 't1': round(t_to, 3),
                             'gap_s': round(gap, 3),
                             'samples_missing': int(round(gap * self.rate)),
                             'rate': self.rate, 'scope': 'between', 'file': None})
                self._log('gap_unattributed t0=%.3f gap_s=%.3f reason=pending-full'
                          % (t_from, gap))
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
        self._trim_jsonl('gaps.jsonl', GAP_FILE_MAX_BYTES, GAP_ROWS_KEEP)
        self._trim_jsonl('index.jsonl', INDEX_FILE_MAX_BYTES, INDEX_ROWS_KEEP)
        self._trim_jsonl('lines.jsonl', LINES_FILE_MAX_BYTES, LINES_ROWS_KEEP)
        return {'deleted': deleted, 'mb_left': round(total, 1)}

    def _trim_jsonl(self, name, cap_bytes, keep_rows):
        """Um journal do DIRECTORIO DO RING tem tecto (a regra vive em `_trim_jsonl_file`)."""
        return _trim_jsonl_file(os.path.join(self.dir, name), cap_bytes,
                                keep_rows, self._log)

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
        # O TECTO FECHA-SE AQUI TAMBEM (2026-11-26): este escritor corre com o
        # ring LIGADO OU DESLIGADO, e um journal que so' cresce nao espera pelo
        # proximo `_prune` de um objecto que pode nem existir.
        _trim_jsonl_file(os.path.join(d, 'lines.jsonl'), LINES_FILE_MAX_BYTES,
                         LINES_ROWS_KEEP)
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
    """Os buracos de CHEGADA que o ring viu.

    `[{t0, t1, gap_s, samples_missing, scope, file}]`: `scope="span"` e o
    `file` nomeiam o segmento cujo `[wall_t0, wall_t1]` contem o intervalo;
    `scope="between"` e `file=None` dizem que ele atravessou uma rotacao e nao
    pertence a ficheiro nenhum (o ficheiro seguinte abre quando ele acaba).

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
