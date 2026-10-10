// _audio-mft-probe.cpp — DOES THIS BOX HAVE A REAL AAC ENCODER?  (lane audio-in-clip)
//
// The brief: AAC through the Windows Media Foundation encoder is the FIRST route for the audio
// trak; if the MFT is not available on this box, fall back to a raw PCM trak and REPORT which route
// shipped and why.  That decision is MEASURED here, not assumed, because a route chosen by hope is
// how a silent clip ships.
//
// Measured so far (this file, same box, same session):
//   - MFTEnumEx(PCM16/48k/stereo -> AAC) finds exactly ONE candidate:
//     "Microsoft AAC Audio Encoder MFT", and ActivateObject + SetOutputType + SetInputType all
//     return S_OK.  The encoder IS present and IS openable.
//   - It REFUSES 16 kHz mono input (SetInputType hr=0xC00D36B4, MF_E_INVALIDMEDIATYPE), so the AAC
//     route needs a resample stage to 48 kHz stereo; the loopback tap's native 16 kHz mono stream
//     cannot go straight in.  That is a design fact, not a defect.
//   - ProcessOutput persistently returns E_INVALIDARG for a caller-supplied sample, which is the
//     last thing between this probe and a GREEN.  The battery below isolates the exact term of the
//     output-sample contract it objects to.
//
// This revision is that battery: each arm takes a FRESH MFT activation, sets the same type pair,
// and varies ONLY the output-sample construction, so the arm that flips E_INVALIDARG into bytes is
// the one the muxer implements.
#include <windows.h>
#include <mfapi.h>
#include <mfidl.h>
#include <mftransform.h>
#include <mferror.h>
#include <evr.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <vector>

#define SAFE_RELEASE(p) do { if (p) { (p)->Release(); (p) = NULL; } } while (0)

static void utf8(const WCHAR* w, char* out, size_t n)
{
    if (!w) { out[0] = 0; return; }
    WideCharToMultiByte(CP_UTF8, 0, w, -1, out, (int)n, NULL, NULL);
}

static void hrtext(HRESULT hr, char* buf, size_t n)
{
    LPWSTR msg = NULL;
    DWORD k = FormatMessageW(FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM |
                                 FORMAT_MESSAGE_IGNORE_INSERTS,
                             NULL, (DWORD)hr, MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
                             (LPWSTR)&msg, 0, NULL);
    if (k && msg) {
        int w = WideCharToMultiByte(CP_UTF8, 0, msg, -1, buf, (int)n, NULL, NULL);
        if (w <= 0) snprintf(buf, n, "no text");
        for (size_t i = 0; buf[i]; ++i) if (buf[i] == '\n' || buf[i] == '\r') buf[i] = ' ';
    } else {
        snprintf(buf, n, "no system text");
    }
    if (msg) LocalFree(msg);
    size_t len = strlen(buf);
    while (len && buf[len - 1] == ' ') buf[--len] = 0;
}

static void hrlabel(HRESULT hr)
{
    char t[256];
    hrtext(hr, t, sizeof(t));
    printf("    hr=0x%08lX  (%s)\n", (unsigned long)hr, t);
}

static void fill_pcm(IMFMediaType* t, int rate, int ch)
{
    t->SetGUID(MF_MT_MAJOR_TYPE, MFMediaType_Audio);
    t->SetGUID(MF_MT_SUBTYPE, MFAudioFormat_PCM);
    t->SetUINT32(MF_MT_AUDIO_BITS_PER_SAMPLE, 16);
    t->SetUINT32(MF_MT_AUDIO_SAMPLES_PER_SECOND, (UINT32)rate);
    t->SetUINT32(MF_MT_AUDIO_NUM_CHANNELS, (UINT32)ch);
    t->SetUINT32(MF_MT_AUDIO_BLOCK_ALIGNMENT, (UINT32)(ch * 2));
    t->SetUINT32(MF_MT_AUDIO_AVG_BYTES_PER_SECOND, (UINT32)(rate * ch * 2));
}

static void fill_aac(IMFMediaType* t)
{
    t->SetGUID(MF_MT_MAJOR_TYPE, MFMediaType_Audio);
    t->SetGUID(MF_MT_SUBTYPE, MFAudioFormat_AAC);
    t->SetUINT32(MF_MT_AUDIO_SAMPLES_PER_SECOND, 48000);
    t->SetUINT32(MF_MT_AUDIO_NUM_CHANNELS, 2);
    t->SetUINT32(MF_MT_AUDIO_BITS_PER_SAMPLE, 16);
    t->SetUINT32(MF_MT_AUDIO_BLOCK_ALIGNMENT, 1);
    t->SetUINT32(MF_MT_AUDIO_AVG_BYTES_PER_SECOND, 16000);
}

