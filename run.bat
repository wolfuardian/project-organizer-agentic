@echo off
cd /d "%~dp0"
powershell -Command "Get-Process python* -ErrorAction SilentlyContinue | Where-Object {$_.CommandLine -like '*main.py*'} | Stop-Process -Force" 2>nul
python -c "import PySide6" 2>nul || pip install PySide6
start "" python main.py
