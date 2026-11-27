"""A FILA EM DISCO DO AUDIO QUE FICOU SEM TRANSCRICAO -- e o executor que a corre.

ORDEM DO DONO (2026-11-03), verbatim:

    *"os modelos entram e saem conforme a carga do sistema, e o audio nao
      processado e' processado sozinho quando a carga libera -- SEM NUNCA
      TRAVAR A MAQUINA DO DONO"*

O PROBLEMA QUE ISTO RESOLVE, medido e nao suposto. O worker ja' guarda o audio
que chega com nada carregado (`worker/live_queue.py`, `PendingAudio`), e ja' o
transcreve sozinho quando a carga desce. Mas:

  1. o spool do worker vive no TEMP dele (`sotto-pending-audio-<pid>`) e o
     `sweep_spool_dir` APAGA o que um run ANTERIOR deixou -- audio de um worker
     que morreu (park por carga, kill, crash) era descartado, nao transcrito;
  2. quando o shell estaciona o worker para libertar CUDA (o unico lever que
     liberta mesmo, porque mata o processo), ninguem retoma esse audio;
  3. nao havia forma de transcrever esse audio com prioridade BAIXA de CPU: um
     lote a competir com o resto da maquina e' a mesma coisa que nao o correr.

O QUE ESTE FICHEIRO E'. Duas coisas, uma em cima da outra:

  * `BatchQueue` -- uma fila EM DISCO (`TMPDIR`/`I:\\cc-tmp`, ou
    `SOTTO_BATCH_QUEUE_DIR`): um manifesto JSON por bloco de audio pendente, mais
    o `float32` cru ao lado. Um restart da shell (ou do worker, ou da maquina)
    nao a apaga: e' o mesmo directorio e os manifestos sao lidos na construcao.
    Escrita ATOMICA (`os.replace`) e nenhum caminho que apague audio sem o ter
    entregado: um bloco so' sai da fila DEPOIS de transcrito (`done`) ou depois de
    `MAX_ATTEMPTS` tentativas, e nesse caso fica com o erro escrito.
  * `BatchExecutor` -- um thread que corre o Parakeet POR CIMA da fila, em modo
    lote, num processo filho de prioridade `BELOW_NORMAL`, **sem abrir
    dispositivo de audio nenhum** (o driver `--transcribe` le' um ficheiro e sai).
    Ele CEDE: a cada `child_poll_s` le' a carga pela MESMA fonte que
    `load_shedding.sample_load()` e, se o nivel subiu acima de `leve`, mata o
    filho e devolve o bloco a' fila. O disco nao perde nada; a maquina nao trava.

A PRIORIDADE E' O PONTO. `BELOW_NORMAL_PRIORITY_CLASS` (0x00004000) no filho e'
o que faz a diferenca entre "processa o resto do audio" e "o PC do dono engasga
enquanto processa o resto do audio": o scheduler do Windows entrega o CPU ao que
o dono esta' a fazer primeiro, e o lote ocupa o que sobra.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time

#: Taxa do audio dos blocos. E' `TARGET_SR` do worker (16 kHz) e nao uma
#: escolha deste modulo: o `PendingAudio` escreve exactamente estes bytes.
RATE = 16000

#: Onde a fila vive quando `SOTTO_BATCH_QUEUE_DIR` nao manda. Ordem: `TMPDIR`,
#: depois `I:\\cc-tmp` (o scratch do dono nesta maquina -- medido 2026-11-03:
#: `TMPDIR` esta' VAZIO e o `gettempdir()` devolve `G:\\Temp`, por isso sem esta
#: segunda linha a fila ia para o meio do temp do sistema em vez do sitio que o
#: dono indicou), e o `gettempdir()` como ultimo recurso.
QUEUE_ENV = 'SOTTO_BATCH_QUEUE_DIR'
QUEUE_DIRNAME = 'sotto-batch-queue'
OWNER_SCRATCH = r'I:\cc-tmp'

#: Padroes dos spools do worker (`worker/live_queue.py`).
SPOOL_DIR_PREFIX = 'sotto-pending-audio-'
SPOOL_FILE_GLOB = 'pending-'
SPOOL_SUFFIX = '.f32'

#: Idade minima de um ficheiro de spool para ser adoptado: um worker vivo pode
#: estar a escrever no ultimo. Dois segundos e' quatro vezes o bloco dele (100 ms).
ADOPT_MIN_AGE_S = 2.0

#: Um bloco que falha N vezes fica `failed` com o erro escrito, em vez de
#: rodar para sempre num ficheiro que o motor nao consegue ler.
MAX_ATTEMPTS = 3

#: Entre duas tentativas do mesmo bloco: sem isto, um bloco venenoso e' tentado
#: em cada volta do executor.
RETRY_BACKOFF_S = 60.0

#: Quantos `done` ficam no directorio. Ficam para a recepcao poder ser lida (o
#: texto transcrito), nao para a fila crescer para sempre.
DONE_KEEP = 200

#: `subprocess` no Windows: sem janela e com prioridade BAIXA.
CREATE_NO_WINDOW = 0x08000000
BELOW_NORMAL_PRIORITY_CLASS = 0x00004000

#: QUANTO DE UM NUCLEO O LOTE PODE OCUPAR -- o ORCAMENTO, nao um gosto.
#:
#: MEDIDO no dono (2026-11-08 23:2x, `_main/shell-thread-cpu.py 55104 --seconds 6`):
#: `pid 55104: 48 threads, 48.4% de UM nucleo`, com `36.0% tid 10848
#: sotto-batch-executor` -- e o vigia da frota nomeou este processo como a maior
#: pressao de stutter (15 episodios/60 min). O laco nunca foi um spin: ele arranca
#: UM filho por bloco e espera-o; o que nao existia era um TECTO declarado, logo a
#: unica coisa que o travava era o nivel de carga subir, e o bloco seguinte comecava
#: no instante em que o anterior acabava.
#:
#: A LEI E' A MESMA DA PINTURA DA LEGENDA (`CAPTION_FRAME_BUDGET`,
#: `caption_overlay.py:81`): o periodo deriva do custo medido, `idle =
#: custo * (1 - orcamento) / orcamento`, e a taxa de servico converge para o
#: orcamento em vez de ser escolhida. Um laco que dorme o tempo que trabalha gasta
#: 100 % de um nucleo por construcao -- foi o defeito que aquele orcamento curou.
#:
#: 12 % e' o numero que o dono pediu: com o filho a 2 fios (o tecto abaixo) um
#: bloco de 15 s de audio que decodifica em 3 s da' `3 * 0.88 / 0.12 = 22 s` de
#: espera, ou seja o lote continua a andar (~4x tempo real de audio) e a maquina
#: nunca perde mais de 12 % de um nucleo para ele ao longo da corrida.
BATCH_CPU_BUDGET = 0.12

#: O TECTO DE FIOS DO FILHO -- o cap que impede um bloco sozinho de estourar o
#: orcamento. O orcamento e' uma MEDIA; um bloco com 8 fios sao 8 nucleos durante
#: segundos, e o dono sente isso mesmo que a media anual seja de 12 %. Dois fios
#: sao o que o driver ja' usava (`--threads 2`); agora o valor e' DECLARADO aqui e
#: viaja na env do filho (`OMP_NUM_THREADS` e as irmas BLAS), e o driver le'-o em
#: vez de repetir o numero. A escolha e' conservadora de proposito: o lote corre
#: em segundo plano e o que interessa e' nao se ouvir.
BATCH_CHILD_THREADS = 2

#: QUANTOS BLOCOS UM FILHO ACEITA POR CARGA DO MOTOR (medido 2026-11-12).
#:
#: O driver e' um PROCESSO por bloco e ele carrega o Parakeet ONNX int4 inteiro antes de
#: decodificar -- ~1,9 GB de paginas de um mmap, em leituras de ~4 MB. O watcher mediu
#: exactamente essa forma no dono (`python.exe(53836)`, `io 162.4MB/s (40 ops/s, 4060 KB/op)`,
#: 2026-11-12 05:0x): um episodio inteiro de stutter e' UMA carga de modelo de um bloco.
#: Com N blocos pendentes isso e' N cargas, e a maquina paga N x 1,9 GB de disco para
#: transcrever N blocos de audio que ja' estao no disco.
#:
#: O tecto e' 8 porque o `BATCH_CPU_BUDGET` e' uma MEDIA sobre o que o laco serve: um filho
#: que aceitasse a fila inteira seria um bloco de horas, e o `yield` por carga alta (a regra
#: que nao se negocеia) nunca teria onde cortar entre um bloco e o seguinte. Oito blocos de
#: 15 s = 2 min de audio por carga, e o custo de UMA carga fica amortizado em oito.
MAX_BLOCKS_PER_CHILD = 8

#: As variaveis que os motores consultam para se limitarem: o runtime ONNX le'
#: `OMP_NUM_THREADS`, o numpy/BLAS le' as outras. O filho recebe TODAS com o mesmo
#: valor, senao o tecto vale para um motor e o outro abre os fios todos.
THREAD_ENV_KEYS = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS',
                   'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
WORKER_DIR = os.path.join(REPO, 'worker')


def queue_dir():
    """O directorio da fila: a env manda, senao `TMPDIR/sotto-batch-queue`."""
    given = os.environ.get(QUEUE_ENV)
    if given:
        return given
    for base in (os.environ.get('TMPDIR'), OWNER_SCRATCH,
                 tempfile.gettempdir()):
        if base and os.path.isdir(base):
            return os.path.join(base, QUEUE_DIRNAME)
    return os.path.join(tempfile.gettempdir(), QUEUE_DIRNAME)


def _noop(_message):
    return None


def _pid_alive(pid):
    """True/False se o processo existe; None quando nao se pode saber."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    if pid <= 0:
        return False
    if os.name != 'nt':
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except OSError:
            return None
        return True
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL('kernel32', use_last_error=True)
        handle = k32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = wintypes.DWORD()
        ok = k32.GetExitCodeProcess(handle, ctypes.byref(code))
        k32.CloseHandle(handle)
        return bool(ok) and code.value == 259  # STILL_ACTIVE
    except Exception:                                            # noqa: BLE001
        return None


