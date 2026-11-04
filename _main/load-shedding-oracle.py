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
BATCH = ROOT / "app" / "webview" / "batch_queue.py"
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
        # O ARRANQUE, na forma que a regiao tem hoje: `open_action(...)` devolve o
        # guard ja' a correr, e e' ele que arranca o laco. A arm continua a medir a
        # PROPRIEDADE (o log nao vive no `try` do arranque), nao a forma antiga.
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "start" and isinstance(node.func.value, ast.Attribute) \
                and node.func.value.attr in ("_load_shedding", "_load_action"):
            start_line = node.lineno
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) \
                and isinstance(node.value.func, ast.Attribute) \
                and node.value.func.attr == "open_action":
            targets = [x for x in node.targets if isinstance(x, ast.Attribute)]
            if any(x.attr == "_load_action" for x in targets):
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


#: O que faz de uma largada uma MEDICAO e nao a instancia do dono. As lanes
#: arrancam o shell com a mutex renomeada, em modo selftest ou sem worker, e
#: morrem quando o teste acaba -- mas deixam `SHELL_STARTUP_STAGE pid=N` no log,
#: e a ultima dessas linhas NAO e' a app. Julgar a ultima linha foi o defeito de
#: 2026-11-01: o oraculo leu o pid de uma largada de medicao (ja' morta) e
#: reprovou a app do dono por uma linha que pertencia a outra instancia.
MEASURE_MARKERS = ("--mutex-name", "--selftest", "--no-worker",
                   "selftest=", "SOTTO_SELFTEST")

#: Quantas recusas o escolhedor imprime antes de resumir. O log guarda uma
#: largada por arranque, e num dia de lanes sao dezenas: o veredicto tem de ser
#: a coisa mais alta do stdout, nao a lista de pids que nao interessam.
_SKIP_LINES = 6


def _pid_alive(pid):
    """True/False se o processo existe; None quando nao se pode saber.

    Windows: `OpenProcess` + `GetExitCodeProcess` (STILL_ACTIVE=259). Fora do
    Windows devolve None, e entao a escolha cai no criterio da mutex so'.
    """
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    if pid <= 0:
        return False
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = k32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = wintypes.DWORD()
        ok = k32.GetExitCodeProcess(handle, ctypes.byref(code))
        k32.CloseHandle(handle)
        return bool(ok) and code.value == 259
    except Exception:                                           # noqa: BLE001
        return None


def _not_the_instance(pid, seg, alive):
    """Porque e' que esta largada NAO e' a instancia viva; None quando E'.

    Tres perguntas, na ordem em que cada uma pode excluir uma largada:
    1. o texto traz um marcador de medicao (a lane nao e' a app);
    2. a largada PERDEU a mutex (`SINGLE_INSTANCE ... already_running=true`);
    3. o processo ja' nao existe (largada morta, tipicamente de medicao).
    Sem a linha `SINGLE_INSTANCE` a largada nao chegou a disputar a mutex e
    tambem nao serve -- mas isso so' decide quando nao ha' processo vivo: um
    shell vivo com o log cortado continua a ser a instancia.
    """
    low = seg.lower()
    for marker in MEASURE_MARKERS:
        if marker.lower() in low:
            return f"marcador de medicao {marker!r}"
    live = alive(pid)
    if live is False:
        return "processo ja' nao existe (largada morta)"
    m = re.search(r"SINGLE_INSTANCE name=\S+ already_running=(true|false)", seg)
    if m and m.group(1) == "true":
        return "perdeu a mutex (already_running=true)"
    if not m and live is not True:
        return "sem `SINGLE_INSTANCE` e sem processo para confirmar"
    return None


def shell_launches(log_path=None):
    """[(pid, segmento)] de todas as largadas, da mais NOVA para a mais velha.

    O segmento de cada uma vai da sua linha `SHELL_STARTUP_STAGE` ate' a linha
    seguinte da MESMA especie -- o log e' escrito por varias instancias, por isso
    um segmento e' uma aproximacao e as arms so' o usam para o que a propria
    largada escreveu no arranque.
    """
    path = Path(log_path) if log_path else (ROOT / "_main" / "webview-run.log")
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    hits = list(re.finditer(r"SHELL_STARTUP_STAGE pid=(\d+)", text))
    starts = [h.start() for h in hits] + [len(text)]
    launches = [(h.group(1), text[starts[i]:starts[i + 1]])
                for i, h in enumerate(hits)]
    launches.reverse()
    return launches


def newest_shell_segment(log_path=None, alive=_pid_alive):
    """(pid, texto) da largada que E' a instancia viva; (None, '') se nao ha'.

    "A instancia" = a largada mais recente que (a) nao e' medicao, (b) ganhou a
    mutex e (c) tem processo vivo. Diz no stdout qual escolheu e porque' recusou
    as outras: um oraculo que julga a instancia errada tem de deixar rasto do
    erro, e nao so' o vermelho.
    """
    launches = shell_launches(log_path)
    if not launches:
        return None, ""
    path = Path(log_path) if log_path else (ROOT / "_main" / "webview-run.log")
    try:
        tail = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        tail = ""
    skipped = 0
    for pid, seg in launches:
        why = _not_the_instance(pid, seg, alive)
        if why is None:
            print(f"  instancia escolhida: pid={pid} (viva, ganhou a mutex,"
                  f" sem marcador de medicao)")
            if skipped:
                print(f"  {skipped} largada(s) mais nova(s) recusada(s) antes desta")
            # A cauda INTEIRA a partir do arranque desta instancia: uma largada
            # posterior nao a interrompe -- so' acrescenta linhas ao mesmo
            # ficheiro, e as linhas desta continuam la'.
            start = tail.find(f"SHELL_STARTUP_STAGE pid={pid}")
            return pid, (tail[start:] if start >= 0 else seg)
        skipped += 1
        # O log acumula uma largada por cada arranque e cada medicao: sem tecto
        # esta lista seria o oraculo a falar mais alto do que o veredicto.
        if skipped <= _SKIP_LINES:
            print(f"  largada ignorada: pid={pid} -- {why}")
    if skipped > _SKIP_LINES:
        print(f"  ... e {skipped - _SKIP_LINES} largada(s) mais antigas, ignoradas"
              f" pelo mesmo criterio")
    print("  nenhuma largada e' a instancia viva -- as arms do log ficam sem sujeito")
    return None, ""

class _NoEngine:
    """O motor de batch que NAO existe -- injectado no interruptor do oraculo.

    PORQUE E' PRECISO DIZER-LHE. `ReduxHiddenSwitch.armed` e' verdadeiro quando
    o parakeet esta' no disco OU o runner existe; a arm da HARD RULE tirava so' o
    runner e deixava a decisao nas maos da maquina. Na maquina de medicao o
    parakeet existe, `armed=True` era a resposta CORRECTA e o oraculo reprovava-a
    -- media o disco, nao a regra. Um motor explicito com `available=False` (e
    `dir` vazio, para o log nao citar um caminho alheio) tira a maquina da
    equacao: o que sobra e' o codigo.
    """

    available = False
    dir = ""

    def release(self, *args, **kwargs):
        return None

    def load(self, *args, **kwargs):
        raise AssertionError("um motor que nao existe nao carrega")


def _naive_selector(log_path=None, alive=None):
    """O ESCOLHEDOR ANTIGO -- a ultima linha do log, sem perguntar mais nada.

    Existe para ser mutante: se as arms do escolhedor nao ficarem VERMELHAS com
    este, nao medem a escolha da instancia (foi exactamente este comportamento
    que reprovou a app do dono, lendo o pid de uma largada de medicao morta).
    """
    launches = shell_launches(log_path)
    if not launches:
        return None, ""
    pid, _seg = launches[0]
    path = Path(log_path) if log_path else (ROOT / "_main" / "webview-run.log")
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return pid, ""
    return pid, text


def selector_arms(select):
    """As arms do ESCOLHEDOR, parametrizadas: `select` e' o que esta' a ser julgado."""
    fake = Path(tempfile.mkdtemp(prefix="load-shed-log-")) / "run.log"
    try:
        fake.write_text(
            "2026-11-01 10:00:00.000 sotto: SHELL_STARTUP_STAGE pid=111 stage=pre-lock\n"
            "2026-11-01 10:00:00.100 sotto: SINGLE_INSTANCE name=Local\\SottoShell"
            " already_running=false\n"
            "2026-11-01 10:00:01.500 sotto: LOAD_SHEDDING_STARTED interval_s=5 canal=shed\n"
            "2026-11-01 10:05:00.000 sotto: SHELL_STARTUP_STAGE pid=222 stage=pre-lock\n"
            "2026-11-01 10:05:00.100 sotto: SINGLE_INSTANCE name=Local\\SottoShell"
            " already_running=false\n"
            "2026-11-01 10:05:00.200 sotto: SHELL_ARGS --selftest --no-worker\n",
            encoding="utf-8")
        vivo = lambda p: str(p) == "111"                         # noqa: E731
        escolhido, texto = select(fake, alive=vivo)
        add(escolhido == "111",
            "com a viva por baixo de uma medicao, escolhe a VIVA",
            "escolheu=%s (a ultima linha do log e' a 222)" % (escolhido or "-"))
        add("LOAD_SHEDDING_STARTED" in texto,
            "e o texto escolhido chega ao `LOAD_SHEDDING_STARTED` (a cauda, nao"
            " um segmento cortado pela largada seguinte)")
        add(shell_launches(fake)[0][0] == "222",
            "o log sintetico tem mesmo o defeito: a ultima linha e' a medicao 222")
        add(select(fake, alive=lambda _p: False) == (None, ""),
            "sem nenhuma viva, o escolhedor devolve NADA (arm sem sujeito, nao"
            " um veredicto sobre uma instancia fantasma)")
    finally:
        shutil.rmtree(fake.parent, ignore_errors=True)


