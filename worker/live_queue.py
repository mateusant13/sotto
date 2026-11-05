"""A FILA DE AUDIO VIVO, e a ESPERA do audio que nenhum motor leu.

Duas coisas vivem aqui, e elas respondem a perguntas OPOSTAS:

  * `enqueue_live` -- a fila do AO VIVO. Tem um tecto em segundos e, quando ele
    passa, sai o bloco mais VELHO: uma legenda que reproduz o passado e' pior do
    que uma legenda que perdeu um instante.
  * `PendingAudio` -- a ESPERA, o audio capturado enquanto NENHUM motor esta'
    carregado (painel fechado, carga alta, ou os dois). Aqui a regra e' a
    inversa da fila viva: NADA se deita fora. O audio transborda da RAM para o
    disco, na ordem em que chegou, e o motor de fundo (o parakeet) le'-o todo
    quando a carga o permitir. Ver ADIANTE.

ORDEM DO DONO (2026-11-01), verbatim:
    "modelos carregados dependendo da carga do sistema ou nao. quando carga
     liberar, carrega sozinho (NUNCA TRAVAR O PC DO USUARIO OU STUTTER OU
     QUALQUER COISA DESSA NATUREZA) e processa qualquer audio nao processado,
     com o parakeet."

A FILA DE AUDIO VIVO: o bloco mais NOVO entra, o mais VELHO sai.

O DONO, 2026-10-30, verbatim:
    *"eu tenho audio tocando, com pessoa falando, e eu to vendo legenda LIGANDO
    dezenas de segundos depois. encontra a porra do gargalo e arruma. se um audio
    tem fala, e pra ter transcricao NA HORA. ACABOU. E' REGRA. LEI. COM PROVA."*

O DEFEITO, por leitura (`worker/sotto_worker.py`, corrigido 2026-10-30): a
`audio_q` nasce com `maxsize=256` -- a 100 ms por bloco sao **25,6 s de audio** --
e o overflow fazia `except queue.Full: counters["queue_drops"] += 1`, deitando
fora o bloco RECEM-CAPTURADO. O pior dos dois mundos: perdia-se o audio do
instante E ficavam na fila os 25,6 s mais antigos, que o consumidor ia
transcrever em ordem, um a um. Uma fila assim nao atrasa a legenda por acaso:
ela E o atraso.

A REGRA. A fila tem um tecto em SEGUNDOS (`LIVE_QUEUE_MAX_S`), nao em numero de
blocos, porque 256 blocos significa coisas diferentes em cada taxa de captura.
Quando ela passa do tecto, o bloco mais ANTIGO sai para entrar o novo: o audio
que chega agora vale mais do que o audio de ha dois segundos, e uma legenda que
reproduz o passado e' pior do que uma legenda que perdeu um instante -- o
instante perdido o dono nem sabe que existiu.

Nada aqui abre dispositivo, janela ou modelo: e' fila, e por isso e' medida por
oraculo sem tocar na app.
"""
from __future__ import annotations

import os
import threading

#: O teto de audio vivo na fila, em segundos.
LIVE_QUEUE_MAX_S = 2.0

#: A RAM que a ESPERA (`PendingAudio`) pode ocupar antes de o bloco mais ANTIGO
#: ir para o disco, em segundos de audio. NAO e' um tecto de perda: e' onde o
#: spool comeca. 120 s a 16 kHz float32 sao 7,7 MB de RAM.
PENDING_RAM_S = 120.0

#: Abaixo disto o spool DIZ que o disco esta' a acabar. E' um aviso e nao uma
#: politica: o audio continua a ir para o disco, porque deitar audio fora nao e'
#: uma accao que este modulo tenha (ver `PendingAudio`).
SPOOL_LOW_DISK_BYTES = 1024 ** 3


