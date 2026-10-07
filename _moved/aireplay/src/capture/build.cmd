@echo off
rem Build the spec-03 prototype.  There is NO MSVC on this box and NO CUDA toolkit:
rem mingw-w64 g++ 15.2.0, with nvEncodeAPI64.dll / d3dcompiler_47.dll / nvcuda.dll bound
rem at RUN time (never linked - a -L on System32 makes ld pick up MSVC's msvcrt import
rem library and die in a wall of __acrt_iob_func errors, measured).
setlocal
set GXX=H:\msys64\mingw64\bin\g++.exe
rem MEASURED 2026-10-07: SRC/OUT used to be hardcoded to H:\aireplay, a JUNCTION
rem whose target is H:\sotto\_moved\aireplay -- a DIFFERENT tree from the repo this
rem file is checked into.  It drifted: main.cpp there hashed A710CA1D (28189 bytes,
rem fails to compile: main.cpp:335 CancelSynchronousIo(native_handle()) is MSVC-only)
rem while the repo copy hashes 87B39C8 (44758 bytes, compiles clean, rc=0, exe built).
rem The recipe was therefore reporting the health of a stale tree.  Resolve from
rem %~dp0 so the recipe builds the tree it actually lives in.
set SRC=%~dp0
set OUT=%~dp0..\..\_main\build
if not exist "%OUT%" mkdir "%OUT%"

"%GXX%" -std=c++17 -O2 -Wall -Wextra -Wno-unused-parameter -I "%SRC%" -I "%SRC%\third_party" "%SRC%\main.cpp" "%SRC%\common.cpp" "%SRC%\d3d11_ctx.cpp" "%SRC%\nv12_convert.cpp" "%SRC%\wgc_capture.cpp" "%SRC%\nvenc_encoder.cpp" "%SRC%\ring_buffer.cpp" "%SRC%\mp4_writer.cpp" "%SRC%\selftest.cpp" "%SRC%\test_window.cpp" "%SRC%\replay.cpp" -o "%OUT%\aireplay-capture.exe" -ld3d11 -ldxgi -luuid -lole32 -loleaut32 -lruntimeobject -lwindowsapp -lpsapi -lgdi32 -luser32
if errorlevel 1 (echo BUILD FAILED & exit /b 1)
echo BUILD OK: %OUT%\aireplay-capture.exe
endlocal