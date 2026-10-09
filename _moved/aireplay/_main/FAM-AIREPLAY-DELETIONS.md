# FAM-LANE-B - AIREPLAY: 21 DELETED TRACKED FILES - recovery manifest

POPULACAO = unstaged deletions in `git -C H:\sotto\_moved\aireplay status --porcelain`
WINDOW   = state as measured 2026-10-07 18:36:52 -03:00
SEAT     = writer. Writes ONLY this receipt + the backup dir. No git add/checkout/reset/commit.

## Why this matters

These paths are tracked in the INNER repo and ABSENT on disk. Both git histories
still believe the file exists, so either repo will commit the deletion silently.
Blobs are recoverable from INNER HEAD. sha256 recorded per path before anything else.

## Recovery manifest (N = 21)

| # | path | INNER HEAD blob (sha1) | sha256 of blob content | on disk | tracked by OUTER sotto | backup written |
|---|---|---|---|---|---|---|
| 1 | `_main/_lane25-stage-durability.ps1` | `9df17af88a92bbd2f8aea5269040b433b736e154` | `59EFF9FC7AE516CF30B4C72A33C39E4AE9001C04AC5039D4EADB27117E86A0FB` | NO | no | 3206 B |
| 2 | `_main/_lane25-stage-probe.log` | `a5a1dcd0f0febff33fa62d0e1ddfa28e235abe01` | `8EC9D293B11AA9687B28B9E6B0FB4849D54B072FE54E0E7BDFC96C206319AB0B` | NO | no | 154 B |
| 3 | `_main/_lane25-stage-probe.ps1` | `ab322b2a196f91b46358c9becb838adcfa6702be` | `57C6822E384D4621DA1A9D31CCBCA21D7BFE1B4C64204ED81E8A8F60ACB010B6` | NO | no | 3997 B |
| 4 | `_main/_lane25-stage.log` | `7508b44b5da2c095db5b30d6af6d3829641f4b72` | `D479B3C34D000F1841FDC4E3945A858C185F57686CEBBAA476EBF1E8175547DA` | NO | no | 201 B |
| 5 | `_main/_lane4-run/armC-v.log` | `58e4a0dea32bb2449995ee54818c7ebf4fcb35ae` | `901CB4E73441058D18D2C1E450283F2064E00EF6B7327E630F133A9870A355C3` | NO | no | 1133 B |
| 6 | `_main/_lane4-run/work/mutant-escape/index/__init__.py` | `d8311a8e02e4fcea42696eedb3e79242aedc209f` | `9C1605929BD0DC51DEB4B0A599BDCBBF8B1610DC2610E827DBD43166C6A83CDD` | NO | no | 2612 B |
| 7 | `_main/_lane4-run/work/mutant-escape/index/schema.py` | `e5f332894de27ac99834954c093b1e02dd980d63` | `88FF530D829B229CF6367FE04142FCDA2E0117929B8C5080C48F7F923B87ED6D` | NO | no | 15748 B |
| 8 | `_main/_lane4-run/work/mutant-escape/index/search.py` | `721c0c813c190383e94cbd7c4a87ac1d5bf5f115` | `993E2FA70A1D55F4AF6E70409073A858E275D47CF6796BDD98DD6403BC30CC57` | NO | no | 10289 B |
| 9 | `_main/_lane4-run/work/mutant-escape/index/selftest.py` | `d1dec45dcbd72ff156f9bebe7ced167938316963` | `D721CB656A083ECC93D0C93CE8D7F53DACBA16A66A99B843DC920E935A83A254` | NO | no | 39987 B |
| 10 | `_main/_lane4-run/work/mutant-escape/index/store.py` | `b52f9ebfc69dc5056dbeb686e534d02f7ea7bad1` | `05B0766BD1783078537982338F501611A484E814FC53B00718C82E9C7D1F566B` | NO | no | 17145 B |
| 11 | `_main/_lane4-run/work/mutant-escape/mutant.json` | `1963c3b11878d68b9032edcb838a7ca0f434c9cc` | `28A41FC35A8CDAF50AAD5F26E5E2AD130F870A71CD982B8271558D69504344BE` | NO | no | 7327 B |
| 12 | `_main/_lane4-run/work/mutant-unit/index/__init__.py` | `d8311a8e02e4fcea42696eedb3e79242aedc209f` | `9C1605929BD0DC51DEB4B0A599BDCBBF8B1610DC2610E827DBD43166C6A83CDD` | NO | no | 2612 B |
| 13 | `_main/_lane4-run/work/mutant-unit/index/schema.py` | `e5f332894de27ac99834954c093b1e02dd980d63` | `88FF530D829B229CF6367FE04142FCDA2E0117929B8C5080C48F7F923B87ED6D` | NO | no | 15748 B |
| 14 | `_main/_lane4-run/work/mutant-unit/index/search.py` | `ee1e275a4aee8466aef3ccdf0372a0f62af556ec` | `AD3B284C9B027C903340BB20D37E46931C73310F326085971D58418CC9335641` | NO | no | 10039 B |
| 15 | `_main/_lane4-run/work/mutant-unit/index/selftest.py` | `d1dec45dcbd72ff156f9bebe7ced167938316963` | `D721CB656A083ECC93D0C93CE8D7F53DACBA16A66A99B843DC920E935A83A254` | NO | no | 39987 B |
| 16 | `_main/_lane4-run/work/mutant-unit/index/store.py` | `f0cef18a507d4f731ca4b584f374cf85d20d7993` | `C683A0A722F878CDCD3B1198A4D99D383CC7214E33083C0131A5A19933ABAB62` | NO | no | 17538 B |
| 17 | `_main/_lane4-run/work/mutant-unit/mutant.json` | `b29161dbe6568e0a22b98e131dbd9edd806f2ed7` | `A75066F3D95E08FFEF2A6E3E124BA87F8DB20B5E084BCF6BB3595971B8F8CF4F` | NO | no | 7242 B |
| 18 | `specs/07-highlights.md` | `783d0f475998dcff0aae3a95de46340f7df6310f` | `4CF88A02B0D733601D3849ABD07DA1E64D1E4F79DEED9D3731A32CDA68214F8C` | NO | no | 28600 B |
| 19 | `src/index/__init__.py` | `d8311a8e02e4fcea42696eedb3e79242aedc209f` | `9C1605929BD0DC51DEB4B0A599BDCBBF8B1610DC2610E827DBD43166C6A83CDD` | NO | no | 2612 B |
| 20 | `src/index/schema.py` | `e5f332894de27ac99834954c093b1e02dd980d63` | `88FF530D829B229CF6367FE04142FCDA2E0117929B8C5080C48F7F923B87ED6D` | NO | no | 15748 B |
| 21 | `src/index/selftest.py` | `3370b320ff62c7a6340afec1d14525e741250ce3` | `E2F5B91A96FB93054D53F215E5C4C48BC6DDA8809AD8516CD599F0555A68724A` | NO | no | 42745 B |

