#!/usr/bin/env python
# NO-BUG: instrumento da ordem do dono de 2026-10-30 -- *"o youtube mostra uma
# palavra por vez e o sotto mostra varias por vez"*. Nao corrige nenhum defeito;
# mede a UNICA coisa que faltava ao oraculo 1:1: quantas palavras estao no ecra
# do Sotto por instante, comparadas com as que o relogio do proprio YouTube ja'
# revelou.
"""ORACLE: A LEGENDA REVELA UMA PALAVRA DE CADA VEZ (e nunca mais que o YouTube).

O QUE ESTAVA ERRADO, e porque e' que nenhum oraculo o via. A revelacao era
contada em PALAVRAS sobre o texto que o UIA entrega. Medido nos 16 quadros de
`_main/fixtures/yt-WdaHAGRBB6s.live-compare-20261026.json`: esse texto cresce por
FRASES -- em t=0,772 s ja' traz `"Have you ever had"` (quatro palavras) quando o
player acabou de revelar a segunda. Os tres oraculos de 1:1 comparavam a NOSSA
janela com a MESMA pintura que a alimentava, por isso eram tautologicos: mediam
o instrumento com ele proprio. Este compara com o RELOGIO DE PALAVRA do payload
(`words[].start`), que e' o unico numero independente da nossa leitura.

O QUE E' MEDIDO:
  1. a linha cresce UMA palavra por tick (o tick do desenho e' `RENDER_S`);
  2. a revelacao antiga (so' pintura) salta -- e o negativo que prova os dentes;
  3. o ecra NUNCA mostra mais palavras do que o relogio revelou;
  4. um cue SEM relogio de palavra cai na pintura e nao inventa revelacao;
  5. `yt_live_frame` avanca o relogio a partir do ancora e EXPIRA.

Uso:
    python _main/youtube-word-clock-oracle.py            -> rc 0 GREEN / rc 1 RED
    python _main/youtube-word-clock-oracle.py --neg-arm  -> muta uma COPIA e exige RED
"""
from __future__ import annotations

import ast
import importlib.util as _ilu
import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(os.environ.get("SOTTO_ROOT") or r"H:\sotto").resolve()
WEBVIEW = ROOT / "app" / "webview"
SHELL = WEBVIEW / "sotto_webview.py"
PAYLOAD = ROOT / "_main" / "fixtures" / "yt-WdaHAGRBB6s.en-orig.json3"
EXIT_PASS, EXIT_FAIL = 0, 1

#: O tick do desenho. Tem de ser MENOR que o espaco entre duas palavras do
#: payload (medido: 0, 240, 400 ms) -- um tick mais grosso que a palavra volta a
#: saltar duas de uma vez, e o defeito era exactamente esse.
TICK_S = 0.06

rows: list[tuple[bool, str, str]] = []


def add(ok, name, detail=""):
    rows.append((bool(ok), name, detail))


def load(name, path):
    sys.path.insert(0, str(WEBVIEW))
    spec = _ilu.spec_from_file_location(name, str(path))
    module = _ilu.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verdict(name):
    passed = sum(1 for ok, _, _ in rows if ok)
    total = len(rows)
    failed = total - passed
    for ok, label, detail in rows:
        if not ok:
            print(f"FALHA: {label}" + (f"  -- {detail}" if detail else ""))
    print(f"\n{name} {'GREEN' if not failed else 'VERMELHO'} -- "
          f"arms={total} pass={passed} fail={failed} "
          f"(rc={EXIT_PASS if not failed else EXIT_FAIL})")
    return EXIT_PASS if not failed else EXIT_FAIL


def class_methods(source, cls, names):
    """Os corpos `names` da classe `cls` -- ou de QUEM OS TIVER, se `cls` for None.

    `_youtube`, `_yt_lines` e `yt_live_frame` vivem em `ExternalCaptionWatcher`
    (nao no `SottoShell`), por isso a busca por `None` existe: procurar numa
    classe fixa deixava o braco a dizer "nao extraido" e o oraculo a medir nada.
    """
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if cls is not None and node.name != cls:
            continue
        found = {n.name: ast.get_source_segment(source, n)
                 for n in node.body
                 if isinstance(n, ast.FunctionDef) and n.name in names}
        if found:
            return found
    return {}


