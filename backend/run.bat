@echo off
REM ---------------------------------------------------------------------
REM RICKTRIX backend - one-click start.
REM
REM Creates the virtualenv, installs dependencies, trains the fare model
REM if it has not been trained yet, and serves the API on port 8000.
REM
REM   run.bat              start the API (trains the model if needed)
REM   run.bat --seed       also seed Supabase, then start
REM   run.bat --retrain    force a fresh model, then start
REM ---------------------------------------------------------------------
setlocal
cd /d "%~dp0"

echo.
echo  RICKTRIX backend
echo  ================
echo.

REM --- 1. find a usable Python -------------------------------------------
set "PY="
for %%C in (py python python3) do (
  if not defined PY (
    %%C -c "import sys; raise SystemExit(0 if (3,9) <= sys.version_info[:2] < (3,13) else 1)" >nul 2>&1
    if not errorlevel 1 set "PY=%%C"
  )
)

if not defined PY (
  echo  ERROR: no Python 3.9-3.12 found on PATH.
  echo  TensorFlow has no wheel for 3.13+. Install Python 3.11 or 3.12 from
  echo  https://www.python.org/downloads/ and tick "Add python.exe to PATH".
  echo.
  pause
  exit /b 1
)

for /f "delims=" %%V in ('%PY% -c "import sys; print(sys.version.split()[0])"') do set "PYVER=%%V"
echo  Python %%PYVER% via %PY%

REM --- 2. virtualenv ------------------------------------------------------
if not exist ".venv\Scripts\python.exe" (
  echo  Creating virtualenv in backend\.venv ...
  %PY% -m venv .venv || goto :failed
)

set "VPY=.venv\Scripts\python.exe"
if not exist "%VPY%" (
  echo  ERROR: virtualenv was not created.
  goto :failed
)

REM --- 3. dependencies ----------------------------------------------------
REM A marker keeps repeat starts fast; delete .venv\installed to force it.
if not exist ".venv\installed" (
  echo  Installing dependencies ^(first run takes a few minutes, TensorFlow
  echo  is the big one^) ...
  "%VPY%" -m pip install --upgrade pip --quiet
  "%VPY%" -m pip install -r requirements.txt || goto :failed
  type nul > ".venv\installed"
  echo  Dependencies installed.
) else (
  echo  Dependencies already installed.
)

REM --- 4. fare model ------------------------------------------------------
if "%~1"=="--retrain" (
  echo  Retraining the fare model ...
  "%VPY%" -m ml.train || goto :failed
) else (
  if not exist "ml\artifacts\fare_model.keras" (
    echo  No trained model found - training now ^(a minute or two^) ...
    "%VPY%" -m ml.train || goto :failed
  ) else (
    echo  Fare model already trained.
  )
)

REM Export to plain numpy weights. The server evaluates those directly, which
REM is what keeps TensorFlow out of the production image. Cheap, so it runs
REM every start to pick up a freshly trained model.
"%VPY%" -m ml.export || goto :failed

REM --- 4b. app icons ------------------------------------------------------
REM Chrome's install prompt and iOS's Add to Home Screen both want real PNGs.
REM They are committed, so this is normally a fast no-op.
if not exist "..\assets\icon-512.png" (
  echo  Generating app icons ...
  "%VPY%" -m scripts.make_icons || goto :failed
)

REM --- 5. seed ------------------------------------------------------------
if "%~1"=="--seed" (
  echo.
  echo  Seeding Supabase ...
  "%VPY%" -m scripts.seed
  echo  ^(skipped or failed if SUPABASE_SERVICE_ROLE_KEY is not set - that is fine^)
)

REM --- 6. stage the static site -------------------------------------------
REM Copied into backend\public so the API can serve the site from one origin.
REM The repo root is never served - that would expose backend\.env.
"%VPY%" -m scripts.build_site || goto :failed

REM --- 7. serve -----------------------------------------------------------
REM 0.0.0.0 so a phone on the same Wi-Fi can reach it. 127.0.0.1 would be
REM localhost-only and unreachable from a device.
for /f "delims=" %%I in ('powershell -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 ^| Where-Object { $$_.IPAddress -notlike ''127.*'' } ^| Select-Object -First 1 -ExpandProperty IPAddress)"') do set "LANIP=%%I"

echo.
echo  Starting on port 8000
if defined LANIP (
  echo    Laptop:  http://localhost:8000
  echo    Phone:   http://!LANIP!:8000    ^<- same Wi-Fi, open this on your phone
) else (
  echo    Laptop:  http://localhost:8000
  echo    Could not detect a LAN address; run `ipconfig` to find it.
)
echo    Docs:    http://localhost:8000/docs
echo.
echo  Windows may ask to allow Python on the network - choose Private, or the
echo  phone will not be able to connect.
echo  Press Ctrl+C to stop.
echo.
"%VPY%" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
goto :eof

:failed
echo.
echo  Startup failed. Scroll up for the error.
echo.
pause
exit /b 1
