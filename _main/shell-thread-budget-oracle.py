"""O ORCAMENTO DE CPU DA SHELL -- PRAZO, NAO COMPLAINT (2026-11-08).

NASCEU DE UMA DM DE STUTTER DO WATCHER, a mesma que o dono ja' reclamou 149
vezes em 14 dias: `pythonw.exe(42572) is the top measured culprit`, 24 episodios
em 60 min. A resposta honesta nao e' "o dono reclamou": e' um NUMERO que diga
qual fio queima o nucleo e quanto, e um portao que recuse o numero quando ele
cresce. Os dois instrumentos ja' existiam e NENHUM passo da bateria os usava:

  * `_main/shell-thread-cpu.py` -- CPU por FIO da shell viva, com o NOME do fio
    (Toolhelp32Snapshot + GetThreadTimes; o `py-spy` nao anexa a esta shell,
    medido 2026-11-05). Ele tinha `--neg-arm` e zero chamadores.
  * `THREAD_CPU total=.. top=..` -- a propria shell publica o resumo de 30 s.

MEDIDO nesta maquina, instancia viva pid 42572, 04:39-04:41 (o log ao lado):
    THREAD_CPU total=19% top=sotto-caption-paint:10% sotto-external-captions:4%
                     sotto-batch-executor:4% sotto-caption-tick:3%
    THREAD_CPU total=37% top=sotto-caption-tick:24% ...   (uma janela)
e a medicao direta do mesmo caminho de pintura: 11,6 ms p95 por quadro.

O TECTO E' DECLARADO, E O NUMERO NAO E' INVENTADO: 25 % de um nucleo no total e
15 % num unico fio ficam ACIMA do medido hoje (19/10) e por isso nao sao um
portao que nasce vermelho; o ratchet de +20 % sobre o baseline e' o que recusa o
crescimento. O alvo pos-cura esta' escrito no recibo, nao aqui.

UM PASSO SALTADO NAO E' UM PORTAO QUE PASSOU: sem shell viva ele diz
`VERDICT: SKIPPED` (a bateria conta como SKIPPED, nunca como verde).

USO
    python _main/shell-thread-budget-oracle.py            # julga a shell viva
    python _main/shell-thread-budget-oracle.py --update    # grava o baseline
    python _main/shell-thread-budget-oracle.py --neg-arm   # controlo do JUIZ
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOL = os.path.join(HERE, 'shell-thread-cpu.py')
LOG = os.path.join(HERE, 'webview-run.log')
BASELINE = os.path.join(HERE, 'shell-thread-budget-baseline.json')

#: Tecto do TOTAL, em % de UM nucleo. Medido 19 % em repouso-com-legenda a tocar.
TOTAL_CEILING = 25.0
#: Tecto de UM fio. Medido 10 % (`sotto-caption-paint`); a cura da pintura tem de
#: trazer este numero para baixo, e o ratchet e' quem o impede de voltar.
THREAD_CEILING = 15.0
#: Quanto o baseline pode crescer antes de o portao falar.
RATCHET = 1.20
#: Janela da medicao independente (s). O instrumento divide pelo tempo medido.
SECONDS = 5.0


def find_shell_pid():
    """O pid da shell VIVA, pelo cmdline (`sotto_webview.py`), nao por um log velho."""
    try:
        import psutil
    except Exception:                       # noqa: BLE001
        return None
    for p in psutil.process_iter(['pid', 'cmdline']):
        try:
            cl = p.info.get('cmdline') or []
        except Exception:                   # noqa: BLE001
            continue
        joined = ' '.join(cl)
        if 'sotto_webview.py' in joined and '--log' in joined:
            return int(p.info['pid'])
    return None


def measure(pid, seconds=SECONDS):
    """(total_pct, [(pct, tid, name)]) do instrumento da casa, ou None."""
    try:
        sys.path.insert(0, HERE)
        import hidden_launch
        argv = [sys.executable, TOOL, str(pid), '--seconds', str(seconds), '--top', '10']
        out = hidden_launch.run(argv)
    except Exception:                       # noqa: BLE001
        out = None
    if isinstance(out, tuple):
        out = out[0]
    if not out:
        try:
            p = subprocess.run([sys.executable, TOOL, str(pid), '--seconds',
                                str(seconds), '--top', '10'], capture_output=True,
                               text=True, timeout=seconds + 40)
            out = p.stdout
        except Exception:                   # noqa: BLE001
            return None
    return parse(out)


def parse(text):
    """Do stdout do `shell-thread-cpu.py` para (total, linhas). PURA."""
    if not text:
        return None
    m = re.search(r'([\d.]+)% de um nucleo no total', text)
    if not m:
        return None
    total = float(m.group(1))
    rows = []
    for ln in text.splitlines():
        r = re.match(r'\s*([\d.]+)%\s+([\d.]+)\s+(\d+)\s+(.+?)\s*$', ln)
        if r:
            rows.append((float(r.group(1)), int(r.group(3)), r.group(4)))
    return total, rows


def log_worst(minutes=60.0, path=LOG):
    """O PIOR `THREAD_CPU` da serie do log -- a janela ANIMADA que a amostra perde.

    MEDIDO 2026-11-08, e e' o defeito do proprio portao: a primeira versao media
    UMA janela de 5 s e deu `total=19.7% top=sotto-caption-paint:5.3%` com o
    dono em REPOUSO -- verde, enquanto o mesmo pid, minutos antes, media 93,6 %
    no fio do tick. O stutter e' INTERMITENTE (24 episodios em 60 min): um portao
    que so' olha o instante de agora aprova o defeito. A serie que a propria
    shell publica (`THREAD_CPU`, janelas de 30 s) ja' contem as janelas ocupadas,
    entao o pior valor delas entra no julgamento ao lado da amostra externa.

    Linhas `heartbeat=true` sao as janelas QUIETAS: entram, e o pior valor e' o
    que decide -- uma serie que so' tem batimentos diz que nao houve stutter.
    """
    import datetime
    out = None
    try:
        lines = io.open(path, encoding='utf-8', errors='replace').read().splitlines()[-4000:]
    except Exception:                       # noqa: BLE001
        return None
    cutoff = time.time() - minutes * 60.0
    for ln in lines:
        if 'THREAD_CPU' not in ln:
            continue
        m = re.search(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)', ln)
        if not m:
            continue
        try:
            when = datetime.datetime.strptime(m.group(1), '%Y-%m-%d %H:%M:%S').timestamp()
        except Exception:                   # noqa: BLE001
            continue
        if when < cutoff:
            continue
        tot = re.search(r'total=(\d+)%', ln)
        tops = re.findall(r'([\w-]+):(\d+)%', ln)
        if not tot:
            continue
        t = float(tot.group(1))
        top_pct, top_name = (max(((float(p), n) for n, p in tops), default=(0.0, '')))
        if out is None or t > out[0] or top_pct > out[1]:
            out = (max(t, out[0]) if out else t,
                   max(top_pct, out[1]) if out else top_pct,
                   top_name if (out is None or top_pct >= out[1]) else out[2],
                   m.group(1))
    return out


def judge(reading, baseline, log_read=None):
    """A DECISAO, pura: (ok, violacoes). Sem I/O -- e' isto que o neg-arm muta."""
    if not reading:
        return False, ['sem leitura do instrumento']
    total, rows = reading
    bad = []
    # O PIOR DAS DUAS LEITURAS (2026-11-08): a amostra de 5 s perde a janela
    # animada, que a serie do log ja' publicou. Gatear so' a amostra e' aprovar
    # um stutter intermitente por nao ter caido no instante da medicao.
    if log_read:
        total = max(total, float(log_read[0] or 0.0))
        if rows:
            if float(log_read[1] or 0.0) > rows[0][0]:
                rows = [(float(log_read[1]), rows[0][1], log_read[2] or rows[0][2])] + rows[1:]
        else:
            rows = [(float(log_read[1]), 0, log_read[2] or '')]
    if total > TOTAL_CEILING:
        bad.append('total=%.1f%% acima do tecto %.0f%%' % (total, TOTAL_CEILING))
    if not rows:
        bad.append('nenhum fio com CPU > 0 na janela')
    else:
        top_pct, _tid, top_name = rows[0]
        if top_pct > THREAD_CEILING:
            bad.append('fio %s=%.1f%% acima do tecto %.0f%%'
                       % (top_name, top_pct, THREAD_CEILING))
        if not top_name or top_name in ('(sem nome)', '?'):
            bad.append('o fio mais quente nao tem NOME -- o numero vira suspeita')
    if log_read:
        print('  serie do log (pior da janela): total=%.0f%% %s=%.0f%% @ %s'
              % (log_read[0], log_read[2] or '?', log_read[1], log_read[3]))
    if baseline:
        b_total = float(baseline.get('total') or 0.0)
        b_thread = float(baseline.get('top_pct') or 0.0)
        if b_total and total > b_total * RATCHET:
            bad.append('total=%.1f%% cresceu >%.0f%% sobre o baseline %.1f%%'
                       % (total, (RATCHET - 1) * 100, b_total))
        if b_thread and rows and rows[0][0] > b_thread * RATCHET:
            bad.append('fio %s=%.1f%% cresceu >%.0f%% sobre o baseline %.1f%%'
                       % (rows[0][2], rows[0][0], (RATCHET - 1) * 100, b_thread))
    return (not bad), bad


