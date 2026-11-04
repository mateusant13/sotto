#!/usr/bin/env python
"""O PORTAO DAS LEIS -- `bend PROOF.bend --verdict`, com seis saidas TIPADAS.

O que este ficheiro e: o portao que a bateria (`_main\_audit-verify-all.cmd`)
pode chamar. O gate de verdade e o do Bend 2, que corre DENTRO do WSL (o
distro `ubuntu-bend`), porque o kernel (Lean 4.34 via BendTT) so esta la.

O QUE O PORTAO COMPROVA, e o que ele NAO comprova:

  PROVA: que as AFIRMACOES de `bend_core\LAWS.bend` sao verdadeiras sobre o
  modelo puro do caminho 1:1 (a revelacao palavra-a-palavra, a vitalidade de
  uma linha, o tecto da janela). O kernel prova cada lei para TODAS as
  entradas do seu dominio, e um def por lei e o que a preenche.

  NAO PROVA: o ORCAMENTO DE TEMPO. Uma lei prova uma ORDEM, nunca um
  milissegundo. O drift e medido por `_main\youtube-drift-oracle.py`, que
  imprime `drift_ms` por linha -- nunca um booleano "sincronizado".

  NAO PROVA: o que o dono VE no ecra. As leis provam o DADO; o desenho e
  medido pelos mirrors (`_main\youtube-reveal-oracle.py`,
  `_main\youtube-rows-oracle.py`), que chamam as funcoes de PRODUCAO.

AS SEIS SAIDAS, e porque sao TIPADAS (POL-6). Um portao que responde 0 ou 1
confunde "a lei e falsa" com "o portao nao correu":

  0  todas as leis verificam E todos os controlos negativos falham pelo motivo
     certo (nomeando a lei que tentam refutar)
  2  uma lei NAO verificou (a prova esta errada)
  3  um controlo negativo fez o que nao devia (verificou, ou falhou sem
     nomear a lei)
  4  INFRAESTRUTURA: o WSL, o `bend`, o veredicto ou o kernel nao estao
     disponiveis. NUNCA e "a lei e falsa"
  5  o INVENTARIO de leis divergiu da lista fixada (uma lei foi apagada ou
     renomeada)
  6  uma sonda de TAMPER nao se comportou (uma prova esvaziada ainda verifica,
     logo o portao nao esta a ler o estado das provas)

O PORCAO DA LAI (o que o `--verdict` diz) e o `--check-only` NAO e: o
`--check-only` nao corre prova nenhuma e imprime `ALL PROOFS CHECK` num
ficheiro que o kernel recusa (upstream #1897, #1896). O `--verdict` e o unico
modo que este repo usa como portao.
"""
# NO-BUG: portao das 14 leis do `LAWS.bend` — `bend PROOF.bend --verdict` no WSL
# `ubuntu-bend`, nunca `--check-only`. Sem ele, "as leis provam o que dizem" seria
# uma afirmacao: ele mede os 14 controles negativos, cada um com o `Location:` exacto.
from __future__ import annotations

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
CORE = os.path.join(REPO, "bend_core")

LAWS = os.path.join(CORE, "LAWS.bend")
PROOF = os.path.join(CORE, "PROOF.bend")
NEG_DIR = CORE

#: O distro WSL onde vive o toolchain. `BEND_WSL_DISTRO` permite apontar para
#: outro, mas NUNCA para outro REPOSITORIO: um override que aponta para uma
#: outra arvore e exactamente a falha que este portao existe para impedir.
DISTRO = os.environ.get("BEND_WSL_DISTRO", "ubuntu-bend")

