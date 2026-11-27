#!/usr/bin/env python
"""O braco vermelho do `feature_map_sync --gate`, como o benchmark o exige.

MEDIDO 2026-11-27: `subsystem.feature_map_gate_ms` declarava
`feature_map_sync.py --repo . --gate --selftest` como `red_arm_cmd`, e essa
combinacao devolve **0** -- o benchmark leu `FALSE-GREEN (red_arm_cmd exited 0)`
na corrida `--verify-red`. O `--selftest` prova os bracos DENTRO do script e sai
verde; o que o benchmark precisa e' um comando que SAIA VERMELHO quando o portao
esta' a funcionar.

A forma e' a do resto da arvore (`--neg-arm`, mutante apanhado = rc 1): aqui
monta-se um repo temporario com o mapa de features AUSENTE, corre-se o portao
canonico contra ele e:

  rc 1 = o portao RECUSOU um repo derivado  -> `NEG-ARM: PASS`   (mutante apanhado)
  rc 0 = o portao PASSOU um repo derivado   -> `NEG-ARM: FAIL`   (verde falso)

Um tema raso nao chega: o repo temporario tem de conter o que o portao procura
primeiro (`features/INDEX.md`), senao o vermelho vem de um ficheiro que falta por
motivo errado e nao de `features.json` ausente.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

CANON = r"C:\Users\Administrador\.agents\skills\project-revival\scripts\feature_map_sync.py"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    canon = argv[0] if argv else CANON
    if not os.path.isfile(canon):
        print(f"CANNOT-MEASURE why=no-canonical-script path={canon}")
        return 3
    with tempfile.TemporaryDirectory(prefix="fmap-neg-") as tmp:
        os.makedirs(os.path.join(tmp, "features"), exist_ok=True)
        # INDEX.md existe, features.json NAO: o problema tem de ser o mapa, nao a pasta.
        with open(os.path.join(tmp, "features", "INDEX.md"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("# INDEX (deliberadamente sem features.json)\n")
        proc = subprocess.run(
            [sys.executable, canon, "--repo", tmp, "--gate", "--no-agents"],
            capture_output=True, text=True, timeout=120,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0:
            marker = "missing features/features.json"
            if marker not in out:
                # Recusou, mas por outra razao: o braco nao prova o que diz provar.
                print(f"NEG-ARM: FAIL -- refused rc={proc.returncode} for the WRONG reason")
                print(out.strip()[:400])
                return 0
            print(f"NEG-ARM: PASS -- gate refused the map-less repo (rc={proc.returncode})")
            return 1
        print("NEG-ARM: FAIL -- the gate PASSED a repo with no features/features.json")
        print(out.strip()[:400])
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
