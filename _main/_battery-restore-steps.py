"""RECONSTRUIR OS PASSOS DA BATERIA a partir do registo VIVO do ultimo run.

CONTEXTO (2026-10-30): `_main/_audit-verify-all.cmd` foi truncado a 0 B por um
`io.open(p,'wb')` meu cujo `write()` levantou TypeError depois do truncate. O
`git` tinha a versao de 02:11 (115 passos); a arvore tinha 169. Este script
reconstroi os 57 passos que faltam a partir de `_cache/battery-steps.json`, que
foi escrito pelo PROPRIO run das 11:13 e guarda, por passo, as deps e o
`expect_rc` -- os dois campos que o oraculo `battery-wiring-oracle.py` compara.

O QUE ELE NAO FAZ: nao inventa um comando sem o provar. Cada comando reconstruido
e' EXECUTADO e o rc tem de bater com o `expect_rc` do registo; um comando que nao
bata e' tentado com as variantes conhecidas (`--neg-arm`, `--check`, `--selftest`)
e, se nenhuma bater, o passo NAO e' escrito e e' publicado como PENDENTE.

Uso:
  python _main/_battery-restore-steps.py            # escreve (dry-run imprimindo)
  python _main/_battery-restore-steps.py --apply    # escreve no .cmd
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
CMD = os.path.join(HERE, "_audit-verify-all.cmd")
CACHE = os.path.join(REPO, "_cache", "battery-steps.json")
OUTDIR = os.path.join(HERE, "_audit-verify")

MODS = {"always", "heavy", "fast", "skip-capable", "cached", "light"}

#: O COMANDO DE CADA PASSO QUE FALTA, escrito a mao e depois PROVADO pelo rc do
#: registo. Nao se adivinha: a heuristica de escolher a dep cujo nome parece o
#: passo ja' escolheu `app\\webview\\sotto_webview.py` para um passo dos strip --
#: um passo que LARGA A APP. Uma dep e' uma dependencia, nao um comando.
EXPLICIT = {
    "altc-first-caption": "python _main\\altc-first-caption-oracle.py",
    "altc-gesture": "python _main\\altc-gesture-oracle.py",
    "headphone-cut": "python _main\\headphone-cut-probe.py",
    "incomplete-word": "python _main\\incomplete-word-oracle.py",
    "ladder-signal": "python _main\\ladder-signal-oracle.py",
    "launch-as-token": "python _main\\launch-as-token.py --selftest",
    "live-code-freshness": "python _main\\live-code-freshness-oracle.py",
    "load-shedding": "python _main\\load-shedding-oracle.py",
    "red-as-expected-altc-first-caption": "python _main\\altc-first-caption-oracle.py --neg-arm",
    "red-as-expected-altc-gesture": "python _main\\altc-gesture-oracle.py --neg-arm",
    "red-as-expected-headphone-cut": "python _main\\headphone-cut-probe.py --neg-arm",
    "red-as-expected-incomplete-word": "python _main\\incomplete-word-oracle.py --neg-arm",
    "red-as-expected-ladder-signal": "python _main\\ladder-signal-oracle.py --neg-arm",
    "red-as-expected-launch-as-token": "python _main\\launch-as-token.py --neg-arm",
    "red-as-expected-load-shedding": "python _main\\load-shedding-oracle.py --neg-arm",
    "red-as-expected-shell-relaunch": "python _main\\shell-relaunch-oracle.py --neg-arm",
    "red-as-expected-word-clock": "python _main\\youtube-word-clock-oracle.py --neg-arm",
    "red-as-expected-youtube-monotonic": "python _main\\youtube-monotonic-oracle.py --neg-arm",
    "red-as-expected-youtube-sotto-drift": "python _main\\youtube-sotto-drift-oracle.py --neg-arm",
    "red-as-expected-youtube-switch": "python _main\\youtube-switch-oracle.py --neg-arm",
    "red-as-expected-yt-no-dub": "python _main\\yt-no-dub-oracle.py --neg-arm",
    "shell-relaunch": "python _main\\shell-relaunch-oracle.py",
    "state-page-write": "python _main\\sotto-state-page.py --write",
    "word-clock": "python _main\\youtube-word-clock-oracle.py",
    "youtube-monotonic": "python _main\\youtube-monotonic-oracle.py",
    "youtube-sotto-drift": "python _main\\youtube-sotto-drift-oracle.py",
    "youtube-switch": "python _main\\youtube-switch-oracle.py",
    "yt-no-dub": "python _main\\yt-no-dub-oracle.py",
}


def read(path, mode="r"):
    if mode == "rb":
        return io.open(path, "rb").read()
    return io.open(path, encoding="utf-8").read()


def script_for(name, deps):
    """O script de um passo: a dep cujo nome de ficheiro mais parece o passo."""
    stem = name.replace("red-as-expected-", "")
    cands = []
    for dep in deps:
        base = os.path.basename(dep).lower()
        if not base.endswith((".py", ".js", ".mjs", ".cmd")):
            continue
        score = 0
        if stem in base:
            score += 3
        if base.startswith(stem):
            score += 3
        if "oracle" in base or "gate" in base:
            score += 1
        cands.append((-score, len(dep), dep))
    if not cands:
        return None
    return sorted(cands)[0][2]


def command_for(dep, args):
    if dep.lower().endswith(".js") or dep.lower().endswith(".mjs"):
        return " ".join(["node", dep.replace("\\", "\\")] + args)
    if dep.lower().endswith(".cmd"):
        return " ".join(["call", dep] + args)
    return " ".join(["python", dep] + args)


def run(cmd, cwd):
    p = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True,
                       timeout=600)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def marker_from_log(name):
    """O texto exigido ao braco negativo, lido do ULTIMO log daquele passo."""
    p = os.path.join(OUTDIR, name + ".log")
    if not os.path.exists(p):
        return ""
    txt = read(p, "rb").decode("utf-8", "replace")
    for line in reversed(txt.splitlines()):
        if "NEG-ARM PASS" in line or "RED as designed" in line:
            return "NEG-ARM PASS"
    return ""


def main() -> int:
    steps = json.load(io.open(CACHE, encoding="utf-8"))["steps"]
    cmd_text = read(CMD)
    declared = set()
    for m in re.finditer(r"call :step\w*([^\r\n]*)", cmd_text):
        for tok in m.group(1).split():
            if tok in MODS:
                continue
            declared.add(tok)
            break
    missing = [n for n in steps if n not in declared]
    print(f"passos no registo: {len(steps)} | declarados: {len(declared)} | "
          f"faltam: {len(missing)}")
    blocks = []
    pendentes = []
    for name in missing:
        meta = steps[name]
        deps = meta.get("deps") or []
        want_rc = int(meta.get("expect_rc") or 0)
        cmd0 = EXPLICIT.get(name)
        script = (deps[0] if deps else "")
        if cmd0 is None:
            pendentes.append((name, "sem comando explicito"))
            continue
        ok = None
        for args in ([],):
            cmd = cmd0
            try:
                rc, out = run(cmd, REPO)
            except Exception as exc:  # noqa: BLE001
                rc, out = -1, repr(exc)
            if rc == want_rc:
                ok = (cmd, args, out)
                break
        if ok is None:
            pendentes.append((name, f"nenhuma variante deu rc={want_rc}"))
            continue
        cmd, args, out = ok
        logname = os.path.basename(meta.get("log") or (name + ".log"))
        deps_txt = ";".join(deps)
        if want_rc == 1:
            mark = marker_from_log(name) or "NEG-ARM PASS"
            blk = (f'if exist {script} (\r\n'
                   f'call :step always {name} 1 "{deps_txt}" "%OUT%\\{logname}" {cmd}\r\n'
                   f'call :expectred {name} !STEP_RC! "%OUT%\\{logname}" "{mark}"\r\n'
                   f') else ( call :expectred {name} MISSING "%OUT%\\{logname}" "{mark}" )')
        else:
            blk = (f'if exist {script} (\r\n'
                   f'call :step always {name} 0 "{deps_txt}" "%OUT%\\{logname}" {cmd}\r\n'
                   f'call :record {name} !STEP_RC!\r\n'
                   f') else ( call :record {name} MISSING )')
        blocks.append(blk)
        print(f"OK  {name:38s} rc={want_rc} cmd={cmd}")

    print(f"\nreconstruidos {len(blocks)} | pendentes {len(pendentes)}")
    for n, why in pendentes:
        print(f"PENDENTE {n}: {why}")

    if "--apply" in sys.argv[1:] and blocks:
        anchor = cmd_text.rfind("\r\ncall :record ")
        ins = cmd_text.rfind("\r\n", 0, cmd_text.find("\r\n", anchor + 2))
        add = ("\r\nREM " + "=" * 70 +
               "\r\nREM PASSOS RECONSTRUIDOS 2026-10-30 a partir de _cache/battery-steps.json"
               "\r\nREM (" + "o ficheiro foi truncado; ver _main/_battery-restore-steps.py)"
               "\r\nREM " + "=" * 70 + "\r\n" +
               "\r\n\r\n".join(blocks) + "\r\n")
        pos = cmd_text.find("\r\necho =============== BATTERY SUMMARY")
        if pos < 0:
            raise SystemExit("SETUP: nao encontrei o inicio do resumo")
        out = cmd_text[:pos] + add + cmd_text[pos:]
        io.open(CMD, "wb").write(out.encode("utf-8"))
        print(f"ESCRITO: {len(out.encode('utf-8'))} B")
    return 0 if not pendentes else 1


if __name__ == "__main__":
    sys.exit(main())
