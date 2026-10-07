# Ghar Sajag USB zero-touch setup

One authoritative implementation: `install-gs-usb-zero-touch.ps1` installs
`gs-usb-autowatch.ps1` and its shared helpers into `C:\ProgramData\GharSajag`.
No board firmware, storage, reset, flashing or serial commands are involved.
The watcher **does attach USB devices** when installed: stop physical qualification
programs before the one-time installation.

## One-time installation

Prerequisites: Windows account owning Ubuntu must be an administrator; Ubuntu
WSL2 must exist with a normal default user, Python 3, `udev` and `dialout` group;
[usbipd-win 4 or newer](https://learn.microsoft.com/en-us/windows/wsl/connect-usb)
must already be installed. Run in **Administrator PowerShell**, under that account:

```powershell
powershell -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu\home\udaybhan\projects\Ghar_sajag_r1\tools\usb\install-gs-usb-zero-touch.ps1"
```

The installer reads the distro component of the UNC path directly; it never
passes a WSL UNC path through `wslpath` or invents a C: path. Paths with spaces
are supported. Reinstall replaces the same task after stopping it, rewrites
managed shell blocks instead of appending duplicates, and preserves unrelated
`wsl.conf` settings and an existing boot command. Partial failures are explicit;
rerun after resolving the reported prerequisite. An externally changed boot
command requires review before reinstall, rather than silently overwriting it.

Task `GharSajag-USB-ZeroTouch` runs at that user's logon with highest privileges,
starts immediately, and restarts on unexpected exit. It does not use SYSTEM,
which would lose access to the user's distro. Installed scripts are protected
from ordinary-user writes. Changing Windows accounts requires installation
under the new account. No user password is stored.

## Everyday use

Connect Hub, connect Node, open WSL, work. New Bash, Zsh and Fish shells get:

```sh
GS_HUB_PORT=/dev/ghar-sajag-hub
GS_NODE_PORT=/dev/ghar-sajag-node
```

Use `"$GS_HUB_PORT"` and `"$GS_NODE_PORT"` in HIL commands. Existing shells retain
their old environment/group membership; open a new shell after installation.
`gs-usb-status` reports alias targets or `MISSING`. Missing boards do not fail
installation. It never opens a serial port.

## State and recovery

The watcher parses official `usbipd state` JSON, rediscovering connected BUSIDs
on every pass. Not shared -> bind -> confirmed Shared -> start Ubuntu/udev ->
attach -> confirmed Attached. An Attached device is left alone. Disconnects,
reconnects and WSL shutdowns are handled by subsequent discovery. It checks
identity/BUSID again before acting, rejects ambiguous identical-role devices,
and fails closed on malformed state. One global mutex and Task Scheduler
IgnoreNew prevent concurrent watchers. Errors back off 30–300 seconds; identical
states/errors are not logged repeatedly. Logs rotate at 2 MB:
`C:\ProgramData\GharSajag\usb-watch.log` and `.1`.

When Node is absent and Windows lists `0000:0002`, the watcher records
`NODE_ENUMERATION_FAILED` once and does not bind/attach that device. This is a
possible Node descriptor failure; that PID alone cannot identify which physical
device failed. Normal `303a:1001` enumeration resumes automatic attachment.
Automation cannot repair a descriptor that Windows cannot read.

There is **no automatic EIO detach/re-attach**. Metadata cannot distinguish a
sleeping C3, firmware USB failure, an application holding an old descriptor, or
a transport failure. Detaching can interrupt active flashing/HIL and does not
repair firmware. Healthy Attached devices never flap. Applications must reopen
a stale serial descriptor after genuine reconnect; alias stability cannot keep
an already-open file descriptor alive.

udev matches Hub `10c4:ea60`, Node `303a:1001` CDC serial interface `00`, imports
USB interface properties and creates stable aliases with dialout access.
Ubuntu udev is started on WSL boot and before attachment, including non-systemd
WSL setups. No tty number is hardcoded. One Hub and one Node are supported;
multiple boards with the same VID/PID require explicit serial-number mapping
(not automatic guessing). Other serial devices are ignored.

## Verification and retirement of older setup

Installer verifies WSL rules, new-shell variables, dialout membership, task
registration/highest privileges and running state. Hardware-specific attachment
is not an installation gate. Offline tests do not replace Windows installation
or real reconnect qualification.

Do not install a second startup watcher. The old downloaded watcher is replaced
in-place by this implementation and the same scheduled-task name. There are no
`gs-usbipd.ps1` or `gs-usb-ready.sh` files here. The existing
`tools/hil/ensure-usb-attached.ps1` is a legacy **one-shot** compatibility helper,
not a startup service; use the stable variables for normal work instead of
running it alongside the watcher. Zone.Identifier download metadata is retained.

Uninstall from Administrator PowerShell using the adjacent
`uninstall-gs-usb-zero-touch.ps1`. It removes the task, managed aliases/environment
and boot hook, restoring the previous boot command. It preserves logs, dialout
membership and usbipd's persistent shares and never detaches boards.

## Offline tests

```sh
python3 -m unittest discover -s tools/usb/tests -p 'test_*.py'
bash -n tools/usb/install-gs-wsl-usb.sh
```

Windows PowerShell (no hardware operations; installer OS boundaries mocked):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu\home\udaybhan\projects\Ghar_sajag_r1\tools\usb\tests\test-usb-automation.ps1"
```

JSON fields follow [official usbipd automation source](https://github.com/dorssel/usbipd-win/blob/master/Usbipd.Automation/Device.cs),
not localized `usbipd list` text.
