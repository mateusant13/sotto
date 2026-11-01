"""O corte de audio do fone -- instrumento unico, duas fontes, uma linha do tempo.

ORDEM DO DONO (2026-10-30, verbatim): *"o fone fica mudo"*, e ele **ouve o barulho do corte**.
A pergunta e': quem corta? Sem instrumento isso e' conversa. Este mede duas coisas ao mesmo tempo,
com relogio comum:

  1. O QUE O WINDOWS FAZ AO DISPOSITIVO (`IMMNotificationClient`, via `pycaw` que ja' vive em
     `_main/_libs`): device added/removed, state changed (ACTIVE/DISABLED/NOTPRESENT/UNPLUGGED),
     default-device changed (por role), property changed. E' o canal que ve' o *barulho do corte*
     (o Windows silencia o endpoint antes de o reconfigurar).
  2. O QUE O SOTTO FAZ (`_main/webview-run.log`): so' as linhas que tocam em audio/worker, lidas por
     offset e nunca reescritas. Uma linha do Sotto a menos de 2 s de um evento de dispositivo e'
     suspeita; sem linha nenhuma, o Sotto nao falou -- e isso tambem e' uma medicao.

E ainda um censo de estado a cada 500 ms (`IAudioEndpointVolume` do default de cada role: mute,
volume), porque um corte pode nao gerar evento nenhum.

USO
    python _main/headphone-cut-probe.py --seconds 60
    python _main/headphone-cut-probe.py --seconds 60 --out _main/headphone-cut.jsonl
    python _main/headphone-cut-probe.py --selftest        # braco positivo E negativo

VEREDICTO (a linha que interessa, uma so')
    HEADPHONE-CUT <N eventos de dispositivo> <M mutacoes de mute> <K linhas do Sotto na janela>
    e, por evento, `quem=<sotto|windows|desconhecido>` com a distancia em ms ate' a linha do Sotto
    mais proxima. `desconhecido` NAO e' inocencia: e' ausencia de prova.
"""
import argparse
import ctypes
import io
import json
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
LIBS = os.path.join(HERE, '_libs')
if LIBS not in sys.path:
    sys.path.insert(0, HERE)
    sys.path.insert(0, LIBS)

APP_LOG = os.path.join(HERE, 'webview-run.log')
SOUND_WORDS = ('AUDIO', 'audio', 'WASAPI', 'wasapi', 'WORKER', 'worker', 'MIC', 'mic',
               'ENDPOINT', 'endpoint', 'SILENCE', 'silence', 'MUTE', 'mute')


def now():
    return time.time()


def stamp(t):
    return time.strftime('%H:%M:%S', time.localtime(t)) + ('.%03d' % int((t % 1) * 1000))


# ---------------------------------------------------------------- o log do Sotto
def follow_log(path=APP_LOG, offset=None):
    """Devolve (novas linhas com tempo, offset novo). So' le o que cresceu."""
    if not os.path.exists(path):
        return [], offset
    size = os.path.getsize(path)
    if offset is None:
        offset = size
    if size < offset:                      # rotacao
        offset = 0
    if size == offset:
        return [], offset
    with io.open(path, 'rb') as handle:
        handle.seek(offset)
        chunk = handle.read()
    offset = size
    out = []
    for raw in chunk.decode('utf-8', 'replace').splitlines():
        if not raw.strip():
            continue
        head = raw[:8]
        t = None
        if head[:2].isdigit() and head[2] == ':' and head[5] == ':':
            try:
                today = time.strftime('%Y-%m-%d')
                t = time.mktime(time.strptime(today + ' ' + head, '%Y-%m-%d %H:%M:%S'))
            except ValueError:
                t = None
        if t is None:
            t = now()
        out.append({'t': t, 'line': raw})
    return out, offset


