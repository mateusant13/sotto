#!/usr/bin/env node
/* cdp.mjs -- THE 380 px INSTRUMENT.
 *
 * WHY THIS FILE EXISTS.
 *
 * The house rule (AGENTS.md, "A SCREENSHOT PROVES COLOUR, NOT COORDINATES") says
 * headless Edge clamps the layout viewport to 492 px on this box, in BOTH
 * --screenshot AND --dump-dom. MEASURED, not assumed, again on 2026-10-20 with
 * the probe in this lane's own log:
 *
 *   --window-size=380,900  -> innerWidth 492
 *   --window-size=520,900  -> innerWidth 496
 *   --window-size=1000,900 -> innerWidth 976
 *   --headless=new and --headless=old: identical numbers
 *
 * i.e. layout_width = max(492, requested - 24) -- the WINDOW's minimum outer
 * width on this box is 516 px and the layout viewport is the window minus 24 px
 * of frame. The panel the owner actually has is 380 px wide
 * (sotto_webview.py PANEL_WIDTH=380), so NOTHING measured in headless Edge
 * describes his window: it describes a 492 px layout cropped to 380. A right
 * edge read from such a picture is 112 px of fiction.
 *
 * THIS FILE MEASURES THE REAL THING. Chrome DevTools Protocol's
 * Emulation.setDeviceMetricsOverride sets the LAYOUT viewport, which is what
 * `vw` units and media queries resolve against, so a 380 px override gives the
 * page the owner's 380 px -- including the `clamp(30px,4.6vw,54px)` caption
 * ramps, which resolve to their FLOOR at 380 and to their MAX at 1280.
 * MEASURED 2026-10-20 through this file: innerWidth 380 at --w 380, 1280 at
 * --w 1280, while the same document through Edge's own --screenshot reports
 * 492.
 *
 * It is a DRIVER, not a build: it launches no vite, no npm, no app, no worker.
 * It only starts a headless Edge with a remote debugging port, which draws
 * nothing on the owner's screen.
 *
 * USAGE -- one page
 *   node _main/_design-lane/cdp.mjs --url file:///... --w 380 --h 900 \
 *        --eval probe.js --shot out.png [--wait 800] [--json out.json] [--key 1]
 *
 * USAGE -- a batch (one browser, many pages; this is what the print driver uses)
 *   node _main/_design-lane/cdp.mjs --jobs jobs.json
 *
 *   a job is { name, url, w, h, keys:["1","2"], out:"x.png", clip:"sel",
 *              dsf:1, wait:1500, eval:"probe.js" }
 */
import { spawn } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync, existsSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';

function arg(name, dflt = null) {
  const i = process.argv.indexOf('--' + name);
  if (i < 0 || i === process.argv.length - 1) return dflt;
  return process.argv[i + 1];
}
const has = (name) => process.argv.includes('--' + name);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function waitForPort(uddir, timeoutMs = 20000) {
  const f = join(uddir, 'DevToolsActivePort');
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    if (existsSync(f)) {
      const txt = readFileSync(f, 'utf8').split(/\r?\n/);
      if (txt[0] && txt[0].trim()) return parseInt(txt[0].trim(), 10);
    }
    await sleep(120);
  }
  throw new Error('cdp.mjs: DevToolsActivePort never appeared');
}

class Cdp {
  constructor(ws) { this.ws = ws; this.id = 0; this.pending = new Map(); this.listeners = []; }
  static async connect(wsUrl) {
    const ws = new WebSocket(wsUrl);
    await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error('ws error')); });
    const c = new Cdp(ws);
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id !== undefined && c.pending.has(msg.id)) {
        const { res, rej } = c.pending.get(msg.id);
        c.pending.delete(msg.id);
        if (msg.error) rej(new Error(msg.error.message + ' ' + JSON.stringify(msg.error)));
        else res(msg.result);
      } else if (msg.method) {
        for (const l of c.listeners) l(msg);
      }
    };
    return c;
  }
  send(method, params = {}, sessionId) {
    const id = ++this.id;
    const payload = { id, method, params };
    if (sessionId) payload.sessionId = sessionId;
    this.ws.send(JSON.stringify(payload));
    return new Promise((res, rej) => {
      this.pending.set(id, { res, rej });
      setTimeout(() => {
        if (this.pending.has(id)) { this.pending.delete(id); rej(new Error('timeout on ' + method)); }
      }, 120000);
    });
  }
  on(fn) { this.listeners.push(fn); }
}

