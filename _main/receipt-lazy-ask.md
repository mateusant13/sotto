# Receipt — porque é que o `ask()` do `lazy-assets.js` não chegava ao shell

**Data:** 2026-10-13 04:0x–04:38 -03:00 · **Lane:** lazy-ask (subagente)
**Resposta curta:** o `ask()` **chegava** ao shell. O que morria era o
`SottoHost.dispatch`, que rebentava a CONSTRUIR o seu mapa de handlers
(`'setStripOffset': self._set_strip_offset` — método de `SottoShell`, não de
`SottoHost`) e por isso deitava fora **todas** as mensagens página→shell, de
qualquer `kind`. Havia ainda **dois** defeitos a jusante, no mesmo caminho:
o gate procurado no objecto errado, e uma corrida `ask`/`inject` que servia os
quatro assets como EMPTY mesmo depois de o gate os permitir. Os três estão
corrigidos e medidos.

---

## 1. A causa atribuída

### D1 — o mapa de handlers do `SottoHost` matava TODAS as mensagens (a causa do "não chega")

`app/webview/sotto_webview.py`, `SottoHost.dispatch` (:3576-3635 antes do fix):

```python
handler = {
    ...
    'setStripOffset': self._set_strip_offset,        # :3605
    'sotto:setStripOffset': self._set_strip_offset,  # :3606
}.get(kind)
```

`_set_strip_offset` é um método de **`SottoShell`** (:6950), não de
`SottoHost`. Um **dict literal avalia TODOS os valores**, portanto o
`AttributeError` dispara **antes** do `.get(kind)`: o `dispatch` morre para
**qualquer** kind — `lazy-asset`, `renderer-ready`, `stats`, tudo.

