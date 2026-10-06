#!/usr/bin/env bash
# agc-gate.sh — does the LIVE automatic gain actually ACT when it is allowed and
# needed? Closes the GATE-CHANGE REQUEST at the foot of docs/audit/auto-gain.md
# (lane SottoAutoGain) under the ORDER lane SottoAgcSpeechOrder established.
#
# THE HOLE IT CLOSES. No shipped oracle asserts the AGC did anything. Someone can
# delete the `agc.process(...)` call (or set AGC_MAX_GAIN_DB=0) and every other
# oracle stays GREEN: `delivery-rate-oracle.py` reads duty/queue_drops, the ring
# probe reads the tap, and neither reads `gain_db`. The stage silently does
# nothing while the run looks healthy.
#
# THE PREDICATE (reads the worker's own WORKER_STATS line, or a `{"state":"done"}`
# JSON payload), and it is scoped by the ORDER:
#
#   RED   iff  agc=on  AND  peak < 0.12  AND  gain_max_db == 0.0  AND speech-present
#   GREEN otherwise, and SKIP when agc=off (that is the CONTROL arm).
#
#   * `peak < 0.12` is the quiet source that NEEDS lifting (the brief's own bar).
#   * `speech-present` == `gate_kept > 0` (the live default: the speech/music gate
#     KEPT chunks, so the stage was both permitted and needed), OR `gate=off`
#     (no gate configured: every chunk is treated as speech).
#   * The speech scoping is REQUIRED by the ORDER: under it, a non-speech source
#     (a drone) is HELD at unity — `gain_max_db=+0.0` at `peak<0.12` — and that is
#     CORRECT, so a bare `gain_max_db==0.0 and peak<0.12` test would fire on the
#     right behaviour. The gate must not.
#
# Usage:
#   bash scripts/agc-gate.sh <file> [<file> ...]   # stats text and/or worker JSONL
#   bash scripts/agc-gate.sh --line "WORKER_STATS ..."
#   bash scripts/agc-gate.sh --selftest            # proves the gate can go RED
#
# Exit: 0 GREEN (every file), 2 RED (a file shows an inert AGC), 3 no signal.
set -u

QUIET_PEAK="0.12"

# Extract `key=value` fields from ONE WORKER_STATS line into shell vars.
parse_stats() {
  local line="$1"
  P_AGC=""; P_PEAK=""; P_GAINMAX=""; P_KEPT=""; P_GATE=""; P_CHUNKS=""
  local f k v
  for f in $line; do
    k="${f%%=*}"; v="${f#*=}"
    case "$k" in
      agc) P_AGC="$v" ;;
      peak) P_PEAK="$v" ;;
      gain_max_db) P_GAINMAX="$v" ;;
      gate_kept) P_KEPT="$v" ;;
      gate) P_GATE="$v" ;;
      chunks) P_CHUNKS="$v" ;;
    esac
  done
  [ -n "$P_AGC" ] && [ -n "$P_PEAK" ] && [ -n "$P_GAINMAX" ]
}

# Pull the LAST WORKER_STATS line from a file (the run's final line), if any.
last_stats_line() {
  awk '/WORKER_STATS/ {ln=$0} END {if (ln!="") print ln}' "$1"
}

verdict_for() {
  # stdin: a stats line. echoes "GREEN|RED|SKIP <reason>"
  local line; line="$(cat)"
  if ! parse_stats "$line"; then
    return 3
  fi
  # arithmetic on the DBFS gain, which is printed signed (+0.0 / -6.0 / +24.0)
  local gm; gm="$(awk -v s="$P_GAINMAX" 'BEGIN{print s+0}')"
  local pk; pk="$(awk -v s="$P_PEAK"   'BEGIN{print s+0}')"
  local kept; kept="$(awk -v s="${P_KEPT:-0}" 'BEGIN{print s+0}')"
  local ch; ch="$(awk -v s="${P_CHUNKS:-0}" 'BEGIN{print s+0}')"
  local quiet; quiet="$(awk -v p="$pk" -v q="$QUIET_PEAK" 'BEGIN{print (p<q)?1:0}')"

  if [ "$P_AGC" = "off" ]; then echo "SKIP agc=off (control arm)"; return 0; fi
  local speech_present=0
  if [ "$kept" -gt 0 ]; then speech_present=1; fi
  if [ "${P_GATE:-on}" = "off" ] && [ "$ch" -gt 0 ]; then speech_present=1; fi

  local zerogain; zerogain="$(awk -v g="$gm" 'BEGIN{print (g==0)?1:0}')"
  if [ "$quiet" = "1" ] && [ "$speech_present" = "1" ] && [ "$zerogain" = "1" ]; then
    echo "RED agc=on peak=$pk (<$QUIET_PEAK) gain_max_db=$gm (==0) kept=$kept gate=${P_GATE:-?} -> the stage did nothing at a level that needs it"
    return 2
  fi
  echo "GREEN agc=on peak=$pk gain_max_db=$gm kept=$kept gate=${P_GATE:-?}"
  return 0
}

