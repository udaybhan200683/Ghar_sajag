#!/usr/bin/env bash
# Deprecated: retained for the former PowerShell-master design.
# The WSL-first qualifier invokes make directly and does not use this file.
set -u

if [ "$#" -ne 2 ]; then
    echo "usage: run-wsl-stage.sh REPO STAGE" >&2
    exit 2
fi

repo=$1
stage=$2
case "$stage" in
    validation-fast|release-gate-final|hil-setup|hil-preflight|hil-smoke|hil-regression) ;;
    *) echo "unsupported HIL supervisor stage: $stage" >&2; exit 2 ;;
esac

cd -- "$repo" || exit 2
if [ -f "$HOME/.espressif/tools/activate_idf_v6.0.3.sh" ]; then
    # shellcheck disable=SC1091
    source "$HOME/.espressif/tools/activate_idf_v6.0.3.sh" || exit 2
fi

# Replace bash with make. wsl.exe waits on the actual stage process.
exec make "$stage"
