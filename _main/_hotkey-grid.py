# -*- coding: utf-8 -*-
"""Fingerprint the FOREIGN hotkey-owner set on this box.

Each combo is registered briefly and unregistered.  A blocked registration
(ctypes.get_last_error() == 1409, ERROR_HOTKEY_ALREADY_REGISTERED) PROVES a
genuine RegisterHotKey owner exists on this desktop: a WH_KEYBOARD_LL hook
swallows keys WITHOUT blocking registration, so 1409 is strictly stronger
evidence than a swallowed keypress.

Controls: Ctrl+C and Alt+C must come back FREE (Alt+C is the shell's own combo,
measured FREE on this box), and Alt+F9 was measured BLOCKED.  If the controls
disagree with this table the run is INCONCLUSIVE -- a blind FREE is not a FREE.
"""
import ctypes
import json
import time

user32 = ctypes.WinDLL("user32", use_last_error=True)

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

VK_HOME = 0x24
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_END = 0x23
VK_F9 = 0x78

_HOTKEY_ID = 0xB0F0

GRID = [
    ("Ctrl+Left", MOD_CONTROL, VK_LEFT),
    ("Alt+Left", MOD_ALT, VK_LEFT),
    ("Ctrl+Right", MOD_CONTROL, VK_RIGHT),
    ("Alt+Right", MOD_ALT, VK_RIGHT),
    ("Ctrl+Up", MOD_CONTROL, VK_UP),
    ("Alt+Up", MOD_ALT, VK_UP),
    ("Ctrl+Down", MOD_CONTROL, VK_DOWN),
    ("Alt+Down", MOD_ALT, VK_DOWN),
    ("Shift+Left", MOD_SHIFT, VK_LEFT),
    ("Alt+Shift+Left", MOD_ALT | MOD_SHIFT, VK_LEFT),
    ("Ctrl+Shift+Left", MOD_CONTROL | MOD_SHIFT, VK_LEFT),
    ("Ctrl+Alt+Left", MOD_CONTROL | MOD_ALT, VK_LEFT),
    ("Win+Left", MOD_WIN, VK_LEFT),
    ("Ctrl+Home", MOD_CONTROL, VK_HOME),
    ("Ctrl+End", MOD_CONTROL, VK_END),
    ("Left-plain", 0, VK_LEFT),
    ("CONTROL Ctrl+C", MOD_CONTROL, 0x43),
    ("CONTROL Alt+C", MOD_ALT, 0x43),
    ("CONTROL Alt+F9", MOD_ALT, VK_F9),
]


def probe(mods, vk):
    ok = user32.RegisterHotKey(None, _HOTKEY_ID, mods, vk)
    err = ctypes.get_last_error()
    if ok:
        user32.UnregisterHotKey(None, _HOTKEY_ID)
    ctypes.set_last_error(0)
    return err, ok != 0


def main():
    rows = []
    for label, mods, vk in GRID:
        err, ok = probe(mods, vk)
        rows.append({"combo": label, "err": err, "free": ok})
        time.sleep(0.05)
    controls = {r["combo"]: r for r in rows if r["combo"].startswith("CONTROL")}
    blind = []
    if not controls["CONTROL Ctrl+C"]["free"]:
        blind.append("CONTROL Ctrl+C")
    if not controls["CONTROL Alt+C"]["free"]:
        blind.append("CONTROL Alt+C")
    if controls["CONTROL Alt+F9"]["free"] is False and not blind:
        pass  # expected: Alt+F9 is genuinely owned by a foreign program
    if blind:
        print("VERDICT: INCONCLUSIVE (control(s) blocked: %s)" % ", ".join(blind))
    for r in rows:
        print("%-20s %-8s err=%d" % (r["combo"], "FREE" if r["free"] else "BLOCKED", r["err"]))
    print("-- controls: " + json.dumps({k: r["err"] for k, r in controls.items()}))
    print("-- blocked: " + ", ".join(r["combo"] for r in rows if not r["free"]))


if __name__ == "__main__":
    main()
