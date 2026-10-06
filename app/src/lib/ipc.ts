/**
 * The three IPC calls Sotto M0 makes. One place, so the panel never invents an
 * `invoke` string of its own.
 */

import { invoke } from '@tauri-apps/api/core';

import type { CaptureState, MemorySample, PanelGeometry } from './types';

/** Is the machine being listened to right now? */
export function captureState(): Promise<CaptureState> {
  return invoke<CaptureState>('capture_state');
}

/** The docked panel's geometry, computed in Rust. */
export function panelGeometry(): Promise<PanelGeometry> {
  return invoke<PanelGeometry>('panel_geometry');
}

/** This process's resident working set, sampled now. */
export function idleRss(): Promise<MemorySample> {
  return invoke<MemorySample>('idle_rss');
}