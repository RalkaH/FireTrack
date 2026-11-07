@echo off
rem FireTrack.bat - zapusk FireTrack: server i brauzer. Ostanovka: zakryt eto okno.
chcp 65001 >nul
cd /d "%~dp0"
title FireTrack

if exist ".venv\Scripts\python.exe" goto run

echo Pervyy zapusk: sozdayu okruzhenie i stavlyu zavisimosti...
python -m venv .venv
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed

:run
".venv\Scripts\python.exe" run.py
if errorlevel 1 goto failed
goto :eof

:failed
echo.
echo FireTrack ne zapustilsya. Oshibka vyshe.
pause
