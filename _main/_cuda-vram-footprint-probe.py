"""THE WORKER'S GPU FOOTPRINT AND ITS LOAD TIME -- the stutter, measured.

Owner, 2026-10-21, for the twentieth time: *"abrir ou fechar o sotto trava pra
caralho meu pc"*. The suspicion this instrument exists to test is the GPU:

    the worker was started WITHOUT provider options, so onnxruntime's DEFAULTS
    applied -- `arena_extend_strategy=kNextPowerOfTwo` (every GPU allocation
    rounds UP to the next power of two), `gpu_mem_limit` UNLIMITED and
    `cudnn_conv_algo_search=EXHAUSTIVE` (the session creation benchmarks
    every convolution algorithm). The measured consequence on the owner's box:
    the worker's steady footprint was ~9.7 GB of a 16 303 MB card, for a model
    whose weights are 747 MB on disk, and the load took 4.1-8.1 s on a quiet
    machine and 32.59 s on a busy one.

THE ARMS ARE THE SAME CODE. The options are in the environment
(`SOTTO_CUDA_ARENA`, `SOTTO_CUDNN_ALGO_SEARCH`, `SOTTO_CUDA_MEM_LIMIT_MB`), so
the "before" arm is the DEFAULTS and the "after" arm is the fix -- no second
copy of the worker, no divergence.

    python _main/_cuda-vram-footprint-probe.py            # both arms
    python _main/_cuda-vram-footprint-probe.py --arm after

The arm names are NOT "before"/"after" in the code: they are "defaults" (the
onnxruntime defaults, forced) and "options" (the fix, as the worker ships it).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
WORKER = os.path.join(REPO, 'worker', 'sotto_worker.py')
SAMPLE = os.path.join(REPO, '_main', 'pt-br-sample.wav')

#: The arms. `env` is what the worker process inherits ON TOP of the caller's.
ARMS = {
    'defaults': {
        'SOTTO_CUDA_ARENA': 'kNextPowerOfTwo',
        'SOTTO_CUDNN_ALGO_SEARCH': 'EXHAUSTIVE',
        'SOTTO_CUDA_MEM_LIMIT_MB': '0',      # 0 = no cap (the default we fix)
    },
    'options': {
        'SOTTO_CUDA_ARENA': 'kSameAsRequested',
        'SOTTO_CUDNN_ALGO_SEARCH': 'HEURISTIC',
        'SOTTO_CUDA_MEM_LIMIT_MB': '4096',
    },
}

GPU_USED = re.compile(r'^\s*(\d+)\s*$')


def gpu_used_mib():
    """The DEVICE's used VRAM in MiB, or None (no nvidia-smi / no card)."""
    try:
        out = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))
    except Exception:
        return None
    for line in out.stdout.splitlines():
        m = GPU_USED.match(line.strip())
        if m:
            return int(m.group(1))
    return None


def run_arm(name, env_extra, sample, timeout_s):
    env = dict(os.environ)
    env.update(env_extra)
    cmd = [sys.executable, WORKER, '--audio', sample]
    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=os.path.join(REPO, 'worker'),
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, encoding='utf-8', errors='replace',
                            env=env, bufsize=1, creationflags=subprocess.CREATE_NO_WINDOW, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))
    peak = None
    baseline = gpu_used_mib()
    load_s = None
    # THE MEASURED PHASE ENDS AT `model-loaded`: the transcription that follows
    # is not what the owner waits for, and waiting for it made the probe sit
    # on the machine for five minutes per arm.
    deadline = t0 + timeout_s
    for line in proc.stdout:
        if time.time() > deadline:
            break
        used = gpu_used_mib()
        if used is not None:
            peak = used if peak is None else max(peak, used)
        line = line.strip()
        if not line.startswith('{'):
            continue
        try:
            payload = json.loads(line)
        except ValueError:
            continue
        if payload.get('state') == 'model-loaded':
            load_s = payload.get('load_s')
            # ONE more sample: the VRAM at the moment the model is up.
            used = gpu_used_mib()
            if used is not None:
                peak = used if peak is None else max(peak, used)
            break
    wall_s = time.time() - t0
    try:
        proc.kill()
    except Exception:
        pass
    try:
        proc.communicate(timeout=30)
    except Exception:
        pass
    return {
        'arm': name,
        'rc': proc.returncode,
        'wall_s': round(wall_s, 2) if wall_s else None,
        'load_s': load_s,
        'gpu_baseline_mib': baseline,
        'gpu_peak_mib': peak,
        'gpu_delta_mib': (peak - baseline) if (peak is not None and
                                               baseline is not None) else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', default='both', choices=['both', 'defaults',
                                                       'options'])
    ap.add_argument('--sample', default=SAMPLE)
    ap.add_argument('--timeout', type=int, default=300)
    ap.add_argument('--order', default='forward', choices=['forward', 'reverse'],
                    help='which arm runs FIRST. The order is a CONFOUND (the '
                         'first arm pays the cold page cache), so the honest '
                         'reading is both orders.')
    args = ap.parse_args()

    if not os.path.exists(args.sample):
        print('NO SAMPLE: %s' % args.sample)
        return 2

    names = list(ARMS) if args.arm == 'both' else [args.arm]
    if args.order == 'reverse':
        names = list(reversed(names))
    rows = []
    for name in names:
        print('--- arm %s ---' % name, flush=True)
        row = run_arm(name, ARMS[name], args.sample, args.timeout)
        rows.append(row)
        print('    load_s=%s  wall_s=%s  gpu_peak=%s MiB  gpu_delta=%s MiB'
              % (row['load_s'], row['wall_s'], row['gpu_peak_mib'],
                 row['gpu_delta_mib']), flush=True)

    print()
    print('ARM        load_s   wall_s   gpu_peak_MiB  gpu_delta_MiB')
    for row in rows:
        print('%-10s %-8s %-8s %-13s %s'
              % (row['arm'], row['load_s'], row['wall_s'],
                 row['gpu_peak_mib'], row['gpu_delta_mib']))
    print(json.dumps(rows, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
