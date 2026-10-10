#include "mp4_writer.h"

#include <cstdio>

namespace aireplay {

// ------------------------------------------------------------------ small box builders
namespace {

struct Box {
    std::vector<uint8_t> b;
    explicit Box(const char* type) { put_u32be(b, 0); b.insert(b.end(), type, type + 4); }
    void end() {
        uint32_t sz = (uint32_t)b.size();
        b[0] = (uint8_t)(sz >> 24); b[1] = (uint8_t)(sz >> 16);
        b[2] = (uint8_t)(sz >> 8);  b[3] = (uint8_t)sz;
    }
};

void put_full_box_header(std::vector<uint8_t>& v, uint8_t version, uint32_t flags)
{
    v.push_back(version);
    v.push_back((uint8_t)(flags >> 16)); v.push_back((uint8_t)(flags >> 8)); v.push_back((uint8_t)flags);
}

// The 3x3 unity matrix in 16.16 / 2.30 fixed point, exactly as the spec writes it.
void put_matrix(std::vector<uint8_t>& v)
{
    const uint32_t m[9] = { 0x00010000, 0, 0, 0, 0x00010000, 0, 0, 0, 0x40000000 };
    for (int i = 0; i < 9; ++i) put_u32be(v, m[i]);
}

} // namespace

// ------------------------------------------------------------------ open / close
Mp4Writer::~Mp4Writer()
{
    if (f_) { fclose(f_); f_ = nullptr; }
}

bool Mp4Writer::open(const std::string& path, const Mp4Config& cfg, std::string* err)
{
    cfg_ = cfg;
    if (cfg_.sps.size() < 4) { *err = "avcC needs at least 4 SPS bytes to read profile/level"; return false; }
    if (cfg_.pps.empty())    { *err = "avcC needs a PPS"; return false; }
    if (cfg_.width == 0 || cfg_.height == 0) { *err = "width/height must be non-zero"; return false; }

    f_ = fopen(path.c_str(), "wb");
    if (!f_) { *err = "could not create " + path; return false; }

    // ftyp
    std::vector<uint8_t> ftyp;
    put_u32be(ftyp, 0);
    ftyp.insert(ftyp.end(), (const uint8_t*)"ftyp", (const uint8_t*)"ftyp" + 4);
    ftyp.insert(ftyp.end(), (const uint8_t*)"isom", (const uint8_t*)"isom" + 4);
    put_u32be(ftyp, 512);
    const char* compat[] = { "isom", "iso2", "avc1", "mp41" };
    for (const char* c : compat) ftyp.insert(ftyp.end(), (const uint8_t*)c, (const uint8_t*)c + 4);
    uint32_t sz = (uint32_t)ftyp.size();
    ftyp[0] = (uint8_t)(sz >> 24); ftyp[1] = (uint8_t)(sz >> 16);
    ftyp[2] = (uint8_t)(sz >> 8);  ftyp[3] = (uint8_t)sz;
    if (fwrite(ftyp.data(), 1, ftyp.size(), f_) != ftyp.size()) { *err = "ftyp write failed"; return false; }
    pos_ = ftyp.size();

    // mdat with a placeholder 32-bit size, patched by close().
    uint8_t hdr[8] = { 0, 0, 0, 0, 'm', 'd', 'a', 't' };
    mdat_start_ = pos_;
    if (fwrite(hdr, 1, 8, f_) != 8) { *err = "mdat header write failed"; return false; }
    pos_ += 8;
    mdat_payload_ = 0;
    return true;
}

bool Mp4Writer::write_sample(const uint8_t* data, size_t size, bool is_sync,
                             uint64_t duration_ticks, std::string* err)
{
    if (!f_) { *err = "write_sample() before open() or after close()"; return false; }
    if (!data || size == 0) { *err = "write_sample() got an empty access unit"; return false; }
    if (size > 0xFFFFFFFFull) { *err = "a single access unit is larger than 4 GiB"; return false; }

    offsets_.push_back(pos_);
    sizes_.push_back((uint32_t)size);
    if (is_sync) sync_numbers_.push_back((uint32_t)sizes_.size());

    uint32_t d = (duration_ticks > 0xFFFFFFFFull) ? 0xFFFFFFFFu : (uint32_t)duration_ticks;
    if (!stts_.empty() && stts_.back().second == d) stts_.back().first += 1;
    else stts_.push_back({ 1u, d });

    if (fwrite(data, 1, size, f_) != size) { *err = "sample write failed"; return false; }
    pos_ += size;
    mdat_payload_ += size;
    return true;
}

double Mp4Writer::audio_seconds() const
{
    // Sum the ACCUMULATED deltas rather than dividing the byte count by an assumed rate:
    // this is the duration the samples actually carry, which is the number the gate checks
    // against the video duration.
    uint64_t ticks = 0;
    for (const auto& e : a_stts_) ticks += (uint64_t)e.first * e.second;
    const uint32_t ts = cfg_.audio.sample_rate ? cfg_.audio.sample_rate : 48000;
    return (double)ticks / (double)ts;
}

bool Mp4Writer::write_audio_sample(const uint8_t* data, size_t size, uint64_t duration_ticks,
                                   std::string* err)
{
    if (!f_) { *err = "write_audio_sample() before open() or after close()"; return false; }
    if (!cfg_.audio.enabled) {
        // There is no legal way to say "no audio" on a file whose reader was told there is
        // audio, so the ONLY honest outcomes are a written sample or a loud failure.
        *err = "write_audio_sample() called with audio disabled in Mp4Config";
        return false;
    }
    if (!data || size == 0) { *err = "write_audio_sample() got an empty sample"; return false; }
    if (size > 0xFFFFFFFFull) { *err = "a single audio sample is larger than 4 GiB"; return false; }

    if (duration_ticks == 0) {
        if (cfg_.audio.pcm) {
            const uint32_t fs = cfg_.audio.channels * cfg_.audio.sample_width;
            duration_ticks = fs ? (size / fs) : 0;
        } else {
            duration_ticks = cfg_.audio.frame_samples ? cfg_.audio.frame_samples : 1024;
        }
    }
    if (duration_ticks == 0) { *err = "audio sample duration came out zero"; return false; }
    if (duration_ticks > 0xFFFFFFFFull) { *err = "audio sample duration is larger than 32 bits"; return false; }
    uint32_t d = (uint32_t)duration_ticks;
    if (!a_stts_.empty() && a_stts_.back().second == d) a_stts_.back().first += 1;
    else a_stts_.push_back({ 1u, d });

    a_offsets_.push_back(pos_);
    a_sizes_.push_back((uint32_t)size);
    if (fwrite(data, 1, size, f_) != size) { *err = "audio sample write failed"; return false; }
    pos_ += size;
    mdat_payload_ += size;
    return true;
}

// ------------------------------------------------------------------ the audio trak
// A descriptor length is a variable-length integer (7 bits per byte, MSB = "more"), which
// is the one place the ISOBMFF writers below can silently go wrong: a wrong length makes
// ffprobe drop the whole trak, so it is computed from the payload rather than written by hand.
void put_descriptor_len(std::vector<uint8_t>& v, uint32_t len)
{
    uint8_t tmp[4];
    int n = 0;
    do { tmp[n++] = (uint8_t)(len & 0x7F); len >>= 7; } while (len);
    while (n > 0) { --n; v.push_back(tmp[n] | (n ? 0x80 : 0x00)); }
}

void put_descriptor(std::vector<uint8_t>& v, uint8_t tag, const std::vector<uint8_t>& payload)
{
    v.push_back(tag);
    put_descriptor_len(v, (uint32_t)payload.size());
    v.insert(v.end(), payload.begin(), payload.end());
}

bool Mp4Writer::build_audio_trak(std::vector<uint8_t>& out, uint64_t movie_timescale,
                                 uint64_t movie_duration, std::string* err) const
{
    if (a_sizes_.empty()) { *err = "build_audio_trak() with zero audio samples"; return false; }
    const Mp4AudioConfig& A = cfg_.audio;
    const uint32_t ts = A.sample_rate ? A.sample_rate : 48000;

    // ---- stsd: ONE sample entry.  AAC -> `mp4a` + `esds`; PCM -> `sowt`, no esds.
    Box stsd("stsd");
    put_full_box_header(stsd.b, 0, 0);
    put_u32be(stsd.b, 1);
    {
        std::vector<uint8_t> ase;
        put_u32be(ase, 0);
        ase.insert(ase.end(), (const uint8_t*)(A.pcm ? "sowt" : "mp4a"),
                   (const uint8_t*)(A.pcm ? "sowt" : "mp4a") + 4);
        for (int i = 0; i < 6; ++i) ase.push_back(0);          // reserved[6]
        put_u16be(ase, 1);                                     // data_reference_index
        for (int i = 0; i < 8; ++i) ase.push_back(0);          // reserved (QuickTime) 
        put_u16be(ase, (uint16_t)A.channels);                  // channelcount
        put_u16be(ase, (uint16_t)(A.pcm ? A.sample_width * 8 : 16)); // samplesize
        put_u16be(ase, 0);                                     // pre_defined
        put_u16be(ase, 0);                                     // reserved
        put_u32be(ase, (uint32_t)ts << 16);                     // samplerate, 16.16 fixed

        if (!A.pcm) {
            // esds: ES -> DecoderConfig -> DecoderSpecificInfo (the ASC) + SLConfig.
            std::vector<uint8_t> dsi;
            put_descriptor(dsi, 0x05, A.asc);                   // DecoderSpecificInfo
            std::vector<uint8_t> sl;
            sl.push_back(0x02);                                 // predefined MP4 config
            put_descriptor(dsi, 0x06, sl);                       // SLConfigDescriptor

            std::vector<uint8_t> dcd;
            dcd.push_back(0x40);                                // objectTypeIndication: MPEG-4 audio
            dcd.push_back(0x05 << 2 | 0x01);                    // audioStream, upstream=0, reserved
            put_u24be(dcd, 0);                                  // bufferSizeDB (unknown)
            put_u32be(dcd, A.bitrate);                          // maxBitrate
            put_u32be(dcd, A.bitrate);                          // avgBitrate
            dcd.insert(dcd.end(), dsi.begin(), dsi.end());
            // put_descriptor(v, tag, payload) APPENDS payload to v, so the sink and the payload
            // must be DISTINCT vectors.  Passing the same one appends the (already grown) vector to
            // itself: the payload is written twice and the length is taken after that mutation.
            // MEASURED 2026-10-10 on the mp4a/esds of runs/verify-tip/clip.mp4 -- the esds came out
            // as 98 bytes of duplicated payload whose FIRST descriptor tag was 0x00, so no reader
            // can reach the ES_Descriptor: ffprobe still NAMES the stream from the mp4a fourcc, but
            // the AudioSpecificConfig is unreadable and it reports NO profile -- measured, same
            // command on both revisions: the broken file reads "aac" (profile=-1), the fixed one
            // reads "aac (LC)" (profile=LC).  A player that trusts the ASC, not the fourcc, is
            // where this stops being cosmetic.
            std::vector<uint8_t> dcd_box;
            put_descriptor(dcd_box, 0x04, dcd);

            std::vector<uint8_t> esd;
            put_u16be(esd, 0);                                  // ES_ID
            esd.push_back(0x00);                                // no dependency / URL / OCR stream
            esd.insert(esd.end(), dcd_box.begin(), dcd_box.end());
            std::vector<uint8_t> esd_box;                       // fresh sink, same rule as dcd_box
            put_descriptor(esd_box, 0x03, esd);

            Box esds("esds");
            put_full_box_header(esds.b, 0, 0);
            esds.b.insert(esds.b.end(), esd_box.begin(), esd_box.end());
            esds.end();

            ase.insert(ase.end(), esds.b.begin(), esds.b.end());
        }

        const uint32_t asz = (uint32_t)ase.size();
        ase[0] = (uint8_t)(asz >> 24); ase[1] = (uint8_t)(asz >> 16);
        ase[2] = (uint8_t)(asz >> 8);  ase[3] = (uint8_t)asz;
        stsd.b.insert(stsd.b.end(), ase.begin(), ase.end());
    }
    stsd.end();

    Box stts("stts");
    put_full_box_header(stts.b, 0, 0);
    put_u32be(stts.b, (uint32_t)a_stts_.size());
    for (const auto& e : a_stts_) { put_u32be(stts.b, e.first); put_u32be(stts.b, e.second); }
    stts.end();

    Box stsc("stsc");
    put_full_box_header(stsc.b, 0, 0);
    put_u32be(stsc.b, 1);
    put_u32be(stsc.b, 1);   // first_chunk
    put_u32be(stsc.b, 1);   // samples_per_chunk — one chunk per sample, like the video trak
    put_u32be(stsc.b, 1);   // sample_description_index
    stsc.end();

    Box stsz("stsz");
    put_full_box_header(stsz.b, 0, 0);
    put_u32be(stsz.b, 0);
    put_u32be(stsz.b, (uint32_t)a_sizes_.size());
    for (uint32_t s : a_sizes_) put_u32be(stsz.b, s);
    stsz.end();

    bool use_co64 = false;
    for (uint64_t o : a_offsets_) if (o > 0xFFFFFFFFull) { use_co64 = true; break; }
    Box stco(use_co64 ? "co64" : "stco");
    put_full_box_header(stco.b, 0, 0);
    put_u32be(stco.b, (uint32_t)a_offsets_.size());
    for (uint64_t o : a_offsets_) { if (use_co64) put_u64be(stco.b, o); else put_u32be(stco.b, (uint32_t)o); }
    stco.end();

    Box astbl("stbl");
    astbl.b.insert(astbl.b.end(), stsd.b.begin(), stsd.b.end());
    astbl.b.insert(astbl.b.end(), stts.b.begin(), stts.b.end());
    astbl.b.insert(astbl.b.end(), stsc.b.begin(), stsc.b.end());
    astbl.b.insert(astbl.b.end(), stsz.b.begin(), stsz.b.end());
    astbl.b.insert(astbl.b.end(), stco.b.begin(), stco.b.end());
    astbl.end();

    Box smhd("smhd");
    put_full_box_header(smhd.b, 0, 0);
    put_u16be(smhd.b, 0);                       // balance
    put_u16be(smhd.b, 0);                       // reserved
    smhd.end();

    Box aur("url ");
    put_full_box_header(aur.b, 0, 1);           // self-contained
    aur.end();

    Box adref("dref");
    put_full_box_header(adref.b, 0, 0);
    put_u32be(adref.b, 1);
    adref.b.insert(adref.b.end(), aur.b.begin(), aur.b.end());
    adref.end();

    Box adinf("dinf");
    adinf.b.insert(adinf.b.end(), adref.b.begin(), adref.b.end());
    adinf.end();

    Box aminf("minf");
    aminf.b.insert(aminf.b.end(), smhd.b.begin(), smhd.b.end());
    aminf.b.insert(aminf.b.end(), adinf.b.begin(), adinf.b.end());
    aminf.b.insert(aminf.b.end(), astbl.b.begin(), astbl.b.end());
    aminf.end();

    Box ahdlr("hdlr");
    put_full_box_header(ahdlr.b, 0, 0);
    put_u32be(ahdlr.b, 0);                      // pre_defined
    ahdlr.b.insert(ahdlr.b.end(), (const uint8_t*)"soun", (const uint8_t*)"soun" + 4);
    put_u32be(ahdlr.b, 0); put_u32be(ahdlr.b, 0); put_u32be(ahdlr.b, 0);
    const char* snm = "SoundHandler";
    ahdlr.b.insert(ahdlr.b.end(), snm, snm + strlen(snm) + 1);
    ahdlr.end();

    uint64_t a_media = 0;
    for (const auto& e : a_stts_) a_media += (uint64_t)e.first * e.second;
    Box amdhd("mdhd");
    put_full_box_header(amdhd.b, 0, 0);
    put_u32be(amdhd.b, 0); put_u32be(amdhd.b, 0);            // creation / modification
    put_u32be(amdhd.b, ts);
    put_u32be(amdhd.b, (uint32_t)(a_media > 0xFFFFFFFFull ? 0xFFFFFFFFull : a_media));
    put_u16be(amdhd.b, 0x55C4);                              // language 'und'
    put_u16be(amdhd.b, 0);                                   // pre_defined
    amdhd.end();

    Box amdia("mdia");
    amdia.b.insert(amdia.b.end(), amdhd.b.begin(), amdhd.b.end());
    amdia.b.insert(amdia.b.end(), ahdlr.b.begin(), ahdlr.b.end());
    amdia.b.insert(amdia.b.end(), aminf.b.begin(), aminf.b.end());
    amdia.end();

    Box atkhd("tkhd");
    put_full_box_header(atkhd.b, 0, 0x000007);              // enabled | in movie | in preview
    put_u32be(atkhd.b, 0); put_u32be(atkhd.b, 0);           // creation / modification
    put_u32be(atkhd.b, 2);                                  // track_ID (video owns 1)
    put_u32be(atkhd.b, 0);                                  // reserved
    put_u32be(atkhd.b, (uint32_t)(movie_duration > 0xFFFFFFFFull ? 0xFFFFFFFFull : movie_duration));
    put_u32be(atkhd.b, 0); put_u32be(atkhd.b, 0);           // reserved[2]
    put_u16be(atkhd.b, 0);                                  // layer
    put_u16be(atkhd.b, 0);                                  // alternate_group
    put_u16be(atkhd.b, 0x0100);                             // volume, full (audio)
    put_u16be(atkhd.b, 0);                                  // reserved
    put_matrix(atkhd.b);
    put_u32be(atkhd.b, 0);                                  // width  (audio: none)
    put_u32be(atkhd.b, 0);                                  // height
    atkhd.end();

    Box atrak("trak");
    atrak.b.insert(atrak.b.end(), atkhd.b.begin(), atkhd.b.end());
    atrak.b.insert(atrak.b.end(), amdia.b.begin(), amdia.b.end());
    atrak.end();

    out = atrak.b;
    (void)movie_timescale;
    return true;
}

bool Mp4Writer::close(std::string* err)
{
    if (!f_) { *err = "close() called twice"; return false; }
    if (sizes_.empty()) { *err = "refusing to write an MP4 with zero samples"; return false; }

    // Patch the mdat size.  A clip past 4 GiB is REFUSED, not truncated.
    uint64_t mdat_total = mdat_payload_ + 8;
    if (mdat_total > 0xFFFFFFFFull) {
        *err = "clip exceeds the 32-bit mdat limit (4 GiB); refusing rather than writing a corrupt file";
        return false;
    }
    uint8_t szb[4] = { (uint8_t)(mdat_total >> 24), (uint8_t)(mdat_total >> 16),
                       (uint8_t)(mdat_total >> 8),  (uint8_t)mdat_total };
    if (_fseeki64(f_, (long long)mdat_start_, SEEK_SET) != 0) { *err = "seek to mdat header failed"; return false; }
    if (fwrite(szb, 1, 4, f_) != 4) { *err = "mdat size patch failed"; return false; }
    if (_fseeki64(f_, 0, SEEK_END) != 0) { *err = "seek to end failed"; return false; }

    // ---------------- duration
    uint64_t media_duration = 0;
    for (auto& e : stts_) media_duration += (uint64_t)e.first * e.second;
    uint32_t movie_timescale = 1000;
    uint64_t movie_duration = (cfg_.timescale ? (media_duration * movie_timescale / cfg_.timescale) : 0);

    // ---------------- stbl children
    Box stsd("stsd");
    put_full_box_header(stsd.b, 0, 0);
    put_u32be(stsd.b, 1);   // entry_count

    // avc1 VisualSampleEntry
    {
        std::vector<uint8_t> avc1;
        put_u32be(avc1, 0);
        avc1.insert(avc1.end(), (const uint8_t*)"avc1", (const uint8_t*)"avc1" + 4);
        for (int i = 0; i < 6; ++i) avc1.push_back(0);      // reserved
        put_u16be(avc1, 1);                                 // data_reference_index
        put_u16be(avc1, 0); put_u16be(avc1, 0);             // pre_defined, reserved
        put_u32be(avc1, 0); put_u32be(avc1, 0); put_u32be(avc1, 0);   // pre_defined[3]
        put_u16be(avc1, (uint16_t)cfg_.width);
        put_u16be(avc1, (uint16_t)cfg_.height);
        put_u32be(avc1, 0x00480000);                        // 72 dpi
        put_u32be(avc1, 0x00480000);
        put_u32be(avc1, 0);                                 // reserved
        put_u16be(avc1, 1);                                 // frame_count
        for (int i = 0; i < 32; ++i) avc1.push_back(0);     // compressorname
        put_u16be(avc1, 0x0018);                            // depth
        avc1.push_back(0xFF); avc1.push_back(0xFF);         // pre_defined = -1

        // avcC
        std::vector<uint8_t> avcC;
        put_u32be(avcC, 0);
        avcC.insert(avcC.end(), (const uint8_t*)"avcC", (const uint8_t*)"avcC" + 4);
        avcC.push_back(1);                                  // configurationVersion
        avcC.push_back(cfg_.sps[1]);                        // AVCProfileIndication
        avcC.push_back(cfg_.sps[2]);                        // profile_compatibility
        avcC.push_back(cfg_.sps[3]);                        // AVCLevelIndication
        avcC.push_back(0xFF);                               // lengthSizeMinusOne = 3
        avcC.push_back(0xE1);                               // numOfSequenceParameterSets = 1
        put_u16be(avcC, (uint16_t)cfg_.sps.size());
        avcC.insert(avcC.end(), cfg_.sps.begin(), cfg_.sps.end());
        avcC.push_back(1);                                  // numOfPictureParameterSets
        put_u16be(avcC, (uint16_t)cfg_.pps.size());
        avcC.insert(avcC.end(), cfg_.pps.begin(), cfg_.pps.end());
        uint32_t asz = (uint32_t)avcC.size();
        avcC[0] = (uint8_t)(asz >> 24); avcC[1] = (uint8_t)(asz >> 16);
        avcC[2] = (uint8_t)(asz >> 8);  avcC[3] = (uint8_t)asz;

        avc1.insert(avc1.end(), avcC.begin(), avcC.end());
        uint32_t sz2 = (uint32_t)avc1.size();
        avc1[0] = (uint8_t)(sz2 >> 24); avc1[1] = (uint8_t)(sz2 >> 16);
        avc1[2] = (uint8_t)(sz2 >> 8);  avc1[3] = (uint8_t)sz2;
        stsd.b.insert(stsd.b.end(), avc1.begin(), avc1.end());
    }
    stsd.end();

    Box stts("stts");
    put_full_box_header(stts.b, 0, 0);
    put_u32be(stts.b, (uint32_t)stts_.size());
    for (auto& e : stts_) { put_u32be(stts.b, e.first); put_u32be(stts.b, e.second); }
    stts.end();

    // stss is omitted when EVERY sample is a sync sample (that is the legal "all sync").
    std::vector<uint8_t> stss;
    bool need_stss = (sync_numbers_.size() != sizes_.size());
    if (need_stss) {
        Box b("stss");
        put_full_box_header(b.b, 0, 0);
        put_u32be(b.b, (uint32_t)sync_numbers_.size());
        for (uint32_t n : sync_numbers_) put_u32be(b.b, n);
        b.end();
        stss = b.b;
    }

    Box stsc("stsc");
    put_full_box_header(stsc.b, 0, 0);
    put_u32be(stsc.b, 1);
    put_u32be(stsc.b, 1);   // first_chunk
    put_u32be(stsc.b, 1);   // samples_per_chunk — one chunk per sample
    put_u32be(stsc.b, 1);   // sample_description_index
    stsc.end();

    Box stsz("stsz");
    put_full_box_header(stsz.b, 0, 0);
    put_u32be(stsz.b, 0);                       // sample_size = 0 -> sizes follow
    put_u32be(stsz.b, (uint32_t)sizes_.size());
    for (uint32_t s : sizes_) put_u32be(stsz.b, s);
    stsz.end();

    bool use_co64 = false;
    for (uint64_t o : offsets_) if (o > 0xFFFFFFFFull) { use_co64 = true; break; }
    Box stco(use_co64 ? "co64" : "stco");
    put_full_box_header(stco.b, 0, 0);
    put_u32be(stco.b, (uint32_t)offsets_.size());
    for (uint64_t o : offsets_) { if (use_co64) put_u64be(stco.b, o); else put_u32be(stco.b, (uint32_t)o); }
    stco.end();

    // ---------------- stbl / minf / mdia / trak / moov
    Box stbl("stbl");
    stbl.b.insert(stbl.b.end(), stsd.b.begin(), stsd.b.end());
    stbl.b.insert(stbl.b.end(), stts.b.begin(), stts.b.end());
    if (need_stss) stbl.b.insert(stbl.b.end(), stss.begin(), stss.end());
    stbl.b.insert(stbl.b.end(), stsc.b.begin(), stsc.b.end());
    stbl.b.insert(stbl.b.end(), stsz.b.begin(), stsz.b.end());
    stbl.b.insert(stbl.b.end(), stco.b.begin(), stco.b.end());
    stbl.end();

    Box vmhd("vmhd");
    put_full_box_header(vmhd.b, 0, 1);
    put_u16be(vmhd.b, 0);                       // graphicsmode
    put_u16be(vmhd.b, 0); put_u16be(vmhd.b, 0); put_u16be(vmhd.b, 0);   // opcolor
    vmhd.end();

    Box url("url ");
    put_full_box_header(url.b, 0, 1);           // self-contained
    url.end();

    Box dref("dref");
    put_full_box_header(dref.b, 0, 0);
    put_u32be(dref.b, 1);
    dref.b.insert(dref.b.end(), url.b.begin(), url.b.end());
    dref.end();

    Box dinf("dinf");
    dinf.b.insert(dinf.b.end(), dref.b.begin(), dref.b.end());
    dinf.end();

    Box minf("minf");
    minf.b.insert(minf.b.end(), vmhd.b.begin(), vmhd.b.end());
    minf.b.insert(minf.b.end(), dinf.b.begin(), dinf.b.end());
    minf.b.insert(minf.b.end(), stbl.b.begin(), stbl.b.end());
    minf.end();

    Box hdlr("hdlr");
    put_full_box_header(hdlr.b, 0, 0);
    put_u32be(hdlr.b, 0);                       // pre_defined
    hdlr.b.insert(hdlr.b.end(), (const uint8_t*)"vide", (const uint8_t*)"vide" + 4);
    put_u32be(hdlr.b, 0); put_u32be(hdlr.b, 0); put_u32be(hdlr.b, 0);
    const char* nm = "VideoHandler";
    hdlr.b.insert(hdlr.b.end(), nm, nm + strlen(nm) + 1);
    hdlr.end();

    Box mdhd("mdhd");
    put_full_box_header(mdhd.b, 0, 0);
    put_u32be(mdhd.b, 0); put_u32be(mdhd.b, 0);           // creation / modification
    put_u32be(mdhd.b, cfg_.timescale);
    put_u32be(mdhd.b, (uint32_t)(media_duration > 0xFFFFFFFFull ? 0xFFFFFFFFull : media_duration));
    put_u16be(mdhd.b, 0x55C4);                            // language 'und'
    put_u16be(mdhd.b, 0);                                 // pre_defined
    mdhd.end();

    Box mdia("mdia");
    mdia.b.insert(mdia.b.end(), mdhd.b.begin(), mdhd.b.end());
    mdia.b.insert(mdia.b.end(), hdlr.b.begin(), hdlr.b.end());
    mdia.b.insert(mdia.b.end(), minf.b.begin(), minf.b.end());
    mdia.end();

    Box tkhd("tkhd");
    put_full_box_header(tkhd.b, 0, 0x000007);             // enabled | in movie | in preview
    put_u32be(tkhd.b, 0); put_u32be(tkhd.b, 0);           // creation / modification
    put_u32be(tkhd.b, 1);                                 // track_ID
    put_u32be(tkhd.b, 0);                                 // reserved
    put_u32be(tkhd.b, (uint32_t)(movie_duration > 0xFFFFFFFFull ? 0xFFFFFFFFull : movie_duration));
    put_u32be(tkhd.b, 0); put_u32be(tkhd.b, 0);           // reserved[2]
    put_u16be(tkhd.b, 0);                                 // layer
    put_u16be(tkhd.b, 0);                                 // alternate_group
    put_u16be(tkhd.b, 0);                                 // volume (video: 0)
    put_u16be(tkhd.b, 0);                                 // reserved
    put_matrix(tkhd.b);
    put_u32be(tkhd.b, (uint32_t)cfg_.width << 16);
    put_u32be(tkhd.b, (uint32_t)cfg_.height << 16);
    tkhd.end();

    Box trak("trak");
    trak.b.insert(trak.b.end(), tkhd.b.begin(), tkhd.b.end());
    trak.b.insert(trak.b.end(), mdia.b.begin(), mdia.b.end());
    trak.end();

    // ---------------- the audio trak (a SECOND trak in THIS SAME moov, track_ID 2)
    // Built before mvhd, because both movie_duration and next_track_ID depend on it.  A
    // stsd entry_count is per-trak, so the video trak keeps entry_count 1 and the audio
    // trak carries the single mp4a/sowt entry: readers then see TWO traks, ONE video
    // stream + ONE audio stream.
    std::vector<uint8_t> atrak;
    if (!a_sizes_.empty()) {
        if (!build_audio_trak(atrak, movie_timescale, movie_duration, err)) return false;
        // The movie must not be shorter than its own audio: a reader that trusts mvhd
        // would cut the sound short.  Video and audio are padded/trimmed by the CALLER
        // to within 50 ms; this only keeps mvhd from being the thing that stops them.
        uint64_t a_media = 0;
        for (auto& e : a_stts_) a_media += (uint64_t)e.first * e.second;
        uint64_t a_movie = (cfg_.audio.sample_rate
                            ? a_media * movie_timescale / cfg_.audio.sample_rate : 0);
        if (a_movie > movie_duration) movie_duration = a_movie;
    }

    Box mvhd("mvhd");
    put_full_box_header(mvhd.b, 0, 0);
    put_u32be(mvhd.b, 0); put_u32be(mvhd.b, 0);
    put_u32be(mvhd.b, movie_timescale);
    put_u32be(mvhd.b, (uint32_t)(movie_duration > 0xFFFFFFFFull ? 0xFFFFFFFFull : movie_duration));
    put_u32be(mvhd.b, 0x00010000);                        // rate
    put_u16be(mvhd.b, 0x0100);                            // volume
    put_u16be(mvhd.b, 0);                                 // reserved
    put_u32be(mvhd.b, 0); put_u32be(mvhd.b, 0);           // reserved[2]
    put_matrix(mvhd.b);
    for (int i = 0; i < 6; ++i) put_u32be(mvhd.b, 0);     // pre_defined
    put_u32be(mvhd.b, atrak.empty() ? 2u : 3u);            // next_track_ID (1 video, +1 audio)
    mvhd.end();

    Box moov("moov");
    moov.b.insert(moov.b.end(), mvhd.b.begin(), mvhd.b.end());
    moov.b.insert(moov.b.end(), trak.b.begin(), trak.b.end());
    if (!atrak.empty()) moov.b.insert(moov.b.end(), atrak.begin(), atrak.end());
    moov.end();

    if (fwrite(moov.b.data(), 1, moov.b.size(), f_) != moov.b.size()) {
        *err = "moov write failed";
        return false;
    }
    pos_ += moov.b.size();
    fflush(f_);
    fclose(f_);
    f_ = nullptr;
    return true;
}

} // namespace aireplay
