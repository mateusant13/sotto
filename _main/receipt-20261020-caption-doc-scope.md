# Recibo 2026-10-20 — a protecção de render do painel estava DESLIGADA (e dois portões estavam verdes sobre o mesmo buraco)

**Data:** 2026-10-20, 10:2x–10:3x -03:00
**Medido em:** Blink (Edge headless — o motor que o WebView2 usa), nos documentos
reais `app/panel/panel.html` e `app/panel/caption.html`, com as folhas reais, na
ordem real que `panel.html` as carrega.
**Instrumentos:** `_main/caption-doc-scope-blink.py` (novo, prova no motor real)
e `_main/caption-independent-oracle.js` (o portão in-process que já existia, e
que era um **verde falso** — a história está abaixo).

---

## 1. O defeito, como foi encontrado

A observação que abriu a caça está no `AGENTS.md` (regra do painel) e no
comentário de `app/panel/zip-overlay.css:443-447`:

> *"com o escopo no atributo que so esta pagina tem (`<html data-caption-window="1">`).
> Assim nao toca em nada do painel."*

A segunda frase era **FALSA**, e a primeira era a razão: `data-caption-window`
**não** marca só a página da legenda.

`app/webview/sotto_webview.py:8722-8724` (`show_caption_window`) escreve esse
atributo **no documento do PAINEL**, em cada mudança do interruptor LIVE:

```python
self.window.evaluate_js(
    'document.documentElement.setAttribute('
    '"data-caption-window", %s)' % ('"on"' if on else '"off"'))
```

O próprio comentário do shell diz: *"o atributo vive no documento do painel e a
folha que o le e a `zip-overlay.css`"*. E `panel.js:697` (`CAPTION_WINDOW_ATTR`)
lê o mesmo atributo para pintar o botão e o indicador.

Portanto as **três** regras de `zip-overlay.css` que eram DA JANELA DA LEGENDA
acertavam também o PAINEL.

## 2. As três regras e o que faziam

| # | regra (antes) | o que era suposto | o que acontecia no painel |
|---|---|---|---|
| a | `html[data-caption-window="on"] #caption-float { display: none !important }` | esconder a legenda INLINE do painel quando a janela nativa sobe | batia certo — mas também podia apagar a legenda se "on" chegasse ao documento da legenda |
| b | `html[data-caption-window] #caption-float .caption-float__line { text-shadow: none !important }` | a legenda da janela **não** tem placa, logo sem sombra (halo) | **tirava a sombra da legenda INLINE do painel**, que tem uma placa por baixo das palavras |
| c | `html[data-caption-window], html[data-caption-window] body { background: transparent !important; ... }` | a janela da legenda não tem fundo | **matava a PROTECÇÃO DE RENDER do painel** (`panel.css:105-127`, o `rgba(11, 15, 20, 0.98)`) |

## 3. A medição (Blink, antes da correcção)

`app/panel/panel.html`, folhas reais, `getComputedStyle`:

| atributo | `html`/`body` background | sombra da legenda inline | `#caption-float` |
|---|---|---|---|
| *(nenhum)* | `rgba(11, 15, 20, 0.98)` | `rgba(0, 0, 0, 0.88) 0px 2px 18px, ...` | `none` |
| `data-caption-window="off"` | **`rgba(0, 0, 0, 0)`** | **`none`** | `none` |
| `data-caption-window="on"` | **`rgba(0, 0, 0, 0)`** | **`none`** | `none` |

**O que isto significa, em-producto:**

1. A janela principal do Sotto é uma forma **transparente**
   (`sotto_webview.py:5844`, `transparent=not self.args.opaque`) — logo, um
   `<html>` transparente **é o ambiente de trabalho a aparecer por trás do
   painel**, não uma cor diferente.
2. A protecção de render (`panel.css:105-127`) é a rede que garante que o painel
   **nunca fica branco** quando o `.panel` não pinta. Com o atributo presente,
   essa rede **não existia**.
3. E o atributo está presente **para sempre** a partir do **primeiro Alt+C**: o
   shell escreve "on" ou "off" e nunca remove o atributo. `"off"` também
  Transparent — o estado normal depois de ligar e desligar a legenda.
4. `caption.html` com `data-caption-window="on"` tinha `display: none` na
   legenda — ou seja, **a legenda podia desaparecer**, se o valor chegasse lá.

## 4. A correcção

**`app/panel/caption.html:2`** — a janela da legenda ganha a **marca própria**:

```html
<html lang="pt-BR" data-caption-window="1" data-caption-doc="1" data-float="on">
```

**`app/panel/zip-overlay.css`** — as três regras são re-escopadas:

