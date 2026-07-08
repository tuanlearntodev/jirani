@echo off
REM Morning briefing wrapper — called by Windows Task Scheduler at logon
REM Runs the WSL script that generates the daily briefing
wsl bash -c "cd /mnt/d/jirani_offline_library_backend && bash scripts/morning-briefing.sh"
