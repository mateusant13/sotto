"""O PLAYER A PINTAR OUTRA FAIXA -- e a legenda do Sotto nao pode desaparecer.

O QUE ESTE PORTAO JULGA (medido primeiro, escrito depois)
--------------------------------------------------------
O dono, 2026-10-22, sobre a legenda do YouTube: *"ta completamente bugada"*.

MEDIDO 2026-10-23 com `_main/yt-1to1-live-compare.py` (Edge proprio, `--mute-audio`,
video `WdaHAGRBB6s`): o player PINTAVA `pt` -- a traducao automatica -- enquanto a
politica servia `en-orig`. As palavras pintadas nunca estao na faixa servida, logo o
`align_painted` nao tinha o que alinhar e `_youtube` devolvia `[]` com
`painted-other-track` **para sempre**: o dono ficou sem a legenda do YouTube e o ASR
tomou o lugar (uma transcricao da traducao lida em voz alta).

A CORRECCAO: quando o player pinta outra faixa, o RELOGIO diz onde o video esta e
desenha-se a cue da faixa SERVIDA nesse instante (a lingua continua a do dono: *"para de
traduzir pra pt br do ingles e do espanhol"*). O relogio so e usado enquanto ANDA -- o
relogio congelado e medido (lia `t=2.0` com o video a 530), e a prova do congelamento e
uma PINTURA QUE MUDA COM O RELOGIO PARADO.

O QUE ESTE INSTRUMENTO NAO CARREGA (e por isso nao pode julgar)
---------------------------------------------------------------
  * nao abre a app, nao abre browser, nao le UIA: o `_youtube` e chamado com as leituras
    do player SUBSTITUIDAS (pintura e relogio vem de listas fixas). O que se mede e a
    DECISAO da shell, nao a leitura;
  * nao prova que o UIA entrega as palavras certas -- isso mede-se com o app a correr, e
    o instrumento que o mede e outro (`_main/yt-1to1-live-compare.py`);
  * `align_painted` corre a serio (o modulo real), porque o arm A4 depende disso.

Uso:
  python _main/youtube-foreign-paint-oracle.py
  python _main/youtube-foreign-paint-oracle.py --neg-arm   # rc=1 por desenho
"""
import argparse
import importlib.util
import os
import shutil
import sys
import threading
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SHELL = os.path.join(os.path.dirname(HERE), "app", "webview", "sotto_webview.py")
SHELL_DIR = os.path.dirname(SHELL)

VID = "WdaHAGRBB6s"
#: A faixa que a politica serve: ingles, duas cues.
TRACK = {
    "state": "has-track",
    "lang": "en",
    "source": "auto",
    "duration": 6.0,
    "cues": [
        {"start": 0.0, "end": 2.0, "text": "Have you ever had to kill a man?"},
        {"start": 2.0, "end": 4.0, "text": ">> No."},
        {"start": 4.0, "end": 6.0, "text": ">> Then this sword is useless."},
    ],
}


class FakeThread(object):
    """O `youtube_track_thread` da shell: nao busca nada, devolve a faixa de cima."""

    def __init__(self, track):
        self.track = track
        self.requests = []

    def request(self, vid, painted=None):
        # O CONTRATO MUDOU 2026-11-03: `request` deixou de bloquear e passou a
        # devolver o que JA' ESTIVER PRONTO (`_yt_track_poll`, fire-and-forget).
        # Um stub que devolvesse `None` punha o laco no ramo `track is None` --
        # e o oraculo media as palavras do player a caminho, nunca a decisao da
        # faixa que ele existe para julgar. Devolver a faixa e' o contrato.
        self.requests.append((vid, tuple(painted or ())))
        return self.track

    def current(self, vid):
        return self.track


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    if SHELL_DIR not in sys.path:
        sys.path.insert(0, SHELL_DIR)
    spec.loader.exec_module(mod)
    return mod