| # | depois |
|---|---|
| a | `html[data-caption-window="on"]:not([data-caption-doc]) #caption-float { display: none !important; }` |
| b | `html[data-caption-doc] #caption-float .caption-float__line { text-shadow: none !important; }` |
| c | `html[data-caption-doc], html[data-caption-doc] body { background: transparent !important; ... }` |

**Porquê `data-caption-doc` e não `data-float`:** `caption-float.js:211` escreve
`data-float` no `documentElement` **do painel** também
(`d.documentElement.setAttribute('data-float', on ? 'on' : 'off')`), portanto
`data-float` não distingue os dois documentos. `data-caption-doc` só existe no
`caption.html` — verificado por censo de todos os `<html>`/`<body>` do `app/panel`.

**A promises que estava escrita e era falsa** ("Assim nao toca em nada do painel")
foi substituída pela que agora é imposta, com o número que a mediu.

## 5. A medição DEPOIS da correcção

| documento | atributo | `html`/`body` | sombra | `#caption-float` |
|---|---|---|---|---|
| `panel.html` | *(nenhum)* | `rgba(11, 15, 20, 0.98)` | presente | `none` |
| `panel.html` | `"off"` | **`rgba(11, 15, 20, 0.98)`** | **presente** | `none` |
| `panel.html` | `"on"` | **`rgba(11, 15, 20, 0.98)`** | presente | `none` |
| `caption.html` | `"1"` (nativo) | `rgba(0, 0, 0, 0)` | `none` | **`block`** (visível) |
| `caption.html` | `"on"` | `rgba(0, 0, 0, 0)` | `none` | **`block`** (visível) |
| `caption.html` | *(nenhum)* | `rgba(0, 0, 0, 0)` | `none` | `block` |

**Sem regressão na janela da legenda:** transparente, sem sombra, e a legenda
**visível em todos os estados** (antes, `"on"` escondia-a).

## 6. Os DOIS buracos que escondiam isto — e os dois estavam verdes

Este é o que vale a pena guardar. O defeito não passou por uma falha de
atenção: passou por **dois buracos independentes no mesmo portão**, e ambos
davam "verde".

### Buraco (i) — a regra não estava na POPULAÇÃO do instrumento

`_main/caption-independent-oracle.js`, função `loadPanel` (linha 161), inlinava
**duas** folhas e não a terceira:

```js
const css = fs.readFileSync(path.join(dir, 'panel.css'), 'utf8');
const floatCss = fs.readFileSync(path.join(dir, 'caption-float.css'), 'utf8');
style.textContent = css + '\n' + floatCss;   // <- zip-overlay.css NAO estava
```

`zip-overlay.css` é exactamente onde viviam as três regras. **Uma regra fora da
população não pode fazer falhar um check.** O harness agora carrega-a, pela
mesma ordem que o `panel.html` a carrega.

### Buraco (ii) — o instrumento saltava o selector errado

O censo estático do mesmo portão (arm B3b) procurava regras de `<html>`/`<body>`
transparentes e **saltava** as que mencionassem `data-caption-window`:

```js
if (member.indexOf('data-caption-window') >= 0) continue;   // <- o buraco
```

Ou seja: o portão estava instruído a ser cego **exactamente onde estava o
defeito**. A excepção passou a ser `data-caption-doc` — o que torna o censo
**mais estrito**, não menos: hoje uma regra transparente de `<html>`/`<body>`
que seja escopada a `data-caption-window` é **apanhada**, porque o shell
escreve esse atributo no painel.

**Prova de que o jsdom resolve a cascata** (para não culpar a ferramenta):
`I:\cc-tmp\jsdom-cascade-test.js` — com `html[data-caption-window]` o jsdom
devolve `rgba(0, 0, 0, 0)`; sem atributo, `rgba(11, 15, 20, 0.98)`. A
capacidade havia; o que faltava era a folha e a excepção.

### O que seAdded ao portão in-process

- **B3d** — a legenda INLINE do painel **mantém** a sua sombra, mesmo com o
  `data-caption-window="off"` que o shell escreve.
- **B3e** — a linha da legenda na janela **não** tem sombra.
- **mutante N9** — reproduz os bytes do pré-fix (as três regras com o scope
  antigo) → **RED** em B3, B3d, B3e.
- **mutante N10** — só a regra da sombra volta ao scope antigo → **RED** em
  B3d, B3e.

Medido: **10/10 mutantes vermelhos**, `NEG-ARM VERDICT: PASS`. O gate em
processo corre na **2ª bateria** (`instruments-battery.mjs`, que reporta
`launches=0`).

