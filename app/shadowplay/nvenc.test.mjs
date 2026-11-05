// These tests invoke the REAL ffmpeg and the REAL GPU. If they are skipped, it is
// because ffmpeg is absent, not because the model is convenient.
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, existsSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { NvencEncoder, NVENC } from "./nvenc.js";

let passed = 0, failed = 0, skipped = 0;
function t(name, fn) {
  try { fn(); passed++; console.log("  PASS " + name); }
  catch (e) { failed++; console.log("  FAIL " + name + " :: " + e.message); }
}

const hasFfmpeg = (() => {
  try { execFileSync("ffmpeg", ["-version"], { windowsHide: true, stdio: "ignore" }); return true; }
  catch { return false; }
})();

const dir = mkdtempSync(join(tmpdir(), "sp-nvenc-"));
try {
  const enc = new NvencEncoder({ preset: "p1" });

  if (!hasFfmpeg) {
    skipped++;
    console.log("  SKIP real-encoder tests: ffmpeg not on PATH");
  } else {
    t("the default GOP is the measured 250, not an assumption", () => {
      assert.equal(enc.gop, 250);
    });

    t("the real GPU encodes a real desktop capture", () => {
      const out = join(dir, "cap.mp4");
      const r = enc.captureAndEncode(out, { fps: 30, seconds: 2 });
      assert.ok(existsSync(out));
      assert.ok(r.bytes > 0, "no bytes were produced");
      assert.ok(r.ms > 0);
      assert.equal(r.codec, NVENC);
    });

    t("the GOP read back is the REAL one, and -g is only a hint", () => {
      // I asked for -g 250 and measured 287. NVENC inserts keyframes of its own,
      // so the requested GOP is a request, not a contract. What matters is that
      // the ring can READ the real value, not that it equals what we asked.
      //
      // The capture must be long enough to CONTAIN two keyframes at the requested GOP,
      // or probeGop correctly refuses to measure a GOP from a clip holding one. At
      // 6 s x 60 fps = 360 frames, a 250-frame GOP leaves only 1.44 GOPs and the readback
      // was impossible by construction -- the fixture was too short for its own assertion.
      // At 12 s = 720 frames = 2.88 GOPs it holds. Measured on this host at WINDOW_UTC
      // 2026-10-10T15:00:37Z: -g 250 over 600 frames gave 3 keyframes at pts 0, 4.166667
      // and 8.333333 -- 4.166667 s x 60 fps = 250.00002 frames, so the encoder honours -g
      // to the frame. 12 s is chosen over 10 s for margin, because a gdigrab capture of a
      // still desktop delivers fewer frames than the requested clock (measured all session).
      const out = join(dir, "long.mp4");
      // A CAPTURA PODE SER FAMINTA (medido 2026-11-05, 2x num gate de commit com
      // a caixa ocupada): o `gdigrab` de um desktop parado entrega MENOS frames
      // do que o relogio pedido, e uma captura de 12 s pode sair com um unico
      // keyframe -- o `probeGop` recusa medir e a arm falhava por ESCASSEZ, nao
      // por defeito. Tres tentativas, e o que se exige de cada uma e' o que a
      // medicao precisa: >=2 keyframes no FICHEIRO.
      const keyTimes = (file) => execFileSync("ffprobe", ["-v", "error",
        "-select_streams", "v:0", "-skip_frame", "nokey",
        "-show_entries", "frame=pts_time", "-of", "csv=p=0", file],
        { windowsHide: true, encoding: "utf8" })
        .split("\n").map((x) => parseFloat(x)).filter((x) => Number.isFinite(x));
      // A ESCASSEZ PEDE MAIS TEMPO, NAO A MESMA TENTATIVA (medido 2026-11-05):
      // com tres capturas de 12 s a competir pelo mesmo desktop, as tres sairam
      // com UM keyframe -- repetir a mesma janela nao da' ao encoder os frames
      // que faltam. A janela cresce (12 -> 20 -> 30 s), que e' a unica moeda que
      // compra frames aqui.
      let keyPts = [];
      // `testsrc2` e' o PADRAO SINTETICO, nao o desktop: o que esta arm mede e' o
      // LEITOR contra o ficheiro, e a captura do ecra a 60 fps prende o
      // compositor -- com a app do dono viva ela levou 3 strikes do
      // `UI_WATCHDOG` e saiu (`UI_WATCHDOG_EXIT code=9`, 2026-11-05 01:33:19).
      // O caminho `gdigrab desktop` continua medido, na captura curta acima.
      for (const seconds of [12, 20, 30]) {
        enc.captureAndEncode(out, { source: "testsrc2", fps: 60, seconds, gop: 250 });
        keyPts = keyTimes(out);
        if (keyPts.length >= 2) break;
        console.log(`       (${seconds} s capture: ${keyPts.length} keyframe(s) -- too short, widening)`);
      }
      const r = enc.gopOf(out, 60);
      assert.ok(r.gop > 0, "probe returned no GOP");
      // O QUE SE JULGA E' O LEITOR, NAO A PROMESSA (2026-11-05). A arm era
      // `r.gop >= 250`, ou seja "o NVENC honrou o -g 250" -- e isso e' uma
      // PROPRIEDADE DO ENCODER, que cai sob contencao de GPU precisa (medido
      // hoje: `nvenc.test.mjs FAIL 4 passed, 1 failed` duas vezes num gate de
      // commit, e 5/5 verdes nas mesmas horas com a caixa livre; a leitura
      // isolada deu 399, 508 e outros valores). O contrato do `gopOf` e'
      // outro: devolver o MENOR espacamento REAL entre keyframes do ficheiro
      // e dizer se e' variavel. Isso mede-se contra o ficheiro, nao contra o
      // pedido, e por isso nao depende de quem mais esta' a usar a GPU.
      assert.ok(keyPts.length >= 2,
        `fixture too short: ${keyPts.length} keyframe(s) after widening to 30 s -- nothing to measure`);
      const realGaps = keyPts.slice(1)
        .map((v, i) => Math.round((v - keyPts[i]) * 60));
      const expected = [...new Set(realGaps)].sort((a, b) => a - b);
      assert.equal(r.gop, expected[0],
        `probe said ${r.gop}, the file's smallest keyframe gap is ${expected[0]}`);
      assert.equal(Boolean(r.variable), expected.length > 1,
        `variable=${r.variable} with gaps ${expected.join(",")}`);
      console.log("       (requested GOP 250, keyframe gaps in the file: "
        + expected.join(",") + " -- probe reported " + r.gop + ")");
    });

    t("remux copies the stream: codec and frame count survive", () => {
      const src = join(dir, "cap.mp4");
      const dst = join(dir, "copy.mp4");
      const encodesBeforeRemux = enc.encodeCount();
      const before = execFileSync("ffprobe", ["-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,nb_frames", "-of", "csv=p=0", src],
        { windowsHide: true, encoding: "utf8" }).trim();
      const r = enc.remux(src, dst);
      const after = execFileSync("ffprobe", ["-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,nb_frames", "-of", "csv=p=0", dst],
        { windowsHide: true, encoding: "utf8" }).trim();
      assert.equal(after, before, "the stream changed across a remux");
      // O CONTADOR E' RELATIVO (2026-11-05): a captura acima pode ter precisado
      // de mais de uma janela, e um numero absoluto de encodes passaria a
      // depender da maquina em vez da propriedade -- "o remux nao encoda".
      assert.equal(enc.encodeCount(), encodesBeforeRemux,
        "remux must not have encoded again");
      assert.equal(enc.calls[enc.calls.length - 1], "remux",
        "the last call in the log must be the remux");
      assert.equal(enc.calls.filter((c) => c === "remux").length, 1,
        "exactly one remux reached the encoder");
      // Byte equality is NOT the invariant: ffmpeg may rewrite the moov box.
      // What must not change is the encoded stream itself.
      console.log("       (remux " + r.inBytes + " -> " + r.outBytes + " bytes, stream identical)");
    });

    t("a remux to a missing input fails loudly rather than silently", () => {
      assert.throws(() => enc.remux(join(dir, "nope.mp4"), join(dir, "x.mp4")));
    });
  }
} finally {
  rmSync(dir, { recursive: true, force: true });
}

console.log(`RESULT ${passed} passed, ${failed} failed${skipped ? `, ${skipped} suite block skipped` : ""}`);
process.exit(failed === 0 ? 0 : 1);