"""A tabela de artefactos e' um PORTAO, nao um relatorio: EMPTY reprova.

PORQUE EXISTE (medido 2026-11-27). O `I:/!watcher/tools/artifact-manifest.py`
mede familias declaradas em `.artifacts.toml`, e o `--gate` dele tem duas
respostas: rc 2 para uma familia ACIMA do tecto e rc 3 para uma varredura
TRUNCADA. Faltavam duas, e as duas sao verdes falsos:

1. **EMPTY nao reprova.** Uma familia cujo `roots` nao existe imprime
   `EMPTY` e o `--gate` devolve **rc 0** -- medido num projecto de teste com
   `roots = ["nope"]`. Uma declaracao que nao mede nada fica registada como
   familia limpa, que e' exactamente a forma de defeito que a lei das stores
   existe para impedir ("um projecto sem manifesto nao consegue responder o
   que consome"; uma familia sem bytes responde o mesmo).
2. **A tabela SOMA nao e' verificada.** Duas familias que se sobrepoem somam os
   mesmos bytes duas vezes. Medido hoje neste repo: `_main/_ordem-before/models`
   sao 147 HARDLINKS de `worker/models` (147/147 mesmo `st_ino`, 0 separados),
   por isso conta-las em duas familias somava 1.20 GiB que nao existem -- o
   total dizia 2.99 GiB quando o volume tem 1.80 GiB nestas familias.

O QUE MEDE, e e' isto que o porta'o exige:
    A1  a tabela e' medida (o instrumento correu e devolveu JSON)
    A2  nenhuma familia esta' EMPTY          -- uma declaracao mede algo
    A3  nenhuma familia esta' OVER o tecto    -- o tecto e' um tecto
    A4  a soma das familias e' o total        -- nenhuma familia contada 2x
    A5  toda a familia nomeia um `producer`   -- uma store sem dono e' um despejo

USO
    python _main/artifact-manifest-oracle.py             # o repo (H:/sotto)
    python _main/artifact-manifest-oracle.py --neg-arm   # prova que morde
    python _main/artifact-manifest-oracle.py --json      # payload do portao
"""
# NO-BUG: portao das stores: declaracao que mede nada, tecto violado, ou tabela que soma o mesmo byte duas vezes e' vermelho
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

#: O instrumento e' da frota e vive FORA deste repo. Ausente = CANNOT-MEASURE,
#: nunca verde: um portao que nao consegue medir nao aprovou nada.
TOOL = r'I:\!watcher\tools\artifact-manifest.py'

#: Um prazo por invocacao. A tabela saudavel deste repo anda em ~1,0 s; medido
#: 2026-11-27, a MESMA tabela levou 92 s numa janela carregada, por isso o prazo
#: e' do chamador e a recusa por prazo e' `CANNOT-MEASURE`, nunca um verde.
STAGE_S = 180.0

EXIT_PASS, EXIT_FAIL, EXIT_CANNOT = 0, 1, 3


def _run(project: str, timeout: float = STAGE_S) -> tuple[int, dict | None, str]:
    """One instrument invocation. Returns (rc, payload, stderr tail)."""
    if not os.path.isfile(TOOL):
        return -1, None, "instrumento ausente: %s" % TOOL
    cmd = [sys.executable, TOOL, "--project", project,
           "--budget-seconds", "60", "--gate", "--json"]
    kwargs = {"capture_output": True, "text": True, "encoding": "utf-8",
              "errors": "replace", "timeout": timeout}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    try:
        proc = subprocess.run(cmd, **kwargs)
    except subprocess.TimeoutExpired:
        return -2, None, "prazo de %.0f s estourado em %s" % (timeout, project)
    payload = None
    if proc.stdout.strip().startswith("{"):
        try:
            payload = json.loads(proc.stdout)
        except ValueError:
            payload = None
    return proc.returncode, payload, (proc.stderr or "").strip()[-400:]


def judge(rc: int, payload: dict | None) -> list[tuple[str, bool, str]]:
    """PURE: the five arms, judged from the instrument's own payload.

    Pure on purpose: the negative arm feeds crafted payloads to THIS function,
    so the control judges the real judge instead of a copy of it.
    """
    rows: list[tuple[str, bool, str]] = []

    fams = (payload or {}).get("families") or []
    measured = payload is not None and rc in (0, 2, 3) and bool(fams)
    rows.append(("A1-tabela-medida", measured,
                 "rc=%s familias=%d" % (rc, len(fams)) if payload is not None
                 else "o instrumento nao devolveu JSON (rc=%s)" % rc))

    empty = [f.get("family") for f in fams if str(f.get("verdict")).upper() == "EMPTY"]
    rows.append(("A2-nenhuma-familia-vazia", not empty,
                 "vazias=%s" % (empty or "nenhuma")))

    over = [f.get("family") for f in fams
            if str(f.get("verdict")).upper() in ("OVER", "TRUNCATED")]
    rows.append(("A3-nenhum-tecto-violado", not over,
                 "acima=%s" % (over or "nenhuma")))

    # A5 first so A4's message can be read on its own.
    nameless = [f.get("family") for f in fams if not str(f.get("producer") or "").strip()]
    rows.append(("A5-toda-familia-nomeia-producer", not nameless,
                 "sem_producer=%s" % (nameless or "nenhuma")))

    if payload is not None and fams:
        parts = sum(int(f.get("bytes") or 0) for f in fams)
        total = int(payload.get("total_bytes") or 0)
        # An EMPTY family contributes 0 on both sides, so this arm is about
        # double counting only; it is checked on every payload that has one.
        ok = parts == total
        rows.append(("A4-soma-e-o-total", ok,
                     "soma=%d total=%d delta=%d" % (parts, total, parts - total)))
    else:
        rows.append(("A4-soma-e-o-total", False, "sem payload para somar"))

    return rows


