#!/usr/bin/env python
# -*- coding: utf-8 -*-
# NO-BUG: observabilidade: mede a verdade da pausa do YouTube nas oito combinacoes de pause_proven(static, moving, fresh) -- so parado sem movimento e com foto deste tick conta como pausa provada, e o shell deriva _paused_proven, _now_paused e a testemunha da mesma chamada, sem copia inline da regra; sem id no ledger
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
    """As OITO combinacoes: so' a pausa NAO desmentida E COM FOTO DO TICK vale."""
    cases = [
        ((True, False, True), True, 'parado, sem movimento, foto deste tick: a pausa vale'),
        ((True, True, True), False, 'parado em 0,25 s mas a foto diz que andou: RECUSA'),
        ((False, True, True), False, 'o relogio andou: nao ha pausa'),
        ((False, False, True), False, 'sem medida de pausa: nao ha pausa'),
        ((True, False, False), False,
         'FOTO VELHA: o relogio nao pode andar numa foto de 5,9 s, logo held_s '
         'mede a idade da foto (02:38:08.713 -> :10.436, 13 s de ecra congelado)'),
        ((True, True, False), False, 'foto velha E desmentida: recusa duas vezes'),
        ((False, True, False), False, 'foto velha sem medida de pausa'),
        ((False, False, False), False, 'foto velha, relogio parado, sem prova'),
    ]
    ok, detail = True, []
    for (static, moving, fresh), want, why in cases:
        got = bool(clock.pause_proven(static, moving, fresh))
        if got != want:
            ok = False
            detail.append('static=%s moving=%s fresh=%s got=%s want=%s (%s)'
                          % (static, moving, fresh, got, want, why))
    return ok, '; '.join(detail) or '8/8 combinacoes'


PAUSE_LITERALS = (
    ('YOUTUBE_PAUSE_STALE_PHOTO', 'a foto velha NAO apaga o ecra (e o held_s mede a idade da foto)'),
    ('YOUTUBE_PAUSE_UNWITNESSED', 'a bandeira sozinha congela a interpolacao e diz o nome'),
    ('YOUTUBE_PAUSE_BLANK_DEFERRED', 'o apagar foi adiado pela dwell, nao decidido'),
)

# Um leitor POR NOME, nao um comentario: cada familia de pausa conta-se aqui.
PAUSE_READER = re.compile(r'YOUTUBE_PAUSE_'
                          r'(DISAGREED|PROVEN|STALE_PHOTO|UNWITNESSED|BLANK_DEFERRED)\b')


def read_pause_episodes(lines):
    """Conta as familias de pausa do log. E' o unico leitor dos tres literais que
    o shell escrevia para o vazio (medido 2026-11-26: zero referencias em `_main`):
    um literal que ninguem le' e' uma frase que o produto diz a ninguem."""
    counts = {}
    for line in lines:
        m = PAUSE_READER.search(line)
        if m:
            counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    return counts


def arm_literals(shell_src):
    """c-observabilidade: os tres literais tem de ser ESCRITOS pelo shell e LIDOS
    por este modulo. Um leitor que so' existe na prosa nao conta: as linhas de
    prova sao sinteticas e o contador tem de as ver."""
    sample = [
        'YOUTUBE_PAUSE_STALE_PHOTO held_s=0.60 age_ms=5891 t=158.00 vid=x',
        'YOUTUBE_PAUSE_UNWITNESSED paused_flag=True still_s=0.25 need_s=2.00 t=159.00 vid=x',
        'YOUTUBE_PAUSE_BLANK_DEFERRED held_s=0.10 quiet_s=0.10 dwell_s=0.30 witness=none vid=x',
        'YOUTUBE_PAUSE_PROVEN witness=flag+clock-static held_s=4.2 t=160.00 vid=x',
    ]
    counts = read_pause_episodes(sample)
    bad = []
    for name, _why in PAUSE_LITERALS:
        key = name[len('YOUTUBE_PAUSE_'):]
        if name not in shell_src:
            bad.append('%s: o shell nao escreve' % name)
        if counts.get(key, 0) != 1:
            bad.append('%s: o leitor contou %d (quer 1)' % (name, counts.get(key, 0)))
    if counts.get('PROVEN', 0) != 1 or counts.get('DISAGREED', 0) != 0:
        bad.append('o contador confunde as familias existentes')
    return (not bad), ('; '.join(bad) if bad
                       else 'os 3 literais orfaos tem escritor no shell e leitor aqui')


