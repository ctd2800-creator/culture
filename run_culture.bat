@echo off
cd /d "%~dp0"
set CULTURE_PORT=5051
echo Starting Culture app on http://127.0.0.1:5051
python "%~dp0culture_app.py"
pause
