#!/usr/bin/env python
# -*- coding: utf-8 -*-
# NO-BUG: A POSSE DO ECRA -- quem pinta, quem e' recusado, e o que a recusa custa ao historico. -- trabalho de CAPACIDADE/observabilidade nascido do `10-DEFECTS.md` §D-23 (o docstring prometia historico e o codigo descartava a linha); nao corresponde a nenhum id de `_main/bug-ledger.json`, e declarado aqui em vez de inventar um id.
"""A POSSE DO ECRA -- quem pinta, quem e' recusado, e o que a recusa custa.

O DEFEITO QUE ESTE PORTAO FECHA (medido 2026-11-12, `docs/spec/10-DEFECTS.md` §D-23):
`SottoShell.external_owner_refuses` dizia, no proprio docstring e na linha de log
`ASR_PAINT_REFUSED`, que a legenda local recusada *"vai para o historico e nao
para o ecra"*. O codigo faz outra coisa: `on_worker_caption` devolve ANTES do
`emit_async('caption', ...)`, e o painel -- unico escritor de `history_append` --
nunca a ve. A linha nao vai ao ecra **nem ao historico**: some, e o unico rasto
era um contador global.

MEDIDO no log do dono (`_main/webview-run.log`, 207 056 linhas, 2026-11-11):
`EXTERNAL_OWNER owner=player episode=1` as 20:01:08.967, **1** linha
`ASR_PAINT_REFUSED` (a primeira do episodio), **16** `EXTERNAL_CAPTIONS_ASR_SUPPRESSED`
e 4 089 `CAPTION_APPLIED` -- 0,4 % das linhas daquela sessao foram descartadas
assim. Foi por isso que o contador passou a sair POR EPISODIO na transicao de
volta: uma perda que ninguem conta e' indistinguivel de uma perda que nao houve.

O QUE ELE JULGA (o codigo REAL, extraido do fonte que embarca; nenhuma regra e'
reimplementada aqui):

  A1 LOCAL-NAO-RECUSA    dono `local` + fonte `device:...` -> pinta (o `emit_async`
                         leva a legenda ao painel, e o painel ao historico).
  A2 PLAYER-RECUSA       dono `player` + fonte local -> recusa: `external_suppressed`
                         sobe, e o `emit_async` NAO e' chamado.
  A3 PLAYER-NAO-SE-RECUSA a linha `external:*` -- a do PROPRIO player -- nunca e'
                         recusada. E' o dono a falar de si; recusa-la calava a
                         fonte que ganhou o ecra.
  A4 A-RECUSA-NAO-ESCREVE-HISTORICO  o que o §D-23 mediu: no ramo de recusa, zero
                         `emit_async`. Se alguem um dia ligar a recusa ao painel,
                         esta arm cai e obriga a decisao a ser escrita.
  A5 UMA-LINHA-POR-TRANSICAO  `set_external_owner` escreve SO' quando o dono muda:
                         tres perguntas `player` seguidas = uma linha `EXTERNAL_OWNER`.
  A6 EPISODIO-CONTADO     a transicao de volta diz `suppressed_episode=<n>` e o
                         contador recomeca em zero no episodio seguinte.
  A7 UM-AVISO-POR-EPISODIO  `ASR_PAINT_REFUSED` sai uma vez por episodio, nao uma
                         por legenda (16 linhas recusadas -> 1 aviso).

`--neg-arm`: muta COPIA de `app/webview/sotto_webview.py` em tres sitios e exige
que a arm correspondente caia -- (M1) o `external:` deixa de ser isento (A3),
(M2) o aviso por episodio passa a sair sempre (A7), (M3) `suppressed_episode`
passa a ser o total (A6). Convencao desta casa: o negativo devolve 1 quando
APANHA.

    python _main/external-owner-oracle.py
    python _main/external-owner-oracle.py --neg-arm
"""
import importlib.util
import io
import os
import re
import shutil
import sys
import tempfile
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBVIEW = os.path.join(ROOT, 'app', 'webview')
SHELL = os.path.join(WEBVIEW, 'sotto_webview.py')
sys.path.insert(0, WEBVIEW)


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class Sink(object):
    """O `log` do shell: guarda as linhas que a shell escreveria."""

    def __init__(self):
        self.lines = []

    def __call__(self, message, *_a, **_k):
        self.lines.append(str(message))

    def count(self, tag):
        return len([l for l in self.lines if l.startswith(tag)])

    def last(self, tag):
        hits = [l for l in self.lines if l.startswith(tag)]
        return hits[-1] if hits else ''


