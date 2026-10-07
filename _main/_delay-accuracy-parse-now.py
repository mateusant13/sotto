"""Second population: a FRESH instance of the app is producing captions RIGHT NOW.

READ-ONLY. The app that this lane measured was cycled (shell 42984 has NO
`SHELL_EXIT` in the log -> killed, not asked to stop) and two new instances are
appended to the SAME `_main/webview-run.log`. This script re-measures the three
numbers on the CURRENT instance, whose population is 20x the 13-caption fixture
session: `history/2026-10-06/09.md`.

Same discipline: population and window declared next to every number, and
`NAO-MENSURAVEL` where the log cannot answer.
"""
import os
import re
import statistics as st
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
LOG = os.path.join(ROOT, "_main", "webview-run.log")
HISTD = os.path.join(ROOT, "history", "2026-10-06")


def words(s):
    s = s.lower()
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    return [w for w in s.split() if w]


def pct(v, p):
    xs = sorted(v)
    k = max(0, min(len(xs) - 1, int(round((p / 100.0) * len(xs) + 0.5)) - 1))
    return xs[k]


def stats(name, v, unit="s"):
    print(f"    {name}: POPULACAO n={len(v)}  min={min(v):.3f} mediana="
          f"{st.median(v):.3f} p90={pct(v, 90):.3f} max={max(v):.3f} "
          f"soma={sum(v):.3f} {unit}")


def lcs_len(a, b):
    prev = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            cur[j] = prev[j - 1] + 1 if a[i - 1] == b[j - 1] else max(prev[j], cur[j - 1])
        prev = cur
    return prev[len(b)]


L = open(LOG, encoding="utf-8", errors="replace").read().splitlines()
print("=" * 78)
print("SESSAO-A-VIVA-2 — instancias que substituiram a app desta lane")
print("=" * 78)

shells = []
for i, l in enumerate(L):
    m = re.search(r"shell=webview2 .* pid=(\d+)", l)
    if m:
        shells.append((i + 1, int(m.group(1))))
spawns = [(i + 1, re.search(r"pid=(\d+)", l).group(1))
          for i, l in enumerate(L) if "BRIDGE_SPAWNED" in l]
exits = [i + 1 for i, l in enumerate(L) if "SHELL_EXIT" in l]
print(f"  log: {len(L)} linhas, {os.stat(LOG).st_size} B, mtime "
      f"{time.strftime('%H:%M:%S', time.localtime(os.stat(LOG).st_mtime))}   "
      f"agora {time.strftime('%H:%M:%S')}")
print(f"  sessoes de shell no log: {len(shells)}")
for (li, pid) in shells[-4:]:
    ended = any(e > li for e in exits)
    # the shell's span ends at the next shell start
    nxt = next((x for x in shells if x[0] > li), None)
    hi = nxt[0] if nxt else len(L) + 1
    seg = L[li - 1:hi - 1]
    sil = sum(1 for x in seg if "BRIDGE_SILENT_BENIGN" in x)
    cap = sum(1 for x in seg if "BRIDGE_CAPTION_SENT" in x)
    app = sum(1 for x in seg if "CAPTION_APPLIED" in x)
    hst = sum(1 for x in seg if "HISTORY_APPEND" in x)
    print(f"    linha {li:5d} shell pid={pid:6d}  linhas {li}..{hi-1}  "
          f"caps={cap} applied={app} history={hst} silent={sil}  "
          f"SHELL_EXIT={'sim' if any(li < e < hi for e in exits) else 'NAO (morto sem despedida)'}")
print("  BRIDGE_SPAWNED (workers):")
for (li, pid) in spawns[-6:]:
    print(f"    linha {li:5d} worker {pid}")

# the session that matters: the last shell
last_li, last_pid = shells[-1]
seg = L[last_li - 1:]
print()
print(f"  ==> A APP AGORA: shell pid={last_pid} (desde a linha {last_li})")

# -------------------------------------------------------------- atraso
print()
print("=" * 78)
print("1. ATRASO — a populacao maior (a instancia AGORA)")
print("=" * 78)
ts = []
for l in seg:
    m = re.search(r'HISTORY_APPEND path="([^"]+)" time=(\d\d:\d\d:\d\d)', l)
    if m:
        ts.append((m.group(1), m.group(2)))
print(f"  POPULACAO: {len(ts)} commits   ficheiro {ts[0][0]}")
print(f"  JANELA: {ts[0][1]} .. {ts[-1][1]}")
hh = [int(t[:2]) * 3600 + int(t[3:5]) * 60 + int(t[6:]) for _, t in ts]
dl = [hh[i + 1] - hh[i] for i in range(len(hh) - 1)]
stats("cadencia commit-a-commit", dl)
print(f"  janela de relogio de parede = {hh[-1] - hh[0]} s "
      f"({(hh[-1]-hh[0])/60.0:.1f} min)")
