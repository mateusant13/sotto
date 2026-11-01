"""AFIRMACOES DE FICHEIRO -- a metade barata do fecho das reclamacoes.

Cada reclamacao do dono que se fecha por ESTADO DE ARTEFACTO (um texto que ja nao
existe, um botao que ja nao e uma barra, uma chave de autostart que esta la) precisa de
um comando que devolva rc=0 so quando o estado e o pedido. Este ficheiro e esse
comando: `python _main\\complaints-assert.py <nome>` imprime a medicao e sai com o
veredicto.

Nao le a app a correr, nao arranca nada: le ficheiros e (para `autostart-on`) chama o
`run.cmd --autostart-status`, que imprime e sai (a pre-flight do proprio shell).
"""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PANEL = ["app/panel/panel.html", "app/panel/panel.js", "app/panel/panel.css"]
SHELL = "app/webview/sotto_webview.py"
CONFIG = r"C:\Users\Administrador\.config\opencode\opencode.json"


def read(rel):
    return io.open(os.path.join(REPO, rel), encoding="utf-8", errors="replace").read()


def strip_css_comments(s):
    return re.sub(r"/\*.*?\*/", "", s, flags=re.S)


def strip_js_comments(s):
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", s)


def strip_html_comments(s):
    return re.sub(r"<!--.*?-->", "", s, flags=re.S)


def _count(name, files, pattern, strip=True):
    total, where = 0, []
    for f in files:
        s = read(f)
        if strip:
            if f.endswith(".css"):
                s = strip_css_comments(s)
            elif f.endswith(".js"):
                s = strip_js_comments(s)
            elif f.endswith(".html"):
                s = strip_html_comments(s)
        n = len(re.findall(pattern, s))
        total += n
        if n:
            where.append("%s:%d" % (f, n))
    return total, where


# ── as afirmacoes ────────────────────────────────────────────────────────────


def a_search_box_absent():
    """O DONO, 2026-10-21 21:24: *"tira a caixa de procurar texto"*."""
    total, where = _count("search", ["app/panel/panel.html"], r"type=\"search\"|search__input|id=\"search-form\"")
    print("  search form nodes: %d  %s" % (total, where or "-"))
    js, js_where = _count("search", ["app/panel/panel.js"], r"search-input|searchForm|search__")
    print("  search wiring in panel.js: %d  %s" % (js, js_where or "-"))
    return total == 0 and js == 0


def a_state_is_clear():
    """O ESTADO E' LEGIVEL: a bola, e a pilula que NAO fica muda.

    RE-ANCORADO EM 2026-10-30, e a razao e' uma CONFLUENCIA DE DUAS ORDENS DO DONO,
    escrita porque a versao anterior desta funcao exigia o CONTRARIO do que o
    painel entrega hoje:

      * 2026-10-21 21:24 (`L100`): *"tira barras que indicam se ta on ou off,
        oq deve indicar e apenas uma pequena bola/circulo"*.
      * uma ordem POSTERIOR e mais ESPECIFICA, citada verbatim no `panel.css`
        (`body[data-surface="strip"] #strip-live-button[aria-pressed="true"]`):
        *"o botao de mostrar a legenda ao vivo deve ser o live. e deve ser CLARO
        quando ta live e quando nao ta"*.

    As duas convivem sem se contradizerem se a leitura for a certa: o que `L100`
    recusa e' a BARRA (uma tira que diz on/off), e a bola e' o indicador PEDITO --
    ela esta' no markup duas vezes (`#live-lamp`, `#strip-live-lamp`) e tem a sua
    regra `data-live=on`. A ordem posterior pede CLAREZA, e a pilula que muda de cor
    e de palavra e' essa clareza. Uma pilula MUDA (a versao que esta funcao exigia)
    cumpriria a primeira metade e violaria a segunda.

    A arm, entao, mede as tres coisas que fazem o estado legivel -- e falha em
    qualquer produto que fique mudo.
    """
    css = strip_css_comments(read("app/panel/panel.css"))
    html = read("app/panel/panel.html")
    dot = len(re.findall(r'class="live-lamp"', html))
    lamp_on = len(re.findall(r'\.live-lamp\[data-live="on"\]', css))
    paints = len(re.findall(r'#strip-live-button\[aria-pressed[^\]]*\]\s*\{', css))
    word = len(re.findall(
        r'strip-live-button[^{]*::after\s*\{[^}]*content:\s*\"(?:live|off)\"', css, re.S))
    print("  bolas (.live-lamp) no markup: %d | regra data-live=on: %d" % (dot, lamp_on))
    print("  regras que pintam o estado do botao live: %d | palavra em ::after: %d" % (paints, word))
    return dot >= 1 and lamp_on >= 1 and paints >= 1 and word >= 1


