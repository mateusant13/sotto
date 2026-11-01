"""A POLITICA DOS MOTORES e da CARGA, fora do `sotto_worker.py`.

O DONO (2026-11-01), verbatim:
    *"modelos carregados dependendo da carga do sistema ou nao. quando carga
    liberar, carrega sozinho (NUNCA TRAVAR O PC DO USUARIO OU STUTTER OU
    QUALQUER COISA DESSA NATUREZA) e processa qualquer audio nao processado, com
    o parakeet."*

PORQUE E' QUE ISTO VIVE NUM MODULO PROPRIO. `worker/sotto_worker.py` esta'
debaixo do ratchet estrutural (`_main/code-health-oracle.py`: bytes, linhas,
defs, classes, funcao mais longa, `except: pass`, `global` -- nenhum pode
piorar), e a propria cura escrita nesse ficheiro e' esta: "a new file does not
make that ratchet worse". O que se extrai aqui nao e' o interruptor (esse fica no
worker, onde o laco do audio o consulta) -- e' aquilo que se pode medir sem
abrir um dispositivo: quem carrega um modelo, quem o larga, e como se escreve um
numero num log.

NADA AQUI ABRE DISPOSITIVO, JANELA OU PLACA. As dependencias do worker entram por
PARAMETRO (`dirs_fn`, `missing_fn`, `rss_fn`, ...) e nao por `import`: um modulo
de politica que importasse o worker pela metade seria a segunda tabela que o
repo inteiro existe para nao ter. E' por isso que nao ha' um unico `import` do
`sotto_worker` neste ficheiro.
"""
from __future__ import annotations

import importlib.util as _ilu
import os
import tempfile as _tempfile
import time

#: FREE physical memory a PARKEET (ONNX int4) pass may start under, in MB. The
#: measured peak of that export is ~615 MB (`worker/redux_live.py`), so this is
#: that peak plus margin -- NOT the ternary runner's 4600 MB floor, which would
#: defer a 615 MB pass on a perfectly healthy machine.
REDUX_ENGINE_MIN_FREE_MB = 800.0

#: Seconds of held audio ONE background parakeet pass decodes at a time. 3.0 is
#: the window `worker/audio_queue_consumer.py` MEASURED on this class of box
#: (2026-10-17: `mean_compute_s=0.745` for `audio_s=14.6`, ~20x real time, 0
#: overruns). A backlog the size of a load episode is therefore drained much
#: faster than it accumulated.
REDUX_ENGINE_WINDOW_S = 3.0

#: O modulo da decisao, carregado UMA vez por processo (ver `shedding`).
_SHEDDING_CACHE = {"module": None, "path": None}


def shedding(path, err=None):
    """`app/webview/load_shedding.py` por caminho, ou None.

    A DECISAO do shedding e' UMA so', e vive ao lado da shell: a tabela dos
    motores, os limiares e a histerese. O worker IMPORTA-a em vez de ter a sua --
    duas tabelas seriam duas verdades, e a que o worker obedece seria sempre a
    que ninguem leu. Carregada por caminho porque o worker corre de `worker/` e a
    shell de `app/webview/`.

    `None` degrada para o nivel publicado pela shell, que e' o comportamento de
    antes: um checkout sem o modulo nao e' razao para parar de transcrever.
    """
    if _SHEDDING_CACHE["module"] is not None and _SHEDDING_CACHE["path"] == path:
        return _SHEDDING_CACHE["module"] or None
    module = None
    try:
        spec = _ilu.spec_from_file_location("load_shedding_worker", path)
        module = _ilu.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 -- sem o modulo, decide a shell
        if err is not None:
            err(f"LOAD_SHEDDING_MODULE_UNAVAILABLE path={path} "
                f"error={type(exc).__name__}: {exc} — o nivel publicado pela shell "
                f"continua a ser obedecido; a medicao local fica OFF")
        module = None
    _SHEDDING_CACHE["module"] = module if module is not None else False
    _SHEDDING_CACHE["path"] = path
    return module


