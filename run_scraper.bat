@echo off
REM ============================================================================
REM Khmer24 Daily Car Scraper - Local Automation Launcher
REM Works with Windows Task Scheduler or direct manual double-click
REM ============================================================================

cd /d "%~dp0"
echo =======================================================
echo [%date% %time%] Starting Khmer24 Daily Scraper...
echo Working directory: %cd%
echo =======================================================

uv run scrape

if %ERRORLEVEL% equ 0 (
    echo =======================================================
    echo [%date% %time%] Scrape completed successfully!
    echo =======================================================
) else (
    echo =======================================================
    echo [%date% %time%] Scrape FAILED with error code %ERRORLEVEL%
    echo =======================================================
)

REM Exit with the return code from the python scraper
exit /b %ERRORLEVEL%