#: O INVENTARIO FIXADO das leis. Uma lei apagada, renomeada ou acrescentada
#: muda este conjunto e o portao falha -- e a falha e o ponto: sem ela, uma lei
#: apagada deixa de ser verificada e nada num run verde diria isso.
EXPECTED_LAWS = (
    # As tres leis do EPOCH/SLOT (2026-10-30): a legenda que nao pinta no
    # instante em que a fonte anterior ainda tem fila, e o reinicio da
    # numeracao por fonte nao pinta o que ja estava na tela.
    "Cap.display_clean_before_new_source",
    "Cap.epoch_monotonic",
    "Nat.no_cross_source_paint",
    "Nat.live_flag_is_false_before_the_line_starts",
    "Nat.live_flag_is_started_and_not_ended",
    "Nat.of_bool_agrees_with_revealed_flag",
    "Nat.revealed_flag_is_zero_or_one",
    "Nat.window_rows_is_the_minimum",
    "Nat.window_rows_never_exceeds_the_capacity",
    "Nat.window_rows_never_exceeds_the_live_rows",
    "Toks.count_due_counts_only_due_words",
    "Toks.count_due_is_monotone_in_time",
    "Toks.count_due_of_an_empty_line_is_zero",
    "Toks.count_due_of_one_word_is_its_flag",
)

#: Os CONTROLOS NEGATIVOS, cada um com a lei que tenta refutar. Um controlo por
#: ficheiro: o kernel pára na PRIMEIRA lei que falha, e dois controlos no
#: mesmo ficheiro deixariam o segundo por exercitar.
EXPECTED_CONTROLS = (
    ("NEGATIVE_epoch_monotonic.bend", "Cap.epoch_monotonic"),
    ("NEGATIVE_no_cross_source_paint.bend", "Nat.no_cross_source_paint"),
    ("NEGATIVE_display_clean_before_new_source.bend",
     "Cap.display_clean_before_new_source"),
    ("NEGATIVE_revealed_flag.bend", "Nat.revealed_flag_is_zero_or_one"),
    ("NEGATIVE_of_bool_agrees.bend", "Nat.of_bool_agrees_with_revealed_flag"),
    ("NEGATIVE_live_flag.bend", "Nat.live_flag_is_started_and_not_ended"),
    ("NEGATIVE_live_flag_before.bend",
     "Nat.live_flag_is_false_before_the_line_starts"),
    ("NEGATIVE_window_rows_min.bend", "Nat.window_rows_is_the_minimum"),
    ("NEGATIVE_window_rows_capacity.bend",
     "Nat.window_rows_never_exceeds_the_capacity"),
    ("NEGATIVE_window_rows_live.bend",
     "Nat.window_rows_never_exceeds_the_live_rows"),
    ("NEGATIVE_count_due_only.bend", "Toks.count_due_counts_only_due_words"),
    ("NEGATIVE_count_due_monotone.bend",
     "Toks.count_due_is_monotone_in_time"),
    ("NEGATIVE_count_due_empty.bend",
     "Toks.count_due_of_an_empty_line_is_zero"),
    ("NEGATIVE_count_due_one_word.bend",
     "Toks.count_due_of_one_word_is_its_flag"),
)

EXIT_OK = 0
EXIT_LAW_FAILED = 2
EXIT_CONTROL_MISBEHAVED = 3
EXIT_INFRA = 4
EXIT_INVENTORY = 5
EXIT_TAMPER = 6

#: O texto que o kernel escreve quando um proof esta errado. O `Location:` com
#: um nome VAZIO e o que distingue um ERRO DE SINTAXE (que nao e um
#: contra-exemplo) de uma LEI REFUTADA.
_FAIL = "SOME PROOFS FAIL"
_GREEN = "ALL PROOFS CHECK"
_OUT_OF_SCOPE = "BendTT: out of scope"


def _wsl_script() -> str:
    """O comando WSL que corre o `bend` dentro do distro do toolchain."""
    return (
        "export PATH=/root/.bend/bin:$HOME/.elan/bin:$PATH; "
        'cd "$1" && bend --verdict "$2"'
    )


