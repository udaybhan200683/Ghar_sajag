@echo off
setlocal
start "Ghar Sajag TC-001 Controller" wsl.exe --cd /home/udaybhan/projects/Ghar_sajag_r1 --exec bash code/tools/local/gs117-tc001-launch.sh
powershell.exe -NoProfile -NonInteractive -Command "$deadline=[DateTime]::UtcNow.AddSeconds(30); while([DateTime]::UtcNow -lt $deadline){try{$response=Invoke-WebRequest -Uri 'http://127.0.0.1:18791/' -UseBasicParsing -TimeoutSec 2; if($response.StatusCode -eq 200){exit 0}}catch{}; Start-Sleep -Milliseconds 500}; exit 1"
if errorlevel 1 (
  echo GS-117 utility did not become reachable at http://127.0.0.1:18791/ within 30 seconds.
  exit /b 1
)
start "" http://127.0.0.1:18791/
