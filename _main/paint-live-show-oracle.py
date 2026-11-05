# NO-BUG: instrumento do show REAL: exige `PANEL_CONTENT ack=true` ANTES de cada `PANEL_SHOWN`, mais `content_ack=true`, `paint_ack=true` e `wait_ms<=400`; diz SKIPPED quando ainda nao houve show; linha `why=bad-answer` legada e' REPLAYADA contra a pagina real
"""O show REAL do dono: a janela foi mapeada DEPOIS de o conteudo ser aplicado?

Duas perguntas, uma so' linha de log cada, porque a ordem e' o defeito:

  * `PANEL_CONTENT ack=true ... order=before-map` -- o shell perguntou a' pagina,
    ANTES do mapa, se a superficie ja' estava vestida (estilo recalculado e
    layout forçado por `getBoundingClientRect`); `ack=true` quer dizer que o
    `body[data-surface]` que o `ShowWindow` vai apresentar ja' era o pedido e o
    estilo dessa superficie ja' estava computado.
  * `PANEL_SHOWN ... content_ack=true content_wait_ms=.. paint_ack=.. wait_ms=..`
    -- o mapa e a frame.

O oraculo julga a ORDEM: cada `PANEL_SHOWN` tem de ter, ANTES dele na sessao
viva, o `PANEL_CONTENT` que o informou, com `ack=true`. Um log em que o show
aparece primeiro e' literalmente a queixa do dono -- *"o painel dar show, nao
deve carregar o background e mostrar, e depois carregar a ui"* -- e o braco
negativo muta exactamente isso.

Regras herdadas de 2026-11-01, sem alteracao:

  * a sessao viva comeca na ULTIMA linha `SHELL_STARTUP_STAGE` (ou `SHELL_START`);
  * `PAINT_WARM ... ack=true` tem de existir nessa sessao quando houve show;
  * todo `PANEL_SHOWN` traz `paint_ack=true` e `wait_ms <= 400` (o tecto e' o
    `PAINT_ACK_TIMEOUT_MS` do shell).

SEM SHOW NA SESSAO NAO E' VERDE: imprime `VERDICT: SKIPPED` com a hora do
arranque, e o passo skip-capable da bateria conta o como SKIPPED -- um passo
saltado nunca e' um portao que passou.

O QUE ELE NAO PROVA: pixel. Quem mede pixel e' `_main/panel-paint-first-census.py`,
numa instancia privada; este le a instancia que o dono carrega, e a lei
`SOTTO_NEVER_ON_OWNER_SCREEN` proibe uma lane de a pôr no ecra dele.

── A RESPOSTA QUE NAO ERA UM DICIONARIO (2026-11-04) ───────────────────────
A primeira versao deste oraculo ficou VERMELHA em cima do defeito e o vermelho
estava certo, mas nao dizia o que se passava: `ack=false why=bad-answer` e mais
nada. A causa foi MEDIDA (`_main/content-gate-answer-probe.py`):
`CONTENT_GATE_JS` devolve `JSON.stringify(out)` -- uma STRING -- e o
`ExecuteScriptAsync` JA' serializa o valor de retorno em JSON, portanto o
`json.loads` do `exec_js` entrega a string `'{"surface":...}'` e o gate antigo
chamava-lhe `bad-answer`. Nenhum show fez ack NUNCA (`grep -c ack=true` = 0).

Por isso o julgamento de uma linha LEGADA (`why=bad-answer`, uma forma que o
shell curado ja' nao consegue escrever) passa a ser um REPLAY medido: a pagina
REAL (`app/panel/panel.html` copiado para `$TMPDIR` com os ficheiros que ele
referencia) e' aberta em `msedge --headless=new` com o `CONTENT_GATE_JS`
SHIPPED, a sonda publica o `typeof` do valor e o JSON que atravessa o WebView2,
e o `gate_answer_payload` / `gate_verdict` EXTRAIDOS do fonte SHIPPED julgam a
resposta. O replay e' o instrumento; a linha do log e' a pergunta.

A linha impressa diz `REPLAY` e traz o viewport medido -- o cliente real da
faixa (380x40) nao existe em headless neste box (o Windows nao deixa a janela
ser menor que ~492x56), e o que o replay prova e' o PREDICADO (superficie,
`display` do cabecalho, caixa nao vazia), nao o tamanho.

Efervescencia: `--neg-arm` muta uma copia do log em SEIS pontos, o FONTE do shell
em TRES (mapa antes do gate, `bad-answer` de volta, repeticao removida) e a
sequencia de respostas do `gate_probe` em dois bracos, e exige os onze
vermelhos. Um mutante no fonte muda O REPLAY: o oraculo executa o codigo do
shell, nunca uma copia.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, 'webview-run.log')
SOURCE = os.path.join(os.path.dirname(HERE), 'app', 'webview', 'sotto_webview.py')
PROBE = os.path.join(HERE, 'content-gate-answer-probe.py')
ACK_MAX_MS = 400.0
#: O orcamento do gate e' `CONTENT_GATE_TIMEOUT_MS` = 250 ms; o fio de cabelo a
#: mais e' o poll e o marshalling, nao uma segunda espera.
CONTENT_MAX_MS = 350.0
#: A UNICA razao que o shell antigo escrevia sem dizer nada -- e a unica que este
#: oraculo aceita re-julgar por replay. Uma razao NOMEADA (`page-error`,
#: `page-not-ready`, `not-applied`, `ui-thread-busy`) e' honesta e NAO e' verde.
_LEGACY_WHY = ('bad-answer',)
_REPLAY_CACHE = {}

_START = ('SHELL_STARTUP_STAGE', 'SHELL_START')
_WARM = 'PAINT_WARM'
_CONTENT = 'PANEL_CONTENT'
_SHOWN = 'PANEL_SHOWN'


def _lines(text):
    return [ln for ln in text.splitlines() if ln.strip()]


def _stamp(line):
    m = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})', line)
    return m.group(1) if m else ''


def _get(line, key):
    m = re.search(r'\b%s=(\S+)' % (re.escape(key),), line)
    return m.group(1) if m else None


def _ms(line, key):
    try:
        return float(_get(line, key))
    except (TypeError, ValueError):
        return None


def _session(lines):
    """A ULTIMA sessao viva: tudo depois do ultimo arranque de shell."""
    start_idx = None
    for i in range(len(lines) - 1, -1, -1):
        if any(tag in lines[i] for tag in _START):
            start_idx = i
            break
    if start_idx is None:
        return None
    return lines[start_idx:]


def _probe_module():
    spec = importlib.util.spec_from_file_location('content_gate_answer_probe', PROBE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _viewport_before(session, index, mode):
    """O cliente que o shell forcou antes deste show -- para o replay o usar."""
    for ln in reversed(session[:index]):
        m = re.search(r'panel client area forced to (\d+)x(\d+)', ln)
        if m:
            return (int(m.group(1)), int(m.group(2)))
    return (380, 40) if (mode or '') == 'strip' else None


def replay_gate(surface, viewport, source_text):
    """A pergunta LEGADA re-julgada pela pagina REAL e pelo shell SHIPPED.

    -> dict do gate (`ack`, `why`, ...) ou `{'ok': False, 'why': <razao>}`.
    Nunca inventa: sem navegador, sem sonda ou sem as funcoes no fonte, diz
    UNPROVEN e o chamador fica vermelho.
    """
    # A CHAVE TEM DE INCLUIR O FONTE: um mutante no `gate_answer_payload` tem de
    # re-julgar, nao apanhar a resposta em cache do fonte REAL (medido: sem isto
    # o braco `bad-answer-de-volta` publicava GREEN).
    key = (surface, viewport, hashlib.sha1(source_text.encode('utf-8')).hexdigest()[:12])
    if key in _REPLAY_CACHE:
        return _REPLAY_CACHE[key]
    try:
        mod = _probe_module()
        measured = mod.page_answer(surface, viewport, source_text)
    except Exception as exc:      # noqa: BLE001 -- o oraculo diz, nunca engole
        out = {'ok': False, 'why': 'sonda indisponivel: %r' % (exc,)}
        _REPLAY_CACHE[key] = out
        return out
    if not measured.get('ok'):
        _REPLAY_CACHE[key] = measured
        return measured
    try:
        out = mod.classify(source_text, measured, surface)
    except Exception as exc:      # noqa: BLE001
        out = {'ok': False, 'why': 'julgamento impossivel: %r' % (exc,)}
        _REPLAY_CACHE[key] = out
        return out
    out['_measured'] = measured
    _REPLAY_CACHE[key] = out
    return out


def judge(text, source_text=None):
    """-> (verdict, detail). `verdict` in GREEN | RED | SKIPPED. Puro: so' o texto."""
    lines = _lines(text)
    session = _session(lines)
    if session is None:
        return 'SKIPPED', {'why': 'nenhum arranque de shell no log -- nao ha sessao viva a julgar',
                           'shows': 0}
    warm = [ln for ln in session if _WARM in ln]
    warm_ok = [ln for ln in warm if (_get(ln, 'ack') or '') == 'true']
    shown_idx = [i for i, ln in enumerate(session) if _SHOWN in ln]
    content_idx = [i for i, ln in enumerate(session) if _CONTENT in ln]
    detail = {'started': _stamp(session[0]), 'warm': len(warm),
              'warm_ack': len(warm_ok), 'shows': len(shown_idx),
              'content': len(content_idx), 'content_ack': 0,
              'shows_verbatim': [], 'fails': []}
    for i in shown_idx:
        detail['shows_verbatim'].append(session[i])
    # UM SHOW QUE NUNCA ACONTECEU NAO TEM CAMINHO. `PAINT_WARM` existe para o
    # PRIMEIRO show nao cair no caminho frio; uma sessao que nunca mostrou o
    # painel (uma lane, uma sessao `--no-self-relaunch`, o dono sem Alt+C) nao
    # deve nada ao caminho quente. Medido 2026-11-04: um arranque de lane sem
    # show nenhum publicava RED "o show cai no caminho frio" -- um vermelho sobre
    # um passo que nao correu. So' se exige o warm quando houve show para julgar.
    if shown_idx and not warm:
        detail['fails'].append('a sessao viva nao tem PAINT_WARM: o show cai no caminho frio')
    elif shown_idx and not warm_ok:
        detail['fails'].append('PAINT_WARM existe mas sem ack=true (%s)'
                               % (_get(warm[-1], 'ack'),))
    # O CONTEUDO DE CADA GATE, e depois a ORDEM dele contra o mapa.
    content_ok = []
    replayed = {}
    for j in content_idx:
        ack = (_get(session[j], 'ack') or '')
        why = _get(session[j], 'why')
        if ack == 'true':
            content_ok.append(j)
            continue
        if why in _LEGACY_WHY:
            # A FORMA QUE O SHELL CURADO NAO ESCREVE. Nao a absolvo: re-julgo-a
            # com a pagina REAL e o codigo SHIPPED, e so' um ack medido a
            # transforma em evidencia de que a superficie estava vestida.
            surface = _get(session[j], 'surface') or ''
            surface = surface.strip('"')
            src = source_text if source_text is not None else _REAL_SOURCE
            if not src:
                detail['fails'].append('conteudo ilegivel (%s): why=%s e sem fonte '
                                       'para o replay' % (_stamp(session[j]) or '?', why))
                continue
            rp = replay_gate(surface, _viewport_before(session, j, surface), src)
            if not rp.get('ok', True):
                detail['fails'].append(
                    'replay UNPROVEN (%s): why=%s e a sonda nao mediu -- '
                    'UNPROVEN nao e um verde' % (_stamp(session[j]) or '?', rp.get('why')))
            elif rp.get('ack'):
                content_ok.append(j)
                replayed[j] = rp
                detail.setdefault('replayed', []).append((session[j], rp))
            else:
                detail['fails'].append(
                    'replay (%s): a pagina medida NAO esta vestida -- ack=false '
                    'why=%s sized=%s head=%s size=%dx%d'
                    % (_stamp(session[j]) or '?', rp.get('why'), rp.get('sized'),
                       json.dumps(rp.get('head')), rp.get('w'), rp.get('h')))
        elif why is None:
            detail['fails'].append(
                'conteudo sem why= (%s): a linha nao diz porque o painel nao estava '
                'vestido' % (_stamp(session[j]) or '?',))
        else:
            detail['fails'].append(
                'conteudo nao aplicado antes do mapa (%s): ack=%s why=%s -- o show '
                'segue pela falha aberta, e o artefacto diz que ele seguiu'
                % (_stamp(session[j]) or '?', ack, why))
    detail['content_ack'] = len(content_ok)
    detail['replayed_count'] = len(replayed)
    bad = []
    waits, cwaits = [], []
    for i in shown_idx:
        ln = session[i]
        ack = _get(ln, 'content_ack')
        cack = _get(ln, 'content_wait_ms')
        cms = _ms(ln, 'content_wait_ms')
        if cms is not None:
            cwaits.append(cms)
        before = [j for j in content_ok if j < i]
        if ack != 'true':
            if before and before[-1] in replayed:
                # A LINHA VIVA DIZ `content_ack=false` PORQUE O SHELL DELA NAO
                # SABIA LER A RESPOSTA. O replay MEDIU que a superficie estava
                # vestida -- o artefacto do shell antigo fica no log como esta,
                # e o que conta e' o que este oraculo mediu agora.
                detail.setdefault('legacy_shows', []).append((ln, replayed[before[-1]]))
            else:
                bad.append((ln, 'content_ack=%s (o mapa nao esperou o conteudo)'
                            % (ack,)))
        elif not before:
            # A ORDEM E' O DEFEITO. Um show sem um `PANEL_CONTENT ack=true`
            # ANTES dele e' a janela a aparecer antes da UI.
            bad.append((ln, 'nenhum PANEL_CONTENT ack=true ANTES do show '
                            '(a janela foi mapeada antes do conteudo)'))
        elif cms is None:
            bad.append((ln, 'sem content_wait_ms'))
        elif cms > CONTENT_MAX_MS:
            bad.append((ln, 'content_wait_ms=%.1f > %.0f' % (cms, CONTENT_MAX_MS)))
        pack = _get(ln, 'paint_ack')
        ms = _ms(ln, 'wait_ms')
        if ms is not None:
            waits.append(ms)
        if pack != 'true':
            bad.append((ln, 'paint_ack=%s' % (pack,)))
        elif ms is None:
            bad.append((ln, 'sem wait_ms'))
        elif ms > ACK_MAX_MS:
            bad.append((ln, 'wait_ms=%.1f > %.0f' % (ms, ACK_MAX_MS)))
    detail['max_wait_ms'] = max(waits) if waits else None
    detail['max_content_wait_ms'] = max(cwaits) if cwaits else None
    for ln, why in bad:
        detail['fails'].append('show %s: %s' % (_stamp(ln) or '?', why))
    if detail['fails']:
        return 'RED', detail
    if not shown_idx:
        return 'SKIPPED', dict(detail, why='nenhum Alt+C nesta sessao ainda (%s) -- nada a julgar'
                               % (detail['started'] or 'sem hora',))
    return 'GREEN', detail


