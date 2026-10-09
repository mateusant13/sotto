// _lane7_window_probe.cpp — the GATE's probe for the lane-7 window negotiation.
//
// It does not reimplement anything: it LINKS the production
// `negotiate_capture_window()` and `query_output_desktop()` from
// src/capture/test_window.cpp (the real .cpp, compiled by the gate with the same
// compiler and flags build.cmd uses).  That is the whole point — a gate that tested a
// COPY of the logic would prove nothing about the shipped logic.
//
// Modes:
//   decide  <case>...   print one `DECISION <case> WxH source=... clamped=.. auto=..`
//                       line per synthetic output desktop.  Cases are declared in the
//                       GATE, not here, so the gate's table is the single source of truth.
//   real                 run query_output_desktop() against this box and print the
//                       decision for AUTO and for the product anchor request.
//
// Exit code: 0 when every requested mode ran.  The ASSERTIONS live in the gate, which
// is what makes arm C (the control) possible: reverting one line in the GATE must make
// it go red without this probe changing at all.
#include "test_window.h"

#include <cstdio>
#include <cstring>
#include <string>

using namespace aireplay;

static void print_decision(const char* label, const WindowDecision& d)
{
    printf("DECISION %-26s %ux%u source=%s clamped=%d auto=%d even_floored=%d ok=%d\n",
           label, d.w, d.h, window_source_name(d.source), d.clamped ? 1 : 0,
           d.requested_auto ? 1 : 0, d.even_floored ? 1 : 0, d.ok() ? 1 : 0);
}

// Parse "WxH" from a case spec like "4k=3840x2160" -> label "4k", desktop 3840x2160.
static bool parse_case(const char* spec, std::string* label, DesktopInfo* d)
{
    const char* eq = strchr(spec, '=');
    if (!eq) return false;
    label->assign(spec, eq - spec);
    unsigned w = 0, h = 0;
    if (sscanf(eq + 1, "%ux%u", &w, &h) != 2) return false;
    d->mon_w = w;
    d->mon_h = h;
    d->virt_w = w;
    d->virt_h = h;
    d->mon_is_physical = true;
    d->valid = (w > 0 && h > 0);
    d->note = "synthetic output desktop from the gate";
    return true;
}

int main(int argc, char** argv)
{
    if (argc < 2) { fprintf(stderr, "usage: window_probe decide <case>... | real\n"); return 2; }
    const std::string mode = argv[1];

    if (mode == "real") {
        const DesktopInfo d = query_output_desktop();
        printf("DESKTOP mon=%ux%u virt=%ux%u dpi=%u awareness=%d physical=%d virtualised=%d valid=%d\n",
               d.mon_w, d.mon_h, d.virt_w, d.virt_h, d.dpi, d.awareness,
               d.mon_is_physical ? 1 : 0, d.metrics_virtualised ? 1 : 0, d.valid ? 1 : 0);
        print_decision("real/auto", negotiate_capture_window(0, 0, d));
        print_decision("real/anchor-1080p", negotiate_capture_window(kDefaultCaptureW, kDefaultCaptureH, d));
        return 0;
    }

    if (mode == "decide") {
        for (int i = 2; i < argc; ++i) {
            std::string label;
            DesktopInfo d;
            if (!parse_case(argv[i], &label, &d)) {
                fprintf(stderr, "bad case '%s' (want label=WxH)\n", argv[i]);
                return 2;
            }
            print_decision(label.c_str(), negotiate_capture_window(0, 0, d));
            print_decision((label + "/req1080p").c_str(),
                           negotiate_capture_window(kDefaultCaptureW, kDefaultCaptureH, d));
            print_decision((label + "/req4k").c_str(), negotiate_capture_window(3840, 2160, d));
            print_decision((label + "/req-odd").c_str(), negotiate_capture_window(2559, 1439, d));
        }
        return 0;
    }

    fprintf(stderr, "unknown mode '%s'\n", mode.c_str());
    return 2;
}