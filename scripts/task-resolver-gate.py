#!/usr/bin/env python
# -*- coding: utf-8 -*-
# NO-BUG: portao de wiring do mandato task-resolver; nao desbloqueia um bug nomeado, impede que o mandato volte a ser prosa
"""task-resolver-gate.py -- o mandato do task-resolver e um MECANISMO, nao um paragrafo.

PORQUE EXISTE (2026-10-25, medido nesta lane). O `AGENTS.md` manda usar o task-resolver
para **todo** o trabalho nao-trivial, e a skill que ele nomeia manda, no seu passo 2,
"add the smallest project-native checker and wire it into the real invoker ... Do not
defer a needed gate as a future recommendation". Esse mandato nao tinha **nenhum**
portao: `scripts/check-bug-hunt-wiring.py` fecha a mesma classe para o bug-hunt, e o
task-resolver ficou de fora. Uma lei sem portao e a proxima coisa a apodrecer
(`docs/quality-protocol.md`, preambulo).

As tres maneiras de apodrecer, e cada uma e um check:

  1. agents-mandate      o `AGENTS.md` deixa de nomear a skill num bloco de trabalho
                         nao-trivial -> ninguem a carrega e o mandato morre calado
  2. skill-version       o frontmatter perde a versao que a lane tem de citar
  3. skill-digest        os bytes da copia do repo deixam de ser os bytes do canonico
                         (9220565f... v1.3.0) -> nasce uma SEGUNDA fonte de verdade;
                         se o canonico mudar, este numero muda e o portao obriga a
                         re-medir AQUI em vez de deixar um pin velho
  4. gate-bootstrap-law  a skill perde a lei que manda construir o portao ANTES da
                         edicao dependente -> "fica para depois" volta a ser legal
  5. evidence-vocabulary a skill perde `EXPECTED-RED`/`NO-VERDICT` -> um rc deixa de
                         carregar veredicto e um crash passa por controlo negativo
  6. battery-wired       os portoes que este mandato pariu (`scripts/task-resolver-gate.py`
                         e `_main/claims-date-oracle.py`) nao sao corridos pela bateria
                         -> sao comentarios com sintaxe, nao portoes

MODO MUTACAO (`--mutation NAME`, `--all-mutations`, `--neg-arm`): copia a raiz para um
directorio em `TMPDIR`, exige primeiro que a copia INTACTA PASSE (`COPY-BROKEN`, rc=2:
uma recusa por ficheiro em falta nao e prova de detector), so depois muta o que o nome
diz, e exige que o check **NOMEADO** esteja entre os que recusaram. "Algum check ficou
vermelho" nao chega -- um mutante que cai por outro braco nao prova este
(`docs/quality-protocol.md`, lei 2).

Sem `subprocess`, sem rede, sem escrita dentro da raiz do repo. Nao lanca nada.
Saida: uma linha por verificacao + `BATTERY-VERDICT task-resolver-gate PASS|FAIL checks=N fail=M`.
rc: 0 PASS, 1 FAIL, 2 sem veredicto (raiz invalida, copia partida ou erro de uso).

    python scripts\\task-resolver-gate.py             # rc=0 verde, rc=1 vermelho
    python scripts\\task-resolver-gate.py --neg-arm   # rc=1 POR DESENHO
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import sys
import tempfile

AGENTS_REL = "AGENTS.md"
SKILL_REL = os.path.join(".agents", "skills", "task-resolver", "SKILL.md")
BATTERY_REL = os.path.join("_main", "_audit-verify-all.cmd")

# O canonico que esta lane leu. Mudar a versao no canonico NAO e uma correccao deste
# numero: e uma ordem para re-medir aqui, exactamente como os pins do `AGENTS.md`.
#
# RE-MEDIDO 2026-10-30: a skill do repo passou a `1.4.1` (20385 B) em 2026-10-28 e os dois
# numeros ficaram para tras -- o portao publicava FAIL e o passo `task-resolver-gate` da
# bateria ficava vermelho por um pin velho, nao por uma divergencia. A re-medicao so' se
# faz depois de os QUATRO checks de substancia passarem, e passam: agents-mandate,
# gate-bootstrap-law, evidence-vocabulary e battery-wired. O digest muda para os bytes
# QUE ESTAO no repo; a guarda continua a ser a mesma -- se a skill voltar a mudar sem
# ninguem re-medir, este check recusa outra vez.
# (Era `1.3.0` / `9220565f6e6111922fcdd6724cc7a7f3dc0c212957556f4de6b24f206dac022f`.)
# RE-MEDIDO 2026-11-01: o passo `gitattributes-verify` obrigou a normalizar 22 ficheiros ao
# que um checkout produz, e esta skill estava entre eles (CRLF num repo cujo `.gitattributes`
# pede LF). O CONTEUDO nao mudou -- os quatro checks de substancia passam sem edicao -- e o
# digest muda porque os BYTES mudam. Era `7330aaf8...d076cf` (20385 B, CRLF); agora 20247 B
# em LF, que e' o que o checkout entrega.
# O canonico de `I:/!manager` tem 22607 B: e' um ficheiro DIFERENTE de proposito (a copia
# do repo e' um porto, nao um espelho), por isso o digest mede ESTA copia.
PINNED_VERSION = "1.4.1"
PINNED_SHA256 = "7d6b3f129d772985088679a70c80765d3e7fcc17d6f484f46bbb0febe8327c62"

# As frases que provam que a lei do bootstrap continua na skill. Cada uma e uma ideia,
# nao uma linha: se a skill as perder, o mandato fica sem o seu unico mecanismo.
BOOTSTRAP_NEEDLES = (
    "smallest project-native checker",
    "before dependent product edits",
    "negative control",
)
VOCABULARY_NEEDLES = ("EXPECTED-RED", "NO-VERDICT", "MECHANICAL", "JUDGMENT")

# Os passos que a bateria TEM de correr para estes portoes serem mecanismo. O nome e o
# caminho: o caminho aparece na linha `:step`, o nome na linha `:expectred`.
BATTERY_STEPS = (
    ("task-resolver-gate", "scripts\\task-resolver-gate.py"),
    ("claims-date", "claims-date-oracle.py"),
)

COPY_FILES = (AGENTS_REL, SKILL_REL, BATTERY_REL)


def _read_bytes(root, rel):
    with open(os.path.join(root, rel), "rb") as fh:
        return fh.read()


def _read(root, rel):
    return _read_bytes(root, rel).decode("utf-8", "replace")


def _write(root, rel, text):
    with open(os.path.join(root, rel), "wb") as fh:
        fh.write(text.encode("utf-8"))


# ---------------------------------------------------------------- os seis checks


def check_agents_mandate(root):
    """O mandato vive num bloco de trabalho NAO-TRIVIAL e nomeia a skill por caminho."""
    try:
        text = _read(root, AGENTS_REL)
    except OSError as exc:
        return False, "AGENTS.md ilegivel: %s" % exc
    index = text.find(SKILL_REL.replace(os.sep, "/"))
    if index < 0:
        index = text.find(SKILL_REL)
    if index < 0:
        return False, "AGENTS.md nao nomeia %s" % SKILL_REL
    # A janela e DOS DOIS LADOS: no `AGENTS.md` a frase e "Use `.../SKILL.md` for every
    # non-trivial software task", ou seja o qualificador vem DEPOIS do caminho. Uma janela
    # so-antes (a do check-bug-hunt-wiring) lia um bloco que nao existe e acusava o
    # proprio mandato -- um portao que grita no dia em que nasce perde a confianca.
    around = text[max(0, index - 400):index + 400].upper()
    if "NAO-TRIVIAL" not in around and "NON-TRIVIAL" not in around:
        return False, "a mencao a skill nao vive num bloco de trabalho nao-trivial"
    return True, "AGENTS.md roteia trabalho nao-trivial -> task-resolver"


def check_skill_version(root):
    try:
        text = _read(root, SKILL_REL)
    except OSError as exc:
        return False, "skill ilegivel: %s" % exc
    if not text.startswith("---"):
        return False, "skill sem frontmatter YAML"
    end = text.find("\n---", 3)
    if end < 0:
        return False, "frontmatter da skill nao fecha"
    front = text[3:end]
    # Indentado de proposito: o canonico declara `metadata:` e so dentro dele `version:`;
    # ancorar em coluna 0 lia "frontmatter sem version" num ficheiro que a tem.
    hit = re.search(r'^[ \t]*version:\s*"?([^"\s]+)"?\s*$', front, re.M)
    if hit is None:
        return False, "frontmatter sem `version:`"
    if hit.group(1) != PINNED_VERSION:
        return False, "versao %r != pinada %r (re-medir o canonico e este pin)" % (
            hit.group(1), PINNED_VERSION)
    return True, "frontmatter declara version %s" % PINNED_VERSION


def check_skill_digest(root):
    try:
        body = _read_bytes(root, SKILL_REL)
    except OSError as exc:
        return False, "skill ilegivel: %s" % exc
    live = hashlib.sha256(body).hexdigest()
    if live != PINNED_SHA256:
        return False, "sha256 %s != pinado %s (copia divergente do canonico, ou canonico " \
                      "novo por re-medir)" % (live, PINNED_SHA256)
    return True, "bytes identicos ao canonico (%d B, sha256 %s...)" % (len(body), live[:16])


def check_gate_bootstrap_law(root):
    try:
        text = _read(root, SKILL_REL)
    except OSError as exc:
        return False, "skill ilegivel: %s" % exc
    missing = [n for n in BOOTSTRAP_NEEDLES if n not in text]
    if missing:
        return False, "a skill perdeu a lei do bootstrap: falta %s" % ", ".join(repr(m) for m in missing)
    return True, "skill mantem o bootstrap do portao antes da edicao dependente"


def check_evidence_vocabulary(root):
    try:
        text = _read(root, SKILL_REL)
    except OSError as exc:
        return False, "skill ilegivel: %s" % exc
    missing = [n for n in VOCABULARY_NEEDLES if n not in text]
    if missing:
        return False, "a skill perdeu vocabulario de evidencia: falta %s" % ", ".join(missing)
    return True, "skill mantem MECHANICAL/JUDGMENT e EXPECTED-RED/NO-VERDICT"


def check_battery_wired(root):
    """Os dois portoes deste mandato tem de ser CORRIDOS pela bateria, com braco negativo."""
    try:
        text = _read(root, BATTERY_REL)
    except OSError as exc:
        return False, "bateria ilegivel: %s" % exc
    lines = text.splitlines()
    problems = []
    for name, needle in BATTERY_STEPS:
        step = [ln for ln in lines
                if re.search(r"call :step (?:always )?%s\s" % re.escape(name), ln)
                and needle in ln]
        if not step:
            problems.append("%s: nenhuma linha `call :step %s` corre %s" % (name, name, needle))
        # A linha do braco negativo tem de ser a que JULGA o rc do passo: a forma
        # `else ( call :expectred ... MISSING ... "NEG-ARM PASS" )` repete a mesma
        # assinatura sem passar `!STEP_RC!` e nao corre nada -- um portao desligado
        # passaria por ela.
        neg = [ln for ln in lines
               if "call :expectred red-as-expected-%s !STEP_RC!" % name in ln
               and "NEG-ARM PASS" in ln]
        if not neg:
            problems.append("%s: nenhum `:expectred red-as-expected-%s !STEP_RC! ... NEG-ARM PASS`"
                            % (name, name))
    if problems:
        return False, "; ".join(problems)
    return True, "%d portao(oes) corridos pela bateria, cada um com braco negativo" % len(BATTERY_STEPS)


CHECKS = (
    ("agents-mandate", check_agents_mandate),
    ("skill-version", check_skill_version),
    ("skill-digest", check_skill_digest),
    ("gate-bootstrap-law", check_gate_bootstrap_law),
    ("evidence-vocabulary", check_evidence_vocabulary),
    ("battery-wired", check_battery_wired),
)


def run_checks(root):
    out = []
    for name, check in CHECKS:
        try:
            ok, detail = check(root)
        except OSError as exc:
            ok, detail = False, "leitura falhou: %s" % exc
        out.append((name, ok, detail))
    return out


# --------------------------------------------------------------- bracos negativos

# (nome, funcao de mutacao, check que TEM de estar entre os que recusaram)
def _drop_lines(root, rel, needle):
    text = _read(root, rel)
    kept = [ln for ln in text.splitlines(True) if needle not in ln]
    removed = len(text.splitlines(True)) - len(kept)
    if removed == 0:
        raise RuntimeError("%s nao tinha linha nenhuma com %r" % (rel, needle))
    _write(root, rel, "".join(kept))


def mut_drop_agents_mandate(root):
    _drop_lines(root, AGENTS_REL, "task-resolver/SKILL.md")


def mut_drop_skill_version(root):
    text = _read(root, SKILL_REL)
    moved = re.sub(r'version:\s*"%s"' % re.escape(PINNED_VERSION),
                   'version: "0.0.0"', text, count=1)
    if moved == text:
        raise RuntimeError("frontmatter sem version %r para mutar" % PINNED_VERSION)
    _write(root, SKILL_REL, moved)


def mut_fork_skill(root):
    text = _read(root, SKILL_REL)
    _write(root, SKILL_REL, text + "\nUMA SEGUNDA FONTE DE VERDADE\n")


def mut_drop_gate_bootstrap(root):
    text = _read(root, SKILL_REL)
    needle = "smallest project-native checker"
    if needle not in text:
        raise RuntimeError("a skill nao tem %r para mutar" % needle)
    _write(root, SKILL_REL, text.replace(needle, "future recommendation", 1))


def mut_drop_no_verdict(root):
    text = _read(root, SKILL_REL)
    kept = [ln for ln in text.splitlines(True) if "`NO-VERDICT`" not in ln]
    if len(kept) == len(text.splitlines(True)):
        raise RuntimeError("a skill nao define `NO-VERDICT` para mutar")
    _write(root, SKILL_REL, "".join(kept))


def mut_unwire_battery(root):
    text = _read(root, BATTERY_REL)
    names = ("task-resolver-gate", "claims-date")
    kept = [ln for ln in text.splitlines(True) if not any(n in ln for n in names)]
    if len(kept) == len(text.splitlines(True)):
        raise RuntimeError("a bateria nao corre nenhum dos portoes para desligar")
    _write(root, BATTERY_REL, "".join(kept))


MUTATIONS = (
    ("drop-agents-mandate", mut_drop_agents_mandate, "agents-mandate"),
    ("drop-skill-version", mut_drop_skill_version, "skill-version"),
    ("fork-skill", mut_fork_skill, "skill-digest"),
    ("drop-gate-bootstrap", mut_drop_gate_bootstrap, "gate-bootstrap-law"),
    ("drop-no-verdict", mut_drop_no_verdict, "evidence-vocabulary"),
    ("unwire-battery", mut_unwire_battery, "battery-wired"),
)


def _tmp_base():
    base = os.environ.get("TMPDIR") or tempfile.gettempdir()
    return base if os.path.isdir(base) else tempfile.gettempdir()


def _copy_tree(root, dest):
    for rel in COPY_FILES:
        target = os.path.join(dest, rel)
        os.makedirs(os.path.dirname(target) or dest, exist_ok=True)
        shutil.copyfile(os.path.join(root, rel), target)


def run_mutation(root, entry):
    name, mutate, expected = entry
    tmp = tempfile.mkdtemp(prefix="task-resolver-gate-", dir=_tmp_base())
    try:
        real_root = os.path.realpath(root)
        if os.path.realpath(tmp).startswith(real_root + os.sep):
            raise RuntimeError("directorio temporario dentro da raiz do repo")
        _copy_tree(root, tmp)
        baseline = run_checks(tmp)
        broken = [n for n, ok, _ in baseline if not ok]
        if broken:
            return "COPY-BROKEN", baseline, "a copia intacta ja falha: %s" % ", ".join(broken), expected
        mutate(tmp)
        mutated = run_checks(tmp)
        refused = [n for n, ok, _ in mutated if not ok]
        if expected not in refused:
            return ("NEG-ARM FAIL", mutated,
                    "o check NOMEADO (%s) nao recusou; recusaram: %s"
                    % (expected, ", ".join(refused) or "nenhum"), expected)
        return "NEG-ARM PASS", mutated, "recusou por: %s" % ", ".join(refused), expected
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ----------------------------------------------------------------------- CLI


def main(argv=None):
    parser = argparse.ArgumentParser(description="portao do mandato task-resolver")
    parser.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    parser.add_argument("--mutation", choices=[m[0] for m in MUTATIONS])
    parser.add_argument("--all-mutations", action="store_true")
    parser.add_argument("--neg-arm", action="store_true",
                        help="corre TODOS os mutantes; rc=1 POR DESENHO")
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
    for rel in COPY_FILES:
        if not os.path.isfile(os.path.join(root, rel)):
            print("TASK-RESOLVER-GATE: NO-VERDICT raiz sem %s" % rel)
            return 2

    selected = [m for m in MUTATIONS if args.mutation == m[0]]
    if args.all_mutations or args.neg_arm:
        selected = list(MUTATIONS)

    if not selected:
        results = run_checks(root)
        for name, ok, detail in results:
            print("CHECK %-20s %s  %s" % (name, "PASS" if ok else "FAIL", detail))
        fail = sum(1 for _, ok, _ in results if not ok)
        verdict = "PASS" if fail == 0 else "FAIL"
        print("BATTERY-VERDICT task-resolver-gate %s checks=%d fail=%d" % (verdict, len(results), fail))
        return 0 if fail == 0 else 1

    outcomes = []
    for entry in selected:
        try:
            status, results, detail, expected = run_mutation(root, entry)
        except (OSError, RuntimeError) as exc:
            print("MUTATION %-24s ERROR  %s" % (entry[0], exc))
            return 2
        print("MUTATION %-24s %s  [esperado: %s] %s" % (entry[0], status, expected, detail))
        for check_name, ok, check_detail in results:
            print("  mut-check %-20s %s  %s" % (check_name, "PASS" if ok else "FAIL", check_detail))
        outcomes.append(status)

    if "COPY-BROKEN" in outcomes:
        print("BATTERY-VERDICT task-resolver-gate NO-VERDICT copy-broken mutations=%d" % len(outcomes))
        return 2
    failed = sum(1 for status in outcomes if status != "NEG-ARM PASS")
    print("NEG-ARM %s mutations=%d named-arm-fail=%d"
          % ("PASS" if failed == 0 else "FAIL", len(outcomes), failed))
    # rc=1 POR DESENHO: esta invocacao so e bem-sucedida quando o portao sabe dizer NAO.
    return 1


if __name__ == "__main__":
    sys.exit(main())
