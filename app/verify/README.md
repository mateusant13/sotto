# verify/ — scratch verification harness, NOT part of the app

Created by the M0 build lane because the full Tauri dependency tree could not
be downloaded on this machine, and because cargo was locked out by another
lane's `cargo build --release` for most of the session.

It compiles the **real** files

- `../src-tauri/src/geometry.rs`
- `../src-tauri/src/memory.rs`

via `#[path]`, and runs the `#[test]` blocks that live inside them. Nothing is
copy-pasted: the assertions executed are the product's assertions.

## What a green here proves (executed, not asserted)

- the docking arithmetic in `dock_right`, including the
  work-area-vs-full-screen control and the containment invariant;
- that `memory.rs` compiles **and links**, which is the only way the
  `#[link(name = "psapi")]` import can be proven — a wrong import library fails
  at link time and `cargo check` would not catch it.

## What a green here does NOT prove

- that the real `tauri::window::Monitor` exposes `work_area()`, `size()`,
  `position()` and `scale_factor()`. Those are stubbed in
  `rustc/tauri_stub.rs`, so the harness encodes my *belief* about the API, not
  the API itself.
- anything about `main.rs`, `commands.rs`, the Svelte frontend, the window
  behaviour, or the hotkey.
- `serde` is a **no-op derive stub** (`rustc/fakeserde.rs`) so the sources that
  carry `#[derive(Serialize)]` still compile without the real dependency. The
  tests never serialise, so this changes nothing they assert.

## Defects this harness actually caught

It is worth recording that this was not a rubber stamp. In its first run it
went red on real bugs in product code:

1. `PanelGeometry` derived `Copy` while holding a `String` field — would not
   compile (`E0204`).
2. `memory.rs` did `available: ok != 0` on an already-`bool` value —
   would not compile (`E0308`).
3. The `PANEL_MAX_WORK_FRACTION` cap was applied in **physical** pixels, so a
   HiDPI screen silently shrank the panel. The test comparing 1x and 2x CSS
   sizes went red and exposed it.
4. A zero-width work area produced `window_x = -1`, breaking the containment
   guarantee on degenerate input.

(1) and (2) are compiler errors that would have been caught by any
`cargo check`. (3) and (4) are logic bugs that a compile-only check would have
shipped.

## How it is run (no cargo, no network)

```
set V=H:\sotto\app\verify
rustc --edition 2021 --crate-type rlib      --crate-name tauri  "$V\rustc\tauri_stub.rs"  -o "$V\rustc\out\libtauri.rlib"
rustc --edition 2021 --crate-type proc-macro --crate-name serde  "$V\rustc\fakeserde.rs"  -o "$V\rustc\out\libserde.dll"
rustc --edition 2021 --test                  --crate-name verify "$V\src\lib.rs" ^
  --extern "tauri=$V\rustc\out\libtauri.rlib" --extern "serde=$V\rustc\out\libserde.dll" ^
  -o "$V\rustc\out\verify_tests.exe" -L "$V\rustc\out"
& "$V\rustc\out\verify_tests.exe" --test-threads=1
```

`Cargo.toml` here exists only so the file is recognisable; the cargo path was
never usable because cargo was locked. Logs land in `rustc/out/`.

## Deleting it

Nothing in the app references this directory. Deleting it changes no product
behaviour — it only deletes evidence.