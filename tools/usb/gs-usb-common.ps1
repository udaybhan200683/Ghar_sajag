# Pure helpers and bounded native-process boundary. Windows PowerShell 5.1.
Set-StrictMode -Version Latest

function Assert-GsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Run once in Administrator PowerShell under the Windows account that owns the Ubuntu distro.'
    }
}

function ConvertTo-GsWslPath([string]$SourcePath, [string]$Distro) {
    # These files are ALREADY in this distro. Never pass this UNC to wslpath.
    if ($SourcePath -match '^\\\\(?:wsl\.localhost|wsl\$)\\([^\\]+)\\(.+)$') {
        if ($Matches[1] -ine $Distro) { throw 'UNC distro differs from requested WSL distro.' }
        return '/' + $Matches[2].Replace('\', '/')
    }
    throw 'Launch this installer from its \\wsl.localhost\<distro>\... or \\wsl$\<distro>\... path.'
}

function Quote-GsNativeArgument([string]$Value) {
    # WSL parses its own Windows command line. Keep plain options unquoted;
    # quote only arguments that require it (spaces, quotes or an empty value).
    if ($Value -match '^[^\s"]+$') { return $Value }
    # CommandLineToArgvW/CRT escaping for arguments that do require quotes.
    $escaped = [regex]::Replace($Value, '(\\*)("|$)', {
        param($match)
        $slashes = $match.Groups[1].Value
        if ($match.Groups[2].Value -eq '"') { return $slashes + $slashes + '\"' }
        return $slashes + $slashes
    })
    return '"' + $escaped + '"'
}

function Invoke-GsWsl {
    param([Parameter(Mandatory)][string]$Distro,
          [Parameter(Mandatory)][string[]]$LinuxArgs,
          [switch]$AsRoot,
          [string]$InputText = '',
          [int]$TimeoutSec = 45)
    if ($Distro -match '[\r\n]' -or $LinuxArgs.Count -eq 0) {
        throw 'Invalid WSL argument list.'
    }
    $wslArgs = @('-d', $Distro)
    if ($AsRoot) { $wslArgs += @('-u', 'root') }
    $wslArgs += '--exec'
    $wslArgs += $LinuxArgs
    Invoke-GsNative -FilePath 'wsl.exe' -NativeArgs $wslArgs -InputText $InputText -TimeoutSec $TimeoutSec
}

function Invoke-GsNative {
    param([string]$FilePath, [string[]]$NativeArgs, [string]$InputText = '', [int]$TimeoutSec = 45)
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $FilePath
    $info.Arguments = (($NativeArgs | ForEach-Object { Quote-GsNativeArgument $_ }) -join ' ')
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $info.RedirectStandardInput = $true
    $info.StandardOutputEncoding = [Text.Encoding]::UTF8
    $info.StandardErrorEncoding = [Text.Encoding]::UTF8
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $info
    try {
        if (-not $process.Start()) { throw "Could not start $FilePath" }
        $output = $process.StandardOutput.ReadToEndAsync()
        $errors = $process.StandardError.ReadToEndAsync()
        if ($InputText) { $process.StandardInput.Write($InputText) }
        $process.StandardInput.Close()
        if (-not $process.WaitForExit($TimeoutSec * 1000)) {
            $process.Kill()
            throw "$FilePath timed out after ${TimeoutSec}s"
        }
        $process.WaitForExit()
        return [pscustomobject]@{ ExitCode = $process.ExitCode; StdOut = $output.Result; StdErr = $errors.Result }
    } finally { $process.Dispose() }
}

function Assert-GsNativeResult($Result, [string]$Operation) {
    if ($Result.ExitCode -ne 0) {
        throw "$Operation failed exit=$($Result.ExitCode): $($Result.StdErr.Trim()) $($Result.StdOut.Trim())"
    }
}

function ConvertFrom-GsUsbState([string]$Json) {
    $document = $Json | ConvertFrom-Json -ErrorAction Stop
    if ($null -eq $document -or $null -eq $document.PSObject.Properties['Devices'] -or
        $null -eq $document.Devices -or $document.Devices -isnot [System.Array]) {
        throw 'Malformed usbipd state: expected Devices array.'
    }
    $seen = @{}
    foreach ($device in $document.Devices) {
        foreach ($name in @('BusId', 'InstanceId', 'Description', 'PersistedGuid', 'ClientIPAddress')) {
            if ($null -eq $device -or $null -eq $device.PSObject.Properties[$name]) {
                throw "Malformed usbipd device: missing $name"
            }
        }
        if ([string]::IsNullOrEmpty([string]$device.BusId)) { continue } # disconnected bindings
        if ($device.BusId -notmatch '^\d+-\d+$' -or $seen.ContainsKey($device.BusId)) {
            throw 'Malformed/duplicate connected BUSID.'
        }
        $seen[$device.BusId] = $true
        if ($device.InstanceId -notmatch '(?i)VID_([0-9a-f]{4})&PID_([0-9a-f]{4})') { continue }
        $vidPid = ($Matches[1] + ':' + $Matches[2]).ToLowerInvariant()
        $shared = -not [string]::IsNullOrEmpty([string]$device.PersistedGuid)
        if ($shared) {
            $guid = [guid]::Empty
            if (-not [guid]::TryParse([string]$device.PersistedGuid, [ref]$guid)) { throw 'Invalid persisted GUID.' }
        }
        $attached = -not [string]::IsNullOrEmpty([string]$device.ClientIPAddress)
        if ($attached) {
            $address = $null
            if (-not [Net.IPAddress]::TryParse([string]$device.ClientIPAddress, [ref]$address)) { throw 'Invalid client address.' }
        }
        $stateName = if ($attached) { 'Attached' } elseif ($shared) { 'Shared' } else { 'Not shared' }
        [pscustomobject]@{ BusId = [string]$device.BusId; InstanceId = [string]$device.InstanceId;
            VidPid = $vidPid; State = $stateName; Description = [string]$device.Description }
    }
}

function New-GsWatchContext {
    return @{ States = @{}; Observations = @{}; NextAttempt = @{}; Failures = @{} }
}

function Set-GsWatchState($Context, [string]$Key, [string]$Value, [scriptblock]$Logger) {
    if (-not $Context.States.ContainsKey($Key) -or $Context.States[$Key] -ne $Value) {
        $Context.States[$Key] = $Value
        & $Logger "STATE $Key $Value"
    }
}

function Get-GsRoleObservation($Rows, [string]$Role) {
    $wanted = if ($Role -eq 'Hub') { '10c4:ea60' } else { '303a:1001' }
    $matchesForRole = @($Rows | Where-Object { $_.VidPid -eq $wanted })
    if ($matchesForRole.Count -gt 1) { return [pscustomobject]@{ Name = 'AMBIGUOUS'; Device = $null } }
    if ($matchesForRole.Count -eq 1) {
        $device = $matchesForRole[0]
        return [pscustomobject]@{ Name = "$($device.BusId):$($device.State):$($device.InstanceId)"; Device = $device }
    }
    if ($Role -eq 'Node' -and @($Rows | Where-Object { $_.VidPid -eq '0000:0002' }).Count -gt 0) {
        return [pscustomobject]@{ Name = 'NODE_ENUMERATION_FAILED'; Device = $null }
    }
    return [pscustomobject]@{ Name = 'ABSENT'; Device = $null }
}

function Invoke-GsWatchPass {
    param($Context, [scriptblock]$ReadRows, [scriptblock]$RunUsbipd,
          [scriptblock]$StartWsl, [scriptblock]$Logger, [datetime]$Now = [datetime]::UtcNow)
    try {
        $rows = @(& $ReadRows)
        Set-GsWatchState $Context 'DISCOVERY' 'OK' $Logger
    } catch {
        Set-GsWatchState $Context 'DISCOVERY' 'INVALID_OR_UNAVAILABLE' $Logger
        return # malformed output NEVER authorizes an action
    }
    foreach ($role in @('Hub', 'Node')) {
        $observation = Get-GsRoleObservation $rows $role
        if (-not $Context.Observations.ContainsKey($role) -or $Context.Observations[$role] -ne $observation.Name) {
            $Context.Observations[$role] = $observation.Name
            $Context.NextAttempt[$role] = $Now
            $Context.Failures[$role] = 0
            Set-GsWatchState $Context $role $observation.Name $Logger
        }
        $device = $observation.Device
        if ($null -eq $device -or $device.State -eq 'Attached' -or $Now -lt $Context.NextAttempt[$role]) { continue }
        try {
            # Refresh immediately before mutations; never reuse a disconnected BUSID.
            $fresh = Get-GsRoleObservation @(& $ReadRows) $role
            if ($null -eq $fresh.Device -or $fresh.Name -ne $observation.Name) { continue }
            if ($device.State -eq 'Not shared') {
                & $RunUsbipd -CommandArgs @('bind', '--busid', $device.BusId)
                $fresh = Get-GsRoleObservation @(& $ReadRows) $role
                if ($null -eq $fresh.Device -or $fresh.Device.InstanceId -ne $device.InstanceId -or
                    $fresh.Device.BusId -ne $device.BusId) { throw 'Device changed during bind.' }
                $device = $fresh.Device
            }
            if ($device.State -eq 'Attached') { continue }
            if ($device.State -ne 'Shared') { throw 'Binding was not confirmed.' }
            & $StartWsl
            # WSL startup can take time: rediscover once more before attach.
            $fresh = Get-GsRoleObservation @(& $ReadRows) $role
            if ($null -eq $fresh.Device -or $fresh.Device.InstanceId -ne $device.InstanceId -or
                $fresh.Device.BusId -ne $device.BusId) { throw 'Device changed during WSL startup.' }
            if ($fresh.Device.State -eq 'Attached') { continue }
            & $RunUsbipd -CommandArgs @('attach', '--wsl', '--busid', $device.BusId)
            $final = Get-GsRoleObservation @(& $ReadRows) $role
            if ($null -eq $final.Device -or $final.Device.InstanceId -ne $device.InstanceId -or
                $final.Device.BusId -ne $device.BusId -or $final.Device.State -ne 'Attached') {
                throw 'Attach did not reach Attached state.'
            }
            $Context.Failures[$role] = 0
            Set-GsWatchState $Context "${role}_ACTION" 'READY' $Logger
        } catch {
            $Context.Failures[$role]++
            $delay = [Math]::Min(300, 30 * [Math]::Pow(2, [Math]::Min(4, $Context.Failures[$role] - 1)))
            $Context.NextAttempt[$role] = $Now.AddSeconds($delay)
            Set-GsWatchState $Context "${role}_ACTION" 'FAILED_RETRY_BACKOFF' $Logger
            # First failure retains detail; identical retries do not spam the log.
            if ($Context.Failures[$role] -eq 1) { & $Logger "ERROR role=$role $($_.Exception.Message)" }
        }
    }
}