# ── O FONTE: A ORDEM TAMBEM SE LE' NO CODIGO ────────────────────────────────
#: As tres funcoes que mapeiam o painel, e o token do mapa de cada uma. O gate
#: tem de aparecer ANTES do mapa no corpo da funcao: um mutante que troca as
#: duas linhas e' "mostrar a janela antes do conteudo ser aplicado" no proprio
#: ficheiro que a app carrega, e o log de uma instancia antiga nao o mostraria.
_SOURCE_PATHS = (
    ('show_panel', 'show_without_activating(self.hwnd)'),
    ('show_strip', 'fg = foreground_unlock(self.hwnd)'),
    ('show_side', 'fg = foreground_unlock(self.hwnd)'),
)
_GATE_CALL = 'content_gate('


def _body_of(src, name, indent=''):
    """O corpo de uma funcao do shell, pelo texto -- `None` se ela nao existe."""
    pattern = (r'\n%sdef %s\([^\n]*\n(.*?)(?=\n%s(?:def|class) )'
               % (re.escape(indent), re.escape(name), re.escape(indent)))
    m = re.search(pattern, src, re.S)
    return m.group(1) if m else None


def judge_source(src):
    """-> lista de falhas (vazia = ordem certa). Puro: so' o texto do fonte."""
    fails = []
    for name, map_call in _SOURCE_PATHS:
        m = re.search(r'\n    def %s\(self[^\n]*\n(.*?)(?=\n    def )' % (re.escape(name),),
                      src, re.S)
        if not m:
            fails.append('%s: funcao nao encontrada no fonte' % (name,))
            continue
        body = m.group(1)
        gate_at = body.find(_GATE_CALL)
        map_at = body.find(map_call)
        if gate_at < 0:
            fails.append('%s: sem `%s` -- o mapa nao pergunta nada a\' pagina'
                         % (name, _GATE_CALL.strip('(')))
        elif map_at < 0:
            fails.append('%s: sem o mapa `%s` -- o instrumento nao sabe o que julgar'
                         % (name, map_call))
        elif gate_at > map_at:
            fails.append('%s: o mapa (`%s`) vem ANTES do gate -- a janela aparece '
                         'antes do conteudo' % (name, map_call))
        # A LINHA DO SHOW TEM DE DIZER PORQUE. Um `content_ack=false` sem
        # `content_why=` e' a mesma linha muda que deixou o defeito passar dois
        # meses: o artefacto diz que o show aconteceu e nao diz o que faltou.
        if gate_at >= 0 and 'content_why=' not in body:
            fails.append('%s: o `PANEL_SHOWN` nao publica `content_why=` -- a '
                         'razao nomeada nao chega ao artefacto' % (name,))
    # ── O GATE EM SI: DECODIFICA E REPETE, E NUNCA ESCREVE UM `bad-answer` ──
    gate = _body_of(src, 'content_gate', indent='    ')
    probe = _body_of(src, 'gate_probe', indent='')
    payload = _body_of(src, 'gate_answer_payload', indent='')
    if gate is None or probe is None or payload is None:
        fails.append('o fonte nao tem `content_gate`/`gate_probe`/`gate_answer_payload` '
                     '-- o instrumento nao julga uma copia')
    else:
        if 'gate_probe(' not in gate:
            fails.append('content_gate: nao usa `gate_probe` -- uma pergunta unica '
                         'sem razao nomeada')
        if 'CONTENT_GATE_TIMEOUT_MS' not in gate:
            fails.append('content_gate: o orcamento (`CONTENT_GATE_TIMEOUT_MS`) saiu '
                         'do caminho')
        if 'gate_should_retry(' not in probe or 'while True' not in probe:
            fails.append('gate_probe: sem a repeticao (`gate_should_retry` dentro do '
                         '`while True`)')
        if 'gate_answer_payload(' not in probe:
            fails.append('gate_probe: nao decodifica a resposta com '
                         '`gate_answer_payload` -- a string JSON volta a ser '
                         '`bad-answer`')
        if 'json.loads' not in payload:
            fails.append('gate_answer_payload: nao le o JSON em string -- e\' a forma '
                         'que a pagina devolve (`JSON.stringify`)')
        for name, body in (('content_gate', gate), ('gate_probe', probe),
                           ('gate_answer_payload', payload)):
            # A DOCSTRING E OS COMENTARIOS NAO ESCREVEM `why=`: so' o codigo conta.
            body = re.sub(r'""".*?"""', '', body, flags=re.S)
            for line in body.splitlines():
                code = line.split('#', 1)[0]
                if 'bad-answer' in code:
                    fails.append('%s: escreve `bad-answer` -- a razao voltou a nao '
                                 'ter nome' % (name,))
    return fails


