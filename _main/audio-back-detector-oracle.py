#!/usr/bin/env python
# NO-BUG: o passo puro "audio voltou e a legenda nao" nao toca no audio nem no ecra -- nao cura a captura, so nomeia qual das duas metades parou.
"""Portao do `audio_back_step`: "o audio voltou e nada acontece" tem duas linhas.

CARD DO DONO (verbatim): *"audio volta e nada acontece"*. O worker ja' publicava
`TAP_IDLE`/`TAP_STALLED` quando o audio SUMIA e `WORKER_RESUMED` quando o PARQUE
acabava; nenhuma das duas responde a pergunta dele -- **os blocos voltaram e a
legenda nao?** O par (blocos a subir, `captions` parado) nao era lido por linha
nenhuma, logo o sintoma era indistinguivel de um worker saudavel a transcrever
silencio.

O QUE ESTE ORACULO JULGA: a maquina PURA `worker.sotto_worker.audio_back_step`
(o chamador no laco de audio apenas passa os numeros) e o SITE de chamada, por
`ast` -- nada aqui abre dispositivo, toca audio ou precisa da tela do dono.

  A1 lacuna (`gap_s >= TAP_STALL_S`) fecha em `CAPTURE_SIGNAL_BACK` com os
     numeros do instante
  A2 a mesma lacuna nao re-arma a cada iteracao
  A3 dentro da graca, nada e' dito
  A4 graca vencida + legendas PARADAS -> `NO_CAPTION_AFTER_AUDIO_BACK`
  A5 graca vencida + legendas AVANCARAM -> silencio, e o estado morre
  A6 a linha do defeito sai UMA vez
  A7 `CAPTURE_SIGNAL_BACK` carrega `blocks=` e `captions=`
  A8 `NO_CAPTION_AFTER_AUDIO_BACK` carrega `blocks_delta=` e `captions=`
  A9 o limiar de lacuna E' o `TAP_STALL_S` do ficheiro (lido por `ast`)
  B  o SITE passa `now`, blocos, legendas e `now - stall_since`, e escreve a
     linha por `err(...)`

USO
  python _main/audio-back-detector-oracle.py            -> rc=0 quando passa
  python _main/audio-back-detector-oracle.py --neg-arm  -> muta o codigo numa
                                                           copia e exige rc=1
"""
import ast
import os
import shutil
import sys
import tempfile
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKER = os.path.join(ROOT, "worker", "sotto_worker.py")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

T0 = 1_000_000.0


def parse(src):
    tree = ast.parse(src)
    consts = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            try:
                consts[node.targets[0].id] = ast.literal_eval(node.value)
            except Exception:                                 # noqa: BLE001
                pass
    return tree, consts


#: `ast.get_source_segment` recomputa `splitlines()` da FONTE INTEIRA em cada
#: chamada (CPython: `_splitlines_no_ff` faz `''.join(lines)` sobre tudo). Medido
#: nesta arvore 2026-11-11 com o `cProfile` do braco positivo: **262 chamadas =
#: 58,0 s dos 62,5 s** -- o resto do oraculo custa 4 s. O worker tem 1,5 MB, logo
#: cada chamada era uma varredura completa e a conta crescia com a fonte, nao com
#: a arm. Aqui a quebra em linhas e' feita UMA vez por fonte e so' a fatia e'
#: recalculada, o que devolve exactamente o mesmo texto (mesma rotina privada do
#: CPython que `get_source_segment` usa; `splitlines(keepends=True)` se ela faltar).
_SEG_LINES = {}


def _lines_of(source):
    ent = _SEG_LINES.get(id(source))
    if ent is not None and ent[0] is source:
        return ent[1]
    split = getattr(ast, "_splitlines_no_ff", None)
    lines = split(source) if split else source.splitlines(keepends=True)
    _SEG_LINES[id(source)] = (source, lines)
    return lines


