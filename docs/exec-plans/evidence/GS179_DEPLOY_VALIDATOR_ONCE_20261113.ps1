# One-time, fixed-scope update for the owner-approved GS-179 validator change.
# This script never changes the scheduled task, task ACL, firewall, portproxy,
# credentials, device state, or any installed snapshot other than the validator
# and its matching manifest hash.
$ErrorActionPreference = 'Stop'

$installationRoot = 'C:\ProgramData\GharSajagEngineeringIngress'
$manifestPath = Join-Path $installationRoot 'installation.json'
$validatorPath = Join-Path $installationRoot 'gs179_engineering_validator.py'
$sourceValidator = '\\wsl.localhost\Ubuntu\home\udaybhan\projects\Ghar_sajag_r1\code\tools\local\gs179_engineering_validator.py'
$expectedNewValidatorHash = 'eb00866c200935651b73b988894803700c98b56f8b6edadf0d0340507691abd9'
$taskName = 'GharSajag-Engineering-Ingress'
$proxyPath = Join-Path $installationRoot 'gs179-windows-lan-proxy.ps1'
$runnerPath = '/mnt/c/ProgramData/GharSajagEngineeringIngress/gs179_engineering_validator.py'
$registeredHostGroupSid = 'S-1-5-21-2627759697-1582304275-3966001432-513'

$expectedInstalled = [ordered]@{
    'gs179-windows-lan-proxy.ps1' = '8c3f3ecd83e5bf854a5188028fa87fe8cc823b49d0638e1b806d7307c5ff9056'
    'gs179_engineering_validator.py' = 'b0725a9c9786f7c52f16765791cd206052e082a9f8813ce363084e1ff56de5db'
    'gs179_verified_endpoint.py' = 'c9b3cb79895d19ef6854aa55084d59b50e014804e43422fb73d84c1f3ceb8c7c'
    'gs117_hil_authorization.py' = '1d321595cbe590d6ca983c23878eafdf2e0841631b8ea0c230873ef28baa21bf'
}

function Get-Sha256([string]$path) {
    return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Assert-ExistingProtectedPath([string]$path, [string]$ownerSid) {
    $item = Get-Item -LiteralPath $path
    $acl = Get-Acl -LiteralPath $path
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
        $acl.Owner -notin @('BUILTIN\Administrators', 'NT AUTHORITY\SYSTEM')) {
        throw "protected_path_identity_invalid:$path"
    }
    $ownerMutationRights = [Security.AccessControl.FileSystemRights]::Write -bor
        [Security.AccessControl.FileSystemRights]::Delete -bor
        [Security.AccessControl.FileSystemRights]::DeleteSubdirectoriesAndFiles -bor
        [Security.AccessControl.FileSystemRights]::ChangePermissions -bor
        [Security.AccessControl.FileSystemRights]::TakeOwnership
    foreach ($rule in $acl.Access) {
        $sid = $rule.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value
        if ($rule.AccessControlType -ne 'Allow' -or
            $sid -notin @('S-1-5-18', 'S-1-5-32-544', $ownerSid) -or
            ($sid -eq $ownerSid -and ($rule.FileSystemRights -band $ownerMutationRights))) {
            throw "protected_path_acl_invalid:$path"
        }
    }
}

function Get-Sddl([string]$path) {
    return (Get-Acl -LiteralPath $path).GetSecurityDescriptorSddlForm(
        [Security.AccessControl.AccessControlSections]::All)
}

function Restore-File([string]$backupPath, [string]$destination, [string]$currentBackupPath) {
    $temporary = "$destination.rollback-$([guid]::NewGuid().ToString('N'))"
    Copy-Item -LiteralPath $backupPath -Destination $temporary
    Set-Acl -LiteralPath $temporary -AclObject (Get-Acl -LiteralPath $destination)
    if (Test-Path -LiteralPath $currentBackupPath) { throw 'rollback_current_backup_already_exists' }
    [IO.File]::Replace($temporary, $destination, $currentBackupPath, $true)
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'administrator_token_required; run this exact script in the owner-approved elevated PowerShell session'
}

