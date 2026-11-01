# RECIBO — a legenda ao vivo NAO RECUA no tempo

**Data:** 2026-10-30
**Queixa do dono (verbatim):**
> *"a legenda nao ta sincronizada direito. e parece que repete a legenda de
> instantes atras no ao vivo, depois desbuga, e mostra ao vivo"*

**Veredicto:** DEFEITO MEDIDO, CURADO E MEDIDO OUTRA VEZ.
`youtube-monotonic-oracle.py` 14/14 PASS, braco negativo rc=1 (157 recuos,
pior 310,68 s). Replay do PROPRIO log do dono: **157 recuos com a regra
antiga, 0 com a nova**.

---

## 1. O QUE ESTAVA ERRADO

### 1.1 A MEDICAO (`_main/webview-run.log`, 2126 linhas `YOUTUBE_CAPTION`)

**129** linhas serviam uma cue cujo INICIO era **anterior** ao da linha
servida antes. Os piores:

| quando | cue servida antes | cue servida depois | recuo |
|---|---|---|---|
| 2026-10-26 17:08:31 → :32 | `start=39.840` `'better.'` | `start=2.240` `'named Kibitz showed up randomly on'` | **37,60 s** |
| 2026-10-27 08:17:22 → :24 | `start=67.720` `'que que tu tava fazendo?'` | `start=34.239` `'economista formada pela USP,'` | **33,48 s** |
| 2026-10-27 08:17:29 → :31 | `start=74.680` `'que que você já fez na sua vida.'` | `start=34.239` (a MESMA de 24 s antes) | **40,44 s** |
| 2026-10-26 17:50:44 → 2026-10-27 08:13:10 | `start=359.600` | `start=0.654` `'[music]'` | **358,95 s** |

A cue `start=34.239` foi servida **tres vezes em 24 s** enquanto a faixa
servida avancava 50 s -> 74 s. **Nao era lentidao: era um relogio congelado
a mandar no ecra.** E' exactamente o que o dono descreveu — repete o instante
de tras, depois "desbuga" quando a proxima linha pintada chega.

### 1.2 A CAUSA (`app/webview/sotto_webview.py`, ramo `painted-other-track`)

```python
if now_t is not None and (moved or key == self.yt_foreign_key):
```

