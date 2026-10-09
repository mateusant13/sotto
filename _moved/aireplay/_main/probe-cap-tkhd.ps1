# probe-cap-tkhd.ps1 — read the MP4 CONTAINER boxes directly and print what they say.
#
# WHY: ffprobe reports the SPS-derived size, which HIDES the fact that the product writes the
# value passed to --cut-size into tkhd and avc1. A file whose track header says one size while
# its coded stream is another is a real defect, and no ffprobe column exposes it. This does.
#
# Box sizes are 32-bit big-endian at the box start; a 64-bit size has size==1 and a real 64-bit
# value in the next 8 bytes; size==0 means "to end of file".
# Layout walked: moov > trak > tkhd  (width/height are the last 8 bytes, 16.16 fixed point)
#               moov > trak > mdia > minf > stbl > stsd > avc1 (16-bit w/h + avcC)
#
# THIS PROBE LIED THREE TIMES BEFORE IT WORKED. All three are recorded because the failure mode
# is the point of this lane: an instrument that reports a defect that is not there is worse than
# one that reports nothing, and every one of these was a FALSE NEGATIVE ("tkhd ABSENT",
# "no trak inside moov") on files ffprobe reads perfectly.
#   bug 1: Find-Box returned `,@($i,$size,$hdr)` tuples. PowerShell UNROLLS a single-element outer
#          array on return, and every container here has exactly one child of interest, so the
#          result came back FLAT. $moov[0] was then the offset int, not a tuple, and the search
#          ran over an empty range. Fix: return one PSCustomObject, which does not unroll.
#   bug 2: Find-Box's OFF meant the TYPE FIELD in one revision and the BOX START in another. A
#          box's size lives in the 4 bytes BEFORE its type, so consumers that added $hdr again
#          skipped 8 bytes and landed mid-box. Fix: OFF is always the box start.
#   bug 3 (the real one, and the one worth remembering): the parameter was named $Type and the
#          loop variable was named $type. POWERSHELL VARIABLE NAMES ARE CASE-INSENSITIVE, so they
#          are ONE variable: the first assignment `$type = 'ftyp'` overwrote the search target,
#          every `$type -eq $Type` was the tautology 'ftyp' -eq 'ftyp', and Find-Box returned the
#          FIRST box of the file while appearing to search. Fix: `$fourcc` vs `$Want`.
# What settled bugs 2 and 3: stop guessing, TRACE the walk with explicit offsets and print what
# each step sees. Guessing cost three attempts; the trace found it immediately.
#
# Usage: pwsh -File probe-cap-tkhd.ps1 -File <clip.mp4> [-File <clip2.mp4> ...]

[CmdletBinding()]
param([Parameter(Mandatory)][string[]]$File)

function BE32([byte[]]$b, [int]$o) { return ([uint32]$b[$o] -shl 24) -bor ([uint32]$b[$o+1] -shl 16) -bor ([uint32]$b[$o+2] -shl 8) -bor [uint32]$b[$o+3] }
function BE16([byte[]]$b, [int]$o) { return ([uint32]$b[$o] -shl 8) -bor [uint32]$b[$o+1] }

# Second bug, found by tracing the box chain by hand and comparing offsets: Find-Box returned the
# offset OF THE TYPE FIELD in one revision and the offset OF THE BOX START in another. A box's size
# lives in the 4 bytes BEFORE its type, so every consumer that added $hdr again skipped 8 bytes and
# landed mid-box, which is why 'trak' was not found even though a hand trace found it immediately.
# Find-Box below returns OFF = the start of the box (where the size field is). Everything is
# self-consistent with that, and the assertions at the end prove the chain was walked correctly.
function Find-Box {
  param([byte[]]$B, [int]$Start, [int]$End, [string]$Want)
  $i = $Start
  while ($i + 8 -le $End) {
    $size = [int64](BE32 $B $i)
    $fourcc = [System.Text.Encoding]::ASCII.GetString($B, $i+4, 4)
    $hdr  = 8
    if ($size -eq 1)     { $size = [int64]$B[$i+8]*16777216 + [int64]$B[$i+9]*65536 + [int64]$B[$i+10]*256 + [int64]$B[$i+11]; $hdr = 16 }
    elseif ($size -eq 0) { $size = $End - $i }
    if ($size -lt $hdr) { break }                 # corrupt or not a box: stop, do not guess
    if (($i + $size) -gt $End) { break }         # a box that overruns its parent is not one of ours
    if ($fourcc -eq $Want) {
      return [pscustomobject]@{ off = $i; size = [int]$size; hdr = $hdr }
    }
    $i += [int]$size
  }
  return $null
}

