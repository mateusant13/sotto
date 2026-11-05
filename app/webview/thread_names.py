"""O NOME DE CADA FIO QUE A SHELL ABRE -- legivel de FORA do processo.

PORQUE EXISTE (medido 2026-11-05)

A shell em REPOUSO queimava 23,4 % de um nucleo na instancia do dono e nao havia
como dizer QUAL dos ~40 fios era: `threading.Thread(name=...)` e' um atributo
Python, invisivel para qualquer outro processo, e o `py-spy` nao consegue
anexar-se a esta shell a partir desta pane -- a shell corre em integridade
`high` (o desktop dele) e a pane em `medium`, logo `py-spy record --pid` devolve
`Acesso negado (os error 5)`. Medido, nao suposto.

O que sobra e' medir de fora com o que o Windows oferece: `GetThreadTimes` por
fio (CPU de cada fio, exato) e `GetThreadDescription` (o nome). O primeiro ja'
existia; o segundo nao, porque nenhum fio do processo se apresentava.

`install()` envolve `threading.Thread.start` UMA vez: cada fio, ao arrancar,
escreve o proprio `Thread.name` como descricao do SO. Uma mudanca, cobertura de
todos os fios -- inclusive dos que este modulo nao conhece.

O QUE NAO FAZ

  * nao muda o comportamento de nenhum fio (o corpo corre igual, so' depois de
    escrever o nome);
  * nao falha: qualquer erro do Windows e' engolido (um nome e' diagnostico);
  * nao instala duas vezes (`install()` e' idempotente).
"""
from __future__ import annotations

import ctypes
import threading

_INSTALLED = False
_MAX_CHARS = 64


def _kernel32():
    return ctypes.WinDLL('kernel32', use_last_error=True)


def _set_description(text: str) -> bool:
    """Escreve o nome no fio ATUAL. `False` quando o Windows nao deixa."""
    try:
        k = _kernel32()
        fn = getattr(k, 'SetThreadDescription', None)
        if fn is None:
            return False
        body = str(text or '')[: _MAX_CHARS - 1]
        fn.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
        fn.restype = ctypes.c_long
        h = k.GetCurrentThread()
        return int(fn(ctypes.c_void_p(h), body)) >= 0
    except Exception:  # noqa: BLE001
        return False


def name_current(text: str) -> bool:
    """Nome explicito para quem nao passa por `install()` (o fio principal)."""
    return _set_description(text)


def install() -> bool:
    """Cada `Thread.start()` passa a nomear-se. Idempotente, nunca levanta."""
    global _INSTALLED
    if _INSTALLED:
        return True
    try:
        original = threading.Thread.start

        def start(self):  # noqa: ANN001 - assinatura do stdlib
            try:
                label = str(getattr(self, 'name', '') or '')
                inner = self._target
                if inner is not None and not getattr(inner, '_sotto_named', False):
                    def _wrapped(*a, **kw):
                        _set_description(label)
                        return inner(*a, **kw)
                    _wrapped._sotto_named = True       # type: ignore[attr-defined]
                    self._target = _wrapped
                elif inner is None:
                    # SUBCLASSE QUE SOBRESCREVE `run` (2026-11-05). Metade dos
                    # fios da shell sao `class X(threading.Thread)` com `run`
                    # proprio -- para esses `_target` e' None e o nome nunca
                    # chegava ao SO. Medido: o fio mais quente depois da cura do
                    # CDP aparecia como `(sem nome)`.
                    original_run = self.run

                    def _run_wrapped(*a, **kw):
                        _set_description(label)
                        return original_run(*a, **kw)
                    self.run = _run_wrapped            # type: ignore[assignment]
            except Exception:  # noqa: BLE001
                pass
            return original(self)

        threading.Thread.start = start
        _INSTALLED = True
        return True
    except Exception:  # noqa: BLE001
        return False


def installed() -> bool:
    return _INSTALLED
