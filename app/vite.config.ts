import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// The Rust side reads `devUrl` and `frontendDist` from tauri.conf.json; this
// port is the one both halves agree on.
export default defineConfig({
  plugins: [svelte()],
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    watch: {
      // Rust rebuilds are cargo's job; watching them from vite restarts the
      // frontend for edits that cannot affect it.
      ignored: ['**/src-tauri/**'],
    },
  },
  build: {
    target: 'es2022',
    minify: 'esbuild',
    sourcemap: false,
  },
});