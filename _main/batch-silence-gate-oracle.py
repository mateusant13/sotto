# NO-BUG: o passe de fundo decodificava SILENCIO DIGITAL (capacidade, nao um id do
# `_main/bug-ledger.json`: nao houve legenda errada, houve CPU queimada por zero).
"""O LOTE NAO DECODIFICA SILENCIO DIGITAL -- e diz quantas janelas saltou.

O FACTO MEDIDO (2026-11-16, no worker vivo do dono, pid 20584, `--threads 2`):

  python _main/shell-thread-cpu.py 20584 --burst --seconds 40 --above 20
  BURST t=+1.0s fios=309.4% session-16-intra-op-3:73.4% ... -0:71.9%
  BURST-END segundos_acima_de_20%=5 pico_fios=309.4% processo_total=31.9%

e, na MESMA janela, o log do lote (`_main/webview-run.log`):

  REDUX_BATCH_KICK reason=interval engine=parakeet audio_s=30.0 ... asr_expired=3
  STATUS_APPLIED text="redux-batch-empty"

`audio_s=30.0` em TODOS os kicks e' o tecto `REDUX_BATCH_PASS_MAX_S`: a fila nunca
drenava, porque cada passe decodificava 10 janelas de 3 s que continham zeros. O
endpoint no mesmo minuto dizia `sample={"peak":0.0,"blocks":2.0}` e
`tap-silent-desktop window_s=4.0 endpoints=6 peak=1.0`.

O QUE MUDOU. `worker/silence_gate.py` (novo) e' o juiz --
`window_is_digital_silence(chunk)`, pico E rms abaixo do par MEDIDO que
`worker/audio_recorder.py` ja' declara (`DIGITAL_SILENCE_PEAK`/`_RMS`, 0,000122 de
pico em todo o loopback sem nada a tocar). `worker/engine_policy.py:run_engine_pass`
pergunta-lhe ANTES de `sw.engine.transcribe()`, conta as janelas saltadas, e publica
`silent_windows=N silent_s=X` UMA vez por passe (nunca uma linha por janela). O audio
saltado continua a ser CONSUMIDO da fila exactamente como antes.

O QUE ESTE ORACULO JULGA (sem modelo, sem dispositivo, sem janela, sem fio):

  A1 silence-is-skipped      zeros sao silencio digital para o juiz.
  A2 quiet-but-real-decodes  um tom a -35 dBFS (pico 0,0178 = 17x o piso) NAO e'
                             silencio e o passe DECODIFICA-O (a invariante: fala
                             baixa nunca e' saltada).
  A3 dither-is-not-silence   pico abaixo do piso mas rms acima (o `and`, nao o
                             `or`): ruido de sala continua a ir ao motor.
  A4 speech-burst-decodes    uma janela 99 % calada com 40 ms de fala no inicio
                             decodifica -- o piso mede a janela, nao a media.
  A5 call-site-count         N=3 janelas silenciosas + 1 de fala: `transcribe`
                             e' chamado EXACTAMENTE UMA vez, e com o PCM da
                             janela de fala (nao com outra).
  A6 accounted-not-dropped  a mesma passagem diz `windows=4 silent_windows=3
                             silent_s=9.0 audio_s=12.0` -- o audio saltado esta'
                             contado, nao desaparecido.
  A7 timebase-of-the-line    a legenda publicada leva o start/end REAIS da janela
                             que a produziu (9,0-12,0 s): saltar janelas nao
                             desloca o tempo das que ficam.
  A8 all-silent-no-load      um passe todo silencioso: zero `transcribe`, zero
                             `load()` (nem os 543,8 MB de `REDUX_ENGINE_LOAD`
                             nem os 2,17 s de leitura), e o estado
                             `redux-batch-empty` CONTINUA a ser publicado com o
                             motivo certo -- um passe que o portao esvaziou nao
                             se apresenta como um passe que o motor esvaziou.
  A9 live-path-untouched     o juiz e' chamado DENTRO de `run_engine_pass` e em
                             mais sitio nenhum (`ast`, em `engine_policy.py` e
                             `engine_switch.py`): a latencia da legenda ao vivo
                             nao leva nem uma leitura deste portao.
  A10 load-is-lazy-once      duas janelas de fala no mesmo passe -> um `load()`.
  A11 judge-cost-under-ceiling  o custo do juiz, MEDIDO, contra um tecto declarado
                             antes (`JUDGE_CEILING_MS`): um limite sem juiz e'
                             decoracao.

`--neg-arm`: duas mutacoes em COPIA (nunca em HEAD), cada uma tem de derrubar os
bracos do portao:
  M1 o sitio da chamada desligado (`if False and window_is_digital_silence(...)`)
     -- e' o codigo de ANTES da cura (decodificacao incondicional).
  M2 os pisos a zero dentro de `silence_gate.py` -- o juiz existe e nao recusa nada.
rc=1 quando apanha as duas, rc=0 quando alguma sobrevive, rc=2 em erro de setup.
"""
from __future__ import annotations