# ── ARMs 11 a 13: a ACCAO, a FILA EM DISCO e o EXECUTOR que cede ─────────────
# ORDEM DO DONO (2026-11-03): *"os modelos entram e saem conforme a carga do
# sistema, e o audio nao processado e' processado sozinho quando a carga
# liberta -- SEM NUNCA TRAVAR A MAQUINA DO DONO"*. As arms abaixo medem as tres
# metades dessa ordem com o codigo REAL (o `LoadAction`, o `BatchQueue` e o
# `BatchExecutor`, importados do repo), nunca com uma copia do comentario.


class _FakeProbe:
    """Uma sequencia de leituras `(commit, cpu)` -- uma NOVA por chamada."""

    def __init__(self, seq=((90.0, 10.0),)):
        self.seq = list(seq)
        self.i = 0

    def sample(self):
        commit, cpu = self.seq[min(self.i, len(self.seq) - 1)]
        self.i += 1
        return float(commit), float(cpu), True


def _action(ls, seq, log=None, armed=True, samples=None, publish=None,
            live=False, dwell_s=0.0, floor_s=None):
    """Um `LoadAction` com prova (`probe`), relogio e publicado falsos.

    `calls["publish"]` e' quantas vezes o FICHEIRO foi escrito -- o que a accao
    faz de facto, agora que o lever e' o modo e nao a vida do processo.
    """
    calls = {"publish": 0, "levels": []}

    def writer(level=None):
        calls["publish"] += 1
        calls["levels"].append(level if level is not None else act.published)
        return True if publish is None else publish()

    kwargs = {}
    if samples is not None:
        kwargs["samples"] = samples
    # `live=False` e' o caso em que a DECISAO aparece no ficheiro: o motor ao
    # vivo esta' desligado pelo dono, por isso nao ha' nada a proteger dele. Com
    # `live=True` o unico valor publicavel e' `leve` (regra A), medido em ARM 16.
    floor = (ls.ACTION_FLOOR_S if armed else 0.0) if floor_s is None else float(floor_s)
    act = ls.LoadAction(state=ls.LoadShedding(floor_s=floor),
                        publish=writer,
                        log_fn=(log.append if log is not None else (lambda _m: None)),
                        probe=_FakeProbe(seq), armed=armed,
                        live_fn=(live if callable(live) else (lambda: live)),
                        dwell_s=dwell_s, **kwargs)
    return act, calls


def arms_action(module_path: Path) -> None:
    print("\nARM 11 -- a ACCAO: o nivel ARMA o MODO, armada por omissao, com PISO,"
          " HISTERESE e SUSTENTACAO")
    ls = load(module_path)
    add(hasattr(ls, "LoadAction") and hasattr(ls, "open_action"),
        "o modulo tem a accao (`LoadAction`/`open_action`)")
    add(ls.ACTION_ARMED_DEFAULT is True,
        "a accao e' ARMADA por omissao (a ordem de 2026-11-03)",
        "ACTION_ARMED_DEFAULT=%r" % (ls.ACTION_ARMED_DEFAULT,))
    add(ls.action_armed("0") is False and ls.action_armed("off") is False,
        "`SOTTO_LOAD_SHED_ACT=0` desarma a accao (para as corridas de medicao)")
    add(ls.action_armed("1") is True and ls.action_armed("") is True,
        "e um valor que nao se reconhece NAO desarma")
    add(ls.ACTION_FLOOR_S >= 180.0,
        "PISO entre duas DESCIDAS de pelo menos 180 s",
        "floor_s=%.0f" % ls.ACTION_FLOOR_S)
    add(ls.ACTION_SAMPLES >= 2,
        "uma accao precisa de leituras SUSTIDAS", "samples=%d" % ls.ACTION_SAMPLES)
    # O LEVER NAO MATA O PROCESSO (medido 2026-11-03: o audio so' existe DENTRO do
    # worker -- matar o worker para a captura no intervalo).
    source = module_path.read_text(encoding="utf-8")
    add("bridge.stop" not in source and "TerminateProcess" not in source,
        "a accao NAO mata o worker: o lever e' o modo que ele ja' obedece (`shed`)")
    add("LOAD_ACTION_PUBLISHED" in source,
        "e a accao escreve o nivel com o numero que o disparou")

    # (a) SUBIR e' imediato: uma maquina a 95 % nao espera por sustentacao.
    logs: list = []
    acted, calls = _action(ls, [(95.0, 20.0)], log=logs)
    state = acted.tick(now=0.0)
    add(calls["publish"] == 1 and acted.published == "muito-alta",
        "uma leitura a 95 % PUBLICA `muito-alta` de imediato (subir nao espera)",
        "published=%s action=%s" % (acted.published, state["action"]))
    add(any("LOAD_ACTION_PUBLISHED" in line for line in logs),
        "e a publicacao fica no log, com os motores que o worker vai largar",
        next((l for l in logs if "LOAD_ACTION_PUBLISHED" in l), ""))
    add(state["engines"] == {'nemotron': False, 'parakeet': False},
        "`muito-alta` e' o modo em que NENHUM modelo corre (a captura continua)")

    # (b) DESCER espera: uma leitura calma nao devolve os modelos.
    one, calls_one = _action(ls, [(10.0, 5.0)])
    one.state = ls.LoadShedding("muito-alta", floor_s=ls.ACTION_FLOOR_S)
    one.published = "muito-alta"
    state = one.tick(now=0.0)
    add(calls_one["publish"] == 0,
        "UMA leitura calma NAO devolve os modelos (nem publica nada)",
        "action=%s level=%s" % (state["action"], state["level"]))
    add(state["held"] >= 1, "e a espera fica contada (`held`), nao silenciosa",
        "held=%d" % state["held"])

    # (c) O PISO: com o nivel ja' descido, a publicacao da descida espera 180 s
    # desde a ultima DESCIDA -- e o nivel SEgura-se no alto (o numero que o
    # ficheiro diz e o numero que a decisao tomou sao o MESMO).
    floored, calls_floor = _action(ls, [(8.0, 5.0)] * 12)
    floored.state = ls.LoadShedding("muito-alta", floor_s=ls.ACTION_FLOOR_S)
    floored.state.last_descent_at = 1000.0
    floored.published = "muito-alta"
    levels = []
    for i in range(1, 20):
        levels.append(floored.tick(now=1000.0 + i * 5.0)["level"])
    add(set(levels) == {"muito-alta"} or "alta" in levels,
        "com o piso a correr o nivel NAO despenca de muito-alta para leve",
        str(sorted(set(levels))))
    add(floored.state.held_by_floor >= 1,
        "e o piso conta as descidas que segurou",
        "held_by_floor=%d" % floored.state.held_by_floor)
    # Passado o piso, a descida acontece -- uma vez, um degrau.
    for i in range(20, 40):
        floored.tick(now=1000.0 + i * 5.0)
    add(floored.state.level in ("alta", "leve") and floored.published == floored.state.level,
        "passado o piso o nivel desce e a publicacao acompanha",
        "level=%s published=%s" % (floored.state.level, floored.published))

    # (d) HISTERESE: a banda RESUME..HIGH segura o nivel (nem desce nem oscila).
    band, calls_band = _action(ls, [(88.5, 10.0), (85.0, 10.0)] * 10, samples=3)
    band_levels = [band.tick(now=i * 5.0)["published"] for i in range(20)]
    add(set(band_levels[-10:]) == {"alta"},
        "a banda RESUME..HIGH segura o nivel publicado em `alta` (nao oscila)",
        str(sorted(set(band_levels))))
    dip, calls_dip = _action(ls, [(88.5, 10.0), (10.0, 5.0), (85.0, 10.0)] * 6)
    for i in range(18):
        dip.tick(now=i * 5.0)
    # O QUE SE MEDE SAO AS PUBLICACOES, nao o valor inicial do ficheiro: a
    # primeira leitura ja' e' `alta` e o `leve` que ali aparece e' o nivel de
    # ARRANQUE, nao uma publicacao.
    add(set(calls_dip["levels"]) <= {"alta"},
        "uma amostra calma isolada nao PUBLICA `leve` (e nao ha' triturador)",
        str(calls_dip["levels"]))

    # (e) DESARMADA: mede, nao força.
    off, calls_off = _action(ls, [(99.0, 99.0)], armed=False)
    off_levels = [off.tick(now=i * 5.0)["published"] for i in range(5)]
    add(off.published == "muito-alta" and off.publications >= 1,
        "desarmada, o nivel SEGUE para o ficheiro (e' a medicao) e nunca volta atras"
        " por accao", "published=%s publications=%d" % (off.published, off.publications))

    # (f) O LACO DO MONITOR NAO ARRANCA: um so' escritor do estado.
    shell_source = (module_path.parent / "sotto_webview.py").read_text(encoding="utf-8")
    add("_load_shedding.start()" not in shell_source,
        "o laco proprio do monitor NAO e' arrancado (dois escritores no mesmo"
        " estado somariam amostras e as confirmacoes chegariam a metade do tempo)")
    add("open_action(\n                    self, monitor=monitor, log_fn=log)" in shell_source
        or "monitor=monitor" in shell_source,
        "a shell chama `open_action(self, monitor=monitor, log_fn=log)` -- uma funcao")
    add("LOAD_ACTION_STARTED" in shell_source and "LOAD_ACTION_LOG_FAILED" in shell_source,
        "e o arranque da accao deixa a linha `LOAD_ACTION_STARTED` (com guard proprio)")
    add("LOAD_SHEDDING_START_FAILED" in shell_source,
        "o guard do arranque continua a existir e a nao engolir o log")