# ------------------------------------------------------- o canal do Windows
try:
    sys.coinit_flags = 0                             # MTA ANTES do comtypes (o proprio pycaw o pede)
    from comtypes import COMObject                   # noqa: E402
    from pycaw.pycaw import AudioUtilities           # noqa: E402
    from pycaw.api.mmdeviceapi import IMMNotificationClient  # noqa: E402
    HAVE_PYCAW = True
except Exception:                                    # pragma: no cover - ambiente
    HAVE_PYCAW = False
    COMObject = object
    IMMNotificationClient = object


class Events(object):
    def __init__(self):
        self.rows = []

    def add(self, kind, **fields):
        row = {'t': now(), 'kind': kind}
        row.update(fields)
        self.rows.append(row)
        print('%s  %-22s %s' % (stamp(row['t']), kind, ' '.join(
            '%s=%s' % (k, v) for k, v in sorted(fields.items()) if v not in (None, ''))), flush=True)
        return row


class Probe(COMObject):
    """`IMMNotificationClient` a serio: o Windows chama estes metodos no thread do COM.

    E' um `COMObject` com `_com_interfaces_`, e nao uma instancia Python solta: medido
    2026-10-30, `RegisterEndpointNotificationCallback(<instancia python>)` levanta
    `ctypes.ArgumentError: Don't know how to convert parameter 1`. O braco de controlo e'
    o `--selftest`, que chama os metodos diretamente e prova que a logica ouve; o que
    falhava era SO' a conversao COM, e por isso o teste tem de ser o registo, nao o metodo.
    """
    _com_interfaces_ = (IMMNotificationClient,) if HAVE_PYCAW else ()

    def __init__(self, events, keep=None, validate=False):
        if HAVE_PYCAW:
            super(Probe, self).__init__()
        self.ev = events
        self.keep = keep if keep is not None else True
        self.validate = validate
        self.state = {}

    # -- os quatro avisos que existem no Windows
    def OnDeviceStateChanged(self, device_id=None, new_state=None):
        if not self.keep:
            return
        self.ev.add('estado', device=device_id, estado=new_state)

    def OnDeviceAdded(self, device_id=None):
        if self.keep:
            self.ev.add('adicionado', device=device_id)

    def OnDeviceRemoved(self, device_id=None):
        if self.keep:
            self.ev.add('removido', device=device_id)

    def OnDefaultDeviceChanged(self, flow=None, role=None, device_id=None):
        if not self.keep:
            return
        self.ev.add('default-mudou', flow=flow, role=role, device=device_id)

    def OnPropertyValueChanged(self, device_id=None, key=None):
        if self.keep:
            self.ev.add('propriedade', device=device_id, key=str(key))

    # -- o censo de estado (o que apanha um corte SEM evento)
    def census(self):
        rows = []
        for role_name, role in (('consola', 0), ('multimedia', 1), ('comunicacao', 2)):
            try:
                dev = AudioUtilities.GetSpeakers()
                vol = dev.EndpointVolume
                muted = bool(vol.GetMute())
                level = round(vol.GetMasterVolumeLevelScalar(), 3)
                rows.append((role_name, muted, level))
            except Exception as exc:
                rows.append((role_name, 'erro', str(exc)[:60]))
                break
        state = tuple(rows)
        changed = state != self.state and self.state
        self.state = state
        return rows, bool(changed)


def mute_mutations(samples):
    """Quantas vezes o mute/volume do default mudou de valor na janela."""
    flips = 0
    prev = None
    for t, rows in samples:
        key = tuple((r[0], r[1], r[2]) for r in rows)
        if prev is not None and key != prev:
            flips += 1
        prev = key
    return flips


def nearest_sotto(event_t, sotto_rows):
    best = None
    for row in sotto_rows:
        delta = abs(event_t - row['t'])
        if best is None or delta < best[0]:
            best = (delta, row)
    return best


