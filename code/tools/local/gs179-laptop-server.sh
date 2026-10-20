#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR/../../.." rev-parse --show-toplevel)"
SERVICE_ROOT="$HOME/.local/share/ghar-sajag/gs179-laptop"
CONFIG_ROOT="$HOME/.config/ghar-sajag/gs179-laptop"
STATE_ROOT="$HOME/.local/state/ghar-sajag/gs179-laptop"
ENV_FILE="$CONFIG_ROOT/server.env"
PG_ROOT="$SERVICE_ROOT/postgres-root"
PG_BIN="$PG_ROOT/usr/lib/postgresql/18/bin"
PG_DATA="$SERVICE_ROOT/postgres"
PG_SOCKET="$SERVICE_ROOT/postgres-socket"
PY_DEPS="$SERVICE_ROOT/python-deps"
TLS_ROOT="$SERVICE_ROOT/tls"
ANDROID_CERT="$TLS_ROOT/android/server.pem"
ANDROID_KEY="$TLS_ROOT/android/server.key"
ANDROID_CA="$TLS_ROOT/android/ca.pem"
PG_CERT="$TLS_ROOT/postgres/server.pem"
PG_KEY="$TLS_ROOT/postgres/server.key"
PG_CA="$TLS_ROOT/postgres/ca.pem"
PROXY_PS1="$SCRIPT_DIR/gs179-windows-lan-proxy.ps1"
UNIT_PATH="$HOME/.config/systemd/user/gs179-laptop.service"
WINDOWS_TARGET_FILE="$STATE_ROOT/windows-wsl-target"
PG_PORT="55432"
APP_PORT="8444"

mkdir -p "$STATE_ROOT"
chmod 700 "$STATE_ROOT"

fail() { printf 'GS179_LOCAL_SERVER BLOCKED: %s\n' "$1" >&2; exit 2; }

windows_powershell() {
    local executable="/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
    [[ -x "$executable" ]] || fail "windows_powershell_executable_unavailable"
    "$executable" "$@"
}

load_config() {
    [[ -f "$ENV_FILE" ]] || fail "private_server_config_missing_run_provision"
    [[ "$(stat -c '%a' "$ENV_FILE")" == "600" ]] || fail "private_server_config_must_be_mode_600"
    # The provisioning command writes only shell-quoted values into this owner-only file.
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    export LD_LIBRARY_PATH="$PG_ROOT/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    export PYTHONPATH="$PY_DEPS:$REPO_ROOT/code/backend:$REPO_ROOT/code/validation:$REPO_ROOT/code/tools/sim"
    export GS179_ANDROID_CA="$ANDROID_CA"
    export GS179_LOCAL_PG_CA="$PG_CA"
}

wsl_ipv4() {
    ip -4 -o addr show dev eth0 | awk '{split($4, a, "/"); if (a[1] !~ /^127\./) {print a[1]; exit}}'
}

windows_wifi_address() {
    windows_powershell -NoProfile -Command 'Get-NetIPAddress -InterfaceAlias "Wi-Fi" -AddressFamily IPv4 | Where-Object { $_.AddressState -eq "Preferred" } | Select-Object -First 1 -ExpandProperty IPAddress' | tr -d '\r'
}

windows_wifi_name() {
    windows_powershell -NoProfile -Command 'Get-NetConnectionProfile -InterfaceAlias "Wi-Fi" | Select-Object -First 1 -ExpandProperty Name' | tr -d '\r'
}

pg_ctl_status() {
    LD_LIBRARY_PATH="$PG_ROOT/usr/lib/x86_64-linux-gnu" \
        "$PG_BIN/pg_ctl" -D "$PG_DATA" status >/dev/null 2>&1
}

