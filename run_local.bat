@echo off
REM Run the simulator on localhost: http://127.0.0.1:8000
cd /d "%~dp0"
python app.py --host 127.0.0.1 --port 8000
pause