def level_order(fallback):
    """A ordem de severidade dos niveis. UMA tabela: a do modulo da decisao.

    O fallback e' a lista que o worker ja' usava para validar o que a shell
    publica (`PanelVisibilityReader.SHED_LEVELS`), e nao uma terceira copia: um
    checkout sem `load_shedding.py` continua a funcionar com a ordem que ele
    mesmo ja' conhecia.
    """
    module = _SHEDDING_CACHE["module"]
    levels = getattr(module, "LEVELS", None) if module else None
    return tuple(levels) if levels else tuple(fallback)


def worse_level(fallback, *levels):
    """O nivel MAIS SEVERO entre os dados. Desconhecido conta como o mais leve."""
    order = level_order(fallback)
    worst = order[0]
    for value in levels:
        if value in order and order.index(value) > order.index(worst):
            worst = value
    return worst


def fmt_num(value):
    """`93.4%` / `n/a` -- o numero que decidiu, no log e nao num comentario."""
    if value is None:
        return "n/a"
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return "n/a" if value != value else "%.1f%%" % value


class ParakeetEngine:
    """O parakeet como motor de FUNDO: carrega quando faz falta, larga sob pressao.

    `worker/redux_live.py` ja' tem os dois exports do parakeet (`OnnxBackend`:
    615 MB medidos; `TernaryBackend`: 3856 MB) e o `load_backend` que escolhe por
    motor. Este objecto NAO reimplementa nada disso -- ele e' a POLITICA de
    carregar e largar em volta deles, que e' o que a ordem pede.

    TRES PROPRIEDADES:

      1. **CARREGA NA THREAD DO LOTE, NUNCA NA DO AUDIO.** `load()` e' chamado
         pelo thread `redux-batch`, por isso a leitura dos pesos e a alocacao do
         modelo nao seguram a fila do audio nem o tap.
      2. **LARGA QUANDO O NIVEL MANDA PARAR, E VOLTA SOZINHO.** `release()`
         deixa cair a referencia ao backend (a sessao ONNX fecha com ela) e diz o
         RSS que voltou; o lote seguinte carrega outra vez. A referencia cai por
         ATRIBUICAO de `None` e o CPython liberta no mesmo instante -- nao ha'
         `gc.collect()` no caminho do audio, que seria uma pausa para poupar uma
         pausa.
      3. **DIZ O QUE FALTA.** `missing` e' a lista de ficheiros que impedem o
         carregamento, POR MOTOR, e vai para o log: "o motor nao esta' no disco" e
         "o motor falhou a carregar" pedem accoes diferentes.

    `available` e' o que ARMA o interruptor (gate 2 da HARD RULE): sem parakeet
    no disco, parar o nemotron deixaria o dono sem transcritor nenhum, e por isso
    o interruptor recusa armar.
    """

    def __init__(self, requested, dirs_fn, missing_fn, rss_fn, threads=0,
                 log_fn=None, default_engine="onnx"):
        self.default = default_engine
        self.requested = str(requested or default_engine).strip().lower()
        if self.requested not in ("onnx", "ternary"):
            self.requested = default_engine
        self.rss_fn = rss_fn
        self.onnx_dir, self.ternary_dir = dirs_fn()
        self.threads = int(threads or 0)
        self.log = log_fn or (lambda _msg: None)
        missing_onnx, missing_ternary = missing_fn(self.onnx_dir, self.ternary_dir)
        self.missing = list(missing_onnx if self.requested == "onnx"
                            else missing_ternary)
        self.dir = self.onnx_dir if self.requested == "onnx" else self.ternary_dir
        self.available = not self.missing
        self._backend = None
        self.loads = 0
        self.releases = 0
        self.load_failures = 0
        self.load_s = 0.0

    def name(self):
        return self.requested

    @property
    def loaded(self):
        return self._backend is not None

    def load(self):
        """Carrega uma vez e devolve o backend. LEVANTA se nao conseguir."""
        if self._backend is not None:
            return self._backend
        import redux_live as _redux_live

        started = time.perf_counter()
        try:
            backend = _redux_live.load_backend(
                self.requested, self.onnx_dir, self.ternary_dir, self.threads, "cpu")
        except BaseException:
            self.load_failures += 1
            raise
        self._backend = backend
        self.loads += 1
        self.load_s = round(time.perf_counter() - started, 2)
        self.log(
            f"REDUX_ENGINE_LOAD engine={self.requested} "
            f"model={os.path.basename(self.dir)} load_s={self.load_s} "
            f"rss_mb={self.rss_fn():.1f} loads={self.loads}")
        return backend

    def release(self, reason="idle"):
        """Larga o modelo. `True` quando havia algo para largar."""
        if self._backend is None:
            return False
        before = self.rss_fn()
        self._backend = None
        self.releases += 1
        self.log(
            f"REDUX_ENGINE_RELEASED engine={self.requested} reason={reason} "
            f"rss_before_mb={before:.1f} rss_after_mb={self.rss_fn():.1f} "
            f"releases={self.releases} — carrega outra vez quando a carga libertar")
        return True

    def transcribe(self, pcm):
        """Uma janela -> texto. So' levanta se o backend levantar."""
        text, _segments = self.load().transcribe(pcm)
        return str(text or "").strip()


