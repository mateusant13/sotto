"""Portao das ETIQUETAS DE VOZ ESTAVEIS (`StableSpeakerSlots`).

O DEFEITO QUE ESTE PORTAO EXISTE PARA APANHAR
---------------------------------------------
MEDIDO na call real do dono com o modelo real (20 s de janela, passo de 10 s,
`_main/_call-diar-cmap.py` + os dumps):

    par 1->2     etiqueta CRUA  25,0 %   (cMAP alinhado, 75,0 %)
    par 15->16   etiqueta CRUA   0,0 %   (cMAP 100,0 %, mapa {0:1, 1:0})

O diarizador renumera a MESMA pessoa de uma janela para a seguinte. `tick`
publicava esse numero cru. E `source` e' a chave da linha no painel
(`panel.js:386` `rowIdentity`), portanto publicar o numero cru significa que as
legendas de UMA pessoa saltam entre duas linhas de 10 em 10 segundos.

Fixar `num_speakers` NAO resolve: medido, acordo cru de **68,4 %** com
`num_clusters=2`, contra **70,2 %** em modo auto. O numero nunca foi o problema;
a NUMERACAO era.

Porque o `cmap` nunca viu isto: o `cmap` ALINHA os dois conjuntos de etiquetas
antes de pontuar, porque os rotulos sao arbitrarios e sem alinhar leria "mudou o
numero" como "mudou a pessoa". Esse alinhamento e' exactamente o que esconde o
defeito. A metrica era cega **por construcao**.

O QUE ESTE PORTAO EXIGE
-----------------------
1. Uma inversao total de numeracao entre janelas devolve os MESMOS slots.
2. Uma voz nova recebe um slot NOVO (e nao rouba um slot existente).
3. Uma voz que cala e volta depois do horizonte recebe slot novo.
4. A ordem de entrada dos segmentos nao muda o resultado.
5. `tick(slots=None)` fica byte-identico ao comportamento antigo -- a correccao
   tem de poder ser desligada.

Braco negativo
--------------
`--neg-arm` substitui `StableSpeakerSlots` por uma copia que deixa passar o
numero local (isto e, o codigo de ANTES da correccao). O arm 1 tem de ir a RED
nessa copia: se a porta passar com a identidade, a porta nao mede nada.
"""
import argparse
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODULE_PATH = os.path.join(ROOT, "worker", "speaker_sidecar.py")


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def seg(start, end, speaker):
    return {"start": float(start), "end": float(end), "speaker": int(speaker)}