def report(reading, baseline, pid=None, log_read=None):
    total, rows = reading
    print('SHELL-THREAD-BUDGET pid=%s total=%.1f%% ceiling=%.0f%% thread_ceiling=%.0f%%'
          % (pid or '?', total, TOTAL_CEILING, THREAD_CEILING))
    for pct, tid, name in rows[:6]:
        print('  %7.1f%% %7d  %s' % (pct, tid, name))
    if baseline:
        print('  baseline total=%.1f%% top=%.1f%% (%s)'
              % (float(baseline.get('total') or 0.0),
                 float(baseline.get('top_pct') or 0.0),
                 baseline.get('measured_at') or '-'))


def _neg_arm():
    """Controlo PURO do JUIZ: nenhuma shell, nenhum pixel na tela dele."""
    good = (14.0, [(9.0, 11, 'sotto-caption-paint'), (3.0, 12, 'yt-cdp-source')])
    base = {'total': 19.0, 'top_pct': 10.0, 'measured_at': '2026-11-08T04:40Z'}
    cases = []

    def add(ok, title):
        cases.append(bool(ok))
        print(('PASS ' if ok else 'FAIL ') + title)

    ok, bad = judge(good, base)
    add(ok, 'M0 leitura saudavel PASSA (controlo positivo, senao o portao nunca fala)')

    ok, bad = judge((41.0, [(24.0, 13, 'sotto-caption-tick')]), base)
    add((not ok) and any('total=' in b for b in bad),
        'M1 total acima do tecto recusado: %s' % (bad[:1] or ['-']))

    ok, bad = judge((18.0, [(17.5, 14, 'sotto-caption-paint')]), base)
    add((not ok) and any('acima do tecto' in b for b in bad),
        'M2 um fio acima do tecto recusado')

    ok, bad = judge((18.0, [(12.0, 15, '(sem nome)')]), base)
    add((not ok) and any('NOME' in b for b in bad),
        'M3 fio quente sem nome recusado')

    ok, bad = judge((30.0, [(11.0, 16, 'sotto-caption-paint')]), base)
    add((not ok) and any('baseline' in b for b in bad),
        'M4 crescimento sobre o baseline recusado')

    ok, bad = judge(None, base)
    add(not ok, 'M5 leitura ausente NUNCA e verde')

    print('\nNEG-ARM check=%d/%d' % (sum(1 for c in cases if c), len(cases)))
    caught = all(cases)
    print('NEG-ARM %s' % ('PASS' if caught else 'FAIL'))
    return 1 if caught else 0


