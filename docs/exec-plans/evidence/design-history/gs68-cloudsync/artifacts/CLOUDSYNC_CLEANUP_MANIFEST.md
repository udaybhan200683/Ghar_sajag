# CloudSync Cleanup Manifest

Date: 2026-10-16 UTC
Status: **CONTENT RECONCILIATION COMPLETE; CLEANUP IN PROGRESS**

## Original refs and checkpoints

| Ref | Original SHA | Remote SHA before cleanup |
|---|---|---|
| `integration/gs68-cloudsync-into-r1` | `ad6df017a7f7bf586a84beb5b54cea2ad74d5962` | `ad6df017a7f7bf586a84beb5b54cea2ad74d5962` |
| `feature/r1-gs68-gs109-mtls-feasibility` | `e740f99d094b4a0ef7397f0a506e8f089fb5d261` | `e740f99d094b4a0ef7397f0a506e8f089fb5d261` |

Canonical checkpoint at inspection: `/home/udaybhan/projects/Ghar_sajag_r1`,
`feature/r1-commercial-baseline`, HEAD `9d16556bbfe741bd4aa59c3df88a0ba0addca3c8`.
Context preflight PASS from the canonical worktree. The canonical working tree
contains active GS-40 modifications and evidence; cleanup did not write there.

## Resolution of the 29-path claim

The earlier 49-path source reconciliation is reused: 30 paths were identical and
19 were superseded. Rechecking the 29 later GS-68 diagnostic/HIL paths resolves
the blocker: **no missing implementation paths**. Every path is tracked on both
branches. Actual worktree bytes were hashed; worktree tracked files were clean,
and the recorded Git blob IDs match those bytes. Twenty paths have identical
Git blobs. Nine are different revisions, but the canonical versions retain the
GS-68 diagnostic/HIL functionality and include later integration (GS-114/GS-40
profile, validation, or observer changes). Evidence is noted per row below.

