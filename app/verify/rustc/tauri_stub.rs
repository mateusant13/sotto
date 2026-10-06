//! A stand-in for the `tauri` crate, used ONLY by the rustc-only verification
//! path in this directory.
//!
//! It provides the exact slice of the window/monitor surface that
//! `geometry.rs` touches, so the real file can be compiled and its real tests
//! run on a machine where cargo is locked by another build and the real Tauri
//! dependency tree cannot be downloaded.
//!
//! It is NOT part of the app, and it is NOT evidence that the real
//! `tauri::window::Monitor` has these methods. See ../README.md.

#![allow(dead_code)]

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct PhysicalSize {
    pub width: u32,
    pub height: u32,
}

impl PhysicalSize {
    pub fn new(width: u32, height: u32) -> Self {
        Self { width, height }
    }
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct PhysicalPosition {
    pub x: i32,
    pub y: i32,
}

impl PhysicalPosition {
    pub fn new(x: i32, y: i32) -> Self {
        Self { x, y }
    }
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Rect {
    pub position: PhysicalPosition,
    pub size: PhysicalSize,
}

#[derive(Debug, Clone, Copy, Default, PartialEq)]
pub struct Monitor {
    pub work: Option<Rect>,
}

impl Monitor {
    pub fn scale_factor(&self) -> f64 {
        1.0
    }

    pub fn size(&self) -> PhysicalSize {
        self.work
            .map(|r| r.size)
            .unwrap_or(PhysicalSize::new(1920, 1080))
    }

    pub fn position(&self) -> PhysicalPosition {
        self.work
            .map(|r| r.position)
            .unwrap_or(PhysicalPosition::new(0, 0))
    }

    pub fn work_area(&self) -> Option<Rect> {
        self.work
    }
}

#[derive(Debug, Clone, Copy, Default, PartialEq)]
pub struct TauriError;

impl std::fmt::Display for TauriError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "stub tauri error")
    }
}

impl std::error::Error for TauriError {}

pub type Result<T> = std::result::Result<T, TauriError>;

#[derive(Debug, Clone, Copy, Default, PartialEq)]
pub struct WebviewWindow {
    pub monitor: Option<Monitor>,
}

impl WebviewWindow {
    pub fn current_monitor(&self) -> Result<Option<Monitor>> {
        Ok(self.monitor)
    }

    pub fn primary_monitor(&self) -> Result<Option<Monitor>> {
        Ok(self.monitor)
    }

    pub fn set_size(&self, _size: PhysicalSize) -> Result<()> {
        Ok(())
    }

    pub fn set_position(&self, _position: PhysicalPosition) -> Result<()> {
        Ok(())
    }
}