pg_start() {
    [[ -x "$PG_BIN/pg_ctl" && -d "$PG_DATA" ]] || fail "postgres_runtime_or_cluster_missing_run_provision"
    mkdir -p "$PG_SOCKET"
    chmod 700 "$PG_SOCKET"
    if ! pg_ctl_status; then
        LD_LIBRARY_PATH="$PG_ROOT/usr/lib/x86_64-linux-gnu" \
        "$PG_BIN/pg_ctl" -D "$PG_DATA" \
            -l "$STATE_ROOT/postgres.log" \
            -o "-c listen_addresses=127.0.0.1 -c port=$PG_PORT -c unix_socket_directories=$PG_SOCKET -c ssl=on -c ssl_min_protocol_version=TLSv1.2 -c ssl_cert_file=$PG_CERT -c ssl_key_file=$PG_KEY -c hba_file=$TLS_ROOT/postgres/pg_hba.conf -c fsync=on -c synchronous_commit=on -c full_page_writes=on -c password_encryption=scram-sha-256 -c log_min_messages=warning -c log_statement=none" \
            -w start
    fi
    local attempt
    for attempt in $(seq 1 20); do
        if PG_SOCKET="$PG_SOCKET" PG_PORT="$PG_PORT" PG_USER="$USER" \
            python3 - <<'PY' >/dev/null 2>&1
import os
import psycopg
with psycopg.connect("host=" + os.environ["PG_SOCKET"] + " port=" +
                     os.environ["PG_PORT"] + " dbname=postgres user=" +
                     os.environ["PG_USER"], connect_timeout=2) as connection:
    settings = dict(connection.execute(
        "SELECT name, setting FROM pg_settings WHERE name IN ('fsync','synchronous_commit','full_page_writes')"
    ).fetchall())
    if settings != {"fsync": "on", "synchronous_commit": "on", "full_page_writes": "on"}:
        raise SystemExit("postgres_durability_settings_mismatch")
PY
        then
            return 0
        fi
        sleep 1
    done
    fail "postgres_not_ready_check_private_postgres_log"
}

proxy_start() {
    local current_wsl previous=""
    current_wsl="$(wsl_ipv4)"
    [[ "$current_wsl" =~ ^172\.(1[6-9]|2[0-9]|3[0-1])\.[0-9]{1,3}\.[0-9]{1,3}$ ]] || fail "wsl_nat_ipv4_unavailable"
    [[ -f "$WINDOWS_TARGET_FILE" ]] && previous="$(cat "$WINDOWS_TARGET_FILE")"
    local win_script
    win_script="$(wslpath -w "$PROXY_PS1")"
    windows_powershell -NoProfile -ExecutionPolicy Bypass -File "$win_script" \
        -Action Start -WifiAddress "$GS179_WINDOWS_WIFI_IPV4" \
        -WslAddress "$current_wsl" -PreviousWslAddress "$previous" \
        -ExpectedWifiName "$GS179_WIFI_NAME"
    printf '%s\n' "$current_wsl" > "$WINDOWS_TARGET_FILE"
    chmod 600 "$WINDOWS_TARGET_FILE"
}

proxy_stop() {
    [[ -f "$ENV_FILE" ]] || return 0
    load_config
    local current_wsl previous=""
    current_wsl="$(wsl_ipv4 || true)"
    [[ -f "$WINDOWS_TARGET_FILE" ]] && previous="$(cat "$WINDOWS_TARGET_FILE")"
    local win_script
    win_script="$(wslpath -w "$PROXY_PS1")"
    windows_powershell -NoProfile -ExecutionPolicy Bypass -File "$win_script" \
        -Action Stop -WifiAddress "$GS179_WINDOWS_WIFI_IPV4" \
        -WslAddress "$current_wsl" -PreviousWslAddress "$previous" \
        -ExpectedWifiName "$GS179_WIFI_NAME"
    rm -f "$WINDOWS_TARGET_FILE"
}

proxy_audit() {
    load_config
    local current_wsl="$(wsl_ipv4 || true)"
    local win_script
    win_script="$(wslpath -w "$PROXY_PS1")"
    windows_powershell -NoProfile -ExecutionPolicy Bypass -File "$win_script" \
        -Action Audit -WifiAddress "$GS179_WINDOWS_WIFI_IPV4" \
        -WslAddress "$current_wsl" -ExpectedWifiName "$GS179_WIFI_NAME"
}