async function pressKey(cdp, sessionId, KEY) {
  /* BOTH `key` AND `code`: the demos switch design on `e.code` ("Digit1".."Digit5")
     and a key event without `code` matches nothing. */
  const code = /^[0-9]$/.test(KEY) ? 'Digit' + KEY
             : /^[a-z]$/.test(KEY) ? 'Key' + KEY.toUpperCase()
             : /^[A-Z]$/.test(KEY) ? 'Key' + KEY
             : KEY;
  const vk = KEY.length === 1 ? KEY.toUpperCase().charCodeAt(0) : 0;
  await cdp.send('Input.dispatchKeyEvent', {
    type: 'keyDown', key: KEY, code, text: KEY.length === 1 ? KEY : undefined,
    windowsVirtualKeyCode: vk,
  }, sessionId);
  await cdp.send('Input.dispatchKeyEvent', {
    type: 'keyUp', key: KEY, code, windowsVirtualKeyCode: vk,
  }, sessionId);
  await sleep(500);
}

async function runJob(cdp, sessionId, job) {
  const W = job.w || 380;
  const H = job.h || 900;
  const DSF = job.dsf || 1;
  const out = { name: job.name, url: job.url, viewport: [W, H], dsf: DSF };

  await cdp.send('Emulation.setDeviceMetricsOverride', {
    width: W, height: H, deviceScaleFactor: DSF, mobile: false,
    screenWidth: W, screenHeight: H,
  }, sessionId);

  const loaded = new Promise((res) => {
    const h = (m) => { if (m.method === 'Page.loadEventFired' && m.sessionId === sessionId) { res(); } };
    cdp.on(h);
  });
  await cdp.send('Page.navigate', { url: job.url }, sessionId);
  await Promise.race([loaded, sleep(20000)]);
  await sleep(job.wait || 1500);

  for (const k of (job.keys || [])) await pressKey(cdp, sessionId, k);
  if (job.keys && job.keys.length) await sleep(job.after || 600);

  if (job.eval) {
    const expr = readFileSync(job.eval, 'utf8');
    const r = await cdp.send('Runtime.evaluate', {
      expression: expr, returnByValue: true, awaitPromise: true,
    }, sessionId);
    out.result = r.exceptionDetails
      ? { error: r.exceptionDetails.text, detail: r.exceptionDetails.exception?.description }
      : r.result.value;
    if (job.outJson) {
      writeFileSync(job.outJson, JSON.stringify(out.result, null, 2));
      out.json = job.outJson;
    }
  }

  if (job.out) {
    const params = { format: 'png', captureBeyondViewport: false, fromSurface: true };
    if (job.clip) {
      /* THE PANEL OF THE DEMO. Two traps, both measured:
         1. the demos show their 380x900 panel SCALED DOWN inside a stage, so a
            straight screenshot of the page is not a picture of the panel at its
            own size -- `dsf` is set to 1/stageScale by the caller, so the PNG
            comes out at the panel's own pixel size with the type rendered at
            that resolution (supersampled, not upscaled);
         2. the panel is VERTICALLY CENTRED in a stage that is taller than the
            viewport, so its rect starts ABOVE the viewport (measured: y = -326
            at 1600x1000). A clip taken from that rect captures the stage, not
            the panel. So the element is scrolled into view FIRST and the rect
            is read again afterwards. */
      const sel = JSON.stringify(job.clip);
      const r = await cdp.send('Runtime.evaluate', {
        expression: `(() => { const e = document.querySelector(${sel});
           if (!e) return null;
           e.scrollIntoView({ block: 'center', inline: 'center' });
           return true; })()`,
        returnByValue: true,
      }, sessionId);
      if (!r.result || !r.result.value) { out.error = 'clip selector not found: ' + job.clip; return out; }
      await sleep(400);
      const r2 = await cdp.send('Runtime.evaluate', {
        expression: `(() => { const e = document.querySelector(${sel});
           const b = e.getBoundingClientRect();
           /* THE CLIP IS IN PAGE COORDINATES, NOT VIEWPORT COORDINATES.
              Page.captureScreenshot takes a rectangle in CSS pixels of the
              DOCUMENT, so a viewport rect has to have the scroll added to it --
              otherwise the print shows whatever is at that offset in the PAGE, which
              is the stage, not the panel. MEASURED 2026-10-20: with the viewport
              rect the clip showed the demo's video frame; with the page rect it
              shows the panel. */
           return { x: b.x + window.scrollX, y: b.y + window.scrollY,
                    width: b.width, height: b.height,
                    vx: b.x, vy: b.y, sx: window.scrollX, sy: window.scrollY }; })()`,
        returnByValue: true,
      }, sessionId);
      const box = r2.result && r2.result.value;
      if (!box) { out.error = 'clip rect not readable: ' + job.clip; return out; }
      params.clip = { x: box.x, y: box.y, width: box.width, height: box.height, scale: 1 };
      params.captureBeyondViewport = true;
      out.clip = { selector: job.clip, box };
    }
    const s = await cdp.send('Page.captureScreenshot', params, sessionId);
    writeFileSync(job.out, Buffer.from(s.data, 'base64'));
    out.shot = job.out;
  }
  return out;
}

