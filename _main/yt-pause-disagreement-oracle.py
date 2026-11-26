#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""UMA PAUSA QUE A MEDIDA DESMENTIU NAO E' PAUSA -- o portao (2026-11-26).

O DEFEITO, verbatim do dono e do log da MESMA sessao (pid 57008):

    "i just opened sotto, went to youtube, subtitles from youtube worked for
     like 2 seconds and then froze, when i unpaused it still did not worked"

O log dele, um tick depois do outro:

    02:38:01.508  YOUTUBE_PAUSE_DISAGREED paused_flag=True clock_rate=0.58
    02:38:01.756  YOUTUBE_PAUSE_PROVEN witness=flag+clock-static held_s=0.25
    02:38:01.764  CAPTION_WINDOW_BLANKED reason=youtube-paused epoch=3
    02:38:09.834  YOUTUBE_PAUSE_RESUMED witness=clock-moved pause_s=8.1
    02:38:10.418  YOUTUBE_PAUSE_PROVEN witness=flag+clock-static held_s=0.6
    02:38:10.436  CAPTION_WINDOW_BLANKED reason=youtube-paused epoch=4

As duas testemunhas medem janelas DIFERENTES: `_yt_clock_moving` desde a foto
anterior (aqui ~8 s), `_yt_clock_static` desde a ultima posicao DIFERENTE (0,25
s). O apagar consultava so' a segunda, entao 0,25 s de buffer apagavam a legenda
de um video a andar; e o espelho `yt_source_paused` ficava ligado, e o
`external_caption` recusa CADA linha seguinte do player enquanto ele estiver
ligado -- o ecra nao voltou ao despausar. E' o congelamento que ele reportou.

O QUE ESTE ORACULO JULGA, sobre o codigo REAL:

  1. A VERDADE da regra (`youtube_clock.pause_proven`): uma pausa provada com o
     relogio a ANDAR no mesmo tick e' recusada; as outras tres combinacoes
     ficam como estavam.
  2. A LIGACAO: o shell usa ESSA funcao para `_paused_proven`, e deriva dela o
     `_now_paused` E a testemunha -- duas copias da regra divergem no proximo
     commit, e a segunda copia e' sempre a que apaga o ecra.

`--neg-arm`: muta uma COPIA do `youtube_clock.py` (`and not` -> `or`) e uma
COPIA do shell (`_now_paused = bool(_paused_proven)` -> `bool(_ct_static)`), e
exige as duas arms a VERMELHO. Um portao cujo mutante passa nao mede nada.
"""
import importlib.util
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CLOCK = os.path.join(ROOT, 'app', 'webview', 'youtube_clock.py')
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read(path):
    with open(path, encoding='utf-8', errors='replace') as fh:
        return fh.read()


def arm_truth(clock):
    """As quatro combinacoes: so' a pausa NAO desmentida vale."""
    cases = [
        ((True, False), True, 'parado e sem movimento: a pausa vale'),
        ((True, True), False, 'parado em 0,25 s mas a foto diz que andou: RECUSA'),
        ((False, True), False, 'o relogio andou: nao ha pausa'),
        ((False, False), False, 'sem medida de pausa: nao ha pausa'),
    ]
    ok, detail = True, []
    for (static, moving), want, why in cases:
        got = bool(clock.pause_proven(static, moving))
        if got != want:
            ok = False
            detail.append('static=%s moving=%s got=%s want=%s (%s)'
                          % (static, moving, got, want, why))
    return ok, '; '.join(detail) or '4/4 combinacoes'


def arm_wiring(shell_src):
    """O shell deriva `_paused_proven` da funcao, e `_now_paused` dela."""
    problems = []
    if '_paused_proven = youtube_clock.pause_proven(_ct_static, _mv_moving)' \
            not in shell_src:
        problems.append('o shell nao chama youtube_clock.pause_proven para _paused_proven')
    if '_now_paused = bool(_paused_proven)' not in shell_src:
        problems.append('_now_paused nao deriva de _paused_proven')
    # NENHUMA SEGUNDA COPIA DA REGRA: um `and not _mv_moving` inline volta a
    # divergir da funcao no proximo commit.
    inline = re.findall(r'if\s+_ct_static\s+and\s+not\s+_mv_moving', shell_src)
    if inline:
        problems.append('%d copia(s) inline da regra: %r' % (len(inline), inline[:1]))
    witness = re.search(r"witness=\(.*?clock-static.*?\)", shell_src, re.S)
    if not witness or '_paused_proven' not in witness.group(0):
        problems.append('a testemunha da borda nao deriva de _paused_proven')
    return (not problems), '; '.join(problems) or 'uma chamada, um dono'


