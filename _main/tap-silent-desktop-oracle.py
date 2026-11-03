"""A MAQUINA CALADA NAO E' UM DISPOSITIVO PARTIDO -- o oraculo da janela que espera.

O DEFEITO QUE ISTO JULGA (medido 2026-11-02 na sessao viva do dono, pid 4404):
com o desktop em silencio, a escada de dispositivos abriu **12 clientes WASAPI em
3 minutos** (`STATUS_APPLIED text="device-rotated (flat)"` a cada ~15 s, sempre
`peak=0.0`), e cada abertura e' um hitch no motor de audio que ele partilha com
todas as outras apps. A escada nao estava errada sobre os candidatos -- estava a
fazer a pergunta errada. A pergunta certa no fim de uma janela plana e'
*"alguem esta' a tocar alguma coisa?"*, e o medidor VIVO
(`wasapi_loopback.live_render_peaks`) responde-a para todos os endpoints de uma vez.

O QUE ESTE ORACULO EXECUTA: a funcao REAL do worker, `silent_desktop_hold`, com
sete arms; e o `--neg-arm` leva a MESMA funcao ao estado anterior (a guarda
desligada) numa COPIA do ficheiro e exige que os arms 1-2 fiquem vermelhos. Um
oraculo que nao apanha o seu proprio mutante nao e' um portao.

Uso:  python _main/tap-silent-desktop-oracle.py [--worker PATH] [--neg-arm]
rc=0  GREEN (ou, no `--neg-arm`, o mutante foi APANHADO)
rc=1  RED   (ou o mutante passou despercebido)
"""
import argparse
import importlib.util
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_WORKER = os.path.join(HERE, '..', 'worker', 'sotto_worker.py')

FLOOR = 0.002
WINDOW = 6.0
CAP = 60.0


