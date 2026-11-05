# Recibo — `parakeet-ultra` (moondream) contra o `parakeet redux` (ONNX int4), o mesmo audio

**Data:** 2026-11-04 23:43–23:47 · **Máquina:** a do dono, gate central GREEN (commit 68,3 %), lease `heavy`
`b4e14fd786cd48e39aa01f8699c820c8` (3000 s) · **Instrumento:** `_main/parakeet-ultra-oracle.py` ·
**Código medido:** `worker/parakeet_ultra.py` + o export `I:/cc-tmp/models-src/parakeet-ultra-onnx/`

## VEREDITO: **RECUSADO** — não ganha, custa 3,5× e TRUNCA áudio longo

| engine | carga a frio | 15 s → inferência (xrt) | 90 s → inferência (xrt) | pico RSS | WER (26 palavras) |
|---|---|---|---|---|---|
| **redux** (ONNX int4, o que embarca) | **7,50 s** | **3,626 s** (**4,14×**) | **23,933 s** (**3,76×**) | **1 793 MB** | 0,1154 (2 subs, 1 ins, 0 del) |
| ultra-onnx | 24,36 s | 12,873 s (1,17×) | 62,521 s (1,44×) | 3 837 MB | 0,1154 (2 subs, 1 ins, 0 del) |
| ultra-torch (CUDA fp16) | 21,75 s | 17,048 s (0,88×) | **0,415 s (217×)** — medição INVÁLIDA | 2 132 MB | 0,1154 |

Três factos, cada um sozinho já decide:

1. **A precisão é IDÊNTICA, ao caractere.** No clipe pt-BR os dois produzem a MESMA frase e o mesmo
   WER 0,1154 com os mesmos 2 subs + 1 ins. Não há ganho nenhum de qualidade para comprar.
   ("melhor WER" era a única razão para carregar 2,4 GB em vez de 416 MB.)
2. **Custa 3,5× em tempo e 2,1× em RAM** no clipe de referência, e 3,2× na carga a frio. Num finisher
   de fundo ao lado de um jogo, isso é o oposto do que a pilha quer.
3. **TRUNCA.** No clipe de 90 s o redux devolve 6 frases (62 palavras, do "Eu não consigo pegar mil de
   força" ao "Ó, infônova."); o ultra-onnx devolve **9 palavras** e para em "Luvas do perseguidor.".
   Um motor que perde 85 % de um clipe de 90 s não entra nesta casa, por barato que fosse — e ele
   não é.

## Os dois instrumentos que este run DENUNCIOU (e que ficam por consertar)

- **`peak_vram_mb` lê NEGATIVO** (`-2805.0` no ultra-onnx, `4148.0` no redux). O leitor é um delta de
  VRAM do sistema: quando um motor descarrega, o delta do outro fica negativo. **VRAM = UNMEASURED
  para os três**, e um número que pode ser negativo não é um número a citar.
- **`ultra-torch` no clipe de 90 s: 0,415 s para 90 s de áudio (217×)**, com o texto degradado
  ("Eu não consigoaro de força, não.. lu do perseg seguidor.."). Isso não é velocidade, é o caminho
  `generate` a sair por uma janela errada. A medição está marcada INVÁLIDA e não sustenta nada; o
  arm torch fica no oráculo para quem quiser investigar o caminho, não como número.

## O que ficou no disco e por quê

`worker/parakeet_ultra.py` (369 linhas) e `worker/ultra_export.py` (429) **ficam**: são o instrumento
com que a recusa foi medida e o único caminho que exporta Ultra para o ABI de três grafos do repo.
Os 2,4 GB do export e os 1,2 GB do `.safetensors` **NÃO** entram no repo (gitignored, `*.safetensors`
por `*.bin`-family) nem no caminho de produção: nenhum import novo em `worker/sotto_worker.py`,
`redux_live.py` ou no shell.

Um defeito de instrumento apanhado no caminho, medido: o `assign=True` do `load_state_dict` não
substitui os buffers que o módulo CRIA, e `encoder.encode_positions.inv_freq` ficava em `meta` — o
`.to()` seguinte recusava o passeio inteiro com `Cannot copy out of meta tensor`. O primeiro run
morreu exactamente nisso (145 s, rastreador completo). A cura deixa um placeholder de zeros, faz o
cast, e RECONSTRÓI o `inv_freq` pela função do próprio módulo, em float32 — é uma frequência de
rotação e metade da precisão dela degrada a posição.

## Como re-medir

```
python _main/parakeet-ultra-oracle.py --neg-arm     # prova o juiz de WER, sem modelos: 9/9
python _main/parakeet-ultra-oracle.py --engine all  # os três braços (pesado: ~2 min, 3,8 GB pico)
```

O `--neg-arm` é a razão de este recibo valer: um juiz de WER que não distingue "idêntico" (0,0000) de
"uma substituição" (1/7 = 0,1429), "uma deleção", "uma inserção", "vazio" (7/7) e "tudo errado" (7/7)
não mede WER — mede a si próprio. Medido hoje: **9 casos, 0 divergentes**.
