#!/usr/bin/env python
# -*- coding: utf-8 -*-
# NO-BUG: P0.2 do roadmap de observabilidade (capacidade, nao desbloqueia bug nomeado): uma pagina de estado GERADA a partir das saidas dos oraculos, para o AGENTS.md poder encolher sem perder os factos, e para um passo que nao correu nunca poder aparecer a verde
"""SOTTO STATE PAGE -- a pagina de estado e GERADA, e recusa-se a inventar.

A LEI (roadmap de observabilidade, P0.2, 2026-10-23, `docs/roadmap-observability.md`):
*"Pagina de estado gerada a partir das saidas dos oraculos, nunca escrita a mao;
recusa renderizar um passo que nao correu"*. O portao declarado nessa linha: *"recusa-se a
inventar: um passo ausente e `NOT RUN`, nunca um verde"*.

O DEFEITO QUE ISTO FECHA. Uma tabela de estado escrita a mao envelhece de uma maneira
silenciosa: o passo foi desligado, a linha ficou verde, e ninguem volta a olhar. Este repo
ja mediu essa classe de falha (`docs/AGENTS-archive-20261021.md`, "um passo saltado nao e
um portao que passou"). Aqui a regra e mecanica: **nao existe texto de estado escrito por
uma pessoa**. A pagina e uma funcao pura de tres artefactos, e nada mais:

    declaracao  `_main/_audit-verify-all.cmd`  -- `call :step [always] [heavy] NOME EXPECT
                "deps" "%OUT%\\NOME.log" <comando>` e `call :expectred NOME !STEP_RC!
                "%OUT%\\NOME-neg.log" "TOKEN"`. A LISTA de passos vem daqui, logo a pagina
                nao pode inventar um passo que a bateria nao declara, nem perder um que ela
                declara (check `step-declared`).
    registo     `_cache/battery-steps.json` -- o que o `_main/_stepcache.py` REGISTOU: rc,
                expect_rc, timestamp, deps e os seus hashes, sha256 do log. Sem entrada aqui,
                o passo NAO CORREU (check `absent-is-not-run`).
    saidas      `_main/_audit-verify/*.log` -- os bytes do oraculo. Um log alterado depois
                do registo e `NO-VERDICT`: o registo descreve bytes que ja nao existem.

OS SEIS ESTADOS, e nenhum deles e um verde que nao se possa defender:

    PASS           rc == expect_rc == 0, log intacto (sha256), deps com o mesmo fingerprint
    EXPECTED-RED   rc == expect_rc != 0 E o token declarado em `:expectred` esta no log
    FAIL           rc != expect_rc  (inclui um braco negativo que ficou VERDE: expect 1, rc 0)
    STALE          rc == expect_rc mas as deps mudaram depois da medicao -- o verde e sobre
                   bytes que ja nao estao no repo, e por isso nao vale como estado de hoje
    NO-VERDICT     log ausente/alterado, token ausente, dep ausente ou passo ilegivel
    NOT RUN        o `:stepcache` nao tem registo: o passo nunca correu (ou nao completou)

`STALE` e o estado que mais aparece hoje, e isso e o resultado, nao um defeito: o repo tem
trabalho de outras lanes por commitar (medido 2026-10-25: 713 caminhos sujos), logo metade
das medicoes de 2026-10-24 descreve bytes que ja nao existem. Uma pagina que escondesse
isso seria a tabela escrita a mao que este item existe para nao ter.

    python _main\\sotto-state-page.py            # renderiza e imprime o resumo (nao escreve)
    python _main\\sotto-state-page.py --write    # escreve docs/state-generated.md
    python _main\\sotto-state-page.py --check    # rc=0 se a pagina nao inventa nada; rc=1 se diverge
    python _main\\sotto-state-page.py --check --require-fresh
                                                 # as seis estruturais + a pagina tem de ser
                                                 # byte-identica a uma renderizacao fresca
    python _main\\sotto-state-page.py --neg-arm  # rc=1 POR DESENHO (mutacoes nomeadas)
    python _main\\sotto-state-page.py --mutation <nome> --check
    python _main\\sotto-state-page.py --list-mutations

LIMITE DECLARADO. A pagina prova o que os ORACULOS disseram, nao que eles sejam honestos
(isso e o `_main/tooling-intent-oracle.py` e os testes de cada oraculo). E `--check` prova
que a pagina nao foi editada a mao; prova-lo contra uma edicao COORDENADA da pagina e do
registo esta fora do alcance de um gate local -- ficaria a precisar de historia, nao de um
censo.

Sem `subprocess`, sem rede. Le e escreve apenas `docs/state-generated.md` (com `--write`) e
os mutantes correm sobre copias em `$TMPDIR`. Nao lanca nada: pode entrar na bateria.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.dirname(HERE)

BATTERY_REL = os.path.join("_main", "_audit-verify-all.cmd")
STATE_REL = os.path.join("_cache", "battery-steps.json")
LOG_DIR_REL = os.path.join("_main", "_audit-verify")
PAGE_REL = os.path.join("docs", "state-generated.md")
ENGINE_REL = os.path.join("_main", "_stepcache.py")

STEP_RE = re.compile(
    r'^[ \t]*call :step[ \t]+(?:(always)[ \t]+)?(?:(heavy)[ \t]+)?'
    r'([A-Za-z0-9_.+\-]+)[ \t]+(\d+)[ \t]+"([^"]*)"[ \t]+"([^"]*)"[ \t]*(.*)$',
    re.IGNORECASE)
EXPRED_RE = re.compile(
    r'^[ \t]*call :expectred[ \t]+([A-Za-z0-9_.+\-]+)[ \t]+!STEP_RC![ \t]+'
    r'"([^"]*)"[ \t]+"([^"]*)"', re.IGNORECASE)

VERDICTS = ("PASS", "EXPECTED-RED", "FAIL", "STALE", "NO-VERDICT", "NOT RUN")
GREEN = ("PASS", "EXPECTED-RED")
ROW_RE = re.compile(
    r'^\|[ \t]*([A-Za-z0-9_.+\-]+)[ \t]*\|[ \t]*([A-Z][A-Z \-]*?)[ \t]*\|'
    r'[ \t]*([^|]*?)[ \t]*\|[ \t]*([^|]*?)[ \t]*\|[ \t]*([^|]*?)[ \t]*\|'
    r'[ \t]*([^|]*?)[ \t]*\|[ \t]*([^|]*?)[ \t]*\|[ \t]*$')

COUNT_KEYS = ("passos", "PASS", "EXPECTED-RED", "FAIL", "STALE", "NO-VERDICT", "NOT RUN")

# O PROBLEMA DO OBSERVADOR, declarado: os dois passos desta ferramenta sao linhas da propria
# pagina, e a corrida da bateria reescreve o log deles ANTES de este processo arrancar -- logo o
# estado deles e intrinsecamente corrido enquanto o observador olha. Nao se finge que nao e: essas
# duas linhas ficam FORA da comparacao de celulas e do resumo (que e o que o passo da bateria
# julga), e continuam a ser renderizadas e verificadas como qualquer outra na escrita da pagina.
# `state-page-write` entrou em 2026-10-30: e' o ESCRITOR, e corre antes de o proprio
# `call :record` o escrever no registo -- a celula dele nunca pode bater com o registo no
# instante em que ele renderiza. Mesma classe do par acima, mesma resposta: FORA da
# comparacao (a comparacao de "nenhum verde inventado" continua a julga-lo).
SELF_STEPS = ("state-page", "red-as-expected-state-page", "state-page-write")


# ------------------------------------------------------------------ leitura


def _read_text(path, errors="replace"):
    with open(path, "rb") as fh:
        return fh.read().decode("utf-8", errors)


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def out_dir_of(root):
    return os.path.join(root, LOG_DIR_REL)


def parse_battery(root):
    """A LISTA de passos, lida da bateria -- a unica declaracao que existe."""
    path = os.path.join(root, BATTERY_REL)
    text = _read_text(path)
    out_dir = out_dir_of(root)
    steps, tokens = [], {}
    for line in text.splitlines():
        m = STEP_RE.match(line)
        if m:
            always, heavy, name, expect, deps, log, cmd = m.groups()
            steps.append({
                "name": name,
                "expect": int(expect),
                "deps": [d for d in deps.split(";") if d.strip()],
                "log": os.path.join(out_dir, os.path.basename(log.replace("\\", "/"))),
                "cmd": cmd.strip(),
                "tags": "/".join(t for t in (always, heavy) if t).lower() or "-",
            })
            continue
        e = EXPRED_RE.match(line)
        if e:
            tokens[e.group(1)] = e.group(3)
    return steps, tokens


def load_engine(root, dep_root=None):
    """O motor do `_stepcache` e a UNICA autoridade do fingerprint (nao se reimplementa).

    `dep_root` existe pelos mutantes: eles copiam pagina/registo/logs para `$TMPDIR`, mas as
    deps pesam **830 927 381 B** (medido 2026-10-25 sobre as 166 deps que a bateria declara),
    por isso as deps sao avaliadas no repo verdadeiro e so o resto vem da copia. E uma escolha
    declarada, nao um atalho escondido.
    """
    path = os.path.join(root, ENGINE_REL)
    spec = importlib.util.spec_from_file_location("_sotto_state_page_stepcache", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.REPO = os.path.abspath(dep_root or root)
    return module


def load_state(root):
    import json
    path = os.path.join(root, STATE_REL)
    with open(path, "rb") as fh:
        payload = json.loads(fh.read().decode("utf-8"))
    steps = payload.get("steps") if isinstance(payload, dict) else None
    if not isinstance(steps, dict):
        raise ValueError("state sem `steps` dict: %s" % STATE_REL)
    return steps


# ------------------------------------------------------------------ veredicto


def verdict_for(step, state, tokens, engine):
    """Um estado por passo, com o motivo ao lado. NUNCA um verde por omissao."""
    name = step["name"]
    entry = state.get(name)
    log = step["log"]
    if not isinstance(entry, dict):
        return "NOT RUN", "-", "sem registo no stepcache (o passo nao completou)"

    rc = entry.get("rc")
    expect = step["expect"]
    recorded_expect = entry.get("expect_rc")
    if not isinstance(rc, int):
        return "NO-VERDICT", "-", "registo sem rc inteiro"
    if recorded_expect is not None and recorded_expect != expect:
        return "NO-VERDICT", str(rc), (
            "registo com expect_rc=%s mas a bateria declara %d" % (recorded_expect, expect))

    if rc != expect:
        return "FAIL", str(rc), "rc=%d != esperado %d" % (rc, expect)

    if not os.path.isfile(log):
        return "NO-VERDICT", str(rc), "log ausente: %s" % os.path.basename(log)
    want_sha = entry.get("log_sha256")
    if want_sha and _sha256(log) != want_sha:
        return "NO-VERDICT", str(rc), "log alterado depois do registo"

    if expect != 0:
        token = tokens.get(name)
        if token and token not in _read_text(log):
            return "NO-VERDICT", str(rc), "token `%s` ausente do log" % token

    fingerprint, missing = engine.fingerprint(step["deps"])
    if missing:
        return "NO-VERDICT", str(rc), "dep ausente: %s" % ", ".join(sorted(missing)[:3])
    if entry.get("fingerprint") and fingerprint != entry["fingerprint"]:
        return "STALE", str(rc), "deps mudaram depois da medicao (medido %s)" % (
            entry.get("timestamp") or "sem data")

    return ("PASS" if expect == 0 else "EXPECTED-RED"), str(rc), ""


def build_rows(root, steps=None, state=None, tokens=None, engine=None, dep_root=None):
    engine = engine or load_engine(root, dep_root)
    steps = steps if steps is not None else parse_battery(root)[0]
    if tokens is None:
        tokens = parse_battery(root)[1]
    state = load_state(root) if state is None else state
    rows = []
    for step in steps:
        verdict, rc, note = verdict_for(step, state, tokens, engine)
        entry = state.get(step["name"]) or {}
        rows.append({
            "name": step["name"],
            "verdict": verdict,
            "rc": rc,
            "expect": str(step["expect"]),
            "when": str(entry.get("timestamp") or "-"),
            "log": os.path.basename(step["log"]),
            "note": note,
            "tags": step["tags"],
        })
    return rows


# ------------------------------------------------------------------ render


def render(root, rows=None):
    rows = rows if rows is not None else build_rows(root)
    counts = dict((key, 0) for key in COUNT_KEYS)
    counts["passos"] = len(rows)
    for row in rows:
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
    lines = [
        "# Estado gerado — Sotto",
        "",
        "> **GERADO por `_main/sotto-state-page.py`. NÃO EDITAR À MÃO.**",
        "> `--check` recusa uma página que não seja byte-idêntica a uma renderização fresca.",
        "> Um passo que não correu é `NOT RUN` — nunca um verde.",
        ">",
        "> Fonte: `_main/_audit-verify-all.cmd` (que passos existem) · `_cache/battery-steps.json`",
        "> (o que o `_stepcache` registou) · `_main/_audit-verify/*.log` (as saídas). Nada aqui é",
        "> escrito por uma pessoa, e nada aqui é um número escolhido: cada célula vem de um desses",
        "> três ficheiros, e `--check` é o portão que o prova.",
        "",
        "Resumo: " + " · ".join("%s=%d" % (key, counts[key]) for key in COUNT_KEYS),
        "",
        "| passo | estado | rc | esperado | quando | log | nota |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        note = row["note"] or row["tags"]
        lines.append("| %s | %s | %s | %s | %s | %s | %s |" % (
            row["name"], row["verdict"], row["rc"], row["expect"], row["when"],
            row["log"], note))
    lines += [
        "",
        "## Como ler",
        "",
        "| estado | significa |",
        "| --- | --- |",
        "| `PASS` | rc igual ao esperado, log com o sha256 registado, deps inalteradas |",
        "| `EXPECTED-RED` | rc de braço negativo como esperado **e** o token exigido está no log |",
        "| `FAIL` | rc diferente do esperado — inclui um braço negativo que ficou verde |",
        "| `STALE` | correu bem, mas as deps mudaram depois: o verde é sobre bytes que já não existem |",
        "| `NO-VERDICT` | log ausente/alterado, token ausente, dep ausente, registo ilegível |",
        "| `NOT RUN` | o stepcache não tem registo: o passo não correu, ou não completou |",
        "",
    ]
    return "\n".join(lines), counts


# ------------------------------------------------------------------ checks


def read_page(root):
    path = os.path.join(root, PAGE_REL)
    if not os.path.isfile(path):
        return None
    rows, summary = [], {}
    for line in _read_text(path).splitlines():
        m = ROW_RE.match(line)
        if m:
            rows.append({
                "name": m.group(1), "verdict": m.group(2).strip(), "rc": m.group(3),
                "expect": m.group(4), "when": m.group(5), "log": m.group(6),
                "note": m.group(7),
            })
        elif line.startswith("Resumo:"):
            for part in line[len("Resumo:"):].split("·"):
                key, _, value = part.strip().partition("=")
                if value.strip().isdigit():
                    summary[key.strip()] = int(value.strip())
    return {"rows": rows, "summary": summary}


def run_checks(root, dep_root=None, require_fresh=True):
    """Os sete checks (seis estruturais + frescura). O ok False e sempre um defeito.

    `require_fresh=False` serve o passo da bateria: a frescura byte-a-byte da pagina e uma
    propriedade do ESCRITOR (`--write` seguido de `--check`), enquanto "nenhum verde inventado"
    e uma propriedade que se pode verificar contra a evidencia viva em qualquer momento. O
    passo da bateria corre as seis estruturais; a lane que escreve a pagina corre as sete.
    """
    try:
        engine = load_engine(root, dep_root)
        steps, tokens = parse_battery(root)
        state = load_state(root)
    except (OSError, ValueError) as exc:
        return [], "leitura falhou: %s" % exc
    page_path = os.path.join(root, PAGE_REL)
    if not os.path.isfile(page_path):
        return [], "pagina ausente: %s" % PAGE_REL
    page = read_page(root)
    results = []

    declared = [s["name"] for s in steps]
    shown = [r["name"] for r in page["rows"]]
    dupes = sorted(set(n for n in shown if shown.count(n) > 1))
    missing = [n for n in declared if n not in shown]
    extra = [n for n in shown if n not in declared]
    ok = not dupes and not missing and not extra
    results.append(("step-declared", ok,
                    "declarados=%d na_pagina=%d duplicados=%s ausentes=%s inventados=%s"
                    % (len(declared), len(shown), dupes[:3] or "-", missing[:3] or "-",
                       extra[:3] or "-")))

    by_name = dict((s["name"], s) for s in steps)
    bad_green, bad_notrun, bad_token, bad_verdict = [], [], [], []
    for row in page["rows"]:
        name, verdict = row["name"], row["verdict"]
        step = by_name.get(name)
        if verdict not in VERDICTS:
            bad_verdict.append("%s=%r" % (name, verdict))
            continue
        if step is None:
            continue
        entry = state.get(name)
        log = step["log"]
        if verdict in GREEN:
            why = None
            if not isinstance(entry, dict):
                why = "sem registo"
            elif entry.get("rc") != step["expect"]:
                why = "rc=%s != esperado %d" % (entry.get("rc"), step["expect"])
            elif not os.path.isfile(log):
                why = "log ausente"
            elif entry.get("log_sha256") and _sha256(log) != entry["log_sha256"]:
                why = "log alterado"
            else:
                fingerprint, missing_deps = engine.fingerprint(step["deps"])
                if missing_deps:
                    why = "dep ausente"
                elif entry.get("fingerprint") and fingerprint != entry["fingerprint"]:
                    why = "deps mudaram"
            if why:
                bad_green.append("%s(%s: %s)" % (name, verdict, why))
        # um passo sem registo E sem log nunca pode aparecer como outra coisa
        if verdict != "NOT RUN" and not isinstance(entry, dict) and not os.path.isfile(log):
            bad_notrun.append("%s=%s" % (name, verdict))
        if verdict == "EXPECTED-RED":
            token = tokens.get(name)
            if not token:
                bad_token.append("%s(sem :expectred declarado)" % name)
            elif not os.path.isfile(log) or token not in _read_text(log):
                bad_token.append("%s(token %r ausente)" % (name, token))
    results.append(("no-invented-green", not bad_green,
                    "%d verde(s) sem sustentacao%s" % (
                        len(bad_green), (": " + ", ".join(bad_green[:3])) if bad_green else "")))
    results.append(("absent-is-not-run", not bad_notrun,
                    "%d passo(s) sem registo e sem log fora de NOT RUN%s" % (
                        len(bad_notrun), (": " + ", ".join(bad_notrun[:3])) if bad_notrun else "")))
    results.append(("expected-red-token", not bad_token,
                    "%d EXPECTED-RED sem o token exigido%s" % (
                        len(bad_token), (": " + ", ".join(bad_token[:3])) if bad_token else "")))
    results.append(("verdict-vocabulary", not bad_verdict,
                    "vocabulario fora da lista%s" % (
                        (": " + ", ".join(bad_verdict[:3])) if bad_verdict else "")))

    # Refutacao 2026-10-25: `no-invented-green` julga o ESTADO de cada linha e deixava passar uma
    # linha com `quando` / `rc` / `expect` / `log` editados a mao -- que tambem sao medidas.
    bad_cells = []
    for row in page["rows"]:
        if row["name"] in SELF_STEPS:
            continue
        step = by_name.get(row["name"])
        if step is None:
            continue
        entry = state.get(row["name"]) or {}
        want = {
            "rc": str(entry.get("rc")) if isinstance(entry.get("rc"), int) else "-",
            "expect": str(step["expect"]),
            "when": str(entry.get("timestamp") or "-"),
            "log": os.path.basename(step["log"]),
        }
        for cell, expected in want.items():
            if row[cell].strip() != expected:
                bad_cells.append("%s.%s=%r != %r" % (row["name"], cell, row[cell].strip(), expected))
    results.append(("cells-match-record", not bad_cells,
                    "%d celula(s) fora do registo%s" % (
                        len(bad_cells), (": " + ", ".join(bad_cells[:3])) if bad_cells else "")))

    try:
        live_rows = build_rows(root, steps=steps, tokens=tokens, state=state, engine=engine)
        fresh, counts = render(root, live_rows)
    except (OSError, ValueError) as exc:
        return results, "renderizacao falhou: %s" % exc
    live = _read_text(page_path)
    if require_fresh:
        drift = [] if live == fresh else _first_diff(live, fresh)
        results.append(("page-in-sync", not drift,
                        "pagina identica a renderizacao fresca" if not drift else
                        "diverge: " + "; ".join(drift[:3])))
    try:
        # CORRECCAO 2026-10-30: subtrair as linhas do PROPRIO observador de dois conjuntos que as
        # classificaram em instantes diferentes dava um desvio de uma unidade (medido: STALE 5 != 6).
        # Agora as linhas do observador saem dos DOIS lados e so' os agregados alheios se comparam.
        def _counts_without_self(rows):
            out = dict((key, 0) for key in COUNT_KEYS)
            for row in rows:
                if row["name"] in SELF_STEPS:
                    continue
                out[row["verdict"]] = out.get(row["verdict"], 0) + 1
                out["passos"] = out.get("passos", 0) + 1
            return out

        page_counts = _counts_without_self(page["rows"])
        live = _counts_without_self(live_rows)
        ok_counts = all(page_counts.get(k) == live.get(k) for k in COUNT_KEYS)
        results.append(("summary-counts", ok_counts,
                        "resumo da pagina = contagem real" if ok_counts else
                        "resumo %r != real %r" % (page_counts, live)))
    except (KeyError, TypeError):
        results.append(("summary-counts", False, "resumo ilegivel"))
    return results, None


def _first_diff(live, fresh):
    live_lines, fresh_lines = live.splitlines(), fresh.splitlines()
    out = []
    for idx in range(max(len(live_lines), len(fresh_lines))):
        a = live_lines[idx] if idx < len(live_lines) else "<fim>"
        b = fresh_lines[idx] if idx < len(fresh_lines) else "<fim>"
        if a != b:
            out.append("linha %d: pagina=%r fresco=%r" % (idx + 1, a[:90], b[:90]))
    return out


# ------------------------------------------------------------------ mutacoes

COPY_FILES = (BATTERY_REL, STATE_REL, PAGE_REL, ENGINE_REL)


def _tmp_base():
    base = os.environ.get("TMPDIR") or tempfile.gettempdir()
    return base if os.path.isdir(base) else tempfile.gettempdir()


def _copy_tree(root, tmp):
    for rel in COPY_FILES:
        source = os.path.join(root, rel)
        target = os.path.join(tmp, rel)
        os.makedirs(os.path.dirname(target) or tmp, exist_ok=True)
        shutil.copyfile(source, target)
    logs_src = out_dir_of(root)
    logs_dst = out_dir_of(tmp)
    os.makedirs(logs_dst, exist_ok=True)
    if os.path.isdir(logs_src):
        for name in sorted(os.listdir(logs_src)):
            source = os.path.join(logs_src, name)
            if os.path.isfile(source):
                shutil.copyfile(source, os.path.join(logs_dst, name))


def _edit_page(tmp, edit):
    path = os.path.join(tmp, PAGE_REL)
    _write_bytes(path, edit(_read_text(path)))


def _write_bytes(path, text):
    with open(path, "wb") as fh:
        fh.write(text.encode("utf-8"))


def _pick_green(root, want="PASS"):
    for row in read_page(root)["rows"]:
        if row["verdict"] == want:
            return row["name"]
    return None


def mut_flip_green_to_notrun(tmp):
    """Apaga o registo E o log de um passo que a pagina da como verde.

    O LOG NAO SE CHAMA COMO O PASSO. Era esse o defeito desta mutacao, medido em
    2026-10-25: ela apagava `<passo>.log` e o ficheiro real de
    `pycompile-sotto_webview` e `pycompile-webview.log`, por isso o registo saia e o
    log ficava, e o braco NOMEADO (`absent-is-not-run`) nao podia disparar -- a
    condicao dele e "sem registo E sem log". A mutacao passou a ler o nome do log
    do PROPRIO registo (antes de o apagar); o braco nomeado volta a ser quem recusa,
    e sem mudar a expectativa declarada.
    """
    name = _pick_green(tmp)
    if name is None:
        raise RuntimeError("nenhum verde na copia para apagar")
    import json
    state_path = os.path.join(tmp, STATE_REL)
    state = json.loads(_read_text(state_path))
    entry = state["steps"].pop(name, None)
    doomed = {name + ".log", name + "-neg.log"}
    if isinstance(entry, dict):
        declared = str(entry.get("log") or "").replace("\\", "/")
        if declared:
            doomed.add(os.path.basename(declared))
    _write_bytes(state_path, json.dumps(state, indent=2, ensure_ascii=False) + "\n")
    for candidate in os.listdir(out_dir_of(tmp)):
        if candidate in doomed:
            os.remove(os.path.join(out_dir_of(tmp), candidate))


def mut_add_fake_row(tmp):
    def edit(text):
        lines = text.splitlines()
        at = max(i for i, l in enumerate(lines) if l.startswith("| ") and l.endswith(" |"))
        lines.insert(at + 1, "| step-que-nao-existe | PASS | 0 | 0 | - | x.log | inventado |")
        return "\n".join(lines) + "\n"
    _edit_page(tmp, edit)


def mut_drop_row(tmp):
    name = _pick_green(tmp)
    if name is None:
        raise RuntimeError("nenhum verde na copia para remover")

    def edit(text):
        return "\n".join(l for l in text.splitlines()
                         if not ROW_RE.match(l) or ROW_RE.match(l).group(1) != name) + "\n"
    _edit_page(tmp, edit)


def mut_rc_mismatch(tmp):
    """Um passo que a pagina da como PASS passa a ter rc diferente no registo."""
    import json
    name = _pick_green(tmp)
    if name is None:
        raise RuntimeError("nenhum verde na copia")
    state_path = os.path.join(tmp, STATE_REL)
    state = json.loads(_read_text(state_path))
    state["steps"][name]["rc"] = 3
    _write_bytes(state_path, json.dumps(state, indent=2, ensure_ascii=False) + "\n")


def mut_strip_neg_token(tmp):
    """Tira o token exigido do log de um braco negativo que a pagina da como EXPECTED-RED."""
    name = _pick_green(tmp, "EXPECTED-RED")
    if name is None:
        raise RuntimeError("nenhum EXPECTED-RED na copia")
    steps, tokens = parse_battery(tmp)
    step = dict((s["name"], s) for s in steps)[name]
    token = tokens.get(name)
    if not token:
        raise RuntimeError("%s nao declara token em :expectred" % name)
    log = step["log"]
    if not os.path.isfile(log):
        raise RuntimeError("log de %s ausente na copia: %s" % (name, log))
    _write_bytes(log, _read_text(log).replace(token, "TOKEN-REMOVIDO"))


def mut_fingerprint_drift(tmp):
    """Reescreve o fingerprint registado de um passo PASS: o estado passa a ser STALE.

    E o gemeo barato de `dirty-deps` -- as deps reais pesam 830 MB e nao se copiam para uma
    sandbox; o observavel (fingerprint registado != fingerprint das deps de hoje) e o mesmo.
    """
    import json
    name = _pick_green(tmp)
    if name is None:
        raise RuntimeError("nenhum verde na copia")
    state_path = os.path.join(tmp, STATE_REL)
    state = json.loads(_read_text(state_path))
    state["steps"][name]["fingerprint"] = "0" * 64
    _write_bytes(state_path, json.dumps(state, indent=2, ensure_ascii=False) + "\n")


def mut_hand_edit_verdict(tmp):
    """Edicao a mao do unico campo que nao pode ser escrito a mao: o estado."""
    name = _pick_green(tmp, "NOT RUN") or _pick_green(tmp, "NO-VERDICT") or _pick_green(tmp, "STALE")
    if name is None:
        raise RuntimeError("nenhum passo nao-verde na copia")

    def edit(text):
        return re.sub(r'^\| ' + re.escape(name) + r' \| [A-Z \-]+ \|',
                      "| %s | PASS |" % name, text, count=1, flags=re.M)
    _edit_page(tmp, edit)


def mut_falsify_when(tmp):
    """Edita a mao a celula `quando` de uma linha: uma data que o registo nao diz."""
    name = _pick_green(tmp) or _pick_green(tmp, "FAIL")
    if name is None:
        raise RuntimeError("nenhuma linha com registo na copia")
    def edit(text):
        out = []
        for line in text.splitlines():
            m = ROW_RE.match(line)
            if m and m.group(1) == name and m.group(5).strip() not in ("-", ""):
                cells = line.split("|")
                cells[5] = " 2026-01-01T00:00:00-0300 "
                line = "|".join(cells)
            out.append(line)
        return "\n".join(out) + "\n"
    _edit_page(tmp, edit)


MUTATIONS = (
    ("forget-step", mut_flip_green_to_notrun, "absent-is-not-run"),
    ("add-fake-row", mut_add_fake_row, "step-declared"),
    ("drop-row", mut_drop_row, "step-declared"),
    ("rc-mismatch", mut_rc_mismatch, "no-invented-green"),
    ("strip-neg-token", mut_strip_neg_token, "expected-red-token"),
    ("fingerprint-drift", mut_fingerprint_drift, "page-in-sync"),
    ("falsify-when", mut_falsify_when, "cells-match-record"),
    ("hand-edit-verdict", mut_hand_edit_verdict, "page-in-sync"),
)


def run_mutation(root, entry):
    name, mutate, expected = entry
    tmp = tempfile.mkdtemp(prefix="state-page-", dir=_tmp_base())
    try:
        if os.path.realpath(tmp).startswith(os.path.realpath(root) + os.sep):
            raise RuntimeError("directorio temporario dentro da raiz do repo")
        _copy_tree(root, tmp)
        # A COPIA E' POSTA EM DIA ANTES DE SER MUTADA. Medido 2026-10-30: a
        # pagina do repositorio estava velha (`Resumo: passos=132` contra os
        # 148 do registo, e celulas `when` de dias antes), por isso a copia
        # INTACTA ja falhava em `cells-match-record` e `page-in-sync` e TODAS
        # as oito mutacoes saiam `COPY-BROKEN` -- o braco negativo media a
        # pagina velha em vez de medir se o check NOMEADO recusa a mutacao, e
        # o passo publicava rc=2. Regenerar a pagina DENTRO da copia tira o
        # confundidor e nao tira os dentes: a mutacao continua a ser a unica
        # diferenca entre a copia e a copia mutada, e o check nomeado continua
        # a ter de recusar.
        # As DEPS pesam 830 MB e sao avaliadas no repo verdadeiro (`dep_root`), por
        # isso a copia tem de ser renderizada com o MESMO `dep_root` com que vai ser
        # verificada. Renderizada com `REPO = tmp` a celula de fingerprint sai de um
        # repo sem modelos e `page-in-sync` recusa a copia que eu proprio escrevi.
        fresh, _counts = render(tmp, build_rows(tmp, dep_root=root))
        _write_bytes(os.path.join(tmp, PAGE_REL), fresh)
        baseline, error = run_checks(tmp, dep_root=root)
        if error is not None:
            return "COPY-BROKEN", [], error, expected
        broken = [n for n, ok, _ in baseline if not ok]
        if broken:
            return "COPY-BROKEN", baseline, "a copia intacta ja falha: %s" % ", ".join(broken), expected
        mutate(tmp)
        mutated, error = run_checks(tmp, dep_root=root)
        if error is not None:
            return "NEG-ARM PASS", [("unreadable-after-mutation", False, error)], \
                   "o artefacto ficou ilegivel: %s" % error, expected
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
    parser = argparse.ArgumentParser(description="pagina de estado gerada + o portao que a prova")
    parser.add_argument("--root", default=DEFAULT_ROOT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--require-fresh", action="store_true",
                        help="exige a pagina byte-identica a uma renderizacao fresca")
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
    for rel in (BATTERY_REL, STATE_REL, ENGINE_REL):
        if not os.path.isfile(os.path.join(root, rel)):
            print("STATE-PAGE: NO-VERDICT artefacto ausente: %s" % rel)
            return 2

    selected = [m for m in MUTATIONS if args.mutation == m[0]]
    if args.all_mutations or args.neg_arm:
        selected = list(MUTATIONS)

    if selected:
        outcomes = []
        for entry in selected:
            try:
                status, results, detail, expected = run_mutation(root, entry)
            except (OSError, RuntimeError, ValueError) as exc:
                print("MUTATION %-20s ERROR  %s" % (entry[0], exc))
                return 2
            print("MUTATION %-20s %s  [esperado: %s] %s" % (entry[0], status, expected, detail))
            for name, ok, check_detail in results:
                print("  mut-check %-20s %s  %s" % (name, "PASS" if ok else "FAIL", check_detail))
            outcomes.append(status)
        if "COPY-BROKEN" in outcomes:
            print("BATTERY-VERDICT state-page NO-VERDICT copy-broken mutations=%d" % len(outcomes))
            return 2
        failed = sum(1 for status in outcomes if status != "NEG-ARM PASS")
        print("NEG-ARM %s mutations=%d named-arm-fail=%d"
              % ("PASS" if failed == 0 else "FAIL", len(outcomes), failed))
        return 1

    if args.write:
        fresh, counts = render(root)
        path = os.path.join(root, PAGE_REL)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _write_bytes(path, fresh)
        print("wrote %s | %s" % (PAGE_REL, " ".join("%s=%d" % (k, counts[k]) for k in COUNT_KEYS)))
        return 0

    results, error = run_checks(root, require_fresh=args.require_fresh)
    if error is not None:
        print("STATE-PAGE: NO-VERDICT %s" % error)
        return 2
    for name, ok, detail in results:
        print("CHECK %-20s %s  %s" % (name, "PASS" if ok else "FAIL", detail))
    fail = sum(1 for _, ok, _ in results if not ok)
    fresh, counts = render(root)
    print("SUMMARY %s" % " ".join("%s=%d" % (k, counts[k]) for k in COUNT_KEYS))
    verdict = "PASS" if fail == 0 else "FAIL"
    print("BATTERY-VERDICT state-page %s checks=%d fail=%d" % (verdict, len(results), fail))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
