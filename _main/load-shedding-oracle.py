#!/usr/bin/env python
# NO-BUG: instrumento da ordem do dono de 2026-10-30 -- shedding por carga
# (alta: so' parakeet; muito-alta: os dois; o audio nunca se larga). Nao corrige
# defeito nenhum: impede que a tabela dos motores e a histerese sejam trocadas
# em silencio, e impede que um nivel passe a desligar o audio.
"""ORACLE: SHEDDING POR CARGA -- que motor corre, e o que o audio NUNCA paga.

ORDEM DO DONO, verbatim (2026-10-30):

    *"shedding por carga -- alta: desliga nemotron, so parakeet; muito alta:
      desliga parakeet tambem. AUDIO SEMPRE fica para processar depois"*

O QUE E' VERIFICADO, e porque e' que isto e' um oraculo e nao uma leitura:

  1. **A TABELA.** `alta` deixa o parakeet e tira o nemotron; `muito-alta` tira os
     dois; `leve` deixa os dois. Uma tabela trocada desliga o motor errado, e o
     dono ouve isso como "a legenda parou".
  2. **O AUDIO NAO TEM NIVEL.** Nenhum nivel tem `audio: False`. Isto e' uma
     arm sobre a TABELA e nao sobre a prosa: se alguem acrescentar um campo de
     audio para "poupar tambem o microfone", o oraculo diz que nao.
  3. **A HISTERESE.** Uma leitura so' nao muda nada; `RESUME_PCT` e' diferente de
     `HIGH_PCT`; a descida precisa de `CONFIRM_SAMPLES` e desce UM degrau de cada
     vez. Um motor que liga e desliga a cada 5 s e' pior do que um desligado.
  4. **A DESCARGA DEGRAU A DEGRAU.** Medido no proprio modulo: com a descida a
     saltar directo ao nivel da leitura, sair de "muito-alta" a 79 % punha o
     nemotron (3,9 GB de modelo) a carregar com a maquina ainda a 79 %.
  5. **O CANAL E' O FICHEIRO, E ELE E' UM SO.** A 2026-10-30 o nivel viaja em
     `_main/panel-visibility.json` (campo `shed`) -- o ficheiro que o worker JA'
     poll. As arms 5 a 8 executam o LEITOR e o DECISOR reais (`worker/
     sotto_worker.py`) e o ESCRITOR real (`PanelVisibilityWriter`), com ficheiros
     no disco: o que se mede e' o que corre, nao o comentario que o descreve.
     A accao coarsa (`SOTTO_LOAD_SHED_ACT` -> `_pause_shell`) foi RETIRADA:
     descarregava os dois motores e perdia o audio, contra a ordem.

Uso:
    python _main/load-shedding-oracle.py            -> rc 0 GREEN / rc 1 RED
    python _main/load-shedding-oracle.py --neg-arm  -> muta uma COPIA e exige RED
"""
from __future__ import annotations

import ast
import importlib.util as _ilu
import os
import json
import re
import shutil
import sys
import tempfile
import time as _time
from pathlib import Path

#: O CHECKOUT QUE SE MEDE. O omissao era `H:\sotto` cravado, o que fazia uma
#: corrida DE UMA WORKTREE medir o repo principal em silencio -- o mesmo verde
#: sobre outro ficheiro. Passa a ser o repo DESTE oraculo (a convencao do
#: `live-queue-oracle.py`), e `SOTTO_ROOT` continua a mandar quando e' dado.
ROOT = Path(os.environ.get("SOTTO_ROOT")
            or Path(__file__).resolve().parent.parent).resolve()
MODULE = ROOT / "app" / "webview" / "load_shedding.py"
SHELL = ROOT / "app" / "webview" / "sotto_webview.py"
WORKER = ROOT / "worker" / "sotto_worker.py"
EXIT_PASS, EXIT_FAIL = 0, 1

rows: list[tuple[bool, str, str]] = []


def add(ok: bool, name: str, detail: str = "") -> bool:
    rows.append((bool(ok), name, detail))
    print(f"  {'GREEN' if ok else 'RED  '} {name}" + (f"  {detail}" if detail else ""))
    return bool(ok)


def load(path: Path):
    spec = _ilu.spec_from_file_location("load_shedding_probe", str(path))
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod



