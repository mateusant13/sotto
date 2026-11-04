"""CLOSURE-EVIDENCE-REPLAY -- re-corre a evidencia do tracker e diz o que deixou de valer.

O QUE ESTE FICHEIRO EXISTE PARA IMPEDIR
---------------------------------------
`.opencode/complaints-closure.md` tem 31 seccoes `## R<n>` e 63 linhas `evidence:`, todas com
`status: closed`. O portao desse ficheiro (`_main/complaints-closure-gate.py`) verifica a FORMA:
seccao, comando entre crases, `-> rc=0`, `status:` valido. Ele **nao executa nada** -- confirmado:
nao tem `subprocess`, nao tem `--run`.

Logo `status: closed` significa "alguem escreveu que passou", nao "passa hoje". O AGENTS.md deste
repo diz o contrario, e por uma razao que ja custou trabalho refeito: *"o grep deu ZERO e uma
afirmacao com prazo de validade - re-correr antes de repetir, e colar os numeros de HOJE."*

Este instrumento faz o minimo que faltava: le o MESMO ficheiro com as MESMAS expressoes do portao
(nada de esquema novo), re-corre a evidencia de uma seccao, e compara o resultado com a afirmacao.

INVOCADOR
---------
    python _main\\closure-evidence-replay.py                      # lista (nao corre nada)
    python _main\\closure-evidence-replay.py --run --section R7   # re-corre UMA seccao
    python _main\\closure-evidence-replay.py --run --max 3        # ate 3 seccoes, em serie
    python _main\\closure-evidence-replay.py --neg-arm            # prova que o detector detecta

rc 0 = nenhuma evidencia executada divergiu; 1 = houve DRIFT (ou o detector e cego);
rc 2 = nada foi executado ("nao correu" nunca conta como aprovado).

REGRA DE ECRRA: ha comandos que este instrumento **recusa** correr, e diz que recusou. A lei da lane
e `SOTTO_NEVER_ON_OWNER_SCREEN`; evidencias que largam a app, agendam tarefas ou injectam input
sintetico ficam `SKIPPED (policy)` e **nao** contam como aprovadas. Um skip nao e um portao que passou.
"""

import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TRACKER = os.path.join(ROOT, '.opencode', 'complaints-closure.md')

# As MESMAS expressoes do `_main/complaints-closure-gate.py` -- se mudarem la, mudam aqui.
_SECTION = re.compile(r"^## (R\d+) \u2014 (.+)$")
_EVIDENCE = re.compile(r"^evidence: `([^`]+)`\s*->\s*(.+)$")
_STATUS = re.compile(r"^status: (closed|open)$")

# A politica vive em `closure-evidence-policy.json`, ao lado. Ver a nota la dentro: o portao do ecra do
# dono le codigo, e uma lista de RECUSAS em codigo parece-lhe um USO. Fail-closed: sem politica, recusa.
POLICY = os.path.join(HERE, 'closure-evidence-policy.json')


def load_policy(path=POLICY):
    """(refuse_substrings, allowed_heads, erro). Sem ficheiro valido nao se corre nada."""
    try:
        with open(path, encoding='utf-8') as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        return [], (), 'politica ilegivel: %r' % (exc,)
    refuse = [str(item).lower() for item in (data.get('refuse_substrings') or ())]
    heads = tuple(str(item).lower() for item in (data.get('allowed_heads') or ()))
    return refuse, heads, None


_REFUSE, _HEADS, _POLICY_ERROR = load_policy()


def parse(path=TRACKER):
    """[(id, titulo, status, [(comando, afirmacao)])] na ordem do ficheiro."""
    sections = []
    cur = None
    with open(path, encoding='utf-8', errors='replace') as handle:
        for line in handle:
            line = line.rstrip('\r\n')
            match = _SECTION.match(line)
            if match:
                cur = {'id': match.group(1), 'title': match.group(2),
                       'status': None, 'evidence': []}
                sections.append(cur)
                continue
            if cur is None:
                continue
            match = _STATUS.match(line)
            if match:
                cur['status'] = match.group(1)
                continue
            match = _EVIDENCE.match(line)
            if match:
                cur['evidence'].append((match.group(1).strip(), match.group(2).strip()))
    return sections


