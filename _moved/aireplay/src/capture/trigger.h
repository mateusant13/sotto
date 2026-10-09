// trigger.h — THE INSTANT-REPLAY TRIGGER: the key that ShadowPlay's whole promise hangs on.
//
// MEASURED FACT this file exists to answer (lane brief §3): "There is no hotkey. 0 hits
// across src/capture. The cut is by time (cut_at_s)."  Before this file the ONLY way a clip
// ended was `Replay::run()`'s `if (!cut_issued && elapsed >= cut_ns) issue_cut(f.qpc_ns)`
// (replay.cpp:539) — one cut, on a timer, and the key did not exist.  This file is that key.
//
// ── WHAT IT IS, AND WHY IT IS TWO PATHS ───────────────────────────────────────────────────
// A global hotkey on Windows has exactly two implementations, and this lane ships BOTH,
// because each one fails in a situation the other survives:
//
//   1. RegisterHotKey + a dedicated message-pump thread.
//      + survives the key being HELD (you get one WM_HOTKEY, autorepeat is suppressed by the
//        OS when MOD_NOREPEAT is set — the suppression is in the kernel, not in our code).
//      + costs nothing while idle: it is a message, not a poll.
//      − FAILS ENTIRELY when another process already registered the key
//        (ERROR_HOTKEY_ALREADY_REGISTERED).  On a gaming PC F10/F11/F12/PrintScreen are the
//        first keys every overlay, every screen recorder and every RGB driver takes.
//      − delivers NOTHING while no thread pumps that message queue.  The naive wiring — call
//        RegisterHotKey from the capture thread and then sit in the capture loop — compiles,
//        runs, reports "armed", and never fires.  This lane exists partly to make that
//        impossible: `arm()` owns the pump thread, so there is no way to arm without a pump.
//
//   2. GetAsyncKeyState polling on its own thread, edge-detected against a per-binding latch.
//      + works even when the key IS already registered by somebody else — it reads the
//        physical key state, not an owned registration.
//      + is not subject to the integrity mismatch that suppresses WM_HOTKEY delivery
//        (UIPI: a hotkey registered at medium integrity is not delivered to a window running
//        at a higher one, and a game launched "Run as administrator" is exactly that).
//      − costs a wakeup every poll_tick_ms, and is LEVEL-triggered, so a held key would emit
//        a request per tick unless it is edge-detected.  That latch is the cure ARM D proves.
//      − reads the key AND the modifier keys (5 extra GetAsyncKeyState calls per tick, not per
//        binding — the mask is measured once and shared), so a binding that ignores `mods`
//        would otherwise be indistinguishable from its own chord.
//      − cannot see the UAC secure desktop (a different desktop); neither path can.
//
// MEASUREMENT STATUS, stated up front and not buried: the dispatch path, the registration
// ladder and the edge logic are all measured by _main\_lane1-trigger-gate.ps1 on THIS host
// (arms A-E; arm D is that gate's CONTROL, not a check).  WHICH PATH FIRES INSIDE A
// FULLSCREEN GAME IS **NOT MEASURED IN-GAME** — no game was run.
//
// CITATION HISTORY for this paragraph, recorded 2026-10-07 — read it before trusting the receipt.
// This header used to end with "See receipts\receipt-15-instant-replay-trigger.md for exactly
// what was measured".  AT 12:27 TODAY THAT FILE DID NOT EXIST: `Test-Path` said False and a
// listing of receipts\ held only receipt-15-offline-cut-pass1147.md.  A citation to a
// measurement that never happened is worse than an admission of having none, so the reference
// was DELETED rather than quietly left standing.  AT 12:40 THE OWNING TRIGGER LANE (L1) WROTE
// THAT FILE (12259 B; untracked in git as of this edit), and the citation is therefore
// RESTORED.  Both statements are true; only the second describes the present.
//
// The audit trail is kept on purpose: the next reader needs to know the reference was once
// false, so that "the receipt exists" is never again mistaken for "the receipt was there when
// the claim was written".  If you are reading this and the file is gone again, trust the GATE —
// _main\_lane23-trigger-defects-gate.ps1 — not the receipt; the gate is what produced every
// number quoted here, and receipts/receipt-23-trigger-defects.md is this lane's own record.
//
// ── WHY THIS DOES NOT EDIT replay.h / replay.cpp / main.cpp ───────────────────────────────
// `Replay::issue_cut(uint64_t)` is PRIVATE (replay.h:162) and takes ONE argument: the QPC
// timestamp to cut at.  So the trigger does not need to know anything about Replay — it
// produces a `CutRequest` and the hookup is a THREE-LINE call in the run loop.  The exact
// patch (file, function, line anchor, code) is in the receipt, §"HOOKUP", because that file
// belongs to another lane and rule 5 of the lane brief forbids editing it.
//
// ── THE RING IS SOMEBODY ELSE'S ─────────────────────────────────────────────────────────
// `RingBuffer` is owned by `Replay`.  This lane may not edit it, so the trigger cannot ask it
// how much history it holds — it ASKS, through the one-method `RingSpanProbe` below, and it
// REPORTS the answer in `CutRequest::ring_span_s` / `::shorter_than_requested`.  "The ring
// held less than N seconds" is exactly the failure that makes an instant-replay product feel
// broken (you press the key, you get a 4-second clip and no explanation), so it is a named
// field, not a silent clamp.
#pragma once
#include "common.h"

