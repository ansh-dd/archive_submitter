@echo off
cd /d "%~dp0frontend"
if not exist node_modules (
  echo node_modules not found. Running npm install...
  call npm install || exit /b 1
)
call npm run dev