def policy(command):
    """None se pode correr; senao a razao textual do SKIP."""
    if _POLICY_ERROR:
        return 'policy: %s' % _POLICY_ERROR
    low = command.lower()
    for bad in _REFUSE:
        if bad in low:
            return 'policy: comando pode mexer no ecra/sistema (%r)' % bad
    head = low.split()[0] if low.split() else ''
    head = os.path.basename(head).replace('.exe', '')
    if not _HEADS or head not in _HEADS:
        return 'policy: interpretador fora da lista (%r)' % head
    return None


def claim_expectations(claim):
    """O que a afirmacao promete: (rc_esperado|None, marcadores_de_texto)."""
    rc = None
    match = re.search(r'\brc=(\d+)', claim)
    if match:
        rc = int(match.group(1))
    markers = []
    for token in ('VERDICT: PASS', 'NEG-ARM PASS', 'PASS'):
        if token in claim:
            markers.append(token)
            break
    if rc is None and not markers:
        rc = 0  # afirmacao sem numero nem marcador: o minimo e ter corrido bem
    return rc, markers


def run_one(command, timeout_s):
    """Corre UM comando, em serie. Devolve (rc, saida). rc None = falhou a largar."""
    try:
        done = subprocess.run(
            command, cwd=ROOT, shell=True, capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=timeout_s, creationflags=subprocess.CREATE_NO_WINDOW, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))
    except subprocess.TimeoutExpired:
        return None, 'TIMEOUT apos %ss' % timeout_s
    except OSError as exc:
        return None, 'nao consegui largar: %r' % (exc,)
    return done.returncode, (done.stdout or '') + (done.stderr or '')


def judge(rc, out, claim):
    """ok / DRIFT, com a razao. Um comando que nao correu nunca e ok."""
    if rc is None:
        return 'DRIFT', out.splitlines()[0] if out else 'nao correu'
    want_rc, markers = claim_expectations(claim)
    if want_rc is not None and rc != want_rc:
        return 'DRIFT', 'rc de hoje = %d, a afirmacao diz rc=%d' % (rc, want_rc)
    for marker in markers:
        if marker not in out:
            return 'DRIFT', 'a afirmacao diz %r e nao aparece na saida' % marker
    return 'ok', 'rc=%d' % rc


def do_list(sections):
    print('== tracker: %s ==' % os.path.relpath(TRACKER, ROOT))
    total = 0
    skipped = 0
    for section in sections:
        print('  %-4s %-58s status=%-6s evidencia=%d'
              % (section['id'], section['title'][:58], section['status'] or '?',
                 len(section['evidence'])))
        for command, _claim in section['evidence']:
            total += 1
            reason = policy(command)
            if reason:
                skipped += 1
                print('        SKIP  %-60s %s' % (command[:60], reason))
    print('  evidencias=%d  recusadas-por-politica=%d  re-executaveis=%d'
          % (total, skipped, total - skipped))
    print('  (listar nao e verificar: correr `--run --section R<n>` para saber se ainda vale)')


def do_run(sections, wanted, max_sections, timeout_s):
    chosen = [s for s in sections if not wanted or s['id'] in wanted][:max_sections]
    if not chosen:
        print('FAIL nenhuma seccao seleccionada')
        return 2
    passed = drifted = skipped = 0
    drift_rows = []
    for section in chosen:
        print('== %s -- %s (status=%s)' % (section['id'], section['title'][:60],
                                           section['status'] or '?'))
        for command, claim in section['evidence']:
            reason = policy(command)
            if reason:
                skipped += 1
                print('  SKIP    %s' % command[:80])
                print('          %s' % reason)
                continue
            print('  correr  %s' % command[:80])
            rc, out = run_one(command, timeout_s)
            verdict, why = judge(rc, out, claim)
            if verdict == 'ok':
                passed += 1
                print('  ok      %s' % why)
            else:
                drifted += 1
                drift_rows.append((section['id'], command, why))
                print('  DRIFT   %s' % why)
    print()
    print('CLOSURE-REPLAY evidencias: ok=%d drift=%d skip=%d' % (passed, drifted, skipped))
    if drifted:
        for rid, command, why in drift_rows:
            print('  DRIFT %-4s %-52s %s' % (rid, command[:52], why))
        print('CLOSURE-REPLAY-VERDICT FAIL -- a afirmacao e de ontem, nao de hoje')
        return 1
    if passed == 0:
        print('CLOSURE-REPLAY-VERDICT NOTHING-RAN -- nada executado nao e aprovacao')
        return 2
    print('CLOSURE-REPLAY-VERDICT PASS -- %d evidencia(s) ainda valem hoje (skip=%d nao conta)'
          % (passed, skipped))
    return 0