#include <atomic>
#include <condition_variable>
#include <deque>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

namespace aireplay {

#ifndef MOD_NOREPEAT
#define MOD_NOREPEAT 0x4000
#endif

// One key the trigger watches.  `mods` is the Win32 MOD_* mask WITHOUT MOD_NOREPEAT — the
// trigger ORs that in itself, so no caller can accidentally ship a repeating hotkey.
//
// `mods` is matched by EQUALITY against the modifiers physically held, never by intersection:
// a binding fires when its key is down AND the held modifier mask IS its `mods`.  Holding a
// modifier the binding did not declare does not match it.  (Intersection is what made
// `Alt+F10` fire the plain `F10` binding too — MEASURED, receipts\receipt-23-trigger-defects.md.)
struct HotkeyBinding {
    uint32_t    vk = 0;        // VK_F10, VK_SNAPSHOT, ...
    uint32_t    mods = 0;      // MOD_ALT | MOD_CONTROL | MOD_SHIFT | MOD_WIN
    const char* name = "";     // "Alt+F10" — stable text for the log and the receipt
    double      window_s = 0;  // what a press of THIS key asks for; 0 => use the trigger default

    bool operator==(const HotkeyBinding& o) const { return vk == o.vk && mods == o.mods; }
};

// THE PRODUCT OF THE TRIGGER.  Deliberately a plain value: the listener thread and the
// capture thread exchange copies and never share a pointer into each other's memory.
struct CutRequest {
    uint64_t    t_cut_ns = 0;              // QPC at detection — the one argument issue_cut() takes
    uint64_t    request_seq = 0;          // 0 for the first press ever, +1 per press
    uint64_t    detected_latency_us = 0;  // measured, not estimated
    double      requested_window_s = 0;   // what the key asked for
    double      ring_span_s = -1;         // what the ring can give; -1 = not probed
    bool        shorter_than_requested = false;
    bool        from_registerhotkey = false;   // which of the two paths produced this
    bool        from_async_poll = false;
    HotkeyBinding binding{};
    std::string note;                     // empty, or the reason it had to say something
};

// Implemented by whoever owns the ring (Replay, or the test double).  One method on purpose:
// this lane must not couple itself to RingBuffer's internals, which another lane owns.
class RingSpanProbe {
public:
    virtual ~RingSpanProbe() {}
    // Seconds of encoded history actually held right now.  -1 => unknown (no probe installed).
    virtual double span_seconds() = 0;
};

// Result of arming ONE binding.  A failure is never silent and never aggregated away: the
// receipt quotes this table verbatim, per key.
struct BindingStatus {
    HotkeyBinding binding{};
    bool     registered = false;       // RegisterHotKey succeeded
    DWORD    register_error = 0;      // 0 iff registered; else the raw GetLastError()
    std::string register_error_text;   // "ERROR_HOTKEY_ALREADY_REGISTERED" / "hr_str"-ish
    bool     polled = false;           // the fallback is armed for it anyway
    bool     owned_by_other_process = false;  // ERROR_HOTKEY_ALREADY_REGISTERED
};

// Everything the receipt needs to quote.  All counters are facts, per hard rule 6.
struct TriggerStats {
    std::atomic<uint64_t> requests{0};
    std::atomic<uint64_t> from_registerhotkey{0};
    std::atomic<uint64_t> from_async_poll{0};
    std::atomic<uint64_t> autorepeat_suppressed{0};  // WM_HOTKEY arriving while a press is latched
    std::atomic<uint64_t> polls{0};
    std::atomic<uint64_t> polls_skipped_sleep{0};   // a poll found work already done
    std::atomic<uint64_t> queue_refused{0};         // producer outran the consumer
    std::atomic<uint64_t> registrations_ok{0};
    std::atomic<uint64_t> registrations_failed{0};
    std::atomic<uint64_t> pump_messages{0};
};

// Injectable key-state source.  Present so the edge logic is PROVABLE (arm C) without
// synthesising a keystroke into whatever window the owner happens to have focused — a test
// that types into the owner's foreground app is a test that damages the owner's work.
// Null => the real GetAsyncKeyState.
using KeystateFn = int (*)(int vk);

class Trigger {
public:
    Trigger();
    ~Trigger();

    // Arms BOTH paths for every binding.  Never returns false for "a key was taken" — that
    // is a per-binding status, not a failure; `armed()` is true when AT LEAST ONE path works
    // for at least one binding.  Returns false only when nothing can work at all (no window,
    // no thread), and *err then says why.
    bool arm(const std::vector<HotkeyBinding>& bindings, double default_window_s,
             std::string* err);

    void disarm();                        // unregisters, stops both threads, idempotent
    bool armed() const { return armed_; }