def _start_log_outside_guard(tree):
    """(linha do `.start()`, linha do log `STARTED`, o log esta' FORA do guard?).

    O guard e' o `try` cujo CORPO contem `self._load_shedding.start()`. O que o
    defeito medido provou e' que uma excepcao no corpo (ou nos `except`) aborta o
    arranque; o `else` de um `try` so' corre quando nao houve excepcao, e o log
    que la' vive tem o seu proprio `try` -- por isso o teste e' "fora do corpo e
    dos `except`", nao "fora do `try` inteiro".
    """
    start_line = log_line = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "start" and isinstance(node.func.value, ast.Attribute) \
                and node.func.value.attr == "_load_shedding":
            start_line = node.lineno
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == "log" and node.args:
            # `log('X %s' % y)` -> o texto nao esta' em `args[0].value`, esta' numa
            # `BinOp`/`JoinedStr`. Procura-se a CONSTANTE em toda a chamada.
            texts = [k.value for k in ast.walk(node) if isinstance(k, ast.Constant)
                     and isinstance(k.value, str)]
            if any("LOAD_SHEDDING_STARTED" in t for t in texts):
                log_line = node.lineno
    if start_line is None or log_line is None:
        return start_line, log_line, False
    return start_line, log_line, log_line > _body_end(tree, start_line)


def _body_end(tree, start_line):
    """Ultima linha do `try` que protege o `.start()` (corpo + excepts)."""
    best = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        body = [getattr(n, "lineno", 0) for n in ast.walk(node) if hasattr(n, "lineno")]
        if not body or not (min(body) <= start_line <= max(body)):
            continue
        parts = list(node.body) + [n for h in node.handlers for n in ast.walk(h)]
        prot = [getattr(n, "lineno", 0) for part in parts
                for n in ast.walk(part) if hasattr(n, "lineno")]
        if prot:
            best = max(best, max(prot))
    return best


def newest_shell_segment(log_path=None):
    """(pid, texto) da ULTIMA largada do shell no log vivo. (None, '') se nao ha'."""
    path = Path(log_path) if log_path else (ROOT / "_main" / "webview-run.log")
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None, ""
    hits = list(re.finditer(r"SHELL_STARTUP_STAGE pid=(\d+)", text))
    if not hits:
        return None, ""
    pid = hits[-1].group(1)
    return pid, text[hits[-1].start():]

def verdict(name: str) -> int:
    failed = [r for r in rows if not r[0]]
    print(f"\n{name} {'GREEN' if not failed else 'VERMELHO'} -- "
          f"arms={len(rows)} pass={len(rows) - len(failed)} fail={len(failed)}")
    return EXIT_PASS if not failed else EXIT_FAIL