def max_blocks(block_ms, cap_s=LIVE_QUEUE_MAX_S):
    """Quantos blocos cabem em `cap_s` segundos."""
    try:
        ms = int(block_ms)
    except (TypeError, ValueError):
        ms = 100
    return max(2, int(float(cap_s) * 1000.0 / max(1, ms)))


def enqueue_live(q, block, cap):
    """Enfileira o bloco mais NOVO; se a fila estiver cheia, deita fora o VELHO.

    `cap` e' o numero maximo de blocos (ver `max_blocks`). Uma fila com
    `maxsize=0` (ilimitada) e' tratada como sem tecto de blocos, mas o tecto em
    segundos continua a valer: o chamador passa `cap` de qualquer forma.

    Devolve `(evicted, dropped)` para o chamador contar o que aconteceu:
    `evicted` = blocos VELHOS que sairam para o novo entrar; `dropped` = o novo
    nao entrou (corrida com o consumidor, fila fechada).
    """
    evicted = 0
    dropped = 0
    try:
        while q.qsize() >= max(1, int(cap)):
            try:
                q.get_nowait()
                evicted += 1
            except Exception:  # noqa: BLE001 -- fila esvaziada por outro lado
                break
        q.put_nowait(block)
    except Exception:  # noqa: BLE001 -- corrida com o consumidor nao pode matar o tap
        dropped += 1
    return evicted, dropped


# ── A ESPERA: o audio que nenhum motor leu ───────────────────────────────────
#: O padrao dos ficheiros que `PendingAudio` escreve. O varrimento so' toca
#: nestes: um directorio de spool que o dono aponte para outro sitio nao pode
#: ser limpo as cegas.
SPOOL_GLOB = "pending-*.f32"

#: O nome do DIRECTORIO de spool. Leva o pid (`engine_policy.probe_and_spool`),
#: e e' o pid que diz se o irmao ainda pode estar a escrever.
SPOOL_DIR_PREFIX = "sotto-pending-audio-"


