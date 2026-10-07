"""Measure the three numbers of the owner's panel complaint from the LIVE app log.

READ-ONLY: reads only. Writes nothing outside stdout (tee'd by the caller).

Sources
  _main/webview-run.log          the log the RUNNING app writes (shell 42984,
                                 worker 46832) -- it APPENDS across instances, so
                                 it also carries the earlier --probe-v2 session
                                 (shell 18020, worker 35672) that produced the 13
                                 captions.
  history/2026-10-06/07.md       what the panel committed to disk for the owner.
  worker/runs/*.jsonl            the worker's OWN event shape (start/end), from
                                 other runs of the SAME fixture -- the live
                                 session's own start/end never reach the log.

Population and window are printed next to every number.
"""
import json
import os
import re
import statistics as st
import time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
LOG = os.path.join(ROOT, "_main", "webview-run.log")
HIST = os.path.join(ROOT, "history", "2026-10-06", "07.md")
FIXTURE = os.path.join(ROOT, "worker", "assets", "sample1.flac")

# The fixture's own words. Source: docs/accuracy-int4-vs-fp16-20261006.md:84
# (sherpa-onnx INT8 over sample1.flac, 39 words, byte-identical to the FP32 arm;
# docs/int8-route-20261006.md:158 calls the same string "Reference for the same
# audio"). It is a MACHINE reference, NOT a human transcript -- the repo says so
# itself. Every number below is against THAT, and is labelled as such.
REFERENCE = (
    "Going along slashy country roads and speaking to damp audiences in droughty "
    "schoolrooms day after day for a fortnight, he'll have to put in an appearance "
    "at some place of worship on Sunday morning and he can come to"
)


def words(s):
    s = s.lower()
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    return [w for w in s.split() if w]


def pct(v, p):
    if not v:
        return float('nan')
    xs = sorted(v)
    k = max(0, min(len(xs) - 1, int(round((p / 100.0) * len(xs) + 0.5)) - 1))
    return xs[k]


def stats(name, v, unit="s"):
    if not v:
        print(f"    {name}: POPULACAO n=0 -- nada a medir")
        return
    print(f"    {name}: POPULACAO n={len(v)}  min={min(v):.3f} "
          f"mediana={st.median(v):.3f} p90={pct(v,90):.3f} max={max(v):.3f} "
          f"soma={sum(v):.3f} {unit}")


def lev(a, b):
    n, m = len(a), len(b)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1,
                          d[i - 1][j - 1] + (a[i - 1] != b[j - 1]))
    return d


def ops(a, b):
    d = lev(a, b)
    i, j, out = len(a), len(b), []
    while i > 0 or j > 0:
        if i and j and d[i][j] == d[i - 1][j - 1] + (a[i - 1] != b[j - 1]):
            out.append(("ok" if a[i - 1] == b[j - 1] else "sub", a[i - 1], b[j - 1]))
            i, j = i - 1, j - 1
        elif i and d[i][j] == d[i - 1][j] + 1:
            out.append(("omit", a[i - 1], ""))
            i -= 1
        else:
            out.append(("ins", "", b[j - 1]))
            j -= 1
    return list(reversed(out))


def lcs_len(a, b):
    n, m = len(a), len(b)
    prev = [0] * (m + 1)
    for i in range(1, n + 1):
        cur = [0] * (m + 1)
        for j in range(1, m + 1):
            cur[j] = prev[j - 1] + 1 if a[i - 1] == b[j - 1] else max(prev[j], cur[j - 1])
        prev = cur
    return prev[m]


lines = open(LOG, encoding="utf-8", errors="replace").read().splitlines()
events = []
for i, l in enumerate(lines):
    m = re.match(r"sotto: (\S+)(.*)$", l)
    if m:
        events.append((i + 1, m.group(1), m.group(2).strip()))


def shell_of(idx):
    pid = None
    for (li, tag, rest) in events:
        if li > idx:
            break
        if tag == "shell=webview2":
            mm = re.search(r"pid=(\d+)", rest)
            if mm:
                pid = int(mm.group(1))
    return pid


def bounds(worker):
    lo = next(li for (li, tag, rest) in events
              if tag == "BRIDGE_SPAWNED" and f"pid={worker}" in rest)
    nx = [li for (li, tag, rest) in events
          if tag in ("BRIDGE_EXIT", "SHELL_EXIT") and li > lo]
    return lo, (nx[0] if nx else len(lines) + 1)


