'use strict';

/**
 * Sotto M0 — the preload bridge.
 *
 * This is the whole API surface between the panel page and the main process,
 * and it is the contract a later milestone will feed. Two directions:
 *
 *   main -> page   the caption arrives over IPC and is handed to the callbacks
 *                  registered with `onCaption` / `onStatus` / `onGeometry`.
 *   page -> main   `hide`, `toggle`, `quit`, `pointer` and the `getInfo` invoke.
 *
 * Plus the receiver itself: `pushCaption(text)` and `setStatus(text)` render
 * immediately, so the page's caption area is complete even before any audio
 * pipeline exists.
 *
 * One rule prevents an infinite loop: a caption that came *from* a page is
 * reported to the main process as `*-observed` (a receipt) and never echoed
 * back to the renderer. Only a producer in the main process drives `onCaption`.
 */

const { contextBridge, ipcRenderer } = require('electron');

/** Registered page-side callbacks. Sets, so two panels can both listen. */
const subscribers = {
  caption: new Set(),
  status: new Set(),
  geometry: new Set(),
};

/** Fan out to page callbacks without letting one broken listener stop the rest. */
function emit(kind, payload) {
  const text = typeof payload === 'string' ? payload : JSON.stringify(payload);
  for (const callback of subscribers[kind]) {
    try {
      callback(typeof payload === 'string' ? payload : JSON.parse(text));
    } catch (err) {
      console.error(`sotto: a ${kind} listener threw: ${err && err.message ? err.message : err}`);
    }
  }
}

ipcRenderer.on('sotto:caption', (_event, payload) => emit('caption', payload || {}));
ipcRenderer.on('sotto:status', (_event, text) => emit('status', String(text == null ? '' : text)));
ipcRenderer.on('sotto:geometry', (_event, geometry) => emit('geometry', geometry || {}));

/** Normalise a caption: the pipeline may hand over a non-string. */
function normalise(text, meta) {
  if (text == null) return null;
  const value = String(text).replace(/\s+/g, ' ').trim();
  if (value === '') return null;
  return { text: value, meta: meta && typeof meta === 'object' ? meta : {} };
}

contextBridge.exposeInMainWorld('sotto', {
  // --- the receiver, callable from the page or a console --------------------
  /**
   * Add a caption line to the panel. Returns the number of lines now shown.
   * Safe to call before the panel is listening: the callbacks are invoked as
   * they arrive and the page registers on first paint.
   */
  pushCaption(text, meta) {
    const caption = normalise(text, meta);
    if (!caption) return false;
    ipcRenderer.send('sotto:caption-observed', caption);
    emit('caption', caption);
    return true;
  },

  /** Replace the status line under the panel. */
  setStatus(text) {
    const value = String(text == null ? '' : text);
    ipcRenderer.send('sotto:status-observed', { text: value });
    emit('status', value);
    return true;
  },

  // --- main -> page subscriptions -----------------------------------------
  /** @param {(caption:{text:string,meta:object}) => void} callback */
  onCaption(callback) {
    if (typeof callback !== 'function') return () => {};
    subscribers.caption.add(callback);
    return () => subscribers.caption.delete(callback);
  },
  onStatus(callback) {
    if (typeof callback !== 'function') return () => {};
    subscribers.status.add(callback);
    return () => subscribers.status.delete(callback);
  },
  onGeometry(callback) {
    if (typeof callback !== 'function') return () => {};
    subscribers.geometry.add(callback);
    return () => subscribers.geometry.delete(callback);
  },

  // --- page -> main --------------------------------------------------------
  hide() {
    ipcRenderer.send('sotto:hide');
  },
  toggle() {
    ipcRenderer.send('sotto:toggle');
  },
  quit() {
    ipcRenderer.send('sotto:quit');
  },

  /**
   * Tell the main process the page is interactive over its own controls. The
   * window is click-through by default so the overlay never eats a click meant
   * for the app underneath; this turns interaction on while the pointer is
   * over the panel body and off again when it leaves.
   */
  setPointerInteractive(active) {
    ipcRenderer.send('sotto:pointer', { active: Boolean(active) });
  },

  /** Resolved once with the hotkey, versions and live geometry. */
  getInfo() {
    return ipcRenderer.invoke('sotto:info').catch((err) => ({
      error: err && err.message ? err.message : String(err),
    }));
  },

  // --- renderer's receipts back to main ------------------------------------
  captionApplied(text) {
    ipcRenderer.send('sotto:caption-applied', { text: String(text == null ? '' : text) });
  },
  statusApplied(text) {
    ipcRenderer.send('sotto:status-applied', { text: String(text == null ? '' : text) });
  },
  ready(payload) {
    ipcRenderer.send('sotto:renderer-ready', payload || {});
  },
  clearApplied(remaining) {
    ipcRenderer.send('sotto:caption-cleared', { remaining: Number(remaining) || 0 });
  },

  // --- constants -----------------------------------------------------------
  HOTKEY: 'Alt+C',
  platform: process.platform,
});