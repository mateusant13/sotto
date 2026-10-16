// _ux-cdp.mjs — drive headless Edge over CDP: navigate, override the viewport,
// evaluate a SETUP expression, then a PROBE expression, optionally screenshot.
// Prints ONE JSON object on stdout. Never touches the owner's screen.
//
// usage:
//   node _ux-cdp.mjs --url <fileurl> --w 380 --h 900 --setup setup.js --probe probe.js
//                      [--shot out.png] [--wait 1500] [--probe2 probe2.js]
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const argv = process.argv.slice(2);
const arg = (n, d) => { const i = argv.indexOf(n); return i >= 0 ? argv[i + 1] : d; };
const url = arg('--url');
const W = parseInt(arg('--w', '380'), 10);
const H = parseInt(arg('--h', '900'), 10);
const setupFile = arg('--setup', '');
const probeFile = arg('--probe', '');
const shot = arg('--shot', '');
const waitMs = parseInt(arg('--wait', '1200'), 10);
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const TMP = 'I:/cc-tmp';
const profile = fs.mkdtempSync(path.join(TMP, 'ux-cdp-'));
const PORT = 9340 + (process.pid % 100);

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
const __watchdog = setTimeout(() => {
  console.log(JSON.stringify({ ok: false, error: 'driver watchdog fired (stuck Edge)' }));
  process.exit(0);
}, parseInt(arg('--maxtime', '60000'), 10));

const child = spawn(EDGE, [
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--disable-extensions', '--disable-background-networking',
  '--remote-debugging-port=' + PORT, '--user-data-dir=' + profile,
  '--window-size=' + W + ',' + H, 'about:blank',
], { stdio: 'ignore' });

let ws;
let wsUrl = null;
try {
  for (let i = 0; i < 300; i++) {
    try { const r = await fetch('http://127.0.0.1:' + PORT + '/json/version'); if (r.ok) { const j = await r.json(); wsUrl = j.webSocketDebuggerUrl; break; } } catch (e) {}
    await sleep(100);
  }
  if (!wsUrl) throw new Error('no devtools endpoint on port ' + PORT);

  ws = new WebSocket(wsUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = e => rej(new Error('ws error')); });

  let nextId = 1;
  const pending = new Map();
  const loadWaiters = [];
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id); pending.delete(msg.id);
      if (msg.error) reject(new Error(JSON.stringify(msg.error))); else resolve(msg.result);
    } else if (msg.method === 'Page.loadEventFired') {
      while (loadWaiters.length) loadWaiters.shift()();
    }
  };
  const send = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
    const id = nextId++; pending.set(id, { resolve, reject });
    ws.send(JSON.stringify(sessionId ? { id, method, params, sessionId } : { id, method, params }));
    setTimeout(() => { if (pending.has(id)) { pending.delete(id); reject(new Error('timeout ' + method)); } }, 30000);
  });

  const { targetInfos } = await send('Target.getTargets');
  const page = targetInfos.find(t => t.type === 'page');
  const { sessionId } = await send('Target.attachToTarget', { targetId: page.targetId, flatten: true });

  await send('Page.enable', {}, sessionId);
  await send('Runtime.enable', {}, sessionId);
  await send('Emulation.setDeviceMetricsOverride',
    { width: W, height: H, deviceScaleFactor: 1, mobile: false }, sessionId);

  const loaded = new Promise(res => loadWaiters.push(res));
  await send('Page.navigate', { url }, sessionId);
  await Promise.race([loaded, sleep(15000)]);
  await sleep(waitMs);

  const evl = async (file) => {
    const expr = file ? fs.readFileSync(file, 'utf8') : 'null';
    const r = await send('Runtime.evaluate',
      { expression: expr, awaitPromise: true, returnByValue: true, allowUnsafeEvalBlockedByCSP: true }, sessionId);
    if (r.exceptionDetails) throw new Error('eval: ' + JSON.stringify(r.exceptionDetails).slice(0, 800));
    return r.result.value;
  };

  const setupResult = await evl(setupFile);
  await sleep(400);
  const probe = await evl(probeFile);

  let shotBytes = 0;
  if (shot) {
    const r = await send('Page.captureScreenshot', { format: 'png', fromSurface: true, captureBeyondViewport: false }, sessionId);
    fs.writeFileSync(shot, Buffer.from(r.data, 'base64'));
    shotBytes = fs.statSync(shot).size;
  }

  const metrics = await send('Runtime.evaluate',
    { expression: '({w:innerWidth,h:innerHeight,dpr:devicePixelRatio})', returnByValue: true }, sessionId);
  console.log(JSON.stringify({ ok: true, viewport: metrics.result.value, setup: setupResult, probe, shot, shotBytes }, null, 1));
  await send('Browser.close').catch(() => {});
} catch (e) {
  console.log(JSON.stringify({ ok: false, error: String(e && e.stack || e) }));
} finally {
  try { clearTimeout(__watchdog); } catch {}
  try { if (ws) ws.close(); } catch {}
  try { child.kill('SIGKILL'); } catch {}
  await sleep(300);

  process.exit(0);
}
