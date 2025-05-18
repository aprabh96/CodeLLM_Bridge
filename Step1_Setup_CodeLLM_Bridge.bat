@echo off
REM Check if the venv directory exists
if exist .\venv (
    echo Virtual environment 'venv' already exists.
    echo Activating virtual environment...
    CALL .\venv\Scripts\activate.bat
    echo Ensuring requirements are installed...
    python -m pip install -r requirements.txt
) else (
    echo Creating virtual environment 'venv'...
    python -m venv venv
    if errorlevel 1 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo Virtual environment 'venv' created successfully.
    echo Activating virtual environment...
    CALL .\venv\Scripts\activate.bat
    echo Installing requirements...
    python -m pip install -r requirements.txt
)
pause 