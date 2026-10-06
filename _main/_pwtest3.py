import sys, json, ctypes
res = {"exe": sys.executable, "stdout": repr(sys.stdout), "stderr": repr(sys.stderr),
       "console_hwnd": int(ctypes.windll.kernel32.GetConsoleWindow())}
try:
    print("sotto: hello from detached pythonw")
    res["print"] = "ok"
except BaseException as e:
    res["print"] = f"{type(e).__name__}: {e}"
open(r"H:\sotto\_main\_pwtest3.json","w").write(json.dumps(res, indent=1))