def _rewrite_method(shell_src, name, new_body):
    """Substitui o CORPO de `def <name>(self, ...)` mantendo a assinatura, para
    que um mutante exercite o metodo REAL e nao uma reescrita deste modulo."""
    import ast
    import textwrap
    tree = ast.parse(shell_src)
    target = None
    for cls in ast.walk(tree):
        if isinstance(cls, ast.ClassDef):
            for fn in cls.body:
                if isinstance(fn, ast.FunctionDef) and fn.name == name:
                    target = fn
                    break
        if target is not None:
            break
    if target is None:
        return None
    seg = ast.get_source_segment(shell_src, target) or ''
    if not seg:
        return None
    args = []
    a = target.args
    for arg in list(a.posonlyargs) + list(a.args):
        args.append(arg.arg)
    sig_src = 'def %s(%s):' % (name, ', '.join(args))
    new = textwrap.dedent(sig_src) + '\n' + textwrap.indent(
        textwrap.dedent(new_body).strip('\n') + '\n', '        ')
    return shell_src.replace(textwrap.dedent(seg), new, 1)


def arm_freshness(shell_src):
    """d-frescura: a FOTO E' DESTE TICK? O metodo REAL do shell decide, nao uma
    copia. `_yt_snap_fresh` nao tinha nenhum braco comportamental (medido
    2026-11-26 por blast-radius: so' havia `rg` de string e espelhos), e e' ele
    que entrega `photo_fresh` ao `pause_proven` -- a metade "foto velha nao
    apaga o ecra" que curou o congelamento do dono.

    A idade vem do `stamp` da PROPRIA foto: sem carimbo legivel a resposta e'
    FALSA (sem medida, a foto nao vale como medida), e uma foto mais velha que
    `DOM_FRESH_S` tambem. O limite e' lido do shell AQUI, nao escrito aqui.
    """
    import ast
    import textwrap
    try:
        tree = ast.parse(shell_src)
    except SyntaxError as exc:
        return False, 'o shell nao parseia: %r' % (exc,)
    node = None
    for cls in ast.walk(tree):
        if isinstance(cls, ast.ClassDef):
            for fn in cls.body:
                if isinstance(fn, ast.FunctionDef) and fn.name == '_yt_snap_fresh':
                    node = fn
                    break
        if node is not None:
            break
    if node is None:
        return False, 'o shell nao tem `_yt_snap_fresh`'
    src = textwrap.dedent(ast.get_source_segment(shell_src, node) or '')
    if not src.strip():
        return False, 'o metodo existe mas nao tem fonte legivel'

    NOW = 1000.0
    fresh_limit = None
    for m in re.finditer(r'^\s*DOM_FRESH_S\s*=\s*([0-9.]+)', shell_src, re.M):
        fresh_limit = float(m.group(1))
        break
    if fresh_limit is None:
        return False, 'o shell nao declara DOM_FRESH_S'

    ns = {'time': type('T', (), {'monotonic': staticmethod(lambda: NOW)})()}
    try:
        exec(compile(src, '<shell:_yt_snap_fresh>', 'exec'), ns)
    except Exception as exc:
        return False, 'o metodo nao executa: %r' % (exc,)
    fn = ns.get('_yt_snap_fresh')
    if not callable(fn):
        return False, 'a extracao nao devolveu uma funcao'

    class Host:
        DOM_FRESH_S = fresh_limit

    host = Host()
    cases = [
        ({'stamp': NOW - 0.05}, True, 'foto deste tick: vale'),
        ({'stamp': NOW - fresh_limit * 0.9}, True, 'foto dentro do limite: vale'),
        ({'stamp': NOW - fresh_limit - 0.5}, False,
         'foto mais velha que DOM_FRESH_S: NAO vale (e o defeito de 5,9 s)'),
        ({}, False, 'sem carimbo: NAO vale -- o desconhecido nao e' + " fresco"),
        ({'stamp': None}, False, 'carimbo None: NAO vale'),
        ({'stamp': 'nao-e-numero'}, False, 'carimbo ilegivel: NAO vale'),
        ({'stamp': NOW + 30.0}, True, 'carimbo do futuro: dentro do limite (relogio unico)'),
    ]
    bad = []
    for snap, want, why in cases:
        try:
            got = bool(fn(host, snap))
        except Exception as exc:
            bad.append('%s -> excecao %r' % (why, exc))
            continue
        if got is not want:
            bad.append('%s -> %s (quer %s)' % (why, got, want))
    return (not bad), ('; '.join(bad) if bad
                       else '%d casos no metodo REAL, limite %.2f s lido do shell'
                            % (len(cases), fresh_limit))