def _pid_alive(pid):
    """`True` quando o pid EXISTE e ainda corre. Incerto conta como VIVO."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return True
    if pid <= 0:
        return True
    if os.name == "nt":
        try:
            import ctypes

            k32 = ctypes.windll.kernel32
            handle = k32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
            if not handle:
                return False
            try:
                code = ctypes.c_ulong(0)
                if k32.GetExitCodeProcess(handle, ctypes.byref(code)):
                    return int(code.value) == 259  # STILL_ACTIVE
                return True
            finally:
                k32.CloseHandle(handle)
        except Exception:  # noqa: BLE001 -- sem resposta do SO, nao se apaga nada
            return True
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def sweep_sibling_spools(spool_dir, keep_pid=None, log=None, alive=None):
    """Remove os DIRECTORIOS de spool de processos que ja' nao existem.

    O DEFEITO QUE ISTO FECHA (medido 2026-11-05). `probe_and_spool` da' a cada
    worker um directorio proprio, `sotto-pending-audio-<pid>`, e a limpeza de
    arranque (`sweep_spool_dir`) varre os FICHEIROS DE DENTRO do directorio que
    recebe. Como cada run cria o seu, a limpeza olhava sempre para o directorio
    que ela propria acabara de criar: nunca via o audio dos runs anteriores.
    Medido nesta maquina: cinco irmaos orfaos em `G:/Temp`
    (pids 22156, 40636, 55348, 62016, 64764), ~52 MB, nenhum dos pids vivo,
    numa maquina onde `I:` esta' a 0,4 % -- e o dono conta disco desperdicado
    como inadmissivel.

    A REGRA e' a MESMA de `sweep_spool_dir` e nao uma nova: um spool de um
    processo que ja' nao existe e' audio de uma sessao sem painel, sem relogio
    de audio e sem consumidor. Nunca se apaga o `keep_pid` (o nosso) nem o de
    um pid VIVO. `alive` existe para o oraculo conduzir isto com uma tabela em
    vez de criar processos.
    """
    import glob
    import shutil

    dirs = 0
    files = 0
    freed = 0
    here = os.path.normpath(spool_dir)
    if not here:
        return dirs, files, freed
    keep = None if keep_pid is None else int(keep_pid)
    is_alive = alive or _pid_alive
    for path in glob.glob(os.path.join(os.path.dirname(here), SPOOL_DIR_PREFIX + "*")):
        pid = _spool_pid(path)
        if pid is None or pid == keep or is_alive(pid):
            continue
        count, size = _dir_usage(path)
        shutil.rmtree(path, ignore_errors=True)
        if os.path.exists(path):
            continue
        dirs += 1
        files += count
        freed += size
    if dirs and log is not None:
        log(f"AUDIO_PENDING_STALE_DIRS_REMOVED parent={os.path.dirname(here)} "
            f"dirs={dirs} files={files} mb={freed / 1048576.0:.1f} — spools de "
            f"pids que ja' nao existem; nenhum ficheiro de um pid vivo foi tocado")
    return dirs, files, freed


def _spool_pid(path):
    """O pid que o NOME de um directorio de spool declara, ou None."""
    name = os.path.basename(os.path.normpath(path))
    if not name.startswith(SPOOL_DIR_PREFIX) or not os.path.isdir(path):
        return None
    try:
        return int(name[len(SPOOL_DIR_PREFIX):])
    except (TypeError, ValueError):
        return None


def _dir_usage(path):
    """`(ficheiros, bytes)` de uma arvore -- o que um `rmtree` vai libertar."""
    count = 0
    size = 0
    for root, _subdirs, names in os.walk(path):
        for fname in names:
            try:
                size += os.path.getsize(os.path.join(root, fname))
                count += 1
            except OSError:
                continue
    return count, size


def sweep_spool_dir(path, log=None, keep_pid=None):
    """Limpa o spool de runs ANTERIORES. Devolve `(ficheiros, bytes)`.

    PORQUE E' QUE ISTO E' CERTO E NAO UMA PERDA DE AUDIO. Um ficheiro que fica
    no spool e' audio de um processo que ja' nao existe: nao ha' painel para o
    mostrar, nem relogio de audio para lhe dar `start`/`end` honestos, nem
    consumidor para a legenda. Transcreve-lo agora punha frases da sessao de
    ontem a entrar na legenda de hoje, com tempos inventados -- pior do que nao
    o ler. Fica dito no log, com o tamanho, para o disco nao crescer em silencio.

    `keep_pid` protege os ficheiros de um processo VIVO que partilhe o
    directorio (o nome leva o pid, ver `PendingAudio._path_locked`).
    """
    import glob

    removed = 0
    freed = 0
    if not path:
        return removed, freed
    for name in glob.glob(os.path.join(path, SPOOL_GLOB)):
        if keep_pid is not None and ("-%d-" % int(keep_pid)) in os.path.basename(name):
            continue
        try:
            size = os.path.getsize(name)
            os.remove(name)
        except OSError:
            continue
        removed += 1
        freed += size
    if removed and log is not None:
        log(f"AUDIO_PENDING_STALE_CLEANED dir={path} files={removed} "
            f"mb={freed / 1048576.0:.1f} — audio de uma sessao anterior, sem "
            f"painel e sem relogio de audio; o desta sessao e' que e' transcrito")
    return removed, freed


class PendingAudio:
    """Audio capturado enquanto NADA esta' carregado: ORDENADO, EXACTO, sem perdas.

    O DEFEITO QUE ISTO SUBSTITUI, medido em `worker/sotto_worker.py`
    (`ReduxHiddenSwitch.add_audio`, revisao 38ab1d6): a espera era uma lista em
    RAM limitada a `--redux-max-audio` (120 s por omissao) e, quando passava do
    tecto, o bloco mais ANTIGO saia com um `REDUX_BUFFER_TRIMMED` no log:

        while self._pending_samples > limit and len(self._pending) > 1:
            dropped = self._pending.pop(0)          # AUDIO PERDIDO

    Numa maquina a 92 % de commit durante uma hora, isso e' 58 minutos de audio a
    desaparecer sem que o dono saiba que existiram. A ordem do dono nao deixa
    margem: *"processa qualquer audio nao processado, com o parakeet"* — nao ha'
    audio "nao processado" que se possa processar depois de o deitar fora.

    A REGRA, em tres partes:

      1. ORDEM. Sai na ordem em que entrou. Uma transcricao fora de ordem nao e'
         um atraso: e' outra frase. O spool guarda o deslocamento de cada bloco no
         ficheiro, por isso a ordem e' a da chegada e nao a de um `glob`.
      2. EXACTIDAO. O bloco e' escrito tal como chegou (`float32` cru), sem
         quantizar e sem cortar a cauda de um bloco a meio: o que o motor de fundo
         le' e' o que o tap entregou.
      3. NENHUMA PERDA. Nao ha' caminho que deite um bloco fora. Se o disco nao
         aceitar (cheio, sem permissao), o bloco FICA na RAM e a falha e' contada
         e dita; se a RAM passar do tecto e nao houver disco, ela cresce em vez de
         perder audio. `dropped` existe para o oraculo poder exigir que fique 0 e
         para o log poder dizer "0" em vez de o prometer.

    OS TECTOS, ditos por inteiro (o oraculo mede os dois):
      * RAM: `ram_s` segundos (por omissao `PENDING_RAM_S` = 120 s = 7,7 MB).
        NAO e' um limite de retencao; e' onde o spool comeca.
      * DISCO: nenhum limite proprio. `SPOOL_LOW_DISK_BYTES` e' um AVISO (uma
        linha por cada 100 blocos) e nao uma politica. O audio apaga-se quando e'
        entregue (`take_all`), que e' o contrato do `audio_recorder`: o texto fica,
        o audio era o meio.
    """

    def __init__(self, rate=16000, ram_s=PENDING_RAM_S, spool_dir=None,
                 log=None, dtype="<f4", sweep_stale=True):
        self.rate = int(rate) or 16000
        self.ram_s = max(0.0, float(ram_s))
        self.spool_dir = spool_dir
        self.log = log or (lambda _msg: None)
        self._dtype = dtype
        self._lock = threading.Lock()
        self._ram = []            # blocos ainda em RAM, por chegar o mais novo
        self._ram_samples = 0
        self._entries = []        # (path, offset, nbytes, samples), o mais antigo primeiro
        self._paths = []          # ficheiros do spool, o mais antigo primeiro
        self._files = 0
        self.blocks_in = 0
        self.blocks_out = 0
        self.blocks_spilled = 0
        self.bytes_spilled = 0
        self.write_failures = 0
        self.low_disk_warned = 0
        #: SEM CAMINHO DE CODIGO QUE O AUMENTE, de proposito: um bloco que entra
        #: e' um bloco que sai (ver `take_all`). O oraculo exige 0 e o log diz 0.
        self.dropped = 0
        #: UM RUN ANTERIOR DEIXA FICHEIROS AQUI. Sao audio de uma sessao que ja'
        #: nao existe (sem painel, sem consumidor, sem relogio de audio para dar
        #: `start`/`end` honestos), por isso limpam-se AGORA e a limpeza e' dita
        #: no log com o tamanho. Os ficheiros de um processo VIVO ficam: o nome
        #: leva o pid (`_path_locked`).
        self.stale_files, self.stale_bytes = (0, 0)
        if sweep_stale and spool_dir:
            self.stale_files, self.stale_bytes = sweep_spool_dir(
                spool_dir, log=self.log, keep_pid=os.getpid())

    # -- entrada ---------------------------------------------------------
    def add(self, block):
        """Um bloco entra. Nunca levanta, nunca o deita fora. Devolve o que fez."""
        if block is None:
            return False
        try:
            samples = int(getattr(block, "size", 0))
        except Exception:  # noqa: BLE001 -- um objecto estranho nao pode matar o tap
            samples = 0
        if samples <= 0:
            return False
        spilled = 0
        with self._lock:
            self._ram.append(block)
            self._ram_samples += samples
            self.blocks_in += 1
            limit = int(self.ram_s * self.rate)
            while self._ram_samples > limit and len(self._ram) > 1:
                head = self._ram[0]
                if not self._spill_locked(head):
                    # O disco nao aceitou: o bloco FICA em RAM. Haver memoria a
                    # mais e' um problema que se ve'; audio perdido nao.
                    break
                self._ram.pop(0)
                self._ram_samples -= int(getattr(head, "size", 0))
                spilled += 1
            total = self.blocks_spilled
        if spilled:
            # RATE-LIMITED: 3 linhas e depois uma a cada 60 s de audio (600
            # blocos), porque este caminho corre a 10 Hz.
            if total <= 3 or total % 600 == 0:
                self.log(
                    f"AUDIO_PENDING_SPILLED blocks_spilled={total} "
                    f"bytes={self.bytes_spilled} ram_s={self.ram_s} "
                    f"dropped={self.dropped}"
                )
        return True

    def _spill_locked(self, block):
        """Escreve UM bloco no fim do ficheiro do spool. `False` = nao escreveu."""
        try:
            raw = block.astype(self._dtype, copy=False).tobytes()
        except Exception as exc:  # noqa: BLE001
            self.write_failures += 1
            self.log(f"AUDIO_PENDING_ENCODE_FAILED {type(exc).__name__}: {exc}")
            return False
        if not raw:
            return False
        path = self._path_locked()
        if path is None:
            return False
        try:
            with open(path, "ab") as fh:
                offset = fh.tell()
                fh.write(raw)
                fh.flush()
        except Exception as exc:  # noqa: BLE001
            self.write_failures += 1
            self.log(
                f"AUDIO_PENDING_WRITE_FAILED {type(exc).__name__}: {exc} "
                f"path={path} — o bloco FICA em RAM; audio nao se deita fora"
            )
            return False
        self._entries.append((path, offset, len(raw), int(getattr(block, "size", 0))))
        self.blocks_spilled += 1
        self.bytes_spilled += len(raw)
        return True

    def _path_locked(self):
        """O ficheiro do spool em uso (ou None quando nao ha' onde escrever)."""
        if self._paths:
            return self._paths[-1]
        if not self.spool_dir:
            return None
        try:
            os.makedirs(self.spool_dir, exist_ok=True)
        except OSError as exc:
            self.write_failures += 1
            self.log(f"AUDIO_PENDING_SPOOL_DIR_FAILED {exc} dir={self.spool_dir}")
            return None
        try:
            free = _free_bytes(self.spool_dir)
        except Exception:  # noqa: BLE001 -- medir o disco nao e' o trabalho
            free = None
        if free is not None and free < SPOOL_LOW_DISK_BYTES:
            self.low_disk_warned += 1
            if self.low_disk_warned <= 3 or self.low_disk_warned % 100 == 0:
                self.log(
                    f"AUDIO_PENDING_LOW_DISK free_mb={free / 1048576.0:.0f} "
                    f"floor_mb={SPOOL_LOW_DISK_BYTES // 1048576} "
                    f"warnings={self.low_disk_warned} — o audio continua a ir para o "
                    f"disco: deitar audio fora nao e' uma accao deste modulo"
                )
        self._files += 1
        path = os.path.join(self.spool_dir, "pending-%d-%04d.f32"
                            % (os.getpid(), self._files))
        self._paths.append(path)
        return path

    # -- leitura ---------------------------------------------------------
    def seconds(self):
        """Quanto audio esta' a espera, em segundos (RAM + disco)."""
        with self._lock:
            return round(self._samples_locked() / float(self.rate), 3)

    def blocks(self):
        with self._lock:
            return len(self._entries) + len(self._ram)

    def _samples_locked(self):
        return self._ram_samples + sum(entry[3] for entry in self._entries)

    def take_all(self):
        """TUDO, na ordem de chegada. Esvazia a espera e apaga o spool.

        Devolve `(blocos, amostras)`, com a MESMA forma do antigo
        `take_pending()` do worker, para o chamador nao ter duas formas de espera.

        Os ficheiros sao APAGADOS no fim: o audio foi entregue a quem o vai
        transcrever, e o que fica e' o texto (a regra do `audio_recorder`). Um
        spool que ficasse no disco depois de lido seria disco desperdicado.
        """
        import numpy as np

        held = []
        with self._lock:
            entries, self._entries = self._entries, []
            paths, self._paths = self._paths, []
            ram, self._ram = self._ram, []
            self._ram_samples = 0
            samples = 0
            handles = {}
            try:
                for (_path, offset, nbytes, nsamples) in entries:
                    fh = handles.get(_path)
                    if fh is None:
                        fh = handles[_path] = open(_path, "rb")
                    fh.seek(offset)
                    raw = fh.read(nbytes)
                    if len(raw) != nbytes:
                        raise OSError("short read from %s: %d/%d" % (_path, len(raw), nbytes))
                    held.append(np.frombuffer(raw, dtype=self._dtype).copy())
                    samples += nsamples
            finally:
                for fh in handles.values():
                    try:
                        fh.close()
                    except OSError:
                        pass
            held.extend(ram)
            for block in ram:
                samples += int(getattr(block, "size", 0))
            self.blocks_out += len(held)
        for path in paths:
            try:
                os.remove(path)
            except OSError:
                pass
        if self.spool_dir:
            try:
                os.rmdir(self.spool_dir)
            except OSError:
                pass
        return held, samples

    def requeue(self, blocks):
        """Devolve a espera o que foi tirado e NAO chegou a ser transcrito.

        Acontece no caminho do `flush_pending` quando o audio tirado e' menor do
        que o minimo que justifica acordar o modelo: os blocos voltam para a
        FRENTE e o contador de saida recua, para `blocks_in == blocks_out` medir
        o que foi realmente entregue.
        """
        kept = []
        for block in blocks or ():
            try:
                if block is not None and int(getattr(block, "size", 0)) > 0:
                    kept.append(block)
            except Exception:  # noqa: BLE001
                continue
        if not kept:
            return 0
        with self._lock:
            self._ram = kept + self._ram
            self._ram_samples += sum(int(getattr(b, "size", 0)) for b in kept)
            self.blocks_out = max(0, self.blocks_out - len(kept))
        return len(kept)

    # -- o que se publica -------------------------------------------------
    def counts(self):
        """Os numeros que o `done`/`WORKER_STATS` publicam e o oraculo exige."""
        with self._lock:
            return {
                "blocks_in": self.blocks_in,
                "blocks_out": self.blocks_out,
                "held_blocks": len(self._entries) + len(self._ram),
                "spilled_blocks": self.blocks_spilled,
                "spilled_bytes": self.bytes_spilled,
                "write_failures": self.write_failures,
                "dropped": self.dropped,
                "seconds": round(self._samples_locked() / float(self.rate), 3),
            }


def _free_bytes(path):
    """Espaco livre no volume de `path`, ou None quando nao se sabe.

    `None` NAO e' "sem espaco": e' "nao medi", e uma medicao falhada nao e'
    evidencia de pressao (a mesma regra do `_free_memory_mb` do worker).
    """
    try:
        import shutil

        return int(shutil.disk_usage(path).free)
    except Exception:  # noqa: BLE001
        return None