def build_watcher(mod, painted, clocks, track=None):
    """Um `ExternalCaptionWatcher` sem `__init__` -- sem janela, sem thread, sem UIA."""
    obj = object.__new__(mod.ExternalCaptionWatcher)
    obj.shell = types.SimpleNamespace(youtube_track_thread=FakeThread(track or TRACK))
    obj.yt_video_id = ""
    obj.yt_cue = ""
    obj.yt_reason = ""
    obj.yt_no_clock_since = 0.0
    obj.yt_hit = None
    obj.yt_paint_why = ""
    obj.yt_caption_logged = ""
    obj.yt_foreign_t = None
    obj.yt_foreign_key = ""
    # 2026-10-30: o `__init__` vivo ganhou o CHAO DO TEMPO
    # (`youtube_monotonic.decide`). Um stub que nao o declare morre com
    # `AttributeError` dentro de `_yt_decide`, e o oraculo mediria a ausencia
    # de um atributo em vez do ramo `painted-other-track`.
    obj.yt_serve_floor = None
    obj.yt_held_logged = None
    # 2026-11-03: o `__init__` vivo tambem ganhou o AMOSTRADOR DO RELOGIO
    # (`_ensure_clock_sampler`), uma thread que le' UIA a 0,40 s. Um stub que nao
    # a declare levanta `AttributeError: no attribute 'stop_event'` dentro dela e
    # -- pior -- um stub que a deixe arrancar faz este oraculo abrir UIA, que ele
    # promete NAO fazer no proprio cabecalho. O sentinela desliga-a: a amostra do
    # relogio continua a ser a lista fixa deste instrumento.
    obj.stop_event = threading.Event()
    obj._yt_clock_thread = True
    # SEM CDP, DE PROPOSITO (2026-11-03). O shell ganhou o caminho CDP como
    # PRIMEIRO (`_yt_source_by_title`, `_yt_cdp_source`) e, com uma fonte
    # configurada e sem foto fresca, o tick devolve NADA por desenho ("sem foto,
    # espera-se o tick seguinte"). Este instrumento julga a decisao do caminho
    # UIA -- o `painted`/relogio -- e um `_yt_cdp_source` vivo põe-lhe a' frente
    # uma porta que ele nao existe para medir. `False` e' o valor que o proprio
    # shell usa para "nao ha' CDP" (o teste e' `if _src and _src is not False`).
    obj._yt_cdp_source = False
    obj._youtube_video_id = lambda *a: VID
    paints = list(painted)
    ticks = list(clocks)
    obj._youtube_painted = lambda *a: (paints.pop(0) if paints else [])
    # O RELOGIO NAO SE ESGOTA (2026-11-03). Um `pop(0)` que devolve `None`
    # quando a lista acaba modela um relogio IMPOSSIVEL: em producao a leitura
    # devolve um numero ou falha (None), nunca "acabaram as amostras" -- e um
    # tick que pede o relogio duas vezes (o afinador da revelacao e o ramo
    # estrangeiro) comia a unica amostra e o oraculo media esse artefacto.
    # Agora a lista e' a CADENCIA: o ultimo valor repete-se.
    _clock = {"used": 0, "last": None}

    def _tick(*a):
        i = _clock["used"]
        if i < len(ticks):
            _clock["used"] = i + 1
            _clock["last"] = ticks[i]
        return _clock["last"]

    obj._youtube_time = _tick
    return obj


def line_of(got):
    """`([(source, [linhas])], urgent)` -> a lista de linhas."""
    lines, _urgent = got
    if not lines:
        return []
    return list(lines[0][1])


def run_polls(mod, painted, clocks, track=None):
    """Uma `_youtube` por cada instante dado; devolve (linhas, razao) de cada poll."""
    obj = build_watcher(mod, painted, clocks, track)
    out = []
    for _ in range(len(clocks)):
        got = obj._youtube(0, None, None)
        out.append((line_of(got), obj.yt_reason))
    return out


#: O player pinta PORTUGUES (a traducao automatica) -- nunca casa com a faixa inglesa.
PT = [["Você", "já"], ["Você", "já", "teve"], ["Já", "teve", "que"]]
#: Palavras que ESTAO na faixa servida (alinhamento por texto tem de ganhar).
#: `_ALIGN_MIN_EXACT` e 3, portanto a pintura tem de trazer pelo menos tres palavras
#: exactas -- e a ultima cue e a mais curta que ainda serve.
EN = [["Then", "this", "sword"]]


