//! Panel geometry: the numbers a docked overlay needs, computed once, in Rust.
//!
//! Why this is not CSS: a docked panel has to respect the **work area** - the
//! screen minus the taskbar. CSS cannot see the work area, and guessing it is
//! how a panel ends up a taskbar-height off the bottom of the screen. The
//! `dock_right` core is a pure function so it can be tested without a window.

use serde::Serialize;
use tauri::{PhysicalPosition, PhysicalSize, WebviewWindow};

/// Panel content width, in logical (CSS) pixels.
pub const PANEL_WIDTH: f64 = 360.0;

/// Transparent breathing room between the panel and the transparent window
/// edge, in logical pixels. Without it the panel's rounded corners are clipped
/// by the window rectangle.
pub const PANEL_MARGIN: f64 = 10.0;

/// The panel never takes more than this fraction of the work-area width.
pub const PANEL_MAX_WORK_FRACTION: f64 = 0.34;

/// A rectangle in physical pixels, kept free of Tauri types so the arithmetic
/// can be unit-tested on its own.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct ScreenRect {
    pub x: f64,
    pub y: f64,
    pub width: f64,
    pub height: f64,
}

/// Every number the panel needs, in one serialisable payload.
///
/// Window coordinates are **physical** pixels (what the window API takes);
/// panel dimensions are **logical** pixels (what the webview lays out in).
#[derive(Debug, Clone, Copy, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PanelGeometry {
    pub work_x: f64,
    pub work_y: f64,
    pub work_width: f64,
    pub work_height: f64,
    pub window_x: f64,
    pub window_y: f64,
    pub window_width: f64,
    pub window_height: f64,
    pub panel_width: f64,
    pub panel_height: f64,
    pub margin: f64,
    pub scale_factor: f64,
    /// Which edge the panel is docked to. A string, not an enum, so a later
    /// milestone can add `"left"` without breaking the frontend's type.
    pub docked: &'static str,
}

impl PanelGeometry {
    /// One line for the startup receipt. Debug builds keep a console, so this
    /// is how the docking numbers get observed without a screenshot.
    pub fn summary(&self) -> String {
        format!(
            "docked={} work={:.0}x{:.0}@({:.0},{:.0}) window={:.0}x{:.0}@({:.0},{:.0}) \
             panel={:.0}x{:.0}css margin={:.0} scale={:.2}",
            self.docked,
            self.work_width,
            self.work_height,
            self.work_x,
            self.work_y,
            self.window_width,
            self.window_height,
            self.window_x,
            self.window_y,
            self.panel_width,
            self.panel_height,
            self.margin,
            self.scale_factor
        )
    }
}

/// Dock the panel to the **right edge** of `work`.
///
/// The window spans the full work-area height and is inset horizontally by
/// [`PANEL_MARGIN`]; the panel element inside the webview is inset by the same
/// margin via CSS, which is why the panel keeps its rounded corners.
///
/// The output is always contained in `work`, whatever `work` is - including
/// degenerate rectangles.
pub fn dock_right(work: ScreenRect, scale_factor: f64) -> PanelGeometry {
    let scale = if scale_factor.is_finite() && scale_factor > 0.0 {
        scale_factor
    } else {
        1.0
    };

    // Work area in CSS pixels. The caps below are applied in LOGICAL space on
    // purpose: applied to physical pixels, a HiDPI screen silently shrinks the
    // panel, because the same work area is fewer CSS pixels wide.
    let work_width_css = work.width / scale;
    let work_height_css = work.height / scale;

    // A margin that leaves the panel no room to live in is a margin that must
    // shrink before anything else does.
    let margin = PANEL_MARGIN
        .min(work_width_css / 8.0)
        .min(work_height_css / 8.0)
        .max(0.0);

    // A panel wider than its share of the work area is a mistake, not a layout.
    let max_panel_css = (work_width_css * PANEL_MAX_WORK_FRACTION).max(0.0);
    let panel_width = PANEL_WIDTH.min(max_panel_css);
    let panel_height = (work_height_css - 2.0 * margin).max(0.0);

    // Physical again, because that is what the window API takes.
    let window_width = ((panel_width + 2.0 * margin) * scale).min(work.width.max(0.0));
    let window_height = (work_height_css * scale).min(work.height.max(0.0));

    PanelGeometry {
        work_x: work.x,
        work_y: work.y,
        work_width: work.width,
        work_height: work.height,
        // Flush to the right edge of the work area, never past it.
        window_x: work.x + work.width - window_width,
        window_y: work.y,
        window_width,
        window_height,
        panel_width,
        panel_height,
        margin,
        scale_factor: scale,
        docked: "right",
    }
}