def arms_queue(batch_path: Path, tmp: Path) -> None:
    print("\nARM 12 -- a FILA EM DISCO sobrevive a um restart")
    batch = load(batch_path)
    source = batch_path.read_text(encoding="utf-8")
    add("os.replace" in source,
        "a escrita e' ATOMICA (`.tmp` + `os.replace`), nao um manifesto truncavel")
    add("sounddevice" not in source and "PaStream" not in source,
        "o driver NAO abre dispositivo de audio (nenhum caminho de captura)")
    add(batch.BELOW_NORMAL_PRIORITY_CLASS == 0x00004000
        and batch.CREATE_NO_WINDOW == 0x08000000,
        "o filho arranca com prioridade BELOW_NORMAL e sem janela",
        "0x%08x | 0x%08x" % (batch.BELOW_NORMAL_PRIORITY_CLASS,
                             batch.CREATE_NO_WINDOW))
    add(batch.MAX_ATTEMPTS >= 2, "um bloco que falha e' tentado mais de uma vez",
        "max_attempts=%d" % batch.MAX_ATTEMPTS)
    # A FILA VIVE ONDE O DONO DISSE: medido 2026-11-03, `TMPDIR` esta' vazio e o
    # `gettempdir()` devolve `G:\Temp` -- sem o candidato `I:\cc-tmp` a fila ia
    # para o temp do sistema em vez do scratch do dono.
    os.environ.pop('SOTTO_BATCH_QUEUE_DIR', None)
    resolved = batch.queue_dir()
    add(batch.QUEUE_DIRNAME in resolved and resolved != os.path.join(
            tempfile.gettempdir(), batch.QUEUE_DIRNAME),
        "o directorio da fila cai no scratch do dono quando `TMPDIR` esta' vazio",
        resolved)
    os.environ['SOTTO_BATCH_QUEUE_DIR'] = str(tmp / "env-queue")
    add(batch.queue_dir() == str(tmp / "env-queue"),
        "`SOTTO_BATCH_QUEUE_DIR` manda sobre tudo", batch.queue_dir())
    os.environ.pop('SOTTO_BATCH_QUEUE_DIR', None)

    root = tmp / "queue"
    q1 = batch.BatchQueue(path=str(root), log_fn=lambda _m: None)
    raw_a = b"\x00\x00\x80\x3f" * 1600          # 0,1 s de float32
    raw_b = b"\x00\x00\x00\xbf" * 3200          # 0,2 s
    first = q1.enqueue_f32(raw_a, source="oracle-a", now=1000.0)
    second = q1.enqueue_f32(raw_b, source="oracle-b", now=1001.0)
    add(first is not None and second is not None and q1.stats()["queued"] == 2,
        "dois blocos entram na fila", str(q1.stats()["queued"]))
    add(first["samples"] == 1600 and abs(first["seconds"] - 0.1) < 1e-9,
        "o bloco leva os samples e os segundos do audio que tem",
        "samples=%s seconds=%s" % (first["samples"], first["seconds"]))
    add(q1.enqueue_f32(b"\x00\x01\x02", source="lixo") is None,
        "um payload que nao e' float32 e' RECUSADO (nao vira audio inventado)")

    # RESTART: outra instancia sobre o MESMO directorio. O bloco que estava
    # `inflight` (o processo morreu a meio) volta a `queued`.
    q1.claim(str(first["id"]))
    q2 = batch.BatchQueue(path=str(root), log_fn=lambda _m: None)
    pending = q2.pending()
    add(len(pending) == 2,
        "uma instancia NOVA ve' os dois blocos (a fila e' o disco)",
        "pending=%d" % len(pending))
    add(q2.recovered >= 1 and pending[0]["id"] == first["id"],
        "o `inflight` de um processo morto volta a `queued` e mantem a ORDEM",
        "recovered=%d first=%s" % (q2.recovered, pending[0]["id"][:20]))
    with open(q2.payload_path(str(first["id"])), "rb") as handle:
        survived = handle.read()
    add(survived == raw_a,
        "os bytes do audio sao os mesmos (nada foi quantizado nem cortado)",
        "bytes=%d" % len(survived))

    # UM MANIFESTO SEM AUDIO NAO E' UM BLOCO: e' um registo sem sujeito.
    orphan_id = "0000000000001-1-9999"
    (root / (orphan_id + ".json")).write_text(
        json.dumps({"id": orphan_id, "state": "queued", "samples": 10,
                    "created": 1.0}), encoding="utf-8")
    (root / "payload-abandonado.f32.tmp").write_bytes(b"\x00" * 8)
    q3 = batch.BatchQueue(path=str(root), log_fn=lambda _m: None)
    add(q3.orphans >= 1 and len(q3.pending()) == 2,
        "manifesto sem payload e `.tmp` abandonado nao entram na fila",
        "orphans=%d pending=%d" % (q3.orphans, len(q3.pending())))
    add(not (root / "payload-abandonado.f32.tmp").exists(),
        "e o `.tmp` de uma escrita interrompida e' limpo")

    done = q3.mark_done(str(second["id"]), text="o audio que esperou virou texto")
    add(done["state"] == "done"
        and json.loads((root / (str(second["id"]) + ".json")).read_text(encoding="utf-8"))["text"]
        == "o audio que esperou virou texto",
        "o bloco transcrito fica `done` com o TEXTO no manifesto (durável)")

    # ADOPCAO: o spool de um worker MORTO vai para a fila; o de um VIVO nao.
    dead_dir = tmp / ("sotto-pending-audio-999999")
    dead_dir.mkdir()
    spool = dead_dir / "pending-999999-0001.f32"
    spool.write_bytes(raw_a)
    old = _time.time() - 60
    os.utime(spool, (old, old))
    live_dir = tmp / ("sotto-pending-audio-%d" % os.getpid())
    live_dir.mkdir()
    live_spool = live_dir / f"pending-{os.getpid()}-0001.f32"
    live_spool.write_bytes(raw_b)
    os.utime(live_spool, (old, old))
    adopted = q3.adopt_dead_spools(roots=[dead_dir, live_dir])
    sources = [e["source"] for e in q3.pending()]
    add(adopted == 1 and any("sotto-pending-audio-999999" in s for s in sources),
        "o spool de um worker MORTO e' adoptado para a fila", "adopted=%d" % adopted)
    add(not any(str(os.getpid()) == s.split("-")[-1] for s in sources),
        "e o de um worker VIVO nao (senao a mesma frase entrava duas vezes)")
    add(q3.adopt_dead_spools(roots=[dead_dir]) == 0,
        "a segunda leitura nao duplica o mesmo ficheiro (indice `adopted.json`)")
    add(spool.exists(),
        "a adopcao COPIA: o spool do worker nao e' apagado por outro modulo")


def arms_engine(batch_path: Path) -> None:
    """ARM 14 -- o lote da fila e' o MESMO motor que o worker ja' usa.

    A ORDEM DO ASSENTO PRINCIPAL (2026-11-03): *"o batch ja' existe e e' o
    parakete... nao escreva um segundo transcritor"*. Medido nesta maquina: o
    `worker/redux_batch.py` (o runner TERNARIO) nao tem checkpoint --
    `worker/models/parakeet-redux-ternary` nao existe --, e o motor que o worker
    REALMENTE usa e' o ONNX int4 via `redux_live.load_backend('onnx', ...)`
    (`worker/engine_policy.py`, `ParakeetEngine`). O driver da fila chama
    EXACTAMENTE esse `load_backend` com o MESMO directorio; nao ha' motor novo,
    nem pesos novos, nem uma segunda forma de ler o audio.
    """
    print("\nARM 14 -- o lote da fila usa o MESMO backend do worker (nao um segundo)")
    source = batch_path.read_text(encoding="utf-8")
    add("redux_live" in source and "load_backend" in source,
        "o driver carrega o backend de `redux_live.load_backend` (o do worker)")
    add("'onnx'" in source and "DEFAULT_ONNX_DIR" in source,
        "e pede o export ONNX int4 por omissao (nao inventa caminho de pesos)")
    add("ParakeetTdtRuntime" not in source and "onnxruntime" not in source,
        "o driver NAO constroi um runtime proprio (nenhum motor embutido)")
    worker_dir = batch_path.parent.parent.parent / "worker"
    try:
        sys.path.insert(0, str(worker_dir))
        if str(worker_dir) not in sys.path:
            raise ImportError(worker_dir)
        import importlib

        live = importlib.import_module("redux_live")
        switch = importlib.import_module("engine_switch")
        add(os.path.isdir(live.DEFAULT_ONNX_DIR),
            "o checkpoint ONNX que os dois abrem existe no disco",
            str(live.DEFAULT_ONNX_DIR))
        add(os.path.normcase(os.path.join(str(worker_dir), switch.REDUX_LIVE_ONNX_RELPATH))
            == os.path.normcase(live.DEFAULT_ONNX_DIR),
            "e o directorio do driver e' o MESMO que o interruptor do worker resolve")
        ternary = os.path.join(str(worker_dir), "models", "parakeet-redux-ternary")
        add(not os.path.isdir(ternary),
            "o runner TERNARIO (`redux_batch.py`) nao tem checkpoint nesta maquina"
            " -- escolhe-lo seria um caminho que nunca corre",
            ternary)
    except Exception as exc:                                     # noqa: BLE001
        add(False, "os modulos do worker importam para medir o motor", repr(exc))


class _FakeChild:
    """Um filho que nunca acaba -- ate' ser morto (o caso do ceder)."""

    #: Tecto de polls: um mutante que APAGA o ceder deixaria o `step()` num laco
    #: infinito (o braco nunca voltaria). Depois de `max_polls` o filho "acaba"
    #: com rc=-9, e o braco fica com um resultado (errado, como deve) em vez de
    #: ficar pendurado.
    max_polls = 8

    def __init__(self, out="", rc=0, hang=False, on_communicate=None):
        self.out = out
        self.err = ""
        self.returncode = rc
        self.hang = hang
        self.killed = False
        self.on_communicate = on_communicate
        self.polls = 0

    def communicate(self, timeout=None):
        self.polls += 1
        if self.on_communicate is not None:
            self.on_communicate(self.polls)
        if self.hang and not self.killed and self.polls <= self.max_polls:
            raise _TimeExpired("fake-child", timeout)
        if self.hang and not self.killed:
            self.returncode = self.returncode if self.returncode else -9
        return self.out, self.err

    def kill(self):
        self.killed = True
        self.returncode = -9


