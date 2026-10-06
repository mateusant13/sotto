# Sotto — tracked durability of the session's fixes (2026-10-06)

**Repo:** `H:/sotto`, branch `main`.
**Auditing lane:** `TrackedDurability`.
**HEAD before this work:** `3e90f929bf0c83cf89d7871487322eebfcb84a4a`
**Commit that makes the work durable:** `5ffeefcc1e73c5c3d6b7aa47e591bfb8babf2e95`
**Ticket this closes:** `2051631332c989dda4e1d42f` — *"worker/wasapi_loopback.py untracked by git so git diff is silently empty for it"*

---

## Verdict

The **two fixes that proved the app works this session lived UNTRACKED**. `git diff` was
silently empty for them, `git ls-files` counted **23** files in a repo whose app is dozens of
files, and a single `git clean -fd` would have erased the whole session. They are now in
`5ffeefc` and provable the way this house proves durability: `git grep ... HEAD`.

| Fix | File | What it fixed |
|---|---|---|
| the flat endpoint | `worker/wasapi_loopback.py` | `nonzero_blocks` 0 → 451, captions 0 → 42 |
| the silent-machine watchdog | `app/webview/sotto_webview.py` | 54 spawns / 14 silences / 35 exits `rc=1`, ~2413.7 MB per respawn |

`git ls-files | wc -l`: **23 → 267 (+244)**.

---

## 1. What was missing — the inventory

Snapshot taken with `git status --porcelain -uall` and `git status --ignored --porcelain -uall`
on the working tree (see method, §3).

### 1a. Untracked but NOT ignored (`??`): **901** entries at snapshot

| class | count | what |
|---|---|---|
| **CODE / DOC / ASSET — now tracked** | **244** | the app, the worker, `scripts/`, `docs/`, `AGENTS.md`, and the `_main/` oracles |
| **GENERATED / SCRATCH — excluded** | **658** | run records, logs, captured stdout, downloaded model weights, per-run scratch dirs |

(901 = 244 + 658 − 1: one code file, `_main/_app-drive.py`, was created by a live lane
*during* the audit and added before the commit — 902 observed in total.)

Breakdown of the **244 tracked** (by top dir):

