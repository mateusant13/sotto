#include "common.h"

#include <psapi.h>
#include <mutex>

namespace aireplay {

static FILE*            g_logf = nullptr;
static std::mutex       g_logmu;

void log_open_file(const std::string& path)
{
    std::lock_guard<std::mutex> lk(g_logmu);
    if (g_logf) { fclose(g_logf); g_logf = nullptr; }
    g_logf = fopen(path.c_str(), "wb");
}

void log_close_file()
{
    std::lock_guard<std::mutex> lk(g_logmu);
    if (g_logf) { fflush(g_logf); fclose(g_logf); g_logf = nullptr; }
}

void log_line(const char* fmt, ...)
{
    char buf[8192];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);

    std::lock_guard<std::mutex> lk(g_logmu);
    fputs(buf, stdout);
    fputc('\n', stdout);
    fflush(stdout);
    if (g_logf) { fputs(buf, g_logf); fputc('\n', g_logf); fflush(g_logf); }
}

std::string narrow(const wchar_t* w)
{
    if (!w) return std::string();
    int n = WideCharToMultiByte(CP_UTF8, 0, w, -1, nullptr, 0, nullptr, nullptr);
    if (n <= 0) return std::string();
    std::string s((size_t)n - 1, '\0');
    WideCharToMultiByte(CP_UTF8, 0, w, -1, &s[0], n, nullptr, nullptr);
    return s;
}

std::string hr_str(long hr)
{
    char b[64];
    snprintf(b, sizeof(b), "0x%08lX", (unsigned long)hr);
    return std::string(b);
}

uint64_t qpc_freq()
{
    LARGE_INTEGER f;
    QueryPerformanceFrequency(&f);
    return (uint64_t)f.QuadPart;
}

uint64_t qpc_now_ns()
{
    static const uint64_t freq = qpc_freq();
    LARGE_INTEGER c;
    QueryPerformanceCounter(&c);
    // freq is 10 000 000 on every Windows box, but the division is kept honest anyway.
    return (uint64_t)((double)c.QuadPart * 1e9 / (double)freq);
}

void micro_wait_ms(uint32_t ms)
{
#ifndef CREATE_WAITABLE_TIMER_HIGH_RESOLUTION
#define CREATE_WAITABLE_TIMER_HIGH_RESOLUTION 0x00000002
#endif
    static HANDLE t = nullptr;
    static bool tried = false;
    if (!tried) {
        tried = true;
        t = CreateWaitableTimerExW(nullptr, nullptr, CREATE_WAITABLE_TIMER_HIGH_RESOLUTION,
                                   TIMER_ALL_ACCESS);
        if (!t) t = CreateWaitableTimerW(nullptr, FALSE, nullptr);
    }
    if (!t) { Sleep(ms); return; }
    LARGE_INTEGER due;
    due.QuadPart = -(LONGLONG)ms * 10000;      // relative, in 100 ns units
    if (!SetWaitableTimer(t, &due, 0, nullptr, nullptr, FALSE)) { Sleep(ms); return; }
    WaitForSingleObject(t, ms + 8);
}

uint64_t process_rss_bytes()
{
    PROCESS_MEMORY_COUNTERS pmc;
    memset(&pmc, 0, sizeof(pmc));
    if (GetProcessMemoryInfo(GetCurrentProcess(), &pmc, sizeof(pmc)))
        return (uint64_t)pmc.WorkingSetSize;
    return 0;
}

void process_cpu_100ns(uint64_t* user, uint64_t* kernel)
{
    // GetProcessTimes(h, &creation, &exit, &kernelTime, &userTime) — kernel is the
    // 3rd out-parameter and user the 4th; getting that order wrong is a classic way
    // to report a number that is right and a label that is a lie.
    FILETIME creation, exit, kern, usr;
    if (GetProcessTimes(GetCurrentProcess(), &creation, &exit, &kern, &usr)) {
        if (user)   *user   = ((uint64_t)usr.dwHighDateTime  << 32) | usr.dwLowDateTime;
        if (kernel) *kernel = ((uint64_t)kern.dwHighDateTime << 32) | kern.dwLowDateTime;
    }
}

void annexb_split(const uint8_t* data, size_t size, std::vector<NalSpan>& out)
{
    out.clear();
    if (!data || size < 4) return;

    struct SC { size_t pos; size_t len; };
    std::vector<SC> scs;
    size_t i = 0;
    while (i + 3 <= size) {
        if (data[i] == 0 && data[i + 1] == 0) {
            if (data[i + 2] == 1) { scs.push_back({ i, 3 }); i += 3; continue; }
            if (i + 4 <= size && data[i + 2] == 0 && data[i + 3] == 1) { scs.push_back({ i, 4 }); i += 4; continue; }
        }
        ++i;
    }
    for (size_t k = 0; k < scs.size(); ++k) {
        size_t start = scs[k].pos + scs[k].len;
        size_t end   = (k + 1 < scs.size()) ? scs[k + 1].pos : size;
        if (end <= start) continue;
        // Trailing zero bytes belong to the NEXT start code, not to this NAL.
        while (end > start && data[end - 1] == 0) --end;
        if (end <= start) continue;
        NalSpan s;
        s.data = data + start;
        s.size = end - start;
        s.type = (uint8_t)(data[start] & 0x1F);
        out.push_back(s);
    }
}

void annexb_to_avcc(const uint8_t* data, size_t size, std::vector<uint8_t>& out)
{
    out.clear();
    std::vector<NalSpan> nals;
    annexb_split(data, size, nals);
    for (const NalSpan& n : nals) {
        put_u32be(out, (uint32_t)n.size);
        out.insert(out.end(), n.data, n.data + n.size);
    }
}

} // namespace aireplay
