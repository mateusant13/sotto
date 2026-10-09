Confirmado o modo: **verificador read-only**. Não edito, não crio, não movo ficheiros — só leio, executo comandos que não escrevem no repositório, e relato em texto.

## P0 — vou fazer AGORA
Nada, até saber o alvo. A instrução chegou sem alvo, escopo nem critério de aceitação, e num verificador isso é o pior Input possível: sem alvo, qualquer "veredicto" seria opiniãoVestigial.

## P0 — JÁ FIZ
- Fixado o contrato desta sessão: leitura apenas, zero edições, relatório só em texto (sem ficheiros de entrega).
- Nada no workspace foi tocado.

## P0 — NÃO FIZ (e porquê)
- **Não inspeccionei o repositório** (`H:\_moved\aireplay`) — não há alvo definido; varrer a árvore às cegas produziria achados sem valor.
- **Não corrigi nada** — proibido neste papel, mesmo que veja um bug.
- **Não escrevi relatório para ficheiro** — "report as text only".

## O que preciso (o mínimo, uma linha chega)
**O que verificar + onde.** Por exemplo: `receipts/receipt-03-*.md` contra `specs/03-*.md`; o `_audit-verify-all.cmd` desta árvore; uma spec contra o código em `src/`; a migração de `H:\sotto` para cá (sha256). Se quiseres, respondo com alvo, e eu volto com evidência por afirmação — o que está **MEASURED / READ / UNKNOWN**, o que o gate **cobre e o que não cobre**, e onde um instrumento deste repo **não conseguiria dizer NÃO**.

Orçamento restante desta chamada: ~717 s. Se o alvo for largo demais para isso, digo qual parte verifico agora e qual fica para a segunda volta, em vez de reportar verde estreito como saúde.

Does your implementation meet the spec? NO - a spec chegou vazia (sem alvo, escopo ou critério de aceitação), por isso nada foi verificado ainda.