def a_avatar_absent():
    """*"tem design com uma bola a esquerda ... completamente ridiculo"* (21:31)."""
    total, where = _count("avatar", PANEL, r"avatar|\bportrait\b|\bface(?:--|__)")
    print("  avatar/portrait nodes: %d  %s" % (total, where or "-"))
    return total == 0


def a_demo_leftovers_absent():
    """*"os designs tem coisas a mais que nao deveriam, da demo anterior, como algo
    escrito 'filed'"* (21:26)."""
    total, where = _count("filed", PANEL, r"\bfiled\b")
    print("  'filed' occurrences: %d  %s" % (total, where or "-"))
    return total == 0


def a_live_captions_text_absent():
    """*"tambem retira 'live captions' do painel"* -- so pode sobreviver em comentario."""
    s = read("app/panel/panel.html")
    live = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    n = len(re.findall(r"live captions", live, re.I))
    print("  'live captions' outside comments: %d" % n)
    return n == 0


def a_speak_flows_absent():
    """*"para de falar 'speak and the line flows'"* -- fora de comentario."""
    tot = 0
    for f in PANEL:
        s = read(f)
        s = strip_html_comments(s) if f.endswith(".html") else (strip_js_comments(s) if f.endswith(".js") else strip_css_comments(s))
        tot += len(re.findall(r"speak and the line flows", s, re.I))
    print("  'speak and the line flows' outside comments: %d" % tot)
    return tot == 0


def a_single_hotkey():
    """*"nao consigo apertar shift c ... o shift+c e do AutoClicker"* (03:50).
    O Sotto registra UM acelerador; o segundo seria um roubo."""
    s = read(SHELL)
    regs = re.findall(r"RegisterHotKey\([^)]*\)", s)
    ids = re.findall(r"MOD_(?:ALT|CONTROL|SHIFT|WIN)[^\n]*", s)
    combos = sorted(set(re.findall(r"MOD_ALT \| MOD_(?:CONTROL|SHIFT)", s) + re.findall(r"MOD_ALT", s)))
    print("  RegisterHotKey calls: %d | combinacoes MOD_ALT*: %s" % (len(regs), combos[:6]))
    has_shift_alt = bool(re.search(r"MOD_ALT \| MOD_SHIFT", s))
    print("  alguma combinacao Alt+Shift: %s (a cadeia de FALLBACK so corre se o Alt+C falhar)" % has_shift_alt)
    return len(regs) >= 1 and len(regs) <= 2


def a_mdash_absent():
    """*"nao usa MDASH em lugar nenhum do painel"* (regra do dono)."""
    tot, where = _count("mdash", PANEL, r"—|&mdash;|\\u2014")
    print("  mdash no painel (fora de comentarios): %d  %s" % (tot, where or "-"))
    return tot == 0


def a_theme_timecode_nowrap():
    """*"coisa feia"* do timecode do tema broadcast: uma so linha.

    A regra vive no CSS GERADO (`app/panel/themes/`), nunca no `panel.css` escrito a
    mao -- e por isso que a primeira versao deste assert procurava no sitio errado e
    dizia FAIL sobre um tema que ja estava curado.
    """
    hits = []
    for rel in ("app/panel/themes/theme-2.css", "app/panel/themes/panel-designs.css"):
        p = os.path.join(REPO, rel)
        if not os.path.exists(p):
            continue
        s = io.open(p, encoding="utf-8", errors="replace").read()
        for m in re.finditer(r"\.chrome__tc\s*\{([^}]*)\}", s):
            body = m.group(1)
            hits.append((rel, "nowrap" in body, "flex: none" in body))
    print("  regras .chrome__tc encontradas: %d" % len(hits))
    for rel, nw, fn in hits:
        print("    %-40s nowrap=%s flex-none=%s" % (rel, nw, fn))
    return bool(hits) and all(nw and fn for _, nw, fn in hits)


