# NO-BUG: A MAQUINA CALADA NAO E' UM DISPOSITIVO PARTIDO -- o oraculo da janela que espera. -- trabalho de CAPACIDADE/observabilidade pedido pelo dono; nao corresponde a nenhum id de `_main/bug-ledger.json`, e declarado aqui em vez de inventar um id.
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
rc=0  PASS  (ou, no `--neg-arm`, o mutante passou despercebido)
rc=1  FAIL  (ou, no `--neg-arm`, o mutante foi APANHADO)
rc=2  o mutante nem correu (ancora ausente -- o oraculo esta' velho)
"""
import argparse
import ast
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
#: Acima disto a "janela plana" ja' e' a espera longa que o defeito mediu.
FLAT_MAX_S = 8.0


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

    # 1-4: a maquina calada estende a MESMA tap -- cada extensao e' a JANELA
    # PLANA que o produto declara (2026-11-11: 4 s, `wasapi_loopback.
    # FLAT_EVIDENCE_S`). O numero NAO se copia para aqui: um oraculo que carimba
    # 12/24/48/60 a mao fica vermelho numa cura que esta' certa, e foi o que
    # aconteceu quando a dobragem 6->12->24->48 deu lugar ao tecto da evidencia.
    # A propriedade que os quatro arms julgam e' a que importa: o MESMO tap
    # estende (nunca None), sempre pelo numero declarado, e esse numero e' curto.
    flat = flat_evidence_s(mod)
    out.append(('1 maquina calada, janela plana -> espera a janela plana',
                hold(0.0, FLOOR, silent, WINDOW, 0, CAP), flat))
    out.append(('2 segunda janela calada -> a MESMA janela plana',
                hold(0.0, FLOOR, silent, WINDOW, 1, CAP), flat))
    out.append(('3 terceira -> a MESMA janela plana',
                hold(0.0, FLOOR, silent, WINDOW, 2, CAP), flat))
    out.append(('4 a janela plana e curta: nunca uma espera longa',
                hold(0.0, FLOOR, silent, WINDOW, 3, CAP), flat))

    # 5: o audio mudou de sitio -- a rotacao E' o movimento certo.
    out.append(('5 outro endpoint a tocar -> rotaciona (None)',
                hold(0.0, FLOOR, playing, WINDOW, 0, CAP), None))

    # 6: medidor ILEGIVEL ({}) nunca e' "sem sinal": comportamento anterior.
    out.append(('6 medidor ilegivel {} -> rotaciona (None)',
                hold(0.0, FLOOR, {}, WINDOW, 0, CAP), None))

    # 7: A LEI MUDOU A 2026-11-02, e o numero esta' no log do dono. O `device_peak`
    # e' o MAXIMO da janela, nao o agora: um som no inicio dela (o clique que abre o
    # video, um bipe) revogava a espera de todas as janelas seguintes e a escada
    # abriu dez clientes WASAPI em dois minutos (`BRIDGE_METER peak=0.1677` as
    # 22:24:32, `device-rotated (flat)` as :41, :50, 22:25:00, :07, :14, :30, :46,
    # 22:26:02, :17, :34). Ele ouviu isso como o audio a sumir. Com o medidor VIVO
    # calado, a janela espera -- e a tap acima do piso ja' nao decide nada.
    out.append(('7 tap acima do piso mas maquina calada AGORA -> espera a janela plana',
                hold(0.050, FLOOR, silent, WINDOW, 0, CAP), flat))
    # 7-bis: o numero que ele viu. Pico de janela 0.1677, medidor vivo a zero.
    out.append(('7b pico de janela 0.1677 com a maquina calada -> espera a janela plana',
                hold(0.1677, FLOOR, silent, WINDOW, 0, CAP), flat))

    # 8: lixo no payload do medidor nao pode explodir nem inventar espera.
    out.append(('8 valores nao numericos -> rotaciona (None)',
                hold(0.0, FLOOR, {'a': 'x'}, WINDOW, 0, CAP), None))
    # 9: a janela plana e' CURTA POR DESENHO. O defeito medido foi uma espera de
    # 43,6 s (6 -> 12 -> 24 -> 48) num rung que entregou zero; um numero acima
    # de FLAT_MAX_S volta a ser essa espera, ainda que a funcao o devolva certo.
    out.append(('9 a janela plana nao passa de %.1f s' % FLAT_MAX_S,
                flat if flat <= FLAT_MAX_S else None, flat))
    return out


def flat_evidence_s(mod):
    """A janela plana LIDA do produto, pelo proprio resolvedor dele.

    `_flat_evidence_s` e' o unico sitio que sabe o numero (importa
    `wasapi_loopback.FLAT_EVIDENCE_S` e cai para `inf` sem o tap). Perguntar-lhe
    e' diferente de copiar o literal: a cura pode mudar 4 para 3 ou 5 e a
    propriedade continua a ser julgada. Sem o resolvedor NAO ha' arm: levanta.
    """
    fn = getattr(mod, '_flat_evidence_s', None)
    if fn is None:
        raise SystemExit('o product.nao tem _flat_evidence_s -- oraculo velho')
    return float(fn())


def emit_names_the_wait(worker_path):
    """A linha `emit(type="status", state=<... "tap-silent-desktop" ...>)` existe.

    ANCORADO NA ARVORE, NAO NO TEXTO (2026-11-11). A verificacao anterior era a
    string `state="tap-silent-desktop"`; o produto passou a escrever
    `state="tap-own-endpoint-loud" if _loud_here else "tap-silent-desktop"` e a
    ancora morreu SEM a propriedade mudar -- o oraculo ficava vermelho numa cura
    que estava certa. Uma chamada `emit` com a palavra-chave `state` e a
    constante 'tap-silent-desktop' na expressao do valor sobrevive a
    reformatacao e a novas condicoes; so' deixa de valer se a emissao
    desaparecer, mudar de nome ou deixar de nomear a espera.
    """
    try:
        with open(worker_path, encoding='utf-8', newline='') as fh:
            tree = ast.parse(fh.read())
    except (OSError, SyntaxError):
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Name) and node.func.id == 'emit'):
            continue
        for kw in node.keywords:
            if kw.arg != 'state':
                continue
            for sub in ast.walk(kw.value):
                if isinstance(sub, ast.Constant) and sub.value == 'tap-silent-desktop':
                    return True
    return False


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
        ('a linha da espera existe', emit_names_the_wait(worker_path)),
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
            print('NEG-ARM IMPOSSIVEL: ancora do mutante ausente -- o oraculo precisa de ser revisto')
            return None
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
        if caught is None:
            # rc=2 = ERRO DE MONTAGEM (a ancora do mutante desapareceu), o mesmo
            # codigo que os outros `--neg-arm` deste repo usam: nao e' "o
            # controlo nao apanhou", e' "o controlo nao correu".
            return 2
        # A frase sem dois-pontos e' a que o `:expectred` da bateria procura
        # (`NEG-ARM PASS`); a forma com dois-pontos e' a canonica deste repo.
        print('NEG-ARM %s' % ('PASS' if caught else 'FAIL'))
        print('NEG-ARM: %s' % ('PASS' if caught else 'FAIL'))
        # `:expectred` NA BATERIA: um controlo que APANHA o mutante sai 1, e 0 quando
        # nao apanha -- a mesma polaridade dos outros `red-as-expected-*` deste repo.
        return 1 if caught else 0
    ok = run(worker)
    print('VERDICT: %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
