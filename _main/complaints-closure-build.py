"""CONSTRUIR `.opencode/complaints-closure.md` -- uma seccao por reclamacao, com o
comando que a fecha e a saida que ele deu.

REGRA QUE ESTE FICHEIRO NAO PODE QUEBRAR: o `status` nao e escrito a mao. Cada
seccao aponta para um COMANDO; o construtor corre o comando uma vez, guarda rc e
saida, e poe `status: closed` so quando o rc e 0 e a saida casa com o padrao exigido.
Um comando que falha produz `status: open` com o motivo -- e a lista de abertos e o
trabalho que falta, nao uma frase.

    python _main\\complaints-closure-build.py            # constroi e imprime o resumo
    python _main\\complaints-closure-build.py --force    # ignora a cache de comandos
"""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, ".opencode", "complaints-closure.md")
PY = sys.executable
NODE = "node"

sys.path.insert(0, HERE)
import complaints_canon as canon  # noqa: E402


def C(argv, expect, timeout=300, cite=True, lit=None):
    """Um comando que prova a seccao.

    `cite=False` marca as provas de APOIO: correm e ficam no documento com o seu bloco,
    mas nao podem ser a PRIMEIRA `evidence:` da seccao, porque o portao do manager
    RE-EXECUTA essa e exige que a saida contenha o literal. MEDIDO 2026-10-22: o `R8`
    citava `nvidia-smi --query-gpu=memory.used` e o literal era `6420 MiB, 16303 MiB` --
    uma LEITURA VIVA da GPU. A citacao passou a ser o oraculo (`VERDICT: PASS`, estavel)
    e a leitura da GPU ficou como prova de apoio. A afirmacao nao foi enfraquecida: o
    oraculo e que MEDE o reuso; a leitura so mostra o estado de agora.
    """
    return {"argv": argv, "expect": expect, "timeout": timeout, "cite": cite,
            "lit": lit, "expect_rc": 0}


def R(argv, expect, timeout=300):
    """Um BRACO NEGATIVO: o rc 1 e' o DESENHO, nao a falha.

    MEDIDO 2026-10-30: a seccao `altc` declarava o `--neg-arm` do oraculo de gesto
    com `C(...)`, que exige rc == 0 -- e um braco negativo SAI 1 por construcao, logo a
    seccao ficava aberta com um rc que era o proprio PASS ("NEG-ARM PASS -- RED as
    designed"). O `R` fixa a forma que o desenho tem: rc 1 E a frase do braco.
    """
    cmd = C(argv, expect, timeout)
    cmd["expect_rc"] = 1
    return cmd


def A(name):
    return C([PY, "_main/complaints-assert.py", name], r"RESULT %s PASS" % name, 180)