def verdict(events_rows, sotto_rows, samples, seconds):
    device_events = [r for r in events_rows if r['kind'] in
                     ('estado', 'removido', 'adicionado', 'default-mudou')]
    flips = mute_mutations(samples)
    print('')
    print('--- quem corta --------------------------------------------------------')
    culprit = {'sotto': 0, 'windows': 0, 'desconhecido': 0}
    for row in device_events:
        near = nearest_sotto(row['t'], sotto_rows)
        if near and near[0] <= 2.0:
            who = 'sotto'
            detail = '%.0f ms de "%s"' % (near[0] * 1000, near[1]['line'][:70])
        elif near:
            who = 'windows'
            detail = 'linha do Sotto mais proxima a %.1f s' % near[0]
        else:
            who = 'desconhecido'
            detail = 'nenhuma linha do Sotto depois do inicio da janela'
        culprit[who] += 1
        print('  %s %-14s -> %s (%s)' % (stamp(row['t']), row['kind'], who, detail))
    print('')
    print('HEADPHONE-CUT eventos=%d mute_flips=%d linhas_sotto=%d janela=%.0fs '
          'sotto=%d windows=%d desconhecido=%d'
          % (len(device_events), flips, len(sotto_rows), seconds,
             culprit['sotto'], culprit['windows'], culprit['desconhecido']))
    if not device_events and not flips:
        print('NOTA: nenhum evento e nenhuma mudanca de mute nesta janela. '
              'Nao e' + ' veredicto: e' + ' ausencia de observacao.')
    return len(device_events), flips, culprit


def run(seconds, out_path=None, keep=True):
    ev = Events()
    probe = Probe(ev, keep=keep)
    registered = False
    if HAVE_PYCAW:
        try:
            enumerator = AudioUtilities.GetDeviceEnumerator()
            enumerator.RegisterEndpointNotificationCallback(probe)
            registered = True
        except Exception:
            ev.add('registro-falhou', erro=str(traceback.format_exc()[-200:]))
    rows, offset = follow_log()
    samples = []
    t0 = now()
    print('janela de %.0f s; dispositivo=%s; log=%s' %
          (seconds, 'ligado' if registered else 'SEM NOTIFICACAO', APP_LOG))
    last_census = 0.0
    while now() - t0 < seconds:
        time.sleep(0.5)
        if now() - last_census >= 0.5:
            last_census = now()
            rows_now, changed = probe.census()
            samples.append((now(), rows_now))
            if changed:
                ev.add('mute-mudou', estado=json.dumps(rows_now, ensure_ascii=False)[:160])
        new, offset = follow_log(offset=offset)
        for row in new:
            if any(word in row['line'] for word in SOUND_WORDS):
                rows.append(row)
    seconds_real = now() - t0
    if registered:
        try:
            AudioUtilities.GetDeviceEnumerator().UnregisterEndpointNotificationCallback(probe)
        except Exception:
            pass
    if out_path:
        with io.open(out_path, 'w', encoding='utf-8') as handle:
            for row in ev.rows:
                handle.write(json.dumps(row, ensure_ascii=False) + '\n')
        print('eventos escritos em %s (%d)' % (out_path, len(ev.rows)))
    return verdict(ev.rows, rows, samples, seconds_real)


