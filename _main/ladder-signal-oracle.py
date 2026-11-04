"""A ESCADA DE CANDIDATOS PERGUNTA "QUEM ESTA A TOCAR **AGORA**"?

O DEFEITO (dono, 2026-10-30, verbatim: *"por que a merda do meu audio ainda some?
arruam caralho"*), medido nesta maquina:

* `_main/webview-run.log` desta revisao tem **3 060** linhas `device-rotated
  reason=flat`, e o painel dizia-lhe `No audio to transcribe`/`Audio tap silent`
  a cada 30 s -- com `BRIDGE_SILENT_BENIGN evidence_age_s=259`, isto e', a repetir
  um veredicto de quatro minutos antes.
* A escada decide a ordem **no arranque do worker** (`device_candidates()`, rung A
  ordenada pelo medidor nesse instante) e depois roda para o candidato SEGUINTE da
  lista. Se ele ainda nao estava a tocar quando o worker nasceu, todas as janelas
  caem em endpoints silenciosos e a escada roda para sempre sem nunca voltar ao que
  passou a ter som.
* Sonda independente desta lane (fora do worker): `wasapi_loopback.live_render_peaks`
  mediu **um** endpoint com sinal, `{2f1295af-...}` = `CABLE Input`, pico **0.649**;
  e um `WasapiLoopbackTap` directo nesse endpoint entregou **30/30 blocos com sinal,
  pico 0.661** em 3 s. O caminho de captura esta' SAO; o que estava errado era a
  ordem por que a escada o abria.

Os bracos:
  1-4  `signal_ranked_next` -- comportamento, com medidor INJECTADO (sem dispositivo).
  5    o sitio da rotacao no worker USA a funcao (le' o CODIGO, nao o comentario).
  6    o shell LIMPA o veredicto de silencio quando o tap volta a carregar sinal.
  7    o vigia de auto-relancamento NAO reinicia a app com som a tocar.
  8    o proprio `shell_relaunch` prova os bracos do som (`--selftest`).

`--neg-arm` muta o WORKER (copia, nunca o ficheiro vivo) para voltar a rodar pela
ordem estatica e exige que ESTE oraculo fique VERMELHO.
"""
# NO-BUG: instrumento da queixa do dono de 2026-10-30 (*"por que a merda do meu audio
# ainda some? arruam caralho"*). Mede a ESCADA de candidatos do worker, a limpeza do
# veredicto de silencio no shell e a guarda de som do auto-relancamento; nao corrige
# nenhum deles -- quem corrige sao os dois ficheiros que ele le.
from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKER = os.path.join(REPO, 'worker', 'sotto_worker.py')
SHELL = os.path.join(REPO, 'app', 'webview', 'sotto_webview.py')
RELAUNCH = os.path.join(REPO, 'app', 'webview', 'shell_relaunch.py')

rows = []


def add(ok, label, detail=''):
    rows.append((bool(ok), label, str(detail)))


def read(path):
    with io.open(path, encoding='utf-8') as fh:
        return fh.read()


def load_helper(source):
    """A funcao `signal_ranked_next`, compilada sozinha (sem carregar modelos)."""
    start = source.index('def signal_ranked_next(')
    # O FIM e' o proximo `def` de TOPO, nao a primeira ocorrencia do NOME: o
    # docstring do helper cita `device_candidates()` e uma fatia ingenua cortava a
    # funcao a meio (medido: devolvia o candidato errado sem levantar erro).
    end = source.index('\ndef device_candidates(', start)
    ns = {}
    exec(compile(source[start:end], WORKER, 'exec'), ns)
    return ns['signal_ranked_next']


