# Priors externos — entrada de linha e roll-up da legenda do YouTube

Escopo: só leitura. Nenhum ficheiro do repo foi alterado por este trabalho.
Recolha: **2026-11-08** (hora local não instrumentada nesta toolset — sem shell/relógio; não invento hora).
Build do player citada: `ecc3e9a7` (o `captions.js` abaixo foi servido com HTTP 200 nesta data).
Fonte de cada linha: código do player, payload JSON3, documentação de terceiros ou heurística de autor.
Legenda de autoria: **[YT-código]** player do YouTube · **[YT-payload]** dados que o YouTube entrega ·
**[autor]** regra/observação de quem escreveu a ferramenta · **[W3C]** definição/spec, não implementação.

---

## 1. Tabela `afirmacao | URL | e' do YouTube ou do autor? | data | confianca`

| # | Afirmação | URL / âncora | Autoria | Data | Confiança |
|---|---|---|---|---|---|
| 1 | Existe um tipo de janela de legenda dedicado ao roll-up (`yJ`, `type=2`), escolhido quando o modo declarado é `xR===2`; a mesma janela recebe a classe `ytp-caption-window-rollup` e `overflow:hidden` inline | https://www.youtube.com/s/player/ecc3e9a7/player_ias.vflset/en_US/captions.js:84-85 e `:130-131` | [YT-código] | 2026-11-08 | alta |
| 2 | `xR` vem de `mhModeHint` (estilo de janela) e `zq` de `rcRows` (posição de janela) no payload | captions.js:249-250 (`V.mhModeHint→x.xR`, `V.rcRows→x.zq`) | [YT-código] | 2026-11-08 | alta |
| 3 | ASR inglês real declara `wsWinStyles[].mhModeHint: 2`, `wpWinPositions[].rcRows: 2`, `ccCols: 40` | https://raw.githubusercontent.com/1c7/Youtube-Auto-Subtitle-Download/master/Youtube-Subtitle-Downloader/fmt=json3/en.json:1-20 | [YT-payload] (captura de terceiro) | ficheiro sem data; acedido 2026-11-08 | alta (formato) / média (data da captura) |
| 4 | ASR coreano real declara o mesmo (`mhModeHint:2`, `rcRows:2`) e `aAppend:1` + `segs:[{"utf8":"\n"}]` antes de cada linha nova | https://raw.githubusercontent.com/DualSubs/YouTube/main/example/asr.ko.json:1-44 | [YT-payload] (captura de terceiro) | ficheiro sem data; acedido 2026-11-08 | alta (formato) / média (data) |
| 5 | A janela do ASR é **uma só para a faixa inteira**: um evento de definição com `dDurationMs` = duração do vídeo (643760 ms) e `wpWinPosId`; todas as palavras usam `wWinId: 1` | 1c7 `en.json:9-20`; DualSubs `asr.ko.json:1-17` | [YT-payload] | acedido 2026-11-08 | alta |
| 6 | Palavras entram progressivamente dentro da mesma linha: cada `segs[]` tem `tOffsetMs`, e o player cria um cue por segmento com `start = tStartMs + tOffsetMs` | captions.js:251-254 (`H=h.tOffsetMs||0`, `new QM(V+H, …)`); `en.json:20-45` | [YT-código] + [YT-payload] | 2026-11-08 | alta |
| 7 | A **linha nova** é o primeiro segmento de um evento **sem `aAppend`**; os segmentos seguintes do mesmo evento são forçados a `append=true` (`v=!0` no fim do corpo do loop) e continuam a mesma linha | captions.js:251-254 (ler o `v=` no fim de `:253`, `!0` em `:254`) | [YT-código] | 2026-11-08 | alta |
| 8 | Em modo roll-up (`xR===2`), um segmento `"\n"` que chega como `aAppend` é **ignorado** (não cria linha em branco) | captions.js:251 (`===2 && v && J==="\n"` → `continue`) | [YT-código] | 2026-11-08 | alta |
| 9 | Estrutura DOM: `div.caption-window` > `span.captions-text` (`display:block; word-wrap:normal`) > `span.caption-visual-line` (`display:block`) > `span.ytp-caption-segment` (`display:inline-block; white-space:pre-wrap`) | captions.js:19 (`.captions-text`), `:32-34` (linha/segmento) | [YT-código] | 2026-11-08 | alta |
| 10 | A quebra tipográfica dentro de uma linha é do browser (inline-block/pre-wrap dentro de um bloco com largura limitada), não uma contagem de caracteres do YouTube; a largura da caixa é `min(conteúdo, 96% do vídeo)` com mínimo medido por `ccCols` travessões | captions.js:87 (`QV=Math.max(G2,GW,width+1)`), `:219-220` (`maxWidth=x*.96`) | [YT-código] | 2026-11-08 | alta |
| 11 | A altura visível da janela é a soma das **últimas `zq` (=`rcRows`) linhas**; `T2` = essa soma | captions.js:87 (`for X=D.Z.params.zq … C+=offsetHeight`) | [YT-código] | 2026-11-08 | alta |
| 12 | O deslocamento aplicado é `B = T2 - altura_total_do_texto` (negativo = sobe) e vira `transform: translateY(Bpx)` no `.captions-text` | captions.js:88-89 (`Neg(D,B)`) | [YT-código] | 2026-11-08 | alta |
| 13 | A classe `ytp-rollup-mode` (que liga a transição CSS) só é adicionada quando o bloco **sobe** (`B < gw`) e **não** no primeiro reset (`B>0 && gw===0`); quando o texto encolhe não há transição (salto) | captions.js:89 (`C=B>0&&D.gw===0, V=B<D.gw; X||isNaN(B)||C||!V||(iL(...,"ytp-rollup-mode"), …)`) | [YT-código] | 2026-11-08 | alta |
| 14 | A classe é removida no `transitionend` (com fallback de **433 ms**) e a janela é reconciliada | captions.js:84 (`new g.tE(this.iq,433,this)`), `:259` (`iq`) | [YT-código] | 2026-11-08 | alta |
| 15 | A transição CSS é `transform .433s cubic-bezier(0,0,.2,1)` em `.ytp-caption-window-rollup.ytp-rollup-mode .captions-text` | espelho formatado: https://raw.githubusercontent.com/cyfung1031/userscript-supports/main/references/www-player.css:15813-15815 | [YT-código] (snapshot de CSS) | commit do espelho: 2023-07-24; JS live com 433 ms: 2026-11-08 | alta na duração/curva; média na letra exacta da regra na build 2026 |
| 16 | O CSS live de 2026 contém `.ytp-caption-window-rollup.ytp-rollup-mode{overflow:hidden}` | https://www.youtube.com/s/player/ecc3e9a7/www-player.css (grep `ytp-caption-window-rollup` → 1 match; ficheiro minificado, tool trunca a 512 B por linha) | [YT-código] | 2026-11-08 (header `Published Time: Tue, 03 Mar 2026`) | alta (a classe existe); a regra da transição não foi extraída do live — ver Q3 |
| 17 | Não há `opacity` nem fade na entrada/saída do roll-up: a animação é só `transform`; `.caption-window` só tem `position/line-height/z-index/pointer/cursor/user-select` | CSS espelho `:15675-15683` e `:15813-15815`; captions.js não toca `opacity` em `yJ`/`aCN` | [YT-código] | 2026-11-08 | alta (código) / média (CSS live) |
| 18 | O DOM **acumula** linhas antigas: `yJ.Br` concatena as linhas anteriores (`this.Y.concat(D.slice(B))`); a janela é que recorta nas últimas `zq` | captions.js:262 | [YT-código] | 2026-11-08 | alta |
| 19 | A primeira linha de uma janela nova aparece **sem animação**: não há valor de `transform` anterior para interpolar e a classe só é adicionada na mudança de offset | captions.js:89 + regra acima | [YT-código] + [INFERENCE] sobre o primeiro frame | 2026-11-08 | média (inferência de pintura; Q8 decide) |
| 20 | VTT de auto-caption do YouTube tem janela rolante de **2 linhas por cue**: linha 1 = carry-forward (texto simples), linha 2 = palavras novas (com tags `<c>`); entre cues reais há um cue de transição de **10 ms** com só o carry-forward | https://github.com/ryanputraa/RB-YouTube-Tools/blob/master/src/main/services/captionParser.ts (comentário `── Auto-generated VTT parser ──`) | [autor] (leitura do output do YouTube) | repo `pushed_at` 2026-04-04; acedido 2026-11-08 | alta (coerente com #3/#4) |
| 21 | `>>` no início da linha 2 marca mudança de falante no VTT auto | RB `captionParser.ts` (mesmo bloco) | [autor] | 2026-04-04 | média |
| 22 | ytranscript: `tStartMs`/`dDurationMs` por evento; `kind:"asr"` distingue automática de manual; **não** descreve renderização/roll-up | https://www.nadimtuhin.com/blog/ytranscript-how-it-works | [autor] (documentação da API Innertube) | 2026-07-28 | alta |
| 23 | YouTube Subtitle Fix: "Prefers two-line subtitles when possible", "Allows three lines only when needed", `maxCharsPerLine` 44/45 — é a **heurística do script** sobre o DOM, não o algoritmo do YouTube | https://github.com/SDavid33/youtube-subtitle-fix (README, secção *What it does*); `tampermonkey.user.js:40` (`maxCharsPerLine: 45`) | [autor] | README sem data; acedido 2026-11-08 | alta (é do autor) |
| 24 | YouTube Subtitle Fix 1.2.10: "Reduced the brief unformatted subtitle flash by running subtitle processing immediately on caption DOM changes" — confirma que o flash existe e é do pipeline de mutação do autor | mesmo README, *Changelog 1.2.10* | [autor] (observação) | sem data no README; acedido 2026-11-08 | média |
| 25 | A tabela da "extensão bilíngue" (largura 84 unidades, pausa 1,3 s, bloco máx 7 s, exibição mín 1 s / máx 5 s, anti-flicker 1,2 s) são regras **do autor da extensão**, não parâmetros do YouTube | `local://paste-1.md` (o próprio paste diz: "Atenção: esses números são regras implementadas pelo autor da extensão, não parâmetros confirmados do YouTube") | [autor] | paste do dono; acedido 2026-11-08 | alta na classificação; **fonte primária não recuperada** (ver §4) |
| 26 | Definição de roll-up: 2/3/4 linhas visíveis; cada linha nova entra em baixo e empurra as outras para cima, a de topo desaparece; usado por live/ASR | https://www.w3.org/community/texttracks/wiki/RollupCaptions (secção *Technical Requirements*) | [W3C] | wiki sem data; acedido 2026-11-08 | alta (definição), não é implementação |
| 27 | O mesmo wiki documenta o XML proprietário antigo do YouTube (`<window rc="4">`, `<text append="1">` por fragmento de palavra, ~66 ms entre fragmentos) | W3C RollupCaptions, *Existing Formats → 1. YouTube proprietary XML* | [W3C] a citar [YT-payload] antigo | sem data; acedido 2026-11-08 | média (formato histórico, não o player 2026) |
| 28 | No repo, a spec medida com a fixture do player já fixa: 2 linhas (`rcRows`), 40 colunas (`ccCols`), máx 42 caracteres/linha, 0 palavras partidas, palavra = `tStartMs + tOffsetMs`, exit 0,424–0,552 s (modelo 0,45 s), 16/16 quadros | `docs/youtube-caption-spec.md` linhas 26-52 e 60-90; fixture `_main/fixtures/yt-WdaHAGRBB6s.en-orig.json3` | [YT-payload] medido internamente | spec do repo 2026-11-06/08 | alta (medição interna) |

