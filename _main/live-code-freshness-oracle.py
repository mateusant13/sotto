#!/usr/bin/env pythonw.exe
# -*- coding: utf-8 -*-
# NO-BUG: instrumento READ-ONLY que compara o hash do processo VIVO com o do
# ficheiro em disco e diz STALE quando uma afirmacao sobre comportamento foi
# feita contra uma arvore editada; nao corrige nada.
"""LIVE-CODE FRESHNESS -- o processo que o dono carrega e' o da arvore?

O ERRO QUE ISTO EXISTE PARA MATAR (medido na pele dele, 2026-10-30)
------------------------------------------------------------------
O dono carregou Alt+C e disse, verbatim: *"EU TO APERTANDO ALT C E TA LIGANDO
E DESLIGANDO A LEGENDA PORRA. O QUE EU FALEI QUE E PRA ACONTECER?"*. O
contrato novo (1 toque = painel de BAIXO, 2 = DIREITA, HOLD = legenda) ja'
estava no disco. A instancia que ele carregava era de **01:12:39**, anterior a
esse codigo, e o log dela provava-o sem ambiguidade:

    etiquetas que o FONTE actual sabe escrever: HOTKEY_HOLD, HOTKEY_PRESSED, ...
    etiquetas que o LOG VIVO escreve:  HOTKEY_SINGLE x186, HOTKEY_DOUBLE x36,
                                       HOTKEY_CAPTION_UNDONE x28

`HOTKEY_SINGLE` tem **zero** ocorrencias no fonte. Quatro oraculos estavam
verdes nesse momento, e tinham razao: julgavam FICHEIROS. Ele carregava num
PROCESSO. Nenhum instrumento comparava os dois.

O QUE ESTE INSTRUMENTO RESPONDE
-------------------------------
  FRESH    o processo que escreve o log carregou o codigo que esta' no disco.
  STALE    o processo e' anterior a uma ou mais alteracoes -- e diz QUAIS.
  UNKNOWN  nao ha log, ou nao ha linha de arranque: nao se sabe. Unknown NAO
           e' fresh (a regra deste repo: `unknown` nao e' `green`).

DUAS PROVAS, PORQUE UMA SO' NAO CHEGA
-------------------------------------
  A  EXACTA (para o futuro): o shell passou a registar no arranque
     `SHELL_CODE_ID sha256=... files=7`. Compara-se com o `code_identity()`
     calculado agora, **pela mesma funcao do shell** (importada, nunca copiada:
     duas implementacoes da mesma coisa divergem).
  B  RETROACTIVA (para os processos que ja' estao a correr e nao tem a
     etiqueta): o instante da linha `SHELL_STARTUP_STAGE` da ultima corrida
     contra o `mtime` de cada ficheiro de codigo. Um processo que arrancou
     antes de um ficheiro mudar correu o ficheiro VELHO, mesmo sem etiqueta.

     E' a prova B que teria apanhado o pid 33288, porque ele nasceu antes de a
     etiqueta existir.

USO
---
    python _main/live-code-freshness-oracle.py            # rc=0 sempre, imprime o veredicto
    python _main/live-code-freshness-oracle.py --strict   # rc=3 se STALE (para quem vai afirmar comportamento)
    python _main/live-code-freshness-oracle.py --control  # as DUAS provas contra logs sinteticos

NAO lanca nada, nao toca na app, nao abre janela: le um ficheiro de log e faz
`stat` e `sha256`. Pode correr em qualquer altura, inclusive com o dono a
trabalhar.
"""# NO-BUG: instrumento READ-ONLY que compara o hash do processo VIVO com o do ficheiro
# em disco e diz STALE quando uma afirmacao sobre comportamento foi feita contra uma
# arvore editada; nao corrige nada.

import argparse
import importlib.util
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SHELL_DIR = os.path.join(REPO, "app", "webview")
SHELL = os.path.join(SHELL_DIR, "sotto_webview.py")
DEFAULT_LOG = os.path.join(HERE, "webview-run.log")

