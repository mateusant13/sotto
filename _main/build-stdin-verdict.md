# Build verdict — recovered stdin control (commit 47bb030)

**Verdict: IT DOES NOT COMPILE. Exit code 1. No executable produced.**
One hard error, and it is an MSVC-only assumption that cannot hold on this box.

Measured 2026-10-07 ~13:44 BRT.

---

## 1. The real compile recipe

There is **no Makefile, no CMakeLists.txt, no build\*.bat and no build\*.ps1 anywhere in
`_moved/aireplay`** — verified by glob (`**/{Makefile,makefile,GNUmakefile,CMakeLists.txt,meson.build}`
→ no matches) and by a recursive scan for `build*.cmd|build*.bat|build*.ps1|*.mk` (exactly one hit).

The only recipe is **`_moved/aireplay/src/capture/build.cmd`**, line 12. It sets:

```
GXX = H:\msys64\mingw64\bin\g++.exe
SRC = H:\aireplay\src\capture
OUT = H:\aireplay\_main\build
```

`SRC` looks stale after the move, but it is **not**: `H:\aireplay` is a **Junction** whose target
is `H:\sotto\_moved\aireplay`, and both paths hash identically
(`main.cpp` SHA256 `A710CA1D0770D2E2198FE3CFA4BCA3867847DCBE5E6CBABEDFEE473F94BDA7C1`, 28189 bytes).
So `build.cmd` runs verbatim; no path fixup was applied.

### Exact command run

```
H:\msys64\mingw64\bin\g++.exe -std=c++17 -O2 -Wall -Wextra -Wno-unused-parameter -I "H:\aireplay\src\capture" -I "H:\aireplay\src\capture\third_party" "H:\aireplay\src\capture\main.cpp" "H:\aireplay\src\capture\common.cpp" "H:\aireplay\src\capture\d3d11_ctx.cpp" "H:\aireplay\src\capture\nv12_convert.cpp" "H:\aireplay\src\capture\wgc_capture.cpp" "H:\aireplay\src\capture\nvenc_encoder.cpp" "H:\aireplay\src\capture\ring_buffer.cpp" "H:\aireplay\src\capture\mp4_writer.cpp" "H:\aireplay\src\capture\selftest.cpp" "H:\aireplay\src\capture\test_window.cpp" "H:\aireplay\src\capture\replay.cpp" -o "H:\sotto\_main\build\aireplay-capture.exe" -ld3d11 -ldxgi -luuid -lole32 -loleaut32 -lruntimeobject -lwindowsapp -lpsapi -lgdi32 -luser32
```

Only `-o` was repointed, to a writable location (`H:\aireplay\_main\build` -> `H:\sotto\_main\build`).
Flags, TU list and link libs are byte-identical to `build.cmd:12`.

`build.cmd` itself was NOT used for the rc, because line 13 collapses every failure to
`exit /b 1` — it would have hidden the real code. The g++ line was invoked directly so
`$LASTEXITCODE` is g++'s own.

### What was compiled

| | |
|---|---|
| source | `_moved/aireplay/src/capture/main.cpp` |
| SHA256 | `A710CA1D0770D2E2198FE3CFA4BCA3867847DCBE5E6CBABEDFEE473F94BDA7C1` |
| git blob | `f288467355bea88e2a65e02f445423c51636841d` — the blob introduced by `47bb030` |
| toolchain | mingw-w64 `g++.exe (Rev8, Built by MSYS2 project) 15.2.0` |
| exe produced | **no** |

The source SHA was hashed immediately before and after the compile and was identical, so this
result is not a torn read.

---

## 2. Exit code

```
REAL_EXIT_CODE=1
```

Captured by reading `$LASTEXITCODE` directly after the redirect. The command was never piped into
`Select-Object`.

---

## 3. First error, verbatim

```
H:\aireplay\src\capture\main.cpp: In member function 'void StdinCtl::shutdown()':
H:\aireplay\src\capture\main.cpp:335:49: error: invalid conversion from 'std::thread::native_handle_type' {aka 'long long unsigned int'} to 'HANDLE' {aka 'void*'} [-fpermissive]
  335 |             CancelSynchronousIo(th.native_handle());
      |                                 ~~~~~~~~~~~~~~~~^~
      |                                                 |
      |                                                 std::thread::native_handle_type {aka long long unsigned int}
In file included from H:/msys64/mingw64/include/winbase.h:21,
                 from H:/msys64/mingw64/include/windows.h:70,
                 from H:\aireplay\src\capture\common.h:16,
                 from H:\aireplay\src\capture\main.cpp:16:
H:/msys64/mingw64/include/ioapiset.h:36:57: note: initializing argument 1 of 'WINBOOL CancelSynchronousIo(HANDLE)'
   36 |   WINBASEAPI WINBOOL WINAPI CancelSynchronousIo (HANDLE hThread);
      |                                                  ~~~~~~~^~~~~~~
```

