@echo off
REM ===========================================================================
REM  Sotto -- the entry point to double-click.  This file is a forwarder.
REM
REM  The app's contract lives in `app\webview\run.cmd`: the argument pre-flight
REM  against the shell's own parser, the hidden `pythonw.exe` launch, and the
REM  bounded readiness handshake.  Nothing is duplicated here -- every flag you
REM  pass travels unchanged, so `Sotto.cmd --no-worker` means exactly what
REM  `run.cmd --no-worker` means, and a new flag added to the shell needs no
REM  edit in this file.
REM
REM  WHAT YOU SHOULD SEE.  Nothing. The app starts hidden and waits for Alt+C;
REM  press it once and the caption panel appears docked to the right edge, press
REM  it again and it goes away.  The panel is the only window, it never takes
REM  focus when it appears, and it leaves no console behind.
REM
REM  The one cosmetic residual: Windows gives a double-clicked .cmd its own
REM  console for as long as the wrapper runs -- ~250 ms for a normal launch, and
REM  up to the readiness bound (30 s) when the app fails to come up, which is
REM  exactly when you WANT it to wait and tell you. See `app\webview\README.md`.
REM ===========================================================================

REM  The forwarder needs `call`, and `call` needs run.cmd to be CRLF: run.cmd was
REM  stored with LF-only line endings, and cmd.exe desynchronises an LF-only batch
REM  that is nested inside another batch -- words from its own REM header got
REM  executed as commands (measured: `'tto' nao e reconhecido como um comando`,
REM  and `--help`/`--bogus-flag` answered rc 255 instead of 0/2). run.cmd is CRLF
REM  now; if it ever goes back to LF, either convert it again or invoke it as
REM  `start "" /b cmd /c "%~dp0app\webview\run.cmd" %*`, so it is the top-level
REM  script of its own cmd instance (which is how a double-click runs it).
REM  `dev` is a SUBCOMMAND, not a shell flag: it never reaches the app, so the
REM  forwarder below stays the only path to `run.cmd`. `Sotto.cmd dev ...` runs
REM  the real pipeline over cached audio: no audio device, no hotkey, no window.
REM  MEASURED: `%*` is NOT affected by `shift` -- it expands to the ORIGINAL
REM  argv, so `call ...sotto-dev.cmd %*` handed the child `dev --selftest` and
REM  the child read `dev` as its window spec. The arguments travel as
REM  `%2..%9` instead, and anything past 9 is refused rather than dropped
REM  silently (a dropped `--video <id>` would score the WRONG video).
if /i "%~1"=="dev" (
REM  There is deliberately NO "too many arguments" guard: `%~10` is not
REM  "arg 10" (cmd reads it as `%~1` plus a literal `0`, which refused every
REM  call -- measured), and a real count needs delayed expansion that this
REM  file must not turn on (`!` would eat `I:\!watcher` paths elsewhere). The
REM  lab itself refuses unknown flags with rc=2, which is the same protection
REM  without the trap.
  call "%~dp0_main\devlab\sotto-dev.cmd" %2 %3 %4 %5 %6 %7 %8 %9
  exit /b %ERRORLEVEL%
)

call "%~dp0app\webview\run.cmd" %*
exit /b %ERRORLEVEL%
