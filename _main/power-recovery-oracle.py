# NO-BUG: Oraculo da recuperacao de energia/sessao (`app/webview/power_recovery.py`).
"""Oraculo da recuperacao de energia/sessao (`app/webview/power_recovery.py`).

Julga a DECISAO e a ENTREGA, nao o Windows: nenhum oraculo deste repo pode
dormir o PC do dono. O que se prova aqui e' exactamente o que se escreveu --
`classify` -> `plan` -> handlers -- e o braco vivo (mensagem `WM_POWERBROADCAST`
entregue ao WndProc REAL de uma instancia viva) vive no passo da bateria, porque
precisa da app a correr.

`--neg-arm` muta uma COPIA do modulo e exige que os arms nomeados caiam; rc=1
quando apanha os mutantes (a convencao da casa: um negativo que devolve 0 passa
como oraculo normal e o mutante nunca e' recusado).
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import os
import shutil
import sys
import tempfile

# BATTERY-HEAVY: app-window -- o `--live-arm` LARGA A APP (escondida, por
# `SOTTO_LANE_LAUNCH=1` + `_main/keepalive.py`) para entregar `WM_POWERBROADCAST` ao
# WndProc de uma instancia viva; a classe pesada da bateria so' corre com
# `SOTTO_BATTERY_HEAVY=1`. Sem essa bandeira o passo publica SKIPPED, nunca verde.

HERE = os.path.dirname(os.path.abspath(__file__))
REAL = os.path.join(HERE, "..", "app", "webview", "power_recovery.py")


def load(path):
    spec = importlib.util.spec_from_file_location("power_recovery_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def judge(mod):
    """Devolve [(arm, ok, detail)] -- a lista e' a prova inteira."""
    m = mod
    out = []

    def arm(name, ok, detail=""):
        out.append((name, bool(ok), detail))

    arm("resume-automatic",
        m.classify(m.WM_POWERBROADCAST, m.PBT_APMRESUMEAUTOMATIC) == "resume")
    arm("resume-suspend",
        m.classify(m.WM_POWERBROADCAST, m.PBT_APMRESUMESUSPEND) == "resume")
    arm("resume-critical",
        m.classify(m.WM_POWERBROADCAST, m.PBT_APMRESUMECRITICAL) == "resume")
    arm("suspend-is-silent",
        m.classify(m.WM_POWERBROADCAST, m.PBT_APMSUSPEND) is None)
    arm("powersetting-is-silent",
        m.classify(m.WM_POWERBROADCAST, m.PBT_POWERSETTINGCHANGE) is None)
    arm("unlock",
        m.classify(m.WM_WTSSESSION_CHANGE, m.WTS_SESSION_UNLOCK) == "unlock")
    arm("lock-is-silent",
        m.classify(m.WM_WTSSESSION_CHANGE, m.WTS_SESSION_LOCK) is None)
    arm("console-connect",
        m.classify(m.WM_WTSSESSION_CHANGE, m.WTS_CONSOLE_CONNECT) == "connect")
    arm("remote-connect",
        m.classify(m.WM_WTSSESSION_CHANGE, m.WTS_REMOTE_CONNECT) == "connect")
    arm("foreign-message-is-silent",
        m.classify(0x0400, 0) is None and m.classify(None, 1) is None)

    arm("plan-resume-three",
        m.plan("resume") == (m.ACT_TOPMOST, m.ACT_WORKER, m.ACT_GEOMETRY),
        repr(m.plan("resume")))
    # O arm que protege o dono: um revive a cada unlock e' um reinicio de 14-26 s
    # a troco de nada, com o worker a atravessar o lock a correr.
    arm("plan-unlock-does-not-restart-the-worker",
        m.ACT_WORKER not in m.plan("unlock"), repr(m.plan("unlock")))
    arm("plan-unlock-fixes-topmost-and-geometry",
        set(m.plan("unlock")) == {m.ACT_TOPMOST, m.ACT_GEOMETRY}, repr(m.plan("unlock")))
    arm("plan-connect-fixes-geometry",
        m.ACT_GEOMETRY in m.plan("connect"), repr(m.plan("connect")))
    arm("plan-none-and-unknown-are-empty",
        m.plan(None) == () and m.plan("nonsense") == ()
        and m.plan("lock") == () and m.plan("suspend") == ())
    p = m.plan("resume")
    arm("plan-has-no-duplicates", len(p) == len(set(p)), repr(p))

    # -- a entrega (sem .NET: `attach` nao corre, `on_message` sim) ----------
    calls = []
    logs = []

    def handler_a(event, act):
        calls.append(("a", event, act))

    def handler_b(event, act):
        calls.append(("b", event, act))
        raise RuntimeError("accao que falha")

    def handler_c(event, act):
        calls.append(("c", event, act))

    rec = m.PowerRecovery({"topmost": handler_a, "worker": handler_b,
                           "geometry": handler_c}, log=logs.append)
    acts = rec.on_message(m.WM_POWERBROADCAST, m.PBT_APMRESUMEAUTOMATIC)
    order = [c[2] for c in calls]
    arm("handlers-fire-in-plan-order",
        order == [m.ACT_TOPMOST, m.ACT_WORKER, m.ACT_GEOMETRY], repr(order))
    arm("a-failing-action-does-not-stop-the-next",
        m.ACT_GEOMETRY in order, repr(order))
    arm("log-line-names-event-and-actions",
        bool(logs) and "POWER_RESUME event=resume" in logs[0]
        and "actions=topmost,worker,geometry" in logs[0], logs[0][:120] if logs else "-")
    calls.clear()
    logs.clear()
    rec.on_message(m.WM_WTSSESSION_CHANGE, m.WTS_SESSION_LOCK)
    arm("no-event-means-no-handler-call",
        calls == [] and not any("POWER_RESUME" in l for l in logs),
        repr(calls))
    arm("returned-actions-match-the-plan", tuple(acts) == m.plan("resume"), repr(acts))

    # -- o TRANSPORTE: uma janela real, uma mensagem real ---------------------
    # Hermetico: janela POPUP de tamanho zero, nunca mostrada, criada e destruida
    # nesta chamada. Nada aparece no ecra de ninguem.
    got = []
    live = m.PowerRecovery({"topmost": lambda e, a: got.append((e, a))},
                           log=lambda _m: None)
    attached = False
    try:
        attached = bool(live.attach()) or live.hwnd is not None
        import ctypes
        from ctypes import wintypes as wt
        u = ctypes.WinDLL("user32", use_last_error=True)
        u.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
        # `SendMessageW` entrega-o JÁ (sincrono) e nao precisa de bomba; o
        # `PostMessageW` fica na fila da THREAD e so' aparece quando alguem a
        # bombeia -- que na app e' a `Application.Run` do WinForms. Um teste sem
        # bomba mede o teste, nao a app (foi o primeiro FAIL deste arm: janela
        # criada, `PostMessageW` aceite, zero chamadas).
        sent = u.SendMessageW(live.hwnd, m.WM_POWERBROADCAST,
                              m.PBT_APMRESUMEAUTOMATIC, 0)
        posted = bool(u.PostMessageW(live.hwnd, m.WM_WTSSESSION_CHANGE,
                                     m.WTS_SESSION_UNLOCK, 0))
        import time as _t

        class _MSG(ctypes.Structure):
            _fields_ = [("hwnd", wt.HWND), ("message", wt.UINT),
                        ("wParam", wt.WPARAM), ("lParam", wt.LPARAM),
                        ("time", wt.DWORD), ("pt", ctypes.c_long * 2)]

        msg = _MSG()
        deadline = _t.time() + 2.0
        while _t.time() < deadline and len(got) < 2:
            if u.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):  # PM_REMOVE
                u.TranslateMessage(ctypes.byref(msg))
                u.DispatchMessageW(ctypes.byref(msg))
            else:
                _t.sleep(0.01)
    finally:
        try:
            live.detach()
        except Exception:
            pass
    arm("transport-window-exists", attached and bool(live.hwnd), str(live.hwnd))
    arm("transport-delivers-send-message", got[:1] == [("resume", "topmost")], repr(got))
    arm("transport-delivers-a-pumped-post", got[-1:] == [("unlock", "topmost")], repr(got))
    arm("transport-has-no-event-for-lock", (lambda: (live.on_message(
        m.WM_WTSSESSION_CHANGE, m.WTS_SESSION_LOCK), len(got) == 2)[1])(), repr(got))

    # -- a FIACAO: o modulo certo ligado ao hwnd certo ------------------------
    # Uma decisao provada e nunca chamada e' o defeito que este repo ja' pagou
    # caro (o `revivePipeline` que existia no painel e nao tinha metade na shell).
    shell = os.path.abspath(os.path.join(HERE, "..", "app", "webview",
                                        "sotto_webview.py"))
    src = io.open(shell, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
    arm("shell-starts-the-recovery", "self._start_power_recovery()" in src)
    arm("shell-maps-all-three-actions",
        all(n in src for n in ("_power_recovery.ACT_TOPMOST",
                               "_power_recovery.ACT_WORKER",
                               "_power_recovery.ACT_GEOMETRY")))
    arm("recovery-announces-itself-once",
        src.count("POWER_RECOVERY_READY") == 1, str(src.count("POWER_RECOVERY_READY")))
    return out


def live_arm(timeout_s=120):
    """A mensagem REAL entregue ao WndProc REAL de uma instancia viva.

    Nao e' input sintetico: `PostMessage` atravessa `WndProc`, que e' exactamente
    o caminho que o Windows usa para `WM_POWERBROADCAST`. O que NAO se prova aqui
    (e por isso nao se afirma) e' a decisao do Windows de emitir o evento quando a
    maquina acorda -- nenhum oraculo deste repo pode dormir o PC do dono.

    Largada pelo caminho da lane (escondida, `SOTTO_LANE_LAUNCH=1`), porque a
    entrega de mensagens para uma janela de integridade superior e' recusada por
    UIPI: medir a entrega exige os DOIS lados no mesmo nivel.
    """
    import subprocess
    import time

    root = os.path.abspath(os.path.join(HERE, ".."))
    log_path = os.path.join(root, "_main", "webview-run.log")
    try:
        off = os.path.getsize(log_path)
    except OSError:
        off = 0

    env = dict(os.environ)
    env["SOTTO_LANE_LAUNCH"] = "1"
    env.setdefault("TMPDIR", r"I:\cc-tmp")
    pw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    keep = subprocess.Popen([pw if os.path.exists(pw) else sys.executable,
                             os.path.join(root, "_main", "keepalive.py")],
                            cwd=root, env=env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=0x08000000, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))

    import ctypes
    from ctypes import wintypes as wt
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
    user32.PostMessageW.restype = wt.BOOL

    hwnd = None
    seen = ""
    deadline = time.time() + timeout_s
    while time.time() < deadline and hwnd is None:
        time.sleep(0.5)
        try:
            with open(log_path, "rb") as fh:
                fh.seek(off)
                chunk = fh.read().decode("utf-8", "replace")
                off += len(chunk.encode("utf-8"))
        except OSError:
            continue
        seen += chunk
        for line in seen.splitlines():
            if "POWER_RECOVERY_READY hwnd=" in line:
                hwnd = int(line.split("hwnd=")[1].split()[0])
                break

    results = []
    if not hwnd:
        results.append(("live:app-armed", False, "sem POWER_RECOVERY_READY"))
    else:
        results.append(("live:app-armed", True, "hwnd=%s" % hwnd))
        mod = load(os.path.abspath(REAL))
        ok1 = bool(user32.PostMessageW(hwnd, mod.WM_POWERBROADCAST,
                                       mod.PBT_APMRESUMEAUTOMATIC, 0))
        ok2 = bool(user32.PostMessageW(hwnd, mod.WM_WTSSESSION_CHANGE,
                                       mod.WTS_SESSION_UNLOCK, 0))
        results.append(("live:post-accepted", ok1 and ok2, "resume=%s unlock=%s"
                        % (ok1, ok2)))
        time.sleep(3.0)
        # RELER: a primeira versao deste arm julgava o `seen` de ANTES do post, e
        # publicou sete FAILs sobre uma app que estava a funcionar. O log e' a
        # prova; uma prova lida antes do estimulo nao prova nada.
        try:
            with open(log_path, "rb") as fh:
                fh.seek(off if False else len(seen.encode("utf-8")))
                tail_chunk = fh.read().decode("utf-8", "replace")
            seen += tail_chunk
        except OSError:
            pass

    try:
        import psutil
        for p in psutil.process_iter(["cmdline"]):
            cl = " ".join(p.info["cmdline"] or [])
            if "sotto_webview.py" in cl or "sotto_worker.py" in cl:
                p.kill()
    except Exception:
        pass
    try:
        keep.kill()
    except Exception:
        pass

    tail = seen
    # As contagens sao RELATIVAS aos eventos que a propria app registou: a maquina
    # do dono tambem emite notificacoes de sessao reais, e uma igualdade fixa
    # ("== 2") mediria o ambiente em vez da fiacao.
    resumes = tail.count("POWER_RESUME event=resume")
    unlocks = tail.count("POWER_RESUME event=unlock")
    topmost = tail.count("POWER_RESUME_TOPMOST requested=true")
    worker = tail.count("POWER_RESUME_WORKER alive=")
    geom = tail.count("POWER_RESUME_GEOMETRY")
    results.append(("live:resume-line", resumes >= 1, "resume=%d unlock=%d" % (resumes, unlocks)))
    results.append(("live:unlock-line", unlocks >= 1, "unlock=%d" % unlocks))
    results.append(("live:topmost-requested", topmost == resumes + unlocks,
                    "topmost=%d esperado=%d" % (topmost, resumes + unlocks)))
    results.append(("live:worker-probe-line", worker == resumes,
                    "worker=%d esperado=%d" % (worker, resumes)))
    results.append(("live:geometry-decided", geom == resumes + unlocks,
                    "geometry=%d esperado=%d" % (geom, resumes + unlocks)))
    results.append(("live:no-action-crash", "POWER_RESUME_ACTION_FAILED" not in tail, ""))
    results.append(("live:attach-registered", "POWER_RECOVERY_ATTACHED" in tail, ""))
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--neg-arm", action="store_true")
    ap.add_argument("--live-arm", action="store_true")
    ap.add_argument("--module", default=os.environ.get("SOTTO_POWER_RECOVERY_MODULE", REAL))
    args = ap.parse_args()

    if args.live_arm:
        res = live_arm()
        bad = [a for a in res if not a[1]]
        for name, ok, detail in res:
            print("%-40s %s %s" % (name, "ok" if ok else "FAIL", detail))
        print("VERDICT: %s %d/%d arms" % ("PASS" if not bad else "FAIL",
                                          len(res) - len(bad), len(res)))
        return 0 if not bad else 1

    if not args.neg_arm:
        res = judge(load(os.path.abspath(args.module)))
        bad = [a for a in res if not a[1]]
        for name, ok, detail in res:
            print("%-46s %s %s" % (name, "ok" if ok else "FAIL", detail if not ok else ""))
        print("VERDICT: %s %d/%d arms" % ("PASS" if not bad else "FAIL",
                                          len(res) - len(bad), len(res)))
        return 0 if not bad else 1

    # -- os mutantes ---------------------------------------------------------
    src = io.open(os.path.abspath(args.module), encoding="utf-8", newline="").read()
    mutants = [
        ("unlock also kicks the worker",
         '_PLANS = {\n    "resume": _RESUME,\n    "unlock": (ACT_TOPMOST, ACT_GEOMETRY),',
         '_PLANS = {\n    "resume": _RESUME,\n    "unlock": _RESUME,'),
        ("resume lost the suspend flavour",
         "if wparam in (PBT_APMRESUMEAUTOMATIC, PBT_APMRESUMESUSPEND,\n"
         "                      PBT_APMRESUMECRITICAL):",
         "if wparam in (PBT_APMRESUMEAUTOMATIC,\n"
         "                      PBT_APMRESUMECRITICAL):"),
        ("one failing action kills the rest",
         "            except Exception as exc:  # noqa: BLE001 -- uma accao nao mata as outras\n"
         "                self.log(\"POWER_RESUME_ACTION_FAILED event=%s action=%s error=%r\"\n"
         "                         % (event, act, exc))",
         "            except Exception as exc:  # noqa: BLE001\n"
         "                self.log(\"POWER_RESUME_ACTION_FAILED event=%s action=%s error=%r\"\n"
         "                         % (event, act, exc))\n"
         "                break"),
    ]
    tmp = tempfile.mkdtemp(prefix="power-recovery-mut-")
    caught = 0
    try:
        for i, (label, old, new) in enumerate(mutants):
            if old not in src:
                print("MUTANT SKIPPED (ancora ausente): %s" % label)
                continue
            path = os.path.join(tmp, "mut%d.py" % i)
            io.open(path, "w", encoding="utf-8", newline="").write(src.replace(old, new, 1))
            res = judge(load(path))
            bad = [a[0] for a in res if not a[1]]
            print("%-38s -> %s  %s" % (label, "CAUGHT" if bad else "NOT-CAUGHT", bad))
            caught += 1 if bad else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    total = len(mutants)
    print("NEG-ARM %s cases=%d caught=%d" % ("PASS" if caught == total else "FAIL",
                                              total, caught))
    return 1 if caught == total else 0


if __name__ == "__main__":
    sys.exit(main())