| # | Path | Old blob | Canonical blob | Old SHA-256 | Canonical SHA-256 | Classification / evidence |
|---:|---|---|---|---|---|---|
| 1 | `code/Makefile` | `fd9d2767aab36ffb401f9960680d1a7e02878ff1` | `d220495b4cf5841bb66b87b8cd7085701aef380b` | `2a0edcf01d56b69ab98bdf1239a6aaf14a12d81a4d7750ea9a10259653cac978` | `f271454b134a2da5cc8c231b3042bce0dfee84010d9734966a00c1a54291b80c` | PRESENT, newer canonical revision: GS-68 protocol/build/HIL targets remain; canonical adds current GS-114/GS-40 targets and test composition. |
| 2 | `code/firmware/common/shared/include/gs/gs68_diag_protocol.hpp` | `562972721e3ca4d05264be72b4ee3dc3067c6324` | `562972721e3ca4d05264be72b4ee3dc3067c6324` | `3455d52a5e34638b3c859da7636be7c5f9e621774a352d336b60a7f2c3b98dcf` | `3455d52a5e34638b3c859da7636be7c5f9e621774a352d336b60a7f2c3b98dcf` | IDENTICAL |
| 3 | `code/firmware/hub/target/esp32s3/idf/CMakeLists.txt` | `b2393974b727f0bf74fb27b36030730bf1c01401` | `ae2d23e5b53213d0fe41be0710d91e64f9169a68` | `15ed0b12fdf8243c03561fc4562ae9fca560da70cf61fa8328e6a6e53b1da1bc` | `5eafa786b1df226a844e26e2dbd1c7c465d11f252e7cb6a7885ce65f0ce7751e` | PRESENT, newer canonical revision: GS68_CLOUDSYNC_DIAGNOSTIC_ONLY and diagnostic component selection remain; canonical adds ACK-hold and signed-FOTA profile guards. |
| 4 | `code/firmware/hub/target/esp32s3/idf/gs68_cloudsync_diagnostic/CMakeLists.txt` | `de4a39a1d32b490aa91ecf583f794fa93130f6eb` | `de4a39a1d32b490aa91ecf583f794fa93130f6eb` | `aece9647b22806f26b746a1fec2e53832cd8d528e9e7e4e82798db679ad3a786` | `aece9647b22806f26b746a1fec2e53832cd8d528e9e7e4e82798db679ad3a786` | IDENTICAL |
| 5 | `code/firmware/hub/target/esp32s3/idf/gs68_cloudsync_diagnostic/app_main.cpp` | `991ef9e78c9e3d5a7f8ea186af148aa19a0a8838` | `991ef9e78c9e3d5a7f8ea186af148aa19a0a8838` | `92c49fe6cd8a6b8cbbef1a02bc06231f0adc834c09043c788087d9a339e9b9e5` | `92c49fe6cd8a6b8cbbef1a02bc06231f0adc834c09043c788087d9a339e9b9e5` | IDENTICAL |
| 6 | `code/firmware/hub/target/esp32s3/idf/sdkconfig.gs68_cloudsync_hil.defaults` | `c1f1b86a5e2b9af976d27b23a549f4f09d7bffcc` | `c1f1b86a5e2b9af976d27b23a549f4f09d7bffcc` | `00a8aefb20a6b67d34c6631128031d112ff091d3f255b21a7280db45a356b1d0` | `00a8aefb20a6b67d34c6631128031d112ff091d3f255b21a7280db45a356b1d0` | IDENTICAL |
| 7 | `code/firmware/node/target/esp32c3/gs68_node_observer.cpp` | `a9fd8fc7ae3b411255d2942b126be2ddd78cf8bd` | `a9fd8fc7ae3b411255d2942b126be2ddd78cf8bd` | `a7c46a0953b811937dfd285cb0b26fbf59bd1c41e60f740ead4e4dc27298b404` | `a7c46a0953b811937dfd285cb0b26fbf59bd1c41e60f740ead4e4dc27298b404` | IDENTICAL |
| 8 | `code/firmware/node/target/esp32c3/gs68_node_observer.hpp` | `43fbcb7ade1678cf4e1f5530645513bde2f6e2d9` | `43fbcb7ade1678cf4e1f5530645513bde2f6e2d9` | `eff330dff2286ad1241a6e807da305cc43b73b8d87e68962daa6f1e1f48d7554` | `eff330dff2286ad1241a6e807da305cc43b73b8d87e68962daa6f1e1f48d7554` | IDENTICAL |
| 9 | `code/firmware/node/target/esp32c3/idf/CMakeLists.txt` | `ec678ceb7d4a78fc9e8e17cd013a94ec73530578` | `4459c882b2656d0cd3226ce6c7304859c8cf2a35` | `17b54d148fac19100b501dc7ad2b8ea94a37db8f7b4d2f8de78ef1e5ca607ca9` | `ef63fae8da7e65fa9064cc3109baa8a892b3f2ada5d272af547c61b72d446c9a` | PRESENT, newer canonical revision: GS_GS68_NODE_OBSERVER and its incompatible-HIL guard remain; canonical adds C8/FOTA profile gates. |
| 10 | `code/firmware/node/target/esp32c3/idf/main/CMakeLists.txt` | `3c5f0629ea6532bef04a1614a4809fb53d4f024a` | `1593d56e95bfb5f9e4f6f4d41b267c015eca4c9d` | `72606be634f17e19e05f3e0e7e6a1ab6f2d20dcdd72e8328ac900d022857fc3e` | `c2eb25ed121fd4e1b534465d5801c4aa71eb479daf1e88fb2042d6860ff70d59` | PRESENT, newer canonical revision: observer source is conditionally compiled and profile definitions remain; canonical adds C8 trace/security definitions. |
| 11 | `code/firmware/node/target/esp32c3/idf/main/app_main.cpp` | `3e76af3e9b28a87db95bfd7ea21bf4bb8e37898e` | `64149d55f6bb3cef98840c28da558544bb644686` | `354a25054f1ab7ffd376c34cb0a842b354d9b4c3605fda2b7ea66c35d5e88d67` | `f6d40550150018881cea2efaa2533e47e38148274e827e119f5a59e05f3e4b71` | PRESENT, newer canonical revision: GS-68 observer include and start_node_observer call remain; canonical adds test-only fixture-security reporting. |
| 12 | `code/firmware/node/target/esp32c3/idf/sdkconfig.gs68_node_observer.defaults` | `550ca784b1b52adb4007af1909ca21e9415fd983` | `550ca784b1b52adb4007af1909ca21e9415fd983` | `0679dfa2078d757a3990f0766dea3c363c0a7e5ef5625d02994b13cf5575e664` | `0679dfa2078d757a3990f0766dea3c363c0a7e5ef5625d02994b13cf5575e664` | IDENTICAL |
| 13 | `code/firmware/node/target/esp32c3/node_runtime_adapter.cpp` | `66c623928a3a0954454d51e12ce44b90d0ed4516` | `7e63faa7fa6e1092d84677f2937d3634bd59ce23` | `1ab5202808983308b23e6c92cdfd8afd205bf9cccf992d3db41425a1ba520dce` | `96192e7e3ec236793b8da30141096de493759418286963fa1772033f73b6a254` | PRESENT, newer canonical revision: GS-68 ACK/event/send/runtime observer publication calls remain; canonical adds bounded GS-114 ACK/sleep trace and qualified-board guards. |
| 14 | `code/scripts/build_gs68_cloudsync_c3_diagnostic.py` | `ba7e6358ecfa20a642a6ff0afc23c6a01cf1ab63` | `ba7e6358ecfa20a642a6ff0afc23c6a01cf1ab63` | `8bb524c43d527f4082e48a05bc1fb4fbdb5d033536dd19cae99b4aa572d3f054` | `8bb524c43d527f4082e48a05bc1fb4fbdb5d033536dd19cae99b4aa572d3f054` | IDENTICAL |
| 15 | `code/scripts/build_gs68_cloudsync_diagnostic.py` | `8261fb937f7584bf898cdd326f2d23219d2bae7f` | `8261fb937f7584bf898cdd326f2d23219d2bae7f` | `f5718daec4406e79f462d4e2b11968e57d351a1fdf8e63e693d7c531883a09ea` | `f5718daec4406e79f462d4e2b11968e57d351a1fdf8e63e693d7c531883a09ea` | IDENTICAL |
| 16 | `code/scripts/test_gs68_diag_protocol_host.py` | `7fd49807124660cf758d788a7a102bc91c4aea37` | `7fd49807124660cf758d788a7a102bc91c4aea37` | `ec01450fd8a97f146a6c7b3be83b090c62d399466eb0c3c66b77c9d7101c4bf8` | `ec01450fd8a97f146a6c7b3be83b090c62d399466eb0c3c66b77c9d7101c4bf8` | IDENTICAL |
| 17 | `code/tests/cpp/gs68_diag_protocol_test.cpp` | `54c86fdf4e97a6f2f98383e53fb103d1762271db` | `54c86fdf4e97a6f2f98383e53fb103d1762271db` | `3330af04509ceccf7ba4bc7dea5ac034f23181d3077345f1dea558c165951d18` | `3330af04509ceccf7ba4bc7dea5ac034f23181d3077345f1dea558c165951d18` | IDENTICAL |
| 18 | `code/tests/engineering_dashboard/test_registration.py` | `743aa59dbb71362a192dcbd26b0e42bf33a882fd` | `e567b7eccc15d552e154ee1113ea7874e0f1618e` | `8c9f2a30b4eb065411645bc5fed87cea41c0fb0ba7a48945ae4a566e01b8da43` | `f41b4d799cf6b29230ad38d4b1838d2483e3b972c06c9a4aede1923838fa9340` | PRESENT, newer canonical revision: all three CloudSync mTLS registry stages remain in the preservation assertion; canonical expects additional GS-114/GS-40 stages. |
| 19 | `code/tests/python/test_component_gate.py` | `665b645736ae07f342fd760de388729585dc2231` | `3b11c1adcd2729281a833df157918f2c7d4b456b` | `a642ca5c8287e3347d1b23527e196b8b5257dd612a257454e451d9fdf01a0add` | `861e0e3a778da5f63244f7bc2aba42966faa6efe472126d058875fe78003a408` | PRESENT, newer canonical revision: CloudSync security stage checks remain and are updated for current 13+5 test output after NodeHealth coverage. |
| 20 | `code/tools/hil/gs68_capture.py` | `8fc106587cb35de59f08414f2b38ced393ee3f04` | `8fc106587cb35de59f08414f2b38ced393ee3f04` | `c30ad7dbf1a527158f3d68366a85fe97672274fc23b8b5217837192dc4be0762` | `c30ad7dbf1a527158f3d68366a85fe97672274fc23b8b5217837192dc4be0762` | IDENTICAL |
| 21 | `code/tools/hil/gs68_cloudsync_cases.json` | `0a71b4564dda470c56631d995382849243778223` | `0a71b4564dda470c56631d995382849243778223` | `74814b0b7bc8718898f6e016a96baeac7a4e28f515c21e3599ad88dc01af8f67` | `74814b0b7bc8718898f6e016a96baeac7a4e28f515c21e3599ad88dc01af8f67` | IDENTICAL |
| 22 | `code/tools/hil/gs68_cloudsync_hil.py` | `2f7cd2cb522905dfe5b44dcb89ec49d6cb54c9f9` | `2f7cd2cb522905dfe5b44dcb89ec49d6cb54c9f9` | `2c1221b1639bb809af4ae57d29899ee21157d200062b5e6d025cee4200e69fdd` | `2c1221b1639bb809af4ae57d29899ee21157d200062b5e6d025cee4200e69fdd` | IDENTICAL |
| 23 | `code/tools/hil/gs68_spare_fixture.template.json` | `6336cc3bcbbc8ee3a7b938b6a76b83f9e1700500` | `6336cc3bcbbc8ee3a7b938b6a76b83f9e1700500` | `4b1497a5bf4edfb4073c3794d32c4ff40ec2b319d865fd2d097dde23d535b5c7` | `4b1497a5bf4edfb4073c3794d32c4ff40ec2b319d865fd2d097dde23d535b5c7` | IDENTICAL |
| 24 | `code/tools/hil/gs68_test_backend.py` | `8a8d605737e735524b049205ad5fcf810c8a15c5` | `8a8d605737e735524b049205ad5fcf810c8a15c5` | `cb0a4215ccd92855982032be8a5427e85d39b866650d0b565c9703fdedce9583` | `cb0a4215ccd92855982032be8a5427e85d39b866650d0b565c9703fdedce9583` | IDENTICAL |
| 25 | `code/tools/hil/gs68_test_backend.template.json` | `779b29b80facab690b702bef73786a9cbb0c5082` | `779b29b80facab690b702bef73786a9cbb0c5082` | `fb7b7b7f7ad553d62076297c2af3ff7f7cc53f62e860c9a43394c2b35b7869a4` | `fb7b7b7f7ad553d62076297c2af3ff7f7cc53f62e860c9a43394c2b35b7869a4` | IDENTICAL |
| 26 | `code/tools/hil/test_gs68_cloudsync_runners.py` | `762220abd6374acc1e5cf9cc3b094ffa844575e2` | `762220abd6374acc1e5cf9cc3b094ffa844575e2` | `aa3d6849024e81a9d2fb756d83ab97478fd2193c742b625ae5031a0b51c8c056` | `aa3d6849024e81a9d2fb756d83ab97478fd2193c742b625ae5031a0b51c8c056` | IDENTICAL |
| 27 | `code/tools/hil/test_gs68_physical_runners.py` | `80ba6a5aa4ebbc6045ea417b2913e112a65104f4` | `80ba6a5aa4ebbc6045ea417b2913e112a65104f4` | `96a7cc2e2aa448093b0d7a41aa2722a51cab2f5bbdd8100b55aaf0c88b09518f` | `96a7cc2e2aa448093b0d7a41aa2722a51cab2f5bbdd8100b55aaf0c88b09518f` | IDENTICAL |
| 28 | `code/validation/component_gate.py` | `8605ae11671bf2770e6a0aee4f38641d15139c7a` | `8605ae11671bf2770e6a0aee4f38641d15139c7a` | `ec16646a1fc9ceecab4ff854949ca23927165e99a9ab452679a90bfa9f0cd463` | `ec16646a1fc9ceecab4ff854949ca23927165e99a9ab452679a90bfa9f0cd463` | IDENTICAL |
| 29 | `code/validation/suites.json` | `c1f2720df4960919967ef5f49cfdb18ed543a74e` | `abf389c7f6b04675c102a59aa249aaab65b76574` | `8b26379d495aa31f49d97fd366b0342c8a1de3fecbed66f827972d83756e5151` | `5bc1a94c6613cf3ee9cc513f332776352c2055120b7502a6ded16cde6b15ed7c` | PRESENT, newer canonical revision: GS-68 HIL and diagnostic input paths remain registered; canonical adds later GS-114/GS-40 validation stages. |