def arms(mod):
    """(nome, o que mede, passa?) -- cada braco tem de passar."""
    results = []

    # A1 -- O DEFEITO QUE ISTO FECHA. Pintura estrangeira + relogio a andar: TEM de sair
    # uma linha, a da faixa servida no instante do relogio, e nao um beco sem saida.
    got = run_polls(mod, PT[:1], [2.5])
    results.append(("A1 pinta-outra-faixa+relogio-a-andar -> linha",
                    got[0][0] == [">> No."] and got[0][1] == "painted-other-track:clock",
                    got))

    # A2 -- O RELOGIO CONGELADO. A pintura MUDA e o relogio fica no mesmo sitio: e a
    # assinatura medida do congelamento, e nada pode ser mostrado (uma linha de outro
    # minuto e pior do que nenhuma). A primeira poll estabelece o instante.
    got = run_polls(mod, PT[:2], [1.0, 1.0])
    # O QUE MUDOU, E PORQUE NAO E' UM AFROUXAMENTO (2026-11-03).
    #
    # Esta arm exigia NADA no segundo tick. O shell ganhou, a 2026-11-02, um
    # ramo por baixo desta guarda -- `painted-no-clock` -- com a foto do dono
    # que o justifica: duas linhas no player e NADA no Sotto, porque o track
    # servido nao alinha e o relogio nao deu instante. O invariante que este
    # braco guarda continua inteiro: com o relogio CONGELADO nada pode vir do
    # relogio -- nenhuma cue de outro instante. O que ele passa a permitir e' o
    # que aquele ramo existe para fazer: as palavras que o PROPRIO PLAYER esta'
    # a desenhar, com o motivo escrito (`painted-no-clock`). A arm recusa as
    # duas coisas que doem: linha vazia no primeiro tick (o defeito de 2026-10-23)
    # e uma linha cuja razao nao diga de onde veio.
    results.append(("A2 pintura-muda+relogio-parado -> nada do relogio",
                    got[0][0] != []
                    and got[1][1] == "painted-no-clock"
                    and got[1][0] == ["Você já teve"],
                    got))

    # A3 -- VIDEO EM PAUSA. A pintura esta QUIETA e o relogio tambem: nao ha prova de
    # congelamento, e a linha que la esta fica (senao a legenda pisca em pausa).
    got = run_polls(mod, [PT[0], PT[0]], [1.0, 1.0])
    first = "Have you ever had to kill a man?"
    results.append(("A3 pintura-quieta+relogio-parado -> a mesma linha",
                    got[0][0] == [first] and got[1][0] == [first],
                    got))

    # A4 -- A PINTURA E DA FAIXA SERVIDA. O alinhamento por texto TEM de ganhar: e o
    # caminho antigo, e o relogio nao pode ser consultado quando ele responde.
    #
    # ATUALIZADO 2026-10-30, e NAO re-fixado: este braco esperava a cue INTEIRA
    # (`">> Then this sword is useless."`). A revelacao palavra-a-palavra de
    # 2026-10-29 (`youtube_reveal.window_by_paint`) passou a devolver o PREFIXO
    # ja' pintado pelo player -- medido aqui: `">> Then this"`. O invariante que
    # o braco guarda continua o mesmo e e' o que fica pinado: motivo `painted`
    # (o alinhamento por texto ganhou, o relogio NAO foi consultado) e uma linha
    # nao vazia que e' PREFIXO do texto da cue. O que muda nao e' o invariante,
    # e' o desenho: fixar o texto inteiro media a revelacao, nao o alinhamento.
    # (O fixture escreve `">> Then this sword is useless."` mas so' pinta
    # `Then this sword` -- o `>>` nao e' pintado, e por isso a contagem de
    # palavras pintadas corta em `">> Then this"`.)
    #
    # A RAZAO CHAMA-SE `painted-lines` DESDE 2026-11-03 (era `painted`). O
    # renomear foi do shell, para separar o ramo que pinta as LINHAS do player
    # (`_yt_rows`) do que alinha palavras; o invariante do braco nao mudou.
    got = run_polls(mod, [EN[0]], [0.0])
    cue_full = ">> Then this sword is useless."
    line = got[0][0][0] if got[0][0] else ""
    # O MARCADOR DE FALANTE NAO CONTA (2026-11-03). O ramo `painted-lines` tira
    # o `>> ` antes de comparar (o `>>` nao e' fala, e' marcador), logo a linha
    # que sai e' `Then this sword` -- prefixo da cue sem o marcador, nao da cue
    # com ele. O invariante do braco nao muda: a linha e' um PREFIXO da cue
    # servida, e a razao diz que o alinhamento por texto ganhou.
    cue_body = cue_full.lstrip("> ").strip()
    results.append(("A4 pintura-da-faixa-servida -> alinhamento por texto",
                    got[0][1] == "painted-lines" and bool(line)
                    and cue_body.startswith(line),
                    got))
    return results