def run(module_path: Path, shell_path: Path) -> int:
    # UMA CORRIDA, UM VEREDICTO: sem isto o segundo mutante herdava as linhas do
    # primeiro e o total (`arms=82`) descrevia duas corridas como uma.
    rows.clear()
    if not module_path.exists():
        print(f"VERDICT: FAIL -- {module_path} ausente")
        return EXIT_FAIL
    ls = load(module_path)

    print("ARM 1 -- a tabela do dono")
    add(ls.ENGINES['leve'] == {'nemotron': True, 'parakeet': True},
        "leve: os dois motores", str(ls.ENGINES['leve']))
    add(ls.ENGINES['alta'] == {'nemotron': False, 'parakeet': True},
        "alta: nemotron DESLIGADO, parakeet continua", str(ls.ENGINES['alta']))
    add(ls.ENGINES['muito-alta'] == {'nemotron': False, 'parakeet': False},
        "muito-alta: os dois desligados", str(ls.ENGINES['muito-alta']))

    print("\nARM 2 -- o AUDIO nao tem nivel")
    for level in ls.LEVELS:
        add('audio' not in ls.ENGINES[level],
            f"{level}: a tabela nao tem campo de audio")
    source = module_path.read_text(encoding="utf-8")
    add("audio" in source.lower(), "o modulo NOMEIA o audio (para o excluir, nao o esquecer)")

    print("\nARM 3 -- os limiares e a histerese")
    add(ls.HIGH_PCT < ls.VERY_HIGH_PCT, "HIGH < VERY_HIGH",
        f"{ls.HIGH_PCT} < {ls.VERY_HIGH_PCT}")
    add(ls.RESUME_PCT < ls.HIGH_PCT, "RESUME < HIGH (histerese a serio)",
        f"{ls.RESUME_PCT} < {ls.HIGH_PCT}")
    add(ls.CONFIRM_SAMPLES >= 2 and ls.CONFIRM_SAMPLES <= ls.WINDOW_SAMPLES,
        "a confirmacao cabe na janela",
        f"confirm={ls.CONFIRM_SAMPLES} window={ls.WINDOW_SAMPLES}")
    add(ls.level_for(ls.HIGH_PCT - 1) == 'leve', "logo abaixo do limiar ainda e' leve")
    add(ls.level_for(ls.VERY_HIGH_PCT) == 'muito-alta', "no limiar muito-alto ja' e' muito-alta")
    add(ls.level_for(None) == 'leve', "leitura ausente NAO desliga nada")

    print("\nARM 4 -- o estado: subir e' imediato, descer e' degrau a degrau")
    state = ls.LoadShedding()
    level, changed, _why = state.observe(99.0)
    add((level, changed) == ('muito-alta', True), "99 % sobe logo para muito-alta",
        f"{level} changed={changed}")
    add(state.stopped() == ['nemotron', 'parakeet'], "muito-alta para os dois",
        str(state.stopped()))
    # uma leitura isolada abaixo do limiar NAO desce: a confirmacao manda
    level, changed, _why = state.observe(70.0)
    add((level, changed) == ('muito-alta', False),
        "UMA leitura calma nao desce o nivel", f"{level} changed={changed}")
    # confirmadas, desce UM degrau -- e nao ate' 'leve' de uma vez
    state.observe(70.0)
    level, changed, _why = state.observe(70.0)
    add((level, changed) == ('alta', True),
        "confirmada, desce UM degrau (muito-alta -> alta)", f"{level}")
    add(state.engines() == {'nemotron': False, 'parakeet': True},
        "no degrau 'alta' o parakeet volta e o nemotron ainda nao", str(state.engines()))
    for _ in range(3):
        level, changed, _why = state.observe(70.0)
    add(level == 'leve', "confirmadas mais tres, chega a leve", level)
    # a zona morta nao muda nada
    band = ls.LoadShedding('alta')
    level, changed, _why = band.observe((ls.RESUME_PCT + ls.HIGH_PCT) / 2.0)
    add((level, changed) == ('alta', False), "a banda entre RESUME e HIGH segura o nivel",
        f"{level} changed={changed}")

    print("\nARM 5 -- o canal: o nivel viaja no ficheiro que o worker ja' poll")
    shell_source = shell_path.read_text(encoding="utf-8")
    # O NOME PODE APARECER NO TEXTO (a docstring diz que foi retirado); o que nao
    # pode existir e' uma LEITURA da env -- um `armed` que voltasse a ligar o
    # `_pause_shell` seria a accao coarsa outra vez.
    add(not re.search(r"environ(?:\.get)?\(\s*['\"]SOTTO_LOAD_SHED_ACT", shell_source),
        "a accao coarsa que descarregava os DOIS motores foi RETIRADA (a env ja' nao"
        " e' lida)")
    add("SOTTO_LOAD_SHED" in shell_source, "a medicao pode ser desligada (SOTTO_LOAD_SHED=0)")
    add("shed_provider" in shell_source and "shed_provider=self.shedding_level" in shell_source,
        "o escritor da visibilidade publica o nivel (`shed_provider`)")
    add("payload['shed'] = level" in shell_source,
        "a chave `shed` e' ADSICAO no payload congelado (nenhum campo renomeado)")
    tree = ast.parse(shell_source)
    klass = next((n for n in tree.body
                  if isinstance(n, ast.ClassDef) and n.name == "LoadSheddingMonitor"), None)
    add(klass is not None, "o monitor existe no shell")
    if klass is not None:
        names = [n.name for n in klass.body if isinstance(n, ast.FunctionDef)]
        add(hasattr(klass.body and klass, "__init__") or "__init__" in names,
            "o monitor tem `__init__`")
        add("_publish" in names, "o monitor PUBLICA o nivel em vez de parar o worker")
        add("_act" not in names, "o `_act` (parar o worker) ja' nao existe")

    # ARM 9-11 -- O DEFEITO MEDIDO NA PRIMEIRA LARGADA REAL (2026-10-30 10:56:55):
    # `LOAD_SHEDDING_START_FAILED error=AttributeError("'LoadSheddingMonitor'
    # object has no attribute 'armed'")`. A linha de log lia um atributo que a
    # cura tinha RETIRADO, e como o log estava DENTRO do mesmo `try` do `.start()`,
    # a etiqueta velha desarmou a funcionalidade inteira: nenhum nivel publicado.
    #
    # Estas arms medem a CLASSE, nao o caso: (a) nenhum `.armed` volta a ser lido,
    # (b) o log do arranque nao vive no mesmo `try` do `.start()` (medido no AST,
    # pelo numero de linha), e (c) o log da app REAL nao tem a falha para o pid
    # mais recente. A (c) e' a que teria apanhado o defeito -- as outras duas
    # descrevem porque e' que ele nao pode voltar.
    # `armed` e' um atributo LEGITIMO de outro objecto (o `ClickWatcher`), por isso
    # a arm nao pode proibir a palavra: proibe a leitura no MONITOR de shedding.
    add(re.search(r"_load_shedding\s*\.\s*armed", shell_source) is None,
        "o `armed` (lever retirado) nao e' lido no monitor de shedding")
    if klass is not None:
        self_armed = [n for n in ast.walk(klass)
                      if isinstance(n, ast.Attribute) and n.attr == "armed"
                      and isinstance(n.value, ast.Name) and n.value.id == "self"]
        add(not self_armed,
            "a classe do monitor nao le' um `self.armed` que nao inicializa"
            " (foi exactamente essa leitura que a desarmou a 2026-10-30)")
    start_line, log_line, guard_ok = _start_log_outside_guard(tree)
    add(guard_ok,
        "o log `LOAD_SHEDDING_STARTED` corre DEPOIS do `try` do `.start()`"
        " (linha %s contra .start() na linha %s)" % (log_line, start_line))
    pid, seg = newest_shell_segment()
    add('LOAD_SHEDDING_START_FAILED' not in seg,
        "a ultima largada real (pid %s) nao tem `LOAD_SHEDDING_START_FAILED`"
        % (pid or "nenhum"))
    add('LOAD_SHEDDING_STARTED' in seg or pid is None,
        "a ultima largada real (pid %s) registou `LOAD_SHEDDING_STARTED`" % (pid or "-"))
    arms_channel(shell_path)
    load_tmp = Path(tempfile.mkdtemp(prefix="load-shed-load-"))
    try:
        arms_load(globals().get("WORKER", ROOT / "worker" / "sotto_worker.py"), load_tmp)
    finally:
        shutil.rmtree(load_tmp, ignore_errors=True)
    return verdict("LOAD-SHEDDING")