(async () => {
  const JOBS_FILE = arg('jobs');
  const jobs = [];
  if (JOBS_FILE) {
    const raw = JSON.parse(readFileSync(JOBS_FILE, 'utf8'));
    const list = Array.isArray(raw) ? raw : (raw.jobs || []);
    for (const j of list) jobs.push(j);
  } else {
    const url = arg('url');
    if (!url) { console.error('cdp.mjs: --url or --jobs is required'); process.exit(2); }
    const job = {
      name: 'single', url,
      w: parseInt(arg('w', '380'), 10), h: parseInt(arg('h', '900'), 10),
      dsf: parseFloat(arg('dsf', '1')),
      wait: parseInt(arg('wait', '900'), 10),
      keys: has('key') ? [arg('key')] : [],
      eval: arg('eval'), out: arg('shot'), outJson: arg('json'),
      clip: arg('clip'),
    };
    jobs.push(job);
  }

  const uddir = mkdtempSync(join(tmpdir(), 'sotto-cdp-'));
  const first = jobs[0];
  const child = spawn(EDGE, [
    '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    '--hide-scrollbars', '--force-device-scale-factor=1', '--disable-extensions',
    '--remote-debugging-port=0', '--user-data-dir=' + uddir,
    '--window-size=' + (first.w || 380) + ',' + (first.h || 900), 'about:blank',
  ], { stdio: 'ignore', windowsHide: true });

  const results = [];
  try {
    const port = await waitForPort(uddir);
    const ver = await (await fetch('http://127.0.0.1:' + port + '/json/version')).json();
    const cdp = await Cdp.connect(ver.webSocketDebuggerUrl);
    const { targetId } = await cdp.send('Target.createTarget', { url: 'about:blank' });
    const { sessionId } = await cdp.send('Target.attachToTarget', { targetId, flatten: true });
    await cdp.send('Page.enable', {}, sessionId);
    await cdp.send('Runtime.enable', {}, sessionId);

    for (const job of jobs) {
      let r;
      try { r = await runJob(cdp, sessionId, job); }
      catch (e) { r = { name: job.name, error: String(e && e.message ? e.message : e) }; }
      results.push(r);
      process.stdout.write((r.error ? 'FAIL ' : 'ok   ') + (job.name || '') +
        (r.error ? ' :: ' + r.error : '') + '\n');
    }
  } catch (e) {
    results.push({ error: String(e && e.message ? e.message : e) });
  } finally {
    try { child.kill(); } catch { /* already gone */ }
    try { rmSync(uddir, { recursive: true, force: true }); } catch { /* best effort */ }
  }

  const text = JSON.stringify({ jobs: results }, null, 2);
  if (arg('json')) writeFileSync(arg('json'), text);
  console.log(text);
  process.exit(results.some((r) => r.error) ? 1 : 0);
})();