import subprocess as _subprocess

_TimeExpired = _subprocess.TimeoutExpired


def arms_executor(batch_path: Path, tmp: Path) -> None:
    print("\nARM 13 -- o EXECUTOR corre com nada carregado e CEDE quando a carga sobe")
    batch = load(batch_path)
    root = tmp / "exec-queue"
    level = {"value": "muito-alta"}
    spawned: list = []
    children: list = []

    def fake_spawn(cmd):
        spawned.append(cmd)
        child = _FakeChild(out=json.dumps({"type": "caption", "text": "linha",
                                           "start": 0.0, "end": 0.1})
                           + "\n" + json.dumps({"type": "result", "text": "linha"}))
        children.append(child)
        return child

    ex = batch.BatchExecutor(queue=batch.BatchQueue(path=str(root),
                                                    log_fn=lambda _m: None),
                             log_fn=lambda _m: None,
                             level_fn=lambda: level["value"], spawn=fake_spawn,
                             child_poll_s=0.01, yield_backoff_s=0.0)
    raw = b"\x00\x00\x80\x3f" * 1600
    ex.queue.enqueue_f32(raw, source="oracle-exec", now=1000.0)
    add(ex.queue.stats()["queued"] == 1, "um bloco para transcrever na fila")

    state, detail = ex.step()
    add(state == "idle" and not spawned,
        "com a carga acima de `leve` o executor NAO arranca nada",
        "state=%s detail=%s spawned=%d" % (state, detail, len(spawned)))
    add(ex.allowed() is False, "`alta`/`muito-alta` nao sao nivel para o lote")

    level["value"] = "leve"
    state, detail = ex.step()
    add(state == "done" and ex.done == 1 and ex.queue.stats()["done"] == 1,
        "com a carga liberta o bloco e' transcrito e marcado `done`",
        "state=%s detail=%s" % (state, str(detail)[:40]))
    add(ex.queue.entries[0].get("text") == "linha",
        "e o texto transcrito fica no manifesto",
        repr(ex.queue.entries[0].get("text")))
    add(any("--transcribe" in " ".join(cmd) for cmd in spawned),
        "o filho e' o driver `--transcribe` (um ficheiro, sem dispositivo)")

    # O CEDER: a carga sobe a meio do bloco -> o filho e' morto e o bloco volta.
    level["value"] = "leve"
    entry = ex.queue.enqueue_f32(raw, source="oracle-yield", now=1002.0)
    hang_children: list = []

    def hang_spawn(cmd):
        child = _FakeChild(hang=True)
        hang_children.append(child)
        return child

    ex._spawn = hang_spawn
    ticks = {"n": 0}

    def rise(_polls):
        ticks["n"] += 1
        if ticks["n"] >= 2:
            level["value"] = "alta"

    hang_children = []
    ex.child_poll_s = 0.01
    ex.yield_backoff_s = 0.0

    def spawn_with_rise(cmd):
        child = _FakeChild(hang=True, on_communicate=rise)
        hang_children.append(child)
        return child

    ex._spawn = spawn_with_rise
    state, detail = ex.step()
    requeued = [e for e in ex.queue.entries if e["id"] == entry["id"]][0]
    add(state == "yield" and ex.yields == 1,
        "a carga a subir a meio do bloco faz o executor CEDER",
        "state=%s detail=%s yields=%d" % (state, detail, ex.yields))
    add(bool(hang_children) and hang_children[-1].killed,
        "e o processo do lote e' MORTO (nao fica a competir com o dono)")
    add(requeued["state"] == "queued" and int(requeued.get("attempts") or 0) == 0,
        "o bloco volta a fila e o ceder NAO conta como falha",
        "state=%s attempts=%s" % (requeued["state"], requeued.get("attempts")))
    add(ex.queue.stats()["pending_s"] > 0,
        "o audio continua na fila (nada foi deitado fora ao ceder)",
        "pending_s=%s" % ex.queue.stats()["pending_s"])

    # A PRIORIDADE, MEDIDA: um filho real arranca e o Windows diz-nos a classe.
    try:
        import psutil

        child = batch._spawn_below_normal([sys.executable, "-c", "import time; time.sleep(0.6)"])
        try:
            got = psutil.Process(child.pid).nice()
        finally:
            child.communicate(timeout=10)
        add(got == psutil.BELOW_NORMAL_PRIORITY_CLASS,
            "o filho REAL arranca com prioridade BELOW_NORMAL (medido com psutil)",
            "nice=%s" % got)
    except Exception as exc:                                     # noqa: BLE001
        add(False, "o filho REAL arranca com prioridade BELOW_NORMAL (medido)",
            "nao medido: %r" % (exc,))


def verdict(name: str) -> int:
    failed = [r for r in rows if not r[0]]
    print(f"\n{name} {'GREEN' if not failed else 'VERMELHO'} -- "
          f"arms={len(rows)} pass={len(rows) - len(failed)} fail={len(failed)}")
    return EXIT_PASS if not failed else EXIT_FAIL


def run(module_path: Path, shell_path: Path, batch_path: Path | None = None) -> int:
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
        "o log `LOAD_SHEDDING_STARTED` corre DEPOIS do `try` do ARRANQUE"
        " (linha %s contra o arranque na linha %s)" % (log_line, start_line))
    pid, seg = newest_shell_segment()
    add('LOAD_SHEDDING_START_FAILED' not in seg,
        "a INSTANCIA VIVA (pid %s) nao tem `LOAD_SHEDDING_START_FAILED`"
        % (pid or "nenhuma -- arm sem sujeito"))
    add('LOAD_SHEDDING_STARTED' in seg or pid is None,
        "a INSTANCIA VIVA (pid %s) registou `LOAD_SHEDDING_STARTED`"
        % (pid or "nenhuma -- arm sem sujeito"))

    # ARM 5b -- O ESCOLHEDOR JULGADO: a arm acima vale o que valer a escolha da
    # instancia, e essa escolha partiu-se a 2026-11-01 (o oraculo leu o pid de
    # uma largada de MEDICAO ja' morta e reprovou a app do dono). Um log
    # sintetico com a forma exacta do defeito -- uma medicao por cima da
    # instancia -- e' o que prova que o escolhedor prefere a viva.
    print("\nARM 5b -- o ESCOLHEDOR da largada: a viva, nunca a medicao por cima")
    selector_arms(newest_shell_segment)
    arms_channel(shell_path)
    load_tmp = Path(tempfile.mkdtemp(prefix="load-shed-load-"))
    try:
        arms_load(globals().get("WORKER", ROOT / "worker" / "sotto_worker.py"), load_tmp)
        # A RETOMA (ordem do dono, 2026-11-04): estacionar ja' era medido; estas
        # arms medem a BORDA -- carrega sozinho, uma vez, com a carga RELIDA.
        arms_resume(globals().get("WORKER", ROOT / "worker" / "sotto_worker.py"),
                    load_tmp)
        # A ACCAO, a FILA e o EXECUTOR (ordem do dono, 2026-11-03). O
        # `batch_queue.py` vive AO LADO do `load_shedding.py` que se esta' a
        # medir: numa corrida de mutante, e' a copia dele que corre.
        batch_path = batch_path or (module_path.parent / "batch_queue.py")
        add(batch_path.exists(), "o `batch_queue.py` da lane esta' no layout medido",
            str(batch_path))
        if batch_path.exists():
            arms_action(module_path)
            arms_queue(batch_path, load_tmp)
            arms_executor(batch_path, load_tmp)
            arms_engine(batch_path)
            arms_worker_channel(module_path)
            arms_live_gesture(load(module_path),
                              module_path.read_text(encoding="utf-8"))
            arms_anti_thrash(load(module_path))
    finally:
        shutil.rmtree(load_tmp, ignore_errors=True)
    # ARM 22 -- A SEGUNDA MEDIDA (2026-11-04): a CPU do sistema CHEGA a decisao.
    print("\nARM 22 -- a CPU do sistema entra na decisao (e nao so' o commit)")
    ls2 = load(module_path)
    seq = iter([(100, 200, 100), (150, 300, 150)])
    cpu = ls2.SystemCpu(reader=lambda: next(seq))
    first = cpu.sample()
    second = cpu.sample()
    add(first is None, "a PRIMEIRA amostra nao pede nada (nao ha delta)", repr(first))
    add(second == 66.7, "a segunda amostra e 66,7 % (100 de 150 ticks ocupados)",
        repr(second))
    add(ls2.level_for_load(40.0, 95.0) == 'alta',
        "commit 40 + cpu 95 -> alta (a CPU sozinha ja pede)",
        ls2.level_for_load(40.0, 95.0))
    add(ls2.level_for_load(40.0, 99.0) == 'muito-alta',
        'commit 40 + cpu 99 -> muito-alta', ls2.level_for_load(40.0, 99.0))
    add(ls2.level_for_load(40.0, None) == 'leve',
        'cpu ausente NAO inventa carga (o comportamento de antes)',
        ls2.level_for_load(40.0, None))
    state2 = ls2.LoadShedding()
    level, changed, why = state2.observe(40.0, cpu_pct=95.0)
    add((level, changed) == ('alta', True), 'observe() com cpu sobe para alta',
        '%s changed=%s' % (level, changed))
    add('cpu' in why.lower() or '95' in why, "a RAZAO nomeia a medida que decidiu", why)
    # -- a FIACAO: o monitor TEM de amostrar e passar, senao a arm acima mede
    #    uma funcao que ninguem chama (a classe de defeito que esta arm fecha).
    shell_src = Path(shell_path).read_text(encoding='utf-8')
    add('self.step(reading, self._cpu.sample())' in shell_src,
        'LoadSheddingMonitor.run() AMOSTRA a CPU e passa-a ao step')
    add('self.state.observe(reading, cpu_pct=cpu_pct)' in shell_src,
        'step() entrega a CPU ao observe (e nao a descarta)')
    add("cpu_pct=%s" in shell_src,
        'o log publica a CPU que decidiu (o numero, nao o adjectivo)')

    return verdict("LOAD-SHEDDING")