def arm_wiring(shell_src):
    """O shell deriva `_paused_proven` da funcao, e `_now_paused` dela."""
    problems = []
    if '_paused_proven = youtube_clock.pause_proven(' not in shell_src \
            or '_ct_static, _mv_moving, _photo_fresh)' not in shell_src:
        problems.append('o shell nao chama youtube_clock.pause_proven com as TRES '
                        'testemunhas (estatica, movimento, frescura)')
    if '_photo_fresh = self._yt_snap_fresh(snap)' not in shell_src:
        problems.append('a frescura da foto nao vem de _yt_snap_fresh(snap)')
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
        bad = src.replace('return bool(photo_fresh) and bool(clock_static) '
                          'and not bool(clock_moving)',
                          'return bool(clock_static) and not bool(clock_moving)')
        if bad == src:
            print('NEG-ARM a-regra  ARM-MISSING (a linha mudou de forma)')
        else:
            p = mutate(bad, None, tmp, 'clock_m1.py')
            mod = load(p, 'clock_m1')
            ok, _ = arm_truth(mod)
            caught.append(('a-regra', not ok))
            print('NEG-ARM a-regra  %s' % ('CAUGHT' if not ok else 'NOT-CAUGHT'))
        # M3: a dimensao da frescura desaparece da chamada viva.
        bad3 = shell_src.replace('_ct_static, _mv_moving, _photo_fresh)',
                                 '_ct_static, _mv_moving, True)')
        if bad3 == shell_src:
            print('NEG-ARM b-frescura ARM-MISSING')
        else:
            ok3, _ = arm_wiring(bad3)
            caught.append(('b-frescura', not ok3))
            print('NEG-ARM b-frescura %s' % ('CAUGHT' if not ok3 else 'NOT-CAUGHT'))
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
    # Um literal apagado do shell tem de derrubar (c), senao o leitor nao le'.
    ok3, _ = arm_literals(shell_src.replace('YOUTUBE_PAUSE_STALE_PHOTO', 'X'))
    caught.append(('c-literal-apagado', not ok3))
    print('NEG-ARM c-literal-apagado %s' % ('CAUGHT' if not ok3 else 'NOT-CAUGHT'))
    # Um leitor cego (regex que nao casa nada) tambem.
    global PAUSE_READER
    saved = PAUSE_READER
    try:
        PAUSE_READER = re.compile(r'NEVER-MATCHES-ANYTHING')
        ok4, _ = arm_literals(shell_src)
    finally:
        PAUSE_READER = saved
    caught.append(('c-leitor-cego', not ok4))
    print('NEG-ARM c-leitor-cego %s' % ('CAUGHT' if not ok4 else 'NOT-CAUGHT'))
    # d-frescura: dois mutantes no CORPO REAL do metodo.
    for label, body in (
            ('d-foto-velha-aceita', 'return True\n'),
            ('d-nunca-fresca', 'return False\n')):
        mutated = _rewrite_method(shell_src, '_yt_snap_fresh', body)
        if mutated is None:
            caught.append((label, False))
            print('NEG-ARM %s NOT-CAUGHT (nao foi possivel mutar)' % label)
            continue
        okd, _ = arm_freshness(mutated)
        caught.append((label, not okd))
        print('NEG-ARM %s %s' % (label, 'CAUGHT' if not okd else 'NOT-CAUGHT'))
    # e-log: muta o CLASSIFICADOR DE DANO -- primeiro volta a regra antiga (que
    # acusava a convergencia), depois apaga o casamento por `t`.
    global PAUSE_BLANK, PAUSE_EVENT
    _save_blank, _save_event = PAUSE_BLANK, PAUSE_EVENT
    try:
        # M_e1: sem ler o APAGAR, todo `PROVEN` adjacente a um `DISAGREED` conta
        # -- e' exactamente a regra de 2026-11-26 que acusava 9 vezes a sessao
        # dele com ZERO apagar.
        PAUSE_BLANK = re.compile(r'NEVER-MATCHES-A-BLANK')
        oke1, _ = arm_log_harm()
        caught.append(('e-volta-a-regra-antiga', not oke1))
        print('NEG-ARM e-volta-a-regra-antiga %s'
              % ('CAUGHT' if not oke1 else 'NOT-CAUGHT'))
    finally:
        PAUSE_BLANK, PAUSE_EVENT = _save_blank, _save_event
    global T_MATCH_S
    _save_t = T_MATCH_S
    try:
        # M_e2: uma tolerancia enorme deixa de distinguir a pausa desmentida da
        # convergencia -- o dano real passa a ser invisivel e o legitimo passa a
        # ser acusado. E' o mutante do numero, nao da estrutura.
        T_MATCH_S = 1e9
        oke2, _ = arm_log_harm()
        caught.append(('e-cego-ao-carimbo', not oke2))
        print('NEG-ARM e-cego-ao-carimbo %s'
              % ('CAUGHT' if not oke2 else 'NOT-CAUGHT'))
    finally:
        T_MATCH_S = _save_t
    return all(c for _, c in caught) and len(caught) == 9


