<script lang="ts">
  import { onMount } from 'svelte';

  import { captureState } from './lib/ipc';
  import type { CaptureState } from './lib/types';

  /*
   * M0 has no audio and no model. The only thing bound to real state is the
   * capture flag, and it is bound NOW rather than when the first transcript
   * arrives - so turning capture on is a change in what Rust reports, not a
   * rewrite of this file.
   */
  let capture = $state<CaptureState | null>(null);
  let failure = $state<string | null>(null);

  onMount(() => {
    captureState()
      .then((state) => (capture = state))
      .catch((e: unknown) => (failure = `IPC failed: ${String(e)}`));
  });
</script>

<div class="panel">
  <header class="titlebar" data-tauri-drag-region>
    <span class="mark" aria-hidden="true"></span>
    <h1>Sotto</h1>
  </header>

  <div class="body">
    <p class="empty">{capture?.message ?? 'Waiting for audio'}</p>

    {#if failure}
      <p class="fault">{failure}</p>
    {/if}

    {#if capture?.active}
      <p class="listening">Listening</p>
    {/if}
  </div>
</div>

<style>
  .panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    margin: var(--panel-margin, 10px);
    border-radius: var(--sotto-radius);
    border: 1px solid transparent;
    background:
      linear-gradient(var(--sotto-bg), var(--sotto-bg)) padding-box,
      linear-gradient(135deg, var(--sotto-accent-a), var(--sotto-accent-b)) border-box;
    overflow: hidden;
  }

  .titlebar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 14px 16px 12px;
    cursor: grab;
  }

  .mark {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--sotto-accent-a), var(--sotto-accent-b));
  }

  h1 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    letter-spacing: 0.01em;
  }

  .body {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    gap: 8px;
    padding: 0 20px;
    text-align: center;
  }

  .empty {
    margin: 0;
    font-size: 13px;
    color: var(--sotto-muted);
  }

  .listening {
    margin: 0;
    font-size: 12px;
    color: var(--sotto-accent-a);
  }

  .fault {
    margin: 0;
    font-size: 12px;
    color: #fca5a5;
  }
</style>