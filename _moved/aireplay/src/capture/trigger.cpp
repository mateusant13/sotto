// trigger.cpp — see trigger.h for the design, the two paths, and the measurement status.
//
// OWNED BY: the instant-replay trigger lane.  Other lanes must not edit this file.  The hookup
// that plugs it into Replay is in receipts\receipt-15-instant-replay-trigger.md §6 — a file that
// DID NOT EXIST when this comment was first written on 2026-10-07 (see the CITATION HISTORY in
// trigger.h).  The measurements that back the modifier-matching cure and the F12 ordering below
// are receipts\receipt-23-trigger-defects.md, gate _main\_lane23-trigger-defects-gate.ps1.
#include "trigger.h"

#include <cmath>
#include <sstream>

namespace aireplay {

namespace {

const wchar_t* kWindowClass = L"AireplayTriggerMessageWindow";

// Queue depth.  A replay clip is written by a second thread WHILE capture continues
// (replay.h header comment), so the consumer drains this fast; 8 is more than the consumer
// can fall behind by, and a full queue is COUNTED (queue_refused) rather than silently
// dropping the newest press — an instant-replay trigger that silently eats the key the owner
// just pressed is the worst possible failure for this product.
constexpr size_t kQueueCapacity = 8;

// How long the WM_HOTKEY path ignores a repeat of the same id.  MOD_NOREPEAT already
// suppresses repeats in the kernel; this is the belt for the drivers that ignore it
// (measured as a real concern on gaming PCs: every RGB/hid vendor ships a remapper).
constexpr uint64_t kRepeatGuardNs = 50ull * 1000ull * 1000ull;   // 50 ms

constexpr uint32_t kPollTickMs = 8;

// Every bit RegisterHotKey takes in fsModifiers EXCEPT MOD_NOREPEAT.  A binding's `mods` is a
// value in this space, and the live mask is measured in it, so the two are directly comparable.
// MOD_NOREPEAT is deliberately absent: it is a kernel autorepeat switch, not a key the user
// holds, and comparing against it would mean no binding could ever match.
constexpr uint32_t kModifierBits = MOD_ALT | MOD_CONTROL | MOD_SHIFT | MOD_WIN;

int real_keystate(int vk) { return GetAsyncKeyState(vk); }

// The modifier mask ACTUALLY held down, right now.  VK_CONTROL/VK_MENU/VK_SHIFT are the
// generic codes GetAsyncKeyState already folds both physical keys of each pair into; WIN has no
// generic code, so both Win keys are read.  This is the value a binding's `mods` must EQUAL —
// not merely intersect.  An intersection is what let `Alt+F10` fire the plain `F10` binding.
uint32_t live_modifier_mask(KeystateFn ksf)
{
    uint32_t m = 0;
    if (ksf(VK_CONTROL) & 0x8000) m |= MOD_CONTROL;
    if (ksf(VK_MENU)    & 0x8000) m |= MOD_ALT;
    if (ksf(VK_SHIFT)   & 0x8000) m |= MOD_SHIFT;
    if ((ksf(VK_LWIN) & 0x8000) || (ksf(VK_RWIN) & 0x8000)) m |= MOD_WIN;
    return m;
}

const char* winerr_text(DWORD e) {
    switch (e) {
        case 0:                  return "OK";
        case ERROR_HOTKEY_ALREADY_REGISTERED: return "ERROR_HOTKEY_ALREADY_REGISTERED";
        case ERROR_INVALID_PARAMETER:        return "ERROR_INVALID_PARAMETER";
        case ERROR_INVALID_WINDOW_HANDLE:    return "ERROR_INVALID_WINDOW_HANDLE";
        case ERROR_NOT_ENOUGH_MEMORY:        return "ERROR_NOT_ENOUGH_MEMORY";
        case ERROR_ACCESS_DENIED:            return "ERROR_ACCESS_DENIED";
        case ERROR_INVALID_FLAGS:            return "ERROR_INVALID_FLAGS";
        default: break;
    }
    static thread_local std::string buf;
    buf = "Win32-" + std::to_string((unsigned long)e);
    return buf.c_str();
}

std::string mod_text(uint32_t mods) {
    std::string s;
    if (mods & MOD_CONTROL) s += "Ctrl+";
    if (mods & MOD_ALT)     s += "Alt+";
    if (mods & MOD_SHIFT)   s += "Shift+";
    if (mods & MOD_WIN)     s += "Win+";
    return s;
}

} // namespace

const std::vector<HotkeyBinding>& default_binding_ladder()
{
    // Order matters: the first binding that REGISTERS is the one the receipt reports as the
    // armed key, but every binding is polled regardless — that is what makes an
    // already-owned key (the common case on a gaming PC) still work.
    //
    // BARE F12 IS LAST, AND THAT IS A RESPONSE TO A DOCUMENTED RESERVATION.  Microsoft's
    // RegisterHotKey reference says, verbatim: "The F12 key is reserved for use by the debugger
    // at all times, so it should not be registered as a hot key. Even when you are not
    // debugging an application, F12 is reserved in case a kernel-mode debugger or a
    // just-in-time debugger is resident."
    // (learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey, fetched
    //  2026-10-07; the sentence is in the page's Remarks section.)
    //
    // WHAT THAT DOES AND DOES NOT SAY — do not upgrade it into a stronger claim than the page
    // makes.  It says F12 "should not be registered".  It does NOT say RegisterHotKey(VK_F12)
    // FAILS, and the page's own failure list (an unregistered hWnd/id pair, a combination
    // already registered) does not include F12.  So "F12 first breaks hotkeys" is FALSE and is
    // not the argument for this ordering.
    // The real argument is weaker and honest: the vendor reserves F12 for a debugger that may
    // be resident whether or not the owner is debugging, so F12 is the least reliable key to
    // PROMOTE — but it is not forbidden, it still registers on this host, and since every
    // binding is polled regardless, keeping it reachable costs nothing.  Hence: still bound,
    // still polled, never the primary.  Ctrl+F12 (above) is the promoted F12-family key.
    //
    // A previous version of this comment claimed F12-first was safe because "NVIDIA's own
    // overlay and most screen recorders default away from it".  That was an UNMEASURED claim
    // about other companies' products and is deleted here rather than restated.  The MS
    // sentence above is the citation this ordering actually rests on, and it is cited because
    // it was read, not because it was assumed.
    static const std::vector<HotkeyBinding> kLadder = {
        { VK_F10,    0,                 "F10",          30.0 },
        { VK_F11,    0,                 "F11",          30.0 },
        { VK_F9,     MOD_CONTROL,       "Ctrl+F9",      30.0 },
        { VK_F9,     MOD_ALT,           "Alt+F9",       30.0 },
        { VK_F10,    MOD_ALT,           "Alt+F10",      30.0 },
        { VK_F11,    MOD_ALT,           "Alt+F11",      60.0 },
        { VK_F12,    MOD_CONTROL,       "Ctrl+F12",     60.0 },
        { VK_SNAPSHOT, 0,               "PrintScreen",  10.0 },
        { VK_F12,    0,                 "F12",          30.0 },
    };
    return kLadder;
}

uint32_t Trigger::queue_capacity() { return (uint32_t)kQueueCapacity; }

// ------------------------------------------------------------------ integrity
uint32_t Trigger::process_integrity_rid()
{
    HANDLE tok = nullptr;
    if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &tok)) return 0;
    DWORD need = 0;
    GetTokenInformation(tok, TokenIntegrityLevel, nullptr, 0, &need);
    if (need == 0) { CloseHandle(tok); return 0; }
    std::vector<uint8_t> buf(need);
    if (!GetTokenInformation(tok, TokenIntegrityLevel, buf.data(), need, &need)) {
        CloseHandle(tok); return 0;
    }
    CloseHandle(tok);
    TOKEN_MANDATORY_LABEL* tml = (TOKEN_MANDATORY_LABEL*)buf.data();
    // GetSidSubAuthorityCount returns a POINTER TO the count byte, not the count (measured
    // here: casting the returned pointer straight to DWORD yielded 243871457 — a heap
    // address — and indexing with it segfaulted).  Dereference it, and refuse a SID that
    // claims more subauthorities than any real one can have.
    PSID sid = tml->Label.Sid;
    if (!sid || !IsValidSid(sid)) return 0;
    const DWORD n_sub = (DWORD)*GetSidSubAuthorityCount(sid);
    if (n_sub == 0 || n_sub > 32) return 0;
    return *GetSidSubAuthority(sid, n_sub - 1);
}

