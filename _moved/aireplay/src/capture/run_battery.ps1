# run_battery.ps1 — the whole measured battery for lane 03 (capture -> NVENC -> ring -> clip).
# Every number in receipts\receipt-03-capture-impl.md comes from a line this script writes.
$ErrorActionPreference = "Continue"
$src = "H:\aireplay\src\capture"
$out = "H:\aireplay\_main\build"
$logs = "H:\aireplay\_main\logs"
$exe = "$out\aireplay-capture.exe"
$mut = "$out\aireplay-capture-MUTANT.exe"

$common = @("$src\main.cpp","$src\common.cpp","$src\d3d11_ctx.cpp","$src\nv12_convert.cpp",
            "$src\wgc_capture.cpp","$src\nvenc_encoder.cpp","$src\ring_buffer.cpp",
            "$src\mp4_writer.cpp","$src\selftest.cpp","$src\test_window.cpp","$src\replay.cpp")
$libs = @("-ld3d11","-ldxgi","-luuid","-lole32","-loleaut32","-lruntimeobject","-lwindowsapp",
          "-lpsapi","-lgdi32","-luser32")

function Beacon($s) { Write-Output ("BEACON " + $s) }

Beacon "build start"
& H:\msys64\mingw64\bin\g++.exe -std=c++17 -O2 -Wall -Wextra -Wno-unused-parameter `
    -I $src -I "$src\third_party" @common -o $exe @libs 2>&1 | Select-Object -First 25
Beacon "build rc=$LASTEXITCODE"
& H:\msys64\mingw64\bin\g++.exe -std=c++17 -O2 -DAIREPLAY_GATE_OFF `
    -I $src -I "$src\third_party" @common -o $mut @libs 2>&1 | Select-Object -First 5
Beacon "mutant build rc=$LASTEXITCODE"

# ---- law 6: the gate, four arms plus the mutant control --------------------------------
function Gate($name, $bin, $fault) {
    $log = "$logs\gate-$name.txt"
    if ($fault) { & $bin --selftest --inject-fault $fault --log $log *> $null }
    else        { & $bin --selftest --log $log *> $null }
    $rc = $LASTEXITCODE
    $verdict = (Select-String -Path $log -Pattern "LAW 6|GATE|ARMED|REFUSED" |
                Select-Object -Last 3 | ForEach-Object { $_.Line.Trim() }) -join " || "
    Beacon "gate $name rc=$rc :: $verdict"
}
Gate "normal"        $exe $null
Gate "tuning"        $exe "tuning-undefined"
Gate "nonvenc"       $exe "no-nvenc"
Gate "skipmap"       $exe "skip-map"
Gate "MUTANT-tuning" $mut "tuning-undefined"

# ---- the runs --------------------------------------------------------------------------
function RunArm($name, $extra) {
    $log = "$logs\arm-$name.txt"
    $before = Get-ChildItem "H:\aireplay\_main\runs\clip-*.mp4" -ErrorAction SilentlyContinue
    $argv = @("--run","--log",$log,"--window-alpha","1") + $extra
    & $exe @argv *> $null
    $rc = $LASTEXITCODE
    $after = Get-ChildItem "H:\aireplay\_main\runs\clip-*.mp4" | Sort-Object LastWriteTime -Descending
    $clip = $after[0].FullName
    Beacon "arm $name rc=$rc clip=$clip"
    Get-Content $log | Where-Object {
        $_ -match "MODE|ring    |peak RSS|RSS|frames  :|captured=|converted|encoded|convert |encode |cpu |census|written into|LOST |shortfall|wall_ms|bytes=|clip\.mp4|IDR|paint_cost|elapsed|drop"
    } | ForEach-Object { Write-Output ("    " + $_.Trim()) }
    if (Test-Path $clip) {
        $probe = & ffprobe -v error -count_frames -select_streams v:0 `
            -show_entries "stream=codec_name,profile,width,height,pix_fmt,r_frame_rate,avg_frame_rate,nb_frames,nb_read_frames,bit_rate" `
            -of default=nw=1 $clip
        Write-Output ("    FFPROBE " + (($probe -join " ") ))
        $null_ = (& ffmpeg -v error -i $clip -f null - 2>&1 | Out-String).Trim()
        Write-Output ("    NULLDECODE stderr_len=" + $null_.Length + " [" + $null_ + "]")
        $copy = "$logs\_remux-$name.mp4"
        $r = (& ffmpeg -v error -y -i $clip -c copy $copy 2>&1 | Out-String).Trim()
        Write-Output ("    REMUX stderr_len=" + $r.Length)
    }
}

RunArm "A-gaming-default-ring" @("--seconds","40","--cut-at","30")
RunArm "B-gaming-evict"       @("--seconds","40","--cut-at","30","--ring-seconds","8","--ring-mb","64")
RunArm "C-desktop"            @("--mode","desktop","--seconds","20","--cut-at","12")
RunArm "D-ring-256"           @("--seconds","25","--cut-at","18","--ring-mb","256","--ring-seconds","30")
RunArm "E-ring-1024"          @("--seconds","25","--cut-at","18","--ring-mb","1024","--ring-seconds","30")

Beacon "battery done"