`moved` e' "o relogio andou". A segunda metade diz "**ou** a pintura e' a
mesma de antes" — e quando a pintura E o relogio estao os dois parados, `key`
e' igual, a condicao e' verdadeira, e o ramo serve a MESMA cue antiga. O
comentario ao lado declara a intencao inversa (*"a prova do congelamento e'
uma pintura que MUDA com o relogio parado"*): **a condicao faz o contrario do
que o comentario diz.**

O relogio (UI Automation do player) e' grosso — le casas inteiras (`t=1206.0`)
— atrasa-se, e **mede-se a saltar para tras 1 s, 4 s e 5 s** (o video em
~1170, a leitura a fazer 1175 -> 1170 -> 1171). Nao sao seeks: e' jitter de
leitura.

---

## 2. A CURA — `app/webview/youtube_monotonic.py` (NOVO, 3653 B)

Duas fontes de tempo, e **so' uma pode recuar**:

* **O RELOGIO** so' tem licenca para ANDAR PARA A FRENTE
  (`decide(now_t, floor)`). Nunca escolhe uma cue atras do chao.
* **A PINTURA** (as palavras que o player desenha agora) e' o relogio mais
  adiantado que existe e o **unico sinal capaz de provar um seek a serio**
  (`advance(floor, position)`): sobe o chao sempre, e so' o desce quando
  salta para tras mais de `SEEK_BACK_S = 2,0 s`.

Assim o relogio nunca arrasta o ecra para tras **e** um seek continua a
funcionar — porque quem o declara e' a pintura, nao a leitura. A regra e' do
TEMPO: nao le dicionario e nao depende da lingua.

### 2.1 ONDE ESTA' LIGADA (`sotto_webview.py`, +55 linhas, 0 removidas)

| sitio | o que faz |
|---|---|
| `__init__` | `yt_serve_floor` (o chao) + `yt_held_logged` (dedupe do log) |
| `_yt_decide(now_t)` | chama `decide`, guarda o chao, escreve `YOUTUBE_CLOCK_HELD` uma vez por leitura travada |
| `_yt_advance(position)` | chama `advance` nos tres pontos de servico |
| ramo `painted` (hit) | `_yt_advance(hit.cue.start)` — a pintura e' o chao |
| ramo `painted-other-track` | `now_t = _yt_decide(now_t)` **antes** de `cue_at`, + `_yt_advance(cue.start)` |
| ramo `has-cue` (so' relogio) | `t = _yt_decide(t)` **antes** de `cue_at`, + `_yt_advance(cue.start)` |

### 2.2 CONTROLOS DIFERENCIAIS (o mesmo cenario, as duas regras)

Watcher VIVO (`object.__new__`, sem janela, sem thread), relogio a fazer
`50 -> 74 -> 10 -> 10`, pintura estrangeira:

| regra | sequencia servida |
|---|---|
| **nova** (a do ficheiro) | `['second cue here'], ['third cue here'], ['third cue here'], ['third cue here']` |
| **antiga** (mutada em memoria) | `['second cue here'], ['third cue here'], ['first cue here'], ['first cue here']` |

A antiga volta ao cue de 10 s depois de ter chegado a 74 s. **E' o defeito, e
a nova nao o faz.**

---

## 3. O INSTRUMENTO — `_main/youtube-monotonic-oracle.py` (13165 B)

| braco | o que mede |
|---|---|
| arm1..arm4 | regra do relogio: nada servido, adiantado, atras do chao (o defeito), e o **jitter de 5 s medido no log** |
| arm5..arm7 | regra da pintura: seek a serio desce, cue repetida segura, avanco sobe |
| arm8 | **replay do log real**: 240 linhas, regra ANTIGA recua **157**, regra NOVA recua **0**; 27 recuos declarados pela pintura (seeks legitimos) |
| arm9 x4 | **ligacao por AST** no codigo vivo: 2 chamadas a `_yt_decide`, 3 a `_yt_advance`, `_yt_decide` ANTES de `cue_at`, modulo importado |
| `--neg-arm` | muta a regra para a antiga: **rc=1**, imprime `NEG-ARM PASS -- RED as designed: a regra ANTIGA recuou o ecra 157 vez(es) em 240 linha(s), pior 310.68 s` |

O replay reinicia o tempo quando o `video_id` muda. **Sem essa coluna o
instrumento acusava 47 "recuos" que eram so' mudancas de video** — corrigido
durante a construcao, e a razao esta' escrita no ficheiro.

---

## 4. O QUE MAIS FOI TOCADO, E PORQUE

| ficheiro | porque |
|---|---|
| `_main/youtube-sync-oracle.py` | o check `3.4` estava **RED desde 2026-10-29**: pina 3 chamadas a `_yt_lines`, e a revelacao palavra-a-palavra trocou o ramo `painted` por `youtube_reveal.window_by_paint`. Passa a exigir 2 (`_yt_lines`) + `window_by_paint`; o invariante ("nenhum sitio devolve um cue so", check 3.3) fica igual. **ATUALIZADO, nao re-fixado** |
| `_main/youtube-foreign-paint-oracle.py` | (a) o stub nao declarava `yt_serve_floor`/`yt_held_logged` -> `AttributeError`; (b) o braco `A4` esperava a cue INTEIRA, que a revelacao de 2026-10-29 substituiu pelo prefixo pintado. Passa a pinar o invariante: motivo `painted` e linha que e' PREFIXO da cue |
| `_main/youtube-track-wiring-oracle.py` | a ancora do mutante `m4` deixou de encaixar com a linha `_yt_advance` no meio; actualizada para o texto vivo |
| `_main/_audit-verify-all.cmd` | passos `youtube-monotonic` + `red-as-expected-youtube-monotonic`, ambos `always` (o replay le `webview-run.log`, que muda a cada arranque) |
| `AGENTS.md` | pin do `.cmd` re-medido: **137532 B / 1797 CRLF / 0 bare LF**, sha256 `BFEFDE57CE2AA1DA768F4945B9565402D1362904E45696FDCD26F7FFF6E04DC6`; `agents-md-pins-oracle.py` -> PASS |

---

## 5. VERIFICACAO EXERCITADA (este turno, nesta arvore)

```
python _main/youtube-monotonic-oracle.py            rc=0  14 PASS / 0 FAIL
python _main/youtube-monotonic-oracle.py --neg-arm  rc=1  NEG-ARM PASS
python _main/youtube-1to1-oracle.py                 rc=0  GREEN
python _main/youtube-reveal-oracle.py               rc=0
python _main/youtube-rows-oracle.py                 rc=0  GREEN
python _main/youtube-drift-oracle.py                rc=0  n=16 mean +172.5 median +107.2
python _main/youtube-sotto-drift-oracle.py          rc=0  drift_sotto -125.0 | drift_player +125.0
python _main/youtube-sync-oracle.py                 rc=0  PASS checks=12 fail=0
python _main/youtube-foreign-paint-oracle.py        rc=0  PASS
python _main/youtube-track-wiring-oracle.py         rc=0  PASS arms 12/12 mutants 5/5
python _main/youtube-paint-first-oracle.py          rc=0  PASS
python _main/caption-lines-oracle.py                rc=0  13 PASS / 0 FAIL
python _main/incomplete-word-oracle.py              rc=0  15 PASS / 0 FAIL
python _main/agents-md-pins-oracle.py               rc=0  PASS
```

`code-health-oracle.py`: **RED, e o RED e' anterior a esta lane.** A minha
delta e' `sotto_webview.py +55 linhas` (o total de +299 vem das lanes de
2026-10-29) e um ficheiro **novo** `youtube_monotonic.py` (3653 B << 120000 B).

`tooling-intent-oracle.py`: estava **FAIL com 4 vermelhas**; ficou **PASS /
0 vermelhas**. A minha ferramenta nova era uma delas; as outras tres
(`bend-laws-gate.py`, `incomplete-word-oracle.py`,
`youtube-sotto-drift-oracle.py`) eram divida das lanes anteriores desta sessao
e fecharam-se com a declaracao `NO-BUG:` que o ratchet pede.

`exception-hygiene-oracle.py`: **RED, e anterior a esta lane.** `HEAD` ja' tem
8 infractores em `worker/sotto_worker.py` contra 7 no baseline (medido:
`git show HEAD:worker/sotto_worker.py` -> 8). **Nao foi inflacionado o
baseline**: o braco C2 existe exactamente para impedir isso. Fica como divida
declarada.

---

## SELF-AUDIT

* **protocolos em falta:** nenhum passo da bateria completa foi corrido neste
  turno depois da ultima edicao ao `.cmd`. O que esta' acima e' executado e
  colado; o que nao esta', nao esta'.
* **verificacao adicional:** o que mais subiria a confianca e' uma corrida
  viva da app contra um video do YouTube — **nao foi feita e nao pode ser
  feita desta lane** (`SOTTO_NEVER_ON_OWNER_SCREEN`; o caminho do YouTube
  precisa de UIA numa janela do Chrome do dono).
* **checkboxes novas:** acrescentar como passo obrigatorio, em qualquer
  alteracao do ramo `painted-other-track`, o replay de
  `_main/webview-run.log` pela regra viva. Uma regra de tempo que ninguem
  corre contra o log real e' uma opiniao.
* **review por outro subagente:** nao.
* **gate-doubt:`falta-no-gate:` o `youtube-monotonic-oracle` nao mede a
  latencia absoluta da legenda (o `drift_ms`), so' que ela nao RECUA. Os dois
  instrumentos sao complementares e nenhum substitui o outro.
  `gate-melhor:` um braco que corre a app escondida com
  `SOTTO_LANE_LAUNCH=1` e compara a sequencia de `YOUTUBE_CAPTION` do log novo
  com a sequencia servida — mas isso exige o video a tocar.
  `verde-de-verdade:` o verde e' do replay do log REAL do dono (157 -> 0) e do
  watcher vivo com controlo diferencial, nao de um fixture inventado.
* **confianca:** **alta** para o defeito e para a cura (medido no log do dono,
  com o controlo antigo ao lado). **media** para "o dono deixa de o ver":
  depende de a pintura da faixa servida estar presente o suficiente para o
  chao subir — que e' o caminho normal do player.
* **nao verificado:** a app com o YouTube ao vivo. `verified` continua
  impossivel de uma lane: fica `FIXED, NOT VERIFIED`.