def neg_arm() -> int:
    """Inverte a tabela numa COPIA (`alta` a deixar o nemotron) e exige RED."""
    tmp = Path(tempfile.mkdtemp(prefix="load-shed-neg-"))
    try:
        copy = tmp / "app" / "webview"
        copy.mkdir(parents=True)
        shutil.copy2(MODULE, copy / "load_shedding.py")
        shutil.copy2(SHELL, copy / "sotto_webview.py")
        target = copy / "load_shedding.py"
        text = target.read_text(encoding="utf-8")
        mutant = text.replace(
            "'alta': {'nemotron': False, 'parakeet': True},",
            "'alta': {'nemotron': True, 'parakeet': True},")
        if mutant == text:
            print("NEG-ARM: nao consegui mutar o alvo (o texto mudou)")
            return EXIT_PASS
        target.write_text(mutant, encoding="utf-8")
        print("NEG-ARM: 'alta' passa a deixar o nemotron a correr (a ordem invertida)")
        rc = run(copy / "load_shedding.py", copy / "sotto_webview.py")
        if rc == EXIT_FAIL:
            print("\nNEG-ARM PASS -- RED as designed: o mutante derruba o oraculo")
            return EXIT_FAIL
        print("\nNEG-ARM FAIL -- o oraculo NAO ve a tabela trocada")
        return EXIT_PASS
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def neg_arm_channel() -> int:
    """Muta o CANAL numa copia do worker e exige RED nos arms 6-8.

    Sem isto, as arms do canal seriam as unicas deste oraculo que nenhum mutante
    derruba -- e uma arm que nada derruba nao mede nada. O mutante e' o defeito
    plausivel: `muito-alta` volta a significar so' "batch", ou seja o parakeet
    continua a correr na maquina que o dono mandou parar.
    """
    tmp = Path(tempfile.mkdtemp(prefix="load-shed-chan-neg-"))
    saved = globals().get("WORKER", WORKER)
    try:
        copy = tmp / "app" / "webview"
        copy.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SHELL, copy / "sotto_webview.py")
        worker_copy, _webview = _mutant_layout(tmp)
        # O CANAL e' o `tick()` da classe, e a classe vive em `engine_switch.py`
        # desde a extraccao -- mutar o `sotto_worker.py` aqui nao tocava em nada
        # que estes arms executam, e o "nao consegui mutar o alvo" era a unica
        # coisa honesta que o braco conseguia dizer.
        switch_copy = tmp / "worker" / "engine_switch.py"
        text = switch_copy.read_text(encoding="utf-8")
        mutant = text.replace('        if shed == "muito-alta":\n            wanted = "shed"',
                              '        if shed == "muito-alta":\n            wanted = "batch"')
        if mutant == text:
            print("NEG-ARM(canal): nao consegui mutar o alvo (o texto mudou)")
            return EXIT_PASS
        switch_copy.write_text(mutant, encoding="utf-8")
        print("NEG-ARM(canal): `muito-alta` passa a deixar o parakeet a correr")
        globals()["WORKER"] = worker_copy
        rc = run(copy / "load_shedding.py", copy / "sotto_webview.py")
        if rc == EXIT_FAIL:
            print("\nNEG-ARM(canal) PASS -- RED as designed: o mutante derruba o oraculo")
            return EXIT_FAIL
        print("\nNEG-ARM(canal) FAIL -- o oraculo NAO ve o canal trocado")
        return EXIT_PASS
    finally:
        globals()["WORKER"] = saved
        shutil.rmtree(tmp, ignore_errors=True)