class RunnerEngine:
    """The legacy batch engine: `worker/redux_batch.py` in a CHILD PROCESS.

    Kept, and NOT replaced by `ParakeetEngine`: it is the only path that can run
    the ternary checkpoint, it is what `_main/canonical-producer-oracle.py`
    drives, and a pass that lives in its own process cannot take this one down.
    `available` is the switch's gate 2 for it -- the runner FILE and the
    checkpoint it will LOAD are two different facts.
    """

    def __init__(self, runner, checkpoint_fn, missing_fn, log_fn=None):
        self.runner = runner
        self.log = log_fn or (lambda _msg: None)
        self.model_dir = checkpoint_fn(runner)
        self.missing = missing_fn(self.model_dir)
        self.available = os.path.exists(runner) and not self.missing
        self.loads = 0

    def name(self):
        return os.path.basename(self.runner)

    @property
    def loaded(self):
        return False

    def load(self):
        self.loads += 1
        return self

    def release(self, reason="idle"):
        return False


# ── O LOTE DE FUNDO, extraido de `ReduxHiddenSwitch` ────────────────────────
# As funcoes abaixo recebem o interruptor (`sw`) e trabalham no estado dele: a
# thread do lote, o parakeet, a devolucao do audio que falhou e a contagem. A
# razao de estarem aqui e' a mesma das classes acima -- o ratchet mede o
# `sotto_worker.py` e nao este ficheiro.