def words_on_screen(lines):
    """Quantas palavras o ecra mostra AGORA (a ultima linha e' a que cresce).

    A PALAVRA E' A DE PRODUCAO (2026-11-03): `youtube_reveal.speech_words`, que
    nao conta o marcador `>>`. Contar por `.split()` aqui punha este instrumento a
    usar uma definicao e o codigo outra -- a arm 4 acusava o ecra de estar a'
    frente do relogio quando o que estava a' frente era o MARCADOR, que nao gasta
    orcamento de revelacao em nenhum dos dois lados.
    """
    lines = [str(l) for l in (lines or []) if str(l).strip()]
    if not lines:
        return 0
    try:
        import youtube_reveal as _yr
        counter = _yr.speech_words
    except Exception:                                            # noqa: BLE001
        counter = str.split
    return len(counter(lines[-1]))


def walk(yc, yr, cues, cue_index, steps_ms=60.0, horizon_s=1.6, old_rule=False):
    """Avanca o relogio a partir do inicio do cue e devolve as contagens por tick."""
    cue = cues[cue_index]
    start = float(cue.get("start") or 0.0)
    out = []
    hit = {"index": cue_index, "from_index": cue_index,
           "painted_from": 0, "aligned": 0, "cue": cue}
    t = start
    while t <= start + horizon_s:
        # A PINTURA: e' o texto que o UIA entrega -- cresce por FRASES.
        painted = str(cue.get("text") or "")
        applied = yc.align_painted(cues, painted.split())
        if applied:
            hit = applied
        if old_rule:
            # A REGRA ANTIGA, aqui como NEGATIVO: prefixo contado em palavras
            # sobre a pintura inteira.
            wanted = yr.painted_prefix_count(hit)
            lines = [yr.first_words(str((hit.get("cue") or {}).get("text") or ""),
                                    wanted)] if wanted else []
        else:
            lines = yr.window_by_paint(cues, hit, played_t=t)
        out.append((round(t, 3), words_on_screen(lines), lines))
        t += steps_ms / 1000.0
    return out