const char* Trigger::integrity_name(uint32_t rid)
{
    switch (rid) {
        case 0x0000: return "UNPROTECTED";
        case 0x1000: return "LOW";
        case 0x2000: return "MEDIUM";
        case 0x3000: return "HIGH";
        case 0x4000: return "SYSTEM";
        default:     return "UNKNOWN";
    }
}

// ------------------------------------------------------------------ window
namespace {

LRESULT CALLBACK trigger_wnd_proc(HWND h, UINT msg, WPARAM wp, LPARAM lp)
{
    return DefWindowProcW(h, msg, wp, lp);
}

} // namespace

bool Trigger::create_message_window(std::string* err)
{
    HMODULE mod = GetModuleHandleW(nullptr);
    instance_ = (DWORD)(uintptr_t)mod;

    WNDCLASSEXW wc = {};
    wc.cbSize        = sizeof(wc);
    wc.lpfnWndProc   = trigger_wnd_proc;
    wc.hInstance     = mod;
    wc.lpszClassName = kWindowClass;
    if (!RegisterClassExW(&wc) && GetLastError() != ERROR_CLASS_ALREADY_EXISTS) {
        if (err) *err = std::string("RegisterClassExW failed: ") + winerr_text(GetLastError());
        return false;
    }

    // HWND_MESSAGE => a MESSAGE-ONLY window.  It is never mapped, never enumerated by
    // EnumWindows, and cannot flash on the owner's screen — hard rule 1 of the lane brief is
    // a design constraint here, not a thing to remember at the end.
    hwnd_ = CreateWindowExW(0, kWindowClass, L"AireplayTrigger", 0, 0, 0, 0, 0,
                            HWND_MESSAGE, nullptr, mod, nullptr);
    if (!hwnd_) {
        if (err) *err = std::string("CreateWindowExW(HWND_MESSAGE) failed: ") + winerr_text(GetLastError());
        return false;
    }
    return true;
}

