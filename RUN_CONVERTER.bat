@echo off
title DNG to JPG Converter
echo.
echo  ===================================
echo   DNG to JPG Converter - Setup
echo  ===================================
echo.

:: Check Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python is not installed or not in PATH.
    echo  Download it from https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

:: Install dependencies
echo  Installing required packages...
pip install rawpy Pillow --quiet
echo  Done.
echo.

:: Launch the app
echo  Launching converter...
python "%~dp0dng_to_jpg_converter.py"