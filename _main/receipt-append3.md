

## 2026-10-06 04:56Z — SHELL DECISION (owner asked: "oq e melhor q electron e leve?" / "tem que ser bonito")

Measured, same day, same machine:
| term | size |
|---|---|
| Electron shell (bundled browser engine) | **213 947 904 B** (`app/node_modules/electron/dist/electron.exe`) |
| ASR worker RSS, idle contract | **2 141.7 MB** (`peak_rss_mb` in the worker's own final stats) |
| ratio | the model costs ~10x the shell |

Tauri is DEAD on this host, and it was measured, not assumed (commit `460125a`):
`cargo` sat 12+ min on "Updating crates.io index" with CPU frozen at 0.203125 across
three 15 s samples while `curl.exe` fetched the same URLs with HTTP 200 in 0.209 s; the
msvc nightly hangs identically. `ctranslate2` also hangs at import, which is why the ASR
route is ONNX Runtime.

DECISION: **keep Electron for now.** A WebView2 port saves ~214 MB of a ~2.4 GB process
(the engine is 9% of the footprint — the model is 89%), and it costs a shell rewrite plus
a new process model, right when Alt+C has only just been proven to register. The look the
owner asked for is already HTML/CSS in `panel.html`/`panel.css`, which renders identically
under WebView2 — so the swap stays CHEAP and can land later without touching the UI.
Revisit when the panel's own cost, not the model's, is the binding constraint.