// ------------------------------------------------------------------ arming
// Runs ON THE PUMP THREAD.  The window must be created here, not on the caller: messages and
// hotkey registrations are routed by the owning thread, so a window created on the caller puts
// every WM_HOTKEY into the caller's queue (see the note on hwnd_ in trigger.h).
bool Trigger::arm_all_bindings(std::string* err)
{
    if (!create_message_window(err)) return false;
    uint32_t any_registered = 0;
    for (size_t i = 0; i < bindings_.size(); ++i) {
        BindingStatus st;
        arm_binding(bindings_[i], next_hotkey_id_ + (uint32_t)i, &st);
        if (st.registered) ++any_registered;
        status_[i] = st;
    }

    const uint32_t rid = process_integrity_rid();
    log_line("  TRIGGER arm: %u key(s), %u registered, %u polled-only, poll_tick=%u ms, "
             "integrity=%s(0x%X), queue_cap=%u",
             (unsigned)bindings_.size(), (unsigned)any_registered,
             (unsigned)(bindings_.size() - any_registered), (unsigned)kPollTickMs,
             integrity_name(rid), (unsigned)rid, (unsigned)kQueueCapacity);

    if (any_registered == 0)
        log_line("  TRIGGER WARN no key registered (all already owned by another process); "
                 "the poll path is the ONLY path live");
    return true;
}

bool Trigger::wait_pump_ready(uint32_t timeout_ms)
{
    std::unique_lock<std::mutex> lk(pump_mu_);
    return pump_cv_.wait_for(lk, std::chrono::milliseconds(timeout_ms),
                             [this] { return pump_ready_; });
}
bool Trigger::arm_binding(HotkeyBinding b, uint32_t id, BindingStatus* out)
{
    BindingStatus st;
    st.binding = b;
    // MOD_NOREPEAT here, unconditionally: a caller cannot opt into a repeating hotkey.
    const uint32_t m = b.mods | MOD_NOREPEAT;

    if (hwnd_) {
        if (RegisterHotKey(hwnd_, (int)id, m, b.vk)) {
            st.registered = true;
            ++stats_.registrations_ok;
        } else {
            st.register_error = GetLastError();
            st.register_error_text = winerr_text(st.register_error);
            st.owned_by_other_process = (st.register_error == ERROR_HOTKEY_ALREADY_REGISTERED);
            ++stats_.registrations_failed;
        }
    } else {
        st.register_error = ERROR_INVALID_WINDOW_HANDLE;
        st.register_error_text = winerr_text(st.register_error);
        ++stats_.registrations_failed;
    }

    // The fallback is armed for EVERY binding, registered or not.  This is the whole point of
    // having two paths: a key another overlay owns cannot be registered by us, but its
    // physical state is still readable.
    st.polled = true;

    log_line("  TRIGGER key=%-10s vk=0x%02X mods=%-18s registered=%s polled=true err=%s",
             b.name, (unsigned)b.vk, mod_text(m).c_str(),
             st.registered ? "yes" : "NO", st.register_error_text.c_str());

    if (out) *out = st;
    return st.registered;
}