static void tone_block(short* out, int frames, int channels, int rate, int block_index, int blk)
{
    const double two_pi = 6.28318530717958647692;
    for (int i = 0; i < frames; ++i) {
        double t = (double)(block_index * blk + i) / (double)rate;
        double v = 0.5 * sin(two_pi * 440.0 * t);
        short s = (short)(v * 32767.0);
        for (int c = 0; c < channels; ++c) out[i * channels + c] = s;
    }
}

static void report_stream_info(IMFTransform* mft)
{
    MFT_INPUT_STREAM_INFO ii;
    MFT_OUTPUT_STREAM_INFO oi;
    ZeroMemory(&ii, sizeof(ii));
    ZeroMemory(&oi, sizeof(oi));
    if (SUCCEEDED(mft->GetInputStreamInfo(0, &ii)))
        printf("    in : cbSize=%lu cbAlignment=%lu flags=0x%08lX\n",
               (unsigned long)ii.cbSize, (unsigned long)ii.cbAlignment, (unsigned long)ii.dwFlags);
    if (SUCCEEDED(mft->GetOutputStreamInfo(0, &oi)))
        printf("    out: cbSize=%lu cbAlignment=%lu flags=0x%08lX\n",
               (unsigned long)oi.cbSize, (unsigned long)oi.cbAlignment, (unsigned long)oi.dwFlags);
}

struct ArmOpts {
    int out_buf_size;        // 0 = use GetOutputStreamInfo().cbSize after types are set
    bool begin_streaming;    // send MFT_MESSAGE_NOTIFY_BEGIN_STREAMING
    bool input_first;
    bool lock_unlock_buf;    // Lock/Unlock then SetCurrentLength(0) after AddBuffer
    bool add_multibuffer;
    int blocks;
};

struct DriveResult {
    unsigned long long out_bytes;
    unsigned long long aac_frames;
    unsigned long long adts_frames;
    unsigned long long frames_in;
    int first_err_block;
    HRESULT first_err;
    char first_err_text[192];
    bool need_more_input;
    DriveResult() : out_bytes(0), aac_frames(0), adts_frames(0), frames_in(0),
                    first_err_block(-1), first_err(0), need_more_input(false) { first_err_text[0] = 0; }
};

static DriveResult drive(IMFTransform* mft, int rate, int ch, int blk, const ArmOpts& o)
{
    DriveResult r;
    for (int b = 0; b < o.blocks; ++b) {
        std::vector<short> pcm(blk * ch);
        tone_block(pcm.data(), blk, ch, rate, b, blk);
        IMFMediaBuffer* inbuf = NULL;
        if (FAILED(MFCreateMemoryBuffer((DWORD)pcm.size() * 2, &inbuf)) || !inbuf) continue;
        BYTE* p = NULL;
        DWORD dummy = 0;
        inbuf->Lock(&p, &dummy, &dummy);
        memcpy(p, pcm.data(), pcm.size() * 2);
        inbuf->Unlock();
        inbuf->SetCurrentLength((DWORD)pcm.size() * 2);
        IMFSample* s = NULL;
        MFCreateSample(&s);
        s->AddBuffer(inbuf);
        inbuf->Release();
        s->SetSampleTime((LONGLONG)r.frames_in * 10000000LL / rate);
        s->SetSampleDuration((LONGLONG)blk * 10000000LL / rate);
        HRESULT hr = mft->ProcessInput(0, s, 0);
        s->Release();
        r.frames_in += blk;
        if (FAILED(hr)) {
            r.first_err_block = b;
            r.first_err = hr;
            hrtext(hr, r.first_err_text, sizeof(r.first_err_text));
            break;
        }

        // output sample
        DWORD want = (DWORD)o.out_buf_size;
        if (want == 0) {
            MFT_OUTPUT_STREAM_INFO oi;
            ZeroMemory(&oi, sizeof(oi));
            if (SUCCEEDED(mft->GetOutputStreamInfo(0, &oi)) && oi.cbSize) want = oi.cbSize;
        }
        if (!want) want = 1536;
        IMFSample* os = NULL;
        IMFMediaBuffer* ob = NULL;
        MFCreateSample(&os);
        MFCreateMemoryBuffer(want, &ob);
        if (o.lock_unlock_buf && ob) {
            BYTE* q = NULL;
            DWORD d = 0;
            ob->Lock(&q, &d, &d);
            ob->Unlock();
            ob->SetCurrentLength(0);
        }
        if (os && ob) {
            os->AddBuffer(ob);
            if (o.add_multibuffer) {
                // a second buffer of the same size, so the MFT may pick either
                IMFMediaBuffer* ob2 = NULL;
                if (SUCCEEDED(MFCreateMemoryBuffer(want, &ob2)) && ob2) {
                    os->AddBuffer(ob2);
                    ob2->Release();
                }
            }
            MFT_OUTPUT_DATA_BUFFER od;
            ZeroMemory(&od, sizeof(od));
            od.dwStreamID = 0;
            od.pSample = os;
            DWORD st = 0;
            HRESULT h = mft->ProcessOutput(0, 1, &od, &st);
            if (h == MF_E_TRANSFORM_NEED_MORE_INPUT) { r.need_more_input = true; }
            else if (h == MF_E_TRANSFORM_STREAM_CHANGE) { r.first_err = h; snprintf(r.first_err_text, sizeof(r.first_err_text), "MF_E_TRANSFORM_STREAM_CHANGE"); }
            else if (SUCCEEDED(h)) {
                IMFSample* got = od.pSample;
                if (got) {
                    IMFMediaBuffer* mb = NULL;
                    if (SUCCEEDED(got->GetBufferByIndex(0, &mb)) && mb) {
                        BYTE* q = NULL;
                        DWORD max = 0, cur = 0;
                        if (SUCCEEDED(mb->Lock(&q, &max, &cur)) && q && cur) {
                            r.out_bytes += cur;
                            r.aac_frames++;
                            bool adts = (cur >= 2 && q[0] == (BYTE)0xFF && (q[1] & (BYTE)0xF0) == (BYTE)0xF0);
                            if (adts) r.adts_frames++;
                            printf("      OUT frame %lu bytes %s  buf0 max=%lu\n",
                                   (unsigned long)cur, adts ? "ADTS-sync" : "rawAAC-noADTS", (unsigned long)max);
                        }
                        mb->Unlock();
                        mb->Release();
                    }
                }
                if (od.pEvents) { od.pEvents->Release(); od.pEvents = NULL; }
            } else {
                r.first_err = h;
                hrtext(h, r.first_err_text, sizeof(r.first_err_text));
            }
        }
        SAFE_RELEASE(ob);
        SAFE_RELEASE(os);
        if (r.first_err && r.out_bytes == 0 && r.first_err_block < 0) {
            r.first_err_block = b;
            break;
        }
    }
    mft->ProcessMessage(MFT_MESSAGE_COMMAND_DRAIN, 0);
    return r;
}

