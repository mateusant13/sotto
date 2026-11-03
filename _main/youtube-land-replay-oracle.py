"""O JOGADOR MANDA ENQUANTO PUBLICA -- replay do caminho VIVO da legenda.

O DEFEITO MEDIDO (2026-11-03, no proprio fonte): `ExternalCaptionWatcher._tick`
escrevia o carimbo "o YouTube esta' a fornecer linhas" em SI MESMO
(`self._yt_owner_until`), mas quem o le' e' o `SottoShell`
(`push_caption_to_window`, e o campo e' lido em exactamente UM sitio). O shell
lia sempre `0.0`, a guarda nunca disparava e a frase do ASR substituia a linha do
player -- que e' o defeito das duas legendas diferentes no mesmo ecra.

Cada arm corre o CAMINHO REAL, sem janela e sem dispositivo de audio:

    ExternalCaptionWatcher._tick  ->  SottoShell.external_caption
                                  ->  push_caption_to_window (slot unico + thread)
                                  ->  overlay (duplo que REGISTA o que ia pintar)

Os dados sao as 16 amostras ja' gravadas do PROPRIO player
(`_main/fixtures/yt-WdaHAGRBB6s.break-position-20261026.json`), as mesmas que o
`youtube-reveal-oracle` usa.

  arm1 `rows-reach-the-overlay-verbatim`  -- as linhas do player chegam ao overlay
       como o player as desenhou (o `>>` sai, e' o marcador que o shell limpa).
  arm2 `player-owns-the-window`           -- depois de um tick do YouTube, o
       carimbo esta' no SHELL e um push do ASR e' RECUSADO.
  arm3 `asr-returns-after-the-window`     -- com o carimbo no passado, o ASR pinta.
  arm4 `one-paint-per-sample`             -- uma amostra, uma pintura (slot unico),
       e a ultima pintura e' a ultima amostra (nunca um texto velho).

`--neg-arm`: muta uma COPIA do shell com a linha antiga (`self._yt_owner_until`)
e exige o arm 2 a cair.
"""
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import time
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBVIEW = os.path.join(ROOT, "app", "webview")
SHELL = os.path.join(WEBVIEW, "sotto_webview.py")
LIVE = os.path.join(ROOT, "_main", "fixtures",
                    "yt-WdaHAGRBB6s.break-position-20261026.json")

sys.path.insert(0, WEBVIEW)