def run(mod):
    arms = []

    def chk(cond, name, why):
        arms.append((bool(cond), name, why))

    # --- 1. A inversao que o modelo real produziu -----------------------------
    # Janelas QUE SE SOBREPOEM, como na vida real: janela k = [0,20], janela
    # k+1 = [10,30], passo 10 s. O mesmo audio (13,0..15,4) aparece nas duas --
    # e o diarizador renumera-o de 0 para 1. E' o TEMPO FALADO PARTILHADO que
    # diz que e' a mesma pessoa; o numero local nao diz nada.
    #
    # A primeira versao deste teste punha janelas DISJUNTAS ([10,19] e [22,29]).
    # Nao havia tempo partilhado para casar e os tres arms que dependem do
    # casamento foram a RED. O codigo estava certo e o teste errado: um arm que
    # falha porque o fixture nao reproduz a condicao nao apanha o defeito.
    slots = mod.StableSpeakerSlots(horizon_s=60.0)
    w1, _m1, _c1 = slots.remap([seg(13.0, 15.4, 0), seg(16.5, 18.0, 0)], now=18.0)
    w2, _m2, _c2 = slots.remap([seg(13.0, 15.4, 1), seg(16.5, 18.0, 1)], now=28.0)
    id_w1 = {s["start"]: s["speaker"] for s in w1}
    id_w2 = {s["start"]: s["speaker"] for s in w2}
    chk(len(set(id_w1.values())) == 1 and len(set(id_w2.values())) == 1,
        "uma voz, um slot, por janela",
        "a janela nao inventou duas pessoas")
    chk(set(id_w1.values()) == set(id_w2.values()),
        "a renumeracao 0->1 devolve o MESMO slot global",
        "medido: par 1->2 cru 25,0 %, par 15->16 cru 0,0 % (inversao total)")
    chk("local_speaker" in w2[0] if isinstance(w2[0], dict) else False,
        "a etiqueta local sobrevive ao remapeamento",
        "sem isto, um bug de remapeamento e invisivel no payload")
    chk(w2[0].get("local_speaker") == 1
        and w2[0].get("speaker") == next(iter(set(id_w1.values()))),
        "local=1, global=<o slot da janela anterior>",
        "os dois campos dizem coisas diferentes, como deve ser")

    # --- 2. Uma voz que nunca falou ------------------------------------------
    fresh = mod.StableSpeakerSlots(horizon_s=60.0)
    a, _m, _c = fresh.remap([seg(13.0, 17.0, 0)], now=17.0)
    b, _m, _c = fresh.remap([seg(13.0, 17.0, 0), seg(18.0, 22.0, 1)], now=22.0)
    chk(len({s["speaker"] for s in b}) == 2,
        "uma voz nova recebe um slot NOVO",
        "a janela k+1 partilha 13..17 com a k: a voz que continua casa; a que "
        "aparece em 18..22 nao tem tempo partilhado com ninguem e nao pode "
        "roubar o slot de ninguem")
    chk({s["start"]: s["speaker"] for s in b}[13.0]
        == {s["start"]: s["speaker"] for s in a}[13.0],
        "a voz que continua mantem o slot E a nova nao o rouba",
        "se este arm passar e o anterior falhar, a atribuicao esta a repartir "
        "mal; os dois juntos fecho o problema")

    # --- 3. O horizonte --------------------------------------------------------
    near = mod.StableSpeakerSlots(horizon_s=60.0)
    near.remap([seg(13.0, 15.4, 0)], now=15.4)
    back, _m, _c = near.remap([seg(13.0, 15.4, 0)], now=25.4)
    chk(back[0]["speaker"] == 1,
        "dentro do horizonte, a voz que cala volta ao MESMO slot",
        "uma pausa curta nao pode fazer uma pessoa virar outra")
    h = mod.StableSpeakerSlots(horizon_s=5.0)
    h.remap([seg(13.0, 15.4, 0)], now=15.4)
    late, _m, _c = h.remap([seg(13.0, 15.4, 0)], now=115.4)
    chk(late[0]["speaker"] != back[0]["speaker"],
        "passado o horizonte, a mesma voz recebe slot novo",
        "slots nao crescem sem limite ao longo de uma call de horas")

    # --- 4. Determinismo -------------------------------------------------------
    base = mod.StableSpeakerSlots(horizon_s=60.0)
    seq = [seg(1.0, 3.0, 0), seg(4.0, 6.0, 1), seg(7.0, 9.0, 0)]
    ids_ref = None
    orderings = [seq, list(reversed(seq)), [seq[1], seq[2], seq[0]],
                 [seq[2], seq[0], seq[1]]]
    for order in orderings:
        s = mod.StableSpeakerSlots(horizon_s=60.0)
        out, _m, _c = s.remap(order, now=9.0)
        key = tuple(sorted((o["start"], o.get("local_speaker"), o.get("speaker"))
                           for o in out))
        if ids_ref is None:
            ids_ref = key
        else:
            chk(key == ids_ref, "a ordem de entrada nao muda nada", repr(order))

    # --- 5. tick sem slots fica byte-identico ---------------------------------
    #
    # O FIXTURE TEM FALA. Este bloco mede o REMAP de slots, e remap so existe
    # quando a janela tem gente a falar: e' o que a porta de densidade
    # (`MIN_SPEECH_FRACTION`) pressupoe. O fixture era `[0.0] * 8000` --
    # silencio digital -- e com a porta ficou a recusar tudo, o que e' o
    # comportamento CORRETO em silencio e o comportamento ERRADO neste teste.
    # Um teste que passa por desactivar a feature que o atravessa esta a medir
    # outra coisa; o audio e' que se corrige, e o silencio ganha o seu proprio
    # arm logo a seguir, onde tem razao para ser recusado.
    class FakeRing:
        rate = 1000
        start_t = 300.0

        def window(self):
            # Onda pseudo-fala, deterministica e com envelope de energia: a
            # porta le a envolvente, nao a forma.
            import math
            return [0.2 * math.sin(2 * math.pi * 180.0 * (i / 1000.0))
                    * (0.6 + 0.4 * math.sin(2 * math.pi * 3.0 * (i / 1000.0)))
                    for i in range(8000)]

        def window_duration_s(self):
            return 8.0

    class SilentRing(FakeRing):
        def window(self):
            return [0.0] * 8000

    calls = []

    def dial(samples, threshold=0.9, num_speakers=-1):
        calls.append(1)
        return {"segments": [seg(1.0, 3.0, 7), seg(4.0, 6.0, 3)]}

    out_file = os.path.join(HERE, "_slots_tick.json")
    if os.path.exists(out_file):
        os.remove(out_file)
    state = mod.tick(FakeRing(), dial, out_file)
    payload = {}
    if os.path.isfile(out_file):
        with open(out_file, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    chk(state.get("state") == "written", "tick sem slots escreve", repr(state))
    chk([s["speaker"] for s in payload.get("segments", [])] == [7, 3],
        "tick sem slots publica os numeros crus, inalterados",
        "a correccao tem de poder ser DESLIGADA")
    chk("speaker_slots" not in payload,
        "sem slots nao aparece nenhum campo novo no payload",
        "OFF tem de ser byte-identico")
    chk([s["start"] for s in payload.get("segments", [])] == [301.0, 304.0],
        "o offset da janela continua a ser aplicado", "")

    # --- 6. uma janela de SILENCIO e' recusada, e nao e' um bug ---------------
    if os.path.exists(out_file):
        os.remove(out_file)
    before = len(calls)
    state = mod.tick(SilentRing(), dial, out_file)
    silent_payload = {}
    if os.path.isfile(out_file):
        with open(out_file, "r", encoding="utf-8") as fh:
            silent_payload = json.load(fh)
    chk(state.get("declined") is True,
        "uma janela de silencio NAO e' atribuida a ninguem", repr(state))
    chk(silent_payload.get("segments") == [],
        "e o payload vai com `segments: []`",
        "%s" % silent_payload.get("segments"))
    chk(silent_payload.get("attribution") == "declined",
        "diz porque -- e nao parece uma janela que nao falou",
        "campo `attribution` = %r" % silent_payload.get("attribution"))
    if os.path.exists(out_file):
        os.remove(out_file)

    return arms


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--neg-arm", action="store_true")
    args = ap.parse_args(argv)

    mod = load_module(MODULE_PATH, "speaker_sidecar_slots")
    if args.neg_arm:
        # A copia "antes da correccao": deixa passar o numero local.
        class IdentitySlots:
            def __init__(self, horizon_s=60.0):
                pass

            def remap(self, segments, now):
                return [dict(s) for s in segments], {}, []

        mod.StableSpeakerSlots = IdentitySlots

    arms = run(mod)
    failed = [a for a in arms if not a[0]]
    for ok, name, why in arms:
        print("  %s %s" % ("GREEN" if ok else "RED  ", name))
        if why:
            print("       %s" % why)
    print("\narms %d/%d" % (len(arms) - len(failed), len(arms)))
    if args.neg_arm:
        ok = bool(failed)
        print("NEG-ARM: a identidade tem de falhar -> %s" % ("RED-OK" if ok else "PASS?!"))
        print("VERDICT: %s" % ("PASS" if ok else "FAIL"))
        return 0 if ok else 1
    print("VERDICT: %s" % ("PASS" if not failed else "FAIL"))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())