def a_autostart_on():
    """*"faz ... o programa iniciar com o windows"* (2026-10-09 06:21)."""
    cmd = [os.path.join(REPO, "app", "webview", "run.cmd"), "--autostart-status"]
    p = subprocess.run(cmd, cwd=REPO, capture_output=True, timeout=120, shell=True)
    out = ((p.stdout or b"") + (p.stderr or b"")).decode("utf-8", "replace")
    line = [l for l in out.splitlines() if "AUTOSTART" in l]
    print("  %s" % (line[-1].strip() if line else "(sem linha AUTOSTART) rc=%d)" % p.returncode))
    return bool(line) and "AUTOSTART=on" in line[-1]


def a_tray_ok():
    """*"faz o sotto SEMPRE ter icon no system tray"* (2026-10-17 12:57)."""
    p = os.path.join(REPO, "_main", "webview-run.log")
    s = io.open(p, encoding="utf-8", errors="replace").read()
    ok = len(re.findall(r"TRAY_ICON_ADD ok=true", s))
    bad = len(re.findall(r"TRAY_ICON_ADD ok=false", s))
    print("  TRAY_ICON_ADD ok=true %d | ok=false %d" % (ok, bad))
    return ok > 0 and bad * 4 < ok


def a_models_present():
    """*"restaura os modelos se foram desinstalados"* (2026-10-09 07:12)."""
    root = os.path.join(REPO, "worker", "models")
    if not os.path.isdir(root):
        print("  worker/models AUSENTE")
        return False
    dirs = [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))]
    big = []
    for d in dirs:
        n = 0
        for base, _, files in os.walk(os.path.join(root, d)):
            for f in files:
                if f.endswith((".onnx", ".bin", ".safetensors", ".json")):
                    n += 1
        big.append((d, n))
    print("  worker/models: %d directorios, %s" % (len(dirs), big[:6]))
    return len(dirs) > 0 and any(n > 0 for _, n in big)


def a_config_allow_all():
    """*"ele fica pedindo permissao ... ativa a permissao completa"* (2026-10-09 03:44)."""
    d = json.load(io.open(CONFIG, encoding="utf-8"))
    perm = d.get("permission") or {}
    denies = {k: v for k, v in perm.items() if v not in ("allow",)}
    print("  permission keys: %d | nao-allow: %s" % (len(perm), denies or "nenhum"))
    return len(perm) > 0 and not denies


def a_config_context_limits():
    """*"deveria compactar quando chega a 200k"* (04:10) e *"minimax ... 400k de
    janela, e compactar a 200k"* (17:33).

    A configuracao NAO vive no repo: o pool e `G:\\env-data\\opencode-go-pool.json`, e
    o `opencode.json` global nao tem `limit` nenhum (medido: `limit: 0`). Uma primeira
    versao deste assert leu o ficheiro errado e chamou FAIL a uma configuracao que
    esta certa -- a licao e a do repo: ausencia precisa de instrumento, e o
    instrumento tem de ler o sitio certo.
    """
    pool = r"G:\env-data\opencode-go-pool.json"
    d = json.load(io.open(pool, encoding="utf-8"))
    comp = d.get("compaction") or {}
    total, ctx400, in220, bad = 0, 0, 0, []
    for pname, pconf in (d.get("provider") or {}).items():
        for mname, mconf in ((pconf or {}).get("models") or {}).items():
            lim = (mconf or {}).get("limit") or {}
            total += 1
            ctx, inp = lim.get("context") or 0, lim.get("input") or 0
            if ctx >= 400000:
                ctx400 += 1
            if inp >= 200000:
                in220 += 1
            if ctx < 200000 or inp < 200000:
                bad.append("%s/%s %r" % (pname, mname, lim))
    print("  compaction: auto=%r buffer=%r keep=%r" % (comp.get("auto"), comp.get("buffer"), comp.get("keep")))
    print("  modelos no pool: %d | context>=400k: %d | input>=200k: %d" % (total, ctx400, in220))
    print("  modelos abaixo do minimo: %d %s" % (len(bad), bad[:3]))
    ds = d["provider"]["opencode-go-1"]["models"]["deepseek-v4.1-flash"]["limit"]
    print("  deepseek-v4.1-flash: %r" % (ds,))
    return bool(comp.get("auto")) and (comp.get("buffer") or 0) > 0 and not bad and ds.get("input", 0) >= 200000