def arms_live_gesture(ls, src=None) -> None:
    """ARM 16 -- a accao NUNCA larga o motor AO VIVO (o nemotron).

    Medido na app do dono (`_main/webview-run.log`, 2026-11-03): quatro niveis
    publicados em ~15 s, cada par a mandar largar/recarregar o nemotron, e a
    legenda ao vivo a morrer com uma maquina a 92,6 % de CPU. Com o ao vivo
    ligado (`_caption_wanted`), o unico valor que este laco pode escrever no
    `shed` e' `leve`: o nemotron e' do GESTO do dono, nao de um limiar.
    """
    print("\nARM 16 -- o motor ao vivo e' do GESTO, nao do limiar")
    src = src or ""
    add("monitor.state = view" in src,
        "o shell le' o nivel PUBLICADO (`shedding_level` -> `monitor.state.level`)")
    add("getattr(shell, '_caption_wanted', True)" in src,
        "e o sinal do ao vivo e' o GESTO do dono (`_caption_wanted`), nao o limiar")
    add("LOAD_ACTION_LIVE_HELD" in src,
        "e a decisao contrariada fica no log (uma vez por minuto)")
    logs = []
    act, calls = _action(ls, [(99.0, 99.0)], log=logs, live=True, samples=3)
    for i in range(3):
        act.tick(now=i * 5.0)
    add(act.state.level == "muito-alta" and calls["publish"] == 0,
        "com o ao vivo LIGADO, uma maquina a 99 % nao publica NADA (fica `leve`)",
        "decision=%s published=%s escritas=%d"
        % (act.state.level, act.published, calls["publish"]))
    add(act.target() == "leve" and act.published == "leve",
        "o alvo publicado e' `leve` enquanto o ao vivo estiver ligado",
        "target=%s published=%s" % (act.target(), act.published))
    add(not any("PUBLISHED" in m and "engines=parakeet" in m for m in logs),
        "e o log nao anuncia uma largada que nunca aconteceu",
        str([m[:60] for m in logs if "PUBLISHED" in m]) or "nenhum PUBLISHED")

    # O GESTO MANDA NOS DOIS SENTIDOS: desligar o ao vivo devolve o limiar a
    # accao, e VOLTAR A LIGAR-LO devolve o `leve` ao ficheiro DE IMEDIATO
    # (mesmo dentro do dwell: isto nao carrega modelo nenhum, e' desligar a
    # politica para o produto voltar).
    state = {"live": False}
    logs2 = []
    act2, calls2 = _action(ls, [(99.0, 99.0)], live=lambda: state["live"],
                           samples=3, dwell_s=60.0, log=logs2)
    for i in range(3):
        act2.tick(now=i * 5.0)
    add(act2.published == "muito-alta",
        "com o ao vivo DESLIGADO o limiar volta a publicar o nivel decidido",
        "published=%s" % act2.published)
    add(any("live=por-limiar" in m for m in logs2),
        "e ai o log diz que quem decidiu foi o LIMIAR",
        next((m for m in logs2 if "PUBLISHED" in m), "-")[:110])
    state["live"] = True
    act2.tick(now=15.0)
    add(act2.published == "leve",
        "e LIGAR o ao vivo publica `leve` no tick seguinte, dentro do dwell",
        "published=%s since=%.0fs" % (act2.published,
                                      act2.as_dict(now=15.0)["since_publish_s"] or -1))
    add(any("live=nemotron-por-gesto" in m for m in logs2),
        "e o log diz QUEM decidiu (o gesto), em vez de mentir sobre o limiar",
        next((m for m in logs2 if "live=nemotron-por-gesto" in m), "-")[:110])

    # A VISTA: o shell le' o publicado, a decisao fica no estado real.
    real = ls.LoadShedding()
    view = ls.PublishedView(real)
    real.observe(99.0, 5.0)
    view.set_published("leve")
    add(view.level == "leve" and real.level == "muito-alta",
        "o shell le' o PUBLICADO (`PublishedView`) e a decisao fica no estado",
        "view=%s real=%s" % (view.level, real.level))
    add(view.engines() == real.engines(),
        "e a vista nao esconde mais nada do estado (so' o nivel)",
        str(view.stopped()))


def arms_anti_thrash(ls) -> None:
    """ARM 17 -- o ANTI-TRITURADOR: dwell nas duas direccoes, subida sustentada.

    A sequencia que o assento principal mediu na app viva (88/60/88/60 em ~15 s)
    tem de produzir NO MAXIMO UMA publicacao, e subir para `alta` tem de esperar
    as mesmas amostras sustentadas que descer. Sem isto o que o dono ve e'
    *"o modelo loading ta toda hora saind out de load"*.
    """
    print("\nARM 17 -- anti-triturar: dwell de %.0f s e subida sustentada"
          % ls.MIN_DWELL_S)
    add(ls.MIN_DWELL_S >= 60.0, "o dwell minimo entre duas publicacoes e' >= 60 s",
        "MIN_DWELL_S=%.1f" % ls.MIN_DWELL_S)

    # A SEQUENCIA MEDIDA, 4 leituras em 15 s (ticks de 3,75 s).
    seq = [(88.0, 10.0), (60.0, 10.0), (88.0, 10.0), (60.0, 10.0)]
    act, calls = _action(ls, seq, samples=3)
    for i in range(4):
        act.tick(now=i * 3.75)
    add(act.publications <= 1,
        "a sequencia 88/60/88/60 em 15 s publica NO MAXIMO UMA vez",
        "publications=%d levels=%s" % (act.publications, calls["levels"]))
    add(act.as_dict()["action"] != "published"
        or act.last_publish_at is not None,
        "e o buffer nao escreve duas vezes o mesmo nivel", str(calls["levels"]))

    # SUBIR PARA `alta` NAO E' IMEDIATO: a primeira leitura de 92 % nao publica.
    spike, calls_spike = _action(ls, [(92.0, 10.0)] * 6, samples=3)
    spike.tick(now=0.0)
    add(spike.publications == 0,
        "a PRIMEIRA leitura a 92 % nao publica `alta` (subir nao e' imediato)",
        "publications=%d published=%s" % (spike.publications, spike.published))
    for i in range(1, 3):
        spike.tick(now=i * 3.75)
    add(spike.publications == 1 and spike.published == "alta",
        "e ao fim das MESMAS %d amostras sustentadas ele publica" % 3,
        "publications=%d published=%s" % (spike.publications, spike.published))

    # OSCILACAO LONGA: nenhuma publicacao a menos de MIN_DWELL_S da anterior.
    long_seq = ([(60.0, 10.0)] * 6 + [(90.0, 10.0)] * 6) * 5
    # `floor_s=0`: aqui mede-se o DWELL (o piso das descidas tem o seu proprio
    # braco, e o relogio do piso e' o real -- injecta-lo aqui so' mediria o
    # oraculo).
    osc, calls_osc = _action(ls, long_seq, samples=3, dwell_s=ls.MIN_DWELL_S,
                             floor_s=0.0)
    stamps = []
    for i in range(len(long_seq)):
        before = osc.publications
        osc.tick(now=i * 5.0)
        if osc.publications != before:
            stamps.append(i * 5.0)
    gaps = [b - a for a, b in zip(stamps, stamps[1:])]
    add(all(g >= ls.MIN_DWELL_S for g in gaps),
        "duas publicacoes nunca ficam a menos de MIN_DWELL_S uma da outra",
        "publicacoes=%d folgas=%s" % (len(stamps), [round(g) for g in gaps]))
    add(len(stamps) >= 2,
        "e a oscilacao real continua a publicar (o dwell nao e' um cadeado)",
        "publicacoes em 300 s=%d" % len(stamps))

    # `muito-alta` E' A EXCEPCAO: e' a maquina a sufocar.
    suff, calls_suff = _action(ls, [(99.0, 10.0)], samples=3)
    suff.tick(now=0.0)
    add(suff.published == "muito-alta",
        "`muito-alta` sobe na PRIMEIRA leitura (a maquina esta' a sufocar)",
        "published=%s after=%d leituras" % (suff.published, 1))


