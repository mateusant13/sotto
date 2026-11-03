"""youtube-verbatim-oracle — a legenda do Sotto tem de ser a LINHA do player, inteira.

AS TRES IMAGENS DO DONO (2026-11-02), cada uma um defeito diferente do mesmo caminho:

  1. `para cima, consegue tirar a Yamato ja' d`  -- a ultima palavra CORTADA a meio
     (`window_by_paint` cortava em `cap = min(pintado, relogio_de_palavra)`, um
     numero de PALAVRAS, e o overlay quebrava o resto);
  2. `jogo, do jogo, vao aos poucos.` POR BAIXO de `rotacionando, a gente` -- a
     janela rolante a empilhar o cue anterior, e a linha a CONSTRUIR-se ao longo do
     tempo em vez de aparecer quando o YouTube a mostra;
  3. o player a desenhar duas linhas e o Sotto CALADO.

O caminho pintado agora e' uma copia: `youtube_window.painted_lines` devolve as
linhas que o player esta' a desenhar, uma por linha, sem o marcador de fala `>>`,
sem cortar, sem juntar. Este ficheiro julga isso e a FIACAO que o usa.

ARMAS (todas leem codigo e funcoes REAIS; nenhuma abre janela):
  1. duas linhas do player continuam DUAS linhas, na ordem, sem `>>`;
  2. nada e' truncado: o numero de palavras da saida e' o da entrada;
  3. repeticoes consecutivas iguais colapsam (o "coisa duplicada" dele);
  4. texto vazio da' `[]` -- nunca texto inventado;
  5. FIACAO: `_youtube` usa `_yt_rows(painted)` nos DOIS ramos pintados e ja'
     nao monta a janela por `window_by_paint` dentro do ramo que casou o track.

`--neg-arm` muta uma COPIA de `youtube_window.py` (corta a ultima palavra) e exige
que a arma 2 va a RED pelo MESMO `judge()` que publica o veredicto: um portao que
nao ve o defeito removido nao pode recusar o defeito a chegar.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
WEBVIEW = os.path.join(REPO, "app", "webview")
WINDOW_PY = os.path.join(WEBVIEW, "youtube_window.py")
SHELL_PY = os.path.join(WEBVIEW, "sotto_webview.py")
FIXTURE = os.path.join(HERE, "fixtures", "yt-WdaHAGRBB6s.break-position-20261026.json")


def load_module(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def judge(mod) -> list[dict]:
    """Every arm, against ONE module (the real one or a mutant of it)."""
    rows = []

    def arm(name, ok, evidence):
        rows.append({"arm": name, "ok": bool(ok), "evidence": str(evidence)[:240]})

    # 1. as duas linhas que o dono fotografou, com o marcador de fala do player.
    two = mod.painted_lines([">> Nossa.", ">> tá segurando essa wave,"])
    arm("two-painted-lines-stay-two-lines",
        two == ["Nossa.", "tá segurando essa wave,"], two)

    # 2. NENHUMA PALAVRA A MENOS. The exact line of the first screenshot, whole.
    src = "para cima, consegue tirar a Yamato já do"
    out = mod.painted_lines([src])
    arm("no-word-is-truncated",
        out == [src] and len(out[0].split()) == len(src.split()), out)

    # 3. duplicadas consecutivas colapsam; diferentes ficam.
    dup = mod.painted_lines(["a hora da resenha", "a hora da resenha", "tentar brigar"])
    arm("consecutive-duplicates-collapse",
        dup == ["a hora da resenha", "tentar brigar"], dup)

    # 3-bis. AS DUAS FORMAS DA JANELA DE LEGENDA (medido 2026-11-02 22:19:36): a
    # faixa manual entrega LINHAS, a automatica entrega PALAVRAS. O numero de linhas
    # e' do player nos dois casos -- nunca um por palavra.
    manual = mod.painted_rows([">> Nossa.", ">> tá segurando essa wave,"])
    auto = mod.painted_rows([">> Nossa.", ">> tá", "segurando", "essa", "wave,"])
    arm("manual-captions-keep-the-players-lines",
        manual == ["Nossa.", "tá segurando essa wave,"], manual)
    arm("auto-captions-split-at-the-players-own-marker",
        auto == ["Nossa.", "tá segurando essa wave,"], auto)
    # 3-ter. COM RECTS a quebra e' a do ecra: duas filas de palavras, duas linhas.
    items = [
        {"text": ">>", "top": 100, "bottom": 130, "left": 10},
        {"text": "Nossa.", "top": 100, "bottom": 130, "left": 50},
        {"text": ">>", "top": 140, "bottom": 170, "left": 10},
        {"text": "tá", "top": 140, "bottom": 170, "left": 50},
        {"text": "segurando", "top": 140, "bottom": 170, "left": 90},
    ]
    rect = mod.painted_rows(["ignorado"], items)
    arm("rows-follow-the-players-rectangles",
        rect == ["Nossa.", "tá segurando"], rect)

    # 3-quater. AS 16 AMOSTRAS GRAVADAS DO PROPRIO PLAYER (2026-10-26,
    # `_main/fixtures/yt-WdaHAGRBB6s.break-position-20261026.json`): cada amostra
    # tem as linhas que o YOUTUBE desenhou (`youtube`) e o que o overlay pintava
    # na altura (`overlay`). 12 das 16 tinham a quebra errada. O texto das linhas
    # do player, achatado em palavras na ordem de leitura -- exactamente a forma
    # que o leitor de UIA entrega -- tem de voltar a dar AS MESMAS LINHAS.
    try:
        with open(FIXTURE, encoding="utf-8") as fh:
            samples = json.load(fh).get("samples") or []
    except Exception as exc:  # noqa: BLE001
        samples = []
        arm("fixture-readable", False, exc)
    if samples:
        # A. O TEXTO: nenhuma palavra perdida nem repetida, em 16/16 amostras reais.
        text_bad = 0
        first_text_bad = ""
        # B. AS QUEBRAS que o marcador consegue reconstruir (o `>>` abre linha). As
        #    outras quebras do player sao de WRAP (a mesma fala a passar de linha sem
        #    marcador nenhum), e para essas o unico instrumento e' o RECT -- que nao
        #    esta' gravado neste fixture, e por isso e' medido ao vivo por
        #    `EXTERNAL_CAPTION_DRAWN rows=` (ver `rows-follow-the-players-rectangles`).
        breaks_ok = breaks_marker = 0
        first_break_bad = ""
        for smp in samples:
            sample_rows = [r for r in (smp.get("youtube") or ()) if str(r).strip()]
            flat = " ".join(sample_rows).split()
            got = mod.painted_rows(flat) if flat else []
            want_joined = " ".join(mod._strip_markers(r) for r in sample_rows).split()
            got_joined = " ".join(got).split()
            if want_joined != got_joined:
                text_bad += 1
                if not first_text_bad:
                    first_text_bad = "t=%s want=%r got=%r" % (smp.get("t"), want_joined, got_joined)
            want_lines = [mod._strip_markers(r) for r in sample_rows]
            want_lines = [w for w in want_lines if w]
            # A amostra so' entra nesta arm quando CADA quebra de linha tem um
            # marcador: a primeira linha e' sempre uma fronteira, as seguintes
            # tem de abrir com `>>`. Sem isso a quebra e' de WRAP -- outro
            # instrumento (o rect), medido ao vivo.
            marker_break = len(sample_rows) > 1 and all(
                any(str(r).strip().startswith(m)
                    for m in mod._SPEAKER_MARKERS)
                for r in sample_rows[1:])
            if marker_break:
                breaks_marker += 1
                if want_lines == got:
                    breaks_ok += 1
                elif not first_break_bad:
                    first_break_bad = "t=%s want=%r got=%r" % (smp.get("t"), want_lines, got)
        arm("player-recorded-text-is-nor-lost-nor-repeated", text_bad == 0,
            "samples=%d match=%d differ=%d %s"
            % (len(samples), len(samples) - text_bad, text_bad, first_text_bad))
        arm("player-recorded-marker-breaks-reproduced",
            breaks_marker > 0 and breaks_ok == breaks_marker,
            "marker_samples=%d match=%d %s" % (breaks_marker, breaks_ok, first_break_bad))

    # 4. nada pintado -> lista vazia (nunca texto inventado).
    arm("empty-paint-is-empty-list",
        mod.painted_lines([]) == [] and mod.painted_lines(["", "  "]) == []
        and mod.painted_lines(None) == [] and mod.painted_rows([]) == [],
        "empty stays empty")
    return rows


def wiring_arms(shell_src: str) -> list[dict]:
    """The shell must CALL the verbatim helper on both painted branches."""
    rows = []

    def arm(name, ok, evidence):
        rows.append({"arm": name, "ok": bool(ok), "evidence": str(evidence)[:240]})

    start = shell_src.find("    def _youtube(self, hwnd, uia, UIA):")
    end = shell_src.find("\n    def ", start + 10)
    body = shell_src[start:end if end > 0 else len(shell_src)]
    # Only the branch that MATCHED the track matters for the old window path; the
    # foreign-track clock branch keeps its own logic on purpose.
    arm("shell-calls-painted-lines", body.count("_yt_rows(painted,") >= 2,
        f"calls={body.count('_yt_rows(painted,')}")
    arm("shell-no-window-by-paint-in-matched-branch",
        "window_by_paint(" not in body,
        f"window_by_paint mentions={body.count('window_by_paint(')}")
    return rows


def main(argv: list[str]) -> int:
    neg = "--neg-arm" in argv
    if neg:
        tmp = tempfile.mkdtemp(prefix="yt-verbatim-neg-")
        try:
            with open(WINDOW_PY, encoding="utf-8") as fh:
                src = fh.read()
            # DOIS MUTANTES, UM POR DEFEITO QUE O DONO FOTOGRAFOU:
            #   M1 -- a palavra cortada (`Yamato ja' d`): o texto perde o ultimo token;
            #   M2 -- a quebra perdida: as linhas do player voltam a ser UMA so'.
            mutants = {
                "M1-truncate-last-word": (
                    "        if out and out[-1] == text:\n            continue\n        out.append(text)",
                    "        if out and out[-1] == text:\n            continue\n"
                    "        out.append(' '.join(text.split()[:-1]))",
                ),
                "M2-join-the-players-lines": (
                    "        if started or pending or not out:\n            out.append(text)",
                    "        if not out:\n            out.append(text)",
                ),
            }
            total = caught_total = 0
            ok = True
            for label, (old, new) in mutants.items():
                if old not in src:
                    print("FAIL mutant-applied — anchor not found for " + label)
                    return 2
                path = os.path.join(tmp, "youtube_window_%s.py" % label.split("-")[0])
                with open(path, "w", encoding="utf-8", newline="") as fh:
                    fh.write(src.replace(old, new, 1))
                mod = load_module(path, "yw_mutant_" + label.split("-")[0])
                rows = judge(mod)
                caught = [r for r in rows if not r["ok"]]
                print("== %s: %d/%d arms RED ==" % (label, len(caught), len(rows)))
                for r in caught:
                    print("RED  " + r["arm"] + " — " + r["evidence"])
                total += len(rows)
                caught_total += len(caught)
                ok = ok and len(caught) >= 1
            print(json.dumps({"cases": total, "caught": caught_total, "neg_arm": True}))
            print("NEG-ARM: PASS" if ok else "NEG-ARM: FAIL")
            return 1 if ok else 2
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    mod = load_module(WINDOW_PY, "yw_real")
    with open(SHELL_PY, encoding="utf-8") as fh:
        shell_src = fh.read()
    rows = judge(mod) + wiring_arms(shell_src)
    ok = sum(1 for r in rows if r["ok"])
    for r in rows:
        print(("PASS " if r["ok"] else "FAIL ") + r["arm"] + " — " + r["evidence"])
    print(json.dumps({"cases": len(rows), "caught": ok}))
    verdict = "PASS" if ok == len(rows) else "FAIL"
    print(f"YOUTUBE-VERBATIM VERDICT: {verdict}")
    print(f"\nVERDICT: {verdict}")
    return 0 if ok == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
