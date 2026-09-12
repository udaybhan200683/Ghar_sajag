# Ghar Sajag v1.5.3 patch notes

This patch makes household behaviour policy configurable through the web/simulation Settings path.

## Configurable per household

- Quiet-hours door alerts: enable/disable, start, end.
- Door-left-open warning timeout.
- Daytime inactivity alert: enable/disable, monitoring start, end.
- No-activity threshold.

These settings are versioned in `/v1/homes/{homeId}/config`, represented in `contracts/config.schema.json`, carried in C++ `HomeConfig.activity_rules`, and applied to the hub activity-rule configuration. Defaults are fallback values for a newly provisioned home only.

## Intentionally not family-configurable

Node↔hub ACK semantics, retry backoff, heartbeat interval and offline threshold remain engineering-owned reliability parameters. Exposing them to normal users could create false-offline states or excessive battery/radio use.

## Privacy

There is no ordinary Privacy ON/OFF setting. Consent withdrawal can still force the internal privacy state so passive collection stops as required.