def make_shell(mod, sink):
    """Um shell MINIMO com os metodos REAIS da posse ligados.

    O que nao e' caminho da pergunta (janela, painel, overlay) fica de fora; o
    `emit_async` e' um gravador, porque A2/A4 perguntam exactamente se ele foi
    chamado.
    """
    shell = types.SimpleNamespace()
    shell.external_owner = 'local'
    shell.external_owner_episode = 0
    shell._asr_owner_episode = False
    shell.external_suppressed = 0
    shell._asr_suppressed_episode = 0
    shell.external_captions_active = False
    shell.external_captions_available = False
    shell.external_lines = 0
    shell.emitted = []
    shell.emit_async = lambda kind, payload: shell.emitted.append((kind, payload))
    shell._captions = []
    shell.pending_error = None
    # A CADEIA DE PINTURA NAO E' DESTE PORTAO. `push_caption_to_window` e' a
    # porta do overlay e tem o seu proprio instrumento (`paint-cost`,
    # `caption-lag-budget`, `paint-live-show`); aqui ela so' registra que a
    # tentativa ACONTECEU, porque a pergunta e' quem e' recusado ANTES dela.
    shell.painted = []
    shell.push_caption_to_window = lambda text, **_k: shell.painted.append(text)
    shell._reload_policy = types.SimpleNamespace(boundary=lambda **_k: None)
    for name in ('external_owner_refuses', 'set_external_owner', 'on_worker_caption'):
        setattr(shell, name, types.MethodType(getattr(mod.SottoShell, name), shell))
    return shell


def run_arms(mod, label=''):
    sink = Sink()
    mod.log = sink
    out = []

    def arm(name, ok, detail=''):
        out.append((name, bool(ok), detail))

    # ── A1: o dono LOCAL pinta, e a linha chega ao painel ────────────────
    s = make_shell(mod, sink)
    s.on_worker_caption('linha local', {'source': 'device:mic', 'final': False})
    arm('A1-LOCAL-NAO-RECUSA',
        len(s.emitted) == 1 and len(s.painted) == 1 and s.external_suppressed == 0,
        'emitted=%d painted=%d suppressed=%d'
        % (len(s.emitted), len(s.painted), s.external_suppressed))

    # ── A2: o PLAYER recusa a linha local, e nada e' emitido ─────────────
    s = make_shell(mod, sink)
    s.set_external_owner('player', reason='external-line:external', had_line=True)
    before = len(s.emitted)
    s.on_worker_caption('linha local', {'source': 'device:mic', 'final': True})
    arm('A2-PLAYER-RECUSA',
        len(s.emitted) == before and s.external_suppressed == 1
        and s._asr_suppressed_episode == 1,
        'emitted=%d suppressed=%d episodio=%d'
        % (len(s.emitted) - before, s.external_suppressed, s._asr_suppressed_episode))

    # ── A3: a linha do PROPRIO player nunca e' recusada ──────────────────
    s = make_shell(mod, sink)
    s.set_external_owner('player', reason='external-line:external', had_line=True)
    before = len(s.emitted)
    s.on_worker_caption('linha do player', {'source': 'external:player', 'final': True})
    arm('A3-PLAYER-NAO-SE-RECUSA',
        len(s.emitted) == before + 1 and s.external_suppressed == 0,
        'emitted=%d suppressed=%d' % (len(s.emitted) - before, s.external_suppressed))

    # ── A4: a recusa nao escreve no historico (o caminho do painel) ──────
    s = make_shell(mod, sink)
    s.set_external_owner('player', reason='external-line:external', had_line=True)
    before = len(s.emitted)
    for _ in range(3):
        s.on_worker_caption('descartada', {'source': 'device:mic', 'final': True})
    arm('A4-A-RECUSA-NAO-ESCREVE-HISTORICO',
        len(s.emitted) == before,
        'emit_async no ramo de recusa=%d (tem de ser 0)' % (len(s.emitted) - before))

    # ── A5: uma linha por TRANSICAO, nao por pergunta ────────────────────
    sink = Sink()
    mod.log = sink
    s = make_shell(mod, sink)
    for _ in range(3):
        s.set_external_owner('player', reason='external-line:external')
    one = sink.count('EXTERNAL_OWNER')
    s.set_external_owner('local', reason='released', had_line=True)
    two = sink.count('EXTERNAL_OWNER')
    arm('A5-UMA-LINHA-POR-TRANSICAO', one == 1 and two == 2,
        'linhas apos 3 perguntas=%d, apos a queda=%d' % (one, two))

    # ── A6: o episodio e' contado, e o numero e' DO EPISODIO ─────────────
    # DOIS episodios de tamanhos DIFERENTES: 2 e depois 3. Um total (5) nao
    # pode passar por um episodio, que e' o mutante M3 -- medido 2026-11-12, a
    # primeira versao gastava 4 de 4 e o total coincidia com o episodio, logo o
    # mutante que imprime o total passava.
    sink = Sink()
    mod.log = sink
    s = make_shell(mod, sink)
    said = []
    for n in (2, 3):
        s.set_external_owner('player', reason='external-line:external', had_line=True)
        for _ in range(n):
            s.on_worker_caption('perdida', {'source': 'device:mic', 'final': False})
        s.set_external_owner('local', reason='released', had_line=True)
        m = re.search(r'suppressed_episode=(\d+)', sink.last('EXTERNAL_OWNER owner=local'))
        said.append(int(m.group(1)) if m else -1)
    total = s.external_suppressed
    arm('A6-EPISODIO-CONTADO', said == [2, 3] and total == 5,
        'episodios ditos=%s (esperado [2, 3]) com total=%d (um total nao e\' um episodio)'
        % (said, total))

    # ── A7: um aviso por episodio, nao por legenda ───────────────────────
    sink = Sink()
    mod.log = sink
    s = make_shell(mod, sink)
    s.set_external_owner('player', reason='external-line:external', had_line=True)
    for _ in range(6):
        s.on_worker_caption('perdida', {'source': 'device:mic', 'final': False})
    warned = sink.count('ASR_PAINT_REFUSED')
    s.set_external_owner('local', reason='released', had_line=True)
    s.set_external_owner('player', reason='external-line:external', had_line=True)
    s.on_worker_caption('perdida', {'source': 'device:mic', 'final': False})
    warned2 = sink.count('ASR_PAINT_REFUSED')
    arm('A7-UM-AVISO-POR-EPISODIO', warned == 1 and warned2 == 2,
        '6 legenda(s) -> %d aviso(s); episodio novo -> %d' % (warned, warned2))
    return out


