"""FASE B -- processar as vozes DEPOIS, sobre o audio que a Fase A guardou.

O QUE FECHA ISTO
================
O dono (2026-10-18): *"precisamos detectar que sao multiplas vozes, pra decidir
isso pra processar depois quando e seguro e nao travar o pc do usuario."*

A Fase A (`worker/speaker_sidecar.py --watch-only`) detecta e -- com
`--watch-save` -- guarda o audio assinalado. Este e' o passo que consome esse
audio: roda a pipeline COMPLETA (segmentacao + embeddings + clustering) sobre um
ou mais clips ja gravados, fora do tempo real, e escreve um payload no mesmo
formato de `_main/diar-live.json`, para que `speaker_bridge` o leia sem mudanca.

O QUE ELE NAO FAZ
==================
- Nao abre NENHUM dispositivo de audio. Corrige um ficheiro, nunca um endpoint.
  Um "processar depois" que va buscar microfone nao e' depois, e' agora com outro
  nome.
- Nao decide QUANDO corre. A politica de "quando e' seguro" e' do dono; isto e' a
  capacidade, nao o agendador.
- Nao escreve em `_main/diar-live.json`. O ficheiro do caminho vivo e' de quem
  esta a correr em directo; overwrite-lo a partir de um clip de ontem trocaria a
  resposta de agora pela de antes, que e' o tipo de bug que so aparece quando
  ninguem esta a ver.

USO
===
    python _main/multivoice-offline.py <ficiro.wav | directorio> [--out X.json]

A GUARDA DE CARGA
=================
O dono, verbatim: *"processar depois quando e' seguro e nao travar o pc do
usuario."* A segunda metade da frase e' uma condicao, e ate agora nao tinha
instrumento: este ficheiro carregava os 135 MB de modelos sem perguntar se havia
folga. `_main/_cpu-load.py` responde a isso, e este script e' o **primeiro
consumidor** dele. Sem este consumidor seria um sinal sem consumidor -- que e'
exactamente o buraco que a Fase A teve com o audio (§7.4).

    rc=3  nenhum clip encontrado
    rc=4  a maquina nao tem nucleo livre: NAO CORREU

O que a guarda NAO faz: nao decide a politica do dono. Nao diz "quando correr" --
diz "agora nao", e so quando nao ha um nucleo sequer livre. Com um nucleo livre
corre, porque um nucleo livre e' o que torna isto seguro. `--ignore-load` existe
para quem sabe o que esta a fazer e quer o resultado na mesma.

A guarda corre ANTES de `_load_sherpa_diarizer`, que e' o ponto: recusar depois de
pagar 135 MB e' pagar para descobrir que nao se pode.
"""
import argparse
import importlib.util
import json
import os
import sys
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "worker"))

import numpy as np                     # noqa: E402

import speaker_sidecar as S            # noqa: E402

FS = 16000

#: Nenhum nucleo livre = a fase B deixa de ser "depois" e passa a competir com o
#: que o dono esta a fazer. Um nucleo livre e' o PISO, nao o ideal.
RC_SEM_FOLGA = 4


def load_cpu_module():
    """`_cpu-load.py` tem um hifen no nome e nao se importa. Carrega-o por caminho.

    Se nao der para o carregar devolve `None`, e o chamador tem de tratar isso
    como uma terceira coisa: uma guarda que nao conseguiu LER a carga nao pode
    virar "nao ha folga" nem "ha folga". Os dois seriam mentira.
    """
    path = os.path.join(HERE, "_cpu-load.py")
    try:
        spec = importlib.util.spec_from_file_location("_sotto_cpu_load", path)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:                                        # noqa: BLE001
        return None