provision() {
    mkdir -p "$SERVICE_ROOT" "$CONFIG_ROOT" "$STATE_ROOT"
    chmod 700 "$SERVICE_ROOT" "$CONFIG_ROOT" "$STATE_ROOT"
    if [[ -d "$PG_DATA" || -e "$ENV_FILE" ]]; then
        [[ -d "$PG_DATA" && -f "$ENV_FILE" ]] || \
            fail "partial_private_provisioning_state_found_preserve_and_inspect_manually"
        load_config
        [[ "$GS179_WINDOWS_WIFI_IPV4" == "192.168.1.6" &&
           -n "$GS179_WIFI_NAME" ]] || \
            fail "stored_wifi_identity_changed_recheck_before_resuming_provision"
        local resume_ip resume_name
        resume_ip="$(windows_wifi_address)"
        resume_name="$(windows_wifi_name)"
        [[ "$resume_ip" == "$GS179_WINDOWS_WIFI_IPV4" &&
           "$resume_name" == "$GS179_WIFI_NAME" ]] || \
            fail "observed_wifi_identity_changed_recheck_before_resuming_provision"
        pg_start
        bootstrap_database
        install_unit
        printf 'GS179_LOCAL_SERVER provisioning resumed without replacing private state\n'
        return 0
    fi
    [[ -f "$ANDROID_CA" && -f "$ANDROID_CERT" && -f "$ANDROID_KEY" && -f "$PG_CA" && -f "$PG_CERT" && -f "$PG_KEY" ]] || fail "local_test_tls_material_missing"
    [[ -d /tmp/gs179-pg-packages/root ]] || fail "previously_verified_postgresql_18_runtime_package_missing"
    [[ -f /tmp/gs179-python-deps/psycopg/__init__.py ]] || fail "previously_verified_psycopg_package_missing"

    if [[ ! -d "$PG_ROOT" ]]; then cp -a /tmp/gs179-pg-packages/root "$PG_ROOT"; fi
    mkdir -p "$PY_DEPS"
    if [[ ! -d "$PY_DEPS/psycopg" ]]; then cp -a /tmp/gs179-python-deps/psycopg "$PY_DEPS/"; fi
    if [[ ! -d "$PY_DEPS/psycopg-3.2.6.dist-info" ]]; then cp -a /tmp/gs179-python-deps/psycopg-3.2.6.dist-info "$PY_DEPS/"; fi
    python3 -m pip install --disable-pip-version-check --target "$PY_DEPS" \
        "gunicorn==23.0.0" "packaging==25.0" >/dev/null
    export LD_LIBRARY_PATH="$PG_ROOT/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    PYTHONPATH="$PY_DEPS" python3 -c 'import psycopg, gunicorn; print("python dependencies ready")'
    "$PG_BIN/initdb" --data-checksums -D "$PG_DATA" -U "$USER" \
        --auth-local=peer --auth-host=scram-sha-256 >/dev/null
    chmod 700 "$PG_DATA"

    cat > "$TLS_ROOT/postgres/pg_hba.conf" <<EOF
local all $USER peer
local all all reject
hostssl gs179_monitoring gs179_app 127.0.0.1/32 scram-sha-256
host all all 0.0.0.0/0 reject
host all all ::/0 reject
EOF
    chmod 600 "$TLS_ROOT/postgres/pg_hba.conf"
    local db_password
    db_password="$(python3 -c 'import secrets; print(secrets.token_urlsafe(36))')"
    local ip_config wifi_name
    ip_config="$(windows_wifi_address)"
    wifi_name="$(windows_wifi_name)"
    [[ "$ip_config" == "192.168.1.6" && -n "$wifi_name" ]] || fail "observed_wifi_identity_changed_recheck_before_provisioning"
    GS179_APP_DB_PASSWORD="$db_password" GS179_WINDOWS_WIFI_IPV4="$ip_config" GS179_WIFI_NAME="$wifi_name" \
        SERVICE_ROOT="$SERVICE_ROOT" TLS_ROOT="$TLS_ROOT" PG_SOCKET="$PG_SOCKET" \
        PG_PORT="$PG_PORT" CONFIG_ROOT="$CONFIG_ROOT" \
        python3 - <<'PY'
import os
from pathlib import Path
from urllib.parse import quote

password = os.environ["GS179_APP_DB_PASSWORD"]
ca = str(Path(os.environ["TLS_ROOT"]) / "postgres" / "ca.pem")
dsn = ("postgresql://gs179_app:" + quote(password, safe="") +
       "@127.0.0.1:" + os.environ["PG_PORT"] + "/gs179_monitoring?sslmode=verify-full&sslrootcert=" + quote(ca, safe="/"))
origin = "https://" + os.environ["GS179_WINDOWS_WIFI_IPV4"]
content = "\n".join((
    "export DATABASE_URL=" + repr(dsn),
    "export GS179_LOCAL_SERVER_DSN=" + repr(dsn),
    "export PUBLIC_ORIGIN=" + repr(origin),
    "export GS179_WINDOWS_WIFI_IPV4=" + repr(os.environ["GS179_WINDOWS_WIFI_IPV4"]),
    "export GS179_WIFI_NAME=" + repr(os.environ["GS179_WIFI_NAME"]),
    "export GS179_TEST_ONLY_MONITORING='1'",
    "export GS179_LOCAL_LAN_TEST_ONLY='1'",
    "export GS179_TEST_ONLY_HOME_PREFIX='gs177-test-'",
)) + "\n"
target = Path(os.environ["CONFIG_ROOT"]) / "server.env"
temp = target.with_suffix(".env.tmp")
fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as stream:
    stream.write(content)
    stream.flush()
    os.fsync(stream.fileno())
os.replace(temp, target)
target.chmod(0o600)
PY
    load_config
    pg_start
    bootstrap_database
    install_unit
    printf 'GS179_LOCAL_SERVER provisioned; secrets remain in %s and %s\n' "$CONFIG_ROOT" "$SERVICE_ROOT"
}

