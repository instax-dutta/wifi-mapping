# Gates: ESP8266 WiFi radio mapping (stage P0/P1)

OWNS: docs/**, firmware/**, host/**, tools/**, data/derived/**, README.md, GATES.md

Scope: one ESP8266 senses WiFi RSSI (ambient scan + single-target promiscuous sniff), the host captures it to JSONL, and the pipeline produces a fingerprint map with an honest localization error plus a wall-count (k) sketch - proven both on the real board and on synthetic data.

- [x] G0: this ledger's oracles can fail honestly
  CHECK: node /Users/saiduttaabhishekdash/.claude/skills/unlazy/scripts/gate-lint.mjs GATES.md
  EXPECT: LINT OK
  EVIDENCE: automatic-evidence=v1; definition-sha256=725a8be4dec23edaed4e222f92e5b1b4af5078dff68ec0025e941d5e49a23d56; exit=0; EXPECT=matched; output-sha256=07de1a3fdbb119780824944843dcfc7da4b1349f87411f5d2df255b3caa7c614; output-bytes=150; shell=/bin/sh; cwd=/Users/saiduttaabhishekdash/wifi-mapping; path=b93c3fbfaca3/30 entries

- [x] G1: the documented hardware matches the live board
  CHECK: node tools/checks/c1-hardware.mjs
  EXPECT: hardware doc verified
  EVIDENCE: automatic-evidence=v1; definition-sha256=aa61c9065938a658d3e57989aa170c2cd67676a4dc04e960ed5adbb82cceed99; exit=0; EXPECT=matched; output-sha256=dd87ca1fbe8737ee0a83f3d28e837dd2cc9afa7739461fc800c5c8c016157d55; output-bytes=22; shell=/bin/sh; cwd=/Users/saiduttaabhishekdash/wifi-mapping; path=b93c3fbfaca3/30 entries

- [x] G2: the DOX tree exists and is indexed
  CHECK: node tools/checks/c2-dox.mjs
  EXPECT: dox tree verified
  EVIDENCE: automatic-evidence=v1; definition-sha256=c5d3cb9d08db59d6bccc548a38f0a1197c9a2b4e397460a61d28ddf28a9969a8; exit=0; EXPECT=matched; output-sha256=d10757e7ececf0423d6dfcbea2faa002a1279427e3d6eaf6df730b4c29f9443b; output-bytes=18; shell=/bin/sh; cwd=/Users/saiduttaabhishekdash/wifi-mapping; path=b93c3fbfaca3/30 entries

- [x] G3: the firmware compiles for the target board
  CHECK: node tools/checks/c3-compile.mjs
  EXPECT: firmware compiled
  EVIDENCE: automatic-evidence=v1; definition-sha256=59372749c20df1d6c81044e261c2d581fbcb1861de80fac158f0b185c318e42c; exit=0; EXPECT=matched; output-sha256=5643b260d475f206d6ae62ad605509092e4528666892b223a14f910c78d2be28; output-bytes=18; shell=/bin/sh; cwd=/Users/saiduttaabhishekdash/wifi-mapping; path=b93c3fbfaca3/30 entries

- [x] G4: the firmware flashes and returns real scans over serial
  CHECK: node tools/checks/c4-hwscan.mjs
  EXPECT: hardware scan verified
  EVIDENCE: automatic-evidence=v1; definition-sha256=443360c2dcd01afea08b19496bf23aff042f0f299c822a4b4ae91b0f31544eac; exit=0; EXPECT=matched; output-sha256=b3cbfdb8650a14bdaf496aaf2cb8db194751d4ee02b7b5781885a6f53611a6e7; output-bytes=38; shell=/bin/sh; cwd=/Users/saiduttaabhishekdash/wifi-mapping; path=b93c3fbfaca3/30 entries

- [x] G5: the host package tests pass
  CHECK: node tools/checks/c5-tests.mjs
  EXPECT: tests passed
  EVIDENCE: automatic-evidence=v1; definition-sha256=7cc0525d197dac47f9025abc57efa538ce01a5b888add02162a66a8ffb0a0453; exit=0; EXPECT=matched; output-sha256=fe57e664bcff3dea7ec404334cbf77b833fa2f27841075e943dd5da8e5ee98f8; output-bytes=13; shell=/bin/sh; cwd=/Users/saiduttaabhishekdash/wifi-mapping; path=b93c3fbfaca3/30 entries

- [x] G6: the analysis pipeline maps and localizes synthetic data
  CHECK: node tools/checks/c6-analyze.mjs
  EXPECT: analysis pipeline verified
  EVIDENCE: automatic-evidence=v1; definition-sha256=64772e608d219788b47be2c3cdf15d98f740feceedd899684a6ef713210b8a9e; exit=0; EXPECT=matched; output-sha256=5063cf5191088924ae480c1fd39eddfaf5aaa3264291982b536777d6c0f69847; output-bytes=48; shell=/bin/sh; cwd=/Users/saiduttaabhishekdash/wifi-mapping; path=b93c3fbfaca3/30 entries

- [x] G7: promiscuous sniffing yields per-packet RSSI from one AP
  CHECK: node tools/checks/c7-sniff.mjs
  EXPECT: sniffer verified
  EVIDENCE: automatic-evidence=v1; definition-sha256=15fe84309f8375b0decf7c728d3d0c219c8e637a896c8db1cfa44ea1798ce56f; exit=0; EXPECT=matched; output-sha256=c2f9f76f4785b47b39bb96a7522125b2b699c57718fada52bcb03c7ae932b832; output-bytes=53; shell=/bin/sh; cwd=/Users/saiduttaabhishekdash/wifi-mapping; path=b93c3fbfaca3/30 entries

- [x] G8: the prior-art survey and architecture decision were reviewed as a whole
  EVIDENCE: Reviewed 2026-10-09. docs/research.md covers 12 works/projects with sources; docs/architecture.md's protocol matches host/wifi_map/records.py and firmware/wifi_mapper.ino; simulate.py emits the same wire format; no-CSI and single-radio constraints are stated and honored. Real board run agrees: 1 ambient AP, sniff 40 pk/8 s.

- [x] G9: the sensor can see and sniff the Board B reference beacon
  CHECK: node tools/checks/c8-refbeacon.mjs
  EXPECT: reference beacon verified
  EVIDENCE: automatic-evidence=v1; definition-sha256=b1f8dfce606f52d99204c745a78d8cbabddee8f2065c5e59c4bd4063bb715246; exit=0; EXPECT=matched; output-sha256=bbfbdcecb3dc0c6ffe14a7ae9d23bb023f16ac4f470519ecd513820820d6ca28; output-bytes=69; shell=/bin/sh; cwd=/Users/saiduttaabhishekdash/wifi-mapping; path=b93c3fbfaca3/30 entries