The nine different-revision paths are present in canonical, and their GS-68
specific call sites, target options, build targets and validation inputs were
checked in actual source. They do not represent missing implementations. The
source-integration blocker is **CLOSED**.

### Additional mTLS-file cross-check

These two files were named in the fresh GitHub comparison; they are outside the
29-path post-audit list, but were also compared by actual content:

| Path | Old blob | Canonical blob | Old SHA-256 | Canonical SHA-256 | Classification |
|---|---|---|---|---|---|
| `code/tests/support/cloudsync_mtls_local.py` | `b8c04ca0d37ce963ca85286de10b1a8e29c6c57d` | `c91fb6d6828c7fbe84952eef201c3d6f74fdd734` | `a7d029799de8acd3e0cc19d71c72759f5081d90bd56787169cf68736c7b1fa0e` | `252040e3d3687badcbd6182d18f1730c3dc409afe12ff88bc9009aacae66c003` | PRESENT, newer canonical revision |
| `code/tests/support/test_cloudsync_security.py` | `1ae400d362af2504a860cf55027b00b726d8b092` | `89de4850d237c222edd0a0e8e78a27aadc86d4a4` | `7acd05dfd5cfab8b4459bc9bc1807c01908726b78acc8a4bec616115776d7a2d` | `723fe754f69883248786ba4720523df7c1da7ccd434b55058740dd8c56169b67` | PRESENT, newer canonical revision |