# ── AS MUTACOES ─────────────────────────────────────────────────────────────
def _last_eq_off(key):
    def mutate(text):
        at = text.rfind('%s=true' % (key,))
        if at < 0:
            return text
        return text[:at] + '%s=false' % (key,) + text[at + len(key) + 5:]
    return mutate


def _content_ack_off(text):
    """Desliga o `ack` da ULTIMA linha `PANEL_CONTENT` -- o campo que o gate le."""
    lines = text.splitlines()
    ci = [i for i, ln in enumerate(lines) if _CONTENT in ln]
    if not ci:
        return text
    at = ci[-1]
    lines[at] = re.sub(r'\back=true\b', 'ack=false', lines[at], count=1)
    return '\n'.join(lines) + ('\n' if text.endswith('\n') else '')


def _map_before_content(text):
    """Empurra o ULTIMO `PANEL_CONTENT` para DEPOIS do ultimo `PANEL_SHOWN`."""
    lines = text.splitlines()
    ci = [i for i, ln in enumerate(lines) if _CONTENT in ln]
    si = [i for i, ln in enumerate(lines) if _SHOWN in ln]
    if not ci or not si:
        return text
    line = lines.pop(ci[-1])
    after = max(i for i, ln in enumerate(lines) if _SHOWN in ln)
    lines.insert(after + 1, line)
    return '\n'.join(lines) + '\n'


