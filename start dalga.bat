@echo off
cd /d "%~dp0"
where pythonw >nul 2>nul && (start "" pythonw "dalga.py" & exit /b)
where pyw >nul 2>nul && (start "" pyw "dalga.py" & exit /b)
start "" python "dalga.py"