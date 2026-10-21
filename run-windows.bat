@echo off
title ShohorSathi Windows Starter (Zero-Docker Mode)
echo ===================================================================
echo   ShohorSathi Zero-Docker Instant Runner (Windows)
echo ===================================================================
echo.
echo [1/2] Launching Backend Server on http://localhost:8088...
start "ShohorSathi Backend Server" cmd /k "python scripts/standalone_server.py"

echo [2/2] Launching Frontend Web Apps (:5173, :5174, :5175)...
echo.
echo Open in browser:
echo   - Customer App: http://localhost:5173
echo   - Provider App: http://localhost:5174
echo   - Admin Panel:  http://localhost:5175
echo.
call pnpm dev
pause