bootstrap_database() {
    PG_SOCKET="$PG_SOCKET" PG_PORT="$PG_PORT" PG_USER="$USER" \
        GS179_LOCAL_SERVER_DSN="$GS179_LOCAL_SERVER_DSN" \
        python3 - <<'PY'
import os
import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg import sql

fields = conninfo_to_dict(os.environ["GS179_LOCAL_SERVER_DSN"])
password = fields.get("password")
if not password:
    raise SystemExit("local_test_database_password_missing")
conn = psycopg.connect(
    "host=" + os.environ["PG_SOCKET"] + " port=" + os.environ["PG_PORT"] +
    " dbname=postgres user=" + os.environ["PG_USER"],
    autocommit=True,
)
try:
    role = conn.execute("SELECT 1 FROM pg_roles WHERE rolname='gs179_app'").fetchone()
    if role is None:
        conn.execute(sql.SQL("CREATE ROLE gs179_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}")
                     .format(sql.Literal(password)))
    db = conn.execute("SELECT 1 FROM pg_database WHERE datname='gs179_monitoring'").fetchone()
    if db is None:
        conn.execute("CREATE DATABASE gs179_monitoring OWNER gs179_app")
finally:
    conn.close()
PY
    GS179_LOCAL_SERVER_DSN="$GS179_LOCAL_SERVER_DSN" python3 - <<'PY'
import os
import psycopg
dsn = os.environ["GS179_LOCAL_SERVER_DSN"]
with psycopg.connect(dsn, connect_timeout=5) as connection:
    row = connection.execute(
        "SELECT current_database(), current_user, current_setting('fsync'), "
        "current_setting('synchronous_commit'), current_setting('full_page_writes')"
    ).fetchone()
    expected = ("gs179_monitoring", "gs179_app", "on", "on", "on")
    if row != expected:
        raise SystemExit("test_database_identity_or_durability_mismatch")
print("GS179_TEST_ONLY_POSTGRES_TLS_VERIFY_FULL=PASS durability=fsync,on;sync,on;full_page_writes,on")
PY
}

install_unit() {
    mkdir -p "$(dirname "$UNIT_PATH")"
    local script_path
    script_path="$(realpath "$SCRIPT_DIR/gs179-laptop-server.sh")"
    cat > "$UNIT_PATH" <<EOF
[Unit]
Description=Ghar Sajag GS-179 local TEST_ONLY PostgreSQL and caregiver HTTPS server
After=default.target
StartLimitIntervalSec=120
StartLimitBurst=4

[Service]
Type=simple
ExecStart=/bin/bash $script_path run
ExecStopPost=/bin/bash $script_path stop-post
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
UMask=0077

[Install]
WantedBy=default.target
EOF
    chmod 600 "$UNIT_PATH"
    systemctl --user daemon-reload
    systemctl --user enable gs179-laptop.service >/dev/null
}

run_service() {
    load_config
    pg_start
    local address
    address="$(wsl_ipv4)"
    [[ -n "$address" ]] || fail "wsl_ipv4_unavailable"
    cd "$REPO_ROOT/code/parivar_saathi_android_app/server"
    exec python3 -m gunicorn wsgi:application --workers 1 --threads 4 --timeout 30 \
        --bind "$address:$APP_PORT" --certfile "$ANDROID_CERT" --keyfile "$ANDROID_KEY" \
        --access-logfile - --error-logfile - \
        --access-logformat '%(t)s %(s)s %(D)s %(m)s %(U)s'
}