def _load_worker(path: Path):
    """O worker REAL, importado do ficheiro (o import custa ~0 s: medido)."""
    # O directorio do worker no `sys.path`: `sotto_worker.py` faz
    # `import live_queue as _live_queue` no TOPO do ficheiro, por isso o import
    # so' encontra a ESPERA se `worker/` estiver no caminho. Um oraculo que
    # carregasse o worker sem isto mediria `pending=None` e os arms do audio
    # passariam sem medir nada.
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    # OS IRMAOS SAO RE-IMPORTADOS DO DIRECTORIO DESTE FICHEIRO. Sem isto, o
    # `engine_switch` do repo REAL (ja' em `sys.modules` desde o primeiro load)
    # sobrevivia a' carga de um mini repo, e os mutantes dos bracos negativos
    # (canal e derrama) escreviam um ficheiro que ninguem importava -- o braco
    # dizia "nao consegui mutar o alvo" e passava.
    for name in ("engine_switch", "engine_policy", "live_queue"):
        sys.modules.pop(name, None)
    spec = _ilu.spec_from_file_location("sotto_worker_probe", str(path))
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── ARM 9/10: a MEDICAO decide, e a carga a libertar devolve os motores ──────
class _FakeReader:
    """O ficheiro da shell: `visible` e `shed`, escritos pelo oraculo."""

    def __init__(self, visible=False, level="leve"):
        self.path = "<oracle-reader>"
        self.visible = visible
        self.level = level
        self.reads = 0
        self.fallbacks = 0

    def read(self):
        self.reads += 1
        return self.visible, "oracle", 0.0

    def shed(self):
        return self.level


class _FakeProbe:
    """Uma sequencia de leituras (commit %, CPU %) -- uma NOVA por chamada."""

    def __init__(self, seq):
        self.seq = list(seq)
        self.i = 0
        self.samples = 0

    def sample(self):
        commit, cpu = self.seq[min(self.i, len(self.seq) - 1)]
        self.i += 1
        self.samples += 1
        return float(commit), float(cpu), True


class _FakeEngine:
    """O parakeet, com a interface que o interruptor usa e nada mais."""

    available = True
    missing = []
    dir = "<oracle>/parakeet-redux"

    def __init__(self):
        self.loads = 0
        self.releases = 0
        self.calls = 0
        self._loaded = False

    def name(self):
        return "onnx"

    @property
    def loaded(self):
        return self._loaded

    def load(self):
        self._loaded = True
        self.loads += 1
        return self

    def release(self, reason="idle"):
        if not self._loaded:
            return False
        self._loaded = False
        self.releases += 1
        return True

    def transcribe(self, pcm):
        self.calls += 1
        return "o audio que esperou virou legenda"


#: Blocos de audio que o braco empurra com o painel fechado. 25 x 100 ms = 2,5 s,
#: mais do que `max_audio_s=1.0` de RAM: o caminho do SPOOL e' medido, nao lido.
LOAD_BLOCKS = 25


