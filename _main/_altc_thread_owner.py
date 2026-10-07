"""Which PID owns the hotkey thread id the log recorded? Toolhelp enumeration."""
import ctypes
import ctypes.wintypes as wt
import json
import sys

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
kernel32.CreateToolhelp32Snapshot.restype = wt.HANDLE
TH32CS_SNAPTHREAD = 0x4


class THREADENTRY32(ctypes.Structure):
    _fields_ = [('dwSize', wt.DWORD), ('cntUsage', wt.DWORD),
                ('th32ThreadID', wt.DWORD), ('th32OwnerProcessID', wt.DWORD),
                ('tpBasePri', ctypes.c_long), ('tpDeltaPri', ctypes.c_long),
                ('dwFlags', wt.DWORD)]


def main():
    pid = int(sys.argv[1])
    wanted = set(int(a) for a in sys.argv[2:])
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    ent = THREADENTRY32()
    ent.dwSize = ctypes.sizeof(THREADENTRY32)
    hits, mine = [], []
    ok = kernel32.Thread32First(snap, ctypes.byref(ent))
    while ok:
        if ent.th32ThreadID in wanted and ent.th32OwnerProcessID == pid:
            hits.append(ent.th32ThreadID)
        if ent.th32OwnerProcessID == pid:
            mine.append(ent.th32ThreadID)
        ok = kernel32.Thread32Next(snap, ctypes.byref(ent))
    print(json.dumps({'pid': pid, 'hotkey_tid_owned_by_pid': sorted(hits),
                      'pid_thread_count': len(mine),
                      'pid_thread_ids': sorted(mine)}, indent=2))


if __name__ == '__main__':
    main()