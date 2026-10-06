//! Verification harness for the two modules that do not need a window.
//!
//! The real sources are pulled in with `#[path]`, so the tests executed are
//! the tests that live in `src-tauri/src/`. See ../README.md for exactly what
//! a green here does and does not prove.
//!
//! Compiled in two steps because `geometry.rs` and `memory.rs` `use` external
//! crates:
//!
//!   1. `rustc --crate-type rlib --crate-name tauri tauri_stub.rs`
//!   2. `rustc --crate-type proc-macro --crate-name serde fakeserde.rs`
//!   3. `rustc --test --extern tauri=... --extern serde=... src/lib.rs`
//!
//! (b) is a no-op derive; (a) is a stub. Neither is product code.

#[path = "../../src-tauri/src/geometry.rs"]
pub mod geometry;

#[path = "../../src-tauri/src/memory.rs"]
pub mod memory;

/// Smoke test that the two modules are actually linked into this binary.
/// Without this, a `cargo test` run that filtered everything out could report
/// green while testing nothing.
#[cfg(test)]
mod harness_is_wired {
    use super::*;

    #[test]
    fn geometry_and_memory_are_compiled_into_this_crate() {
        let work = geometry::ScreenRect { x: 0.0, y: 0.0, width: 1920.0, height: 1040.0 };
        let g = geometry::dock_right(work, 1.0);
        assert_eq!(g.docked, "right");
        assert!(memory::sample().available, "the memory probe must run here");
    }

    #[test]
    fn the_stub_monitor_reports_a_work_area() {
        // Guards the harness itself: if the stub stopped exposing work_area(),
        // the geometry tests above would silently stop proving anything.
        let monitor = tauri_stub_monitor();
        assert_eq!(monitor.work_area().map(|r| r.size.height), Some(1040));
    }

    fn tauri_stub_monitor() -> tauri::Monitor {
        tauri::Monitor {
            work: Some(tauri::Rect {
                position: tauri::PhysicalPosition::new(0, 0),
                size: tauri::PhysicalSize::new(1920, 1040),
            }),
        }
    }
}