Introduzido por `7fcd97e` (**2026-10-12 22:26**, "THE BOTTOM PANEL DRAGS ON
SCREEN NOW"). O último `RECEIVER_READY` em disco é **2026-10-12 22:12:54** — o
canal página→shell está morto desde esse commit.

**Porque é que ninguém viu:** a excepção não vai para o log do shell. Vai para o
logger do pywebview, no stdout:

```
[pywebview] Traceback (most recent call last):
  File ".../webview/util.py", line 255, in _call
    result = func(*func_params)
  File "...\_paint-offscreen-sotto_webview.py", line 3606, in dispatch
    'setStripOffset': self._set_strip_offset,
AttributeError: 'SottoHost' object has no attribute '_set_strip_offset'
```

O log do shell mostrava `PRELOAD_ACTIVE hasSotto=true methods=15` e nada mais —
parecia saudável.

### D2 — o gate procurado no objecto errado

`SottoHost._lazy_asset` (:3754 antes do fix) fazia
`getattr(self, '_lazy_gate', None)`, mas `_lazy_gate` só existe em
`SottoShell` (`_arm_lazy_gate`, :4462/:4465/:4473). Com D1 corrigido, o ask
**chega** e é recusado: `PANEL_LAZY_ASK_REFUSED reason=no-gate`.

### D3 — a corrida `ask`/`inject` (porque os assets continuavam VAZIOS)

Com D1+D2 corrigidos, o gate abre — mas **depois** de já ter respondido:

```
04:31:50.476 PANEL_LAZY_EMPTY  url=.../themes/cinematic.css
04:31:50.485 PANEL_LAZY_EMPTY  url=.../skins/skins.js
04:31:50.494 PANEL_LAZY_EMPTY  url=.../skin-host.js
04:31:50.521 PANEL_LAZY_EMPTY  url=.../skin-layout.css
04:31:50.531 PANEL_LAZY_ALLOW  url=themes/cinematic.css   <- 55 ms tarde
04:31:50.531 PANEL_LAZY_ALLOW  url=skins/skins.js
04:31:50.531 PANEL_LAZY_ALLOW  url=skin-host.js
04:31:50.531 PANEL_LAZY_ALLOW  url=skin-layout.css
```

O `ask()` viaja como MENSAGEM; o `<link>/<script>` injectado logo a seguir é
pedido IMEDIATAMENTE. O gate responde ao pedido com o 200 VAZIO e os bytes reais
nunca são buscados. Readback da página no mesmo braço: `cinRules=0`
(o `cinematic.css` de 350 KB com ZERO regras), `SOTTO_SKINS=undefined`,
`window.SottoSkin=undefined`.

---

## 2. O que foi medido (comandos e números)

Instrumento: `_main/panel-paint-probe.py` (cópia off-desk, `--theme cine-cellar`),
com sondas que eu acrescentei ao ficheiro do probe (não ao produto):
`--probe both` (sonda NO PRELOAD + sonda NA PÁGINA, cada uma pelos DOIS canais:
`window.sotto.dispatch` e `window.chrome.webview.postMessage` cru) e
`--readback` (estado da página lido por `exec_js`, o único seam que funciona).

```
py -3 _main/panel-paint-probe.py --theme cine-cellar --secs 14 --probe both --readback
node --check app/panel/lazy-assets.js
py -3 -m py_compile _main/panel-paint-probe.py app/webview/sotto_webview.py
```

| medida (`_main/_paint-asked.log`) | ANTES (HEAD) | só D1 | D1+D2 | D1+D2+D3 |
|---|---|---|---|---|
| `BRIDGE_UNKNOWN_KIND` (sondas do preload) | **0** | **10** | 10 | **10** |
| `RECEIVER_READY` (script DA PÁGINA, `panel.js:3116`) | **0** | **1** | 1 | **1** |
| `PANEL_LAZY_ASK_REFUSED` | 0 | 4 (`reason=no-gate`) | **0** | **0** |
| `PANEL_LAZY_ALLOW` | **0** | 0 | **4** | **4** |
| `PANEL_LAZY_EMPTY url=` | 4 | 4 | 4 | **0** |
| tracebacks `no attribute '_set_strip_offset'` (asked+notasked) | 35+34 | 0+0 | 0+0 | 0+0 |
| readback `cinRules` / `SOTTO_SKINS` / `bodySkin` | n/d | n/d | 0 / undefined / '' | **616 / object / '1'** |

A sonda do preload devolveu 5 disparos × 2 canais = 10 mensagens, com o estado
codificado no próprio `kind`:

```
kind='preprobe-r0-c1p0s1a0'   t=0:    chrome.webview=1, pywebview._returnValuesCallbacks=0,
                                      window.sotto.dispatch=1, pywebview.api=0
kind='preprobe-s1-c1p1s1a1'   t=300ms: tudo presente
...
kind='preprobe-s4-c1p1s1a1'   t=5000ms
```

(c=chrome.webview, p=`_returnValuesCallbacks`, s=`window.sotto.dispatch`,
a=`pywebview.api`.) Em t=0 o `post()` do shell PÕE EM FILA (o seu
`channelOpen()` exige `_returnValuesCallbacks`) e o flush entrega depois — a
fila não era o problema, como o utilizador já tinha medido.

Readback final (braço `cine-cellar`, D1+D2+D3):

```
cinRules=616  sheets=12  SOTTO_SKINS=object  skinHost=object  bodySkin='1'
lazyHrefs = themes/cinematic.css, skins/skins.js, skin-host.js, skin-layout.css
lazyLog:  ask themes/cinematic.css / inject themes/cinematic.css
          ask skins/skins.js       / inject skins/skins.js
          ask skin-host.js         / inject skin-host.js
          ask skin-layout.css      / inject skin-layout.css
```

### A prova de que a premissa dos 298 `RECEIVER_READY` estava STALE

```
Get-Content _main/webview-run.log | Select-String 'RECEIVER_READY' | Select-Object -Last 3
  2026-10-12 22:12:54.493 ... (último em disco)
```
E na instância VIVA do dono (arrancou antes de 23:06 de 10-12, ainda a correr,
5686 linhas desde o arranque): `RECEIVER_READY 0`, `STATUS_APPLIED 0`,
`PAGE_ERROR 0`, `BRIDGE_UNKNOWN_KIND 0` — enquanto os pushes shell→página
corriam normalmente (`BRIDGE_STATUS_HELD 3013`, `BRIDGE_STATS_PUSH 396`).
O `_main/panel-state.json` da app viva diz `rendererReady: false`.
**Ou seja: não era "a página chega e o preload não"; era NADA a chegar.**

---

## 3. Os fixes aplicados (e verificados)

1. `app/webview/sotto_webview.py` — as duas entradas do mapa passam a apontar
   para o objecto certo:
   `'setStripOffset': self._shell._set_strip_offset` (e o gémeo `sotto:`).
2. `app/webview/sotto_webview.py` — `_lazy_asset` lê o gate onde ele vive:
   `gate = getattr(self._shell, '_lazy_gate', None)`.
3. `app/panel/lazy-assets.js` — `ask(url, done)`: o `inject` passa a correr
   **depois da confirmação do shell**. O canal esperável é o api do pywebview
   (`window.pywebview.api.dispatch`, que é `SottoHost.dispatch` — `js_api=SottoHost(self)`,
   :3978 — e cuja promise resolve **depois** de o Python regressar, isto é,
   depois de `LazyAssetGate.allow()`). Enquanto o api não existe, espera
   (turnos de 50 ms, até 2 s) em vez de correr à frente; e cai no canal
   fire-and-forget (`window.sotto.dispatch`) se o api não aparecer. Todos os
   caminhos terminam em `done`, e há um `setTimeout(settle, 1500)` como piso:
   um shell que nunca responda não deixa o inject por correr.

Verificação: a linha `PANEL_LAZY_EMPTY url=` passou de **4 → 0**, o
`cinematic.css` passou a ter **616 regras** no documento, e o par de skins
montou (`SOTTO_SKINS=object`, `SOTTO_SKIN=object`, `body[data-skin]='1'`).

**Erro meu, apanhado e corrigido na mesma sessão:** a primeira revisão do fix 3
fechava sobre `var url` (function-scoped) dentro do ciclo, portanto o callback
diferido injectava o ÚLTIMO valor da lista — o readback mostrou `cinRules=-2`
(o link do cinematic nunca foi injectado) e um `PANEL_LAZY_EMPTY` para
`skin-layout.css` 2 ms depois do ask. Corrigido com um IIFE por iteração.

---

## 4. O que NÃO fechei / não medi

1. **A app do dono continua cega até o shell ser reiniciado.** A instância viva
   tem o shell ANTIGO carregado (`code.shell.stale: true`; `loaded=8656c2414f6f42c7`
   vs `disk`), e o hot reload não vigia o shell. Só o Lead lança: **o comando é
   o de sempre** (`run.cmd` / `sotto_webview.py`), e é preciso reiniciar para o
   dono ver a correcção.
2. **A sonda DA PÁGINA (inline `<script>`) nunca disparou — bloqueada pelo CSP da
   própria página**: `panel.html:22-25` tem
   `script-src 'self'` (sem `'unsafe-inline'`). O par de controlo usado foi o
   `renderer-ready` do próprio `panel.js` (mesmo `post()`, mesmo formato):
   0 antes / 1 depois. O arm inline fica **NÃO MEDIDO** e não é evidência em
   nenhum sentido.
3. **O veredicto de PIXÉIS do probe ficou UNSETTLED** nos dois últimos braços
   (`PAINT-VERDICT FAIL`, rc=3): o capturador não encontrou dois frames
   consecutivos iguais dentro do orçamento de 25 s (a instabilidade conhecida do
   instrumento — caret de 1,06 s / orçamento de settle). A janela FOI encontrada
   e capturada (PNG escrito). **Não afirmo** que o painel pinta bem com o
   `cinematic.css`: o que está medido é o DOM/CSSOM (`cinRules=616`) e o gate.
4. **O caminho `pd-*` (`themes/panel-designs.css`) não foi medido** com o fix 3,
   nem uma troca de tema em runtime (MutationObserver → `settle`).
5. **A fraqueza estrutural do D1 NÃO está corrigida.** O mapa continua a ser um
   dict literal: uma entrada má futura volta a matar TODOS os kinds, e a
   excepção volta a ficar só no logger do pywebview. Recomendação (não
   aplicada, para o Lead decidir): resolver o handler **por kind** (tabela
   nome→nome + `getattr(..., None)`) ou, no mínimo, envolver a construção num
   `try/except` que faça `log('BRIDGE_HANDLER_MAP_FAILED kind=... error=...')`.
   Sem isso, este apagão é invisível outra vez.
6. **Wart de diagnóstico:** um ask repetido para um URL já permitido é registado
   como `PANEL_LAZY_ASK_REFUSED reason=not-deferred` (parece recusa, é
   idempotência). Não toquei nisso.
7. Os limites do fix 3 (2 s à espera do api; 1500 ms de piso do `settle`) são
   decisões minhas, medidas apenas no caminho feliz (o api resolve em poucos ms).

---

## 5. Pins (para o Lead conferir antes de commitar)

| ficheiro | bytes | sha256 |
|---|---|---|
| `app/webview/sotto_webview.py` | 503026 | `8884370C63054530EAAAC1DFD4F381860242953650149C7B2B20F3044D8C6AEF` |
| `app/panel/lazy-assets.js` | 18556 | `94C1745D94FD3C833E001A03EC9B5E2C012E8DBF83456B00E5616953EB4BAA8D` |
| `_main/panel-paint-probe.py` | 44614 | `1D9D744775B9476BD709EEE318CE434E8CD14B996BC7E014E39CEA0F891D8A94` |

Diffs vs `HEAD`: `sotto_webview.py` 2 linhas de código (+ comentário),
`lazy-assets.js` reescrita do `ask` + 3 call sites, `panel-paint-probe.py`
sondas/readback (só instrumento). Nada foi adicionado ao git (o Lead faz).
