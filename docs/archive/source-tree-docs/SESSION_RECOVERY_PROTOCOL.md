# Authenticated session recovery

The Node's ordinary NodeHealth interval remains 120 seconds. Rejoin v2 adds
one negotiated capability, `health_ack_supported` (bitmap bit 0). A v2 Node
offers it; a v2 Hub selects only offered supported bits. Legacy v1 Rejoin and
commissioning bodies remain byte-for-byte unchanged.

## Rejoin wire bodies

The existing GS fragment envelope remains version 1. Its message kind and
length distinguish the bodies below. Integer fields in these bodies use the
existing little-endian wire convention.

* v1 RejoinHello: version byte `1`, four length-prefixed identity strings,
  session u64, node challenge 16 bytes, authentication 32 bytes.
* v2 RejoinHello: version byte `2`, offered capabilities u32, then the same
  four strings, session, challenge, and authentication.
* v1 RejoinChallenge: Hub challenge 16 bytes, authentication 32 bytes.
* v2 RejoinChallenge: selected capabilities u32, then Hub challenge and
  authentication. The 52-byte body is distinct from the 48-byte v1 body.
* RejoinFinal and RejoinAck keep their 32-byte confirmation bodies; the
  negotiated version changes the transcript and authentication label.

The authenticated transcript uses its existing big-endian integer encoding.
The v2 Hello transcript has domain `GS-P2-REJOIN-v2\0`, version byte,
offered capabilities u32, identity strings, session u64, and Node challenge.
The challenge transcript appends the Hello authentication, Hub challenge,
and selected capabilities u32. These values are authenticated through all
following MACs and session-key derivation. V2 labels are exactly:

* `GS-P2-REJOIN-HELLO-v2`
* `GS-P2-REJOIN-HUB-v2`
* `GS-P2-REJOIN-NODE-FINAL-v2`
* `GS-P2-REJOIN-HUB-ACK-v2`
* `GS-P2-REJOIN-SESSION-SALT-v2`

V1 keeps its existing `-v1` labels and transcript. Neither version accepts
unknown capability bits. An unpinned Node may fall back to v1 after 30 seconds
without an authenticated v2 challenge. A Node that has successfully verified
the v2 final ACK persists its Hub-specific capability pin once. It does not
fall back for that Hub afterward. A v1 session has no HealthAck expectation;
the Hub sends no HealthAck to a v1 peer.

## Health and recovery

Data-plane frame type 4 is NodeHealthAck. Its sole payload is the acknowledged
health sequence as a big-endian u64. The secure downlink frame binds it to the
current session and provides replay protection. The Hub sends it after
accepting an authenticated NodeHealth from a negotiated v2 peer. Only an AEAD
verified, replay-valid ACK matching the outstanding sequence refreshes the
Node's monotonic last authenticated contact time. A matching application ACK
or accepted authenticated control frame also refreshes it. MAC send success
does not.

After 430000 ms without authenticated Hub contact, the Node enters
`SESSION_STALE`, invalidates its old transport keys and counters, and begins
fresh authenticated rejoin. A pending event can trigger this earlier after
three completed or timed-out send opportunities, at least 10000 ms since its
first attempt, and no authenticated contact in that interval. One missed
packet cannot trigger rejoin. PowerPolicy receives the contact and rejoin
deadlines; light sleep remains capped at 30000 ms.
The Node's 430000 ms deadline is separate from the Hub's 310000 ms liveness
lease so two missed health opportunities plus an RF recovery interval do not
force a needless Node rejoin.

The in-service Node owner submits one-packet rejoin messages without waiting
for a MAC callback, so PIR sampling continues during retries. A delayed
security-send callback is allowed to settle before application sends resume.

The Node durably allocates a strictly newer session candidate before its first
Hello. Retries use the same candidate. An exact Hello retransmission while a
challenge is pending receives the same challenge; a committed equal-session
Hello is rejected. Backoff starts at about 1.5, 3, and
10 seconds, grows to 60 seconds, and adds deterministic jitter of at most
100 ms. Only after a valid Hub challenge and a first transmitted Final can a
commit be ambiguous. A Final send attempt is treated conservatively as a
possible transmission even if its MAC callback is lost. After 180000 ms and
at least four Final send attempts,
the Node allocates a fresh higher candidate. Consecutive ambiguous windows
double up to one hour. Without an authenticated challenge, an outage causes
no repeated session allocations. An allocation failure stops transport use.

Pending business events keep their original EventKey, timestamp, and payload.
After rejoin, their packets use new session keys and counters. The Hub admits
an older event origin session under the current authenticated transport
session and deduplicates by durable EventKey; a duplicate receives the
original-key application ACK without repeating business effects.