def _source_map_first(src):
    """Troca, em cada funcao do mapa, o gate e a linha do mapa de lugar."""
    out = []
    for chunk in re.split(r'(?=\n    def )', src):
        name = chunk.lstrip('\n').split('\n', 1)[0].strip()
        swapped = chunk
        for fname, map_call in _SOURCE_PATHS:
            if name.startswith('def %s(' % (fname,)):
                gate_line = '        content = self.content_gate(reason, self.surface_applied)\n'
                map_line = '        %s\n' % (map_call,)
                if gate_line in swapped and map_line in swapped:
                    # MOVE, nao troca: o gate sai do lugar e entra DEPOIS do
                    # mapa -- o mutante e' "a janela primeiro", com o
                    # comentario e a distancia que o ficheiro real tem.
                    swapped = swapped.replace(gate_line, '', 1)
                    swapped = swapped.replace(map_line, map_line + gate_line, 1)
        out.append(swapped)
    return ''.join(out)


def _source_old_bad_answer(src):
    """POE O DEFEITO DE VOLTA: uma resposta que nao e' dicionario vira `bad-answer`.

    E' literalmente o `else` de 2026-11-04: a classe de erro e' "o shell nao le a
    string JSON e nao diz nada", e o oraculo tem de a apanhar PELO REPLAY, nao
    por ler um comentario.
    """
    m = re.search(r'\ndef gate_answer_payload\([^\n]*\n(.*?)(?=\n\n\n)', src, re.S)
    if not m:
        return src
    return (src[:m.start()]
            + '\ndef gate_answer_payload(answer):\n'
              '    """CONTROL: o shell antigo -- a string JSON nao e\' lida."""\n'
              '    if isinstance(answer, dict):\n'
              "        return answer, '', ''\n"
              "    return None, 'bad-answer', ''"
            + src[m.end():])