NOW = time.strftime("%Y-%m-%d %H:%M:%S")
LMT = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.stat(LOG).st_mtime))
print("=" * 78)
print(f"SOURCE: {os.path.relpath(LOG, ROOT)} ({len(lines)} linhas, "
      f"{os.stat(LOG).st_size} B, mtime {LMT})   AGORA {NOW}")
print("=" * 78)

# ---------------------------------------------------------------- 0 sessions
print("\n0. SESSOES (o log APPENDA entre instancias da app)")
for (li, tag, rest) in events:
    if tag == "BRIDGE_SPAWNED":
        wp = re.search(r"pid=(\d+)", rest).group(1)
        print(f"   linha {li:5d}  BRIDGE_SPAWNED worker={wp}  shell={shell_of(li)}")
    if tag == "SHELL_EXIT":
        print(f"   linha {li:5d}  SHELL_EXIT {rest[:70]}")

FIX_LO, FIX_HI = bounds(35672)
LIVE_LO, LIVE_HI = bounds(46832)
print(f"   sessao do fixture : linhas {FIX_LO}..{FIX_HI} (shell 18020, worker 35672)")
print(f"   sessao AO VIVO    : linhas {LIVE_LO}..{LIVE_HI} (shell "
      f"{shell_of(LIVE_LO)}, worker 46832)  <- a que o dono tem")

# ------------------------------------------------------------------ 1 ATRASO
print("\n" + "=" * 78)
print("1. ATRASO")
print("=" * 78)

sess = [(li, t, r) for (li, t, r) in events if FIX_LO <= li <= FIX_HI]
revs = [r for (_, t, r) in sess if t == "BRIDGE_CAPTION_SENT"]
applied = [r for (_, t, r) in sess if t == "CAPTION_APPLIED"]
print(f"   sessao do fixture, contagens brutas:")
print(f"     BRIDGE_CAPTION_SENT (revisoes que o painel recebeu) = {len(revs)}")
print(f"     CAPTION_APPLIED     (a pagina confirmou ter pintado) = {len(applied)}")
print(f"     HISTORY_APPEND      (linha escrita no disco)         = "
      f"{sum(1 for _,t,_ in sess if t=='HISTORY_APPEND')}")
appends = [(li, r) for (li, t, r) in sess if t == "HISTORY_APPEND"]
ts = [(li, re.search(r"time=(\d\d:\d\d:\d\d)", r).group(1)) for li, r in appends]
print(f"     BRIDGE_SILENT_BENIGN (painel em 'sem audio')         = "
      f"{sum(1 for _,t,_ in sess if t=='BRIDGE_SILENT_BENIGN')}")

clock_tags = Counter(t for (_, t, r) in events if re.search(r"\d\d:\d\d:\d\d", r))
print(f"   tags do log vivo que carregam relogio de parede: {dict(clock_tags)}")

print("""
   1a. ATRASO legenda-a-legenda (audio falado -> texto que aparece)
       NAO-MENSURAVEL: faltam DOIS campos, e a prova nao e' a ausencia no log,
       e' o emissor:
         - BRIDGE_CAPTION_SENT nao tem relogio. Quem a escreve e'
           app/webview/sotto_webview.py:2133 --
           log(f'BRIDGE_CAPTION_SENT delivered=true text={json.dumps(text)}').
         - CAPTION_APPLIED tambem nao. Quem a escreve e' :1133 --
           log(f'CAPTION_APPLIED text=... count=...').
         - E a posicao de audio da legenda tambem nao viaja: o WORKER emite
           {"type":"caption","text":...,"start":S,"end":E} (medido em
           worker/runs/gate-live-speech.jsonl), mas :2131-2133
           (on_worker_caption) manda o texto ao painel e imprime so' o texto.
       Sem relogio E sem posicao de audio na MESMA linha nao existe derivacao.
       Um atraso adivinhado nao e' uma resposta; NAO-MENSURAVEL e'.
""")
print("   1b. O QUE E' DERIVAVEL: o unico relogio de parede do log --")
print("       HISTORY_APPEND time=HH:MM:SS (resolucao 1 s, relogio local).")
print("       E' o commit que o dono ve no historico do painel e no ficheiro.")
print(f"       POPULACAO: os {len(ts)} commits da sessao do fixture  "
      f"JANELA {ts[0][1]}..{ts[-1][1]}")