def arms_worker_channel(module_path: Path) -> None:
    """ARM 15 -- o nivel so' vale se o WORKER o ler: o canal fica armado.

    Sem `SOTTO_REDUX_WHEN_HIDDEN=1` o worker constroi `switch = None` e o `shed`
    que este laco publica e' um numero que ninguem obedece. O arranque da accao
    escreve a variavel (o shell monta o ambiente do filho com `dict(os.environ)`),
    e NAO a escreve quando a accao esta desarmada nem quando o operador ja' deu
    um valor.
    """
    print("\nARM 15 -- o canal do worker e' armado pelo arranque da ACCAO")
    src = module_path.read_text(encoding="utf-8")
    add("SOTTO_REDUX_WHEN_HIDDEN" in src,
        "o modulo conhece o canal que o worker le'",
        "SOTTO_REDUX_WHEN_HIDDEN")
    add("def _arm_worker_channel" in src,
        "e tem uma funcao que o arma no arranque")
    add("self._arm_worker_channel()" in src,
        "e o `LoadGuard.start()` chama-a ANTES de arrancar o laco")
    saved = os.environ.pop("SOTTO_REDUX_WHEN_HIDDEN", None)
    try:
        module = load(module_path)
        class _S:
            shedding_level = "leve"
            _caption_wanted = False
            def publish_shedding_level(self, _level):
                return True
        lines = []
        guard = module.open_action(_S(), executor=False,
                                   log_fn=lambda m: lines.append(m))
        add(os.environ.get("SOTTO_REDUX_WHEN_HIDDEN") == "1",
            "a accao ARMADA poe SOTTO_REDUX_WHEN_HIDDEN=1 no ambiente",
            repr(os.environ.get("SOTTO_REDUX_WHEN_HIDDEN")))
        add(any("LOAD_ACTION_WORKER_CHANNEL" in m for m in lines),
            "e diz no log porque' o fez",
            " | ".join(lines[-1:]))
        add(guard.action.as_dict().get("worker_channel") == "1",
            "o estado relata o canal armado",
            repr(guard.action.as_dict().get("worker_channel")))
        os.environ.pop("SOTTO_REDUX_WHEN_HIDDEN", None)
        # O OPERADOR MANDA: um valor ja' presente nao e' reescrito.
        os.environ["SOTTO_REDUX_WHEN_HIDDEN"] = "0"
        lines2 = []
        module.open_action(_S(), executor=False,
                           log_fn=lambda m: lines2.append(m))
        add(os.environ.get("SOTTO_REDUX_WHEN_HIDDEN") == "0",
            "e um valor do OPERADOR nao e' reescrito",
            repr(os.environ.get("SOTTO_REDUX_WHEN_HIDDEN")))
        add(any("source=env" in m for m in lines2),
            "e o log diz que o canal veio do ambiente",
            " | ".join(lines2[-1:]))
        # DESARMADA: nao arma nada.
        os.environ.pop("SOTTO_REDUX_WHEN_HIDDEN", None)
        lines3 = []
        saved_act = os.environ.get("SOTTO_LOAD_SHED_ACT")
        os.environ["SOTTO_LOAD_SHED_ACT"] = "0"
        try:
            module.open_action(_S(), executor=False,
                               log_fn=lambda m: lines3.append(m))
        finally:
            if saved_act is None:
                os.environ.pop("SOTTO_LOAD_SHED_ACT", None)
            else:
                os.environ["SOTTO_LOAD_SHED_ACT"] = saved_act
        add(os.environ.get("SOTTO_REDUX_WHEN_HIDDEN") is None,
            "a accao DESARMADA nao arma o worker",
            repr(os.environ.get("SOTTO_REDUX_WHEN_HIDDEN")))
        add(any("armed=false" in m for m in lines3),
            "e o log diz que a accao esta' desarmada",
            " | ".join(lines3[-1:]))
    finally:
        if saved is None:
            os.environ.pop("SOTTO_REDUX_WHEN_HIDDEN", None)
        else:
            os.environ["SOTTO_REDUX_WHEN_HIDDEN"] = saved


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
        rc = run(copy / "load_shedding.py", copy / "sotto_webview.py", BATCH)
        if rc == EXIT_FAIL:
            print("\nNEG-ARM PASS -- RED as designed: o mutante derruba o oraculo")
            return EXIT_FAIL
        print("\nNEG-ARM FAIL -- o oraculo NAO ve a tabela trocada")
        return EXIT_PASS
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def neg_arm_cpu_wiring() -> int:
    """O mutante da FIACAO da CPU: o monitor volta a chamar `step(reading)`.

    Sem isto, a arm 22 mediria `SystemCpu` e `level_for_load` -- dois pedacos
    que ja' existiam -- e nao a ligacao que a 2026-11-04 faltava. O mutante e'
    o defeito exacto: amostrar a CPU e nao a entregar.
    """
    tmp = Path(tempfile.mkdtemp(prefix="load-shed-cpu-neg-"))
    try:
        copy = tmp / "app" / "webview"
        copy.mkdir(parents=True)
        shutil.copy2(MODULE, copy / "load_shedding.py")
        text = Path(SHELL).read_text(encoding='utf-8')
        mutant = text.replace('self.step(reading, self._cpu.sample())',
                              'self.step(reading)', 1)
        if mutant == text:
            print("NEG-ARM CPU: nao consegui mutar o alvo (o texto mudou)")
            return EXIT_PASS
        (copy / "sotto_webview.py").write_text(mutant, encoding='utf-8')
        print("NEG-ARM CPU: o monitor amostra a CPU e NAO a entrega")
        rc = run(copy / "load_shedding.py", copy / "sotto_webview.py", BATCH)
        if rc == EXIT_FAIL:
            print("\nNEG-ARM CPU PASS -- RED as designed")
            return EXIT_FAIL
        print("\nNEG-ARM CPU FAIL -- o oraculo NAO ve a CPU descartada")
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
        rc = run(copy / "load_shedding.py", copy / "sotto_webview.py", BATCH)
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
        # ESTA ARM PROVA O MECANISMO `hidden_after_s`, e desde 2026-11-03 ele
        # esta' DESLIGADO por omissao (o dono: o modelo fica sempre). A arm
        # liga-o de proposito; quem prova a omissao e' a ARM 12.
        unload_when_hidden=True,
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
        unload_when_hidden=True,
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


    # ARM 12 -- A VISAO NAO E' PRESSAO (ordem do dono, 2026-11-03, verbatim:
    # *"era pra ta com o modelo sempre. e so descarregar quando o pc precisa da
    # vram ou gpu em outros apps"*). Sem a bandeira, painel escondido + maquina
    # folgada tem de deixar o motor AO VIVO carregado: era isto que fazia o dono
    # ver `carregando modelo…` ao apertar Ctrl+Espaco com um video a tocar.
    print("\nARM 12 -- escondido e sem pressao: o motor ao vivo FICA carregado")
    logs3: list[str] = []
    eng3 = _FakeEngine()
    eng3.load()
    reader3 = _FakeReader(visible=False)
    probe3 = _FakeProbe([(8.0, 4.0)])
    s3 = sw.ReduxHiddenSwitch(
        True, reader3, str(tmp / "no-runner.py"), logs3.append,
        hidden_after_s=0.0, batch_interval_s=1.0, max_audio_s=1.0,
        engine=eng3, probe=probe3, spool_dir=str(tmp / "spool3"))
    modes = [s3.tick() for _ in range(5)]
    add(modes == ["stream"] * 5,
        "escondido desde t=0 com a maquina livre: o modo FICA `stream`",
        f"modes={modes} unload_when_hidden={s3.unload_when_hidden}")
    add((eng3.loaded, eng3.releases) == (True, 0),
        "e o modelo NAO foi largado nem uma vez",
        f"loaded={eng3.loaded} releases={eng3.releases}")

    # ARM 13 -- O ESTACIONAMENTO DA SHELL LARGA O MOTOR, NAO O PROCESSO
    # (2026-11-03): e' o pedido que substitui o `bridge.stop('external-captions')`,
    # que matava o worker e com ele o cliente WASAPI -- o audio do dono piscava.
    print("\nARM 13 -- park=captions -> batch, e o log nomeia o pedido")
    logs4: list[str] = []

    class _ParkReader(_FakeReader):
        def __init__(self, visible, park):
            super().__init__(visible)
            self._park_reason = park

        def park(self):
            return self._park_reason

    eng4 = _FakeEngine()
    eng4.load()
    s4 = sw.ReduxHiddenSwitch(
        True, _ParkReader(False, 'captions'), str(tmp / "no-runner.py"),
        logs4.append, hidden_after_s=0.0, batch_interval_s=1.0,
        max_audio_s=1.0, engine=eng4, probe=_FakeProbe([(8.0, 4.0)]),
        spool_dir=str(tmp / "spool4"))
    mode = s4.tick()
    add(mode == "batch", "park=captions -> batch (o ao vivo para, o parakeet fica)",
        f"mode={mode}")
    add(any("park=captions" in l for l in logs4),
        "e a linha nomeia o pedido da shell",
        next((l for l in logs4 if "REDUX_SHEDDING" in l), ""))
    s4.reader._park_reason = None
    mode2 = s4.tick()
    add(mode2 == "stream", "sem pedido, volta a `stream` (o motor recarrega sozinho)",
        f"mode={mode2}")


# ── ARMs 23 a 25: A RETOMA -- a carga liberta e o backlog entra SOZINHO ──────
# ORDEM DO DONO (2026-11-04), verbatim: *"modelos carregados dependendo da carga
# do sistema ou nao. quando carga liberar, carrega sozinho (NUNCA TRAVAR O PC DO
# USUARIO OU STUTTER) e processa qualquer audio nao processado, com o parakeet"*.
#
# A METADE QUE FALTAVA. Estacionar ja' existia (ARM 10: 96 % larga o motor) e o
# audio nunca se perde (ARM 9: 25 blocos, RAM -> disco, `dropped=0`). RETOMAR
# nao existia em sitio nenhum: `maybe_kick` so' corre em `mode == "batch"` e
# respeita o `batch_interval_s`, por isso o audio acumulado em `shed` que chegasse
# a `leve` (modo `stream`) ficava em espera ate' ao `stop()` do processo -- o dono
# recebia a transcricao quando fechasse a app. Estas arms medem a BORDA: o motor
# carrega sozinho UMA vez, com a carga RELIDA antes de carregar, e o N do backlog
# fica no log.
RESUME_BLOCKS = 25


def _parked_switch(sw, tmp: Path, name: str, seq, blocks=RESUME_BLOCKS):
    """Um interruptor REAL estacionado por carga, com `blocks` de audio a espera.

    O caminho e' o da app: `tick()` le' a carga medrada (o probe), larga o motor
    em `muito-alta`, e `add_audio` poe os blocos na `PendingAudio` (RAM -> disco).
    Devolve `(switch, engine, logs, probe)`.
    """
    import numpy as np

    logs: list[str] = []
    eng = _FakeEngine()
    probe = _FakeProbe(seq)
    # O `LOAD_RESUME`/`LOAD_RESUME_HELD` sao escritos pelo `err` do worker (o
    # canal de stderr), nao pelo log do interruptor: sem esta troca a arm
    # julgaria uma linha que nunca chega a lista que ela le'. E' o mesmo `err`
    # que `_resume_gate` recebe como `log_fn`.
    sw.err = logs.append
    s = sw.ReduxHiddenSwitch(
        True, _FakeReader(visible=False), str(tmp / "no-runner.py"),
        logs.append, hidden_after_s=0.0, batch_interval_s=1.0, max_audio_s=1.0,
        engine=eng, probe=probe, spool_dir=str(tmp / ("spool-" + name)))
    add(s.tick() == "shed", "a maquina carregada estaciona o motor (mode=shed)",
        f"level={s._shed} armed={s.armed}")
    for _i in range(blocks):
        s.add_audio(np.full(1600, 0.2, dtype=np.float32))
    held = s._pending_counts()
    add(held["held_blocks"] == blocks and held["dropped"] == 0,
        f"os {blocks} blocos ficam todos a espera (nenhum deitado fora)",
        f"held={held['held_blocks']} dropped={held['dropped']}")
    return s, eng, logs, probe


