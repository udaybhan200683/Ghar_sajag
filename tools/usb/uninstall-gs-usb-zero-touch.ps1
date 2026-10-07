param([string]$WslDistro = 'Ubuntu')
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\gs-usb-common.ps1"
Assert-GsAdministrator
$programDir = Join-Path $env:ProgramData 'GharSajag'
$config = Get-Content (Join-Path $programDir 'config.json') -Raw | ConvertFrom-Json
$WslDistro = $config.WslDistro
$task = Get-ScheduledTask -TaskName 'GharSajag-USB-ZeroTouch' -ErrorAction SilentlyContinue
if ($task) {
    Stop-ScheduledTask -TaskName $task.TaskName
    Unregister-ScheduledTask -TaskName $task.TaskName -Confirm:$false
}
$script = @'
set -eu
home=$(getent passwd "$1" | cut -d: -f6)
/usr/local/sbin/gs-usb-wsl-config --home "$home" --remove
rm -f /usr/local/bin/gs-usb-status /usr/local/sbin/gs-usb-boot /usr/local/sbin/gs-usb-udev-start /usr/local/sbin/gs-usb-wsl-config
udevadm control --reload-rules
'@
$result = Invoke-GsWsl -Distro $WslDistro -AsRoot -LinuxArgs @('/bin/bash','-s','--',$config.WslUser) -InputText $script
Assert-GsNativeResult $result 'WSL uninstall'
foreach ($file in @('gs-usb-autowatch.ps1','gs-usb-common.ps1','config.json')) { Remove-Item (Join-Path $programDir $file) -Force -ErrorAction SilentlyContinue }
Write-Host 'Removed watcher and managed WSL configuration. Existing USB shares, dialout membership and logs preserved; no detach performed.'
