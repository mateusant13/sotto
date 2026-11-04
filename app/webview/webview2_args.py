"""O PORTO DE DEPURACAO DO WEBVIEW2 E' NOSSO, NUNCA DA CAIXA.

`WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS` e' lido pelo loader do WebView2 no
ambiente do PROCESSO, uma unica vez, quando o ambiente e' criado. Logo um valor
herdado do processo que nos largou (uma lane, um terminal com
`--remote-debugging-port=9333`, um perfil de shell) abre um porto de depuracao em
TODAS as janelas WebView2 desta app -- e, pior, faz o produto comportar-se
diferente na sessao do dono e na de uma lane, que e' a pior classe de defeito
que existe aqui: a medicao passa e o dono nao tem o comportamento.

O PRODUTO NAO PRECISA DE PORTO NENHUM. A fonte de legenda do YouTube
(`app/webview/youtube_cdp_source.py`) le o browser DO DONO em 9222; o WebView2
proprio desta app nunca e' alvo de CDP. Portanto:

  - sem pedido explicito, o valor herdado e' REMOVIDO (e a linha de log diz o
    que foi removido, para a contaminacao de uma lane nao ser silenciosa);
  - uma sessao de depuracao pede-o com `--cdp-port N` / `SOTTO_CDP_PORT=N`, e o
    valor resultante e' exatamente UM argumento: o porto pedido.

Toda a decisao vive em `plan()`, que e' pura: um oraculo executa esta funcao com
o ambiente a mao e depois confirma no ambiente `os.environ` que o valor
realmente desapareceu.
"""

from __future__ import annotations

import os

#: A variavel que o loader do WebView2 le do ambiente do processo.
INHERIT_VAR = 'WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'

#: O argumento que so' um pedido explicito produz.
PORT_ARG = '--remote-debugging-port=%d'


def plan(inherited, cdp_port=None):
    """Decide o valor FINAL da variavel. Pura: nao toca no ambiente.

    `inherited` e' o valor que o processo recebeu (ou None). `cdp_port` e' o
    porto pedido explicitamente (int ou string; None = ninguem pediu).

    Devolve `{'action', 'value', 'dropped'}`, onde `action` e' exatamente um de:

      'set'     -- um porto foi pedido; `value` e' o argumento UNICO que vai la'
      'cleared' -- havia um valor herdado e nao houve pedido: `value` e' None
      'none'    -- nao havia nada herdado nem pedido: nada muda no ambiente
    """
    port = None
    if cdp_port not in (None, ''):
        port = int(str(cdp_port).strip())
        if not (1 <= port <= 65535):
            raise ValueError('cdp_port fora de 1..65535: %r' % (cdp_port,))
    dropped = inherited or ''
    if port is not None:
        return {'action': 'set', 'value': PORT_ARG % port, 'dropped': dropped}
    if inherited:
        return {'action': 'cleared', 'value': None, 'dropped': dropped}
    return {'action': 'none', 'value': None, 'dropped': ''}


def apply(decision, environ=None):
    """Aplica o `plan()` ao ambiente do PROCESSO e devolve o que ficou.

    `environ` existe para o oraculo poder provar a mutacao num mapping proprio
    sem tocar no ambiente de quem o executa.
    """
    env = os.environ if environ is None else environ
    action = decision.get('action')
    if action == 'set':
        env[INHERIT_VAR] = decision['value']
    elif action == 'cleared':
        # `pop` e nao `del`: uma decisao 'cleared' sem a chave presente nao e'
        # um erro, e' so' uma corrida perdida.
        env.pop(INHERIT_VAR, None)
    elif action != 'none':
        raise ValueError('action desconhecida: %r' % (action,))
    return {'action': action,
            'present': INHERIT_VAR in env,
            'value': env.get(INHERIT_VAR),
            'dropped': decision.get('dropped') or ''}
