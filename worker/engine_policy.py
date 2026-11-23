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
from caption_noise import admit_batch_caption
from silence_gate import window_is_digital_silence

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

#: O CICLO QUE SE EXCITA A SI PROPRIO (MEDIDO 2026-11-09, DM do watcher, stutter
#: 50452). O log do dono tem `REDUX_ENGINE_LOAD 82` / `REDUX_ENGINE_RELEASED 70`
#: numa execucao, com o par mais apertado a 31 s: a maquina enche -> o Sotto larga
#: 460 MB -> a maquina acalma -> o Sotto recarrega -> a RECARGA (1,9 s de leitura
#: + a alocacao) e' a rajada -> a maquina enche outra vez. Nada aqui melhora a
#: transcricao: e' o proprio custo a alimentar o gatilho que o largou.
#: Dois pisos, e os dois sao do MOTOR, nao do nivel: o nivel pode mandar largar a
#: cada segundo sem que o modelo chegue a sair, e o lote seguinte nao paga a
#: leitura dos pesos por um nivel que acabou de descer.
RELOAD_FLOOR_S = 60.0
#: O piso tambem cresce com o custo medido do carregamento: um motor que leva
#: 20 s para carregar nao pode voltar a carregar 60 s depois de o ter largado --
#: o debito seria 1/3 do tempo em disco.
RELOAD_FLOOR_LOAD_FACTOR = 10.0
#: O PISO E' DO CICLO, NAO DA PRIMEIRA VOLTA (dono, 2026-11-15: *"o modelo que
#: transcreve ao vivo, fica afk/idle ou descarrega muito rapido"*). O defeito
#: medido acima foi um par de **31 s** entre carregar e largar; uma largada que
#: veio DEPOIS de o motor residir este tempo nao e' meia volta desse ciclo, e'
#: o fim de uma sessao. Sem esta separacao o piso atrasava o audio que volta
#: (`REDUX_BATCH_DEFERRED reason=reload-floor wait_s=...`) por um ciclo em que
#: ele nao tomou parte -- 60 s de silencio a mais para quem so' parou de falar.
#: O numero e' **300 s = 10x** o par medido (31 s) e o mesmo valor que
#: `app/webview/warm_engine.py` usa como `WARM_THRASH_RESIDENT_S` -- duas
#: declaracoes, um numero so' (o oraculo do motor quente compara-os).
RELOAD_FLOOR_LONG_RESIDENT_S = 300.0

#: O modulo da decisao, carregado UMA vez por processo (ver `shedding`).
_SHEDDING_CACHE = {"module": None, "path": None}

#: `worker/live_queue.py`, pela mesma via (ver `live_queue`).
_LIVE_QUEUE_CACHE = {"module": None, "path": None}

#: O directorio deste ficheiro -- e' onde `live_queue.py` vive.
_HERE = os.path.dirname(os.path.abspath(__file__))


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