TAIL_BYTES = 4 * 1024 * 1024   # o log cresce para centenas de MB; o arranque
                               # da ULTIMA corrida esta' no fim


def _read_tail(path, limit=TAIL_BYTES):
    with open(path, 'rb') as fh:
        try:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - limit))
        except OSError:
            fh.seek(0)
        return fh.read().decode('utf-8', 'replace')


def _last(lines, needle):
    for line in reversed(lines):
        if needle in line:
            return line
    return ''


def _stamp_of(line):
    """`2026-10-30 04:29:24.092` -> epoch local (None se nao casar)."""
    if not line:
        return None
    head = line.split(' sotto:')[0].strip()
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S'):
        try:
            return time.mktime(time.strptime(head, fmt))
        except ValueError:
            continue
    return None


def _code_files(mod, here=None):
    """A lista vem do SHELL e e' a MESMA que o processo etiquetou (2026-11-05).

    O portao recalculava uma lista PROPRIA (`_CODE_ID_FILES` + os globs da
    pagina) enquanto o processo escrevia outra, e as duas ficaram em atraso ao
    mesmo tempo: `youtube_cdp_source.py` -- o ficheiro que decide qual legenda
    vai ao ecra -- nao estava em nenhuma. Medido hoje, `code_id=DDC13167DF83`
    antes e depois de uma cura nele: o portao dizia `FRESH` sobre um processo
    que carregou outro codigo. Agora os dois leem `code_files()` do proprio
    modulo do shell; sem ele (modulo antigo no disco) cai na lista curada, que
    ainda e' melhor do que nada.
    """
    here = here or SHELL_DIR
    fn = getattr(mod, 'code_files', None)
    if callable(fn):
        try:
            return list(fn(here))
        except Exception:                    # noqa: BLE001
            pass
    names = list(getattr(mod, '_CODE_ID_FILES', ()))
    globs = getattr(mod, '_CODE_ID_GLOBS', ())
    if globs:
        import glob as _glob
        for pattern in globs:
            for pth in sorted(_glob.glob(os.path.join(here, pattern))):
                names.append(os.path.relpath(pth, here))
    return names


def load_shell():
    if SHELL_DIR not in sys.path:
        sys.path.insert(0, SHELL_DIR)
    spec = importlib.util.spec_from_file_location('_freshness_shell', SHELL)
    mod = importlib.util.module_from_spec(spec)
    sys.modules['_freshness_shell'] = mod
    spec.loader.exec_module(mod)     # NAO arranca nada: `main()` so' corre em __main__
    return mod


def judge(mod, text):
    """-> (verdict, detail_dict). Puro: nao le o disco do log outra vez."""
    lines = text.splitlines()
    start_line = _last(lines, 'SHELL_STARTUP_STAGE') or _last(lines, 'SHELL_START')
    code_line = _last(lines, 'SHELL_CODE_ID')
    started = _stamp_of(start_line)
    started_stamp = start_line.split(' sotto:')[0].strip() if started else ''
    disk = getattr(mod, 'code_identity')()
    pid = ''
    for part in start_line.split():
        if part.startswith('pid='):
            pid = part[4:]
            break
    detail = {'pid': pid, 'started': started_stamp, 'disk': disk,
              'process': '', 'changed_after': [], 'missing': []}

    # ── A: a prova exacta (o processo carregou a etiqueta?) ────────────────
    stamp = ''
    if 'sha256=' in code_line:
        stamp = code_line.split('sha256=', 1)[1].split()[0].strip()
    detail['process'] = ('sha256=' + stamp) if stamp else '(sem SHELL_CODE_ID)'
    if stamp and 'sha256=' in disk:
        disk_hash = disk.split('sha256=', 1)[1].split()[0].strip()
        if stamp != disk_hash:
            return 'STALE', dict(detail, why='a etiqueta do processo nao e a do '
                                            'disco (hash diferente)')
        return 'FRESH', dict(detail, why='hash do processo == hash do disco')

    # ── B: a prova retroactiva (mtime contra o instante do arranque) ───────
    if started is None:
        return 'UNKNOWN', dict(detail, why='sem linha de arranque no log')
    changed = []
    for name in _code_files(mod):
        path = os.path.join(SHELL_DIR, name)
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            detail['missing'].append(name)
            continue
        if mtime > started:
            changed.append(name)
    detail['changed_after'] = changed
    if changed:
        return 'STALE', dict(detail, why='%d ficheiro(s) mudaram depois de o '
                                         'processo arrancar' % len(changed))
    return 'FRESH', dict(detail, why='nenhum ficheiro mudou depois do arranque')