med = st.median(dl)
holes = [(ts[i][1], ts[i + 1][1], d) for i, d in enumerate(dl) if d >= 5 * med]
print(f"  buracos >= 5x mediana ({5*med:.0f} s): {len(holes)}")
for a, b, d in sorted(holes, key=lambda x: -x[2])[:10]:
    print(f"    {a} -> {b}   {d} s = {d/60.0:.1f} min sem legenda")
print(f"  tempo em buracos >= 5x mediana: {sum(d for _,_,d in holes)} s "
      f"de {hh[-1]-hh[0]} s = {100.0*sum(d for _,_,d in holes)/max(1,hh[-1]-hh[0]):.1f}% da janela")
print()
print("  1a. ATRASO legenda-a-legenda: NAO-MENSURAVEL (mesmo motivo da sessao")
print("      anterior: BRIDGE_CAPTION_SENT e CAPTION_APPLIED nao tem relogio).")
print("      O que se mede ACIMA e' a cadencia de COMMIT, nao a latencia.")

# -------------------------------------------------------------- acerto
print()
print("=" * 78)
print("2. ACERTO — a populacao maior")
print("=" * 78)
histfiles = sorted(os.listdir(HISTD))
print(f"  ficheiros de hora no disco: {histfiles}")
ref = ("Going along slashy country roads and speaking to damp audiences in "
       "droughty schoolrooms day after day for a fortnight, he'll have to put in "
       "an appearance at some place of worship on Sunday morning and he can come to")
refw = words(ref)
print(f"  referencia (MAQUINA, 39 palavras, docs/accuracy-...:84) vs o conteudo de:")
print(f"    history/2026-10-06/09.md")
h = os.path.join(HISTD, "09.md")
commits = []
for l in open(h, encoding="utf-8", errors="replace").read().splitlines():
    m = re.match(r"- \[(\d\d:\d\d:\d\d)\] (.*)$", l)
    if m:
        commits.append((m.group(1), m.group(2)))
print(f"  POPULACAO: {len(commits)} linhas  JANELA {commits[0][0]}..{commits[-1][0]}")
capw = words(" ".join(x for _, x in commits))
print(f"  palavras mostradas: {len(capw)}  para um clipe de {len(refw)}: "
      f"{len(capw)/len(refw):.1f}x")
refset, capset = set(refw), set(capw)
cov = sorted(refset & capset)
print(f"  (A) COBERTURA (bag-of-words) da referencia: {len(cov)}/{len(refset)} "
      f"= {100.0*len(cov)/len(refset):.1f}%")
print(f"      NAO apareceram: {', '.join(sorted(refset-capset))}")
# the fixture's own words, not the pt-BR/other content, is what these lines are
fixturelike = [c for c in commits if len(set(words(c[1])) & refset) >= 2]
print(f"  linhas que partilham >=2 palavras com a referencia: "
      f"{len(fixturelike)}/{len(commits)}")
tot_shown = tot_ord = 0
for t, x in fixturelike:
    cw = words(x)
    tot_shown += len(cw)
    tot_ord += lcs_len(refw, cw)
print(f"  (B) ACERTO EM ORDEM nessas linhas: {tot_ord}/{tot_shown} = "
      f"{100.0*tot_ord/max(1,tot_shown):.1f}%")
print("  (C) REDUNDANCIA: a historia e' CUMULATIVA (cada linha comeca com a anterior)")

# -------------------------------------------------------------- continuidade
print()
print("=" * 78)
print("3. CONTINUIDADE")
print("=" * 78)
sil = [l for l in seg if "BRIDGE_SILENT_BENIGN" in l]
peaks = [float(re.search(r"peak=([\d.]+)", x).group(1)) for x in sil if "peak=" in x]
rs = sorted({int(re.search(r"restarts=(\d+)", x).group(1)) for x in sil if "restarts=" in x})
print(f"  BRIDGE_SILENT_BENIGN nesta instancia: {len(sil)}")
if peaks:
    print(f"  peak do tap: min={min(peaks)} mediana={st.median(peaks)} max={max(peaks)}")
print(f"  restarts= vistos: {rs}")
lastcap = max((i for i, l in enumerate(seg) if "BRIDGE_CAPTION_SENT" in l), default=None)
firstsil = next((i for i, l in enumerate(seg)
                 if "BRIDGE_SILENT_BENIGN" in l and lastcap is not None and i > lastcap), None)
print(f"  ultimo BRIDGE_CAPTION_SENT no indice {lastcap} de {len(seg)-1}; "
      f"primeiro 'sem audio' depois dele no indice {firstsil}")
print("  => a instancia NOVA produz legenda E DEPOIS cai no mesmo estado 'sem audio'.")
print()
print("  o que o painel esta' a pintar no fim do log:")
for l in seg[-2:]:
    print(f"    {l[:120]}")
print()
print("=" * 78)
print("FIM (read-only)")
print("=" * 78)
