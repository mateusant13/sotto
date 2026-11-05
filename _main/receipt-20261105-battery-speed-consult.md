# Consulta — como deixar a bateria MUITO mais rapida (gpt/consultgpt, 2026-11-05)

**Pergunta enviada, com o brief completo do projecto:** `I:/cc-tmp/battery-speed-brief.md` (8,8 KB: o
produto, o contrato dos passos, a infra que ja' existe, os numeros medidos, as restricoes da maquina).
**Resposta inteira:** `I:/cc-tmp/gpt-battery-answer.md` (24,4 KB). Sessoes `sotto-battery-speed` /
`sotto-battery-speed-2` no consultgpt.

---

## 1. O que o consultor respondeu (estrutura A-F pedida)

**(A) Arquitectura alvo.** Trocar "320 provas = 320 invocacoes" por um **supervisor em Python
manifest-driven**: manifesto imutavel -> grafo de execucao (DAG) -> classificacao por classe -> workers
Python persistentes (P0 puro, P1 fixture/estatica, P2 contrato de produto) + executor de mutacoes
isolado + leitores de log vivo serializados + faixa heavy com lease. A `.cmd` fica como lancador de
compatibilidade. Caches atomica, gates de fio/cobertura/orcamento no fim.

**(B) Mudancas priorizadas (segundos estimados por ele, sobre os 1 362,9 s medidos):**

| # | mudanca | s |
|---|---|---|
| 1 | `red-as-expected` deixa de re-correr o oraculo inteiro: muta a copia e chama **uma arm** | 150–300 |
| 2 | evidencia partilhada com proveniencia (um medidor caro, N consumidores) | 100–250 |
| 3 | interpretadores Python persistentes (amortizar arranque + imports) | 60–100 |
| 4 | tirar imports de produto dos oraculos estaticos | 30–100 |
| 5 | cache a granularidade de ARM, nao de passo | 30–100 |
| 6 | fingerprint por dependencia semantica, nao ficheiro inteiro | 20–80 |
| 7 | paralelismo limitado de P0/P1 (2 workers, nao 8) | 10–40 |
| 8 | fixtures sinteticas imutaveis reutilizadas | 10–30 |

**(C) Invariantes como portoes:** cobertura de oraculos, integridade de dependencias, cobertura de arms
positivas, **eficacia da mutacao** (a mutacao TEM de morder o sitio que ela julga), contrato de rc,
`NEG-ARM ... PASS` no log, hash do produto antes/depois (uma mutacao nunca toca fonte de produto), skip
nunca e' verificado, zero janelas, zero escrita em endpoint de audio, identidade do processo observado,
prazo nunca e' sucesso, job object so' mata o que e' seu, **cache HIT so' significa "esta prova exacta ja'
correu e passou"** (com `mutation_applied` gravado), commit atomico do cache, pagina de estado coerente,
ratchet de orcamento, lease para heavy.

**(D) Apagar:** a `.cmd` de 3 196 linhas como FONTE de verdade (fica como lancador); um processo por
oraculo nos passos P0/P1; a re-execucao do oraculo inteiro por mutacao; a re-medicao quando ja' existe
evidencia validada; dependencias de ficheiro inteiro onde a fronteira semantica existe; politica de
paralelismo por contagem de CPUs; `SKIPPED` lido como `PASS`.

**(E) Contra-medição que falsificaria "mantivemos os invariantes":** contagem de oraculos registados,
arms positivas e negativas executadas OU validamente em cache, mutacoes aplicadas com sucesso, taxa de
rejeicao, skips nao declarados (tem de ser 0), falsos HIT de cache, hashes que nao batem, modificacoes de
fonte por mutacao, dependencias por declarar, tempos de timeout, contaminacao cruzada, janelas criadas,
operacoes de audio, heavy sem lease, e — criterio explicito — **duracao a quente > 60 s**. E separar
sempre `verified_executed` de `verified_cached`, porque uma taxa de HIT alta esconde que a suite parou de
exercitar caminhos.

**(F) Risco #1 dele:** cache demasiado agressivo com lista de dependencias incompleta = confianca falsa;
risco #2: mutacao cerimonial (mutante que nao morde, ou que e' recusado por outra razao).

---

## 2. O que eu MEDI contra as estimativas dele (a correccao que a casa exige)

Ele trabalhou sobre um brief sem o codigo, e disse-o. Estas quatro medicoes foram feitas agora, nesta
maquina, e **contradizem a ordem de grandeza** de dois itens:

| medicao | numero medido | conseque^ncia |
|---|---|---|
| `python -c pass` | **75–90 ms** (min..max de 3) | um processo por passo custa ~0,09 s, nao 250–400 ms |
| `python -c "import sys,os,json"` | 69–85 ms | idem |
| `import app.webview.sotto_webview` (cumulativo) | **0,163 s** / 110 modulos | re-importar o ficheiro de 26 k linhas nao custa 1 s |
| `import worker.sotto_worker` (cumulativo) | **0,180 s** / 106 modulos | idem |

Logo o **tecto absoluto** dos itens 3+4 (workers persistentes + tirar imports) e' da ordem de
`261 x 0,09 s ≈ 23 s` de arranque + no maximo `~42 s` (261 x 0,163 s) se TODOS os passos pequenos
importassem um dos modulos grandes — e a maioria nao importa. Realista: **40–60 s**, nao 90–200 s. Os
itens 1 e 2 continuam a ser os grandes, e o item 1 e' o unico que mexe na cauda pesada medida
(`red-as-expected-*`: 65,0 + 60,2 + 46,8 + 43,7 + 40,0 + 36,2 = **291,9 s em SEIS passos**).

Consequencia de plano: **nao** comecar pelos workers persistentes (item 3); comecar por (1) e (2), que
atacam onde o tempo esta' de facto, e so' depois o custo por passo.

---

## 3. O que eu vou adoptar, e em que ordem

1. **Arm-alvo nas mutacoes** (item 1). Contrato por oraculo: `positive_arm()`, `negative_arm(mut)`,
   `measure()`; o passo `red-as-expected-*` muta a copia e chama SO' as arms que aquele mutante julga
   (`MUTANTS` ja' tem `judges`). Prova: o passo tem de continuar a dar rc=1 e a nomear o mutante.
2. **Eficacia da mutacao como portao** (o risco #2 dele, que a casa ja' viu: `UNMUTABLE` num oraculo
   significa passo cerimonial). `count(old) != 1` -> RED, nunca "survived".
3. **`verified_executed` vs `verified_cached` no registo do cache** e na pagina de estado (contra-medicao
   (E) que hoje nao existe: o cache grava `elapsed_s`/`log_sha256`, nao a proveniencia da mutacao).
4. **Fingerprint por dependencia semantica** (item 6) SO' onde houver portao que prove a fronteira —
   senao e' o risco #1 dele. A regra da casa ja' existe: "uma dependencia que nao nomeia o ficheiro
   deixaria o passo em cache a descrever um codigo que ja' mudou".
5. **Paralelismo limitado** (item 7) por ultimo, com 2 workers P0/P1 e travado pelo estado do gate da
   frota, porque esta maquina congelou uma vez por causa de trabalho paralelo.

**Nao adoptado por decisao:** tirar a `.cmd` como fonte de verdade enquanto a corrida nao puder ser
provada equivalente (o interior da `.cmd` e' a unica coisa que um leitor humano consegue auditar hoje,
e a substituicao exige um manifesto que ainda nao existe); e qualquer mudanca de classe de um passo para
"ganhar tempo" — a classe e' lida do comando, nao escolhida.
