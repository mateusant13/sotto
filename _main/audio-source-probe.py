#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audio-source-probe.py -- MEDICAO DA FONTE DO SOM (metade "quem esta a soar").

Lane: audio-source-metadata. Escreve APENAS em _main\.
Nunca abre um stream de captura nem reproduz audio: so Activate(IAudioSessionManager2)
e Activate(IAudioMeterInformation) no endpoint, mais QueryInterface do meter por sessao.

Via: IMMDeviceEnumerator -> endpoint de render -> IAudioSessionManager2 ->
GetSessionEnumerator -> IAudioSessionControl2 (pid, display_name, icon_path,
identifier, is_system_sounds) + IAudioMeterInformation (quem esta mais alto).

Uso:
  python audio-source-probe.py --secs 20 --hz 4 --out x.jsonl --txt x.txt
  python audio-source-probe.py --once --all-endpoints
  python audio-source-probe.py --once --neg-arm-iid      # controlo: meter tem de ficar nulo
  python audio-source-probe.py --once --neg-arm-floor    # controlo: chao absurdo -> source=null
  python audio-source-probe.py --list-endpoints
"""
import argparse
import collections
import ctypes
import ctypes.wintypes as wintypes
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "_libs"))

import comtypes  # noqa: E402
from comtypes import COMMETHOD, GUID, HRESULT, IUnknown  # noqa: E402
from ctypes import POINTER, c_float, c_uint32, byref  # noqa: E402

from pycaw.api.audiopolicy import IAudioSessionControl2  # noqa: E402
from pycaw.api.audioclient import ISimpleAudioVolume  # noqa: E402
from pycaw.constants import DEVICE_STATE, EDataFlow  # noqa: E402
from pycaw.utils import AudioUtilities  # noqa: E402


# --------------------------------------------------------------------------
# IAudioMeterInformation -- definido a mao porque o pycaw nao o traz.
# IID oficial: {C02216F6-8C67-4B5B-9D00-D008E73E0064}
# --------------------------------------------------------------------------
METER_IID = "{C02216F6-8C67-4B5B-9D00-D008E73E0064}"


class IAudioMeterInformation(IUnknown):
    _iid_ = GUID(METER_IID)
    _methods_ = (
        COMMETHOD([], HRESULT, "GetPeakValue", (["out"], POINTER(c_float), "pfPeak")),
        COMMETHOD(
            [],
            HRESULT,
            "GetMeteringChannelCount",
            (["out"], POINTER(c_uint32), "pnChannelCount"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "GetChannelsPeakValues",
            (["in"], c_uint32, "u32ChannelCount"),
            (["out"], POINTER(c_float), "afPeakValues"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "QueryHardwareSupport",
            (["out"], POINTER(c_uint32), "pdwHardwareSupportMask"),
        ),
    )


# --------------------------------------------------------------------------
# caminho do executavel por PID (API nativa; nada de WMI)
# --------------------------------------------------------------------------
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_k32.OpenProcess.restype = wintypes.HANDLE
_k32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    POINTER(wintypes.DWORD),
]
_k32.QueryFullProcessImageNameW.restype = wintypes.BOOL
_k32.CloseHandle.argtypes = [wintypes.HANDLE]


def exe_path_for_pid(pid):
    """Caminho completo do executavel, ou None (pid 0 / acesso negado / morto)."""
    if not pid:
        return None
    h = _k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return None
    try:
        buf = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(32768)
        if _k32.QueryFullProcessImageNameW(h, 0, buf, byref(size)):
            return buf.value
        return None
    finally:
        _k32.CloseHandle(h)


SESSION_STATE = {0: "Inactive", 1: "Active", 2: "Expired"}


def say(msg):
    """print seguro: sob pythonw.exe sys.stdout e None."""
    if sys.stdout is not None:
        try:
            print(msg, flush=True)
        except Exception:
            pass


# --------------------------------------------------------------------------
# instrumento
# --------------------------------------------------------------------------
def pick_source(pool, floor):
    """Escolhe A FONTE dentro de um conjunto de candidatos.

    Regra declarada: maior `peak_max_win` (janela deslizante); empate desfeito pelo
    `peak` instantaneo; tem de passar o chao. Devolve None se nada passar o chao.
    Factored para poder ser testada com candidatos sinteticos (--selftest), sem audio.
    """
    if not pool:
        return None
    ordered = sorted(
        pool, key=lambda c: (c["peak_max_win"], c["peak"]), reverse=True
    )
    best = ordered[0]
    if best["peak_max_win"] < floor:
        return None
    second = None
    for c in ordered[1:]:
        if c["peak_max_win"] >= floor:
            second = c
            break
    out = dict(best)
    out["reason"] = "max-peak_max_win-above-floor"
    if second:
        out["runner_up"] = {
            "pid": second["pid"],
            "exe_name": second["exe_name"],
            "display_name": second["display_name"],
            "peak_max_win": second["peak_max_win"],
        }
        a = best["peak_max_win"]
        b = second["peak_max_win"]
        out["margin_ratio"] = round(a / b, 3) if b > 0 else None
        out["ambiguous"] = bool(b > 0 and a / b < 1.5)
    else:
        out["runner_up"] = None
        out["margin_ratio"] = None
        out["ambiguous"] = False
    return out


class SessionMeterTracker:
    """Guarda o pico maximo por sessao numa janela deslizante.

    Chave = instance_identifier (unico por sessao/instancia); se vier vazio,
    caimos para (endpoint_id, pid, identifier).
    """

    def __init__(self, window_secs):
        self.window = float(window_secs)
        self._hist = collections.defaultdict(collections.deque)

    def key(self, ep_id, sess):
        k = sess.get("instance_identifier") or ""
        if not k:
            k = "%s|%s|%s" % (ep_id, sess.get("pid"), sess.get("identifier"))
        return k

    def push(self, key, t, peak):
        dq = self._hist[key]
        dq.append((t, peak))
        while dq and t - dq[0][0] > self.window:
            dq.popleft()
        return max((p for _, p in dq), default=0.0)

    def max_in_window(self, key):
        dq = self._hist.get(key)
        if not dq:
            return 0.0
        return max((p for _, p in dq), default=0.0)


class Probe:
    def __init__(self, args):
        self.args = args
        self.meter_iid = args.meter_iid or METER_IID
        self.floor = float(args.floor)
        self.tracker = SessionMeterTracker(args.win)
        self.exe_cache = {}
        self._endpoints = None
        self.default_ep_id = None
        self._meter_unavailable = 0
        self._meter_ok = 0
        self._meter_err = collections.Counter()

    # ---- endpoints -------------------------------------------------------
    def refresh_endpoints(self):
        enumerator = AudioUtilities.GetDeviceEnumerator()
        try:
            default_dev = enumerator.GetDefaultAudioEndpoint(
                EDataFlow.eRender.value, 1  # eMultimedia
            )
            self.default_ep_id = default_dev.GetId()
        except Exception as exc:  # pragma: no cover
            self.default_ep_id = None
            self.note("GetDefaultAudioEndpoint falhou: %r" % (exc,))

        collection = enumerator.EnumAudioEndpoints(
            EDataFlow.eRender.value, DEVICE_STATE.ACTIVE.value
        )
        eps = []
        for i in range(collection.GetCount()):
            dev = collection.Item(i)
            if dev is None:
                continue
            ep = {"id": dev.GetId(), "device": dev, "name": None, "wrapper": None}
            try:
                wrapper = AudioUtilities.CreateDevice(dev)
                ep["wrapper"] = wrapper
                ep["name"] = wrapper.FriendlyName
            except Exception as exc:
                ep["name"] = "<erro: %r>" % (exc,)
            eps.append(ep)
        self._endpoints = eps
        return eps

    def endpoint_meter(self, dev):
        """Controlo positivo do instrumento: meter do ENDPOINT (o mix).
        Activate(IAudioMeterInformation) nao abre stream de captura."""
        try:
            iface = dev.Activate(GUID(self.meter_iid), comtypes.CLSCTX_ALL, None)
            m = iface.QueryInterface(IAudioMeterInformation)
            return float(m.GetPeakValue())
        except Exception as exc:
            return "ERR:%s" % (exc,)

    # ---- sessoes ---------------------------------------------------------
    def sessions_of(self, ep):
        out = []
        try:
            # Activate devolve IUnknown: e preciso QueryInterface (pycaw faz o mesmo).
            mgr = ep["wrapper"].AudioSessionManager
            enum = mgr.GetSessionEnumerator()
            count = enum.GetCount()
        except Exception as exc:
            return [{"error": "GetSessionEnumerator falhou: %r" % (exc,)}]

        for i in range(count):
            row = {"index": i}
            try:
                ctl = enum.GetSession(i)
                ctl2 = ctl.QueryInterface(IAudioSessionControl2)
            except Exception as exc:
                row["error"] = "GetSession/QI falhou: %r" % (exc,)
                out.append(row)
                continue
            try:
                row["pid"] = int(ctl2.GetProcessId())
            except Exception as exc:
                row["pid"] = None
                row["pid_error"] = repr(exc)
            try:
                row["is_system_sounds"] = ctl2.IsSystemSoundsSession() == 0
            except Exception as exc:
                row["is_system_sounds"] = None
                row["issys_error"] = repr(exc)
            try:
                row["state"] = SESSION_STATE.get(int(ctl2.GetState()), "?")
            except Exception as exc:
                row["state"] = None
                row["state_error"] = repr(exc)
            for field, getter in (
                ("display_name", "GetDisplayName"),
                ("icon_path", "GetIconPath"),
                ("identifier", "GetSessionIdentifier"),
                ("instance_identifier", "GetSessionInstanceIdentifier"),
            ):
                try:
                    row[field] = getattr(ctl2, getter)()
                except Exception as exc:
                    row[field] = None
                    row[field + "_error"] = repr(exc)

            pid = row.get("pid")
            if pid:
                if pid not in self.exe_cache:
                    self.exe_cache[pid] = exe_path_for_pid(pid)
                row["exe"] = self.exe_cache[pid]
                row["exe_name"] = (
                    os.path.basename(row["exe"]) if row.get("exe") else None
                )
            else:
                row["exe"] = None
                row["exe_name"] = None

            # volume/mute da sessao: metadado barato e util (app muda nao soa)
            try:
                vol = ctl2.QueryInterface(ISimpleAudioVolume)
                row["volume"] = round(float(vol.GetMasterVolume()), 6)
                row["muted"] = bool(vol.GetMute())
            except Exception as exc:
                row["volume"] = None
                row["muted"] = None
                row["volume_error"] = repr(exc)

            # o meter DA SESSAO
            try:
                if self.args.meter_iid:
                    # controlo: QI pelo IID CONFIGURADO. Com um IID falso isto
                    # levanta E_NOINTERFACE -> peak None (o controlo fica vermelho).
                    m = ctl2.QueryInterface(GUID(self.meter_iid))
                else:
                    m = ctl2.QueryInterface(IAudioMeterInformation)
                row["peak"] = round(float(m.GetPeakValue()), 6)
                row["peak_available"] = True
                self._meter_ok += 1
            except Exception as exc:
                row["peak"] = None
                row["peak_available"] = False
                self._meter_unavailable += 1
                self._meter_err[type(exc).__name__ + ":" + str(exc)[:60]] += 1
            out.append(row)
        return out

    # ---- uma amostra -----------------------------------------------------
    def sample(self, seq):
        t = time.time()
        eps = self._endpoints
        if self.args.all_endpoints:
            use = eps
        else:
            use = [e for e in eps if e["id"] == self.default_ep_id] or eps

        rec = {
            "seq": seq,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t))
            + (".%03d" % int((t % 1) * 1000))
            + time.strftime("%z", time.localtime(t)),
            "ts_unix": round(t, 3),
            "floor": self.floor,
            "win_secs": self.args.win,
            "endpoints": [],
        }
        candidates = []
        for ep in use:
            sess = self.sessions_of(ep)
            em = self.endpoint_meter(ep["device"])
            for s in sess:
                if s.get("peak") is None:
                    continue
                k = self.tracker.key(ep["id"], s)
                s["peak_max_win"] = round(self.tracker.push(k, t, s["peak"]), 6)
                s["_key"] = k
            rec["endpoints"].append(
                {
                    "id": ep["id"],
                    "name": ep["name"],
                    "is_default": ep["id"] == self.default_ep_id,
                    "endpoint_meter_peak": em,
                    "sessions": sess,
                }
            )
            for s in sess:
                if s.get("peak_available"):
                    candidates.append(
                        {
                            "endpoint_id": ep["id"],
                            "endpoint_name": ep["name"],
                            "index": s.get("index"),
                            "pid": s.get("pid"),
                            "exe": s.get("exe"),
                            "exe_name": s.get("exe_name"),
                            "display_name": s.get("display_name"),
                            "icon_path": s.get("icon_path"),
                            "identifier": s.get("identifier"),
                            "instance_identifier": s.get("instance_identifier"),
                            "is_system_sounds": bool(s.get("is_system_sounds")),
                            "state": s.get("state"),
                            "muted": s.get("muted"),
                            "volume": s.get("volume"),
                            "peak": s.get("peak"),
                            "peak_max_win": s.get("peak_max_win"),
                        }
                    )

        # ---- quem e A FONTE ---------------------------------------------
        # Regra: maior peak_max_win (janela deslizante declarada) entre as sessoes
        # NAO-sistema; empate desfeito pelo peak instantaneo; tem de passar o chao.
        apps = [c for c in candidates if not c["is_system_sounds"]]
        syss = [c for c in candidates if c["is_system_sounds"]]
        rec["n_sessions_with_meter"] = len(candidates)
        rec["n_app_sessions"] = len(apps)

        src = pick_source(apps, self.floor)
        src_any = pick_source(candidates, self.floor)
        rec["source"] = src
        rec["source_including_system_sounds"] = src_any
        if src is None and src_any is None:
            rec["source_reason"] = "all-sessions-below-floor"
        if self.args.watch_file:
            try:
                rec["watch_bytes"] = os.path.getsize(self.args.watch_file)
            except OSError as exc:
                rec["watch_bytes"] = None
                rec["watch_error"] = repr(exc)
        return rec

    # ---- utilitarios -----------------------------------------------------
    def note(self, msg):
        if sys.stderr is not None:
            try:
                sys.stderr.write("NOTE %s\n" % msg)
                sys.stderr.flush()
            except Exception:
                pass


def human_line(rec):
    src = rec.get("source")
    if src is None:
        s = "SOURCE=null (%s)" % rec.get("source_reason", "no app session above floor")
    else:
        s = "SOURCE pid=%s exe=%s peak_win=%.4f peak=%.4f name=%r%s" % (
            src["pid"],
            src["exe_name"],
            src["peak_max_win"],
            src["peak"],
            src["display_name"],
            " AMBIGUOUS(margin=%.2f)" % src["margin_ratio"]
            if src.get("ambiguous")
            else "",
        )
    rows = []
    for ep in rec["endpoints"]:
        for ss in ep["sessions"]:
            if not ss.get("peak_available"):
                continue
            rows.append(
                "pid=%s %s peak=%.4f win=%.4f dn=%r sys=%s st=%s"
                % (
                    ss.get("pid"),
                    ss.get("exe_name"),
                    ss.get("peak", -1),
                    ss.get("peak_max_win", -1),
                    ss.get("display_name"),
                    ss.get("is_system_sounds"),
                    ss.get("state"),
                )
            )
    return "[%s] %s | %s" % (rec["ts"], s, " ;; ".join(rows))


def selftest():
    """Gate da LOGICA de escolha da fonte, com candidatos sinteticos.

    Nao precisa de audio nenhum: testa o que decide "qual soa mais alto" e o chao.
    Cada braco imprime PASS/FAIL; o veredicto final e a conjuncao.
    """
    def cand(pid, exe, win, peak, syss=False):
        return {
            "pid": pid, "exe_name": exe, "display_name": "", "peak": peak,
            "peak_max_win": win, "is_system_sounds": syss, "endpoint_name": "X",
        }

    arms = []

    def check(name, cond, detail):
        arms.append((name, bool(cond), detail))
        say("  %-52s %s   %s" % (name, "PASS" if cond else "FAIL", detail))

    a = cand(1, "game.exe", 0.50, 0.31)
    b = cand(2, "discord.exe", 0.20, 0.18)
    r = pick_source([a, b], 0.001)
    check("maior peak_max_win ganha", r and r["exe_name"] == "game.exe", "src=%s" % (r and r["exe_name"]))
    check("margin_ratio = 2.5", r and r["margin_ratio"] == 2.5, "margin=%s" % (r and r["margin_ratio"]))
    check("nao ambiguo (2.5 >= 1.5)", r and r["ambiguous"] is False, "ambiguous=%s" % (r and r["ambiguous"]))
    check("runner_up e o segundo", r and r["runner_up"]["exe_name"] == "discord.exe", "%s" % (r and r["runner_up"]))

    r2 = pick_source([cand(1, "a.exe", 0.50, 0.5), cand(2, "b.exe", 0.45, 0.45)], 0.001)
    check("empate apertado -> ambiguo", r2 and r2["ambiguous"] is True, "margin=%s" % (r2 and r2["margin_ratio"]))

    r3 = pick_source([a, b], 1.1)
    check("chao 1.1 corta tudo -> None", r3 is None, "src=%s" % (r3,))

    cands_sys = [cand(0, None, 0.9, 0.9, syss=True), b]
    apps_sys = [c for c in cands_sys if not c["is_system_sounds"]]
    r4 = pick_source(apps_sys, 0.001)
    check("sons de sistema NAO sao a fonte (particao)", r4 and r4["exe_name"] == "discord.exe",
          "src=%s" % (r4 and r4["exe_name"]))
    r5 = pick_source(cands_sys, 0.001)
    check("mas sao a fonte no pool TOTAL", r5 and r5["is_system_sounds"] is True,
          "src=%s" % (r5 and r5.get("exe_name")))

    r6 = pick_source([], 0.001)
    check("pool vazio -> None", r6 is None, "src=%s" % (r6,))

    r7 = pick_source([cand(1, "x.exe", 0.001, 0.001)], 0.001)
    check("exactamente no chao -> passa", r7 is not None, "src=%s" % (r7 and r7["exe_name"]))

    ok = all(c for _, c, _ in arms)
    say("SELFTEST-VERDICT: %s  (%d/%d PASS)" % ("GREEN" if ok else "RED",
                                                sum(1 for _, c, _ in arms if c), len(arms)))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--secs", type=float, default=0.0, help="duracao (0 = com --once)")
    ap.add_argument("--hz", type=float, default=2.0, help="amostras por segundo")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--out", default=None, help="JSONL por amostra")
    ap.add_argument("--txt", default=None, help="log humano")
    ap.add_argument("--floor", type=float, default=0.001,
                    help="chao de amplitude linear (0.001 = -60 dBFS)")
    ap.add_argument("--win", type=float, default=1.0,
                    help="janela deslizante do pico por sessao (s)")
    ap.add_argument("--all-endpoints", action="store_true",
                    help="todas as endpoints de render activas (default: so a por omissao)")
    ap.add_argument("--list-endpoints", action="store_true")
    ap.add_argument("--watch-file", default=None,
                    help="controlo cruzado: tamanho (bytes) deste ficheiro por amostra "
                         "(ex.: _main/webview-run.log, que cresce quando o worker transcreve)")
    ap.add_argument("--no-endpoint-meter", action="store_true",
                    help="nao le o meter do endpoint (controlo positivo)")
    ap.add_argument("--meter-iid", default=None,
                    help="controlo: IID alternativo do meter (neg-arm-iid)")
    ap.add_argument("--neg-arm-iid", action="store_true")
    ap.add_argument("--neg-arm-floor", action="store_true")
    ap.add_argument("--selftest", action="store_true",
                    help="gate da logica de escolha da fonte com candidatos sinteticos")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    if args.neg_arm_iid:
        args.meter_iid = "{00000000-0000-0000-0000-0000000000FF}"
    if args.neg_arm_floor:
        args.floor = 1.1

    comtypes.CoInitialize()
    t_wall0 = time.time()
    t_cpu0 = time.process_time()
    try:
        p = Probe(args)
        p.refresh_endpoints()
        if args.list_endpoints:
            for ep in p._endpoints:
                say("endpoint default=%s name=%r id=%s"
                    % (ep["id"] == p.default_ep_id, ep["name"], ep["id"]))
            return 0

        fout = open(args.out, "w", encoding="utf-8") if args.out else None
        ftxt = open(args.txt, "w", encoding="utf-8") if args.txt else None
        n = 0
        samples = []
        while True:
            rec = p.sample(n)
            samples.append(rec)
            line = human_line(rec)
            say(line)
            if ftxt:
                ftxt.write(line + "\n")
                ftxt.flush()
            if fout:
                fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fout.flush()
            n += 1
            if args.once:
                break
            if args.secs > 0 and (time.time() - t_wall0) >= args.secs:
                break
            time.sleep(max(0.0, 1.0 / args.hz))

        # ---- custo do proprio instrumento --------------------------------
        try:
            import psutil

            rss_mb = psutil.Process().memory_info().rss / (1024 * 1024)
        except Exception:
            rss_mb = None
        summary = {
            "kind": "probe-summary",
            "samples": n,
            "wall_secs": round(time.time() - t_wall0, 3),
            "cpu_secs": round(time.process_time() - t_cpu0, 3),
            "cpu_percent_of_one_core": round(
                100.0 * (time.process_time() - t_cpu0) / max(1e-6, time.time() - t_wall0), 2
            ),
            "rss_mb": round(rss_mb, 1) if rss_mb else None,
            "threads": 1,
            "meter_reads_ok": p._meter_ok,
            "meter_reads_unavailable": p._meter_unavailable,
            "meter_errors": dict(p._meter_err),
            "default_endpoint_id": p.default_ep_id,
            "meter_iid": p.meter_iid,
            "floor": args.floor,
        }
        say(json.dumps(summary, ensure_ascii=False))
        if ftxt:
            ftxt.write(json.dumps(summary, ensure_ascii=False) + "\n")
            ftxt.close()
        if fout:
            fout.write(json.dumps(summary, ensure_ascii=False) + "\n")
            fout.close()
        return 0
    finally:
        comtypes.CoUninitialize()


if __name__ == "__main__":
    sys.exit(main())
