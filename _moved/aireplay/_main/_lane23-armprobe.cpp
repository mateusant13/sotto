// _lane23-armprobe.cpp — the measurement probe behind _lane23-trigger-defects-gate.ps1.
//
// It links the SAME trigger.cpp the app links, so every number it prints is the shipped
// behaviour of the file under test.  The gate builds this file twice: once against the real
// trigger.cpp, once against a COPY whose cure is reverted.  Both sides print the SAME line
// format, so arm D can compare them without any special case.
//
// Everything here drives the trigger through prepare_for_test() + poll_once() with a SYNTHETIC
// key-state function.  No real keystroke is ever synthesised into the owner's session —
// that would type into whatever window he has focused.
//
// Machine-readable output, one line per arm:
//   LANE23-A cuts=<n> bound=<name[,name...]>
//   LANE23-B cuts=<n>
//   LANE23-C arm_rc=<0|1> registered=<0|1> owned=<0|1> err=<code> errtext=<text> key=<name>
//   LANE23-C summary_names_key=<0|1>
#include "trigger.h"

#include <cstdio>
#include <string>
#include <vector>

using namespace aireplay;

namespace {

bool g_down[256] = { false };

int fake_keystate(int vk)
{
    if (vk < 0 || vk >= 256) return 0;
    return g_down[vk] ? (int)0x8001 : 0;   // high bit set == pressed, exactly like the real API
}

void reset_keys()
{
    for (int i = 0; i < 256; ++i) g_down[i] = false;
}

void set_mods(const int* mods, int n, bool down)
{
    for (int i = 0; i < n; ++i) g_down[mods[i]] = down;
}

// Collect every queued request and render their binding names as "A,B,C".
std::string drain_names(Trigger& t)
{
    std::string names;
    CutRequest r;
    while (t.take(&r, 0)) {
        if (!names.empty()) names += ",";
        names += (r.binding.name ? r.binding.name : "(null)");
    }
    return names.empty() ? "(none)" : names;
}

uint32_t tick(Trigger& t)
{
    return t.poll_once(qpc_now_ns(), fake_keystate);
}

// ── ARM A ──────────────────────────────────────────────────────────────────────────────────
// ONE Alt+F10 press must produce EXACTLY ONE CutRequest, and that request must be bound to
// Alt+F10.  The bindings are the two rows of the SHIPPED ladder that a single physical chord
// can reach, copied verbatim from default_binding_ladder() so the probe cannot drift from the
// shipped defaults.
void arm_a()
{
    const std::vector<HotkeyBinding> b = {
        { VK_F10, 0,       "F10",    30.0 },
        { VK_F10, MOD_ALT, "Alt+F10", 30.0 },
    };
    Trigger t;
    t.prepare_for_test(b, 30.0);

    reset_keys();
    const int alt[] = { VK_MENU };
    set_mods(alt, 1, true);
    g_down[VK_F10] = true;
    uint32_t cuts = 0;
    for (int i = 0; i < 3; ++i) cuts += tick(t);   // hold across ticks
    g_down[VK_F10] = false;                         // release the key BEFORE the modifier
    cuts += tick(t);
    set_mods(alt, 1, false);
    cuts += tick(t);

    printf("LANE23-A cuts=%u bound=%s\n", cuts, drain_names(t).c_str());
    fflush(stdout);
    reset_keys();
}

// ── ARM B ──────────────────────────────────────────────────────────────────────────────────
// THE CONTRACT'S HOLD SEMANTICS, as trigger.h states them: a held key yields ONE request and
// not one per 8 ms tick; a SECOND distinct press yields a second request; and the latch
// re-arms on release so the second press is not swallowed.
//   trace: down,down,down | up | down,down | up   => 2 rising edges => 2 cuts
// run twice over the SAME two bindings, once plain and once with Alt held, because the
// modifier path must not change the hold semantics.
void arm_b_once(const char* tag, bool with_alt)
{
    const std::vector<HotkeyBinding> b = {
        { VK_F10, 0,       "F10",    30.0 },
        { VK_F10, MOD_ALT, "Alt+F10", 30.0 },
    };
    Trigger t;
    t.prepare_for_test(b, 30.0);

    reset_keys();
    const int alt[] = { VK_MENU };
    if (with_alt) set_mods(alt, 1, true);

    const bool trace[7] = { true, true, true, false, true, true, false };
    uint32_t cuts = 0;
    for (int i = 0; i < 7; ++i) {
        g_down[VK_F10] = trace[i];
        cuts += tick(t);
    }
    if (with_alt) set_mods(alt, 1, false);
    g_down[VK_F10] = false;
    cuts += tick(t);

    printf("LANE23-B%s cuts=%u bound=%s\n", tag, cuts, drain_names(t).c_str());
    fflush(stdout);
    reset_keys();
}

void arm_b()
{
    arm_b_once("-plain", false);
    arm_b_once("-alt", true);
}

// ── ARM C ──────────────────────────────────────────────────────────────────────────────────
// "A binding is already owned by another app."  This one is MEASURED, not described: this
// process occupies VK_F23 with its OWN RegisterHotKey first, and only then arms the trigger on
// the same key.  The refusal is therefore a real ERROR_HOTKEY_ALREADY_REGISTERED from the OS.
//
// Two claims are asserted, and they are different claims:
//   1. arm() STILL RETURNS TRUE — the poll path is live for a key we cannot register.  That is
//      the documented contract (trigger.h: "Never returns false for 'a key was taken'").
//   2. the refusal SAYS WHICH KEY.  A status of "registered=0" with no name is the defect this
//      arm exists to catch: the owner cannot tell which of nine keys is missing.
void arm_c()
{
    const HotkeyBinding b = { VK_F23, 0, "F23", 30.0 };

    // Occupy the key from THIS process, on this thread, before the trigger tries.
    const int squatter_id = 0x4B23;
    const bool squatter_ok = RegisterHotKey(nullptr, squatter_id, MOD_NOREPEAT, VK_F23) != FALSE;

    std::string err;
    Trigger t;
    const bool armed = t.arm({ b }, 30.0, &err);

    unsigned reg = 0, owned = 0;
    DWORD ecode = 0;
    std::string etext, keyname;
    if (!t.status().empty()) {
        const BindingStatus& s = t.status()[0];
        reg = s.registered ? 1u : 0u;
        owned = s.owned_by_other_process ? 1u : 0u;
        ecode = (unsigned)s.register_error;
        etext = s.register_error_text;
        keyname = s.binding.name ? s.binding.name : "(null)";
    }
    const std::string summary = t.arm_summary();
    const bool summary_names_key = summary.find("F23") != std::string::npos;

    t.disarm();
    if (squatter_ok) UnregisterHotKey(nullptr, squatter_id);

    printf("LANE23-C squatter=%d arm_rc=%d registered=%u owned=%u err=%u errtext=%s key=%s\n",
           squatter_ok ? 1 : 0, armed ? 1 : 0, reg, owned, (unsigned)ecode,
           etext.empty() ? "(none)" : etext.c_str(), keyname.c_str());
    printf("LANE23-C summary_names_key=%d summary=%s\n",
           summary_names_key ? 1 : 0, summary.c_str());
    fflush(stdout);
}

} // namespace

int main()
{
    arm_a();
    arm_b();
    arm_c();
    fflush(stdout);
    return 0;
}