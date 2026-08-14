@echo off
setlocal
set "SAMPLE_DIR=%~dp0"
set "PYTHON_EXE=%SAMPLE_DIR%..\..\..\ChurchManager\.runtime-venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo ChurchManager's Python environment could not be found.
    echo Expected: %PYTHON_EXE%
    pause
    exit /b 1
)

"%PYTHON_EXE%" "%SAMPLE_DIR%app.py"
if errorlevel 1 pause
