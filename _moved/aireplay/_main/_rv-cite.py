import subprocess, os, json
ROOT = r"H:\sotto\_moved\aireplay"
def wt_lines(rel):
    p = os.path.join(ROOT, rel.replace("/", os.sep))
    if not os.path.isfile(p): return None
    with open(p, "rb") as f: return f.read().count(b"\n") + (0 if open(p,'rb').read()[-1:]==b"\n" else 1)
def head_lines(rel):
    r = subprocess.run(["git","cat-file","-e","HEAD:"+rel], cwd=ROOT, capture_output=True)
    if r.returncode != 0: return None
    r = subprocess.run(["git","show","HEAD:"+rel], cwd=ROOT, capture_output=True)
    if r.returncode != 0: return None
    return r.stdout.count(b"\n")
CITES = {
"L1": [("src/capture/trigger.cpp",[262,387,404,424,431,442,448,459,505,523,272,315,317,334,281,282,346,378,380,554]),
       ("src/capture/trigger.h",[28,29,33,37,39,40,42,55,99,103,120,106,47,53]),
       ("src/capture/trigger_selftest.cpp",[134,173,332,334,352]),
       ("src/capture/build.cmd",[12]),
       ("src/capture/replay.cpp",[240,241,248,198]),
       ("src/capture/main.cpp",[145,247]),
       ("receipts/receipt-15-instant-replay-trigger.md",[11,12,42,110,191,198,199]),
       ("receipts/receipt-23-trigger-defects.md",[386]),
       ("_main/_lane1-trigger-gate.ps1",[14,18,37,44,117,133,136,138,140,150,152,157,166]),
       ("_main/_lane23-trigger-defects-gate.ps1",[52,54,108,110,191,221]),
       ("_main/logs/lane1/lane1-trigger-gate.txt",[3,4,5,16,17])],
"L3": [("src/capture/ring_buffer.cpp",[20,53,39,43,81,82]),
       ("src/capture/ring_buffer.h",[51,53]),
       ("src/capture/replay.cpp",[38,42,57,130,143,148]),
       ("src/capture/main.cpp",[145,247]),
       ("src/capture/d3d11_ctx.cpp",[70]),
       ("receipts/receipt-16-ring-cap-from-system-ram.md",[42,52,63,75,92]),
       ("_main/_lane3-ringcap-gate.ps1",[17,18,187,188,305])],
"L8": [("AGENTS.md",[456,458]),
       ("_main/ROADMAP.md",[42,61]),
       ("_main/LANE-BRIEF.md",[21]),
       ("src/capture/trigger.cpp",[346]),
       ("docs/integration-sotto-app.md",[]),
       ("docs/overlay-hotkey-contract.md",[])],
"L15":[("specs/07-highlights.md",[4,6,35,57,89,172,177,184,186,219,220,256,276,277,285,296,333,338,339,293,296,425,429,436]),
       ("_main/oracle-07-highlights.py",[104,120,147,156,175,176,216,218]),
       ("src/capture/replay.cpp",[125,132,138,149]),
       ("src/capture/trigger.h",[47,53,99,103,106,120]),
       ("src/asr/segment.py",[64,97,102,103,104]),
       ("src/asr/transcribe.py",[47]),
       ("src/asr/level.py",[45,146]),
       ("src/asr/constants.py",[91,142,144,172]),
       ("specs/03-capture-encode.md",[137,140]),
       ("receipts/receipt-14-ring-cap-vram-vs-ram.md",[])],
}
MIDWRITE = ("receipt-21","receipt-23","receipt-14","heartbeat.ps1","_lane16-wake-gate.ps1")
out={}
for lane, files in CITES.items():
    print("="*96); print("LANE", lane)
    for rel, lines in files:
        w = wt_lines(rel); h = head_lines(rel)
        tag = ""
        if any(m in rel for m in MIDWRITE): tag = "  <MID-WRITE LANE>"
        if w is None and h is None:
            print("  MISSING-BOTH  %-48s%s" % (rel, tag)); continue
        dangling = [n for n in lines if (w is not None and n>w) or (h is not None and n>h)]
        status = "ok" if not dangling else "DANGLING %s" % dangling
        if w is None: status = "NOT-IN-WORKTREE; " + status
        if h is None: status = "NOT-AT-HEAD; " + status
        print("  wt=%-6s head=%-6s %-46s %s%s" % (w if w else "-", h if h else "-", rel, status, tag))
        out.setdefault(lane,[]).append((rel,w,h,dangling))
json.dump(out, open(os.path.join(ROOT,"_main","_rv-cite.json"),"w"), indent=1)
