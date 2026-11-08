#!/usr/bin/env python3
"""Um `call :step` que ninguem regista e' um veredicto que ninguem le.

NASCEU DE UMA MEDICAO (2026-11-08). O bloco do painel da
`_main\\_audit-verify-all.cmd` corria DEZ passos e tinha UM `call :record`:

    call :step panel2-dom-probe ...
    call :step panel-header-oracle ...
    call :step panel-drag-targets ...
    call :step panel-history-clip ...
    call :step panel-pause-payload ...
    call :step red-as-expected-panel-pause-payload ...
    call :step outside-click-timer ...
    call :step red-as-expected-outside-click-timer ...
    call :step panel-deps ...
    call :step red-as-expected-panel-deps ...
    call :record panel2-dom-probe !STEP_RC!

O `:step` NAO conta nada: ele corre o comando, grava o registo do cache e deixa o
`rc` em `!STEP_RC!`. Quem conta e' `:record` / `:expectred` / `:skipped`. Logo
aqueles dez vereditos viravam UM -- e o unico que ficava era o `!STEP_RC!` do
ULTIMO passo da lista (`red-as-expected-panel-deps`), carimbado no nome do
primeiro. Medido na corrida de 2026-11-08: `panel-deps` podia dizer FAIL, e o
sumario mostrava `panel2-dom-probe` verde.

A REGRA QUE ESTE FICHEIRO JULGA, e sao QUATRO metades:
  R1 todo `call :step` tem de ter o SEU registo (`:record`, `:expectred` ou
     `:skipped`) com o MESMO nome;
  R2 esse registo tem de vir ANTES do proximo `call :step` -- senao o
     `!STEP_RC!` que ele le e' de outro passo, que e' o defeito medido acima;
  R3 nenhum registo pode apontar para um passo que nao existe -- um `:record`
     orfao e' um nome que o sumario conta e nada correu;
  R4 a DECLARACAO e o REGISTO tem de concordar sobre o codigo de saida: um
     `:step ... 1` so' pode ser consumido por `:expectred`, um `:step ... 0` por
     `:record`. Medido 2026-11-08: `red-as-expected-caption-drag` e
     `red-as-expected-outside-click-timer` estavam declarados `0` com oraculos
     que devolvem 1 QUANDO APANHAM -- vermelhos em toda a corrida por um numero
     trocado, e nada no ficheiro dizia qual das duas metades estava errada.

O QUE NAO E' UM DEFEITO, e o instrumento sabe distinguir:
  * um `:record ... MISSING` dentro do `else` de um `if exist` e' o registo do
    mesmo nome (o caminho "o instrumento nao esta' la'");
  * um `call :skipped <nome> ...` e `call :control <nome> ...` contam como registo, e sao
    os registos certos para
    um passo que sabe dizer que nao mediu;
  * linhas `REM` nao contam para nada.

Uso:
  python _main\\battery-record-pairing-oracle.py                    # rc 0 verde, 1 vermelho
  python _main\\battery-record-pairing-oracle.py --neg-arm          # rc 1 POR DESENHO
  python _main\\battery-record-pairing-oracle.py --cmd <outro.cmd>

Sem `subprocess`, sem rede, sem escrever dentro da raiz do repo.
"""
from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
CMD_REL = os.path.join("_main", "_audit-verify-all.cmd")

#: `call :step [always|heavy] <nome> ...`  /  `call :record <nome> ...`
#: `call :expectred <nome> ...`             /  `call :skipped <nome> ...`
STEP_RE = re.compile(r"^call\s+:step\s+(?:always\s+|heavy\s+)*(?P<name>\S+)\s+"
                    r"(?P<rc>-?\d+)", re.I)
RECORD_RE = re.compile(r"^call\s+:(?P<kind>record|expectred|skipped|control)\s+(?P<name>\S+)",
                       re.I)


def read_cmd(path):
    with io.open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read().splitlines()


def lines_of(text, path):
    if isinstance(text, str):
        return text.splitlines()
    return text


