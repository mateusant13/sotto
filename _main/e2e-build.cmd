@echo off
rem e2e-build.cmd -- build.cmd's recipe (build.cmd:12) pointed at the REPO source
rem instead of the stale H:\aireplay tree, and outputs into THIS worktree so no
rem other lane's build directory is touched.  Recipe unchanged: same sources,
rem same flags, same libs.
rem
rem WHY: the prebuilt H:\aireplay\_main\build\aireplay-capture.exe (13:05) PREDATES
rem main.cpp (13:58) and logs no "STDIN CONTROL" line at all -- both branches of
rem that log are unconditional -- so it is NOT a build of this source.  Measuring
rem end-to-end against it would measure the wrong binary.
rem
rem Note build.cmd:12 links -ld3d11 -ldxgi -luuid -lole32 -loleaut32
rem -lruntimeobject -lwindowsapp -lpsapi -lgdi32 -luser32.  There is no -lavrt and
rem no -lwasapi; audio_tap.cpp is not in the source list, so the shipped binary
rem has no audio path at all.
setlocal
set GXX=H:\msys64\mingw64\bin\g++.exe
set SRC=H:\sotto-wt\ArbV8\_moved\aireplay\src\capture
set OUT=H:\sotto-wt\e2e2\_main\build
if not exist "%OUT%" mkdir "%OUT%"

"%GXX%" -std=c++17 -O2 -Wall -Wextra -Wno-unused-parameter -I "%SRC%" -I "%SRC%\third_party" "%SRC%\main.cpp" "%SRC%\common.cpp" "%SRC%\d3d11_ctx.cpp" "%SRC%\nv12_convert.cpp" "%SRC%\wgc_capture.cpp" "%SRC%\nvenc_encoder.cpp" "%SRC%\ring_buffer.cpp" "%SRC%\mp4_writer.cpp" "%SRC%\selftest.cpp" "%SRC%\test_window.cpp" "%SRC%\replay.cpp" -o "%OUT%\aireplay-capture.exe" -ld3d11 -ldxgi -luuid -lole32 -loleaut32 -lruntimeobject -lwindowsapp -lpsapi -lgdi32 -luser32
if errorlevel 1 (echo BUILD FAILED & exit /b 1)
echo BUILD OK: %OUT%\aireplay-capture.exe
endlocal