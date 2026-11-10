# RECIBO — a linha que sai em CIRILICO do motor de lote (2026-11-10)

Tudo o que segue foi medido nesta arvore, hoje. Onde ha um numero, o comando que o produziu
esta do lado; nenhum veio de log velho.

## 1. O que estava a acontecer, contado na corpus do dono

`history/2026-11-0*/*.md`, 20 ficheiros, 1166 linhas de legenda:

| | |
|---|---|
| linhas com escrita de outro alfabeto | **25** |
| das 25, `producer=redux` (motor de lote) | **25** — nenhuma do motor ao vivo |
| linhas latinas | 1141 |

Os exemplos, verbatim (arquivo:linha):

```
12.md:20   - [12:52:42] Тава кусада, движе.
12.md:26   - [12:53:11] Бандай, всем привет!
13.md:23   - [13:38:19] Σκάστο μονίνεται ορημαθείο, νούτο το κόκκινο.
01.md:39   - [01:44:51] Unreal text. Gotta make you Я говорю на кем I gotta let you now.
00.md:31   - [00:20:04] Sobre Видите, как са...
```

A ultima e' a forma que mais custa: a linha comeca em ingles, acerta, e **escorrega** para
outra lingua a meio. Nao e' fala mal reconhecida — e' o modelo a mudar de idioma dentro da
janela, o mesmo mecanismo que o `Mmm` que a `caption_noise` ja' cura.

## 2. A cura, e por que ela e' um predicado por LINHA

`worker/caption_noise.py`:

* `_SCRIPT_RUN` = um bloco de >=2 letras de **cirilico, grego, hebraico, arabe, thai, kana,
  han ou hangul**. O motor de fundo e' `parakeet`/ingles: a escrita dele e' latina, sempre, e
  um bloco de outro alfabeto so' pode ser alucinacao.
* `is_foreign_script_caption()` julga a linha INTEIRA (como o `is_noise_caption`): a janela
  vizinha re-decodifica a cauda, e meia linha estrangeira nao e' meia transcricao — e' uma
  errada.
* `admit_batch_caption()` continua a ser o UNICO ponto de admissao do lote e passa a contar
  `script_lines` ao lado de `noise_lines`. Dois contadores, nao um: com um so', o log do dono
  nao distinguiria as duas regras.
* `engine_policy.run_engine_pass` zera os dois por passe e publica
  `script_lines=<n>` na linha `REDUX_ENGINE_DONE`.

Limiar 2 e nao 3: uma palavra estrangeira comeca com duas letras, e o corpus dele nunca
mostrou um caso de defeito com uma letra so' — entao uma letra isolada (`Я`, uma sigla) fica.

## 3. O que foi medido ao escrever a cura

```
python worker/caption_noise.py --selftest
  ...
  PASS foreign-script captions are refused -- []
  PASS latin captions are not refused -- []
  PASS a cyrillic window publishes nothing and the real one survives
  PASS the batch log says script_lines=1, not noise_lines
  PASS corpus: refused == lines with foreign script, zero latin refused
       -- {"files": 20, "foreign": 25, "refused": 25, "latin": 1141, "unexpected": []}
  PASS negative arm re-breaks it (both noise windows publish)
  PASS negative arm of the script rule (the cyrillic window publishes again)
  {"ok": true, "cases": 13, "caught": 13, "neg_arm": "PASS", "neg_arm_script": "PASS"}
  NEG-ARM: PASS                                                          rc=0
```

Dois bracos negativos, de proposito: um desarma `_NOISE_WORD` e o outro desarma `_SCRIPT_RUN`.
Um negativo que so' derrubasse o `Mmm` deixaria a regra nova sem prova nenhuma — a classe
"um controlo que nao pode falhar", do lado de quem acha que provou as duas metades.

O braco da corpus mede a COBERTURA do padrao, nao o repete: `refused == with_foreign`. Se um
intervalo do `_SCRIPT_CLASS` faltasse (esquecer o grego, por exemplo), `refused` cairia abaixo
de `with_foreign` e o numero denunciava-o. Num worktree sem `history/` o braco diz
`SKIP corpus` e nao conta como verde.

## 4. Custo

O predicado e' um `re.search` sobre uma classe de caracteres por janela de 3 s: ~2 us, ao lado
dos ~0,745 s de computo do motor de lote medidos em 14,6 s de audio. Nao ha segundo decode,
nem modelo, nem disco.

## 5. O que NAO esta' verificado

* Nenhuma desta linha foi vista no ecra do dono: a prova e' o `--selftest` e a corpus DELE, que
  e' historico em disco, nao a app viva. `fixed, NOT verified` ate' uma rodada real.
* O motor AO VIVO (nemotron) nao passa por este choke point — as 25 linhas medidas eram todas
  `producer=redux`. Se o ao vivo tambem escorregar para outro alfabeto, o predicado serve, mas
  o call site dele e' outro e este recibo nao o cobre.