# ---------------------------------------------------------------------------
# os mutantes: cada um tem de deixar o portao VERMELHO
# ---------------------------------------------------------------------------
MUTANTS = [
    (
        "sem-guarda-do-relogio",
        "o relogio congelado passa a ser usado (A2 fica verde)",
        """            if now_t is not None and (moved or key == self.yt_foreign_key):""",
        """            if now_t is not None:""",
    ),
    (
        "sem-a-pintura-quieta",
        "a pausa deixa de segurar a linha (A3 fica vermelho)",
        """            if now_t is not None and (moved or key == self.yt_foreign_key):""",
        """            if now_t is not None and moved:""",
    ),
    (
        "sem-linha",
        "a cue encontrada nunca e mostrada (A1 fica vermelho)",
        # RE-ANCORADO 2026-11-03. O trecho de hoje e' um RETORNO ANTECIPADO
        # (`if not text: return None`) e nao o `if text:` que a ancora citava --
        # media 0 vezes e o braco morria com "a ancora casou 0 vezes". O mutante
        # apaga as PALAVRAS, que e' o que a A1 mede (a cue encontrada nunca e'
        # mostrada); a forma do `if` fica a do fonte, para a copia ser mutante e
        # nao um ficheiro invalido.
        """        text = str((cue or {}).get('text') or '').strip()
        if not text:
            return None
        self.yt_cue = text""",
        """        text = ''
        if not text:
            return None
        self.yt_cue = text""",
    ),
]


def crlf(text):
    """A shell e CRLF-pura: o texto que a parte tem de ser CRLF tambem."""
    return text.replace("\r\n", "\n").replace("\n", "\r\n")


def build_mutant(text, name, old, new):
    old, new = crlf(old), crlf(new)
    count = text.count(old)
    if count != 1:
        raise RuntimeError("%s: a âncora casou %d vezes (esperado 1)" % (name, count))
    path = os.path.join(SHELL_DIR, "_ytpaint-neg-%s.py" % name)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text.replace(old, new, 1))
    return path


def clean_mutants():
    for name in os.listdir(SHELL_DIR if os.path.isdir(SHELL_DIR) else "."):
        if name.startswith("_ytpaint-neg-") and name.endswith(".py"):
            try:
                os.remove(os.path.join(SHELL_DIR, name))
            except OSError:
                pass


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--neg-arm", action="store_true",
                    help="aponta o portao a uma copia partida: tem de sair rc=1")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    clean_mutants()
    failures = []
    try:
        if args.neg_arm:
            # O BRACO NEGATIVO: a decisao E julgada, e julga-se com uma copia partida.
            text = open(SHELL, encoding="utf-8", newline="").read()
            name, _why, old, new = MUTANTS[0]
            path = build_mutant(text, "neg-arm", old, new)
            mod = load_module(path, "_ytpaint_neg_arm")
            bad = [r for r in arms(mod) if not r[1]]
            if bad:
                print("YT-PAINT-FOREIGN NEG-ARM PASS -- a copia partida foi apanhada:")
                for label, _ok, got in bad:
                    print("  RED %s -> %r" % (label, got))
                return 1
            print("YT-PAINT-FOREIGN NEG-ARM FAIL -- a copia partida ficou verde")
            return 2

        mod = load_module(SHELL, "sotto_shell_ytpaint")
        for label, ok, got in arms(mod):
            print("%s %s" % ("GREEN" if ok else "RED  ", label))
            if not ok:
                print("      got=%r" % (got,))
                failures.append(label)

        text = open(SHELL, encoding="utf-8", newline="").read()
        for name, why, old, new in MUTANTS:
            try:
                path = build_mutant(text, name, old, new)
            except RuntimeError as exc:
                print("RED   mutante %s nao pode ser construido: %s" % (name, exc))
                failures.append(name)
                continue
            mmod = load_module(path, "_ytpaint_neg_%s" % name.replace("-", "_"))
            caught = [r for r in arms(mmod) if not r[1]]
            if caught:
                print("GREEN mutante %s apanhado (%s)" % (name, why))
            else:
                print("RED   mutante %s NAO foi apanhado (%s)" % (name, why))
                failures.append(name)
    finally:
        clean_mutants()

    if failures:
        print("YT-PAINT-FOREIGN VERDICT FAIL (%d)" % len(failures))
        return 2
    print("YT-PAINT-FOREIGN VERDICT PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