## 7. A prova no motor real — `_main/caption-doc-scope-blink.py`

Portão novo, **no motor real**: Blink/Edge headless, `getComputedStyle` sobre os
documentos reais. 9 checks:

| # | o que pergunta |
|---|---|
| P1 | o painel é opaco sem atributo nenhum |
| P2 | o painel **sobrevive** à escrita "off" do shell |
| P3 | o painel **sobrevive** à escrita "on" do shell |
| P4 | a legenda inline do painel **mantém** a sombra |
| P5 | com a escrita "on", a legenda inline do painel está escondida |
| C1 | o documento da legenda é **transparente** (sem placa, sem caixa) |
| C2 | a linha da legenda **não** tem sombra |
| C3 | a legenda da janela está **visível** (nunca `display: none`) |
| C4 | o documento da legenda é transparente mesmo sem atributo |

- **PRISTINE:** `9 check(s), 0 failed` → `VERDICT: PASS`, rc=0.
- **`--neg-arm`:** o mutante M1 (os bytes do pré-fix) → **RED** em P2, P3, P4 →
  `NEG-ARM VERDICT: PASS`, rc=0.

**FORA das baterias, por regra** (regra 6 do `AGENTS.md`): este portão **LANÇA**
o Edge, e um portão que lança fica fora. O censo de `AGENTS.md` foi re-medido:
**20 dentro / 23 fora**, dos 23 **5 in-process** e **18 que criam processo**.

### Um bug meu que este portão tinha (e que está corrigido)

A primeira versão lia e escrevia as folhas em **modo texto**. As *universal
newlines* do Python transformaram `app/panel/caption.html` — que é **LF**
(`.gitattributes:503`) — em **CRLF**, à terceira execução. Um portão que
reescreve os ficheiros que mede é um portão que estraga o produto. Agora:
o portão trabalha **sempre numa cópia descartável** e faz o patch **em bytes**.
**Medido depois da correcção:** `caption.html`, `panel.html` e `zip-overlay.css`
com o **mesmo sha256** antes e depois das duas execuções → `INALTERADO`.
O `caption.html` foi reposto a LF (6277 B, 116 bare LF, 0 CRLF).

## 8. A regra que fica (`AGENTS.md` nº 8)

> **UMA REGRA QUE NÃO ESTÁ NA POPULAÇÃO DO INSTRUMENTO NÃO PODE SER APANHADA
> POR ELE.** A população de um instrumento é parte do contrato dele, e uma lista
> de exclusões é parte da sua cegueira: escreve o que ele **não** carrega, e
> justifica cada selector que ele desculpa.

## 9. Estado do produto no momento desta medição

- App do dono viva: **pid 42860** (pythonw), worker **43520**, desde 08:11:02.
- Log `I:\cc-tmp\sotto-081102.log`: **0** `UI_THREAD_STALL`, **0** `exec_js TIMEOUT`,
  **0** `Traceback`.
- **A app NÃO foi relançada** durante este trabalho: a correcção é de CSS/HTML e
  é servida em cada arranque; o dono não precisa de reiniciar nada para a
  legenda 1:1 continuar a funcionar.

## 10. Ficheiros tocados

| ficheiro | medido |
|---|---|
| `app/panel/caption.html` | 6277 B, LF (116 bare LF, 0 CRLF), sha `BA330F4D2E1403A0…` |
| `app/panel/zip-overlay.css` | 30420 B, CRLF puro (545 CRLF, 0 bare LF), sha `8974539EE7C18A92…` |
| `_main/caption-independent-oracle.js` | 48595 B, LF, sha `6C6BE6B2AF7AC603…` |
| `_main/caption-doc-scope-blink.py` | 13090 B, LF, sha `81D77BE2504B9EAB…` (novo) |
| `_main/instruments-battery.mjs` | 24204 B, CRLF puro, sha `B5A37876F5806250…` |
| `AGENTS.md` | 113416 B, LF, sha `15BA1B20B3A1B111…` (regras 6 e 8) |

## 11. Verificação

```
node _main/caption-independent-oracle.js              -> 54 checks, 0 failed, VERDICT: PASS
node _main/caption-independent-oracle.js --neg-arm     -> 10/10 mutantes RED, NEG-ARM VERDICT: PASS
python _main/caption-doc-scope-blink.py                -> 9 checks, 0 failed, VERDICT: PASS
python _main/caption-doc-scope-blink.py --neg-arm       -> M1 RED (P2, P3, P4), NEG-ARM VERDICT: PASS
```

E, depois de todas as execuções: `caption.html`, `panel.html` e
`zip-overlay.css` com **o mesmo sha256** de antes → o portão não mexe no produto.