stop_post() {
    local service_result="${SERVICE_RESULT:-unknown}"
    if [[ "$service_result" != "success" ]]; then
        printf 'GS179_STOP_POST: service_result=%s; PostgreSQL left running for local recovery\n' "$service_result"
        return 0
    fi
    if [[ -x "$PG_BIN/pg_ctl" && -d "$PG_DATA" ]] && pg_ctl_status; then
        LD_LIBRARY_PATH="$PG_ROOT/usr/lib/x86_64-linux-gnu" \
            "$PG_BIN/pg_ctl" -D "$PG_DATA" -m fast -w stop
    fi
}

postgres_health_check() {
    if ! pg_ctl_status; then
        printf 'POSTGRES_READY=FAIL reason=server_not_running\n'
        return 1
    fi
    if ! GS179_LOCAL_SERVER_DSN="$GS179_LOCAL_SERVER_DSN" GS179_LOCAL_PG_CA="$GS179_LOCAL_PG_CA" \
        python3 - <<'PY' >/dev/null 2>&1
import os
from pathlib import Path
import psycopg
from psycopg.conninfo import conninfo_to_dict

dsn = os.environ["GS179_LOCAL_SERVER_DSN"]
fields = conninfo_to_dict(dsn)
expected_ca = Path(os.environ["GS179_LOCAL_PG_CA"]).resolve(strict=True)
if (fields.get("host") != "127.0.0.1" or fields.get("port") != "55432" or
        fields.get("dbname") != "gs179_monitoring" or fields.get("user") != "gs179_app" or
        fields.get("sslmode") != "verify-full" or
        Path(fields.get("sslrootcert", "")).resolve(strict=True) != expected_ca):
    raise SystemExit("local_postgres_identity_or_tls_config_mismatch")
with psycopg.connect(dsn, connect_timeout=3) as connection:
    connection.execute("SET TRANSACTION READ ONLY")
    actual = connection.execute(
        "SELECT current_database(), current_user, current_setting('fsync'), "
        "current_setting('synchronous_commit'), current_setting('full_page_writes'), "
        "(SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid())"
    ).fetchone()
if actual != ("gs179_monitoring", "gs179_app", "on", "on", "on", True):
    raise SystemExit("local_postgres_identity_tls_or_durability_check_failed")
PY
    then
        printf 'POSTGRES_READY=FAIL reason=verified_readiness_check_failed\n'
        return 1
    fi
    printf 'POSTGRES_READY=PASS tls=verify-full durability=fsync,synchronous_commit,full_page_writes\n'
}

local_https_health_check() {
    local address
    address="$(wsl_ipv4 || true)"
    if [[ -z "$address" ]]; then
        printf 'CAREGIVER_HTTPS_READY=FAIL reason=wsl_ipv4_unavailable\n'
        return 1
    fi
    if ! curl --fail --silent --show-error --connect-timeout 3 --max-time 8 \
        --cacert "$ANDROID_CA" --resolve "$GS179_WINDOWS_WIFI_IPV4:$APP_PORT:$address" \
        "https://$GS179_WINDOWS_WIFI_IPV4:$APP_PORT/readyz"; then
        printf 'CAREGIVER_HTTPS_READY=FAIL reason=local_tls_readiness_failed\n'
        return 1
    fi
    printf '\nCAREGIVER_HTTPS_READY=PASS tls=ca_and_ip_san_verified\n'
}

