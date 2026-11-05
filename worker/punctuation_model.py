"""PONTUACAO DE MODELO (opcional, e NUNCA em caminho critico).

Ordem do dono (2026-11-05, verbatim): *"por que a gente nao normaliza as frases
ou usa pontuacao de forma inteligente?"*. Duas metades da resposta:

  * `worker/punctuation_prosody.py` -- a metade SEM modelo: a pausa medida decide
    onde ha uma marca. Custo zero de disco, funciona em qualquer lingua.
  * este ficheiro -- a metade COM modelo: um restaurador de pontuacao treinado em
    ingles (`sherpa-onnx-online-punct-en`, Apache-2.0, Edge-Punct-Casing
    arXiv:2407.13142), int8 **7,1 MB**, CPU, 1 fio.

MEDIDO nesta maquina (2026-11-05, 10 linhas reais do `CAPTION_IN` do log do dono):
carga **91 ms**, por linha **6,1-8,5 ms** (mediana 6,8). Um chunk do worker e'
560 ms, logo o custo e' ~1,2 % de um chunk.

O QUE ELE FAZ MAL, e por isso a guarda de lingua e' obrigatoria: em texto
portugues ele devolve caixa aleatoria -- medido, `"eu gosto muito disso sabe
como e que e"` -> `"EU Gosto Muito, disso sabe como E que E"`. Um restaurador
ingles sobre fala portuguesa nao e' "um pouco melhor", e' ruido com aparencia de
pontuacao. Logo: tag de lingua que nao comece por `en` -> identidade, sempre.

E o `?` e' o caso que a casa mediu em contrario: o `punct-prosody-oracle`
mostrou que o F0 NAO correlaciona com pergunta (5 pausas de clausula limpas, 3
subindo e 2 caindo, e 0 fixtures com pergunta). Um `?` que o modelo ingles poe a
meio de uma hipotese parcial foi medido: `"that I? didn't"`. Regra daqui: `?` e
`!` so' sobrevivem quando FECHAM o texto; a meio, sao removidos. `,` e `.` ficam.

AUSENTE E' UM ESTADO NORMAL: sem o modelo em `worker/models/punct-en/` este
modulo devolve o texto intacto e `status()` diz por que. Nada aqui pode fazer
uma legenda falhar -- toda a chamada ao modelo esta' dentro de um `try`, e o
caminho de excepcao e' a identidade.
"""
from __future__ import annotations

import os
import re
import threading
from pathlib import Path

#: Onde o par (modelo, vocab) e' procurado. O primeiro que existir ganha.
#: `worker/models/` e' git-ignored (pesos), como o resto dos motores.
DEFAULT_DIR = Path(__file__).resolve().parent / "models" / "punct-en"

MODEL_FILE = "model.int8.onnx"
VOCAB_FILE = "bpe.vocab"

#: As marcas que o modelo pode introduzir, por decisao do dono: `,` e `.` sao
#: pontuacao de escrita; `?`/`!` sao prosodia, e a prosodia nao foi medida como
#: sinal confiavel nesta casa. Ver o docstring.
INLINE_MARKS = (",", ".")
END_MARKS = (".", "?", "!")

_LOCK = threading.Lock()
_ENGINE = None
#: A tag de lingua do PROCESSO, posta por quem a resolveu (`StreamAsr`). O
#: `_event` vive no `LineFormer`, que nao tem a resolucao -- e inventar uma tag
#: la' seria adivinhar a lingua, que e' o que a guarda existe para nao fazer.
_LANG = None
_STATE = {"tried": False, "reason": "not-tried", "dir": None, "load_ms": None}

#: `SOTTO_PUNCT_MODEL` = `0` desliga mesmo com o modelo no disco; `1`/`en`
#: liga (e a tag de lingua ainda tem de ser inglesa). Ausente = o modelo decide.
_ENV = "SOTTO_PUNCT_MODEL"


def _ensure_package_importable(d: Path) -> None:
    """O pacote viaja AO LADO do modelo (`worker/models/punct-en/sherpa_onnx`).

    Nada e' instalado no `site-packages` do dono e nada aqui toca no
    `onnxruntime`: este pacote traz o proprio runtime nativo (medido: a corrida
    que o mediu nao tinha `onnxruntime` instalado e funcionou). Um segundo
    `onnxruntime` no `sys.path` poderia vencer o build CUDA que o worker usa --
    o `worker-providers` mediu 10,75x com CUDA contra 2,27x em CPU, e essa
    regressao silenciosa e' exactamente o que este comentario existe para nao
    acontecer.
    """
    import sys  # noqa: PLC0415

    vendored = d / "sherpa_onnx"
    if not vendored.is_dir():
        return
    top = str(d)
    if top not in sys.path:
        sys.path.insert(0, top)


def find_model(root=None) -> Path | None:
    """O directorio do modelo, ou `None`. Le o DISCO, nao o ambiente."""
    d = Path(root) if root is not None else DEFAULT_DIR
    try:
        if (d / MODEL_FILE).is_file() and (d / VOCAB_FILE).is_file():
            return d
    except OSError:
        return None
    return None


def set_lang(tag) -> None:
    """Guarda a tag de lingua do processo. Chamado uma vez, na resolucao."""
    global _LANG
    _LANG = tag


def current_lang():
    return _LANG


