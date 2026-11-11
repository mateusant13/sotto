#!/usr/bin/env python
# NO-BUG: julga a FORMA do WORKER_BOOT_PROF (marcas monotonas e atribuiveis), nao opina sobre nenhum milissegundo do arranque nem o reduz.
"""O portao do `WORKER_BOOT_PROF`: onde os 8,5-44,3 s do arranque foram gastos.

CARD DO DONO (verbatim): *"arranque: demora DEMAIS a responder"*. O custo existia
e nao tinha dono: medido no log vivo (`_main/webview-run.log`), `BRIDGE_LOAD_MS
ms=28938 / 8953 / 44344`, e a unica copia do perfil ia para o stderr do worker, que
a shell so' publica na cauda da MORTE -- `grep -c WORKER_BOOT_PROF` no log dele
dava **ZERO**. A cura (2026-11-10) poe a tag em `ENGINE_VISIBLE_TAGS`, e este
oraculo e' o que le' a linha que agora chega.

O QUE ELE JULGA, e o que ele NAO faz: ele NAO opina sobre o valor de nenhum
milissegundo -- um limiar de latencia nesta maquina degradada seria um numero
inventado, e a casa proibe limiar de gosto. Ele julga a FORMA, que e' o que torna
o numero atribuivel:

  A1 a ultima linha `WORKER_BOOT_PROF` do log parseia em `name=value` (float)
  A2 as tres sessoes ORT estao la' e sao MONOTONAS (`sess_encoder` <
     `sess_decoder` < `sess_joint`): fora de ordem, o que esta' marcado nao e' o
     que o nome diz
  A3 `og_model` vem DEPOIS de `sess_joint` -- se vier antes, as marcas estao
     trocadas e a atribuicao e' ficcao
  A4 o perfil tem pelo menos SEIS marcas: um perfil de duas marcas nao explica
     boot nenhum
  A5 o total e' IMPRESSO, com as marcas em ordem -- o numero que o dono paga tem
     de estar na saida do passo, nao so' no ficheiro dele
  K  sem linha nenhuma: `SKIPPED` (o worker ainda nao arrancou com a cura), e um
     passo saltado nunca conta como verde

USO
  python _main/boot-profile-oracle.py            -> rc=0 (PASS ou SKIPPED)
  python _main/boot-profile-oracle.py --neg-arm  -> julga perfis FALSOS e exige
                                                    a recusa dos tres mutantes
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "_main", "webview-run.log")

TAG = "WORKER_BOOT_PROF"
_PAIR = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=(-?[0-9]+(?:\.[0-9]+)?)")
#: AS MARCAS VIAJAM EM DOIS OBJETOS JSON, e o regex de pares planos lia `pid=`.
#: MEDIDO no log vivo (2026-11-11): a linha do produto e'
#:   WORKER_BOOT_PROF pid=20984 boot_prof_s={"cuda_dirs": 0.022, ...,
#:                   "sess_joint": 5.091} load_phases_s={"encoder": 4.748, ...}
#: -- o `_PAIR` casava o `pid` e devolvia um perfil de UMA marca, o que reprovava
#: A2 e A4 num arranque perfeitamente atribuivel. O perfil e' a UNIAO dos dois
#: objectos (`boot_prof_s` traz as fases de import e as sessoes ORT,
#: `load_phases_s` traz o detalhe do carregamento), e um `pid` nao e' marca de
#: tempo: ele fica FORA do dict que o `judge` mede.
_OBJ = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=(\{[^{}]*\})")


def parse_profiles(text):
    """Todas as linhas `WORKER_BOOT_PROF` do texto, em ordem, como dicts."""
    out = []
    for line in text.splitlines():
        i = line.find(TAG)
        if i < 0:
            continue
        body = line[i + len(TAG):]
        prof = {}
        for key, raw in _OBJ.findall(body):
            try:
                loaded = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(loaded, dict):
                continue
            for name, value in loaded.items():
                try:
                    prof[name] = float(value)
                except (TypeError, ValueError):
                    continue
        # O formato PLANO (`sess_encoder=6.5 sess_joint=6.9`) continua a ser
        # lido: e' a forma das fixtures antigas e dos braços negativos, e um
        # parser que so' conhecesse a forma nova transformaria `--log <fixture>`
        # num SKIP silencioso.
        if not prof:
            prof = dict((k, float(v)) for k, v in _PAIR.findall(body)
                        if k != "pid")
        if prof:
            out.append(prof)
    return out


def judge(prof):
    """As quatro propriedades de forma. Devolve a lista de nomes que falham."""
    fails = []
    if len(prof) < 6:
        fails.append("A4")
    order = ("sess_encoder", "sess_decoder", "sess_joint")
    if not all(m in prof for m in order):
        fails.append("A2")
    else:
        vals = [prof[m] for m in order]
        if not (vals[0] <= vals[1] <= vals[2]):
            fails.append("A2")
    if "sess_joint" in prof and "og_model" in prof and prof["og_model"] < prof["sess_joint"]:
        fails.append("A3")
    if not prof:
        fails.append("A1")
    return fails


def print_split(prof):
    """O split, na ordem em que aconteceu -- por VALOR, nao pela ordem do dict."""
    items = sorted(prof.items(), key=lambda kv: kv[1])
    prev = 0.0
    parts = []
    for name, t in items:
        parts.append("%s=+%.3f" % (name, t - prev))
        prev = t
    print("  SPLIT total=%.3fs  %s" % (prev, " ".join(parts)))


def main(argv):
    global LOG
    if "--log" in argv:
        # ler OUTRO log (um spawn de probe, um fixture) -- e' o que permite
        # exercitar A1-A4 contra um perfil REAL nesta maquina.
        i = argv.index("--log")
        LOG = argv[i + 1]
    if "--neg-arm" in argv:
        clean = {"cuda_dirs": 0.081, "probe": 0.359, "numpy_import": 0.379,
                 "ort_import": 0.379, "og_import": 0.395, "sess_encoder": 6.14,
                 "sess_decoder": 6.245, "sess_joint": 6.296, "og_model": 8.543,
                 "og_processor": 8.572}
        mutants = {
            "M1_ordem_das_sessoes": dict(clean, sess_decoder=6.0),
            "M2_og_model_antes_das_sessoes": dict(clean, og_model=1.0),
            "M3_perfil_curto": {"og_model": 8.5, "og_processor": 8.6},
        }
        if judge(clean):
            print("NEG-ARM: FAIL -- o perfil LIMPO ja' reprova (%s)" % judge(clean))
            return 1
        caught = 0
        for name, prof in mutants.items():
            bad = judge(prof)
            if bad:
                caught += 1
                print("  %-30s CAUGHT (%s)" % (name, ",".join(bad)))
            else:
                print("  %-30s NOT-CAUGHT" % name)
        total = len(mutants)
        print("NEG-ARM: %s -- %d/%d mutantes apanhados"
              % ("PASS" if caught == total else "FAIL", caught, total))
        # CONVENCAO DA CASA: o negativo devolve 1 AO APANHAR. Um controlo que
        # devolve 0 ao apanhar e' um passo normal a espera de 0, e o `:expectred`
        # do `.cmd` nunca o ve'.
        return 1 if caught == total else 0

    print("BOOT-PROFILE")
    if not os.path.exists(LOG):
        print("  K    SKIP  log ausente: %s" % LOG)
        print("VERDICT: SKIPPED")
        return 0
    with open(LOG, "r", encoding="utf-8", errors="replace") as fh:
        profiles = parse_profiles(fh.read())
    if not profiles:
        print("  K    SKIP  nenhuma linha %s no log (o worker ainda nao arrancou "
              "com a cura de visibilidade)" % TAG)
        print("VERDICT: SKIPPED")
        return 0
    prof = profiles[-1]
    fails = judge(prof)
    print("  A1   %s  %d marcas lidas" % ("ok" if "A1" not in fails else "FAIL", len(prof)))
    print("  A2   %s  sessoes ORT monotonas" % ("ok" if "A2" not in fails else "FAIL"))
    print("  A3   %s  og_model depois de sess_joint" % ("ok" if "A3" not in fails else "FAIL"))
    print("  A4   %s  perfil com >= 6 marcas" % ("ok" if "A4" not in fails else "FAIL"))
    print_split(prof)
    print(json.dumps({"profiles": len(profiles), "marks": prof}, sort_keys=True))
    print("")
    if fails:
        print("VERDICT: FAIL -- %s" % "; ".join(sorted(set(fails))))
        return 1
    print("VERDICT: PASS -- 4 arm(s), 0 failure(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