def _seg(source, node):
    """`ast.get_source_segment(source, node)`, com as linhas ja' quebradas."""
    if node is None:
        return None
    if getattr(node, "end_lineno", None) is None \
            or getattr(node, "end_col_offset", None) is None:
        return None
    lines = _lines_of(source)
    first, last = node.lineno - 1, node.end_lineno - 1
    if last == first:
        return lines[first].encode()[node.col_offset:node.end_col_offset].decode()
    head = lines[first].encode()[node.col_offset:].decode()
    tail = lines[last].encode()[:node.end_col_offset].decode()
    return head + "".join(lines[first + 1:last]) + tail


def load_func_namespace(src, path, real_mod):
    """A funcao `audio_back_step` SO', com os globals do worker REAL.

    POR QUE NAO `load_namespace` (medido 2026-11-11): aquele executa o
    `worker/sotto_worker.py` INTEIRO -- 1,5 MB com os imports de topo -- e o
    `--neg-arm` fazia isso UMA VEZ POR MUTANTE. Custo medido sem tecto: positivo
    37,4 s, controlo **136,7 s**; com o tecto de CPU da bateria o passo chegou a
    242,4 s e morreu no prazo de 240 (`rc=124`), que e' o mesmo que nao ter
    controlo nenhum.

    As arms A1-A9 chamam so' a funcao; as arms B/B2/C1/C2 leem o FONTE mutado
    (que continua a ser passado intacto). Entao em vez do ficheiro inteiro
    executa-se o segmento da funcao sobre um namespace semeado com os globals do
    modulo REAL -- que e' o que a funcao veria de qualquer forma.

    O que isto NAO cobre: um mutante cuja diferenca viva FORA da funcao e que so'
    uma arm de COMPORTAMENTO possa ver. Nenhum dos seis de hoje e' assim (M4 e M6
    sao lidos pelo fonte, M1-M3 estao dentro da funcao) -- e se um futuro fosse,
    o mutante sairia `NOT-CAUGHT` e o `--neg-arm` FALHA alto, nunca passa em
    silencio.
    """
    tree = ast.parse(src)
    fn = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "audio_back_step":
            fn = node
            break
    if fn is None:
        raise RuntimeError("audio_back_step ausente na fonte mutada")
    segment = _seg(src, fn)
    mod = types.ModuleType("audio_back_mutant")
    mod.__file__ = path
    mod.__dict__.update({k: v for k, v in vars(real_mod).items()
                         if not k.startswith("__")})
    exec(compile(segment, path, "exec"), mod.__dict__)
    return mod