def _source_no_retry(src):
    """REMOVE A REPETICAO: uma pergunta e o orcamento fica por gastar."""
    needle = ('        if not gate_should_retry(out[\'why\'], out[\'ack\'], '
              'clock() - t0, budget_s):\n            break\n')
    if needle not in src:
        return src
    return src.replace(needle, '        break\n', 1)


def retry_arm(source_text):
    """A repeticao, medida no `gate_probe` SHIPPED com um relogio de brinquedo.

    -> (fails, notes). Duas perguntas: uma resposta que nao e' JSON e' seguida da
    resposta vestida (tem de ackar na SEGUNDA), e uma sequencia que nunca acka
    tem de parar DENTRO do orcamento (250 ms), nunca 250 ms por tentativa.
    """
    fails = []
    try:
        mod = _probe_module()
        ns = mod.shell_functions(source_text)
    except Exception as exc:      # noqa: BLE001
        return ['retry-arm: nao consegui executar o `gate_probe` shipped: %r' % (exc,)], {}
    good = json.dumps({'surface': 'strip', 'style': True, 'sized': True, 'w': 380,
                       'h': 40, 'bg': 'rgb(0,0,0)', 'head': 'none', 'vis': 'visible',
                       'error': ''})
    budget = 0.25

    def probe(sequence, step=0.016):
        state = {'t': 0.0}
        calls = []

        def clock():
            return state['t']

        def ask(left):
            calls.append(left)
            state['t'] += step
            return sequence[min(len(calls) - 1, len(sequence) - 1)]

        out = ns['gate_probe']('strip', ask, budget, clock=clock, pause=lambda s: None)
        return out, calls

    recovered, calls = probe(['TypeError: SottoSurfaces is not a function', good])
    if not recovered['ack']:
        fails.append('retry: a primeira resposta ma nao foi repetida ate ao ack '
                     '(attempts=%s why=%s)' % (recovered['attempts'], recovered['why']))
    if recovered['attempts'] != 2:
        fails.append('retry: esperava 2 tentativas, medi %s' % (recovered['attempts'],))
    never, calls2 = probe(['not json at all'], step=0.05)
    if never['ack']:
        fails.append('retry: uma sequencia sem ack produziu ack')
    if never['wait_ms'] > budget * 1000.0:
        fails.append('retry: o orcamento foi excedido (%.1f ms > %.0f ms)'
                     % (never['wait_ms'], budget * 1000.0))
    if any(left > budget for left in calls2):
        fails.append('retry: uma tentativa recebeu mais orcamento do que o total')
    if never['attempts'] < 2:
        fails.append('retry: nao repetiu antes de gastar o orcamento '
                     '(attempts=%s)' % (never['attempts'],))
    notes = {'recovered_attempts': recovered['attempts'],
             'recovered_wait_ms': recovered['wait_ms'],
             'never_attempts': never['attempts'], 'never_wait_ms': never['wait_ms'],
             'max_ask_s': round(max(calls2) if calls2 else 0.0, 4)}
    return fails, notes


