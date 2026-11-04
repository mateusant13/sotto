"""THE PAIR THAT ACTUALLY HIDES A CHILD CONSOLE, IN ONE PLACE.

MEASURED 2026-11-04, ON THE OWNER'S SCREEN. `creationflags=CREATE_NO_WINDOW`
alone does NOT stop a visible console window when the PARENT HAS NO CONSOLE --
and no parent in this product has one: the shell runs under `pythonw.exe`, the
worker under `pythonw.exe`, and a lane runs from an agent process that has no
console either. Measured: `subprocess.Popen(['cmd','/c','ping','-n','4','127.0.0.1'],
creationflags=0x08000000)` from such a parent painted a full `ping` console in
front of him. The window belongs to the console the child ALLOCATES, and
`CREATE_NO_WINDOW` is documented as "the console application is run without a
console window" only because the loader also applies the `STARTUPINFO` show
state -- which is exactly the half this repo kept forgetting:

    si = STARTUPINFO()
    si.dwFlags |= STARTF_USESHOWWINDOW
    si.wShowWindow = SW_HIDE          # 0

`_main/hidden-launch.py` is the probe-side version of this (its `--selftest`
asserts "python child has no console window"); this module is the product-side
one, so `app/` and `worker/` do not each re-derive the recipe.

USE IT AS KWARGS, NEVER AS A BARE FLAG:

    from no_console import popen_kwargs
    subprocess.Popen(argv, **popen_kwargs())                  # plain child
    subprocess.Popen(argv, **popen_kwargs(BELOW_NORMAL))      # plus a class

`_main/console-window-audit.py` refuses a spawn that carries `creationflags`
without this pair (`WEAK-FLAG`), and `_main/console-weakflag-baseline.json`
freezes the debt that predates the rule.
"""

from __future__ import annotations

import os
import subprocess

#: `CREATE_NO_WINDOW`: the child gets a console, and that console has no window.
CREATE_NO_WINDOW = 0x08000000


def startupinfo():
    """A `STARTUPINFO` that says SW_HIDE, or None off Windows."""
    if os.name != 'nt':
        return None
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0            # SW_HIDE
    return si


def popen_kwargs(extra_flags=0):
    """The kwargs every console spawn in this product must carry."""
    flags = extra_flags or 0
    if os.name == 'nt':
        flags |= CREATE_NO_WINDOW
    kw = {'creationflags': flags}
    si = startupinfo()
    if si is not None:
        kw['startupinfo'] = si
    return kw
