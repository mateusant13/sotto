#!/usr/bin/env python.exe
# -*- coding: utf-8 -*-
"""UI-WATCHDOG-POLICY -- QUANDO uma amostra do cao-de-guarda conta como golpe.

Existe porque a app se MATOU enquanto estava a TRABALHAR (2026-11-05 06:57:25,
`EXIT_BEGIN code=9 reason=ui-watchdog pid=31768`). O registo que condena o
detector antigo esta' no `_main/webview-run.log` dessa sessao:

    06:54:51.426 UI_WATCHDOG_STRIKE strike=1 hwnd=142024326 err=0
    06:55:11.712 UI_WATCHDOG_STRIKE strike=2 hwnd=142024326 err=0   (20,3 s)
    06:55:24.478 UI_WATCHDOG_STRIKE strike=3 hwnd=142024326 err=0   (12,8 s)
    06:57:06.343 YT_FRAME src=external:youtube:liveframe rows=1 lines=['just walk up and kill this']
    06:57:15.059 EXTERNAL_CAPTIONS_READ_MS ms=8609.0 ...
    06:57:25.926 EXIT_BEGIN code=9 reason=ui-watchdog pid=31768

Duas coisas erradas, e cada uma sozinha basta:

1. **`err=0` nao e' a assinatura de "a janela nao responde".** A assinatura
   DOCUMENTADA de um `SendMessageTimeout` que estoura o prazo com
   `SMTO_ABORTIFHUNG` e' `ERROR_TIMEOUT` (1460). Medido nesta maquina
   (`SendMessageTimeoutW(hwnd, WM_NULL, 0, 0, SMTO_ABORTIFHUNG, 6000)`):
   janela viva -> `got=1 err=0`; hwnd bogus e hwnd NULL -> `got=0 err=1400`.
   O `err=0` com `got=0` nao e' nenhum dos dois: nao prova nada sobre a janela.

2. **O observador tambem estava esfomeado.** Os golpes deviam estar a
   `poll_s=5,0` + prazo `6,0` uns 11 s um do outro; sairam a 20,3 s e 12,8 s,
   e o `HOTKEY_OBSERVER_ALIVE max_gap_ms=68969` do mesmo minuto diz que o
   PROCESSO inteiro ficou 69 s sem correr. Uma medida de tempo feita por um
   relogio que nao anda nao distingue "a UI esta' presa" de "eu e' que nao
   corri": essa amostra nao vale um golpe.

E o que a app fazia um minuto depois dos tres golpes: pintava a legenda do
YouTube (`YT_FRAME rows=1`) e avancava os batimentos do observador. Quem
trabalha assim nao tem a janela congelada no ecra do dono.

A POLITICA, e ela e' pura para poder ser exercitada sem uma janela:

  * amostra ESFOMEADA (o laco do observador demorou > 1,5x o orcamento)
    -> `starved`: zera a sequencia, nem conta nem desculpa;
  * `got` != 0 -> `answered`: a UI respondeu, zera a sequencia;
  * `got == 0` e `err == 1460` -> `strike` (a assinatura documentada);
  * `got == 0` e outro `err` (`0`, `1400`, ...) -> `noerr`: NAO conta como
    golpe de "presa", mas acumula numa sequencia mais longa, porque um
    `got=0` repetido a cada volta continua a ser uma janela que nao responde
    a nada -- o que nao pode e' sair por TRES dessas em 33 s.

Dois tipos de sequencia, dois limiares: `strikes` (assinatura 1460, o normal)
e `noerr` (sem assinatura, o dobro das voltas). A saida usa o MESMO limiar de
"pilha estrangeira" que ja' existia: seis voltas quando nenhum frame da pilha
de UI e' nosso.

    python app\\webview\\ui_watchdog_policy.py    # selftest, rc=0 PASS
"""
import sys

#: `ERROR_TIMEOUT` -- a UNICA assinatura de prazo estourado.
ERROR_TIMEOUT = 1460