def run(payload_path: Path) -> int:
    if not payload_path.exists():
        print(f"VERDICT: FAIL -- {payload_path} ausente")
        return EXIT_FAIL
    yc = load("yc_oracle", WEBVIEW / "youtube_captions.py")
    yr = load("yr_oracle", WEBVIEW / "youtube_reveal.py")
    cues = yc.parse_json3(payload_path.read_text(encoding="utf-8"))
    with_clock = [i for i, c in enumerate(cues) if c.get("words")]

    print("ARM 1 -- o payload tem relogio de palavra (sem ele nada disto se mede)")
    add(bool(cues), "cues lidos do payload", f"{len(cues)}")
    add(len(with_clock) >= 10,
        "os cues trazem `words[].start`", f"{len(with_clock)} de {len(cues)}")
    if not with_clock:
        return verdict("WORD-CLOCK")

    # -- 1: um tick = no maximo UMA palavra ---------------------------------
    print("\nARM 2 -- a linha cresce UMA palavra por tick")
    # O CRITERIO E' UMA COMPARACAO, NAO UM NUMERO FIXO: duas palavras podem cair
    # dentro do mesmo tick de 60 ms (ha' palavras a 40 ms uma da outra no
    # payload) e o proprio YouTube as mostra juntas. O que NAO pode acontecer e'
    # o ecra andar mais depressa do que o relogio dele -- e' isso que "varias de
    # uma vez" quer dizer quando o player mostra uma.
    jumps = []
    ahead = []
    for index in with_clock[:6]:
        cue = cues[index]
        series = walk(yc, yr, cues, index)
        for (t0, n0, _), (t1, n1, _) in zip(series, series[1:]):
            c0 = yr.word_clock_count(cue, t0) or 0
            c1 = yr.word_clock_count(cue, t1) or 0
            jumps.append((n1 - n0, t0, index))
            if (n1 - n0) > max(1, c1 - c0):
                ahead.append((n1 - n0, c1 - c0, t0, index))
    worst = max(jumps, key=lambda row: row[0]) if jumps else (0, 0.0, -1)
    add(not ahead,
        "nenhum tick anda mais depressa do que o relogio do YouTube",
        f"salto maximo={worst[0]} em t={worst[1]} (cue {worst[2]}) | fora={ahead[:3]}")
    add(any(step == 1 for step, _, _ in jumps),
        "e a linha CRESCE uma palavra de cada vez (nao congelada)",
        f"{sum(1 for step, _, _ in jumps if step == 1)} passos de uma palavra")

    # -- 2: o negativo -- a regra antiga salta ------------------------------
    print("\nARM 3 -- o NEGATIVO: a revelacao so' por PINTURA salta uma frase")
    old = walk(yc, yr, cues, with_clock[0], old_rule=True)
    new = walk(yc, yr, cues, with_clock[0])
    old_first = max((n for _, n, _ in old), default=0)
    new_first = max((n for _, n, _ in new[:2]), default=0)
    add(old_first >= 3 and old_first > new_first,
        "a regra antiga mostra a FRASE inteira desde o primeiro instante",
        f"antiga={old_first} palavras vs nova={new_first}")

    # -- 3: nunca mais que o relogio ---------------------------------------
    print("\nARM 4 -- o ecra nunca mostra mais do que o YouTube revelou")
    over = []
    for index in with_clock[:6]:
        cue = cues[index]
        for t, count, lines in walk(yc, yr, cues, index):
            clock = yr.word_clock_count(cue, t)
            if clock is None:
                continue
            here = words_on_screen(lines)
            if here > clock:
                over.append((here, clock, t, index))
    add(not over, "nenhuma amostra a frente do relogio de palavra", str(over[:3]))

    # -- 4: cue sem relogio cai na pintura, sem inventar --------------------
    print("\nARM 5 -- um cue SEM relogio de palavra nao inventa revelacao")
    bare = {"text": "one two three four", "start": 0.0, "end": 4.0}
    hit = {"index": 0, "from_index": 0, "painted_from": 0, "aligned": 2,
           "cue": bare}
    lines = yr.window_by_paint([bare], hit, played_t=1.0)
    add(words_on_screen(lines) == 2,
        "sem `words`, a contagem volta a ser a da PINTURA",
        f"{lines}")
    add("three" not in " ".join(lines),
        "e as palavras que o player ainda nao pintou NAO aparecem", f"{lines}")

    # -- 5: o ancora do relogio vivo ---------------------------------------
    print("\nARM 6 -- `yt_live_frame`: o relogio avanca entre leituras, e expira")
    source = SHELL.read_text(encoding="utf-8")
    bodies = class_methods(source, None, ("yt_live_frame",))
    add("yt_live_frame" in bodies, "yt_live_frame extraido do ficheiro que corre")
    if "yt_live_frame" in bodies:
        ns = {"time": _Clock(), "log": lambda *a, **k: None}
        module = ast.Module(body=[ast.parse(bodies["yt_live_frame"]).body[0]],
                            type_ignores=[])
        exec(compile(module, "<yt-live-frame>", "exec"), ns)
        fn = ns["yt_live_frame"]
        cue = cues[with_clock[0]]

        class FrameShell:
            YT_ANCHOR_MAX_S = 3.0
            _yt_anchor = (float(cue.get("start") or 0.0), 100.0)
            _yt_track = {"cues": [cue]}

            def _yt_lines(self, track, t):
                import youtube_window
                return youtube_window.revealed_lines(track.get("cues") or (), t, 2)

        shell = FrameShell()
        ns["time"].now = 100.0
        first = fn(shell)
        # A FONTE MUDOU DE NOME (2026-11-03): o produtor do frame vivo devolve
        # `external:youtube:liveframe` (o `:track` e' a leitura do UIA). O que a
        # arm exige e' um frame do YouTube COM linhas -- o nome do canal e' forma.
        add(first is not None and str(first[0]).startswith("external:youtube:")
            and bool(first[1]),
            "com ancora fresco devolve um frame", str(first)[:60])
        # O ANTERIOR: avancar 1,2 s tem de revelar MAIS palavras e nunca menos.
        before = words_on_screen(first[1]) if first else 0
        ns["time"].now = 101.2
        later = fn(shell)
        after = words_on_screen(later[1]) if later else 0
        add(after >= before, "o relogio local so' ANDA para a frente",
            f"{before} -> {after}")
        ns["time"].now = 100.0 + FrameShell.YT_ANCHOR_MAX_S + 0.01
        add(fn(shell) is None,
            "um ancora velho devolve None (o ecra congela, nao inventa)")
    # -- 7: a ANIMACAO da linha nova (ordem do dono, verbatim: *"por que a
    # nossa legenda nao tem a mesma animacao da do youtube? arruma"*) --------
    print("\nARM 7 -- a linha nova entra com FADE, e o fade acaba em FULL")
    wf = load("wf_oracle", WEBVIEW / "word_fade.py")
    curve = [wf.alpha_at(t) for t in (0.0, 0.016, 0.03, 0.06, 0.09, 0.12)]
    add(curve[0] == 0 and curve[-1] == wf.FULL,
        "o fade vai de 0 a FULL na duracao declarada", str(curve))
    add(all(a <= b for a, b in zip(curve, curve[1:])),
        "e so' sobe (nenhum piscar a meio do fade)", str(curve))
    add(wf.alpha_at(None) == wf.FULL,
        "sem instante o alfa e' FULL -- uma linha nunca fica invisivel",
        str(wf.alpha_at(None)))
    overlay_src = (WEBVIEW / "caption_overlay.py").read_text(encoding="utf-8")
    add("BLENDFUNCTION(AC_SRC_OVER, 0, fade, AC_SRC_ALPHA)" in overlay_src,
        "o `UpdateLayeredWindow` recebe o ALFA DO FADE (e nao 255 fixo)")
    fade_bodies = class_methods(overlay_src, None, ("_fade_alpha",))
    add("_fade_alpha" in fade_bodies, "_fade_alpha extraido do overlay")
    if "_fade_alpha" in fade_bodies:
        fns = {"time": _Clock()}
        module = ast.Module(body=[ast.parse(fade_bodies["_fade_alpha"]).body[0]],
                            type_ignores=[])
        exec(compile(module, "<fade-alpha>", "exec"), fns)
        fns["time"].now = 100.0

        class FadeShell:
            # O `_fade_alpha` do OVERLAY le' o botao do fade (2026-11-03,
            # `caption_overlay.FADE_ON`): um duplo sem ele derrubava o oraculo
            # com AttributeError em vez de medir a matematica do alfa.
            FADE_ON = True
            _fade_t0 = None

        shell = FadeShell()
        add(fns["_fade_alpha"](shell) == 255, "sem fade a correr, alfa FULL")
        shell._fade_t0 = 99.94
        mid = fns["_fade_alpha"](shell)
        add(0 < mid < 255, "a meio do fade o alfa esta' entre 0 e FULL", f"{mid}")
        shell._fade_t0 = 90.0
        add(fns["_fade_alpha"](shell) == 255 and shell._fade_t0 is None,
            "passada a duracao, o fade fecha-se e nao volta a repintar sozinho")
    return verdict("WORD-CLOCK")


