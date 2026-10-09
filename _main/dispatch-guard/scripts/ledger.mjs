// ledger.mjs - shared invocation recorder for the mcode-dispatch-guard Plugin.
//
// PURPOSE. The MiniMax hook contract states that "malformed input/output, process
// failures, and unsupported handlers produce bounded diagnostics and normally fail
// open without a user-facing error" (references/local-plugin-hooks.md:229-230).
// Fail-open is invisible by construction: a hook that stopped loading looks exactly
// like a hook that is enforcing. The only thing that can break that symmetry is a
// record written on EVERY invocation, so liveness becomes a measurement.
//
// PRIVACY. No message content is ever written. Only: event name, verdict, action
// class, byte length, and a truncated SHA-256 of the payload. A secret inside a
// report therefore cannot reach the ledger, which keeps the reference's rule
// ("Never place secrets in commands, stdout, stderr, Hook JSON, or package files",
// :232-233) satisfied by construction rather than by discipline.

import { createHash } from "node:crypto";
import { appendFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";

export const LEDGER_NAME = "invocations.jsonl";

/**
 * Resolve the writable state directory.
 * PLUGIN_DATA is the runtime's injected, host-owned directory. PLUGIN_DATA_OVERRIDE
 * lets the self-test point at a scratch dir without touching a real install.
 * Returns null when no writable location is known - the caller then degrades to
 * "no ledger" rather than failing the turn.
 */
export function resolveDataDir() {
  const raw = process.env.PLUGIN_DATA || process.env.PLUGIN_DATA_OVERRIDE || "";
  if (!raw) return null;
  try {
    mkdirSync(raw, { recursive: true });
    return raw;
  } catch {
    return null;
  }
}

/** Short, stable, non-reversible fingerprint of a payload. */
export function fingerprint(text) {
  if (typeof text !== "string") return null;
  return createHash("sha256").update(text, "utf8").digest("hex").slice(0, 16);
}

/**
 * Append one invocation record. Never throws: a ledger that cannot be written must
 * not be able to break a turn, because the failure mode we are defending against is
 * the hook doing something worse than nothing.
 */
export function record(entry) {
  const dir = resolveDataDir();
  if (!dir) return false;
  const line =
    JSON.stringify({
      ts: new Date().toISOString(),
      pid: process.pid,
      ...entry,
    }) + "\n";
  try {
    appendFileSync(join(dir, LEDGER_NAME), line, "utf8");
    return true;
  } catch {
    return false;
  }
}

/** Read stdin fully, bounded. Returns "" on any failure. */
export async function readStdin() {
  const chunks = [];
  let size = 0;
  try {
    for await (const chunk of process.stdin) {
      size += chunk.length;
      if (size > 1024 * 1024) break; // contract caps stdin at 1 MiB (:225)
      chunks.push(chunk);
    }
  } catch {
    return "";
  }
  return Buffer.concat(chunks).toString("utf8");
}

/** Parse the hook payload. Returns {} when absent or malformed - never throws. */
export function parsePayload(raw) {
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}