def _wsl_path(win_path):
    """Traduz um caminho Windows para o caminho WSL.

    MEDIDO 2026-10-29: passar o caminho Windows tal e qual ao `bash -lc`
    NAO funciona -- o `cd` recebe `H:\sotto\bend_core`, que o Linux nao
    reconhece ("No such file or directory"). A traducao e o `wslpath -a` do
    proprio WSL, e e ela que torna o portao utilizavel a partir do Windows.
    """
    try:
        proc = subprocess.run(
            ["wsl", "-d", DISTRO, "-e", "wslpath", "-a", win_path],
            capture_output=True, text=True, timeout=120,
        creationflags=subprocess.CREATE_NO_WINDOW, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))
    except (OSError, subprocess.SubprocessError):
        return ""
    if proc.returncode != 0:
        return ""
    return (proc.stdout or "").strip().replace("\r", "")


def run_bend_version():
    """Le a versao do `bend` (e do `lean`), que e o que produziu o veredicto.

    O log tem de dizer QUAL kernel disse verde: a aceitacao do kernel alarga
    entre versions (upstream #1892), e um log que so diz "verde" nao diz se as
    leis ainda valem ou se o kernel passou a aceitar mais.
    """
    try:
        proc = subprocess.run(
            ["wsl", "-d", DISTRO, "-e", "bash", "-lc",
             "export PATH=/root/.bend/bin:$HOME/.elan/bin:$PATH; "
             "bend version; echo '--- lean ---'; lean --version"],
            capture_output=True, text=True, timeout=180,
        creationflags=subprocess.CREATE_NO_WINDOW, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))
    except (OSError, subprocess.SubprocessError) as exc:
        return ("INFRA: cannot run wsl: %r" % (exc,), EXIT_INFRA)
    return ((proc.stdout or "") + (proc.stderr or "")).replace("\0", "")


def run_bend(name):
    """Corre `bend --verdict <name>` no `bend_core`. Devolve (saida, rc).

    O caminho do repositorio e o do ficheiro passam como ARGV e nunca
    interpolados no script interno: um caminho com aspas mudaria o comando.
    """
    core_wsl = _wsl_path(CORE)
    if not core_wsl:
        return ("INFRA: cannot translate %s to a WSL path (is the '%s' distro "
                "installed?)" % (CORE, DISTRO), EXIT_INFRA)
    try:
        proc = subprocess.run(
            ["wsl", "-d", DISTRO, "-e", "bash", "-lc", _wsl_script(),
             "_", core_wsl, name],
            capture_output=True, text=True, timeout=1800,
        creationflags=subprocess.CREATE_NO_WINDOW, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))
    except (OSError, subprocess.SubprocessError) as exc:
        return ("INFRA: cannot run wsl: %r" % (exc,), EXIT_INFRA)
    out = (proc.stdout or "") + (proc.stderr or "")
    return (out.replace("\0", ""), proc.returncode)


def verdict_class(text):
    """`green` | `out-of-scope` | `proof-fail` | `no-verdict`.

    A distincao entre `out-of-scope` e `proof-fail` e OBRIGATORIA: o kernel
    reporta um limite de traducao com as MESMAS palavras que uma lei falsa
    (upstream #1897). Sem esta distincao, o portao sairia com "a lei nao
    verificou" e apontaria o proximo agente para uma prova que esta boa.
    """
    if _GREEN in text:
        return "green"
    if _OUT_OF_SCOPE in text:
        return "out-of-scope"
    if _FAIL in text:
        return "proof-fail"
    return "no-verdict"


def has_location(text, want):
    """True quando o texto traz `Location: <want>` com o nome EXACTO.

    Comparacao literal, nao regex: os nomes de lei tem pontos, e `Nat.min_le_r`
    como ERE tambem casa `NatXminYle_r` -- o que deixaria uma falha diferente
    satisfazer a assercao. O `Location:` vazio de um erro de sintaxe nunca
    casa um nome, que e o ponto.
    """
    for line in (text or "").splitlines():
        if not line.startswith("Location:"):
            continue
        name = line.split(":", 1)[1].strip()
        if name and name == want:
            return True
    return False