foreach ($f in $File) {
  Write-Output "=== $f"
  if (-not (Test-Path $f)) { Write-Output "    MISSING"; continue }
  $B = [System.IO.File]::ReadAllBytes($f)
  Write-Output ("    bytes={0}" -f $B.Length)
  $moov = Find-Box $B 0 $B.Length 'moov'
  if ($null -eq $moov) { Write-Output "    no moov (is this a valid MP4?)"; continue }
  $trak = Find-Box $B ($moov.off + $moov.hdr) ($moov.off + $moov.size) 'trak'
  if ($null -eq $trak) { Write-Output "    no trak inside moov"; continue }
  $trStart = $trak.off + $trak.hdr; $trEnd = $trak.off + $trak.size

  # --- tkhd: 4 bytes version/flags + ... + 8 reserved + 36 matrix + 4 width + 4 height
  $t = Find-Box $B $trStart $trEnd 'tkhd'
  $tkhdW = $null; $tkhdH = $null
  if ($null -ne $t) {
    $w = BE32 $B ($t.off + $t.size - 8); $h = BE32 $B ($t.off + $t.size - 4)
    $tkhdW = $w -shr 16; $tkhdH = $h -shr 16
    Write-Output ("    tkhd  DECLARED size = {0}x{1}   (16.16 raw {2},{3})" -f $tkhdW, $tkhdH, $w, $h)
  } else { Write-Output "    tkhd  ABSENT" }

  # --- avc1 sample entry: 6 reserved + 2 dri + 16 reserved + 2 w + 2 h + ... + avcC
  $mdia = Find-Box $B $trStart $trEnd 'mdia'
  if ($null -ne $mdia) {
    $minf = Find-Box $B ($mdia.off + $mdia.hdr) ($mdia.off + $mdia.size) 'minf'
    if ($null -ne $minf) {
      $stbl = Find-Box $B ($minf.off + $minf.hdr) ($minf.off + $minf.size) 'stbl'
      if ($null -ne $stbl) {
        $stsd = Find-Box $B ($stbl.off + $stbl.hdr) ($stbl.off + $stbl.size) 'stsd'
        if ($null -ne $stsd) {
          # stsd is a FullBox: 8 header + 4 version/flags + 4 entry_count = 16 before entry 1
          $a = Find-Box $B ($stsd.off + $stsd.hdr + 8) ($stsd.off + $stsd.size) 'avc1'
          if ($null -ne $a) {
            # VisualSampleEntry: 8 header + 6 reserved + 2 data_ref_index + 16 pre_defined/reserved
            # = 32 bytes, THEN width and height. Reading at +24 printed 0x0 and looked like an
            # empty field; the width is at +32. Offsets here were traced byte by byte.
            $aw = BE16 $B ($a.off + 32); $ah = BE16 $B ($a.off + 34)
            Write-Output ("    avc1  DECLARED size = {0}x{1}" -f $aw, $ah)
            # avcC starts after the 78-byte VisualSampleEntry header and carries the REAL SPS
            $acOff = $a.off + 78
            if ($acOff + 4 -le $B.Length -and [System.Text.Encoding]::ASCII.GetString($B, $acOff+4, 4) -eq 'avcC') {
              $prof=$B[$acOff+7]; $lvl=$B[$acOff+9]
              $spcLen = BE16 $B ($acOff+11)
              Write-Output ("    avcC  SPS profile_idc={0} level_idc={1} sps_bytes={2}" -f $prof, $lvl, $spcLen)
            }
          }
        }
      }
    }
  }

  # --- SELF-CHECK: a probe that found nothing proves nothing, so state what it walked.
  if ($null -eq $t) {
    Write-Output "    SELFCHECK FAILED: moov and trak were walked, tkhd was not found. Report NO RESULT."
  } else {
    Write-Output ("    SELFCHECK ok: moov@{0}+{1} trak@{2}+{3} tkhd@{4}+{5}" -f `
                  $moov.off, $moov.size, $trak.off, $trak.size, $t.off, $t.size)
    if ($null -ne $tkhdW) {
      Write-Output ("    => a player that trusts tkhd sizes this track {0}x{1}, whatever the SPS says" -f $tkhdW, $tkhdH)
    }
  }
}
