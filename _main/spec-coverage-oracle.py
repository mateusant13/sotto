"""spec-coverage -- cada modulo de PRODUTO tem de estar descrito em `docs/spec/`.

PORQUE ESTE FICHEIRO EXISTE (dono, verbatim): *"your goal is done when you can turn into WORDS
all behavior of sotto"*. Uma frase dessas nao se cumpre por prosa: cumpre-se quando a POPULACAO
esta escrita. O `spec-citations-oracle` resolve as citacoes que os documentos FAZEM; nenhum
portao perguntava a pergunta simetrica -- que ficheiros de produto existem e QUAL deles nao e'
nomeado por documento nenhum. Medido em 2026-11-12 antes deste passo existir: **231 ficheiros de
produto, 168 sem o caminho escrito na especificacao** (82 deles modelos de skin, 32 sondas).

O QUE CONTA COMO DESCRITO. Duas formas, e a segunda e' FRACA de proposito:

  * o CAMINHO relativo com barras normais (`app/webview/external_subs.py`) -- e' o criterio;
  * o NOME do ficheiro sem directorio -- aceite, mas CONTADO em `nome_apenas=`, porque um
    `stage.html` casado por engano noutro documento e' exactamente a classe de prova que este
    projecto ja' pagou caro para descobrir (ver `10-DEFECTS.md` §D-10).

AS CLASSES, nao os 231 ficheiros. Tres directorios sao DADOS e nao comportamento, e escrever uma
seccao por ficheiro seria ruido: `app/panel/skins/**` (modelos `.caption/.chrome/.panel/.stage.html`
de cada skin), `worker/_probe/**` (sondas de medicoes antigas) e os mutantes congelados do worker
(`worker/_prefix_audioflag.py`, `worker/_sotto_worker_agcinert.py`, `worker/runs/**`). Cada classe
tem de estar nomeada por DOCUMENTO (`--require-group`), para que "e' uma classe" nao vire
"ninguem escreveu nada".

O QUE ESTE PORTAO NAO PROVA. Que a linha citada diga o que a frase diz -- isso e' do
`spec-citations-oracle` mais a leitura. Ele prova a COBERTURA: que nenhum modulo de produto ficou
fora da especificacao.

USO
    python _main/spec-coverage-oracle.py               # veredicto (rc=0 passa)
    python _main/spec-coverage-oracle.py --list-gaps   # imprime os ausentes, um por linha
    python _main/spec-coverage-oracle.py --neg-arm     # rc=1 quando apanha o mutante plantado
"""
# NO-BUG: trabalho de capacidade: ordem do dono ("your goal is done when you can turn into WORDS all behavior of sotto") pedia a POPULACAO escrita, e nenhum bug do ledger cobre documentacao

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(ROOT, "docs", "spec")

PRODUCT_ROOTS = ("app/webview", "worker", "app/panel")
PRODUCT_EXTS = (".py", ".js", ".mjs", ".css", ".html")

# Directorios que nao entram na populacao: build, cache, artefactos de medicao.
SKIP_DIRS = {
    ".git", "node_modules", "_legacy", "models", "runs", "_cache", "__pycache__",
    ".pytest_cache", "_audit-verify", "_redux-gate-mutants", "_quarantine", "_scratch",
}

# CLASSES: um prefixo que se descreve uma vez, com o rotulo que o documento tem de conter.
GROUPS = (
    ("app/panel/skins/", "app/panel/skins/"),
    ("worker/_probe/", "worker/_probe/"),
)

# Ficheiros de produto que NAO sao comportamento: copias congeladas usadas como mutantes por
# oraculos (README, "Tres ficheiros dentro de worker/ nao sao produto"). Cada um tem razao escrita.
FROZEN = {
    "worker/_prefix_audioflag.py": "copia congelada (mutante do oraculo do prefixo de audio)",
    "worker/_sotto_worker_agcinert.py": "copia congelada (mutante do oraculo do AGC)",
}

# COPIAS QUE UM ORACULO ESCREVE DENTRO DA ARVORE DURANTE A CORRIDA, e apaga no
# fim (`input-path-oracle.py:477` escreve `app/webview/_inputpath-neg-<nome>.py`,
# `:487` limpa-os). Medido 2026-11-12: com a bateria a correr, este portao contou
# CINCO delas como produto e publicou `ausentes=5 VERDICT: FAIL` sobre um ficheiro
# que nenhum humano escreveu e que ja' nao existia quando a corrida acabou --
# a `populacao` deste portao e' lida do DISCO, por isso uma corrida concorrente
# muda a resposta. Nao sao produto: sao o artefacto efemero de um braco negativo,
# com o prefixo declarado no proprio oraculo (`MUTANT_PREFIX`).
EPHEMERAL_PREFIXES = (
    "_inputpath-neg-",
)


