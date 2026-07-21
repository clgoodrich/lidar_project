@echo off
REM Roads Studio - double-click to launch the road-extraction knob board.
cd /d "%~dp0"
title Roads Studio
echo ============================================
echo  Roads Studio
echo  Opening http://127.0.0.1:8095/ in your browser...
echo  (if no tab opens, paste that URL into your browser)
echo  Close this window to stop.
echo ============================================
python -m roads_studio.main
echo.
echo Roads Studio exited. Press any key to close.
pause >nul