def run(worker_path=WORKER):
    source = read(worker_path)
    fn = load_helper(source)

    # -- 1. quem esta' a tocar AGORA passa a ser o proximo -------------------
    cands = [
        {'name': 'VoiceMeeter Input', 'endpoint_id': 'a'},
        {'name': 'Speakers (NVIDIA Broadcast)', 'endpoint_id': 'b'},
        {'name': 'CABLE Input', 'endpoint_id': 'c'},
    ]
    live = {'a': 0.0, 'b': 0.0004, 'c': 0.6492}
    nxt = fn(cands, 1, peaks=lambda: live)
    add(nxt['name'] == 'CABLE Input',
        'a rotacao escolhe o endpoint que ESTA a tocar',
        'escolhido=%r ordem=%r' % (nxt['name'], [c['name'] for c in cands]))
    add([c['name'] for c in cands][1] == 'CABLE Input',
        'o candidato escolhido fica no LUGAR da rotacao (nada e saltado)',
        str([c['name'] for c in cands]))

    # -- 2. sem leitura, a ordem NAO se mexe ("sem leitura" != "sem sinal") ---
    cands2 = [{'name': 'A', 'endpoint_id': 'a'}, {'name': 'B', 'endpoint_id': 'b'}]
    n2 = fn(cands2, 1, peaks=lambda: {})
    add(n2['name'] == 'B' and [c['name'] for c in cands2] == ['A', 'B'],
        'medidor indisponivel mantem a ordem que ja existe', repr(n2['name']))

    # -- 3. tudo abaixo do piso: ordem intacta -------------------------------
    cands3 = [{'name': 'A', 'endpoint_id': 'a'}, {'name': 'B', 'endpoint_id': 'b'}]
    n3 = fn(cands3, 0, peaks=lambda: {'a': 0.0, 'b': 0.0001})
    add(n3['name'] == 'A', 'sinal abaixo do piso nao reordena', repr(n3['name']))

    # -- 4. fim da lista -> None --------------------------------------------
    add(fn([{'name': 'A', 'endpoint_id': 'a'}], 1) is None,
        'fim da lista devolve None (a escada fecha o ramo)', 'k=1 len=1')

    # -- 5. o SITIO DA ROTACAO usa a funcao (le' codigo, nao comentario) ------
    # O comentario acima da chamada nomeia a funcao; o braco le' a CHAMADA.
    call = re.search(r'nxt\s*=\s*signal_ranked_next\(\s*candidates\s*,'
                     r'\s*attempt_no\s*\+\s*1\s*\)', source)
    add(call is not None,
        'a rotacao do worker chama signal_ranked_next(candidates, attempt_no+1)',
        'chamada=%r' % (call.group(0) if call else None))
    add('def signal_ranked_next(' in source
        and 'live_render_peaks' in source.split('def signal_ranked_next(')[1].split('def device_candidates(')[0],
        'a funcao pergunta ao medidor VIVO (live_render_peaks) e nao a lista fixa',
        'ok')

    # -- 6. o shell limpa o veredicto velho, e so' com a prova certa --------
    # MEDIDO nesta maquina, 2026-10-30 09:00:57: o painel dizia `namedState=no-audio`,
    # `panel.status='not ready'`, e ao mesmo tempo `live.count=1` com a legenda
    # `'fuve da |'` no ecra -- porque `no_audio` (nascido de uma janela
    # `reason=flat`, que significa "nada transcrevivel NESTA janela") nunca era
    # limpo. A prova de que ha' audio a transcrever e' uma LEGENDA, nao um pico:
    # `flat` pode trazer `peak=0.78` (musica) e continuar sem fala.
    shell = read(SHELL)
    add('NO_AUDIO_CLEARED reason=caption' in shell,
        'o shell limpa o veredicto de silencio quando chega uma LEGENDA', 'log')
    add('TAP_SIGNAL_FLOOR' not in shell,
        'a limpeza NAO e por pico (um pico alto nao prova fala)', 'const removida')
    clear = re.search(r'if self\.no_audio:\n'
                      r'(?:.*\n)*?\s+self\.no_audio\s*=\s*False', shell)
    add(clear is not None,
        'a limpeza e um ramo explicito `if self.no_audio:` que o poe a False',
        'guarda=%r' % (clear.group(0)[:40] if clear else None))
    pos_caption = shell.find('NO_AUDIO_CLEARED reason=caption')
    pos_ingest = shell.find("if kind == 'caption':")
    add(0 <= pos_ingest < pos_caption,
        'a limpeza vive no ramo da INGESTAO da legenda, nao num tick qualquer',
        'ingest=%d limpeza=%d' % (pos_ingest, pos_caption))

    # -- 7. o vigia nao reinicia com som a tocar ----------------------------
    relaunch = read(RELAUNCH)
    add('SHELL_RELAUNCH_DEFERRED reason=audio' in relaunch,
        'o vigia de relancamento recusa reiniciar com som a tocar', 'log')
    add('sound_playing' in relaunch and 'import audio_playing' in relaunch,
        'a sonda de som esta LIGADA na arma do vigia', 'arm()')

    # -- 8. o selftest do proprio modulo prova-o ---------------------------
    proc = subprocess.run([sys.executable, RELAUNCH, '--selftest'],
                          capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
    add(proc.returncode == 0 and 'SELFTEST PASS' in (proc.stdout or ''),
        'shell_relaunch --selftest continua PASS com os bracos do som',
        (proc.stdout or proc.stderr or '').strip().splitlines()[-1:] or '')

    failed = [r for r in rows if not r[0]]
    for ok, label, detail in rows:
        print('%s %s%s' % ('PASS' if ok else 'FALHA', label,
                           '' if ok else '  <- %s' % detail))
    print('\nLADDER-SIGNAL %s -- arms=%d pass=%d fail=%d (rc=%d)'
          % ('GREEN' if not failed else 'VERMELHO', len(rows),
             len(rows) - len(failed), len(failed), 0 if not failed else 1))
    return 0 if not failed else 1


def neg_arm():
    """Copia do worker com a rotacao ESTATICA de volta: o oraculo TEM de ficar RED."""
    tmp = tempfile.mkdtemp(prefix='ladder-neg-')
    try:
        copy = os.path.join(tmp, 'sotto_worker.py')
        shutil.copy2(WORKER, copy)
        text = io.open(copy, encoding='utf-8').read()
        mutant = re.sub(r'nxt\s*=\s*signal_ranked_next\(\s*candidates\s*,\s*attempt_no\s*\+\s*1\s*\)',
                        'nxt = candidates[attempt_no + 1] if attempt_no + 1 < len(candidates) else None',
                        text, count=1)
        if mutant == text:
            print('NEG-ARM: nao consegui mutar o sitio da rotacao')
            return 1
        io.open(copy, 'w', encoding='utf-8', newline='').write(mutant)
        global rows
        rows = []
        rc = run(worker_path=copy)
        if rc != 0:
            print('\nNEG-ARM PASS -- RED as designed: a rotacao estatica derruba o oraculo')
            return 1
        print('\nNEG-ARM FALHOU: o oraculo ficou VERDE com a rotacao estatica')
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv):
    if '--neg-arm' in argv:
        return neg_arm()
    if not os.path.exists(WORKER):
        print('VERDICT: FAIL -- worker ausente: %s' % WORKER)
        return 1
    return run()


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