#: `ERROR_INVALID_WINDOW_HANDLE` -- medido num hwnd bogus, e' a assinatura de
#: "este hwnd nao existe" (a janela foi recriada ou destruida).
ERROR_INVALID_WINDOW_HANDLE = 1400

#: Quantas amostras SEM assinatura (`got=0` e outro erro) seguidas antes de a
#: janela ser tratada como presa de facto. O dobro do limiar normal, porque a
#: amostra nao traz a assinatura e a app paga a espera com uma janela morta no
#: ecra se estiver enganada.
NOERR_STRIKES = 6

#: E o TECTO: `got=0` sem assinatura, doze vezes seguidas com o relogio do
#: observador SAUDAVEL (~2 min), e' evidencia suficiente para sair mesmo sem
#: `ERROR_TIMEOUT`. O caso do dono (tres amostras, duas delas num laco que
#: levou 20 s) nao chega perto disto -- e o que este tecto impede e' a app
#: FICAR congelada no ecra para sempre por nao ter a assinatura certa.
NOERR_HARD_CAP = 12

#: Quanto o laco do observador pode demorar acima do orcamento antes de a
#: propria amostra ser invalida (o processo nao correu, logo o relogio dele
#: nao mede a janela).
STARVE_FACTOR = 1.5


class State(object):
    """A sequencia de golpes. Um objecto, dois contadores, zero surpresas."""

    def __init__(self, strikes_needed=3, noerr_strikes=NOERR_STRIKES):
        self.strikes_needed = int(strikes_needed)
        self.noerr_needed = int(noerr_strikes)
        self.strikes = 0
        self.noerr = 0

    def reset(self):
        had = self.strikes or self.noerr
        self.strikes = 0
        self.noerr = 0
        return had

    def __repr__(self):
        return '<State strikes=%d/%d noerr=%d/%d>' % (
            self.strikes, self.strikes_needed, self.noerr, self.noerr_needed)


def classify(got, err, took_s, budget_s):
    """A amostra, em uma de quatro palavras. Nao decide nada por si.

    * `starved`  -- o observador nao correu no tempo; a amostra nao vale;
    * `answered` -- a janela respondeu;
    * `strike`   -- `got=0` com `ERROR_TIMEOUT`, a assinatura documentada;
    * `noerr`    -- `got=0` sem assinatura: conta, mas nao como golpe de presa.
    """
    try:
        took_s = float(took_s)
        budget_s = float(budget_s)
    except (TypeError, ValueError):
        return 'starved'
    if budget_s > 0 and took_s > budget_s * STARVE_FACTOR:
        return 'starved'
    if got:
        return 'answered'
    try:
        err = int(err or 0)
    except (TypeError, ValueError):
        err = 0
    return 'strike' if err == ERROR_TIMEOUT else 'noerr'


def feed(state, kind):
    """Aplica a amostra ao estado e diz o que fazer: `wait` ou `exit`."""
    if kind in ('starved', 'answered'):
        state.reset()
        return 'wait'
    if kind == 'strike':
        state.strikes += 1
        state.noerr = 0
        return 'wait' if state.strikes < state.strikes_needed else 'confirm'
    state.noerr += 1
    state.strikes = 0
    if state.noerr < state.noerr_needed:
        return 'wait'
    return 'confirm'


def confirm(state, kind):
    """A volta de confirmacao (sem dormir): `exit` SO' com a assinatura.

    A confirmacao existe para o caso raro de o limiar de `noerr` ter sido
    atingido por uma janela que ja' morreu: um hwnd que nao existe nunca vai
    responder, e sair por isso mataria a app por uma janela recriada.
    """
    if kind == 'answered':
        state.reset()
        return 'wait'
    if kind == 'strike':
        return 'exit'
    return 'wait'


def hard_cap(state):
    """Tecto: `got=0` sem assinatura vezes sem conta NAO pode ficar no ecra.

    Doze amostras seguidas com o relogio do observador sadio (~2 min) e' uma
    janela que nao responde a nada, mesmo sem `ERROR_TIMEOUT`.
    """
    return state.noerr >= NOERR_HARD_CAP