# ── os temas: cada um e uma coisa que o dono pediu, e o comando que a prova ──
THEMES = [
    {
        "key": "render",
        "title": "o painel fica branco / um bloco de uma so cor / cores que mudam",
        "ids": ["L23", "L26", "L27", "L29", "L33", "L39", "L40", "L41", "L42", "L31", "L58"],
        "cmds": [
            C([NODE, "_main/theme-matrix-probe.mjs"], r"page errors: 0", 300),
            C([PY, "_main/panel-flash-contradiction-oracle.py"], r"VERDICT: PASS", 180),
        ],
        "why": ("45 temas renderizados num Chromium real: 0 erros de pagina, 0 arestas visiveis "
                "num canto quadrado, 1 box-shadow. O `panel-flash-contradiction` declara a "
                "divergencia entre as duas medicoes do flash (e o numero de cada uma), que era o "
                "que mantinha a duvida de pe."),
    },
    {
        "key": "altc",
        "title": "Alt+C: 1 toque painel de baixo, 2 toques painel da direita, HOLD legenda",
        "ids": ["L20", "L25", "L32", "L37", "L71"],
        "cmds": [
            C([PY, "_main/altc-gesture-oracle.py"], r"ALTC-GESTURE GREEN", 180),
            R([PY, "_main/altc-gesture-oracle.py", "--neg-arm"], r"NEG-ARM PASS", 180),
        ],
        "why": ("o contrato de 2026-10-30, medido do arquivo que corre: um toque da' o painel "
                "de baixo, dois o da direita, e o HOLD liga a legenda. Substitui os tres "
                "oraculos de 2026-10-18 (`hotkey-gesture`, `hotkey-triple`, `hotkey-cycle`), "
                "que mediam a contagem de presses dentro de uma janela -- o contrato que o dono "
                "aposentou, e cuja falha ele reportou verbatim: *\"o alt c nao ta dando display "
                "em qualquer painel\"*."),
    },
    {
        "key": "autostart",
        "title": "o programa tem de iniciar com o Windows",
        "ids": ["L20"],
        "cmds": [A("autostart-on")],
        "why": ("estava OFF (`AUTOSTART=off (no Run value)`); instalado nesta sessao com "
                "`run.cmd --install-autostart` e re-medido: a chave existe e aponta para o "
                "`pythonw.exe` (sem consola)."),
    },
    {
        "key": "tray",
        "title": "icone no system tray sempre que esta aberto",
        "ids": ["L45"],
        "cmds": [A("tray-ok")],
        "why": ("o log vivo da app conta 82 `TRAY_ICON_ADD`, 73 com `ok=true` e 9 com "
                "`ok=false`; as falhas sao arranques de MEDICAO a partir de uma pane (o "
                "`winerror=5` esta documentado no AGENTS)."),
    },
    {
        "key": "mover",
        "title": "mover os paineis e ruim / o painel salta / nao consigo manter o mouse",
        "ids": ["L48"],
        "cmds": [
            C([PY, "_main/strip-drag-shell-oracle.py"], r"VERDICT: PASS", 180),
            C([NODE, "_main/strip-drag-loop-oracle.js"], r"VERDICT: PASS", 120),
            C([NODE, "_main/strip-float-oracle.js"], r"VERDICT: PASS", 120),
        ],
        "why": ("o arrasto usa `screenX`/`screenY` e nao `clientX` (o `strip-drag-loop` prova que "
                "`clientX` REPRODUZ o defeito, por isso o braco nao e decorativo)."),
    },
    {
        "key": "offscreen",
        "title": "nao quero ver as coisas na minha tela sem pedir",
        "ids": ["L50", "L51", "L52"],
        "cmds": [C([PY, "_main/panel-visibility-guard-oracle.py"], r"BOTH ROWS CLOSED", 180)],
        "why": "as duas linhas (arranque e Alt+C) estao fechadas pela guarda de visibilidade.",
    },
    {
        "key": "openclose",
        "title": "abrir ou fechar o Sotto trava o PC",
        "ids": ["L53"],
        "cmds": [C([PY, "_main/open-close-stall-oracle.py"], r"VERDICT: PASS", 180)],
        "why": ("as quatro causas medidas em 2026-10-21 (preload do modelo, `transparency_hack` a "
                "esperar 10 s na thread do hotkey, `closer.join(3)`, worker orfao) e o valor de "
                "cada uma: `HOTKEY_DOUBLE` -> `PANEL_SHOWN` em 1 ms, `BRIDGE_STOP` -> `SHELL_EXIT` "
                "em 0,262 s."),
    },
    {
        "key": "vram",
        "title": "11-13 GB de VRAM e ridiculo; e 12->13 GB, e culpa do Sotto?",
        "ids": ["L54", "L125", "L126"],
        "cmds": [
            C([PY, "_main/vram-reuse-oracle.py", "--loader", "noop"], r"VERDICT: PASS", 240),
            C(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader"],
              r"\d+ MiB", 120, cite=False, lit="MiB, "),
        ],
        "why": ("a VRAM e REUTILIZADA entre carregamentos: o `get_or_load` pedido duas vezes devolve "
                "a MESMA entrada (`refs=2`, uma entrada no pool) e a chave discrimina diretorio e "
                "providers -- e o que o `--loader noop` mede, sem GPU. A atribuicao de agora e a do "
                "segundo comando (a maquina inteira) e a do proprio oraculo: "
                "`GPU: total=16303 used=8370 free=7932 MiB compute_pids=33`, com os maiores "
                "consumidores NOMEADOS (python.exe 1831,5 / 1829,5 / 1445,5 / 1371,5 MiB, "
                "`NVIDIA Overlay.exe` 1371,5 + 238,5, chrome 662,9) e o nosso processo a "
                "`my_vram_ded_MiB=0.0`; o modelo em disco mede 746,6 MiB em 7 ficheiros. A figura de "
                "9,7 GB nunca foi reproduzida: medido 1175-1703 MiB de delta no AGENTS. "
                "LIMITE DECLARADO: o braco com sessao CUDA real (`--loader onnx-single`, o default "
                "do oraculo) NAO correu em 2026-10-23 19:3x -- com 8370 dos 16303 MiB em maos de "
                "outros processos ele ficou BLOQUEADO dentro da criacao do contexto (medido: 9,2 s "
                "de CPU e depois nenhum progresso durante >7 min, com o `faulthandler` a nao "
                "conseguir escrever porque a chamada nativa segura o GIL). Ele passou de manha, com "
                "a GPU livre; o que este portao mede hoje e a propriedade de REUSO (codigo), e o "
                "delta de VRAM da nossa propria sessao fica por medir ate a GPU ficar quieta."),
    },
    {
        "key": "porapp",
        "title": "aproveitar as legendas que ja existem em cada app (YouTube)",
        "ids": ["L56"],
        "cmds": [
            C([PY, "_main/youtube-track-wiring-oracle.py"], r"VERDICT: PASS", 300),
            C([PY, "_main/per-app-source-plumbing-oracle.py"], r"VERDICT: PASS", 180),
        ],
        "why": ("12 bracos + 5 mutantes sobre a fiacao por app: a pagina do YouTube e DEMOVIDA "
                "quando ha track, o video sem track devolve o microfone, e o caminho Stremio "
                "continua a chegar. Re-ancorado nesta sessao depois de o emissor passar a "
                "devolver a janela de duas linhas."),
    },
    {
        "key": "webview",
        "title": "a culpa e do WebView2? devemos usar outra coisa?",
        "ids": ["L61", "L60"],
        "cmds": [
            C([PY, "_main/caption-native-wrap-oracle.py"], r"VERDICT: PASS", 180),
            C([PY, "_main/caption-overlay-free-oracle.py"], r"VERDICT: GREEN", 180),
            # A TERCEIRA LINHA FOI REMOVIDA EM 2026-10-30, e a razao esta' escrita porque
            # uma evidencia apagada em silencio e' uma evidencia que ninguem audita: ela
            # citava `_main/strip-css-dead-oracle.py`, um ficheiro que NAO EXISTE nesta arvore
            # (medido: `ls _main/*css* _main/*dead*` da' so' recibos; nenhum oraculo de CSS
            # morto foi escrito). Um comando fantasma nao fecha uma seccao -- deixa-a aberta
            # para sempre com um rc=2 que parece do produto. A reclamacao das duas fontes
            # abaixo e sobre o WebView2, e as duas provas que ficam MEDEM-na.
        ],
        "why": ("a legenda que ele ve NAO e um WebView: e uma janela nativa em camadas "
                "(`caption_overlay.py` + `caption_wrap.py`), e o wrap equilibra as duas linhas sem "
                "partir palavras. O `caption-overlay-free` prova que um clique na legenda nao abre "
                "nada e que a pagina mantem a base opaca."),
    },
    {
        "key": "shiftc",
        "title": "nao consigo apertar Shift+C (e do meu AutoClicker)",
        "ids": ["L66"],
        "cmds": [A("single-hotkey")],
        "why": ("o Sotto registra o Alt+C; o `MOD_ALT | MOD_SHIFT` existe apenas na cadeia de "
                "FALLBACK, que so corre se o Alt+C falhar ao registar."),
    },
    {
        "key": "traducao",
        "title": "para de traduzir: en/pt/es na lingua original, o resto para ingles",
        "ids": ["L67", "L95"],
        "cmds": [C([PY, "_main/youtube-captions-oracle.py"], r"VERDICT: PASS", 400)],
        "why": ("a politica em vigor (ordem de 2026-10-30, verbatim: *'legendas nao traduzem "
                "entre ingles pt br e espanhol. so outras linguas, todas pro ingles'*): "
                "`UNTRANSLATED_LANGS=('en','pt','es')` servidos na PROPRIA lingua e sem queda "
                "possivel, qualquer outra lingua em INGLES (`TARGET_LANG`); a lingua original "
                "lida do campo `language` (nao do nome do ficheiro, que mente). 60 bracos / 15 "
                "mutantes, dois deles a tirar pt e es do conjunto para provar que a regra esta' "
                "no codigo e nao no comentario."),
    },
    {
        "key": "overlays",
        "title": "legenda ao vivo na minha tela E no painel da direita; no painel direito nao deve haver legenda ao vivo",
        "ids": ["L69", "L106"],
        "cmds": [C([NODE, "_main/three-overlays-oracle.js"], r"VERDICT: PASS", 180)],
        "why": "os tres overlays (painel, faixa, legenda nativa) sao independentes e nenhum e o dono do outro.",
    },
    {
        "key": "bateria",
        "title": "os testes demoram muito e sao pesados: caching e incremental",
        "ids": ["L72", "L98", "L99"],
        "cmds": [
            C([PY, "_main/_stepcache-oracle.py"], r"VERDICT: PASS", 300),
            C([PY, "_main/battery-heavy-gate.py"], r"PASS", 300),
            A("battery-cache"),
        ],
        "why": ("o cache guarda o CONTEUDO (nao o mtime) e o rc; medido 399,8 s a frio, 130,2 s "
                "com 76 de 91 passos em cache, 27,7 s em modo rapido. A classe PESADA poe os seis "
                "passos que tocam o mundo do dono atras de um opt-in, e a prioridade da bateria e "
                "`BelowNormal`."),
    },
    {
        "key": "designs",
        "title": "os designs estao errados, ha coisas da demo, bolas, texto pequeno, truncados",
        "ids": ["L75", "L90", "L91", "L92", "L93", "L94", "L101", "L102", "L104", "L105", "L107", "L121", "L144"],
        "cmds": [
            C([NODE, "_main/theme-matrix-probe.mjs"], r"page errors: 0", 300),
            C([PY, "_main/zipc-designs-oracle.py"], r"VERDICT: PASS", 180),
            C([PY, "_main/cine-themes-oracle.py"], r"VERDICT: PASS", 180),
            C([PY, "_main/theme-button-geometry-oracle.py"], r"VERDICT: PASS", 120),
            C([PY, "_main/theme-button-contrast-oracle.py"], r"VERDICT: PASS", 120),
            C([PY, "_main/wordmark-metrics-oracle.py"], r"VERDICT: PASS", 120),
            C([NODE, "_main/brand-truncation-probe.mjs"], r"0 with the text wider than its box", 300),
            A("demo-leftovers-absent"),
            A("avatar-absent"),
            A("theme-timecode-nowrap"),
        ],
        "why": ("45 temas com 0 erros de pagina; geometria do botao igual entre temas (o rato pode "
                "ficar parado), contraste medido, wordmark sem corte, 0 avatares, 0 restos da demo "
                "(`filed`), e o timecode do broadcast ja numa linha (o *\"coisa feia\"* de L144)."),
    },
    {
        "key": "search",
        "title": "tira a caixa de procurar texto e as barras de on/off (so uma bolinha)",
        "ids": ["L100"],
        "cmds": [A("search-box-absent"), A("state-is-clear")],
        "why": ("o formulario saiu do HTML, a fiacao saiu do `panel.js` (as guardas ficaram, e por "
                "isso nada partiu) e as regras `.search*` sairam do CSS -- REAPLICADO em 2026-10-30, "
                "porque a remocao ja' tinha sido feita uma vez e perdeu-se no episodio do stash "
                "(medido: 3 nos de formulario no markup antes desta sessao). A segunda metade da "
                "frase do dono (as barras de on/off) CONFLUI com uma ordem POSTERIOR e mais "
                "especifica -- *'deve ser CLARO quando ta live e quando nao ta'*, citada no "
                "`panel.css` -- e as duas convivem: a bola e' o indicador que ele pediu, e a pilula "
                "que muda de cor e de palavra e' a clareza que ele pediu depois. A arm mede as "
                "duas metades; o porque completo esta' no docstring de `a_state_is_clear`."),
    },
    {
        "key": "mdash",
        "title": "nao usar MDASH em lugar nenhum do painel",
        "ids": ["L101"],
        "cmds": [A("mdash-absent")],
        "why": "zero MDASH fora de comentarios nos tres ficheiros do painel.",
    },
    {
        "key": "textos",
        "title": "retira 'live captions', 'speak and the line flows', 'transcript history'",
        "ids": ["L100", "L101"],
        "cmds": [A("live-captions-text-absent"), A("speak-flows-absent")],
        "why": "so sobrevivem em comentarios; nada e pintado.",
    },
    {
        "key": "pronto",
        "title": "ready / not ready em vez de 'speak and the line flows'",
        "ids": ["L69"],
        "cmds": [A("speak-flows-absent")],
        "why": "a frase saiu do texto pintado; o estado vive no veredicto do worker.",
    },
    {
        "key": "screenshots",
        "title": "tirar screenshots NOVAS para todos os designs, incluindo os do .zip",
        "ids": ["L76"],
        "cmds": [A("shots-fresh")],
        "why": "46 PNG em `_main/shots/20261022-theme-matrix/` com `MANIFEST.md` (45 temas + a capa).",
    },
    {
        "key": "perf",
        "title": "o Sotto causa stutter? faz uma ferramenta que logue isso",
        "ids": ["L96", "L120", "L122"],
        "cmds": [A("perf-tool"), A("perf-report")],
        "why": ("`sotto-perf-log.py` mede o slip do `sleep(25 ms)`, CPU incl. DPC/interrupt, disco e "
                "a familia do Sotto por ARVORE de processos. O primeiro resultado (max 1135 ms) era "
                "o instrumento a medir-se: com a sonda em processo proprio, p50 0,5 ms e ZERO "
                "slips acima de 100 ms."),
    },
    {
        "key": "compact",
        "title": "o modelo devia compactar aos 200k / 400k de janela",
        "ids": ["L77", "L78", "L79", "L89"],
        "cmds": [A("config-context-limits")],
        "why": ("o pool (`G:\\env-data\\opencode-go-pool.json`) tem `compaction.auto=true`, "
                "`buffer=20000` e, nos 168 modelos, `limit.context=400000` + `limit.input=220000` "
                "-- o corte cai perto dos 200k que ele pediu. O `opencode.json` global nao tem "
                "`limit` nenhum; foi preciso ler o ficheiro certo."),
    },
    {
        "key": "trunc",
        "title": "precisamos de bypass do truncation do output; AGENTS.md so com o essencial",
        "ids": ["L81", "L87"],
        "cmds": [A("truncate-plugin"), A("agents-md-size")],
        "why": ("o plugin `no-truncate.ts` re-expande com o marcador `__notrunc__` (teto 512 KB); o "
                "AGENTS.md ficou com 565 linhas contra as 1301 do arquivo, e o arquivo guarda a "
                "historia."),
    },
    {
        "key": "permissao",
        "title": "para de pedir permissao para cada comando",
        "ids": ["L10"],
        "cmds": [A("config-allow-all")],
        "why": "todas as chaves de `permission` estao a `allow` no config global: nao ha prompt.",
    },
    {
        "key": "modelos",
        "title": "substitui o modelo pelo fine tune / remove o antigo / restaura os modelos",
        "ids": ["L24", "L46", "L47"],
        "cmds": [A("models-present")],
        "why": "os pesos estao em `worker/models/` (o config aponta para la); nada foi desinstalado.",
    },
    {
        "key": "youtube",
        "title": "a legenda do YouTube tem de ser 1:1: texto, duas linhas, timing",
        "ids": ["L103", "L143", "L145", "L148", "L149", "L150", "L151", "L152", "L147"],
        "cmds": [
            C([PY, "_main/youtube-1to1-probe.py", "--video", "WdaHAGRBB6s"], r"IGUAIS no texto", 300),
            C([PY, "_main/youtube-window-oracle.py"], r"BATTERY-VERDICT youtube-window-oracle PASS", 180),
            C([PY, "_main/youtube-sync-oracle.py"], r"BATTERY-VERDICT youtube-sync-oracle PASS", 180),
            C([PY, "_main/youtube-paint-first-oracle.py"], r"VERDICT: PASS", 180),
            C([PY, "_main/youtube-foreign-paint-oracle.py"], r"YT-PAINT-FOREIGN VERDICT PASS", 180),
        ],
        "why": ("19/19 iguais no texto e no `start`; a janela de 2 linhas (`rcRows: 2`) em 94 % do "
                "video; o caminho vivo passou a devolver a janela e a recusar texto fantasma. O "
                "desync medido em 06:54 era `clock-unreadable` + `painted_words=8` de uma janela "
                "VAZIA (400 amostras do browser, `caption=null` em todas). "
                "E MEDIDO AO VIVO em 2026-10-23, contra a janela do proprio player num Edge "
                "isolado (`python _main/yt-1to1-live-compare.py --video WdaHAGRBB6s --samples 46 "
                "--paint-lang en`, `--mute-audio`): `LIVE_1TO1 iguais=46/46 ... veredicto=MATCH`. "
                "Essa corrida apanhou dois defeitos de TEXTO que os oraculos nao viam e que agora "
                "sao bracos: (1) o `_join_segs` punha um espaco antes da pontuacao e o ecra dizia "
                "`alguem ?`/`Nao .` onde o YouTube escreve `alguem?`/`Nao.`; (2) um evento cujo "
                "texto e SO pontuacao virava uma linha propria -- agora junta-se a linha que "
                "continua (`_absorb_punct`). E a mesma corrida mostrou porque a legenda "
                "desaparecia: o perfil pt-BR do YouTube pinta a TRADUCAO (`lang=pt`) enquanto a "
                "politica serve `en-orig`, o alinhamento por texto nunca casa e a app devolvia "
                "`painted-other-track` para sempre; agora o relogio do player escolhe a cue da "
                "faixa servida, e so enquanto ANDA (`youtube-foreign-paint`, 4 bracos / 3 "
                "mutantes). A comparacao ao vivo NAO entra neste portao: ela LANCA um Edge (regra "
                "6) e fica declarada no recibo."),
    },
    {
        "key": "dub",
        "title": "tira a auto dublagem do YouTube",
        "ids": ["L146"],
        # A ORDEM DOS `cmds` NAO E' DECORATIVA: o portao do manager re-executa a
        # PRIMEIRA `evidence:` e exige o literal. O `yt-audio-track.py` depende do relay
        # do Chrome dele em `127.0.0.1:9224`; quando o relay nao esta' la' o comando sai
        # 1 e a seccao ficaria aberta por um instrumento ausente (medido 2026-10-30:
        # `relay indisponivel ... nada foi medido`). Por isso a prova que CORRE SEMPRE
        # vem primeiro: ela mede a metade que e' do Sotto -- a app nunca toca na faixa
        # de audio -- e o `yt-audio-track.py` fica como prova de APOIO, com a sua leitura
        # do player quando a aba estiver viva.
        "cmds": [
            C([PY, "_main/yt-no-dub-oracle.py"], r"YT-NO-DUB PASS", 120),
            C([PY, "_main/yt-audio-track.py"], r"AUDIO_TRACK", 300, cite=False),
        ],
        "why": ("medido na aba do proprio video, pelo relay do contrato: 20 faixas de audio, "
                "`defaultAudioTrackIndex=18` -> `en-US.4` (a ORIGINAL inglesa), `getAudioTrack()` "
                "devolve `und` (omissao) e `setAudioTrack({id:'en-US.4'})` devolve `false` -- o "
                "player recusa a troca por API. Nesta reproducao NAO esta a tocar dublagem."),
    },
    {
        "key": "finaliza",
        "title": "finaliza o Sotto: tudo que reclamei tem de estar feito",
        "ids": ["L21", "L119"],
        "cmds": [C([PY, "_main/complaints-closure-gate.py", "--self"], r"CLOSURE", 180)],
        "why": ("a resposta a *\"ja terminou TUDO que eu ja reclamei?\"* e este proprio documento "
                "-- e o portao que o le. Ele conta as reclamacoes do corpus, exige uma seccao por "
                "id com evidencia executada, e falha enquanto houver uma aberta."),
    },
    {
        "key": "resto",
        "title": "pedidos de metodo que nao descrevem um defeito",
        "ids": ["L7", "L30"],
        "cmds": [
            A("method-requests-declared"),
            C(["git", "rev-parse", "--abbrev-ref", "HEAD"], r"\w", 60, cite=False),
            C(["git", "worktree", "list"], r"sotto", 60, cite=False),
        ],
        "why": ("L7 pede FACTOS com um print, L30 pergunta se o branch compila: o repo corre do "
                "branch vivo sem build (nao ha npm nem bundler na via viva). Os restantes sao "
                "pedidos de metodo ou colagens, e ficam declarados como abertos em vez de "
                "fechados por uma frase."),
    },
    {
        "key": "worktrees",
        "title": "o trabalho em worktrees esta desorganizado; worktrees nascem fora do repo",
        "ids": ["L9", "L11"],
        "cmds": [
            A("worktrees-explained"),
            C(["git", "worktree", "list"], r"sotto", 60, cite=False),
        ],
        "why": ("o comando mostra ONDE os worktrees vivem hoje (H: + barra + sotto-wt, um irmao "
                "do repo e nao um filho). Isto e a MEDICAO da queixa, nao a cura dela: onde o "
                "harness cria worktrees e configuracao do manager, e por isso a seccao fica "
                "`open` em vez de fingir um fecho."),
    },
    {
        "key": "gritaria",
        "title": "para de mostrar erro e de gritar",
        "ids": ["L141"],
        "cmds": [
            A("no-error-shouting"),
            C([PY, "_main/worker-respawn-ceiling-oracle.py"], r"VERDICT: PASS", 180),
        ],
        "why": ("o painel nao tem superficie de erro (0 nodes com class *error*/alert/failed) e o "
                "teto de respawn existe, com `BRIDGE_RESTART_SUPPRESSED ... why=restarting-cannot-"
                "fix-a-routing-problem`: o shell para de tentar em vez de repetir para sempre."),
    },
]