---

## 2. O que a medição no player tem de decidir

As perguntas abaixo são as que o código **não** fecha sozinho: o código diz o que o player *pode*
fazer; só uma sessão viva diz o que ele *fez* nesta build, neste vídeo, em pt-BR. Todas são
respondíveis com CDP/DOM na sessão própria (headless), sem tocar no ecrã do dono.

**Q1 — O payload ASR pt-BR de hoje traz `mhModeHint:2` e `rcRows:2`?**
Responde: capturar o `timedtext` que o player pede e assertar as chaves. Esperado por #3/#4:
`wsWinStyles[].mhModeHint==2`, `wpWinPositions[].rcRows==2`, `ccCols==40`.
Se vier 0/1 ou sem `wpWinPositions`, a afirmação "ASR = roll-up declarado" cai para este vídeo.
Isto não está medido no repo: a fixture `WdaHAGRBB6s` é de um vídeo, não de pt-BR.

**Q2 — A janela tem a classe e o clip?**
Responde: `document.querySelector('#ytp-caption-window-container .caption-window')` →
`classList.contains('ytp-caption-window-rollup')`, `getComputedStyle(el).overflow==='hidden'`,
`el.offsetHeight` ≈ 2 × altura de `.caption-visual-line`.
Esperado por #1/#11: sim, e altura = 2 linhas.

