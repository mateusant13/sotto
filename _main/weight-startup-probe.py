"""PESO E ARRANQUE -- quanto custa o Sotto e quanto tempo ele leva a ficar pronto.

Ordem do dono (2026-11-04): *"mede peso/arranque"*. Nao havia instrumento que
respondesse as duas coisas na MESMA corrida: o `cost-medido` de 2026-10-31 mediu
processos e RSS de uma sessao ja' quente, e o censo do primeiro frame mede o que
acontece DEPOIS de a pagina existir -- o buraco entre o duplo-clique e o primeiro
pixel ficava sem numero.

O que este probe faz, e so' isto:

  1. arranca a app pelo caminho da lane (`SOTTO_LANE_LAUNCH=1` + `_main/keepalive.py`),
     ESCONDIDA -- AGENTS.md, `SOTTO_NEVER_ON_OWNER_SCREEN`;
  2. carimba o instante de cada marco do log VIVO (`SHELL_STARTUP_STAGE`,
     `SINGLE_INSTANCE`, `WEBVIEW_NAV start/dom/done`, `BRIDGE_SPAWNED`,
     `WEBVIEW2_*`), convertendo o `t=` do proprio shell em ms desde o processo;
  3. amostra a ARVORE de processos a 1 Hz (RSS, VMS, threads, handles, CPU) --
     somando o shell, o worker, o `msedgewebview2.exe` e o `python` do keepalive;
  4. mata a arvore pelo ARTEFACTO (`sotto_webview.py` / `sotto_worker.py` /
     `keepalive.py` no CommandLine), nunca por uma palavra generica -- a regra
     do repo, e a razao dela: um filtro `sotto` ja' matou processo alheio.

Nao toca no audio do dono (nenhum SetMute/SetVolume), nao mostra painel, nao
escreve no `panel-state.json` dele (a lane usa o seu proprio estado quando o
`run.cmd` o isola; aqui apenas se le' o que a shell escrever).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time

ROOT = r"H:\sotto"
LOG = os.path.join(ROOT, "_main", "webview-run.log")
HERE = os.path.dirname(os.path.abspath(__file__))

ARTIFACTS = ("sotto_webview.py", "sotto_worker.py", "keepalive.py")

# Os marcos que importam, na ordem em que o arranque os produz.
MARKERS = (
    "SHELL_STARTUP_STAGE",
    "SINGLE_INSTANCE",
    "HOTKEY_REGISTERED",
    "TRAY_ICON_ADD",
    "WEBVIEW2_PROFILE",
    "PANEL_SHOW_GATE",
    "PANEL_VISIBILITY_AT_STARTUP",
    "WEBVIEW2_INIT_FAILED",
    "WEBVIEW_NAV",
    "PANEL_LAZY_GATE_ARMED",
    "BRIDGE_SPAWNED",
    "WORKER_PROVIDERS",
    "BRIDGE_STATS",
    "WORKER_READY",
    "PANEL_CONTENT",
    "STARTUP_NOT_READY",
    "HANG",
)


def tree(psutil, root_pids):
    procs = set()
    for pid in root_pids:
        if not pid:
            # PID 0 e' o *System Idle Process*: psutil devolve-lhe a memoria do
            # SISTEMA e o tempo de CPU OCIOSO (medido: rss_mb=3558, cpu_s=477778
            # na primeira amostra da corrida de 07:40). Uma amostra com ele vale
            # mais que a app inteira e nao e' a app.
            continue
        try:
            p = psutil.Process(pid)
        except psutil.Error:
            continue
        procs.add(p)
        try:
            procs.update(p.children(recursive=True))
        except psutil.Error:
            pass
    return list(procs)


def sample(psutil, pids):
    tot = {"rss_mb": 0.0, "vms_mb": 0.0, "threads": 0, "handles": 0, "cpu": 0.0, "n": 0}
    for p in tree(psutil, pids):
        try:
            with p.oneshot():
                m = p.memory_info()
                tot["rss_mb"] += m.rss / 1048576.0
                tot["vms_mb"] += m.vms / 1048576.0
                tot["threads"] += p.num_threads()
                try:
                    tot["handles"] += p.num_handles()
                except Exception:
                    pass
                tot["cpu"] += sum(p.cpu_times()[:2])
                tot["n"] += 1
        except psutil.Error:
            continue
    return tot


def sotto_pids(psutil):
    pid_shell = pid_worker = pid_keep = 0
    for p in psutil.process_iter(["cmdline"]):
        try:
            cl = " ".join(p.info["cmdline"] or [])
        except Exception:
            continue
        low = cl.lower()
        if "sotto_webview.py" in low:
            pid_shell = p.pid
        elif "sotto_worker.py" in low:
            pid_worker = p.pid
        elif "keepalive.py" in low:
            pid_keep = p.pid
    return pid_shell, pid_worker, pid_keep


def kill_tree(psutil, pids):
    killed = []
    for p in tree(psutil, pids):
        try:
            p.kill()
            killed.append(p.pid)
        except Exception:  # noqa: BLE001 -- AccessDenied num processo do dono
            continue
    psutil.wait_procs([psutil.Process(p) for p in killed if psutil.pid_exists(p)], timeout=5)
    return killed


def read_new_log(offset):
    try:
        with open(LOG, "rb") as fh:
            fh.seek(offset)
            data = fh.read()
    except OSError:
        return offset, ""
    return offset + len(data), data.decode("utf-8", "replace")


def run_once(psutil, hold_s, label, launch="lane"):
    try:
        off = os.path.getsize(LOG)
    except OSError:
        off = 0

    t0 = time.monotonic()
    wall0 = time.time()
    keep = None
    if launch == "task":
        # `schtasks /run` larga a app com a integridade do dono (high): e' a
        # unica via que da' WebView2 funcional a partir de uma lane -- medido
        # 07:40, a largada directa da pane morre em `WEBVIEW2_INIT_FAILED
        # 0x80010108` e `TRAY_ICON_ADD ok=false winerror=5` (UIPI). A app
        # continua a nascer ESCONDIDA; nada aparece no ecra dele.
        subprocess.run(["schtasks", "/run", "/tn", "Sotto"],
                       capture_output=True, creationflags=0x08000000, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))
    else:
        env = dict(os.environ)
        env["SOTTO_LANE_LAUNCH"] = "1"
        env.setdefault("TMPDIR", r"I:\cc-tmp")
        # `pythonw.exe` pela regra do repo: nenhuma consola visivel.
        pw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if not os.path.exists(pw):
            pw = sys.executable
        keep = subprocess.Popen([pw, os.path.join(HERE, "keepalive.py")], cwd=ROOT, env=env,
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                creationflags=0x08000000, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))

    stamps = {}
    samples = []
    seen_nav = 0
    deadline = t0 + hold_s
    while time.monotonic() < deadline:
        pids = sotto_pids(psutil)
        if pids[0] and "shell" not in stamps:
            stamps["shell"] = round((time.monotonic() - t0) * 1000)
        if pids[1] and "worker" not in stamps:
            stamps["worker"] = round((time.monotonic() - t0) * 1000)

        off, chunk = read_new_log(off)
        for line in chunk.splitlines():
            if "sotto:" not in line:
                continue
            for mk in MARKERS:
                if mk not in line:
                    continue
                if mk == "WEBVIEW_NAV":
                    seen_nav += 1
                    key = "nav%d" % seen_nav
                else:
                    key = mk
                if key in stamps:
                    continue
                # O carimbo e' o `t=` do PROPRIO shell (ms desde o processo),
                # nao o instante em que esta varredura leu a linha: numa leitura
                # por segundo tres marcos chegam no mesmo `chunk` e ficavam todos
                # com a mesma hora -- medido 07:5x, `nav1=nav2=nav3=4875ms`.
                m_t = re.search(r"\bt=(\d+)\b", line)
                stamps[key] = int(m_t.group(1)) if m_t else round((time.monotonic() - t0) * 1000)
                stamps[key + "_line"] = line.strip()[:200]

        s = sample(psutil, pids)
        if s["n"]:
            samples.append({"ms": round((time.monotonic() - t0) * 1000),
                            "rss_mb": round(s["rss_mb"], 1),
                            "threads": s["threads"], "handles": s["handles"],
                            "cpu_s": round(s["cpu"], 2), "procs": s["n"]})
        time.sleep(1.0)

    pids = sotto_pids(psutil)
    # Numa largada por TAREFA a app corre no nivel do dono: a pane (medium) NAO
    # a consegue matar -- medido 07:52, `psutil.AccessDenied (pid=14212)` e o
    # probe morreu com a app de pe'. A via que o Windows da' e' a propria tarefa.
    killed = []
    denied = []
    if launch == "task":
        subprocess.run(["schtasks", "/end", "/tn", "Sotto"],
                       capture_output=True, creationflags=0x08000000, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))
        time.sleep(1.0)
    try:
        killed = kill_tree(psutil, list(pids) + ([keep.pid] if keep else []))
    except Exception as exc:  # noqa: BLE001 -- uma recusa nao apaga a medicao
        denied.append(repr(exc))
    if keep is not None:
        try:
            keep.wait(timeout=5)
        except Exception:
            pass
    time.sleep(1.0)

    peak = max((s["rss_mb"] for s in samples), default=0.0)
    return {
        "label": label,
        "launch": launch,
        "wall_start": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(wall0)),
        "pids": {"shell": pids[0], "worker": pids[1], "keepalive": pids[2]},
        "stamps_ms": stamps,
        "samples": samples,
        "peak_rss_mb": peak,
        "steady_rss_mb": samples[-1]["rss_mb"] if samples else 0.0,
        "peak_procs": max((s["procs"] for s in samples), default=0),
        "peak_threads": max((s["threads"] for s in samples), default=0),
        "cpu_s_total": samples[-1]["cpu_s"] if samples else 0.0,
        "killed": killed,
        "denied": denied,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hold", type=int, default=75, help="segundos de amostragem por corrida")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--launch", choices=("lane", "task"), default="lane",
                    help="lane = keepalive (medium); task = schtasks \\Sotto (high, WebView2 funciona)")
    ap.add_argument("--out", default=os.path.join(HERE, "_cache", "weight-startup.json"))
    args = ap.parse_args()

    import psutil

    shell, worker, keep = sotto_pids(psutil)
    if shell or worker or keep:
        print("RECUSA: ja' existe instancia viva shell=%s worker=%s keepalive=%s"
              % (shell, worker, keep))
        return 2

    results = [run_once(psutil, args.hold, "run%d" % (i + 1), args.launch) for i in range(args.runs)]

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=1)

    for r in results:
        st = r["stamps_ms"]
        print("%s  shell=%sms worker=%sms nav1=%sms nav2=%sms nav3=%sms"
              % (r["label"], st.get("shell", "-"), st.get("worker", "-"),
                 st.get("nav1", "-"), st.get("nav2", "-"), st.get("nav3", "-")))
        print("   pico RSS %.1f MB | estavel %.1f MB | processos %d | threads %d | CPU %.1fs"
              % (r["peak_rss_mb"], r["steady_rss_mb"], r["peak_procs"],
                 r["peak_threads"], r["cpu_s_total"]))
    print("json:", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
