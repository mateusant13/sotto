# NO-BUG: O CUSTO DA ESCADA DE DISPOSITIVOS, EM SEGUNDOS, ANTES/DEPOIS. -- instrumento de custo pedido pelo dono ("levou 3 segundos ... arruma"); nao corresponde a nenhum id de `_main/bug-ledger.json`, e declarado aqui em vez de inventar um id.
"""O CUSTO DA ESCADA DE DISPOSITIVOS, EM SEGUNDOS -- e a cura, medida.

O DEFEITO QUE ISTO JULGA (medido 2026-11-11, `_main/webview-run.log`, sessao pid
49180; as linhas estao citadas verbatim em `LOG_SAMPLES` com o numero delas):

  17:34:42.832  LADDER_TRY attempt=1/11 device='WASAPI loopback: VoiceMeeter Input ...' ms=16 result=opened
  17:34:42.834  STATUS capture-started
  17:34:49.620  STATUS tap-silent-desktop
  17:35:26.461  STATUS device-rotated (flat)        <- 43,6 s depois de abrir
  17:35:27.496  LADDER_TRY attempt=2/11 device='WASAPI loopback: CABLE Input ...' ms=46 result=opened

O primeiro rung era o DEFAULT (`VoiceMeeter Input`), entregou ZERO, e ficou
43,6 s aberto. A janela plana e' 6 s (`window_s=6.0` na linha
`NO_AUDIO_CLEARED evidence=`): ~37 s dos 43,6 foram ESPERA, nao decisao --
`silent_desktop_hold` dobra a espera (6 -> 12 -> 24 -> 48 -> 60) e so' pergunta
ao medidor VIVO no fim de cada extensao. E o rung que TINHA o audio do dono
(`CABLE Input`) era o segundo, porque nada lembrava qual endpoint carregou audio
na sessao anterior.

O QUE ESTE ORACULO EXECUTA. Nunca abre dispositivo, nunca renderiza, nunca
lanca processo: so' funcoes puras e um ficheiro temporario de journal.

  * `worker/sotto_worker.py::silent_desktop_hold` -- a funcao REAL, replicada
    com as amostras do log (medidor calado aos 6 s e aos 18 s, sinal aos 42 s;
    derivado do proprio registo: o rung nao rotacionou aos 6 nem aos 18 s, e
    rotacionou aos 42 s). O ANTES e' a mesma funcao com o tecto de 2026-11-11
    REMOVIDO numa copia (`_before_copy`), que e' exactamente a politica
    historica 6->12->24->48; o DEPOIS e' o ficheiro como esta' na arvore.
  * `worker/wasapi_loopback.py::endpoint_rank_key` -- a ordem da escada, com e
    sem journal, com verdicts frescos e expirados, e com o medidor vivo a mandar.
  * `record_endpoint_verdict` / `endpoint_verdicts` -- o journal, num ficheiro
    temporario (`SOTTO_ENDPOINT_JOURNAL`), incluindo ficheiro corrupto.
  * `tap_verdict` -- a classificacao da evidencia do proprio tap.

Uso:  python _main/device-ladder-cost-oracle.py
      python _main/device-ladder-cost-oracle.py --neg-arm
rc=0  PASS (`VERDICT: PASS (n/n)`)
rc=1  FAIL  (ou, no `--neg-arm`, todos os mutantes APANHADOS: `NEG-ARM: PASS (m/m)`)
rc=2  o mutante nem correu (ancora ausente -- o oraculo esta' velho)
"""
import argparse
import ast
import importlib.util
import os
import sys
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.abspath(os.path.join(HERE, '..', 'worker', 'sotto_worker.py'))
WL = os.path.abspath(os.path.join(HERE, '..', 'worker', 'wasapi_loopback.py'))
WORKER_DIR = os.path.dirname(WORKER)

#: As copias deste oraculo sao importadas por caminho. Um `.pyc` reaproveitado
#: entre dois mutantes do MESMO tamanho, escritos no mesmo segundo, serve o
#: codigo do mutante anterior -- medido aqui: o M3 era julgado com o bytecode do
#: M2 e "escapava" pelo arm errado. Sem bytecode nao ha' cache que minta.
sys.dont_write_bytecode = True