/// Read the geometry for `panel`'s monitor, then apply it to the window.
///
/// Returns `None` when the platform reports no monitor at all, which is a
/// state worth distinguishing from "geometry is zero".
pub fn dock(panel: &WebviewWindow) -> Option<PanelGeometry> {
    let monitor = panel
        .current_monitor()
        .ok()
        .flatten()
        .or_else(|| panel.primary_monitor().ok().flatten())?;

    let scale = monitor.scale_factor();
    let size = monitor.size();
    let position = monitor.position();

    let screen = ScreenRect {
        x: position.x as f64,
        y: position.y as f64,
        width: size.width as f64,
        height: size.height as f64,
    };

    // The work area is the screen minus the taskbar.
    //
    // TAURI 2 API CHANGE (measured 2026-10-07, `cargo build` error E0308 x2):
    // in Tauri 1 `Monitor::work_area()` returned `Option<Rect>`, so this arm
    // matched `Some(area) / None`. In Tauri 2 it returns `&PhysicalRect`
    // DIRECTLY - there is no None arm, because the platform always reports one.
    // Matching it as an Option is what broke the build; the fallback below is
    // therefore kept for a degenerate zero-sized rect, not for None.
    let area = monitor.work_area();
    let work = if area.size.width > 0 && area.size.height > 0 {
        ScreenRect {
            x: area.position.x as f64,
            y: area.position.y as f64,
            width: area.size.width as f64,
            height: area.size.height as f64,
        }
    } else {
        // A platform that reports no usable work area gets the full monitor
        // rect, and the number stays traceable to `screen`.
        screen
    };

    Some(dock_right(work, scale))
}

