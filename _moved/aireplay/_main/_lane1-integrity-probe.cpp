// _lane1-integrity-probe.cpp — isolates Trigger::process_integrity_rid(), the only Win32 call
// between the last line the crashed selftest printed and the line it never reached.
#include "trigger.h"
#include <cstdio>

using namespace aireplay;

int main()
{
    log_line("probe: before");
    HANDLE tok = nullptr;
    const BOOL ok = OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &tok);
    log_line("probe: OpenProcessToken ok=%d err=%lu", (int)ok, (unsigned long)GetLastError());
    if (!ok) return 2;

    DWORD need = 0;
    const BOOL q0 = GetTokenInformation(tok, TokenIntegrityLevel, nullptr, 0, &need);
    log_line("probe: sizing call ok=%d need=%lu err=%lu",
             (int)q0, (unsigned long)need, (unsigned long)GetLastError());
    if (need == 0) { CloseHandle(tok); return 3; }

    std::vector<uint8_t> buf(need);
    const BOOL q1 = GetTokenInformation(tok, TokenIntegrityLevel, buf.data(), need, &need);
    log_line("probe: fill call ok=%d bytes=%lu", (int)q1, (unsigned long)need);
    if (!q1) { CloseHandle(tok); return 4; }

    TOKEN_MANDATORY_LABEL* tml = (TOKEN_MANDATORY_LABEL*)buf.data();
    PSID sid = tml->Label.Sid;
    log_line("probe: sid ptr=%p valid=%d", (void*)sid, (int)IsValidSid(sid));
    const DWORD n_sub = (DWORD)*GetSidSubAuthorityCount(sid);
    log_line("probe: subauthorities=%lu", (unsigned long)n_sub);
    const DWORD rid = n_sub ? *GetSidSubAuthority(sid, n_sub - 1) : 0;
    CloseHandle(tok);
    log_line("probe: rid=0x%X name=%s", (unsigned)rid, Trigger::integrity_name(rid));
    log_line("probe: via static helper rid=0x%X", (unsigned)Trigger::process_integrity_rid());
    return 0;
}