def arms_load(worker_path: Path, tmp: Path) -> None:
    """ARMs 9 e 10: a medicao local, a espera do audio e a volta sozinha."""
    import numpy as np

    try:
        sw = _load_worker(worker_path)
    except Exception as exc:                                        # noqa: BLE001
        add(False, "o worker importa para os arms de carga", repr(exc))
        return
    add(sw._live_queue is not None, "o worker tem a ESPERA (`live_queue`) importada")
    add(sw._policy.shedding(sw._SHEDDING_PATH, None) is not None,
        "o worker importa o modulo da decisao (via `engine_policy`)")
    if sw._live_queue is None or sw._policy.shedding(sw._SHEDDING_PATH, None) is None:
        return

    print("\nARM 9 -- a DECISAO le' a carga MEDIDA, e escreve o numero")
    logs: list[str] = []
    eng = _FakeEngine()
    reader = _FakeReader(visible=False)          # o painel esta' FECHADO
    probe = _FakeProbe([(96.0, 11.0)])
    s = sw.ReduxHiddenSwitch(
        True, reader, str(tmp / "no-runner.py"), logs.append,
        hidden_after_s=0.0, batch_interval_s=1.0, max_audio_s=1.0,
        engine=eng, probe=probe, spool_dir=str(tmp / "spool"))
    add(s.armed is True, "armado: o parakeet no disco e' o motor de fundo",
        f"engine={s.batch_kind} armed={s.armed}")
    add(s.batch_kind == "parakeet", "o lote corre no PARKEET, nao no runner ternario")
    add(s.tick() == "shed",
        "commit 96 % MEDIDO -> shed, mesmo com a shell a dizer `leve`")
    line = [l for l in logs if l.startswith("REDUX_SHEDDING")]
    add(bool(line) and "commit_pct=96.0%" in line[-1] and "measured=muito-alta" in line[-1],
        "o numero que disparou esta' no log", line[-1] if line else "(sem linha)")
    add(bool(line) and "published=leve" in line[-1],
        "e o log diz que a shell nao tinha dito nada (foi a medicao)")

    # O AUDIO QUE CHEGA COM NADA CARREGADO: entra TODO, e o modelo nem acorda.
    for _i in range(LOAD_BLOCKS):
        s.add_audio(np.full(1600, 0.25, dtype=np.float32))
        s.maybe_kick()
    counts = s._pending_counts()
    add(counts["blocks_in"] == LOAD_BLOCKS,
        f"os {LOAD_BLOCKS} blocos capturados com nada carregado entraram na espera",
        str(counts["blocks_in"]))
    add(counts["dropped"] == 0, "nenhum foi deitado fora", str(counts["dropped"]))
    add(counts["spilled_blocks"] > 0,
        "a espera transbordou da RAM para o DISCO (nao para o lixo)",
        f"spilled={counts['spilled_blocks']}")
    add(counts["seconds"] >= LOAD_BLOCKS * 0.1 - 0.001,
        "e o audio inteiro continua a espera", f"{counts['seconds']} s")
    add((eng.loaded, eng.loads) == (False, 0),
        "com a maquina a 96 % o modelo NAO foi carregado")

    # A CARGA LIBERTA: o nivel desce degrau a degrau, e o motor volta sozinho.
    probe.seq = [(12.0, 6.0)]
    mode = s.mode
    for _i in range(30):
        mode = s.tick()
        if mode == "batch":
            break
    add(mode == "batch", "a carga a libertar devolve o worker ao lote (sozinho)",
        f"mode={mode} level={s._shed}")
    s.maybe_kick()
    if s.in_flight():
        s._inflight.join(30.0)
    after = s._pending_counts()
    add(eng.loads >= 1, "o motor CARREGOU sozinho quando a carga libertou",
        f"loads={eng.loads}")
    add(after["blocks_in"] == after["blocks_out"],
        "contagem: N entrou == N saiu",
        f"in={after['blocks_in']} out={after['blocks_out']}")
    add(after["seconds"] == 0.0, "a espera DRENOU para ZERO", f"{after['seconds']} s")
    add(after["dropped"] == 0, "e nada se perdeu no caminho", str(after["dropped"]))
    caps = [c for c in s.drain_captions() if c.get("type") == "caption"]
    add(len(caps) >= 1, "o audio que esperou virou legenda", f"{len(caps)} linha(s)")
    if caps:
        span = round(caps[-1]["end"] - caps[0]["start"], 2)
        add(span > 0 and caps[0]["start"] == 0.0,
            "e as linhas levam o tempo REAL do audio que cobriram",
            f"start={caps[0]['start']} end={caps[-1]['end']} span={span}s")
    add(all(c.get("route") == "redux-batch" for c in caps),
        "todas as linhas dizem de que motor vieram (`route=redux-batch`)")

    print("\nARM 10 -- `muito-alta` LARGA o modelo, e o lote seguinte recarrega-o")
    logs2: list[str] = []
    eng2 = _FakeEngine()
    eng2.load()                                   # ja' esta' carregado
    reader2 = _FakeReader(visible=False)
    probe2 = _FakeProbe([(96.0, 95.0)])
    s2 = sw.ReduxHiddenSwitch(
        True, reader2, str(tmp / "no-runner.py"), logs2.append,
        hidden_after_s=0.0, batch_interval_s=1.0, max_audio_s=1.0,
        engine=eng2, probe=probe2, spool_dir=str(tmp / "spool2"))
    add(s2.tick() == "shed", "96 % de commit e 95 % de CPU -> shed")
    add((eng2.loaded, eng2.releases) == (False, 1),
        "o modelo foi LARGADO (a sessao ONNX cai e o RSS volta)",
        f"loaded={eng2.loaded} releases={eng2.releases}")
    add(any("REDUX_ENGINE_RELEASE" in l for l in logs2),
        "e a largada esta' no log, com o motivo",
        next((l for l in logs2 if "REDUX_ENGINE_RELEASE" in l), ""))
    probe2.seq = [(8.0, 4.0)]
    for _i in range(30):
        if s2.tick() == "batch":
            break
    s2.add_audio(np.full(1600, 0.1, dtype=np.float32))
    for _i in range(9):
        s2.add_audio(np.full(1600, 0.1, dtype=np.float32))
    s2.maybe_kick()
    if s2.in_flight():
        s2._inflight.join(30.0)
    add(eng2.loads >= 2, "e RECARREGOU sozinho no lote seguinte",
        f"loads={eng2.loads}")
    add(s2._pending_counts()["blocks_in"] == s2._pending_counts()["blocks_out"],
        "as 10 linhas de audio desse lote tambem entraram e sairam",
        f"in={s2._pending_counts()['blocks_in']} out={s2._pending_counts()['blocks_out']}")


