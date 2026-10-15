# GS-124 Stage 1 service access boundary — 2026-10-13

Owner: GS-122/124/125. Requirement: GS-122 comment 10705; existing ED-D01/02/03-MIN.
This is a branch-scoped host implementation contract, not production deployment approval.

## Implemented on the isolated dashboard branch

`code/backend/ghar_sajag/service_access.py` implements a service-ticket domain
against the existing host SQLite database and ownership registry. Migration 011
adds tickets, one-time access requests, an atomic company dispatch cursor and
minimal action metadata. `BEGIN IMMEDIATE` serializes assignment, approval,
denial, revocation and expiry with their audit rows. The Home's active Hub,
installation epoch and current active Node physical/logical IDs and enrollment
generations come from the existing ownership
registry. Every diagnostic authorization rechecks the employee, ticket,
assignment, staff role, Home, Hub, epoch, Node enrollment set and fixed expiry.
Time is sampled after acquiring the writer lock; approval and expiry cannot use
a timestamp captured before a competing writer completes. Failed writes roll
back the cursor, request and audit together. The approved default
is 1800 seconds in `code/config/service_access.json`; schema version and integer
range 60–3600 seconds are validated. This range is a bounded host engineering
contract, not a separately approved commercial duration policy. The grant never
slides. Expiry requires a new Start and a new caregiver approval.

`ServiceDiagnosticAuthority` composes a currently approved ticket with the
existing `DiagnosticAuthorizer` READ_DIAGNOSTICS policy. It supplies no Class B
event binding until a qualified technical source exists. Its scope and verified
principal are resolved in one transaction, including ticket, Hub and Node
enrollment bindings. Class A service reads reject foreign device IDs and missing
or stale Node generations, then reauthorize before returning any data. These
checks use injected technical fixtures; no live exporter is qualified. No diagnostic route,
service route, privileged control, OTP, synthetic admin bypass, device command or
second device registry is installed. The existing public caregiver PWA and local
`JsonApi` are unchanged. The 54 prior diagnostic-foundation cases remain present.

## Production interfaces still required

1. **Verified principal and active staff (GS-76/143).** A server-side session
   adapter must implement `ServiceAuthority.principal`, `caregiver_home`,
   `active_staff`, `active_employee` and `company_for_home`. It must verify issuer,
   signature, audience, expiry, revocation, current company employment/role and
   current Home membership/ownership epoch. The fixture object capabilities in
   tests do not verify credentials. Neither `X-Actor-Id`, a request JSON field,
   nor a client-set `verified` flag may populate this interface. The real adapter
   must provide a consistent authority snapshot or shared transaction/version
   fence with ticket writes; external-directory changes between checks are not
   transactionally fenced by host SQLite alone.
2. **Durable production persistence.** Review compatibility with the actual
   deployed backend and select/implement the PostgreSQL adapter and migration.
   Preserve ticket/Home/Hub foreign keys, partial unique live-request constraint,
   one-time approval, atomic company cursor and audit rows. Specify transaction
   isolation/row locks for concurrent workers, recovery, idempotency keys,
   retention and owner/staff change invalidation. Migration 011 is SQLite syntax
   and is not a production-ready PostgreSQL schema. Host tests establish
   restart/concurrency only within that SQLite boundary.
3. **Authenticated API and PWA composition.** Bind a real verified session and
   server-side CSRF control to caregiver ticket creation and Approve/Deny/Revoke,
   admin dispatch and technician Start. The caregiver must see a verified staff
   display name and exact ticket/Home/Hub/current-Node scope before an explicit
   click. Return backend-recorded expiry, use no-store responses, stop polling
   and clear caches on revoke/expiry/Home switch/logout, and test all three roles
   in a real browser. The existing PWA token-provider interface is injectable,
   but no production login/session composition exists. No routes or UI are
   activated by this Stage 1 change.
4. **Diagnostic source and authorization composition.** A qualified GS-65/109
   technical source and current original-EventKey/Node resolver are needed before
   live Class A/B reads. Any route must call the ticket-bound authorization on
   every request and again before returning data, retain ED-D03 bounds/no-store,
   and clear cursors after scope changes. Class B is disabled by the Stage 1
   adapter. Class A's source contract must supply the actual enrolled physical
   device ID and current enrollment generation for Node records; a caller flag
   cannot establish this provenance. Real-Home admin diagnostics still require
   caregiver approval.

Ticket/service metadata retention is unresolved; no number is inferred here.
Production service routes remain disabled until these interfaces and tests are
reviewed together. Physical GS-114 and GS-148 remain independent.