FLOOR = 0.002          # `TAP_PEAK_FLOOR`; o arm 12 afirma-o nos dois ficheiros
WINDOW = 6.0           # `--tap-window` por omissao, e `window_s=6.0` no log
MAX_WINDOW = 60.0      # `TAP_SILENT_DESKTOP_MAX_S`
QUIET = {'vm': 0.0, 'cable': 0.0}
LOUD = {'vm': 0.0, 'cable': 0.264}

#: As linhas do log que este oraculo replica. Cada entrada e' (linha_do_log,
#: texto verbatim); `_main/webview-run.log` e' a fonte.
LOG_SAMPLES = [
    (192457, "2026-11-11 17:34:20.559 sotto: BRIDGE_SPAWNED pid=54524 ... "
             "SOTTO_AUDIO_DEVICE=(unset)"),
    (192603, "2026-11-11 17:34:42.832 sotto: WORKER LADDER_TRY attempt=1/11 "
             "device='WASAPI loopback: VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)' "
             "api=None ms=16 retries=0 result=opened"),
    (192604, "2026-11-11 17:34:42.834 sotto: STATUS_APPLIED text=\"capture-started\""),
    (192606, "2026-11-11 17:34:49.620 sotto: STATUS_APPLIED text=\"tap-silent-desktop\""),
    (192646, "2026-11-11 17:35:26.461 sotto: STATUS_APPLIED text=\"device-rotated (flat)\""),
    (192647, "2026-11-11 17:35:27.496 sotto: WORKER LADDER_TRY attempt=2/11 "
             "device='WASAPI loopback: CABLE Input (VB-Audio Virtual Cable)' "
             "api=None ms=46 retries=0 result=opened"),
    (192656, "2026-11-11 17:35:34.282 sotto: STATUS_APPLIED text=\"tap-own-endpoint-loud\""),
    (192742, "2026-11-11 17:36:30.315 sotto: NO_AUDIO_CLEARED reason=caption captions=1 "
             "evidence=\"device-rotated reason=flat peak=0.0 floor=0.002 "
             "from=WASAPI loopback: VoiceMeeter Input (VB-Audio VoiceMeeter VAIO) "
             "to=WASAPI loopback: CABLE Input (VB-Audio Virtual Cable) window_s=6.0\""),
    (192744, "2026-11-11 17:36:30.732 sotto: WORKER CAPTURE_SIGNAL_BACK gap_s=63 blocks=1072 "
             "captions=1 device='WASAPI loopback: CABLE Input (VB-Audio Virtual Cable)'"),
]

#: Carimbos que a tabela usa (mesmo log, mesma sessao pid 49180).
T_SPAWN = 1778618060.559        # 17:34:20.559 BRIDGE_SPAWNED pid=54524
T_OPEN_1 = 1778618082.832       # 17:34:42.832 LADDER_TRY attempt=1
T_CAPTURE_1 = 1778618082.834    # 17:34:42.834 capture-started
T_SILENT = 1778618089.620       # 17:34:49.620 tap-silent-desktop
T_ROTATE = 1778618126.461       # 17:35:26.461 device-rotated (flat)
T_OPEN_2 = 1778618127.496       # 17:35:27.496 LADDER_TRY attempt=2
T_OWN_LOUD = 1778618134.282     # 17:35:34.282 tap-own-endpoint-loud

MEASURED_OPEN_TO_ROTATE_S = T_ROTATE - T_CAPTURE_1      # 43.636 s
MEASURED_METER_READ_S = 0.755   # `live_render_peaks()` nesta maquina, 6
                                # endpoints, meter_ms=0.12 (medido 2026-11-11)
OPEN_COST_1_S = 0.016           # `ms=16` da LADDER_TRY attempt=1
OPEN_COST_2_S = 0.046           # `ms=46` da LADDER_TRY attempt=2

#: O medidor VIVO nos fins de janela, derivado do PROPRIO log: o rung nao
#: rotacionou aos 6 s nem aos 18 s (logo `loudest <= floor` nas duas) e
#: rotacionou aos 42 s (logo `loudest > floor` nessa). Nao e' uma suposicao sobre
#: o dono: e' o que o comportamento registado implica.
METER_AT = [(6.0, QUIET), (18.0, QUIET), (42.0, LOUD)]