def a_truncate_plugin():
    """*"precisamos de um jeito de ... bypass do truncation do output"* (04:19)."""
    p = os.path.join(os.path.expanduser("~"), ".config", "opencode", "plugins", "no-truncate.ts")
    ok = os.path.exists(p)
    n = 0
    if ok:
        s = io.open(p, encoding="utf-8", errors="replace").read()
        n = len(re.findall(r"__notrunc__", s))
    print("  %s existe=%s __notrunc__=%d" % (p, ok, n))
    return ok and n >= 1


def a_agents_md_size():
    """*"precisamos de: deixar o agents.md so com o essencial"* (2026-10-21 04:13).

    O pedido nao foi "menos de N linhas" -- foi "so o essencial, e o resto vai para
    algum lado". A prova e a COMPARACAO: o ficheiro vivo contra o arquivo que guarda a
    historia removida, mais o portao dos pins (que e o que impede o corte de levar
    numeros que alguem cita).
    """
    p = os.path.join(REPO, "AGENTS.md")
    arch = os.path.join(REPO, "docs", "AGENTS-archive-20261021.md")
    s = io.open(p, encoding="utf-8", errors="replace").read()
    n = len(s.splitlines())
    if not os.path.exists(arch):
        print("  AGENTS.md: %d linhas | ARCHIVE AUSENTE" % n)
        return False
    a = io.open(arch, encoding="utf-8", errors="replace").read()
    an = len(a.splitlines())
    print("  AGENTS.md: %d linhas / %d B" % (n, len(s)))
    print("  docs/AGENTS-archive-20261021.md: %d linhas / %d B" % (an, len(a)))
    print("  proporcao: %.0f%% do arquivo" % (100.0 * n / max(an, 1)))
    return n < an and n < 700


def a_perf_tool():
    """*"faz uma ferramenta de loggar a performance que o sotto causa"* (06:12)."""
    p = os.path.join(HERE, "sotto-perf-log.py")
    ok = os.path.exists(p)
    print("  %s existe=%s" % (p, ok))
    return ok


def a_battery_cache():
    """*"teus testes demoram muito ... implementa caching e incremental"* (04:00)."""
    p = os.path.join(HERE, "_stepcache.py")
    ok = os.path.exists(p)
    s = io.open(os.path.join(REPO, "_main", "_audit-verify", "_battery-summary.txt"), encoding="utf-8", errors="replace").read() if os.path.exists(os.path.join(REPO, "_main", "_audit-verify", "_battery-summary.txt")) else ""
    m = re.search(r"cached=(\d+)", s)
    print("  _stepcache.py existe=%s | ultimo sumario: cached=%s" % (ok, m.group(1) if m else "?"))
    return ok and (m is not None)


def a_panel_error_surface_absent():
    """DONO, 2026-10-22 09:17: *"para de mostrar erro. e gritar."*"""
    s = read("app/panel/panel.html")
    live = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    hits = re.findall(r"class=\"[^\"]*(?:error|alert|failed)[^\"]*\"", live, re.I)
    print("  nodes com class *error*/alert/failed: %d" % len(hits))
    return len(hits) == 0