def _atomic_write(path, data):
    """Escreve `data` (bytes) em `path` SEM deixar um ficheiro a meio.

    O par `.tmp` + `os.replace` e' o que faz um crash a meio da escrita deixar o
    ficheiro ANTIGO (ou nenhum) em vez de um manifesto truncado que a leitura
    seguinte teria de adivinhar.
    """
    tmp = path + '.tmp'
    with open(tmp, 'wb') as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _atomic_write_text(path, text):
    _atomic_write(path, text.encode('utf-8'))


class BatchQueue:
    """A fila em disco. Uma instancia por utilizador; o disco e' o estado.

    TUDO o que e' estado esta' no directorio: nao ha' indice em RAM que um
    restart perca. Um manifesto chama-se `<id>.json` e o audio `<id>.f32`; o
    `id` e' ordenavel (`<epoch>-<pid>-<seq>`), por isso a ordem de chegada
    sobrevive a um restart sem depender da ordem de um `glob`.
    """

    def __init__(self, path=None, log_fn=None, rate=RATE, clock=None):
        self.path = path or queue_dir()
        self.log = log_fn or _noop
        self.rate = int(rate)
        self._clock = clock or time.time
        self._lock = threading.RLock()
        self._seq = 0
        self.entries = []
        self.recovered = 0
        self.orphans = 0
        # A CONTAGEM DA LEITURA (2026-11-24, MEDIDO). O log do dono tinha
        # `BATCH_QUEUE_ORPHANS manifests_without_audio=2 dir=I:\cc-tmp\sotto-batch-queue`
        # **2288 vezes** -- um a cada 10 s (`poll_s`), sempre o MESMO conjunto --
        # e o `sotto-batch-executor` media 4,7 % de um nucleo em `THREAD_CPU`
        # (total da shell 12,6 %). Uma varredura cujo resultado nao pode mudar
        # sem o directorio mudar pergunta UMA vez, nao 360 vezes por hora.
        self.scans = 0
        self.scan_skips = 0
        self._scan_stamp = None
        self._orphans_logged = 0
        try:
            os.makedirs(self.path, exist_ok=True)
        except OSError as exc:
            self.log(f'BATCH_QUEUE_DIR_FAILED error={exc!r} dir={self.path}')
        self.refresh()

    # -- caminhos ---------------------------------------------------------
    def _manifest_path(self, entry_id):
        return os.path.join(self.path, '%s.json' % entry_id)

    def _payload_path(self, entry_id):
        return os.path.join(self.path, entry_id + SPOOL_SUFFIX)

    def payload_path(self, entry_id):
        return self._payload_path(entry_id)

    def manifest_path(self, entry_id):
        return self._manifest_path(entry_id)

    # -- leitura ----------------------------------------------------------
    def refresh(self, force=False):
        """Rele' o directorio. CRASH RECOVERY: `inflight` volta a `queued`.

        Um bloco `inflight` e' um bloco cujo processo morreu a meio (a shell
        fechou, o executor foi morto). Deixa-lo nesse estado seria perde-lo em
        silencio -- exactamente o que este modulo existe para impedir.

        O DIRECTORIO QUE NAO MUDOU NAO SE RELE (2026-11-24, MEDIDO): o executor
        chama isto a cada `poll_s` (10 s) e cada chamada fazia `listdir` + um
        `open`+`json.load` por manifesto, com o resultado sempre igual -- 2288
        linhas `BATCH_QUEUE_ORPHANS` identicas no log do dono. A guarda e' a LISTA
        DE NOMES que o `listdir` ja' devolve: o directorio cujos nomes sao os
        mesmos nao paga um `open`+`json.load` por manifesto. A primeira leitura e
        o `force=True` correm sempre, e e' isso que a recuperacao de `inflight`
        depois de um crash continua a ter.

        PORQUE NAO O `st_mtime_ns` DO DIRECTORIO (medido nesta maquina, 2026-11-24):
        no NTFS o carimbo do directorio e' actualizado de forma PREGUICOSA e
        `os.stat` devolve o valor antigo por segundos. O braco A3 deste oraculo
        criou um manifesto e a leitura seguinte disse `scans=1` -- a guarda
        escondia trabalho NOVO. Um NOME e' a testemunha certa para "entrou ou saiu
        um bloco"; um manifesto reescrito no sitio pelo MESMO processo nao precisa
        de releitura (o manifesto em RAM ja' mudou) e nenhum outro processo
        reescreve um manifesto existente -- `enqueue_f32` cria um id novo.
        """
        with self._lock:
            try:
                names = sorted(os.listdir(self.path))
            except OSError as exc:
                self.log(f'BATCH_QUEUE_LIST_FAILED error={exc!r} dir={self.path}')
                names = []
            stamp = tuple(names)
            if not force and stamp == getattr(self, '_scan_stamp', None):
                self.scan_skips += 1
                return list(self.entries)
            self.scans += 1
            self._scan_stamp = stamp
            entries = []
            recovered = 0
            orphans = 0
            for name in names:
                if name.endswith('.tmp'):
                    # Restos de uma escrita interrompida: o payload/ manifesto
                    # definitivo nao existe, logo estes bytes nao sao fila nem
                    # audio entregue.
                    try:
                        os.remove(os.path.join(self.path, name))
                    except OSError:
                        pass
                    continue
                if not name.endswith('.json'):
                    continue
                path = os.path.join(self.path, name)
                try:
                    with open(path, 'r', encoding='utf-8') as handle:
                        entry = json.load(handle)
                except (OSError, ValueError) as exc:
                    self.log(f'BATCH_QUEUE_MANIFEST_UNREADABLE file={name} error={exc!r}')
                    continue
                if not isinstance(entry, dict) or not entry.get('id'):
                    continue
                payload = self._payload_path(str(entry['id']))
                if entry.get('state') != 'done' and not os.path.isfile(payload):
                    # MANIFESTO SEM AUDIO: o payload nunca chegou ao disco. Nao e'
                    # um bloco a transcrever; e' um registo sem sujeito.
                    orphans += 1
                    continue
                if entry.get('state') == 'inflight':
                    entry['state'] = 'queued'
                    entry['recovered'] = int(entry.get('recovered') or 0) + 1
                    recovered += 1
                    self._write_manifest(entry)
                entries.append(entry)
            entries.sort(key=lambda e: (str(e.get('created') or ''), str(e['id'])))
            self.entries = entries
            self.recovered += recovered
            self.orphans += orphans
            if recovered:
                self.log(f'BATCH_QUEUE_RECOVERED inflight={recovered} dir={self.path}')
            # A LINHA SO' QUANDO O NUMERO MUDA. O estado e' o mesmo conjunto de
            # orfaos; repeti-lo a cada 10 s nao informa ninguem e escreve no log
            # 360 vezes por hora (medido: 2288 linhas). A mudanca -- aparecer um
            # orfao novo, ou o audio chegar e a lista esvaziar -- continua a ser
            # dita no instante em que acontece.
            if orphans and orphans != getattr(self, '_orphans_logged', 0):
                self.log(f'BATCH_QUEUE_ORPHANS manifests_without_audio={orphans} dir={self.path}')
            self._orphans_logged = orphans
            return list(self.entries)

    def pending(self):
        """Os blocos por transcrever, por ordem de chegada. `failed` fica fora."""
        with self._lock:
            return [dict(e) for e in self.entries if e.get('state') == 'queued']

    def next_entry(self, now=None):
        """O proximo bloco: o mais antigo que ja' passou o backoff."""
        found = self.next_entries(1, now=now)
        return found[0] if found else None

    def next_entries(self, limit, now=None):
        """Os proximos `limit` blocos prontos, por ordem de chegada.

        Existe para o executor poder pagar UMA carga do motor para varios blocos
        (ver `MAX_BLOCKS_PER_CHILD`): a fila continua a entregar a lista por
        ordem, e quem chama e' que decide quantos aceita.
        """
        now = self._clock() if now is None else now
        limit = max(1, int(limit))
        out = []
        with self._lock:
            for entry in self.entries:
                if len(out) >= limit:
                    break
                if entry.get('state') != 'queued':
                    continue
                retry_at = float(entry.get('retry_at') or 0.0)
                if retry_at and retry_at > now:
                    continue
                out.append(dict(entry))
        return out

    def stats(self):
        counts = {'queued': 0, 'inflight': 0, 'done': 0, 'failed': 0}
        samples = 0
        for entry in self.entries:
            state = str(entry.get('state') or 'queued')
            counts[state] = counts.get(state, 0) + 1
            if state != 'done':
                samples += int(entry.get('samples') or 0)
        counts['dir'] = self.path
        counts['pending_s'] = round(samples / float(self.rate), 3)
        return counts

    # -- escrita ----------------------------------------------------------
    def _write_manifest(self, entry):
        _atomic_write_text(self._manifest_path(str(entry['id'])),
                           json.dumps(entry, ensure_ascii=False, indent=1))

    def _new_id(self, now=None):
        now = self._clock() if now is None else now
        self._seq += 1
        return '%013d-%d-%04d' % (int(now * 1000), os.getpid(), self._seq)

    def enqueue_f32(self, raw, source='?', now=None, meta=None):
        """Um bloco (ou um ficheiro inteiro) de `float32` cru entra na fila.

        O PAYLOAD VAI PRIMEIRO, O MANIFESTO DEPOIS. Ao contrario, um crash entre
        os dois deixaria um manifesto a apontar para audio que nao existe --
        e a leitura seguinte teria de o julgar. Assim o pior caso e' um payload
        sem manifesto: nao e' um bloco da fila, e' lixo que nao aparece no
        `pending()`. Devolve o manifesto, ou None quando o disco recusou.
        """
        raw = bytes(raw or b'')
        if len(raw) < 4 or len(raw) % 4:
            self.log(f'BATCH_QUEUE_ENQUEUE_REFUSED reason=payload-not-float32 '
                     f'bytes={len(raw)} source={source}')
            return None
        now = self._clock() if now is None else now
        entry_id = self._new_id(now)
        payload = self._payload_path(entry_id)
        try:
            os.makedirs(self.path, exist_ok=True)
            _atomic_write(payload, raw)
        except OSError as exc:
            self.log(f'BATCH_QUEUE_ENQUEUE_FAILED error={exc!r} source={source} '
                     f'dir={self.path}')
            return None
        entry = {
            'id': entry_id,
            'created': round(float(now), 3),
            'rate': self.rate,
            'samples': len(raw) // 4,
            'seconds': round(len(raw) / 4.0 / float(self.rate), 3),
            'source': str(source),
            'state': 'queued',
            'attempts': 0,
            'retry_at': 0.0,
        }
        entry.update(meta or {})
        try:
            self._write_manifest(entry)
        except OSError as exc:
            self.log(f'BATCH_QUEUE_MANIFEST_FAILED error={exc!r} id={entry_id}')
            try:
                os.remove(payload)
            except OSError:
                pass
            return None
        with self._lock:
            self.entries.append(entry)
            self.entries.sort(key=lambda e: (str(e.get('created') or ''), str(e['id'])))
        self.log(f'BATCH_QUEUE_ENQUEUED id={entry_id} source={source} '
                 f'seconds={entry["seconds"]} pending={self.stats()["queued"]}')
        return dict(entry)

    def enqueue_file(self, path, source=None, now=None):
        """Um ficheiro `float32` cru (o spool do worker) entra na fila, copiado."""
        try:
            with open(path, 'rb') as handle:
                raw = handle.read()
        except OSError as exc:
            self.log(f'BATCH_QUEUE_READ_FAILED error={exc!r} path={path}')
            return None
        return self.enqueue_f32(raw, source=source or os.path.basename(path), now=now)

    def claim(self, entry_id):
        """Marca o bloco como `inflight`: outra volta nao o pega ao mesmo tempo."""
        with self._lock:
            entry = self._find(entry_id)
            if entry is None:
                return None
            entry['state'] = 'inflight'
            entry['started'] = round(self._clock(), 3)
            self._write_manifest(entry)
            return dict(entry)

    def requeue(self, entry_id, reason='', bump_attempts=True, now=None):
        """Devolve o bloco a' fila (cedeu por carga, ou o processo morreu)."""
        now = self._clock() if now is None else now
        with self._lock:
            entry = self._find(entry_id)
            if entry is None:
                return None
            if bump_attempts:
                entry['attempts'] = int(entry.get('attempts') or 0) + 1
            entry['state'] = 'queued'
            entry['retry_at'] = round(now + RETRY_BACKOFF_S, 3) if entry['attempts'] else 0.0
            entry['last_reason'] = str(reason)
            self._write_manifest(entry)
            return dict(entry)

    def mark_done(self, entry_id, text='', elapsed_s=None, meta=None):
        with self._lock:
            entry = self._find(entry_id)
            if entry is None:
                return None
            entry['state'] = 'done'
            entry['text'] = str(text or '')
            entry['finished'] = round(self._clock(), 3)
            if elapsed_s is not None:
                entry['elapsed_s'] = round(float(elapsed_s), 3)
            entry.update(meta or {})
            self._write_manifest(entry)
            try:
                os.remove(self._payload_path(entry_id))
            except OSError:
                pass
            self._prune_done()
            return dict(entry)

    def mark_failed(self, entry_id, error=''):
        with self._lock:
            entry = self._find(entry_id)
            if entry is None:
                return None
            entry['state'] = 'failed'
            entry['error'] = str(error or '')[:2000]
            entry['finished'] = round(self._clock(), 3)
            self._write_manifest(entry)
            try:
                os.remove(self._payload_path(entry_id))
            except OSError:
                pass
            return dict(entry)

    def _find(self, entry_id):
        for entry in self.entries:
            if str(entry.get('id')) == str(entry_id):
                return entry
        return None

    def _prune_done(self):
        done = [e for e in self.entries if e.get('state') == 'done']
        if len(done) <= DONE_KEEP:
            return 0
        for entry in done[:len(done) - DONE_KEEP]:
            try:
                os.remove(self._manifest_path(str(entry['id'])))
            except OSError:
                pass
            self.entries.remove(entry)
        return len(done) - DONE_KEEP

    # -- a adopcao do audio que ficou sem transcricao ---------------------
    def adopt_dead_spools(self, roots=None, now=None):
        """Adopta o spool de um worker que JA' NAO EXISTE para dentro da fila.

        PORQUE E' QUE SO' OS MORTOS. Um directorio `sotto-pending-audio-<pid>`
        de um worker VIVO e' audio que esse worker ainda vai transcrever: copia-lo
        agora poria a mesma frase duas vezes na legenda. O pid esta' no nome do
        directorio, e a pergunta "existe?" e' barata e respondivel.

        A COPIA NAO APAGA A ORIGEM. O spool pertence ao worker e o
        `sweep_spool_dir` dele limpa-o no arranque seguinte; este modulo nao
        apaga audio de ninguem. Para a segunda leitura nao duplicar o mesmo
        ficheiro, a impressao digital `(caminho, tamanho, mtime)` fica em
        `adopted.json`, no directorio da fila.
        """
        now = self._clock() if now is None else now
        roots = list(roots) if roots is not None else self._default_roots()
        index_path = os.path.join(self.path, 'adopted.json')
        seen = self._read_index(index_path)
        adopted = 0
        scanned = 0
        for directory in roots:
            name = os.path.basename(directory)
            pid = None
            if name.startswith(SPOOL_DIR_PREFIX):
                tail = name[len(SPOOL_DIR_PREFIX):]
                pid = tail if tail.isdigit() else None
                if pid is not None and _pid_alive(pid) is not False:
                    # Vivo (ou nao se sabe): o dono do ficheiro ainda o pode ler.
                    continue
            try:
                names = sorted(os.listdir(directory))
            except OSError:
                continue
            for fname in names:
                if not fname.startswith(SPOOL_FILE_GLOB) or not fname.endswith(SPOOL_SUFFIX):
                    continue
                full = os.path.join(directory, fname)
                try:
                    info = os.stat(full)
                except OSError:
                    continue
                scanned += 1
                if (now - info.st_mtime) < ADOPT_MIN_AGE_S:
                    continue
                key = '%s|%d|%d' % (full, info.st_size, int(info.st_mtime))
                if key in seen:
                    continue
                entry = self.enqueue_file(full, source='spool:%s' % name, now=now)
                if entry is None:
                    continue
                seen[key] = {'id': entry['id'], 'bytes': info.st_size,
                             'adopted_at': round(float(now), 3)}
                adopted += 1
        if adopted:
            self._write_index(index_path, seen)
            self.log(f'BATCH_QUEUE_ADOPTED files={adopted} roots={len(roots)} '
                     f'pending_s={self.stats()["pending_s"]}')
        return adopted

    def _default_roots(self):
        base = os.environ.get('TMPDIR') or tempfile.gettempdir()
        roots = []
        try:
            for name in sorted(os.listdir(base)):
                full = os.path.join(base, name)
                if os.path.isdir(full) and name.startswith(SPOOL_DIR_PREFIX):
                    roots.append(full)
        except OSError:
            pass
        explicit = os.environ.get('SOTTO_REDUX_SPOOL_DIR')
        if explicit and os.path.isdir(explicit) and explicit not in roots:
            roots.append(explicit)
        return roots

    @staticmethod
    def _read_index(path):
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    @staticmethod
    def _write_index(path, data):
        try:
            _atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=1))
        except OSError:
            pass