#: O journal que a sessao anterior teria escrito: `CABLE Input` entregou sinal
#: (`tap-own-endpoint-loud` as 17:35:34.282; o pico acima do piso na linha
#: `NO_AUDIO_CLEARED`), `VoiceMeeter` entregou zero em 42 s.
JOURNAL_WARM = {
    'cable': {'verdict': 'signal', 'age_s': 300.0, 'peak': 0.264, 'blocks': 420},
    'vm': {'verdict': 'flat', 'age_s': 420.0, 'peak': 0.0, 'blocks': 420},
}
ENDPOINTS = [
    {'endpoint_id': 'vm', 'meter_peak': 0.0, 'is_default': True},
    {'endpoint_id': 'cable', 'meter_peak': 0.0, 'is_default': False},
]
DEFAULT_EP = 'vm'
SIGNAL_EP = 'cable'

#: O tecto que a cura acrescenta. O ANTES e' reconstruido removendo-o.
CAP_MARK = ', _flat_evidence_s())'
CAP_PLAIN = ', float(max_window_s))'


def _nl(text):
    return '\r\n' if '\r\n' in text else '\n'


def _strip_cap(text):
    """(texto_sem_tecto, n) -- a politica historica 6->12->24->48->60.

    n = quantas saidas foram revertidas. Uma copia do "antes" sem reversao nao e'
    o antes, e' o depois; o caller confere `n`.
    """
    nl = _nl(text)
    cap = CAP_MARK.replace('\n', nl)
    plain = CAP_PLAIN.replace('\n', nl)
    n = text.count(cap)
    return text.replace(cap, plain), n


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sibling_copy(src, tag, transform):
    """Copia `src` ao lado do original, aplicando `transform(texto)->(texto,n)`.

    Ao lado, e nao em %TEMP%: o worker importa os irmaos (`wasapi_loopback`)
    pelo nome, e uma copia noutra pasta morre com ModuleNotFoundError antes de
    qualquer arm correr (medido no `--neg-arm` do `tap-silent-desktop-oracle.py`).
    """
    text = open(src, encoding='utf-8', newline='').read()
    out, n = transform(text)
    path = os.path.join(os.path.dirname(src), '_mutant-ladder-%d-%s.py' % (os.getpid(), tag))
    with open(path, 'w', encoding='utf-8', newline='') as fh:
        fh.write(out)
    return path, n


def _mutant(src, tag, old, new, expect=1):
    """Copia com `expect` substituicoes exatas. (path, ok)."""
    text = open(src, encoding='utf-8', newline='').read()
    nl = _nl(text)
    old_nl = old.replace('\n', nl)
    if text.count(old_nl) != expect:
        return None, False
    path, _ = _sibling_copy(src, tag, lambda t: (t.replace(old_nl, new.replace('\n', nl)), 1))
    return path, True


# ── a replica da escada ──────────────────────────────────────────────────────
def _meter_lookup(table, t):
    for at, live in table:
        if abs(float(at) - float(t)) < 1e-6:
            return live
    return QUIET


def replay(hold, meter_at=None, window_s=WINDOW, max_window_s=MAX_WINDOW):
    """(segundos_ate_rotacionar, holds) -- UM candidato, com a funcao REAL.

    A primeira janela e' `window_s` (o tap so' a fecha em `now >= window_end`);
    cada extensao e' o que `hold` devolver. `None` = rotacionar.
    """
    meter_at = METER_AT if meter_at is None else meter_at
    t = float(window_s)
    k = 0
    holds = []
    while True:
        live = meter_at(t) if callable(meter_at) else _meter_lookup(meter_at, t)
        hold_s = hold(0.0, FLOOR, live, window_s, k, max_window_s)
        holds.append(hold_s)
        if hold_s is None:
            return t, holds
        t += float(hold_s)
        k += 1
        if t > 3600.0:
            return None, holds


def worst_hold(holds):
    finite = [float(h) for h in holds if h]
    return max(finite) if finite else 0.0


def order(entries, verdicts, now=1.0e6):
    """A ordem REAL (`endpoint_rank_key` do ficheiro sob teste)."""
    key = _RANK
    return [e['endpoint_id'] for e in sorted(entries, key=lambda e: key(e, verdicts, now))]


