# A BATERIA FALHOU, E A FALHA E MINHA: `ARM help` no `run-cmd-exit-oracle`

2026-10-13. `node _main/instruments-battery.mjs` -> **SUMMARY: 88/89 instrument(s) rc=0;
failed=1; launches=0**. O instrumento que falha e `run-cmd-exit-oracle.py`, e falhou em
**DUAS corridas separadas** com o mesmo braco -- logo e reprodutivel, nao e flake.

```
ARM help          rc=0 want=0 ms=959 FAIL
ARM-VERDICT      FAIL  failed arms=[help]
GAP-VERDICT      PASS  all 4 gaps green
CENSUS-VERDICT   PASS  243 samples, 0 with a visible window
```

## O que a linha diz, lida com cuidado

`rc=0 want=0` -- **o codigo de saida esta CORRECTO.** O braco falha por isso noutra
condicao, e o proprio oraculo diz qual e o objectivo: a saida do `run.cmd --help` tem de ser
estavel (`--check-args` e `help=argparse.SUPPRESS`, por isso o pre-voo nao deve mudar o help).

**Notei tambem que `ms=959` onde o registo historico andava perto de 250 ms** -- o braco ficou
mais lento, e a saida mede algo que nao devia ter mudado.

## O que EU sei que mudei hoje nesse caminho

* `_open_log` ganhou a rotacao (`1b21cf8`): `os.path.getsize`, e sobre o cap uma leitura da
  cauda + `os.replace`. **O pre-voo `--check-args` corre `import webview` e depois argparse
  imprime o help e sai** -- a nao ser que algum caminho meu faca `_open_log` correr antes.
* Acrescentei linhas ao shell (guarda de idempotencia do `set_panel_surface`, `queue_drops`
  na whitelist, e os comentarios). Se algum destes caiu num DOCSTRING que o argparse imprima,
  a saida muda.

## O que NAO consegui determinar, e e a razao deste recibo

**NAO sei qual das minhas mudancas alterou a saida do `--help`, nem quanto.** Tentei correr o
`--help` e medir a saida e nao consegui ler o resultado -- as minhas ultimas tentativas
rebentaram (output vazio, comando malformado). **Nao vou adivinhar o diff.**

O passo seguinte e obvio e barato: correr `run.cmd --help > agora.txt`, comparar com o pino de
`4956 B` que o AGENTS.md carrega, e ver a primeira linha que difere. **Com o diff na mao a
causa e de uma linha; sem ele, seria a quinta vez que eu afirmava sem medir.**

## O que isto significa, dito sem rodeio

**A rede de seguranca desta sessao esta VERMELHA, e a falha e minha.** Todos os fixes de P0
que fiz desde a ultima bateria verde (a guarda da shell, a whitelist do `queue_drops`) estao
por cima de um vermelho que eu proprio introduzi. **Nao os vou apresentar como verificados
por bateria.**
