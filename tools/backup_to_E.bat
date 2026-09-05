@echo off
REM ============================================================
REM  backup_to_E.bat   -- letter-keyed launcher, SUPERSEDED
REM  Prefer tools/backup_to_t7.ps1 (see below). Kept because this one
REM  wrote the mirror that docs/verify_backup_report.md records as PASS.
REM
REM  Target:  E:\Colton\_BACKUPS\lidar_project_MIRROR
REM
REM  This replaces the old backup_to_E.bat, which pointed at
REM  E:\lidar_project -- a path that has never existed on this machine.
REM
REM  F: was gone on 2026-08-12 and is back as of 2026-08-19, but it is a
REM  DIFFERENT state: F:\lidar_project, written on 2026-08-05/06, no longer
REM  exists on the remounted volume. Nothing from those runs is recoverable.
REM  The current mirror script is tools/backup_to_t7.ps1. It resolves the

REM  target by VOLUME LABEL, not drive letter: the same physical T7 answered

REM  to F: and later to E: on 2026-09-03, so a letter-keyed launcher can copy

REM  onto the wrong disk. tools/backup_to_F.bat was deleted for that reason.
REM
REM  robocopy compares timestamp + size per file:
REM    - New files            -> copied
REM    - Changed/newer files  -> copied
REM    - Identical files      -> skipped
REM    - Newer in the TARGET  -> skipped (/XO)
REM  Nothing is EVER deleted from the backup. /MIR is deliberately not
REM  used, because /MIR deletes.
REM
REM  Sibling folder lidar_project_SNAPSHOT_prereorg_2026-08-12 is FROZEN.
REM  Never write to it. It is the pre-reorganization rollback point.
REM ============================================================

set "SRC=%~dp0.."
set "DST=E:\Colton\_BACKUPS\lidar_project_MIRROR"
set "LOG=%~dp0..\backup_to_E_Colton_last_run.log"

pushd "%SRC%" && set "SRC=%CD%" && popd

if not exist "E:\" (
    echo [ERROR] Drive E:\ is not available. Plug in the drive and re-run.
    pause
    exit /b 1
)

if not exist "E:\Colton\_BACKUPS\" mkdir "E:\Colton\_BACKUPS"

echo Copying new/changed files from:
echo   %SRC%
echo to:
echo   %DST%
echo.

REM /XJ: do not traverse junctions. (The junctions into
REM E:\lidar_project_data_DO_NOT_DELETE that the old script warned about are
REM gone -- their absence is what broke _prep_road_1m.py on 2026-08-06. The
REM flag is kept because it is free insurance if any are re-created.)
robocopy "%SRC%" "%DST%" /E /XO /XJ /FFT /R:2 /W:5 /MT:8 /NP /NDL /TEE /LOG:"%LOG%"

if %ERRORLEVEL% GEQ 8 (
    echo.
    echo [ERROR] Robocopy failed - exit code %ERRORLEVEL%. See %LOG%
    pause
    exit /b %ERRORLEVEL%
)

echo. >> "%DST%\_BACKUP_MANIFEST.txt"
echo run %DATE% %TIME%  robocopy exit %ERRORLEVEL% >> "%DST%\_BACKUP_MANIFEST.txt"

echo.
echo Done. Only new or revised files were copied. Log: %LOG%
pause
exit /b 0