**Q3 — A transição computada é `transform 0.433s cubic-bezier(0,0,0.2,1)`?**
Responde: amostrar `getComputedStyle(document.querySelector('.captions-text'))` **durante** um
`ytp-rollup-mode`: `transitionProperty==='transform'`, `transitionDuration==='0.433s'`,
`transitionTimingFunction==='cubic-bezier(0, 0, 0.2, 1)'`.
Este é o único modo de fechar a linha 15/16 (o live CSS está minificado e o tool trunca a linha).
Se a build 2026 tiver mudado a curva/duração, é esta pergunta que o diz.

**Q4 — O movimento é só `transform`, e é exactamente uma altura de linha?**
Responde: por `requestAnimationFrame`, ler a matriz de `.captions-text` (`f` = translateY),
`opacity`, `el.getBoundingClientRect()` e `window.getComputedStyle(win).height` antes/meio/depois.
Esperado por #12/#17: `opacity` constante 1, topo/altura da caixa constantes, `ΔtranslateY` =
altura de **uma** linha (não da caixa), sinal negativo. Isto é o que o dono chama "a linha
anterior sobe"; se `Δ` ≠ 1 linha, a imitação está errada.

**Q5 — Quanto tempo até assentar (400–470 ms)?**
Responde: `transitionend` em `.captions-text` + timestamps de `performance.now()`.
Esperado por #14/#15: ~433 ms. A spec interna mede 0,424–0,552 s por UIA; o bracket contém 433,
mas a UIA não distingue 433 de 450 — esta pergunta distingue.

