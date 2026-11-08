# Politica de lingua do track do YouTube (ORDEM 1)

## A LEI EM VIGOR (ordem do dono, 2026-11-08, verbatim)

> *"eu ja falei pra NAO traduzir entre pt br ingles e espanhol entre si. mas pra traduzir o resto
> pra linguagem que eu escolhi pro sotto. que no caso é pt br. entao eu to vendo um anime agora, e a
> legenda ta aparecendo japones."*
> *"e faz o botao de config pra eu escolher pra qual lingua traduzir."*

| língua ORIGINAL do vídeo | o que é servido |
|---|---|
| inglês, português ou espanhol | **a própria língua, e nada mais** — nenhuma tradução em nenhuma direcção entre as três (a metade de 2026-10-30 que continua inteira) |
| qualquer outra (chinês, japonês, alemão…) | **a língua ESCOLHIDA pelo dono** — persistida, `DEFAULT_TARGET = 'pt'` — e a língua do vídeo só como **segundo** pedido, para quando a tradução escolhida não exista |

Implementação: `app/webview/caption_settings.py` guarda a escolha (`DEFAULT_TARGET = 'pt'`,
`path()` com `SOTTO_CAPTION_SETTINGS`, `load()`, `save()`, `target_lang()`, `set_target_lang(code)`).
`app/webview/youtube_captions.py` lê-a no import (`TARGET_LANG = _caption_settings.target_lang()`),
grava-a em `set_target_language(code)` (`''` volta ao default persistido) e `_target_langs(orig)`
devolve `(base,)` para en/pt/es, `(base,)` quando o alvo é a própria língua do vídeo, e
`(target, orig)` no resto — **o alvo primeiro**, o original como último recurso.

**MEDIDO 2026-11-08 (executado, não lido):** `_target_langs('ja') == ('pt', 'ja')`;
`_target_langs('en') == ('en',)`; `_target_langs('pt') == ('pt',)`; com a escolha `fr`:
`_target_langs('ja') == ('fr', 'ja')` e `_target_langs('en') == ('en',)`; com a escolha `ja`:
`_target_langs('ja') == ('ja',)` (uma só entrada — pedir a "tradução" para a própria língua seria
pedir a mesma faixa duas vezes). A escolha sobrevive a um **import novo** e um ficheiro
corrompido/ausente responde `'pt'`.

**A ESCOLHA EXPLÍCITA NÃO É UM BURACO NA REGRA.** Um `pick` nunca traduz um vídeo en/pt/es: a
resposta é sempre a própria língua desses três (`a59`, 3 origens × 5 escolhas). Fora dos três, o
`pick` **é honrado** (`a60`, 4 línguas × 7 escolhas), ao contrário do desenho de 2026-10-30, que o
fechava em inglês. Portão: `python _main/youtube-captions-oracle.py` → **66 arms / 18 mutantes**;
`--neg-arm` sai **1 por desenho** com `18/18` apanhados.

## A REGRA ABSOLUTA DE 2026-10-30 — a metade "outras línguas → inglês" está SUBSTITUÍDA (histórico)

> **SUBSTITUÍDA em 2026-11-08 pela ordem acima.** O que fica de pé é a primeira metade (en/pt/es, a
> própria língua). O texto abaixo mantém-se para ninguém a "arrumar" de volta: **"qualquer outra
> língua vai para inglês" deixou de ser a lei** — vai para a língua escolhida pelo dono, e o inglês
> só aparece se for a escolha dele.

> *"regra nunca que pode ser quebrada: legendas nao traduzem entre ingles pt br e espanhol.
> só outras linguas, todas pro ingles."*

| língua ORIGINAL do vídeo | o que era servido (até 2026-11-08) |
|---|---|
| inglês, português ou espanhol | **a própria língua, e nada mais** — nenhuma tradução em nenhuma direcção entre as três (**ainda em vigor**) |
| qualquer outra (chinês, japonês, alemão…) | ~~**inglês** (a auto-tradução do YouTube), e a língua do vídeo só como último recurso~~ — **SUBSTITUÍDO: a língua escolhida, `pt` por omissão** |