def neg_arm():
    """Tres mutacoes plantadas numa COPIA do shell; cada arm tem de cair."""
    tmp = tempfile.mkdtemp(prefix='extowner-neg-')
    try:
        src = io.open(SHELL, encoding='utf-8', errors='replace').read()
        mutants = {
            'M1-external-nao-isento': (
                "        if str(source or '').startswith('external:'):\n"
                "            return False\n", ""),
            'M2-aviso-sempre': (
                "        if not getattr(self, '_asr_owner_episode', False):",
                "        if True:"),
            'M3-episodio-e-total': (
                'f\'suppressed_episode={_lost if owner == "local" else 0} \'',
                'f\'suppressed_episode={getattr(self, "external_suppressed", 0)} \''),
        }
        caught = []
        for name, (old, new) in mutants.items():
            body = src
            for a, b in ((old, new),
                         (old.replace('\n', '\r\n'), new.replace('\n', '\r\n'))):
                if a in body:
                    body = body.replace(a, b, 1)
                    break
            else:
                caught.append((name, 'ANCORA-AUSENTE'))
                continue
            path = os.path.join(tmp, name.replace('-', '_') + '.py')
            io.open(path, 'w', encoding='utf-8', newline='').write(body)
            mod = load_module(path, 'sotto_webview_' + name.replace('-', '_'))
            arms = run_arms(mod, name)
            red = [a for a, ok, _d in arms if not ok]
            print('  %-24s arms vermelhas: %s' % (name, ', '.join(red) or '-'))
            if red:
                caught.append((name, red))
        print('NEG-ARM: %s (%d/%d mutantes apanhados)'
              % ('PASS' if len(caught) == len(mutants) else 'FAIL',
                 len(caught), len(mutants)))
        return 0 if len(caught) == len(mutants) else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv):
    mod = load_module(SHELL, 'sotto_webview')
    if '--neg-arm' in argv:
        rc = neg_arm()
        return 1 if rc == 0 else 0        # 1 = apanhou, a convencao desta casa
    arms = run_arms(mod)
    for name, ok, detail in arms:
        print('%-36s %s  %s' % (name, 'PASS' if ok else 'FAIL', detail))
    fail = [a for a, ok, _d in arms if not ok]
    print('VERDICT: %s (%d/%d arms)'
          % ('PASS' if not fail else 'FAIL', len(arms) - len(fail), len(arms)))
    return 0 if not fail else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