def _descend(sw, s, gate, ticks=12):
    """Corre a BORDA como o laco do audio corre: `tick` e depois a retoma."""
    outs = []
    for _i in range(ticks):
        s.tick()
        outs.append(sw.resume_catch_up(s, gate))
    if s.in_flight():
        s._inflight.join(30.0)
    return outs


def arms_resume(worker_path: Path, tmp: Path) -> None:
    """ARMs 23/24/25 -- a retoma: uma vez, so' com a carga RELIDA, com N no log."""
    # A FIACAO PRIMEIRO: uma funcao que ninguem chama passa todas as arms abaixo.
    calls = [line.strip() for line in worker_path.read_text(encoding="utf-8").splitlines()
             if line.strip().startswith("resume_catch_up(switch")]
    add(bool(calls),
        "o laco do audio CHAMA a retoma (o codigo nao e' um ornamento)",
        calls[0] if calls else "(nenhuma chamada no worker)")
    try:
        sw = _load_worker(worker_path)
    except Exception as exc:                                        # noqa: BLE001
        add(False, "o worker importa para os arms da retoma", repr(exc))
        return
    ls = sw._policy.shedding(sw._SHEDDING_PATH, None) if sw._policy else None
    add(ls is not None and hasattr(ls, "ResumeGate") and hasattr(ls, "resume_calm"),
        "o modulo da decisao tem a RETOMA (`ResumeGate`/`resume_calm`)")
    if ls is None or not hasattr(ls, "ResumeGate"):
        return

    print("\nARM 23 -- a RETOMA: carga alta -> baixa carrega o motor UMA vez")
    # A BANDA, primeiro como funcao pura: e' o unico pedaco que decide CARREGAR.
    add(ls.resume_calm(95.0, 5.0) == (False, 'commit>=%.0f%%' % ls.RESUME_PCT),
        "95 % de commit NAO autoriza carregar", str(ls.resume_calm(95.0, 5.0)))
    add(ls.resume_calm(None, 5.0)[0] is False,
        "uma leitura de commit AUSENTE nao autoriza carregar (a direccao segura)")
    add(ls.resume_calm(79.0, 69.0)[0] is True,
        "abaixo da banda nas duas medidas autoriza",
        str(ls.resume_calm(79.0, 69.0)))
    add(ls.resume_calm(79.0, 85.0)[0] is False,
        "commit calmo com CPU acima de CPU_RESUME_PCT NAO autoriza")
    add(ls.resume_calm(79.0, None)[0] is True,
        "CPU ausente nao inventa carga (a convencao de `level_for_cpu`)")

    s, eng, logs, _probe = _parked_switch(
        sw, tmp, "resume", [(96.0, 90.0), (12.0, 6.0)])
    gate = sw._resume_gate(s)
    add(gate is not None, "o worker sabe construir o `ResumeGate` do checkout")
    outs = _descend(sw, s, gate)
    resumed = [o for o in outs if o.get("resumed")]
    add(len(resumed) == 1,
        "a serie alta -> baixa produz EXACTAMENTE UMA retoma",
        "retomas=%d levels=%s" % (len(resumed), [o.get("level") for o in outs]))
    add(resumed and resumed[0]["blocks"] == RESUME_BLOCKS,
        "e o N do backlog entregue e' o N que esperava",
        "blocks=%s" % (resumed[0]["blocks"] if resumed else None))
    add(eng.loads == 1, "o motor carregou SOZINHO, uma vez", f"loads={eng.loads}")
    resume_lines = [l for l in logs if l.startswith("LOAD_RESUME ")]
    add(len(resume_lines) == 1 and "blocks=%d" % RESUME_BLOCKS in resume_lines[0],
        "o log da retoma diz `blocks=N` (o tamanho do backlog entregue)",
        resume_lines[0] if resume_lines else "(sem linha)")
    after = s._pending_counts()
    add(after["blocks_in"] == after["blocks_out"] == RESUME_BLOCKS,
        "contagem: N entrou == N saiu",
        f"in={after['blocks_in']} out={after['blocks_out']}")
    add(after["seconds"] == 0.0 and after["dropped"] == 0,
        "a espera drenou para ZERO e nada se perdeu",
        f"seconds={after['seconds']} dropped={after['dropped']}")
    caps = [c for c in s.drain_captions() if c.get("type") == "caption"]
    add(len(caps) >= 1 and all(c.get("route") == "redux-batch" for c in caps),
        "o audio que esperou virou legenda do lote", f"{len(caps)} linha(s)")
    # MAIS TICKS CALMOS: a retoma nao se repete (uma vez por borda).
    for _i in range(6):
        s.tick()
        sw.resume_catch_up(s, gate)
    if s.in_flight():
        s._inflight.join(30.0)
    add(eng.loads == 1 and len([l for l in logs if l.startswith("LOAD_RESUME ")]) == 1,
        "ticks calmos seguintes NAO voltam a carregar (uma vez por borda)",
        f"loads={eng.loads}")

    print("\nARM 24 -- carga que sobe DEPOIS da amostra calma mantem o motor parado")
    # (a) HISTERESE: uma amostra calma isolada nunca chega a nivel `leve`.
    state = ls.LoadShedding()
    levels = [state.observe(value, 5.0)[0] for value in (96.0, 12.0, 96.0, 12.0, 96.0)]
    gate_h = ls.ResumeGate(probe=None)
    outs_h = [gate_h.tick(lv) for lv in levels]
    add(all(lv == "muito-alta" for lv in levels),
        "a serie alta -> UMA baixa -> alta NAO desce o nivel (a confirmacao manda)",
        str(levels))
    add(not any(o["resume"] for o in outs_h) and gate_h.resumes == 0,
        "e a retoma nunca e' autorizada: o motor FICA estacionado",
        "resumes=%d" % gate_h.resumes)

    # (b) A RE-LEITURA: o nivel desceu, mas a maquina ja' subiu outra vez.
    s2, eng2, logs2, _p2 = _parked_switch(
        sw, tmp, "reread",
        [(96.0, 90.0)] + [(12.0, 6.0)] * 4 + [(97.0, 95.0)])
    gate2 = sw._resume_gate(s2)
    outs2 = _descend(sw, s2, gate2)
    resumed2 = [o for o in outs2 if o.get("resumed")]
    add(not resumed2,
        "o nivel desceu mas a RE-LEITURA viu 97 %: nenhuma retoma",
        "resumed=%d levels=%s" % (len(resumed2),
                                  sorted({o.get("level") for o in outs2})))
    add(eng2.loads == 0,
        "e o motor NAO foi carregado (a leitura velha nao carrega 615 MB)",
        f"loads={eng2.loads}")
    add(any("LOAD_RESUME_HELD" in l for l in logs2),
        "a recusa e' DITA no log (nao e' um silencio)",
        next((l for l in logs2 if "LOAD_RESUME_HELD" in l), "(sem linha)"))
    add(not any(l.startswith("LOAD_RESUME ") for l in logs2),
        "e nenhuma linha de retoma foi escrita")
    held2 = s2._pending_counts()
    add(held2["held_blocks"] == RESUME_BLOCKS and held2["dropped"] == 0,
        "o audio continua TODO a espera (a carga subiu, ele fica para depois)",
        f"held={held2['held_blocks']} dropped={held2['dropped']}")

    print("\nARM 25 -- N blocos entregues ao lote com N no MESMO log")
    s3, eng3, logs3, _p3 = _parked_switch(
        sw, tmp, "count", [(96.0, 90.0), (12.0, 6.0)], blocks=37)
    gate3 = sw._resume_gate(s3)
    outs3 = _descend(sw, s3, gate3)
    line3 = next((l for l in logs3 if l.startswith("LOAD_RESUME ")), "")
    add("blocks=37" in line3 and "audio_s=3.70" in line3,
        "a linha da retoma leva o N e o audio_s do backlog entregue", line3)
    add(any(l.startswith("REDUX_BATCH_KICK") and "audio_s=3.7" in l for l in logs3),
        "e o lote do parakeet recebeu esse mesmo audio",
        next((l for l in logs3 if l.startswith("REDUX_BATCH_KICK")), ""))
    add(eng3.loads == 1 and s3._pending_counts()["seconds"] == 0.0,
        "37 blocos -> 1 carga do motor -> espera a ZERO",
        f"loads={eng3.loads} seconds={s3._pending_counts()['seconds']}")


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
    # O PROPRIO WORKER TAMBEM: o docstring prometia-o e sem ele `neg_arm_*`
    # media um `FileNotFoundError` (o import do worker copiado) e chamava a isso
    # "RED" -- um braco negativo que passa por o alvo nao existir nao mede mutante
    # nenhum. Foi o braco da RETOMA que o expos (2026-11-04).
    shutil.copy2(WORKER, worker_dir / "sotto_worker.py")
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


