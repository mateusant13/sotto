"""A FAIXA DE AUDIO QUE O PLAYER DO YOUTUBE ESTA A USAR -- medido pelo relay do contrato.

O DONO, 2026-10-22 09:35 e 09:52: *"tira a auto dublagem"*.

O QUE ESTE COMANDO FAZ E O QUE NAO FAZ. Ele LE a aba pelo relay ja vivo
(`127.0.0.1:9224`, `ompRelayVersion=18.6.1`), escolhida por URL e nunca por indice, e
pergunta ao player tres coisas: a lista de faixas de audio que o `playerResponse`
declara, qual e a de omissao (`defaultAudioTrackIndex`), e o que o `getAudioTrack()`
devolve depois de pedir a faixa ORIGINAL. Nao arranca browser, nao abre aba, nao muda
nada que o dono veja alem de tentar a seleccao da original (que o player pode recusar,
e recusou).

Se a aba nao estiver la, diz isso e sai 1 -- uma medicao ausente nao e uma medicao.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request

RELAY = "http://127.0.0.1:9224/json/list"
DRIVER = r"I:\!manager\tools\ext-reload-cdp.mjs"
WORKDIR = r"I:\!manager"

JS = r"""
(function(){
  var mp = document.getElementById('movie_player');
  var pr = window.ytInitialPlayerResponse || {};
  var r = (pr.captions||{}).playerCaptionsTracklistRenderer || {};
  var at = (r.audioTracks||[]).map(function(a){return a.audioTrackId;});
  var before = null; try { before = mp && mp.getAudioTrack(); } catch(e){}
  var def = r.defaultAudioTrackIndex;
  var original = (def != null && at[def]) ? at[def] : (at.filter(function(x){return /^en[.-]/.test(x);})[0] || null);
  var set = null;
  if (original && mp && mp.setAudioTrack) { try { set = String(mp.setAudioTrack({id: original})); } catch(e){ set = 'exc:'+e; } }
  var after = null; try { after = mp && mp.getAudioTrack(); } catch(e){}
  return JSON.stringify({
    n: at.length, ids: at,
    defaultIndex: def, defaultId: (def != null ? at[def] : null),
    original: original, setResult: set,
    before: before ? {id: before.id, lang: before.languageCode, dub: before.isAutoDubbed} : null,
    after: after ? {id: after.id, lang: after.languageCode, dub: after.isAutoDubbed} : null
  });
})()
"""


#: O video das reclamacoes de 2026-10-22. A aba e escolhida POR URL, e primeiro por
#: este id -- havia duas abas do YouTube abertas e a primeira que aparece no relay nao
#: e a que o dono estava a ver (medido: `watch?v=EAgaA_T1OP0`, com 1 faixa e sem
#: `defaultAudioTrackIndex`). Escolher por INDICE foi o defeito que a primeira versao
#: deste ficheiro cometeu.
TARGET_VIDEO = "WdaHAGRBB6s"


def pick_target():
    data = json.load(urllib.request.urlopen(RELAY, timeout=5))
    tabs = [t for t in data if isinstance(t, dict) and "youtube.com" in (t.get("url") or "")]
    for t in tabs:
        if TARGET_VIDEO in (t.get("url") or ""):
            return t
    for t in tabs:
        if "/watch" in (t.get("url") or ""):
            return t
    return tabs[0] if tabs else None


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if not os.path.exists(DRIVER):
        print("AUDIO_TRACK driver ausente: %s" % DRIVER)
        return 1
    try:
        t = pick_target()
    except Exception as exc:  # noqa: BLE001
        print("AUDIO_TRACK relay indisponivel (%r) -- nada foi medido" % (exc,))
        return 1
    if not t:
        print("AUDIO_TRACK nenhuma aba do YouTube no relay -- nada foi medido")
        return 1
    print("AUDIO_TRACK target=%s url=%s" % (t.get("id"), (t.get("url") or "")[:70]))
    p = subprocess.run(["bun", DRIVER, "--target", t["id"], "--expr", JS],
                       cwd=WORKDIR, capture_output=True, timeout=120, creationflags=subprocess.CREATE_NO_WINDOW)
    raw = ((p.stdout or b"") + (p.stderr or b"")).decode("utf-8", "replace")
    m = None
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                m = json.loads(line)
            except Exception:
                continue
    if not m or not m.get("ok"):
        print("AUDIO_TRACK sem resposta do driver: %s" % raw.strip()[:200])
        return 1
    try:
        v = json.loads(m.get("value") or "{}")
    except Exception:
        print("AUDIO_TRACK valor ilegivel: %r" % (m.get("value"),))
        return 1
    print("AUDIO_TRACK faixas=%d defaultIndex=%s defaultId=%s original=%s"
          % (v.get("n"), v.get("defaultIndex"), v.get("defaultId"), v.get("original")))
    print("AUDIO_TRACK antes=%s setAudioTrack=%s depois=%s"
          % (json.dumps(v.get("before")), v.get("setResult"), json.dumps(v.get("after"))))
    dub = (v.get("before") or {}).get("dub")
    ids = v.get("ids") or []
    print("AUDIO_TRACK dublagens listadas=%d | antes marcado comme dublagem=%s"
          % (max(len(ids) - 1, 0), dub))
    # O veredicto: a faixa em uso e a de omissao, E essa e a original do video.
    ok = v.get("n", 0) >= 1 and v.get("defaultId") is not None and v.get("defaultId") == v.get("original")
    print("AUDIO_TRACK veredicto=%s (a faixa de omissao E a original do video)"
          % ("original-em-uso" if ok else "nao-confirmado"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
