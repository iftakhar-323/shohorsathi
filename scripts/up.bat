@echo off
REM Windows runner for ShohorSathi setup script.
REM Automatically delegates to Git Bash or WSL.

where bash >nul 2>&1
if %ERRORLEVEL% equ 0 (
    bash scripts/up.sh %*
    exit /b %ERRORLEVEL%
)

if exist "C:\Program Files\Git\bin\bash.exe" (
    "C:\Program Files\Git\bin\bash.exe" scripts/up.sh %*
    exit /b %ERRORLEVEL%
)

if exist "%LOCALAPPDATA%\Programs\Git\bin\bash.exe" (
    "%LOCALAPPDATA%\Programs\Git\bin\bash.exe" scripts/up.sh %*
    exit /b %ERRORLEVEL%
)

where wsl >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo Delegating to WSL...
    wsl ./scripts/up.sh %*
    exit /b %ERRORLEVEL%
)

echo ============================================================
echo [ERROR] Bash was not found in your PATH.
echo.
echo Please open 'Git Bash' from your Start Menu and run:
echo     cd shohorsathi
echo     ./scripts/up.sh --demo
echo ============================================================
exit /b 1

