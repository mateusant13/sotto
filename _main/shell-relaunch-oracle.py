"""Gate: o dono nunca precisa de aprovar uma largada para ver o codigo novo.

O QUE ESTE ORACULO FIXA (ordem do dono, verbatim 2026-10-30)
    "vai dar launch sozinho no sotto. e eu nao quero que essa merda precise de mim
     aprovando nada"

As armas leem CODIGO (AST para Python, `schtasks /query` para a tarefa), nunca comentarios:
quem documenta a regra nao pode ser castigado por a documentar.

ARMS
  1  o modulo existe e o `--selftest` passa (as seis guardas + o disparo)
  2  o disparo e' a TAREFA AGENDADA do dono (`schtasks /run`), nunca um processo criado a mao
  3  o shell ARMA o vigia no arranque (chamada real no codigo, nao um comentario)
  4  ha' uma saida para quem nao quer o vigia (bandeira E variavel), e as duas dizem porque
  5  piso / tecto / debounce sao constantes do modulo e sao usados no `tick`
  6  a accao da tarefa corre o script com `--relaunch` (o caminho que MATOU e lancou)
  7  o script mata pelo pid DO LOG, nunca por um filtro de nome
  8  a ordem e' matar (sob a guarda `pid`) -> esperar a mutex -> lancar
  9  uma instancia so' conta como viva se GANHOU a mutex (`already_running=false`)
 10  a tarefa `SottoRelaunch` existe e aponta para o .cmd deste repo
 11  `--check` le' a instancia viva e NAO toca em nada (rc=0 com app viva)
NEG-ARM (um mutante por arma que tem de ficar vermelha)
  M1  tirar a guarda de ociosidade          -> arm 1 (selftest) vermelho
  M2  tirar o tecto por hora                -> arm 1 vermelho
  M3  trocar o disparo por `subprocess.Popen` -> arm 2 vermelho
  M4  tirar a chamada `arm(...)` do shell    -> arm 3 vermelho
  M5  matar por nome (`taskkill /IM`)        -> arm 7 vermelho
  M6  desligar o kill com `if False:`        -> arm 8 vermelho
  M7  inverter o rc do modo de controlo      -> arm 12 vermelho

UM MUTANTE NUNCA TOCA NA APP DO DONO
------------------------------------
Medido 2026-10-30: um mutante herdava a tarefa REAL e relancou a app dele a meio do neg-arm
(`relaunch pedido tag=task`, pid morto). Cada copia recebe `TASK = 'SottoNEGARM'`, e o oraculo
RECUSA correr um mutante se a copia nao ficar inerte.
"""
# BATTERY-HEAVY: app-window -- este instrumento EXERCITA o auto-relancamento do
# shell: ele larga `pythonw` com o token da app (e o `--neg-arm` repoe o direito
# culpado para exigir o `err=5` de volta). Medido 2026-10-30: os dois passos
# declarados `always` produziram dois `SHELL_STARTUP_STAGE` no log da app.

# NO-BUG: instrumento do auto-relancamento da app (`app/webview/shell_relaunch.py`) --
# mede as recusas (piso, debounce, tecto, ociosidade, som a tocar) e o disparo; nao
# corrige o vigia, le-o.
from __future__ import annotations

import argparse
import ast
import io
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
MODULE = os.path.join(ROOT, 'app', 'webview', 'shell_relaunch.py')
RELAUNCHER = os.path.join(ROOT, '_main', 'sotto-relaunch.py')
TASK_CMD = os.path.join(ROOT, '_main', 'sotto-relaunch.cmd')
TASK = 'SottoRelaunch'

PASS, FAIL = [], []


def arm(name, ok, detail=''):
    (PASS if ok else FAIL).append(name)
    print('%s %s%s' % ('PASS' if ok else 'FAIL', name, ('  -- ' + detail) if detail else ''))
    return ok


def _src(path):
    with io.open(path, encoding='utf-8') as fh:
        return fh.read()


def _func_src(tree, text, name):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(text, node) or ''
    return ''


def _call_names(text):
    """Nomes de funcao chamados, por AST (nao por texto)."""
    tree = ast.parse(text)
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            target = node.func
            if isinstance(target, ast.Attribute):
                out.add(target.attr)
            elif isinstance(target, ast.Name):
                out.add(target.id)
    return out


def arm_1_selftest(root):
    result = subprocess.run([sys.executable,
                             os.path.join(root, 'app', 'webview', 'shell_relaunch.py'),
                             '--selftest'], capture_output=True, close_fds=True, creationflags=subprocess.CREATE_NO_WINDOW)
    tail = (result.stdout or b'').decode('utf-8', 'replace').strip().splitlines()[-1:] or ['']
    return arm('1 o selftest do vigia passa', result.returncode == 0, tail[0][:90])