if [ "${1:-}" = "--selftest" ]; then
  red_line="WORKER_STATS tag=final blocks=200 peak=0.100952 rms=0.01 gain_db=+0.0 gain_min_db=+0.0 gain_max_db=+0.0 peak_out=0.000000 gain_would_db=+16.0 gain_would_max_db=+16.0 held_blocks=0 speech_blocks=0 agc=on resampled_samples=320000 chunks=35 captions=0 music_gated_chunks=0 gate_kept=35 gate=on queue_drops=0"
  green_line="WORKER_STATS tag=final blocks=200 peak=0.100952 rms=0.01 gain_db=+16.0 gain_min_db=+0.0 gain_max_db=+16.0 peak_out=0.64 gain_would_db=+16.6 gain_would_max_db=+16.6 held_blocks=0 speech_blocks=200 agc=on resampled_samples=320000 chunks=35 captions=7 music_gated_chunks=0 gate_kept=35 gate=on queue_drops=0"
  drone_line="WORKER_STATS tag=final blocks=200 peak=0.090000 rms=0.02 gain_db=+0.0 gain_min_db=+0.0 gain_max_db=+0.0 peak_out=0.000000 gain_would_db=+15.0 gain_would_max_db=+15.0 held_blocks=200 speech_blocks=0 agc=on resampled_samples=320000 chunks=35 captions=0 music_gated_chunks=35 gate_kept=0 gate=on queue_drops=0"
  ctl_line="WORKER_STATS tag=final blocks=200 peak=0.100952 rms=0.01 gain_db=+0.0 gain_min_db=+0.0 gain_max_db=+0.0 peak_out=0.0 agc=off resampled_samples=320000 chunks=35 captions=6 music_gated_chunks=0 gate_kept=0 gate=off queue_drops=0"
  rc=0
  printf '%s' "$red_line"   | verdict_for; [ $? -eq 2 ] || { echo "SELFTEST FAIL: RED fixture not RED"; rc=1; }
  printf '%s' "$green_line" | verdict_for; [ $? -eq 0 ] || { echo "SELFTEST FAIL: GREEN fixture not GREEN"; rc=1; }
  # the drone case: gain held at 0 at a quiet level, but the gate kept NOTHING ->
  # must NOT be RED (that is the ORDER working).
  out="$(printf '%s' "$drone_line" | verdict_for)"; case "$out" in GREEN*) ;; *) echo "SELFTEST FAIL: drone (held, gate_kept=0) fired RED: $out"; rc=1;; esac
  # the control arm: agc=off -> SKIP.
  out="$(printf '%s' "$ctl_line" | verdict_for)"; case "$out" in SKIP*) ;; *) echo "SELFTEST FAIL: control (agc=off) not SKIP: $out"; rc=1;; esac
  [ "$rc" = 0 ] && echo "SELFTEST GREEN (RED fixture fires, GREEN fixture passes, drone+control do not fire)"
  exit "$rc"
fi

if [ "${1:-}" = "--line" ]; then
  printf '%s' "$2" | verdict_for; exit $?
fi

[ $# -ge 1 ] || { echo "usage: bash scripts/agc-gate.sh <file>... | --line LINE | --selftest" >&2; exit 3; }

worst=0
for f in "$@"; do
  if [ ! -f "$f" ]; then echo "MISSING $f"; worst=3; continue; fi
  line="$(last_stats_line "$f")"
  if [ -z "$line" ]; then echo "NO-WORKER_STATS $f"; worst=3; continue; fi
  out="$(printf '%s' "$line" | verdict_for)"; rc=$?
  echo "$(basename "$f"): $out"
  if [ "$rc" = 2 ]; then worst=2; elif [ "$rc" = 3 ] && [ "$worst" != 2 ]; then worst=3; fi
done
echo "VERDICT: $([ "$worst" = 0 ] && echo GREEN || ([ "$worst" = 2 ] && echo RED || echo NO-SIGNAL))"
exit "$worst"
