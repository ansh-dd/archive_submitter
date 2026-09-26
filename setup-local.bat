@echo off
setlocal
cd /d "%~dp0"

echo === PRJ-09 Local Setup ===

echo [1/4] Creating Python virtual environment...
if not exist backend\.venv\Scripts\python.exe (
  python -m venv backend\.venv || goto :error
)

echo [2/4] Installing backend dependencies...
backend\.venv\Scripts\python.exe -m pip install --upgrade pip || goto :error
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt || goto :error

if not exist backend\.env (
  copy backend\.env.example backend\.env >nul
)
if not exist frontend\.env.local (
  copy frontend\.env.local.example frontend\.env.local >nul
)

echo [3/4] Installing frontend dependencies...
pushd frontend
call npm install || (popd & goto :error)
popd

echo [4/4] Running backend tests...
pushd backend
.venv\Scripts\python.exe -m pytest -q || (popd & goto :error)
popd

echo.
echo Setup complete.
echo Run run-backend.bat and run-frontend.bat in two terminals/windows.
pause
exit /b 0

:error
echo.
echo Setup failed. Review the error above.
pause
exit /b 1