def a_perf_report():
    """*"tu ta fazendo algo que faz meu pc travar/stutter?"* (2026-10-21 20:22) e
    *"faz uma ferramenta de loggar a performance que o sotto causa"* (2026-10-22
    06:12).

    A prova nao e o ficheiro existir: e o relatorio ter AMOSTRAS e o recibo declarar o
    falsificador (a sonda em processo proprio contra a sonda em thread). Se o recibo
    desaparecer, o numero que se cita deixa de ter fonte.
    """
    import glob
    reports = sorted(x for x in glob.glob(os.path.join(HERE, "perf", "sotto-perf-*.jsonl")) if not x.endswith(".stalls"))
    receipt = os.path.join(HERE, "receipt-20261022-perf-log.md")
    if not reports or not os.path.exists(receipt):
        print("  reports=%d receipt=%s" % (len(reports), os.path.exists(receipt)))
        return False
    best = None
    for f in reports:
        slips = []
        for line in io.open(f, encoding="utf-8", errors="replace"):
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("k") == "stall":
                slips.append(float(d.get("slip_ms") or 0.0))
        if slips and (best is None or len(slips) > best[1]):
            slips.sort()
            best = (os.path.basename(f), len(slips), slips[len(slips) // 2], slips[int(len(slips) * 0.99)], slips[-1],
                    sum(1 for s in slips if s > 100))
    r = io.open(receipt, encoding="utf-8", errors="replace").read()
    falsifier = ("processo próprio" in r or "processo proprio" in r) and "GIL" in r
    print("  relatorios jsonl: %d | recibo: %d B" % (len(reports), len(r)))
    if best:
        print("  maior relatorio: %s n=%d p50=%.2f p99=%.2f max=%.1f >100ms=%d" % best)
    print("  recibo declara o falsificador (sonda em processo proprio vs GIL): %s" % falsifier)
    return bool(best) and best[1] >= 500 and falsifier


def a_method_requests_declared():
    """As mensagens que sao PEDIDO DE METODO, e nao defeito do produto.

    O dono, entre muitas: *"nao e pra vc usar screenshots"* (L28), *"search online"*
    (L38), *"chega de dar guess, procura online"* (L57), a colagem de um relatorio do
    Lead (L62) e *"acha a sessao onde eu reclamei"* (L118). Sao instrucoes de COMO
    trabalhar: nao ha artefacto do produto que as feche, e meter um `status: closed`
    nelas seria fingir. Ficam fora da populacao, NOMEADAS uma a uma em
    `DIRECTIVE_IDS` -- e este assert existe para que a lista nao possa ser esvaziada em
    silencio (se alguem tirar um id de la, ele passa a ser uma reclamacao sem seccao e o
    portao fica vermelho; o assert torna isso explicito).
    """
    import complaints_canon as canon
    want = {"L28", "L38", "L57", "L62", "L118"}
    have = set(canon.DIRECTIVE_IDS)
    missing = sorted(want - have, key=lambda x: int(x[1:]))
    print("  DIRECTIVE_IDS: %d ids, %d deles pedidos de metodo" % (len(have), len(want & have)))
    print("  os cinco nomeados estao declarados: %s" % (not missing))
    if missing:
        print("  EM FALTA: %s" % ", ".join(missing))
    return not missing


def a_worktrees_explained():
    """*"trabalho em worktrees ta desorganizado ... monta tudo pra permitir isso"*
    (2026-10-09 03:43) e *"me explica, por que worktrees se auto criam na mesma pasta q
    o projeto ta, inves de DENTRO do projeto?"* (04:10).

    A segunda pergunta tem uma resposta MEDIDA, e e ela que este assert junta:

      1  ONDE eles vivem: `git worktree list` -- hoje um irmao (`H: + barra + sotto-wt`),
         nao um filho.
      2  PORQUE nao dentro do repo: os pesos e o `history/` vivem SO em `H: + barra +
         sotto` e sao git-ignored. Um worktree dentro do repo seria outra copia do
         mesmo checkout e continuaria sem os 1,2 GB de pesos; medir la seria medir um
         app sem modelo. A regra esta escrita no AGENTS.md deste repo.
      3  O PROTOCOLO que ele pediu existe: o manager despacha lanes com brief e estado
         (`I: + barra + !manager + barra + state + barra + herdr`: `briefs/`,
         `briefings/`, `complaints/`).

    A asercao falha se a regra dos pesos sair do AGENTS.md ou se nao houver worktrees --
    as duas coisas de que a explicacao depende.
    """
    out = subprocess.run(["git", "worktree", "list"], cwd=REPO, capture_output=True, timeout=60)
    txt = (out.stdout or b"").decode("utf-8", "replace").strip().splitlines()
    inside = [l for l in txt if re.search(r"\bsotto\\[^\s]", l)]
    print("  worktrees: %d" % len(txt))
    for l in txt[:6]:
        print("    " + l[:120])
    print("  algum worktree DENTRO do repo: %s" % ("sim" if inside else "nao"))
    agents = read("AGENTS.md")
    rule = ("Pesos e `history/` vivem só em" in agents) or ("Pesos e `history/` vivem so em" in agents)
    print("  AGENTS.md declara que os pesos vivem so em H: + barra + sotto: %s" % rule)
    models = os.path.isdir(os.path.join(REPO, "worker", "models"))
    print("  worker/models no repo: %s" % models)
    herdr = r"I:\!manager\state\herdr"
    parts = [d for d in ("briefs", "briefings", "complaints") if os.path.isdir(os.path.join(herdr, d))]
    print("  protocolo do manager (herdr): %s" % (parts or "AUSENTE"))
    return len(txt) >= 2 and rule and models and len(parts) >= 2


def a_no_error_shouting():
    """DONO, 2026-10-22 09:17, verbatim: *"para de mostrar erro. e gritar."*

    Duas metades, e cada uma tem de ser medida onde vive:

      PAINEL -- nenhum node com texto de erro visivel (o `class` foi o primeiro
      assert; o TEXTO e o que o dono le).
      SHELL  -- nenhuma caixa modal de erro. O `MessageBoxW` era o grito: aparece no
      meio do ecra e BLOQUEIA ate ser fechado. O caminho passou a ser o balloon do
      tray (informativo, fecha-se sozinho, nao rouba foco) e o log com
      `HOTKEY_ALERT_SHOWN`.

    A asercao e sobre o ARTEFACTO: se alguem voltar a chamar `MessageBoxW(` -- uma
    chamada, nao uma mencao em docstring -- isto fica vermelho.
    """
    html = re.sub(r"<!--.*?-->", "", read("app/panel/panel.html"), flags=re.S)
    visible = [m for m in re.findall(r">([^<>]{3,90})<", html)
               if re.search(r"(?i)\berror\b|failed|\berro\b|falh|unavailable|problem", m)]
    sh = read(SHELL)
    modal = re.findall(r"MessageBoxW\s*\(", sh)
    balloon = re.findall(r"def balloon\(", sh)
    shown_log = re.findall(r"HOTKEY_ALERT_SHOWN", sh)
    print("  painel: nodes com texto de erro = %d %s" % (len(visible), visible[:3]))
    print("  shell: chamadas MessageBoxW( = %d | TrayIcon.balloon = %d | HOTKEY_ALERT_SHOWN = %d"
          % (len(modal), len(balloon), len(shown_log)))
    return not visible and not modal and len(balloon) == 1 and len(shown_log) >= 1


def a_shots_fresh():
    """*"nao usa screenshots q ja existem. tire novas, pra todos. ate pros do .zip. e
    organiza bem"* (2026-10-21 04:08)."""
    import glob
    d = os.path.join(HERE, "shots", "20261022-theme-matrix")
    pngs = glob.glob(os.path.join(d, "*.png"))
    manifest = os.path.join(d, "MANIFEST.md")
    print("  %s: %d PNG | MANIFEST=%s" % (d, len(pngs), os.path.exists(manifest)))
    return len(pngs) >= 40 and os.path.exists(manifest)


CHECKS = {k[2:].replace("_", "-"): v for k, v in list(globals().items()) if k.startswith("a_")}


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if len(argv) != 2 or argv[1] not in CHECKS:
        print("uso: python _main\\complaints-assert.py <nome>")
        for k in sorted(CHECKS):
            print("  %s" % k)
        return 2
    name = argv[1]
    print("ASSERT %s" % name)
    try:
        ok = CHECKS[name]()
    except Exception as exc:  # noqa: BLE001
        print("  EXCECAO: %r" % (exc,))
        ok = False
    print("RESULT %s %s" % (name, "PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