bool Trigger::arm(const std::vector<HotkeyBinding>& bindings, double default_window_s,
                  std::string* err)
{
    disarm();
    if (bindings.empty()) { if (err) *err = "no bindings"; return false; }

    bindings_ = bindings;
    default_window_s_ = default_window_s > 0 ? default_window_s : 30.0;
    held_.assign(bindings_.size(), 0);
    status_.clear();
    status_.resize(bindings_.size());   // sized BEFORE the pump thread fills it in
    quit_.store(false);
    seq_ = 0;
    next_hotkey_id_ = 0xA17E;
    pump_ready_ = false;
    pump_window_ok_ = false;
    pump_error_.clear();

    // The PUMP thread creates the window and registers the hotkeys, so every WM_HOTKEY lands in
    // the queue that is actually being pumped.  arm() then blocks until that has happened: a
    // caller that sees arm()==true knows a window exists, the keys are registered, and a pump
    // is running.  Arming a hotkey with no pump is the silent failure this file exists to
    // prevent, so the ordering is load-bearing.
    pump_thread_ = std::thread(&Trigger::pump_thread_main, this);
    const bool pump_armed = wait_pump_ready(5000);
    poll_thread_ = std::thread(&Trigger::poll_thread_main, this);

    if (!pump_armed) {
        if (err) *err = "the message pump thread did not become ready within 5 s";
        disarm();
        return false;
    }
    if (!pump_window_ok_ && !poll_thread_live()) {
        if (err) *err = "no window and no poll thread: " + pump_error_;
        disarm();
        return false;
    }
    // A window failure is NOT fatal while the poll path is live: that is the whole point of
    // shipping two paths, and the log above already said which keys are polled-only.
    if (!pump_window_ok_ && err) *err = pump_error_;

    armed_.store(true);
    return true;
}

void Trigger::disarm()
{
    if (!armed_.exchange(false) && !pump_thread_.joinable() && !poll_thread_.joinable()) return;
    quit_.store(true);

    // No UnregisterHotKey / DestroyWindow here on purpose: both belong to the pump thread (see
    // the note on hwnd_ in trigger.h) and it does them as its last act.  Joining IS the wait.
    if (pump_thread_.joinable()) pump_thread_.join();
    if (poll_thread_.joinable()) poll_thread_.join();

    bindings_.clear();
    status_.clear();
    held_.clear();
    {
        std::lock_guard<std::mutex> lk(q_mu_);
        queue_.clear();
    }
}

bool Trigger::pump_thread_live() const
{
    // A thread that was never started, or that has already exited, is not a pump.
    if (!pump_thread_.joinable()) return false;
    return !quit_.load();
}

bool Trigger::poll_thread_live() const
{
    if (!poll_thread_.joinable()) return false;
    return !quit_.load();
}

