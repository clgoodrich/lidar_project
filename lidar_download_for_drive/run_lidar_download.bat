@echo off
rem Starts or resumes the lidar tile download. Safe to close and rerun.
rem Usage   run_lidar_download.bat Pennsylvania   (6 windows, about 12.6 GB)
rem         run_lidar_download.bat               (all 52 windows, about 129 GB)
rem Saves on the same drive as this repo. The full run (129 GB) needs that much free space.
rem Tracking file  <repo>\data\_source\lidar\lidar_us_windows\download_status.csv
rem Log file       <repo>\data\_source\lidar\lidar_us_windows\download_log.txt
python "%~dp0..\..\..\..\notebooks\wellsight_v2\s1_build\_fetch_lidar_windows_us.py" --window-prefix "%~1"
pause