def scan(lines):
    """Devolve `(steps, records, findings)`.

    `steps`   -- [(indice, nome)] na ordem do ficheiro
    `records` -- {nome: [(indice, kind)]}
    `findings`-- [(regra, nome, detalhe)]
    """
    steps, records, findings = [], {}, []
    for index, line in enumerate(lines):
        bare = line.strip()
        if not bare or bare.upper().startswith("REM"):
            continue
        step = STEP_RE.match(bare)
        if step:
            steps.append((index, step.group("name"), int(step.group("rc"))))
            continue
        rec = RECORD_RE.match(bare)
        if rec:
            records.setdefault(rec.group("name"), []).append((index, rec.group("kind")))

    # R1 -- todo passo tem registo do SEU nome.
    for index, name, _rc in steps:
        if name not in records:
            findings.append(("R1-sem-registo", name,
                             "linha %d: `call :step %s` nao tem `:record`/`:expectred`/"
                             "`:skipped` com esse nome" % (index + 1, name)))

    # R2 -- o registo vem antes do proximo passo.
    for position, (index, name, _rc) in enumerate(steps):
        mine = records.get(name)
        if not mine:
            continue
        # O PRIMEIRO registo DEPOIS do passo, nunca o ultimo do nome: um passo
        # pode estar declarado em dois ramos (`if exist` / `else`) e o ramo do
        # `else` vive DEPOIS do passo seguinte -- medido 2026-11-08, o
        # `battery-plan` foi acusado por causa do `:record ... MISSING` do
        # `else`, que esta' na linha certa do ramo errado.
        later = [at for at, _kind in mine if at > index]
        if not later:
            findings.append(("R2-registo-antes", name,
                             "linha %d: o registo deste nome esta' ANTES do `call :step`"
                             % (index + 1)))
            continue
        after_me = later[0]
        boundary = None
        for nxt_index, _nxt_name, _nxt_rc in steps[position + 1:]:
            if nxt_index > index:
                boundary = nxt_index
                break
        if boundary is not None and after_me > boundary:
            skipped_by = min((i, n) for i, n, _r in steps[position + 1:])
            findings.append(("R2-registo-atrasado", name,
                             "linha %d: o registo deste passo esta' na linha %d, DEPOIS "
                             "do `call :step %s` da linha %d -- o `!STEP_RC!` que ele le "
                             "e' de outro passo"
                             % (index + 1, after_me + 1, skipped_by[1], skipped_by[0] + 1)))
    # R4 -- a DECLARACAO e o REGISTO tem de concordar sobre o codigo de saida.
    # Medido 2026-11-08: `red-as-expected-caption-drag` estava declarado
    # `:step ... 0` (o passo tem de sair 0) com um oraculo que devolve 1 QUANDO
    # APANHA, e o `--neg-arm` do `outside-click-timer` estava no mesmo contrato.
    # Os dois ficavam vermelhos em TODA a corrida por um numero trocado, e nada
    # no ficheiro dizia qual das duas metades estava errada. O `!STEP_RC!` de um
    # `:step ... 1` so' pode ser consumido por `:expectred`.
    for index, name, declared in steps:
        mine = records.get(name) or []
        later = [(at, kind) for at, kind in mine if at > index]
        if not later:
            continue
        kind = later[0][1]
        if declared == 1 and kind == "record":
            findings.append(("R4-contrato-trocado", name,
                             "linha %d: `:step` declara 1 (o passo tem de sair 1) e o "
                             "registo da linha %d e' `:record`, que exige 0 -- use "
                             "`:expectred`" % (index + 1, later[0][0] + 1)))
        elif declared == 0 and kind == "expectred":
            findings.append(("R4-contrato-trocado", name,
                             "linha %d: `:step` declara 0 e o registo da linha %d e' "
                             "`:expectred`, que exige 1 -- um dos dois numeros esta' errado"
                             % (index + 1, later[0][0] + 1)))
    # R5 -- UM passo tem UM registo. Medido 2026-11-08: o bloco do
    # `panel-pause-payload` tinha `:expectred` E, logo depois, um `:record` do
    # MESMO nome -- a segunda linha re-registava o rc=1 do CONTROLO como se
    # fosse o passo normal a espera de 0, e o sumario publicava `...=1` num
    # passo que o `:expectred` ao lado tinha acabado de aprovar. Um registo a
    # mais e' uma linha mentirosa, e nenhuma das quatro regras anteriores a via
    # (R1 pergunta por PRESENCA, R2 pela ORDEM, R3 pela EXISTENCIA do passo,
    # R4 pela CONCORDANCIA do primeiro). O bloco de cada passo vai do seu
    # `call :step` ate' ao `call :step` seguinte, e nesse intervalo o nome pode
    # aparecer UMA vez.
    for index, name, _rc in steps:
        following = [nxt for nxt, _n, _r in steps if nxt > index]
        boundary = following[0] if following else len(lines)
        # O RAMO DO `else` NAO CONTA: um passo declarado em `if exist ... (` /
        # `) else (` tem um registo por ramo, e o do `else` e' o `MISSING` --
        # que nao le `!STEP_RC!` nenhum (medido 2026-11-08 no `battery-plan`).
        inside = [(at, kind) for at, kind in (records.get(name) or [])
                  if index < at < boundary
                  and ' MISSING' not in lines[at].upper()]
        if len(inside) > 1:
            findings.append(("R5-registo-repetido", name,
                             "linha %d: o passo tem %d registos no seu bloco (%s) -- o "
                             "segundo le o `!STEP_RC!` do primeiro e o sumario passa a "
                             "ter dois vereditos sobre o mesmo passo"
                             % (index + 1, len(inside),
                                ', '.join(':%s linha %d' % (k, a + 1) for a, k in inside))))

    # R3 -- nenhum registo orfao.
    step_names = {name for _i, name, _r in steps}
    for name in sorted(records):
        if name not in step_names:
            findings.append(("R3-registo-orfao", name,
                             "linha %d: `:%s %s` registra um passo que nao tem `call :step`"
                             % (records[name][0][0] + 1, records[name][0][1], name)))
    return steps, records, findings