def arm_2_fire_is_the_task(root):
    text = _src(os.path.join(root, 'app', 'webview', 'shell_relaunch.py'))
    tree = ast.parse(text)
    body = _func_src(tree, text, '_run_task')
    ok = 'schtasks' in body and "'/run'" in body
    manual = [tok for tok in ('CreateProcess', 'Popen', 'execv', 'startfile') if tok in body]
    return arm('2 o disparo e a tarefa agendada do dono', ok and not manual,
               'manual=%s' % (manual,) if manual else '')


def arm_3_shell_arms_it(root):
    text = _src(os.path.join(root, 'app', 'webview', 'sotto_webview.py'))
    names = _call_names(text)
    ok = 'arm' in names and 'shell_relaunch' in text
    # `ast.unparse` e nao `get_source_segment`: o segundo e' O(ficheiro) por chamada, e
    # este ficheiro tem 790 KB com centenas de `if` -- uma versao passou 78 s so' aqui.
    tree = ast.parse(text)
    guarded = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = ast.unparse(node.test)
        if 'no_self_relaunch' in test and 'SOTTO_NO_SELF_RELAUNCH' in test:
            if 'shell_relaunch.arm' in ast.unparse(node):
                guarded = True
    return arm('3 o shell arma o vigia no arranque', ok and guarded,
               '' if guarded else 'a chamada nao esta dentro do ramo da saida')


def arm_4_optout(root):
    text = _src(os.path.join(root, 'app', 'webview', 'sotto_webview.py'))
    ok = ("'--no-self-relaunch'" in text and 'SOTTO_NO_SELF_RELAUNCH' in text
          and 'SHELL_RELAUNCH_DISABLED reason=' in text)
    return arm('4 ha saida (bandeira e variavel) e ela diz porque', ok)


def arm_5_constants(root):
    text = _src(os.path.join(root, 'app', 'webview', 'shell_relaunch.py'))
    tree = ast.parse(text)
    consts = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant):
                consts[target.id] = node.value.value
    tick = _func_src(tree, text, 'tick')
    want = {'FLOOR_S': 120.0, 'CAP_PER_HOUR': 3, 'STABLE_S': 4.0}
    ok = all(consts.get(k) == v for k, v in want.items())
    used = all(k in tick for k in ('FLOOR_S', 'STABLE_S')) and 'within_cap' in tick
    return arm('5 piso/tecto/debounce sao constantes E usados', ok and used,
               str({k: consts.get(k) for k in want}))


def arm_6_task_action(root):
    path = os.path.join(root, '_main', 'sotto-relaunch.cmd')
    if not os.path.exists(path):
        return arm('6 a accao da tarefa corre o script com --relaunch', False, 'sem .cmd')
    text = _src(path)
    ok = 'sotto-relaunch.py' in text and '--relaunch' in text
    return arm('6 a accao da tarefa corre o script com --relaunch', ok)


def arm_7_kill_by_pid(root):
    text = _src(os.path.join(root, '_main', 'sotto-relaunch.py'))
    tree = ast.parse(text)
    kill = _func_src(tree, text, 'kill')
    ok = "'/PID'" in kill and "'/IM'" not in kill
    return arm('7 mata pelo pid do log, nunca por nome', ok)


def arm_8_order(root):
    text = _src(os.path.join(root, '_main', 'sotto-relaunch.py'))
    tree = ast.parse(text)
    main = _func_src(tree, text, 'main')
    i_kill = main.find('kill(pid)')
    i_wait = main.find('wait_mutex_free()')
    i_launch = main.find('launch_via_task()')
    ok = -1 < i_kill < i_wait < i_launch
    # A GUARDA DO KILL TEM DE SER `pid`, NAO UMA CONSTANTE. Um `if False:` mantem a ORDEM
    # no texto e desliga o kill: a instancia antiga segura a mutex, o sucessor e' recusado,
    # e o dono fica sem app -- o pior resultado desta ideia. (Apanhado pelo proprio
    # neg-arm: o mutante M6 sobrevivia a um braco so' textual.)
    guards = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and 'kill(pid)' in ast.unparse(node):
            guards.append(ast.unparse(node.test).strip())
    return arm('8 matar (sob a guarda `pid`) -> esperar a mutex -> lancar',
               ok and 'pid' in guards, 'guards=%s kill=%d wait=%d launch=%d'
               % (guards, i_kill, i_wait, i_launch))