def supported_lang(tag) -> bool:
    """A guarda de lingua. `en`, `en-US`, `EN_us` -> True; o resto -> False.

    `None` (lingua desconhecida) e' **False**: aplicar um restaurador ingles a
    texto de lingua desconhecida foi medido a produzir caixa aleatoria em
    portugues, e "desconhecida" nao e' "provavelmente ingles".
    """
    if tag is None:
        return False
    return str(tag).strip().lower().replace("_", "-").split("-")[0] == "en"


def _env_allows() -> bool:
    v = os.environ.get(_ENV, "").strip().lower()
    if v in ("0", "off", "false", "no"):
        return False
    return True


def load(root=None):
    """Carrega (uma vez) e devolve o motor, ou `None` com o motivo em `status()`."""
    global _ENGINE
    with _LOCK:
        if _ENGINE is not None:
            return _ENGINE
        if _STATE["tried"]:
            return None
        _STATE["tried"] = True
        if not _env_allows():
            _STATE["reason"] = "disabled-by-env"
            return None
        d = find_model(root)
        if d is None:
            _STATE["reason"] = "model-absent"
            _STATE["dir"] = str(root if root is not None else DEFAULT_DIR)
            return None
        try:
            _ensure_package_importable(d)
            import sherpa_onnx  # noqa: PLC0415 -- opcional, nunca no import do worker
        except Exception as exc:  # pragma: no cover - ambiente sem o pacote
            _STATE["reason"] = f"package-absent ({type(exc).__name__})"
            _STATE["dir"] = str(d)
            return None
        try:
            import time  # noqa: PLC0415

            t0 = time.perf_counter()
            cfg = sherpa_onnx.OnlinePunctuationConfig(
                sherpa_onnx.OnlinePunctuationModelConfig(
                    cnn_bilstm=str(d / MODEL_FILE),
                    bpe_vocab=str(d / VOCAB_FILE),
                    num_threads=1,
                )
            )
            _ENGINE = sherpa_onnx.OnlinePunctuation(cfg)
            _STATE["load_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            _STATE["reason"] = "loaded"
            _STATE["dir"] = str(d)
            return _ENGINE
        except Exception as exc:  # pragma: no cover - modelo corrompido
            _STATE["reason"] = f"load-failed ({type(exc).__name__}: {exc})"
            _STATE["dir"] = str(d)
            return None


def status() -> dict:
    """Estado para log/oraculo. Nunca carrega o modelo por si."""
    return {
        "reason": _STATE["reason"],
        "dir": _STATE["dir"],
        "load_ms": _STATE["load_ms"],
        "engine": _ENGINE is not None,
    }


_TRAILING_COMMA = re.compile(r",\s*$")
_MID_QUESTION = re.compile(r"\s*[?!]+(?=\s)")


def _filter(text: str) -> str:
    """So' `,` e `.` a meio; `?`/`!` apenas a fechar; nenhum comma a fechar.

    Medido: `"that I? didn't"` -- a hipotese parcial faz o modelo inglês
    perguntar a meio de uma frase. Um comma final tambem e' artefacto: a linha
    acaba ali por decisao do corte, nao por a fala ter parado.
    """
    if not text:
        return text
    out = _MID_QUESTION.sub("", text)
    out = re.sub(r"[?!]\s*$", ".", out)
    out = _TRAILING_COMMA.sub("", out)
    return out


def punctuate(text: str, tag=None, root=None) -> str:
    """Devolve `text` pontuado, ou `text` INALTERADO quando nao se aplica.

    Chamar e' sempre seguro: sem modelo, sem pacote, com lingua errada ou com o
    motor a levantar, devolve a mesma string que recebeu.
    """
    if not text or not text.strip():
        return text
    if tag is None:
        tag = _LANG
    if not supported_lang(tag):
        return text
    engine = load(root)
    if engine is None:
        return text
    try:
        with _LOCK:
            out = engine.add_punctuation_with_case(text)
    except Exception:
        return text
    if not isinstance(out, str) or not out.strip():
        return text
    return _filter(out)


def log_line() -> str:
    """Uma linha para o log do worker, para que o estado nunca seja adivinhado.

    A lingua entra na linha por medicao: a primeira versao dizia
    `reason=not-tried` numa sessao cuja lingua resolvida era `pt-BR`, e "ainda
    nao tentei" lia-se como falha quando o estado era o DESENHO (o restaurador
    e' ingles). `lang-unsupported` diz isso e mais nada.
    """
    s = status()
    # `active` e' a pergunta que a linha existe para responder ("a pontuacao vai
    # acontecer?"); `loaded` diz se o motor esta' em memoria. Sao coisas
    # diferentes e a primeira versao as confundiu: com o motor carregado e a
    # lingua em pt-BR, `loaded=true` lia-se "pontuando" quando nada pontuava.
    if not supported_lang(_LANG):
        return (f"PUNCT_MODEL active=false loaded={str(s['engine']).lower()} "
                f"reason=lang-unsupported lang={_LANG}")
    if s["engine"]:
        return (f"PUNCT_MODEL active=true loaded=true dir={s['dir']} "
                f"load_ms={s['load_ms']} lang={_LANG} "
                f"marks=comma,period max_end=question")
    return (f"PUNCT_MODEL active=false loaded=false reason={s['reason']} "
            f"dir={s['dir']} lang={_LANG}")


if __name__ == "__main__":  # pragma: no cover - smoke a mao
    import sys

    t = " ".join(sys.argv[1:]) or "hello there how are you doing today"
    print(log_line())
    print(repr(punctuate(t, tag="en")))
    print(repr(punctuate(t, tag="pt-BR")))
