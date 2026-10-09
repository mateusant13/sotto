# receipt-36 — share: export pipeline, upload client, and how a failure is shown

Lane: share/export/upload. Date: 2026-10-07/08.
Paths owned and touched: `src/pipeline/share_export.py`, `src/pipeline/share_upload.py`,
`src/pipeline/share_metadata.py`, `src/pipeline/share_gate.py`, `src/ui/share_dialog.py`,
this receipt. Nothing outside `src/*/share*` was modified.

Gate, one command, both colours, exit code in `$LASTEXITCODE`:

```
python src\pipeline\share_gate.py            # VERDICT PASS, rc=0
```

Last full run: **live arms A–G, 96 checks, all green; control `m1` red on B and C;
control `m2` red on B; every unrelated arm green in both controls; `VERDICT PASS`,
rc=0.** No network, no credentials.

---

## 1. What already existed, and what this lane therefore did NOT build

Checked before writing a line, 2026-10-07:

| what exists | where | consequence for this lane |
|---|---|---|
| an ISO-BMFF muxer | `src/capture/mp4_writer.{h,cpp}` | **not re-implemented.** C++, another lane's files. Its output is already a playable mp4. |
| a clip store with an atomic commit protocol | `src/storage/layout.py` (`.partial` → `key.json.tmp` → `os.replace` → unlink marker, `:397`/`:448-460`) | **reused verbatim.** The share is written by `ClipWriter`, so the "half-written file" failure is prevented by the store's own protocol rather than a new cleanup path that could disagree with it. |
| ffmpeg/ffprobe resolution | `src/pipeline/chain.py:339-343` (PATH, then `H:\ffmpeg\bin`, `C:\ffmpeg\bin`, `C:\ProgramData\chocolatey\bin`) | **mirrored, not imported** — `_tool` is a private method of another lane's class. This is the ONE bounded duplication in the lane: eight lines of path list, not an encoder. Recorded rather than hidden. |
| ffmpeg accepted as a dependency | `chain.py:465-475`, printed as `REAL_SUBSTITUTE` | the export inherits that precedent instead of inventing a policy. |

**So the export is not "encode the clip".** It is the two things a *recorded* clip is not
yet: a faststart file, and a committed share.

## 2. Why faststart is the export's real job

`mp4_writer.h:9` states the shape: `ftyp` + an `mdat` whose payload is appended as samples
arrive, and a `moov` written by `close()`. **DERIVED, not measured** — read from the header
text. A file whose index sits at the end cannot start playing until it has been read to the
end, which is fine locally and useless for an upload someone is watching. `-c copy` moves the
index and re-encodes nothing.

**MEASURED on this host.** `ffmpeg -i IN -c copy -movflags +faststart OUT`, exit code 0.
**Population N=5, window: 5 consecutive exports, 2026-10-08 01:0x UTC**, fixture = a 64×64,
30 fps, 0.5 s `testsrc` clip muxed by ffmpeg, committed through the real `ClipWriter`:

| n | source bytes | share bytes | equal | source box order | share box order | `moov`@ | `mdat`@ | reencoded |
|---|---|---|---|---|---|---|---|---|
| 1 | 6762 | 6762 | yes | ftyp, free, mdat, moov | ftyp, moov, free, mdat | 32 | 902 | false |
| 2 | 6762 | 6762 | yes | ftyp, free, mdat, moov | ftyp, moov, free, mdat | 32 | 902 | false |
| 3 | 6762 | 6762 | yes | ftyp, free, mdat, moov | ftyp, moov, free, mdat | 32 | 902 | false |
| 4 | 6762 | 6762 | yes | ftyp, free, mdat, moov | ftyp, moov, free, mdat | 32 | 902 | false |
| 5 | 6762 | 6762 | yes | ftyp, free, mdat, moov | ftyp, moov, free, mdat | 32 | 902 | false |

5/5: byte count unchanged, `moov` moved from last to offset 32, zero re-encoding.