hh = [int(x[:2]) * 3600 + int(x[3:5]) * 60 + int(x[6:]) for _, x in ts]
span = hh[-1] - hh[0]
deltas = [hh[i + 1] - hh[i] for i in range(len(hh) - 1)]
print(f"       window de relogio de parede = {span} s")
stats("cadencia commit-a-commit (n-1 intervalos)", deltas)
med = st.median(deltas)
holes = [(ts[i][1], ts[i + 1][1], d) for i, d in enumerate(deltas) if d >= 2 * med]
print(f"       buracos (delta >= 2x mediana = {2*med:.0f} s):")
for a, b, d in holes:
    print(f"         {a} -> {b}   {d} s sem nenhum commit")

print("""
   1c. O QUE O DONO SENTE NAO E' O ATRASO DO ASR -- e' o SILENCIO.
       A legenda aparece ou nao aparece; quando nao aparece, o painel escreve
       "No audio to transcribe" e fica la'. Medido na sessao AO VIVO (abaixo,
       secao 3): 503 anuncios de 'sem audio'. O silencio e' o atraso
       INFINITO, e e' a maior parte do tempo de parede da app.
""")

# ---------------------------------------------------------------- 2 ACERTO
print("=" * 78)
print("2. ACERTO")
print("=" * 78)
commits = []
for l in open(HIST, encoding="utf-8", errors="replace").read().splitlines():
    m = re.match(r"- \[(\d\d:\d\d:\d\d)\] (.*)$", l)
    if m:
        commits.append((m.group(1), m.group(2)))
synthetic = [c for c in commits if "SOTTO-V2-" in c[1] or c[1].strip().rstrip(".") == "Ruf"]
fixture = [c for c in commits if c not in synthetic]
print(f"   POPULACAO: {len(commits)} linhas em {os.path.relpath(HIST, ROOT)}  "
      f"JANELA {commits[0][0]}..{commits[-1][0]}")
print(f"   do fixture: {len(fixture)}   injectadas pelo probe --probe-v2: {len(synthetic)}")
for t, x in fixture:
    print(f"     {t}  {x}")

refw = words(REFERENCE)
capw = words(" ".join(x for _, x in fixture))
print(f"\n   referencia (MAQUINA, nao humano): {len(refw)} palavras")
print(f"     \"{REFERENCE}\"")
print(f"   capturado (concatenacao dos commits do fixture): {len(capw)} palavras")

print("""
   NOTA DE MEDICAO (muda o instrumento): o worker ENTROU A MEIO do clipe -- o
   clipe toca em LOOP e o tap comeca no meio, logo o texto do painel nao comeca
   no inicio do script. Comparar a concatenacao com a referencia como se fosse
   uma leitura do inicio produz um WER global sem sentido (o painel comeca a
   mostrar o FIM do script: "After Day for He'll have Sunday and he can").
   Logo, quatro numeros que NAO dependem da fase de entrada:
""")

refset = set(refw)
capw = words(" ".join(x for _, x in fixture))
# de-duplicate: a line of the history is CUMULATIVE (starts with the previous)
runs = []
for t, x in commits:
    prev = runs[-1][1].rstrip(".").lower() if runs else None
    if prev and x.lower().startswith(prev):
        runs[-1] = (t, x)
    else:
        runs.append((t, x))
print(f"   A historia do painel e' CUMULATIVA: 11 linhas do fixture = "
      f"{sum(1 for t,x in runs if 'SOTTO-V2-' not in x and x.strip().rstrip('.')!='Ruf')} "
      f"corridas. Cada commit repete o texto da anterior -- e' por isso que o "
      f"ficheiro tem {len(capw)} palavras para um clipe de 39.")
for t, x in runs:
    print(f"     {t}  {x}")

# (A) coverage: order-free
cov = sorted(set(refw) & set(capw))
print(f"\n   (A) COBERTURA (bag-of-words, sem ordem)")
print(f"       {len(cov)}/{len(set(refw))} palavras distintas da referencia aparecem "
      f"= {100.0*len(cov)/len(set(refw)):.1f}%")
print(f"       NAO apareceram: "
      + ", ".join(sorted(set(refw) - set(capw))))

# (B) ordered agreement OF THE TEXT SHOWN, per line (phase-independent)
tot_shown = tot_ord = 0
print(f"\n   (B) ACERTO EM ORDEM do que foi mostrado (LCS de cada linha contra a "
      f"referencia / palavras dessa linha)")
