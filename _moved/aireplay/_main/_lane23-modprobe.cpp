// _lane23-modprobe.cpp — MEASUREMENT PROBE for the modifier-matching defect.
//
// Used by _lane23-trigger-defects-gate.ps1.  Not part of the app; it links the SAME
// trigger.cpp the app does, so what it prints is the shipped behaviour.
//
// It drives poll_once() with a SYNTHETIC key-state function (never a real keystroke —
// injecting one would type into whatever window the owner has focused), because
// Trigger::prepare_for_test() + poll_once() is exactly the seam trigger.h:159-170
// documents for making the edge logic provable.
//
// Prints one machine-readable line:
//   LANE23-MOD altf10_cuts=<n> altf10_bound=<name>
//   LANE23-MOD plainf10_cuts=<n> plainf10_bound=<name>
#include "trigger.h"

#include <cstdio>
#include <string>
#include <vector>

namespace {

bool g_down[256] = { false };

int fake_keystate(int vk)
{
    if (vk < 0 || vk >= 256) return 0;
    return g_down[vk] ? (int)0x8001 : 0;
}

void reset_keys()
{
    for (int i = 0; i < 256; ++i) g_down[i] = false;
}

// Press `mods` + `key`, hold for 3 ticks, release, and collect every request produced.
struct PressResult {
    std::vector<std::string> bound_names;
    uint32_t cuts = 0;
    uint32_t ticks = 0;
};

PressResult press(aireplay::Trigger& t, int key, const int* mods, int n_mods)
{
    PressResult r;
    reset_keys();
    for (int m = 0; m < n_mods; ++m) g_down[mods[m]] = true;
    g_down[key] = true;
    for (int i = 0; i < 3; ++i) { r.cuts += t.poll_once(aireplay::qpc_now_ns(), fake_keystate); ++r.ticks; }
    g_down[key] = false;
    for (int m = 0; m < n_mods; ++m) g_down[mods[m]] = false;
    r.cuts += t.poll_once(aireplay::qpc_now_ns(), fake_keystate); ++r.ticks;  // release tick

    aireplay::CutRequest req;
    std::string names;
    while (t.take(&req, 0)) {
        r.bound_names.push_back(req.binding.name ? req.binding.name : "(null)");
        names += (names.empty() ? "" : ",");
        names += (req.binding.name ? req.binding.name : "(null)");
    }
    (void)names;
    reset_keys();
    return r;
}

} // namespace

int main()
{
    using namespace aireplay;

    // The two bindings from the SHIPPED ladder that a single physical chord can reach:
    // "F10" (mods 0) and "Alt+F10" (MOD_ALT).  Copied verbatim from trigger.cpp's
    // default_binding_ladder() so this probe cannot drift away from the shipped defaults.
    const std::vector<HotkeyBinding> b = {
        { VK_F10, 0,       "F10",    30.0 },
        { VK_F10, MOD_ALT, "Alt+F10", 30.0 },
    };

    {
        Trigger t;
        t.prepare_for_test(b, 30.0);
        const int alt[] = { VK_MENU };
        const PressResult r = press(t, VK_F10, alt, 1);
        std::string names;
        for (size_t i = 0; i < r.bound_names.size(); ++i) {
            if (i) names += ",";
            names += r.bound_names[i];
        }
        printf("LANE23-MOD altf10_cuts=%u altf10_bound=%s\n", r.cuts, names.c_str());
    }
    {
        Trigger t;
        t.prepare_for_test(b, 30.0);
        const PressResult r = press(t, VK_F10, nullptr, 0);
        std::string names;
        for (size_t i = 0; i < r.bound_names.size(); ++i) {
            if (i) names += ",";
            names += r.bound_names[i];
        }
        printf("LANE23-MOD plainf10_cuts=%u plainf10_bound=%s\n", r.cuts, names.c_str());
    }
    fflush(stdout);
    return 0;
}