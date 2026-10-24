@echo off
setlocal
start "Ghar Sajag TC-001 Controller" wsl.exe --cd /home/udaybhan/projects/Ghar_sajag_r1 --exec bash code/tools/local/gs117-tc001-launch.sh
timeout /t 3 /nobreak >nul
start "" http://127.0.0.1:18791/