# ── O EXECUTOR: prioridade BAIXA, cede pela MESMA fonte que `sample_load()` ───
def _default_level():
    """O nivel de carga agora, pela mesma fonte do shedding (`sample_load`)."""
    try:
        import load_shedding

        reading = load_shedding.sample_load()
        return load_shedding.level_for_load(reading.get('commit_pct'),
                                            reading.get('cpu_pct'))
    except Exception:                                            # noqa: BLE001
        # NAO SEI nao e' "leve": um executor que corre porque a medicao rebentou
        # e' o mesmo erro que desligar motores porque a medicao rebentou.
        return 'muito-alta'


def child_env(base=None, threads=None):
    """A env do filho: a do pai, com o TECTO DE FIOS escrito por cima.

    O filho e' um `python` que carrega o Parakeet: sem este tecto, o motor ONNX,
    o numpy e o torch abrem um fio por nucleo fisico, e um bloco sozinho usa a
    maquina toda durante segundos. O tecto e' declarado UMA vez
    (`BATCH_CHILD_THREADS`) e chega por dois caminhos coerentes: aqui na env (o
    que o motor ONNX le' sozinho) e no `--threads` que o driver passa ao
    `load_backend` (o que o torch `set_num_threads` le').
    """
    env = dict(os.environ if base is None else base)
    value = str(int(threads if threads is not None else BATCH_CHILD_THREADS))
    for key in THREAD_ENV_KEYS:
        env[key] = value
    return env