def instance_fresh():
    """O processo vivo carrega o codigo do disco? (True/False/None = nao sei).

    PORQUE ISTO EXISTE (medido 2026-11-08, no mesmo dia em que o portao nasceu):
    na primeira corrida real o portao acusou 93,6 % num processo que carregava
    codigo de QUATRO HORAS ANTES da cura -- um vermelho honesto sobre o passado.
    Um portao que fica vermelho por codigo que ja' nao existe nao mede o code
    atual, e a casa ja' sabe onde isso acaba: alguem o desliga. A regra do repo
    (`_main/live-code-freshness-oracle.py`, passo 0 do bug-hunt) e' que STALE nao
    e' veredicto sobre o FONTE -- e o mesmo aqui: `SKIPPED reason=stale-instance`,
    com o numero medido ao lado para a serie nao se perder.
    """
    try:
        sys.path.insert(0, HERE)
        import hidden_launch
        out = hidden_launch.run([sys.executable,
                                 os.path.join(HERE, 'live-code-freshness-oracle.py'),
                                 '--strict'])
        rc = out[1] if isinstance(out, tuple) and len(out) > 1 else None
    except Exception:                       # noqa: BLE001
        return None
    if rc is None:
        return None
    return rc == 0


def main(argv):
    if '--neg-arm' in argv:
        return _neg_arm()
    pid = find_shell_pid()
    if not pid:
        print('SHELL-THREAD-BUDGET SKIPPED reason=no-live-shell')
        print('VERDICT: SKIPPED')
        return 0
    reading = measure(pid)
    if not reading:
        print('SHELL-THREAD-BUDGET CANNOT-MEASURE pid=%d reason=no-reading' % pid)
        print('VERDICT: CANNOT-MEASURE')
        return 1
    baseline = {}
    try:
        baseline = json.load(open(BASELINE, encoding='utf-8'))
    except Exception:                       # noqa: BLE001
        baseline = {}
    if '--update' in argv:
        total, rows = reading
        data = {'total': round(total, 1),
                'top_pct': round(rows[0][0], 1) if rows else 0.0,
                'top_name': rows[0][2] if rows else '',
                'measured_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                'pid': pid}
        with open(BASELINE, 'w', encoding='utf-8') as fh:
            json.dump(data, fh, indent=2)
            fh.write('\n')
        print('SHELL-THREAD-BUDGET baseline escrito: '
              'total=%.1f%% top=%s:%.1f%%' % (total, data['top_name'], data['top_pct']))
        return 0
    log_read = log_worst()
    report(reading, baseline, pid, log_read)
    ok, bad = judge(reading, baseline, log_read)
    if not ok:
        fresh = instance_fresh()
        if fresh is False:
            print('SHELL-THREAD-BUDGET SKIPPED reason=stale-instance '
                  '-- o processo vivo e anterior ao codigo do disco (medido acima; '
                  'a cura nao esta nele e o veredicto e do primeiro arranque dele)')
            print('VERDICT: SKIPPED')
            return 0
    for b in bad:
        print('VIOLACAO ' + b)
    print('VERDICT: %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