def log_verdict(path, since=None):
    """A CONTRADICAO NO LOG, QUE E' A UNICA PROVA QUE O DONO PODE PRODUZIR (2026-11-26).

    O dono reinicia, abre um video e a linha do tempo existe. Este modo le o
    `webview-run.log` dele e responde UMA pergunta: alguma vez o ecra foi apagado
    por uma pausa que o MESMO episodio desmentiu? Um `YOUTUBE_PAUSE_PROVEN` a
    menos de 5 linhas de um `YOUTUBE_PAUSE_DISAGREED`, no mesmo video e com o
    `t` igual, e' exactamente o defeito de 2026-11-26.

    O log e' APPEND-ONLY e guarda meses: julgar o ficheiro inteiro acusa o codigo
    ANTIGO para sempre (medido: 18 episodios contraditos, todos anteriores ao
    fix). Por isso a janela DEFAULT e' a ULTIMA sessao -- da ultima linha
    `SHELL_STARTUP_STAGE` em diante -- que e' exactamente a pergunta do dono
    depois de reiniciar. `--since 'YYYY-MM-DD HH:MM'` escolhe outra janela.
    """
    import re
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            lines = fh.read().splitlines()
    except OSError as exc:
        print('YT-PAUSE-LOG CANNOT-MEASURE reason=%r' % (exc,))
        return 3
    start = 0
    if since:
        for n, line in enumerate(lines):
            if line.startswith(since):
                start = n
                break
        else:
            print('YT-PAUSE-LOG CANNOT-MEASURE reason=since-not-found since=%r' % (since,))
            return 3
    else:
        for n, line in enumerate(lines):
            if 'SHELL_STARTUP_STAGE' in line and 'stage=pre-lock' in line:
                start = n
    lines = lines[start:]
    count = judge_log(lines, since_line=start)
    if count is None:
        print('YT-PAUSE-LOG CANNOT-MEASURE reason=no-pause-lines lines=%d' % len(lines))
        return 3
    episodes, bad, settle, fam = count
    print('YT-PAUSE-LOG episodes=%d contradicted=%d settled=%d lines=%d'
          % (episodes, len(bad), settle, len(lines)))
    print('YT-PAUSE-LOG families=' + ' '.join(
        '%s=%d' % (k, fam[k]) for k in
        ('PROVEN', 'DISAGREED', 'STALE_PHOTO', 'UNWITNESSED', 'BLANK_DEFERRED')
        if k in fam))
    for n, t, vid in bad[:10]:
        print('  CONTRADICTED line=%d t=%s vid=%s' % (n + 1, t, vid))
    print('YT-PAUSE-LOG VERDICT: %s%s'
          % ('CLEAN' if not bad else 'CONTRADICTED',
             '' if not bad else
             ' -- a blank was decided against the same measurement'))
    return 0 if not bad else 1