The offending line (`main.cpp:335`, unmodified):

```cpp
            CancelSynchronousIo(th.native_handle());
```

### Why it fails here

`std::thread::native_handle_type` is `pthread_t` (`unsigned long long`) under mingw-w64, and
`CancelSynchronousIo` wants a `HANDLE` (`void*`). Under **MSVC** `native_handle_type` *is* a
`void*`, so this line was written against a toolchain **this box does not have**. That is the
whole failure: the 207 recovered lines were authored for MSVC and landed on a box whose only
compiler is mingw. `-fpermissive` would demote it to a warning and link, which is why the flag
being named in the error is itself the tell.

This line is load-bearing, not cosmetic: it is the documented only exit from a blocked stdin
`ReadFile` at shutdown (`StdinCtl::shutdown`, see the comment at `main.cpp:329`). Silencing it
with `-fpermissive` would compile but leave the shutdown path unproven.

---

## 4. Full compiler output

The run produced **20 lines** (not 60), reproduced in full — this is the complete output:

```
H:\aireplay\src\capture\main.cpp: In member function 'void StdinCtl::shutdown()':
H:\aireplay\src\capture\main.cpp:335:49: error: invalid conversion from 'std::thread::native_handle_type' {aka 'long long unsigned int'} to 'HANDLE' {aka 'void*'} [-fpermissive]
  335 |             CancelSynchronousIo(th.native_handle());
      |                                 ~~~~~~~~~~~~~~~~^~
      |                                                 |
      |                                                 std::thread::native_handle_type {aka long long unsigned int}
In file included from H:/msys64/mingw64/include/winbase.h:21,
                 from H:/msys64/mingw64/include/windows.h:70,
                 from H:\aireplay\src\capture\common.h:16,
                 from H:\aireplay\src\capture\main.cpp:16:
H:/msys64/mingw64/include/ioapiset.h:36:57: note: initializing argument 1 of 'WINBOOL CancelSynchronousIo(HANDLE)'
   36 |   WINBASEAPI WINBOOL WINAPI CancelSynchronousIo (HANDLE hThread);
      |                                                  ~~~~~~~^~~~~~~
H:\aireplay\src\capture\main.cpp: At global scope:
H:\aireplay\src\capture\main.cpp:252:13: warning: 'void jf_null(std::string&, const char*)' defined but not used [-Wunused-function]
  252 | static void jf_null(std::string& acc, const char* k)
      |             ^~~~~~~~~~~~~~
H:\aireplay\src\capture\main.cpp:240:13: warning: 'void jf_num(std::string&, const char*, uint64_t)' defined but not used [-Wunused-function]
  240 | static void jf_num(std::string& acc, const char* k, uint64_t v)
      |             ^~~~~~~~~~~~~~
```

Raw log: `_main/build-stdin-out-134443.txt`.

**Exactly one hard error.** Every other translation unit in the link line compiled clean, so
`main.cpp` is the single blocker. The two warnings are dead helpers (`jf_num`, `jf_null`) written
for a fuller protocol than the `ping`-only `handle()` currently implements — they are not
blockers.

---

## 5. Measurement-integrity note (a run that was discarded)

An earlier run at 13:43:45 reported **rc=1** with **88 lines** and a much worse failure set:

- `main.cpp:651` / `:653` / `:655` — `error: version control conflict marker in file`
  (`<<<<<<< HEAD` / `=======` / `>>>>>>> feat/stdin-v9` still sitting inside `main()`)
- three `redefinition` errors — `probe_json`, `stdin_read_line`, `stdin_write_reply` each defined
  twice (at ~233 and ~591), i.e. the stdin block had been applied twice
- `'o' was not declared in this scope` cascading through `main()`

That run was **discarded, not reported as the verdict**, because `main.cpp` was rewritten at
**13:43:55** — ten seconds after that compile — and the file on disk is now 621 lines, matching
the committed blob `f288467` with no markers and no duplicates. The `rc=1` of that run is
coincidentally the same, but its cause was a transient conflicted working tree that no longer
exists. Had that run been taken at face value it would have blamed the 207 lines for a merge
that had already been undone.

This is recorded because it is the failure mode this box already has a rule about: a real exit
code proves the compiler ran, not that you measured the revision you meant to.

---

## 6. Not done, deliberately

No fix attempted, per brief. `main.cpp` untouched; the SHA in §1 is still the on-disk hash.
No `-fpermissive`, no cast, no MSVC shim.