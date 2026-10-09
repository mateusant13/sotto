@echo off
cd /d H:\sotto-wt\ArbV8
echo Confirm whether a freshly started process restores cron delivery. Read H:\sotto-wt\ArbV8\_main\CRON-VERDICT.md. Then query C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite read-only: SELECT COUNT(*), MAX(created_at_ms) FROM local_runtime_v2_cron_runs. Report whether new rows exist after 2026-10-06 13:11:00Z. Report only, never write to the store. Every number carries POPULATION and WINDOW.> H:\sotto-wt\ArbV8\_main\brief2.txt
type H:\sotto-wt\ArbV8\_main\brief2.txt | H:\env\npm-global\mcode.cmd exec --input - --cwd H:\sotto-wt\ArbV8
