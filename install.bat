@echo off
rem ----------------------------------------
rem Detect the folder where this script lives
rem ----------------------------------------
set "script_path=%~dp0"
if "%script_path:~-1%"=="\" set "script_path=%script_path:~0,-1%"

rem ----------------------------------------
rem Use that as the project directory (and venv location)
rem ----------------------------------------
set "project_dir=%script_path%"
set "venv_dir=%project_dir%"

rem ----------------------------------------
rem 1) Create virtual environment right in the project folder
rem ----------------------------------------
python -m venv "%venv_dir%"

rem ----------------------------------------
rem 2) Activate virtual environment
rem ----------------------------------------
call "%venv_dir%\Scripts\activate"

rem ----------------------------------------
rem 3) Install requirements from the project root
rem ----------------------------------------
pip install -r "%project_dir%\requirements.txt"

rem ----------------------------------------
rem 4) Deactivate virtual environment
rem ----------------------------------------
deactivate

echo.
echo ========================================
echo   Installation complete!
echo   Project folder (with venv): %project_dir%
echo ========================================
pause
