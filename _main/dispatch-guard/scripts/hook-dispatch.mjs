#!/usr/bin/env node
// hook-dispatch.mjs - THE SINGLE CHOKE POINT for every hook in this plugin.
//
// OWNER DIRECTIVE, 2026-10-06: the owner continues his other projects in the
// mcode DESKTOP. Two sessions stay on the CLI and must be EXEMPT from the hook
// layer entirely, so that plugin behaviour happens ONLY in the desktop version:
//
//   EXEMPT (CLI) : mvs_ea552229fe164f9e8856fcca8589c41a   manager / this agent
//                  mvs_9eb3cbf9024c4d57bdefc4bf19d0ec03   VOD.RIP
//   EVERYTHING ELSE : hooks run.
//
// WHY A WRAPPER AND NOT A PATCH IN EACH HOOK. Fifteen handlers would each need
// the same three lines, and the one that gets forgotten is invisible: it keeps
// firing and nothing says so. Here there is exactly one place a session can be
// exempted, and hooks.json names it for every handler. The exemption is visible
// in the manifest, which is the file a reader actually opens.
//
// THE SEAM. This process is transparent: it reads the hook's stdin ONCE, decides,
// then either execs the real handler with that same stdin and forwards its
// stdout/stderr/exit code verbatim, or exits 0 having emitted nothing. A handler
// cannot tell the difference, except that in an exempt session it never runs.
//
// IT NEVER WEDGES A PROMPT. Any failure here -- unreadable exemption list,
// unknown target, spawn error -- falls through to RUNNING THE TARGET anyway.
// Failing open towards "the owner's desktop keeps its hooks" is the safe
// direction; failing closed would silently disable protection everywhere.
//
// rc: forwards the handler's rc. This wrapper adds no verdict of its own.
import { readFileSync, existsSync, appendFileSync } from 'node:fs';
import { join, dirname, basename } from 'node:path';
import { spawnSync } from 'node:child_process';

const EXEMPT_FILE = join(process.env.MINIMAX_HOME || '', 'session-exemptions.json');
const FALLBACK_EXEMPT = [
  'mvs_ea552229fe164f9e8856fcca8589c41a',  // manager / this agent -- CLI by owner directive
  'mvs_9eb3cbf9024c4d57bdefc4bf19d0ec03',  // VOD.RIP                    -- CLI by owner directive
];

// ONE EXEMPTION IS NOT A VERDICT ABOUT EVERY PLUGIN IN THAT SESSION.
//
// MEASURED 2026-10-06, twice, and the second time it was not a plugin at all.
//
// 1. A plugin named vodrip-verify-on-stop exists whose entire job is to run in the
//    VOD.RIP session. A blanket session exemption silently killed it -- the exemption
//    was written for "do not run the desktop plugin layer here" and was read as "this
//    session gets no hooks at all".
//
// 2. The p0-ratchet hook -- the one the owner asked for by name, to stop the agent
//    reporting instead of executing -- was ALSO silently dead, because the manager's
//    own session is on the exempt list. MEASURED: running the dispatcher with session
//    mvs_ea552229 produced EMPTY output while a desktop session produced the handler's
//    output from the same command. The exemption had exempted the agent from the very
//    hook meant to correct the agent.
//
// So the exemption is by SCRIPT, not only by session. ALWAYS_RUN survives an exempt
// session. A session exemption must never be able to switch off the guards that
// session exists to run.
const ALWAYS_RUN = [
  'vodrip-verify-on-stop',     // the VOD.RIP session's own guard
  'p0-ratchet-inject',        // the owner's "make it do what is next" hook
  'selfaudit-dispatch-inject',// the owner's "after a SELF-AUDIT, dispatch" hook
  'mission-inject',          // the owner's standing mission; the second door when the cron is dead
];

function exemptSessions() {
  try {
    if (!EXEMPT_FILE || !existsSync(EXEMPT_FILE)) return FALLBACK_EXEMPT;
    const j = JSON.parse(readFileSync(EXEMPT_FILE, 'utf8'));
    const list = Array.isArray(j.exempt_sessions) ? j.exempt_sessions : FALLBACK_EXEMPT;
    return list.filter((s) => typeof s === 'string' && /^mvs_/.test(s));
  } catch {
    return FALLBACK_EXEMPT;   // an unreadable list must not disable the hooks
  }
}