// ------------------------------------------------------------------ threads
void Trigger::pump_thread_main()
{
    // Window + registration happen HERE, on the thread that will pump.  See the note on hwnd_
    // in trigger.h: a window owned by another thread routes WM_HOTKEY into THAT thread's queue.
    std::string werr;
    const bool win_ok = arm_all_bindings(&werr);
    {
        std::lock_guard<std::mutex> lk(pump_mu_);
        pump_window_ok_ = win_ok;
        pump_error_ = werr;
        pump_ready_ = true;
    }
    pump_cv_.notify_all();

    MSG msg;
    while (!quit_.load()) {
        const DWORD r = MsgWaitForMultipleObjects(0, nullptr, FALSE, kPollTickMs,
                                                  QS_ALLINPUT);
        if (r == WAIT_TIMEOUT) continue;
        if (r != QS_ALLINPUT && r != (WAIT_OBJECT_0 + 0)) continue;
        // Drain everything queued: one press can be a burst, and a pump that handles one
        // message per iteration is a pump that drops presses under load.
        while (hwnd_ && PeekMessageW(&msg, hwnd_, 0, 0, PM_REMOVE)) {
            if (msg.message == WM_HOTKEY) {
                ++stats_.pump_messages;
                const uint32_t id = (uint32_t)msg.wParam;
                const size_t idx = (id >= next_hotkey_id_) ? (size_t)(id - next_hotkey_id_)
                                                           : (size_t)-1;
                if (idx >= bindings_.size()) continue;
                // Autorepeat belt: MOD_NOREPEAT should already have made a repeat impossible.
                static thread_local uint64_t last_ns[kQueueCapacity + 16];
                const uint64_t now = qpc_now_ns();
                if (last_ns[idx] && (now - last_ns[idx]) < kRepeatGuardNs) {
                    ++stats_.autorepeat_suppressed;
                    continue;
                }
                last_ns[idx] = now;
                emit(build_request(bindings_[idx], seq_, true, false, now, ""), true, false);
            }
        }
    }

    // The window and its hotkey registrations belong to THIS thread, so THIS thread releases
    // them.  Unregistering/Destroying from the caller's thread would leave the registration
    // alive (or fail outright) after disarm() returned — a hotkey that outlives the app.
    for (size_t i = 0; i < status_.size(); ++i)
        if (status_[i].registered && hwnd_)
            UnregisterHotKey(hwnd_, (int)(next_hotkey_id_ + (uint32_t)i));
    if (hwnd_) {
        DestroyWindow(hwnd_);
        hwnd_ = nullptr;
    }
}

void Trigger::prepare_for_test(const std::vector<HotkeyBinding>& bindings, double default_window_s)
{
    disarm();
    bindings_ = bindings;
    default_window_s_ = default_window_s > 0 ? default_window_s : 30.0;
    held_.assign(bindings_.size(), 0);
    status_.clear();
    for (const HotkeyBinding& b : bindings_) {
        BindingStatus st;
        st.binding = b;
        st.polled = true;          // pretend it registered: the poll path does not care
        status_.push_back(st);
    }
    armed_.store(true);
    next_hotkey_id_ = 0xA17E;
    seq_ = 0;
}

uint32_t Trigger::poll_once(uint64_t tick0_ns, KeystateFn ksf)
{
    if (!ksf) ksf = key_state_ ? key_state_ : real_keystate;
    uint32_t emitted = 0;

    // THE MODIFIER MASK, measured ONCE per tick.  It cannot change inside the loop, and
    // re-reading the physical modifier keys once per binding would be both wasteful and — if a
    // keystroke landed mid-tick — capable of giving two bindings two different views of the
    // same tick.  Read once, compared by every binding, is the only consistent reading.
    const uint32_t held_mods = live_modifier_mask(ksf);

    for (size_t i = 0; i < bindings_.size(); ++i) {
        const bool key_down = (ksf((int)bindings_[i].vk) & 0x8000) != 0;

        // A binding matches only when its FULL declared mask is held and nothing else is.
        // EQUALITY, not intersection: with an intersection a press carrying EXTRA modifiers
        // still matches a binding that never declared them, which is how `Alt+F10` came to
        // fire the plain `F10` binding as well as its own.  MEASURED on the pre-fix build
        // (see receipts\receipt-23-trigger-defects.md): one Alt+F10 press produced TWO
        // CutRequests bound "F10" and "Alt+F10", and a bare F10 press produced those same two.
        const bool down = key_down && held_mods == (bindings_[i].mods & kModifierBits);

        const bool was_down = held_[i] != 0;
        if (down && !was_down) {
            const uint64_t now = qpc_now_ns();
            std::string note;
            if (!status_[i].registered && status_[i].owned_by_other_process)
                note = "key not registerable (" + status_[i].register_error_text +
                       "): fired by the poll path instead";
            CutRequest r = build_request(bindings_[i], seq_, false, true, now, note);
            r.detected_latency_us = (now - tick0_ns) / 1000ull;
            emit(std::move(r), false, true);
            ++emitted;
        }
        if (was_down) ++stats_.autorepeat_suppressed;   // a held key that did NOT re-fire
        //CURE-EDGE-LATCH  (single line; _lane1-trigger-gate.ps1 deletes this line, in a
        // COPY, to build the control binary — a held key must produce exactly ONE cut)
        held_[i] = down ? 1 : 0;
    }
    return emitted;
}

