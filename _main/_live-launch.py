"""Lane SottoLiveForOwner: launch the app the owner's way, windowless.

Uses the house's sanctioned hidden spawner (CREATE_NO_WINDOW) so the wrapper
`cmd.exe` never puts a console window on the owner's screen. `run.cmd` itself
`start`s pythonw detached, which is a GUI-subsystem binary (no console).

Usage: py -3 _live-launch.py [log-path]
"""
import sys

sys.path.insert(0, r"I:\!manager\scripts")
import spawn_hidden  # noqa: E402

log = sys.argv[1] if len(sys.argv) > 1 else r"H:\sotto\_main\live-owner.log"
argv = ["cmd", "/c", r"H:\sotto\app\webview\run.cmd",
        "--with-worker", "--log", log]
proc = spawn_hidden.run_hidden(argv)
print("RUNCMD_RC", proc.returncode, "log", log)