A implementação da metade substituída vivia em `TARGET_LANG = 'en'` e em `a60` ("qualquer outra
língua vai SEMPRE para INGLES, escolha ou nao"). **Foi exactamente esse desenho que produziu o
defeito que ele viu**: para um anime japonês sem faixa inglesa, `_target_langs` devolvia
`('en', 'ja')` — o inglês não existe, e o "segundo pedido" era a própria faixa japonesa, logo a
legenda saía em japonês. `a49` e `a60` foram reescritos para a lei nova em 2026-11-08.

`UNTRANSLATED_LANGS = ('en', 'pt', 'es')` continua a ser o dono único das três línguas intocadas, e
`_target_langs` devolve **um** elemento para elas (sem fallback: um `(orig, 'en')` seria exactamente
a tradução proibida).

> Movido de `AGENTS.md` em 2026-10-23 (trim). Conteudo verbatim;
> a medicao e as ressalvas sao as que la estavam.

### 1. O track da YouTube tem de ser a LÍNGUA ORIGINAL
> *"to vendo que o transcript atual ta sendo traduzido. nao e pra traduzir. e pra ser lingua original.
> quando ingles, e quando pt br. quando chines ou japones, ou qualquer outra, pode traduzir. ah, menos
> espanhol."*

**REGRA SUBSTITUÍDA (2026-10-21) — fica escrita para ninguém a "arrumar" de volta; a regra em
vigor é a de 2026-11-08, no topo deste ficheiro.** O texto abaixo descreve o que o código fazia até
2026-10-30 (espanhol → `es,en`, com fallback inglês; `NEVER_TRANSLATED_LANGS`); os nomes de
símbolo que ele cita (`NEVER_TRANSLATED_LANGS`) **já não existem** — o conjunto passou a
`UNTRANSLATED_LANGS = ('en','pt','es')` e a lista das três passou a ter UM elemento, sem fallback.

**A REGRA DE 2026-10-21 (revista pelo próprio dono mais tarde no MESMO dia):**
*"para de traduzir pra pt br do ingles e do espanhol. o resto, traduza para ingles. qualquer
outra lingua pra ingles."* ⇒ **a legenda é INGLÊS para qualquer vídeo**, e **ESPANHOL** para um
vídeo espanhol (o espanhol **nunca** é traduzido). Implementado em
`app/webview/youtube_captions.py`: `TARGET_LANG = 'en'` (`:464`),
`NEVER_TRANSLATED_LANGS = ('es',)` (`:469`), `_target_langs(orig)` (`:472` — vídeo es → es,en;
vídeo en → en; qualquer outro → en, e a **própria língua** como último recurso, para um vídeo sem
faixa de inglês) e `_original_language(info)` (`:500`, o campo `language`, base `en-US` → `en`).
O portão tem **três** mutantes para a política (a língua original não lida, o destino em
português outra vez, o esquecimento da excepção espanhola) ⇒ **uma política que não se pode
quebrar é um comentário.**

> **A metade "qualquer outra língua pra inglês" também está SUBSTITUÍDA (2026-11-08):** o dono
> mandou traduzir o resto para **a língua que ele escolheu** (`pt` por omissão), e um anime
> japonês saía em japonês por causa do `TARGET_LANG = 'en'` acima — ver a LEI EM VIGOR no topo.
> O que continua em vigor desta regra é só o **nunca traduzir en↔pt↔es** e o **espanhol nunca
> traduzido**.

**A REGRA ANTERIOR (substituída — fica escrita para ninguém a "arrumar" de volta):** original para
**en, pt-BR, es**; tradução **permitida** para zh/ja/qualquer outra; **espanhol NUNCA traduzido.**
O defeito vivia em `app/webview/youtube_captions.py` (`_auto_lang_keys`), que pedia
`pref` (traduzido, `tlang=`) antes de esgotar as chaves `-orig`.

**MEDIDO 2026-10-21 (a chave do defeito):** no vídeo que o dono estava a ver
(`-LODwSuymII`), `yt-dlp` diz **`language = 'en-US'`** — o vídeo é **INGLÊS** — e a
tabela tem **177 línguas**. A entrada portuguesa **não** é a original: é a
**auto-tradução** do YouTube, e o URL dela **não traz `tlang`** — por isso "a chave
que parece original" **não prova** a língua original. **O campo `language` é que
prová.** O serviço servia a **tradução** de um vídeo inglês (e o dono reclamou
exactamente disso). **A CORRECÇÃO (2026-10-21):** `_original_language(info)` (o campo `language`,
base `en-US` → `en`) + `_target_langs(orig)` (a política acima) → a faixa do **player** só conta
se for **da língua que a política pede** (o "1:1 com o vídeo" é sobre a legenda ser **do vídeo**,
não sobre seguir uma tradução que o player ligou). Portão:
`_main/youtube-captions-oracle.py` → **53/53 arms, 13/13 mutantes** (dois novos: a
língua original não lida, e a política a permitir tudo). **Re-medir antes de citar
linha.**