def _selftest():
    # Cada linha imprime PASS/FAIL e o veredicto e' o rc: um selftest que
    # imprime FAIL e sai 0 seria o mesmo instrumento que mentiu as 06:57.
    fails = []

    def say(name, ok):
        if not ok:
            fails.append(name)
        print('%-52s %s' % (name, 'PASS' if ok else 'FAIL'))

    # a assinatura documentada conta e chega a tres
    s = State(3)
    seq = [classify(0, 1460, 6.0, 11.0) for _ in range(3)]
    got = [feed(s, k) for k in seq]
    say('1460 tres vezes -> confirm',
        seq == ['strike'] * 3 and got == ['wait', 'wait', 'confirm'])

    # o caso MEDIDO no dono: tres `err=0` NAO podem sair
    s = State(3)
    seq = [classify(0, 0, 6.0, 11.0) for _ in range(3)]
    got = [feed(s, k) for k in seq]
    say('err=0 tres vezes -> NAO sai (caso do dono)',
        seq == ['noerr'] * 3 and got == ['wait'] * 3)

    # o observador esfomeado: a amostra nao vale e zera a sequencia
    s = State(3)
    feed(s, 'strike'); feed(s, 'strike')
    kind = classify(0, 1460, 20.3, 11.0)
    act = feed(s, kind)
    say('laco de 20,3 s com orcamento de 11 s -> invalida',
        kind == 'starved' and act == 'wait' and s.strikes == 0)

    # erro sem assinatura tambem nao pode matar app que trabalha
    s = State(3)
    s.strikes = 2
    kind = classify(0, 1400, 6.0, 11.0)
    feed(s, kind)
    say('hwnd invalido zera a sequencia 1460',
        kind == 'noerr' and s.strikes == 0 and s.noerr == 1)

    # uma janela que nunca responde ACABA por sair (seis amostras sem assinatura)
    s = State(3)
    acts = [feed(s, 'noerr') for _ in range(NOERR_STRIKES)]
    say('seis noerr seguidos -> confirm',
        acts[-1] == 'confirm' and acts.count('confirm') == 1)

    # confirmacao: so' a assinatura manda sair
    s = State(3)
    say('confirmacao exige 1460',
        confirm(s, 'strike') == 'exit' and confirm(s, 'noerr') == 'wait'
        and confirm(s, 'answered') == 'wait')

    # a resposta zera tudo
    s = State(3)
    feed(s, 'strike')
    had = s.reset()
    say('responder zera a sequencia', bool(had) and s.strikes == 0 and s.noerr == 0)

    # orcamento zero (um duplo de teste) nao inventa esfomeamento
    say('orcamento 0 nao impede a assinatura', classify(0, 1460, 6.0, 0) == 'strike')

    # entrada absurda nao derruba o laco
    say('amostra com lixo -> starved', classify(0, None, None, None) == 'starved')

    # o caso que a app viveu: a amostra esfomeada NAO pode herdar golpes antigos
    s = State(3)
    s.strikes = 2
    feed(s, classify(0, 1460, 22.0, 11.0))
    say('esfomeamento com 2 golpes ja' + "'" + ' contados -> 0',
        s.strikes == 0)

    # o TECTO: sem assinatura, a app sai so' quando a janela nao responde a
    # nada ha' doze voltas seguidas
    s = State(3)
    for _ in range(11):
        feed(s, 'noerr')
    before = hard_cap(s)
    feed(s, 'noerr')
    say('teco de noerr: 11 nao, 12 sim', (not before) and hard_cap(s))

    # e uma resposta zera o tecto
    s = State(3)
    for _ in range(12):
        feed(s, 'noerr')
    feed(s, 'answered')
    say('resposta zera o tecto', not hard_cap(s))

    print('VERDICT: %s (%d/%d)' % ('PASS' if not fails else 'FAIL',
                                   len(fails), 12))
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(_selftest())