def live_queue(err=None):
    """`worker/live_queue.py` por caminho -- so' para a limpeza dos spools irmaos.

    Pela mesma razao de `shedding`: o worker corre de `worker/` mas este modulo
    tambem e' carregado por caminho pelos harnesses (`--policy DIR`), logo um
    `import live_queue` dependeria de o `sys.path` do chamador ter `worker/`.
    Nao ha' `import` do worker aqui: `live_queue` nao importa nada deste repo.
    """
    path = os.path.join(_HERE, "live_queue.py")
    if _LIVE_QUEUE_CACHE["module"] is not None and _LIVE_QUEUE_CACHE["path"] == path:
        return _LIVE_QUEUE_CACHE["module"] or None
    module = None
    try:
        spec = _ilu.spec_from_file_location("live_queue_sweep", path)
        module = _ilu.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 -- sem ele, o disco fica como estava
        if err is not None:
            err(f"AUDIO_PENDING_SWEEP_UNAVAILABLE path={path} "
                f"error={type(exc).__name__}: {exc} — os spools de runs anteriores "
                f"nao sao removidos neste arranque")
        module = None
    _LIVE_QUEUE_CACHE["module"] = module if module is not None else False
    _LIVE_QUEUE_CACHE["path"] = path
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
        #: `cuda` or `cpu` for the LAST backend this object loaded (None before the
        #: first load). Set by `load()` from the backend's own readback, so a
        #: GPU-unavailable batch engine cannot be mistaken for a GPU one.
        self.device = None
        self.loads = 0
        self.releases = 0
        self.load_failures = 0
        self.load_s = 0.0
        #: O RELOGIO DO CICLO CARGA/LARGADA (2026-11-09). `loaded_t` e'
        #: `released_t` sao a parede em que cada um aconteceu; `reload_floor_left`
        #: e `release_age_s` sao o que os pisos leem.
        self.loaded_t = 0.0
        self.released_t = 0.0
        #: Quanto tempo o motor residiu na ULTIMA largada (0 = nunca largou). E' o
        #: que decide se o piso da recarga se aplica -- ver `reload_floor_left`.
        self.last_resident_s = 0.0

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
                self.requested, self.onnx_dir, self.ternary_dir, self.threads, "cuda",
                log=self.log)
        except BaseException:
            self.load_failures += 1
            raise
        self._backend = backend
        self.loads += 1
        self.loaded_t = time.time()
        self.load_s = round(time.perf_counter() - started, 2)
        self.device = getattr(backend, "device", "cuda")
        self.log(
            f"REDUX_ENGINE_LOAD engine={self.requested} "
            f"model={os.path.basename(self.dir)} load_s={self.load_s} "
            f"device={self.device} "
            f"rss_mb={self.rss_fn():.1f} loads={self.loads}")
        return backend

    def release_age_s(self):
        """Ha' quantos segundos o motor esta' CARREGADO (0 se nao esta')."""
        if self._backend is None or not self.loaded_t:
            return 0.0
        return max(0.0, time.time() - self.loaded_t)

    def reload_floor_left(self):
        """Segundos que faltam para o motor poder voltar a carregar (0 = livre).

        O PISO DEPOIS DA LARGADA (2026-11-09): recarregar imediatamente a seguir
        a largar e' o laco que se excita a si proprio -- medido, 82 cargas e 70
        largadas numa execucao, com um par a 31 s. O piso e' `RELOAD_FLOOR_S`,
        esticado por `load_s * RELOAD_FLOOR_LOAD_FACTOR` para um motor cuja
        leitura custa dezenas de segundos.

        O PISO NAO ALCANCA UMA LARGADA DE LONGA RESIDENCIA (2026-11-15). O ciclo
        que ele corta e' "carrega, larga em 31 s, recarrega": se o motor RESIDIU
        `RELOAD_FLOOR_LONG_RESIDENT_S` (300 s = 10x esse par), a largada foi o fim
        de uma sessao e nao meia volta de nada -- cobrar 60 s de espera ao audio
        que voltou seria o proprio defeito que o dono reportou, aplicado a quem
        nao participou do ciclo. A decisao fica registada onde e' lida: a linha
        `REDUX_BATCH_DEFERRED reason=reload-floor` deixa de sair e o piso devolve
        0, com `release_age_s()` a dizer quanto o motor esteve carregado.
        """
        if not self.released_t:
            return 0.0
        if self.last_resident_s >= RELOAD_FLOOR_LONG_RESIDENT_S:
            return 0.0
        floor = max(RELOAD_FLOOR_S, RELOAD_FLOOR_LOAD_FACTOR * float(self.load_s or 0))
        return max(0.0, floor - (time.time() - self.released_t))

    def release(self, reason="idle"):
        """Larga o modelo. `True` quando havia algo para largar.

        A LARGADA NUNCA E' RECUSADA (2026-11-09): a pressao manda sempre, e um
        modelo que a pressao pediu para sair sai na hora. O CICLO que se excita a
        si proprio (o log do dono tem 82 cargas / 70 largadas numa execucao) corta-se
        no lado da CARGA, com o piso `reload_floor_left` -- largar e' barato e
        devolve 460 MB; o que custa 1,9 s de disco e a rajada de CPU e' VOLTAR.
        """
        if self._backend is None:
            return False
        before = self.rss_fn()
        # A RESIDENCIA FICA ESCRITA ANTES DO `loaded_t` CAIR (2026-11-15): e' ela
        # que decide se a proxima carga paga o piso (`reload_floor_left`), e
        # depois da largada `release_age_s()` ja' devolve 0.
        self.last_resident_s = self.release_age_s()
        self._backend = None
        self.releases += 1
        self.released_t = time.time()
        self.loaded_t = 0.0
        self.log(
            f"REDUX_ENGINE_RELEASED engine={self.requested} reason={reason} "
            f"rss_before_mb={before:.1f} rss_after_mb={self.rss_fn():.1f} "
            f"resident_s={self.last_resident_s:.0f} releases={self.releases} "
            f"— carrega outra vez quando a carga libertar")
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


