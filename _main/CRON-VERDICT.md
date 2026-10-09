# CRON VERDICT — o cron dispara. Parou há ~31 horas. POPULAÇÃO = 1442 execuções.

Medido pelo root em 2026-10-07 17:17–17:19 -03:00, leitura read-only
(`file:...?mode=ro`) de `C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite`.

## 1. A RESPOSTA À PERGUNTA DO DONO

O dono perguntou, três vezes: *"o cronjob nao sei se funciona de verdade... tenha
certeza que funcione e dispara."*

**FUNCIONAVA. E PAROU.**

| medição | POPULAÇÃO | valor |
|---|---|---|
| execuções registadas | todas as linhas de `local_runtime_v2_cron_runs` | **1442** |
| entregues | idem | **1433** (99,4 %) |
| falhadas | idem | **9** |
| `trigger_source='scheduled'` | idem | 1442 · **0 manuais** |
| crons distintos com execuções | idem | **24** |
| latência de entrega | das execuções mais recentes | ~159 ms |
| execuções nas últimas 12 h | idem | **0** |
| última execução | MAX(created_at_ms) | **2026-10-06 13:11:00Z** = 10:11 local |

## 2. O CRON CONSOLIDADO

`d43fb9be-283d-4dd3-8e73-d9fb562fd181` -> scheduler `3e640109-0683-4f55-9bd3-27bbb323bc6f`
- 555 execuções, **551 entregues**, 4 falhadas
- `run_count=444` no scheduler vs 555 linhas na tabela: **111 execuções são
  anteriores à ressurreição do job**
- `state=active`, `*/3 * * * *`, `schedule_generation=3`
- `project='I:\!manager'` — **o path está CORRECTO**, não é `H:`
- `prompt_bytes=8553`

## 3. O SINTOMA: TODOS OS CRONS PARARAM JUNTOS

`local_runtime_v2_scheduler_jobs`: POPULAÇÃO = 30 linhas, **5 `active`**.

| scheduler_id | runs | next_run_at_ms | estado |
|---|---|---|---|
| `3e640109` `*/3` | 444 | 2026-10-06 14:00Z | **OVERDUE** |
| `5f1b385a` `*/11` | 95 | 2026-10-06 13:22Z | **OVERDUE** |
| `sched-7f2c94e` `*/3` | 0 | 2026-10-07 15:07Z | **OVERDUE** |
| `e0edcddc`, `21471b7a` | 0 | 2027-01-01 | futuro |

**3 dos 5 `active` têm `next_run_at_ms` no passado.** Estado internamente
contraditório: armado para disparar, próxima execução no passado, a não disparar.

As 5 últimas execuções são de **4 crons DISTINTOS**, dentro de 11 minutos
(13:00–13:11Z). **Pararam juntos.** Um `next_run_at_ms` obsoleto num job
individual pararia UM job; pararam todos. **O defeito está no scheduler, não no
estado de um job.**

## 4. O QUE ESTÁ POR PROVAR

- **O MECANISMO.** Sei o sintoma com POPULAÇÃO = 1442 e uma assinatura limpa.
  Não li o código do loop do scheduler, não sei o que acontece a um job atrasado,
  e não sei se as 9 execuções `failed` mataram o loop.
- **O BRIEFING DIZ "dispara no próximo arranque", mas esta sessão já arrancou e os
  crons continuam parados.** Ou a hidratação não explica tudo, ou o processo começou
  antes da janela de mensagens.
- **59 bytes de divergência:** a cópia na base de dados tem `prompt_bytes=8553`; o
  ficheiro `I:\!manager\scripts\cron-mission-prompt.md` em disco mede **8612**.
  Não se sabe se é conteúdo ou encoding.

## 5. RETRACÇÕES QUE ESTE FICHEIRO CORRIGE

O root vinha a repetir, com base no briefing e nunca na fonte:

| WRONG | MEDIDO |
|---|---|
| "entrega nunca provada" | 1442 execuções, 1433 entregues |
| "`claimId=None`, `deliveryAttempts=0`" | **campos que não existem na tabela** |
| "não há loja de cron em `.minimax\v2`" | há, com 30 linhas de scheduler |
| "cron nunca dispara" | disparou 444–555 vezes |

**Regra:** o briefing injectado é uma afirmação herdada. A fonte primária é a
tabela. Nomes de campos que não foram lidos não são evidência.

## 6. ACÇÃO

O mecanismo provável é hidratação/loop morto, e a acção de recuperação é um
**restart do processo** — que repõe a hidratação a partir da loja e reescreve
`next_run_at_ms`. Isso SÓ volta a acontecer se o mecanismo for esse. Sem o passo 4
provado, um restart é uma acção plausível, não uma correcção garantida.

`mcode` está disponível: `H:\env\npm-global\mcode.cmd`, pacote
`@minimax-ai/code@0.6.3`. **O root affirmed que não podia executá-lo sem antes
verificar — e verificou, e pode.**