def arm_9_winner_only(root):
    text = _src(os.path.join(root, '_main', 'sotto-relaunch.py'))
    ok = 'already_running=false' in text and 'def live_shell_pid' in text
    return arm('9 so conta como viva a instancia que GANHOU a mutex', ok)


def arm_10_task_registered(root):
    result = subprocess.run(['schtasks', '/query', '/tn', TASK, '/xml'], capture_output=True,
                            close_fds=True, creationflags=subprocess.CREATE_NO_WINDOW)
    text = (result.stdout or b'').decode('cp850', 'replace')
    ok = result.returncode == 0 and 'sotto-relaunch.cmd' in text
    highest = '<RunLevel>HighestAvailable</RunLevel>' in text
    return arm('10 a tarefa existe e corre o .cmd deste repo', ok,
               'rc=%d highest=%s' % (result.returncode, highest))


def arm_11_check_readonly(root):
    result = subprocess.run([sys.executable, os.path.join(root, '_main', 'sotto-relaunch.py'),
                             '--check'], capture_output=True, close_fds=True, creationflags=subprocess.CREATE_NO_WINDOW)
    out = (result.stdout or b'').decode('utf-8', 'replace')
    ok = result.returncode in (0, 1) and 'instancia viva' in out and 'mutex livre' in out
    return arm('11 `--check` le e nao toca (rc=0 com app viva)', ok,
               out.strip().replace('\n', ' | ')[:90])


# ------------------------------------------------------------------ neg-arm

MUTANTS = [
    ('ociosidade', 'M1', 'shell_relaunch.py',
     "        if busy:\n            return 'wait'",
     "        if False:\n            return 'wait'"),
    ('tecto', 'M2', 'shell_relaunch.py',
     "        allowed, recent = within_cap(_read_counter(self.counter_path)['relaunches'], now)",
     "        allowed, recent = True, []"),
    ('disparo', 'M3', 'shell_relaunch.py',
     "        result = subprocess.run(['schtasks', '/run', '/tn', task], capture_output=True,\n"
     "                                close_fds=True)",
     "        result = subprocess.Popen(['pythonw', 'x.py']); return True, 'x'"),
    ('armar', 'M4', 'sotto_webview.py',
     '            shell_relaunch.arm(shell, log)',
     '            pass  # shell_relaunch.arm(shell, log)'),
    # ANCORA RE-MEDIDA EM 2026-10-30: a linha viva virou `   result = subprocess.run([...`
    # (tres espacos + `result = `, `sotto-relaunch.py:159`), e o mutante descrevia a forma
    # ANTIGA -- "nao ancorava", logo o braco do kill-por-NOME ficava sem prova. O defeito que
    # ele injecta e' o que ja' matou dois processos alheios neste repo.
    ('nome', 'M5', 'sotto-relaunch.py',
     "   result = subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'],",
     "   result = subprocess.run(['taskkill', '/IM', 'pythonw.exe', '/F'],"),
    ('ordem', 'M6', 'sotto-relaunch.py',
     '    if pid:\n        if not kill(pid):',
     '    if False:\n        if not kill(pid):'),
    ('rc-do-controlo', 'M7', 'shell-relaunch-oracle.py',
     '    print(\'NEG-ARM PASS -- %d mutante(s), cada um derrubado por um braco nomeado\' % len(MUTANTS))\n'
     '    return 1',
     '    print(\'NEG-ARM PASS -- %d mutante(s), cada um derrubado por um braco nomeado\' % len(MUTANTS))\n'
     '    return 0'),
]


def _copy_repo(tmp):
    for sub in ('app/webview', 'app/panel', '_main'):
        src = os.path.join(ROOT, *sub.split('/'))
        dst = os.path.join(tmp, *sub.split('/'))
        os.makedirs(dst, exist_ok=True)
        for name in os.listdir(src):
            path = os.path.join(src, name)
            if os.path.isfile(path) and name.endswith(('.py', '.js', '.html', '.cmd')):
                shutil.copy2(path, os.path.join(dst, name))


def _neutralise(tmp):
    """Cada copia recebe uma tarefa que NAO EXISTE. Devolve quantos ficheiros ficaram inertes."""
    neutral = 0
    for cand in (os.path.join(tmp, 'app', 'webview', 'shell_relaunch.py'),
                 os.path.join(tmp, '_main', 'sotto-relaunch.py')):
        if not os.path.exists(cand):
            continue
        body = _src(cand)
        touched = False
        for const in ("TASK = 'SottoRelaunch'", "TASK = 'Sotto'"):
            if const in body:
                body = body.replace(const, "TASK = 'SottoNEGARM'", 1)
                touched = True
        if touched:
            with io.open(cand, 'w', encoding='utf-8') as fh:
                fh.write(body)
            neutral += 1
    return neutral


