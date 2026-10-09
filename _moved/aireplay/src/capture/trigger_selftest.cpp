// trigger_selftest.cpp — the five named arms.  See trigger_selftest.h for what each proves.
#include "trigger_selftest.h"

#include <algorithm>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <sstream>

namespace aireplay {

namespace {

// ------------------------------------------------------------------ test doubles
bool g_down[256] = { false };

int fake_keystate(int vk)
{
    if (vk < 0 || vk >= 256) return 0;
    return g_down[vk] ? (int)0x8001 : 0;   // high bit set == pressed, exactly like the real API
}

class FakeRingProbe : public RingSpanProbe {
public:
    double s = 0.0;
    double span_seconds() override { return s; }
};

// Drain everything the trigger currently holds.  Non-blocking on purpose: the arms assert on
// COUNTS, so a test that waits could hide a duplicate behind a slow consumer.
size_t drain(Trigger& t, std::vector<CutRequest>* into)
{
    size_t n = 0;
    CutRequest r;
    while (t.take(&r, 0)) { if (into) into->push_back(r); ++n; }
    return n;
}

void reset_keys()
{
    for (int i = 0; i < 256; ++i) g_down[i] = false;
}

// Run one scripted poll tick and report how many requests it produced.
uint32_t tick(Trigger& t)
{
    return t.poll_once(qpc_now_ns(), fake_keystate);
}

// ------------------------------------------------------------------ arm C (also the control probe)
struct ArmCResult { uint32_t cuts = 0; uint64_t suppressed = 0; };

ArmCResult run_arm_c_body()
{
    // One binding.  VK_F24 is used because it is a real virtual key that essentially nothing
    // registers, and this arm must not steal a key the owner is using.
    const HotkeyBinding b = { VK_F24, 0, "F24", 30.0 };
    Trigger t;
    t.prepare_for_test({ b }, 30.0);
    reset_keys();

    // down, down, down | up, up | down, down | up   => two distinct presses, two holds.
    const bool trace[8] = { true, true, true, false, false, true, true, false };
    ArmCResult r;
    for (int i = 0; i < 8; ++i) {
        g_down[VK_F24] = trace[i];
        r.cuts += tick(t);
    }
    r.suppressed = t.stats().autorepeat_suppressed.load();
    reset_keys();
    return r;
}

} // namespace

int run_arm_c_probe(const std::string& out_path)
{
    const ArmCResult r = run_arm_c_body();
    std::ofstream f(out_path, std::ios::binary | std::ios::trunc);
    if (!f) { printf("ARMC ERROR cannot write %s\n", out_path.c_str()); return 2; }
    f << "ARMC cuts=" << r.cuts << " suppressed=" << r.suppressed << "\n";
    f.close();
    printf("ARMC cuts=%u suppressed=%llu\n", r.cuts, (unsigned long long)r.suppressed);
    return 0;
}

// ------------------------------------------------------------------ arms
namespace {

// ARM A — real RegisterHotKey against the shipped ladder, on the owner's machine.
ArmResult arm_a_registration_ladder()
{
    std::ostringstream d;
    std::string err;
    Trigger t;
    if (!t.arm(default_binding_ladder(), 30.0, &err)) {
        return { "A", false, "arm() refused: " + err };
    }

    const auto& st = t.status();
    std::string refusedText;
    uint32_t reg = 0, refused = 0, no_error_text = 0;
    for (const BindingStatus& s : st) {
        if (s.registered) ++reg;
        else {
            ++refused;
            if (s.register_error_text.empty()) ++no_error_text;
            refusedText += std::string(s.binding.name) + "=" + s.register_error_text + "; ";
        }
    }
    if (no_error_text) {
        d << "every refusal must carry a Win32 error; " << no_error_text << " did not";
        t.disarm();
        return { "A", false, d.str() };
    }
    if (!t.pump_thread_live() && !t.poll_thread_live()) {
        d << "armed but NEITHER the pump nor the poll thread is live - the silent-failure "
             "this file exists to prevent";
        t.disarm();
        return { "A", false, d.str() };
    }

    const uint32_t rid = Trigger::process_integrity_rid();
    d << "keys=" << st.size() << " registered=" << reg << " polled_only=" << refused
      << " pump_live=" << (t.pump_thread_live() ? 1 : 0)
      << " poll_live=" << (t.poll_thread_live() ? 1 : 0)
      << " integrity=" << Trigger::integrity_name(rid)
      << " | refused: " << (refused ? refusedText : std::string("none"));
    t.disarm();   // RELEASE the owner's keys immediately — this arm must not hold F10/F12.
    return { "A", true, d.str() };
}

// ARM B — a REAL WM_HOTKEY through the REAL pump thread.
ArmResult arm_b_dispatch()
{
    const HotkeyBinding b = { VK_F24, 0, "F24", 30.0 };
    std::ostringstream d;
    std::string err;
    Trigger t;
    if (!t.arm({ b }, 30.0, &err)) return { "B", false, "arm() refused: " + err };

    const bool registered = t.status()[0].registered;
    d << "F24 registered=" << (registered ? 1 : 0);

    // Post twice, ~5 ms apart: MOD_NOREPEAT should make the second one unnecessary, and the
    // in-code repeat guard catches a driver that ignores MOD_NOREPEAT.
    PostMessageW(t.message_window(), WM_HOTKEY, (WPARAM)t.hotkey_id_at(0), 0);
    micro_wait_ms(5);
    PostMessageW(t.message_window(), WM_HOTKEY, (WPARAM)t.hotkey_id_at(0), 0);

    CutRequest r;
    bool got = t.take(&r, 800);
    if (!got) { d << " | NO request within 800 ms of a real WM_HOTKEY"; t.disarm(); return { "B", false, d.str() }; }

    d << " | first press -> seq=" << r.request_seq << " via_rhk=" << (r.from_registerhotkey ? 1 : 0)
      << " via_poll=" << (r.from_async_poll ? 1 : 0)
      << " window=" << (long long)(r.requested_window_s * 1000) << "ms"
      << " t_cut_ns>0=" << (r.t_cut_ns > 0 ? 1 : 0)
      << " pump_messages=" << t.stats().pump_messages.load();

    if (!r.from_registerhotkey) { d << " | the request did NOT come from the RegisterHotKey path"; t.disarm(); return { "B", false, d.str() }; }
    if (r.t_cut_ns == 0)          { d << " | t_cut_ns is zero; issue_cut() would cut at t=0"; t.disarm(); return { "B", false, d.str() }; }

    micro_wait_ms(120);   // let the pump drain any second message
    const size_t extra = drain(t, nullptr);
    const uint64_t supp = t.stats().autorepeat_suppressed.load();
    d << " | extra_requests=" << extra << " autorepeat_suppressed=" << supp;
    t.disarm();

    if (extra != 0) { d << " | ONE press produced " << (extra + 1) << " requests"; return { "B", false, d.str() }; }
    if (supp == 0)  { d << " | the immediate repeat was NOT suppressed"; return { "B", false, d.str() }; }
    return { "B", true, d.str() };
}

// ARM C — the edge latch, over a scripted key trace.
ArmResult arm_c_edge()
{
    const ArmCResult r = run_arm_c_body();
    std::ostringstream d;
    // The trace is  down,down,down,up,up,down,down,up  (indices 0..7).  Exactly two RISING edges
    // exist, at i=0 and i=5, so cuts must be 2.  `suppressed` counts every tick that found the
    // key ALREADY down and therefore did not re-fire: i=1,2,3 and i=6,7 = 5 ticks.  (An earlier
    // draft of this arm asserted 4 and was wrong; the trace, not the code, was re-derived.)
    d << "8 ticks over down,down,down,up,up,down,down,up -> cuts=" << r.cuts
      << " (want 2) suppressed=" << r.suppressed << " (want 5)";
    if (r.cuts != 2) {
        d << " | FAIL: a held key must produce ONE cut, not " << r.cuts;
        return { "C", false, d.str() };
    }
    if (r.suppressed != 5) {
        d << " | FAIL: the hold counter disagrees with the trace";
        return { "C", false, d.str() };
    }
    return { "C", true, d.str() };
}

// ARM D — THE CONTROL.  The mutant binary must FAIL arm C, or arm C is asserting nothing.
int run_child(const std::string& exe, const std::string& args, DWORD* rc_out, DWORD timeout_ms)
{
    std::wstring cmd = L"\"" + std::wstring(exe.begin(), exe.end()) + L"\" " +
                       std::wstring(args.begin(), args.end());
    std::vector<wchar_t> buf(cmd.begin(), cmd.end());
    buf.push_back('\0');
    STARTUPINFOW si = {};
    si.cb = sizeof(si);
    PROCESS_INFORMATION pi = {};
    // CREATE_NO_WINDOW: hard rule 1 — this child must never flash a console on the owner's
    // screen.  The selftest itself is a console app the gate redirects, which inherits.
    if (!CreateProcessW(nullptr, buf.data(), nullptr, nullptr, FALSE,
                        CREATE_NO_WINDOW, nullptr, nullptr, &si, &pi))
        return 0;
    WaitForSingleObject(pi.hProcess, timeout_ms);
    DWORD code = 0;
    GetExitCodeProcess(pi.hProcess, &code);
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    if (rc_out) *rc_out = code;
    return 1;
}

ArmResult arm_d_control(const std::string& mutant_exe, const std::string& work_dir)
{
    std::ostringstream d;
    if (mutant_exe.empty())
        return { "D", false, "no mutant binary given: the control did not run, so arm C is "
                              "unproven and this gate must not pass" };

    const std::string probe = work_dir + "\\lane1-trigger-armc-mutant.txt";
    DeleteFileA(probe.c_str());

    DWORD rc = 0xFFFFFFFF;
    if (!run_child(mutant_exe, "--arm-c-only --out \"" + probe + "\"", &rc, 30000))
        return { "D", false, "could not launch the mutant: " + mutant_exe };

    std::ifstream f(probe, std::ios::binary);
    std::string line;
    if (f) std::getline(f, line);
    unsigned cuts = 0, supp = 0;
    if (line.find("ARMC") == std::string::npos ||
        sscanf(line.c_str(), "ARMC cuts=%u suppressed=%u", &cuts, &supp) != 2)
        return { "D", false, "the mutant wrote no ARMC line (got \"" + line + "\")" };

    d << "mutant=" << mutant_exe << " rc=" << rc
      << " | mutant cuts=" << cuts << " suppressed=" << supp
      << " (the FIXED build must say cuts=2 suppressed=5; anything else means the cure is "
         "really gone)";

    if (cuts == 2)
        return { "D", false, d.str() + " | FAIL: the mutant behaves exactly like the fixed "
                                        "build, so arm C cannot fail and proves nothing" };
    return { "D", true, d.str() };
}

// ARM E — the ring holds less than the key asked for.
ArmResult arm_e_short_ring()
{
    std::string d;
    const HotkeyBinding b = { VK_F24, 0, "F24", 30.0 };
    FakeRingProbe probe;

    struct Case { double span; bool want_short; const char* label; };
    const Case cases[3] = {
        {  2.0, true,  "ring 2s vs 30s asked" },
        { 45.0, false, "ring 45s vs 30s asked" },
        {  0.0, true,  "ring empty vs 30s asked" },
    };

    for (const Case& c : cases) {
        Trigger t;
        t.prepare_for_test({ b }, 30.0);
        probe.s = c.span;
        t.set_ring_probe(&probe);
        reset_keys();
        g_down[VK_F24] = true;
        tick(t);
        g_down[VK_F24] = false;

        CutRequest r;
        if (!t.take(&r, 50)) {
            reset_keys();
            return { "E", false, d + c.label + ": no request" };
        }
        d += (d.empty() ? "" : " | ") + std::string(c.label) + " -> shorter=" +
             (r.shorter_than_requested ? "1" : "0") +
             " ring_span=" + std::to_string((long long)(r.ring_span_s * 1000)) + "ms" +
             " asked=" + std::to_string((long long)(r.requested_window_s * 1000)) + "ms";
        if (r.shorter_than_requested != c.want_short) {
            reset_keys();
            return { "E", false, d + " | FAIL: wanted shorter=" +
                     std::to_string(c.want_short ? 1 : 0) };
        }
        if (c.want_short && r.note.empty()) {
            reset_keys();
            return { "E", false, d + " | FAIL: a short clip with NO note is the silent "
                                      "truncation this arm exists to forbid" };
        }
    }

    // No probe at all => "unknown", NOT "long enough".
    {
        Trigger t;
        t.prepare_for_test({ b }, 30.0);
        reset_keys();
        g_down[VK_F24] = true;
        tick(t);
        g_down[VK_F24] = false;
        CutRequest r;
        if (!t.take(&r, 50)) { reset_keys(); return { "E", false, "no request (unprobed case)" }; }
        d += " | no probe -> ring_span=" + std::to_string((long long)r.ring_span_s) +
             " shorter=" + (r.shorter_than_requested ? "1" : "0");
        if (r.ring_span_s != -1.0 || r.shorter_than_requested) {
            reset_keys();
            return { "E", false, d + " | FAIL: with no probe the trigger must report "
                                     "unknown, not a fabricated span" };
        }
    }
    reset_keys();
    return { "E", true, d };
}

} // namespace

int run_trigger_selftest(const std::string& mutant_exe, const std::string& work_dir)
{
    std::vector<ArmResult> arms;
    arms.push_back(arm_a_registration_ladder());
    arms.push_back(arm_b_dispatch());
    arms.push_back(arm_c_edge());
    arms.push_back(arm_d_control(mutant_exe, work_dir));
    arms.push_back(arm_e_short_ring());

    log_line("  TRIGGER SELFTEST — measurement status: arms A-E measure THIS host's desktop "
             "session. WHICH PATH FIRES IN A FULLSCREEN GAME = NOT MEASURED IN-GAME (no game "
             "was run).");
    bool all = true;
    for (const ArmResult& a : arms) {
        log_line("ARM %s %s :: %s", a.name.c_str(), a.pass ? "PASS" : "FAIL", a.detail.c_str());
        if (!a.pass) all = false;
    }
    const int n_pass = (int)std::count_if(arms.begin(), arms.end(),
                                          [](const ArmResult& a) { return a.pass; });
    log_line("TRIGGER-SELFTEST %d/%d arms :: %s", n_pass, (int)arms.size(),
             all ? "GREEN" : "RED");
    return all ? 0 : 1;
}

} // namespace aireplay

// ------------------------------------------------------------------ entry point
// A SEPARATE translation-unit main() on purpose: it must not collide with main.cpp's main(),
// which the gate never links (the gate links every OTHER capture source).
int main(int argc, char** argv)
{
    using namespace aireplay;
    std::string mutant, work_dir = "H:\\aireplay\\_main\\build", out;
    bool arm_c_only = false;
    for (int i = 1; i < argc; ++i) {
        const std::string a = argv[i];
        if (a == "--mutant" && i + 1 < argc)        mutant = argv[++i];
        else if (a == "--work-dir" && i + 1 < argc)  work_dir = argv[++i];
        else if (a == "--out" && i + 1 < argc)      out = argv[++i];
        else if (a == "--arm-c-only")               arm_c_only = true;
    }
    if (arm_c_only) return run_arm_c_probe(out.empty() ? std::string("armc.txt") : out);

    log_open_file(work_dir + "\\lane1-trigger-selftest.log");
    const int rc = run_trigger_selftest(mutant, work_dir);
    log_close_file();
    return rc;
}