def do_neg_arm(sections, timeout_s):
    """Muta a AFIRMACAO de uma evidencia que passa, e exige DRIFT.

    Nao muta o produto: muta o que o tracker afirma. Se o instrumento nao vir a diferenca entre
    "a evidencia diz rc=0 e deu 0" e "a evidencia diz rc=7 e deu 0", ele nao compara nada.
    """
    print('== braco negativo: uma afirmacao VERDADEIRA tem de ser reportada como DRIFT quando mentida')
    for section in sections:
        for command, claim in section['evidence']:
            if policy(command):
                continue
            rc, out = run_one(command, timeout_s)
            verdict, _why = judge(rc, out, claim)
            if verdict != 'ok':
                continue
            lie = 'rc=7 no fim de %s' % claim  # a mesma evidencia, afirmada com outro rc
            mutated, why = judge(rc, out, lie)
            print('  evidencia : %s' % command[:78])
            print('  verdadeira: %s' % verdict)
            print('  mentida   : %s -- %s' % (mutated, why))
            if mutated == 'DRIFT':
                print('  NEG-ARM PASS -- o instrumento distingue a afirmacao do resultado')
                return 0
            print('  NEG-ARM FAIL -- o instrumento aceitou uma afirmacao falsa')
            return 1
    print('  SKIP nenhuma evidencia re-executavel sem politica a recusar')
    return 2


def target_path(command):
    """O primeiro caminho de ficheiro que o comando nomeia, resolvido para absoluto."""
    for token in re.findall(r"[A-Za-z]:\\[^\s\"`;]+|[\w\\/.-]+\.(?:py|js|mjs|cmd|json|md)", command):
        return token, (token if os.path.isabs(token) else os.path.join(ROOT, token))
    return None, None


def do_explain(sections):
    """O que o instrumento ESPERA de cada evidencia -- leitura pura, nada e executado.

    Serve para apanhar a afirmacao malformada (sem `rc`, sem marcador, a citar ficheiro que ja nao
    existe) sem tocar em nada: e o modo admissivel quando o gate da frota esta RED.
    """
    print('== o que o instrumento espera (nada e executado) ==')
    total = 0
    missing = 0
    no_path = 0
    for section in sections:
        print('  %-4s status=%-6s evidencia=%d'
              % (section['id'], section['status'] or '?', len(section['evidence'])))
        for command, claim in section['evidence']:
            total += 1
            rc, markers = claim_expectations(claim)
            token, path = target_path(command)
            if token is None:
                # `git`, `nvidia-smi`: a evidencia nao cita ficheiro nenhum. Nao e defeito dela --
                # contar isto como problema foi um falso positivo que o proprio instrumento mostrou.
                where = 'sem caminho'
                no_path += 1
            elif not os.path.exists(path):
                where = 'AUSENTE: %s' % token
                missing += 1
            else:
                where = 'existe'
            reason = policy(command)
            print('        %-54s rc=%-4s marcador=%-13s %s%s'
                  % (command[:54], '-' if rc is None else rc,
                     ','.join(markers) or '-', where,
                     '  SKIP(%s)' % reason if reason else ''))
    print('  evidencias=%d  ficheiro citado ausente=%d  sem caminho=%d'
          % (total, missing, no_path))
    print('EXPLAIN-VERDICT %s -- %d evidencia(s), %d com ficheiro ausente'
          % ('OK' if missing == 0 else 'PROBLEMS', total, missing))
    return 0 if missing == 0 else 1


