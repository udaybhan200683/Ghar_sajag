param([string]$WslDistro = 'Ubuntu', [ValidateRange(2,60)][int]$IntervalSec = 2)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\gs-usb-common.ps1"
Assert-GsAdministrator
$TaskName = 'GharSajag-USB-ZeroTouch'
foreach ($tool in @('wsl.exe','usbipd.exe')) { Get-Command $tool -ErrorAction Stop | Out-Null }
$distro = @(Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss' | Get-ItemProperty | Where-Object { $_.DistributionName -eq $WslDistro })
if ($distro.Count -ne 1 -or $distro[0].Version -ne 2) { throw 'Requested distro must be WSL2, installed under this Windows account.' }
$version = Invoke-GsNative usbipd.exe @('--version')
Assert-GsNativeResult $version 'usbipd version'
if ($version.StdOut -notmatch '(\d+)\.\d+\.\d+' -or [int]$Matches[1] -lt 4) { throw 'Install usbipd-win 4 or newer first.' }
$identity = Invoke-GsWsl -Distro $WslDistro -LinuxArgs @('id','-un')
Assert-GsNativeResult $identity 'WSL user detection'
$wslUser = $identity.StdOut.Trim()
if ($wslUser -eq 'root' -or $wslUser -notmatch '^[a-z_][a-z0-9_-]*$') { throw 'Set a normal default WSL user before installing.' }
$linuxInstaller = ConvertTo-GsWslPath (Join-Path $PSScriptRoot 'install-gs-wsl-usb.sh') $WslDistro
Write-Host "Installing WSL aliases for $wslUser..."
$result = Invoke-GsWsl -Distro $WslDistro -AsRoot -LinuxArgs @('/bin/bash','-s','--',$linuxInstaller,$wslUser) -InputText 'exec /bin/bash "$1" "$2"' -TimeoutSec 90
Assert-GsNativeResult $result 'WSL USB setup'
Write-Host $result.StdOut.Trim()
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Stop-ScheduledTask -TaskName $TaskName
    for ($attempt=0; $attempt -lt 20; $attempt++) {
        if ((Get-ScheduledTask -TaskName $TaskName).State -ne 'Running') { break }
        Start-Sleep -Milliseconds 500
    }
    if ((Get-ScheduledTask -TaskName $TaskName).State -eq 'Running') { throw 'Old watcher did not stop; refusing competing watcher.' }
}
$programDir = Join-Path $env:ProgramData 'GharSajag'
New-Item -ItemType Directory -Force $programDir | Out-Null
# Elevated task scripts must not be writable by ordinary accounts.
$aclResult = Invoke-GsNative icacls.exe @($programDir,'/inheritance:r','/grant:r','*S-1-5-18:(OI)(CI)F','*S-1-5-32-544:(OI)(CI)F')
Assert-GsNativeResult $aclResult 'Watcher directory protection'
foreach ($file in @('gs-usb-common.ps1','gs-usb-autowatch.ps1')) { Copy-Item -Force (Join-Path $PSScriptRoot $file) $programDir }
@{ WslDistro=$WslDistro; IntervalSec=$IntervalSec; WslUser=$wslUser } | ConvertTo-Json | Set-Content (Join-Path $programDir 'config.json') -Encoding UTF8
$watcherTarget = Join-Path $programDir 'gs-usb-autowatch.ps1'
$currentUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File ' + (Quote-GsNativeArgument $watcherTarget) + ' -Watch')
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $currentUser
$principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval ([TimeSpan]::FromMinutes(1))
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Ghar Sajag USB zero-touch watcher (one Hub and one Node).' -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 3
$installed = Get-ScheduledTask -TaskName $TaskName
if ($installed.State -ne 'Running' -or $installed.Principal.RunLevel -ne 'Highest') { throw 'Watcher self-verification failed; inspect Task Scheduler and usb-watch.log.' }
Write-Host "ZERO_TOUCH_INSTALL_COMPLETE task=$TaskName user=$wslUser"
Write-Host "Log: $programDir\usb-watch.log"
Write-Host 'New shells: GS_HUB_PORT=/dev/ghar-sajag-hub GS_NODE_PORT=/dev/ghar-sajag-node'
Write-Host 'Absent boards / MISSING aliases are not installation failures.'