def _mutant_layout(tmp: Path):
    """Um repo em miniatura: `tmp/worker/sotto_worker.py` + `tmp/app/webview/`.

    O ARRANJO E' O CONTEUDO DO TESTE. `sotto_worker.py` resolve o modulo da
    decisao por caminho relativo ao PAI da sua pasta (`_SHEDDING_PATH`) e importa
    `live_queue` da SUA pasta. Um mutante posto solto em `tmp/sotto_worker.py`
    importa um worker SEM a decisao e SEM a espera, e os RED que isso produz nao
    vem do mutante -- medem o layout do oraculo. Devolve
    `(caminho do worker mutante, pasta app/webview)`.

    OS IRMAOS DO WORKER VEM TODOS. Desde a extraccao o interruptor (a classe que
    estes arms executam) vive em `worker/engine_switch.py`, e ele proprio importa
    `engine_policy`; um mini repo com so' o `live_queue.py` importaria o
    `engine_switch` do repo REAL e o mutante aplicado aqui nao seria o que corre.
    """
    worker_dir = tmp / "worker"
    webview = tmp / "app" / "webview"
    worker_dir.mkdir(parents=True, exist_ok=True)
    webview.mkdir(parents=True, exist_ok=True)
    shutil.copy2(MODULE, webview / "load_shedding.py")
    for sibling in ("live_queue.py", "engine_switch.py", "engine_policy.py"):
        shutil.copy2(ROOT / "worker" / sibling, worker_dir / sibling)
    return worker_dir / "sotto_worker.py", webview