def loss_report(watch_path):
    """O que a fila FIFO perdeu de audio, lido do payload do sidecar.

    ESTE E' O ULTIMO ELO DA CORDA. O sidecar conta o que apaga e publica-o, o
    watcher diz-o ao dono -- mas quem corre a separacao depois da callRecebia
    um resultado sem qualquer aviso. Separar 3 clips e dizer "pronto" quando
    foram 7 e' a forma mais cara de estar errado: o dono acredita que leu a
    call toda.

    O payload e' reescrito a cada janela, por isso so o `clips_evicted_total`
    -- o acumulado do processo -- e' util aqui. Devolve `None` quando nao ha
    payload nenhum: um `--audio` de um ficheiro que nao veio do sidecar e' um
    caso legitimo e nao uma anomalia.
    """
    if not watch_path:
        return None
    try:
        with open(watch_path, "r", encoding="utf-8") as fh:
            pay = json.load(fh)
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(pay, dict):
        return None
    if "clips_evicted_total" not in pay:
        return None
    try:
        lost = int(pay["clips_evicted_total"])
    except (TypeError, ValueError):
        # MEDIDO: com `clips_evicted: 'x'` esta funcao devolvia `lost: 0` --
        # isto e', liso no campo, dito ao dono como "a fila NAO perdeu audio".
        # Lixo no campo nunca pode virar "zero perdido": e' a mentira na
        # direccao perigosa. Distingue-se o registo ausente (None) do registo
        # ilegivel (lost=None com razao), e quem imprime diz as duas coisas
        # diferentes.
        return {"lost": None, "unreadable": pay.get("clips_evicted_total"),
                "spans": pay.get("n_spans"), "multivoice_s": pay.get("multivoice_s"),
                "written_at": pay.get("written_at")}
    return {"lost": lost,
            "spans": pay.get("n_spans"),
            "multivoice_s": pay.get("multivoice_s"),
            "written_at": pay.get("written_at")}


def read_wav(path):
    with wave.open(path, "rb") as w:
        if w.getsampwidth() != 2:
            raise SystemExit("%s: so leio WAV de 16 bit (tem %d)"
                             % (path, w.getsampwidth() * 8))
        if w.getframerate() != FS:
            raise SystemExit("%s: %d Hz, este leitor quer %d Hz"
                             % (path, w.getframerate(), FS))
        raw = w.readframes(w.getnframes())
    return (np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0)


