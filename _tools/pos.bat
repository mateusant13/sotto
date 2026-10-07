@echo off
echo Reply with exactly the word ALIVE and nothing else. This is a liveness probe.> H:\sotto-wt\ArbV8\_main\pos_in.txt
type H:\sotto-wt\ArbV8\_main\pos_in.txt | H:\env\npm-global\mcode.cmd exec --input - --cwd H:\sotto-wt\ArbV8