/// Move and resize `panel` to match `geometry`.
pub fn apply(panel: &WebviewWindow, geometry: &PanelGeometry) -> Result<(), String> {
    let size = PhysicalSize::new(
        geometry.window_width.round().max(1.0) as u32,
        geometry.window_height.round().max(1.0) as u32,
    );
    let position = PhysicalPosition::new(
        geometry.window_x.round() as i32,
        geometry.window_y.round() as i32,
    );

    panel
        .set_size(size)
        .map_err(|e| format!("set_size {size:?} failed: {e}"))?;
    panel
        .set_position(position)
        .map_err(|e| format!("set_position {position:?} failed: {e}"))?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    const EPS: f64 = 0.5;

    /// 1080p screen with a 40 px taskbar docked at the bottom.
    fn work_area() -> ScreenRect {
        ScreenRect {
            x: 0.0,
            y: 0.0,
            width: 1920.0,
            height: 1040.0,
        }
    }

    #[test]
    fn docks_flush_to_the_right_edge_of_the_work_area() {
        let g = dock_right(work_area(), 1.0);
        assert!(
            (g.window_x + g.window_width - (g.work_x + g.work_width)).abs() < EPS,
            "panel must sit flush against the right edge, got {}",
            g.summary()
        );
        assert_eq!(g.docked, "right");
    }

    /// The control that catches the off-by-a-taskbar-height bug: dock against
    /// the work area and against the full screen, and the two must differ.
    #[test]
    fn uses_the_work_area_not_the_full_screen() {
        let screen = ScreenRect {
            width: 1920.0,
            height: 1080.0,
            ..work_area()
        };

        let from_work = dock_right(work_area(), 1.0);
        let from_screen = dock_right(screen, 1.0);

        assert_eq!(from_work.window_height, 1040.0, "{}", from_work.summary());
        assert_eq!(from_screen.window_height, 1080.0);
        assert!(
            from_work.window_height < from_screen.window_height,
            "a taskbar must shrink the panel; it did not"
        );
    }

    #[test]
    fn always_stays_inside_the_work_area() {
        for work in [
            work_area(),
            ScreenRect { x: 1920.0, y: -200.0, width: 1280.0, height: 1024.0 },
            ScreenRect { x: 0.0, y: 0.0, width: 320.0, height: 480.0 },
            ScreenRect { x: 0.0, y: 0.0, width: 1.0, height: 1.0 },
            ScreenRect { x: 0.0, y: 0.0, width: 0.0, height: 0.0 },
        ] {
            for scale in [0.5, 1.0, 1.25, 2.0] {
                let g = dock_right(work, scale);
                let msg = g.summary();
                assert!(g.window_x >= work.x - EPS, "left edge outside: {msg}");
                assert!(g.window_y >= work.y - EPS, "top edge outside: {msg}");
                assert!(
                    g.window_x + g.window_width <= work.x + work.width + EPS,
                    "right edge outside: {msg}"
                );
                assert!(
                    g.window_y + g.window_height <= work.y + work.height + EPS,
                    "bottom edge outside: {msg}"
                );
                assert!(g.window_width.is_finite() && g.window_height.is_finite());
            }
        }
    }

    #[test]
    fn panel_content_keeps_its_width_and_the_margin() {
        let g = dock_right(work_area(), 1.0);
        assert_eq!(g.panel_width, PANEL_WIDTH);
        assert_eq!(g.margin, PANEL_MARGIN);
        assert_eq!(g.window_width, PANEL_WIDTH + 2.0 * PANEL_MARGIN);
        assert_eq!(g.panel_height, 1040.0 - 2.0 * PANEL_MARGIN);
    }

    #[test]
    fn a_hidpi_screen_doubles_the_physical_window() {
        // 3840x2080 physical at scale 2 is the SAME 1920x1040 CSS work area as
        // the 1x case above. If the panel changed CSS size here, the geometry
        // would be DPI-dependent - which is the bug this catches.
        let hidpi_work = ScreenRect { x: 0.0, y: 0.0, width: 3840.0, height: 2080.0 };
        let at_1x = dock_right(work_area(), 1.0);
        let at_2x = dock_right(hidpi_work, 2.0);

        assert_eq!(at_2x.panel_width, at_1x.panel_width, "CSS panel width must not depend on DPI");
        assert_eq!(at_2x.panel_width, PANEL_WIDTH);
        assert_eq!(at_2x.window_width, (PANEL_WIDTH + 2.0 * PANEL_MARGIN) * 2.0);
        assert_eq!(at_2x.window_height, 2080.0);
        assert_eq!(at_2x.window_x, 3840.0 - 760.0);
    }

    #[test]
    fn a_hidpi_screen_does_not_shrink_the_panel_below_its_share() {
        // 1920 physical at scale 2 is only 960 CSS px wide, so the share cap is
        // genuinely smaller there - and it must be judged in CSS pixels.
        let g = dock_right(work_area(), 2.0);
        assert_eq!(g.panel_width, 960.0 * PANEL_MAX_WORK_FRACTION);
        assert!(g.window_width <= 1920.0, "{}", g.summary());
    }

    #[test]
    fn a_narrow_screen_shrinks_the_panel_instead_of_overflowing() {
        let narrow = ScreenRect { x: 0.0, y: 0.0, width: 320.0, height: 800.0 };
        let g = dock_right(narrow, 1.0);
        assert!(g.window_width <= 320.0, "{}", g.summary());
        assert!(
            g.panel_width <= 320.0 * PANEL_MAX_WORK_FRACTION + PANEL_MARGIN,
            "panel ate the screen: {}",
            g.summary()
        );
        assert!(g.panel_width > 0.0);
    }

    #[test]
    fn an_absurd_scale_factor_does_not_produce_nonsense() {
        let g = dock_right(work_area(), 0.0);
        assert_eq!(g.scale_factor, 1.0, "a zero scale must fall back to 1");
        assert!(g.window_width.is_finite());
    }
}