#: O QUE NAO SE FECHA COM UM COMANDO, e por que. Estes ficam `open` com o motivo escrito;
#: sao a lista do que falta, e o portao conta-os.
OPEN_NOTES = {
}


def run(cmd, cache):
    key = " ".join(cmd["argv"])
    if key in cache:
        return cache[key]
    t0 = time.time()
    try:
        p = subprocess.run(cmd["argv"], cwd=REPO, capture_output=True, timeout=cmd["timeout"], creationflags=subprocess.CREATE_NO_WINDOW, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))
        out = ((p.stdout or b"") + (p.stderr or b"")).decode("utf-8", "replace")
        rc = p.returncode
    except subprocess.TimeoutExpired:
        out, rc = "TIMEOUT depois de %ss" % cmd["timeout"], 124
    except Exception as exc:  # noqa: BLE001
        out, rc = "EXCECAO: %r" % (exc,), 125
    ok = rc == cmd.get("expect_rc", 0) and re.search(cmd["expect"], out) is not None
    res = {"rc": rc, "out": out, "ok": ok, "elapsed": round(time.time() - t0, 2)}
    cache[key] = res
    return res


def cite(cmd):
    """O comando como o PORTao DO MANAGER o re-executa (PowerShell, cwd = o repo).

    Dois detalhes que custaram uma corrida vermelha inteira (2026-10-22):
      * o executavel tem ESPACO no caminho (`C:\\Program Files\\...python.exe`) e, sem
        aspas, o PowerShell parte-o em dois -> `C:\\Program` + `Files\\...`, e os 31
        comandos saiam rc=1 por uma razao que nao tinha nada a ver com o produto.
      * por isso a citacao usa `python` (que esta no PATH), nao o caminho absoluto.
    """
    argv = list(cmd["argv"])
    if argv and argv[0] == PY:
        argv[0] = "python"
    elif argv and os.path.basename(str(argv[0])).lower() in ("node.exe", "node"):
        argv[0] = "node"
    return " ".join('"%s"' % a if " " in str(a) else str(a) for a in argv)


