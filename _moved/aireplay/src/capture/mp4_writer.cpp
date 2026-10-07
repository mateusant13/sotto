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
    put_u32be(mvhd.b, 2);                                 // next_track_ID
    mvhd.end();

    Box moov("moov");
    moov.b.insert(moov.b.end(), mvhd.b.begin(), mvhd.b.end());
    moov.b.insert(moov.b.end(), trak.b.begin(), trak.b.end());
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
