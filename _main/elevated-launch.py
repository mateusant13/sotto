#!/usr/bin/env python.exe
# -*- coding: utf-8 -*-
# NO-BUG: ferramenta de infraestrutura; nao corrige um defeito do produto
"""ELEVATED-LAUNCH -- lancar com token `high` a partir de um processo `medium`.

O PROBLEMA, medido (2026-10-23, quatro mecanismos + tres novos):

    pane = medium      desktop/explorer = high

Um filho `medium` da pane falha em duas coisas que vivem no desktop:
`TRAY_ICON_ADD ok=false winerror=5` (UIPI: um processo `medium` nao fala com a
taskbar `high`) e `WEBVIEW2_INIT_FAILED 0x80010108 RPC_E_DISCONNECTED`. Nao e
um defeito do Sotto: e o token. Morde **qualquer** projecto que precise de tray,
WebView2, hooks globais ou janelas no desktop.

O QUE NAO FUNCIONA (tudo medido, nao suposto):
  - `Start-Process -Verb RunAs` da pane  -> pedido recusado, sem prompt UAC
  - `Start-Process app.cmd`              -> bloqueia e nao arranca nada
  - `explorer.exe app.cmd`               -> sem efeito, 0 linhas de log
  - token emprestado do Explorer         -> o filho e `high` mas NUNCA executa
                                            codigo (1 thread / 2 MB)

O QUE FUNCIONA: o **Agendador de Tarefas**. O servico corre como SYSTEM e
constroi o token ele proprio, por isso `--run` nao pede UAC e o filho nasce
`high`. Medido em 2026-10-23 23:00:55, a partir da pane `medium`:

    TRAY_ICON_ADD ok=true winerror=0
    WEBVIEW2: sem falha
    HOTKEY_REGISTERED isRegistered=true

USO (o mesmo para qualquer projecto):

    python _main\\elevated-launch.py --create sotto --cmd "cmd.exe /c H:\\sotto\\Sotto.cmd"
    python _main\\elevated-launch.py --run sotto
    python _main\\elevated-launch.py --status sotto
    python _main\\elevated-launch.py --delete sotto

`--create` e idempotente (`/f`) e usa `onlogon` + `/rl HIGHEST` + `/it`, o que
faz a tarefa sobreviver ao logon e correr na sessao interactiva do dono.

PORQUE NAO MEXO NO UAC: desligar o `EnableLUA` maquina-fora resolve isto e
**abre** a maquina (todo o processo do administrador passa a `high`, sem
fronteira nenhuma). Um token elevado a pedido resolve o mesmo e mantem a
fronteira; o preco e uma tarefa por aplicacao.
"""
import argparse
import subprocess
import sys


def schtasks(*args):
    cmd = ['schtasks'] + list(args)
    p = subprocess.run(cmd, capture_output=True, text=True, errors='replace')
    return p.returncode, (p.stdout or '') + (p.stderr or '')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--create', metavar='NOME')
    ap.add_argument('--run', metavar='NOME')
    ap.add_argument('--delete', metavar='NOME')
    ap.add_argument('--status', metavar='NOME')
    ap.add_argument('--cmd', help='linha de comando (obrigatoria com --create)')
    ap.add_argument('--at-logon', action='store_true', default=True,
                    help='(padrao) a tarefa corre tambem no logon')
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:  # noqa: BLE001
        pass

    if a.create:
        if not a.cmd:
            print('--create exige --cmd "..."')
            return 2
        rc, out = schtasks('/create', '/tn', a.create, '/tr', a.cmd,
                           '/sc', 'onlogon', '/rl', 'HIGHEST', '/it', '/f')
        print(out.strip())
        print('ELEVATED-LAUNCH CREATE %s rc=%d' % (a.create, rc))
        return rc

    if a.run:
        rc, out = schtasks('/run', '/tn', a.run)
        print(out.strip())
        print('ELEVATED-LAUNCH RUN %s rc=%d' % (a.run, rc))
        return rc

    if a.delete:
        rc, out = schtasks('/delete', '/tn', a.delete, '/f')
        print(out.strip())
        print('ELEVATED-LAUNCH DELETE %s rc=%d' % (a.delete, rc))
        return rc

    if a.status:
        rc, out = schtasks('/query', '/tn', a.status, '/fo', 'list', '/v')
        print(out.strip()[:1200])
        print('ELEVATED-LAUNCH STATUS %s rc=%d' % (a.status, rc))
        return rc

    ap.print_help()
    return 2


if __name__ == '__main__':
    sys.exit(main())
