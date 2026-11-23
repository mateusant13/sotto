/* The temp root a browser fixture should use is CHOSEN BY MEASURED COST, not by
 * `os.tmpdir()` existing.
 *
 * Why this file exists (measured 2026-11-23). Two drills -- `panel-themes` and
 * `panel-history-clip` -- build a copy of `app/panel` and launch Playwright with
 * a profile under `os.tmpdir()`. On this box `os.tmpdir()` answers
 * `I:\cc-tmp` from the shell and `G:\watcher-state\cache\tmp` under the battery's
 * cage, and the two volumes cost very different things for the same work:
 *
 *   volume (2026-11-23)                stat()      read 4 KiB
 *   H:\cc-tmp                          0.016 ms    0.037 ms
 *   G:\watcher-state\cache\tmp         0.047 ms    0.069 ms
 *   I:\cc-tmp                          8.022 ms    0.068 ms      <-- 500x stat
 *
 * Deep on `I:` the same drill measured 44.1 s against a 9.0 s baseline and the
 * panel-themes negative arm spent 192.67 s before a `page.goto` timed out. A
 * fixture that copies 2 882 files and stats each of them pays that 500x per file,
 * so the choice is not cosmetic. This is the same defect `sotto-state-page.py`
 * already carries a cure for (a temp root picked by EXISTENCE), and the same
 * policy fixes it here: probe the candidates with the operations the fixture
 * performs, print the numbers, use the cheapest.
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

export function fixtureTempRoot(tag = 'FIXTURE') {
  const seen = [];
  const candidates = [];
  const push = (p) => {
    if (!p) return;
    const abs = path.resolve(p);
    if (!candidates.includes(abs)) candidates.push(abs);
  };
  push(process.env.TMPDIR);
  push(os.tmpdir());
  push(path.join(path.parse(REPO).root, 'cc-tmp'));

  let best = null;
  let bestMs = null;
  const detail = [];
  for (const cand of candidates) {
    let ms = null;
    try {
      fs.mkdirSync(cand, { recursive: true });
      const dir = fs.mkdtempSync(path.join(cand, '.fixture-probe-'));
      const files = [];
      for (let i = 0; i < 40; i += 1) {
        const p = path.join(dir, `p${i}.bin`);
        fs.writeFileSync(p, 'x'.repeat(4096));
        files.push(p);
      }
      /* BEST OF TWO, because the first pass on a volume pays its own cold
       * metadata cache: measured 2026-11-23, the same volume answered 0.032 ms
       * per op on one run and 0.103 ms on the next, and a single sample chose
       * the slower volume. Two passes and the minimum ends the argument. */
      let best = null;
      for (let pass = 0; pass < 2; pass += 1) {
        const t0 = process.hrtime.bigint();
        for (let round = 0; round < 5; round += 1) {
          for (const p of files) fs.statSync(p);
        }
        for (const p of files) fs.readFileSync(p);
        const one = Number(process.hrtime.bigint() - t0) / 1e6 / (40 * 6);
        if (best === null || one < best) best = one;
      }
      ms = best;
      fs.rmSync(dir, { recursive: true, force: true });
    } catch (err) {
      ms = null;
    }
    detail.push(`${cand}=${ms === null ? 'ERR' : ms.toFixed(3)}`);
    seen.push({ cand, ms });
    if (ms !== null && (bestMs === null || ms < bestMs)) {
      best = cand;
      bestMs = ms;
    }
  }
  const chosen = best || os.tmpdir();
  /* Set all three names Node and Playwright consult, so the profile and the
   * copies land together on the volume that was actually measured. */
  process.env.TMPDIR = chosen;
  process.env.TMP = chosen;
  process.env.TEMP = chosen;
  console.log('%s TMPROOT chosen=%s per-op-ms=%s candidates=%s',
    tag, chosen, bestMs === null ? 'n/a' : bestMs.toFixed(3), detail.join(', '));
  return chosen;
}

export default fixtureTempRoot;