def load_module(path):
    """Importa o ficheiro do worker pelo CAMINHO, sem entrar em `sys.path` dele."""
    spec = importlib.util.spec_from_file_location('sotto_worker_under_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def arms(mod):
    """(nome, obtido, esperado) -- `obtido` e' o que a funcao REAL devolve."""
    hold = mod.silent_desktop_hold
    silent = {'a': 0.0000, 'b': 0.0003, 'c': 0.001}
    playing = {'a': 0.0000, 'b': 0.4400, 'c': 0.001}
    out = []

    # 1-4: a maquina calada estende a MESMA tap, dobrando ate' ao tecto.
    out.append(('1 maquina calada, janela plana -> espera 12 s',
                hold(0.0, FLOOR, silent, WINDOW, 0, CAP), 12.0))
    out.append(('2 segunda janela calada -> 24 s',
                hold(0.0, FLOOR, silent, WINDOW, 1, CAP), 24.0))
    out.append(('3 terceira -> 48 s',
                hold(0.0, FLOOR, silent, WINDOW, 2, CAP), 48.0))
    out.append(('4 tecto: a quarta nao passa de 60 s',
                hold(0.0, FLOOR, silent, WINDOW, 3, CAP), 60.0))

    # 5: o audio mudou de sitio -- a rotacao E' o movimento certo.
    out.append(('5 outro endpoint a tocar -> rotaciona (None)',
                hold(0.0, FLOOR, playing, WINDOW, 0, CAP), None))

    # 6: medidor ILEGIVEL ({}) nunca e' "sem sinal": comportamento anterior.
    out.append(('6 medidor ilegivel {} -> rotaciona (None)',
                hold(0.0, FLOOR, {}, WINDOW, 0, CAP), None))

    # 7: esta tap CARREGA sinal -- a janela plana nao e' silencio da maquina.
    out.append(('7 esta tap acima do piso -> rotaciona (None)',
                hold(0.050, FLOOR, silent, WINDOW, 0, CAP), None))

    # 8: lixo no payload do medidor nao pode explodir nem inventar espera.
    out.append(('8 valores nao numericos -> rotaciona (None)',
                hold(0.0, FLOOR, {'a': 'x'}, WINDOW, 0, CAP), None))
    return out


def wiring(worker_path):
    """A guarda esta' LIGADA no sitio certo? Texto do fonte, braco de fiacao.

    O repo usa este braco quando correr o caminho vivo custa um caption
    (`reveal-wired`). Aqui o que se exige e' que o ramo do fim da janela pergunte
    ao medidor ANTES de fechar a tap: um predicado perfeito que ninguem chama e'
    um ficheiro morto.
    """
    text = open(worker_path, encoding='utf-8', newline='').read()
    checks = [
        ('a funcao existe', 'def silent_desktop_hold(' in text),
        ('o tecto esta declarado', 'TAP_SILENT_DESKTOP_MAX_S = 60.0' in text),
        ('o medidor tem um leitor so', 'def _live_render_peaks(' in text),
        ('a janela plana pergunta ao medidor antes de fechar',
         'live = _live_render_peaks()' in text),
        ('a espera devolve a janela SEGUINTE, nao um fecho',
         'return now + hold_s' in text),
        ('a escada usa essa janela',
         'extended = window_ended(' in text and 'window_end = extended' in text),
        ('a linha da espera existe', 'state="tap-silent-desktop"' in text),
    ]
    return checks


def run(worker_path, negate=False):
    mod = load_module(worker_path)
    results = arms(mod)
    ok = True
    for name, got, want in results:
        same = (got == want) if isinstance(want, float) or want is None else False
        if isinstance(want, float) and isinstance(got, (int, float)):
            same = abs(float(got) - want) < 1e-6
        print('ARM %-56s got=%-8s want=%-8s %s'
              % (name, got, want, 'PASS' if same else 'FAIL'))
        ok = ok and same
    for name, passed in wiring(worker_path):
        print('WIRE %-55s %s' % (name, 'PASS' if passed else 'FAIL'))
        ok = ok and passed
    return ok


def neg_arm(worker_path):
    """Desliga a guarda numa COPIA e exige os arms 1-2 VERMELHOS."""
    # O MUTANTE VIVE AO LADO DO ORIGINAL, e nao em TMP: o worker importa os irmaos
    # (`engine_switch`, `wasapi_loopback`) por caminho relativo, e uma copia em
    # `%TEMP%` morre com `ModuleNotFoundError` antes de qualquer arm correr --
    # medido: o primeiro `--neg-arm` deste ficheiro falhou exactamente assim.
    tmpdir = os.path.dirname(os.path.abspath(worker_path))
    copy = os.path.join(tmpdir, '_mutant-silent-desktop-%d.py' % os.getpid())
    try:
        text = open(worker_path, encoding='utf-8', newline='').read()
        # O ficheiro pode estar CRLF: a ancora e' escrita no MESMO separador que ele usa.
        nl = '\r\n' if '\r\n' in text else '\n'
        needle = nl.join(['    if not live:', '        return None', ''])
        mutant = ('    return None  # MUTANTE: a guarda desligada (o defeito de 2026-11-02)'
                  + nl)
        if needle not in text:
            print('NEG-ARM: ancora nao encontrada -- o oraculo precisa de ser revisto')
            return False
        open(copy, 'w', encoding='utf-8', newline='').write(text.replace(needle, mutant, 1))
        mod = load_module(copy)
        hold = mod.silent_desktop_hold
        silent = {'a': 0.0, 'b': 0.0003}
        caught = (hold(0.0, FLOOR, silent, WINDOW, 0, CAP) is None
                  and hold(0.0, FLOOR, silent, WINDOW, 2, CAP) is None)
        print('NEG-ARM mutante=guarda-desligada janelas_que_deviam_esperar=%s %s'
              % ('estendidas' if not caught else 'rotacionadas', 'PASS' if caught else 'FAIL'))
        return caught
    finally:
        try:
            os.remove(copy)
        except OSError:
            pass


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--worker', default=DEFAULT_WORKER)
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args(argv)
    worker = os.path.abspath(args.worker)
    if args.neg_arm:
        caught = neg_arm(worker)
        print('NEG-ARM PASS' if caught else 'NEG-ARM FAIL')
        # `:expectred` NA BATERIA: um controlo que APANHA o mutante sai 1, e 0 quando
        # nao apanha -- a mesma polaridade dos outros `red-as-expected-*` deste repo.
        return 1 if caught else 0
    ok = run(worker)
    print('VERDICT: %s' % ('GREEN' if ok else 'RED'))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