#: O PORTAO DE SILENCIO VIVE EM `worker/silence_gate.py` (2026-11-16): o juiz, o
#: piso MEDIDO que ele usa e a medicao que o justifica viajam juntos, e um
#: ficheiro novo e' o sitio sancionado pelo ratchet estrutural. O que fica AQUI
#: e' o sitio da chamada, a contagem do que foi saltado e a linha que o publica.
def run_engine_pass(sw, held, samples, reason, start_s=0.0):
    """O parakeet NESTE processo, na thread `redux-batch`. Nunca levanta.

    PORQUE AQUI E NAO NA THREAD DO AUDIO. `engine.load()` le 615 MB de pesos
    do disco e aloca-os; `transcribe()` corre a rede. Nenhum dos dois pode
    acontecer no caminho do `audio_q`, que e' o que produz a legenda: a fila
    enchia enquanto o modelo carregava e os blocos perdiam-se. Esta thread
    existe exactamente para isso, e o audio continua a entrar na
    `PendingAudio` enquanto ela trabalha.

    O TRABALHO E' FRAccionado EM JANELAS (`engine_window_s`, 3 s): cada linha
    leva o `start`/`end` REAL da janela; entre janelas o `mode` e' reconferido
    e uma janela falhada devolve o audio a `PendingAudio` com backoff.
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
    #: Windows kept OUT of the engine, in windows and in seconds: "nothing was
    #: transcribed" must never be indistinguishable from "nothing was handed
    #: over" -- the pass still CONSUMES this audio from the queue, as before.
    silent_windows = silent_samples = 0
    #: The load is LAZY now: an all-silent pass never pays the 543.8 MB / 2.17 s
    #: of `REDUX_ENGINE_LOAD`, and the first window that has speech loads it.
    loaded = False
    sw.noise_lines = sw.script_lines = 0
    t0 = time.time()
    try:
        while offset < total:
            if sw.mode == "shed" and lines:
                break
            chunk = pcm[offset:offset + window]
            offset += int(chunk.size)
            windows += 1
            if window_is_digital_silence(chunk):
                silent_windows += 1
                silent_samples += int(chunk.size)
                continue
            if not loaded:
                sw.engine.load()
                loaded = True
            text = str(sw.engine.transcribe(chunk) or "").strip()
            if not text:
                continue
            if not admit_batch_caption(sw, text):
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
            f"silent_windows={silent_windows} "
            f"silent_s={round(silent_samples / float(sw.rate), 2)} "
            f"lines={lines} noise_lines={getattr(sw, 'noise_lines', 0)} "
            f"script_lines={getattr(sw, 'script_lines', 0)} loads={sw.engine.loads} "
            f"rss_mb={sw.rss():.1f} "
            f"wall_s={round(time.time() - t0, 2)}")
        if offset < total:
            # O NIVEL SUBIU A MEIO. As janelas ja' feitas ficam feitas; o
            # resto NAO se deita fora -- volta para a frente da espera e sai
            # quando a carga libertar. Sem isto, uma descida a `muito-alta` a
            # meio de um lote de dez minutos apagava o que faltava em
            # silencio, que e' exactamente o que a ordem proibe.
            rest = _slice_blocks(held, offset)
            if rest and sw.pending is not None:
                sw.pending.requeue(rest)
            sw.log(
                f"REDUX_ENGINE_YIELD reason=shed level={sw._shed} "
                f"done_s={round(offset / float(sw.rate), 2)} "
                f"requeued_s={round((total - offset) / float(sw.rate), 2)} "
                f"— o audio que falta volta a espera e sai quando a carga libertar")
        if lines == 0:
            # Silencio e' um facto que o lote TEM de dizer: o painel estava
            # fechado e este era o unico transcritor a correr. Um passe que o
            # PORTAO esvaziou nao se apresenta como um passe que o motor esvaziou.
            heard_s = round(samples / float(sw.rate), 2)
            detail = (
                f"the parakeet ran over {heard_s}s of accumulated audio and "
                f"emitted no caption; the panel is hidden and this is the only "
                f"transcriber running") if not silent_windows else (
                f"{silent_windows} of {windows} windows were digital silence and "
                f"were not decoded ({round(silent_samples / float(sw.rate), 2)}s "
                f"of {heard_s}s); the rest emitted no caption; the panel is "
                f"hidden and this is the only transcriber running")
            sw._captions.put({
                "type": "status",
                "state": "redux-batch-empty",
                "producer": sw.producer,
                "audio_s": heard_s,
                "detail": detail,
            })
    except BaseException as exc:  # noqa: BLE001 -- carregar pode estourar memoria
        sw._release_engine("pass-failed")
        sw._park(_slice_blocks(held, offset), f"engine-{type(exc).__name__}",
                   extra=f"windows={windows} lines={lines} error={exc!r}")

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

    E os IRMAOS de runs anteriores sao removidos AQUI, antes de o directorio novo
    nascer: o spool de cada worker tem o pid no nome, logo a limpeza de dentro do
    directorio (`PendingAudio`) so' podia ver o que este run acabara de criar.
    Medido 2026-11-05: cinco irmaos orfaos (~52 MB) de pids mortos em `G:/Temp`.
    Com `SOTTO_REDUX_SPOOL_DIR` o directorio e' do dono e nao se varre nada.
    """
    module = shedding(shedding_path, err)
    probe = module.LoadProbe() if module is not None else None
    custom = os.environ.get("SOTTO_REDUX_SPOOL_DIR")
    if custom:
        return probe, custom
    spool_dir = os.path.join(_tempfile.gettempdir(),
                             f"sotto-pending-audio-{os.getpid()}")
    queue_mod = live_queue(err)
    if queue_mod is not None:
        try:
            queue_mod.sweep_sibling_spools(spool_dir, keep_pid=os.getpid(), log=err)
        except Exception as exc:  # noqa: BLE001 -- limpar disco nao e' o arranque
            if err is not None:
                err(f"AUDIO_PENDING_SWEEP_FAILED {type(exc).__name__}: {exc}")
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



