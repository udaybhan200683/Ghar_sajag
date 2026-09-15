# Phase 1 application API contract (local integrated lab)

`/pwa/foundation/` is the local PWA application boundary. All responses are JSON and live mutations are uncached. `X-Actor-Id` identifies a seeded development member; it is not a production credential. Server-side `FoundationService` checks active membership for reads and active OWNER for writes, and scopes SQL operations to the configured household. A deployed adapter must replace the development actor header with an authenticated session while retaining the domain checks.

| Resource | Read | Mutation | Authoritative table |
| --- | --- | --- | --- |
| `home` | `GET` | `PATCH` full `{display_name,timezone,language}` | `households` |
| `members` | `GET` list | `POST` `{member_id,display_name,relationship,role,contact}` | `family_members` |
| `members/{id}` | — | `PATCH` editable fields; `DELETE` deactivates | `family_members` |
| `devices` | `GET` registered list | `POST` `{device_id,display_name,kind,capability,room}` | `device_registry` |
| `devices/{id}` | `GET` detail | `PATCH` `{display_name,room,enabled}`; `DELETE` unregisters | `device_registry` |
| `devices/{id}/health` | — | `POST` `{online,health,battery_mv,battery_percent,drain_status}` | `device_registry`, `device_health_history` |
| `policy` | `GET` `{version,settings}` | `PATCH` complete validated settings object | `application_policy` |
| `network` | `GET` simulator hub/WAN status | — | host simulation projection |

IDs are lowercase letters/digits/hyphens, 2–32 characters, starting with a letter. Device kind/capability and room must be supported combinations. The role values are `OWNER`, `FAMILY`, `CAREGIVER`; only OWNER mutates. A final active OWNER and final registered Hub cannot be removed. Member deactivation and device unregistration retain historical records and identity tombstones. Health updates are simulator events through the same registry; real physical pairing/Wi-Fi provisioning are not represented by a successful API call.

Expected outcomes: `200` read/edit/delete/health, `201` add, `400` malformed/invalid/duplicate/inactive or required-infrastructure violation, `403` unauthorized actor or local-origin violation, `404` unknown resource, `500` storage failure with no success response. The PWA keeps a failed editor open with an error. The service worker caches static shell assets only, never these responses. Targeted enforcement is in `tests/python/test_foundation.py` and `tests/python/test_phase1_application.py`; desktop/mobile acceptance is in `tests/playwright/phase1_foundation.spec.ts` (focused 12/12 PASS outside sandbox); complete WSL release qualification is pending.
