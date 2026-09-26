@echo off
cd /d "%~dp0backend"
echo This deletes the LOCAL SQLite database only.
set /p confirm=Type YES to continue: 
if /I not "%confirm%"=="YES" exit /b 0
if exist archive.db del archive.db
echo Local database reset.
pause
