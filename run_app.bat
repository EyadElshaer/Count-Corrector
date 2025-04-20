@echo off
echo Starting Count Corrector...
python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Error running the application. Please make sure Python is installed.
    echo.
    echo You can download Python from: https://www.python.org/downloads/
    echo.
    pause
) 