def load_shell(path=SHELL):
    spec = importlib.util.spec_from_file_location("sotto_shell_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["sotto_shell_under_test"] = mod
    spec.loader.exec_module(mod)
    mod.log = lambda _m: None                 # o oraculo nao escreve no log vivo
    return mod


class Overlay(object):
    """O duplo do overlay: registra o que IA' ser pintado, com o instante."""

    hwnd = 1
    visible = True

    def __init__(self):
        self.calls = []

    def set_work_area(self, *_a, **_k):
        return None

    def set_text(self, text, previous="", instant=False, **_k):
        self.calls.append((time.monotonic(), text, previous, bool(instant)))

    def show(self, on=True):
        self.visible = bool(on)
        return True


class ReloadPolicy(object):
    def boundary(self, **_k):
        return None


class FakeShell(object):
    """O `self` minimo para os metodos REAIS do `SottoShell` correrem.

    Um atributo nao declarado devolve 0: os metodos reais leem dezenas de
    contadores (`_overlay_pushes`, `_asr_dropped`, ...) e um duplo que os
    esquecesse morria com `AttributeError` em cada um deles -- quando um 0/False
    e' exactamente o valor inicial que a producao tem. O que precisa de ser
    objecto (o overlay, o display, o work_area) e' declarado a mao abaixo.
    """

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return 0


def fake_shell(mod):
    """Um `self` on minimo para os metodos REAIS do `SottoShell` correrem."""
    shell = FakeShell()
    shell.visible = True
    shell._caption_window_shown = True
    shell._caption_wanted = True
    shell._yt_owner_until = 0.0
    shell.display = {}
    shell.external_lines = 0
    shell.external_captions_active = False
    shell.caption_overlay = Overlay()
    shell._reload_policy = ReloadPolicy()
    # OS CAMPOS QUE A PRODUCAO TEM A `None`, E NAO A 0 (2026-11-03): o
    # `__getattr__` do duplo devolve 0 para um nome ausente, e o
    # `_caption_paint_wake` pergunta `getattr(self, '_caption_event', None)` --
    # com 0 o `ev.set()` rebentava e o caminho caia no `_drain` sincrono, medindo
    # um caminho que a producao NAO percorre. Estes `None` explicitos devolvem ao
    # duplo a forma do objecto real, e a thread da legenda passa a ser a real.
    shell._caption_event = None
    shell._caption_pending = None
    shell._caption_pending_instant = False
    shell._caption_pending_cue = None
    shell._caption_drain_posted = False
    shell._caption_painted = ""
    shell._external_last_text = ""
    shell._external_rows_logged = ""
    shell._overlay_pushes = 0
    shell._asr_dropped = 0
    shell._source_epoch = 0
    shell.yt_source_paused = False
    shell._last_caption_was_player = False
    shell._caption_idle_seq = 0
    shell.CAPTION_IDLE_HIDE_S = 6.0
    shell.work_area = lambda: {"x": 0, "y": 0, "w": 1200, "h": 200}
    shell.emit = lambda *_a, **_k: None
    shell._arm_caption_idle_hide = lambda *_a, **_k: None
    shell._park_worker_when_settled = lambda *_a, **_k: False
    # Os que o duplo DEFINE nao sao substituidos pelos reais: `__getattr__` do
    # `FakeShell` devolve 0 para um nome ausente, e `hasattr` sobre ele e' sempre
    # verdade -- a primeira versao deste laco devolvia o metodo REAL por cima do
    # stub e o `_arm_caption_idle_hide` (que arma um `threading.Timer`) corria com
    # um inteiro no lugar do callback.
    stubbed = {"_arm_caption_idle_hide", "_park_worker_when_settled"}
    for name in ("external_caption", "push_caption_to_window",
                 "_caption_paint_wake", "_caption_paint_loop",
                 "_drain_caption_pending"):
        if name in stubbed:
            continue
        fn = getattr(mod.SottoShell, name, None)
        if fn is not None:
            setattr(shell, name, types.MethodType(fn, shell))
    return shell


def samples():
    with io.open(LIVE, encoding="utf-8") as fh:
        live = json.load(fh)
    out = []
    for sample in live.get("samples") or ():
        rows = list(sample.get("youtube") or ())
        if rows:
            out.append((float(sample.get("t") or 0.0), rows))
    return out


def cleaned(rows):
    """O que o shell entrega ao overlay: cada linha limpa (`>>` sai)."""
    mod = sys.modules["sotto_shell_under_test"]
    return [mod.clean_external_text(r) for r in rows]


def split_rows(text):
    """As LINHAS do texto que chegou ao overlay.

    O texto do canal `rows` chega com um `\n` FINAL, e nao e' um erro: o
    terminador marca uma janela `rows` como ja' quebrada, para o `_layout` do
    overlay nao re-quebrar uma linha que o player quebrou noutro sitio. Comparar
    `split("\n")` cru punha uma linha vazia no fim de TODAS as amostras e o arm
    dizia 0/16 sobre um caminho que entregava as linhas certas.
    """
    body = str(text or "")
    if body.endswith("\n"):
        body = body[:-1]
    return body.split("\n") if body else []


def wait_paint(overlay, timeout=0.6):
    end = time.monotonic() + timeout
    before = len(overlay.calls)
    while time.monotonic() < end:
        if len(overlay.calls) > before:
            return True
        time.sleep(0.005)
    return False


def arm_verbatim(mod):
    """As linhas do player chegam ao overlay como o player as desenhou."""
    shell = fake_shell(mod)
    watcher = mod.ExternalCaptionWatcher(shell)
    same = 0
    total = 0
    diffs = []
    for _t, rows in samples():
        want = cleaned(rows)
        shell.caption_overlay.calls.clear()
        watcher._tick([("external:youtube:track", rows)], True)
        if not wait_paint(shell.caption_overlay):
            diffs.append((rows, "sem pintura"))
            total += 1
            continue
        _when, text, _prev, _instant = shell.caption_overlay.calls[-1]
        got = split_rows(text)
        total += 1
        if got == want:
            same += 1
        else:
            diffs.append((want, got))
    return (total > 0 and same == total), "%d/%d amostras iguais %s" % (
        same, total, diffs[:2] if diffs else "")


def arm_owner(mod):
    """Depois de um tick do YouTube, o ASR e' RECUSADO no shell."""
    shell = fake_shell(mod)
    watcher = mod.ExternalCaptionWatcher(shell)
    _t, rows = samples()[2]
    watcher._tick([("external:youtube:track", rows)], True)
    wait_paint(shell.caption_overlay)
    stamp = float(getattr(shell, "_yt_owner_until", 0.0) or 0.0)
    ahead = stamp > time.monotonic()
    shell.caption_overlay.calls.clear()
    shell.push_caption_to_window("frase do asr que nao pode ganhar")
    painted = wait_paint(shell.caption_overlay, 0.2)
    return (ahead and not painted), "carimbo_no_shell=%s em_futuro=%s asr_pintou=%s" % (
        stamp > 0, ahead, painted)


def arm_asr_after(mod):
    """Com o carimbo no passado, o ASR volta a pintar (a janela expira)."""
    shell = fake_shell(mod)
    shell._yt_owner_until = time.monotonic() - 1.0
    shell.caption_overlay.calls.clear()
    shell.push_caption_to_window("linha do asr depois da janela")
    painted = wait_paint(shell.caption_overlay, 0.6)
    text = shell.caption_overlay.calls[-1][1] if shell.caption_overlay.calls else ""
    return (painted and "asr" in str(text)), "pintou=%s text=%r" % (painted, text[:40])


def arm_one_paint(mod):
    """Uma amostra, uma pintura; a ultima pintura e' a ultima amostra."""
    shell = fake_shell(mod)
    watcher = mod.ExternalCaptionWatcher(shell)
    rows_all = samples()
    counts = []
    for _t, rows in rows_all:
        before = len(shell.caption_overlay.calls)
        watcher._tick([("external:youtube:track", rows)], True)
        wait_paint(shell.caption_overlay)
        time.sleep(0.12)                      # deixa a thread assentar
        counts.append(len(shell.caption_overlay.calls) - before)
    last_want = cleaned(rows_all[-1][1])
    got = split_rows(shell.caption_overlay.calls[-1][1])
    # DUAS ESCRITAS POR AMOSTRA SAO O DESENHO, NAO UM DEFEITO: o `_tick` manda a
    # linha (aberta) e, quando o texto muda, manda-a fechada (`final=True`) --
    # sao os dois canais que o `_main/youtube-rows-oracle.py` ja' mede. O que a
    # regra do slot unico proibe e' PINTAR UM TEXTO VELHO, e um terceiro push.
    return (max(counts) <= 2 and got == last_want), "pinturas=%s ultimo_igual=%s" % (
        counts, got == last_want)


def neg_arm():
    """A COPIA com o carimbo no watcher (o defeito): o arm 2 tem de cair."""
    tmp = tempfile.mkdtemp(prefix="yt-land-neg-")
    try:
        with io.open(SHELL, encoding="utf-8") as fh:
            src = fh.read()
        needle = "shell._yt_owner_until = time.monotonic() + 2.0"
        if needle not in src:
            return None, "o mutante nao encontrou o carimbo -- o detector nao serve"
        copy = os.path.join(tmp, "sotto_webview_mutant.py")
        with io.open(copy, "w", encoding="utf-8", newline="") as fh:
            fh.write(src.replace(needle,
                                 "self._yt_owner_until = time.monotonic() + 2.0", 1))
        mod = load_shell(copy)
        ok, detail = arm_owner(mod)
        return (not ok), detail
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    mod = load_shell()
    arms = (("rows-reach-the-overlay-verbatim", arm_verbatim),
            ("player-owns-the-window", arm_owner),
            ("asr-returns-after-the-window", arm_asr_after),
            ("one-paint-per-sample", arm_one_paint))
    results = []
    for name, fn in arms:
        ok, detail = fn(mod)
        results.append((name, ok, detail))
        print("%-34s %s %s" % (name, "GREEN" if ok else "RED", detail))

    if "--neg-arm" in argv:
        caught, detail = neg_arm()
        if caught is None:
            print("NEG-ARM FAIL %s" % detail)
            return 1
        print("NEG-ARM carimbo-no-watcher %s %s"
              % ("GREEN (o defeito volta)" if caught else "FAIL", detail))
        bad = [n for n, ok, _ in results if not ok]
        return 0 if (caught and not bad) else 1

    bad = [n for n, ok, _ in results if not ok]
    print("VERDICT: %s (%d/%d arms)"
          % ("PASS" if not bad else "FAIL", len(results) - len(bad), len(results)))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
