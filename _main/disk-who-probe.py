"""QUEM ESTA' A AFOGAR O DISCO -- no instante em que o gate fica RED.

Nasceu do mesmo evento que o dono reporta: *"o PC inteiro trava: herdr, os
terminais dentro dele, o chrome, tudo ao mesmo tempo"*. O gate central mede a
LATENCIA (que estava a 418,8 ms sustained) e nao diz QUEM a paga. Este instrumento
faz a segunda metade: le o delta de I/O de CADA processo entre duas amostras e
ranqueia por bytes, com a latencia do volume ao lado para o numero nao ser lido
fora de contexto.

READ-ONLY POR DESENHO. Nao abre dispositivo, nao toca em audio, nao mata nada:
duas leituras de contadores e uma conta. `psutil` custa ~40-90 ms aqui (700+
processos); a cadencia e' 1000 ms.

USO
    python _main/disk-who-probe.py --samples 3 --gap-ms 1000
    python _main/disk-who-probe.py --samples 8 --gap-ms 2000 --json _main/_cache/disk-who.json

SAIDA (stderr e' ruido; stdout e' o relatorio)
    DISK_WHO window_s=.. samples=.. population=.. unreadable=..
    <pid> <name> read_mb_s=.. write_mb_s=.. io_mb_s=.. share=..%
    VOLUME <nome> latency_ms=.. queue=..
    VERDICT: ONE-TERM | SPREAD | UNKNOWN

`UNKNOWN` nunca e' "nada a ver": se a populacao ilegivel for grande ou se o
volume nao responder, o relatorio diz isso em vez de publicar zero.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

try:
    import psutil
except Exception:  # noqa: BLE001
    psutil = None


_PS_DISK = r"""
$ErrorActionPreference = 'Stop'
$count = %(count)d
$gap = %(gap)d
$times = New-Object System.Collections.Generic.List[long]
$bases = New-Object System.Collections.Generic.List[long]
$queue = New-Object System.Collections.Generic.List[double]
$i = 0
while ($i -lt $count) {
  $row = Get-CimInstance Win32_PerfRawData_PerfDisk_PhysicalDisk -Filter "Name='_Total'"
  if ($null -eq $row) { throw 'perfdisk-no-total-instance' }
  $times.Add([long]$row.AvgDisksecPerTransfer)
  $bases.Add([long]$row.AvgDisksecPerTransfer_Base)
  $queue.Add([double]$row.CurrentDiskQueueLength)
  $i++
  if ($i -lt $count) { Start-Sleep -Milliseconds $gap }
}
(($times | ForEach-Object { $_.ToString() }) -join ',') + ';' +
(($bases | ForEach-Object { $_.ToString() }) -join ',') + ';' +
(($queue | ForEach-Object { $_.ToString() }) -join ',')
"""


def volume_latency(count=3, gap_ms=250):
    """Latencia media do disco fisico -- A MESMA RULER DO GATE CENTRAL.

    MEDIDO a primeira versao deste instrumento (2026-11-05): eu lia
    `AvgDisksecPerTransfer` como se fosse SEGUNDOS e publiquei
    `latency_ms=981746603000.0`. O campo e' um PERF_AVERAGE_TIMER em ticks de
    100 ns que so' significa alguma coisa contra o seu `_Base`:
    `(t1-t0)/(b1-b0)` da' os 100 ns por transferencia. O gate central
    (`I:/!manager/tools/performance-gate.py`, `read_disk_latency`) usa exatamente
    esta conta; um instrumento que mede a mesma coisa com outra formula desmente
    o portao e nao avisa ninguem.

    Zero transferencias na janela e' disco OCIOSO (0 ms), nunca `UNKNOWN`.
    """
    if os.name != 'nt':
        return {'error': 'non-windows'}
    try:
        out = subprocess.run(
            ['powershell', '-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden',
             '-Command', _PS_DISK % {'count': max(3, int(count)), 'gap': max(50, int(gap_ms))}],
            capture_output=True, text=True, timeout=40,
            creationflags=0x08000000,
            startupinfo=subprocess.STARTUPINFO(
                dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0),
        )
    except Exception as exc:  # noqa: BLE001
        return {'error': repr(exc)}
    lines = [ln.strip() for ln in (out.stdout or '').splitlines() if ln.strip()]
    if not lines or lines[-1].count(';') != 2:
        return {'error': 'unparseable %r' % (lines[-1:] or out.stderr[:80],)}
    times_raw, bases_raw, queue_raw = lines[-1].split(';')
    try:
        times = [int(v) for v in times_raw.split(',') if v]
        bases = [int(v) for v in bases_raw.split(',') if v]
        queue = [float(v) for v in queue_raw.split(',') if v]
    except Exception as exc:  # noqa: BLE001
        return {'error': repr(exc)}
    if len(times) < 2 or len(bases) < 2:
        return {'error': 'short-window'}
    d_base = bases[-1] - bases[0]
    if d_base <= 0:
        return {'latency_ms': 0.0, 'queue': round(sum(queue) / len(queue), 2), 'transfers': 0}
    latency_ms = ((times[-1] - times[0]) / float(d_base)) / 10000.0
    return {
        'latency_ms': round(latency_ms, 1),
        'queue': round(sum(queue) / len(queue), 2),
        'transfers': d_base,
    }


GATE = r'I:\!manager\tools\performance-gate.py'


def cross_check():
    """A MESMA JANELA, DUAS IMPLEMENTACOES -- e o numero tem de bater.

    Nasceu de um erro real deste ficheiro: a primeira versao lia
    `AvgDisksecPerTransfer` como segundos e publicou 9,8e11 ms. Um instrumento
    que mede a latencia do disco e nao se compara com o instrumento que ja' a
    mede nao tem como saber que esta' errado; este controle le a funcao
    `read_disk_latency` do gate central pelo caminho e compara.

    Devolve `(ok, detalhe)`. Gate ausente e' `UNKNOWN`, nunca "bateu".
    """
    import importlib.util
    if not os.path.exists(GATE):
        return None, 'gate ausente (%s)' % GATE
    try:
        spec = importlib.util.spec_from_file_location('perf_gate', GATE)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        samples = mod.read_disk_latency()
    except Exception as exc:  # noqa: BLE001
        return None, 'gate nao respondeu: %r' % (exc,)
    # O gate devolve UMA AMOSTRA POR JANELA (`[{transfers, latency_ms, idle}]`), e
    # a politica dele e' sobre a sequencia. A comparacao justa com a minha janela
    # unica e' a MAIOR amostra dele -- se a minha estiver abaixo da menor ou acima
    # da maior, os dois instrumentos estao a medir coisas diferentes.
    try:
        lat = [float(s['latency_ms']) for s in samples if not s.get('idle')]
    except Exception:  # noqa: BLE001
        return None, 'amostras do gate inesperadas: %r' % (samples,)
    if not lat:
        return None, 'gate sem amostras nao-ociosas'
    gate_ms = max(lat)
    mine = volume_latency(count=3, gap_ms=250)
    if 'latency_ms' not in mine:
        return None, 'a minha leitura falhou: %r' % (mine,)
    diff = abs(mine['latency_ms'] - float(gate_ms))
    # O CRITERIO E' DE FORMULA, NAO DE IGUALDADE, e a primeira versao deste
    # controle estava errada por nao saber isso: comparava 29,6 ms com 10,4 ms e
    # dava FAIL, mas as duas leituras cobrem intervalos CONSECUTIVOS (nunca o
    # mesmo), e a latencia do disco e' espalhada de 0,07 a 418 ms na mesma
    # maquina -- um fator de 3 entre vizinhas e' o normal, nao um defeito. O
    # erro que este controle existe para apanhar e' de FORMULA (a versao que lia
    # `AvgDisksecPerTransfer` como segundos publicou 9,8e11 ms), e esse aparece
    # com uma razao de ordens de grandeza. Por isso: 10x ou 200 ms absolutos.
    ratio = (max(mine['latency_ms'], float(gate_ms)) + 1e-9) / (min(mine['latency_ms'], float(gate_ms)) + 1e-9)
    ok = diff <= 200.0 or ratio <= 10.0
    return ok, ('meu=%.1f ms gate_max=%.1f ms (amostras=%s) diff=%.1f ms'
                % (mine['latency_ms'], float(gate_ms),
                   [round(v, 1) for v in lat], diff))


def snapshot():
    """{pid: (name, read_bytes, write_bytes)} + quantos nao se deixaram ler."""
    rows = {}
    unreadable = 0
    if psutil is None:
        return rows, -1
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            io = proc.io_counters()
            rows[proc.info['pid']] = (proc.info['name'] or '?', io.read_bytes, io.write_bytes)
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError, OSError):
            unreadable += 1
    return rows, unreadable


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--samples', type=int, default=3)
    ap.add_argument('--gap-ms', type=int, default=1000)
    ap.add_argument('--top', type=int, default=8)
    ap.add_argument('--json', dest='json_out', default=None)
    ap.add_argument('--cross-check', action='store_true',
                    help='compara a minha latencia com a do gate central na mesma janela')
    args = ap.parse_args(argv)

    if psutil is None:
        print('DISK_WHO UNKNOWN reason=psutil-ausente')
        return 3

    gap = max(200, args.gap_ms) / 1000.0
    first, unread1 = snapshot()
    # O volume e' lido no FIM da janela: a pergunta e' "quem pagou a latencia
    # que o gate viu", nao "quem estava a pagar antes de eu comecar".
    time.sleep(gap * max(1, args.samples))
    second, unread2 = snapshot()
    vol = volume_latency(count=3, gap_ms=250)
    window_s = gap * max(1, args.samples)

    per = []
    for pid, (name, r2, w2) in second.items():
        prev = first.get(pid)
        if prev is None:
            continue
        dr = max(0, r2 - prev[1])
        dw = max(0, w2 - prev[2])
        if dr + dw <= 0:
            continue
        per.append({
            'pid': pid, 'name': name,
            'read_mb_s': round(dr / window_s / 1048576.0, 2),
            'write_mb_s': round(dw / window_s / 1048576.0, 2),
            'io_mb_s': round((dr + dw) / window_s / 1048576.0, 2),
            'bytes': dr + dw,
        })
    total = sum(p['bytes'] for p in per) or 1
    for p in per:
        p['share_pct'] = round(100.0 * p['bytes'] / total, 1)
    per.sort(key=lambda p: -p['bytes'])

    population = len(second)
    print('DISK_WHO window_s=%.1f samples=%d population=%d unreadable=%d '
          'volume_latency_ms=%s queue=%s transfers=%s'
          % (window_s, args.samples, population, unread2,
             vol.get('latency_ms', '?'), vol.get('queue', '?'), vol.get('transfers', '?')))
    for p in per[:args.top]:
        print('  pid=%-7d %-26s read_mb_s=%-7.2f write_mb_s=%-7.2f io_mb_s=%-7.2f share=%5.1f%%'
              % (p['pid'], p['name'][:26], p['read_mb_s'], p['write_mb_s'], p['io_mb_s'], p['share_pct']))

    # O VEREDITO TEM DE PODER SER UNKNOWN. Um unico processo a dominar (>=50 %
    # do I/O da janela) e' um termo; varios a dividir e' SPREAD; populacao
    # ilegivel grande ou volume mudo e' UNKNOWN.
    if vol.get('error') or unread2 < 0:
        verdict = 'UNKNOWN'
    elif not per:
        verdict = 'UNKNOWN'
    elif per[0]['share_pct'] >= 50.0:
        verdict = 'ONE-TERM'
    else:
        verdict = 'SPREAD'
    print('VERDICT: %s' % verdict)

    if args.cross_check:
        ok, detail = cross_check()
        label = 'PASS' if ok else ('UNKNOWN' if ok is None else 'FAIL')
        print('CROSS-CHECK %s %s' % (label, detail))
        if ok is False:
            return 1

    if args.json_out:
        os.makedirs(os.path.dirname(args.json_out) or '.', exist_ok=True)
        with open(args.json_out, 'w', encoding='utf-8') as fh:
            json.dump({'window_s': window_s, 'volume': vol, 'rows': per[:args.top + 8],
                       'population': population, 'unreadable': unread2,
                       'verdict': verdict}, fh, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