_RANK = None


# ── os arms ──────────────────────────────────────────────────────────────────
def arms(world):
    """(id, ok, detalhe) -- cada linha e' uma afirmacao verificavel."""
    w = world['worker']
    before = world['before']
    wl = world['wl']
    out = []

    def add(name, ok, detail):
        out.append((name, bool(ok), detail))

    # 1. Calibracao: a escada ANTES, com as amostras do log, reproduz o custo
    #    medido. Sem isto o "depois" nao e' comparavel com nada.
    before_rot, before_holds = replay(before.silent_desktop_hold)
    delta = MEASURED_OPEN_TO_ROTATE_S - before_rot
    add('01 antes-calibra-no-log', 0.0 <= delta <= 2.0,
        'antes=%.3fs medido=%.3fs delta=%.3fs (fecho+emit+abertura) holds=%s'
        % (before_rot, MEASURED_OPEN_TO_ROTATE_S, delta,
           [None if h is None else round(h, 1) for h in before_holds]))

    # 2. O TETO ANTES: a maior espera que a escada se da' a si propria.
    cap = before.silent_desktop_hold(0.0, FLOOR, QUIET, WINDOW, 4, MAX_WINDOW)
    add('02 antes-teto-da-espera', worst_hold(before_holds) == 24.0 and cap == 60.0,
        'pior_hold=%.1fs tecto=%s (a espera que tapa o audio mudar de sitio)'
        % (worst_hold(before_holds), cap))

    # 3. DEPOIS: a janela plana, em todos os degraus, e UM numero so'.
    caps = [w.silent_desktop_hold(0.0, FLOOR, QUIET, WINDOW, k, MAX_WINDOW)
            for k in range(5)]
    ev = getattr(w, '_flat_evidence_s', None)
    ev = ev() if callable(ev) else 'missing'
    add('03 depois-janela-plana=4s', all(c == 4.0 for c in caps) and ev == 4.0,
        'holds=%s _flat_evidence_s()=%r (era 12/24/48/60)'
        % ([None if c is None else round(c, 1) for c in caps], ev))

    # 4. DEPOIS: o pior atraso entre "o medidor ve o audio noutro endpoint" e a
    #    rotacao -- o numero que o dono sente.
    after_rot, after_holds = replay(w.silent_desktop_hold)
    bound_after = worst_hold(after_holds) + MEASURED_METER_READ_S
    bound_before = worst_hold(before_holds) + MEASURED_METER_READ_S
    add('04 atraso-max-de-reacao-cai', bound_after <= 4.8 and bound_after < bound_before,
        'antes=%.2fs (24,0+0,755) depois=%.2fs (4,0+0,755); rotacao aos %.0fs em ambas'
        % (bound_before, bound_after, after_rot))

    # 5. A ORDEM COM JOURNAL: o endpoint que entregou sinal recentemente passa a'
    #    frente do DEFAULT quando o medidor vivo nao distingue (todos 0.000).
    warm = order(ENDPOINTS, JOURNAL_WARM)
    add('05 journal-poe-o-sinal-a-frente', warm[0] == SIGNAL_EP and warm[-1] == DEFAULT_EP,
        'ordem=%s (journal: cable=signal, vm=flat)' % warm)

    # 5a. E o faz MESMO quando o default nao tem verdict nenhum (unknown, tier 2):
    #     e' esta a propriedade que o tier 1 existe para dar -- se o `signal` nao
    #     promover, um boot em que o plano do default expirou volta a abrir o
    #     default primeiro, que e' o defeito.
    o = order(ENDPOINTS, {'cable': {'verdict': 'signal', 'age_s': 60.0}})
    add('05a journal-signal-vence-o-unknown', o[0] == SIGNAL_EP,
        'ordem=%s (journal: cable=signal, vm sem verdict)' % o)

    # 5b. E o DEFAULT PROVADO PLANO vai para o fim mesmo sem nenhum sinal.
    o = order(ENDPOINTS, {'vm': {'verdict': 'flat', 'age_s': 120.0}})
    add('05b journal-manda-o-plano-para-o-fim', o[0] != DEFAULT_EP and o[-1] == DEFAULT_EP,
        'ordem=%s (journal: vm=flat, nada mais)' % o)

    # 6. SEM REGRESSAO: sem journal a ordem tem de ser EXACTAMENTE a de hoje.
    o = order(ENDPOINTS, {})
    add('06 sem-journal-a-ordem-e-a-de-hoje', o[0] == DEFAULT_EP,
        'ordem=%s (default primeiro, como antes)' % o)

    # 7. O MEDIDOR VIVO manda sempre: um verdict nao esconde um endpoint a tocar.
    live_loud = [{'endpoint_id': 'vm', 'meter_peak': 0.2, 'is_default': True},
                 {'endpoint_id': 'cable', 'meter_peak': 0.0, 'is_default': False}]
    o = order(live_loud, JOURNAL_WARM)
    add('07 medidor-vivo-vence-o-journal', o[0] == DEFAULT_EP,
        'ordem=%s (vm com meter_peak=0.2, journal diz flat)' % o)

    # 8. O verdict EXPIRA: meia hora depois a ordem volta a ser a de hoje.
    stale = {'cable': {'verdict': 'signal', 'age_s': 1801.0},
             'vm': {'verdict': 'flat', 'age_s': 1801.0}}
    o = order(ENDPOINTS, stale)
    add('08 verdict-expirado-nao-ordena', o[0] == DEFAULT_EP,
        'ordem=%s (age=1801s > TTL=%.0fs)' % (o, wl.VERDICT_TTL_S))

    # 9. O JOURNAL, num ficheiro a serio: escreve, le e ordena.
    tmp = os.path.join(HERE, '_oracle-journal-%d.json' % os.getpid())
    old_env = os.environ.get('SOTTO_ENDPOINT_JOURNAL')
    try:
        os.environ['SOTTO_ENDPOINT_JOURNAL'] = tmp
        now = 1.0e6
        wl.record_endpoint_verdict('vm', 'VoiceMeeter', 0.0, 420, 42.0, 420, 420, now=now - 420)
        wl.record_endpoint_verdict('cable', 'CABLE Input', 0.264, 420, 42.0, 420, 3, now=now - 300)
        got = wl.endpoint_verdicts(now=now)
        ok = (got.get('vm', {}).get('verdict') == 'flat'
              and got.get('cable', {}).get('verdict') == 'signal'
              and abs(got['cable']['age_s'] - 300.0) < 0.1)
        o = order(ENDPOINTS, got, now=now)
        ok = ok and o[0] == SIGNAL_EP
        with open(tmp, 'w', encoding='utf-8') as fh:      # ficheiro corrupto
            fh.write('{not json')
        ok = ok and wl.endpoint_verdicts(now=now) == {}
        add('09 journal-escreve-le-e-ordena', ok,
            'verdicts=%s ordem=%s corrupto={}'
            % ({k: v['verdict'] for k, v in got.items()}, o))
    finally:
        if old_env is None:
            os.environ.pop('SOTTO_ENDPOINT_JOURNAL', None)
        else:
            os.environ['SOTTO_ENDPOINT_JOURNAL'] = old_env
        try:
            os.remove(tmp)
        except OSError:
            pass

    # 10. Um tap que NAO ouviu o suficiente nao apaga o que um tap que ouviu escreveu.
    tmp = os.path.join(HERE, '_oracle-journal-%d.json' % os.getpid())
    old_env = os.environ.get('SOTTO_ENDPOINT_JOURNAL')
    try:
        os.environ['SOTTO_ENDPOINT_JOURNAL'] = tmp
        now = 1.0e6
        wl.record_endpoint_verdict('cable', 'CABLE Input', 0.264, 420, 42.0, 420, 3, now=now - 60)
        wrote = wl.record_endpoint_verdict('cable', 'CABLE Input', 0.0, 3, 0.3, 3, 3, now=now)
        row = wl.endpoint_verdicts(now=now).get('cable') or {}
        add('10 tap-curto-nao-apaga-verdict', wrote is None and row.get('verdict') == 'signal',
            'wrote=%r verdict=%r blocks=%r' % (wrote, row.get('verdict'), row.get('blocks')))
    finally:
        if old_env is None:
            os.environ.pop('SOTTO_ENDPOINT_JOURNAL', None)
        else:
            os.environ['SOTTO_ENDPOINT_JOURNAL'] = old_env
        try:
            os.remove(tmp)
        except OSError:
            pass

    # 10b. O TAP REAL a journalizar: `_record_verdict` le' atributos que nenhuma
    # verificacao estrutural apanha (`self.ep.endpoint_id`, nao `self.endpoint_id`)
    # -- um tap sem `.ep` escrevia ZERO e calava-se, porque o corpo engole tudo
    # para nunca partir o `close()`. Aqui o metodo verdadeiro corre contra um tap
    # com os mesmos atributos que o `_pump` escreve.
    tmp = os.path.join(HERE, '_oracle-journal-%d.json' % os.getpid())
    old_env = os.environ.get('SOTTO_ENDPOINT_JOURNAL')
    try:
        os.environ['SOTTO_ENDPOINT_JOURNAL'] = tmp

        def _tap(eid, peak, blocks, packets, silent, age=6.0):
            t = object.__new__(wl.WasapiLoopbackTap)
            t.ep = types.SimpleNamespace(endpoint_id=eid, name=eid)
            # O MESMO formato do rung do DEFAULT: o tap resolve o endpoint em
            # `.ep` e NAO recebe id nenhum. Ler `self.endpoint_id` aqui escrevia
            # `None` -- nenhuma linha, em silencio (mutante M6).
            t.endpoint_id = None
            t.packets, t.blocks_delivered = packets, blocks
            t.peak, t.silent_packets = peak, silent
            t._t_opened = time.time() - age
            t._verdict_recorded = False
            return t

        wl.WasapiLoopbackTap._record_verdict(
            _tap('ep-flat', 0.0, 420, 420, 420))     # Windows marcou SILENT em tudo
        wl.WasapiLoopbackTap._record_verdict(
            _tap('ep-loud', 0.35, 420, 420, 0))      # a tocar
        wl.WasapiLoopbackTap._record_verdict(
            _tap('ep-flat', 0.0, 5, 5, 5, age=0.3))  # curto: nao apaga
        got = wl.endpoint_verdicts()
        ok = (got.get('ep-flat', {}).get('verdict') == 'flat'
              and got.get('ep-flat', {}).get('blocks') == 420
              and got.get('ep-loud', {}).get('verdict') == 'signal')
        add('10b tap-real-escreve-signal-e-flat', ok,
            'sem_ep=%r veredictos=%s'
            % (wl.WasapiLoopbackTap._record_verdict(object.__new__(wl.WasapiLoopbackTap)) is None,
               {k: v['verdict'] for k, v in got.items()}))
    finally:
        if old_env is None:
            os.environ.pop('SOTTO_ENDPOINT_JOURNAL', None)
        else:
            os.environ['SOTTO_ENDPOINT_JOURNAL'] = old_env
        try:
            os.remove(tmp)
        except OSError:
            pass

    # 11. A evidencia do proprio tap, com os numeros desta sessao.
    rows = [
        ('rung1 flat 42s/420', wl.tap_verdict('vm', 'VoiceMeeter', 0.0, 420, 42.0, 420, 420), 'flat'),
        ('rung2 sinal', wl.tap_verdict('cable', 'CABLE Input', 0.264, 420, 42.0, 420, 3), 'signal'),
        ('tap de 0.3s', wl.tap_verdict('x', 'x', 0.0, 3, 0.3, 3, 3), 'no-data'),
        ('pico acima do piso', wl.tap_verdict('x', 'x', 0.0021, 420, 42.0, 420, 0), 'signal'),
    ]
    bad = [(n, g[0], want) for n, g, want in rows if g[0] != want]
    add('11 tap-verdict-com-os-numeros-do-log', not bad,
        'flat/signal/no-data/piso %s' % ('ok' if not bad else bad))

    # 12. O piso e' O MESMO numero nos dois ficheiros.
    add('12 piso-igual-nos-dois-ficheiros',
        float(wl.SIGNAL_PEAK_FLOOR) == float(w.TAP_PEAK_FLOOR) == FLOOR,
        'wasapi_loopback=%.6f worker=%.6f' % (wl.SIGNAL_PEAK_FLOOR, w.TAP_PEAK_FLOOR))

    # 13. O numero da janela tem UMA fonte (o tap), e o worker nao o duplica.
    src = open(getattr(w, '__file__'), encoding='utf-8', newline='').read()
    add('13 janela-plana-tem-uma-fonte',
        ('FLAT_EVIDENCE_S = 4.0' in open(getattr(wl, '__file__'), encoding='utf-8').read()
         and '_wl.FLAT_EVIDENCE_S' in src and src.count(CAP_MARK) == 2),
        'tap=%.1fs saidas_com_tecto=%d' % (wl.FLAT_EVIDENCE_S, src.count(CAP_MARK)))

    # 14. A FIACAO no ficheiro do tap: o `close()` journaliza, e a ordem le'.
    tree = ast.parse(open(getattr(wl, '__file__'), encoding='utf-8', newline='').read())
    close_calls = record_calls = rank_sort = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == 'WasapiLoopbackTap':
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name == 'close':
                    for sub in ast.walk(fn):
                        if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                                and sub.func.attr == '_record_verdict'):
                            close_calls = True
                if isinstance(fn, ast.FunctionDef) and fn.name == '_record_verdict':
                    for sub in ast.walk(fn):
                        if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                                and sub.func.id == 'record_endpoint_verdict'):
                            record_calls = True
        if isinstance(node, ast.FunctionDef) and node.name == '_live_endpoint_order':
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                        and sub.func.attr == 'sort'):
                    for kw in sub.keywords:
                        if kw.arg == 'key':
                            for leaf in ast.walk(kw.value):
                                if isinstance(leaf, ast.Name) and leaf.id == 'endpoint_rank_key':
                                    rank_sort = True
    add('14 tap-fiacao-close-e-ordem', close_calls and record_calls and rank_sort,
        'close->_record_verdict=%s _record_verdict->record=%s sort->rank_key=%s'
        % (close_calls, record_calls, rank_sort))

    return out