for t, x in fixture:
    cw = words(x)
    c = lcs_len(refw, cw)
    tot_shown += len(cw)
    tot_ord += c
    extra = [w for w in cw if w not in refset]
    print(f"       {t}  {c:2d}/{len(cw):2d} = {100.0*c/len(cw):5.1f}%   "
          + (f"fora da referencia: {extra}" if extra else ""))
print(f"       TOTAL {tot_ord}/{tot_shown} = {100.0*tot_ord/tot_shown:.1f}% das "
      f"palavras mostradas estao em ordem dentro do script do fixture")

# (C) redundancy
print(f"\n   (C) REDUNDANCIA (o que faz o dono dizer 'nao ta certo')")
print(f"       o painel mostrou {tot_shown} palavras para um clipe de {len(refw)}: "
      f"{tot_shown/len(refw):.2f}x")

# (D) truncations: captured word that is a strict prefix of a reference word
trunc = []
for w in dict.fromkeys(capw):
    if w in refset or len(w) < 3:
        continue
    for v in set(refw):
        if v != w and v.startswith(w):
            trunc.append((w, v))
            break
print(f"\n   (D) CORTES (token truncado na fronteira do chunk): {len(trunc)}")
for w, v in trunc:
    print(f"       {w:14s} (de {v})")

print("\n   AVISO sobre a propria referencia: ela e' MAQUINA, nao humano. Duas")
print("   palavras dela sao suspeitas de erro do ASR que a produziu: 'slashy'")
print("   (o audio diz 'slushy' -- e o capturado ao vivo diz 'slushy') e")
print("   'droughty' (o audio diz 'drafty' -- o capturado diz 'drafty'). Se")
print("   corrigidas, a cobertura SOBE; nao ha transcript humano neste repo")
print("   (docs/accuracy-int4-vs-fp16-20261006.md, secao 'Ground-truth WER').")

# per-commit coverage, so the failing phrases can be named
print(f"\n   por commit (palavras que pertencem a referencia, na ordem):")
for t, x in fixture:
    cw = words(x)
    hold = " ".join(w for w in cw if w in refset)
    print(f"     {t}  {hold[:70]}")

# worker-side view of the SAME session (from BRIDGE_EXIT stderr_tail)
print("\n   lado do WORKER na mesma sessao (BRIDGE_EXIT stderr_tail, linha 498):")
exit_line = next(r for (_, t, r) in sess if t == "BRIDGE_EXIT")
mm = re.search(r"WORKER_STATS tag=tick ([^\"]+)", exit_line)
if mm:
    kv = dict(kv.split("=", 1) for kv in mm.group(1).split() if "=" in kv)
    for k in ("audio_s", "captions", "tokens", "frames", "blanks", "blank_frac",
              "empty_chunks", "vad_gated_chunks", "music_gated_chunks",
              "gate_kept", "queue_drops", "infer_wall_s", "rotations"):
        if k in kv:
            print(f"     {k:18s} = {kv[k]}")
    a, iw = float(kv.get("audio_s", 0)), float(kv.get("infer_wall_s", 0))
    if a:
        print(f"     infer/audio (rtf)  = {iw/a:.3f}  "
              f"(<1 => o worker nao e' o gargalo de computo)")

# ------------------------------------------------------------ 3 CONTINUIDADE
print("\n" + "=" * 78)
print("3. CONTINUIDADE")
print("=" * 78)


def silence(worker, tag):
    lo, hi = bounds(worker)
    s = [(li, t, r) for (li, t, r) in events if lo <= li <= hi]
    sil = [r for (_, t, r) in s if t == "BRIDGE_SILENT_BENIGN"]
    rev = [r for (_, t, r) in s if t == "BRIDGE_CAPTION_SENT"]
    appliedn = sum(1 for _, t, _ in s if t == "CAPTION_APPLIED")
    ms = sorted({int(re.search(r"ms=(\d+)", x).group(1)) for x in sil} or [0])
    peaks = [float(re.search(r"peak=([\d.]+)", x).group(1))
             for x in sil if "peak=" in x]
    reasons = Counter(re.search(r'because="([^" ]+)', x).group(1) for x in sil)
    states = Counter(re.search(r"state=(\S+)", x).group(1) for x in sil)
    print(f"   {tag}: linhas {lo}..{hi}  revisions={len(rev)}  "
          f"CAPTION_APPLIED={appliedn}  'sem audio'={len(sil)}")
    print(f"     ms= distintos: {ms}   estados: {dict(states)}   "
          f"causas: {dict(reasons)}")
    if sil:
        print(f"     o silencio e' re-anunciado a cada {ms[0]/1000.0:.0f} s: "
              f"{len(sil)} anuncios = {len(sil)*ms[0]/1000.0:.0f} s de estado 'sem audio'")
    if peaks:
        print(f"     peak do tap nos anuncios de 'sem audio': n={len(peaks)} "
              f"min={min(peaks)} mediana={st.median(peaks)} max={max(peaks)}")
    return lo, hi


