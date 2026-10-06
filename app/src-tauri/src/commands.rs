//! The IPC surface between Rust and the panel.
//!
//! These three commands are the whole contract between the shell and the
//! frontend in M0. Later milestones change what Rust *says*, not how the
//! panel asks.

use serde::Serialize;

use crate::{geometry, memory};

/// What the panel renders from.
///
/// M0 has no audio path, so `active` is always false. The command exists so
/// the panel binds to real state now: M1 turns this on instead of the panel
/// being rewritten around a new shape.
#[derive(Debug, Clone, Copy, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CaptureState {
    pub active: bool,
    /// Where the answer came from. `"m0-no-capture"` is not a stub value, it
    /// is the true state of M0: there is no capture.
    pub source: &'static str,
    /// `"idle"` until M1 gives it a second value.
    pub state: &'static str,
    /// The empty-state line the panel shows.
    pub message: &'static str,
}

/// Reports whether capture is active. Always false in M0.
#[tauri::command]
pub fn capture_state() -> CaptureState {
    CaptureState {
        active: false,
        source: "m0-no-capture",
        state: "idle",
        message: "Waiting for audio",
    }
}

/// The docked panel's geometry: work area, panel size, window placement.
#[tauri::command]
pub fn panel_geometry(panel: tauri::WebviewWindow) -> Result<geometry::PanelGeometry, String> {
    geometry::dock(&panel).ok_or_else(|| "no monitor reported for the overlay".to_string())
}

/// This process's resident working set, sampled now.
#[tauri::command]
pub fn idle_rss() -> memory::MemorySample {
    memory::sample()
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The empty state must look empty. A `capture_state()` that ever returned
    /// `true` in M0 would be a fabricated transcript waiting to happen.
    #[test]
    fn capture_is_inactive_in_m0() {
        let s = capture_state();
        assert!(!s.active);
        assert_eq!(s.state, "idle");
        assert_eq!(s.source, "m0-no-capture");
        assert_eq!(s.message, "Waiting for audio");
    }
}