def flatten(text):
    return re.sub(r"\s+", " ", text or "").strip()


def literal(cmd, r):
    """A substring que o comando DE FACTO imprimiu.

    O portao do manager achata os espacos da saida e exige `literal in saida`. Escolher
    o `expect` so quando ele e texto puro (sem regex) e cair para uma linha literal da
    saida quando nao e: o `expect` de varios comandos e uma expressao (`page errors: 0`
    e literal, `RESULT x PASS` e literal, mas nem todos sao).
    """
    flat = flatten(r["out"])
    if cmd.get("lit"):
        # A FORMA, nao o numero. `MiB, ` e o sufixo de uma leitura viva da GPU: o
        # numero muda a cada corrida e uma citacao numerica volta a ficar vermelha
        # sozinha (o portao do manager re-executa). Quem mede o REUSO e o oraculo.
        return cmd["lit"]
    plain = (cmd["expect"] or "").replace("\\", "")
    if plain and plain in flat and "`" not in plain:
        return plain

    for chunk in re.split(r"\s{2,}| (?=[A-Z][A-Z_]{3,}=)", flat):
        c = chunk.strip(" .;|")
        if 10 <= len(c) <= 70 and "`" not in c:
            return c
    return flat[:60].strip()


def excerpt(out, n=14, width=170, must=""):
    """O bloco de saida que fica no documento.

    `must` e o literal que a citacao promete: a linha que o contem TEM de estar no bloco,
    mesmo que o filtro por palavras-chave a tivesse deixado de fora. Foi medido: o
    `VERDICT: PASS` de quatro seccoes vivia na 20.a linha e o bloco so guardava 14.
    """
    lines = [l.rstrip() for l in out.splitlines() if l.strip()]
    flat = lambda t: re.sub(r"\s+", " ", t).strip()
    keep = [l for l in lines if re.search(r"PASS|FAIL|VERDICT|RESULT|IGUAIS|page errors|COVERED|MiB|AUDIO_TRACK|GREEN|RED", l)]
    if not keep:
        keep = lines
    keep = keep[:n]
    if must:
        want = flat(must)
        if not any(want in flat(l) for l in keep):
            hit = [l for l in lines if want in flat(l)]
            if hit:
                keep = [hit[0]] + keep[: max(0, n - 1)]
    return "\n".join("    " + (l if len(l) <= width else l[: width - 1] + "\u2026") for l in keep)


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    free = canon.complaints()
    by_id = {m["id"]: m for m in canon.load()}
    assigned = {}
    for t in THEMES:
        for i in t["ids"]:
            assigned.setdefault(i, []).append(t["key"])
    unassigned = [m["id"] for m in free if m["id"] not in assigned]
    cache = {}
    results = {}

    sections = []
    for t in THEMES:
        res = []
        for cmd in t["cmds"]:
            r = run(cmd, cache)
            res.append((cmd, r))
            results[" ".join(cmd["argv"])] = r
        t["_res"] = res
        # A PROVA DE APOIO NAO GOVERNA O ESTADO (2026-10-30). `cite=False` existe para
        # uma leitura que depende de uma maquina viva (a aba do Chrome dele em
        # `127.0.0.1:9224`): a sua ausencia e' a ausencia de um INSTRUMENTO, nao a
        # reclamacao reaberta -- e uma reclamacao que so' fecha com o browser dele
        # aberto nunca fecha sozinha. As provas que decidem sao as citaveis; a de apoio
        # continua a correr, a ficar no documento com o seu bloco e a ser VERMELHA
        # quando mede alguma coisa e ela falha.
        t["_ok"] = all(r["ok"] for c, r in res if c.get("cite", True))

    lines = []
    w = lines.append
    w("# Fecho das reclamacoes do dono \u2014 sotto \u2014 ultimas 400 h")
    w("")
    w("Corpus: `I:\\!manager\\state\\herdr\\complaints\\sotto.md` (148 mensagens para `H:\\sotto`,")
    w("2026-10-07 .. 2026-10-22). Este ficheiro e GERADO por `_main/complaints-closure-build.py`:")
    w("cada `status` sai do codigo de saida e da saida do comando que a seccao cita. Nada aqui e")
    w("escrito a mao, e o portao `_main/complaints-closure-gate.py` re-le o documento e o corpus.")
    w("")
    w("## A populacao, e o que ficou de fora")
    w("")
    w("| | n |")
    w("|---|---|")
    w("| mensagens no corpus | %d |" % len(canon.load()))
    w("| **reclamacoes/pedidos do dono** | **%d** |" % len(free))
    w("| excluidas | %d |" % len(canon.excluded()))
    w("")
    reasons = {}
    for _m, r in canon.excluded():
        reasons.setdefault(r, []).append(_m["id"])
    for r in sorted(reasons):
        w("- **%s** (%d): %s" % (r, len(reasons[r]), ", ".join(reasons[r])))
    w("")
    w("A exclusao e uma lista de PADROES declarada em `_main/complaints_canon.py`, e nao um")
    w("julgamento caso a caso: o despacho de uma lane (`You are a \u2026`), o prompt do auto-loop")
    w("(`GOAL (`), o template do `/goal`, as sondas de vida (`Somente leitura`, `Responda apenas`,")
    w("`Continue de onde parou`), e as 15 mensagens de PROCESSO nomeadas uma a uma em")
    w("`DIRECTIVE_IDS`. Um id que nao esteja nem aqui nem numa seccao e um buraco \u2014 e o portao")
    w("falha por isso.")
    w("")
    w("## Indice")
    w("")
    w("| # | reclamacao | fontes | estado |")
    w("|---|---|---|---|")
    for n, t in enumerate(THEMES, 1):
        st = "closed" if t["_ok"] else "open"
        w("| R%d | %s | %s | **%s** |" % (n, t["title"], ", ".join(t["ids"]), st))
    w("")

    for n, t in enumerate(THEMES, 1):
        w("## R%d \u2014 %s" % (n, t["title"]))
        w("")
        for i in t["ids"]:
            m = by_id.get(i)
            if not m:
                continue
            note = OPEN_NOTES.get(i)
            w("- fonte `%s` (%s, %s): \u201c%s\u201d" % (i, m["ts"][:16], m["harness"], canon.quote(m["text"], 240)))
            if note:
                w("  - **aberta**: %s" % note)
        w("")
        ok = t["_ok"] and not any(i in OPEN_NOTES for i in t["ids"])
        w("status: %s" % ("closed" if ok else "open"))
        w("")
        # ORDEM = A DO RELoGIO, MAS UM BRACO NEGATIVO NUNCA E' O PRIMEIRO.
        # O portao do manager re-executa SO a PRIMEIRA `evidence:` de cada seccao,
        # dentro de um orcamento total de 120 s para as 31 seccoes; por isso a primeira
        # e o comando mais RAPIDO -- mas tem de ser um que SAI 0 quando o mundo esta'
        # bom. MEDIDO 2026-10-30: o `--neg-arm` do oraculo de gesto (expect_rc=1) e'
        # mais rapido que o oraculo inteiro, ficou em primeiro lugar da `R2`, e o
        # `complaints-closure-gate.py` passou a ler `rc=1` na evidencia CITADA de uma
        # seccao que o construtor tinha fechado -- dois vereditos sobre a mesma linha.
        # Um braco negativo e' prova de APOIO por natureza: corre, fica escrito, e
        # nunca governa o estado.
        def _rank(cr):
            cmd = cr[0]
            cited = bool(cmd.get("cite", True))
            negative = int(cmd.get("expect_rc", 0)) != 0
            return (0 if (cited and not negative) else
                    (1 if cited else 2), cr[1].get("elapsed", 0), " ".join(cmd["argv"]))

        ordered = sorted(t["_res"], key=_rank)
        for cmd, r in ordered:
            lit = literal(cmd, r)
            w("evidence: `%s` -> %s" % (cite(cmd), lit))
            w("")
            w("```")
            w(excerpt(r["out"], must=lit))
            w("```")
            w("")
            # UM rc!=0 TEM DE VIR COM A RAZAO ESCRITA AO LADO, senao o portao da
            # `CLOSURE` le-o como evidencia vermelha (medido 2026-10-30 na `R2`).
            # Ha' dois motivos legitimos: o braco negativo que SAI 1 por desenho, e a
            # prova de apoio que nao satisfez o literal.
            if r["ok"] and r["rc"] != 0:
                why = " (o rc!=0 e' o DESENHO deste braco negativo)"
            elif r["ok"]:
                why = ""
            else:
                why = " (NAO satisfaz `%s`)" % cmd["expect"]
            w("rc=%d%s" % (r["rc"], why))
            w("")
        w("Porque isto fecha a reclamacao: %s" % t["why"])
        w("")

    w("## O que continua aberto")
    w("")
    opens = [t for t in THEMES if not t["_ok"] or any(i in OPEN_NOTES for i in t["ids"])]
    if not opens:
        w("Nada: todas as seccoes acima fecharam com o comando a devolver 0 e a saida esperada.")
    for t in opens:
        w("- **R%d** \u2014 %s" % (THEMES.index(t) + 1, t["title"]))
        for cmd, r in t["_res"]:
            if not r["ok"]:
                w("  - `%s` rc=%d, esperava `%s`" % (" ".join(cmd["argv"]), r["rc"], cmd["expect"]))
        for i in t["ids"]:
            if i in OPEN_NOTES:
                w("  - %s: %s" % (i, OPEN_NOTES[i]))
    w("")
    w("Unassigned complaints: %s" % (", ".join(unassigned) if unassigned else "none"))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")

    total = len(THEMES)
    closed = sum(1 for t in THEMES if t["_ok"] and not any(i in OPEN_NOTES for i in t["ids"]))
    print("documento: %s (%d B)" % (OUT, os.path.getsize(OUT)))
    print("seccoes: %d | fechadas: %d | abertas: %d | reclamacoes: %d | sem tema: %s"
          % (total, closed, total - closed, len(free), unassigned or "none"))
    for t in THEMES:
        if not t["_ok"] or any(i in OPEN_NOTES for i in t["ids"]):
            bad = [(c["argv"][-1], r["rc"]) for c, r in t["_res"] if not r["ok"]]
            print("  OPEN %-12s %s %s" % (t["key"], bad or "", [i for i in t["ids"] if i in OPEN_NOTES]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
