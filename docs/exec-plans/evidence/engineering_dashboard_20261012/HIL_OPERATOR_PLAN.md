# Proposed GS-125 HIL observation plan — NOT EXECUTED

Owner GS-125 with GS-114/GS-130. Status BLOCKED_GS114_NO_GO. Reuse existing
`validation-board-hil`, `validation-motion-hil`, physical catalogue and GS-114
hardware profile. No additional acquisition runner is created. This plan is a
review artifact; it authorizes no hardware access and supplies no approval phrase.

## Prerequisites for a later explicit approval

Identify a disposable C3 + S3 N16R8 fixture, board serials, actual flash/PSRAM,
AM312 optical wiring/pinout and the exact test operations. Supply approved image
paths/hashes, firmware source/configuration fingerprint and running-image proof
for both boards. Confirm existing Node pending events and storage preserve
their state. A candidate built image is not running-image evidence.

GS-114 must resolve the C3 observation/reset risk and S3 replay-fence failure.
Demonstrate a reset-safe capture adapter/method without opening the protected
fixture here. DTR/RTS low alone is insufficient proof. Confirm backend/technician
authorization and the source-matched dashboard subset. Use unique output
directories; never replace historical captures. User approval must name the
fixture, observation/stimulus plan and operations; the runner's typed phrase is
a second guard, not a substitute. No outage, fault injection, reset, power-cycle,
erase or provisioning is part of a passive observation approval.

## Existing runner capability and gaps

The board runner accepts `--observe`, explicit C3/S3 stable ports, image paths,
bounded duration and unique report path. Its default records NOT_RUN and exits 3
without opening ports. It recognizes eight HIL-A cases; passive capture cannot
qualify outage/replay stimuli. Running-image hash/configuration proof still needs
independent evidence. Some existing formatter logs lack the exact authentication
or retirement markers expected by the observer: absence is BLOCKED, never a
reason to weaken the parser or mark PASS. Node-local and physical-qualified key
representations require verified identity binding, not naïve literal equality.

The motion runner accepts `--run`, explicit stable ports/images, bounded capture
duration and unique report path. It guides **C8-P2, C8-P3 and C8-P4** only. C8-P1,
P5, P8 and P9 in the acceptance matrix require additional separately approved
existing manual campaigns; the runner does not execute them. C8-P3 is the
existing sustained-HIGH episode case. Injected motion is explicitly rejected.
Real GPIO wake, restore, optical movement, original EventKey, S3 authenticated
application ACK and C3 retained-event retirement must all be independently
captured. Missing one of those markers cannot qualify the path.

The 17 existing no-port HIL tests exercised these guards and parser failure
cases using controlled input. Their PASS is harness readiness only. Default
runner NOT_RUN, partial observed markers or a simulated GPIO edge prove no
physical product behavior. Catalogue rows keep their existing definitions.

## Future observation sequence after prerequisites and approval

1. Save source/remote checkpoint, approved image identities, fixture IDs and
   current backend/Home/Node ownership. Record prior pending-event counts and
   safe observation evidence without changing state.
2. Observe board identity, authenticated contact/NodeHealth and natural events
   with existing board runner; record source/domain/age for each observation.
3. Use the existing motion runner for a real operator optical AM312 stimulus.
   Capture qualified creation, original local identity, authenticated mapping,
   S3 durable processing, application ACK and exact retained-event retirement.
4. Through approved existing CloudSync, capture actual original-key backend
   COMMITTED and durable query. Compare caregiver room/status/chronology and
   technician trace against independent observations; preserve UNKNOWN gaps.
5. Run exact-device installation only after its policy/design is approved;
   another device or an old backlog event must not satisfy the armed step.
6. Record each individual case, source/image match, exact key mapping, clock
   uncertainty and evidence hashes. A missing stage yields PARTIAL/BLOCKED;
   installation and physical product E2E cannot claim overall PASS.

No commands with `--observe`/`--run` are executed or generated as ready-to-run
commands in this campaign. Exact command values depend on the later approved
fixture. Privileged operations need separate approval and supported contracts.