**Q6 — A classe é adicionada e removida em cada linha, ou fica presa?**
Responde: `MutationObserver` em `attributes:['class']` no `.caption-window`, contar
`ytp-rollup-mode` por linha. Esperado por #13/#14: um add + um remove por subida (removida no
`transitionend`), e **nenhum** add quando o texto encolhe.
Se ficar presa, a próxima subida começa com a transição já armada e o tempo real muda.

**Q7 — A linha nova já está no DOM quando o `transform` muda?**
Responde: `MutationObserver` com `childList` (`.captions-text`) e `attributes:['style']` no mesmo
observer; comparar `performance.now()`/`MutationRecord` order. Esperado por #7/#12: `childList`
antes do `style`, na mesma task/frame.
Se o `transform` vier antes da linha, a linha "salta" no fim em vez de entrar a deslizar.

**Q8 — A primeira linha de uma janela nova anima?**
Responde: forçar legendas OFF→ON e amostrar `transform`/`opacity` nos primeiros frames.
Esperado por #19: sem transição, texto aparece já na posição final.
Se animar, #19 cai e a entrada tem uma animação própria que ainda não vimos no código.

**Q9 — Seek/pausa/velocidade: salto ou transição?**
Responde: seek para o meio de uma faixa, `playbackRate=2`, e medir. Esperado por #13: sem classe
quando o offset é recalculado do zero (`gw===0`), logo salto; o `transform` é recalculado em
`Br`, não interpolado.

