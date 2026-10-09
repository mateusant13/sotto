# review-synthesis.ps1 — census of dispatched reviewer verdicts, for receipt-28.
# READ-ONLY: touches nothing in the repo. Writes only to $env:TEMP (left there; the OS reaps it).
# Usage:  pwsh -NoProfile -File H:\sotto\_moved\aireplay\_main\review-synthesis.ps1 `
#                   [-ParentSession <id>] [-SelfSession <id>]
#
# LANE-BRIEF hard rule 2: never pipe a native command when you need its exit code.
#   -> every native call here is Start-Process -Wait with redirected files, and the exit
#      code is read off the PROCESS OBJECT, never off a pipeline.
# LANE-BRIEF hard rule 1: never leave a visible console window.
#   -> python is launched via Start-Process -WindowStyle Hidden.
#
# -SelfSession: the SYNTHESIS lane's own session id, so the census does not count the
#   synthesizer as a 7th reviewer of the lanes. There is no runtime env var carrying the
#   current session id on this host (measured: only SESSIONNAME / WT_SESSION exist), so it
#   cannot be auto-detected. Omit it and the denominator is wrong -- that bug shipped once
#   (census said REVIEWERS_FOUND=7 when only 6 reviewers existed) and is why the param is here.

[CmdletBinding()]
param(
  [string]$ParentSession = 'mvs_b7a9f3a7db404912b32d28fc11b83645',
  [string]$SelfSession   = ''
)

$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'

$Db  = 'C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite'
$Tmp = Join-Path $env:TEMP ('rev-census-' + [guid]::NewGuid().ToString('N').Substring(0,8))
New-Item -ItemType Directory -Force -Path $Tmp | Out-Null

$py = @"
import sqlite3, json, sys
DB = sys.argv[1]; PARENT = sys.argv[2]; SELF = sys.argv[3]
c = sqlite3.connect('file:%s?mode=ro' % DB, uri=True)

def content(d):
    try: j = json.loads(d)
    except Exception: return ''
    return j.get('msg_content') if isinstance(j, dict) else ''

rows = c.execute('select session_id, agent_name, status, updated_at_ms'
                 ' from local_runtime_sessions where parent_session_id=?'
                 ' order by updated_at_ms', (PARENT,)).fetchall()
kids = [r for r in rows if r[1] == 'verifier' and r[0] != SELF]
print('CHILDREN_OF %s = %d ; VERIFIER_SEATS_EXCLUDING_SELF = %d'
      % (PARENT, len(rows), len(kids)))

complete = inflight = silent = 0
detail = []
for sid, agent, status, upd in kids:
    msgs = c.execute('select role, data_json from local_runtime_message_rows'
                     ' where session_id=? order by id', (sid,)).fetchall()
    a = [content(d) for r, d in msgs if r == 'assistant' and content(d).strip()]
    prompt = next((content(d) for r, d in msgs if r == 'user'), '')
    lane = '?'
    for tok in ('L15','L16','L1','L3','L4','L8'):
        if ('lane %s ' % tok) in prompt[:400] or ('lane %s —' % tok) in prompt[:400]:
            lane = tok; break
    vline = ''
    for x in reversed(a):
        for ln in x.splitlines():
            if ln.startswith('Does your implementation meet the spec?'):
                vline = ln.strip(); break
        if vline: break
    if vline:
        state = 'COMPLETE'; complete += 1
    elif status == 'started':
        state = 'IN-FLIGHT'; inflight += 1
    else:
        state = 'VERDICT-NOT-FOUND'; silent += 1
    detail.append((lane, status, state, len(a), sum(len(x) for x in a),
                   sum(1 for x in a if len(x) >= 1500), sid, vline))

print('%-5s %-8s %-9s %-20s %5s %5s %s' % ('LANE','STATUS','MSGS','SESSION','CHARS','LONG','VERDICT'))
for lane, status, state, nm, ch, nl, sid, vline in sorted(detail):
    print('%-5s %-8s %-9d %-20s %5d %5d %s' % (
        lane, status, nm, sid[:20], ch, nl,
        (vline[:46] + '..') if len(vline) > 46 else ('*** ' + state + ' ***')))

print()
for lane, status, state, nm, ch, nl, sid, vline in sorted(detail):
    print('LANE %-4s %-16s status=%-8s msgs=%-3d long_reports=%-2d verdict=%s'
          % (lane, state, status, nm, nl, 'YES' if vline else 'NO'))
print()
print('REVIEWERS_FOUND      = %d' % len(kids))
print('VERDICTS_READ        = %d' % complete)
print('VERDICT_NOT_FOUND    = %d' % silent)
print('STILL_IN_FLIGHT      = %d' % inflight)
"@

$pyFile = Join-Path $Tmp 'census.py'
Set-Content -Path $pyFile -Value $py -Encoding UTF8
$outFile = Join-Path $Tmp 'census.out'
$errFile = Join-Path $Tmp 'census.err'

if (-not (Test-Path $Db)) { Write-Error "runtime store not found: $Db"; exit 2 }

$p = Start-Process -FilePath 'py' -ArgumentList @('-3', $pyFile, $Db, $ParentSession, $SelfSession) `
        -WindowStyle Hidden -RedirectStandardOutput $outFile `
        -RedirectStandardError $errFile -Wait -PassThru
$rc = $p.ExitCode

Get-Content $outFile -Raw -Encoding UTF8
if ($rc -ne 0) {
    Write-Host "census FAILED rc=$rc (tmp=$Tmp)" -ForegroundColor Red
    Get-Content $errFile -Raw -Encoding UTF8 | Write-Host
}
Write-Host "CENSUS-RC $rc"
Write-Host "TMP-LEFT-BEHIND $Tmp"
exit $rc