import ast
import importlib.util
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORKER = os.path.join(ROOT, "worker")
ENGINE_POLICY = os.path.join(WORKER, "engine_policy.py")
ENGINE_SWITCH = os.path.join(WORKER, "engine_switch.py")
SILENCE_GATE = os.path.join(WORKER, "silence_gate.py")

sys.path.insert(0, WORKER)

RESULTS = []           # [(arm-id, ok, detail)]

#: O tecto do juiz, declarado ANTES de medir. Duas reducoes sobre 3 s de audio a
#: 16 kHz custam microssegundos; 1,0 ms por janela e' folga de 100x e continua a
#: ser ~0,04 % do que uma decodificacao custa (2,40 s de parede por janela,
#: medido em `engine_switch.py`).
JUDGE_CEILING_MS = 1.0


class SetupError(Exception):
    pass


def add(ok, arm, detail=''):
    RESULTS.append((arm, bool(ok), detail))
    print(('PASS ' if ok else 'FAIL ') + arm + ((' -- %s' % (detail,)) if detail else ''))


def load_module(path, name):
    """Um modulo do produto carregado por caminho (nunca por `import` do repo)."""
    if not os.path.exists(path):
        raise SetupError('ficheiro ausente: %s' % path)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SetupError('nao foi possivel carregar %s' % path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# ── o PCM dos bracos ─────────────────────────────────────────────────────────
def silence(n):
    import numpy as np

    return np.zeros(int(n), dtype=np.float32)


def tone(n, amp=0.02, hz=220.0, rate=16000):
    import numpy as np

    t = np.arange(int(n), dtype=np.float64)
    return (amp * np.sin(2.0 * np.pi * hz * t / float(rate))).astype(np.float32)


def speech_burst(n, amp=0.05, burst=640, rate=16000):
    """Janela quase toda calada com um bloco curto de fala no inicio."""
    x = silence(n)
    x[:int(burst)] = tone(burst, amp=amp, hz=180.0, rate=rate)
    return x


# ── o interruptor e o motor FALSE ────────────────────────────────────────────
class _Captions:
    def __init__(self):
        self.items = []

    def put(self, item):
        self.items.append(item)


class _Engine:
    """O motor que CONTA. Nenhum modelo, nenhum dispositivo."""

    def __init__(self, texts=(), dir_name='models/parakeet-redux-onnx-int4'):
        self.texts = list(texts)
        self.chunks = []
        self.loads = 0
        self.dir = dir_name

    def name(self):
        return 'onnx'

    def load(self):
        self.loads += 1
        return self

    def transcribe(self, pcm):
        self.chunks.append(None if pcm is None else pcm.copy())
        return self.texts.pop(0) if self.texts else ''


class _Switch:
    rate = 16000
    mode = 'normal'
    producer = 'redux'
    segments = 0
    segment_lines = 0

    def __init__(self, engine, window_s=3.0):
        self.engine = engine
        self.engine_window_s = window_s
        self._captions = _Captions()
        self.logs = []
        self.parked = []
        self.pending = None

    def log(self, message):
        self.logs.append(str(message))

    def rss(self):
        return 0.0

    def _park(self, held, reason, extra=''):
        self.parked.append((reason, extra))

    def _release_engine(self, reason):
        self.logs.append('RELEASE ' + reason)


def run_pass(policy, blocks, texts=(), window_s=3.0):
    """Um passe REAL de `run_engine_pass` sobre `blocks`. Devolve o interruptor."""
    import numpy as np

    sw = _Switch(_Engine(texts), window_s=window_s)
    held = [np.asarray(b, dtype=np.float32) for b in blocks]
    policy.run_engine_pass(sw, held, int(sum(b.size for b in held)), 'oracle')
    return sw


def done_line(sw):
    for line in sw.logs:
        if line.startswith('REDUX_ENGINE_DONE'):
            return line
    return ''


def kv(line):
    out = {}
    for token in line.split():
        if '=' in token:
            key, _, value = token.partition('=')
            out[key] = value
    return out


def status(sw):
    for item in sw._captions.items:
        if item.get('type') == 'status' and item.get('state') == 'redux-batch-empty':
            return item
    return None


# ── os bracos ────────────────────────────────────────────────────────────────
def run_positive(policy_path=ENGINE_POLICY, gate_path=SILENCE_GATE,
                 module_name='engine_policy_under_test'):
    import numpy as np

    sys.modules.pop('silence_gate', None)
    policy = load_module(policy_path, module_name)
    gate = sys.modules.get('silence_gate') or load_module(gate_path, 'silence_gate')
    judge = gate.window_is_digital_silence

    # A1 -- o juiz, na cor que interessa
    add(judge(silence(48000)) is True,
        'A1 silence-is-skipped', 'zeros -> digital silence')

    # A2 -- fala BAIXA mas real continua a decodificar (a invariante)
    quiet = tone(48000, amp=0.0178)      # -35 dBFS de pico
    sw = run_pass(policy, [quiet], ['quiet line'])
    add(judge(quiet) is False and len(sw.engine.chunks) == 1,
        'A2 quiet-but-real-decodes',
        'peak=%.4f decoded=%d' % (float(np.max(np.abs(quiet))), len(sw.engine.chunks)))

    # A3 -- o `and`, nao o `or`: pico abaixo do piso com rms acima NAO e' silencio
    rng = np.random.default_rng(20261116)
    dither = np.clip((rng.standard_normal(48000) * 2.4e-4).astype(np.float32),
                     -9.0e-4, 9.0e-4).astype(np.float32)
    dither_rms = float(np.sqrt(np.mean(np.square(dither, dtype=np.float64))))
    add(float(np.max(np.abs(dither))) < gate.DIGITAL_SILENCE_PEAK
        and judge(dither) is False,
        'A3 dither-is-not-silence',
        'peak=%.2e rms=%.2e (floors %.0e/%.0e) -> not silence'
        % (float(np.max(np.abs(dither))), dither_rms,
           gate.DIGITAL_SILENCE_PEAK, gate.DIGITAL_SILENCE_RMS))

    # A4 -- janela quase calada com fala curta: decodifica
    burst = speech_burst(48000)
    add(judge(burst) is False, 'A4 speech-burst-decodes',
        '40 ms of speech inside 3 s of zeros is still speech')

    # A5 -- o SITIO REAL: 3 silenciosas + 1 de fala
    speech = tone(48000, amp=0.03)
    sw = run_pass(policy, [silence(48000), silence(48000), silence(48000), speech],
                  ['hello world'])
    one = (len(sw.engine.chunks) == 1
           and sw.engine.chunks[0] is not None
           and np.array_equal(sw.engine.chunks[0], speech))
    add(one, 'A5 call-site-count',
        'transcribe calls=%d' % len(sw.engine.chunks))

    # A6 -- contabilizado, nao desaparecido
    fields = kv(done_line(sw))
    add(fields.get('windows') == '4' and fields.get('silent_windows') == '3'
        and fields.get('silent_s') == '9.0' and fields.get('audio_s') == '12.0',
        'A6 accounted-not-dropped',
        done_line(sw) or '(sem linha REDUX_ENGINE_DONE)')

    # A7 -- a linha que fica leva o tempo REAL dela
    caps = [x for x in sw._captions.items if x.get('type') == 'caption']
    add([(c.get('start'), c.get('end'), c.get('text')) for c in caps]
        == [(9.0, 12.0, 'hello world')],
        'A7 timebase-of-the-line',
        [(c.get('start'), c.get('end'), c.get('text')) for c in caps])

    # A8 -- passe todo silencioso: nem motor, nem carga, e o estado continua
    sw = run_pass(policy, [silence(48000) for _ in range(4)])
    st = status(sw)
    add(len(sw.engine.chunks) == 0 and sw.engine.loads == 0 and st is not None
        and 'digital silence' in str(st.get('detail', '')),
        'A8 all-silent-no-load',
        'transcribe=%d load=%d detail=%r'
        % (len(sw.engine.chunks), sw.engine.loads,
           (st or {}).get('detail', '')[:80]))

    # A9 -- o juiz vive no passe do LOTE, e em mais sitio nenhum
    add(_judge_is_batch_only(), 'A9 live-path-untouched', _judge_census())

    # A10 -- a carga e' preguicosa e UMA
    sw = run_pass(policy, [tone(48000, amp=0.03), tone(48000, amp=0.04)], ['a', 'b'])
    add(sw.engine.loads == 1 and len(sw.engine.chunks) == 2,
        'A10 load-is-lazy-once',
        'load=%d transcribe=%d' % (sw.engine.loads, len(sw.engine.chunks)))

    # A11 -- o custo do portao, medido, contra um tecto declarado
    window = tone(48000, amp=0.03)
    judge(window)                                        # aquece
    t0 = time.perf_counter()
    reps = 200
    for _ in range(reps):
        judge(window)
    per_ms = (time.perf_counter() - t0) / reps * 1000.0
    add(per_ms <= JUDGE_CEILING_MS, 'A11 judge-cost-under-ceiling',
        '%.4f ms/window (ceiling %.2f ms) -> %.1f ms for the %d-window cap pass'
        % (per_ms, JUDGE_CEILING_MS, per_ms * 10, 10))

    return all(ok for _arm, ok, _d in RESULTS)


def _judge_census():
    """Onde `window_is_digital_silence` e' chamado: `path:line -> funcao`."""
    hits = []
    for path in (ENGINE_POLICY, ENGINE_SWITCH):
        if not os.path.exists(path):
            continue
        with open(path, encoding='utf-8') as fh:
            tree = ast.parse(fh.read())
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            for inner in ast.walk(node):
                if (isinstance(inner, ast.Call)
                        and isinstance(inner.func, ast.Name)
                        and inner.func.id == 'window_is_digital_silence'):
                    hits.append('%s:%d -> %s' % (os.path.basename(path),
                                                 inner.lineno, node.name))
    return ', '.join(hits) if hits else 'no call found'


def _judge_is_batch_only():
    """True quando o juiz e' chamado SO' dentro de `run_engine_pass`.

    Uma chamada fora dele seria o portao a entrar no caminho da legenda ao vivo,
    que esta lane nao pode tocar.
    """
    for path in (ENGINE_POLICY, ENGINE_SWITCH):
        if not os.path.exists(path):
            return False
        with open(path, encoding='utf-8') as fh:
            tree = ast.parse(fh.read())
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            for inner in ast.walk(node):
                if (isinstance(inner, ast.Call)
                        and isinstance(inner.func, ast.Name)
                        and inner.func.id == 'window_is_digital_silence'
                        and node.name != 'run_engine_pass'):
                    return False
    return 'run_engine_pass' in _judge_census()


# ── o controlo negativo ──────────────────────────────────────────────────────
def _mutate(src, old, new, where):
    if old not in src:
        raise SetupError('%s: mutation anchor not found: %r' % (where, old[:60]))
    return src.replace(old, new, 1)


MUTATIONS = (
    # (tag, ficheiro, de, para)
    ('M1 call-site-off', 'engine_policy',
     '            if window_is_digital_silence(chunk):',
     '            if False and window_is_digital_silence(chunk):'),
    ('M2 floors-zeroed', 'silence_gate',
     '    peak_floor = (DIGITAL_SILENCE_PEAK if peak_floor is None',
     '    peak_floor = (0.0 if peak_floor is None'),
)


def run_negative():
    """Duas mutacoes em COPIA; cada uma tem de derrubar os bracos do portao."""
    sources = {}
    for key, path in (('engine_policy', ENGINE_POLICY),
                      ('silence_gate', SILENCE_GATE)):
        if not os.path.exists(path):
            raise SetupError('ficheiro ausente: %s' % path)
        with open(path, encoding='utf-8') as fh:
            sources[key] = fh.read()

    tmp = tempfile.mkdtemp(prefix='batch-silence-neg-')
    verdicts = []
    try:
        for index, (tag, key, old, new) in enumerate(MUTATIONS):
            payload = dict(sources)
            payload[key] = _mutate(payload[key], old, new, tag)
            case_dir = os.path.join(tmp, 'm%d' % index)
            os.makedirs(case_dir, exist_ok=True)
            for name, text in payload.items():
                with open(os.path.join(case_dir, name + '.py'), 'w',
                          encoding='utf-8') as fh:
                    fh.write(text)
            # O diretorio mutado tem de vir PRIMEIRO no caminho: o carregamento
            # da copia de `engine_policy` faz `from silence_gate import ...` e tem
            # de apanhar a copia mutada, nao o modulo real ja' em `sys.modules`.
            sys.path.insert(0, case_dir)
            sys.modules.pop('silence_gate', None)
            RESULTS.clear()
            try:
                passed = run_positive(os.path.join(case_dir, 'engine_policy.py'),
                                      os.path.join(case_dir, 'silence_gate.py'),
                                      'engine_policy_mutant_%d' % index)
            except SetupError as exc:
                raise SetupError('%s: %s' % (tag, exc))
            finally:
                try:
                    sys.path.remove(case_dir)
                except ValueError:
                    pass
            failing = [arm for arm, ok, _d in RESULTS if not ok]
            verdicts.append((tag, not passed, failing))
            print('  %s -> %s (still green: %s)'
                  % (tag, 'RED' if not passed else 'PASS',
                     [arm for arm, ok, _d in RESULTS if ok]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    caught = all(red for _t, red, _f in verdicts)
    for tag, red, failing in verdicts:
        print('  %s: %s -- red arms: %s'
              % (tag, 'CAUGHT' if red else 'SURVIVED',
                 ', '.join(failing) if failing else '(none)'))
    if caught:
        print('NEG-ARM: PASS -- %d/%d mutants caught' % (len(verdicts), len(verdicts)))
        return True
    print('NEG-ARM: FAIL -- a mutation survived')
    return False


def main(argv):
    if '--neg-arm' in argv:
        try:
            caught = run_negative()
        except SetupError as exc:
            print('NEG-ARM SETUP ERROR: %s' % exc)
            print('NEG-ARM: rc=2 -- nao houve mutacao para julgar (nao e um PASS)')
            return 2
        return 1 if caught else 0
    try:
        ok = run_positive()
    except SetupError as exc:
        print('SETUP ERROR: %s' % exc)
        return 2
    print('VERDICT: %s (%d/%d)' % ('PASS' if ok else 'FAIL',
                                   sum(1 for _a, o, _d in RESULTS if o),
                                   len(RESULTS)))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
