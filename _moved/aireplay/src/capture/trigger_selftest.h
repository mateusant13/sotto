// trigger_selftest.h — the named, mechanical gate for the instant-replay trigger.
//
// Arms, and what each one is FOR (a gate that cannot fail is not a gate):
//
//   A  REGISTRATION LADDER — real RegisterHotKey calls against the shipped key ladder on the
//      OWNER'S OWN MACHINE.  Asserts every refusal carries a non-empty Win32 error and that at
//      least one key OR one polled fallback is live.  This is the "another app owns the key"
//      failure mode, measured rather than described.
//   B  DISPATCH — a REAL WM_HOTKEY posted to the trigger's own message-only window, consumed
//      off the pump thread.  Asserts one press becomes exactly one CutRequest with
//      from_registerhotkey set, and that an immediate repeat is SUPPRESSED (the belt under
//      MOD_NOREPEAT).
//   C  EDGE / AUTOREPEAT / RELEASE — eight poll ticks over a scripted key trace
//      (down,down,down,up,up,down,down,up) through a SYNTHETIC key-state function.
//      Asserts exactly 2 requests and **5** suppressed holds.  Synthetic on purpose: injecting a
//      real keystroke would type into whatever window the owner has focused.
//      The 5 is derived from the trace, not chosen: two rising edges (indices 0 and 5) so 2 cuts,
//      and the other five ticks (1,2,3,6,7) each found the key ALREADY down and did not re-fire.
//      An earlier draft of THIS COMMENT said 4, which the code never asserted; the code was right
//      and the comment was wrong.  Corrected 2026-10-07 (lane 23) — the gate prints
//      `suppressed=5 (want 5)`, so leaving "4" here would have been a comment that contradicts
//      the measurement it claims to describe.
//   D  CONTROL — runs arm C's binary against a MUTANT built from a COPY of trigger.cpp with
//      the cure line deleted, and REQUIRES THE MUTANT TO FAIL.  If the mutant still produced 2,
//      arm C is asserting nothing and this arm goes RED.  This is what stops a vacuous gate.
//   E  SHORT RING — a probe that holds 2 s for a key that asked for 30 s, and one that holds
//      45 s.  Asserts shorter_than_requested flips and that the note says so.
//
// NOT COVERED BY ANY ARM, and stated rather than implied: whether a hotkey reaches a
// FULLSCREEN GAME.  No game was run.  Arms A/B/C/D/E prove the trigger's own machinery on
// this host, fullscreen-desktop or not.
#pragma once
#include "trigger.h"

namespace aireplay {

struct ArmResult {
    std::string name;
    bool        pass = false;
    std::string detail;
};

// Writes one `ARM <name> <PASS|FAIL> :: <detail>` line per arm to the log AND stdout.
// `mutant_exe` is the control binary for arm D; if empty, arm D FAILS (a gate that runs
// without its control is not a gate).  Returns 0 iff every arm passed.
int run_trigger_selftest(const std::string& mutant_exe, const std::string& work_dir);

// Arm C on its own, for the control binary: writes "ARMC cuts=<n> suppressed=<n>" to `out_path`
// and returns 0 ALWAYS — a probe reports, the parent judges.
int run_arm_c_probe(const std::string& out_path);

} // namespace aireplay