#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'WSL setup requires root' >&2; exit 2; }
TARGET_USER=${1:?usage: install-gs-wsl-usb.sh USER}
[[ $TARGET_USER != root ]] || { echo 'Refusing root as interactive WSL user' >&2; exit 2; }
TARGET_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f6)
[[ -n $TARGET_HOME && -d $TARGET_HOME ]] || { echo 'Unknown WSL user/home' >&2; exit 2; }
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
command -v python3 >/dev/null
command -v udevadm >/dev/null || { echo 'Install Ubuntu udev first' >&2; exit 2; }
getent group dialout >/dev/null

# Install files only. No serial reads/writes, board resets or USB detach.
install -m 0755 "$SCRIPT_DIR/gs-usb-wsl-config.py" /usr/local/sbin/gs-usb-wsl-config
cat >/usr/local/sbin/gs-usb-udev-start <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
if udevadm control --reload-rules >/dev/null 2>&1; then exit 0; fi
if [[ -d /run/systemd/system ]]; then
  systemctl start systemd-udevd.service
else
  daemon=/usr/lib/systemd/systemd-udevd
  [[ -x $daemon ]] || daemon=/lib/systemd/systemd-udevd
  "$daemon" --daemon
fi
udevadm control --reload-rules
# Restore aliases for devices already present when the daemon was absent.
udevadm trigger --action=add --subsystem-match=tty
udevadm settle --timeout=10
SCRIPT
chmod 0755 /usr/local/sbin/gs-usb-udev-start
cat >/usr/local/sbin/gs-usb-boot <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
/usr/local/sbin/gs-usb-udev-start
previous=$(python3 -c 'import json; print(json.load(open("/etc/ghar-sajag-usb/install-state.json"))["previous_boot_command"])')
if [[ -n $previous ]]; then exec /bin/sh -c "$previous"; fi
SCRIPT
chmod 0755 /usr/local/sbin/gs-usb-boot
python3 /usr/local/sbin/gs-usb-wsl-config --home "$TARGET_HOME"
usermod -aG dialout "$TARGET_USER"
chown "$TARGET_USER:$(id -gn "$TARGET_USER")" "$TARGET_HOME/.bashrc" "$TARGET_HOME/.profile" "$TARGET_HOME/.zshenv" "$TARGET_HOME/.config/fish/conf.d/ghar-sajag-usb.fish"
for profile in .bash_profile .bash_login; do
  if [[ -f "$TARGET_HOME/$profile" ]]; then chown "$TARGET_USER:$(id -gn "$TARGET_USER")" "$TARGET_HOME/$profile"; fi
done
cat >/usr/local/bin/gs-usb-status <<'SCRIPT'
#!/usr/bin/env bash
set -u
for role in Hub Node; do
  alias_path="/dev/ghar-sajag-${role,,}"
  target=MISSING
  if [[ -L $alias_path && -c $alias_path ]]; then target=$(readlink -f "$alias_path"); fi
  printf '%-4s: %s -> %s\n' "$role" "$alias_path" "$target"
done
SCRIPT
chmod 0755 /usr/local/bin/gs-usb-status
/usr/local/sbin/gs-usb-udev-start
udevadm control --reload-rules
udevadm trigger --action=add --subsystem-match=tty
udevadm settle --timeout=10
[[ -s /etc/udev/rules.d/99-ghar-sajag-usb.rules && -s /etc/profile.d/ghar-sajag-usb.sh ]]
# Check the target user's new shell, not the installing root shell.
runuser -u "$TARGET_USER" -- bash -ic 'test "$GS_HUB_PORT" = /dev/ghar-sajag-hub && test "$GS_NODE_PORT" = /dev/ghar-sajag-node' </dev/null
id -nG "$TARGET_USER" | tr ' ' '\n' | grep -qx dialout
echo "WSL_USB_SETUP_OK user=$TARGET_USER"
/usr/local/bin/gs-usb-status
