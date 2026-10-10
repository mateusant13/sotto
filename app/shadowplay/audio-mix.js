// Global audio mix. AUDIO.md section 4 is the spec this implements:
// the two cases differ in how they sum, and one of them clips.
//
// UNCORRELATED (independent sources): sum in the POWER domain.
//   RMS_total = sqrt(sum of squares). Two equal uncorrelated signals add
//   +3.01 dB over one of them, never 0.
// CORRELATED (a source already carrying the mix, e.g. loopback of a stream
// that includes the app): sum LINEARLY. Two equal signals add +6.02 dB and clip.
//
// The headroom exists to cover exactly this gap. Measured: -2.990 dBFS
// uncorrelated vs +0.021 dBFS correlated. See CLIPPING-REFUTATION.txt.
export const HEADROOM_DB = 3.01;

export function sumPower(samples) {
  if (!samples.length) throw new RangeError("no samples to sum");
  let s = 0;
  for (const x of samples) s += x * x;
  return Math.sqrt(s);
}

export function toDbFS(linear) {
  if (linear <= 0) return -Infinity;
  return 20 * Math.log10(linear);
}

export function fromDbFS(db) {
  return Math.pow(10, db / 20);
}

// Both cases at unity gain, for a caller that wants the raw sums.
export function mix(components, { correlated = false } = {}) {
  if (!Array.isArray(components) || components.length === 0) {
    throw new RangeError("mix needs at least one component");
  }
  const linear = correlated
    ? components.reduce((a, b) => a + b, 0)      // linear sum: clips
    : sumPower(components);                        // power sum: does not clip
  return { linear, dbfs: toDbFS(linear), correlated };
}

// What gain keeps the worst case under 0 dBFS, given the documented headroom.
export function safeGain(correlated) {
  return correlated ? fromDbFS(-HEADROOM_DB) : 1;
}