def mutate(path, src, dst, name):
    """Escreve uma copia mutada (nunca toca no ficheiro vivo)."""
    os.makedirs(dst, exist_ok=True)
    out = os.path.join(dst, name)
    with open(out, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(path)
    return out


def neg_arm(clock, shell_src):
    caught = []
    tmp = tempfile.mkdtemp(prefix='yt-pause-neg-')
    try:
        # M1: a regra deixa de recusar a pausa desmentida.
        src = read(CLOCK)
        bad = src.replace('return bool(clock_static) and not bool(clock_moving)',
                          'return bool(clock_static) or bool(clock_moving)')
        if bad == src:
            print('NEG-ARM a-regra  ARM-MISSING (a linha mudou de forma)')
        else:
            p = mutate(bad, None, tmp, 'clock_m1.py')
            mod = load(p, 'clock_m1')
            ok, _ = arm_truth(mod)
            caught.append(('a-regra', not ok))
            print('NEG-ARM a-regra  %s' % ('CAUGHT' if not ok else 'NOT-CAUGHT'))
        # M2: o shell volta a derivar o apagar da pausa curta.
        bad2 = shell_src.replace('_now_paused = bool(_paused_proven)',
                                 '_now_paused = bool(_ct_static)')
        if bad2 == shell_src:
            print('NEG-ARM b-ligacao ARM-MISSING')
        else:
            ok2, _ = arm_wiring(bad2)
            caught.append(('b-ligacao', not ok2))
            print('NEG-ARM b-ligacao %s' % ('CAUGHT' if not ok2 else 'NOT-CAUGHT'))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return all(c for _, c in caught) and len(caught) == 2


def log_verdict(path):
    """A CONTRADICAO NO LOG, QUE E' A UNICA PROVA QUE O DONO PODE PRODUZIR (2026-11-26).

    O dono reinicia, abre um video e a linha do tempo existe. Este modo le o
    `webview-run.log` dele e responde UMA pergunta: alguma vez o ecra foi apagado
    por uma pausa que o MESMO episodio desmentiu? Um `YOUTUBE_PAUSE_PROVEN` a
    menos de 5 linhas de um `YOUTUBE_PAUSE_DISAGREED`, no mesmo video e com o
    `t` igual, e' exactamente o defeito de 2026-11-26.

    Nao entra nos arms nem na bateria: o log HISTORICO tem o defeito, logo uma
    arm que o julgasse nascia vermelha. Ele corre depois da proxima sessao do
    dono, e o veredicto e' `CLEAN` ou `CONTRADICTED` com as linhas nomeadas.
    """
    import re
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            lines = fh.read().splitlines()
    except OSError as exc:
        print('YT-PAUSE-LOG CANNOT-MEASURE reason=%r' % (exc,))
        return 3
    pat = re.compile(r'YOUTUBE_PAUSE_(DISAGREED|PROVEN)\b.*?t=([0-9.]+)'
                     r'.*?vid=(\S+)')
    seen, bad = [], []
    for n, line in enumerate(lines):
        m = pat.search(line)
        if not m:
            continue
        seen.append((n, m.group(1), m.group(2), m.group(3)))
    for n, kind, t, vid in seen:
        if kind != 'PROVEN':
            continue
        for n2, kind2, t2, vid2 in seen:
            if kind2 != 'DISAGREED' or abs(n2 - n) > 5 or vid2 != vid:
                continue
            if abs(float(t2) - float(t)) <= 0.05:
                bad.append((n, t, vid))
                break
    if not seen:
        print('YT-PAUSE-LOG CANNOT-MEASURE reason=no-pause-lines lines=%d' % len(lines))
        return 3
    print('YT-PAUSE-LOG episodes=%d contradicted=%d lines=%d'
          % (sum(1 for s in seen if s[1] == 'PROVEN'), len(bad), len(lines)))
    for n, t, vid in bad[:10]:
        print('  CONTRADICTED line=%d t=%s vid=%s' % (n + 1, t, vid))
    print('YT-PAUSE-LOG VERDICT: %s%s'
          % ('CLEAN' if not bad else 'CONTRADICTED',
             '' if not bad else ' -- a blank was decided against the same measurement'))
    return 0 if not bad else 1


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if '--log' in argv:
        i = argv.index('--log')
        if i + 1 >= len(argv):
            print('--log needs a path')
            return 2
        return log_verdict(argv[i + 1])
    clock = load(CLOCK, 'youtube_clock_live')
    shell_src = read(SHELL)

    a, da = arm_truth(clock)
    print('[%s] a-regra     a pausa desmentida e recusada -- %s'
          % ('PASS' if a else 'FAIL', da))
    b, db = arm_wiring(shell_src)
    print('[%s] b-ligacao   o shell deriva o apagar e a testemunha da regra -- %s'
          % ('PASS' if b else 'FAIL', db))

    if '--neg-arm' in argv:
        ok = neg_arm(clock, shell_src)
        print('NEG-ARM VERDICT: %s' % ('PASS' if ok else 'FAIL'))
        # A CONVENCAO DA CASA: mutante apanhado = rc 1 (`red-as-expected`).
        # Um neg-arm que sai 0 e' indistinguivel de um oraculo que nao julga.
        return 1 if ok else 0

    green = a and b
    print('YT-PAUSE-DISAGREEMENT VERDICT: %s (2 arms)' % ('GREEN' if green else 'RED'))
    return 0 if green else 1


if __name__ == '__main__':
    sys.exit(main())