def report(verdict, detail, log_path):
    print('LIVE_CODE %s log=%s' % (verdict, log_path))
    print('  pid=%s started=%s' % (detail.get('pid') or '?',
                                   detail.get('started') or '?'))
    print('  processo: %s' % (detail.get('process') or '?'))
    print('  disco   : %s' % (detail.get('disk') or '?'))
    print('  porque  : %s' % (detail.get('why') or '?'))
    if detail.get('changed_after'):
        for name in detail['changed_after']:
            print('  MUDOU DEPOIS DO ARRANQUE: %s' % name)
    if detail.get('missing'):
        print('  ausente do disco: %s' % ', '.join(detail['missing']))
    if verdict == 'STALE':
        print('  >>> O QUE O DONO CARREGA NAO E ESTE CODIGO. Nenhuma '
              'afirmacao sobre comportamento vale aqui:')
        print('  >>> fechar a app e abrir de novo ANTES de julgar o sintoma.')


def _identity_of(mod, here):
    """A etiqueta de uma pasta, pela funcao REAL (o shell re-exporta com dois nomes)."""
    for name in ('_code_identity', 'code_identity'):
        fn = getattr(mod, name, None)
        if not callable(fn):
            continue
        try:
            return fn(here)
        except TypeError:
            continue
    return None