// The session id field name has never been observed in a contract document; a
// prior lane verified only that the runtime sends snake_case AND camelCase
// variants of a field. So discover it by shape rather than by name, and if no
// key looks like a session id we cannot claim the session is exempt.
function currentSessionId(payload) {
  for (const [k, v] of Object.entries(payload || {})) {
    if (/session.*id/i.test(k) && typeof v === 'string' && /^mvs_/.test(v)) return v;
  }
  return null;
}

const target = process.argv[2];
if (!target) process.exit(0);

// Read stdin once. It is forwarded verbatim to the handler.
let stdinBuf;
try { stdinBuf = readFileSync(0); } catch { stdinBuf = Buffer.alloc(0); }

let session = null;
try { session = currentSessionId(JSON.parse(stdinBuf.toString('utf8'))); } catch { /* not json */ }

// A HEARTBEAT, so "is the manifest live?" stops being a belief.
// MEASURED 2026-10-06: the owner was told the hook layer was wired, and it was not
// firing -- because the agent's own session was exempt, so the dispatcher skipped
// every handler and said NOTHING. Nothing in the system could distinguish "wired but
// exempt" from "wired and running", and that is exactly how the ratchet stayed dead
// for hours. One line per invocation, to a file any later turn can read, closes that.
//
// IT IS WRITTEN BEFORE THE EXEMPTION CHECK ON PURPOSE. A heartbeat that only records
// work that DID run is blind to exactly the case it exists to catch: a dispatcher that
// is invoked constantly and skips everything. Write failure is silent -- a heartbeat
// must never be able to wedge a hook.
const _isExempt = !!(session && exemptSessions().includes(session));
const _always = ALWAYS_RUN.some((n) => basename(target).startsWith(n));
try {
  const dir = process.env.MINIMAX_HOME || join(process.env.USERPROFILE || '', '.minimax');
  appendFileSync(join(dir, 'hook-dispatch-heartbeat.log'),
    `${new Date().toISOString()}\tpid=${process.pid}\tsession=${session || 'none'}` +
    `\ttarget=${basename(target)}\texempt=${_isExempt}\talways=${_always}` +
    `\taction=${(_isExempt && !_always) ? 'SKIP' : 'RUN'}\n`);
} catch { /* never fatal */ }

if (_isExempt && !_always) {
  process.exit(0);      // exempt: the handler never runs, and nothing is emitted
}

const res = spawnSync(process.execPath, [target], {
  input: stdinBuf,
  stdio: ['pipe', 'pipe', 'pipe'],
  timeout: 9000,
  maxBuffer: 64 * 1024,
});

// A HEARTBEAT, so "is the manifest live?" stops being a belief.
// MEASURED 2026-10-06: the owner was told the hook layer was wired, and it was not
// firing -- because the agent's own session was exempt, so the dispatcher skipped
// every handler and said nothing. Nothing in the system could distinguish "wired but
// exempt" from "wired and running". One line per invocation, to a file the owner or a
// later turn can read, closes that. Write failure is silent: a heartbeat must never be
// able to wedge a hook.
try {
  const dir = process.env.MINIMAX_HOME || join(process.env.USERPROFILE || '', '.minimax');
  const log = join(dir, 'hook-dispatch-heartbeat.log');
  const stamp = new Date().toISOString();
  appendFileSync(log,
    `${stamp}\tpid=${process.pid}\tsession=${session || 'none'}\ttarget=${basename(target)}\texempt=${exemptSessions().includes(session || '')}\n`);
} catch { /* never fatal */ }
if (res.stdout && res.stdout.length) process.stdout.write(res.stdout);
if (res.stderr && res.stderr.length) process.stderr.write(res.stderr);
// A handler that timed out or blew its buffer still returns ITS status: a timeout
// is not this wrapper's verdict to invent, and collapsing it to 0 would read as
// a clean pass. Fall through to the handler's code, or 1 if there is none.
process.exit(typeof res.status === 'number' ? res.status : 1);