[CmdletBinding()]
param(
    [ValidateSet('ensure-attached')]
    [string]$Mode = 'ensure-attached',
    [int]$TimeoutSeconds = 30,
    [switch]$ParserCheck,
    [switch]$SelfTest
)

# USB-only Windows boundary for the WSL-first Phase-1 HIL supervisor.
# Keep this file ASCII-only and Windows PowerShell 5.1 compatible.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ExpectedDevices = @(
    [pscustomobject]@{ Role = 'Hub'; Vid = '10c4'; Pid = 'ea60' },
    [pscustomobject]@{ Role = 'C3'; Vid = '303a'; Pid = '1001' }
)
$script:NativeProcessTestHook = $null

function Write-UsbLog([string]$Message) { Write-Host ('HIL-USB: ' + $Message) }

function Quote-NativeArgument([string]$Value) {
    $quote = [string][char]34
    if ($Value.IndexOf([char]34) -ge 0) { throw 'native argument contains an unsupported quote' }
    if ($Value.Length -eq 0) { return $quote + $quote }
    if ($Value -notmatch '\s') { return $Value }
    return $quote + $Value + $quote
}

function Invoke-NativeProcess([string]$FileName, [string[]]$Arguments) {
    if ($null -ne $script:NativeProcessTestHook) {
        return & $script:NativeProcessTestHook $FileName $Arguments
    }
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $FileName
    $psi.Arguments = (($Arguments | ForEach-Object { Quote-NativeArgument $_ }) -join ' ')
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $psi
    try { $started = $process.Start() } catch {
        throw "NATIVE_PROCESS_NOT_STARTED: ${FileName}: $($_.Exception.Message)"
    }
    if (-not $started) { throw "NATIVE_PROCESS_NOT_STARTED: $FileName" }
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    return [pscustomobject]@{
        ExitCode = [int]$process.ExitCode
        StdOut = [string]$stdoutTask.Result
        StdErr = [string]$stderrTask.Result
    }
}

function Format-NativeResult([object]$Result) {
    return "exit=$($Result.ExitCode); stdout=[$($Result.StdOut.Trim())]; stderr=[$($Result.StdErr.Trim())]"
}

function Invoke-Usbipd([string[]]$Arguments) {
    return Invoke-NativeProcess 'usbipd.exe' $Arguments
}

function ConvertFrom-UsbipdList([string]$Text) {
    $rows = @()
    $section = 'Unknown'
    foreach ($line in ($Text -split "`r?`n")) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        if ($line -match '^\s*Connected\s*:\s*$') { $section = 'Connected'; continue }
        if ($line -match '^\s*Persisted\s*:\s*$') { $section = 'Persisted'; continue }
        $row = $null
        if ($section -ne 'Persisted' -and $line -match 'BUSID=(?<busid>[^;]+).*VID:PID=(?<vid>[0-9a-fA-F]{4}):(?<pid>[0-9a-fA-F]{4}).*DEVICE=(?<device>.*?);STATE=(?<state>[^;]+)') {
            $row = [pscustomobject]@{
                BusId = $Matches.busid.Trim(); Vid = $Matches.vid.ToLowerInvariant()
                Pid = $Matches.pid.ToLowerInvariant(); Device = $Matches.device.Trim()
                State = $Matches.state.Trim()
            }
        }
        if ($null -eq $row -and $section -eq 'Connected' -and $line -match '^\s*(?<busid>\S+)\s+(?<vid>[0-9a-fA-F]{4}):(?<pid>[0-9a-fA-F]{4})\s+(?<device>.*?)\s+(?<state>Not shared|Not attached|No supported|Shared|Attached)\s*$') {
            $row = [pscustomobject]@{
                BusId = $Matches.busid.Trim(); Vid = $Matches.vid.ToLowerInvariant()
                Pid = $Matches.pid.ToLowerInvariant(); Device = $Matches.device.Trim()
                State = $Matches.state.Trim()
            }
        }
        if ($null -ne $row) { $rows += $row }
    }
    return @($rows)
}

function Get-UsbipdDevices {
    $result = Invoke-Usbipd @('list', '--parsable')
    $combined = $result.StdOut + "`n" + $result.StdErr
    $unsupported = $combined -match '(?i)unrecognized command or argument.*--parsable|unknown option.*--parsable|invalid option.*--parsable'
    if ($result.ExitCode -ne 0 -and -not $unsupported) {
        throw "USBIPD_LIST_FAILED: $(Format-NativeResult $result)"
    }
    $rows = if ($result.ExitCode -eq 0) { @(ConvertFrom-UsbipdList $result.StdOut) } else { @() }
    if ($unsupported -or $rows.Count -eq 0) {
        $result = Invoke-Usbipd @('list')
        if ($result.ExitCode -ne 0) { throw "USBIPD_LIST_FAILED: $(Format-NativeResult $result)" }
        $rows = @(ConvertFrom-UsbipdList $result.StdOut)
    }
    return @($rows)
}