def run_neg_arm():
    """Uma copia do repo por mutante; afirma que o oraculo fica VERMELHO por AQUELE braco."""
    print('NEG-ARM: %d mutante(s)' % len(MUTANTS))
    broken = 0
    for label, tag, rel, old, new in MUTANTS:
        tmp = tempfile.mkdtemp(prefix='sotto-relaunch-neg-')
        try:
            _copy_repo(tmp)
            neutral = _neutralise(tmp)
            if neutral < 2:
                print('  %s %s RECUSA: a copia nao ficou inerte (neutral=%d)'
                      % (tag, label, neutral))
                broken += 1
                continue
            path = os.path.join(tmp, 'app', 'webview', rel)
            if not os.path.exists(path):
                path = os.path.join(tmp, '_main', rel)
            text = _src(path)
            if text.count(old) != 1:
                print('  %s %s NAO ANCORA (%d ocorrencia(s)) -- o mutante descreve codigo que '
                      'ja nao existe' % (tag, label, text.count(old)))
                broken += 1
                continue
            with io.open(path, 'w', encoding='utf-8') as fh:
                fh.write(text.replace(old, new, 1))
            result = subprocess.run([sys.executable, os.path.abspath(__file__), '--arms-only',
                                     '--root', tmp], capture_output=True, close_fds=True, creationflags=subprocess.CREATE_NO_WINDOW)
            out = (result.stdout or b'').decode('utf-8', 'replace')
            reds = [line.split()[1] for line in out.splitlines() if line.startswith('FAIL')]
            if result.returncode != 0 and reds:
                print('  %s %s KILLED by %s' % (tag, label, ','.join(reds)))
            else:
                print('  %s %s SOBREVIVEU (o oraculo continuou verde)' % (tag, label))
                broken += 1
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    # O CODIGO DE SAIDA DESTE MODO E' INVERTIDO, e e' assim que a casa o le: o passo
    # `red-as-expected-*` da bateria exige **rc=1** ("o defeito injectado foi encontrado")
    # mais a string `NEG-ARM PASS` no log. rc=0 aqui significa que algum mutante SOBREVIVEU.
    if broken:
        print('NEG-ARM FAIL -- %d mutante(s) sem braco (rc=0: nenhum defeito encontrado)'
              % broken)
        return 0
    print('NEG-ARM PASS -- %d mutante(s), cada um derrubado por um braco nomeado' % len(MUTANTS))
    return 1


def arm_12_negarm_rc(root):
    """O modo de controlo sai **1** quando apanha o defeito (a casa le rc=1 como sucesso)."""
    detail = _src(os.path.join(root, '_main', 'shell-relaunch-oracle.py'))
    ok = 'return 1\n\n\ndef main' in detail or ("return 0 if not FAIL else 1" in detail
                                                  and "return 1\n" in detail)
    # a condicao real: no ramo `if broken:` a funcao devolve 0, e fora dele devolve 1
    tree = ast.parse(detail)
    fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'run_neg_arm':
            fn = node
    if fn is None:
        return arm('12 o modo de controlo sai 1 ao apanhar o defeito', False, 'sem run_neg_arm')
    src = ast.unparse(fn)
    branch = src.split('if broken:')[-1].split('return')[1].strip()[:1]
    tail = src.strip().rsplit('return', 1)[-1].strip()[:1]
    return arm('12 o modo de controlo sai 1 ao apanhar o defeito',
               branch == '0' and tail == '1', 'ramo_falha=%s ramo_sucesso=%s' % (branch, tail))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--neg-arm', action='store_true')
    ap.add_argument('--arms-only', action='store_true')
    ap.add_argument('--root', default=ROOT)
    args = ap.parse_args(argv)
    if args.neg_arm:
        return run_neg_arm()
    root = os.path.abspath(args.root)
    print('SHELL-RELAUNCH ORACLE  root=%s' % root)
    arm_1_selftest(root)
    arm_2_fire_is_the_task(root)
    arm_3_shell_arms_it(root)
    arm_4_optout(root)
    arm_5_constants(root)
    arm_6_task_action(root)
    arm_7_kill_by_pid(root)
    arm_8_order(root)
    arm_9_winner_only(root)
    arm_10_task_registered(root)
    arm_11_check_readonly(root)
    arm_12_negarm_rc(root)
    print('SHELL-RELAUNCH VERDICT %s -- arms=%d pass=%d fail=%d'
          % ('GREEN' if not FAIL else 'VERMELHO', len(PASS) + len(FAIL), len(PASS), len(FAIL)))
    return 0 if not FAIL else 1


if __name__ == '__main__':
    raise SystemExit(main())
