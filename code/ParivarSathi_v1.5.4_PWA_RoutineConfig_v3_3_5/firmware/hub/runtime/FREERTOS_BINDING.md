# Hub runtime binding to ESP-IDF / FreeRTOS

The portable `HubRuntime` is deliberately single-owner. Bind it to ESP-IDF as follows; do not call business logic directly from driver callbacks.

| Runtime task | Proposed priority / stack starting point | Owns | Receives |
|---|---|---|---|
| Radio ingest callback | callback context; no task allocation | Fixed-size copy and admission only | ESP-NOW frame → static `radio_rx_queue` |
| `hub_event_task` | priority 8 / 8 KiB | `HubRuntime`, journal writes, coverage, rules, config transition serialization | radio, timer, UI and internal fault envelopes |
| `cloud_sync_task` | priority 5 / 8 KiB | MQTT session and reads from committed outbox | reconnect, app commit ACK and command envelopes |
| `ui_task` | priority 6 / 5 KiB | debounce/read buttons and privacy switch; render feedback | GPIO edges and state snapshots |
| `maintenance_task` | priority 3 / 8 KiB | diagnostics, service window and OTA orchestration | explicit maintenance commands only |

Starting values are not release values. Measure high-water stack use, queue occupancy, callback latency and starvation on the exact board and pinned ESP-IDF build.

Rules:

- Use statically allocated bounded queues; overflow becomes an observable fault/gap.
- Timers enqueue `DEADLINE`, `LEASE_EXPIRED` or `GRACE_ENDED`; timer callbacks never mutate rule state.
- `hub_event_task` is the only routine/config/coverage state writer.
- A business ACK is sent only after `HubJournal::commit` succeeds or identifies a duplicate already committed.
- MQTT PUBACK never retires the local outbox; only the backend application-commit ACK does.
- Privacy input is sampled before passive ingest is enabled. Passive activity received while privacy is active returns `DISCARDED_POLICY` without journaling.
