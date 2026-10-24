#!/usr/bin/env bash
set -euo pipefail
cd /home/udaybhan/projects/Ghar_sajag_r1
# Start only the already-installed local caregiver service when inactive. This
# does not invoke GS-179 network refresh, proxy/firewall edits or Hub ingress.
if ! systemctl --user is-active --quiet gs179-laptop.service; then
    systemctl --user start gs179-laptop.service || {
        printf 'TC001: existing GS179 laptop service could not start; open the console for readiness details.\n' >&2
    }
fi
exec python3 code/tools/local/gs117_tc001_console.py
