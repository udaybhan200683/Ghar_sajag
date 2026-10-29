#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT=/home/udaybhan/projects/Ghar_sajag_r1
cd "$REPO_ROOT"
if [[ "${1:-}" == --hil-policy-status || "${1:-}" == --hil-readiness ]]; then
    exec python3 code/tools/local/gs117_tc001_console.py "$@"
fi
GS179="$REPO_ROOT/code/tools/local/gs179-laptop-server.sh"

# Reuse the existing service's bounded local recovery and end-to-end health
# checks. A failed Windows LAN proxy is displayed but does not prevent the
# loopback GS-117 utility from opening in a safely BLOCKED state.
if ! "$GS179" dev-start; then
    printf 'TC001_ENVIRONMENT_READY=FAIL; see the stage-specific GS179 readiness results above.\n' >&2
fi
if ! "$GS179" proxy-audit; then
    printf 'TC001_WINDOWS_PROXY_AUDIT=FAIL; Windows state could not be read by the current user.\n' >&2
fi
if curl --fail --silent --show-error --connect-timeout 1 --max-time 2 \
        -o /dev/null http://127.0.0.1:18791/; then
    printf 'GS117_WEB_UTILITY_READY=ALREADY_RUNNING url=http://127.0.0.1:18791/\n'
    exit 0
fi
exec python3 code/tools/local/gs117_tc001_console.py
