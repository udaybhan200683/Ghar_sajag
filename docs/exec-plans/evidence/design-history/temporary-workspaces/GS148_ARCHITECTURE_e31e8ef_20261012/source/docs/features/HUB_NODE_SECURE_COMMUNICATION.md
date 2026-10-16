# Hub-Node Secure Communication

Feature documentation type:
ENGINEERING FUNCTIONAL GUIDE

This guide explains stable feature functionality and implementation.

It is NOT the current project-status authority.

For current project status: `docs/progress/CURRENT_STATUS_AND_ROADMAP.md`
For implementation/evidence traceability: `docs/validation/MASTER_TRACEABILITY.csv`
For feature qualification: `docs/validation/` and `evidence/hil/runs/`

## 1. Purpose

ESP-NOW provides short-range datagram delivery. By itself, a received packet does not prove which enrolled Node created it, whether its contents changed, or whether it is a replay. The application security layer adds authenticated peer identity, confidentiality, integrity, direction separation, replay rejection and session freshness. The Hub still routes accepted payload through the normal event, health, ACK, control or FOTA owner; cryptography does not replace those application policies.

## 2. Easy mental model

```text
commissioning establishes long-term trust
                  |
                  v
authenticated rejoin creates a fresh session
                  |
                  v
runtime session protects each frame
                  |
                  v
Node events / health / ACK / control travel through
authenticated protection, then normal owner routing
```

Commissioning and rejoin are covered in the Device Identity guide. This guide focuses on the established association and normal secured communication.

## 3. Security layers solve different problems

| Layer | Job | Does not replace |
|---|---|---|
| Factory asymmetric identity | Persistent public/private identity proves a physical device's identity | Runtime packet encryption or firmware publisher verification |
| Commissioning authentication | Authenticates exact Node and Hub/Home, assignments and authorization; creates installation binding | Per-packet freshness after reboot |
| Ephemeral ECDH | Establishes shared secret material without sending the secret over radio | Peer authorization by itself; identities/transcript must also authenticate |
| HKDF-SHA-256 | Derives context-separated installation/session key material | Authentication or encryption of packets by itself |
| Runtime symmetric AEAD | AES-256-GCM encrypts and authenticates each runtime frame | Firmware signing or authorization policy |
| Replay protection | Rejects duplicate/too-old packet counters inside a session | New valid messages from an authorized peer |
| FOTA image signature | Verifies firmware publisher authenticity under the configured signing profile | Runtime channel security; see the FOTA engineering guide |

Identity keys, installation keys, session traffic keys and firmware signing keys are distinct roles. Secret key bytes should never be logged or added to diagnostic output.

## 4. Runtime session lifecycle

An authenticated rejoin carries a Node boot session greater than the Hub's persisted accepted session, fresh Node and Hub challenges, and transcript authentication under the installation key. Both sides derive the same fresh session salt after confirmation. The Hub persists its accepted session before admitting application data. Each owner then starts a new `RuntimeFrameSecurity` instance for that Node.

HKDF context includes the association and session salt, and yields separate uplink and downlink AES-256-GCM keys. Session ID, Device/Home/Hub/logical identity and direction are authenticated in the frame header/associated data. Session replacement clears the old owner context; an old ACK or data frame cannot be accepted under the new context. Counters begin at one for each direction within a fresh session. Receive replay state is a 64-counter window; the counter is marked received only after a valid AEAD tag and successful plaintext decode path. A session rollback is rejected by the frame security object and, across reboot, by the persisted Hub session floor plus Node's monotonic boot-session source.

## 5. Runtime AEAD in plain language

AEAD does two things together: AES-GCM encrypts the payload so observers cannot read it, and creates a tag so a receiver can detect changes and verify that the sender holds the session key. The unencrypted envelope carries version, session and counter information. Associated data authenticates that envelope plus the physical/logical/Home/Hub identities and direction without encrypting those routing fields. Altering any authenticated field invalidates the tag. A counter outside the accepted replay window is rejected before it can refresh application state. The open method exposes no plaintext before tag verification.

The current envelope overhead is 28 bytes and the maximum ESP-NOW application payload is 250 bytes. `seal` refuses an oversized encoded frame; callers must keep encoded plaintext at or below 222 bytes.

## 6. Node to Hub traffic

```text
NodeRuntime / health owner
       |
       +--> encode event or NodeHealth
       |        -> NodeSecurityLink RuntimeFrameSecurity (uplink)
       |        -> bounded radio callback queue -> ESP-NOW
       |
       v
Hub radio callback queue
       -> source MAC selects candidate owner/session only
       -> per-Node AEAD open and replay check
       -> identity/session match + plaintext decode
       -> event ingest/journal or authenticated health update
       -> event ACK sealed downlink when durable admission permits
```

