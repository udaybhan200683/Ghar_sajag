param([switch]$Watch, [string]$WslDistro = 'Ubuntu', [ValidateRange(2,60)][int]$IntervalSec = 2)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'gs-usb-common.ps1')
Assert-GsAdministrator
# A second launch exits rather than competing with the scheduled watcher.
$mutex = New-Object Threading.Mutex($false, 'Global\GharSajag-USB-ZeroTouch')
$locked = $false
try {
    try { $locked = $mutex.WaitOne(0) } catch [Threading.AbandonedMutexException] { $locked = $true }
    if (-not $locked) { exit 0 }
    $configPath = Join-Path $PSScriptRoot 'config.json'
    if (Test-Path $configPath) {
        $config = Get-Content -Raw $configPath | ConvertFrom-Json
        $WslDistro = $config.WslDistro
        $IntervalSec = $config.IntervalSec
    }
    $logPath = Join-Path $PSScriptRoot 'usb-watch.log'
    $logger = {
        param($message)
        if ((Test-Path $logPath) -and (Get-Item $logPath).Length -gt 2MB) {
            Move-Item -Force $logPath "$logPath.1"
        }
        Add-Content -Encoding UTF8 $logPath "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $message"
    }
    $readRows = {
        $result = Invoke-GsNative 'usbipd.exe' @('state')
        Assert-GsNativeResult $result 'usbipd state'
        ConvertFrom-GsUsbState $result.StdOut
    }
    $runUsbipd = {
        param([string[]]$commandArgs)
        $result = Invoke-GsNative 'usbipd.exe' $commandArgs
        Assert-GsNativeResult $result ('usbipd ' + ($commandArgs -join ' '))
    }
    $startWsl = {
        # This starts the specified distro and its udev daemon, not a serial console.
        $result = Invoke-GsWsl -Distro $WslDistro -AsRoot -LinuxArgs @('/usr/local/sbin/gs-usb-udev-start')
        Assert-GsNativeResult $result 'WSL startup/udev'
    }
    $context = New-GsWatchContext
    & $logger "START distro=$WslDistro interval=${IntervalSec}s"
    do {
        Invoke-GsWatchPass $context $readRows $runUsbipd $startWsl $logger
        if ($Watch) { Start-Sleep -Seconds $IntervalSec }
    } while ($Watch)
} finally {
    if ($locked) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
