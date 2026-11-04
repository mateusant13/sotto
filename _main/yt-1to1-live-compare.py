"""A LEGENDA QUE O DONO VE NO YOUTUBE, CONTRA A QUE O SOTTO RETIRA -- no mesmo instante.

O DONO, 2026-10-22, verbatim:
    *"tu vai pegar exatamente a transcricao do navegador/youtube desse video e comparar
    com o que aparece no transcript do sotto. ... a que retiramos do youtube, tem que
    bater timing, linha/quebra de linha e etc, 1:1."* (L145)
    *"e nao esquece: tu vai fazer funcionar 1:1, e tambem ter o display 1:1. e pra surgir
    palavras, quebrar linhas, usar o timing de nova linha ou nao, igual o youtube."* (L149)
    *"ta completamente fora de sync"* (L151)
    *"eu nao sei como que tu nao comparou ainda a legenda que aparece na minha tela vs o
    tempo da legenda do youtube."* (L152)

PORQUE ESTE FICHEIRO EXISTE. `_main/youtube-1to1-probe.py` compara DADOS com DADOS (o json3
do YouTube contra os cues que `fetch_track` produz) e diz, na sua propria docstring, que NAO
julga o ecra. O dono reclamou do ECRA. A metade que faltava e este ficheiro: le, no player
que esta a correr no navegador dele, a linha que o YouTube esta mesmo a DESENHAR -- o mesmo
texto que ele ve -- e compara-a, instante a instante, com o que o Sotto retiraria da mesma
tabela.

COMO, sem lançar nada: pelo relay ja vivo (`127.0.0.1:9224`), o contrato do dono. Nao arranca
servidor nem Chrome. Em MODO `edge` (o omisso) abre o SEU Edge, num perfil proprio
(`I:\cc-tmp\edge-1to1`), com `--mute-audio`: nenhuma aba do dono e tocada, e o Edge e morto
pela arvore do PID que este ficheiro lancou.

Em modo `relay` o contrato e OUTRO, e o paragrafo antigo dizia-o ao contrario: ele NAVEGA a aba
do dono para a URL do video, chama `Page.bringToFront`, e depois `seekTo(0)` + `playVideo()`
poem o video a tocar. `pick_tab` NAO abre aba nenhuma -- escolhe uma que ja existe (a pagina
inicial do YouTube primeiro, senao a primeira aba de video), porque o relay nao endereca o id
de `Target.createTarget` e `/json/new` responde 405. Por isso, desde 2026-10-27, esse modo
RECUSA correr sem `--allow-playback-control`: uma medicao que poe o video do dono a tocar tem
de ser pedida por nome, nunca ser o caminho omisso de um script.

O QUE COMPARA, exactamente:
  * o TEXTO desenhado (as `.ytp-caption-segment` de cada `.caption-window`, por linha);
  * o INSTANTE, que e o relogio do proprio player (`getCurrentTime`) e nao um relogio nosso;
  * a JANELA (quantas linhas ao mesmo tempo) e o `rcRows`/`ccCols` que o payload declara.

E ESCOLHE A FAIXA POR MEDICAO: busca os candidatos e serve aquele cujas linhas CONTEM o que o
player desenhou. Uma "preferencia de lingua" nao pode decidir isto -- foi assim que o dono
comparou portugues com ingles (2026-10-20).

    python _main\\yt-1to1-live-compare.py --video WdaHAGRBB6s
    python _main\\yt-1to1-live-compare.py --video WdaHAGRBB6s --samples 16 --json I:\\cc-tmp\\c.json

Sai 0 quando TODAS as amostras batem (texto e janela), 1 quando alguma nao bate, 2 quando nao
foi possivel medir (sem relay, sem aba, sem payload) -- uma medicao ausente nao e um veredicto.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "app", "webview"))

RELAY = "http://127.0.0.1:9224/json/list"
DRIVER = r"I:\!manager\tools\ext-reload-cdp.mjs"
WORKDIR = r"I:\!manager"

#: O video das reclamacoes de 2026-10-22; `--video` muda-o.
TARGET_VIDEO = "WdaHAGRBB6s"

#: O que se le depois de cada salto. O driver tem um limite de **18 s** por
#: `Runtime.evaluate` (medido: um laco de 12 amostras dentro de um so `--await` deu
#: `timeout Runtime.evaluate`), por isso o laco vive em Python: um salto, uma leitura.
#: O player fica PAUSADO, logo `getCurrentTime()` nao anda entre as duas chamadas -- o
#: instante em que o texto e lido E o instante que se pediu.
#: LIGAR O CC -- A TOCAR, ANTES do setup. MEDIDO 2026-10-23: `toggleSubtitles()` com o
#: player ja pausado muda o `aria-pressed` para `true` e NAO pinta nada (44 amostras seguidas
#: vazias); o mesmo toggle com o video a tocar pinta em todas as amostras seguintes. Por isso
#: o ligar acontece aqui, com a pagina ainda no autoplay, e o setup so LE o estado.
CC_JS = r"""
(async function(){
  var mp = document.getElementById('movie_player');
  if (!mp) return JSON.stringify({error: 'no-player'});
  function ccOn() {
    var b = document.querySelector('.ytp-subtitles-button');
    return !!(b && b.getAttribute('aria-pressed') === 'true');
  }
  var before = ccOn(), tries = 0;
  while (!ccOn() && tries < 3) {
    try { mp.toggleSubtitles(); } catch (e) {}
    await new Promise(function (res) { setTimeout(res, 900); });
    tries++;
  }
  if (!before && ccOn()) {
    try { mp.pauseVideo(); } catch (e) {}
    await new Promise(function (res) { setTimeout(res, 250); });
    try { mp.playVideo(); } catch (e) {}
    await new Promise(function (res) { setTimeout(res, 900); });
  }
  return JSON.stringify({cc_before: before, cc_now: ccOn(), tries: tries});
})()
"""

#: Escolher a faixa que o player pinta -- para comparar o MESMO idioma que a app serve.
#: MEDIDO 2026-10-23: o perfil de um Edge novo abre a UI em pt-BR e o YouTube escolhe a
#: TRADUCAO automatica (`lang="pt"` na janela do player), enquanto a app serve o original
#: (`en-orig`, a politica do dono). Comparar pt contra en mede a POLITICA, nao a fidelidade:
#: com `--paint-lang en` o player pinta a faixa que a app serve e as duas tabelas sao a MESMA.
SET_TRACK_JS = (
    "(function(){var mp=document.getElementById('movie_player');"
    "if(!mp) return JSON.stringify({error:'no-player'});"
    "try{mp.setOption('captions','track',{languageCode:%(lang)s});}"
    "catch(e){return JSON.stringify({error:String(e)})}"
    "var cur=null;try{cur=mp.getOption('captions','track');}catch(e){}"
    "return JSON.stringify({lang:(cur&&cur.languageCode)||''});})()")

SETUP_JS = r"""
(async function(){
  var mp = document.getElementById('movie_player');
  if (!mp || !mp.getDuration) return JSON.stringify({error: 'no-player'});
  var dur = mp.getDuration();
  if (!(dur > 0)) return JSON.stringify({error: 'no-duration'});
  // MUDO E PARADO ANTES DE QUALQUER OUTRA COISA. O dono, 2026-10-23: *"nao quero ouvir o
  // audio. tenta nao fazer eu ouvi enquanto o sistema ainda escuta"*. Sao a PRIMEIRA
  // instrucao, nao a ultima: um seek num player a tocar faz som.
  var wasMuted = false, wasTime = 0, wasState = 0;
  try { wasMuted = mp.isMuted(); } catch (e) {}
  try { wasTime = mp.getCurrentTime(); } catch (e) {}
  try { wasState = mp.getPlayerState(); } catch (e) {}
  try { mp.mute(); } catch (e) {}
  try { mp.pauseVideo(); } catch (e) {}
  var vd = {}; try { vd = mp.getVideoData() || {}; } catch (e) {}
  var pr = {}; try { pr = mp.getPlayerResponse() || {}; } catch (e) {}
  var r = ((pr.captions || {}).playerCaptionsTracklistRenderer || {});
  var tracks = (r.captionTracks || []).map(function (c) {
    return {lang: c.languageCode, kind: c.kind, vss: c.vssId,
            name: (c.name && c.name.simpleText) || '', url: c.baseUrl || ''};
  });
  // O BOTAO CC E A VERDADE. `getOption('captions','track')` sobrevive ao CC desligado --
  // MEDIDO 2026-10-23: o objecto da faixa estava preenchido e o contentor vazio, porque quem
  // diz se o YouTube DESENHA e `aria-pressed` do botao `.ytp-subtitles-button`. O LIGAR vive
  // no CC_JS, ANTES deste setup: ligar a legenda com o player ja PAUSADO nao pinta nada
  // (medido: 44 amostras seguidas vazias com `cc=true`), e ligar a tocar pinta.
  function ccOn() {
    var b = document.querySelector('.ytp-subtitles-button');
    return !!(b && b.getAttribute('aria-pressed') === 'true');
  }
  var on = ccOn(), forced = false, tries = 0;
  var trackLang = '';
  try { var cur = mp.getOption('captions', 'track'); trackLang = (cur && cur.languageCode) || ''; } catch (e) {}
  window.__sotto = {wasMuted: wasMuted, wasTime: wasTime, wasState: wasState,
                    dur: dur, captionsOn: on};
  return JSON.stringify({video_id: vd.video_id || '', title: vd.title || '', dur: dur,
                         visibility: document.visibilityState,
                         tracks: tracks, win: r.wpWinPositions || [],
                         captions_on: on, cc_tries: tries, track_lang: trackLang,
                         forced_track: forced, wasMuted: wasMuted});
})()
"""

READ_CAPTION_JS = r"""
(function(){
  var mp = document.getElementById('movie_player');
  var wins = [].slice.call(document.querySelectorAll(
    '.ytp-caption-window-container .caption-window'));
  // DUAS LEITURAS, PORQUE O DESENHO TEM DUAS CAMADAS. `lines` e o texto de cada janela
  // (o que se ve), `segs` sao os SEGMENTOS -- e a janela em modo rollup tem um segmento
  // por LINHA (medido 2026-10-23: `>> Entao esta espada e inutil.` e `>> Nao` vinham em
  // dois segmentos da MESMA janela). Comparar a janela colada contra uma lista de linhas
  // dava `NAO` por construcao; a lista de segmentos e o que se pode comparar 1:1.
  var lines = wins.map(function (w) {
    return [].slice.call(w.querySelectorAll('.ytp-caption-segment'))
      .map(function (s) { return s.textContent; }).join(' ');
  }).filter(function (x) { return String(x).trim() !== ''; });
  var segs = [];
  wins.forEach(function (w) {
    [].slice.call(w.querySelectorAll('.ytp-caption-segment')).forEach(function (s) {
      var txt = s.textContent;
      if (String(txt).trim() === '') { return; }
      // A LINHA QUE SAI FICA NO DOM A ANIMAR-SE. MEDIDO 2026-10-23: em duas transicoes o
      // contentor tinha TRES segmentos -- o das cues vivas e um que ja nao esta vivo -- e
      // por isso a leitura de `segs` sem opacidade contava uma linha de mais. O `opacity`
      // diz se a linha esta no ecra: a que sai vai a 0.
      var el = s, op = 1;
      while (el && el !== w) {
        var st = window.getComputedStyle(el);
        if (st && st.opacity !== '' && st.opacity !== '1') { op = parseFloat(st.opacity); }
        if (op < 1) { break; }
        el = el.parentElement;
      }
      // A TERCEIRA LINHA ESTA NO DOM, MAS FORA DA CAIXA. MEDIDO 2026-10-23: em seis
      // transicoes o contentor tinha TRES segmentos com opacidade 1; a janela tem
      // `overflow: hidden` e a linha que rola para fora fica FORA do rect da janela. O que
      // o dono ve e o que esta DENTRO da caixa -- e o modelo de duas linhas so pode ser
      // acusado se uma linha VISIVEL ficar de fora.
      var vis = false;
      try {
        var sr = s.getBoundingClientRect(), wr = w.getBoundingClientRect();
        vis = (sr.height > 0 && sr.bottom > wr.top + 1 && sr.top < wr.bottom - 1);
      } catch (e) { vis = true; }
      segs.push({t: txt, o: (isNaN(op) ? 1 : op), v: vis,
                 l: (w.getAttribute('lang') || '')});
    });
  });
  var t = null, state = null;
  try { t = mp.getCurrentTime(); } catch (e) {}
  try { state = mp.getPlayerState(); } catch (e) {}
  return JSON.stringify({t: t, lines: lines, segs: segs, state: state});
})()
"""

#: TOCAR, MUDO. MEDIDO 2026-10-23: com o player PAUSADO o YouTube nao pinta legenda
#: nenhuma -- 10 amostras seguidas voltaram vazias com `cc=true`, `track_lang=pt` e
#: `visibility=visible`; a tocar (state=1) a janela aparece em todas. O som morre no
#: `--mute-audio` do Edge e no `mp.mute()` que ja correu no setup.
PLAY_JS = r"""
(function(){
  var mp = document.getElementById('movie_player');
  try { mp.mute(); } catch (e) {}
  // DO INICIO: a pagina autoplay-a enquanto se espera pelo player, logo o setup apanha o
  // video ja a meio (medido: t=5,7 s) e a primeira linha do video nunca seria comparada.
  try { mp.seekTo(0, true); } catch (e) {}
  try { mp.playVideo(); } catch (e) {}
  return JSON.stringify({ok: true, t: (function(){ try { return mp.getCurrentTime(); }
                                                  catch (e) { return null; } })()});
})()
"""

SEEK_JS = ("(function(){var mp=document.getElementById('movie_player');"
           "try{mp.seekTo(%(t).3f, true);}catch(e){return JSON.stringify({error:String(e)})}"
           "return JSON.stringify({ok:true, t:mp.getCurrentTime()});})()")

RESTORE_JS = r"""
(function(){
  var mp = document.getElementById('movie_player');
  var st = window.__sotto || {};
  try { mp.seekTo(st.wasTime || 0, true); } catch (e) {}
  try { if (!st.wasMuted) mp.unMute(); } catch (e) {}
  if (!st.captionsOn) { try { mp.toggleSubtitles(); } catch (e) {} }
  try { if (st.wasState === 1) mp.playVideo(); } catch (e) {}
  return JSON.stringify({restored: true});
})()
"""


def relay_tabs():
    with urllib.request.urlopen(RELAY, timeout=6) as fh:
        return json.load(fh)


#: O EDGE DO DONO, `--mute-audio`, num PERFIL PROPRIO. O dono, 2026-10-23: *"abre essa merda no
#: edge e muta o edge de algum jeito q eu nao escute mas o sistema sim. eu nao to usando o edge
#: entao tu pode fazer mais oq tu quiser."*
#:
#: Porque nao o relay do Chrome: MEDIDO 2026-10-23 -- numa aba em SEGUNDO PLANO o contentor de
#: legendas do player fica VAZIO (`html: ""`) mesmo com a faixa `en` escolhida e o video a tocar,
#: porque o renderizador nao pinta em aba escondida; e `Page.bringToFront` no relay mexia na aba
#: que o dono tem aberta. Um Edge proprio resolve as duas coisas: a aba esta a frente, e o som
#: morre no `--mute-audio` do PROPRIO browser -- o sistema dele fica como estava.
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
EDGE_PROFILE = r"I:\cc-tmp\edge-1to1"
_DRIVER_ENV = None
_EDGE_PROC = None
_YC = None


def start_edge(port=9333):
    """Lanca o Edge isolado e devolve o websocket do browser (CDP)."""
    global _DRIVER_ENV, _EDGE_PROC
    os.makedirs(EDGE_PROFILE, exist_ok=True)
    args = [EDGE,
            "--remote-debugging-port=%d" % port,
            "--user-data-dir=%s" % EDGE_PROFILE,
            "--mute-audio",
            "--no-first-run",
            "--no-default-browser-check",
            "--autoplay-policy=no-user-gesture-required",
            "--window-size=1280,800",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "about:blank"]
    _EDGE_PROC = subprocess.Popen(args, creationflags=0x08000000)  # CREATE_NO_WINDOW
    for _ in range(60):
        time.sleep(0.5)
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/json/version" % port, timeout=3) as fh:
                ws = json.load(fh).get("webSocketDebuggerUrl")
            if ws:
                _DRIVER_ENV = dict(os.environ, EXT_RELOAD_CDP=ws)
                return ws, ""
        except Exception:  # noqa: BLE001
            continue
    return None, "edge nao abriu o CDP em %d s" % 30


def edge_pages(port=9333):
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/json/list" % port, timeout=5) as fh:
            return [t for t in json.load(fh) if t.get("type") == "page"]
    except Exception:  # noqa: BLE001
        return []


def stop_edge():
    """Mata SO a arvore do Edge que este ficheiro lancou -- pelo PID dele, nunca por nome."""
    global _EDGE_PROC
    if _EDGE_PROC is None:
        return
    pid = _EDGE_PROC.pid
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception:  # noqa: BLE001
        pass
    try:
        _EDGE_PROC.wait(timeout=10)
    except Exception:  # noqa: BLE001
        pass
    _EDGE_PROC = None


def driver(args, timeout=180):
    p = subprocess.run(["bun", DRIVER] + args, cwd=WORKDIR,
                       capture_output=True, timeout=timeout, env=_DRIVER_ENV, creationflags=subprocess.CREATE_NO_WINDOW)
    raw = ((p.stdout or b"") + (p.stderr or b"")).decode("utf-8", "replace")
    for line in reversed(raw.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except ValueError:
                continue
    return {"ok": False, "error": raw.strip()[:300]}


def pick_tab(tabs, want=None):
    """A aba onde medir, e a URL a que ela volta no fim.

    MEDIDO 2026-10-23: `Target.createTarget` devolve um id CDP CRU (`0CDD…`) que o relay
    NAO endereca -- o relay usa ids proprios (`PAGEotrfs8JA.…`) e `attachToTarget` com o
    id cru falha com `-32000 No target with id`. E `/json/new` responde **405** (o relay e
    um CDP restrito). Logo nao se abre aba: usa-se uma que ja existe, e DEVOLVE-SE a URL
    dela no fim. A primeira escolha e a PAGINA INICIAL do YouTube -- a que ninguem esta a
    ver -- e so depois uma aba de video.
    """
    if want:
        for t in tabs:
            if t.get("id") == want:
                return t, t.get("url") or "https://www.youtube.com/"
        return None, None
    yt = [t for t in tabs if "youtube.com" in (t.get("url") or "")]
    home = [t for t in yt if (t.get("url") or "").rstrip("/") == "https://www.youtube.com"]
    if home:
        return home[0], home[0].get("url")
    if yt:
        return yt[0], yt[0].get("url")
    return None, None


def norm(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def fetch_json3(url, timeout=45):
    """O payload da faixa em json3.

    O `baseUrl` que o player devolve NAO traz `fmt`: sem o parametro o endpoint de
    timedtext responde **XML**, e `parse_json3` devolve ZERO cues para todas as faixas --
    foi o que a primeira corrida deste ficheiro mediu (`cues: 0` em 20 candidatas).
    `fmt=json3` e o que o proprio player acrescenta.
    """
    u = str(url or "")
    if "fmt=" not in u:
        u += ("&" if "?" in u else "?") + "fmt=json3"
    req = urllib.request.Request(u, headers={
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"),
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        return fh.read().decode("utf-8", "replace")


def painted_cues(info, lang, timeout=45):
    """As cues da faixa que o PLAYER esta a pintar, achadas pela lingua que ele declara.

    O player diz `lang="pt"` na sua propria janela (e `getOption('captions','track')` diz o
    mesmo). O yt-dlp tem essa lingua em `automatic_captions`/`subtitles`. A traducao tem
    URL propria (`tlang=`), logo as cues vem no idioma pintado -- e sao essas que se comparam
    com o que esta no ecra. Devolve [] quando nao ha entrada para a lingua.
    """
    want = str(lang or "").lower().split("-")[0].strip()
    if not want:
        return []
    for table in (info.get("subtitles") or {}, info.get("automatic_captions") or {}):
        for key, entries in (table or {}).items():
            if str(key).lower().split("-")[0] != want:
                continue
            for entry in entries or ():
                url = (entry or {}).get("url")
                if not url:
                    continue
                try:
                    cues = yc_parse(fetch_json3(url, timeout))
                except Exception:  # noqa: BLE001
                    continue
                if cues:
                    return cues
    return []


def yc_parse(raw):
    """`parse_json3` do app, sem importar o modulo outra vez."""
    global _YC
    if _YC is None:
        import youtube_captions as _mod
        _YC = _mod
    return _YC.parse_json3(raw)



def segs_text(sample, min_op=0.05):
    """Os segmentos que estao NO ECRA, na ordem -- a linha que sai (opacidade a 0) nao conta.

    Duas exclusoes medidas, ambas de coisas que estao no DOM e nao sao a legenda:
      * `o` -- a linha que esta a sair vai a opacidade 0;
      * `v` -- a linha que rola para fora fica FORA do rect da janela (`overflow: hidden`);
      * `l` -- a JANELA DE DICA que o YouTube desenha ao ligar o CC ("Ingles (gerada
        automaticamente)", "Clique em para configuracoes") nao tem `lang`; a legenda tem.
        O filtro por `lang` so vale quando ALGUMA janela o traz, para uma mudanca do
        YouTube nao apagar a medicao inteira.
    """
    items = [it for it in (sample.get("segs") or ()) if isinstance(it, dict)]
    if any((it.get("l") or "") for it in items):
        items = [it for it in items if (it.get("l") or "")]
    out = []
    for item in items:
        if isinstance(item, dict):
            try:
                op = float(item.get("o") if item.get("o") is not None else 1.0)
            except (TypeError, ValueError):
                op = 1.0
            if op <= min_op:
                continue
            # `v` = a linha esta DENTRO da caixa da janela (a que rola para fora nao conta).
            if item.get("v") is False:
                continue
            txt = item.get("t")
        else:
            txt = item
        if norm(txt):
            out.append(norm(txt))
    return out


def line_matches(theirs, ours):
    """A linha do YouTube e a nossa sao o MESMO desenho?

    DENTRO DE UMA CUE O YOUTUBE ESCREVE A LINHA A CRESCER: medido 2026-10-23 no Edge,
    `Você já` -> `Você já teve que` -> `Você já teve que matar alguem` no mesmo segundo e
    meio, e a tabela do json3 tem a linha INTEIRA desde o inicio da cue (o payload so diz
    quando a linha comeca e acaba). Logo ser PREFIXO e o mesmo desenho, nao divergencia --
    comparar o texto final a meio da cue acusaria um defeito que nao existe. O que se mede
    aqui e a JANELA (que linhas, em que ordem, em que instante) e o TEXTO FINAL.
    """
    tn, on = norm(theirs), norm(ours)
    if tn == on:
        return True
    return bool(tn) and on.startswith(tn)


def window_class(theirs, ours, t, cues):
    """A janela do YouTube e a nossa sao o MESMO desenho? (com a animacao dele contada)

    Tres jeitos MEDIDOS (2026-10-23, Edge, `WdaHAGRBB6s`) de o DOM nao bater com a lista
    de linhas SEM haver defeito nosso:
      * `dom-3`  -- a linha que rola para fora ainda esta no DOM e dentro da caixa durante a
                    animacao; o que se compara e o FIM da lista do YouTube;
      * `lag`    -- o YouTube ainda NAO pintou a linha que acabou de comecar (a nossa tabela
                    ja a tem, porque o payload diz que esta viva) -- o atraso e a animacao
                    dele, e mede-se: 0,45 s;
      * `prefix` -- a linha a ser escrita palavra a palavra (o texto final e o mesmo).
    Qualquer outra coisa e `diverge`.
    """
    if theirs == ours:
        return 'igual'
    if len(theirs) > len(ours) and all(
            line_matches(a, b) for a, b in zip(theirs[-len(ours):], ours)):
        return 'dom-3'
    if (len(ours) == len(theirs) and len(ours) > 1
            and all(line_matches(a, b) for a, b in zip(theirs[1:], ours[:-1]))):
        cue = _cue_of(ours[-1], cues)
        if cue is not None and 0.0 <= (t - float(cue.get("start") or 0.0)) <= 0.45:
            return 'lag'
    if len(ours) == len(theirs) and all(line_matches(a, b) for a, b in zip(theirs, ours)):
        return 'prefix'
    return 'diverge'


def _cue_of(text, cues):
    for c in cues or ():
        if norm(c.get("text")) == norm(text):
            return c
    return None


#: AS ANCORAS DO BLOCO DE AMOSTRAGEM, construidas por concatenacao DE PROPOSITO.
#: Escritas inteiras, apareciam no proprio codigo do detector e `src.find()` encontrava
#: esse literal PRIMEIRO: MEDIDO 2026-10-27 -- tres ocorrencias de `samples = []`, duas
#: delas dentro de `_sampler_seeks`/`selfcheck`, e a fatia saia com 43 caracteres
#: (`ini = src.find(...)`), logo `amostragem_salta=False` para sempre e o portao vermelho
#: por construcao. Partir as strings pela metade e o que impede o detector de se ler a si.
_LOOP_INI = 'driver(["--target", tid, "--expr", PLAY_JS])' + "\n        samples = " + "[]"
_LOOP_FIM = '        data["samples"] = ' + "samples"


def _sampling_block(src):
    """`(ini, fim)` do laco que amostra, ou `(-1, -1)`.

    UMA definicao do bloco, usada pelo detector e pelo portao. Duas havia -- e a segunda
    apontava para outra coisa (`selfcheck` procurava os mesmos literais que o detector
    contem), que e como um portao passa a medir-se a si mesmo.
    """
    ini = src.find(_LOOP_INI)
    if ini < 0:
        return -1, -1
    fim = src.find(_LOOP_FIM, ini)
    if fim <= ini:
        return -1, -1
    return ini, fim


def _sampler_seeks(src):
    """A amostragem deste ficheiro pede `SEEK_JS` (salta) antes de cada leitura?

    O CABECALHO PROMETE-O: "percorre o video a saltos (`seekTo`) e le a janela de
    legendas depois de cada". Sem o salto a amostra fica onde o relogio de parede a
    apanhou, e num player a bufferizar isso e o principio do video.
    """
    ini, fim = _sampling_block(src)
    if ini < 0:
        return None
    return "SEEK_JS %" in src[ini:fim]


def selfcheck():
    """Portao do instrumento: a amostragem salta, e o detector apanha quem deixar de saltar."""
    with open(__file__, "r", encoding="utf-8") as fh:
        src = fh.read()
    ini, fim = _sampling_block(src)
    ok = _sampler_seeks(src)
    if ok is None:
        print("SELFCHECK FAIL: nao encontrei o bloco de amostragem neste ficheiro")
        return 2
    # BRACO NEGATIVO: tirada a linha do salto, o detector TEM de dizer que nao salta.
    block = src[ini:fim]
    mutated = "\n".join(ln for ln in block.splitlines() if "SEEK_JS %" not in ln)
    neg = _sampler_seeks(src[:ini] + mutated + "\n" + src[fim:])
    print("SELFCHECK amostragem_salta=%s neg_arm_salta=%s" % (ok, neg))
    if ok is True and neg is False:
        print("SELFCHECK PASS")
        return 0
    print("SELFCHECK FAIL: a amostragem nao salta, ou o detector nao a distingue")
    return 2


def main(argv=None):
    ap = argparse.ArgumentParser(description="YouTube desenhado vs Sotto retirado, no mesmo instante")
    ap.add_argument("--video", default=TARGET_VIDEO)
    ap.add_argument("--samples", type=int, default=12)
    ap.add_argument("--every", type=float, default=0.6,
                    help="segundos entre leituras enquanto o video toca")
    ap.add_argument("--json", default=None)
    ap.add_argument("--tab", default=None, help="id do alvo no relay (por omissao: a pagina inicial do YouTube)")
    ap.add_argument("--browser", choices=("edge", "relay"), default="edge",
                    help="edge = um Edge proprio, --mute-audio (por omissao); relay = a aba do dono")
    ap.add_argument("--edge-port", type=int, default=9333)
    ap.add_argument("--paint-lang", default=None,
                    help="forca a faixa que o PLAYER pinta (ex.: en) -- para comparar o mesmo idioma")
    ap.add_argument("--keep-open", action="store_true", help="nao mata o Edge no fim (depuracao)")
    ap.add_argument("--allow-playback-control", action="store_true",
                    help="relay: OBRIGATORIO para tocar na aba do dono (navega, poe a frente, "
                         "da seekTo(0) e playVideo); sem esta bandeira o modo relay RECUSA")
    ap.add_argument("--selfcheck", action="store_true",
                    help="verifica (estatico, sem browser) que a amostragem SALTA com SEEK_JS; "
                         "traz o braco negativo")
    args = ap.parse_args(argv)
    if args.selfcheck:
        return selfcheck()
    # O PORTAO. Modo relay mexe na aba do DONO: navega-a para a URL, poe-na a frente, da
    # `seekTo(0)` e `playVideo()`. MEDIDO 2026-10-27 no codigo: `pick_tab` escolhe uma aba
    # que ja existe (nao abre nenhuma) e `RESTORE_JS` so devolve o play se `wasState === 1`
    # foi lido ANTES -- leitura que o fluxo faz depois de `CC_JS`. Logo um video PAUSADO
    # pode sair a tocar. Recusar por omissao e o unico estado seguro; quem quiser o contrario
    # pede-o por nome.
    if args.browser == "relay" and not args.allow_playback_control:
        print("LIVE_1TO1 REFUSED -- o modo relay controla a aba do DONO "
              "(navega, Page.bringToFront, seekTo(0), playVideo(), toggleSubtitles).")
        print("LIVE_1TO1 nada foi tocado e nada foi medido. Se for mesmo isso que se quer, "
              "passe --allow-playback-control.")
        print("LIVE_1TO1 o caminho omisso (`--browser edge`) abre um Edge proprio e mudo e "
              "nao toca em aba nenhuma dele.")
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    import youtube_captions as yc
    import youtube_window as yw

    if args.browser == "edge":
        ws, err = start_edge(args.edge_port)
        if not ws:
            print("LIVE_1TO1 %s -- nada foi medido" % err)
            return 2
        print("LIVE_1TO1 edge cdp=%s (perfil %s, --mute-audio)" % (ws[:48], EDGE_PROFILE))
        pages = edge_pages(args.edge_port)
        if not pages:
            print("LIVE_1TO1 edge sem pagina")
            return 2
        tid = pages[0]["id"]
        back = "about:blank"
        print("LIVE_1TO1 aba alvo=%s (%s)" % (tid[:18], (pages[0].get("url") or "")[:40]))
    else:
        tabs = None
        try:
            tabs = relay_tabs()
        except Exception as exc:  # noqa: BLE001
            print("LIVE_1TO1 relay indisponivel (%r) -- nada foi medido" % (exc,))
            return 2
        if not tabs:
            print("LIVE_1TO1 relay sem abas -- nada foi medido")
            return 2
        print("LIVE_1TO1 relay abas=%d" % len(tabs))

        tab, back = pick_tab(tabs, args.tab)
        if tab is None:
            print("LIVE_1TO1 nenhuma aba do YouTube no relay -- nada foi medido")
            return 2
        tid = tab["id"]
        print("LIVE_1TO1 aba alvo=%s (%s) -- volta a %s no fim"
              % (tid, (tab.get("url") or "")[:55], (back or "")[:55]))

    url = "https://www.youtube.com/watch?v=%s" % args.video
    try:
        nav = driver(["--target", tid, "--navigate", url, "--wait-href", args.video])
        # A ABA TEM DE ESTAR A FRENTE. MEDIDO 2026-10-23: em segundo plano o contentor de
        # legendas fica VAZIO (`html: ""`) mesmo com a faixa `en` escolhida e o video a
        # tocar -- o renderizador nao pinta numa aba escondida, e a comparacao mediria
        # nada. `Page.bringToFront` activa a aba (o som fica no mudo do sistema).
        driver(["--target", tid, "--call", "Page.bringToFront"])
        print("LIVE_1TO1 navegou: %s" % (args.video,))
        # o player leva segundos a montar
        ready = None
        for _ in range(30):
            time.sleep(1.0)
            ready = driver(["--target", tid, "--expr",
                            "JSON.stringify({mp:!!document.getElementById('movie_player'),"
                            "dur:(function(){try{return document.getElementById('movie_player')"
                            ".getDuration()}catch(e){return null}})()})"])
            try:
                val = json.loads(ready.get("value") or "{}")
            except ValueError:
                val = {}
            if val.get("mp") and (val.get("dur") or 0) > 0:
                break
        else:
            print("LIVE_1TO1 player nao ficou pronto: %s" % (nav.get("error") or ready))
            return 2
        setup = driver(["--target", tid, "--expr", CC_JS, "--await"])
        if not setup.get("ok"):
            print("LIVE_1TO1 cc falhou: %s" % setup.get("error"))
        else:
            print("LIVE_1TO1 cc: %s" % (setup.get("value") or "")[:120])
        if args.paint_lang:
            got = driver(["--target", tid, "--expr",
                          SET_TRACK_JS % {"lang": json.dumps(args.paint_lang)}])
            print("LIVE_1TO1 faixa do player forcada: %s" % (got.get("value") or "")[:120])
            time.sleep(1.5)
        setup = driver(["--target", tid, "--expr", SETUP_JS, "--await"])
        if not setup.get("ok"):
            print("LIVE_1TO1 setup falhou: %s" % setup.get("error"))
            return 2
        data = json.loads(setup.get("value") or "{}")
        if data.get("error"):
            print("LIVE_1TO1 sem medicao: %s" % data["error"])
            return 2
        dur = float(data.get("dur") or 0)
        driver(["--target", tid, "--expr", PLAY_JS])
        samples = []
        target = max(1, args.samples)
        #: A AMOSTRAGEM E A SALTOS, como o cabecalho deste ficheiro promete -- e NAO pelo
        #: relogio de parede. MEDIDO 2026-10-26: a tocar e sem `seekTo`, o video andou 1,5 s
        #: de `currentTime` em 24 s de parede (buffering); as 40 amostras ficaram todas em
        #: t=3,3..4,8 s -- anuncio/entrada, `cc=True` e janela vazia -- e o instrumento
        #: devolveu "nada medido" (rc=2) em vez de uma medicao. O instante de cada amostra
        #: passa a ser ESCOLHIDO (grelha sobre `dur`), nao o que o player calhou de atingir.
        span = max(0.0, dur - 0.6)
        step = (span / float(target - 1)) if target > 1 else 0.0
        deadline = time.time() + target * (3.0 + max(0.0, args.every)) + 20
        while len(samples) < target and time.time() < deadline:
            i = len(samples)
            at = min(span, step * i) if span > 0 else 0.0
            if span > 0:
                try:
                    driver(["--target", tid, "--expr", SEEK_JS % {"t": at}])
                except Exception:  # noqa: BLE001
                    pass
                # o contentor de legendas so repinta depois de o salto assentar
                time.sleep(max(0.0, args.every))
            got = driver(["--target", tid, "--expr", READ_CAPTION_JS])
            try:
                val = json.loads(got.get("value") or "{}")
            except ValueError:
                val = {}
            samples.append({"t": val.get("t"), "asked": round(at, 3),
                            "lines": val.get("lines") or [],
                            "segs": val.get("segs") or [], "state": val.get("state")})
            if val.get("state") == 0 and float(val.get("t") or 0) >= dur - 0.6:
                break
        data["samples"] = samples
    finally:
        # O ESTADO DO DONO VOLTA SEMPRE -- mudo, instante, legenda, e a URL da aba.
        try:
            driver(["--target", tid, "--expr", RESTORE_JS], timeout=60)
        except Exception:  # noqa: BLE001
            pass
        if back:
            try:
                driver(["--target", tid, "--navigate", back], timeout=60)
                print("LIVE_1TO1 aba devolvida a %s" % back[:60])
            except Exception as exc:  # noqa: BLE001
                print("LIVE_1TO1 nao consegui devolver a aba: %r" % (exc,))
        if args.browser == "edge" and not args.keep_open:
            stop_edge()
            print("LIVE_1TO1 edge fechado (a arvore do PID que abrimos)")

    if data.get("error"):
        print("LIVE_1TO1 sem medicao: %s" % data["error"])
        return 2
    samples = data.get("samples") or []
    tracks = data.get("tracks") or []
    print("LIVE_1TO1 video=%s (%s) dur=%.1fs amostras=%d faixas=%d"
          % (data.get("video_id"), (data.get("title") or "")[:42], float(data.get("dur") or 0),
             len(samples), len(tracks)))
    print("LIVE_1TO1 legenda no player: cc=%s (tries=%d) track_lang=%s visibility=%s"
          % (data.get("captions_on"), data.get("cc_tries") or 0,
             data.get("track_lang") or "-", data.get("visibility") or "-"))
    if not samples:
        print("LIVE_1TO1 nenhuma amostra")
        return 2
    if not any(s.get("lines") for s in samples):
        # NADA DESENHADO NAO E UM VEREDICTO: e uma medicao que nao aconteceu.
        for s0 in samples[:8]:
            print("  vazio t=%s state=%s lines=%s" % (s0.get("t"), s0.get("state"),
                                                     s0.get("lines")))
        print("LIVE_1TO1 o player nao desenhou nenhuma linha nas %d amostras "
              "(cc=%s) -- nada medido" % (len(samples), data.get("captions_on")))
        return 2

    # ---- A FAIXA QUE O PLAYER PINTA, pelo yt-dlp ----
    #
    # A PRIMEIRA VERSAO DESTE FICHEIRO COMPARAVA COM A FAIXA QUE O APP SERVIRIA e todas as
    # linhas davam `NAO` por uma razao que nao era defeito: o player pintava a traducao
    # (`track_lang=pt`) e o app servia o original (`en-orig`, a politica do dono). Texto de
    # linguas diferentes nunca e igual -- comparar isso mede a POLITICA, nao a fidelidade.
    # A fidelidade (timing, quebra de linha, janela que rola) mede-se contra a faixa que o
    # player PINTA, que e a unica que ele desenha.
    painted_lang = str(data.get("track_lang") or "")
    try:
        info = yc._extract_info(data.get("video_id") or args.video, 60)
    except Exception as exc:  # noqa: BLE001
        print("LIVE_1TO1 yt-dlp falhou: %r" % (exc,))
        return 2
    pcues = painted_cues(info, painted_lang)
    print("LIVE_1TO1 faixa PINTADA=%s cues=%d" % (painted_lang or "-", len(pcues)))

    # ---- O QUE O APP SERVIRIA -- pelo caminho do proprio app ----
    #
    # NAO se usa o `baseUrl` do player: MEDIDO 2026-10-23, ele responde um corpo VAZIO a um
    # GET nosso (`cues: 0` em 20 faixas), enquanto a URL do yt-dlp (a mesma que o
    # `fetch_track` usa) devolve 9 304 B e 19 cues para o mesmo video. O lado do Sotto e o
    # `fetch_track` REAL, com `painted=` igual ao que o caminho vivo lhe passa.
    words = []
    for s in samples:
        for line in (segs_text(s) or [norm(x) for x in (s.get("lines") or [])]):
            if norm(line):
                words = norm(line).split()
                break
        if words:
            break
    track = yc.fetch_track(data.get("video_id") or args.video,
                           painted=words or None, use_cache=False)
    cues = track.get("cues") or []
    if not cues:
        print("LIVE_1TO1 o app nao serviu track: state=%s reason=%s"
              % (track.get("state"), track.get("reason")))
        return 2
    tr = {"lang": track.get("lang"), "kind": track.get("source")}
    capacity = yw.CAPACITY
    print("LIVE_1TO1 faixa que o app serve=%s/%s cues=%d player_source=%s"
          % (tr["lang"], tr["kind"], len(cues), track.get("player_source")))

    # ---- A COMPARACAO ----
    # O lado do SOTTO e o modelo de janela do proprio app (`live_lines`), aplicado as cues da
    # faixa que o player pinta -- logo o que se mede e: o app desenharia as MESMAS linhas, no
    # MESMO instante? Um segmento por linha (o rollup do YouTube desenha assim).
    ours_cues = pcues or cues
    ok = 0
    fails = []
    print("")
    print("%-3s %-8s %-2s %-46s %-46s %s"
          % ("i", "t", "n", "YOUTUBE (o que ele ve)", "SOTTO (a mesma tabela)", "igual"))
    for i, s in enumerate(samples):
        t = float(s.get("t") or 0.0)
        theirs = segs_text(s) or [norm(x) for x in (s.get("lines") or []) if norm(x)]
        ours = [norm(x) for x in yw.live_lines(ours_cues, t, capacity) if norm(x)]
        cls = window_class(theirs, ours, t, ours_cues)
        same = cls != 'diverge'
        ok += 1 if same else 0
        if not same:
            fails.append({"i": i, "t": t, "youtube": theirs, "sotto": ours})
        print("%-3d %-8.2f %-2d %-40s %-40s %-7s"
              % (i, t, len(theirs),
                 (" | ".join(theirs))[:40], (" | ".join(ours))[:40], cls))

    print("")
    print("LIVE_1TO1 iguais=%d/%d (modelo de janela sobre a faixa pintada=%s)"
          % (ok, len(samples), painted_lang or tr["lang"]))
    # A POLITICA, dita em voz alta: se o player pinta uma lingua que a politica nao serve, a
    # legenda do app tem de aparecer na MESMA janela com o texto do ORIGINAL -- e e isso que a
    # alinhacao por instante tem de fazer. Aqui so se declara a divergencia.
    served_alive = sum(1 for s in samples
                       if yw.live_lines(cues, float(s.get("t") or 0.0), capacity))
    print("LIVE_1TO1 politica: player pinta=%s app serve=%s/%s janela-do-app-viva=%d/%d"
          % (painted_lang or "-", tr["lang"], tr["kind"], served_alive, len(samples)))
    for f in fails[:6]:
        print("  DIVERGE t=%.2f  youtube=%r  sotto=%r" % (f["t"], f["youtube"], f["sotto"]))
    verdict = "MATCH" if ok == len(samples) else "MISMATCH"
    print("LIVE_1TO1 veredicto=%s" % verdict)
    if args.json:
        io_dump = {"video": data.get("video_id"), "track": tr.get("lang"),
                   "painted_lang": painted_lang, "painted_cues": len(pcues),
                   "samples": samples, "matches": ok, "fails": fails,
                   "verdict": verdict, "captions_on": data.get("captions_on")}
        with open(args.json, "w", encoding="utf-8", newline="") as fh:
            json.dump(io_dump, fh, ensure_ascii=False, indent=1)
    return 0 if verdict == "MATCH" else 1


if __name__ == "__main__":
    sys.exit(main())