def table(world):
    """O antes/depois em segundos -- o que o dono sente, e o que a cura move."""
    before_rot, before_holds = replay(world['before'].silent_desktop_hold)
    after_rot, after_holds = replay(world['worker'].silent_desktop_hold)
    rows = [
        ('pior espera entre "audio visivel noutro endpoint" e rotacao',
         '%.2f s' % (worst_hold(before_holds) + MEASURED_METER_READ_S),
         '%.2f s' % (worst_hold(after_holds) + MEASURED_METER_READ_S)),
        ('pior janela plana antes de a decisao ser re-tomada',
         '%.1f s' % world['before'].silent_desktop_hold(0.0, FLOOR, QUIET, WINDOW, 4, MAX_WINDOW),
         '%.1f s' % world['worker'].silent_desktop_hold(0.0, FLOOR, QUIET, WINDOW, 4, MAX_WINDOW)),
        ('rung aberto -> rotacao nesta sessao (pid 49180)',
         '%.2f s (medido)' % MEASURED_OPEN_TO_ROTATE_S,
         '0.00 s (journal quente: CABLE e o rung 1, nao ha rotacao)'),
        ('abertura -> primeiro dispositivo COM SINAL (journal quente)',
         '%.3f s' % (MEASURED_OPEN_TO_ROTATE_S + OPEN_COST_2_S),
         '%.3f s' % OPEN_COST_1_S),
        ('arranque -> primeiro dispositivo com sinal (journal quente)',
         '%.2f s' % (T_ROTATE - T_SPAWN),
         '%.2f s' % (T_OPEN_1 - T_SPAWN + OPEN_COST_1_S)),
    ]
    print('TABLE %-58s %-24s %s' % ('metrica', 'antes', 'depois'))
    for name, b, a in rows:
        print('TABLE %-58s %-24s %s' % (name, b, a))
    print('TABLE rung1=%r rung2=%r (log); ordem com journal=%s'
          % ('VoiceMeeter Input', 'CABLE Input', order(ENDPOINTS, JOURNAL_WARM)))
    print('TABLE replicado dos 42 s ate ao fim da janela 3: %.0f s; log %.3f s'
          % (before_rot, MEASURED_OPEN_TO_ROTATE_S))