def run_arms(fn, src, tree, consts, say):
    """Roda A1-A9/B/C sobre a funcao e a fonte dadas. Devolve a lista de falhas."""
    _SRC_CACHE["src"] = src
    fails = []
    stall_s = float(consts["TAP_STALL_S"])
    grace = float(consts["AUDIO_BACK_GRACE_S"])

    def check(name, ok, detail=""):
        if not ok:
            fails.append(name)
        say(name, ok, detail)

    st, line = fn(T0, 120, 4, stall_s + 4.0, None)
    check("A1", bool(line) and "CAPTURE_SIGNAL_BACK" in line, str(line))
    st2, line2 = fn(T0 + 0.1, 121, 4, 0.1, st) if st else (None, "sem estado")
    check("A2", line2 is None and st2 is not None, str(line2))
    _s3, line3 = fn(T0 + grace / 2.0, 200, 4, 0.1, st)
    check("A3", line3 is None, str(line3))
    st4, line4 = fn(T0 + grace + 1.0, 400, 4, 0.1, st)
    check("A4", bool(line4) and "NO_CAPTION_AFTER_AUDIO_BACK" in line4, str(line4))
    st5, line5 = fn(T0 + grace + 1.0, 400, 5, 0.1, st)
    check("A5", line5 is None and st5 is None, "%r %r" % (line5, st5))
    _s6, line6 = fn(T0 + grace + 2.0, 401, 4, 0.1, st4)
    check("A6", line6 is None, str(line6))
    check("A7", "blocks=120" in (line or "") and "captions=4" in (line or ""), str(line))
    check("A8", "blocks_delta=%d" % (400 - 120) in (line4 or "")
          and "captions=4" in (line4 or ""), str(line4))
    # A9 E' ESTRUTURAL, nao textual: um `in src` casava com o proprio comentario
    # que cita o limiar, e o mutante M3 (2,5 no lugar de `TAP_STALL_S`) passava
    # por causa disso -- medido no `--neg-arm` desta mesma rodada.
    cmp_ok = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name) \
                and node.left.id == "gap_s" and len(node.comparators) == 1 \
                and isinstance(node.comparators[0], ast.Name) \
                and node.comparators[0].id == "TAP_STALL_S":
            cmp_ok = True
    check("A9", cmp_ok, "o limiar e' o TAP_STALL_S do ficheiro (por AST)")

    call = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == "audio_back_step":
            call = node
    if call is None:
        check("B", False, "nenhum sitio chama audio_back_step")
        check("B2", False, "sem sitio nao ha' linha")
    else:
        segment = _seg(src, call) or ""
        ok = "stall_since" in segment and "counters" in segment \
            and "device_blocks" in segment
        check("B", ok, segment.replace("\n", " ")[:120])
        check("B2", "_back_line" in src and "err(" in src, "a linha sai por err(...)")

    # ── C: A LINHA CHEGA AO LOG (2026-11-10) ────────────────────────────────
    # Um instrumento cujo output morre no `stderr_tail` e' indistinguivel de um
    # instrumento que nao existe: `WORKER_THREADS` (2026-11-09) foi a primeira
    # vez, e estas quatro tags sao a segunda. Tres coisas tem de ser verdade ao
    # mesmo tempo, e nenhuma delas se ve' no texto do worker sozinho.
    fails.extend(_visibility_arms(check, src))
    return fails


#: As tags que o `err(...)` do worker escreve e que o log do dono tem de ver.
#: `ENGINE_VISIBLE_TAGS` e' casada por `line.startswith`, por isso a posicao da
#: tag na linha faz parte do contrato -- e' o que C2 mede.
VISIBLE = ("LADDER_TRY", "WORKER_BOOT_PROF",
           "CAPTURE_SIGNAL_BACK", "NO_CAPTION_AFTER_AUDIO_BACK")
SHELL = os.path.join(ROOT, "app", "webview", "sotto_webview.py")


def _tag_tuple(shell_src):
    """`ENGINE_VISIBLE_TAGS` da shell, lida do FONTE (sem importar a shell)."""
    stree = ast.parse(shell_src)
    for node in stree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id == "ENGINE_VISIBLE_TAGS":
            try:
                return tuple(ast.literal_eval(node.value))
            except Exception:                                 # noqa: BLE001
                return None
    return None


