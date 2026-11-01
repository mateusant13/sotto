# Output grande: truncamento e o bypass deliberado

> Movido de `AGENTS.md` em 2026-10-23 (trim). Conteudo verbatim;
> a medicao e as ressalvas sao as que la estavam.


O output de uma tool call é cortado antes de entrar no contexto. O limite vem de `tool_output` na config
activa (`G:\env-data\opencode-go-pool.json`): **`max_lines: 600`, `max_bytes: 24576`** (24 KB) — o
mecanismo é nativo (`packages/opencode/src/tool/truncate.ts`, lido por `shell`, `read`, `grep` e tools de
plugin) e não há flag por chamada.

**Três formas de não perder o que interessa:**

1. **Nativo, sempre ligado:** o output completo é escrito em disco e o texto cortado traz
   `Full output saved to: <ficheiro>`. Lê-se com `read` (`offset`/`limit`) ou `grep` sobre esse ficheiro.
   **Preferir isto** para um dump grande de que só se querem umas linhas.
2. **Bypass pedido, por chamada:** o token **`__notrunc__`** em qualquer parte dos argumentos (na prática,
   um comentário na linha de comando: `... | Select-Object -First 40  # __notrunc__`) faz o plugin
   re-expandir o output completo.
3. **Bypass global:** `OPENCODE_NO_TRUNCATE=1` no ambiente do servidor vale para todas as chamadas.

O tecto da re-expansão é **512 KB** (`OPENCODE_NO_TRUNCATE_MAX`), e acima disso o corte fica com uma nota a
dizer onde está o ficheiro: um bypass que anula o limite por completo é a mesma avaria que o limite existe
para evitar. O plugin é `~/.config/opencode/plugins/no-truncate.ts`, composto com o ECC em `index.ts`
(um entrypoint por plugin ⇒ o `default` encadeia os dois hooks `tool.execute.after`). Verificado por seis
braços em `I:\cc-tmp\no-truncate-check.ts`: sem marcador nada muda, com marcador e com env re-expande,
output não truncado é intocado, tecto excedido mantém o corte e nomeia o ficheiro, ficheiro ilegível não
rebenta. **Muda a config/plugin ⇒ reiniciar o serviço** (o `Config` é cacheado com `Duration.infinity`).
