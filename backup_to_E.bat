@echo off
REM ============================================================
REM  backup_to_E.bat
REM  Incremental copy of the lidar_project folder to E:\lidar_project
REM
REM  Uses robocopy, which compares timestamp + size per file:
REM    - New files            -> copied
REM    - Changed/newer files  -> copied
REM    - Identical files      -> skipped
REM    - Files newer in the TARGET than the source -> skipped (/XO)
REM  Nothing is ever deleted from the target.
REM ============================================================

set "SRC=%~dp0"
set "DST=E:\lidar_project"

REM strip trailing backslash from SRC (robocopy quirk with quoted paths)
if "%SRC:~-1%"=="\" set "SRC=%SRC:~0,-1%"

if not exist "E:\" (
    echo [ERROR] Drive E:\ is not available. Plug in the drive and re-run.
    pause
    exit /b 1
)

echo Copying new/changed files from:
echo   %SRC%
echo to:
echo   %DST%
echo.

robocopy "%SRC%" "%DST%" /E /XO /FFT /R:2 /W:5 /MT:8 /NP /TEE /LOG:"%SRC%\backup_to_E_last_run.log"

REM robocopy exit codes 0-7 are success (0 = nothing to copy, 1 = files copied)
if %ERRORLEVEL% GEQ 8 (
    echo.
    echo [ERROR] Robocopy reported a failure - exit code %ERRORLEVEL%. See backup_to_E_last_run.log
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo Done. Only new or revised files were copied. Log: backup_to_E_last_run.log
pause
exit /b 0