def neg_arm_resume() -> int:
    """A RE-LEITURA antes de carregar deixar de existir, e exige RED.

    O mutante e' o defeito plausivel desta metade: o `ResumeGate` autoriza a
    retoma com o nivel (a histerese) e nunca relê a maquina -- ou seja carrega
    615 MB com o commit de volta aos 97 %, que e' o stutter que a ordem proibe.
    Sem este braco, as arms 23-25 podiam passar com o `_reread` a devolver
    `calm=True` sempre: mediriam a fiacao e nao a guarda.
    """
    tmp = Path(tempfile.mkdtemp(prefix="load-shed-resume-neg-"))
    try:
        worker_copy, webview = _mutant_layout(tmp)
        target = webview / "load_shedding.py"
        text = target.read_text(encoding="utf-8")
        mutant = text.replace(
            "        calm, why = resume_calm(commit, cpu)\n"
            "        return calm, commit, cpu, why",
            "        calm, why = True, 'mutante: a re-leitura nao conta'\n"
            "        return calm, commit, cpu, why")
        if mutant == text:
            print("NEG-ARM(retoma): nao consegui mutar o alvo (o texto mudou)")
            return EXIT_PASS
        target.write_text(mutant, encoding="utf-8")
        print("NEG-ARM(retoma): a retoma deixa de RELER a carga antes de carregar")
        rows.clear()
        arms_resume(worker_copy, tmp)
        failed = [r for r in rows if not r[0]]
        if failed:
            for _ok, name, detail in failed:
                print(f"  RED   {name}  {detail}")
            print(f"\nNEG-ARM(retoma) PASS -- RED as designed: {len(failed)} arm(s)")
            return EXIT_FAIL
        print("\nNEG-ARM(retoma) FAIL -- o oraculo NAO ve a re-leitura a faltar")
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
            lambda _m: None, hidden_after_s=0.0, model_dir=str(model),
            engine=_NoEngine())
        vis.write_text(pay(shed="muito-alta"), encoding="utf-8")
        add(nao_armado.tick() == "stream",
            "sem motor de batch na maquina o shed NAO corta o ao vivo (HARD RULE)",
            "armed=%s engine_available=%s" % (nao_armado.armed,
                                              nao_armado.engine_available))

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


def neg_arm_selector() -> int:
    """Muta o ESCOLHEDOR da largada para o defeito de 2026-11-01 e exige RED.

    O instrumento tambem e' mutavel: um escolhedor que volta a pegar na ULTIMA
    linha do log (medicao morta por cima da app viva) tem de fazer as arms do
    escolhedor ficarem VERMELHAS -- sem isso o braco que reprovou a app do dono
    podia voltar sem ninguem dar por isso.
    """
    rows.clear()
    print("NEG-ARM(selector): o escolhedor volta a ser `hits[-1]` (a ultima largada)")
    selector_arms(_naive_selector)
    failed = [r for r in rows if not r[0]]
    print("\nNEG-ARM(selector) frechas: %d de %d" % (len(failed), len(rows)))
    if failed:
        print("NEG-ARM(selector) PASS -- RED as designed:")
        for _ok, name, detail in failed:
            print("   RED  %s  %s" % (name, detail))
        return EXIT_FAIL
    print("\nNEG-ARM(selector) FAIL -- o escolhedor antigo passou: as arms nao o medem")
    return EXIT_PASS


def _mutant_copy(tmp: Path):
    """Uma copia do repo em miniatura: os TRES ficheiros desta lane."""
    copy = tmp / "app" / "webview"
    copy.mkdir(parents=True, exist_ok=True)
    shutil.copy2(MODULE, copy / "load_shedding.py")
    shutil.copy2(SHELL, copy / "sotto_webview.py")
    if BATCH.exists():
        shutil.copy2(BATCH, copy / "batch_queue.py")
    return copy


def _neg_arm_text(label, path_in_copy, old, new, why, prefix):
    """Muta `old -> new` numa copia e exige RED. Devolve o rc do braco.

    `EXIT_FAIL` = o mutante derrubou o oraculo (o braco PASSA); `EXIT_PASS` = o
    oraculo continuou verde com o defeito dentro (o braco FALHA).
    """
    tmp = Path(tempfile.mkdtemp(prefix=prefix))
    try:
        copy = _mutant_copy(tmp)
        target = copy / path_in_copy
        text = target.read_text(encoding="utf-8")
        mutant = text.replace(old, new)
        if mutant == text:
            print("NEG-ARM(%s): nao consegui mutar o alvo (o texto mudou)" % label)
            return EXIT_PASS
        target.write_text(mutant, encoding="utf-8")
        print("NEG-ARM(%s): %s" % (label, why))
        rc = run(copy / "load_shedding.py", copy / "sotto_webview.py",
                 copy / "batch_queue.py")
        if rc == EXIT_FAIL:
            print("\nNEG-ARM(%s) PASS -- RED as designed: o mutante derruba o oraculo"
                  % label)
            return EXIT_FAIL
        print("\nNEG-ARM(%s) FAIL -- o oraculo NAO ve %s" % (label, why))
        return EXIT_PASS
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def neg_arm_floor() -> int:
    """PISO 180 s -> 0: as descidas voltam a poder recarregar modelo em ciclos."""
    return _neg_arm_text(
        "piso", "load_shedding.py",
        "ACTION_FLOOR_S = 180.0", "ACTION_FLOOR_S = 0.0",
        "o PISO entre descidas passa a 0 s (o triturador do VramGuard)",
        "load-shed-floor-neg-")


def neg_arm_sustain() -> int:
    """Sustentacao fora: uma leitura calma devolve ja' os modelos."""
    return _neg_arm_text(
        "histerese", "load_shedding.py",
        "elif self._stable >= self.samples:", "elif self._stable >= 1:",
        "UMA leitura calma passa a bastar para devolver os modelos",
        "load-shed-sustain-neg-")


def neg_arm_persist() -> int:
    """Crash recovery fora: o `inflight` de um processo morto fica perdido."""
    return _neg_arm_text(
        "restart", "batch_queue.py",
        "if entry.get('state') == 'inflight':",
        "if False and entry.get('state') == 'inflight':",
        "o `inflight` de um processo morto deixa de voltar a fila (o restart perde audio)",
        "load-shed-persist-neg-")


def neg_arm_dwell() -> int:
    """DWELL 60 s -> 0: os niveis voltam a poder ser publicados a 3 s um do outro."""
    return _neg_arm_text(
        "dwell", "load_shedding.py",
        "MIN_DWELL_S = 60.0", "MIN_DWELL_S = 0.0",
        "sem dwell entre publicacoes (o triturador medido na app do dono)",
        "load-shed-dwell-neg-")


def neg_arm_rise_immediate() -> int:
    """A subida volta a ser IMEDIATA para `alta`, sem sustentacao nem dwell."""
    old = """                elif since is not None and since < self.dwell_s:
                    self.held += 1
                    self._skip_log('LOAD_ACTION_HELD level=%s published=%s'
                                   ' reason=dwell since=%.0fs dwell=%.0fs'
                                   % (target, self.published, since,
                                      self.dwell_s), now)
                elif (LEVELS.index(target) > LEVELS.index(self.published)
                      and target == 'muito-alta'):"""
    new = """                elif LEVELS.index(target) > LEVELS.index(self.published):"""
    return _neg_arm_text(
        "subida", "load_shedding.py", old, new,
        "SUBIR volta a ser imediato para `alta` (ignora sustentacao e dwell)",
        "load-shed-rise-neg-")


def neg_arm_channel_arm() -> int:
    """O `start()` deixa de armar o canal do worker -> o `shed` volta a ser um
    numero que ninguem le'."""
    return _neg_arm_text(
        "canal", "load_shedding.py",
        "        self._arm_worker_channel()\n",
        "        pass  # canal nao armado\n",
        "o `shed` publicado deixa de chegar ao worker (ninguem le' o nivel)",
        "load-shed-chan-neg-")


def neg_arm_yield() -> int:
    """O executor deixa de ceder: continua a correr com a maquina carregada."""
    return _neg_arm_text(
        "cede", "batch_queue.py",
        "                    if not self.allowed():\n                        self._kill(child)",
        "                    if False:\n                        self._kill(child)",
        "o executor deixa de ceder quando a carga sobe (corre com a maquina cheia)",
        "load-shed-yield-neg-")


def main(argv) -> int:
    if "--neg-arm-drain" in argv:
        return neg_arm_drain()
    if "--neg-arm-channel" in argv:
        return neg_arm_channel()
    if "--neg-arm" in argv:
        # OS QUATRO MUTANTES, e o pior dos quatro e' o veredicto: uma tabela
        # trocada, um canal trocado, um bloco de audio deitado fora, ou um
        # escolhedor que julga a instancia errada tem de ser apanhados, e um
        # verde num deles nao compra os outros.
        table = neg_arm()
        channel = neg_arm_channel()
        drain = neg_arm_drain()
        selector = neg_arm_selector()
        # OS MUTANTES DA ACCAO (ordem do dono, 2026-11-03): o piso, a sustentacao,
        # a fila a sobreviver ao restart, e o executor a ceder sob carga. Seis
        # mutantes, e o pior dos seis e' o veredicto: um verde num deles nao
        # compra os outros.
        chan = neg_arm_channel_arm()
        dwell = neg_arm_dwell()
        rise = neg_arm_rise_immediate()
        floor = neg_arm_floor()
        sustain = neg_arm_sustain()
        persist = neg_arm_persist()
        cede = neg_arm_yield()
        cpu_wiring = neg_arm_cpu_wiring()
        # O MUTANTE DA RETOMA (ordem do dono, 2026-11-04): a retoma volta a
        # carregar com a carga AINDA em alta. Treze mutantes, e o pior dos treze
        # e' o veredicto: um verde num deles nao compra os outros.
        resume = neg_arm_resume()
        every = (table, channel, drain, selector, floor, sustain, persist, cede,
                 chan, dwell, rise, cpu_wiring, resume)
        return (EXIT_FAIL if all(rc == EXIT_FAIL for rc in every) else EXIT_PASS)
    return run(MODULE, SHELL)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
