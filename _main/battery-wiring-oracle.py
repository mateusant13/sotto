#!/usr/bin/env python
# -*- coding: utf-8 -*-
# NO-BUG: P3.1 do roadmap de observabilidade (capacidade): um oraculo de enforcement que existe e que nenhum passo da bateria corre e capacidade que ninguem nota; o ratchet torna visivel a divida e proibe que ela cresca
"""BATTERY-WIRING ORACLE -- nenhum oraculo de enforcement novo sem um passo que o corra.

A LINHA (roadmap de observabilidade, P3.1, 2026-10-23): *"Ratchet do wiring da bateria: 90
oraculos de enforcement existem e nenhum passo os corre (37 de 127 ligados); um oraculo novo
sem passo e vermelho"*. Os tres numeros dessa frase eram de 2026-10-23; hoje sao outros e este
ficheiro mede-os em vez de os citar.

O DEFEITO QUE ISTO FECHA. Um oraculo que ninguem corre e um comentario caro: o repo acumulou
ferramentas de enforcement que so provam algo quando alguem se lembra de as chamar. O padrao
ja apareceu antes e esta escrito no `AGENTS.md`: *"um passo saltado nao e um portao que passou"*.
Aqui a regra e mecanica, e tem ratchet: a populacao e a mesma que o `tooling-intent-oracle.py`
usa (os mesmos cinco globs, para nao haver duas definicoes de "oraculo de enforcement"), o
*wiring* e lido da UNICA declaracao que existe (`call :step ...` em `_main/_audit-verify-all.cmd`),
e o baseline so pode **encolher**.

    wired      o basename do ficheiro aparece numa linha `call :step` da bateria (nos deps ou
               no comando) -- e a mesma linha que o `:step` executa, logo nao ha uma segunda
               ideia de "ligado".
    unwired    existe em `_main/` e nao aparece em passo nenhum.

AS SEIS CHECAGENS, e o que cada uma recusa:

    census-readable    a bateria, a populacao e o baseline tem de ser legiveis e nao vazios
                       (um censo que le zero ficheiros nao e um censo verde, e um parser partido)
    baseline-schema    cada entrada tem `file`, `reason` e `date` -- uma licenca sem razao e sem
                       data e a mesma doenca que este repo ja tratou nas afirmacoes numericas
    baseline-ceiling   o numero de entradas nao passa do CEILING pinado NESTE ficheiro (o JSON
                       nao pode levantar o seu proprio tecto)
    new-unwired        um oraculo fora do baseline e sem passo -> RED
    baseline-orphans   uma entrada do baseline que ja esta ligada (ou ja nao existe) -> RED: a
                       licenca tem de ENCOLHER quando a divida e paga
    wiring-counted     a particao tem de fechar: population == wired + unwired, e wired > 0

    python _main\\battery-wiring-oracle.py            # rc=0 verde, rc=1 vermelho
    python _main\\battery-wiring-oracle.py --write-baseline
    python _main\\battery-wiring-oracle.py --neg-arm  # 6 mutantes; rc=1 POR DESENHO
    python _main\\battery-wiring-oracle.py --list-mutations

LIMITE DECLARADO. Isto prova que um ficheiro e REFERENCIADO por um passo, nao que o passo o
exercite como e suposto (um passo pode chamar o ficheiro com o argv errado) nem que o oraculo
seja honesto -- isso e o teste de cada oraculo. E um passo pode correr um oraculo por outro
caminho (um wrapper): fica `unwired` e tem de ser declarado no baseline com essa razao.

Sem `subprocess`, sem rede. Le a bateria e o baseline; os mutantes correm sobre copias em
`$TMPDIR` e a populacao e lida do repo real (os ~170 ficheiros nao se copiam para uma sandbox).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.dirname(HERE)

BATTERY_REL = os.path.join("_main", "_audit-verify-all.cmd")
BASELINE_REL = os.path.join("_main", "battery-wiring-baseline.json")
MAIN_REL = "_main"

# Os MESMOS cinco globs do `_main/tooling-intent-oracle.py`: duas definicoes de "oraculo de
# enforcement" seriam duas verdades.
TOOL_GLOBS = ("*oracle*.py", "*-gate.py", "*_gate*.py", "*-guard.py", "*_guard*.py")

# O tecto da divida, em CODIGO (o JSON nao se auto-levanta). 124 = medido 2026-10-25 11:4x:
# populacao 170, ligados 46, sem passo 124. Se descer, alguem ligou oraculos; se subir, e uma
# decisao com recibo.
CEILING = 124

SCHEMA = "sotto-battery-wiring-baseline/1"

# A data do censo que deu origem ao baseline. Constante, e nao `today`, para o baseline ser
# reproduzivel: uma data que se reescreve sozinha nao data nada.
MEASURED_ON = "2026-10-25"
DEFAULT_REASON = ("oraculo de enforcement anterior a 2026-10-25 sem passo na bateria; "
                  "existe e nao e chamado, logo nao prova nada ate alguem o ligar")
STEP_RE = re.compile(r'^\s*call :step\b', re.IGNORECASE)


# ------------------------------------------------------------------ censo


def population(root):
    names = set()
    main = os.path.join(root, MAIN_REL)
    for pattern in TOOL_GLOBS:
        for path in glob.glob(os.path.join(main, pattern)):
            names.add(os.path.basename(path))
    return names


def step_lines(root):
    path = os.path.join(root, BATTERY_REL)
    text = open(path, "rb").read().decode("utf-8", "replace")
    return [line for line in text.splitlines() if STEP_RE.match(line)]


#: UM BASENAME TEM DE CASAR INTEIRO (2026-11-03). A comparacao era `name in line`,
#: e isso deu um falso "ligado" medido: `der-oracle.py` casava dentro de
#: `loading-placeholder-oracle.py` -- `placehol`+`der-oracle.py`. Com um passo novo
#: a nomear o placeholder, `der-oracle.py` passou a contar como ligado e a entrada
#: dele no baseline virou `baseline-orphans FALHA`. Um ficheiro e' um TOKEN: o que
#: estiver de cada lado nao pode ser letra, digito, `_`, `-` nem `.`.
_NAME_RE_CACHE = {}


def _name_in(line, name):
    key = name
    rx = _NAME_RE_CACHE.get(key)
    if rx is None:
        import re
        rx = re.compile(r'(?<![A-Za-z0-9_.-])' + re.escape(name) + r'(?![A-Za-z0-9_.-])')
        _NAME_RE_CACHE[key] = rx
    return rx.search(line) is not None


def census(root, pop=None):
    """(population, wired, unwired) -- `wired` = o basename aparece numa linha `call :step`."""
    pop = population(root) if pop is None else set(pop)
    lines = step_lines(root)
    wired = sorted(name for name in pop if any(_name_in(line, name) for line in lines))
    unwired = sorted(pop - set(wired))
    return pop, wired, unwired


# ------------------------------------------------------------------ baseline


def load_baseline(root):
    path = os.path.join(root, BASELINE_REL)
    if not os.path.isfile(path):
        return None, "baseline ausente: %s" % BASELINE_REL
    try:
        payload = json.loads(open(path, "rb").read().decode("utf-8"))
    except (OSError, ValueError) as exc:
        return None, "baseline ilegivel: %s" % exc
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return None, "baseline sem lista `entries`"
    return entries, None


def baseline_files(entries):
    return [e.get("file") for e in entries if isinstance(e, dict)]


# ------------------------------------------------------------------ checks


def run_checks(root, pop=None):
    results = []
    try:
        pop_, wired, unwired = census(root, pop)
    except (OSError, ValueError) as exc:
        return [], "censo ilegivel: %s" % exc
    entries, error = load_baseline(root)

    readable = error is None and bool(pop_) and len(wired) + len(unwired) == len(pop_)
    results.append(("census-readable", readable,
                    error or ("populacao=%d ligados=%d sem_passo=%d" % (len(pop_), len(wired),
                                                                        len(unwired)))
                    if error is None else error))
    if error is not None:
        return results, None

    bad_schema = [e for e in entries
                  if not isinstance(e, dict) or not isinstance(e.get("file"), str)
                  or not e.get("file") or not isinstance(e.get("reason"), str) or not e.get("reason")
                  or not isinstance(e.get("date"), str) or not e.get("date")]
    results.append(("baseline-schema", not bad_schema,
                    "%d entrada(s) sem file/reason/date%s" % (
                        len(bad_schema),
                        (": " + ", ".join(str(e)[:40] for e in bad_schema[:2])) if bad_schema else "")))

    results.append(("baseline-ceiling", len(entries) <= CEILING,
                    "baseline com %d entrada(s) <= CEILING %d" % (len(entries), CEILING)
                    if len(entries) <= CEILING else
                    "baseline com %d entradas > CEILING %d" % (len(entries), CEILING)))

    licensed = set(baseline_files(entries))
    new_unwired = [name for name in unwired if name not in licensed]
    results.append(("new-unwired", not new_unwired,
                    "nenhum oraculo novo sem passo" if not new_unwired else
                    "%d oraculo(s) sem passo e sem licenca: %s"
                    % (len(new_unwired), ", ".join(new_unwired[:4]))))

    orphans = [name for name in sorted(licensed) if name not in unwired]
    results.append(("baseline-orphans", not orphans,
                    "nenhuma entrada orfa" if not orphans else
                    "%d entrada(s) que ja nao sao divida (ligadas ou apagadas): %s"
                    % (len(orphans), ", ".join(orphans[:4]))))

    # A FORMA DE UMA LINHA `call :step` TEM DE SER `always|heavy <nome> <rc> <deps> <log> <cmd>`.
    # MEDIDO 2026-10-30, e custou um ficheiro: escrevi `call :step expect-red <nome> 1 ...`,
    # os argumentos deslizaram um lugar, o `.log` passou a ser o COMANDO e as dependencias
    # passaram a ser o LOG -- o cmd tentou executar o ficheiro de log e o erro dele foi
    # REDIRIGIDO PARA DENTRO de `_main/shell-relaunch-oracle.py`, que ficou com 40 bytes de
    # mensagem do Windows no lugar do codigo. Uma linha mal formada nao falha: ela DESTROI.
    bad_shape = []
    for line in step_lines(root):
        if not line.strip().startswith("call :step"):
            continue
        rest = line.strip()[len("call :step"):].strip()
        first = rest.split()[0] if rest.split() else ""
        # O parser aceita `always`, `heavy` ou NADA (a classe vem do prefixo do nome:
        # `red-as-expected-*` e' o controlo). O que ele NAO aceita e' um token de classe
        # escrito a mao -- e esse erro NAO falha em silencio, ele desloca os argumentos.
        if first.lower() in ("expect-red", "expect_red", "expectred", "control",
                             "skip", "record", "heavy-only"):
            bad_shape.append(line.strip()[:70])
    results.append(("step-line-shape", not bad_shape,
                    "nenhuma linha `call :step` nomeia uma classe que o parser nao aceita"
                    if not bad_shape
                    else "%d linha(s) sem classe: %s" % (len(bad_shape), " | ".join(bad_shape[:2]))))

    results.append(("wiring-counted", len(wired) > 0 and len(wired) + len(unwired) == len(pop_),
                    "ligados=%d sem_passo=%d populacao=%d" % (len(wired), len(unwired), len(pop_))))
    return results, None


def write_baseline(root):
    pop, wired, unwired = census(root)
    if len(unwired) > CEILING:
        print("RED  %d oraculo(s) sem passo > CEILING %d: nao se grava um baseline que cresce"
              % (len(unwired), CEILING))
        return 1
    try:
        existing = {e.get("file"): e for e in (load_baseline(root)[0] or []) if isinstance(e, dict)}
    except (OSError, ValueError):
        existing = {}
    entries = []
    for name in unwired:
        prior = existing.get(name) or {}
        entries.append({
            "file": name,
            "reason": prior.get("reason") or DEFAULT_REASON,
            "date": prior.get("date") or MEASURED_ON,
        })
    payload = {
        "schema": SCHEMA,
        "why": "Os oraculos de enforcement que ja existiam em 2026-10-25 sem passo na bateria. "
               "Ratchet: so pode encolher. Ver _main/battery-wiring-oracle.py.",
        "ceiling": CEILING,
        "entries": entries,
    }
    path = os.path.join(root, BASELINE_REL)
    with open(path, "wb") as fh:
        fh.write(json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8") + b"\n")
    print("wrote %s with %d entry(ies) (ceiling %d, ligados %d de %d)"
          % (BASELINE_REL, len(entries), CEILING, len(wired), len(pop)))
    return 0


# ------------------------------------------------------------------ mutacoes

COPY_FILES = (BATTERY_REL, BASELINE_REL)


def _tmp_base():
    base = os.environ.get("TMPDIR") or tempfile.gettempdir()
    return base if os.path.isdir(base) else tempfile.gettempdir()


def _copy_tree(root, tmp):
    for rel in COPY_FILES:
        source = os.path.join(root, rel)
        target = os.path.join(tmp, rel)
        os.makedirs(os.path.dirname(target) or tmp, exist_ok=True)
        shutil.copyfile(source, target)


def _read(path):
    return open(path, "rb").read().decode("utf-8", "replace")


def _write(path, text):
    with open(path, "wb") as fh:
        fh.write(text.encode("utf-8"))


def _first_unwired(root):
    _, _, unwired = census(root)
    if not unwired:
        raise RuntimeError("nenhum oraculo sem passo no repo real")
    return unwired[0]


def mut_add_unwired_oracle(tmp, pop):
    """Um ficheiro novo que casa os globs e nao aparece em passo nenhum."""
    return ("pop", set(pop) | {"zzz-novo-oracle.py"})


def mut_delete_baselined(tmp, ctx):
    """Apaga do disco um oraculo licenciado: a licenca fica orfa."""
    return ("pop", set(ctx["pop"]) - {ctx["unwired"][0]})


def mut_wire_baselined(tmp, ctx):
    """Liga um oraculo licenciado: a licenca tem de encolher."""
    name = ctx["unwired"][0]
    path = os.path.join(tmp, BATTERY_REL)
    text = _read(path)
    line = ('call :step zzz-mutante 0 "" "%%OUT%%\\zzz.log" python _main\\%s\n' % name)
    _write(path, text.rstrip("\n") + "\n" + line)
    return None


def mut_grow_baseline(tmp, pop):
    """Sobe o baseline ATE' AO TECTO PINADO + 1, e nao "+1 entrada".

    A versao anterior acrescentava UMA entrada. Com o baseline em 124 (no tecto)
    isso provava o `baseline-ceiling`; com o baseline a 113 -- encolhido de
    verdade em 2026-10-30 (11 entradas orfas de ficheiros apagados) -- uma
    entrada nova fazia 114 e o `baseline-ceiling` PASSAVA, porque o tecto nao
    tinha sido tocado. O mutante ficava INERTE e o check nomeado deixava de ser
    provado: o mutante so' era apanhado por OUTRO check (`baseline-orphans`),
    por o nome ser inventado.

    O mutante le o CEILING pinado NESTE ficheiro e cresce ate' la' + 1, por isso
    crescer o baseline deixa de ser invisivel a qualquer encolhimento futuro.
    """
    path = os.path.join(tmp, BASELINE_REL)
    payload = json.loads(_read(path))
    entries = list(payload["entries"])
    alvo = int(payload.get("ceiling") or CEILING) + 1
    while len(entries) < alvo:
        entries.append({"file": "zzz-inventado-%d-oracle.py" % len(entries),
                        "reason": "entrada inventada pelo mutante",
                        "date": "2026-10-25"})
    payload["entries"] = entries
    _write(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return None


def mut_drop_baseline(tmp, pop):
    os.remove(os.path.join(tmp, BASELINE_REL))
    return None


def mut_blank_battery(tmp, pop):
    """Uma bateria sem um unico `call :step`: o censo le zero ligados e nao pode ficar verde."""
    _write(os.path.join(tmp, BATTERY_REL), "REM bateria vazia pelo mutante\n")
    return None


MUTATIONS = (
    ("add-unwired-oracle", mut_add_unwired_oracle, "new-unwired"),
    ("wire-baselined", mut_wire_baselined, "baseline-orphans"),
    ("delete-baselined", mut_delete_baselined, "baseline-orphans"),
    ("grow-baseline", mut_grow_baseline, "baseline-ceiling"),
    ("drop-baseline", mut_drop_baseline, "census-readable"),
    ("blank-battery", mut_blank_battery, "wiring-counted"),
)


def run_mutation(root, entry):
    name, mutate, expected = entry
    tmp = tempfile.mkdtemp(prefix="battery-wiring-", dir=_tmp_base())
    try:
        if os.path.realpath(tmp).startswith(os.path.realpath(root) + os.sep):
            raise RuntimeError("directorio temporario dentro da raiz do repo")
        _copy_tree(root, tmp)
        real_pop = population(root)
        _, _, real_unwired = census(root)
        ctx = {"pop": real_pop, "unwired": real_unwired}
        baseline, error = run_checks(tmp, pop=real_pop)
        if error is not None:
            return "COPY-BROKEN", [], error, expected
        broken = [n for n, ok, _ in baseline if not ok]
        if broken:
            return "COPY-BROKEN", baseline, "a copia intacta ja falha: %s" % ", ".join(broken), expected
        override = mutate(tmp, ctx)
        pop = real_pop if override is None else override[1]
        mutated, error = run_checks(tmp, pop=pop)
        if error is not None:
            return "COPY-BROKEN", mutated or [], "censo ilegivel apos a mutacao: %s" % error, expected
        refused = [n for n, ok, _ in mutated if not ok]
        if expected not in refused:
            return "NEG-ARM FAIL", mutated, \
                   "o check NOMEADO (%s) nao recusou; recusaram: %s" % (
                       expected, ", ".join(refused) or "nenhum"), expected
        return "NEG-ARM PASS", mutated, "recusou por: %s" % ", ".join(refused), expected
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------ CLI


def main(argv=None):
    parser = argparse.ArgumentParser(description="ratchet do wiring dos oraculos na bateria")
    parser.add_argument("--root", default=DEFAULT_ROOT)
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument("--mutation", choices=[m[0] for m in MUTATIONS])
    parser.add_argument("--all-mutations", action="store_true")
    parser.add_argument("--neg-arm", action="store_true", help="corre TODOS os mutantes; rc=1 POR DESENHO")
    parser.add_argument("--list-mutations", action="store_true")
    args = parser.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    if args.list_mutations:
        for name, _, expected in MUTATIONS:
            print("%s -> %s" % (name, expected))
        return 0

    root = os.path.abspath(args.root)
    if not os.path.isfile(os.path.join(root, BATTERY_REL)):
        print("BATTERY-WIRING: NO-VERDICT bateria ausente: %s" % BATTERY_REL)
        return 2

    if args.write_baseline:
        return write_baseline(root)

    selected = [m for m in MUTATIONS if args.mutation == m[0]]
    if args.all_mutations or args.neg_arm:
        selected = list(MUTATIONS)

    if not selected:
        results, error = run_checks(root)
        if error is not None:
            print("BATTERY-WIRING: NO-VERDICT %s" % error)
            return 2
        for name, ok, detail in results:
            print("CHECK %-18s %s  %s" % (name, "PASS" if ok else "FAIL", detail))
        fail = sum(1 for _, ok, _ in results if not ok)
        pop, wired, unwired = census(root)
        print("SUMMARY populacao=%d ligados=%d sem_passo=%d ceiling=%d"
              % (len(pop), len(wired), len(unwired), CEILING))
        print("BATTERY-VERDICT battery-wiring %s checks=%d fail=%d"
              % ("PASS" if fail == 0 else "FAIL", len(results), fail))
        return 0 if fail == 0 else 1

    outcomes = []
    for entry in selected:
        try:
            status, results, detail, expected = run_mutation(root, entry)
        except (OSError, RuntimeError, ValueError) as exc:
            print("MUTATION %-22s ERROR  %s" % (entry[0], exc))
            return 2
        print("MUTATION %-22s %s  [esperado: %s] %s" % (entry[0], status, expected, detail))
        for check, ok, check_detail in results:
            print("  mut-check %-18s %s  %s" % (check, "PASS" if ok else "FAIL", check_detail))
        outcomes.append(status)
    if "COPY-BROKEN" in outcomes:
        print("BATTERY-VERDICT battery-wiring NO-VERDICT copy-broken mutations=%d" % len(outcomes))
        return 2
    failed = sum(1 for status in outcomes if status != "NEG-ARM PASS")
    print("NEG-ARM %s mutations=%d named-arm-fail=%d"
          % ("PASS" if failed == 0 else "FAIL", len(outcomes), failed))
    return 1


if __name__ == "__main__":
    sys.exit(main())