def build_world(worker_path=WORKER, wl_path=WL):
    """Os dois modulos que os arms julgam, e o ANTES reconstruido numa copia."""
    global _RANK
    if WORKER_DIR not in sys.path:
        sys.path.insert(0, WORKER_DIR)
    wl = load_module(wl_path, 'ladder_wl_under_test')
    _RANK = wl.endpoint_rank_key
    before_path, n = _sibling_copy(worker_path, 'before', _strip_cap)
    try:
        before = load_module(before_path, 'ladder_worker_before')
    finally:
        try:
            os.remove(before_path)
        except OSError:
            pass
    worker = load_module(worker_path, 'ladder_worker_after')
    return {'worker': worker, 'before': before, 'wl': wl, 'cap_stripped': n}


def run(world):
    results = arms(world)
    ok = True
    for name, passed, detail in results:
        print('ARM %-34s %s  %s' % (name, 'PASS' if passed else 'FAIL', detail))
        ok = ok and passed
    table(world)
    print('VERDICT: %s (%d/%d)' % ('PASS' if ok else 'FAIL',
                                   sum(1 for r in results if r[1]), len(results)))
    return ok


# ── neg-arm: cinco mutantes, cada um tem de acender um arm ───────────────────
MUTANTS = [
    ('M1 guarda-do-medidor-desligada', 'worker',
     '    if not live:\n        return None\n',
     '    return None  # MUTANTE: a guarda desligada (maquina calada vira rotacao)\n'),
    ('M2 journal-ignora-signal', 'wl',
     '        if kind == \'signal\':\n            sig_age = age\n',
     '        if kind == \'signal\':\n            sig_age = None  # MUTANTE\n'),
    ('M3 journal-nao-rebaixa-o-plano', 'wl',
     '        elif kind == \'flat\':\n            flat_age = age\n',
     '        elif kind == \'flat\':\n            flat_age = None  # MUTANTE\n'),
    ('M4 tap-nao-journaliza-no-close', 'wl',
     '        self._record_verdict()\n        for ref in (self._capture',
     '        pass  # MUTANTE: o close deixa de journalizar\n        for ref in (self._capture'),
    ('M5 tecto-da-janela-removido', 'worker',
     CAP_MARK + '\n', (CAP_PLAIN + '\n'), 2),
    ('M6 journal-le-o-id-errado', 'wl',
     "            eid = getattr(self.ep, 'endpoint_id', None)\n",
     "            eid = self.endpoint_id  # MUTANTE: o rung do default escreve None\n"),
]