def normal(project: str, as_json: bool) -> int:
    rc, payload, err = _run(project)
    if rc == -1:
        print("VERDICT: CANNOT-MEASURE -- %s" % err)
        return EXIT_CANNOT
    if rc == -2:
        print("VERDICT: CANNOT-MEASURE -- %s" % err)
        return EXIT_CANNOT
    rows = judge(rc, payload)
    bad = [r for r in rows if not r[1]]
    if as_json:
        print(json.dumps({
            "arms": [{"arm": a, "ok": ok, "detail": d} for a, ok, d in rows],
            "families": len((payload or {}).get("families") or []),
            "total_bytes": (payload or {}).get("total_bytes"),
            "instrument_rc": rc,
            "verdict": "GREEN" if not bad else "RED",
        }, ensure_ascii=False))
    else:
        for arm, ok, detail in rows:
            print("ARM %-36s %s  %s" % (arm, "GREEN" if ok else "RED", detail))
        for fam in (payload or {}).get("families") or []:
            print("  %-28s %12d B %6d f  %-5s cap=%.3f GiB  [%s]"
                  % (fam.get("family"), fam.get("bytes") or 0, fam.get("files") or 0,
                     fam.get("verdict"), float(fam.get("cap_gib") or 0),
                     fam.get("kind")))
        print("TOTAL %d B / %d familias" % ((payload or {}).get("total_bytes") or 0,
                                            len((payload or {}).get("families") or [])))
        print("VERDICT:", "GREEN" if not bad else "RED",
              "-- %d/%d arms, instrumento rc=%s" % (len(rows) - len(bad), len(rows), rc))
    return EXIT_PASS if not bad else EXIT_FAIL


#: Cada mutacao e' (nome, o que ela PROVA, como se constroi o caso). O braco
#: negativo constroi cada caso num directoriao temporario e exige o juiz VERMELHO
#: -- a casa devolve rc 1 quando todos os mutantes foram apanhados.
def _mutant_empty(tmp: str) -> tuple[str, int]:
    open(os.path.join(tmp, ".artifacts.toml"), "w", encoding="utf-8").write(
        '[[family]]\nname="ghost"\nroots=["nope"]\nproducer="x"\n'
        'kind="reclaimable"\ncap_gib=1.0\n')
    return tmp, 0


def _mutant_over(tmp: str) -> tuple[str, int]:
    keep = os.path.join(tmp, "keep")
    os.makedirs(keep, exist_ok=True)
    with open(os.path.join(keep, "blob.bin"), "wb") as fh:
        fh.write(b"x" * 4096)
    open(os.path.join(tmp, ".artifacts.toml"), "w", encoding="utf-8").write(
        '[[family]]\nname="tiny-cap"\nroots=["keep"]\nproducer="x"\n'
        'kind="reclaimable"\ncap_gib=0.000001\n')
    return tmp, 0


def _mutant_no_producer(tmp: str) -> tuple[str, int]:
    keep = os.path.join(tmp, "keep")
    os.makedirs(keep, exist_ok=True)
    with open(os.path.join(keep, "blob.bin"), "wb") as fh:
        fh.write(b"x")
    open(os.path.join(tmp, ".artifacts.toml"), "w", encoding="utf-8").write(
        '[[family]]\nname="nameless"\nroots=["keep"]\nproducer=""\n'
        'kind="reclaimable"\ncap_gib=1.0\n')
    return tmp, 0


def _mutant_absent(tmp: str) -> tuple[str, int]:
    # SEM manifesto: o instrumento responde rc 5 e nao devolve tabela.
    return tmp, 0


MUTANTS = (
    ("familia-vazia", "A2", _mutant_empty),
    ("tecto-violado", "A3", _mutant_over),
    ("familia-sem-producer", "A5", _mutant_no_producer),
    ("sem-manifesto", "A1", _mutant_absent),
)


def neg_arm() -> int:
    bad = 0
    for name, expect_arm, build in MUTANTS:
        with tempfile.TemporaryDirectory(prefix="artifact-neg-") as tmp:
            project, _ = build(tmp)
            rc, payload, err = _run(project, timeout=120.0)
            rows = judge(rc, payload)
            failed_arms = [a for a, ok, _ in rows if not ok]
            caught = bool(failed_arms) and any(a.startswith(expect_arm) for a in failed_arms)
            if caught:
                print("NEG-ARM %-22s PASS -- %s vermelho (%s)"
                      % (name, expect_arm, ", ".join(failed_arms)))
            else:
                print("NEG-ARM %-22s FAIL -- %s ficou VERDE (rc=%s arms=%s%s)"
                      % (name, expect_arm, rc, failed_arms, (" " + err) if err else ""))
                bad += 1
    print("\n%d/%d mutacoes avermelharam o seu braco" % (len(MUTANTS) - bad, len(MUTANTS)))
    # HOUSE CONVENTION: rc 1 quando todos os mutantes foram apanhados (o
    # `:expectred` da bateria exige rc=1), rc 2 quando o proprio controlo falhou.
    print("NEG-ARM VERDICT:", "PASS" if not bad else "FAIL")
    # The battery's `:expectred` for this step asks for the exact bytes
    # "NEG-ARM PASS"; the older verdict line above is kept for the receipt.
    print("NEG-ARM PASS" if not bad else "NEG-ARM FAIL")
    return 2 if bad else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="o portao da tabela de artefactos")
    ap.add_argument("--project", default=ROOT)
    ap.add_argument("--neg-arm", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.neg_arm:
        return neg_arm()
    return normal(os.path.abspath(args.project), args.json)


if __name__ == "__main__":
    sys.exit(main())