def _env_threads(default=None):
    """O tecto de fios que a ENV manda sobre a constante (`None` = a constante).

    Fail-open para a constante e nunca para 0: um valor invalido na env nao pode
    transformar o tecto em "sem limite" nem num filho sem fios.
    """
    fallback = int(BATCH_CHILD_THREADS if default is None else default)
    try:
        value = int(os.environ.get('OMP_NUM_THREADS') or fallback)
    except (TypeError, ValueError):
        return fallback
    return value if value > 0 else fallback


def _spawn_below_normal(cmd, env=None):
    """Arranca o filho com prioridade BAIXA e sem janela. Windows-safe.

    O PAR, NAO O BIT (medido 2026-11-04 no ecran do dono): `CREATE_NO_WINDOW`
    sozinho nao esconde a janela quando o pai nao tem consola, e este modulo
    corre dentro de `pythonw`. `no_console.popen_kwargs` traz o `startupinfo`
    com `SW_HIDE` que fecha o caso.

    `env=None` continua a ser o caminho de producao: a env sai de `child_env()`
    com o tecto de fios. Um chamador que ja' traga a sua env passa-a e e'
    respeitado (o `load-shedding-oracle` arranca um filho de teste assim).
    """
    from no_console import popen_kwargs
    extra = BELOW_NORMAL_PRIORITY_CLASS if os.name == 'nt' else 0
    if env is None:
        env = child_env()
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding='utf-8', errors='replace',
                            env=env, **popen_kwargs(extra))