def run_engine_pass(sw, held, samples, reason, start_s=0.0):
    """O parakeet NESTE processo, na thread `redux-batch`. Nunca levanta.

    PORQUE AQUI E NAO NA THREAD DO AUDIO. `engine.load()` le 615 MB de pesos
    do disco e aloca-os; `transcribe()` corre a rede. Nenhum dos dois pode
    acontecer no caminho do `audio_q`, que e' o que produz a legenda: a fila
    enchia enquanto o modelo carregava e os blocos perdiam-se. Esta thread
    existe exactamente para isso, e o audio continua a entrar na
    `PendingAudio` enquanto ela trabalha.

    O TRABALHO E' FRAccionado EM JANELAS (`engine_window_s`, 3 s): um atraso
    de dez minutos nao vira uma linha unica de dez minutos, e cada linha
    leva o `start`/`end` REAL da janela de audio de onde saiu (o relogio do
    audio, nao o relogio da parede). Entre janelas o `mode` e' reconferido:
    se o nivel subiu para `muito-alta`, o resto fica para depois em vez de
    continuar a moer a maquina.

    UMA JANELA QUE FALHA NAO LEVA AS OUTRAS: exactamente o audio ainda NAO
    transcrito volta para a frente da `PendingAudio` e o `_park` poe um
    backoff, para um motor partido nao ser tentado 1x por segundo.
    """
    import numpy as np

    try:
        pcm = np.concatenate(held) if len(held) > 1 else np.asarray(held[0])
    except Exception as exc:  # noqa: BLE001 -- nunca levantar daqui
        sw._park(held, "engine-concat", extra=f"error={exc!r}")
        return
    window = max(1, int(sw.engine_window_s * sw.rate))
    total = int(pcm.size)
    offset = 0
    lines = 0
    windows = 0
    t0 = time.time()
    try:
        sw.engine.load()
        while offset < total:
            if sw.mode == "shed" and lines:
                break
            chunk = pcm[offset:offset + window]
            offset += int(chunk.size)
            windows += 1
            text = str(sw.engine.transcribe(chunk) or "").strip()
            if not text:
                continue
            sw._captions.put({
                "type": "caption",
                "text": text,
                "start": round(start_s + (offset - int(chunk.size)) / float(sw.rate), 2),
                "end": round(start_s + offset / float(sw.rate), 2),
                "final": True,
                "producer": sw.producer,
                "producerModel": os.path.basename(sw.engine.dir),
                "route": "redux-batch",
            })
            lines += 1
        sw.segments += 1
        sw.segment_lines += lines
        sw.log(
            f"REDUX_ENGINE_DONE reason={reason} engine={sw.engine.name()} "
            f"model={os.path.basename(sw.engine.dir)} "
            f"audio_s={round(samples / float(sw.rate), 2)} windows={windows} "
            f"lines={lines} loads={sw.engine.loads} "
            f"rss_mb={sw.rss():.1f} "
            f"wall_s={round(time.time() - t0, 2)}")
        if offset < total:
            # O NIVEL SUBIU A MEIO. As janelas ja' feitas ficam feitas; o
            # resto NAO se deita fora -- volta para a frente da espera e sai
            # quando a carga libertar. Sem isto, uma descida a `muito-alta` a
            # meio de um lote de dez minutos apagava o que faltava em
            # silencio, que e' exactamente o que a ordem proibe.
            rest = slice_blocks(held, offset)
            if rest and sw.pending is not None:
                sw.pending.requeue(rest)
            sw.log(
                f"REDUX_ENGINE_YIELD reason=shed level={sw._shed} "
                f"done_s={round(offset / float(sw.rate), 2)} "
                f"requeued_s={round((total - offset) / float(sw.rate), 2)} "
                f"— o audio que falta volta a espera e sai quando a carga libertar")
        if lines == 0:
            # Silencio e' um facto que o lote TEM de dizer: o painel estava
            # fechado e este era o unico transcritor a correr.
            sw._captions.put({
                "type": "status",
                "state": "redux-batch-empty",
                "producer": sw.producer,
                "audio_s": round(samples / float(sw.rate), 2),
                "detail": (
                    f"the parakeet ran over {round(samples / float(sw.rate), 2)}s "
                    f"of accumulated audio and emitted no caption; the panel is "
                    f"hidden and this is the only transcriber running"),
            })
    except BaseException as exc:  # noqa: BLE001 -- carregar pode estourar memoria
        sw._release_engine("pass-failed")
        sw._park(slice_blocks(held, offset), f"engine-{type(exc).__name__}",
                   extra=f"windows={windows} lines={lines} error={exc!r}")

@staticmethod
def _slice_blocks(held, skip):
    """Os blocos a partir da amostra `skip` -- o que ainda NAO foi transcrito."""
    out = []
    pos = 0
    for block in held:
        size = int(block.size)
        if pos + size <= skip:
            pos += size
            continue
        cut = int(skip - pos)
        out.append(block[cut:] if cut > 0 else block)
        pos += size
    return out