def neg_arm(world):
    """MUTA copias dos ficheiros reais e exige que os arms fiquem VERMELHOS."""
    caught = 0
    total = 0
    for spec in MUTANTS:
        name, kind, old, new = spec[:4]
        expect = spec[4] if len(spec) > 4 else 1
        total += 1
        src = WORKER if kind == 'worker' else WL
        path, ok = _mutant(src, 'neg', old, new, expect=expect)
        if not ok:
            print('NEG-ARM %-36s IMPOSSIVEL (ancora ausente)' % name)
            continue
        try:
            mut = build_world(path if kind == 'worker' else WORKER,
                              path if kind == 'wl' else WL)
            red = [n for n, passed, _ in arms(mut) if not passed]
            if red:
                caught += 1
                print('NEG-ARM %-36s APANHADO por %s'
                      % (name, ','.join(r.split()[0] for r in red)))
            else:
                print('NEG-ARM %-36s ESCAPOU (nenhum arm vermelho)' % name)
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
            global _RANK
            _RANK = world['wl'].endpoint_rank_key
    print('NEG-ARM: %s (%d/%d)'
          % ('PASS' if caught == total else 'FAIL', caught, total))
    return caught == total


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--worker', default=WORKER)
    ap.add_argument('--wasapi', default=WL)
    ap.add_argument('--neg-arm', action='store_true')
    a = ap.parse_args(argv)
    try:
        world = build_world(a.worker, a.wasapi)
    except Exception as exc:                        # noqa: BLE001
        print('ORACLE IMPOSSIVEL: %r' % (exc,))
        return 2
    if a.neg_arm:
        return 1 if neg_arm(world) else 0
    return 0 if run(world) else 1


if __name__ == '__main__':
    raise SystemExit(main())