def _duplicate_first_record(lines):
    """Copia o registo de um passo logo depois do original -- o defeito medido."""
    out = list(lines)
    for index, line in enumerate(out):
        step = STEP_RE.match(line.strip())
        if not step:
            continue
        name = step.group("name")
        for at in range(index + 1, min(index + 4, len(out))):
            rec = RECORD_RE.match(out[at].strip())
            if rec and rec.group("name") == name:
                out.insert(at + 1, out[at])
                return out, True
    return out, False


MUTANTS = (
    # (rotulo, transformacao sobre as LINHAS, o que tem de ficar vermelho)
    ("passo-sem-registo",
     lambda lines: _insert_after_first_step(lines),
     "R1-sem-registo"),
    ("registo-atrasado",
     lambda lines: _delay_first_record(lines),
     "R2-registo-atrasado"),
    ("registo-orfao",
     lambda lines: _append_orphan_record(lines),
     "R3-registo-orfao"),
    ("registo-repetido",
     _duplicate_first_record,
     "R5-registo-repetido"),
    ("contrato-trocado",
     lambda lines: _flip_first_declaration(lines),
     "R4-contrato-trocado"),
)


def _flip_first_declaration(lines):
    """Um `:step ... 0` que passa a declarar 1 com o `:record` ao lado intacto."""
    out = list(lines)
    for index, line in enumerate(out):
        bare = line.strip()
        step = STEP_RE.match(bare)
        if step and step.group("rc") == "0" and RECORD_RE.match(
                out[index + 1].strip() if index + 1 < len(out) else ""):
            out[index] = line.replace(" %s " % step.group("name"),
                                      " %s " % step.group("name"), 1).replace(
                ":step %s 0 " % step.group("name"), ":step %s 1 " % step.group("name"), 1)
            return out, ":step %s 1 " % step.group("name") in out[index]
    return out, False


def _append_orphan_record(lines):
    out = list(lines) + ['call :record mutante-orfao !STEP_RC!']
    return out, True


def _insert_after_first_step(lines):
    out = list(lines)
    for index, line in enumerate(out):
        if STEP_RE.match(line.strip()):
            out.insert(index + 1,
                       'call :step mutante-sem-registo 0 "_main\\x.py" "%OUT%\\x.log" python x.py')
            return out, True
    return out, False


def _delay_first_record(lines):
    """Troca a ordem do primeiro par: o registo vai para depois do passo seguinte."""
    out = list(lines)
    step_index = record_index = None
    name = None
    for index, line in enumerate(out):
        step = STEP_RE.match(line.strip())
        if step and step_index is None:
            step_index, name = index, step.group("name")
            continue
        rec = RECORD_RE.match(line.strip())
        if rec and step_index is not None and rec.group("name") == name:
            record_index = index
            break
    if step_index is None or record_index is None:
        return out, False
    record = out.pop(record_index)
    out.insert(step_index + 1, record)
    # ... e um passo novo entre eles, que e' o que faz o `!STEP_RC!` ser de outro
    out.insert(step_index + 1,
               'call :step mutante-no-meio 0 "_main\\y.py" "%OUT%\\y.log" python y.py')
    return out, True


def run(lines, label):
    steps, records, findings = scan(lines)
    print("--- %s ---" % label)
    print("passos: %d | nomes com registo: %d | achados: %d"
          % (len(steps), len(records), len(findings)))
    for rule, name, detail in findings:
        print("  %-18s %-28s %s" % (rule, name, detail))
    ok = not findings
    print("VERDICT: %s" % ("PASS" if ok else "FAIL"))
    return ok


def neg_arm(lines, tmp):
    """Cada mutante tem de produzir o achado que ele promete -- nao 'algum' achado."""
    caught = 0
    for label, transform, expected_rule in MUTANTS:
        mutated, applied = transform(lines)
        if not applied:
            print("MUTANTE %-22s IMPOSSIVEL -- a mutacao nao aplicou (o ficheiro mudou de forma)"
                  % label)
            continue
        path = os.path.join(tmp, "mutante-%s.cmd" % label)
        with io.open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write("\n".join(mutated) + "\n")
        _steps, _records, findings = scan(read_cmd(path))
        rules = {rule for rule, _n, _d in findings}
        good = expected_rule in rules
        print("MUTANTE %-22s %s (%s)" % (label, "CAUGHT" if good else "NOT-CAUGHT",
                                         ", ".join(sorted(rules)) or "nenhum achado"))
        caught += 1 if good else 0
    total = len(MUTANTS)
    print("NEG-ARM: %s (%d/%d mutantes apanhados)" % ("PASS" if caught == total else "FAIL",
                                                     caught, total))
    return 1 if caught == total else 0


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cmd", default=os.path.join(REPO, CMD_REL))
    parser.add_argument("--neg-arm", action="store_true")
    args = parser.parse_args(argv[1:])
    if not os.path.exists(args.cmd):
        print("BATTERY-RECORD-PAIRING: o ficheiro nao esta' la': %s" % args.cmd)
        return 2
    if args.neg_arm:
        tmp = tempfile.mkdtemp(prefix="record-pairing-")
        try:
            return neg_arm(read_cmd(args.cmd), tmp)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    ok = run(read_cmd(args.cmd), os.path.relpath(args.cmd, REPO))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