class _Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now


def neg_arm() -> int:
    """Muta uma COPIA: o corte pela palavra volta a ser so' a pintura."""
    global WEBVIEW
    tmp = Path(tempfile.mkdtemp(prefix="wc-neg-"))
    try:
        copy = tmp / "app" / "webview"
        copy.mkdir(parents=True)
        for name in ("youtube_captions.py", "youtube_reveal.py",
                     "youtube_window.py", "sotto_webview.py",
                     "caption_overlay.py", "overlay_paint.py", "word_fade.py"):
            shutil.copy2(WEBVIEW / name, copy / name)
        target = copy / "youtube_reveal.py"
        text = target.read_text(encoding="utf-8")
        # 2026-11-01: o alvo mudou de forma (o `min` estava a ser aplicado dentro de um
        # ternario de UMA linha, `cap = (min(wanted, clock) if wanted > 0 else clock)`),
        # e a ancora antiga deixou de casar -- o braco dizia "o texto mudou" em vez de
        # provar o que quer que fosse. A mutacao continua a mesma ideia: tirar o relogio
        # do cap, que e' exactamente a lei que o oraculo julga.
        mutant = text.replace(
            "                    cap = (min(wanted, clock) if wanted > 0 else clock)",
            "                    cap = (wanted if wanted > 0 else clock)")
        if mutant == text:
            print("NEG-ARM: nao consegui mutar o alvo (o texto mudou)")
            return EXIT_FAIL
        target.write_text(mutant, encoding="utf-8")
        print("NEG-ARM: o corte volta a ser so' a PINTURA (a frase inteira de uma vez)")
        # E o fade volta a ser 255 fixo -- a segunda regressao que o dono pediu.
        ov = copy / "caption_overlay.py"
        otext = ov.read_text(encoding="utf-8")
        omut = otext.replace("BLENDFUNCTION(AC_SRC_OVER, 0, fade, AC_SRC_ALPHA)",
                             "BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)")
        if omut != otext:
            ov.write_text(omut, encoding="utf-8")
            print("NEG-ARM: o blend volta a 255 fixo (sem animacao)")
        saved = WEBVIEW
        WEBVIEW = copy
        try:
            rc = run(PAYLOAD)
        finally:
            WEBVIEW = saved
        if rc == EXIT_FAIL:
            print("\nNEG-ARM PASS -- RED as designed: o mutante derruba o oraculo")
            return EXIT_FAIL
        print("\nNEG-ARM FAIL -- o oraculo NAO ve a regressao")
        return EXIT_PASS
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv) -> int:
    global SHELL
    if "--neg-arm" in argv:
        return neg_arm()
    return run(PAYLOAD)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