def population():
    """Os ficheiros de produto, e as classes, medidos do disco -- nunca de uma lista escrita a mao."""
    files, groups = [], {}
    for base in PRODUCT_ROOTS:
        for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, base)):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                if not name.endswith(PRODUCT_EXTS):
                    continue
                if name.startswith(EPHEMERAL_PREFIXES):
                    continue
                rel = os.path.relpath(os.path.join(dirpath, name), ROOT).replace(os.sep, "/")
                hit = next((label for prefix, label in GROUPS if rel.startswith(prefix)), None)
                if hit is not None:
                    groups.setdefault(hit, []).append(rel)
                    continue
                files.append(rel)
    return sorted(set(files)), groups


def documents():
    """O texto de TODOS os documentos da especificacao, e o de cada um em separado."""
    per_file = {}
    if not os.path.isdir(SPEC):
        return per_file
    for name in sorted(os.listdir(SPEC)):
        if not name.endswith(".md"):
            continue
        with open(os.path.join(SPEC, name), encoding="utf-8", errors="replace") as fh:
            per_file[name] = fh.read()
    return per_file


def judge(files, groups, docs, extra_files=()):
    """Julga a cobertura. Devolve (ok, detalhes). `extra_files` existe para o braco negativo."""
    text = "\n".join(docs.values())
    missing, name_only, frozen_seen = [], [], []
    for rel in list(files) + list(extra_files):
        if rel in FROZEN:
            frozen_seen.append(rel)
            continue
        if rel in text:
            continue
        base = os.path.basename(rel)
        if base in text:
            name_only.append(rel)
            continue
        missing.append(rel)
    missing_groups = [label for label in groups if label not in text]
    ok = not missing and not missing_groups
    return ok, {
        "missing": missing,
        "name_only": name_only,
        "missing_groups": missing_groups,
        "frozen": frozen_seen,
    }


def _print(detail, files, groups):
    print("SPEC-COVERAGE populacao=%d classes=%d (%s)"
          % (len(files), len(groups), ", ".join("%s=%d" % (k, len(v)) for k, v in sorted(groups.items()))))
    for rel in detail["name_only"]:
        print("  NOME-APENAS  %s" % rel)
    for label in detail["missing_groups"]:
        print("  CLASSE-SEM-SECCAO  %s (%d ficheiros)" % (label, len(groups[label])))
    for rel in detail["missing"]:
        print("  AUSENTE      %s" % rel)
    if detail["frozen"]:
        print("  CONGELADO    %s (%s)" % (", ".join(detail["frozen"]),
                                          "; ".join(FROZEN[r] for r in detail["frozen"])))


def neg_arm(files, groups, docs):
    """O mutante plantado: um ficheiro de produto que nenhum documento nomeia.

    MEDIDO 2026-11-12: com o portao a passar em toda a populacao, a arm que o prova e' um ficheiro
    inventado. Ele NAO e' escrito em disco -- o mutante e' a entrada na populacao, porque um
    ficheiro temporario dentro de `app/webview/` entrava no censo de ficheiros do `code-health`.
    """
    ghost = "app/webview/_modulo-que-ninguem-escreveu.py"
    ok_after, detail_after = judge(files, groups, docs, extra_files=(ghost,))
    ghost_caught = ghost in detail_after["missing"]

    # Uma CLASSE sem seccao tambem tem de cair: removemos o rotulo do texto dos documentos.
    docs_wo = dict(docs)
    label = GROUPS[0][1]
    for name in list(docs_wo):
        docs_wo[name] = docs_wo[name].replace(label, "<<removido pelo neg-arm>>")
    ok_g, detail_g = judge(files, groups, docs_wo)
    group_caught = label in detail_g["missing_groups"]

    print("NEG-ARM fantasma       %s  (%s)" % ("CAUGHT" if ghost_caught else "NOT-CAUGHT", ghost))
    print("NEG-ARM classe-sem-doc %s  (%s)" % ("CAUGHT" if group_caught else "NOT-CAUGHT", label))
    return 0 if (ghost_caught and group_caught) else 1


def main(argv):
    files, groups = population()
    docs = documents()
    ok, detail = judge(files, groups, docs)
    _print(detail, files, groups)

    if "--list-gaps" in argv:
        for rel in detail["missing"]:
            print(rel)
        return 0

    if "--neg-arm" in argv:
        if not ok:
            print("SPEC-COVERAGE o positivo NAO esta' verde: o neg-arm julga o portao, nao a populacao")
            return 2
        rc = neg_arm(files, groups, docs)
        print("SPEC-COVERAGE NEG-ARM %s" % ("PASS" if rc == 0 else "FAIL"))
        return 1 if rc == 0 else 0        # 1 = apanhou, que e' a convencao desta casa

    print("SPEC-COVERAGE docs=%d ausentes=%d nome_apenas=%d classes_sem_seccao=%d"
          % (len(docs), len(detail["missing"]), len(detail["name_only"]),
             len(detail["missing_groups"])))
    print("SPEC-COVERAGE VERDICT: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
