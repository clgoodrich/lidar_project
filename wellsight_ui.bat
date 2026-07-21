@echo off
REM WellSight Control Panel — double-click launcher
cd /d "%~dp0"
echo Starting WellSight Control Panel...
echo A browser tab will open at http://localhost:8501
echo Close this window to stop the UI (running jobs keep going).
python -m streamlit run ui/app.py
pause