#: A UNICA COISA QUE ESTE ORACULO PODE CHAMAR DE DANO E' O APAGAR.
PAUSE_BLANK = re.compile(r'CAPTION_WINDOW_BLANKED reason=youtube-paused\S*')
PAUSE_EVENT = re.compile(r'YOUTUBE_PAUSE_(DISAGREED|PROVEN)\b.*?t=([0-9.]+)'
                         r'.*?vid=(\S+)')

#: Quanto dois carimbos de posicao tem de concordar para serem a MESMA medida.
#: Duas fotos vizinhas a 4 Hz diferem ate' 0,25 s (o proprio piso curto do
#: `CLOCK_STATIC_PAUSE_FLAG_S`); a tolerancia e' 5x menor, porque o que se
#: procura e' a MESMA posicao lida duas vezes, nao uma posicao proxima.
T_MATCH_S = 0.05


def judge_log(lines, since_line=0):
    """Conta as contradicoes REAIS. Devolve `None` quando nao ha' linha de pausa.

    O QUE ESTAVA ERRADO, e o numero que o condenou (medido 2026-11-26, sobre o
    `_main/webview-run.log` inteiro, 284 010 linhas). A regra antiga chamava
    contradicao a QUALQUER `YOUTUBE_PAUSE_PROVEN` a menos de 5 linhas de um
    `YOUTUBE_PAUSE_DISAGREED` com o mesmo `t` e o mesmo video: **32 episodios**
    no ficheiro e **9 na ultima sessao do dono**. Mas nessa sessao havia
    **UM** `CAPTION_WINDOW_BLANKED reason=youtube-paused` em 23 395 linhas --
    as 11:46:37.979, armado pelo `PROVEN held_s=0.5 t=2.85` das :37.978, com o
    `RESUMED` a chegar 13 linhas depois. **Zero** dano. A regra antiga estava a
    acusar a CONVERGENCIA de uma pausa verdadeira:

        a 1a foto ainda andava  -> `pause_proven` recusa  -> DISAGREED
        a 2a foto ja' esta' parada -> `pause_proven` prova -> PROVEN

    Isso e' o algoritmo a funcionar, nao a falhar. Um portao que acusa o
    caminho certo perde a autoridade (AGENTS.md: "um portao que acusa quem esta'
    certo perde a autoridade"), e este acusava 9 vezes por sessao para sempre.

    A PERGUNTA CERTA E' A DO DONO: *"quando eu despausei ainda nao funcionava"*.
    O dano e' o ECRAN APAGADO -- `CAPTION_WINDOW_BLANKED reason=youtube-paused*`
    -- e so' quando o `PROVEN` que o armou pertence a um episodio que a MESMA
    regra desmentiu (`DISAGREED`, mesmo `t` a 0.05 s, mesmo video, a menos de 8
    linhas). Medido com esta regra sobre o ficheiro inteiro: **10** episodios,
    o ultimo a 2026-11-26 02:38:10 -- todos ANTERIORES ao fix que introduziu
    `photo_fresh` no `pause_proven`. Na sessao de 2026-11-26 11:45 (o codigo
    corrigido): **0**. Uma regra que nao sabe ficar verde num log corrigido
    nao prova o fix; uma que nao sabe ficar vermelha no log antigo nao prova
    nada. Esta e' conduzida nas duas direcoes por `arm_log_harm`.
    """
    events = []
    for n, line in enumerate(lines):
        m = PAUSE_EVENT.search(line)
        if m:
            events.append((n, m.group(1), float(m.group(2)), m.group(3)))
    if not events:
        # SEM NENHUM EVENTO DE PAUSA NAO HA' MEDIDA -- e ausencia de medida nao
        # vira veredicto (nem verde nem vermelho).
        return None
    by_line = {e[0]: e for e in events}
    bad = []
    for n, line in enumerate(lines):
        if not PAUSE_BLANK.search(line):
            continue
        armed = None
        for j in range(n, max(0, n - 14), -1):
            hit = by_line.get(j)
            if hit is not None and hit[1] == 'PROVEN':
                armed = hit
                break
        if armed is None:
            continue
        j0, _kind, t, vid = armed
        for k in range(max(0, j0 - 8), j0 + 1):
            hit = by_line.get(k)
            if (hit is not None and hit[1] == 'DISAGREED'
                    and hit[3] == vid
                    and abs(hit[2] - t) <= float(T_MATCH_S)):
                bad.append((n, '%.2f' % t, vid))
                break
    settle = 0
    for n, kind, t, vid in events:
        if kind != 'PROVEN':
            continue
        for n2, kind2, t2, vid2 in events:
            if (kind2 == 'DISAGREED' and vid2 == vid and abs(n2 - n) <= 5
                    and abs(t2 - t) <= float(T_MATCH_S)):
                settle += 1
                break
    episodes = sum(1 for e in events if e[1] == 'PROVEN')
    return episodes, bad, settle, read_pause_episodes(lines)