## Three-way divergence on src/index/ (the load-bearing subtree)

lane/idx16, lane/idxperf, lane/gatecheck and research/index-collision* all cite
src/index/search.py and src/index/schema.py. Same directory, three states:

| file | INNER HEAD blob | on disk | tracked by OUTER sotto | outer status |
|---|---|---|---|---|
| `src/index/__init__.py` | `d8311a8e02e4fcea42696eedb3e79242aedc209f` | NO | see ls-files | clean |
| `src/index/schema.py` | `e5f332894de27ac99834954c093b1e02dd980d63` | NO | see ls-files | clean |
| `src/index/search.py` | `911ea6fc15f7a7f34db085ce675d4a00c90f32a6` | YES | see ls-files | clean |
| `src/index/selftest.py` | `3370b320ff62c7a6340afec1d14525e741250ce3` | NO | see ls-files | clean |
| `src/index/store.py` | `0ed4a25d5fa5b1830851003d7ea3ef7aa2ba8d03` | YES | see ls-files | clean |
| `src/index/schema.sql` | `HEAD:src/index/schema.sql` | YES | see ls-files | clean |
| `src/index/_index-green-probe.py` | `HEAD:src/index/_index-green-probe.py` | YES | see ls-files | clean |

OUTER tracks these src/index paths:
- `_moved/aireplay/src/index/_index-green-probe.py`
- `_moved/aireplay/src/index/schema.sql`
- `_moved/aireplay/src/index/search.py`
- `_moved/aireplay/src/index/store.py`

## Last commit touching each deleted path (who removed / last had it)

