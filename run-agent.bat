@echo off
REM SniperIT Agent Launcher - Runs with SSL verification disabled
REM This script runs the SniperIT Agent with the -issl flag to ignore SSL certificate verification

echo.
echo ================================================
echo    SniperIT Agent v2 - Quick Launcher
echo ================================================
echo.

REM Check if the executable exists
if not exist "SniperIT-Agent.exe" (
    echo ERROR: SniperIT-Agent.exe not found in dist folder!
    echo Please ensure the executable has been built.
    echo.
    pause
    exit /b 1
)

echo Starting SniperIT Agent with SSL verification disabled...
echo Command: SniperIT-Agent.exe -issl
echo.

REM Run the agent with -issl flag
SniperIT-Agent.exe -issl

REM Pause to show results
echo.
echo Agent execution completed.
pause