if (-not (Test-Path -LiteralPath $installationRoot -PathType Container) -or
    -not (Test-Path -LiteralPath $manifestPath -PathType Leaf) -or
    -not (Test-Path -LiteralPath $validatorPath -PathType Leaf) -or
    -not (Test-Path -LiteralPath $sourceValidator -PathType Leaf)) {
    throw 'fixed_installation_or_source_missing'
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$ownerSid = $identity.User.Value
$expectedNames = @($expectedInstalled.Keys | Sort-Object)
$actualNames = @($manifest.sources.PSObject.Properties.Name | Sort-Object)
if ($manifest.schema -ne 'GS179_ENGINEERING_EXECUTOR_V1' -or
    $manifest.ownerSid -ne $ownerSid -or
    $manifest.authorityHash -notmatch '^[a-f0-9]{64}$' -or
    ($expectedNames -join ',') -ne ($actualNames -join ',')) {
    throw 'protected_manifest_identity_or_schema_invalid'
}

Assert-ExistingProtectedPath $installationRoot $ownerSid
Assert-ExistingProtectedPath $manifestPath $ownerSid
foreach ($name in $expectedInstalled.Keys) {
    $path = Join-Path $installationRoot $name
    Assert-ExistingProtectedPath $path $ownerSid
    $actual = Get-Sha256 $path
    if ($actual -ne $expectedInstalled[$name] -or
        $manifest.sources.PSObject.Properties[$name].Value -ne $expectedInstalled[$name]) {
        throw "installed_snapshot_not_at_expected_preupdate_hash:$name"
    }
}
if ((Get-Sha256 $sourceValidator) -ne $expectedNewValidatorHash) {
    throw 'reviewed_validator_source_hash_mismatch'
}

$task = Get-ScheduledTask -TaskName $taskName -TaskPath '\' -ErrorAction Stop
$expectedExecutable = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
$expectedArguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$proxyPath`" -Action RunEngineeringExecutor -EndpointKind PhysicalHubIngress"
$action = @($task.Actions)
if ($task.State -eq 'Running' -or $action.Count -ne 1 -or
    $action[0].Execute -ine $expectedExecutable -or
    ([regex]::Replace([string]$action[0].Arguments, '\s+', ' ').Trim() -ine $expectedArguments) -or
    $task.Principal.UserId -ine $env:USERNAME -or
    $task.Principal.LogonType -ne 'S4U' -or $task.Principal.RunLevel -ne 'Highest') {
    throw 'registered_task_identity_action_or_state_invalid'
}
$scheduler = New-Object -ComObject 'Schedule.Service'
$scheduler.Connect()
$registeredTask = $scheduler.GetFolder('\').GetTask($taskName)
$taskSddlBefore = $registeredTask.GetSecurityDescriptor(7)

$rootSddlBefore = Get-Sddl $installationRoot
$manifestSddlBefore = Get-Sddl $manifestPath
$validatorSddlBefore = Get-Sddl $validatorPath
$expectedRootSddl = 'O:BAG:{0}D:PAI(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;0x1200a9;;;{1})' -f $registeredHostGroupSid, $ownerSid
$expectedFileSddl = 'O:BAG:{0}D:AI(A;ID;FA;;;SY)(A;ID;FA;;;BA)(A;ID;0x1200a9;;;{1})' -f $registeredHostGroupSid, $ownerSid
$expectedTaskSddl = 'O:BAG:{0}D:(A;;FA;;;SY)(A;;FA;;;BA)(A;;0x1200a9;;;{1})(A;;FR;;;{1})' -f $registeredHostGroupSid, $ownerSid
if ($rootSddlBefore -ne $expectedRootSddl -or
    $manifestSddlBefore -ne $expectedFileSddl -or
    $validatorSddlBefore -ne $expectedFileSddl -or
    $taskSddlBefore -ne $expectedTaskSddl) {
    throw 'existing_task_or_protected_acl_does_not_match_reviewed_fixture'
}

$ingressBefore = @(Get-NetTCPConnection -State Listen -LocalPort 8445 -ErrorAction SilentlyContinue).Count
if ($ingressBefore -ne 0) { throw 'active_8445_session_prevents_validator_update' }
$timeBefore = @(Get-NetUDPEndpoint -LocalPort 4468 -ErrorAction SilentlyContinue).Count
$caregiverBefore = @(Get-NetTCPConnection -State Listen -LocalPort 443 -ErrorAction SilentlyContinue).Count
$manifestOwnerSidBefore = $manifest.ownerSid
$manifestAuthorityHashBefore = $manifest.authorityHash
$manifestInstalledBefore = $manifest.installed
$manifestProxyHashBefore = $manifest.proxySha256

$backupRoot = Join-Path $installationRoot ('validator-update-rollback-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ'))
if (Test-Path -LiteralPath $backupRoot) { throw 'rollback_directory_already_exists' }
New-Item -ItemType Directory -Path $backupRoot | Out-Null
Set-Acl -LiteralPath $backupRoot -AclObject (Get-Acl -LiteralPath $installationRoot)
$validatorBackup = Join-Path $backupRoot 'gs179_engineering_validator.py'
$manifestBackup = Join-Path $backupRoot 'installation.json'
$replaceBackupValidator = Join-Path $backupRoot 'gs179_engineering_validator.pre-replace.py'
$replaceBackupManifest = Join-Path $backupRoot 'installation.pre-replace.json'
Copy-Item -LiteralPath $validatorPath -Destination $validatorBackup
Copy-Item -LiteralPath $manifestPath -Destination $manifestBackup
Set-Acl -LiteralPath $validatorBackup -AclObject (Get-Acl -LiteralPath $validatorPath)
Set-Acl -LiteralPath $manifestBackup -AclObject (Get-Acl -LiteralPath $manifestPath)
if ((Get-Sha256 $validatorBackup) -ne $expectedInstalled['gs179_engineering_validator.py'] -or
    (Get-Sha256 $manifestBackup) -ne (Get-Sha256 $manifestPath)) {
    throw "rollback_backup_verification_failed:$backupRoot"
}
Assert-ExistingProtectedPath $backupRoot $ownerSid
Assert-ExistingProtectedPath $validatorBackup $ownerSid
Assert-ExistingProtectedPath $manifestBackup $ownerSid
if ((Get-Sddl $backupRoot) -ne $rootSddlBefore -or
    (Get-Sddl $validatorBackup) -ne $validatorSddlBefore -or
    (Get-Sddl $manifestBackup) -ne $manifestSddlBefore) {
    throw "rollback_backup_acl_verification_failed:$backupRoot"
}

$suffix = [guid]::NewGuid().ToString('N')
$stagedValidator = Join-Path $installationRoot ('.gs179_engineering_validator.py.update-' + $suffix)
$stagedManifest = Join-Path $installationRoot ('.installation.json.update-' + $suffix)
$validatorReplaced = $false
$manifestReplaced = $false
$preserveTemporaryFiles = $false
try {
    Copy-Item -LiteralPath $sourceValidator -Destination $stagedValidator
    Set-Acl -LiteralPath $stagedValidator -AclObject (Get-Acl -LiteralPath $validatorPath)
    if ((Get-Sha256 $stagedValidator) -ne $expectedNewValidatorHash -or
        (Get-Sddl $stagedValidator) -ne $validatorSddlBefore) {
        throw 'staged_validator_hash_mismatch'
    }

    $manifest.sources.PSObject.Properties['gs179_engineering_validator.py'].Value = $expectedNewValidatorHash
    $manifestJson = ConvertTo-Json -InputObject $manifest -Depth 10
    [IO.File]::WriteAllText($stagedManifest, $manifestJson, [Text.UTF8Encoding]::new($true))
    Set-Acl -LiteralPath $stagedManifest -AclObject (Get-Acl -LiteralPath $manifestPath)
    if ((Get-Sddl $stagedManifest) -ne $manifestSddlBefore) {
        throw 'staged_manifest_acl_mismatch'
    }

    # Both destinations and staged files are on the same protected volume.
    # If either replacement or subsequent verification fails, restore both
    # original bytes from the protected rollback copies below.
    $validatorReplaced = $true
    [IO.File]::Replace($stagedValidator, $validatorPath, $replaceBackupValidator, $true)
    if ((Get-Sha256 $replaceBackupValidator) -ne $expectedInstalled['gs179_engineering_validator.py']) {
        throw 'atomic_validator_backup_hash_mismatch'
    }
    $manifestReplaced = $true
    [IO.File]::Replace($stagedManifest, $manifestPath, $replaceBackupManifest, $true)
    if ((Get-Sha256 $replaceBackupManifest) -ne (Get-Sha256 $manifestBackup)) {
        throw 'atomic_manifest_backup_hash_mismatch'
    }
    if ((Get-Sddl $replaceBackupValidator) -ne $validatorSddlBefore -or
        (Get-Sddl $replaceBackupManifest) -ne $manifestSddlBefore) {
        throw 'atomic_backup_acl_mismatch'
    }

    $installedManifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    foreach ($name in $expectedInstalled.Keys) {
        $expectedHash = if ($name -eq 'gs179_engineering_validator.py') {
            $expectedNewValidatorHash
        } else { $expectedInstalled[$name] }
        if ((Get-Sha256 (Join-Path $installationRoot $name)) -ne $expectedHash -or
            $installedManifest.sources.PSObject.Properties[$name].Value -ne $expectedHash) {
            throw "postupdate_snapshot_verification_failed:$name"
        }
    }
    if ($installedManifest.ownerSid -ne $manifestOwnerSidBefore -or
        $installedManifest.authorityHash -ne $manifestAuthorityHashBefore -or
        $installedManifest.installed -ne $manifestInstalledBefore -or
        $installedManifest.proxySha256 -ne $manifestProxyHashBefore) {
        throw 'postupdate_manifest_authority_metadata_changed'
    }
    if ((Get-Sddl $installationRoot) -ne $rootSddlBefore -or
        (Get-Sddl $manifestPath) -ne $manifestSddlBefore -or
        (Get-Sddl $validatorPath) -ne $validatorSddlBefore) {
        throw 'postupdate_installation_acl_changed'
    }
    $taskAfter = Get-ScheduledTask -TaskName $taskName -TaskPath '\' -ErrorAction Stop
    $taskAfterCom = $scheduler.GetFolder('\').GetTask($taskName)
    if ($taskAfter.TaskPath -ne '\' -or
        $taskAfter.Principal.UserId -ine $task.Principal.UserId -or
        $taskAfter.Principal.LogonType -ne $task.Principal.LogonType -or
        $taskAfter.Principal.RunLevel -ne $task.Principal.RunLevel -or
        $taskAfter.Actions.Count -ne 1 -or
        $taskAfter.Actions[0].Execute -ine $action[0].Execute -or
        ([regex]::Replace([string]$taskAfter.Actions[0].Arguments, '\s+', ' ').Trim() -ine $expectedArguments) -or
        $taskAfterCom.GetSecurityDescriptor(7) -ne $taskSddlBefore) {
        throw 'postupdate_task_identity_action_or_acl_changed'
    }

    # Read-only parse/load through the actual installed validator. --help exits
    # before authority evaluation or any network mutation.
    $wsl = Join-Path $env:WINDIR 'System32\wsl.exe'
    $helpOutput = & $wsl --distribution Ubuntu --user udaybhan --exec /usr/bin/python3 -I -S $runnerPath --help 2>&1
    if ($LASTEXITCODE -ne 0 -or ($helpOutput -join "`n") -notmatch 'physical-ingress-authority') {
        throw 'installed_validator_snapshot_load_check_failed'
    }
    if (@(Get-NetTCPConnection -State Listen -LocalPort 8445 -ErrorAction SilentlyContinue).Count -ne 0 -or
        @(Get-NetUDPEndpoint -LocalPort 4468 -ErrorAction SilentlyContinue).Count -ne $timeBefore -or
        @(Get-NetTCPConnection -State Listen -LocalPort 443 -ErrorAction SilentlyContinue).Count -ne $caregiverBefore) {
        throw 'postupdate_network_state_changed'
    }

    [pscustomobject]@{
        Result = 'VALIDATOR_UPDATED_AND_VERIFIED'
        Task = $taskName
        InstalledValidatorSha256 = Get-Sha256 $validatorPath
        RollbackDirectory = $backupRoot
        TaskIdentityActionAclPreserved = $true
        Tcp8445Listeners = 0
        Udp4468CountPreserved = $timeBefore
        Tcp443ListenersPreserved = $caregiverBefore
        NetworkOrHardwareOperationPerformed = $false
    } | ConvertTo-Json -Compress
} catch {
    $failure = $_.Exception.Message
    $rollbackErrors = @()
    try { if ($manifestReplaced) { Restore-File $manifestBackup $manifestPath (Join-Path $backupRoot 'installation.rollback-current.json') } } catch { $rollbackErrors += "manifest:$($_.Exception.Message)" }
    try { if ($validatorReplaced) { Restore-File $validatorBackup $validatorPath (Join-Path $backupRoot 'gs179_engineering_validator.rollback-current.py') } } catch { $rollbackErrors += "validator:$($_.Exception.Message)" }
    if ($rollbackErrors.Count -gt 0) {
        $preserveTemporaryFiles = $true
        throw "VALIDATOR_UPDATE_FAILED_ROLLBACK_INCOMPLETE; failure=$failure; rollback=$($rollbackErrors -join ';'); recovery=$backupRoot"
    }
    throw "VALIDATOR_UPDATE_FAILED_ROLLED_BACK; failure=$failure; recovery=$backupRoot"
} finally {
    if (-not $preserveTemporaryFiles) {
        foreach ($temporaryPath in @($stagedValidator, $stagedManifest)) {
            if (Test-Path -LiteralPath $temporaryPath) { Remove-Item -LiteralPath $temporaryPath -Force }
        }
    }
}
