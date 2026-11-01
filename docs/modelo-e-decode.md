# Desvios conhecidos do spec do modelo

> Movido de `AGENTS.md` em 2026-10-23 (trim). Conteudo verbatim;
> a medicao e as ressalvas sao as que la estavam.


| o que o modelo diz | o que o código faz hoje |
|---|---|
| lang id fixo | `model.lang_id` = **`"auto"`** (101). `"os"` é aceite mas perigoso (destruiu uma língua em cada direcção). Precedência `--lang-id` > `SOTTO_LANG_ID` > config; id não declarado **recusa ruidosamente (exit 2)**, nunca é clampado. |
| VAD opcional | `use_vad: true` está LIGADO e não é inerte: um chunk de silêncio faz `process()` devolver `None` (10 de 12 chunks gated). |
| int4 no config | config selecciona `...-int8` (`left_context: 70`); custo medido vs int4 = +268 MB RSS. |
| um device que abre e não ouve nada sai 0 | agora `state="silent-device"`, verdict próprio, **exit 3**; e `ran_but_silent` é testado PRIMEIRO, logo `done.verdict == "silent-device"` iff `exit == 3`. |
| `--audio` precisa de `--selftest` | **falso hoje**: `--audio X` sozinho transcreve X. |