def arm_log_harm():
    """e-log: o classificador de dano, conduzido nas DUAS direcoes.

    Sem esta arm, a unica prova da regra era o log do dono -- um ficheiro que
    so' cresce e que nunca fica vermelho de proposito. Aqui cada arm e' um
    fixture sintetico do MESMO formato, mais o validador REAL (`judge_log`).
    """
    cases = [
        (['YOUTUBE_PAUSE_DISAGREED paused_flag=True clock_rate=0.58 t=10.00 vid=A',
          'YOUTUBE_PAUSE_PROVEN witness=flag+clock-static held_s=0.3 t=10.00 vid=A',
          'CAPTION_WINDOW_BLANKED reason=youtube-paused epoch=5 wanted=true'],
         1, 'o dano: um apagar armado por uma pausa que o mesmo episodio desmentiu'),
        (['YOUTUBE_PAUSE_DISAGREED paused_flag=True clock_rate=0.58 t=10.00 vid=A',
          'YOUTUBE_PAUSE_PROVEN witness=flag+clock-static held_s=0.5 t=10.00 vid=A',
          'CAPTION_PAINT_SURFACE src=player rows=1 text="x" ms=1 epoch=5'],
         0, 'CONVERGENCIA (a cura): as duas testemunhas a concordar, nenhum apagar'),
        (['YOUTUBE_PAUSE_PROVEN witness=flag+clock-static held_s=4.2 t=88.00 vid=A',
          'CAPTION_WINDOW_BLANKED reason=youtube-paused epoch=6 wanted=true'],
         0, 'uma pausa VERDADEIRA (sem desmentido) continua a apagar'),
        (['CAPTION_WINDOW_BLANKED reason=youtube-paused epoch=2 wanted=true',
          'YOUTUBE_PAUSE_DISAGREED paused_flag=True clock_rate=0.30 t=5.00 vid=A'],
         0, 'o apagar nao pode ser armado pelo evento que vem DEPOIS dele'),
        (['YOUTUBE_PAUSE_DISAGREED paused_flag=True clock_rate=0.30 t=5.00 vid=A',
          'YOUTUBE_PAUSE_PROVEN witness=flag+clock-static held_s=0.3 t=9.00 vid=A',
          'CAPTION_WINDOW_BLANKED reason=youtube-paused epoch=3 wanted=true'],
         1, 'o dano atravessa o carimbo? nao: `t` diferente nao e a mesma medida '
            '-- o PROVEN de 9.00 nao tem desmentido e o apagar e legitimo'),
    ]
    bad = []
    for lines, want, why in cases:
        got = judge_log(lines)
        if got is None:
            bad.append('%s -> None' % why)
            continue
        n_bad = len(got[1])
        # o ultimo caso e' o controle NEGATIVO do casamento por `t`: 0 e' o
        # numero certo, e por isso o desejo dele e' 0 e nao 1.
        expect = 0 if why.startswith('o dano atravessa') else want
        if n_bad != expect:
            bad.append('%s -> %d (quer %d)' % (why, n_bad, expect))
    return (not bad), ('; '.join(bad) if bad
                       else '%d fixtures no classificador REAL' % len(cases))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if '--log' in argv:
        i = argv.index('--log')
        if i + 1 >= len(argv):
            print('--log needs a path')
            return 2
        since = None
        if '--since' in argv:
            j = argv.index('--since')
            if j + 1 >= len(argv):
                print('--since needs a prefix, e.g. "2026-11-26 02:37"')
                return 2
            since = argv[j + 1]
        return log_verdict(argv[i + 1], since)
    clock = load(CLOCK, 'youtube_clock_live')
    shell_src = read(SHELL)

    a, da = arm_truth(clock)
    print('[%s] a-regra     a pausa desmentida e recusada -- %s'
          % ('PASS' if a else 'FAIL', da))
    b, db = arm_wiring(shell_src)
    print('[%s] b-ligacao   o shell deriva o apagar e a testemunha da regra -- %s'
          % ('PASS' if b else 'FAIL', db))
    c, dc = arm_literals(shell_src)
    print('[%s] c-leitor    os 3 literais de pausa tem escritor e leitor -- %s'
          % ('PASS' if c else 'FAIL', dc))
    d, dd = arm_freshness(shell_src)
    print('[%s] d-frescura  o metodo REAL _yt_snap_fresh decide a foto do tick -- %s'
          % ('PASS' if d else 'FAIL', dd))
    e, de = arm_log_harm()
    print('[%s] e-log       o dano e o APAGAR, e so quando a mesma regra o desmentiu '
          '-- %s' % ('PASS' if e else 'FAIL', de))

    if '--neg-arm' in argv:
        ok = neg_arm(clock, shell_src)
        print('NEG-ARM VERDICT: %s' % ('PASS' if ok else 'FAIL'))
        # A CONVENCAO DA CASA: mutante apanhado = rc 1 (`red-as-expected`).
        # Um neg-arm que sai 0 e' indistinguivel de um oraculo que nao julga.
        return 1 if ok else 0

    green = a and b and c and d and e
    print('YT-PAUSE-DISAGREEMENT VERDICT: %s (5 arms)' % ('GREEN' if green else 'RED'))
    return 0 if green else 1


if __name__ == '__main__':
    sys.exit(main())