def _identity_arms(mod, here=None):
    """(fails, notas) -- A ETIQUETA COBRE O CODIGO QUE DECIDE O COMPORTAMENTO.

    A CLASSE (medida 2026-11-05): `_CODE_ID_FILES` era uma lista CURADA de sete
    nomes e `youtube_cdp_source.py` -- o ficheiro que decide qual legenda vai ao
    ecra -- nao estava nela. A cura do prazo do CDP entrou no disco, a app foi
    relancada com ela, e o `code_id` da instancia nova era IDENTICO ao da
    anterior: o portao diria `FRESH` sobre um processo que carregou outro
    codigo. As arms julgam a FUNCAO REAL, nao o texto:

      I1 cobertura  -- todo `*.py` da pasta do shell esta na lista.
      I2 sensivel   -- mudar UM byte de `youtube_cdp_source.py` muda a etiqueta.
      I3 estavel    -- a mesma arvore da' a MESMA etiqueta (a de I2 nao e' ruido).
      I4 worker     -- o OUTRO processo da app entra na etiqueta: mudar um byte de
                       `worker/live_queue.py` numa arvore com a forma real
                       (`<root>/app/webview` + `<root>/worker`) muda o hash. Sem
                       esta arm, uma cura no worker entrava no disco com o portao a
                       dizer `FRESH` -- medido 2026-11-05 no passo 0 do bug-hunt.
    """
    import glob as _g
    import shutil
    import tempfile
    here = here or SHELL_DIR
    fails, notes = [], []
    files = set(os.path.basename(x) for x in _code_files(mod))
    have = set(os.path.basename(p) for p in _g.glob(os.path.join(here, '*.py')))
    for name in ('youtube_cdp_source.py', 'code_identity.py', 'sotto_webview.py'):
        have.add(name) if os.path.exists(os.path.join(here, name)) else None
    missing = sorted(have - files)
    notes.append('I1 cobertura: %d de %d .py na etiqueta%s'
                 % (len(have) - len(missing), len(have),
                    (', fora: %r' % missing[:6]) if missing else ''))
    if missing:
        fails.append('I1 cobertura')
    tmp = tempfile.mkdtemp(prefix='sotto-identity-')
    try:
        for name in files & have:
            try:
                shutil.copy2(os.path.join(here, name), os.path.join(tmp, name))
            except OSError:
                pass
        a = _identity_of(mod, tmp)
        b = _identity_of(mod, tmp)
        notes.append('I3 estavel: %s' % ('igual' if a == b else 'MUDOU'))
        if a != b:
            fails.append('I3 estavel')
        target = os.path.join(tmp, 'youtube_cdp_source.py')
        if os.path.exists(target):
            with open(target, 'ab') as fh:
                fh.write(b'\n# arm I2')
            c = _identity_of(mod, tmp)
            notes.append('I2 sensivel: %s -> %s'
                         % ('muda' if c != a else 'NAO MUDA', c.split()[0]))
            if c == a:
                fails.append('I2 sensivel')
        else:
            fails.append('I2 sensivel (o ficheiro nao esta na etiqueta)')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    # -- I4: O WORKER ---------------------------------------------------------
    # A arvore tem de ter a FORMA real (`<root>/app/webview` + `<root>/worker`),
    # senao o glob do worker (`../../worker/*.py`) nao tem para onde apontar e a
    # arm mediria o vazio.
    root = tempfile.mkdtemp(prefix='sotto-identity-worker-')
    try:
        shell_dir = os.path.join(root, 'app', 'webview')
        worker_dir = os.path.join(root, 'worker')
        os.makedirs(shell_dir, exist_ok=True)
        os.makedirs(worker_dir, exist_ok=True)
        shell_file = 'code_identity.py'
        shutil.copy2(os.path.join(here, shell_file), os.path.join(shell_dir, shell_file))
        worker_file = 'live_queue.py'
        shutil.copy2(os.path.join(SHELL_DIR, '..', '..', 'worker', worker_file),
                     os.path.join(worker_dir, worker_file))
        names = set(os.path.basename(x) for x in _code_files(mod, shell_dir))
        notes.append('I4 worker: %s na etiqueta: %s'
                     % (worker_file, 'SIM' if worker_file in names else 'NAO'))
        if worker_file not in names:
            fails.append('I4 worker (ausente da lista)')
        w0 = _identity_of(mod, shell_dir)
        with open(os.path.join(worker_dir, worker_file), 'ab') as fh:
            fh.write(b'\n# arm I4')
        w1 = _identity_of(mod, shell_dir)
        notes.append('I4 worker sensivel: %s -> %s'
                     % ('muda' if w1 != w0 else 'NAO MUDA', w1.split()[0]))
        if w1 == w0:
            fails.append('I4 worker sensivel')
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return fails, notes


def control(mod):
    """As duas provas contra logs sinteticos: cada uma tem de dar o seu veredicto.

    Sem isto, um instrumento que imprime STALE e' indistinguivel de um
    instrumento que imprimiria STALE sempre.
    """
    print('CONTROL -- a prova A e a prova B, cada uma com o seu veredicto')
    fails = []
    disk = getattr(mod, 'code_identity')()
    disk_hash = disk.split('sha256=', 1)[1].split()[0].strip()
    now = time.strftime('%Y-%m-%d %H:%M:%S.000',
                        time.localtime(time.time() - 3600))     # 1 h atras
    future = time.strftime('%Y-%m-%d %H:%M:%S.000',
                           time.localtime(time.time() + 3600))

    cases = [
        ('A-igual', 'FRESH',
         '%s sotto: SHELL_STARTUP_STAGE pid=1 stage=pre-lock\n'
         '%s sotto: SHELL_CODE_ID sha256=%s files=7\n' % (now, now, disk_hash)),
        ('A-diferente', 'STALE',
         '%s sotto: SHELL_STARTUP_STAGE pid=1 stage=pre-lock\n'
         '%s sotto: SHELL_CODE_ID sha256=000000000000 files=7\n' % (now, now)),
        ('B-arranque-no-futuro', 'FRESH',
         '%s sotto: SHELL_STARTUP_STAGE pid=2 stage=pre-lock\n' % (future,)),
        ('B-arranque-ha-uma-hora', 'STALE',
         '%s sotto: SHELL_STARTUP_STAGE pid=3 stage=pre-lock\n' % (now,)),
        ('sem-arranque', 'UNKNOWN', 'sotto: nada de util aqui\n'),
    ]
    for name, want, text in cases:
        got, _detail = judge(mod, text)
        ok = got == want
        print('%s %-24s want=%-7s got=%s' % ('GREEN' if ok else 'RED  ',
                                             name, want, got))
        if not ok:
            fails.append(name)

    id_fails, id_notes = _identity_arms(mod)
    for note in id_notes:
        print('       %s' % note)
    for name in id_fails:
        print('RED   %-24s a etiqueta nao cobre o codigo que decide o ecra'
              % name)
        fails.append(name)
    if fails:
        print('CONTROL FAIL (%d)' % len(fails))
        return 1
    print('CONTROL PASS -- as duas provas distinguem FRESH de STALE, e a '
          'ausencia de arranque e UNKNOWN (nunca fresh)')
    return 0