class BatchExecutor(threading.Thread):
    """Transcreve a fila, um bloco por vez, e CEDE quando a carga sobe.

    A REGRA QUE NAO SE NEGOCEIA: nada corre com o nivel acima de `leve`. Cada
    volta do laco le' a carga; se o nivel subiu, o filho e' morto e o bloco
    volta a' fila com `retry_at` -- o audio nao se perde, o dono nao espera.
    """

    def __init__(self, queue=None, log_fn=None, level_fn=None, spawn=None,
                 python=None, window_s=15.0, poll_s=10.0, child_poll_s=3.0,
                 yield_backoff_s=30.0, adopt_every_s=60.0, session_root=None,
                 adopt_roots=None, budget=None):
        super().__init__(name='sotto-batch-executor', daemon=True)
        self.queue = queue or BatchQueue(log_fn=log_fn)
        self.log = log_fn or _noop
        self.level_fn = level_fn or _default_level
        # O ORCAMENTO DE CPU DO LACO (2026-11-08): a mesma lei da pintura da
        # legenda -- o periodo deriva do custo medido, `idle = custo *
        # (1 - orcamento) / orcamento`, e a taxa de servico converge para
        # `BATCH_CPU_BUDGET`. O filho leva o tecto de fios na env, para um bloco
        # sozinho nao poder estourar o orcamento por si.
        self.budget = float(BATCH_CPU_BUDGET if budget is None else budget)
        self.child_env = child_env()
        if spawn is not None:
            self._spawn = spawn
        else:
            self._spawn = lambda cmd: _spawn_below_normal(cmd, env=self.child_env)
        self.python = python or sys.executable
        self.window_s = float(window_s)
        self.poll_s = float(poll_s)
        self.child_poll_s = float(child_poll_s)
        self.yield_backoff_s = float(yield_backoff_s)
        self.adopt_every_s = float(adopt_every_s)
        self.session_root = session_root
        # O CAMPO QUE FALTAVA (2026-11-03, MEDIDO no log VIVO do dono, pid 4992).
        # `run()` chama `self.queue.adopt_dead_spools(self.adopt_roots)` e este
        # nome NUNCA era atribuido: `BATCH_EXEC_ERROR error=AttributeError(...'no
        # attribute 'adopt_roots'')` uma vez por minuto, desde o arranque. Duas
        # consequencias, ambas medidas: (1) a ADOPCAO dos spools que um worker
        # morto deixou NUNCA corria -- o audio que o dono gravou e o worker
        # largou nao era transcrito por ninguem; (2) a excepcao e' apanhada no
        # `try` do laco ANTES do `self.step()`, logo a volta em que ela cai
        # perde um passo inteiro da fila (uma por minuto).
        self.adopt_roots = adopt_roots
        # DE ONDE SE ADOPTAM OS SPOOLS MORTOS. `None` = todos os spools reais
        # (o comportamento de producao: o audio que um worker largou tem de ser
        # transcrito). Um INSTRUMENTO passa a raiz do seu proprio directorio
        # temporario, e entao mede o SEU trabalho e nao o spool de uma sessao
        # viva na mesma maquina -- medido: sem esta porta, o primeiro braco do
        # `batch-queue-drain-oracle` via `spawns=1` com a fila VAZIA, porque o
        # `_last_adopt` arranca em 0.0 e a primeira volta do laco adoptava o
        # spool real de `I:\cc-tmp`.
        # `_stop_event` e NAO `_stop`: `threading.Thread` tem um metodo `_stop()`
        # que o `join()` chama, e esta classe sombreava-o com um `Event` -- qualquer
        # `join()` num executor levantava `TypeError: 'Event' object is not
        # callable` (medido 2026-11-08 no oracle deste orcamento, no primeiro
        # `ex.join(5.0)`). O nome do evento nao e' contrato publico: `stop()` e'.
        self._stop_event = threading.Event()
        self._child = None
        self.runs = 0
        self.done = 0
        self.failed = 0
        self.yields = 0
        self._last_adopt = 0.0
        # O QUE O ORCAMENTO MEDIU: o custo dos blocos e a espera que ele impoe.
        # Ficam expostos no `as_dict()` para o limite ser medivel de fora (o log
        # diz os tres numeros; estes contadores sao a soma da corrida).
        self.last_cost_s = 0.0
        self.cost_s = 0.0
        self.idle_s = 0.0

    # -- a decisao --------------------------------------------------------
    def level(self):
        try:
            return str(self.level_fn() or 'leve')
        except Exception:                                        # noqa: BLE001
            return 'muito-alta'

    def allowed(self):
        """So' o nivel `leve` deixa o lote correr."""
        return self.level() == 'leve'

    def command_for(self, entries):
        """O filho: este MESMO ficheiro, em modo `--transcribe`, com N blocos.

        Um ficheiro que sabe ser os dois lados e' o que evita um runner novo no
        `worker/`: o driver le' o `float32` cru e transcreve com o Parakeet
        (ONNX int4), sem abrir dispositivo de audio e sem tocar no spool.

        Varios PAYLOADS num filho (2026-11-12): o driver carrega o motor UMA vez e
        decodifica todos os blocos que couberem em `MAX_BLOCKS_PER_CHILD`. Sem
        isto, cada bloco paga a leitura do mmap das pesos (~1,9 GB) -- medido no
        watcher como `io 162.4MB/s (40 ops/s, 4060 KB/op)`. O `--ids` viaja na
        mesma ordem dos payloads, para o resultado de cada bloco voltar ao `id`
        dele; sem `--ids` o driver numera pela ordem (`0,1,2...`).
        """
        entries = list(entries) if isinstance(entries, (list, tuple)) else [entries]
        rate = int(entries[0].get('rate') or RATE) if entries else RATE
        cmd = [self.python, os.path.abspath(__file__), '--transcribe']
        cmd += [self.queue.payload_path(str(e['id'])) for e in entries]
        cmd += ['--ids', ','.join(str(e['id']) for e in entries),
                '--rate', str(rate),
                '--window-s', str(self.window_s),
                '--json']
        return cmd

    # -- um bloco (ou um lote de blocos) ----------------------------------
    def step(self):
        """Corre os blocos que couberem em `MAX_BLOCKS_PER_CHILD`. Devolve
        `(estado, detalhe)`; `('idle', ...)` sem nada a fazer.

        Estados: `idle` (nada a fazer / carga alta), `yield` (cedeu), `done`,
        `failed`.

        PORQUE UM FILHO PARA VARIOS BLOCOS (medido 2026-11-12): o driver e' um
        processo por bloco e carrega o Parakeet inteiro antes de decodificar. Com a
        fila a ter varios blocos, cada um pagava ~1,9 GB de leitura do mmap das
        pesos -- a forma exacta que o watcher mediu no dono
        (`python.exe(53836) io 162.4MB/s 40 ops/s 4060 KB/op`). Agora uma carga
        serve ate' `MAX_BLOCKS_PER_CHILD` blocos, e o `yield` por carga alta
        continua a ter onde cortar (entre lotes, e no maximo oito blocos depois).
        """
        if not self.allowed():
            return ('idle', 'level=%s' % self.level())
        claimed = self._claim_batch()
        if claimed is None:
            return ('idle', 'claim-lost')
        if not claimed:
            return ('idle', 'queue-empty')
        started = time.monotonic()
        self.runs += 1
        child, failure = self._spawn_batch(claimed)
        if failure is not None:
            self._charge(started)
            return ('failed', failure)
        self._child = child
        try:
            outcome, out = self._wait_batch(child, claimed, started)
        finally:
            self._child = None
        if outcome is not None:                       # stop / yield / communicate
            self._charge(started)
            return outcome
        return self._settle_batch(claimed, child, out, self._charge(started))

    def _claim_batch(self):
        """Os blocos deste lote, ja' `inflight`. `None` = o claim perdeu a corrida."""
        entries = self.queue.next_entries(MAX_BLOCKS_PER_CHILD)
        claimed = []
        for entry in entries:
            got = self.queue.claim(str(entry['id']))
            if got is not None:
                claimed.append(entry)
        if entries and not claimed:
            return None
        return claimed

    def _spawn_batch(self, claimed):
        """`(child, None)` ou `(None, estado_de_falha)`. O erro e' nomeado por bloco."""
        first_id = str(claimed[0]['id'])
        try:
            return self._spawn(self.command_for(claimed)), None
        except Exception as exc:                                 # noqa: BLE001
            self.log(f'BATCH_EXEC_SPAWN_FAILED id={first_id} '
                     f'blocks={len(claimed)} error={exc!r}')
            for entry in claimed:
                self._after_failure(entry, 'spawn: %r' % (exc,))
            return None, 'spawn'

    def _wait_batch(self, child, claimed, started):
        """Espera o filho. `(None, stdout)` = ele acabou; senao `((estado, detalhe), '')`.

        O stdout SAI daqui porque e' o `communicate()` que o devolve -- depois dele
        o cano esta' fechado e `child.stdout` nao e' o contrato do `Popen` que se
        le (foi exactamente esse o `AttributeError` medido no oraculo do painel em
        2026-11-12).
        """
        first_id = str(claimed[0]['id'])
        while True:
            if self._stop_event.is_set():
                self._kill(child)
                self._requeue_batch(claimed, 'executor-stop')
                return ('yield', 'stop'), ''
            try:
                out, _err = child.communicate(timeout=self.child_poll_s)
                return None, out
            except subprocess.TimeoutExpired:
                if not self.allowed():
                    self._kill(child)
                    self.yields += 1
                    self.log(f'BATCH_EXEC_YIELDED id={first_id} '
                             f'blocks={len(claimed)} level={self.level()} '
                             f'elapsed_s={time.monotonic() - started:.1f} '
                             f'seconds_pending={claimed[0].get("seconds")} -- os '
                             f'blocos voltam a fila')
                    self._requeue_batch(claimed, 'load-%s' % self.level())
                    self._stop_event.wait(self.yield_backoff_s)
                    return ('yield', 'load'), ''
            except Exception as exc:                             # noqa: BLE001
                self._kill(child)
                for entry in claimed:
                    self._after_failure(entry, 'communicate: %r' % (exc,))
                return ('failed', 'communicate'), ''

    def _requeue_batch(self, claimed, reason):
        for entry in claimed:
            self.queue.requeue(str(entry['id']), reason, bump_attempts=False)

    def _settle_batch(self, claimed, child, out, elapsed):
        """Fecha a conta do lote: `done` por bloco cujo resultado VEIO."""
        code = getattr(child, 'returncode', None)
        per_id, _text, _captions = _parse_batch_output(out)
        if code != 0:
            detail = 'rc=%r' % (code,)
            for entry in claimed:
                self._after_failure(entry, detail)
            return ('failed', detail)
        done_text = []
        for entry in claimed:
            entry_id = str(entry['id'])
            got = per_id.get(entry_id)
            if got is None and len(claimed) == 1:
                # UM bloco so': o filho nao precisa de carimbar `id` (um driver
                # antigo nao conhece `--ids`) e o resultado sem `id` e' dele. Com
                # DOIS ou mais, o mesmo texto cairia em todos -- ai' a ausencia e'
                # defeito e o bloco NAO pode ser dado por transcrito.
                got = per_id.get('')
            if got is None:
                self._after_failure(entry, 'no-result')
                continue
            self.done += 1
            self.queue.mark_done(entry_id, text=got['text'], elapsed_s=elapsed,
                                 meta={'captions': got['captions']})
            self.log(f'BATCH_EXEC_DONE id={entry_id} seconds={entry.get("seconds")} '
                     f'elapsed_s={elapsed:.1f} captions={got["captions"]} '
                     f'chars={len(got["text"])} blocks={len(claimed)}')
            done_text.append(got['text'])
        return ('done', ' '.join(done_text))

    def _after_failure(self, entry, error):
        attempts = int(entry.get('attempts') or 0) + 1
        entry_id = str(entry['id'])
        if attempts >= MAX_ATTEMPTS:
            self.failed += 1
            self.queue.mark_failed(entry_id, error)
            self.log(f'BATCH_EXEC_FAILED id={entry_id} attempts={attempts} '
                     f'error={error[:300]!r} -- fica na fila como FAILED, com o erro')
            return
        self.queue.requeue(entry_id, error)
        self.log(f'BATCH_EXEC_RETRY id={entry_id} attempts={attempts} '
                 f'error={error[:300]!r}')

    def _kill(self, child):
        try:
            child.kill()
        except Exception:                                        # noqa: BLE001
            pass
        try:
            child.communicate(timeout=5)
        except Exception:                                        # noqa: BLE001
            pass

    def _charge(self, started):
        """Fecha a conta do bloco: o custo medido e' o que o orcamento usa.

        Chamado em TODOS os caminhos que devolvem `done`/`failed` (inclusive o
        `spawn` que rebenta e o `communicate` que erra): sem isso o `run()`
        esperava pelo custo do bloco ANTERIOR depois de uma falha, e uma fila de
        falhas punha o laco a dormir por trabalho que nao existiu.
        """
        cost = max(0.0, time.monotonic() - started)
        self.last_cost_s = cost
        self.cost_s += cost
        return cost

    def _pace(self, cost_s=None):
        """Dorme o que o ORCAMENTO manda antes do proximo bloco.

        A LEI (a mesma de `CAPTION_FRAME_BUDGET`, `caption_overlay.py`): com o
        laco a servir a taxa `b`, um bloco que custou `c` segundos tem de ser
        seguido de `c * (1 - b) / b` de espera. Sem isto o periodo e' o custo --
        um laco que dorme o tempo que trabalha gasta 100 % de um nucleo por
        construcao, e foi exactamente esse o defeito que aquele orcamento curou.

        `self._stop_event.wait` e nao `time.sleep`: um stop corta a espera e o fio
        termina sem deixar nada atras (e sem filho em voo -- aqui nao ha' filho).
        """
        cost = float(self.last_cost_s if cost_s is None else cost_s)
        budget = float(self.budget)
        if cost <= 0.0 or budget <= 0.0 or budget >= 1.0:
            return 0.0
        idle = cost * (1.0 - budget) / budget
        self.idle_s += idle
        self.log('BATCH_CPU_BUDGET used_ms=%.0f budget=%.2f rate=%.2f '
                 'idle_ms=%.0f' % (cost * 1000.0, budget,
                                   cost / (cost + idle), idle * 1000.0))
        self._stop_event.wait(idle)
        return idle

    # -- o laco -----------------------------------------------------------
    def run(self):
        while not self._stop_event.is_set():
            try:
                now = time.monotonic()
                if now - self._last_adopt >= self.adopt_every_s:
                    self._last_adopt = now
                    self.queue.adopt_dead_spools(self.adopt_roots)
                state, detail = self.step()
            except Exception as exc:                             # noqa: BLE001
                self.log(f'BATCH_EXEC_ERROR error={exc!r}')
                state = 'idle'
            # O ORCAMENTO MANDA ENTRE BLOCOS: o custo medido do bloco que
            # acabou de sair e' o periodo que o proximo vai ter de esperar.
            if state in ('done', 'failed'):
                self._pace()
            if state == 'yield':
                continue
            if state == 'idle':
                # O DIRECTORIO E' A FILA, E A FILA CRESCE POR FORA.
                #
                # MEDIDO (2026-11-03, instancia viva pid 41760): um bloco
                # enfileirado por OUTRO processo (manifesto + `.f32` no MESMO
                # directorio) ficou `queued` para sempre com `level=leve` e
                # `poll_s=10` -- o `refresh()` so' corria no `__init__`, portanto o
                # executor comparava um retrato tirado no arranque com uma pasta
                # que ja' tinha mudado. Um bloco que ninguem ve' e' audio perdido,
                # e o audio perdido e' exactamente o que o spool do worker larga
                # quando larga o modelo: a accao do shedding ficava provada e a
                # promessa ("o audio nao processado e' processado sozinho") nao.
                #
                # A RELEITURA SO' ACONTECE AQUI, com NENHUM filho em voo: o
                # `refresh()` devolve `inflight` a `queued` (recuperacao de crash),
                # e faze-lo entre o `claim()` e o fim do filho punha o mesmo bloco
                # a correr duas vezes.
                self._refresh_queue()
                self._stop_event.wait(self.poll_s)

    def _refresh_queue(self):
        """Rele' o directorio quando nao ha' nada em voo, e so' diz quando mudou."""
        try:
            before = len(self.queue.pending())
            self.queue.refresh()
            after = len(self.queue.pending())
        except Exception as exc:                                 # noqa: BLE001
            self.log(f'BATCH_QUEUE_REFRESH_FAILED error={exc!r}')
            return
        if after != before:
            self.log(f'BATCH_QUEUE_REFRESH pending={before}->{after} '
                     f'dir={self.queue.path}')

    def stop(self):
        self._stop_event.set()
        child = self._child
        if child is not None:
            self._kill(child)

    def as_dict(self):
        spent = float(self.cost_s) + float(self.idle_s)
        duty = (float(self.cost_s) / spent) if spent > 0 else 0.0
        return {'runs': self.runs, 'done': self.done, 'failed': self.failed,
                'yields': self.yields, 'level': self.level(),
                'budget': self.budget, 'duty': round(duty, 3),
                'queue': self.queue.stats()}