def law_inventory():
    """As leis declaradas em `LAWS.bend`, ordenadas."""
    try:
        with open(LAWS, "r", encoding="utf-8") as fh:
            src = fh.read()
    except OSError:
        return []
    return sorted(m.group(1) for m in
                  re.finditer(r"^law\s+([^:\s]+)\s*:", src, re.M))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    selftest = "--selftest" in argv

    if not os.path.exists(LAWS) or not os.path.exists(PROOF):
        print("BEND-GATE FAIL: bend_core/{LAWS,PROOF}.bend not found "
              "-- wrong repository root (%s)" % REPO)
        return EXIT_INFRA

    problems = []

    # (1) A VERSAO. Ha duas distribuicoes com o nome `bend`: a 1 (o crate
    # bend-lang) nao tem `law` nem `--verdict` e nao parseia `bend_core/*.bend`.
    # Uma falha de parse e indistinguivel de "as leis estao quebradas", por isso
    # o portao afirma a DISTRIBUICAO antes de julgar qualquer lei.
    #
    # MEDIDO 2026-10-29: o `bend` 2.0.39 aceita `--version` como ARGUMENTO de
    # ficheiro (e complains "no such file: version"), mas `bend version` sem
    # o `--` imprime a versao. Por isso a versao e lida com `bend version` e o
    # `--verdict` fica para os ficheiros.
    vout = run_bend_version()
    if "bend 2." not in vout:
        print("BEND-GATE FAIL: this gate needs Bend 2 ('bend 2.x.y'); got: %r"
              % (vout.strip() or "<no output>"))
        return EXIT_INFRA
    print("== bend: %s ==" % vout.strip().splitlines()[0])

    # (2) A LEI. O `--verdict` e o unico modo usado como portao.
    out, rc = run_bend("PROOF.bend")
    klass = verdict_class(out)
    if klass == "out-of-scope":
        print("BEND-GATE FAIL: the kernel did not see every proof "
              "(BendTT translation limit). This is NOT a refuted law.")
        print(out[:2000])
        return EXIT_INFRA
    if _FAIL in out and _GREEN in out:
        print("BEND-GATE FAIL: bend printed BOTH verdicts; refusing to guess.")
        print(out[:2000])
        return EXIT_INFRA
    if klass == "proof-fail":
        print("BEND-GATE FAIL: a law did not check.")
        print(out[:2000])
        return EXIT_LAW_FAILED
    if klass != "green":
        print("BEND-GATE FAIL: no verdict line from bend (toolchain problem).")
        print(out[:2000])
        return EXIT_INFRA
    if rc != 0:
        print("BEND-GATE FAIL: bend printed a success verdict but exited %d; "
              "refusing to trust it." % rc)
        return EXIT_INFRA
    print("PASS: every law in LAWS.bend checks (proofs in PROOF.bend).")

    # (3) O INVENTARIO. Uma lei apagada deixa de ser verificada e nada num run
    # verde diria isso.
    got_laws = law_inventory()
    if got_laws != sorted(EXPECTED_LAWS):
        print("BEND-GATE FAIL: LAWS.bend law inventory drifted from the pin.")
        print("--- expected (pinned) ---")
        for name in sorted(EXPECTED_LAWS):
            print("  " + name)
        print("--- found in LAWS.bend ---")
        for name in got_laws:
            print("  " + name)
        return EXIT_INVENTORY
    print("PASS: law inventory matches the pinned %d laws."
          % len(got_laws))

    # (4) A DIVISAO. `LAWS.bend` sozinho tem de reportar as suas leis como
    # AFIRMACOES ABERTAS ("N TODOs found"). Se verificasse sozinho, as provas
    # teriam voltado para o ficheiro das afirmacoes -- e a separacao de revisao
    # que a divisao compra era um selo vazio.
    claims, claims_rc = run_bend("LAWS.bend")
    if _GREEN in claims:
        print("BEND-GATE FAIL: LAWS.bend checks on its own -- proofs leaked "
              "back into the claim file.")
        return EXIT_LAW_FAILED
    if "TODOs found" not in claims:
        print("BEND-GATE FAIL: LAWS.bend produced no open-claim count.")
        print(claims[:2000])
        return EXIT_INFRA
    if claims_rc == 0:
        print("BEND-GATE FAIL: LAWS.bend exited 0 while claiming open TODOs.")
        return EXIT_INFRA
    todo_line = next((ln for ln in claims.splitlines()
                      if "TODOs found" in ln), "?")
    print("PASS: LAWS.bend alone reports its laws as open claims: %s"
          % todo_line.strip())

    # (5) OS CONTROLOS NEGATIVOS. Cada um tem de falhar E nomear a lei que
    # tenta refutar. Um controlo que so falha (por um erro de sintaxe) nao e um
    # controlo: e o que o gate diz a si proprio.
    for filename, law in EXPECTED_CONTROLS:
        path = os.path.join(NEG_DIR, filename)
        if not os.path.exists(path):
            print("BEND-GATE FAIL: negative control %s is MISSING." % filename)
            return EXIT_CONTROL_MISBEHAVED
        cout, crc = run_bend(filename)
        if _GREEN in cout:
            print("BEND-GATE FAIL: negative control %s checked -- the gate is "
                  "broken." % filename)
            return EXIT_CONTROL_MISBEHAVED
        if _FAIL not in cout:
            print("BEND-GATE FAIL: %s produced no verdict (toolchain problem)."
                  % filename)
            print(cout[:2000])
            return EXIT_INFRA
        if crc == 0:
            print("BEND-GATE FAIL: %s printed a failure verdict but exited 0; "
                  "refusing to trust it." % filename)
            return EXIT_INFRA
        if not has_location(cout, law):
            print("BEND-GATE FAIL: %s failed WITHOUT naming %s." % (filename, law))
            print("      A parse/type error is not a counterexample -- the "
                  "control is not a control.")
            print(cout[:2000])
            return EXIT_CONTROL_MISBEHAVED
        print("PASS: negative control %s fails on %s, as it must."
              % (filename, law))

    # (6) AS SONDAS DE TAMPER. Um veredicto verde no ficheiro COMO ESTA e
    # cego a uma prova APAGADA ou a uma prova ESVAZIADA (uma prova de um
    # enunciado mais fraco ainda e uma prova). Duas copias alteradas fecham
    # as duas; cada uma tem de falhar por um motivo PROVADO.
    tamper_dir = CORE
    probe_names = []
    try:
        with open(PROOF, "r", encoding="utf-8") as fh:
            proof_src = fh.read()

        # (a) UMA PROVA APAGADA.
        victim = "Laws.Nat.revealed_flag_is_zero_or_one"
        stripped = _delete_def(proof_src, victim)
        if stripped == proof_src:
            print("BEND-GATE FAIL: tamper probe A could not build a changed "
                  "copy (the def pattern is stale).")
            return EXIT_TAMPER
        probe_a = os.path.join(tamper_dir, ".bend-tamper-a-%d.bend"
                               % os.getpid())
        probe_names.append(os.path.basename(probe_a))
        with open(probe_a, "w", encoding="utf-8") as fh:
            fh.write(stripped)
        out_a, rc_a = run_bend_path(probe_a)
        if _GREEN in out_a:
            print("BEND-GATE FAIL: tamper probe A STILL checked -- the gate "
                  "does not read proof state.")
            return EXIT_TAMPER
        if _FAIL not in out_a or rc_a == 0:
            print("BEND-GATE FAIL: tamper probe A did not fail for the right "
                  "reason.")
            print(out_a[:2000])
            return EXIT_TAMPER
        print("PASS: tamper probe A (a deleted proof) is detected.")

        # (b) UMA PROVA ESVAZIADA (o corpo trocado por `{==}`).
        emptied = _empty_body(proof_src, victim)
        if emptied == proof_src:
            print("BEND-GATE FAIL: tamper probe B could not build a changed "
                  "copy (the def pattern is stale).")
            return EXIT_TAMPER
        probe_b = os.path.join(tamper_dir, ".bend-tamper-b-%d.bend"
                               % os.getpid())
        probe_names.append(os.path.basename(probe_b))
        with open(probe_b, "w", encoding="utf-8") as fh:
            fh.write(emptied)
        out_b, rc_b = run_bend_path(probe_b)
        if _GREEN in out_b:
            print("BEND-GATE FAIL: tamper probe B STILL checked -- the gate "
                  "does not read proof state.")
            return EXIT_TAMPER
        if _FAIL not in out_b or rc_b == 0:
            print("BEND-GATE FAIL: tamper probe B did not fail for the right "
                  "reason.")
            print(out_b[:2000])
            return EXIT_TAMPER
        print("PASS: tamper probe B (an emptied proof) is detected.")
    finally:
        for name in probe_names:
            try:
                os.remove(os.path.join(tamper_dir, name))
            except OSError:
                pass

    if selftest:
        # O `--selftest` exercita o classificador de veredicto com as quatro
        # classes, incluindo a que nenhum ficheiro deste repositorio produz.
        cases = (
            ("green", _GREEN, "green"),
            ("out-of-scope", "%s\nBendTT: out of scope: x" % _FAIL,
             "out-of-scope"),
            ("proof-fail", "%s\nLocation: Laws.Nat.min_le_r" % _FAIL,
             "proof-fail"),
            ("garbage", "bend: parse error at line 3", "no-verdict"),
        )
        bad = 0
        for label, text, want in cases:
            got = verdict_class(text)
            if got == want:
                print("PASS: selftest %s -> %s" % (label, got))
            else:
                print("FAIL: selftest %s -> %s (wanted %s)" % (label, got, want))
                bad = 1
        if bad:
            return EXIT_CONTROL_MISBEHAVED
        print("PASS: selftest green (verdict classification).")

    print("== bend gate green ==")
    return EXIT_OK