NEG_CASES = (
    # (rotulo, o que muda, o que se espera)
    # A ULTIMA, NAO A PRIMEIRA (medido 2026-11-02): `replace(..., 1)` mutava o
    # `PANEL_SHOWN` de uma sessao ANTERIOR e o julgar so le a sessao viva -- a
    # mutacao nao movia o artefacto do veredicto e o braco publicava NOT-CAUGHT
    # (cases=3 caught=2). A licao ja' estava no `show-lento` ao lado.
    ('show-sem-ack', _last_eq_off('paint_ack'), 'RED'),
    # O MUTANTE DA ORDEM: o mapa primeiro, o conteudo depois. E' a queixa do
    # dono escrita num log.
    ('mapa-antes-do-conteudo', _map_before_content, 'RED'),
    ('show-sem-ack-conteudo', _last_eq_off('content_ack'), 'RED'),
    ('conteudo-nao-aplicado', _content_ack_off, 'RED'),
    # A cauda sintetica e' a ULTIMA ocorrencia: mutar a primeira apanhava uma sessao velha
    # e o braco passava verde (medido).
    ('show-lento', lambda t: re.sub(r'wait_ms=[\d.]+(?=[^\d.]*$)', 'wait_ms=951.0', t), 'RED'),
    ('sessao-sem-aquecimento', lambda t: '\n'.join(
        ln for ln in t.splitlines() if _WARM not in ln), 'RED'),
)


SOURCE_CASES = (
    ('fonte-mapa-antes-do-gate', _source_map_first),
    ('fonte-bad-answer-de-volta', _source_old_bad_answer),
    ('fonte-sem-repeticao', _source_no_retry),
)


def neg_arm(text, source_text=None, real_text=None):
    """`text` e' a amostra sintetica; `real_text` e' o log do dono, para os bracos
    que so' o REPLAY sabe julgar."""
    cases = list(NEG_CASES)
    bad = 0
    total = 0

    def check(label, ok, note):
        nonlocal bad, total
        total += 1
        bad += 0 if ok else 1
        print('  %-34s -> %-8s %s  %s'
              % (label, 'RED' if ok else 'GREEN',
                 'RED-as-required' if ok else 'NOT-CAUGHT', note[:90]))

    for label, mutate, expect in cases:
        got, detail = judge(mutate(text), source_text)
        check(label, got == expect, (detail.get('fails') or ['-'])[0])
    # O MUTANTE DO FONTE, ao lado dos do log: a ordem no ficheiro que a app
    # carrega, nao so' na linha que ele escreveu.
    if source_text:
        for label, mutate in SOURCE_CASES:
            fails = judge_source(mutate(source_text))
            check(label, bool(fails),
                  (fails or ['o mutante passou -- o instrumento nao le o fonte'])[0])
        # O DEFEITO DE VOLTA TEM DE DERRUBAR O JULGAMENTO DO LOG TAMBEM: o
        # `gate_answer_payload` mutado e' o que classifica a resposta MEDIDA.
        # SO' QUANDO HA' UMA LINHA LEGADA PARA RE-JULGAR. Sem ela o replay
        # devolve `replayadas=0` e o braco publicava RED-por-nada (ou GREEN-por-
        # nada, que era o caso): um passo sem evidencia nao julga. A cobertura
        # desta classe vive agora no par sem navegador logo abaixo.
        # APOSENTADA (2026-11-05): este braco so' sabia julgar atraves do
        # replay com NAVEGADOR e app viva, e neste host o replay devolve
        # `replayadas=0` -- ele publicava GREEN sem julgar nada (`cases=12
        # caught=11`, o unico mutante que passava). A classe que ele cobria
        # (a resposta crua em STRING JSON tem de ser LIDA, nao chamada de
        # `bad-answer`) esta' agora em `string-answer-read-by-the-gate`, que
        # corre o `gate_probe` SHIPPED com uma resposta construida a mao: e'
        # deterministico, nao precisa de browser, e cai com o mutante.
        print('  %-34s -> RETIRED  coberto por string-answer-read-by-the-gate'
              % 'bad-answer-de-volta-derruba-o-log')
        # O MESMO DEFEITO, SEM DEPENDER DE HA' UMA LINHA LEGADA NO LOG
        # (2026-11-05). O braco acima julga o log do dono, e o log do dono nao
        # tem NENHUMA linha `why=bad-answer` (`replayadas=0`) -- por isso ele
        # publicava GREEN sem julgar nada, e o mutante `bad-answer-de-volta`
        # era o unico dos doze que passava (cases=12 caught=11). Aqui a
        # resposta CRUA da pagina e' construida a mao, na forma exacta que ela
        # envia (uma STRING JSON) e empurrada pelo `gate_probe` que o show
        # corre: o fonte REAL faz ack na primeira tentativa, o mutante
        # responde `bad-answer`.
        probe_mod = _probe_module()
        synthetic = {'answer': json.dumps({'surface': 'strip', 'style': True,
                                           'sized': True, 'w': 380, 'h': 40})}
        good = probe_mod.classify(source_text, synthetic, 'strip')
        bad_answer = probe_mod.classify(_source_old_bad_answer(source_text),
                                        synthetic, 'strip')
        check('string-answer-read-by-the-gate',
              bool(good.get('ack')) and good.get('why') == 'applied'
              and bad_answer.get('why') == 'bad-answer',
              'real: ack=%s why=%s / mutante: ack=%s why=%s'
              % (good.get('ack'), good.get('why'),
                 bad_answer.get('ack'), bad_answer.get('why')))
        # A REPETICAO: o `gate_probe` SHIPPED e' executado com um relogio de
        # brinquedo, e o mutante que a remove tem de o apanhar.
        fails, notes = retry_arm(source_text)
        check('retry-recupera-dentro-do-orcamento', not fails,
              (fails or ['attempts=%s wait_ms=%s / nunca-ack attempts=%s wait_ms=%s'
                         % (notes.get('recovered_attempts'), notes.get('recovered_wait_ms'),
                            notes.get('never_attempts'), notes.get('never_wait_ms'))])[0])
        fails_m, _ = retry_arm(_source_no_retry(source_text))
        check('retry-removido', bool(fails_m),
              (fails_m or ['o mutante sem repeticao passou -- o braco nao mede nada'])[0])
        real_fails = judge_source(_REAL_SOURCE) if _REAL_SOURCE else ['fonte real ausente']
        print('POSITIVE-CONTROL: o fonte REAL tem a ordem, a leitura e a repeticao? '
              '%s%s' % ('sim' if not real_fails else 'NAO -- o braco nao mede nada',
                        '' if not real_fails else '  %s' % (real_fails[0][:80],)))
        verdict_r, detail_r = judge(real_text or text, _REAL_SOURCE or source_text)
        print('POSITIVE-CONTROL: o log REAL e\' julgado com replay? '
              'replayadas=%d veredicto=%s%s'
              % (detail_r.get('replayed_count', 0), verdict_r,
                 '' if detail_r.get('replayed_count') else
                 '  (nenhuma linha legada -- nada a replayar)'))
    if not text.strip():
        print('NEG-ARM: a amostra esta vazia -- as mutacoes nao provam nada')
        return 1
    print('NEG-ARM cases=%d caught=%d' % (total, total - bad))
    if bad:
        print('NEG-ARM FAIL')
        return 2
    print('NEG-ARM PASS')
    return 1   # convencao da casa: o braco negativo PASSOU sai rc=1 e o passo e' expect-red


