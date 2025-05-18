@echo off
REM Activate the virtual environment
if exist .\venv\Scripts\activate.bat (
    echo Activating virtual environment...
    CALL .\venv\Scripts\activate.bat
) else (
    echo Virtual environment not found. Please run Step1_Setup_CodeLLM_Bridge.bat first.
    pause
    exit /b 1
)

REM Run the Python script
echo Running CodeLLM Bridge...
python CodeLLM_Bridge.py

pause 