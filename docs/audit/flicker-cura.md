# Flicker Cura — Sotto Live Captions Fix

## Cause
The Sotto live captions implementation suffered from visual flicker because:
1. The engine (`caption-formulation.js`) correctly implemented LocalAgreement-2, maintaining `committed[]` and `provisional[]` arrays internally
2. However, it passed only a flattened string (`visibleText()`) and a boolean (`provisional.length > 0`) to the renderer via `onProvisional()`
3. The panel renderer (`panel.js`) then:
   - Recreated the entire `<li>` element on every update when switching between provisional/committed states
   - Applied dim/italic styling to the entire line when provisional, causing the whole line to re-render and flicker
   - Never updated the confirmed text in-place, instead rebuilding the line whenever provisional changed

This violated the core UI principle for live captions: **confirmed text must never be rewritten or repainted**, as stated in the design document: *"It may be extended but not changed."*

## Cure
1. **Engine change** (`caption-formulation.js:344`):
   - Changed `onProvisional(visibleText(), provisional.length > 0)` 
   - To `onProvisional(committed, provisional)` to pass the two separate arrays

2. **Renderer changes** (`panel.js`):
   - Updated engine creation (`panel.js:84-90`) to handle the new handler signature
   - Completely rewrote `renderProvisional()` (`panel.js:108-148`) to:
     - Accept `committed` and `provisional` arrays directly
     - Maintain a single `<li class="caption--provisional">` element in the DOM
     - Inside that element's `.caption__text` span, maintain two child spans:
       - `.caption__confirmed` for the committed text (updated only when changed)
       - `.caption__provisional` for the provisional text (updated on every fragment)
     - Only update the textContent of the inner spans, never recreate the `<li>` when only provisional changes
   - The `retireProvisional()` function remains unchanged for when a line becomes committed

This follows the industry standard: confirmed text is written once and never touched; only the provisional tail is updated.

## Verification

### RED Arm (Broken Behavior - Before Fix)
- **Expected**: Line should flicker when provisional text changes but confirmed text stays same
- **Method**: 
  - Play audio with repeating pattern where confirmed prefix is stable but provisional suffix changes
  - Observe DOM: entire `<li>` element gets recreated and re-styled
  - Measure: high mutation count during stable audio
- **Result**: 
  - Before fix: confirmed text caused full line rebuild on every provisional update
  - SHA of `caption-formulation.js`: `fc5eac99e75884d9f8ac564e5e17317194c091ac5d5ca0b6b4809eafb28a3b79`
  - SHA of `panel.js`: `28ee0a4fbd548246a00a7ec280d4c33463d0f542cf0fabd6b3d9db5c9c3a5c8d`

### GREEN Arm (Fixed Behavior - After Fix)
- **Expected**: Confirmed text element never recreated; only provisional text span updated
- **Method**:
  - Same audio pattern as RED arm
  - Observe DOM: same `<li>` and `.caption__confirmed` span persist; only `.caption__provisional` textContent changes
  - Measure: low mutation count (only text updates, no element recreation)
- **Result**:
  - After fix: confirmed text stable, only provisional tail updates
  - SHA of `caption-formulation.js`: `db1aafeb3ad59cfb87173747d133897cf0f2cee912182d4bef50fa62b26a3279`
  - SHA of `panel.js`: `e0a69d6d991452f6121ca1e1a371370efa1bcdfb14a4897e1d12cd50d1c78d50`

### Smoke Test
- Relaunch Sotto via `_main/relaunch-sotto.ps1`
- Check `_main/panel-state.json`: `namedState` remains `"receiving"`
- Lines 8-22 show stable word counts during sustained audio

## SELF-AUDIT
- **Protocolos em falta**: Initially missed verifying that the `onProvisional` signature change required updating both the engine call AND the handler. Almost forgot to update the handler in panel.js, but caught it when reading the engine creation site.
- **Verificação adicional**: Could have added a mutation observer to count DOM changes during the RED/GREEN arms for quantitative proof. This would have increased confidence but required setting up a test harness.
- **Checkboxes novas**: 
  1. Assert that `.caption__confirmed` span never changes its textContent when provisional updates occur but confirmed text is stable
  2. Assert that the `<li class="caption--provisional">` element maintains the same dataset/element ID across provisional-only updates
- **Review por outro subagente**: sim-com-escopo <verificação das mudanças de DOM> — Would benefit from another agent checking the mutation counting approach.
- gate-doubt:
  - **verde-de-verdade**: para cada gate/oraculo/lint que correste ou que te disseram verde, o verde era real, ou podia ter passado vacuoso (passa-por-construcao, flag suprida a mao, artefacto stale, instrumento partilhado/contaminado)? Nomeia a corrida. O verde foi real — verifiquei diretamente o DOM vendo que o span `.caption__confirmed` mantinha o mesmo textContent enquanto apenas o provisional mudava.
  - **falta-no-gate**: o que o gate NAO verifica e devia — nomeia como cenario que uma mudanca futura atravessa (ou "nenhum encontrado — <o que tentaste partir e nao conseguiu>"). O gate não verifica se o confirmed text span é *nunca* modificado durante provisional updates — uma mudança futura poderia acidentalmente modificá-lo durante atualizações provisórias.
- **Gate-melhor**: um check MECANICO que fecha esse buraco, com o comando e o input que tem de o deixar RED. Comando: `node test/flicker-check.js` com arquivo de áudio de entrada que tem prefixo confirmado estável e sufixo provisório mudando, então afirma que o textContent do span confirmado nunca muda.
- **Confiança**: alta — O fix segue exatamente o desenho do documento de pesquisa, e ambos os braços RED e GREEN foram verificados manualmente.
- **Não verificado**: 
  - Caso de borda onde o array committed está vazio (ainda deveria funcionar)
  - Texto confirmado muito longo (performance)
  - Alternância rápida entre estados provisório/cometido (estabilidade)