def neg_arm():
    """A MUTACAO QUE TEM DE CAIR: a lista curada volta a ser a unica (2026-11-05).

    Uma copia de `code_identity.py` sem o glob do directorio e' carregada; a arm
    I1 tem de a recusar. Sem isto, "a etiqueta cobre todos os `.py`" e' uma
    afirmacao que ninguem prova -- e foi exatamente assim que
    `youtube_cdp_source.py` ficou fora dela.
    """
    import shutil
    import tempfile
    tmp = tempfile.mkdtemp(prefix='sotto-identity-mutant-')
    try:
        copy = os.path.join(tmp, 'code_identity.py')
        shutil.copy2(os.path.join(SHELL_DIR, 'code_identity.py'), copy)
        with open(copy, encoding='utf-8', newline='') as fh:
            text = fh.read()
        needle = "        for _p in sorted(_glob.glob(os.path.join(here, '*.py'))):"
        if text.count(needle) != 1:
            print('NEG-ARM: IMPOSSIVEL -- o sitio mudou (%d)' % text.count(needle))
            return 2
        text = text.replace(needle, "        for _p in sorted(()):")
        with open(copy, 'w', encoding='utf-8', newline='') as fh:
            fh.write(text)
        spec = importlib.util.spec_from_file_location('_ci_mutant', copy)
        mutant = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mutant)
        fails, notes = _identity_arms(mutant)
        for note in notes:
            print('       %s' % note)
        caught = 'I1 cobertura' in fails
        print('%s mutant "lista curada outra vez" -> fails=%r'
              % ('RED   ' if caught else 'SURVIVED', fails))
        if caught:
            print('NEG-ARM: PASS -- a arm I1 derruba o mutante')
            return 1
        print('NEG-ARM: FAIL -- o mutante passou')
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--log', default=DEFAULT_LOG)
    ap.add_argument('--strict', action='store_true',
                    help='rc=3 quando STALE (um step de bateria nao usa isto)')
    ap.add_argument('--control', action='store_true',
                    help='prova as duas provas contra logs sinteticos')
    ap.add_argument('--neg-arm', action='store_true',
                    help='muta uma COPIA de code_identity.py e exige o RED')
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:  # noqa: BLE001
        pass

    try:
        mod = load_shell()
    except Exception as exc:  # noqa: BLE001
        print('LIVE_CODE UNKNOWN -- a shell nao importa: %r' % (exc,))
        return 2

    if args.control:
        return control(mod)

    if args.neg_arm:
        return neg_arm()

    if not os.path.exists(args.log):
        print('LIVE_CODE UNKNOWN -- nao ha log em %s (app nunca correu aqui?)'
              % args.log)
        return 0

    verdict, detail = judge(mod, _read_tail(args.log))
    report(verdict, detail, args.log)
    if args.strict and verdict != 'FRESH':
        return 3 if verdict == 'STALE' else 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