Event identity and retained retry state belong to `NodeRuntime`; Node recovery storage preserves pending identity/payload across reboot. Radio callbacks copy bounded work to owner queues. The Hub chooses a session context from the source MAC, but only a valid AEAD frame bound to that context's Device ID, Home, Hub, logical identity, direction and session is attributed to that Node. Event ingestion then performs its own dedupe/durable journal/reducer logic.

`NodeHealth` follows the same secure uplink. It reports runtime and sensing state, retained event status, retry/error counters, heap and a health sequence. FOTA ACK is a different typed message and enters the secure FOTA owner path; it is not an application-event ACK.

## 7. Hub to Node traffic

The Hub uses the enrolled Node's active session context to seal downlink frames. Application event ACK is produced only after the Hub's configured durable ingest result; controls are decoded and handled by their owner after authentication. Secure FOTA v2 messages and FOTA ACKs use the same session protection but also bind transfer identity/index/status in the FOTA protocol. The Hub FOTA request API is internal and has no external production caller; physical secure FOTA is not yet qualified. See `FOTA_ENGINEERING_FLASHING_SECURITY_AND_RECOVERY_GUIDE.md` for image and update-layer details.

## 8. Event ACK semantics

An ACK proves that the Hub owner received and accepted a specific event identity at the protocol's durable-ingest boundary, and that the response is authentic for the current Node session. It does not prove caregiver delivery or downstream cloud processing. ACK data binds event identity/sequence and session; the Node retires matching retained work only after opening and decoding the authenticated ACK, then persists the retirement.

Duplicate delivery can receive a duplicate/durable ACK without reapplying the event reducer. Wrong-node, wrong-event, malformed, stale-session or replayed ACKs cannot retire a pending event. A lost ACK leaves the event retained for retry; the Hub's journal deduplicates it.

## 9. Health and liveness

Health is authenticated like any other uplink. The Hub checks the health sequence/session and refreshes liveness using accepted authenticated Node activity. Event traffic can also refresh liveness; health is not the only proof that a Node is alive. A monotonically increasing health sequence detects stale/repeated health reports within the relevant state model. It is not a wall-clock timestamp, and liveness refresh does not invent a time-of-day measurement.

## 10. Replay and stale-session examples

| Received frame | Result |
|---|---|
| Same authenticated session/counter a second time | Replay window rejects it; no second event/health update |
| Counter older than the 64-frame receive window | Reject as stale |
| Counter/header altered while retaining old GCM tag | AEAD authentication fails |
| Valid old-session ACK after rejoin installed a newer session | Old frame context no longer selected/accepted; pending event remains |
| Correct session/counter but direction changed | Direction is authenticated and keys differ; reject |
| New valid message with a fresh counter | Decode, identity checks and application policy decide admission |

## 11. Outage, restart and in-flight events

During Hub outage, the Node retains pending event identity and retries under its current session until the connection fails; after rejoin it uses a fresh session and newly sealed frames. The Hub restart reloads the durable registry and journal, but runtime session objects are RAM-only and must be recreated by rejoin. A C3 restart similarly loads its association and retained recovery record, allocates a fresh boot session, rejoins and recreates runtime keys.

An old encrypted frame in flight is not valid in the replacement session. The Node resends the retained event under the new key/session. If the Hub already durably recorded that event before restart, journal dedupe returns the appropriate duplicate ACK without replaying the reducer. Target physical restart/power-cut scenarios remain a qualification gap even though host recovery models and target wiring exist.

## 12. Multi-Node isolation

Each enrolled physical Device ID has a registry record, installation key, active session object, directional keys and replay window. MAC chooses a candidate route only; authenticated physical and logical identity must match that route. ACKs are checked against the owning Node and pending event/session. Thus a valid packet from Node A cannot be relabeled as Node B by changing a header, source routing value or ACK destination. Registry conflicts are rejected or quarantined. Host simulation covers multiple contexts; physical multi-node radio capacity and isolation have not been qualified.

## 13. ESP-NOW relationship

Current protection is application-layer AES-GCM implemented in `RuntimeFrameSecurity`. Do not describe it as ESP-NOW native peer encryption. Native peer encryption is a separate radio/link feature and is not required for the application envelope to authenticate payloads. Radio addresses remain transport selectors, not cryptographic identities.

## 14. Packet and resource constraints

ESP-NOW v1 application payloads are limited to 250 bytes. The 28-byte secure envelope leaves 222 bytes for encoded application content; normal event and health codecs enforce the resulting frame size. Commissioning has a separate bounded fragmentation format. Secure FOTA's inner header plus 28-byte AEAD envelope leaves a 192-byte data chunk: `14 + 192 + 28 = 234` bytes. A 193-byte chunk would exceed the 250-byte bound. These limits are wire constraints, not radio throughput guarantees.

## 15. Failure matrix