def _visibility_arms(check, src):
    """C1 as tags estao na allowlist; C2 a tag e' o PRIMEIRO token da linha."""
    fails = []
    if not os.path.exists(SHELL):
        check("C1", False, "shell ausente: %s" % SHELL)
        return ["C1"]
    shell_src = open(SHELL, "r", encoding="utf-8").read()
    tags = _tag_tuple(shell_src)
    if tags is None:
        check("C1", False, "ENGINE_VISIBLE_TAGS ilegivel na shell")
        fails.append("C1")
    else:
        missing = [t for t in VISIBLE if t not in tags]
        check("C1", not missing, {"missing": missing, "tags": len(tags)})
        if missing:
            fails.append("C1")

    # C2: no SITE, o primeiro pedaco da linha e' a tag. Duas formas contam:
    # `err(<funcao_pura>(...))` (a funcao devolve a linha com a tag) e
    # `err("<TAG> ...")` (literal). Uma `%`-formatacao com o prefixo ANTES da
    # tag -- `err("device=%r %s" % (dev, line))` -- e' exatamente o defeito que
    # manteve estas linhas invisiveis, e por isso C2 le o primeiro argumento.
    tree = ast.parse(src)
    tag_first = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "err" and node.args):
            continue
        segment = (_seg(src, node.args[0]) or "").strip()
        for tag in VISIBLE:
            # literal que comeca pela tag
            if segment.startswith('"%s' % tag) or segment.startswith("'%s" % tag):
                tag_first.setdefault(tag, "literal")
            # `err(<funcao_pura>(...))` -- a funcao devolve a linha COM a tag no
            # comeco, e o encadeamento de strings vive dentro dela (ver
            # `ladder_try_line`). O que NAO conta e' prefixar a saida no sitio.
            if isinstance(node.args[0], ast.Call) \
                    and isinstance(node.args[0].func, ast.Name) \
                    and _returns_tag(tree, node.args[0].func.id, tag):
                tag_first.setdefault(tag, node.args[0].func.id)
            # `"%s device=%r" % (_back_line, ...)` -- a tag entra como PRIMEIRO
            # campo da formatacao, e o valor que a carrega e' a linha pura.
            if isinstance(node.args[0], ast.BinOp) and isinstance(node.args[0].op, ast.Mod):
                left = _seg(src, node.args[0].left) or ""
                if left.strip().startswith('"%s ') or left.strip().startswith("'%s "):
                    values = node.args[0].right
                    names = [n.id for n in ast.walk(values) if isinstance(n, ast.Name)]
                    for name in names:
                        fn = _producer_of(tree, name)
                        if fn and _returns_tag(tree, fn, tag):
                            tag_first.setdefault(tag, name)
    got = sorted(tag_first)
    want = [t for t in VISIBLE if t != "WORKER_BOOT_PROF"] + ["WORKER_BOOT_PROF"]
    missing2 = [t for t in want if t not in tag_first]
    # `WORKER_BOOT_PROF` sai por `"WORKER_BOOT_PROF " + " ".join(...)`, nao por
    # `%`: a forma e' outra e o literal comeca pela tag, por isso ja' esta' em
    # `tag_first`. O que falta aqui e' qualquer outra.
    check("C2", not missing2, {"tag_first": got, "missing": missing2})
    if missing2:
        fails.append("C2")
    return fails


