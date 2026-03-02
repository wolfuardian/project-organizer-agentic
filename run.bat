@echo off
cd /d "%~dp0"
python -c "import PySide6" 2>nul || pip install PySide6
python main.py
pause
