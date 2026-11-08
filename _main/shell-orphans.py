"""ORFAOS DA SHELL: quem largou a app e nao a recolheu.

Nasceu da DM de stutter de 2026-11-08: `pythonw.exe(55104)`, cmdline desta arvore
(`sotto_webview.py --log ... --no-self-relaunch --ready-file _main\ready-*-*.txt`),
PAI MORTO (`?(43148)`), 108 % de UM nucleo e `SottoNativeCaption` pintado as 17:47 e
as 18:11 no ecra do dono. Nao era uma lane viva: era o resto dela.

O `run.cmd` faz `start` DETACHED (de proposito: a app fica escondida por dias), por
isso "pai morto" NAO distingue um orfao de uma largada legitima -- a app do dono
tambem nasce sem pai. Por isso este instrumento NAO MATA NADA: ele NOMEIA. Uma
listagem que o dono pode ler e um pid que o chamador pode matar; um matador
automatico que erra o alvo mata a app dele no meio da transcricao.

    python _main/shell-orphans.py            # lista
    python _main/shell-orphans.py --gate      # rc=1 quando ha orfao (passo da bateria)

Um orfao aqui e' uma shell cujo pai morreu E cuja idade cabe na janela
(`--max-age-min`, default 240): a app do dono tambem nasce sem pai, mas tem dias de
idade, enquanto o resto de um passo nasce DURANTE a corrida. As duas leituras sao
impressas (ORFAO/PAI-VIVO + idade), para que um falso positivo seja visivel a olho.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL_NAME = 'sotto_webview.py'
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
_STARTUP = None
if os.name == 'nt':
    _STARTUP = subprocess.STARTUPINFO()
    _STARTUP.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    _STARTUP.wShowWindow = 0


def _ps(script):
    out = subprocess.run(
        ['powershell', '-NoProfile', '-NonInteractive', '-Command', script],
        capture_output=True, text=True, encoding='cp850', errors='replace',
        creationflags=NO_WINDOW, startupinfo=_STARTUP)
    return out.stdout


PS = r'''
$procs = Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*sotto_webview.py*' }
$all = @{}
foreach ($p in Get-CimInstance Win32_Process) { $all[$p.ProcessId] = $p }
$rows = foreach ($p in $procs) {
  $parent = $all[$p.ParentProcessId]
  [pscustomobject]@{
    pid = $p.ProcessId
    name = $p.Name
    parent = $p.ParentProcessId
    parent_alive = [bool]$parent
    cmdline = $p.CommandLine
    started = $p.CreationDate
  }
}
$rows | ConvertTo-Json -Compress
'''


def census():
    raw = _ps(PS).strip()
    if not raw:
        return []
    data = json.loads(raw)
    if isinstance(data, dict):
        data = [data]
    return [r for r in data if SHELL_NAME in (r.get('cmdline') or '')]


def judge_rows(rows, max_age):
    """Julga a lista: (orfaos DESTA janela, linhas de impressao)."""
    fresh, lines = [], []
    for r in rows:
        age = _age_min(r)
        orphan = not r.get('parent_alive')
        lines.append('SHELL-ORPHANS %s pid=%s name=%s parent=%s idade=%s min'
                     % ('ORFAO' if orphan else 'PAI-VIVO', r['pid'], r.get('name'),
                        r.get('parent'), '?' if age is None else '%.1f' % age))
        if orphan and age is not None and age <= max_age:
            fresh.append(r)
    return fresh, lines


def neg_arm():
    """CONTROLE: cria um orfao DE VERDADE (filho cujo pai morre) e exige que o
    censo o nomeie. Nenhuma janela, nenhum audio, nenhum modelo: o "orfao" e' um
    `time.sleep` com a cadeia de argumentos da shell."""
    import time
    py = sys.executable
    fake = os.path.join(REPO, 'app', 'webview', SHELL_NAME)
    # O intermediario larga o neto e sai: o neto fica sem pai, como o medido.
    mid = ('import subprocess,sys\n'
           'subprocess.Popen([sys.executable, "-c", "import time;time.sleep(25)", %r])\n'
           % fake)
    subprocess.run([py, '-c', mid], timeout=30,
                   creationflags=NO_WINDOW, startupinfo=_STARTUP)
    time.sleep(2.0)
    rows = census()
    caught, _ = judge_rows(rows, 240.0)
    for r in caught:
        try:
            subprocess.run(['taskkill', '/PID', str(r['pid']), '/F'], timeout=20,
                           creationflags=NO_WINDOW, startupinfo=_STARTUP,
                           capture_output=True, text=True, encoding='cp850',
                           errors='replace')
        except Exception:      # noqa: BLE001
            pass
    ok = bool(caught)
    print('NEG-ARM %s -- orfaos plantados=%d nomeados=%d'
          % ('PASS' if ok else 'FAIL', 1, len(caught)))
    return 1 if ok else 0


def _age_min(row):
    """Idade em minutos a partir do `/Date(...)` do CIM, ou None."""
    import datetime
    raw = row.get('started') or ''
    digits = ''.join(ch for ch in str(raw) if ch.isdigit())[:13]
    if not digits:
        return None
    try:
        born = datetime.datetime.utcfromtimestamp(int(digits) / 1000.0)
    except (ValueError, OverflowError):
        return None
    return (datetime.datetime.utcnow() - born).total_seconds() / 60.0


def main(argv):
    if '--neg-arm' in argv:
        return neg_arm()
    gate = '--gate' in argv
    # O TECTO DE IDADE (medido 2026-11-08): a app do DONO tambem nasce sem pai --
    # o `run.cmd` faz `start` DETACHED --, por isso "pai morto" sozinho acusaria a
    # app dele em TODA a corrida. O portao julga o orfao NASCIDO AGORA (janela de
    # 240 min, a mesma ordem de grandeza de um run), e imprime a idade de cada um
    # para que um falso positivo seja visivel a olho.
    max_age = 240.0
    for a in argv:
        if a.startswith('--max-age-min='):
            max_age = float(a.split('=', 1)[1])
    rows = census()
    if not rows:
        print('SHELL-ORPHANS none -- nenhum processo desta arvore carrega %s' % SHELL_NAME)
        return 0
    fresh = []
    for r in rows:
        age = _age_min(r)
        orphan = not r.get('parent_alive')
        tag = 'ORFAO' if orphan else 'PAI-VIVO'
        print('SHELL-ORPHANS %s pid=%s name=%s parent=%s idade=%s min'
              % (tag, r['pid'], r.get('name'), r.get('parent'),
                 '?' if age is None else '%.1f' % age))
        if orphan and age is not None and age <= max_age:
            fresh.append(r)
    print('SHELL-ORPHANS total=%d orfaos_nesta_janela=%d janela=%.0fmin'
          % (len(rows), len(fresh), max_age))
    if gate and fresh:
        # Nomear e' o portao: uma largada que ninguem recolheu vira divida visivel,
        # nunca um culpado de stutter descoberto horas depois pelo watcher.
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
