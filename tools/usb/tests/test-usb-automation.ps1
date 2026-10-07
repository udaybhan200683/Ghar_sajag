$ErrorActionPreference='Stop'
. "$PSScriptRoot\..\gs-usb-common.ps1"
$count=0
function Check($value,$name) { if (-not $value) { throw "FAIL $name" }; $script:count++ }
function Device($vid='10C4',$pidValue='EA60',$state='Not shared',$bus='1-3') {
    [pscustomobject]@{ BusId=$bus; InstanceId="USB\VID_${vid}&PID_${pidValue}\board"; Description='board'; PersistedGuid=$(if($state -ne 'Not shared'){'12345678-1234-1234-1234-123456789abc'}else{$null}); ClientIPAddress=$(if($state -eq 'Attached'){'172.20.1.2'}else{$null}) }
}
function Setup($devices) {
    $script:mock=@{ Devices=@($devices); Commands=[Collections.Generic.List[string]]::new(); Logs=[Collections.Generic.List[string]]::new(); Starts=0; FailStart=$false; Malformed=$false }
    $script:ctx=New-GsWatchContext
}
$read={ if($mock.Malformed){ throw 'bad JSON' }; ConvertFrom-GsUsbState (ConvertTo-Json -Depth 5 -InputObject @{Devices=@($mock.Devices)}) }
$run={ param($CommandArgs) $mock.Commands.Add(($CommandArgs -join ' ')); foreach($d in $mock.Devices){ if($d.BusId -eq $CommandArgs[-1]){ if($CommandArgs[0] -eq 'bind'){$d.PersistedGuid='12345678-1234-1234-1234-123456789abc'}else{$d.ClientIPAddress='172.20.1.2'} } } }
$start={ $mock.Starts++; if($mock.FailStart){throw 'WSL unavailable'} }
$log={param($line) $mock.Logs.Add($line)}
function Pass([datetime]$at=[datetime]::UtcNow) { Invoke-GsWatchPass $ctx $read $run $start $log $at }
Setup @(Device); Pass
Check (($mock.Commands -join ';') -eq 'bind --busid 1-3;attach --wsl --busid 1-3') 'not shared binds then attaches'
Setup @(Device -state Shared); Pass
Check ($mock.Commands.Count -eq 1 -and $mock.Commands[0] -eq 'attach --wsl --busid 1-3') 'shared attaches'
Setup @(Device -state Attached); Pass
Check ($mock.Commands.Count -eq 0 -and $mock.Starts -eq 0) 'attached left alone'
$mock.Devices=@(Device -state Shared -bus '2-7'); Pass
Check ($mock.Commands[0] -eq 'attach --wsl --busid 2-7') 'BUSID rediscovered'
Setup @(Device -vid 303A -pidValue 1001); Pass
Check ($mock.Commands.Count -eq 2) 'normal node'
Setup @(Device -vid '0000' -pidValue '0002'); Pass
$n=$mock.Logs.Count; Pass
Check ($mock.Commands.Count -eq 0 -and $mock.Logs.Count -eq $n -and ($mock.Logs -join ' ') -match 'NODE_ENUMERATION_FAILED') 'descriptor failure quiet'
$mock.Devices=@(Device -vid 303A -pidValue 1001); Pass
Check ($mock.Commands.Count -eq 2) 'descriptor recovery'
Setup @(Device -state Shared); $mock.FailStart=$true; $at=[datetime]::UtcNow; Pass $at; $n=$mock.Logs.Count; Pass ($at.AddSeconds(2))
Check ($mock.Commands.Count -eq 0 -and $mock.Starts -eq 1 -and $mock.Logs.Count -eq $n) 'WSL failure backs off'
$mock.FailStart=$false; Pass ($at.AddSeconds(31))
Check ($mock.Commands.Count -eq 1) 'WSL recovery'
Setup @(); $mock.Malformed=$true; Pass; $n=$mock.Logs.Count; Pass
Check ($mock.Commands.Count -eq 0 -and $mock.Logs.Count -eq $n) 'malformed output quiet fail closed'
Setup @((Device),(Device -bus '2-2')); Pass
Check ($mock.Commands.Count -eq 0) 'duplicate role fail safe'
$rejected=$false; try{ConvertFrom-GsUsbState '{"Devices":[{}]}' | Out-Null}catch{$rejected=$true}; Check $rejected 'invalid JSON schema'
Check ((ConvertTo-GsWslPath '\\wsl.localhost\Ubuntu\home\udaybhan\projects\Ghar_sajag_r1\tools\usb\install-gs-wsl-usb.sh' Ubuntu) -eq '/home/udaybhan/projects/Ghar_sajag_r1/tools/usb/install-gs-wsl-usb.sh') 'UNC exact invocation'
Check ((ConvertTo-GsWslPath '\\wsl$\Ubuntu\home\a b\script.sh' Ubuntu) -eq '/home/a b/script.sh') 'UNC spaces'
$rejected=$false; try{ConvertTo-GsWslPath 'C:\bad' Ubuntu | Out-Null}catch{$rejected=$true}; Check $rejected 'no Windows fallback'
Check ((Quote-GsNativeArgument 'a b') -eq '"a b"') 'native spaces quoted'
foreach($file in Get-ChildItem "$PSScriptRoot\..\*.ps1") {
    $tokens=$null; $errors=$null
    [Management.Automation.Language.Parser]::ParseFile($file.FullName,[ref]$tokens,[ref]$errors) | Out-Null
    Check ($errors.Count -eq 0) "PowerShell parse $($file.Name)"
}
Setup @(Device -state Shared)
$raceStart={ $mock.Starts++; $mock.Devices=@(Device -state Shared -bus '9-9') }
Invoke-GsWatchPass $ctx $read $run $raceStart $log
Check ($mock.Commands.Count -eq 0) 'BUSID race never attaches replacement'
Setup @(Device -state Attached); Pass; $mock.Devices=@(); Pass
$mock.Devices=@(Device -state Shared -bus '7-7'); Pass
Check ($mock.Commands.Count -eq 1 -and $mock.Commands[0] -match '7-7') 'disconnect reconnect'
Check ((Quote-GsNativeArgument 'path\') -eq 'path\') 'plain native argument remains bare'
Check ((Quote-GsNativeArgument '-d') -eq '-d') 'WSL option remains bare'
& {
    $wslCaptures=[Collections.Generic.List[object]]::new()
    function Invoke-GsNative {
        param($FilePath,$NativeArgs,$InputText,$TimeoutSec)
        $wslCaptures.Add([pscustomobject]@{FilePath=$FilePath; Args=@($NativeArgs); InputText=$InputText})
        [pscustomobject]@{ExitCode=0;StdOut='ok';StdErr=''}
    }
    Invoke-GsWsl -Distro Ubuntu -LinuxArgs @('id','-un') | Out-Null
    Invoke-GsWsl -Distro Ubuntu -LinuxArgs @('/bin/true') | Out-Null
    Invoke-GsWsl -Distro Ubuntu -AsRoot -LinuxArgs @('/bin/true') | Out-Null
    Invoke-GsWsl -Distro Ubuntu -LinuxArgs @('/bin/bash','-lc','printf "%s" "hello world"') | Out-Null
    $linuxPath=ConvertTo-GsWslPath '\\wsl.localhost\Ubuntu\home\a b\odd"name\script.sh' Ubuntu
    Invoke-GsWsl -Distro Ubuntu -AsRoot -LinuxArgs @('/bin/bash','-s','--',$linuxPath,'udaybhan') -InputText 'exec /bin/bash "$1" "$2"' | Out-Null
    Invoke-GsWsl -Distro 'Ubuntu Preview' -LinuxArgs @('/bin/bash','-lc','printf "a b"') | Out-Null
    Check (($wslCaptures[0].Args -join '|') -eq '-d|Ubuntu|--exec|id|-un') 'user-detection argv'
    Check (($wslCaptures[1].Args -join '|') -eq '-d|Ubuntu|--exec|/bin/true') 'true argv'
    Check (($wslCaptures[2].Args -join '|') -eq '-d|Ubuntu|-u|root|--exec|/bin/true') 'root argv'
    Check ($wslCaptures[3].Args[3] -eq '/bin/bash' -and $wslCaptures[3].Args[4] -eq '-lc' -and
        $wslCaptures[3].Args[5] -eq 'printf "%s" "hello world"' -and
        $wslCaptures[3].Args[0] -eq '-d') 'bash payload follows WSL options'
    Check ($wslCaptures[4].Args[8] -eq $linuxPath -and $wslCaptures[4].InputText -eq 'exec /bin/bash "$1" "$2"') 'UNC spaces and quote preserved'
    Check ((($wslCaptures[0].Args | ForEach-Object { Quote-GsNativeArgument $_ }) -join ' ') -eq '-d Ubuntu --exec id -un') 'actual command-line serialization'
    Check (($wslCaptures[5].Args -join '|') -eq '-d|Ubuntu Preview|--exec|/bin/bash|-lc|printf "a b"') 'distro and Bash payload spaces'
    Check ((($wslCaptures[5].Args | ForEach-Object { Quote-GsNativeArgument $_ }) -join ' ') -eq '-d "Ubuntu Preview" --exec /bin/bash -lc "printf \"a b\""') 'quoted native payload serialization'
}
Write-Output "USB_OFFLINE_PASS checks=$count (mocks only; no USB commands executed)"
# Run the real installer body twice with ALL OS boundaries replaced by mocks.
# No Task Scheduler, registry, filesystem install, WSL or usbipd operation runs.
& {
    $installMock=@{Task=$null; Registrations=0; Stops=0; Starts=0; AdminChecks=0; Paths=[Collections.Generic.List[string]]::new(); WslCalls=[Collections.Generic.List[object]]::new()}
    function Assert-GsAdministrator { $installMock.AdminChecks++ }
    function Get-Command { param($Name,$ErrorAction) [pscustomobject]@{Name=$Name} }
    function Get-ChildItem { param($Path) [pscustomobject]@{DistributionName='Ubuntu';Version=2} }
    function Get-ItemProperty { process { $_ } }
    function Invoke-GsNative {
        param($FilePath,$NativeArgs,$InputText,$TimeoutSec)
        $out=if($FilePath -eq 'usbipd.exe'){'usbipd-win 5.0.0'}elseif($NativeArgs -contains 'id'){'udaybhan'}else{'WSL_USB_SETUP_OK'}
        if($FilePath -eq 'wsl.exe') { $installMock.WslCalls.Add([pscustomobject]@{Args=@($NativeArgs);InputText=$InputText}) }
        if($NativeArgs -contains '/bin/bash'){ $installMock.Paths.Add(($NativeArgs -join ' ')) }
        [pscustomobject]@{ExitCode=0;StdOut=$out;StdErr=''}
    }
    function Get-ScheduledTask { param($TaskName,$ErrorAction) $installMock.Task }
    function Stop-ScheduledTask { param($TaskName) $installMock.Stops++; $installMock.Task.State='Ready' }
    function New-Item { param($ItemType,[switch]$Force,$Path) }
    function Copy-Item { param([switch]$Force,$Path,$Destination) }
    function Set-Content { param($Path,$Encoding) process {} }
    function New-ScheduledTaskAction { param($Execute,$Argument) @{Execute=$Execute;Argument=$Argument} }
    function New-ScheduledTaskTrigger { param([switch]$AtLogOn,$User) @{User=$User} }
    function New-ScheduledTaskPrincipal { param($UserId,$LogonType,$RunLevel) @{RunLevel=$RunLevel} }
    function New-ScheduledTaskSettingsSet { param([switch]$AllowStartIfOnBatteries,[switch]$DontStopIfGoingOnBatteries,[switch]$StartWhenAvailable,$MultipleInstances,$ExecutionTimeLimit,$RestartCount,$RestartInterval) @{} }
    function Register-ScheduledTask {
        param($TaskName,$Action,$Trigger,$Principal,$Settings,$Description,[switch]$Force)
        $installMock.Registrations++
        $installMock.Task=[pscustomobject]@{State='Ready';Principal=[pscustomobject]$Principal}
    }
    function Start-ScheduledTask { param($TaskName) $installMock.Starts++; $installMock.Task.State='Running' }
    function Start-Sleep { param($Seconds,$Milliseconds) }
    $source=Get-Content "$PSScriptRoot\..\install-gs-usb-zero-touch.ps1" -Raw
    $source=$source.Replace('. "$PSScriptRoot\gs-usb-common.ps1"','# common helpers supplied by test')
    $source=$source.Replace('$PSScriptRoot', ('"' + (Split-Path $PSScriptRoot -Parent) + '"'))
    $installer=[scriptblock]::Create($source)
    & $installer
    & $installer
    Check ($installMock.Registrations -eq 2 -and $installMock.Stops -eq 1 -and $installMock.Starts -eq 2) 'installer rerun replaces same stopped task'
    Check ($installMock.AdminChecks -eq 2) 'installer requires admin on every invocation'
    Check (($installMock.Paths -join ' ') -notmatch '/mnt/c/wsl') 'installer passes direct Linux UNC-derived path'
    Check ($installMock.WslCalls.Count -eq 4) 'two WSL calls per installation'
    Check (($installMock.WslCalls[0].Args -join '|') -eq '-d|Ubuntu|--exec|id|-un') 'installer user detection argv'
    Check (($installMock.WslCalls[1].Args[0..6] -join '|') -eq '-d|Ubuntu|-u|root|--exec|/bin/bash|-s') 'installer root setup argv'
    Check ($installMock.WslCalls[1].Args[8] -eq '/home/udaybhan/projects/Ghar_sajag_r1/tools/usb/install-gs-wsl-usb.sh') 'installer Linux path'
    Check ($installMock.WslCalls[1].InputText -eq 'exec /bin/bash "$1" "$2"') 'installer bootstraps exact WSL script'
    Check (($installMock.WslCalls[2].Args -join '|') -eq ($installMock.WslCalls[0].Args -join '|') -and
        ($installMock.WslCalls[3].Args -join '|') -eq ($installMock.WslCalls[1].Args -join '|')) 'rerun WSL argv stable'
}
Write-Output "USB_ALL_OFFLINE_PASS checks=$count"
