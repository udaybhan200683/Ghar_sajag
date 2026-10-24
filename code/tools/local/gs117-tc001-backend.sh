#!/usr/bin/env bash
set -euo pipefail
config_file="$HOME/.config/ghar-sajag/gs179-laptop/server.env"
[[ -f "$config_file" && "$(stat -c %a "$config_file")" == 600 ]] || exit 2
# The GS-179 installer wrote this owner-only shell environment file.
# shellcheck disable=SC1090
source "$config_file"
export PYTHONPATH="$HOME/.local/share/ghar-sajag/gs179-laptop/python-deps${PYTHONPATH:+:$PYTHONPATH}"
export LD_LIBRARY_PATH="$HOME/.local/share/ghar-sajag/gs179-laptop/postgres-root/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export GS179_ANDROID_CA="$HOME/.local/share/ghar-sajag/gs179-laptop/tls/android/ca.pem"
exec python3 "$(dirname "$0")/gs117_tc001_backend.py"