**The honest limit of that number.** The SOURCE in this measurement is an ffmpeg-muxed file,
not a file produced by `mp4_writer`. What is measured is the relocation step. That the
product's own muxer also emits `moov` last is **DERIVED from `mp4_writer.h:9`** and was NOT
measured on a captured clip, because on this box WGC refuses every item
(`CreateForWindow failed 0x80070005`) and the capture test window is a 4×4 px corner.
**A real captured clip through this export is NOT MEASURED.** The byte-for-byte equality
claim also holds only for the fixture's size; a >4 GiB `mdat` crosses the 32-bit limit that
`mp4_writer.h:10` already refuses at, and that path is untested here.

The gate does not take this on trust: `mp4_box_order()` re-reads the box headers out of the
file the code produced and compares the `moov` and `mdat` offsets. The checker is deliberately
NOT ffprobe — it must not be the thing being checked.

## 3. The upload client — which service, and which API

**YouTube Data API v3, `videos.insert`.** Every parameter below was read from the discovery
document, not recalled:
`https://www.googleapis.com/discovery/v1/apis/youtube/v3/rest`, **revision `20261006`**,
fetched 2026-10-07.

| fact | value | source |
|---|---|---|
| path / method | `youtube/v3/videos`, `POST` | `$d.resources.videos.methods.insert` |
| required query param | `part` (this client sends `part=snippet,status`) | idem |
| scope | `https://www.googleapis.com/auth/youtube.upload` | idem |
| `supportsMediaUpload` | `True` | idem |
| `rootUrl` | `https://youtube.googleapis.com/` | idem |
| `servicePath` | **`''` (empty)** | idem |
| `flatPath` | `youtube/v3/videos` | idem |
| privacy enum | `public`, `unlisted`, `private` | `$d.schemas.VideoStatus.properties.privacyStatus.enum` |
| title/description/tags | `VideoSnippet` properties | `$d.schemas.VideoSnippet.properties` |
| quota | **1600 units per `videos.insert`** | quota doc, own summary: "ranging from 1 for actions such as `list` to 1600 for actions like `videos insert`" |

References: <https://developers.google.com/youtube/v3/docs/videos/insert> ·
<https://developers.google.com/youtube/v3/determine_quota_cost>

**`rootUrl` is `youtube.googleapis.com` and `servicePath` is empty — not `www.googleapis.com`.**
Worth stating because the second host is the one most implementations carry in their heads.

**WHAT IS NOT CLAIMED.** `MEDIA_UPLOAD_URL` is `rootUrl + "upload/" + flatPath`; the `upload/`
infix is Google's documented media-upload convention, and the discovery document supplies the
two halves it is built from. That composition is **DERIVED**, it is a class attribute so a
correction is one edit, and it was **never transmitted** — no credential exists on this box.
An over-long title is likewise not bounded here: the discovery document carries **no
`maxLength`** for `VideoSnippet.title`, so this lane asserts no 100-character limit and lets
the service answer `invalidTitle`, which the client maps to a sentence.

**Quota is a product fact, so it is surfaced.** `describe()` reports the 1600 units; a capture
app that re-uploads on every share spends the day's quota in about nine uploads. That belongs
in front of the user, not in a doc.

## 4. The metadata — and the names I am NOT sure about

`src/index/**` belongs to another lane and was not touched. Read from the live tree,
`src/index/schema.sql:41-63`, the `video` table in full:

> id, content_key, file_key, path, size_bytes, mtime_ns, duration_ms, codec, w, h, fps,
> bitrate, added_at, last_seen_scan, missing, state

**There is no `title` column and no `app`/`game` column.** So:

| field | certainty | where it comes from today |
|---|---|---|
| timestamp | **CONFIRMED** | `key.json.started_at_s` (epoch, UTC), written by `ClipWriter.commit`; the capture instant, not the export instant |
| duration | **CONFIRMED** | `video.duration_ms INTEGER NOT NULL` (`schema.sql:52`) |
| identity | **CONFIRMED** | `video.content_key TEXT NOT NULL UNIQUE, CHECK(length=64)` (`schema.sql:44`) |
| **title** | **PROPOSED — does not exist** | requested from the index lane as `video.title TEXT`. Accepts `title` or `clip_title` (`TITLE_COLUMN_CANDIDATES`) |
| **app** | **PROPOSED — does not exist** | requested as `video.app TEXT`. Accepts `app`/`game`/`source_app`/`app_name` |

Until those columns exist the title is **user-supplied at share time** and persisted in the
share's own `key.json` under `extra={"share": {...}}`, which `ClipWriter.commit` already
accepts. This lane never reads `video.title`.

**The trap worth naming:** the nearest existing field is `key.json.source_device`, which is the
**capture device** (`CutResult`), not the app. Falling back to it would publish
`Monitor 1\DISPLAY1` as a game title. It is carried as a separate field and never used as an
app.

A PROPOSED row never fails the gate — it is a request, not a claim, and a gate that goes red
because another lane has not added a column yet is a gate that gets deleted. ARM F asserts the
opposite: that the CONFIRMED rows still match the live schema, read back from
`schema.sql` at run time rather than trusted from a comment.

## 5. How a failure is shown

**The rule: every state a user can reach has a sentence, and no state renders a raw
exception.** `share_dialog.render()` refuses to interpolate an exception repr, a WinError or
a bare HTTP status; the worst it will show is a bounded redacted detail, and only under
`verbose=True`. `_NEVER_SHOW_RAW` is the denylist and ARM G asserts it.

| state | tone | what the user reads |
|---|---|---|
| `failed` | error | "The upload was interrupted after 2048 of 6762 bytes. **The clip is still on this PC** — nothing was posted." + **Try again** |
| `cancelled` | neutral | "Upload cancelled. **Nothing was posted** — the clip is still on this PC." + **Share it** |
| `refused` | error | "Sign in to YouTube first. Nothing was uploaded." + **Fix and retry** |
| `succeeded` | ok | "Shared." + the URL, and Share is **disabled** |

Two decisions inside that table. A **cancel is not an error** — nothing broke, and painting it
red teaches users to distrust the panel. A **refused** (missing credential) is not a network
hiccup and must not be retried blindly. And the Share button comes back after every failure
except success, because the clip is still on disk and the next move is another attempt.

## 6. Credentials

The owner issued no API keys and none were invented, requested, or written into the repo.
`YOUTUBE_ACCESS_TOKEN` is read in the order: constructor argument → environment variable →
**stop**, raising `CredentialMissing` that names the variable and the scope it needs and
**deliberately carries no value**. Every string leaving `share_upload` passes through
`_redact()`.

ARM E proves the leak path with a token the gate invents (`gate-invented-token-DO-NOT-USE-4f2b`):
the token **is** in the `Authorization` header (it has to be), and a real failed upload whose
transport exception text contains that token produces an `UploadOutcome` whose `detail` and
`user_message` do not. ARM D asserts the refusal is loud, names `YOUTUBE_ACCESS_TOKEN` and
`youtube.upload`, and carries nothing token-shaped. The gate **pops the variable from the
environment for the whole run**, so a green run cannot have borrowed the owner's keys.

## 7. The gate — and the reviewer's doubt

A sibling area's green gate meant "a 9-segment, offset-0 store is correct" while every real
blocker sat outside it. So: **an arm counts only once it has been watched going red.**

| arm | the failure it names | checks |
|---|---|---|
| A | the happy path really works (fake, no network, no credential) | 13 |
| B | **a network-layer failure mid-upload must not report success** | 13 |
| C | **a cancelled upload leaves nothing a later run reads as a finished share** | 12 |
| D | the real client refuses loudly and specifically without a credential | 6 |
| E | the credential appears in the auth header and nowhere else | 13 |
| F | the CONFIRMED metadata fields still match the live schema | 7 |
| G | every state has a sentence and none is an exception dump | 19 |