**Q10 — A palavra aparece no instante `tStartMs + tOffsetMs`?**
Responde: por palavra nova (`childList` em `.caption-visual-line`), ler
`video.currentTime*1000` e comparar com o payload.
Esperado por #6: uma palavra por instante, não a linha inteira de uma vez; desvio < 1 frame.
A spec interna já viu 15/16 concordâncias por UIA; isto fecha o 16.º.

**Q11 — Quantos `.caption-visual-line` existem vs quantos estão visíveis?**
Responde: contar nós e interseção com `getBoundingClientRect()` da janela.
Esperado por #11/#18: **mais de 2 nós** no DOM ao longo do vídeo, 2 visíveis (mais a que está a
sair durante 433 ms). Isto é o que obriga a imitar "stack que cresce + clip", não "2 divs
reciclados".

**Q12 — A quebra de linha é sempre do browser dentro de uma `caption-visual-line`, ou há cues
com `\n`?**
Responde: para cada linha, comparar `offsetHeight` com a altura de uma linha e inspecionar
`textContent` por `\n`; cruzar com eventos sem `aAppend` do payload.
Esperado por #7/#10: novas linhas = eventos sem `aAppend`; `\n` não aparece em modo 2 (#8);
quebra por wrap só quando o texto excede a largura (spec interna: 0 palavras partidas em 19 linhas).

---

## 3. Números que NÃO são do YouTube (anti-confusão)

| Número | De quem é | Onde | Porque não serve para imitar o player |
|---|---|---|---|
| 84 unidades de largura | autor da extensão bilíngue | `local://paste-1.md` | O payload do YouTube declara `ccCols: 40`; 84 é unidade do autor |
| pausa 1,3 s / bloco máx 7 s / mín 1 s / máx 5 s | autor da extensão bilíngue | `local://paste-1.md` | Cadência de segmentação do autor; o player segue os eventos do payload (no sample: 2,0 / 1,28 / 1,28 s entre linhas) |
| anti-flicker 1,2 s | autor da extensão bilíngue | `local://paste-1.md` | Não existe no CSS/JS do player |
| `maxCharsPerLine` 44/45, "prefer 2 lines" | autor do YouTube Subtitle Fix | README + `tampermonkey.user.js:40` | Heurística sobre o DOM depois de o player já ter quebrado |
| 2 linhas visíveis | **YouTube** | `rcRows:2` no payload + `zq` no `qsU` | Coincide com o "prefer 2 lines" do autor, mas a origem é o payload |
| 10 ms (cues de transição) | **YouTube** (formato VTT), lido por autor | RB `captionParser.ts` | É o cue de carry-forward, não a animação |

---

## 4. Lacunas e o que não foi possível fechar

1. **Fonte primária da extensão bilíngue**: a página citada no paste não resolve
   (`https://zenn.dev/taikuyu/articles/9bc1c322898e3b4` → HTTP 404 em 2026-11-08). Os números
   ficam classificados como *do autor* com base no próprio paste; nenhum deles é usado como
   prior do YouTube. Não gastei mais buscas: o paste já declara a autoria.
2. **Transição CSS na build 2026**: o live `www-player.css` está minificado numa linha e a
   tool trunca a 512 B; a regra exacta foi lida de um espelho formatado de 2023-07-24. O JS
   live usa 433 ms (#14), o que corrobora a duração; a letra exacta fecha em Q3.
3. **Payload pt-BR**: não capturado nesta recolha. #3/#4 são capturas de terceiros (inglês e
   coreano), sem data. O parser live ainda lê `wsWinStyles`/`wpWinPositions` (#2), o que torna
   improvável que o formato tenha morrido, mas não é medição do vídeo do dono. Q1 fecha.
4. **Primeiro frame da primeira linha** (#19): inferido do código (sem valor anterior de
   `transform`), não observado. Q8 fecha.
5. **Hora local**: a toolset não tem shell/relógio; todas as linhas levam a data (2026-11-08),
   nenhuma leva hora inventada.
