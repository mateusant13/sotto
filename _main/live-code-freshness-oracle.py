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


def _changed_since(names, dirpath, started):
    """A PROVA B, PURA: (mudaram, ausentes). Facto HISTORICO, nao re-derivavel.

    `started` vem da linha de arranque do log e os `mtime` sao passados -- as duas
    pontas sao facto gravado, nenhuma e' "agora". E' esta a prova que um leitor
    pode repetir mais tarde e obter o MESMO veredicto (a prova A compara com o
    disco de hoje, e essa referencia MOVE-SE a cada commit).
    """
    changed, missing = [], []
    for name in names:
        path = os.path.join(dirpath, name)
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            missing.append(name)
            continue
        # TOLERANCIA DE 1 s: o instante do arranque vem do log truncado ao
        # segundo e o `mtime` tem sub-segundo -- sem isto um ficheiro gravado no
        # MESMO segundo do arranque aparecia como "mudou depois" (medido no
        # proprio `--control`, caso `A-igual`: FRESH virava STALE). Um ficheiro
        # tocado dentro do 1 s do arranque fica coberto pela prova A.
        if mtime > started + 1.0:
            changed.append(name)
    return changed, missing


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

    # AS DUAS PROVAS CORREM SEMPRE (2026-11-09). A prova A decide sozinha hoje, e
    # o defeito disso foi medido: ela compara a etiqueta GRAVADA no arranque com o
    # hash do disco AGORA -- a segunda ponta move-se a cada commit, logo o veredicto
    # nao e' reproduzivel depois ("disco=3FED08353D1B" citado as 13:0x e
    # "72CB6AC71423" minutos mais tarde, os dois verdadeiros e nenhum auditavel).
    # A prova B compara dois factos GRAVADOS (instante do arranque x mtime), e essa
    # o leitor de amanha repete e obtem o mesmo. Agora as duas aparecem no relatorio
    # e a A nao esconde a B.
    stamp = ''
    if 'sha256=' in code_line:
        stamp = code_line.split('sha256=', 1)[1].split()[0].strip()
    detail['process'] = ('sha256=' + stamp) if stamp else '(sem SHELL_CODE_ID)'
    a_differs = None
    if stamp and 'sha256=' in disk:
        disk_hash = disk.split('sha256=', 1)[1].split()[0].strip()
        a_differs = stamp != disk_hash
        detail['disk_hash'] = 'sha256=' + disk_hash
    detail['disk_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    detail['proof_a'] = a_differs
    if started is None:
        if a_differs:
            return 'STALE', dict(detail, why='a etiqueta do processo nao e a do '
                                            'disco (hash diferente); sem linha de '
                                            'arranque nao ha prova B')
        return 'UNKNOWN', dict(detail, why='sem linha de arranque no log')
    changed, missing = _changed_since(_code_files(mod), SHELL_DIR, started)
    detail['changed_after'] = changed
    detail['missing'] = detail['missing'] + missing
    detail['proof_b'] = len(changed)
    if a_differs:
        why = ('a etiqueta do processo nao e a do disco AGORA (prova A, referencia '
               'movel); a prova B confirma: %d ficheiro(s) mudaram depois do '
               'arranque' % len(changed))
        if not changed:
            why = ('a etiqueta do processo nao e a do disco AGORA (prova A), mas '
                   'nenhum ficheiro tem mtime depois do arranque -- leitura a '
                   'repetir: pode ser a arvore a mudar durante a medida')
        return 'STALE', dict(detail, why=why)
    if changed:
        return 'STALE', dict(detail, why='%d ficheiro(s) mudaram depois de o '
                                         'processo arrancar (prova B: mtime x '
                                         'arranque, ambos gravados)' % len(changed))
    return 'FRESH', dict(detail, why='hash do processo == hash do disco e nenhum '
                                     'ficheiro mudou depois do arranque')


def report(verdict, detail, log_path):
    print('LIVE_CODE %s log=%s' % (verdict, log_path))
    print('  pid=%s started=%s' % (detail.get('pid') or '?',
                                   detail.get('started') or '?'))
    print('  processo: %s   <- GRAVADO no arranque, nao muda' %
          (detail.get('process') or '?'))
    print('  disco   : %s   <- lido AGORA (%s), move-se a cada commit' %
          (detail.get('disk') or '?', detail.get('disk_at') or '?'))
    pa = detail.get('proof_a')
    print('  prova A : %s' % ('hash diferente' if pa else
                              ('hash igual' if pa is False else 'indisponivel')))
    pb = detail.get('proof_b')
    print('  prova B : %s' % ('%d ficheiro(s) com mtime depois do arranque'
                              % pb if pb is not None else 'indisponivel'))
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
    # AS DUAS PONTAS SAEM DO CODIGO, NAO DO RELOGIO (medido 2026-11-05). A arm
    # "arranque ha uma hora" usava `agora - 3600` e o veredicto dela dependia de
    # ALGUEM ter tocado num ficheiro da shell na ultima hora: numa corrida em que
    # nada mudou desde entao, `FRESH` e' a resposta CERTA e a arm ficava vermelha
    # por um facto do mundo, nao por um defeito do instrumento. Agora o arranque
    # e' derivado do mtime mais NOVO dos ficheiros que o instrumento julga:
    # 60 s antes deles (logo o codigo e' mais novo -> STALE) e 1 h depois (o
    # arranque e' posterior a todo o codigo -> FRESH).
    newest = 0.0
    for _name in _code_files(mod):
        try:
            newest = max(newest, os.path.getmtime(os.path.join(SHELL_DIR, _name)))
        except OSError:
            continue
    if newest <= 0.0:
        newest = time.time()
    now = time.strftime('%Y-%m-%d %H:%M:%S.000',
                        time.localtime(newest - 60))            # 1 min antes do codigo
    future = time.strftime('%Y-%m-%d %H:%M:%S.000',
                           time.localtime(newest + 3600))

    # `now` = 1 min ANTES do ficheiro mais novo (o codigo mudou depois do
    # arranque -> a prova B dispara); `future` = 1 h DEPOIS (nenhum ficheiro
    # mudou depois do arranque -> a prova B cala). Cada caso escolhe a ponta que
    # isola a prova que quer medir: com as duas provas sempre a correr (2026-11-09)
    # um caso com arranque ANTERIOR ao codigo e hash igual e' internamente
    # contraditorio -- o processo nao podia ter o hash da arvore que ainda nao
    # existia --, e por isso ele passa a medir o que de facto mede: a prova B.
    cases = [
        ('A-igual', 'FRESH',
         '%s sotto: SHELL_STARTUP_STAGE pid=1 stage=pre-lock\n'
         '%s sotto: SHELL_CODE_ID sha256=%s files=7\n' % (future, future, disk_hash)),
        ('A-diferente', 'STALE',
         '%s sotto: SHELL_STARTUP_STAGE pid=1 stage=pre-lock\n'
         '%s sotto: SHELL_CODE_ID sha256=000000000000 files=7\n' % (future, future)),
        ('B-manda-com-A-igual', 'STALE',
         '%s sotto: SHELL_STARTUP_STAGE pid=4 stage=pre-lock\n'
         '%s sotto: SHELL_CODE_ID sha256=%s files=7\n' % (now, now, disk_hash)),
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


FRESH_LOG = os.path.join(HERE, '_cache', 'live-code-freshness.jsonl')
FRESH_LOG_MAX = 256 * 1024     # o log do dono enche um disco; este registo nao


def _record(verdict, detail, log_path):
    """UM REGISTO POR AVALIACAO -- para "o que ele dizia as 13:20" ter resposta.

    Sem isto, cada invocacao compara um facto gravado com o PRESENTE e o numero
    citado numa DM deixa de ser reproduzivel minutos depois (medido 2026-11-09:
    o mesmo ficheiro lido duas vezes em 20 min deu dois hashes diferentes e os
    dois estavam certos). O ficheiro e' append-only, roda por tamanho, e nunca
    impede o veredicto: falhar a escrever aqui nao muda o rc.
    """
    import json
    try:
        os.makedirs(os.path.dirname(FRESH_LOG), exist_ok=True)
        try:
            if os.path.getsize(FRESH_LOG) > FRESH_LOG_MAX:
                os.replace(FRESH_LOG, FRESH_LOG + '.1')
        except OSError:
            pass
        rec = {'at': time.strftime('%Y-%m-%d %H:%M:%S'), 'verdict': verdict,
               'log': log_path, 'pid': detail.get('pid') or '',
               'started': detail.get('started') or '',
               'boot_hash': detail.get('process') or '',
               'disk_hash_at': detail.get('disk_hash') or '',
               'proof_a': detail.get('proof_a'),
               'proof_b_changed': detail.get('proof_b'),
               'changed_after': (detail.get('changed_after') or [])[:40],
               'why': detail.get('why') or ''}
        with open(FRESH_LOG, 'a', encoding='utf-8', newline='') as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
    except Exception:                                          # noqa: BLE001
        pass


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
    _record(verdict, detail, args.log)
    if args.strict and verdict != 'FRESH':
        return 3 if verdict == 'STALE' else 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