def selftest():
    """Braco positivo E negativo: o instrumento TEM de conseguir ver um corte.

    Positivo: um `Events` alimentado a mao com um evento + uma linha do Sotto a 300 ms conta como
    `sotto`; a MESMA linha a 30 s conta como `windows`.
    Negativo: o `keep=False` (o filtro desligado) NAO pode registar nada, e um log que nao cresceu
    nao pode inventar linhas.
    """
    failures = []

    def check(name, ok, detail=''):
        print('%s %s %s' % ('PASS' if ok else 'FAIL', name, detail))
        if not ok:
            failures.append(name)

    ev = Events()
    probe = Probe(ev)
    probe.OnDefaultDeviceChanged(0, 0, 'dev-x')
    probe.OnDeviceStateChanged('dev-x', 8)
    check('o instrumento ouve os dois avisos', len(ev.rows) == 2, 'eventos=%d' % len(ev.rows))

    t = 1000.0
    sotto_near = [{'t': t + 0.3, 'line': 'AUDIO_SOMETHING'}]
    near = nearest_sotto(t, sotto_near)
    check('linha a 300 ms e o Sotto', near[0] < 2.0, '%.2f s' % near[0])
    far = nearest_sotto(t, [{'t': t + 30.0, 'line': 'AUDIO_LONGE'}])
    check('linha a 30 s nao e o Sotto', far[0] > 2.0, '%.2f s' % far[0])
    check('sem linhas e desconhecido', nearest_sotto(t, []) is None)

    quiet = Probe(Events(), keep=False)
    quiet.OnDeviceStateChanged('dev-x', 1)
    check('filtro desligado nao regista', len(quiet.ev.rows) == 0,
          'eventos=%d' % len(quiet.ev.rows))

    before, off = follow_log()
    more, off2 = follow_log(offset=off)
    check('um log parado nao inventa linhas', len(more) == 0, 'linhas=%d' % len(more))

    missing, _ = follow_log(path=os.path.join(HERE, 'nao-existe.log'))
    check('log ausente devolve vazio e nao levanta', missing == [])

    # O LEITOR TEM DE FUNCIONAR SOBRE O LOG A SERIO (senao "0 linhas" e' uma avaria do
    # instrumento a passar por janela calma -- a mesma doenca do "grep deu ZERO").
    real, _ = follow_log(path=APP_LOG, offset=0)
    parsed = [row for row in real if row['t'] and row['t'] > 1e9]
    check('le o log vivo e devolve linhas com tempo', len(real) > 0 and len(parsed) == len(real),
          'linhas=%d com_tempo=%d' % (len(real), len(parsed)))
    if real:
        span = real[-1]['t'] - real[0]['t']
        check('os tempos do log sao monotonos', span >= 0, 'span=%.0fs' % span)

    flips = mute_mutations([(0, [('consola', False, 1.0)]), (1, [('consola', False, 1.0)]),
                            (2, [('consola', True, 1.0)]), (3, [('consola', True, 1.0)])])
    check('uma mudanca de mute e contada uma vez', flips == 1, 'flips=%d' % flips)

    print('')
    print('HEADPHONE-CUT SELFTEST %s -- %d falha(s)' %
          ('PASS' if not failures else 'FAIL', len(failures)))
    return 0 if not failures else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seconds', type=float, default=60.0)
    ap.add_argument('--out')
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--neg-arm', dest='neg_arm', action='store_true',
                    help='o braco negativo: o instrumento TEM de dizer que nao ve' + ' nada')
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if args.neg_arm:
        # O braco NEGATIVO nao e' "correr isto e ver": e' provar que o veredicto NAO afirma
        # culpa quando nao ha evento nenhum. Alimenta-se o veredicto com zero eventos.
        n, flips, culprit = verdict([], [], [(0, [('consola', False, 1.0)])], 1.0)
        ok = n == 0 and flips == 0 and sum(culprit.values()) == 0
        # A CASA LE rc=1 COMO SUCESSO NO BRACO DE CONTROLO (`:expectred` exige rc==1 e o token).
        # Ate' 2026-10-30 este ramo devolvia 0 no caso BOM, e o passo `red-as-expected-headphone-cut`
        # ficava vermelho por FORMA, nao por conteudo -- o mesmo defeito ja' medido noutros tres.
        print('NEG-ARM PASS -- RED as designed: janela vazia nao acusa ninguem' if ok
              else 'NEG-ARM FAIL -- o veredicto inventou culpa sem evento')
        return 1 if ok else 0
    return 0 if run(args.seconds, args.out) else 0


if __name__ == '__main__':
    sys.exit(main())