_REAL_SOURCE = ''


def replay_report(text, source_text):
    """Imprime o veredicto REPLAYADO de cada linha legada do ficheiro inteiro.

    A sessao viva e' o que o veredicto julga; a linha de 12:15:43 esta numa
    sessao anterior e nao entra nele -- mas ela e' METADE da evidencia do dono,
    e o replay responde-lhe do mesmo jeito. `content_ack=true` aqui e' sempre
    `REPLAY = medido agora`, nunca uma afirmacao sobre o processo antigo.
    """
    lines = _lines(text)
    rows = []
    for i, ln in enumerate(lines):
        if _CONTENT not in ln or (_get(ln, 'ack') or '') == 'true':
            continue
        why = _get(ln, 'why')
        surface = (_get(ln, 'surface') or '').strip('"')
        viewport = _viewport_before(lines, i, surface)
        row = {'stamp': _stamp(ln), 'why': why, 'surface': surface,
               'viewport': viewport, 'line': ln}
        if why in _LEGACY_WHY:
            rp = replay_gate(surface, viewport, source_text)
            row['replay'] = rp
        rows.append(row)
    return rows


def _print_replay(rows):
    for row in rows:
        rp = row.get('replay')
        if rp is None:
            print('PAINT-LIVE replay %s: why=%s (NAO e\' uma forma legada -- o shell '
                  'curado diz esta razao, e ela nao se re-julga)'
                  % (row['stamp'] or '?', row['why']))
            continue
        if not rp.get('ok', True):
            print('PAINT-LIVE replay %s: UNPROVEN why=%s' % (row['stamp'] or '?', rp.get('why')))
            continue
        measured = rp.get('_measured') or {}
        print('PAINT-LIVE replay %s: content_ack=%s why=%s applied=%s style=%s '
              'sized=%s size=%dx%d head=%s viewport=%s gate_ms=%s attempts=%s'
              % (row['stamp'] or '?', str(rp.get('ack')).lower(), rp.get('why'),
                 json.dumps(str(rp.get('applied'))), str(rp.get('style')).lower(),
                 str(rp.get('sized')).lower(), rp.get('w'), rp.get('h'),
                 json.dumps(rp.get('head')), measured.get('viewport'),
                 measured.get('gate_ms'), rp.get('attempts')))
        print('  LEGADO (verbatim, o shell daquela sessao): %s' % (row['line'],))


