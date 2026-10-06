/**
 * The shape of what Rust sends over IPC.
 *
 * These mirror the `#[serde(rename_all = "camelCase")]` structs in
 * `src-tauri/src/`. They are hand-written rather than generated: M0 has three
 * commands, and a generated type file would be more machinery than the whole
 * contract.
 */

/** `commands::CaptureState` */
export interface CaptureState {
  /** Always false in M0 - there is no audio path yet. */
  active: boolean;
  source: string;
  state: string;
  message: string;
}

/** `geometry::PanelGeometry` */
export interface PanelGeometry {
  workX: number;
  workY: number;
  workWidth: number;
  workHeight: number;
  windowX: number;
  windowY: number;
  windowWidth: number;
  windowHeight: number;
  /** Logical (CSS) pixels - what the panel element lays out in. */
  panelWidth: number;
  panelHeight: number;
  margin: number;
  scaleFactor: number;
  docked: string;
}

/** `memory::MemorySample` */
export interface MemorySample {
  workingSetBytes: number;
  commitBytes: number;
  privateBytes: number;
  pid: number;
  source: string;
  available: boolean;
}