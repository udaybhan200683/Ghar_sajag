# GS-40 / GS-117 authenticated runtime configuration renewal

Status: source implemented / NOT_DEPLOYED; IMPLEMENTATION_DESIGN under owner GS-117#12072 / GS-40#12073.
Physical acceptance and deployment: NOT_RUN. Original event: Bedroom/141/1.

## Confirmed boundary and scope

The physical S3 acknowledged 141/1 durably, then fenced publication on its
expired GS40T/1 configuration. The startup receiver cannot renew a running
configuration. The existing authenticated authority request is never reached
because periodic time refresh first rejects that expiry. Journal contents have
not yet been independently inspected; durable ACK is not a later storage scan.

BUG_CLASSIFICATION=R1_BLOCKER
REQUIREMENT_SOURCE=R1_RELEASE_CONTRACT; GS-D007/009/021-029/034; owner12072/12073
TASK_SCOPE=existing TEST_ONLY configuration renewal, authority and pending CloudSync
OUT_OF_SCOPE=new identity service, production use of fixture secrets, new motion,
storage erase, pairing, expiry bypass, firmware deployment without applicable scope

Affected components: S3 GS40 configuration/material provider and refresh owner;
existing isolated authority fixture and HTTPS response bounds. Node event/radio
and durable-before-ACK contracts do not change. Required tests: new expiry,
generation, same-material, nonce/profile/identity and recovery negatives; prior
GS40 bootstrap/cloud-trust and affected fixture/API tests; relevant target build.
Host tests, physical renewal and endurance are distinct evidence.

## Reuse and recovery contract

Reuse the existing `/v1/test/authority/refresh` mTLS route and GS40T/1 encrypted
configuration envelope, provisioning root, fresh target P-256 session/challenge,
signature/AEAD verifier and current ownership/credential checks. No new listener,
issuer database, root, credential or privileged executor is introduced.

An explicitly identified configuration-renewal request on that route carries
the existing Hub, fingerprint, credential/boot generations and fresh nonce,
plus the target session public key and previous configuration generation. The
existing fixture may return a fresh complete encrypted configuration only when
its private, explicitly configured template matches the authenticated Hub/Home,
certificate and credential generation. A missing provider fails closed.

The provisioning signer remains distinct from the authority signer. The reply
uses the existing length-prefixed G40E envelope, not a new cryptographic format.
Its generation must advance and its signed expiry must be current and bounded.
The target verifies it under the existing provisioning root and fresh session.
For this recovery scope, all configuration content other than generation and
expiry must match the currently admitted material. Credential/ownership/network
replacement remains outside this renewal path. A canonical content digest of
the original signed payload binds that equality after the Wi-Fi secret is wiped.

Authenticated time recovery may obtain a fresh nonce/boot-bound time proof while
configuration publication is expired. That grants only the ability to attempt
the existing certificate-authenticated recovery route. It never supplies a
Home binding or authorizes events. Publication remains fenced until BOTH a
fresh signed configuration and a current signed authority lease are accepted.
Normal TLS certificate validity, hostname/CA and current registry authorization
remain mandatory. Expired/revoked credentials are not rescued by this path.

The existing refresh owner starts renewal before expiry, retries with bounded
backoff, and retries after expiry/outage. Generation/expiry activation is atomic;
failed candidates do not replace admitted secrets or touch the journal. Current
material checks expiry on every publication lookup, independent of refresh-task
timing. Successful configuration replacement is followed by the existing signed
authority renewal; normal CloudSync then drains the original durable backlog.

## Continuous-operation boundaries

Existing fixture replay protection must retain a bounded live replay window,
not terminate after a lifetime request count. Signed-time service counters are
telemetry, not a lifetime stop condition. Service lifetime/explicit shutdown and
registered Engineering network authority remain enforced separately.

This runtime renewal does not establish autonomous cold-boot commercial
provisioning. Current TEST_ONLY secrets are RAM-only; production provisioning
and legitimate retained configuration must use their existing secure owners.
Do not persist fixture secrets or silently convert this path into production.
Restart, credential rotation, Windows lifecycle and multi-day qualification
remain explicit gaps until implemented and physically measured.

## Acceptance

Exercise multiple renewal cycles, expired recovery, outage/backoff, nonce and
generation rejection, wrong Hub/Home/fingerprint/profile, invalid envelope and
publication fencing. Verify the original 141/1 in actual S3 durable state before
asserting recovery, then exactly one PostgreSQL/API result and actual APK proof.
Keep GS-117 open and preserve its original failed run. No reset loop or fresh
event may substitute for original-event recovery.

## 2026-11-13 source milestone and permanent-fix audit

Affected host evidence: bootstrap 201 checks; TLS/trust-provider security target
PASS (Python 14+15+13+6 tests); restricted recovery adapter PASS; mapping22/22;
ESP-IDF6.0.3 TEST_ONLY S3 build PASS. See GS40_RENEWAL_20261113 receipts.
This is not physical renewal, a current journal scan or endurance acceptance.
No new motion, serial opening, reset, flash, key or enrollment change occurred.
Windows read-only endpoint check: TCP8445=0,UDP4468=0,caregiver443=1.

| Issue | Confirmed cause | Correction | Deployed? | Regression/retest | Remaining gap |
|---|---|---|---|---|---|
| S3 expiry/CloudSync | Expired startup configuration rejected before authority recovery | Fresh signed/encrypted same-material renewal; current config plus lease required | NO | 201 bootstrap checks; affected security integration; target build | Issuer composition; safe firmware update; original141/1; physical outage/endurance |
| Fixture lifetime limits | Signed-time request loop stopped at256; replay cache became lifetime cap | Explicit shutdown controls service; bounded live replay entries | NO live service in this milestone | 300 UDP requests;399 authority requests; time-window pruning | Actual service restart/long duration |
| Windows mutable-source pin | Unrelated GS117 byte identity checked for fixed network operation | Protected validator decoupled previously | Previously installed SHA eb00866c...abd9 | Previous non-elevated Start/Close and source tests reused | Windows restart and full SYSTEM cleanup attribution |
| C3 repeated COM reconfiguration | Same timeout assignment reconfigured Windows COM/DCB/DTR/RTS each read | Existing collector changes timeout only when different | Host abf05b5; physical141/1 followed correction | Prior collector28/28; readiness2/2; one physical event | Independent repeated reopen/restart/multi-day evidence |
| C3 oversized parser | Oversized line tail dispatched as another command | Existing firmware discard-to-delimiter source correction | NOT_PROVEN on C3 | Prior source/build tests preserved | Safe firmware deployment and physical malformed-input recovery |
| Signed-time orphan child | Wrapper shutdown did not prove ownership cleanup of child | No new wrapper correction claimed | NO | Prior explicit Stop preserved | Normal/failure/expiry child cleanup qualification |
| Autonomous cold boot | TEST_ONLY secrets/config remain RAM-only; startup receiver only | Not solved by runtime renewal | NO | NOT_RUN | Existing secure commercial provisioning owner; no fixture-secret persistence |

The existing single reboot11983 is USED. No reset/update is inferred from the
owner's general implementation direction. Prepare an explicit safe update plan
that preserves the original journal and association before protected deployment.
Do not erase, initialize or seed a replacement event. If141/1 is missing, preserve
that finding as a separate durability defect. Cold-start sensing stays ON HOLD.
The 3600s/1800s privileged ingress policy remains unchanged; continuous product
operation and continuous development environment are separate unqualified gaps.
No claim is made that a retest five days later will pass. Qualification duration
for the physical renewal correction is zero; >1h and multi-day runs remain NOT_RUN.