def _parse_output(stdout):
    """`(texto, linhas)` das linhas JSON que o driver escreveu.

    O driver emite `{"type":"caption",...}` por linha fechada e um
    `{"type":"result","text":...}` no fim; o texto do `result` e' a uniao das
    linhas, sem repetir a mesma frase duas vezes.
    """
    captions = []
    text = ''
    for raw in (stdout or '').splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get('type') == 'caption':
            line = str(payload.get('text') or '').strip()
            if line:
                captions.append(line)
        elif payload.get('type') == 'result':
            text = str(payload.get('text') or '').strip()
    if not text:
        text = ' '.join(captions).strip()
    return text, len(captions)


def _parse_batch_output(stdout):
    """`(por_id, texto_unico, n_legendas)` das linhas JSON de um filho com N blocos.

    O driver com `--ids` carimba `id` em cada `caption`/`result`, e um filho de um
    bloco so' continua a emitir o mesmo JSON sem `id` -- por isso a ausencia de
    `id` cai num balde proprio (`''`), que o executor so' le' quando pediu UM
    bloco. Assim o contrato antigo nao quebra e o novo e' estritamente aditivo.
    """
    per_id = {}
    order = []
    for raw in (stdout or '').splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(payload, dict):
            continue
        kind = payload.get('type')
        if kind not in ('caption', 'result'):
            continue
        bucket_id = str(payload.get('id') or '')
        bucket = per_id.get(bucket_id)
        if bucket is None:
            bucket = per_id[bucket_id] = {'text': '', 'captions': 0, 'lines': []}
            order.append(bucket_id)
        if kind == 'caption':
            line = str(payload.get('text') or '').strip()
            if line:
                bucket['lines'].append(line)
                bucket['captions'] += 1
        else:
            bucket['text'] = str(payload.get('text') or '').strip()
    for bucket in per_id.values():
        if not bucket['text']:
            bucket['text'] = ' '.join(bucket['lines']).strip()
        bucket.pop('lines', None)
    if len(order) == 1:
        only = per_id[order[0]]
        return per_id, only['text'], only['captions']
    return per_id, '', sum(b['captions'] for b in per_id.values())


