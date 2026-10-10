// _audio-tone-render.cpp -- RENDER A TONE INTO ONE ENDPOINT AND PROVE THE LOOPBACK CARRIES IT.
// Scratch probe for lane feat/audio-in-clip, run from H:/sotto-wt/audioclip/_main.
//
// WHY IT EXISTS (the gap that blocked the cut): the python injector
// _audio-tone-inject.py needs sounddevice, which NO python on this box has installed
// (ModuleNotFoundError under C:/Program Files/Python311 and under _venv-diar), so an
// "I played a tone" claim could not be backed by anything.  This probe is the C++ half:
// it renders a sine into a NAMED endpoint through WASAPI shared render and, in the SAME
// process, opens a read-only LOOPBACK tap on that same endpoint and measures what came
// back.  Nothing is audible unless --allow-audible is passed: the default render endpoint
// (VoiceMeeter Input on this box) is REFUSED outright.
//
// It links against exactly the libraries build.cmd already links (-lole32 -luuid
// -lruntimeobject -lwindowsapp -loleaut32): no new dependency is introduced.
#include <windows.h>
#include <mmdeviceapi.h>
#include <audioclient.h>
#include <functiondiscoverykeys_devpkey.h>
#include <combaseapi.h>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <string>
#include <vector>

static void printf_(const char* f, ...) {}
#define LOG(...) do { printf(__VA_ARGS__); putchar('\n'); } while (0)

namespace {

struct ComScope {
    HRESULT hr = S_OK;
    ComScope() { hr = CoInitializeEx(nullptr, COINIT_MULTITHREADED); }
    ~ComScope() { if (SUCCEEDED(hr) && hr != S_FALSE) CoUninitialize(); }
    bool ok() const { return hr == S_OK || hr == S_FALSE || hr == RPC_E_CHANGED_MODE; }
};

std::string hres(HRESULT hr) {
    char b[32];
    snprintf(b, sizeof(b), "0x%08lx", (unsigned long)hr);
    return std::string(b);
}

std::string narrow(const wchar_t* w) {
    if (!w) return std::string();
    int n = WideCharToMultiByte(CP_UTF8, 0, w, -1, nullptr, 0, nullptr, nullptr);
    std::string s(n ? n - 1 : 0, '\0');
    if (n > 1) WideCharToMultiByte(CP_UTF8, 0, w, -1, &s[0], n, nullptr, nullptr);
    return s;
}

std::string fname(IMMDevice* d) {
    if (!d) return std::string();
    IPropertyStore* ps = nullptr;
    std::string out;
    if (SUCCEEDED(d->OpenPropertyStore(STGM_READ, &ps)) && ps) {
        PROPVARIANT pv; PropVariantInit(&pv);
        if (SUCCEEDED(ps->GetValue(PKEY_Device_FriendlyName, &pv)) && pv.vt == VT_LPWSTR) {
            out = narrow(pv.pwszVal);
        }
        PropVariantClear(&pv);
        ps->Release();
    }
    return out;
}

std::string dev_id(IMMDevice* d) {
    LPWSTR w = nullptr;
    if (!d) return "";
    if (FAILED(d->GetId(&w)) || !w) return "";
    std::string s = narrow(w);
    CoTaskMemFree(w);
    return s;
}

bool contains_ci(const std::string& hay, const std::string& needle) {
    auto low = [](std::string s) {
        for (char& c : s) if (c >= 'A' && c <= 'Z') c = (char)(c + 32);
        return s;
    };
    return low(hay).find(low(needle)) != std::string::npos;
}

struct Mix {
    uint32_t rate = 0; uint16_t ch = 0; uint16_t bits = 0;
    bool is_float = false; uint16_t align = 0;
};

bool read_mix(IMMDevice* d, Mix* m) {
    IAudioClient* c = nullptr;
    if (FAILED(d->Activate(__uuidof(IAudioClient), CLSCTX_INPROC_SERVER, nullptr,
                           reinterpret_cast<void**>(&c))) || !c) return false;
    WAVEFORMATEX* mix = nullptr;
    bool ok = false;
    if (SUCCEEDED(c->GetMixFormat(&mix)) && mix) {
        uint16_t tag = mix->wFormatTag;
        if (tag == WAVE_FORMAT_EXTENSIBLE && mix->cbSize >= 22) {
            tag = (uint16_t)(reinterpret_cast<const WAVEFORMATEXTENSIBLE*>(mix)
                                 ->SubFormat.Data1 & 0xFFFF);
        }
        m->rate = mix->nSamplesPerSec; m->ch = mix->nChannels; m->bits = mix->wBitsPerSample;
        m->align = mix->nBlockAlign; m->is_float = (tag == WAVE_FORMAT_IEEE_FLOAT);
        ok = true;
        CoTaskMemFree(mix);
    }
    c->Release();
    return ok;
}

}  // namespace

