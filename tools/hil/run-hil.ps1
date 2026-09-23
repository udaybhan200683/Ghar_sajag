[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Mode = 'qualify'
)

# Deprecated compatibility notice. WSL is the only Phase-1 master supervisor.
# This file intentionally performs no USB, path, make, bash or HIL orchestration.
Write-Error @"
tools/hil/run-hil.ps1 is deprecated and no longer orchestrates Phase-1 HIL.
Run from normal WSL Ubuntu:
  cd ~/projects/Ghar_sajag
  make hil-qualify
Requested legacy mode: $Mode
"@
exit 2