# ── O DRIVER: `--transcribe` -- um ficheiro, sem dispositivo, e sai ──────────
def _worker_path(*parts):
    return os.path.join(WORKER_DIR, *parts)


def load_engine(threads=None, onnx_dir=None, ternary_dir=None):
    """Carrega o backend do Parakeet UMA vez. Devolve `(backend, threads)`.

    Existe para o modo com varios blocos: a carga do motor e' ~1,9 GB de leitura e
    o unico jeito de a pagar uma vez por LOTE (e nao por bloco) e' carregar aqui e
    passar o backend a cada payload. Um payload sozinho continua a poder chamar
    `transcribe_payload` sem engine, que carrega por dentro.
    """
    if threads is None:
        threads = _env_threads()
    threads = int(threads or BATCH_CHILD_THREADS)
    if WORKER_DIR not in sys.path:
        sys.path.insert(0, WORKER_DIR)
    import redux_live

    onnx_dir = onnx_dir or redux_live.DEFAULT_ONNX_DIR
    ternary_dir = ternary_dir or redux_live.DEFAULT_TERNARY_DIR
    backend = redux_live.load_backend('onnx', onnx_dir, ternary_dir, threads, 'cuda')
    return backend, threads


def transcribe_payload(path, rate=RATE, window_s=15.0, gap_s=0.6,
                       threads=None, onnx_dir=None, ternary_dir=None,
                       engine=None, entry_id=None):
    """Transcreve um `float32` cru e devolve `[(start, end, texto), ...]`.

    REUSA o que ja' existe, e nao um motor paralelo: `worker/redux_live.py` tem
    o backend ONNX int4 do Parakeet (`load_backend`) e o segmentador que define
    o contrato da legenda (`LiveSegmenter`). Este driver so' troca a FONTE de
    audio (um ficheiro em vez de um dispositivo) e o RELOGIO (tudo o que a CPU
    der, em vez do ritmo de tempo real do `FileTap`), porque um lote que espera
    pelo relogio de um tap de ficheiro leva 10 minutos reais para 10 minutos de
    audio -- e o dono pediu que o resto do audio fosse processado, nao que a
    maquina ficasse ocupada o mesmo tempo que o audio durou.
    """
    import numpy as np

    # O TECTO DE FIOS DO FILHO, lido da env que o executor escreveu
    # (`child_env`): o motor ONNX le' `OMP_NUM_THREADS` sozinho, mas o
    # `torch.set_num_threads` do backend so' obedece ao argumento -- por isso o
    # MESMO numero viaja nos dois caminhos e nao ha' um deles a abrir os fios
    # todos. `--threads` continua a poder-mandar sobre a env.
    if WORKER_DIR not in sys.path:
        sys.path.insert(0, WORKER_DIR)
    import redux_live

    if engine is None:
        engine, threads = load_engine(threads, onnx_dir, ternary_dir)
    backend = engine
    seg = redux_live.LiveSegmenter(window_s=float(window_s), gap_s=float(gap_s),
                                   vad=True)
    pcm = np.fromfile(path, dtype='<f4')
    step = max(1, int(float(window_s) * rate))
    lines = []
    index = 0
    while index < pcm.size:
        chunk = np.ascontiguousarray(pcm[index:index + step], dtype=np.float32)
        index += chunk.size
        if chunk.size == 0:
            break
        seg.feed(chunk)
        if not seg.should_decode():
            continue
        joined = np.concatenate(seg.seg) if len(seg.seg) > 1 else seg.seg[0]
        try:
            text, _segments = backend.transcribe(joined)
        except Exception as exc:                                 # noqa: BLE001
            print(json.dumps({'type': 'error', 'stage': 'decode',
                              'detail': '%s: %s' % (type(exc).__name__, exc)},
                             ensure_ascii=False), flush=True)
            continue
        text = str(text or '').strip()
        if text:
            seg.last_text = text
        seg.close(text)
        for event in seg.drain():
            if not event.get('final'):
                continue
            line = {'type': 'caption', 'text': event['text'],
                    'start': event['start'], 'end': event['end'],
                    'producer': 'redux', 'route': 'batch-queue',
                    'final': True}
            if entry_id is not None:
                line['id'] = entry_id
            lines.append(line)
            print(json.dumps(line, ensure_ascii=False), flush=True)
    result = {'type': 'result', 'text': ' '.join(line['text'] for line in lines),
              'segments': len(lines), 'rate': rate,
              'samples': int(pcm.size), 'path': os.path.abspath(path)}
    if entry_id is not None:
        result['id'] = entry_id
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return lines