int main(void)
{
    setvbuf(stdout, NULL, _IONBF, 0);

    HRESULT hr = CoInitializeEx(NULL, COINIT_MULTITHREADED);
    printf("COM: CoInitializeEx(COINIT_MULTITHREADED) hr=0x%08lX\n", (unsigned long)hr);
    hr = MFStartup(MF_VERSION, MFSTARTUP_FULL);
    printf("MF : MFStartup(MF_VERSION) hr=0x%08lX\n", (unsigned long)hr);
    if (FAILED(hr)) { printf("VERDICT: RED - the Media Foundation runtime did not start\n"); return 2; }

    struct Arm {
        const char* id;
        const char* desc;
        ArmOpts o;
    };
    ArmOpts base;
    base.out_buf_size = 16000;
    base.begin_streaming = true;
    base.input_first = false;
    base.lock_unlock_buf = false;
    base.add_multibuffer = false;
    base.blocks = 4;

    Arm arms[8];
    arms[0].id = "A1"; arms[0].desc = "output buffer 16000 (today's failing shape)"; arms[0].o = base;
    { ArmOpts o = base; o.out_buf_size = 0; arms[1].id = "A2"; arms[1].desc = "output buffer = GetOutputStreamInfo().cbSize exactly"; arms[1].o = o; }
    { ArmOpts o = base; o.out_buf_size = 0; o.lock_unlock_buf = true; arms[2].id = "A3"; arms[2].desc = "cbSize + Lock/Unlock then SetCurrentLength(0)"; arms[2].o = o; }
    { ArmOpts o = base; o.out_buf_size = 0; o.add_multibuffer = true; arms[3].id = "A4"; arms[3].desc = "cbSize + a second same-size buffer on the sample"; arms[3].o = o; }
    { ArmOpts o = base; o.out_buf_size = 0; o.begin_streaming = false; arms[4].id = "A5"; arms[4].desc = "cbSize, NO NOTIFY_BEGIN_STREAMING message"; arms[4].o = o; }
    { ArmOpts o = base; o.out_buf_size = 0; o.input_first = true; arms[5].id = "A6"; arms[5].desc = "input type first, then output, cbSize buffer"; arms[5].o = o; }
    { ArmOpts o = base; o.out_buf_size = 0; o.begin_streaming = false; o.input_first = true; arms[6].id = "A7"; arms[6].desc = "input first + no begin-streaming + cbSize"; arms[6].o = o; }
    { ArmOpts o = base; o.out_buf_size = 0; o.begin_streaming = false; o.input_first = false; o.blocks = 40; arms[7].id = "A8"; arms[7].desc = "A5 for 40 blocks (long-drive, 0.85 s)"; arms[7].o = o; }

    const int kArms = (int)(sizeof(arms) / sizeof(arms[0]));
    int producing = 0;
    int green_arm = -1;
    unsigned long long green_bytes = 0;

    for (int ai = 0; ai < kArms; ++ai) {
        printf("\n=== %s: %s ===\n", arms[ai].id, arms[ai].desc);
        IMFActivate** acts = NULL;
        UINT32 n = 0;
        IMFMediaType* t48 = NULL;
        IMFMediaType* taac = NULL;
        MFCreateMediaType(&t48);
        MFCreateMediaType(&taac);
        fill_pcm(t48, 48000, 2);
        fill_aac(taac);
        MFT_REGISTER_TYPE_INFO ri, ro;
        t48->GetGUID(MF_MT_MAJOR_TYPE, &ri.guidMajorType);
        t48->GetGUID(MF_MT_SUBTYPE, &ri.guidSubtype);
        taac->GetGUID(MF_MT_MAJOR_TYPE, &ro.guidMajorType);
        taac->GetGUID(MF_MT_SUBTYPE, &ro.guidSubtype);
        hr = MFTEnumEx(MFT_CATEGORY_AUDIO_ENCODER, MFT_ENUM_FLAG_ALL, &ri, &ro, &acts, &n);
        if (n == 0) {
            printf("    MFTEnumEx found no candidate (hr=0x%08lX)\n", (unsigned long)hr);
            SAFE_RELEASE(t48);
            SAFE_RELEASE(taac);
            continue;
        }
        IMFTransform* mft = NULL;
        if (FAILED(acts[0]->ActivateObject(IID_IMFTransform, (void**)&mft)) || !mft) {
            printf("    ActivateObject FAILED\n");
            for (UINT32 i = 0; i < n; ++i) acts[i]->Release();
            CoTaskMemFree(acts);
            SAFE_RELEASE(t48);
            SAFE_RELEASE(taac);
            continue;
        }
        HRESULT h1, h2;
        if (arms[ai].o.input_first) {
            h1 = mft->SetInputType(0, t48, 0);
            h2 = mft->SetOutputType(0, taac, 0);
        } else {
            h1 = mft->SetOutputType(0, taac, 0);
            h2 = mft->SetInputType(0, t48, 0);
        }
        printf("    SetOutput hr=0x%08lX / SetInput hr=0x%08lX (both S_OK = the type pair is accepted)\n",
               (unsigned long)h1, (unsigned long)h2);
        if (FAILED(h1) || FAILED(h2)) {
            printf("    ARM REFUSED at type-set time\n");
            for (UINT32 i = 0; i < n; ++i) acts[i]->Release();
            CoTaskMemFree(acts);
            mft->Release();
            SAFE_RELEASE(t48);
            SAFE_RELEASE(taac);
            continue;
        }
        if (arms[ai].o.begin_streaming) mft->ProcessMessage(MFT_MESSAGE_NOTIFY_BEGIN_STREAMING, 0);
        report_stream_info(mft);
        DriveResult r = drive(mft, 48000, 2, 1024, arms[ai].o);
        printf("    %s RESULT bytes=%llu frames=%llu adts=%llu in_frames=%llu need_more_input=%d\n",
               arms[ai].id, (unsigned long long)r.out_bytes, (unsigned long long)r.aac_frames,
               (unsigned long long)r.adts_frames, (unsigned long long)r.frames_in,
               (int)r.need_more_input);
        if (r.first_err) {
            printf("    %s ERROR %s hr=0x%08lX ", arms[ai].id,
                   r.first_err_block >= 0 ? "at ProcessInput" : "at ProcessOutput", (unsigned long)r.first_err);
            printf("(%s)\n", r.first_err_text);
        }
        if (r.out_bytes > 0) {
            producing++;
            if (green_arm < 0) { green_arm = ai; green_bytes = r.out_bytes; }
        }
        for (UINT32 i = 0; i < n; ++i) acts[i]->Release();
        CoTaskMemFree(acts);
        mft->Release();
        SAFE_RELEASE(t48);
        SAFE_RELEASE(taac);
    }

    printf("\nBATTERY: arms=%d producing=%d\n", kArms, producing);
    if (producing) {
        printf("BATTERY: WINNING ARM %s with %llu bytes\n", arms[green_arm].id, (unsigned long long)green_bytes);
        printf("VERDICT: GREEN - a real AAC encoder exists on this box and produced bytes from a 440 Hz tone\n");
        return 0;
    }
    printf("VERDICT: RED - every arm got a valid type pair and still produced zero bytes\n");
    return 5;
}
