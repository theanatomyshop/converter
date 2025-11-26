@echo off
setlocal

REM Ensure the Anaconda activation script exists before calling it
set "ENV_ACTIVATE=%USERPROFILE%\anaconda3\Scripts\activate.bat"
if not exist "%ENV_ACTIVATE%" (
    echo Could not find Anaconda activate script at "%ENV_ACTIVATE%".
    echo Update ENV_ACTIVATE in run_converter.bat to match your installation path.
    goto end
)

call "%ENV_ACTIVATE%" myenv

REM Work from the directory where this batch file resides
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%" || (
    echo Failed to change directory to "%SCRIPT_DIR%".
    goto end
)

REM Run the converter script from this directory
if exist converter.py (
    python converter.py
) else (
    echo converter.py not found in "%SCRIPT_DIR%".
)

:end
pause
endlocal
