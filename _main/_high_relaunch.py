"""Re-larga ESTE instrumento com o token de um processo `high`.

NASCEU DE UM DEFEITO MEDIDO, 2026-11-01. Dois passos da bateria
(`strip-stats-wave`, `strip-stats-log-budget`) publicavam
`VERDICT: SKIPPED - ... a pagina nunca ficou viva ... a caixa estava demasiado
carregada para medir`. A razao era FALSA: os registos dos bracos (40 linhas cada)
mostram `SHELL_STARTUP_STAGE stage=pre-lock` seguido de uma excecao do WebView2
(`Microsoft.Web.WebView2.WinForms.WebView2.<InitCoreWebView2Async>d__25.MoveNext()`).
A pane larga a `medium` (`S-1-16-8192`) e o WebView2 nao inicializa ai'; 35 s de
espera eram publicados como "caixa carregada", uma afirmacao que a evidencia
contradiz.

A primitiva NAO se reescreve aqui: `_main/strip_launch_as_token.py` ja' faz isto
(e o `--selftest` dele exige EXECUCAO e heranca do nivel). Este modulo so' poe a
descoberta da fonte, a retentativa, e a leitura do rc do filho num sitio so', com
os tres factos que custaram medicao:

  * O DIREITO ERRADO DERRUBA O PEDIDO INTEIRO. `TOKEN_ADJUST_SESSIONID` exige
    `SeTcbPrivilege` e sozinho devolve `err=5`; um pedido que o inclua parece
    "sem acesso" e nao e'. A primitiva ja' pede o conjunto certo.
  * A DESCOBERTA E' RETENTADA; A MEDICAO NAO. `_selftest_source()` falhou 2 em 20
    chamadas seguidas nesta caixa. Uma passagem sem fonte media a `medium`,
    recebia `WEBVIEW2_INIT_FAILED` e PUBLICAVA RED -- um veredicto sobre o
    produto que era um veredicto sobre o lugar de onde o instrumento foi largado.
  * O HANDLE PRECISA DE DOIS ACESSOS. So' `SYNCHRONIZE` deixa ESPERAR mas nao LER
    o codigo; `GetExitCodeProcess` falha e o pai caia no caminho "medir assim
    mesmo", reescrevendo por cima do relatorio do filho a partir de uma `medium`.

Uso, no `main()` do instrumento, ANTES de qualquer medicao:

    rc = high_relaunch.relaunch_if_needed(__file__, argv)
    if rc is not None:
        return rc

`relaunch_if_needed` devolve `None` quando ja' se corre a `HIGH` (mede tu) e o rc
do filho quando houve re-largada; nunca devolve um rc inventado.
"""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time

TOKEN_ENV = 'SOTTO_MEASURED_HIGH'

HERE = os.path.dirname(os.path.abspath(__file__))
# O NOME TEM HIFEN: por isso nao se importa, carrega-se por caminho (o mesmo
# que `_strip-surface-probe.py` faz, e a razao pela qual ele cunha um nome
# sem hifen para o modulo carregado).
LAUNCHER = os.path.join(HERE, 'launch-as-token.py')

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)


def _load():
    import importlib.util
    spec = importlib.util.spec_from_file_location('strip_launch_as_token',
                                                  LAUNCHER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def integrity():
    """A integridade DESTE processo: `{'pid','sid','name','token'}`."""
    try:
        module = _load()
        sid = module.integrity_of()
        return {'pid': os.getpid(), 'sid': sid,
                'name': module.integrity_name(sid),
                'token': os.environ.get(TOKEN_ENV) == '1'}
    except Exception as exc:                                    # noqa: BLE001
        return {'pid': os.getpid(), 'sid': None, 'name': 'UNKNOWN',
                'token': os.environ.get(TOKEN_ENV) == '1', 'error': repr(exc)}


def relaunch_if_needed(script, argv, *, attempts=3, retry_sleep_s=1.5,
                       wait_ms=900000):
    """Ver o docstring do modulo. `None` = "ja' es' `HIGH`: mede tu"."""
    module = _load()
    this = integrity()
    if this['name'] == 'HIGH':
        return None
    source = None
    for attempt in range(attempts):
        candidate = module._selftest_source()
        if candidate and module.integrity_name(
                module.integrity_of(candidate)) == 'HIGH':
            source = candidate
            break
        if attempt < attempts - 1:
            time.sleep(retry_sleep_s)
    if not source:
        print('INTEGRIDADE: sem fonte `high` nesta sessao (%d tentativas). '
              'NAO se mede a `medium`: mediria WEBVIEW2_INIT_FAILED e '
              'chamar-lhe-ia veredicto do produto.' % attempts, flush=True)
        return 3
    os.environ[TOKEN_ENV] = '1'
    ok, err, child = module.launch(
        source, sys.executable, [os.path.abspath(script)] + list(argv),
        cwd=HERE)
    if not ok:
        print('RE-LARGADA FALHOU: CreateProcessAsUser err=%d (fonte pid=%d)'
              % (err, source), flush=True)
        return 3
    kernel32.OpenProcess.restype = wt.HANDLE
    handle = kernel32.OpenProcess(0x00100000 | 0x1000,  # SYNCHRONIZE|QUERY
                                  False, child)
    if not handle:
        print('RE-LARGADA: sem handle para o filho pid=%d' % child, flush=True)
        return 3
    kernel32.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
    kernel32.WaitForSingleObject.restype = wt.DWORD
    kernel32.GetExitCodeProcess.argtypes = [wt.HANDLE, ctypes.POINTER(wt.DWORD)]
    kernel32.WaitForSingleObject(handle, wait_ms)
    code = wt.DWORD()
    ok_code = kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
    kernel32.CloseHandle(handle)
    print('medido pelo filho pid=%d (fonte pid=%d, %s): rc=%s'
          % (child, source,
             module.integrity_name(module.integrity_of(source)),
             code.value if ok_code else '?'), flush=True)
    if not ok_code:
        # O FILHO MEDIU; O RC DELE NAO PODE SER LIDO. Nao se mede outra vez (a
        # segunda ronda a `medium` apagaria o relatorio dele), e nao se publica
        # um veredicto que ninguem leu.
        return 3
    return int(code.value)


WEBVIEW2_SIGNS = ('WEBVIEW2_INIT_FAILED', 'InitCoreWebView2Async',
                  'RPC_E_DISCONNECTED')
LOAD_SIGNS = ()


def webview2_failure(text):
    """O codigo do WebView2 numa leitura, ou `None`. Ver `WEBVIEW2_SIGNS`."""
    for line in (text or '').splitlines():
        if any(sign in line for sign in WEBVIEW2_SIGNS):
            import re
            m = re.search(r'0x[0-9A-Fa-f]{8}|\(([^)]+)\)', line)
            return (m.group(0) if m else line.strip())[:80]
    return None