| dir | n | notes |
|---|---|---|
| `_main/` | 147 | the oracle/proof scripts and receipts, e.g. `flat-endpoint-oracle.py`, `model-spec-oracle.py`, `device-silence-oracle.py`, `wasapi-com-init-oracle.py` |
| `docs/` | 50 | the audit prose **and** `docs/model-specs/` (the model's own normative docs) |
| `app/` | 43 | `src/` (Svelte), `src-tauri/` (Rust), `verify/`, `webview/` (**incl. `sotto_webview.py`**), `electron/*.js`, `index.html`, manifests |
| `worker/` | 6 | **`wasapi_loopback.py`**, `lang_prompt.py`, `README.md`, 3 `.flac` fixtures |
| `AGENTS.md`, `scripts/agc-gate.sh` | 2 | repo context + the AGC gate |

Breakdown of the **658 excluded** (by top dir): `_main/` 413, `worker/` 205, `app/` 40.

### 1b. Ignored (`!!`)

| | before | after |
|---|---|---|
| total ignored | **4081** | **4743** |
| `app/node_modules/` etc. | 3649 | 3649 |
| `*.log` | 365 | 365 |
| `__pycache__/` | 32 | 32 |
| `worker/models/` | 28 | 53 |
| `*.wav` | 3 | 3 |
| `history/` | 1 | 1 |
| other (run records, scratch dirs, `.err`/`.out`/`.jsonl`/stdout) | 3 | **640** |

The +662 in "ignored" are exactly the 658 generated files that moved from **untracked** to
**ignored**, plus 4 that were already ignored (recounted under the new rules).

---

## 2. The change

* **244 files added by EXPLICIT PATH** — `git add --pathspec-from-file`, never `git add -A`.
* **10 tracked files staged for their session modifications**: `worker/sotto_worker.py`,
  `worker/config.json`, `app/electron/{main,preload,panel,worker-bridge,hot-reload}*`,
  `app/electron/BRIDGE.md`, `.gitignore`. (`worker/sotto_worker.py` alone is +2633 lines in
  this commit — the silent-device / verdict-order work that was otherwise uncommitted.)
* **`.gitignore` extended to exclude ONLY generated/scratch state** (§4). The two named fixes
  were **not touched**: their sha256 is byte-identical before and after (§3).

Commit contents: `254 files changed, 70261 insertions(+), 346 deletions(-)` — `244 A`, `10 M`.

---

## 3. Proof of durability (the instrument this repo uses)

```
$ git ls-files | wc -l
267                       # was 23 (ls-files-before snapshot, 23 lines)

$ git grep -c no_audio HEAD -- app/webview/sotto_webview.py
HEAD:app/webview/sotto_webview.py:10

$ git grep -c no_audio_evidence HEAD -- app/webview/sotto_webview.py
HEAD:app/webview/sotto_webview.py:6

$ git grep -c COM_REF_TAKEN HEAD -- worker/wasapi_loopback.py
HEAD:worker/wasapi_loopback.py:5

$ git grep -c _com_init HEAD -- worker/wasapi_loopback.py
HEAD:worker/wasapi_loopback.py:5
```

**Negative control** — the *same* commands against the commit *before* the change are RED,
which is what proves the grep is measuring the commit and not the working tree:

```
$ git grep -c no_audio HEAD~1 -- app/webview/sotto_webview.py ; echo rc=$?
rc=1                      # no output: the fix was NOT in HEAD~1
$ git grep -c COM_REF_TAKEN HEAD~1 -- worker/wasapi_loopback.py ; echo rc=$?
rc=1
$ git ls-tree HEAD~1 -- worker/wasapi_loopback.py app/webview/sotto_webview.py
                          # empty: neither file existed in HEAD~1
```

### sha256 BEFORE == sha256 AFTER (the fixes were recorded, not rewritten)

| file | size (B) | sha256 |
|---|---|---|
| `worker/wasapi_loopback.py` | 27856 | `10a1e611a9d701ac222aaee1dd98fa3952fa8e423805fbbc4bbcb701ada68f6d` |
| `app/webview/sotto_webview.py` | 160779 | `eaefd4cfd430b776a2f2a1d2486bb83939aa050c4180aff3e716f92637e98118` |

Both hashes were recomputed from disk **after** the commit and match the pre-add manifest
(`sha256sum` output below is the post-commit run; the manifest rows are the pre-add run).

## 3a. Per-file size + sha256 BEFORE adding (all 244)

Verbatim manifest, `size<TAB>sha256<TAB>path`, captured **before** `git add`:

```
21539	7456ec5514ddb6a05de9d8752cf813f15abd43489838166902b8b0c2f8a5eb06	AGENTS.md
17968	8eb2cb043fc2013e62baa325f2a2f402492dfa292c7bd0245753a4403a0559ec	_main/RunCmdExitContract.md
14443	5409abaa9e452cb1689fa99e457d06d0b3c7afda9a545f1f86e9fa8c2a3ab883	_main/SottoDeviceResolution.md
21287	d0768df16737c9dfc836bca53bac4d69875d64afe52e7559e0703245085dc6a9	_main/SottoExit3Panel.md
18832	c6296b4d78494f6f6b51df164bc32b5a8ddc86ccca3741cdc597e1023f7cfa70	_main/SottoPanelPaintsVerdict.md
4785	7548ccc6b001ba6f5de38db76a3f2a473787faacd84bc9a80b03cef67444f24b	_main/SottoStartupFlash.md
20381	ca287a982b65c2b662a935ba5b8110bc32d6e5972e631ddb29b6ecfea940dbc3	_main/SottoStartupVisibility.md
1526	d78f7be7013b870811e8b7d2b6edd0d50993ba8a62cada3142f1e626a8f1db63	_main/_agc_calib.py
3859	9eb6d0d54d55cf7713b5a1623119d37f14e7b2d38d4b2c0f85af3ea9170136d8	_main/_agc_live.py
1069	659353b9d780ab24a5b9b611e3eb94a68c605f19ef6859959218f26cf7dc5447	_main/_app-census.py
2888	1ba7d4214a8c104137c15e164553f0b81246976b969f8e734461f33c3d69b494	_main/_app-log-parse.py
2792	0373b522b0c6aa2a3bae9337e4e1c9d05da394d41719ce044df56d57c386a876	_main/_armE-fake-worker.py
5557	adde887354c50e62b281934af80e26e9a79d39d71291e9b52f7c19b9230e60a7	_main/_armE-window-census.py
5069	736f3a61e18ed0c32f5cdd98425d65912479684cc89816b32f96cbd26bf2ad7a	_main/_bfrc_all_endpoints.py
2033	4a5ee6ba9145b0bb488e048fe4c144463d835684d43ba4e336b28769fbab265f	_main/_bfrc_armB.py
2464	41de36707feedf48636ec6446bd3bcff9bcae10b9abc031d348895335e10ae14	_main/_bfrc_armd.py
2526	9c3d8a770776fadc48152430b86a8d9d2e4865932387bb1a737c688a6d3cdcd3	_main/_bfrc_capture.py
3271	875e3bc6bd423ef61642d4d4d938288ef19d54b8e7f3295624bf701c9caebe82	_main/_bfrc_content.py
2149	b5fbb3145d496f7e18aea2531671221453c03ca7169da47d3b6a70ab5dd35b5e	_main/_bfrc_content2.py
3683	06f55a526651095b3eebbf4212c136d18cf8668dd3b17b2907c0118f32c5cc22	_main/_bfrc_endpoint.py
6485	4fddc253cab477b1a9dc8e2c9f920c717d36ee88848c64274563d4b10652bfd3	_main/_bfrc_endpoints.py
5459	0441999d07f37d816ba9c9a65f84a740445168b5ba55f31d0d4b0cc4794b9532	_main/_bfrc_flags.py
2033	050b508404911b2a982e8d0639f1533c90075cbe1116527266b286aa8029cea8	_main/_bfrc_head.py
1785	f101b2e82ce9ef5492973cca78d8fb2b682227aaa8eac69361267e5108dbd023	_main/_bfrc_make_arms.py
4343	4e336e24e2088d6f10c229d2624e0ec1ea951ab489bd62591f49012e806d15fc	_main/_bfrc_mic.py
1828	95cfde7d980e1ea289f1928e7ad93fcf8aba9143c9ffd857de124031950b4bbb	_main/_bfrc_mix.py
3111	54d87dba963f03ec3ec2e4ff6c628966efe7025e629ad3b4444e5ee348ef9ae6	_main/_bfrc_play_capture.py
806	7a28235805a32aed823b4a55ade050ec6b96fa0809ab117a41b08f3f67310de1	_main/_bfrc_playdrone.py
2225	ef5d6f13d06f71487f432b7fce9996ff7348fc4c0d8a6d04e295bcca89ec3931	_main/_bfrc_proof.py
1585	b9a03baf6f87f296b9e9399d6ba574955973c8c9d842a719215af2fe4f716d8b	_main/_bfrc_run_arms.py
3761	b899f46ca7940c9c91308f039e8f1c02432f696cfde6a26eba3b398253a33270	_main/_cfg-partial-bogus.json
3761	5cf8742379ab874846feb8feffdf77c16445da7517205a3e824f5e57a890949c	_main/_cfg-partial-false.json
27938	1637200662838a6a0570e5124458246df51b94869a08c1414283fff56b8d4440	_main/_cmfatal-changedmode/wasapi_loopback.py
1788	77112cee6a09ab113648cd69b4dbcea7a1ae0cc9e7147042b166a735e16cf56e	_main/_comdbg.py
2216	5b54b91e1d9d026e091d833deea0621622b72ddcff36503e9e1fa10f75b83507	_main/_comdbg2.py
3813	40dd306a8f563e8cd15b401fb6a677abfd8683d0c9fc8361fc2eb57083edab24	_main/_dance-probe.py
2521	50deab5cbe9279b11da12a123cbd772391595d9901982634bfa3b90148d4c7bf	_main/_diary-src.md
3266	b207b7a68f46b3cc1b2f8fc785afa7cbea94f65d9fb610d517ad3eaa1a42acca	_main/_diary2.md
20277	2a2f8021d1e92fef2ca20e6bcf8b6167b452965d7752c88598acfe6a454a753f	_main/_flat-endpoint-mutant-wasapi_loopback.py
2306	6496a37a10e4f285518513fa6d5652a72beeff0069defd744dbba515ed69516f	_main/_join-play.py
690	1b222fda18e5cc762a42b021a565c26e47d3d90a161b0d366d31c8f9f8b7da24	_main/_live-launch.py
1296	94df2b4a58d972e6ce5ddac8d03130f047f6a399848a3f9e5dc4a3cad173c49e	_main/_live_key.py
1363	c29a7e7c21ac6aaa66eea0b61e104f1ac0043bebc034b5c0073db771117d9129	_main/_oss_oracle.py
103419	9a971d2049666007521e2397a29b1a909e72f644c8c73e2f52aa3a6376327958	_main/_panel-clear-lifted-mutant.py
2899	f8752b08d5f50b96b12b19c3e573a240198916bd94e42547fb29f06dab47c2ca	_main/_panel-gap-visibility.py
2082	3d17e858670ab570484b83617ab45f408c6a875ab83014d3ecd1c5985b0cfe48	_main/_panel-v2-reveal-check.py
103609	0fb21eaa1bffb7794f93e2567541a3205fd3759a529432310d8e32ac369bff9a	_main/_panel-verdict-benign-mutant.py
2385	cceafed011fab458490ca5ceb3fc4d43094cea041218ce49433db34643d9d586	_main/_ppv-census-driver.py
103597	698004d338bdf92694f822c7a671d661f1f51e5cf5e3a6db9c28c2137cc13204	_main/_ppv-paintorder-mutant.py
91353	b1d55f1c0dfa3dfedf323e8e4f35391fe08a50f4b9fd82e1e0507dba6b012291	_main/_prefix-under-test.py
407	84fc6cbdf17724ad232e3a70411ca7d2268c33e43a986986c2ef7f8fc07cb4e9	_main/_pwtest3.py
959	a67536ccb64f94761a550caae3f6643dcc49981fc9259e537715b24ec8de964c	_main/_run-hidden.py
100	a7ba9a372fe251b5d1513fc7032c260af358274c059fedb932cd1ce9c56fe177	_main/_runcmd-cmdline.ps1
2931	12ffef0bc2226a256d16438137350f85a019e996b6b8fb1137cc8cb4e56eaf2f	_main/_runcmd-console-probe.py
5361	a252c7a3e060a8af2faa057922a3bf6ea892c64893364fa53188c6b097357ddc	_main/_runcmd-panel-flash-probe.py
410	71f8b454e2378697f6b9e819c7ab951df3d985063af57b8013912b95b05b8116	_main/_runcmd-ps.ps1
808	29a5d6cf4133b19465208d2295a7256b01c54095522cdc22505decac42f9c075	_main/_sdr_show.py
100648	388dce4889b5177f11ffa852c0bd7f36f515755c4b939696bc1207e909953570	_main/_shell-visible-neg-arm.py
252	90e71a1385ba21ded51214eddf99691c68a2b8ded948d3884d6d46bdc30fc68c	_main/_sotto-procs.ps1
5074	66fdd87868efeaca0203af7f9e8ede7bcee4f424c4aa32d80707696b3a8acca7	_main/_tap-restart-fake-worker.py
3823	b1d637c43baa3c1ecb40849d9ec9178ecf1c9ff3c16c72b07fb43854168087ff	_main/_tap-restart-live-arm.py
156833	21e759004a7b138fa10cf118253dd9d2f6a978a30410a03754d5112fa26d6c73	_main/_tap-restart-prefix-mutant.py
2110	3f8d26b7a3d961f28d92a4cb16bef9bc207421c9937c823cd6583cebe5ef1155	_main/_visiblechanged-probe.py
20277	2a2f8021d1e92fef2ca20e6bcf8b6167b452965d7752c88598acfe6a454a753f	_main/_wasapi-com-before-20261006-063555.py
115	46f2f44dce954f7b7b7ffca9d73423523f81f786258f2ea057a93d2586a40736	_main/_win.ps1
1375	acec3d854a5cf5642a6987d991c4fdc6e2a20c1db1d3865f8744031ff12d58cd	_main/agc_drone_floor.py
5692	525246d4d81d028e53814dbe28d2ced897f0ee405103dabfd17fa56149c8bad5	_main/agc_order_live.py
4075	935b532710bc38187e21dc26786dc0bf044fd94fd937683430daa3f4e98a95a1	_main/agc_order_probe.py
2137	810e754960fb499960801d094f65a6d8f7662894ee42c6fea3cc44bc8a2bb881	_main/arena-probe.py
14115	068b911bf983088f1881f64fcdac294146b815371b30de12577c64ceafb4d746	_main/bfrc_decisive-report.md
24153	70ca9d484809b2b4914930d3c6efee92bcc03d28c48c5b5738c7e1ac7c2c0dcf	_main/capability-probe.py
9922	3d2bf4e3371b09cfaeaa8f970990f3674273bedb5dc42a55ea91aa9777edd544	_main/caption-lines-oracle.py
5781	3b13fce55cc32263f47370d6f1d2d9828fb6e54103d48f521b7c1cdfd93c054c	_main/caption-renderer-integration.js
3329	895c6fc85c3be464cca3e1c47519743b43cb3614f8d70c42f2c1e51ae8f8ff63	_main/config-block50.json
6334	73f7f0f11022ac7d425e0492493517bb71ee3c71dde8e7fcfdaab0b01e679640	_main/config-keys-oracle.py
3330	bfae621e3f2e79b168e675ee6b317c6c7861a35f2dc81abc52b0f82e028a81ac	_main/config-minchars8.json
1997	0ff2edb940c71122bb9d999f42385f9fd7785335f3433d85eb0cdf41183d29a4	_main/config-vad-off.json
4210	719a68f7b9fcb6260e0b8c6e8ab71be171db37bb46087ec8585f753309b9a440	_main/control/caption-formulation-pre.js
2081	ad2774dc3d99a13bae7b34ad91b350f451e66ce77733c49fc7bb0df7728e8132	_main/control/join-pre.js
20080	ff97eb48dd46671f6173451000f4ab77c8b6d3aeb6ab1ffcdf31f89d7981b239	_main/delivery-rate-oracle.py
2370	94bbcd093d99647eded08a3b4f0ec9b3fcba52bb6c0ce4280c0f97f7b9282e5d	_main/device-names.py
3060	659d91788fdf8d0ab565a5b1eb068f73af15c38739b136d8a3c5b382bed6b8be	_main/device-probe.py
8555	7a7573388fb2bdab97dfb73475c40466b8f7391f1bdb02c057894df714f5c283	_main/device-silence-oracle.py
4034	0ec6be77efcaaec03744104a1b77654cbbc1f0b859c1eb32668b8f99b27063f3	_main/diary-20261006-0609.md
3054	e6e44d4b74ffb429ffca22eead21da62cebc127133f5a67ba166570ba4c34bf0	_main/diary-20261006-0637.md
2546	0e2475345a33e270c9b93d32fbba4bef0445853f53e78580f60b2dd8ad71e900	_main/dr-ring-probe.py
3236	65da95ffb14ac46d1150a1a5ee91599993656bdd6c20d6a92488fefc3dcdc96e	_main/flat-endpoint-control-changedmode.py
2336	4d79634d13eda73bed164cce316869ade5b71f4a20da756f3c60c5d144155ff4	_main/flat-endpoint-ladder.py
24315	2f54987abd4b536c9701a9fece5bfcdbcfbbc05a6ba8236ec0e3f54f6d244440	_main/flat-endpoint-oracle.py
11155	00a41ab59816d2acacd43176b3e26d26926ab467ea9ad2296a6249b0c3433f1a	_main/flat-endpoint-receipt.md
11278	d4f5100ed4a4c7980af2c8188870f3ac410b2e5e31633ed702d17ff82f2547c9	_main/flat-endpoint.diff
925	ab26c0c4d5720ef9650658fd9ee06be5bfb3e1d02eaee26b96c65bfe7e57ad14	_main/gate_play.py
2963	2c238e4660db68de7046ed6c4c4800312c4d6d411db66d4dd32ef25012068052	_main/gpu-diag.py
4513	817b10b505ecfe9b9a18ba4b8161a1fca03ab38222bff794d4218058fd8cd445	_main/inject-all-probe.py
4906	1bd8e6ee8fefe34f57c3bff708e1c2e362b29013bbc71e1a6e1353a215dd6437	_main/inject-probe.py
10478	7885ed4c5d2a3bf85ad1dad38fc3b82aa25c8942f6e0ab73c3b3f932413bb913	_main/join-harness.js
3493	70ef4794f2e948298cb0a71249b043cf0926b6a1b1753f3af0b0808dc0abb35c	_main/ladder-probe.py
1994	313e221da38c8d1be926bb29156597eb535c68ebd65d9546661a620d12f968c7	_main/lang-id-config-13.json
4550	ddad5a16dd2a121481ea7b291c9a88f39fab55868b6e8e5e41506c0faae89ac0	_main/lang-id-default-arms.py
18239	4cd24f2dce59ddb2357ca718e975cf74e21bbcdbede0e8ceee5e1907d41818e5	_main/lang-id-default-receipt.md
8238	05d670f25a7cac8a93b48ed3a06624af716449ec8ff36875cbc594a910a9b056	_main/lang-id-oracle.py
18304	1c7757500127da27b190dbcd47e4a5f2051269aeec94f29f8d51a5d4a8039bb0	_main/lang-id-receipt.md
4034	47b3f011f6f4081d3ac7e454fb5543e663c65d9a0671ac203130c05f3f14de8f	_main/lang-id-runs.py
2813	622965ab898da3e6d733183a7a8fa01f8f112726a958049e51cbbf34afc63ae7	_main/langdef-arms.json
3290	9cbf9901484c576eec796397b23bf3d25916d40a6e3b6e6d4c57d6a7d99802a8	_main/listen-probe.py
1260	b753aa76a6822e52a5e04f3b0f0c19fe37c0e7254f1b589191a9688dd2104230	_main/make-tts-samples.ps1
3144	d3204236126727a8c61db303a483e1d6ad6f25b0cb800a95ce5676da46654996	_main/measure-asr-warmup.py
3140	c3912f582fa5ca8993be6bd0f91a4b0d49986dbf11d0489229fe8ccafb139437	_main/measure-readiness.py
2011	f47fbb9ae52fa7a06dd6a1e5a456801fc7594a1e55ae1ec6e4f71168f7fd736c	_main/model-spec-oracle.py
13075	6b65844dcaa4bf4b1cb29013d5125c1ddb475a819e70332548a5b4ce79f79aa9	_main/panel-exit3-armE-receipt.md
49742	0cf17b1d8a86e809ea48bb59e990752814caddd958c28417019f82fe8e98872f	_main/panel-exit3-oracle.py
38537	ea549954700dcf916201d89b8a239d5166c2350cb1effaa3c195db871733eb5f	_main/panel-hidden-at-startup-oracle.py
25210	f0eeb05cf92458fcef0a7b9e20c548fec56abf1f9964da59737e3acb812de68c	_main/panel-startup-flash-census.py
18827	af8012e10e4d29d2cd536a73ab01bf335726c98efcf9216ffd4afaa4ba6b65bd	_main/panel-startup-visibility-oracle.py
19297	d75551d8e2f286d5f5b0599a8eb7a8f38bec26dd31dfd1c56e4ae43c42bf7ee3	_main/panel-visible-window-probe.py
2062	01dcc0ebf24fe975f54b558aff74cf76c6a5d0f5e694d737a5495eac69f5fafb	_main/play-to-default.py
2944	e65c934c7047d24d6bb9ddd2b53bbd5a76a7a131ae5cd575061b9d8c214c74f9	_main/precision-ram-probe.py
2799	d7877f3ceb5ff7db650e912f400e694113f299d95252463da7a9511d8327464a	_main/provider-cost-probe.py
3151	5c4e0f854c6f5edb385bd78f9fd5c15c063bed405a65ef497a0273e90782cd7e	_main/receipt-append.md
3267	f2e97e3e14c28a198aff07b4812a310ed447e5308a6ebcb989546939d1a8ddae	_main/receipt-append2.md
1346	391aa4f867304ab9b7379e1de98b493b20630e54bf5d08c8697182c7fb13b52f	_main/receipt-append3.md
3229	a4b642203c5b58a06669540356a9af216839aabe46c14ae75e8105b3be4c3a05	_main/receipt-append4.md
2917	95f20567835710137b0dc859b13ebd92dc517f1485843fc1bd4862782beb6f94	_main/receipt-append5.md
2429	2ba799c7a24b4ae8cb5d4365772e5439f6face8a9191de380ea97c20e6cf1c52	_main/rect-probe.js
52152	5f43d7f296488c27ff87f41dc5aec9330e1be1a8e077f2857ff1b967de4ae5cb	_main/run-cmd-exit-oracle.py
3487	b9c08fecb94f8031d40bf88a37d49c9e1a0c44167e711ad1344a8dac6f8add6e	_main/run-cmd-prefix-20261006.cmd
2469	b922d7695821366087be6e2a158ec91ec640e7ccdaf0659be7e2c0ca7a66b139	_main/run-live-hidden.py
5884	31b26a6221361d3a23c5508ba7882f5fd5e68d9c930013d2e92cd1cc60bdc6a4	_main/run-live-routed.py
3356	15d55fb5fbbea07092bbb641d0936c5c79d82f506318fdb1d43dfac033b98733	_main/run-with-cuda.py
24634	4b3ce76e1dc8fc419fee4d53577b1b50fe65e82d4e7c162cf7defd73461459af	_main/runcmd-entry-driver.py
5182	37131130f6ce217ba3139e0daae353fafc5fd932dbd1960038d9188a038f786c	_main/sdr_idlefloor.py
3750	6452b1c0813f5f7c2bfc8ec4fa9ee6c9ad76cc7582d181dc18424465bb914dcf	_main/sdr_proof.py
108336	45f37917d3e49f8cb92ecc39cc2695832ff84899f9e5164969b498e4c7a3da03	_main/sotto-webview-prefix-20261006.py
4469	0cc16d7f29f527b08a2ab32b897a0a4d9f5c28a776fa5440e1b9419301531500	_main/speech-gate-oracle.py
16452	abecf9ab0a048f05e1121e2203746c34aaf571f418b5a0705237b577bc5eafa4	_main/tap-restart-loop-oracle.py
4203	1d4a174fc4743a40b9e5742ced74492015997e3c512e8320b83c006d3dbffe09	_main/tap_positive_control.py
1955	cee815f2c983e1db790138ec1b2af8567045d98b435d1cc536052c67ab0c27eb	_main/vad-arm-run.py
3326	dc616129bd66b0336ae3e896df31bc25f9569718e1fa0ab43322f10b268df6a7	_main/vad-option-probe.py
2100	7049df9187b462e81c3276f8bb661780bd6366656e119f239df6da0f32a1c69c	_main/vad-renderer-arms.js
16921	135ac3c9ea1fe86dee640208c36c1fcb7adc29536d9c2a75eb867568aff8fbad	_main/vad-turn-boundary-20261006.md
14011	96fb5626a02a421e5ef48013d1152950604b7ac4722eadab5a9324ef729709de	_main/verdict-order-oracle.py
13070	703e6ac01c8814e9bb4f6c0a76e11947c98a906f3164baeadf29b0f989f0f665	_main/verdict-order-receipt.md
12967	81872cee56f1c7ee074d15ff23929693221c2d37d52dd477096485f695ac6123	_main/wasapi-com-init-oracle.py
58	917afa09adce6f53ff253709dab3a7a440328907d4ce214c362f0517cee9605c	app/.gitignore
24496	bba6e55d7b756d8aaa9ab263b1a00ea433daf91ffb8f763ad464511a0f18792a	app/electron/HOTRELOAD.md
13640	b8a235659c73a6638651cda44679710a61509a079102ac210297e105cf05f916	app/electron/bridge-single-instance-selftest.js
16802	fc5eac99e75884d9f8ac564e5e17317194c091ac5d5ca0b6b4809eafb28a3b79	app/electron/caption-formulation.js
27148	c6b2d23e3981083c36001f1ee667d9ff1b3e5ffd80ea2d92857b2f35838c7850	app/electron/dom-probe.js
6000	df9232b7391af438bd2aa52dc053ae036d635ca76218f9fe986dbccbca3a8644	app/electron/history-store.js
8328	026b4bcee876672fbde65aece46565313e886a8547e8c4aa7b73dadfc4957431	app/electron/hot-reload.js
9286	8a8526149ee9471ec2c00a66258731e0e6ae414b54f8a48a7d6df679e0802bc1	app/electron/worker-proc-count-probe.js
289	aa1283fa5170b7e121f7271fca98fc317a9ce6c752c0cbd6096f82270ebe363f	app/index.html
79286	9b55a189b6c7e9d8b092da080481c0e0f93a4288f3b61f3093fe4a87547b896e	app/package-lock.json
691	ba771c3e7fd73f3ad84495284f4112509d867dc2755ff7a52b3efae7d5af0132	app/package.json
672	2c04ee0e6fec4171e8554905b1055ac5e4b1a779af30b7bd1834e8372ac82b99	app/src-tauri/Cargo.toml
38	056a51c06dc223d06896cdc9611aec38afe0fb62520555b2393d9425b8f3d31b	app/src-tauri/build.rs
213	0fa7369ae121ee5656e6955b9ab6fa536cb4d2610bd75a414fb11d7555cfcc99	app/src-tauri/capabilities/default.json
2717	5ec3bdf58a796368663a063f2a3bd348f33c36ee9ff95a2bb5579762d9b390ac	app/src-tauri/icons/128x128.png
5345	ead5d9ee0c5cad3c380ff013650335a0fac86a5b15740a10ebc25abbbb299d58	app/src-tauri/icons/128x128@2x.png
627	a80eff7262879018f1567cb1d32cdc8fdc1cab4c6b67f00f14c34eddf8e6ed8b	app/src-tauri/icons/32x32.png
2717	5ec3bdf58a796368663a063f2a3bd348f33c36ee9ff95a2bb5579762d9b390ac	app/src-tauri/icons/StoreLogo.png
4670	f33caf64055d534d7821b111812e79ab841b5a4a088694c591b97bac9f8d33d9	app/src-tauri/icons/icon.ico
2085	7bae6d80fba4cccd50043a1be697d3f16718d2708d2c9b9d33ae66a44d919620	app/src-tauri/src/commands.rs
11602	79f8a28ad9b1b9f54a218ce337b7e0140e03cbdb8573ee79a732964162455346	app/src-tauri/src/geometry.rs
4208	1088b34013fb56889afce0825115a0982b9f5aac0838a6d2aa23dcdb279e3d53	app/src-tauri/src/main.rs
5236	b3827714e48a98c6c8fa3c8cbd93ee25a17a051e7759975356c1a8a1a6d4a8c7	app/src-tauri/src/memory.rs
1151	21094b6333e38112199df8df7d7f6ae12398f8679946b5a04053c73f72b3915b	app/src-tauri/tauri.conf.json
2305	89f7d05e0b46d45607cc05849ef9472c219c89534d24b10b0f44386938df13be	app/src/App.svelte
868	4ea6ff78bded86f754ac368754502d4f1cb2ab8ea6bcf5a036a1659872974c34	app/src/app.css
718	e63e385e9e7846ccd91d6348f5e65b90cdc2326c4b3c1f2d2e0403b0f065c5c4	app/src/lib/ipc.ts
1085	dad8e1c5e55cca1f59b28fef2a26a02a589ea6faedc992cf1fef322716358a75	app/src/lib/types.ts
247	7d1b21f0895569b040dc2d086b6b042f7ec38d815e974d56294f75d036eb409f	app/src/main.ts
70	74673abaf2f34ba29e3aaed33e53a45db40baa3733f25ab09894301a0f814803	app/src/vite-env.d.ts
115	e8fda1b552b5019292bf9e7d4b81055aa053dea46dda40b14e9723066485c95a	app/svelte.config.js
536	10f592842ca66c6bc88ca5006c8361f843ccee5e4e679490300477b1af9399a1	app/tsconfig.json
541	4d8d39ea13a68d641a5d7a90f7beaa2e950c60b321509ecf2cd2cf803ae2a022	app/verify/Cargo.toml
3183	f7041a2daeeaf90225c5922c662f70e380dcbc96097073beb9cde4c20ff0dd02	app/verify/README.md
863	d46efa0e94dfe2ccf81fc861983857695d3bd8e183600d237268c02ee54f44ea	app/verify/rustc/fakeserde.rs
2488	269f2238ff0b5f97b12329212a49b969a4cf4e84433cb1d6bec5cab7a1c386c4	app/verify/rustc/tauri_stub.rs
1965	05c57870cc94390ef696572b2a29042af381f788c0e6b076851a13d97999ae9d	app/verify/src/lib.rs
612	e7d0effbd37ae4f70337b9d4d2eaa3976d1466e45389e21766a43028935d27a7	app/vite.config.ts
6616	175b2717cb88ab80e7836e67d78aefd40cbd06f275f06dad084f36f052dc5e7f	app/webview/README.md
25465	4fa7f550d066aaa69322e995cbf5cafd196cda3d74821903431f555933e222f3	app/webview/hot_reload.py
8551	8951e69c3b758fb05b9ca4a17f35a27b0556c6042e65d7ec232994e0bb5d367b	app/webview/run.cmd
160779	eaefd4cfd430b776a2f2a1d2486bb83939aa050c4180aff3e716f92637e98118	app/webview/sotto_webview.py
1159	7443635900640f6a8a1270202ddad1b6d6573ffe9b22bb131a5ea1af36076dbb	app/webview/stage.html
25906	a36e4158e7d65963ea3bb7ca90b7ad443edc09c5f9b362d7fc75cab75ef34783	docs/accuracy-int4-vs-fp16-20261006.md
17025	ddd4bce0b0e0a6077fdf6ac610aaf337b7a3f4a1cab53430fe5c72a068289709	docs/audio-ladder.md
17427	281726158d7f70d56b4aaac117919d7d97310d3ae9bc3ae93583fe58dbc3ec25	docs/audit/00-MAPA-CONSOLIDADO.md
15394	bcbe615e2829facebc6de0dec39ca4b58cdb03beebf6c1947e52679fbff8f33f	docs/audit/00-MAPA-REBUILD.md
21528	5bf88b3ebe5ef36b460d1aa79a2a7c422b37255872952157a31f3dcc996cb7b0	docs/audit/00-MAPA-REVIEW.md
28312	ca6a89c1520f9e894dafde68b784b3d8b795b08259f8f5b2b8cc36f4bad97c8c	docs/audit/audio-path.md
21965	f79b9987cd4265723a8ad54977fc88adf5b05e58227f7817230acaa1be095666	docs/audit/auto-gain.md
40664	e446936428039affadb429c7d7a37752d04a543904ca5ccb59f7e5d52bef8c56	docs/audit/blank-frames-root-cause.md
21480	fd0d91de59dfb8baeb21ee299095da18502cc1cd3b7e79404969bb401e2a305d	docs/audit/caption-formulation.md
35874	df840beece10975974f2cb8b016674a22aa7fa3373d1b4463ed7da0572003cfc	docs/audit/config-inert-fixed.md
24760	c30a83bf6ab9c2d2e076a0d51a7c9b0aff1159ba197c1f75ed4aeadeb1e88394	docs/audit/device-routing.md
28780	56a9273372bea66633230cde4ff6d6d602561ead8967b2d04c21de80f8cb0fdf	docs/audit/doc-vs-code.md
23113	f8a703776ca91095aa9d21ea8904527b7fced107eabfbd79b38f7a5e693ac0e9	docs/audit/flat-endpoint.md
24850	81650a2d57c4da79ceb7f979d4288a816eb0dbc08162f9b83c917f4976397f6f	docs/audit/launch-entry.md
25874	34fe789dc14d0ff25a0f946230c57b21e1cd3ed4d45adc34d21d1ee223fae38c	docs/audit/live-for-owner.md
21374	782cf94753ceb403537ac295866d1f4608f5267dde73c87aa2a4c0c09f2d11e8	docs/audit/load-churn.md
25605	a498611f3335fff6540a8755b4eedcda43367bf9a2867f346862172662bdd3f3	docs/audit/model-config.md
33713	7f51ba5db3be46748b7f03fb16c32bf644362388e570bb81b14bddcefc5c27d4	docs/audit/oracles.md
18906	b432ecb7e8568dec2801b5bb161937bb169d2e00aeb569a9ac997edc4ec6a26f	docs/audit/original-prompt-adjudication.md
20268	bea2875857163906b250dad1ab24ee86aa23a19746d27ad3ba88dd60a49eaa32	docs/audit/panel-gap.md
21314	a3938b74f70f872b5eb102a2c16dad9e470e17b4dd36420604e0c6dd6a04be5b	docs/audit/panel-v2.md
27726	cb024d472a3d37154f925c05afbe0d9d54d41111cb681c8f160379fe2515a967	docs/audit/run-cmd-gaps-fixed.md
23903	833af5612b62b7ae05b4b4931fedb185e92b39fe28ef31dbb81619fa916dd2d5	docs/audit/shell-bridge.md
19863	60174eec65c21ba33f6263a17a6841341da6123abbc5b67cfcc454afde61ae4e	docs/audit/speech-separation.md
16794	7a4134f1f662d2a7f6c9086f451a45f4da152200cf72600ba94f39ab1542a57f	docs/audit/tap-restart-loop.md
24188	902e4c105fa5c76f236ad581b01489626b089c689aebb50abf33195c54ba3d2b	docs/audit/window-visibility.md
32967	19fc9e20d9b627a0514564d83bf8824e9fbeda5545668389efbd3b256d041e67	docs/audit/windows-landmines.md
24061	b34d085d39c63f10349dcfa7aeda188da95c4bb70fe046d82328036051701fe3	docs/caption-formulation-20261006.md
30779	643680b2fb99e91db8dc766624ea39abbd1b2a12043f2e2ca8749a14a4ed5bfc	docs/full-audit-transcription-20261006.md
33198	2e04e4f01758403d29329115ffd3ec8c75bdad68c0318d2a9a492228f39f9017	docs/gpu-route-20261006.md
25012	bab243b2060fb1eb8608d4d5dd33e35a7adffc6123427895ac8ecb1377f20d6d	docs/int8-route-20261006.md
17962	9139dde68fc8e7b68d89ae8fd6a67e5ca021fe2b274af90f98d7899a63ac2026	docs/live-captions-20261006.md
11293	a1eb4ff6891dff9ffaab1f78260c68f7cdcdf274d627f0cb16107a5c842c9871	docs/model-specs/README.md
602	0592a224f30670e00f5e0f1f106f0171428b0abde0fd4cbc64237b02c2241502	docs/model-specs/original/fp16/config.json
2020	a1efe863e1057d4658bce8175c978020ac35a63a3c9a65ae899f324a32c8e4f6	docs/model-specs/original/fp16/languages.json
413	ab28d41eb87ce3922006edeb9c3fad4d5ce451f9a56a12d84f470f02a5ec157b	docs/model-specs/original/int4/audio_processor_config.json
1892	39568fbeebbe848696a1e2a01c7f33df000f72c29f2285509fd12442bda9571e	docs/model-specs/original/int4/genai_config.json
365	f41f943eeb1310a89dd58cf3e11e654a8ae1a788fceeb6cd1eacce3a6d081965	docs/model-specs/original/int4/model_config.json
183	ea4b35353f468fea11f436f837d9621a29b4ba9d1c73c1ed0aa5743f5a53919e	docs/model-specs/original/int4/tokenizer_config.json
3575	d8233985487ca07680dc22578e51cdee5fb58da61040bfe13109d60d66039b7d	docs/model-specs/original/int8/README.md
432	d4b1aa9f905bd0104958999e77f2a617842b849312830b334cb662494fdcfb28	docs/model-specs/original/int8/audio_processor_config.json
1962	0fdbafa35aca9db89c69f82cadb7b66a2e5260114fcc19d05e87d87dde15fb4f	docs/model-specs/original/int8/genai_config.json
403	6326fd6d3daf3dc78e46687ae5aed96038ae055bcba7cff6c66c93e9d4888200	docs/model-specs/original/int8/model_config.json
190	f041dd779a20f792ecc8aa154390a2145f8344e8dcf59970eced63be4311f630	docs/model-specs/original/int8/tokenizer_config.json
9557	c511fb298624326615895c2c2a45dc93987956f578503082ae01c45ac9793c6a	docs/model-specs/original/worker-README.md
39039	7a8e3ef25dc4f6785fe6c72414983534f94e6c5be4ef9491e2f395bed917350e	docs/oss-approaches-20261006.md
33253	fbd628eb274d19c1f15830d17a24a01b0c42f4a04122cc2d1741954f83ca1ecd	docs/stack-verification.md
16260	e3b5591700d7586f3969342fa60e5d6d003cd8130cbe45de06728898926b3b14	docs/webview-app-20261006.md
24712	7be955edb4eb4e6056f075d71b30f92fd536daa5dff00ae83dae0e17bd9c29aa	docs/webview-shell-20261006.md
25064	30b9168e8bdf079f15213319248b6abed4c2bebab896b82c560787f8240d8729	docs/worker-single-instance-20261006.md
6506	a291931ec06f536f8bdbeae732bf9bc30f6273a814f5e61772daeaef5b728c21	scripts/agc-gate.sh
14546	252e1e3406dfb16a656a58eb1873373de09a8562992f4d25c7faf449fa3beba1	worker/README.md
282378	cb5c48a2d1d6f7dedd0330f088a4cbe76de1a86e6a6109c06d255bb1ca2f7542	worker/assets/sample1.flac
80674	b2d9fa02c13368007184c84365fa0ebcaeed39ad7fe119c06e8458b3336c40c4	worker/assets/sample1_4s.flac
278018	4e82c7e879bce92c1d3bc99ddb7bdf681611bc251b6d244430e54fe44b86e75e	worker/assets/sample2.flac
14097	10dd72d1a9e8c071f948c0f344afe25c91e7f0f5df26959c3275e6f2832a3d67	worker/lang_prompt.py
27856	10a1e611a9d701ac222aaee1dd98fa3952fa8e423805fbbc4bbcb701ada68f6d	worker/wasapi_loopback.py
5217	502428913f67dd3b6e7853cb6b839d4b793e0ec4168d9b2166425b7659fd7634	_main/_app-drive.py
```

Total bytes added: **3,859,193** (~3.7 MiB) across 244 files. The manifest file itself was
`sha256`-checked by re-running the same hasher post-commit for the two fix files (§3).

---

## 4. Deliberately excluded — and why

Nothing was dropped silently. The rules live in `.gitignore` (see the diff in the commit) and
are spelled out here with the reason each class is NOT source:

| excluded | why |
|---|---|
| `worker/models/**` — **53 files, 3024.6 MB** | Downloaded model weights (`.onnx` headers were already ignored; the `.onnx.data` sidecars and `*.json` metadata were the untracked bulk). Sotto fetches them on first run; they are reproducible state, not source. The model's **own normative docs** are tracked separately under `docs/model-specs/`. |
| `worker/runs/**`, `_main/*.{log,log.stdout,err,out,jsonl,txt,mirror}`, `*.err`, `*.out`, `*.jsonl`, `*.stdout`, `*.mirror`, `*.pid` | **Records of a run.** `git clean` is allowed to take any of it. |
| `worker/_probe/`, `worker/_e2e/`, `worker/_sotto_worker_agcinert.py`, `_main/_probe/`, `app/electron/_hotreload/`, `app/electron/_single-instance/`, `app/electron/_dom-probe-*.json`, `app/webview/_flash-show-*.py`, `app/webview/_vis-live-*.py` | **Per-run scratch and negative-arm mutants.** Mutant copies (e.g. `_sotto_worker_agcinert.py`, `_flash-show-sotto_webview.py`) are deliberately-broken arms, not production modules. |
| `app/verify/rustc/out/` (`*.dll`, `*.exe`, `*.rlib`, `*.a`) | Build output of the Rust verification harness; the `.rs` sources ARE tracked. |
| `_main/*.png` (4 screenshots), `_main/*.wav`, `_main/*.flac`, `_main/*.orig-*` | Captured screenshots and audio scratch; the `.wav` class was already ignored. |
| **audio > 15 s (LIXO)** — `_main/vad-gap-sample.flac` (**33.905 s**), `_main/pt-br-sample.wav.orig-15.2s` (**15.192 s**) | Over the 15 s bar: excluded. Measured with `ffprobe`. **Included** instead: `worker/assets/sample1.flac` (13.690 s), `sample2.flac` (14.215 s), `sample1_4s.flac` (4.000 s) — all ≤ 15 s, so they are durable fixtures. |
| `app/node_modules/`, `app/dist/`, `*/target/`, `src-tauri/gen/`, `__pycache__/` | Machine cache / Electron runtime / Rust toolchain output. Already, or newly, ignored. |
| `history/` | The owner's own transcript data (`<date>/<HH>.md`), grows every run; was already added to `.gitignore` in the working tree and is kept there. |

---

## 5. Ground truth, and what this report does NOT claim

* The **working tree is a moving target**: lanes were writing while this audit ran. One code
  file (`_main/_app-drive.py`) appeared mid-audit and was added; one tracked file
  (`_main/panel-hidden-at-startup-oracle.py`) was modified by a sibling lane *after* the
  commit and shows as ` M`. That is the concurrency, not a defect in this commit.
* This commit does **not** re-run the two fixes' oracles. It records the code that already
  proved them (the proof is the lanes' own evidence, cited in the ticket and `AGENTS.md`).
* `git ls-files` = 267 is the count **at commit time**; later lanes adding files will raise it.
* 4 ignored entries that were already ignored were re-counted under the new rules — the
  before/after ignored tables in §1b are the same instrument (`git status --ignored`) run at
  two moments, not two different definitions.

---

## 6. GATE-CHANGE REQUEST

A hole this audit found is in a **gate**, so it is returned as a request, not fixed here.

- gate: `I:/!manager/scripts/self-audit-lint.sh` — `bash I:/!manager/scripts/self-audit-lint.sh <receipt-or-dir>`
- invoker: the lane-completion path that already runs this lint over a `status: done` receipt (its rules (c)/(d) are read by every closing lane)
- hole: **no rule checks that a receipt's own claimed fix artifact is TRACKED by git.** A lane can prove a fix green, stamp the receipt `done`, and leave the file untracked. Measured this session: `worker/wasapi_loopback.py` and `app/webview/sotto_webview.py` were BOTH untracked while their proofs were green, `git diff` was empty for them, and `git ls-files` counted **23** files in a repo whose app is dozens. This receipt closes the instance; the gate does not exist, so the next lane repeats it.
- change: for a `done`-stamped receipt that names a repo-relative fix path, require `git -C <repo> ls-files --error-unmatch <path>` to exit 0; otherwise emit `GATE-FIX-UNTRACKED`.
- nonvacuity: the RED input is the pre-commit state of `worker/wasapi_loopback.py` in `H:/sotto` — `git -C H:/sotto ls-files --error-unmatch worker/wasapi_loopback.py` exits non-zero before `5ffeefc` and 0 after. `--selftest` must carry both arms.
- blast: `I:/!manager/scripts/self-audit-lint.sh` only. Receipts naming a NON-repo artifact (paths under `I:/!manager/runs`, `G:/…`) must be out of scope, or the rule turns existing green receipts red.
- revert: `git -C I:/!manager checkout -- scripts/self-audit-lint.sh`
- prepared_by / merged_by: `TrackedDurability`; Main

---

## SELF-AUDIT

* **protocolos em falta** — I did not find a repo protocol that says which untracked files are
  "production"; I *invented* the code-vs-generated boundary and had to document it so it can
  be argued with. A `CONTRIBUTING`-style rule ("what enters git") was missing from `AGENTS.md`;
  adding one would remove the judgement this audit had to supply.
* **verificacao adicional** — Worth a cheap extra check: after the commit, run
  `git status --porcelain -uall` on a **second** pass minutes later to catch late-arriving
  code files (I did one pass; a live lane already produced a new file). Cost: ~1 s.
* **checkboxes novas** — MECHANICAL new step for any durability audit:
  `git check-ignore --stdin < <(added-paths)` MUST print nothing **before** `git add` — this
  is exactly the drift that bit here (4 screenshots + 1 oversized .wav were classified KEEP by
  the classifier and GEN by `.gitignore`; the check surfaced all 5 before the commit).
* **review por outro subagente** — `sim-com-escopo "conferir a fronteira codigo/gerado do
  _main/ (147 ficheiros): algum e' run output que entrou, ou codigo que ficou de fora?"`
* **gate-doubt** —
  * verde-de-verdade: the `git grep -c ... HEAD` greps are REAL (they read the commit object,
    and the HEAD~1 negative control is rc=1 with no output — the run that proves it is the
    negative control, not the positive one). `ls-files` 267 is real (read after commit). Caveat
    I must name: `sha256sum` was recomputed **after** the commit, so for the two fix files the
    "before" value comes from the pre-add manifest — the two agree, but the comparator is my
    own manifest, not git's blob hash.
  * falta-no-gate: **nothing in the repo verifies that a fix lane's artifact is tracked at
    all.** A future change — a lane writing `worker/new_module.py` and proving it green — walks
    straight past every gate and lands untracked again, exactly as ticket `2051631332c989…`
    describes. The gate does not exist; that is the hole.
  * gate-melhor: add a mechanical check run after any lane claims a fix:
    `git ls-files --error-unmatch <the file the lane names> >/dev/null || echo UNTRACKED-FIX`
    — with the RED input being the current pre-commit state of `worker/wasapi_loopback.py`
    (which returns `UNTRACKED-FIX` before `5ffeefc` and silence after).
* **confianca** — `alta` on "the 244 files are in `5ffeefc` and the two fixes are provable in
  it" (git objects, cited greps). `media` on "the code-vs-generated boundary is the right one"
  (it is defensible and documented, but it is a judgement; a reviewer could reasonably move
  `_main/*.json` inputs or the `_probe/` dirs).
* **nao verificado** — (a) the two fixes' *runtime* behaviour (not re-run; the lanes' evidence
  is cited, not reproduced); (b) that every one of the 658 excluded files is truly
  reproducible (assumed from `.gitignore` semantics, not re-derived); (c) `worker/assets/*.flac`
  content correctness (only duration measured); (d) the remote — nothing was pushed.

---

## CACHE/PRICE

```
## CACHE/PRICE
- task/agent: TrackedDurability
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\TrackedDurability.jsonl
- cache: read=5173888 write=0 hit=96.6278% (cache-read / input+cache-read); universe: 43 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\TrackedDurability.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: opencode-go-3/deepseek-flash: calls=39 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=4 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-3/deepseek-flash $0.00000000; opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 43 of 43 matched usage rows
- when-failed: break_items=3; WHEN=2026-10-06T09:55:08.426000+00:00 | break_items=2; WHEN=2026-10-06T09:57:15.658000+00:00 (state=RESOLVED-BREAKS-OMP; population: 2 of 116257 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'TrackedDurability']; window: 2026-10-06T09:55:08.426000+00:00..2026-10-06T09:57:15.658000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a110a3-42e6-742c-91fd-f560279873fa provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791280508426 | session_id=01a110a3-42e6-742c-91fd-f560279873fa provider=deepseek-flash model=deepseek-flash item_index=55; turn_id=1791280635658 (state=RESOLVED-BREAKS-OMP; population: 2 of 116257 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'TrackedDurability']; window: 2026-10-06T09:55:08.426000+00:00..2026-10-06T09:57:15.658000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- report generated_at: 2026-10-06T10:00:01.940519+00:00
- usage rows: 43
- model + route: opencode-go-3/deepseek-flash, opencode-zen/space-bunny-free
- input tokens: 180562
- output tokens: 43165
- cache-read tokens: 5173888
- cache-write tokens: 0
- hit ratio: 96.6278% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- price partition: price partition by token class and model: opencode-go-3/deepseek-flash: calls=39 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=4 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-3/deepseek-flash $0.00000000; opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 43 of 43 matched usage rows
- prefix breaks: 5 (state=RESOLVED-BREAKS-OMP; population: 2 of 116257 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'TrackedDurability']; window: 2026-10-06T09:55:08.426000+00:00..2026-10-06T09:57:15.658000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- WHEN / WHERE failed:
  - break_items=3; WHEN=2026-10-06T09:55:08.426000+00:00; WHERE session_id=01a110a3-42e6-742c-91fd-f560279873fa provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791280508426
  - break_items=2; WHEN=2026-10-06T09:57:15.658000+00:00; WHERE session_id=01a110a3-42e6-742c-91fd-f560279873fa provider=deepseek-flash model=deepseek-flash item_index=55; turn_id=1791280635658
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```