def park_pass(sw, held, why, extra=""):
    """Um lote que falhou DEVOLVE o audio e arrefece -- nunca o apaga.

    O backoff e' necessario e nao e' um detalhe: sem ele, um motor partido e'
    tentado de `batch_interval_s` em `batch_interval_s`, cada tentativa a
    carregar 615 MB -- o "busy loop" que o dono proibe, com uma factura de
    RAM. 2^n segundos ate' 60, e o log diz quanto falta para a proxima.
    """
    sw.runner_failures += 1
    delay = min(60.0, 2.0 ** min(6, sw.runner_failures))
    sw._backoff_until = time.time() + delay
    if held and sw.pending is not None:
        sw.pending.requeue(held)
    sw.log(
        f"REDUX_BATCH_FAILED reason={why} failures={sw.runner_failures} "
        f"retry_in_s={delay:.1f} held_s={sw.pending_seconds()} "
        f"requeued_blocks={len(held)} {extra}".rstrip())

def probe_and_spool(shedding_path, err):
    """`(probe, spool_dir)`: a medicao local e o sitio do audio que espera.

    PORQUE AQUI. `main()` e' a funcao mais longa do `sotto_worker.py` e o ratchet
    mede-a (`max_func`); e este trabalho -- decidir se ha' medicao local e onde o
    spool vive -- nao precisa de estar dentro do arranque do worker para ser lido.

    `probe` e' a leitura LOCAL de commit/CPU (`load_shedding.LoadProbe`): a decisao
    deixa de depender de a shell ter escrito o ficheiro. `None` quando este
    checkout nao tem o modulo, e entao decide so' a shell -- exactamente o
    comportamento de antes.

    O SPOOL do audio que espera por um motor: `SOTTO_REDUX_SPOOL_DIR`, ou um
    directorio proprio no temp. `PendingAudio` limpa-o ao construir-se (audio de
    um run anterior e' de uma sessao que ja' nao existe) e apaga o que escreveu
    quando o entrega -- o disco nao se gasta a espera.
    """
    module = shedding(shedding_path, err)
    probe = module.LoadProbe() if module is not None else None
    spool_dir = (os.environ.get("SOTTO_REDUX_SPOOL_DIR")
                 or os.path.join(_tempfile.gettempdir(),
                                 f"sotto-pending-audio-{os.getpid()}"))
    return probe, spool_dir

def done_fields(sw, counts):
    """Os factos do `done`/stats que este lane acrescenta, num dict.

    `counts` vem de `_pending_counts()` (`blocks_in`, `blocks_out`,
    `spilled_blocks`, `held_blocks`, `dropped`). `reduxAudioDropped` nao tem
    caminho de codigo que o aumente (ver `worker/live_queue.py`): um bloco que
    entra e' um bloco que sai, e o `done` DIZ isso em vez de o prometer.
    """
    return {
        "reduxEngine": sw.batch_kind,
        "reduxEngineDir": os.path.basename(getattr(sw.engine, "dir", "") or ""),
        "reduxEngineMinFreeMb": sw.engine_min_free_mb,
        "reduxAudioIn": counts.get("blocks_in", 0),
        "reduxAudioOut": counts.get("blocks_out", 0),
        "reduxAudioSpilled": counts.get("spilled_blocks", 0),
        "reduxAudioSpooled": counts.get("held_blocks", 0),
        "reduxAudioDropped": counts.get("dropped", 0),
        "reduxShedLevel": sw._shed,
        "reduxShedPublished": sw._shed_published,
        "reduxShedMeasured": sw._shed_measured,
        "reduxShedCommitPct": sw._commit_pct,
        "reduxShedCpuPct": sw._cpu_pct,
    }