- `_main/_lane25-stage-durability.ps1` -> 87efeaf 2026-10-07 13:47:37 -0300 mateusant13 lane25: census 18 locale-grouped format sites; 1 defective memory site fixed
- `_main/_lane25-stage-probe.log` -> 87efeaf 2026-10-07 13:47:37 -0300 mateusant13 lane25: census 18 locale-grouped format sites; 1 defective memory site fixed
- `_main/_lane25-stage-probe.ps1` -> 87efeaf 2026-10-07 13:47:37 -0300 mateusant13 lane25: census 18 locale-grouped format sites; 1 defective memory site fixed
- `_main/_lane25-stage.log` -> 87efeaf 2026-10-07 13:47:37 -0300 mateusant13 lane25: census 18 locale-grouped format sites; 1 defective memory site fixed
- `_main/_lane4-run/armC-v.log` -> 51f84cc 2026-10-07 12:26:55 -0300 mateusant13 freeze: estado do clone Sotto em 2026-10-07 12:2x (entrega transportavel)
- `_main/_lane4-run/work/mutant-escape/index/__init__.py` -> 51f84cc 2026-10-07 12:26:55 -0300 mateusant13 freeze: estado do clone Sotto em 2026-10-07 12:2x (entrega transportavel)
- `_main/_lane4-run/work/mutant-escape/index/schema.py` -> 51f84cc 2026-10-07 12:26:55 -0300 mateusant13 freeze: estado do clone Sotto em 2026-10-07 12:2x (entrega transportavel)
- `_main/_lane4-run/work/mutant-escape/index/search.py` -> 51f84cc 2026-10-07 12:26:55 -0300 mateusant13 freeze: estado do clone Sotto em 2026-10-07 12:2x (entrega transportavel)
- `_main/_lane4-run/work/mutant-escape/index/selftest.py` -> 51f84cc 2026-10-07 12:26:55 -0300 mateusant13 freeze: estado do clone Sotto em 2026-10-07 12:2x (entrega transportavel)
- `_main/_lane4-run/work/mutant-escape/index/store.py` -> 51f84cc 2026-10-07 12:26:55 -0300 mateusant13 freeze: estado do clone Sotto em 2026-10-07 12:2x (entrega transportavel)
- `_main/_lane4-run/work/mutant-escape/mutant.json` -> 51f84cc 2026-10-07 12:26:55 -0300 mateusant13 freeze: estado do clone Sotto em 2026-10-07 12:2x (entrega transportavel)
- `_main/_lane4-run/work/mutant-unit/index/__init__.py` -> 51f84cc 2026-10-07 12:26:55 -0300 mateusant13 freeze: estado do clone Sotto em 2026-10-07 12:2x (entrega transportavel)
- `_main/_lane4-run/work/mutant-unit/index/schema.py` -> 51f84cc 2026-10-07 12:26:55 -0300 mateusant13 freeze: estado do clone Sotto em 2026-10-07 12:2x (entrega transportavel)
- `_main/_lane4-run/work/mutant-unit/index/search.py` -> 51f84cc 2026-10-07 12:26:55 -0300 mateusant13 freeze: estado do clone Sotto em 2026-10-07 12:2x (entrega transportavel)
- `_main/_lane4-run/work/mutant-unit/index/selftest.py` -> 51f84cc 2026-10-07 12:26:55 -0300 mateusant13 freeze: estado do clone Sotto em 2026-10-07 12:2x (entrega transportavel)
- `_main/_lane4-run/work/mutant-unit/index/store.py` -> 51f84cc 2026-10-07 12:26:55 -0300 mateusant13 freeze: estado do clone Sotto em 2026-10-07 12:2x (entrega transportavel)
- `_main/_lane4-run/work/mutant-unit/mutant.json` -> 51f84cc 2026-10-07 12:26:55 -0300 mateusant13 freeze: estado do clone Sotto em 2026-10-07 12:2x (entrega transportavel)
- `specs/07-highlights.md` -> 51f84cc 2026-10-07 12:26:55 -0300 mateusant13 freeze: estado do clone Sotto em 2026-10-07 12:2x (entrega transportavel)
- `src/index/__init__.py` -> 066005d 2026-10-07 12:23:02 -0300 mateusant13 wake v4: mcode exec --session is the door; the SQLite queue only validates
- `src/index/schema.py` -> 51f84cc 2026-10-07 12:26:55 -0300 mateusant13 freeze: estado do clone Sotto em 2026-10-07 12:2x (entrega transportavel)
- `src/index/selftest.py` -> a5fd446 2026-10-07 12:35:39 -0300 mateusant13 index: the searchable clip index (schema, writer, search, migration) + LANE4 gate

## Constraints honoured

- No `git add`, no `git checkout`, no `git reset`, no commit.
- No file deleted by this lane. Backups are ADDITIVE only, into `_main/_deleted-blob-backup/`.
- N = 21 deletions, POPULATION = unstaged deletions in this one repo at this instant.
- Nothing here is staged. The parent orchestrator owns every commit.

