@echo off
REM Activate Anaconda environment
call "%USERPROFILE%\anaconda3\Scripts\activate" myenv

REM Navigate to the script directory
cd /d "C:\Users\thean\OneDrive\Desktop\Working\Amazon XML"

REM Run the converter script
python converter.py

REM Keep the window open to view the output
pause
