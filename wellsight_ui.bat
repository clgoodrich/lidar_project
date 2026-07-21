@echo off
REM WellSight Control Panel - double-click launcher
cd /d "%~dp0"
echo ============================================
echo  WellSight Control Panel
echo  Opening http://localhost:8501 in your browser...
echo  (if no tab opens, paste that URL into your browser)
echo  Close this window or press Ctrl+C to stop.
echo ============================================
python -m streamlit run ui/app.py --server.headless false --server.port 8501
echo.
echo Streamlit exited. Press a key to close.
pause >nul