function Select-ExpectedUsbDevices([object[]]$Rows) {
    $selected = @{}
    foreach ($expected in $ExpectedDevices) {
        $matches = @($Rows | Where-Object { $_.Vid -eq $expected.Vid -and $_.Pid -eq $expected.Pid })
        if ($matches.Count -eq 0) { throw "$($expected.Role) USB device $($expected.Vid):$($expected.Pid) is missing" }
        if ($matches.Count -ne 1) { throw "$($expected.Role) USB identity is ambiguous" }
        $device = $matches[0]
        if ($device.State -eq 'Not shared') {
            throw "BLOCKED_NEEDS_USBIPD_BIND: $($expected.Role) BUSID $($device.BusId)"
        }
        if ($device.State -notin @('Shared', 'Attached')) {
            throw "$($expected.Role) BUSID $($device.BusId) has unsupported state $($device.State)"
        }
        $selected[$expected.Role] = $device
    }
    return $selected
}

function Ensure-UsbAttached([int]$BoundSeconds = 30) {
    $deadline = [DateTime]::UtcNow.AddSeconds($BoundSeconds)
    $acceptedBus = @{}
    $lastMessage = 'USB state was not inspected'
    do {
        try {
            $devices = Select-ExpectedUsbDevices (Get-UsbipdDevices)
            $allAttached = $true
            foreach ($role in @('Hub', 'C3')) {
                $device = $devices[$role]
                if ($device.State -eq 'Attached') {
                    Write-UsbLog "$role already Attached (BUSID $($device.BusId))"
                    continue
                }
                $allAttached = $false
                if ($acceptedBus.ContainsKey($role) -and $acceptedBus[$role] -eq $device.BusId) {
                    Write-UsbLog "$role attach accepted; waiting for state refresh (BUSID $($device.BusId))"
                    continue
                }
                Write-UsbLog "attaching $role (BUSID $($device.BusId))"
                $result = Invoke-Usbipd @('attach', '--wsl', '--busid', $device.BusId)
                if ($result.ExitCode -ne 0) {
                    throw "USBIPD_ATTACH_FAILED: $role BUSID $($device.BusId): $(Format-NativeResult $result)"
                }
                $acceptedBus[$role] = $device.BusId
                if (-not [string]::IsNullOrWhiteSpace($result.StdErr)) {
                    Write-UsbLog "usbipd information: $($result.StdErr.Trim())"
                }
            }
            if ($allAttached) {
                Write-UsbLog 'expected Hub and C3 are Attached'
                return 0
            }
            $lastMessage = 'attach accepted; waiting for live Attached state'
        } catch {
            $lastMessage = $_.Exception.Message
            if ($lastMessage -match 'ambiguous|BLOCKED_NEEDS_USBIPD_BIND|unsupported state|USBIPD_ATTACH_FAILED|USBIPD_LIST_FAILED') { throw }
        }
        if ([DateTime]::UtcNow -ge $deadline) { break }
        Start-Sleep -Milliseconds 500
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "BLOCKED_USB_ATTACH_TIMEOUT: $lastMessage"
}

function Assert-SelfTest([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw "self-test failed: $Message" }
}

function Invoke-SelfTest {
    $info = "usbipd: info: Using WSL distribution 'Ubuntu' to attach."
    $script:ListCall = 0
    $script:AttachBus = @()
    $script:NativeProcessTestHook = {
        param($fileName, $arguments)
        if ($arguments[0] -eq 'attach') {
            $script:AttachBus += $arguments[3]
            return [pscustomobject]@{ ExitCode = 0; StdOut = ''; StdErr = $info }
        }
        $script:ListCall++
        $bus = if ($script:ListCall -le 2) { '4-1' } else { '7-2' }
        $state = if ($script:ListCall -ge 4) { 'Attached' } else { 'Shared' }
        $text = "BUSID=$bus;VID:PID=10c4:ea60;DEVICE=Hub;STATE=$state`nBUSID=4-2;VID:PID=303a:1001;DEVICE=C3;STATE=Attached"
        return [pscustomobject]@{ ExitCode = 0; StdOut = $text; StdErr = '' }
    }
    [void](Ensure-UsbAttached 3)
    Assert-SelfTest (($script:AttachBus -join ',') -eq '4-1,7-2') 'changed BUSID and informational stderr'

    $plain = "Connected:`nBUSID  VID:PID    DEVICE  STATE`n1-1    10c4:ea60  Hub     Attached`n1-2    303a:1001  C3      Attached`n`nPersisted:`nGUID  DEVICE"
    Assert-SelfTest (@(ConvertFrom-UsbipdList $plain).Count -eq 2) 'plain Connected parsing ignores Persisted'
    $persistedParsable = $plain + "`nBUSID=9-9;VID:PID=10c4:ea60;DEVICE=stale;STATE=Attached"
    Assert-SelfTest (@(ConvertFrom-UsbipdList $persistedParsable).Count -eq 2) 'parsable Persisted row ignored'
    $ambiguous = $plain.Replace('1-2    303a:1001  C3      Attached', "1-3    10c4:ea60  Hub2    Attached`n1-2    303a:1001  C3      Attached")
    $message = ''
    try { [void](Select-ExpectedUsbDevices (ConvertFrom-UsbipdList $ambiguous)) } catch { $message = $_.Exception.Message }
    Assert-SelfTest ($message -match 'Hub USB identity is ambiguous') 'ambiguous VID PID fails closed'
    $notShared = $plain.Replace('Hub     Attached', 'Hub     Not shared')
    $message = ''
    try { [void](Select-ExpectedUsbDevices (ConvertFrom-UsbipdList $notShared)) } catch { $message = $_.Exception.Message }
    Assert-SelfTest ($message -match 'BLOCKED_NEEDS_USBIPD_BIND') 'Not shared is blocked'

    $script:PlainCalls = 0
    $script:NativeProcessTestHook = {
        param($fileName, $arguments)
        if ($arguments.Count -eq 2) {
            return [pscustomobject]@{ ExitCode = 1; StdOut = ''; StdErr = "Unrecognized command or argument '--parsable'" }
        }
        $script:PlainCalls++
        return [pscustomobject]@{ ExitCode = 0; StdOut = $plain; StdErr = '' }
    }
    Assert-SelfTest (@(Get-UsbipdDevices).Count -eq 2 -and $script:PlainCalls -eq 1) 'legacy plain-list fallback'

    $script:AttachAttempted = $false
    $script:NativeProcessTestHook = {
        param($fileName, $arguments)
        if ($arguments[0] -eq 'attach') { $script:AttachAttempted = $true; throw 'unexpected attach' }
        $text = "BUSID=1-1;VID:PID=10c4:ea60;DEVICE=Hub;STATE=Attached`nBUSID=1-2;VID:PID=303a:1001;DEVICE=C3;STATE=Attached"
        return [pscustomobject]@{ ExitCode = 0; StdOut = $text; StdErr = '' }
    }
    [void](Ensure-UsbAttached 1)
    Assert-SelfTest (-not $script:AttachAttempted) 'already Attached does not attach'

    $script:NativeProcessTestHook = {
        param($fileName, $arguments)
        if ($arguments[0] -eq 'attach') {
            return [pscustomobject]@{ ExitCode = 23; StdOut = 'attach output'; StdErr = 'access denied' }
        }
        $text = "BUSID=1-1;VID:PID=10c4:ea60;DEVICE=Hub;STATE=Shared`nBUSID=1-2;VID:PID=303a:1001;DEVICE=C3;STATE=Attached"
        return [pscustomobject]@{ ExitCode = 0; StdOut = $text; StdErr = '' }
    }
    $message = ''
    try { [void](Ensure-UsbAttached 1) } catch { $message = $_.Exception.Message }
    Assert-SelfTest ($message -match 'USBIPD_ATTACH_FAILED.*exit=23.*access denied') 'nonzero attach fails'

    $script:NativeProcessTestHook = {
        param($fileName, $arguments)
        if ($arguments[0] -eq 'attach') {
            return [pscustomobject]@{ ExitCode = 0; StdOut = ''; StdErr = $info }
        }
        $text = "BUSID=1-1;VID:PID=10c4:ea60;DEVICE=Hub;STATE=Shared`nBUSID=1-2;VID:PID=303a:1001;DEVICE=C3;STATE=Attached"
        return [pscustomobject]@{ ExitCode = 0; StdOut = $text; StdErr = '' }
    }
    $message = ''
    try { [void](Ensure-UsbAttached 0) } catch { $message = $_.Exception.Message }
    Assert-SelfTest ($message -match 'BLOCKED_USB_ATTACH_TIMEOUT') 'successful attach without Attached state times out'
    $script:NativeProcessTestHook = $null
    Write-Host 'HIL-USB SELF-TEST: PASS'
}

function Invoke-ParserCheck {
    $tokens = $null
    $errors = $null
    [System.Management.Automation.Language.Parser]::ParseFile($PSCommandPath, [ref]$tokens, [ref]$errors) | Out-Null
    if ($errors.Count -ne 0) { throw (($errors | ForEach-Object { $_.Message }) -join '; ') }
    Write-Host 'HIL-USB PARSER-CHECK: PASS'
}

try {
    if ($ParserCheck) { Invoke-ParserCheck; exit 0 }
    if ($SelfTest) { Invoke-SelfTest; exit 0 }
    if ($Mode -ne 'ensure-attached') { throw "unsupported mode: $Mode" }
    if ($null -eq (Get-Command usbipd.exe -ErrorAction SilentlyContinue)) { throw 'usbipd.exe is unavailable' }
    exit (Ensure-UsbAttached $TimeoutSeconds)
} catch {
    Write-Error ('HIL-USB: FAIL - ' + $_.Exception.Message)
    exit 2
}