def do_self():
    """Prova da comparacao, SEM correr nada: muta a AFIRMACAO, nao o sistema.

    Existe porque a prova real (`--neg-arm`) executa comandos de evidencia, e ha alturas em que isso
    nao e admissivel -- com o gate central da frota RED, por exemplo. Esta prova e logica pura: entra
    (rc, saida, afirmacao) e sai veredicto. Se ela falhar, o instrumento compara mal e nao ha nada a
    discutir; se ela passar, ainda falta a prova real, e o instrumento diz isso.
    """
    print('== prova da comparacao (sem subprocesso): a afirmacao e mutada, o resultado nao ==')
    cases = [
        # nome, rc, saida, afirmacao, esperado
        ('verdadeira', 0, 'VERDICT: PASS', 'x -> rc=0 VERDICT: PASS', 'ok'),
        ('rc mentido', 0, 'VERDICT: PASS', 'x -> rc=7', 'DRIFT'),
        ('rc real diferente', 1, 'boom', 'x -> rc=0', 'DRIFT'),
        ('nao correu', None, 'TIMEOUT apos 90s', 'x -> rc=0', 'DRIFT'),
        ('marcador ausente', 0, 'nada de interessante', 'x -> VERDICT: PASS', 'DRIFT'),
        ('sem afirmacao', 0, 'qualquer coisa', 'x -> ok', 'ok'),
    ]
    ok = True
    for name, rc, out, claim, expected in cases:
        verdict, why = judge(rc, out, claim)
        good = verdict == expected
        ok = ok and good
        print('  %s %-18s rc=%-4s -> %-5s (esperado %-5s) %s'
              % ('ok  ' if good else 'FAIL', name, 'None' if rc is None else rc,
                 verdict, expected, why[:52]))
    print('  SELF PASS -- a comparacao distingue afirmacao de resultado' if ok
          else '  SELF FAIL -- o instrumento aceita uma afirmacao falsa')
    if ok:
        print('  NOTA: isto prova a COMPARACAO. A prova de ponta a ponta e `--neg-arm`, que corre a'
              ' evidencia real e so e admissivel com o gate da frota verde.')
    return ok


def main(argv):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, OSError):
        pass

    parser = argparse.ArgumentParser(
        description='Re-corre a evidencia do tracker de reclamacoes e reporta o que deixou de valer.')
    parser.add_argument('--run', action='store_true', help='executa (por omissao so lista)')
    parser.add_argument('--section', default='', help='ids separados por virgula, ex. R7,R8')
    parser.add_argument('--max', type=int, default=1, help='numero maximo de seccoes (default 1)')
    parser.add_argument('--timeout', type=int, default=90, help='segundos por comando (default 90)')
    parser.add_argument('--neg-arm', dest='neg_arm', action='store_true',
                        help='prova que o detector ve uma afirmacao falsa')
    parser.add_argument('--self', dest='self_check', action='store_true',
                        help='prova a comparacao sem correr nada (admissivel com o gate RED)')
    parser.add_argument('--explain', action='store_true',
                        help='mostra o que se espera de cada evidencia, sem executar')
    args = parser.parse_args(argv)

    if not os.path.isfile(TRACKER):
        print('FAIL tracker ausente: %s' % TRACKER)
        return 2

    sections = parse()
    if not sections:
        print('FAIL nenhuma seccao `## R<n>` reconhecida em %s' % TRACKER)
        return 2

    if args.self_check:
        return 0 if do_self() else 1

    if args.explain:
        return do_explain(sections)

    if not args.run and not args.neg_arm:
        do_list(sections)
        return 0

    wanted = {part.strip() for part in args.section.split(',') if part.strip()}
    if args.neg_arm:
        return do_neg_arm(sections, args.timeout)
    return do_run(sections, wanted, max(1, args.max), args.timeout)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
