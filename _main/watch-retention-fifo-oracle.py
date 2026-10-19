"""PORTAO DA RETENCAO -- quando o limite de disco chega.

O BURACO, E A FAMILIA A QUE ELE PERTENCE
========================================
O dono, 2026-10-18: *"precisamos detectar que sao multiplas vozes, pra decidir
isso pra processar depois quando e' seguro."* Para "processar depois" ser
possivel, o audio assinalado tem de SOBREVIVER ate la -- e esse foi o primeiro
buraco: a deteccao vivia, o audio nao.

Este e' o **segundo** buraco da mesma familia, e so aparece quando a call e'
longa o suficiente para encher a fila. `--watch-save-max-mb 256` e' FIFO: quando
o limite chega, o clip mais ANTIGO e' apagado para dar espaco ao novo.

O QUE SE MEDIA ANTES DE MEXER (e que e' o que este porta fixa)
==============================================================
`save_multivoice_clips` chamava `_evict_oldest(...)` e **deitava fora o valor
devolvido**. `watch_tick` publicava `n_clips` = quantos foram ESCRITOS e nunca
quantos foram PERDIDOS.

Duas consequencias, ambas medidas neste porta, nenhuma hipotetica:

  1. **O audio do dono desaparece em silencio.** Nenhum log, nenhum campo no
     payload, nada. O dono correria a Fase B sobre o directorio e receberia um
     resultado sem 30 minutos de sobreposicoes, sem nenhuma pista de que
     faltaram.

  2. **Pior: um clip pode ser contado como guardado no mesmo instante em que e'
     apagado.** A eviccao corre DEPOIS da escrita, dentro da mesma chamada.
     MEDIDO: o estado dizia `n_clips=2` com **zero** clips no disco.

Isto e' a doutrina do projecto a ser violada num sitio novo: *um numero que se le
como caminho quando nao e' caminho e' pior do que nao imprimir.*

O `--neg-arm`
=============
Poe `_evict_oldest` a devolver vazio sem apagar nada -- o limite deixa de existir
-- e o porta tem de REPROVAR. Um limite que nao sabe dizer NAO nao e' um limite.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "worker"))

import numpy as np                     # noqa: E402

import speaker_sidecar as S            # noqa: E402

FS = 16000

#: Um clip de 60 frames = 60 * 270 amostras = 16200 = 31,6 KB em 16 kHz/16 bit.
#: Todos os numeros de tampa abaixo sao escolhidos a partir deste, e nao a olho.
CLIP_BYTES = 60 * 270 * 2

FAILURES = []
CHECKS = [0]


def check(ok, label, detail=""):
    CHECKS[0] += 1
    if not ok:
        FAILURES.append(label)
    detail = detail if isinstance(detail, str) else repr(detail)
    print("   [%s] %s%s" % ("ok" if ok else "XX", label,
                            ("  -- " + detail) if detail else ""))
    return ok


def fake_sess(classes):
    """Um `sess` que devolve uma classe powerset escolhida frame a frame."""
    arr = np.zeros((1, len(classes), 7), dtype=np.float32)
    for i, c in enumerate(classes):
        arr[0, i, c] = 1.0

    class Fake(object):
        def run(self, _out, _feeds):
            return [arr]
    return Fake()


def tone(n, seed=0):
    """Audio que passa a janela de energia (a porta tem de ver fala aqui)."""
    rng = np.random.RandomState(seed)
    base = np.sin(np.linspace(0, 40.0, n)) * 0.35
    noise = rng.randn(n) * 0.02
    return list(np.clip(base + noise, -1.0, 1.0))


def dir_bytes(d):
    total = 0
    try:
        for f in os.listdir(d):
            try:
                total += os.path.getsize(os.path.join(d, f))
            except OSError:
                pass
    except OSError:
        pass
    return total


def clips_on_disk(d):
    try:
        return sorted(f for f in os.listdir(d) if f.startswith("mv-"))
    except OSError:
        return []


def unpack(res):
    """`(sobreviventes, apagados)` se o contrato ja for esse; senao o que ha."""
    if isinstance(res, tuple) and len(res) == 2:
        return list(res[0]), list(res[1])
    return list(res), None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--neg-arm", action="store_true",
                    help="_evict_oldest nunca apaga: o limite desaparece e o "
                         "portao tem de reprovar")
    args = ap.parse_args(argv)
    return _neg_arm() if args.neg_arm else _run()


# ===========================================================================
# O BRACO NEGATIVO
# ===========================================================================


def _neg_arm():
    print("=" * 78)
    print("PORTAO DA RETENCAO   BRAACO NEGATIVO: o limite deixa de existir")
    print("=" * 78)

    src_path = os.path.join(ROOT, "worker", "speaker_sidecar.py")
    src = open(src_path, encoding="utf-8").read()
    # A ancora e' a assinatura COMPLETA. Quando a correccao a mudou de `-> int`
    # para `-> list`, este neg arm deixou de encontrar a ancora e disse "a
    # ancora mudou" em vez de medir um mutante inventado -- que e' o
    # comportamento certo. Um neg arm que aplica a mutacao em silencio depois
    # de a ancora mudar mede a coisa errada e da um verde que nao quer dizer nada.
    anchor = "def _evict_oldest(out_dir: str, max_mb: float) -> list:"
    if anchor not in src:
        print("   [XX] A ANCRA DO MUTANTE MUDOU -- o neg arm mede o codigo "
              "anterior, e o codigo mudou. Actualiza este porta.")
        print("       (procurado: %s)" % anchor)
        return 1
    mutated = src.replace(
        anchor,
        "def _evict_oldest(out_dir, max_mb):\n"
        "    return []  # MUTANTE: nunca apaga\n"
        "def _evict_oldest_unused(out_dir: str, max_mb: float) -> list:",
        1)
    mod = types.ModuleType("speaker_sidecar_mutant")
    mod.__file__ = src_path
    exec(compile(mutated, src_path, "exec"), mod.__dict__)

    tmp = tempfile.mkdtemp(prefix="fifo-neg-", dir="I:\\cc-tmp")
    try:
        d = os.path.join(tmp, "clips")
        samples = tone(int(4 * FS), 5)
        for k in range(6):
            mod.save_multivoice_clips(
                samples, 1_700_000_000.0 + k * 30.0, [(0, 60)], d, FS, 0.0,
                0.10)
        on_disk = clips_on_disk(d)
        total_mb = dir_bytes(d) / 1048576.0
        check(total_mb > 0.10 * 1.02,
              "BRACO NEGATIVO: sem o limite o directorio cresce acima da tampa, "
              "e o porta tem de reprovar isto",
              "%.3f MB com tampa 0,100 MB -- %d clips" % (total_mb, len(on_disk)))
        check(len(on_disk) == 6,
              "e nada foi apagado: o FIFO deixou de ser FIFO",
              "%d de 6 clips" % len(on_disk))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("-" * 78)
    # Neste braço os checks escrevem o que o MUTANTE faz, nao o que o produto
    # certo faz: passarem e' a prova de que o mutante se queimou. inverted would
    # be reading an empty FAILURES as "escapou".
    if FAILURES:
        print("VERDICT: FAIL  (%d/%d: %s)  -- o mutante ESCAPOU ao porta: "
              "com a tampa neutralizada, nada o distingue do produto certo."
              % (len(FAILURES), CHECKS[0], "; ".join(FAILURES)))
        return 1
    print("VERDICT: PASS  (%d/%d)  -- este era o BRACO NEGATIVO: PASS significa "
          "que a tampa esta a FAZER ALGUMA COISA." % (CHECKS[0], CHECKS[0]))
    return 0


# ===========================================================================


def _run():
    print("=" * 78)
    print("PORTAO DA RETENCAO -- a fila FIFO do audio assinalado")
    print("=" * 78)
    print("  um clip de 60 frames ocupa %.1f KB; as tampas sao escolhidas a "
          "partir dai" % (CLIP_BYTES / 1024.0))

    # ---- 1. A TAMPA E' CUMPRIDA -------------------------------------------
    print("\n1. A TAMPA")
    tmp = tempfile.mkdtemp(prefix="fifo-", dir="I:\\cc-tmp")
    try:
        d = os.path.join(tmp, "clips")
        cap_mb = 3 * CLIP_BYTES / 1048576.0 * 1.05      # ~3 clips
        S.save_multivoice_clips(tone(int(4 * FS), 3), 1_700_000_000.0,
                                [(0, 60), (180, 240), (360, 420)],
                                d, FS, 0.0, cap_mb)
        total_mb = dir_bytes(d) / 1048576.0
        on1 = clips_on_disk(d)
        check(total_mb <= cap_mb * 1.02,
              "o directorio fica dentro da tampa",
              "%.3f MB com tampa %.3f MB" % (total_mb, cap_mb))
        check(len(on1) >= 2,
              "e a tampa foi feita para deixar sobreviver mais de um clip -- "
              "com um so, as provas da ordem nao dizem nada",
              "%d clips" % len(on1))

        # ---- 2. FIFO: O MAIS ANTIGO SAI PRIMEIRO ---------------------------
        print("\n2. A ORDEM")
        tmp2 = tempfile.mkdtemp(prefix="fifo2-", dir="I:\\cc-tmp")
        try:
            d2 = os.path.join(tmp2, "clips")
            names_written = []
            for k in range(8):
                stamp = 1_700_000_000.0 + k * 30.0
                names_written.append("mv-%d.wav" % int(round(stamp * 1000.0)))
                S.save_multivoice_clips(tone(int(4 * FS), k), stamp,
                                        [(0, 60)], d2, FS, 0.0, cap_mb)
            on2 = clips_on_disk(d2)
            check(len(on2) >= 2,
                  "sobrevive mais de um clip (a prova precisa de substantia)",
                  "%d de 8" % len(on2))
            check(on2 == sorted(on2),
                  "o que fica sao os clips MAIS NOVOS",
                  "%s .. %s" % (on2[0] if on2 else "-", on2[-1] if on2 else "-"))
            check(len(on2) < len(names_written),
                  "e a fila nao cresce sem limite",
                  "%d de %d" % (len(on2), len(names_written)))
            # A garantia FIFO a serio: se sobrevive alguem, o mais novo
            # sobrevive. Um FIFO que tirasse o mais novo apagava a
            # sobreposicao mais recente -- que e' a que o dono ainda quer ver.
            check(on2 and on2[-1] == names_written[-1],
                  "e o mais novo sobrevive, se alguem sobrevive",
                  "%s" % (on2[-1] if on2 else "-"))
        finally:
            shutil.rmtree(tmp2, ignore_errors=True)

        # ---- 3. O QUE SE PERDEU E' DITO -----------------------------------
        print("\n3. O QUE SE PERDEU E' DITO, ou o audio do dono desaparece calado")
        tmp3 = tempfile.mkdtemp(prefix="fifo3-", dir="I:\\cc-tmp")
        try:
            d3 = os.path.join(tmp3, "clips")
            tight = 1.5 * CLIP_BYTES / 1048576.0          # cabe 1
            # 16 s de audio, e nao 4: o ultimo span comeca no frame 720, que a
            # 270 amostras por frame sao 194400 amostras = 12,2 s. Com 4 s de
            # buffer, TRES dos cinco spans eram truncados para fora e nunca
            # escreviam clip nenhum -- e a prova da conta fechava a dizer 5
            # quando so havia 2. Um fixture que produz menos do que conta
            # mede outra coisa.
            samples3 = tone(int(16 * FS), 7)
            res3 = S.save_multivoice_clips(
                samples3, 1_700_000_100.0,
                [(0, 60), (180, 240), (360, 420), (540, 600), (720, 780)],
                d3, FS, 0.0, tight)
            surviving, evicted = unpack(res3)
            check(evicted is not None,
                  "`save_multivoice_clips` DEVOLVE quantos clips apagou",
                  "devolveu %s -- o numero de perdidos e' irrecuperavel"
                  % type(res3).__name__)
            if evicted is not None:
                check(len(surviving) + len(evicted) == 5,
                      "escritos = sobreviventes + apagados (a conta fecha)",
                      "%d + %d = %d, esperado 5"
                      % (len(surviving), len(evicted),
                         len(surviving) + len(evicted)))
                check(len(evicted) > 0,
                      "e com a tampa apertada esse numero NAO e' zero",
                      "%d apagados" % len(evicted))
                check(len(surviving) == len(clips_on_disk(d3)),
                      "e o que sobra e' exactamente o que esta no disco",
                      "sobreviveram %d, disco %d"
                      % (len(surviving), len(clips_on_disk(d3))))

            # ---- 4. O CLIP APAGADO NA MESMA CHAMADA ------------------------
            # A eviccao corre DEPOIS da escrita, na mesma chamada. Com uma tampa
            # que nem cabe um clip, o ficheiro acabado de escrever e' o
            # primeiro a sair. MEDIDO no estado de hoje: `n_clips=2` no disco 0.
            d4 = os.path.join(tmp3, "clips4")
            sur4, ev4 = unpack(S.save_multivoice_clips(
                tone(int(4 * FS), 9), 1_700_000_200.0, [(0, 60)],
                d4, FS, 0.0, 1e-9))
            on4 = clips_on_disk(d4)
            check(len(sur4) == len(on4),
                  "os clips contados como guardados sao os que EXISTEM",
                  "contados %d, no disco %d" % (len(sur4), len(on4)))
            check((ev4 is not None) and len(ev4) >= 1,
                  "e o clip que se apagou a si mesmo e' DITO, nao engolido",
                  "apagados %s" % (ev4 if ev4 is not None else "?"))
        finally:
            shutil.rmtree(tmp3, ignore_errors=True)

        # ---- 5. O ESTADO E O PAYLOAD QUE A SHELL LE -----------------------
        print("\n4. O ESTADO E O PAYLOAD QUE A SHELL LE")
        tmp5 = tempfile.mkdtemp(prefix="fifo5-", dir="I:\\cc-tmp")
        try:
            d5 = os.path.join(tmp5, "clips")
            out5 = os.path.join(tmp5, "w.json")
            buf = S.RingBuffer(rate=FS, window_s=4.0)
            buf.push(tone(int(4 * FS), 11), 1_700_000_300.0)
            sess = fake_sess([4] * 40 + [0] * 40 + [4] * 40)
            st = S.watch_tick(buf, sess, out5, S.DEFAULT_WATCH_HOLD, 1.0,
                              d5, 0.0, tight)
            check("n_clips_evicted" in st,
                  "`watch_tick` PUBLICA quantos clips a fila perdeu",
                  "campos: %s" % sorted(st))
            check(st.get("n_clips") == len(clips_on_disk(d5)),
                  "e `n_clips` e' o que SOBREVIVEU, nao o que foi escrito",
                  "n_clips=%s, no disco %d" % (st.get("n_clips"),
                                              len(clips_on_disk(d5))))
            pay = json.load(open(out5, encoding="utf-8"))
            check("clips_evicted" in pay,
                  "e o payload gravado tambem o diz -- e' o registo que "
                  "sobrevive a uma janela que desliza e a um processo que "
                  "reinicia",
                  "chaves: %s" % sorted(pay))
        finally:
            shutil.rmtree(tmp5, ignore_errors=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ---- 5. O ACUMULADO SOBREVIVE A JANELAS -------------------------------
    # MEDIDO antes da correcção: em quatro janelas que perderam 1, 1 e 1 clip,
    # o payload final dizia `clips_evicted: 1`. O numero lia-se como "perdidos
    # ate agora" e era "perdidos agora" -- e o payload e' reescrito a cada
    # janela, por isso o historico da perda vivia so no log.
    print("\n5. O ACUMULADO SOBREVIVE A JANELAS")
    tmp6 = tempfile.mkdtemp(prefix="fifo6-", dir="I:\\cc-tmp")
    try:
        d6 = os.path.join(tmp6, "clips")
        out6 = os.path.join(tmp6, "w.json")
        tight6 = 1.5 * CLIP_BYTES / 1048576.0
        samples6 = tone(int(16 * FS), 21)
        sess6 = fake_sess([4] * 60)
        evicted_total = 0
        per_tick = []
        for k in range(4):
            buf = S.RingBuffer(rate=FS, window_s=10.0)
            buf.push(samples6, 1_700_000_400.0 + k * 30.0)
            st = S.watch_tick(buf, sess6, out6, S.DEFAULT_WATCH_HOLD, 1.0,
                              d6, 0.0, tight6, evicted_before=evicted_total)
            evicted_total = int(st.get("n_clips_evicted_total") or 0)
            per_tick.append(int(st.get("n_clips_evicted") or 0))
        pay6 = json.load(open(out6, encoding="utf-8"))
        check(evicted_total == sum(per_tick),
              "`n_clips_evicted_total` e' a SOMA das janelas, nao a ultima",
              "total=%d, soma=%s" % (evicted_total, per_tick))
        check(evicted_total > max(per_tick),
              "e por isso e' maior do que qualquer janela sozinha -- era "
              "exatamente onde o numero mentia",
              "total=%d, maior janela=%d" % (evicted_total, max(per_tick)))
        check(pay6.get("clips_evicted_total") == evicted_total,
              "e o payload gravado leva o acumulado, para quem o ler depois",
              "payload=%s" % pay6.get("clips_evicted_total"))
        check("clips_evicted" in pay6 and "clips_evicted_total" in pay6,
              "os DOIS campos existem: o da janela e' o do total",
              "chaves: %s" % [k for k in sorted(pay6) if "clips" in k])

        # ---- 5b. O ACUMULADO SOBREVIVE A UM REINICIO DO SIDECAR -----------
        # MEDIDO e furo real: o sidecar reinicia SOZINHO durante uma call (o
        # watcher reinicia-o). Um total que so vive em memoria e' esquecido a
        # cada reinicio, e a Fase B corrida depois volta a dizer "completo"
        # sobre audio que ja foi perdido. O payload sobrevive ao processo;
        # por isso e' ele que guarda a verdade.
        with open(out6, "w", encoding="utf-8") as fh:
            json.dump({"clips_evicted_total": 9, "n_spans": 1}, fh)
        resumed = S.resume_evicted_total(out6)
        check(resumed == 9,
              "um sidecar que arranca a meio da call retoma o total do payload",
              "retomou %s" % resumed)
        resumed0 = S.resume_evicted_total(os.path.join(tmp6, "nao-existe.json"))
        check(resumed0 == 0,
              "e sem payload retoma ZERO, sem rebentar",
              "retomou %s" % resumed0)
        with open(out6, "w", encoding="utf-8") as fh:
            fh.write("{ nao e' json")
        resumed_bad = S.resume_evicted_total(out6)
        check(resumed_bad == 0,
              "payload CORROMPIDO nao derruba o sidecar -- um ficheiro a meio "
              "nao pode parar a deteccao",
              "retomou %s" % resumed_bad)
    finally:
        shutil.rmtree(tmp6, ignore_errors=True)

    # ---- 7. QUEM CORRE A FASE B FICA A SABER? ----------------------------
    # O ultimo elo. O sidecar conta, o watcher diz ao dono -- mas quem chega
    # depois da call e corre a separacao sobre o directorio recebia um
    # resultado sem qualquer aviso. Separar 3 clips e dizer "pronto" quando
    # foram 7 e' a forma mais cara de estar errado.
    print("\n6. QUEM CORRE A FASE B FICA A SABER QUE O DIRECTORIO ESTA INCOMPLETO")
    import importlib.util                                          # noqa: PLC0415
    spec = importlib.util.spec_from_file_location(
        "_mvo", os.path.join(HERE, "multivoice-offline.py"))
    mvo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mvo)
    tmp7 = tempfile.mkdtemp(prefix="fifo7-", dir="I:\\cc-tmp")
    try:
        p7 = os.path.join(tmp7, "w.json")

        def probe(body, raw=None):
            with open(p7, "w", encoding="utf-8") as fh:
                fh.write(raw if raw is not None else json.dumps(body))
            return mvo.loss_report(p7)

        check(probe({"n_spans": 2}) is None,
              "sem registo de fila, devolve None (nao 'zero perdido')")
        check(probe({"clips_evicted_total": 7})["lost"] == 7,
              "com o total, devolve o numero")
        check(probe({"clips_evicted_total": 0})["lost"] == 0,
              "e zero quando zero -- que e' diferente")
        unread = probe({"clips_evicted_total": "x"})
        check(unread is not None and unread.get("lost") is None,
              "e ILEGIVEL quando o campo nao se lê -- MEDIDO: isto devolvia "
              "`lost: 0`, ou seja, lixo no campo dizia 'nada se perdeu'",
              "%r" % (unread or {}).get("unreadable"))
        check(probe(None, raw="{ nao e' json") is None,
              "payload ilegivel devolve None, nao zero")
        src = open(os.path.join(HERE, "multivoice-offline.py"),
                   encoding="utf-8").read()
        check("incomplete" in src and "clips_lost" in src,
              "e o payload de saida leva `incomplete`/`clips_lost`, para quem "
              "o consumir saber sem ler o ecra")
        check("COMPLETUDE" in src,
              "e ha uma faixa no ecra -- o campo sozinho nao chega: o dono "
              "le o ecra")
    finally:
        shutil.rmtree(tmp7, ignore_errors=True)

    print("-" * 78)
    if FAILURES:
        print("VERDICT: FAIL  (%d/%d: %s)"
              % (len(FAILURES), CHECKS[0], "; ".join(FAILURES)))
        return 1
    print("VERDICT: PASS  (%d/%d checks)" % (CHECKS[0], CHECKS[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())