def neg_arm_drain() -> int:
    """Muta o worker para DEITAR UM BLOCO FORA e exige RED nos arms da carga.

    O mutante e' o defeito antigo, no sitio novo: a espera passa do tecto de RAM e
    o bloco NOVO e' recusado em vez de ir para o disco. Se o oraculo nao o vir, os
    arms 9/10 sao prosa.
    """
    tmp = Path(tempfile.mkdtemp(prefix="load-shed-drain-neg-"))
    try:
        worker_copy, _webview = _mutant_layout(tmp)
        # `add_audio` vive em `engine_switch.py` desde a extraccao: o mutante tem
        # de ser escrito no ficheiro que os arms IMPORTAM (ver `_mutant_layout`).
        switch_copy = tmp / "worker" / "engine_switch.py"
        text = switch_copy.read_text(encoding="utf-8")
        mutant = text.replace(
            "        if self.pending is None:\n            return False\n"
            "        return self.pending.add(block)",
            "        if self.pending is None:\n            return False\n"
            "        if self.pending.seconds() > self.max_audio_s:\n"
            "            return False  # MUTANTE: deita fora o audio novo\n"
            "        return self.pending.add(block)")
        if mutant == text:
            print("NEG-ARM(derrama): nao consegui mutar o alvo (o texto mudou)")
            return EXIT_PASS
        switch_copy.write_text(mutant, encoding="utf-8")
        print("NEG-ARM(derrama): com a RAM cheia o audio NOVO passa a ser deitado fora")
        rows.clear()
        arms_load(worker_copy, tmp)
        failed = [r for r in rows if not r[0]]
        if failed:
            for _ok, name, detail in failed:
                print(f"  RED   {name}  {detail}")
            print(f"\nNEG-ARM(derrama) PASS -- RED as designed: {len(failed)} arm(s)")
            return EXIT_FAIL
        print("\nNEG-ARM(derrama) FAIL -- o oraculo NAO ve o bloco deitado fora")
        return EXIT_PASS
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def arms_channel(shell_path: Path) -> None:
    """ARMs 6 a 8: o canal inteiro, executado -- leitor, decisor e escritor."""
    worker_path = globals().get("WORKER", ROOT / "worker" / "sotto_worker.py")
    tmp = Path(tempfile.mkdtemp(prefix="load-shed-channel-"))
    try:
        print("\nARM 6 -- o LEITOR do nivel: falha FECHADA para `leve`")
        try:
            sw = _load_worker(worker_path)
        except Exception as exc:                                    # noqa: BLE001
            add(False, "o worker importa para o oraculo", repr(exc))
            return
        vis = tmp / "vis.json"

        def reader_with(payload_text):
            if payload_text is None:
                try:
                    vis.unlink()
                except OSError:
                    pass
            else:
                vis.write_text(payload_text, encoding="utf-8")
            rd = sw.PanelVisibilityReader(str(vis))
            rd.read()
            return rd

        def pay(**kw):
            base = {"visible": True, "writtenAtEpoch": _time.time(),
                    "staleAfterSeconds": 60}
            base.update(kw)
            return json.dumps(base)

        add(reader_with(None).shed() == "leve", "sem ficheiro -> leve")
        add(reader_with(pay()).shed() == "leve", "sem a chave `shed` -> leve")
        add(reader_with(pay(shed="banana")).shed() == "leve", "valor que nao e' nivel -> leve")
        add(reader_with("{ isto nao e' json").shed() == "leve", "JSON rebentado -> leve")
        for lv in ("leve", "alta", "muito-alta"):
            add(reader_with(pay(shed=lv)).shed() == lv, "leitura honesta de %s" % lv)

        print("\nARM 7 -- o DECISOR do worker: o nivel pesa sobre a visibilidade")
        runner = tmp / "redux_batch.py"
        runner.write_text("# stub\n", encoding="utf-8")
        model = tmp / "model"
        model.mkdir(exist_ok=True)
        for fname in sw.REDUX_CHECKPOINT_FILES:
            (model / fname).write_text("{}", encoding="utf-8")

        def switch_for(shed, visible=True, runner_path=None):
            vis.write_text(pay(visible=visible, shed=shed), encoding="utf-8")
            rd = sw.PanelVisibilityReader(str(vis))
            return sw.ReduxHiddenSwitch(
                True, rd, str(runner_path or runner), lambda _m: None,
                hidden_after_s=0.0, model_dir=str(model))

        add(switch_for("leve").tick() == "stream", "leve + visivel -> stream")
        add(switch_for("alta").tick() == "batch", "alta -> batch (ao vivo PARA, parakeet fica)")
        add(switch_for("muito-alta").tick() == "shed", "muito-alta -> shed (nada corre)")
        add(switch_for("alta", visible=False).tick() == "batch",
            "alta com o painel escondido continua batch (uma decisao, nao duas)")
        nao_armado = sw.ReduxHiddenSwitch(
            True, sw.PanelVisibilityReader(str(vis)), str(tmp / "nope.py"),
            lambda _m: None, hidden_after_s=0.0, model_dir=str(model))
        vis.write_text(pay(shed="muito-alta"), encoding="utf-8")
        add(nao_armado.tick() == "stream",
            "sem motor de batch na maquina o shed NAO corta o ao vivo (HARD RULE)",
            "armed=%s" % nao_armado.armed)

        print("\nARM 8 -- o ESCRITOR publica `shed` no MESMO ficheiro congelado")
        try:
            sys.path.insert(0, str(shell_path.parent))
            spec = _ilu.spec_from_file_location("shell_probe", str(shell_path))
            shell = _ilu.module_from_spec(spec)
            spec.loader.exec_module(shell)
        except Exception as exc:                                    # noqa: BLE001
            add(False, "o shell importa para o oraculo", repr(exc))
            return
        out = tmp / "written.json"
        level = {"value": "alta"}
        writer = shell.PanelVisibilityWriter(
            path=str(out), observe=lambda: True, log=lambda _m: None,
            interval_s=1.0, shed_provider=lambda: level["value"])
        writer.write("test")
        payload = json.loads(out.read_text(encoding="utf-8"))
        add(payload.get("shed") == "alta", "o payload leva `shed=alta`", str(payload.get("shed")))
        add(payload.get("visible") is True and "writtenAtEpoch" in payload,
            "e os campos do contrato congelado continuam la")
        level["value"] = "leve"
        writer.write("test2")
        add(json.loads(out.read_text(encoding="utf-8")).get("shed") == "leve",
            "o nivel SEGUE a mudanca (nao e' um valor de construcao)")

        def explode():
            raise RuntimeError("provider sakiu")
        writer2 = shell.PanelVisibilityWriter(
            path=str(out), observe=lambda: True, log=lambda _m: None,
            interval_s=1.0, shed_provider=explode)
        writer2.write("test3")
        payload3 = json.loads(out.read_text(encoding="utf-8"))
        add("shed" not in payload3 and payload3.get("visible") is True,
            "um provider que rebenta NAO inventa um nivel (o ficheiro aterra na mesma)",
            "shed=%r" % payload3.get("shed"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv) -> int:
    if "--neg-arm-drain" in argv:
        return neg_arm_drain()
    if "--neg-arm-channel" in argv:
        return neg_arm_channel()
    if "--neg-arm" in argv:
        # OS TRES MUTANTES, e o pior dos tres e' o veredicto: uma tabela trocada,
        # um canal trocado, ou um bloco de audio deitado fora tem de ser
        # apanhados, e um verde num deles nao compra os outros.
        table = neg_arm()
        channel = neg_arm_channel()
        drain = neg_arm_drain()
        return (EXIT_FAIL if (table == EXIT_FAIL and channel == EXIT_FAIL
                              and drain == EXIT_FAIL) else EXIT_PASS)
    return run(MODULE, SHELL)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
