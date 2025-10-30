@echo off
REM Build script for Chord to MIDI Converter - Windows
REM This script builds a standalone Windows executable

echo ========================================
echo Chord to MIDI Converter - Windows Build
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher
    pause
    exit /b 1
)

echo Installing required dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo Building Windows executable...
echo.

REM Clean previous builds
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

REM Build using PyInstaller
pyinstaller --onefile --windowed ^
    --name "ChordToMIDI" ^
    --distpath "./dist" ^
    --workpath "./build" ^
    --specpath "." ^
    --hidden-import "midiutil" ^
    --hidden-import "tkinter" ^
    --add-data "README.md;." ^
    chord_to_midi_converter.py

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Build failed
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build completed successfully!
echo.
echo Executable location: dist\ChordToMIDI.exe
echo.
echo You can now run the application by double-clicking:
echo   dist\ChordToMIDI.exe
echo ========================================
echo.

pause