def open_executor(queue=None, log_fn=None, **kwargs):
    """Arranca o executor. Uma chamada, e a shell nao sabe mais nada disto."""
    executor = BatchExecutor(queue=queue, log_fn=log_fn, **kwargs)
    executor.start()
    if log_fn is not None:
        log_fn('BATCH_QUEUE_STARTED dir=%s poll_s=%.0f priority=below-normal'
               % (executor.queue.path, executor.poll_s))
    return executor


def main(argv=None):
    import argparse

    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        prog='batch_queue',
        description='Fila em disco do audio sem transcricao, e o driver de um '
                    'bloco (Parakeet batch, sem dispositivo de audio).')
    parser.add_argument('--transcribe', metavar='PAYLOAD', nargs='+', default=None,
                        help='transcreve um ou mais float32 crus e sai (modo do '
                             'executor); o motor e\' carregado UMA vez para todos')
    parser.add_argument('--ids', default='',
                        help='ids dos blocos, na mesma ordem dos PAYLOADs; cada '
                             'linha JSON leva o seu `id` de volta')
    parser.add_argument('--rate', type=int, default=RATE)
    parser.add_argument('--window-s', type=float, default=15.0)
    parser.add_argument('--gap-s', type=float, default=0.6)
    parser.add_argument('--threads', type=int, default=None,
                        help='tecto de fios do motor (env OMP_NUM_THREADS, '
                             'senao BATCH_CHILD_THREADS)')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    if args.transcribe:
        payloads = list(args.transcribe)
        ids = [i for i in str(args.ids or '').split(',') if i] or []
        try:
            engine, _threads = load_engine(args.threads)
        except SystemExit as exc:
            print(json.dumps({'type': 'error', 'stage': 'load', 'detail': str(exc)}),
                  flush=True)
            return 2
        rc = 0
        for index, payload in enumerate(payloads):
            entry_id = ids[index] if index < len(ids) else (
                str(index) if len(payloads) > 1 else None)
            try:
                transcribe_payload(payload, rate=args.rate,
                                   window_s=args.window_s, gap_s=args.gap_s,
                                   threads=args.threads, engine=engine,
                                   entry_id=entry_id)
            except Exception as exc:                             # noqa: BLE001
                # UM bloco que estoura NAO derruba os outros: o resultado dele e' uma
                # linha de erro com o `id`, e o filho segue. Sem isto um payload
                # corrompido mataria a transcricao dos oito blocos do lote.
                print(json.dumps({'type': 'error', 'stage': 'decode',
                                  'id': entry_id, 'detail': '%s: %s' % (type(exc).__name__, exc)},
                                 ensure_ascii=False), flush=True)
                rc = 1
        return rc
    queue = BatchQueue()
    print(json.dumps({'dir': queue.path, 'stats': queue.stats()},
                     ensure_ascii=False), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