def _producer_of(tree, name):
    """A funcao que ATRIBUI `name` (uma so', a do ficheiro)."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            tgt = node.targets[0]
            if isinstance(tgt, ast.Tuple) and any(
                    isinstance(e, ast.Name) and e.id == name for e in tgt.elts):
                val = node.value
                if isinstance(val, ast.Call) and isinstance(val.func, ast.Name):
                    return val.func.id
    return None


def _returns_tag(tree, fname, tag):
    """A funcao `fname` devolve um texto que COMECA pela tag?"""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == fname:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Return) and sub.value is not None:
                    segment = _seg(_SRC_CACHE.get("src", ""), sub.value) or ""
                    if ('"%s ' % tag) in segment or ("'%s " % tag) in segment \
                            or segment.strip().startswith(('"%s"' % tag, "'%s'" % tag)):
                        return True
    return False


#: `_returns_tag` precisa do texto; `run_arms` nao o tem, por isso o modulo
#: guarda o ultimo fonte lido. Prefixado por `_` para nao parecer estado.
_SRC_CACHE: dict = {}


def main(argv):
    global SHELL
    say = lambda n, ok, d: print("  %-4s %s%s" % (n, "ok" if ok else "FAIL",
                                                 ("  " + str(d)) if d else ""))
    src = open(WORKER, "r", encoding="utf-8").read()
    tree, consts = parse(src)
    from worker.sotto_worker import audio_back_step
    real_mod = sys.modules["worker.sotto_worker"]

    if "--neg-arm" in argv:
        tmp = tempfile.mkdtemp(prefix="audio-back-neg-")
        path = os.path.join(tmp, "mutant.py")
        mutants = {
            "M1_graca_invertida": src.replace(
                "if now - back_watch['t'] < grace_s:",
                "if now - back_watch['t'] > 10 ** 9:"),
            "M2_nunca_compara_legenda": src.replace(
                "    if captions != back_watch['captions']:\n        return None, None\n", ""),
            "M3_limiar_proprio": src.replace(
                "if gap_s >= TAP_STALL_S:", "if gap_s >= 2.5:"),
            "M4_site_apagado": src.replace(
                "back_watch, _back_line = audio_back_step(", "back_watch, _back_line = (None, None); _unused("),
            # M5/M6: a linha volta a morrer no `stderr_tail` -- M5 tira a tag da
            # allowlist da SHELL, M6 repoe o prefixo que a empurrava para o meio.
            # Sao mutacoes de FICHEIROS DIFERENTES: a copia carrega o par
            # (worker, shell) e cada arm le o seu.
            "M5_tag_fora_da_allowlist": None,
            "M6_prefixo_antes_da_tag": src.replace(
                'err("%s device=%r" % (_back_line, dev.get("name")))',
                'err("device=%r %s" % (dev.get("name"), _back_line))'),
        }
        caught = 0
        shell_src = open(SHELL, "r", encoding="utf-8").read() if os.path.exists(SHELL) else ""
        shell_tmp = os.path.join(tmp, "shell_mutant.py")
        for name, mutated in mutants.items():
            if name == "M5_tag_fora_da_allowlist":
                # a SHELL mutante e' que tem de ser lida: troca-se o ficheiro
                # apontado por SHELL, nao o worker.
                mutated = shell_src.replace("'CAPTURE_SIGNAL_BACK',", "")
                if mutated == shell_src:
                    print("  %-26s NOT-APPLIED (a ancora nao existe)" % name)
                    continue
                open(shell_tmp, "w", encoding="utf-8", newline="").write(mutated)
                real, SHELL = SHELL, shell_tmp
                try:
                    mfails = run_arms(audio_back_step, src, tree, consts,
                                      lambda *a, **k: None)
                finally:
                    SHELL = real
                os.remove(shell_tmp)
                if mfails:
                    caught += 1
                    print("  %-26s CAUGHT (%s)" % (name, ",".join(mfails)))
                else:
                    print("  %-26s NOT-CAUGHT" % name)
                continue
            if mutated == src:
                print("  %-24s NOT-APPLIED (a ancora nao existe)" % name)
                continue
            open(path, "w", encoding="utf-8").write(mutated)
            mtree, mconsts = parse(mutated)
            try:
                mod = load_func_namespace(mutated, path, real_mod)
                mfails = run_arms(mod.audio_back_step, mutated, mtree, mconsts,
                                  lambda *a, **k: None)
            except Exception:                                 # noqa: BLE001
                mfails = ["crash"]
            if mfails:
                caught += 1
                print("  %-24s CAUGHT (%s)" % (name, ",".join(mfails)))
            else:
                print("  %-24s NOT-CAUGHT" % name)
        shutil.rmtree(tmp, ignore_errors=True)
        total = len(mutants)
        print("NEG-ARM: %s -- %d/%d mutantes apanhados"
              % ("PASS" if caught == total else "FAIL", caught, total))
        # CONVENCAO DA CASA: o negativo devolve **1 quando APANHA**. Aqui estava
        # ao contrario (`0` ao apanhar), logo o `:expectred ... 1` do passo via
        # rc=0 e chamava-lhe "o controlo nao foi para vermelho" -- o controlo
        # apanhava os SEIS mutantes e o passo publicava-o como falha. Medido
        # 2026-11-11: 6/6 CAUGHT e rc=0; depois da cura, 6/6 CAUGHT e rc=1.
        return 1 if caught == total else 0

    print("AUDIO-BACK-DETECTOR")
    fails = run_arms(audio_back_step, src, tree, consts, say)
    print("")
    if fails:
        print("VERDICT: FAIL -- %s" % "; ".join(fails))
        return 1
    print("VERDICT: PASS -- 11 arm(s), 0 failure(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