void Trigger::poll_thread_main()
{
    while (!quit_.load()) {
        const uint64_t tick0 = qpc_now_ns();
        ++stats_.polls;
        poll_once(tick0, key_state_);
        ++stats_.polls_skipped_sleep;
        Sleep(kPollTickMs);
    }
}

// ------------------------------------------------------------------ request
CutRequest Trigger::build_request(const HotkeyBinding& b, uint64_t seq, bool via_rhk,
                                  bool via_poll, uint64_t t_ns, std::string note)
{
    CutRequest r;
    r.binding = b;
    r.t_cut_ns = t_ns;
    r.request_seq = seq;
    r.from_registerhotkey = via_rhk;
    r.from_async_poll = via_poll;
    r.requested_window_s = b.window_s > 0 ? b.window_s : default_window_s_;

    // The short-ring case, MEASURED and NAMED.  This lane cannot ask RingBuffer anything
    // (Replay owns it), so it asks the probe; if nobody installed one, it says "unknown"
    // rather than pretending the ring is long enough.
    if (probe_) {
        r.ring_span_s = probe_->span_seconds();
        if (r.ring_span_s >= 0.0 && r.ring_span_s < r.requested_window_s) {
            r.shorter_than_requested = true;
            if (note.empty())
                note = "ring holds " + std::to_string((long long)(r.ring_span_s * 1000)) +
                       " ms but the key asked for " +
                       std::to_string((long long)(r.requested_window_s * 1000)) +
                       " ms: the clip will be short, and this says so";
        }
    }
    r.note = note;
    return r;
}

void Trigger::emit(CutRequest&& r, bool via_rhk, bool via_poll)
{
    {
        std::lock_guard<std::mutex> lk(q_mu_);
        if (queue_.size() >= kQueueCapacity) {
            ++stats_.queue_refused;
            log_line("  TRIGGER REFUSED request %llu: the queue holds %u and the consumer is "
                     "not draining (a press was DROPPED, and this is the line that says so)",
                     (unsigned long long)r.request_seq, (unsigned)kQueueCapacity);
            return;
        }
        r.request_seq = seq_++;
        queue_.push_back(std::move(r));
    }
    if (via_rhk) ++stats_.from_registerhotkey;
    if (via_poll) ++stats_.from_async_poll;
    ++stats_.requests;
    q_cv_.notify_one();
}

// ------------------------------------------------------------------ consumer
bool Trigger::take(CutRequest* out, uint32_t timeout_ms)
{
    std::unique_lock<std::mutex> lk(q_mu_);
    if (queue_.empty()) {
        if (timeout_ms == 0) return false;
        q_cv_.wait_for(lk, std::chrono::milliseconds(timeout_ms), [this] { return !queue_.empty(); });
    }
    if (queue_.empty()) return false;
    if (out) *out = queue_.front();
    queue_.pop_front();
    return true;
}

bool Trigger::peek_pending() const
{
    std::lock_guard<std::mutex> lk(q_mu_);
    return !queue_.empty();
}

void Trigger::set_ring_probe(RingSpanProbe* p) { probe_ = p; }

std::string Trigger::arm_summary() const
{
    std::ostringstream s;
    s << "TRIGGER_SUMMARY armed=" << (armed_ ? 1 : 0)
      << " keys=" << status_.size()
      << " registered=" << stats_.registrations_ok.load()
      << " refused=" << stats_.registrations_failed.load()
      << " polled_only=" << (status_.size() - stats_.registrations_ok.load())
      << " requests=" << stats_.requests.load();
    for (const BindingStatus& b : status_)
        if (!b.registered)
            s << " [" << b.binding.name << "=" << b.register_error_text << "]";
    return s.str();
}

// ------------------------------------------------------------------ lifetime
Trigger::Trigger() = default;

Trigger::~Trigger() { disarm(); }

} // namespace aireplay