def main(argv=None):
    global _REAL_SOURCE
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--log', default=LOG)
    ap.add_argument('--source', default=SOURCE)
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args(argv)
    source_text = ''
    if os.path.exists(args.source):
        source_text = open(args.source, encoding='utf-8', errors='replace').read()
        _REAL_SOURCE = source_text
    # O FONTE E' JULGADO SEMPRE: o log pode nao ter um show ainda, mas a ordem no
    # codigo que ele vai carregar ja' e' uma pergunta com resposta.
    src_fails = judge_source(source_text) if source_text else ['fonte ausente em %s' % (args.source,)]
    if not os.path.exists(args.log):
        print('PAINT-LIVE VERDICT: SKIPPED (sem log em %s)' % (args.log,))
        return 0
    text = open(args.log, encoding='utf-8', errors='replace').read()
    if args.neg_arm:
        # A amostra das mutacoes e' o log REAL; se ele nao tem um show ainda, fabrica-se um
        # a partir do arranque, porque um braco negativo sobre texto vazio e' um braco a rir.
        # SEMPRE uma cauda sintetica LIMPA: as mutacoes tem de morder alguma coisa, e o
        # texto vivo pode nao ter show nenhum (foi o caso medido hoje). O braco positivo
        # deste oraculo continua a ser o log REAL (`--log`), nunca esta cauda.
        # A AMOSTRA E' UMA SESSAO SINTETICA FECHADA, nao o log real com uma
        # cauda: o log real ja' tem um `PANEL_CONTENT` que o REPLAY acka, e um
        # deles ANTES do show sintetico satisfazia a ordem sem que o mutante
        # fizesse nada -- medido 2026-11-04 (`mapa-antes-do-conteudo` publicava
        # GREEN). Uma sessao propria torna cada mutacao a UNICA fonte do
        # veredicto, e o braco positivo e' o BLOCO SEM MUTACAO (o `judge` do log
        # real continua a ser corrido a parte, no braco positivo abaixo).
        sample = (
            '2099-01-01 00:00:00.000 sotto: SHELL_STARTUP_STAGE pid=999999 '
            'stage=pre-lock python=py.exe panel=true\n'
            '2099-01-01 00:00:00.100 sotto: PAINT_WARM reason=startup ack=true '
            'ack_wait_ms=31.0\n'
            '2099-01-01 00:00:01.000 sotto: PANEL_CONTENT surface=strip ack=true '
            'applied="strip" style=true sized=true size=380x40 head="none" '
            'vis=visible wait_ms=9.0 why=applied order=before-map '
            'reason=hotkey-cycle-strip timeout_ms=250.0 attempts=1 error=""\n'
            '2099-01-01 00:00:01.030 sotto: PANEL_SHOWN reason=hotkey-cycle-strip '
            'mode=strip visible=true paint_ack=true content_ack=true '
            'content_why=applied content_attempts=1 content_wait_ms=9.0 '
            'wait_ms=32.0\n')
        clean, _clean_detail = judge(sample, source_text or None)
        if clean != 'GREEN':
            print('NEG-ARM: a amostra sintetica nao e\' verde sem mutacao (%s) -- '
                  'as mutacoes nao provam nada' % (clean,))
            return 2
        return neg_arm(sample, source_text or None, text)
    verdict, detail = judge(text, source_text or None)
    print('PAINT-LIVE arranque=%s warm=%d ack=%d conteudo=%d conteudo_ack=%d shows=%d '
          'max_wait_ms=%s max_content_wait_ms=%s'
          % (detail.get('started') or '-', detail.get('warm', 0),
             detail.get('warm_ack', 0), detail.get('content', 0),
             detail.get('content_ack', 0), detail.get('shows', 0),
             detail.get('max_wait_ms'), detail.get('max_content_wait_ms')))
    shows = detail.get('shows_verbatim') or []
    if shows:
        print('PAINT-LIVE shows (verbatim, sessao viva):')
        for ln in shows:
            print('  %s' % (ln,))
    else:
        # A SESSAO VIVA AINDA NAO TEM SHOW. As ultimas linhas do log sao de uma
        # sessao ANTERIOR e nao entram no veredicto; ficam impressas porque sao a
        # unica evidencia de show que o ficheiro tem hoje.
        old = [ln for ln in _lines(text) if _SHOWN in ln][-3:]
        for ln in old:
            print('PAINT-LIVE show (verbatim, FORA da sessao viva): %s' % (ln,))
    # O REPLAY: cada linha `why=bad-answer` do ficheiro, re-julgada pela pagina
    # REAL e pelo shell SHIPPED. E' a unica resposta honesta para uma linha que
    # o shell da altura nao sabia ler.
    legacy_rows = replay_report(text, source_text) if source_text else []
    if legacy_rows:
        _print_replay(legacy_rows)
    for ln, rp in detail.get('legacy_shows') or []:
        print('PAINT-LIVE show LEGADO %s: content_ack=false na linha, REPLAY ack=%s '
              'why=%s' % (_stamp(ln) or '?', str(rp.get('ack')).lower(), rp.get('why')))
    for why in src_fails:
        print('  RED (fonte): %s' % (why,))
    for why in detail.get('fails') or []:
        print('  RED: %s' % (why,))
    if src_fails:
        print('PAINT-LIVE VERDICT: RED')
        return 1
    if verdict == 'SKIPPED':
        print('PAINT-LIVE VERDICT: SKIPPED (%s)'
              % (detail.get('why') or 'nada a julgar',))
        return 0
    print('PAINT-LIVE VERDICT: %s' % (verdict,))
    return 0 if verdict == 'GREEN' else 1


if __name__ == '__main__':
    raise SystemExit(main())
