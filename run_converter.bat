@echo off
setlocal

REM Activate Anaconda
call "C:\ProgramData\anaconda3\condabin\activate.bat" myenv

REM Change to the folder where this BAT file is located
cd /d "%~dp0"

REM Run the python script
python converter.py

pause
endlocal