**Controls — the gate's actual content.** The same evaluation runs against a mutated **copy**:

| control | mutation | must red | observed |
|---|---|---|---|
| `m1` commit-unconditional | `if not self.outcome.ok:` → `if False:` | B, C | **red = B, C**; all others green |
| `m2` network-lies | the fake returns `SUCCEEDED` on the network failure | B | **red = B**; all others green |

**A control that reds everything is as useless as one that stays green**, so the verdict also
requires each control to leave its unrelated arms green, and requires the mutation to be
proven applied (exact match count 1). A control that is red for the wrong reason looks exactly
like evidence — the failure `contracts.py:17` documents from receipt-16 §10.

### Three gate bugs this lane found in ITSELF, kept because they are the point

1. **The control ran the cure.** The child was spawned as `python <ORIGINAL share_gate.py>`
   with `PYTHONPATH` at the mutated tree; the script's own directory won, so the child imported
   the **unmutated** modules. Both controls stayed green and the run reported "the arms are
   robust" when it meant "the mutation never ran". Fixed by running the copy's own gate, and
   the child now reports its `src_root`, which the parent asserts equals the copy — so this
   cannot happen silently again.
2. **The control had the wrong SHAPE.** The copy was flat; product code derives paths from
   `__file__` (`_schema_sql()` walks up two levels and appends `src/index/schema.sql`), so
   `schema.sql` was not found and every CONFIRMED field read as DRIFT — ARM F went red in
   *both* controls for a reason unrelated to the mutation. Fixed by giving the control the
   production shape `<dest>/src/<pkg>`. The gate caught this on its own
   "unrelated arm went red" rule and refused to call the run a pass.
3. **Two arms were wrong, not the product.** ARM E's leak check built a `CredentialMissing` by
   hand *with the token in the message* and then asserted the message did not contain it — a
   self-referential check that could only ever fail, testing a string the arm had just written.
   Replaced with a real failing upload through the real client. And `share_dirs()` matched
   directories whose parent was numeric, which swept in the `clips/2026/10/08` **date**
   directories and asserted they carried a `.partial` marker — the gate was failing on the
   calendar. Both fixed; `layout.CLIP_ID_RE` is now the selector.

Also fixed en route: `verify_index_expectations()` branched on `exp.field == "clip_id"` for a
field named `started_at_s`, so it searched `schema.sql` instead of `layout.py` and reported a
false DRIFT — found by ARM F, which is what a live arm is for.

## 8. Left undone, deliberately

- **No OAuth flow.** Refreshing a token is an authorisation dance this lane has no
  credentials to perform. It takes a token; it does not obtain one.
- **No retry policy in the client.** `retryable` is reported and the job decides. A retry
  belongs where it is known whether the user pressed Share once or twice.
- **No Twitch/Discord client.** The interface is the deliverable; one real implementation and
  one fake were asked for and both exist. A second real service is a second lane's worth of
  spec work, not a stub.
- **`_admit` style pre-flight against the 1600-unit quota** is not implemented; the number is
  surfaced, not enforced.

## 9. Files

| file | what it is |
|---|---|
| `src/pipeline/share_export.py` | the export pipeline on top of `layout.ClipWriter`; `mp4_box_order`/`is_faststart`; `ShareJob` = export → upload → commit-conditioned-on-success |
| `src/pipeline/share_upload.py` | `UploadClient` interface, `UploadOutcome`, `FakeUploadClient`, `YouTubeUploadClient` (resumable), `CredentialMissing`, `_redact` |
| `src/pipeline/share_metadata.py` | `ShareMetadata`, the CONFIRMED/PROPOSED expectations table, `verify_index_expectations()`, `to_youtube_video_resource()` |
| `src/pipeline/share_gate.py` | arms A–G, the two mutation controls, `--json`, `--skip-controls` |
| `src/ui/share_dialog.py` | the headless view model: every state → a sentence, never a raw exception |

Run it: `python src\pipeline\share_gate.py` (rc 0 = pass, 1 = fail).