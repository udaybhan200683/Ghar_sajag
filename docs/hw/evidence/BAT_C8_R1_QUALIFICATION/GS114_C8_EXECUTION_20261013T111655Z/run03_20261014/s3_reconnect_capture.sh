#!/usr/bin/env bash
# Single-reader, read-only S3 UART capture for Hub power-cycle HIL cases.
# Waits for the stable USB by-id link and reopens only after that link vanishes.
set -u

# USB serial disconnects may send SIGHUP to the reader even though its loop is
# designed to detach and reopen the stable by-id path. Keep the sole observer
# alive so it can wait for the Hub's next enumeration.
trap '' HUP

device="${S3_DEVICE:-/dev/serial/by-id/usb-1a86_USB_Single_Serial_5CBC401023-if00}"
out="${S3_CAPTURE_LOG:-$(dirname "$0")/s3_uart_timestamped.log}"

timestamp() {
    date -u +%Y-%m-%dT%H:%M:%S.%NZ
}

while :; do
    if [[ ! -e "$device" ]]; then
        sleep 0.2
        continue
    fi
    if fuser -s "$device" 2>/dev/null; then
        sleep 0.2
        continue
    fi
    if ! stty -F "$device" 115200 raw -echo -hupcl -ixon -ixoff 2>/dev/null; then
        sleep 0.2
        continue
    fi
    if ! exec 3<>"$device"; then
        sleep 0.2
        continue
    fi

    printf '%s [s3-capture] reader_attached stable_path=%s\n' "$(timestamp)" "$device" >>"$out"
    while [[ -e "$device" ]]; do
        line=''
        if IFS= read -r -t 1 line <&3; then
            printf '%s [s3] %s\n' "$(timestamp)" "$line" >>"$out"
        else
            read_status=$?
            if ((read_status > 128)); then
                continue
            fi
            break
        fi
    done
    exec 3<&-
    exec 3>&-
    printf '%s [s3-capture] reader_detached stable_path=%s\n' "$(timestamp)" "$device" >>"$out"
done
