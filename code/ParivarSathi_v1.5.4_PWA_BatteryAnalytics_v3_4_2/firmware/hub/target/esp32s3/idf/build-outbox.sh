#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ -z "${IDF_PATH:-}" ]]; then
    IDF_PATH="/home/udaybhan/.espressif/v6.0.3/esp-idf"
fi
if [[ ! -f "$IDF_PATH/export.sh" ]]; then
    echo "ESP-IDF export.sh not found at $IDF_PATH" >&2
    exit 2
fi

build_root="${GS_S3_OUTBOX_BUILD_ROOT:-/home/udaybhan/projects/.ghar_sajag_s3_outbox_lifecycle_build}"
mkdir -p "$build_root"
export SDKCONFIG="$build_root/sdkconfig"
export SDKCONFIG_DEFAULTS="$script_dir/sdkconfig.defaults;$script_dir/sdkconfig.defaults.outbox"

# This build profile is isolated from the target's existing sdkconfig/build
# tree and selects the gs_outbox + gs_state partition candidate explicitly.
source "$IDF_PATH/export.sh" >/dev/null
idf.py -C "$script_dir" -B "$build_root/build" \
    -D IDF_TARGET=esp32s3 -D "SDKCONFIG=$SDKCONFIG" reconfigure build
