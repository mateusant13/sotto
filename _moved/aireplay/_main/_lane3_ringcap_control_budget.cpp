// _lane3_ringcap_control_budget.cpp — ARM D control instrument (lane 3).
//
// This file's ONLY job is to call the budget API.  Compiled against the CURRENT
// ring_buffer.cpp it links and prints a budget.  Compiled against the PRE-CHANGE ring_buffer
// (restored in a COPY under _main\_lane3-ringcap-control\) it MUST FAIL TO LINK with
// "undefined reference to query_ring_budget" / "ring_apply_budget".
//
// That link failure IS the measurement: it proves the pre-change ring owned no system-RAM
// budget at all — the cap shipped from the GPU's VRAM (d3d11_ctx.cpp:70) and the ring just
// accepted whatever it was handed.  A control that passes on both sides proves nothing, so
// this arm is required to go RED-as-expected against the old code.
//
// It allocates nothing: ring_apply_budget is a pure function, so the clamp can be observed
// without committing gigabytes.
#include "ring_buffer.h"

#include <cstdio>

using namespace aireplay;

int main()
{
    RingBudget b = query_ring_budget();
    size_t under = ring_apply_budget(512ull << 20, b);      // under the cap: untouched
    size_t over  = ring_apply_budget(8ull << 30, b);        // over the cap: clamped
    printf("CONTROL budget_api=present cap_mib=%llu clamp_under_mib=%llu clamp_over_mib=%llu\n",
           (unsigned long long)(b.cap_bytes >> 20),
           (unsigned long long)(under >> 20),
           (unsigned long long)(over >> 20));
    return 0;
}