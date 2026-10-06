//! Sotto M0 - the shell.
//!
//! A frameless, transparent, always-on-top overlay docked to the right edge of
//! the screen, toggled by a **global** Alt+C. No audio, no model, no transcript.
//! M0's only job is to exist measurably: it opens, it toggles, and it has an
//! idle resident-memory baseline to be compared against later.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod geometry;
mod memory;

use tauri::{App, Manager, WebviewWindow};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutEvent, ShortcutState};

/// Label of the overlay window. Must match `app.windows[].label` in
/// `tauri.conf.json`; if they drift, the hotkey has nothing to toggle.
pub const PANEL_LABEL: &str = "overlay";

/// The global toggle. Global rather than window-local is the whole point: the
/// panel is hidden most of the time, so a hotkey that only worked while the
/// panel had focus would never fire.
pub const HOTKEY: &str = "Alt+C";

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .invoke_handler(tauri::generate_handler![
            commands::capture_state,
            commands::panel_geometry,
            commands::idle_rss,
        ])
        .setup(setup)
        .run(tauri::generate_context!())
        .expect("sotto: failed to start");
}

fn setup(app: &mut App) -> Result<(), Box<dyn std::error::Error>> {
    // 1. Dock the panel before the first paint, so it never appears in the
    //    wrong place and then slides there.
    match app.get_webview_window(PANEL_LABEL) {
        Some(panel) => match geometry::dock(&panel) {
            Some(geo) => {
                println!("sotto: {}", geo.summary());
                if let Err(e) = geometry::apply(&panel, &geo) {
                    // A window that failed to move still runs; say so loudly
                    // rather than pretending the panel is docked.
                    eprintln!("sotto: could not dock the panel: {e}");
                }
            }
            None => eprintln!("sotto: no monitor reported; the panel is NOT docked"),
        },
        None => eprintln!("sotto: window '{PANEL_LABEL}' is missing from tauri.conf.json"),
    }

    // 2. Register the global hotkey with its handler in one call.
    app.global_shortcut()
        .on_shortcut(HOTKEY, |app, _shortcut, event: ShortcutEvent| {
            // Alt+C fires on press AND release; only act on one of them.
            if event.state() != ShortcutState::Pressed {
                return;
            }
            match app.get_webview_window(PANEL_LABEL) {
                Some(panel) => toggle(&panel),
                None => eprintln!("sotto: {HOTKEY} fired but window '{PANEL_LABEL}' is gone"),
            }
        })?;

    // 3. Check the registration instead of asserting it. Another app may own
    //    Alt+C, and a hotkey that silently did not register is a hotkey that
    //    does not work.
    if app.global_shortcut().is_registered(HOTKEY) {
        println!("sotto: global shortcut {HOTKEY} registered = true");
    } else {
        return Err(format!("global shortcut {HOTKEY} did not register (is it owned by another app?)").into());
    }

    // The idle baseline is sampled at startup so a number exists even if
    // nothing ever calls the IPC command.
    println!("sotto: idle baseline {}", memory::sample().working_set_kib());
    Ok(())
}

/// Show the panel if it is hidden, hide it if it is shown.
fn toggle(panel: &WebviewWindow) {
    match panel.is_visible() {
        Ok(true) => {
            if let Err(e) = panel.hide() {
                eprintln!("sotto: hide failed: {e}");
            }
        }
        Ok(false) => {
            if let Err(e) = panel.show() {
                eprintln!("sotto: show failed: {e}");
            }
            // Show alone leaves the panel behind whatever has focus; the
            // toggle is only useful if the panel can be interacted with.
            if let Err(e) = panel.set_focus() {
                eprintln!("sotto: focus failed: {e}");
            }
        }
        Err(e) => eprintln!("sotto: visibility query failed: {e}"),
    }
}