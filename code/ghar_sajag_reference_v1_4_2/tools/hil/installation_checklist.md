# Physical installation gate (T02)

Do not mark a home eligible for unattended pilot operation until all applicable checks have evidence:

- Exact hub and C3 board profiles recorded; credentials are unique and readback verified.
- Four labeled nodes are bound to the intended home and location.
- Every enabled PIR/reed input produces a test event from its installed position.
- “I’m OK”, “Call family” and the latching privacy switch pass locally.
- Test alert is clearly labeled TEST, reaches the selected real phone and records human acknowledgement.
- Node-offline, hub-offline, WAN-loss and recovery states are distinguishable.
- USB/battery transitions, low-battery behavior, enclosure temperature and current draw are measured.
- Reboot/power interruption does not duplicate an incident or lose a durably acknowledged event.
- Test events do not enter production summaries, escalation metrics or future professional response routing.