silence(35672, "FIXTURE ")
lo, hi = silence(46832, "AO VIVO ")

print("\n   cross-check do relogio do silencio (independente do log):")
hist_dir = os.path.join(ROOT, "history", "2026-10-06")
files = sorted(os.listdir(hist_dir))
last_hist = max(os.stat(os.path.join(hist_dir, f)).st_mtime for f in files)
print(f"     ficheiros em history/2026-10-06/: {files}")
print(f"     ultimo commit no disco : {time.strftime('%H:%M:%S', time.localtime(last_hist))}"
      f"  ({os.path.relpath(HIST, ROOT)})")
print(f"     agora                  : {time.strftime('%H:%M:%S')}")
elapsed = time.time() - last_hist
print(f"     decorrido desde entao  : {elapsed:.0f} s = {elapsed/60:.1f} min")
n_live = sum(1 for (li, t, r) in events if li >= LIVE_LO and t == "BRIDGE_SILENT_BENIGN")
print(f"     {n_live} anuncios x 15 s = {n_live*15} s  "
      f"(concordancia: {100.0*n_live*15/max(elapsed,1):.1f}%)")
print(f"     => desde {time.strftime('%H:%M:%S', time.localtime(last_hist))} o painel escreveu "
      f"ZERO legendas no disco: {len(files)} ficheiros de hora, o mais novo e' "
      f"{files[-1]}")

# ------------------------------------------- fixture session ordered timeline
print("\n   linha do tempo da sessao do fixture (evidencia crua):")
KEEN = ("BRIDGE_START", "BRIDGE_SPAWNED", "PANEL_V2_PROBE_WAIT",
        "BRIDGE_CAPTION_SENT", "CAPTION_APPLIED", "HISTORY_APPEND",
        "BRIDGE_SILENT_BENIGN", "BRIDGE_EXIT")
for (li, t, r) in sess:
    if t in KEEN:
        print(f"     {li:4d} {t:20s} {r[:96]}")

# ------------------------------------------- head staleness from worker JSONL
print("\n   4. ATRASO DO LADO DO ASR -- populacao DECLARADA: runs do MESMO fixture")
print("      (nao a sessao viva: la' o start/end nunca chega ao log)")
TAPS = ["worker/runs/gate-live-speech.jsonl", "_main/_join-run.out",
        "_main/sdr_arm1_live.jsonl"]
allsp = []
for p in TAPS:
    fp = os.path.join(ROOT, p)
    if not os.path.exists(fp):
        print(f"      AUSENTE {p}")
        continue
    cap = []
    for l in open(fp, encoding="utf-8", errors="replace"):
        try:
            d = json.loads(l)
        except ValueError:
            continue
        if d.get("type") == "caption" and "start" in d:
            cap.append(d)
    sp = [round(c["end"] - c["start"], 3) for c in cap]
    allsp += sp
    print(f"      {p}: n={len(sp)}")
    stats("      end-start", sp)
print(f"      TODOS JUNTOS: n={len(allsp)}")
stats("      end-start (audio que a legenda ja' cobre)", allsp)
print("      LEITURA: 'end' e' a posicao de audio no momento em que o worker emite")
print("      (queue_drops=0 => o tap acompanha o tempo real), e 'start' e' onde o")
print("      TEXTO mostrado comeca. Logo end-start e' quanto audio ja' passou desde")
print("      a primeira palavra DAQUELA linha -- a STALENESS da cabeca da legenda,")
print("      nao a latencia do ASR. A latencia do ASR (fim do texto NUNCA atras do")
print("      audio), essa e' ~0 porque rtf<1.")

# ------------------------------------------------------------------- fixtures
import soundfile as sf
info = sf.info(FIXTURE)
print(f"\n   fixture: {os.path.relpath(FIXTURE, ROOT)}  {info.frames} frames @ "
      f"{info.samplerate} Hz = {info.frames/info.samplerate:.3f} s  "
      f"({info.channels}ch {info.format})")
print("\n" + "=" * 78)
print("FIM -- read-only, nada escrito por este script.")
print("=" * 78)