| Failure | Expected behavior | Engineer response |
|---|---|---|
| Bad AEAD tag | Drop before plaintext is exposed; rejection counter/log may increment | Check session mismatch, corruption, wrong peer context; do not bypass authentication |
| Replay counter | Reject duplicate or too-old frame; no state refresh | Capture session/counter and inspect retransmission behavior |
| Wrong source MAC | No active candidate session or wrong expected commissioning peer; drop | Check radio peer mapping; MAC alone cannot establish identity |
| Wrong Node identity | Authenticated associated identity does not match routed registry entry; drop/quarantine policy | Compare Device ID/logical ID, Hub registry and source mapping |
| Stale session | Reject old session or non-increasing rejoin | Check fresh boot-session allocation and Hub persisted session floor |
| Session replacement | Invalidate old session traffic and pinned work | Drain/retry retained event using new session; restart transfer if FOTA |
| Malformed frame | Codec/length/version validation rejects before owner handling | Capture size/type/error; inspect codec version and frame bounds |
| Queue full | Bounded callback/owner queue drops or rejects; health records queue error where available | Inspect queue drop counters, heap and producer rate; rely on bounded retry |
| Lost ACK | Node keeps event pending and retries; Hub dedupe prevents duplicate reducer application | Inspect event ID, retry/backoff, Hub journal and ACK send/result logs |

## 16. Important source files/classes

Paths below are relative to `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/`.

- `firmware/common/security/runtime_frame_security.*` — `RuntimeFrameSecurity`, key derivation, envelope, AEAD and replay window.
- `firmware/common/security/rejoin_protocol.*` — authenticated session creation and fresh salt.
- `firmware/common/security/commissioning_protocol.*` — long-term trust and installation binding preceding runtime use.
- `firmware/node/target/esp32c3/node_security_link.*` — association load, rejoin, session installation and Node secure-frame access.
- `firmware/hub/target/esp32/hub_security_link.*` — registry lookup, rejoin/session state, per-MAC routing context and removal.
- `firmware/node/target/esp32c3/node_runtime_adapter.cpp` — secure uplink event/health, downlink ACK/control opening, authenticated FOTA ACK routing.
- `firmware/hub/target/esp32/hub_runtime_adapter.cpp` — secure receive, authenticated health/event routing and ACK/control/FOTA sealing.
- `firmware/common/transport/data_plane_codec.*` — event, NodeHealth and ACK wire codec; `firmware/hub/components/ingest/ingest.*` owns event admission.
- `firmware/node/runtime/node_runtime.*` and `firmware/node/components/storage/node_recovery_persistence.*` — event identity, retry/retention and recovery state.
- `firmware/common/transport/fota_secure_wire.*` and `firmware/node/fota/secure_fota_adapter.*` — secure FOTA framing/adaptation.

## 17. Diagnostics

Useful non-secret fields are physical Device ID, logical ID, Home/Hub ID, session ID, registry state, rejoin phase, frame direction/counter, event ID or sequence, ACK result, health sequence, queue/drop counters, and rejection reason. Never log installation keys, wrapping keys, private keys, installer codes, session salts or plaintext sensitive payloads.

Current target logs include application ACK session/sequence/class/retirement, rejected unauthenticated/replayed ACKs, authenticated event sequence/ACK/send result, authenticated NodeHealth session/sequence and selected health fields, and rejected stale/mismatched health. Pair these with Hub registry load and rejoin outcome diagnostics. A MAC/RSSI log alone does not establish secure identity.

## 18. Tests and qualification boundary

**Host verified:** Runtime AEAD/replay, host commissioning/rejoin, multi-Node attribution, wrong-node/misrouted/stale ACK rejection, retention/retry and journal dedupe have source validation in `tests/cpp/multinode_host_validation.cpp`, `tests/cpp/rejoin_host_validation.cpp` and related security validations.

**Target-build verified:** PSA crypto and Hub/C3 secure owner routing compile in target configurations. This verifies integration/buildability, not radio behavior or production secrets.

**Physically qualified:** Existing Phase-1 radio/HIL evidence exercises the legacy data path. It is not proof of current-HEAD application AEAD, rejoin, secure ACK or secure FOTA behavior.

**Not yet physically qualified:** Current-HEAD commissioning-to-runtime secure exchange, Hub/C3 restart session replacement, replay injection, multi-Node secure radio isolation, production protected credentials and secure FOTA. Physical qualification must be read from the exact run and commit in `evidence/hil/runs/` and applicable validation plans.

## 19. Current limitations

- Current target identity/wrapping-key provisioning is development support; production key custody/protected storage is not established.
- Product commissioning entry point and fully authorized external control channel are incomplete.
- Target physical commissioning/rejoin/runtime AEAD qualification is pending; do not infer it from host validation or target compilation.
- Hub registry, per-Node peer/session wiring and target NVS persistence have capacity and power-cut/rollback qualification gaps.
- Multi-node host simulation does not prove ESP-NOW peer limits, RF behavior, timing or target resource headroom.
- Runtime cryptographic authentication does not itself authorize every application action or prove firmware publisher authenticity.