    // CONSUMER SIDE — the run loop calls this.  Blocks up to timeout_ms for a request.
    bool take(CutRequest* out, uint32_t timeout_ms = 0);
    bool peek_pending() const;

    // Replaced in the self-test; never in production.  Documented so nobody "optimises" it away.
    void set_keystate_fn(KeystateFn fn) { key_state_ = fn; }

    // THE POLL TICK, factored out of poll_thread_main so it can be driven synchronously by
    // the self-test.  Production calls it once per tick; the self-test calls it directly with
    // a synthetic key-state function.  Public ON PURPOSE: making it private would leave the
    // edge latch provable only by synthesising real keystrokes into whatever window the owner
    // happens to have focused, which damages his work.  Returns the number of requests it
    // emitted this tick.
    uint32_t poll_once(uint64_t tick0_ns, KeystateFn ksf);

    // SELF-TEST SEAM — sets up binding state WITHOUT touching the global hotkey table and
    // WITHOUT starting either thread, so the self-test can drive poll_once() deterministically.
    // Production never calls this; arm() is the production entry point.
    void prepare_for_test(const std::vector<HotkeyBinding>& bindings, double default_window_s);

    // The id RegisterHotKey was given for binding `index` — the wParam of its WM_HOTKEY.
    // Exposed so the self-test can post a REAL WM_HOTKEY instead of calling a private method.
    uint32_t hotkey_id_at(size_t index) const { return next_hotkey_id_ + (uint32_t)index; }

    // The probe is a BORROWED pointer — it must outlive the trigger or be cleared first.
    void set_ring_probe(RingSpanProbe* p);

    // --- observability -------------------------------------------------------------------
    const std::vector<BindingStatus>& status() const { return status_; }
    std::string arm_summary() const;      // one line: what armed, what was refused and why
    TriggerStats& stats() { return stats_; }
    const TriggerStats& stats() const { return stats_; }
    HWND message_window() const { return hwnd_; }
    bool pump_thread_live() const;
    bool poll_thread_live() const;
    static uint32_t queue_capacity();

    // This process's integrity level (TOKEN_MANDATORY_LABEL).  Quoted because it is the
    // documented determinant of whether a hotkey registered HERE is delivered to a window
    // running at a HIGHER level — i.e. to an admin-launched game.
    static uint32_t process_integrity_rid();
    static const char* integrity_name(uint32_t rid);

private:
    void pump_thread_main();
    void poll_thread_main();
    bool  create_message_window(std::string* err);
    bool  arm_all_bindings(std::string* err);   // runs ON the pump thread, after the window exists
    bool  wait_pump_ready(uint32_t timeout_ms);
    bool  arm_binding(HotkeyBinding b, uint32_t id, BindingStatus* out);
    void  emit(CutRequest&& r, bool via_rhk, bool via_poll);
    CutRequest build_request(const HotkeyBinding& b, uint64_t seq, bool via_rhk, bool via_poll,
                             uint64_t t_ns, std::string note);

    std::vector<HotkeyBinding> bindings_;
    std::vector<BindingStatus> status_;
    std::vector<uint8_t>       held_;   // the edge latch, one byte per binding
    double                     default_window_s_ = 30.0;

    // THE WINDOW BELONGS TO THE PUMP THREAD, and that is load-bearing, not tidiness.
    // PostMessage/RegisterHotKey route by the thread that OWNS the window: create the window
    // on the caller and pump on a worker, and every WM_HOTKEY is delivered into the CALLER's
    // queue — which, in this product, is the capture loop sitting in a condition-variable wait.
    // The hotkey then fires perfectly and is never seen.  MEASURED: that is exactly what arm B
    // caught the first time (0 requests in 800 ms of a real WM_HOTKEY).
    HWND        hwnd_ = nullptr;
    std::mutex        pump_mu_;
    std::condition_variable pump_cv_;
    bool               pump_ready_ = false;
    bool               pump_window_ok_ = false;
    std::string        pump_error_;
    DWORD       instance_ = 0;          // the class name we registered
    uint32_t    next_hotkey_id_ = 0xA17E;
    std::atomic<bool> armed_{false};
    std::atomic<bool> quit_{false};
    std::thread pump_thread_;
    std::thread poll_thread_;

    mutable std::mutex      q_mu_;
    std::condition_variable q_cv_;
    std::deque<CutRequest>  queue_;
    TriggerStats            stats_;

    KeystateFn      key_state_ = nullptr;
    RingSpanProbe*  probe_ = nullptr;
    uint64_t        seq_ = 0;
};

// The keys this lane ships as the DEFAULT ladder.  Tried in this order; the first one that
// registers wins, and every one of them is polled regardless, so a key already owned by
// another overlay is still reachable.
//
// BARE F12 IS LAST, and the reason is a reservation Microsoft documents by name — NOT a claim
// that RegisterHotKey(F12) fails, which the documentation does not make.  It is still bound and
// still polled; it is simply never promoted to the primary key.  The full argument, with the
// quoted sentence and the URL it came from, is in trigger.cpp at default_binding_ladder().
const std::vector<HotkeyBinding>& default_binding_ladder();

} // namespace aireplay