def _delete_def(src, name):
    """Apaga o def `name` (e o seu corpo indentado) do fonte."""
    lines = src.splitlines(keepends=True)
    out = []
    skipping = False
    for line in lines:
        if skipping:
            if line.strip() and not line[0].isspace():
                skipping = False
            else:
                continue
        if line.startswith("def %s(" % name):
            skipping = True
            continue
        out.append(line)
    return "".join(out)


def _empty_body(src, name):
    """Troca o corpo do def `name` por `{==}`."""
    lines = src.splitlines(keepends=True)
    out = []
    inside = False
    for line in lines:
        if not inside and line.startswith("def %s(" % name):
            inside = True
            out.append(line)
            out.append("  {==}\n")
            continue
        if inside:
            if line.strip() and not line[0].isspace():
                inside = False
                out.append(line)
            continue
        out.append(line)
    return "".join(out)


def run_bend_path(abs_path):
    """Corre o bend num ficheiro que esta DENTRO do `bend_core` (as sondas de
    tamper vivem num sub-directorio temporario, para o `import LAWS.bend`
    resolver)."""
    core_wsl = _wsl_path(CORE)
    if not core_wsl:
        return ("INFRA: cannot translate %s to a WSL path" % CORE, EXIT_INFRA)
    try:
        proc = subprocess.run(
            ["wsl", "-d", DISTRO, "-e", "bash", "-lc",
             "export PATH=/root/.bend/bin:$HOME/.elan/bin:$PATH; "
             'cd "$1" && bend --verdict "$2"',
             "_", core_wsl, os.path.basename(abs_path)],
            capture_output=True, text=True, timeout=1800,
        creationflags=subprocess.CREATE_NO_WINDOW, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))
    except (OSError, subprocess.SubprocessError) as exc:
        return ("INFRA: cannot run wsl: %r" % (exc,), EXIT_INFRA)
    out = (proc.stdout or "") + (proc.stderr or "")
    return (out.replace("\0", ""), proc.returncode)


if __name__ == "__main__":
    sys.exit(main())
