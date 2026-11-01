"""O CANONE DAS RECLAMACOES -- quem conta como reclamacao, e por que.

Um portao que diz "fechamos tudo" sem uma populacao declarada e uma opiniao. Este
modulo e a populacao: le o corpus do dono (`sotto.md`, 148 mensagens para `H:\\sotto`),
separa o que e **reclamacao/pedido do dono** do que e **texto de despacho** (prompt de
lane, prompt de auto-loop, sonda de leitura) e entrega os ids `L<n>` -- os mesmos
numeros de linha do ficheiro do corpus, para qualquer pessoa poder conferir.

A EXCLUSAO E UMA LISTA DE PADROES, NAO UM JULGAMENTO. Cada motivo existe e e dito:

  dispatch      comeca por "You are a " / "You are an " -- e um brief que o LEAD (ou o
                proprio agente) escreveu; nao e o dono a reclamar.
  auto-loop     comeca por "GOAL (" -- o loop a pedir trabalho, nao o dono.
  probe         "Somente leitura", "Responda apenas", "Modelo trocado", "Continue de
                onde", "Continue o trabalho", "CONTINUE: retome" -- sondas de vida.
  goal-template comeca por "# /goal" -- o template do modo goal.
  meta          "e veja meus prompts sobre esses problemas" -- instrucao de metodo.
  noise         "ping", "go", "check", "ok", "faz tudo", "siga com tudo", "reiniciei",
                "boa. continua", "responde e continua", "[Image 1]" sozinho -- nao ha
                reclamacao no texto.

TUDO O RESTO CONTA. Inclui pedidos ("faz o alt c funcionar"), perguntas com queixa
("por que ta assim?") e reclamacoes explicitas ("ta completamente fora de sync").
"""

from __future__ import annotations

import io
import re

CORPUS = r"I:\!manager\state\herdr\complaints\sotto.md"

_MSG = re.compile(r"^- \*\*(.+?)\*\* \[(\w+)\] (.*)$")

#: MENSAGENS DE PROCESSO, nomeadas uma a uma. Nao sao reclamacoes do produto: sao
#: instrucoes de metodo, perguntas de estado, ou colagens de outros agentes. Ficam
#: listadas aqui (e o documento imprime-as com o texto) para que a exclusao seja
#: auditavel -- um id que nao aparece nem como reclamacao nem nesta lista e um buraco.
DIRECTIVE_IDS = {
    "L12": "aponta sessoes de outros harnesses",
    "L13": "explica o comando dsh",
    "L17": "pede a continuacao noutro projecto (clone do shadowplay)",
    "L22": "proibe subagents nesta sessao",
    "L43": "pede handoff para outro harness",
    "L49": "autoriza prints so do app",
    "L55": "autoriza fazer o que falta e pedir commit/push",
    "L59": "diz que nao precisa de mandar imagens",
    "L63": "aprova o plano do Lead",
    "L82": "da permissao para mudar arquitectura",
    "L28": "pedido de metodo: nao usar screenshots",
    "L38": "pedido de metodo: procurar a solucao online",
    "L57": "pedido de metodo: chega de guess, procurar online",
    "L62": "colagem de um relatorio do Lead, nao fala do dono",
    "L118": "pede para localizar a sessao onde reclamou",
    "L127": "declara LIGHT MODE (nao correr coisas pesadas)",
    "L139": "pergunta se ja terminou tudo",
    "L142": "cola um GOAL-BLOCKED anterior",
    "L153": "meta: duas abas abertas",
}

_EXCLUDE = (
    ("dispatch", re.compile(r"^(You are a |You are an )")),
    ("auto-loop", re.compile(r"^GOAL \(")),
    ("goal-template", re.compile(r"^# /goal")),
    ("probe", re.compile(r"^(Somente leitura|Responda apenas|Modelo trocado|Continue de onde|Continue o trabalho|CONTINUE: retome)")),
    ("meta", re.compile(r"^(e veja meus prompts)")),
    # NOISE IS ANCHORED to the WHOLE message. A prefix rule swallowed real
    # complaints: "reiniciei. continua. e me explica, por que worktrees..." (L11) and
    # "ok. continua tudo que falta. ... mas algo q vi agora e: contraste" (L121) both
    # began with a noise word and both carried a complaint.
    ("noise", re.compile(r"^(ping\]?|go|check|ok\.?|faz tudo|siga com tudo\.?( mantenha uma todo list)?|reinici\w*\.?( continua\.?)?|reinciei o pc\.?( continua)?|boa\. continua( com todo o resto\.?)?|responde e continua|\[Image 1\]( <)?)$")),
)


def load(path=CORPUS):
    """Todas as mensagens, na ordem do ficheiro."""
    out = []
    for i, line in enumerate(io.open(path, encoding="utf-8", errors="replace").read().splitlines(), 1):
        m = _MSG.match(line)
        if not m:
            continue
        out.append({"line": i, "ts": m.group(1), "harness": m.group(2), "text": m.group(3), "id": "L%d" % i})
    return out


def classify(msg):
    """(papel, motivo) -- 'complaint'/'excluded'."""
    # A quote character is how the corpus records some messages ("Somente leitura…",
    # "Responda apenas…"); it must not hide the pattern from the exclusion list.
    t = msg["text"].strip().lstrip('"').strip()
    if not t:
        return "excluded", "noise"
    if msg["id"] in DIRECTIVE_IDS:
        return "excluded", "directive"
    for reason, rx in _EXCLUDE:
        if rx.match(t):
            return "excluded", reason
    return "complaint", "owner"


def complaints(path=CORPUS):
    return [m for m in load(path) if classify(m)[0] == "complaint"]


def excluded(path=CORPUS):
    return [(m, classify(m)[1]) for m in load(path) if classify(m)[0] == "excluded"]


def quote(text, n=180):
    """A cita do dono, numa linha, com o texto cortado a `n` caracteres."""
    flat = re.sub(r"\s+", " ", text).strip()
    return flat if len(flat) <= n else flat[: n - 1].rstrip() + "\u2026"


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    msgs = load()
    comp = complaints()
    exc = excluded()
    print("corpus        : %s" % CORPUS)
    print("mensagens     : %d" % len(msgs))
    print("reclamacoes   : %d" % len(comp))
    print("excluidas     : %d" % len(exc))
    reasons = {}
    for _, r in exc:
        reasons[r] = reasons.get(r, 0) + 1
    for r, n in sorted(reasons.items()):
        print("  %-14s %d" % (r, n))
    print("")
    for m in comp:
        print("%-6s %s  %s" % (m["id"], m["ts"][:16], quote(m["text"], 110)))
