"""Lane SottoLiveForOwner: press the REAL global Alt+C, twice.

Injected input (keybd_event) goes through the same OS input path a physical
keypress does, so the registered hotkey (HOTKEY_REGISTERED ... isRegistered=true)
is exercised end to end -- not a direct call to the toggle function.

Prints the foreground window before and after, so "the panel did not steal
focus" is a measurement and not a claim.
"""
import ctypes
import ctypes.wintypes as wt
import sys
import time

user32 = ctypes.windll.user32
VK_MENU = 0x12
VK_C = 0x43
KEYEVENTF_KEYUP = 0x0002


def foreground() -> str:
    hwnd = user32.GetForegroundWindow()
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return f'hwnd={hwnd} title={buf.value!r}'


def alt_c():
    user32.keybd_event(VK_MENU, 0, 0, 0)
    user32.keybd_event(VK_C, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(VK_C, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)


rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 2
print('focus_before', foreground(), flush=True)
for i in range(rounds):
    alt_c()
    time.sleep(1.2)
    print(f'after_press_{i + 1} focus', foreground(), flush=True)
time.sleep(0.5)
print('done', flush=True)