def collect(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            for name in sorted(os.listdir(p)):
                if name.startswith("mv-") and name.endswith(".wav"):
                    out.append(os.path.join(p, name))
        elif p.lower().endswith(".wav"):
            # MEDIDO por um check do portao da guarda: um `.wav` que nao existe
            # passava aqui dentro, e a fase B so descobria isso DEPOIS de pagar
            # os 135 MB dos dois modelos -- rebentando com um traceback cru em
            # vez de dizer "esse ficheiro nao esta la". Descobrir um caminho
            # errado e' de graca; descobrir depois de carregar 135 MB nao e'.
            if os.path.exists(p):
                out.append(p)
            else:
                print("offline: ignorado (nao existe) %s" % p)
        else:
            print("offline: ignorado (nao e' wav nem directorio) %s" % p)
    return out


def diarize_one(sess, audio, threshold, num_speakers):
    """A pipeline completa sobre UM clip. Devolve segmentos absolutos locais."""
    res = sess.process(audio).sort_by_start_time()
    return [{"start": round(float(s.start), 3),
             "end": round(float(s.end), 3),
             "speaker": int(s.speaker)}
            for s in res]


def guard(cpu, ignore_load):
    """A guarda de carga, isolada para poder ser testada sem 135 MB.

    Devolve `(rc, load_why)`. `rc` e' 0 para passar, `RC_SEM_FOLGA` para
    recusar. `load_why` e' a frase que vai para o ecra E para dentro do payload,
    porque um RTF sem a carga ao lado e' um numero sem contexto.

    `cpu` e' o modulo ou `None`. `None` tem TRES meanings diferentes e esta
    funcao tem de os distinguir: `--ignore-load` (desligado a mao), modulo que
    nao carregou (nao se sabe), e recusa (sabe-se e nao ha folga). Recusar por nao
    saber seria mentir sobre a maquina; aceitar sem dizer seria o mesmo pelo
    outro lado.
    """
    if ignore_load:
        print("offline: --ignore-load -- a guarda de carga foi desligada A TE O "
              "QUE. O RTF que se segue nao diz nada sobre a maquina.")
        return 0, "guarda DESLIGADA a mao (--ignore-load)"
    if cpu is None:
        print("offline: AVISO -- nao consegui ler `_cpu-load.py`, portanto nao "
              "sei se a maquina tem folga. Vou correr na mesma: recusar por nao "
              "saber seria pior do que dizer que nao sei.")
        return 0, "carga NAO LIDA (modulo `_cpu-load.py` nao carregou)"
    ok, why = cpu.load_ok()
    print("offline: [carga] %s" % why)
    if not ok:
        print("offline: RECUSA (rc=%d) -- a fase B carrega dois modelos e "
              "precisa de um nucleo para ela. Nao abri dispositivo de audio nem "
              "escrevi nada." % RC_SEM_FOLGA)
        print("          Repete quando houver folga, ou --ignore-load se "
              "saberes o que estas a fazer.")
        return RC_SEM_FOLGA, why
    return 0, why


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="+",
                    help="WAV files, or a directory of mv-*.wav clips")
    ap.add_argument("--threshold", type=float, default=0.9,
                    help="0,9 MEDIDO: 0,50 da 3 vozes, 0,70 da 2, 0,90 da 2. "
                         "A omissao do sherpa e' 0,5 e da o pior resultado")
    ap.add_argument("--num-speakers", type=int, default=-1)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--out", default="",
                    help="payload JSON; omitted = one line per clip on stdout")
    ap.add_argument("--ignore-load", action="store_true",
                    help="correr mesmo sem nucleo livre (sabendo o que se faz)")
    ap.add_argument("--watch-payload", default=r"H:\sotto\_main\diar-watch.json",
                    help="payload do sidecar --watch-only; e' lido para DIZER se "
                         "a fila perdeu audio. Vazio = nao perguntar")
    args = ap.parse_args(argv)

    clips = collect(args.paths)
    if not clips:
        print("offline: nenhum clip encontrado em %s" % ", ".join(args.paths))
        return 3

    # O rc continua 0 quando correu: o trabalho pedido -- separar as vozes
    # destes clips -- foi feito. A incompletude do CONJUNTO de entrada e'
    # outra coisa, e por isso e' um campo e uma faixa no ecra, nao um erro: um
    # rc != 0 diria "isto falhou", e nao e' verdade.
    incomplete = False

    # ---- A GUARDA, ANTES DE PAGAR OS 135 MB ------------------------------
    rc, load_why = guard(None if args.ignore_load else load_cpu_module(),
                         args.ignore_load)
    if rc:
        return rc

    print("offline: %d clip(s), so segmentacao NAO -- esta e' a fase cara" % len(clips))
    print("        threshold %.2f  |  janela segura ate %.0f s "
          "(acima disso a pipeline fica mais lenta que o tempo real -- "
          "medido, `_main/_phase-b-cliff-probe.py`)" % (args.threshold, S.SAFE_WINDOW_S))
    sess = S._load_sherpa_diarizer(S.DEFAULT_SEG_MODEL, S.DEFAULT_EMB_MODEL,
                                  threads=args.threads, threshold=args.threshold)

    results = []
    total_audio_s = total_wall_s = 0.0
    for path in clips:
        try:
            audio = read_wav(path)
        except (SystemExit, OSError) as exc:
            # Um clip ilegivel e' um clip que se salta, com a razao dita. Um
            # traceback aqui significa que o resto da fila nao corre -- e a
            # fase B existe para processar o resto.
            print("offline: %s" % exc)
            continue
        dur = len(audio) / float(FS)
        t0 = time.perf_counter()
        try:
            segs = diarize_one(sess, audio, args.threshold, args.num_speakers)
        except Exception as exc:                                    # noqa: BLE001
            print("offline: %s FALHOU: %s: %s"
                  % (os.path.basename(path), type(exc).__name__, exc))
            continue
        wall = time.perf_counter() - t0
        total_audio_s += dur
        total_wall_s += wall

        if dur > S.SAFE_WINDOW_S:
            print("offline: AVISO -- clip de %.1f s acima de %.0f s: a pipeline "
                  "completa fica mais lenta que o tempo real (medido: RTF 0,67 "
                  "aos 11 s, RTF 1,69 aos 14 s). Se nao precisares do audio "
                  "inteiro, corta-o." % (dur, S.SAFE_WINDOW_S))

        # O timestamp do nome do clip e' o instante ABSOLUTO do inicio. E' ele
        # que devolve o troco ao relogio da chamada, em vez de o deixar num
        # "0.0 s" que so quer dizer "desde que este ficheiro comecou".
        base = 0.0
        name = os.path.basename(path)
        if name.startswith("mv-") and name[3:-4].isdigit():
            base = int(name[3:-4]) / 1000.0

        voices = sorted({s["speaker"] for s in segs})
        print("\n%s  %.1f s" % (name, dur))
        print("  wall %.2f s  (RTF %.3f -- a fase B e' a cara, por desenho)"
              % (wall, wall / dur if dur else 0))
        print("  vozes %d %s | %d segmentos"
              % (len(voices), voices, len(segs)))
        for s in segs[:8]:
            print("     %8.2f - %8.2f  voz %d"
                  % (base + s["start"], base + s["end"], s["speaker"]))
        if len(segs) > 8:
            print("     ... mais %d" % (len(segs) - 8))

        results.append({
            "file": path,
            "clip_base_abs": base,
            "duration_s": round(dur, 3),
            "wall_s": round(wall, 3),
            "rtf": round(wall / dur, 4) if dur else None,
            "load_at_measure": load_why,
            "n_speakers": len(voices),
            "speakers": voices,
            "segments": segs,
            "written_at": time.time(),
        })

    if total_audio_s:
        print("\nTOTAL: %.1f s de audio em %.1f s de parede (RTF %.3f)"
              % (total_audio_s, total_wall_s, total_wall_s / total_audio_s))
        # O RTF sem a carga ao lado e' um numero que se le como caminho quando
        # nao e' caminho. A carga tambem vai para dentro do payload gravado.
        print("  medido sob: %s" % load_why)

    # ---- O RESULTADO ESTA COMPLETO? ---------------------------------------
    print("\n" + "-" * 78)
    loss = loss_report(args.watch_payload)
    if loss is None:
        print("COMPLETUDE: nao ha payload do sidecar para comparar -- este "
              "directorio pode ser qualquer coisa.")
        print("            (esperado quando o audio nao veio de --watch-save)")
    elif loss.get("lost") is None:
        print("COMPLETUDE: NAO SEI -- o payload tem `clips_evicted_total` mas "
              "nao se consegue ler (%r)." % loss.get("unreadable"))
        print("            Nao vou dizer que nada se perdeu: nao ler um numero "
              "nao e' o mesmo que ele ser zero.")
    elif loss["lost"] <= 0:
        print("COMPLETUDE: a fila NAO perdeu audio -- o directorio tem tudo o "
              "que o sidecar assinalou.")
    else:
        print("COMPLETUDE: INCOMPLETO -- a fila FIFO perdeu %d clip(s) de audio "
              "que o sidecar JA TINHA ASSINALADO." % loss["lost"])
        print("            Separar o que resta e' correcto; o que falta Nao "
              "reaparece.")
        print("            Para nao perder: --watch-save-max-mb maior, ou "
              "correr a Fase B mais assiduamente.")
        print("            Payload: %s" % args.watch_payload)
        incomplete = True
    print("-" * 78)

    if args.out:
        # `segments` e' a chave que `speaker_bridge.payload_if_fresh` exige. Este
        # payload tem a MESMA forma do do caminho vivo, para que um consumidor
        # nao tenha de saber de onde veio.
        for r in results:
            r["n_segments"] = len(r["segments"])
        payload = {"state": "offline", "written_at": time.time(),
                   "n_segments": sum(r["n_segments"] for r in results),
                   "n_speakers": max([r["n_speakers"] for r in results] or [0]),
                   "clips": results,
                   # Quem consumir este payload tem de saber se o conjunto de
                   # entrada era o completo. Um payload que nao o diz deixa quem
                   # le exactamente onde o dono estava: a acreditar que leu a
                   # call toda.
                   "incomplete": incomplete,
                   "clips_lost": (loss or {}).get("lost") if loss else None,
                   "watch_payload": args.watch_payload or ""}
        S.write_payload_atomic(args.out, payload)
        print("payload escrito em %s" % args.out)
    else:
        for r in results:
            print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())