int main(int argc, char** argv) {
    double seconds = 6.0, freq = 440.0, amp = 0.5;
    std::string want = "CABLE Input";
    bool allow_audible = false, dry = false, render_only = false;
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        auto next = [&]() -> std::string { return (i + 1 < argc) ? std::string(argv[++i]) : ""; };
        if (a == "--seconds") seconds = atof(next().c_str());
        else if (a == "--freq") freq = atof(next().c_str());
        else if (a == "--amp") amp = atof(next().c_str());
        else if (a == "--endpoint") want = next();
        else if (a == "--allow-audible") allow_audible = true;
        else if (a == "--dry") dry = true;
        else if (a == "--render-only") render_only = true;
    }

    ComScope com;
    if (!com.ok()) { LOG("FATAL CoInitializeEx %s", hres(com.hr).c_str()); return 2; }
    IMMDeviceEnumerator* enm = nullptr;
    HRESULT hr = CoCreateInstance(__uuidof(MMDeviceEnumerator), nullptr, CLSCTX_INPROC_SERVER,
                                  __uuidof(IMMDeviceEnumerator), reinterpret_cast<void**>(&enm));
    if (FAILED(hr) || !enm) { LOG("FATAL enumerator %s", hres(hr).c_str()); return 2; }

    IMMDeviceCollection* coll = nullptr;
    if (FAILED(enm->EnumAudioEndpoints(eRender, DEVICE_STATE_ACTIVE, &coll)) || !coll) {
        LOG("FATAL EnumAudioEndpoints"); enm->Release(); return 2;
    }
    IMMDevice* def = nullptr;
    SUCCEEDED(enm->GetDefaultAudioEndpoint(eRender, eConsole, &def));
    std::string def_id = def ? dev_id(def) : "";

    UINT count = 0; coll->GetCount(&count);
    LOG("ENUMERATED active render endpoints: %u", (unsigned)count);
    IMMDevice* chosen = nullptr;
    for (UINT i = 0; i < count; ++i) {
        IMMDevice* d = nullptr;
        if (FAILED(coll->Item(i, &d)) || !d) continue;
        std::string nm = fname(d), id = dev_id(d);
        Mix m{}; read_mix(d, &m);
        bool is_def = (id == def_id && !def_id.empty());
        LOG("  [%u] %-34s default=%d mix=%uHz ch=%u %s%s", (unsigned)i, nm.c_str(), is_def ? 1 : 0,
            (unsigned)m.rate, (unsigned)m.ch, m.is_float ? "float" : "pcm",
            nm.empty() ? " (unnamed)" : "");
        if (!chosen && contains_ci(nm.empty() ? id : nm, want)) chosen = d; else d->Release();
    }
    if (!chosen) { LOG("FATAL no active endpoint matches '%s'", want.c_str()); return 2; }

    std::string cn = fname(chosen), cid = dev_id(chosen);
    if (cid == def_id && !def_id.empty() && !allow_audible) {
        LOG("REFUSED '%s' is the DEFAULT render endpoint: rendering there is AUDIBLE on the"
            " owner's desk. Pass --allow-audible to override, deliberately, in writing.", cn.c_str());
        chosen->Release(); return 3;
    }
    Mix m{}; read_mix(chosen, &m);
    LOG("CHOSEN name=\"%s\"", cn.c_str());
    LOG("CHOSEN id=%s", cid.c_str());
    LOG("CHOSEN mix=%u Hz ch=%u %s (%.0f ms of frames per 10 ms packet)",
        (unsigned)m.rate, (unsigned)m.ch, m.is_float ? "float32" : "pcm16",
        (double)(m.rate / 100) / (double)m.rate * 1000.0 * m.ch);
    if (dry) { LOG("DRY: not rendering"); return 0; }

    // ---- the RENDER side: shared-mode render client on the chosen endpoint.
    IAudioClient* rc = nullptr;
    if (FAILED(chosen->Activate(__uuidof(IAudioClient), CLSCTX_INPROC_SERVER, nullptr,
                                reinterpret_cast<void**>(&rc))) || !rc) {
        LOG("FATAL Activate(render) %s", "fail"); chosen->Release(); return 2;
    }
    WAVEFORMATEX* mix = nullptr;
    if (FAILED(rc->GetMixFormat(&mix)) || !mix) { LOG("FATAL GetMixFormat"); rc->Release(); return 2; }
    hr = rc->Initialize(AUDCLNT_SHAREMODE_SHARED, 0, 1000000ULL * 10, 0, mix, nullptr);
    CoTaskMemFree(mix);
    if (FAILED(hr)) { LOG("FATAL Initialize(render) %s", hres(hr).c_str()); rc->Release(); return 2; }
    UINT32 buf_frames = 0;
    rc->GetBufferSize(&buf_frames);
    IAudioRenderClient* rnd = nullptr;
    if (FAILED(rc->GetService(__uuidof(IAudioRenderClient), reinterpret_cast<void**>(&rnd))) || !rnd) {
        LOG("FATAL GetService(IAudioRenderClient)"); rc->Release(); return 2;
    }
    rc->Start();

    // ---- the LOOPBACK side (optional): the read-only tap, same device, same process.
    IAudioClient* lc = nullptr;
    IAudioCaptureClient* cap = nullptr;
    if (!render_only) {
    if (FAILED(chosen->Activate(__uuidof(IAudioClient), CLSCTX_INPROC_SERVER, nullptr,
                                reinterpret_cast<void**>(&lc))) || !lc) {
        LOG("FATAL Activate(loopback)"); rc->Stop(); rnd->Release(); rc->Release(); return 2;
    }
    WAVEFORMATEX* lmix = nullptr;
    if (FAILED(lc->GetMixFormat(&lmix)) || !lmix) { LOG("FATAL GetMixFormat(loopback)"); lc->Release(); return 2; }
    hr = lc->Initialize(AUDCLNT_SHAREMODE_SHARED, AUDCLNT_STREAMFLAGS_LOOPBACK, 1000000ULL, 0, lmix, nullptr);
    CoTaskMemFree(lmix);
    if (FAILED(hr)) { LOG("FATAL Initialize(loopback) %s", hres(hr).c_str()); lc->Release(); return 2; }
    if (FAILED(lc->GetService(__uuidof(IAudioCaptureClient), reinterpret_cast<void**>(&cap))) || !cap) {
        LOG("FATAL GetService(IAudioCaptureClient)"); lc->Release(); return 2;
    }
    lc->Start();
    }

    const DWORD tick0 = GetTickCount64();
    double phase = 0.0, peak = 0.0, sum_sq = 0.0;
    uint64_t frames = 0, packets = 0, silence_packets = 0, rendered = 0;
    const uint32_t frames_per_tick = m.rate / 100;   // 10 ms of frames
    for (;;) {
        double elapsed = (GetTickCount64() - tick0) / 1000.0;
        if (elapsed >= seconds) break;
        UINT32 padding = 0; rc->GetCurrentPadding(&padding);
        UINT32 avail = (buf_frames > padding) ? (buf_frames - padding) : 0;
        if (avail == 0) { Sleep(1); continue; }
        // Fill EVERY available frame, not one 10 ms packet: the host timer granularity is
        // ~15.6 ms (MEASURED: 480 frames per 15.6 ms = 30720 of the 48000 frames/s the mix
        // consumes), so a one-packet-per-loop render loop runs the buffer dry ~36% of the
        // time and WASAPI then reads SILENCE -- the tone arrives with gaps and a gate that
        // counts exact zeros refuses the clip.  Writing the whole available frame count
        // catches up in one call and keeps the buffer full.
        uint32_t n = avail;
        BYTE* data = nullptr;
        UINT32 done = 0;
        if (FAILED(rnd->GetBuffer(n, &data)) || !data) break;
        // The sine is written into EVERY channel in the mix format: a mono sink fed on
        // one channel only would be half the measurement.
        const double step = 2.0 * 3.14159265358979 * freq / (double)m.rate;
        for (uint32_t i = 0; i < n; ++i) {
            float v = (float)(std::sin(phase) * amp);
            phase += step; if (phase > 2.0 * 3.14159265358979) phase -= 2.0 * 3.14159265358979;
            if (m.is_float) {
                float* p = reinterpret_cast<float*>(data);
                for (uint16_t c = 0; c < m.ch; ++c) p[i * m.ch + c] = v;
            } else {
                int16_t* p = reinterpret_cast<int16_t*>(data);
                int q = (int)(v * 32767.0);
                if (q > 32767) q = 32767; if (q < -32768) q = -32768;
                for (uint16_t c = 0; c < m.ch; ++c) p[i * m.ch + c] = (int16_t)q;
            }
        }
        if (FAILED(rnd->ReleaseBuffer(n, 0))) break;
        rendered += n;
        Sleep(5);
        // drain the loopback that this packet produced
        for (; cap; ) {
            UINT32 np = 0;
            if (FAILED(cap->GetNextPacketSize(&np))) break;
            if (np == 0) break;
            BYTE* b = nullptr; UINT32 got = 0; DWORD flags = 0; UINT64 qpc = 0;
            if (FAILED(cap->GetBuffer(&b, &got, &flags, &qpc, nullptr)) || !b) break;
            if (m.is_float) {
                const float* p = reinterpret_cast<const float*>(b);
                for (UINT32 i = 0; i < got; ++i) {
                    float v = 0.0f;
                    for (uint16_t c = 0; c < m.ch; ++c) v += p[i * m.ch + c];
                    v /= (float)m.ch;
                    double a = std::fabs((double)v);
                    if (a > peak) peak = a;
                    sum_sq += (double)v * (double)v;
                }
            }
            frames += got; ++packets;
            double pk = 0.0;
            {
                const float* p = reinterpret_cast<const float*>(b);
                double s = 0.0;
                for (UINT32 i = 0; i < got; ++i) { float v = 0.0f;
                    for (uint16_t c = 0; c < m.ch; ++c) v += p[i * m.ch + c];
                    v /= (float)m.ch; s += (double)v * (double)v; }
                if (got) pk = std::sqrt(s / (double)got);
                if (pk < 0.001) ++silence_packets;
            }
            (void)pk;
            cap->ReleaseBuffer(got);
        }
    }
    const double elapsed = (GetTickCount64() - tick0) / 1000.0;
    const double rms = frames ? std::sqrt(sum_sq / (double)frames) : 0.0;
    rc->Stop(); if (lc) lc->Stop();
    LOG("RENDER  endpoint=\"%s\" %u Hz ch=%u %s", cn.c_str(), (unsigned)m.rate, (unsigned)m.ch,
        m.is_float ? "float32" : "pcm16");
    LOG("RENDER  frames=%llu over %.2f s = %.1f Hz of source", (unsigned long long)rendered,
        elapsed, (double)rendered / elapsed);
    LOG("CAPTURE packets=%llu frames=%llu = %.2f s of mix-rate audio", (unsigned long long)packets,
        (unsigned long long)frames, (double)frames / (double)m.rate);
    LOG("CAPTURE silent_packets(below 0.001 rms)=%llu", (unsigned long long)silence_packets);
    LOG("RESULT: peak=%.6f rms=%.6f expected_rms(%.3f*sin)=%.6f", peak, rms, amp,
        amp * 0.70710678118655);
    if (render_only && packets == 0) LOG("VERDICT: RENDER-ONLY: the render stream ran, no loopback client was opened");
    else if (packets == 0) LOG("VERDICT: NO-PACKETS: nothing came back through the loopback");
    else if (peak < 0.02) LOG("VERDICT: SILENT: the loopback carried no tone (peak < 0.02)");
    else LOG("VERDICT: TONE-CARRIED: the loopback carried the rendered sine");
    rnd->Release(); rc->Release(); if (cap) cap->Release(); if (lc) lc->Release(); chosen->Release();
    enm->Release(); coll->Release(); if (def) def->Release();
    return 0;
}
