#!/usr/bin/env python
# -*- coding: utf-8 -*-
# NO-BUG: ratchet de proveniencia de ROTA nos recibos de lane; nao desbloqueia um bug nomeado, impede que uma rota declarada volte a passar por rota medida
"""RECEIPT-PROVENANCE ORACLE -- um recibo que nomeia uma rota tem de a MEDIR, nao de a declarar.

O DEFEITO QUE ISTO EXISTE PARA IMPEDIR (medido 2026-10-26)
---------------------------------------------------------
`state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md` dizia, na linha 4:

    route: owner-authorized OpenCode Go 1 (DeepSeek V4.1 Flash)

E o processo que **produziu** aquele recibo correu em `opencode-go-3/deepseek-v4.1-flash`. A rota
declarada era a que a politica de encaminhamento **sonda primeiro** (`.agents/skills/task-resolver/
references/model-routing.md`: *"probe DeepSeek V4.1 Flash through `opencode-go-1`, then ... `opencode-go-6`"*),
nao a que serviu o trabalho. Quem escreveu o recibo escreveu a **intencao** e chamou-lhe facto.

Isto nao e um typo: e a classe *"declarar o que devia ter sido em vez de medir o que foi"*, e o
`AGENTS.md` deste repo ja a nomeia do outro lado (*"um numero derivado publica-se com populacao e
janela"*). A rota e um numero derivado.

O QUE ESTE PORTAO EXIGE
-----------------------
Um recibo de lane pode declarar qualquer rota -- mas se nomeia um slot pago (`opencode-go-1..6`,
`minimax`) no seu **bloco de cabecalho**, entao:

  1. header-route-measured     o cabecalho carrega uma MEDICAO junto da declaracao:
                               `providerID=<slot>` **e** `session=ses_...`. Uma declaracao sem
                               medicao e a doenca original, e e RED.
  2. header-route-agrees       o ULTIMO slot nomeado no cabecalho -- a afirmacao EFECTIVA, depois de
                               qualquer `SUPERSEDED` -- e o slot que a medicao nomeia. O historico
                               fica escrito e o portao le o presente.
  3. measurement-cites-tool    a medicao nomeia o INSTRUMENTO que a produziu (`opencode.db`,
                               `opencode.log`, `CommandLine`, `process-info`). Um token
                               `providerID=` sem instrumento e decoracao, nao proveniencia.
  4. population-nonempty       zero recibos lidos e rc=2 NO-VERDICT. **Um skip nao e um portao que
                               passou** (AGENTS.md, docs/bateria-e-portoes.md).

A POPULACAO e `state/work/**/receipt*.md`: o recibo de lane e onde a rota e declarada. `_main/receipt-*.md`
sao os recibos de correccao do repo, escritos depois da medicao e com outro contrato -- ficam de fora,
declarado aqui em vez de descoberto depois.

    python _main\\receipt-provenance-oracle.py             # rc=0 verde, rc=1 vermelho, rc=2 sem veredicto
    python _main\\receipt-provenance-oracle.py --neg-arm   # rc=1 POR DESENHO

Sem rede, sem subprocess, sem escrita dentro da raiz do repo (as mutacoes correm em copias sob TMPDIR).
Nao lanca nada: le bytes.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

POPULATION_ROOT = os.path.join(ROOT, "state", "work")

# Um slot pago: os seis aliases Go e o provider MiniMax (model-routing.md §2-§3). As duas formas
# contam: o token (`opencode-go-1`) e a PROSA (`OpenCode Go 1`) -- foi a prosa que o defeito original
# usou na linha 4, e uma regex so-de-token era cega exactamente ao sitio do defeito (medido no neg-arm).
_SLOT_TOK = re.compile(r"opencode-go-([1-6])|opencode\s+go\s*([1-6])|\bminimax\b", re.IGNORECASE)
_PROVIDER = re.compile(r"providerID=(opencode-go-[1-6]|minimax)\b", re.IGNORECASE)
_SESSION = re.compile(r"session=(ses_[A-Za-z0-9]+)")


def slots_in(text: str) -> list[str]:
    """Slots normalizados a `opencode-go-N` / `minimax`, seja qual for a forma escrita."""
    out: list[str] = []
    for m in _SLOT_TOK.finditer(text):
        if m.group(1):
            out.append(f"opencode-go-{m.group(1)}")
        elif m.group(2):
            out.append(f"opencode-go-{m.group(2)}")
        else:
            out.append("minimax")
    return out

# Os instrumentos que sabem responder "que rota serviu este processo". Fechado de proposito: um
# instrumento novo entra aqui por edicao, com o porque, em vez de ser aceite por parecenca.
_TOOLS = (
    "opencode.db",      # session_v2.model -- o registo do harness, por sessao
    "opencode.log",     # o log do launcher, com o --model de cada launch
    "CommandLine",      # Win32_Process: o argv do processo vivo
    "process-info",     # a observacao do manager sobre um pid
    "session_v2",       # a tabela, por nome
)
_TOOL = re.compile("|".join(re.escape(t) for t in _TOOLS), re.IGNORECASE)

HEADER_CAP = 25  # linhas nao vazias que ainda contam como cabecalho

# A linha que DECLARA a rota. E o campo `route:`, e e ele que o portao julga -- nao a prosa em volta.
_DECL = re.compile(r"^\s*[·>\-\*]?\s*route\s*:", re.IGNORECASE)


def header_block(text: str) -> list[str]:
    """As primeiras linhas nao vazias, ate a primeira seccao `## ` (techo de seguranca em HEADER_CAP)."""
    out: list[str] = []
    for raw in text.splitlines():
        if raw.startswith("## "):
            break
        if not raw.strip():
            continue
        out.append(raw)
        if len(out) >= HEADER_CAP:
            break
    return out


def declaration_line(header: list[str]) -> str | None:
    for raw in header:
        if _DECL.match(raw):
            return raw
    return None


def judge(text: str) -> list[tuple[str, bool, str]]:
    """As quatro leituras sobre um recibo. Devolve (check, ok, detail)."""
    header = header_block(text)
    joined = "\n".join(header)

    # Os tokens de medicao introduzem eles proprios um slot (`providerID=opencode-go-3`), por isso sao
    # retirados antes de se ler a DECLARACAO: senao "o ultimo slot nomeado" seria sempre o medido, e o
    # check seria uma tautologia que nunca derruba nada (medido no primeiro neg-arm deste ficheiro).
    claim_text = _PROVIDER.sub("providerID=<measured>", joined)
    claim_slots = slots_in(claim_text)

    decl = declaration_line(header)
    decl_slots = slots_in(decl) if decl else []
    if not decl_slots:
        decl_slots = claim_slots  # sem campo `route:`, a declaracao e a cabeca do recibo

    providers = [m.group(1).lower() for m in _PROVIDER.finditer(joined)]
    sessions = [m.group(1) for m in _SESSION.finditer(joined)]
    tools = sorted({m.group(0).lower() for m in _TOOL.finditer(joined)})
    superseded = any("SUPERSEDED" in raw.upper() for raw in header)

    results: list[tuple[str, bool, str]] = []

    # 1. Uma declaracao de rota sem medicao ao lado.
    if not claim_slots:
        results.append(("header-route-measured", True, "no paid slot named in the header: not judged"))
    elif providers and sessions:
        results.append(
            ("header-route-measured", True,
             f"slot(s) {','.join(sorted(set(claim_slots)))} measured by providerID + session={sessions[0]}")
        )
    else:
        missing = []
        if not providers:
            missing.append("providerID=")
        if not sessions:
            missing.append("session=ses_")
        results.append(
            ("header-route-measured", False,
             f"header names slot(s) {','.join(sorted(set(claim_slots)))} with no measurement "
             f"(missing {'+'.join(missing)}) -- a declared route is not a measured route")
        )

    # 2. A declaracao tem de ser a medicao -- ou declarar-se substituida por ela, nomeando-a.
    # Um recibo que diz "corri em Go 1" e mede Go 3 sem o marcar e exactamente a doenca original.
    if not providers:
        results.append(
            ("header-route-agrees", True,
             "not judged (no measurement present: see header-route-measured)")
        )
    else:
        measured = providers[-1]
        declared = decl_slots[-1] if decl_slots else None
        if declared is None:
            results.append(("header-route-agrees", True, "no declaration to judge"))
        elif declared == measured:
            results.append(("header-route-agrees", True, f"declared={declared} measured={measured}"))
        else:
            names_measured = measured in claim_slots
            ok = superseded and names_measured
            why = (
                f"declared={declared} measured={measured}: supersession declared and the measured slot is named"
                if ok else
                f"declared={declared} measured={measured}: no SUPERSEDED marker "
                f"({'measured slot not named in header' if not names_measured else 'claim still presented as fact'})"
            )
            results.append(("header-route-agrees", ok, why))

    # 3. Uma medicao sem instrumento e decoracao.
    if not providers:
        results.append(("measurement-cites-tool", True,
                        "not judged (no measurement present: see header-route-measured)"))
    else:
        ok = bool(tools)
        results.append(
            ("measurement-cites-tool", ok,
             f"instrument(s) named: {','.join(tools)}" if ok
             else "providerID= present but no instrument named (opencode.db / opencode.log / CommandLine / process-info)")
        )

    return results


def population() -> list[str]:
    found: list[str] = []
    if not os.path.isdir(POPULATION_ROOT):
        return found
    for dirpath, _dirnames, filenames in os.walk(POPULATION_ROOT):
        for name in filenames:
            low = name.lower()
            if low.startswith("receipt") and low.endswith(".md"):
                found.append(os.path.join(dirpath, name))
    return sorted(found)


def run(paths: list[str]) -> tuple[bool, list[str]]:
    lines: list[str] = []
    if not paths:
        lines.append("CHECK population-nonempty      FAIL   0 receipt(s) under state/work -- NO VERDICT")
        return (False, lines)

    failures = 0
    for path in paths:
        try:
            rel = os.path.relpath(path, ROOT).replace("\\", "/")
        except ValueError:  # copia de mutacao num volume diferente (TMPDIR em G:/I:)
            rel = path.replace("\\", "/")
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        for name, ok, detail in judge(text):
            failures += 0 if ok else 1
            lines.append(f"CHECK {name:<22} {'PASS' if ok else 'FAIL':<6} {rel}: {detail}")
    if not failures:
        lines.insert(0, f"CHECK population-nonempty      PASS   {len(paths)} receipt(s) judged")
    return (failures == 0, lines)


def _mutate(src: str, dst: str, kind: str) -> None:
    with open(src, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    header_end = text.find("\n## ")
    head = text if header_end < 0 else text[:header_end]
    tail = "" if header_end < 0 else text[header_end:]

    if kind == "claim-without-measurement":
        head = _PROVIDER.sub("providerID=<none>", head)
        head = _SESSION.sub("session=<none>", head)
    elif kind == "supersession-removed":
        head = re.sub(r"SUPERSEDED", "NOTE", head, flags=re.IGNORECASE)
    elif kind == "decorative-measurement":
        for tool in _TOOLS:
            head = re.sub(re.escape(tool), "X", head, flags=re.IGNORECASE)
    elif kind == "copy-intact":
        pass
    else:  # pragma: no cover
        raise SystemExit(f"unknown mutation {kind}")

    with open(dst, "w", encoding="utf-8", newline="") as fh:
        fh.write(head + tail)


def neg_arm(paths: list[str]) -> int:
    """Cada mutacao tem de derrubar a SUA arm nomeada. Um recibo intacto tem de ficar VERDE."""
    if not paths:
        print("NEG-ARM FAIL no population to mutate -- the detector was not exercised")
        return 1

    src = paths[0]
    rel = os.path.relpath(src, ROOT).replace("\\", "/")
    tmp = tempfile.mkdtemp(prefix="receipt-prov-")
    arms = [
        ("claim-without-measurement", "header-route-measured"),
        ("supersession-removed", "header-route-agrees"),
        ("decorative-measurement", "measurement-cites-tool"),
    ]
    named_fail = 0
    problems: list[str] = []

    try:
        # Guardo negativo primeiro: se a copia INTACTA ja esta vermelha, o detector nao discrimina
        # nada e nenhuma arm seguinte vale.
        intact = os.path.join(tmp, "receipt-intact.md")
        _mutate(src, intact, "copy-intact")
        ok_intact, _ = run([intact])
        if not ok_intact:
            print(f"NEG-ARM FAIL COPY-BROKEN  the intact copy of {rel} is already red; "
                  f"a red mutation would prove nothing")
            return 1

        for kind, expected in arms:
            dst = os.path.join(tmp, f"receipt-{kind}.md")
            _mutate(src, dst, kind)
            _ok, lines = run([dst])
            failed = [ln.split()[1] for ln in lines if ln.startswith("CHECK") and " FAIL " in ln]
            hit = expected in failed
            named_fail += 0 if hit else 1
            print(f"  mutation {kind:<34} -> {'PASS' if hit else 'FAIL'} (refused by {','.join(failed) or 'nothing'}; expected {expected})")
            if not hit:
                problems.append(kind)

        # A populacao vazia tambem e um check: um diretorio sem recibos nao pode dar verde.
        empty = os.path.join(tmp, "empty")
        os.makedirs(empty, exist_ok=True)
        global POPULATION_ROOT
        original, POPULATION_ROOT = POPULATION_ROOT, empty
        try:
            ok_empty, _ = run(population())
        finally:
            POPULATION_ROOT = original
        hit = not ok_empty
        named_fail += 0 if hit else 1
        print(f"  mutation {'empty-population':<34} -> {'PASS' if hit else 'FAIL'} (expected population-nonempty to refuse)")
        if not hit:
            problems.append("empty-population")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    total = len(arms) + 1
    if named_fail:
        print(f"NEG-ARM FAIL mutations={total} named-arm-fail={named_fail} ({','.join(problems)})")
        return 1
    print(f"NEG-ARM PASS mutations={total} named-arm-fail=0")
    return 1  # vermelho POR DESENHO, como os outros bracos do repo


def main() -> int:
    ap = argparse.ArgumentParser(description="A declared route must be a measured route.")
    ap.add_argument("--neg-arm", action="store_true", help="prove the detector detects (rc=1 by design)")
    ap.add_argument("--path", action="append", default=None, help="judge one receipt instead of the population")
    args = ap.parse_args()

    paths = args.path if args.path else population()

    if args.neg_arm:
        return neg_arm(paths)

    ok, lines = run(paths)
    for ln in lines:
        print(ln)
    if not paths:
        print("VERDICT: NO-VERDICT")
        return 2
    print(f"VERDICT: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