phone_lan_health_check() {
    local observed_ip observed_name
    observed_ip="$(windows_wifi_address 2>/dev/null || true)"
    observed_name="$(windows_wifi_name 2>/dev/null || true)"
    if [[ -z "$observed_ip" || -z "$observed_name" ]]; then
        printf 'PHONE_LAN_REACHABLE=UNKNOWN reason=windows_wifi_read_unavailable\n'
        return 0
    fi
    if [[ "$observed_ip" != "$GS179_WINDOWS_WIFI_IPV4" ]]; then
        printf 'PHONE_LAN_REACHABLE=BLOCKED_CONFIG_MISMATCH expected_address=%s observed_address=%s\n' \
            "$GS179_WINDOWS_WIFI_IPV4" "$observed_ip"
        return 0
    fi
    if [[ "$observed_name" != "$GS179_WIFI_NAME" ]]; then
        printf 'PHONE_LAN_REACHABLE=BLOCKED_CONFIG_MISMATCH reason=wifi_identity_mismatch\n'
        return 0
    fi
    if curl --fail --silent --show-error --connect-timeout 3 --max-time 8 \
        --cacert "$ANDROID_CA" "https://$GS179_WINDOWS_WIFI_IPV4/readyz"; then
        printf '\nPHONE_LAN_REACHABLE=PASS tls=ca_and_ip_san_verified\n'
    else
        printf 'PHONE_LAN_REACHABLE=FAIL reason=existing_windows_forwarding_or_endpoint_unavailable\n'
    fi
    return 0
}

health_check() {
    load_config
    local local_ready=0
    if postgres_health_check; then :; else local_ready=1; fi
    if local_https_health_check; then :; else local_ready=1; fi
    if (( local_ready == 0 )); then
        printf 'LOCAL_BACKEND_READY=PASS\n'
    else
        printf 'LOCAL_BACKEND_READY=FAIL\n'
    fi
    phone_lan_health_check
    printf 'HUB_INGRESS_READY=NOT_CONFIGURED (caregiver service has no active authenticated Hub ingress)\n'
    return "$local_ready"
}

wait_for_local_backend() {
    local attempt
    for attempt in $(seq 1 30); do
        if postgres_health_check >/dev/null 2>&1 && local_https_health_check >/dev/null 2>&1; then
            return 0
        fi
        if (( attempt < 30 )); then sleep 1; fi
    done
    printf 'GS179_STARTUP_READINESS: local PostgreSQL/caregiver HTTPS did not become ready within 30 seconds\n' >&2
    return 1
}

start_service() {
    load_config
    systemctl --user reset-failed gs179-laptop.service
    systemctl --user start gs179-laptop.service
    wait_for_local_backend || { health_check || true; return 1; }
    health_check
}

restart_service() {
    load_config
    systemctl --user reset-failed gs179-laptop.service
    systemctl --user restart gs179-laptop.service
    wait_for_local_backend || { health_check || true; return 1; }
    health_check
}

run_event() {
    load_config
    export GS179_LOCAL_PERSISTENT_POSTGRES=1
    export GS179_LOCAL_SERVER_DSN="$GS179_LOCAL_SERVER_DSN"
    python3 "$REPO_ROOT/code/tools/local/gs179_laptop_node_event.py"
}

run_health_source() {
    load_config
    export GS179_LOCAL_PERSISTENT_POSTGRES=1
    python3 "$REPO_ROOT/code/tools/local/gs179_laptop_node_event.py" --health-only
}

change_login() {
    load_config
    export GS179_CAREGIVER_CREDENTIALS="${GS179_CAREGIVER_CREDENTIALS:-$STATE_ROOT/caregiver-login.json}"
    python3 "$REPO_ROOT/code/tools/local/gs179_change_login.py"
}

run_caregiver_browser() {
    load_config
    python3 "$REPO_ROOT/code/tools/local/gs179_laptop_browser.py"
}

case "${1:-}" in
    provision) provision ;;
    install-unit) install_unit ;;
    start) start_service ;;
    stop) systemctl --user stop gs179-laptop.service ;;
    restart) restart_service ;;
    status)
        systemctl --user status --no-pager gs179-laptop.service || true
        if [[ -x "$PG_BIN/pg_ctl" && -d "$PG_DATA" ]]; then
            LD_LIBRARY_PATH="$PG_ROOT/usr/lib/x86_64-linux-gnu" "$PG_BIN/pg_ctl" -D "$PG_DATA" status || true
        fi
        ;;
    health) health_check ;;
    logs) journalctl --user-unit=gs179-laptop.service --no-pager -n "${2:-100}" ;;
    event) run_event ;;
    change-login) change_login ;;
    browser) run_caregiver_browser ;;
    run) run_service ;;
    proxy-start) load_config; proxy_start ;;
    stop-post) stop_post ;;
    health-source) run_health_source ;;
    proxy-audit) proxy_audit ;;
    *) printf 'Usage: %s {provision|install-unit|start|stop|restart|status|health|proxy-audit|logs [N]|event|health-source|browser|change-login}\n' "$0"; exit 2 ;;
esac
