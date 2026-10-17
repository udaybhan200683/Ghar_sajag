# Integration and parallel-ownership handoff — 2026-10-17

OWNER: GS-157 caregiver Internet call and proposed separate Android caregiver app ticket; GS-154 S3/audio prerequisites; GS-143 production caregiver trust; GS-40/68/109/148 upstream live tasks.

REQUIREMENT_STATUS: New approved Internet-first product direction recorded in GS-153/154/157/162; no inbound PSTN. Previous PSTN-first text is historical.

STARTING_SOURCE: Remote `feature/r1-commercial-baseline` HEAD `29890b36a753ffdc46d7be9399a4a6cbed97d727` inspected 2026-10-17. This source may become stale. Source docs require context preflight before canonical substantive editing; none was possible without the owner's local WSL worktree. DO NOT auto-create source mutations, do NOT merge current GS-40 changes or compete for canonical writer.

OUT_OF_SCOPE: production Hub WebRTC audio, live FCM setup, Android signed APK, signing keys, test eFuse, protected hardware, unsafe production actor headers, LTE/2G/4G hardware, PSTN, iOS app, full release.

NEAREST SAFE WORK: make isolated Android Gradle build feasible in separate approved branch/worktree; integrate verified session + canonical actor and Home membership, source-to-device registration; implement ICE/TURN allocator, install FCM only after policy suitability review; WebRTC app-to-browser demo and Android devices; Hub offerer after GS-40 merge; focused actual E2E with real Hub and caregiver phone; record all test evidence. Product hardening remains required before shipping.

RISK: FCM provider acceptance does not equal notification display or answered call. FCM terms exclude life-critical use; use independent qualified channel for true emergency workflows. CURRENT VERDICT: TESTED ISOLATED SIGNALING CONTRACT, NOT END_TO_END_PRODUCT_PASS.
