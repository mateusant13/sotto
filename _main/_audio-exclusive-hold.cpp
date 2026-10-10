#include <windows.h>
#include <mmdeviceapi.h>
#include <audioclient.h>
#include <functiondiscoverykeys.h>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <thread>
#include <chrono>

// A REAL competing process on a render endpoint: AUDCLNT_SHAREMODE_EXCLUSIVE, so the next
// process that opens that endpoint for a shared-mode loopback capture is refused with
// AUDCLNT_E_DEVICE_IN_USE (0x8889000A).  That is the only way to reach arm 6 without a mock:
// two SHARED loopback taps on one endpoint coexist (measured), so the competing holder has to
// be an EXCLUSIVE one.
extern "C" const PROPERTYKEY PKEY_Device_FriendlyName;

static bool has(const wchar_t* s, const char* needle) {
    std::string a;
    for (const wchar_t* q = s; *q; ++q) a += (char)*q;
    return a.find(needle) != std::string::npos;
}

int main(int argc, char** argv) {
    const char* needle = argc > 1 ? argv[1] : "CABLE Input";
    int hold_ms = argc > 2 ? atoi(argv[2]) : 20000;
    HRESULT ci = CoInitializeEx(nullptr, COINIT_MULTITHREADED);
    if (FAILED(ci) && ci != RPC_E_CHANGED_MODE) { printf("COINIT-FAIL 0x%08lX\n", (unsigned long)ci); return 1; }
    IMMDeviceEnumerator* en = nullptr;
    if (FAILED(CoCreateInstance(__uuidof(MMDeviceEnumerator), nullptr, CLSCTX_ALL,
                                __uuidof(IMMDeviceEnumerator), (void**)&en))) {
        printf("ENUM-FAIL\n"); return 1;
    }
    IMMDeviceCollection* col = nullptr;
    if (FAILED(en->EnumAudioEndpoints(eRender, DEVICE_STATE_ACTIVE, &col)) || !col) { printf("ENUM-ENDPOINTS-FAIL\n"); return 1; }
    UINT n = 0; col->GetCount(&n);
    IMMDevice* dev = nullptr;
    for (UINT i = 0; i < n && !dev; ++i) {
        IMMDevice* d = nullptr;
        if (FAILED(col->Item(i, &d)) || !d) continue;
        IPropertyStore* ps = nullptr;
        if (SUCCEEDED(d->OpenPropertyStore(STGM_READ, &ps)) && ps) {
            PROPVARIANT v; PropVariantInit(&v);
            if (SUCCEEDED(ps->GetValue(PKEY_Device_FriendlyName, &v)) && v.pwszVal && has(v.pwszVal, needle)) dev = d;
            PropVariantClear(&v);
            ps->Release();
        }
        if (dev != d) d->Release();
    }
    if (!dev) { printf("NO-SUCH-ENDPOINT\n"); return 1; }
    IAudioClient* ac = nullptr;
    HRESULT hr = dev->Activate(__uuidof(IAudioClient), CLSCTX_ALL, nullptr, (void**)&ac);
    if (FAILED(hr) || !ac) { printf("ACTIVATE-FAIL 0x%08lX\n", (unsigned long)hr); return 1; }
    WAVEFORMATEX* wf = nullptr;
    if (FAILED(ac->GetMixFormat(&wf)) || !wf) { printf("MIXFORMAT-FAIL\n"); return 1; }
    struct Cfg { DWORD rate; WORD ch; WORD bits; };
    const Cfg cfgs[] = {
        { wf->nSamplesPerSec, wf->nChannels, wf->wBitsPerSample },
        { 48000, 2, 16 }, { 44100, 2, 16 }, { 96000, 2, 16 },
        { 48000, 2, 24 }, { 48000, 2, 32 }, { 44100, 2, 32 },
    };
    bool held = false;
    for (const Cfg& c : cfgs) {
        WAVEFORMATEX f; ZeroMemory(&f, sizeof(f));
        f.wFormatTag = WAVE_FORMAT_PCM;
        f.nChannels = c.ch; f.nSamplesPerSec = c.rate; f.wBitsPerSample = c.bits;
        f.nBlockAlign = (WORD)(f.nChannels * f.wBitsPerSample / 8);
        f.nAvgBytesPerSec = f.nSamplesPerSec * f.nBlockAlign;
        hr = ac->Initialize(AUDCLNT_SHAREMODE_EXCLUSIVE, 0, 2000000, 0, &f, nullptr);
        printf("INITIALIZE-EXCLUSIVE %lu Hz %u ch %u bit hr=0x%08lX\n",
               (unsigned long)c.rate, (unsigned)c.ch, (unsigned)c.bits, (unsigned long)hr);
        if (SUCCEEDED(hr)) { held = true; break; }
    }
    if (!held) { printf("EXCLUSIVE HOLDER NOT UP\n"); ac->Release(); CoUninitialize(); return 2; }
    printf("HOLDING %d ms\n", hold_ms);
    std::this_thread::sleep_for(std::chrono::milliseconds(hold_ms));
    printf("RELEASED\n");
    CoTaskMemFree(wf); ac->Release(); dev->Release(); en->Release(); col->Release();
    CoUninitialize();
    return 0;
}