`cloudsync_mtls_local.py` now obtains a typed `TimeReadiness` and calls
`authorize_cloud_tls_context`; the old helper called
`authorize_cloud_tls_peer`. `test_cloudsync_security.py` retains the earlier
security cases and adds `VerifiedHubContext`, Home binding, trusted-time checks,
and test 013. These are newer canonical revisions, not absent implementation.

## Obsolete worktree inventory

The obsolete worktree had no tracked modifications and no process cwd/open file
under its path at the ownership check. The only untracked path was
`code/firmware/hub/target/esp32s3/idf/managed_components/`, downloaded ESP-IDF
LittleFS dependency source (not project implementation). Ignored paths were
build outputs, dependency installations, test evidence/logs and Python caches.
No unique untracked implementation was found. All are within the explicitly
approved obsolete worktree removal scope.

## Documents preserved

The following unique design/feasibility report and this manifest are present in
`/home/udaybhan/projects/_artifacts/gs68_cloudsync_design_docs/`:

- `GS68_GS109_GS148_MTLS_SOFTWARE_FEASIBILITY_20261016.md`
- `CLOUDSYNC_CLEANUP_MANIFEST.md`

The feasibility report was preserved with its original bytes. Duplicate or
superseded architecture/decision documents were skipped; the canonical
GS-148 architecture decision, storage-sync architecture and decision log
contain the later material. No unique decision `.txt` document was found.
No source, build, binary, dependency, cache or log archive was created. Existing
artifact files were not changed; only this manifest was updated.

## Cleanup execution

- Integration branch removal: PENDING
- Feasibility branch removal: PENDING
- Obsolete worktree removal: PENDING
- Generated builds/dependencies/caches/logs: PENDING with worktree removal
- Canonical GS-40 working files: untouched; all operations against canonical
  have been read-only. No merge, checkout, reset, restore, stage, commit or clean
  was performed there.
