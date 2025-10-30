@echo off
REM Build script for Chord to MIDI Converter v1.0 - Windows
REM No microphone permissions required

echo ============================================
echo  Chord to MIDI Converter v1.0 - Windows Build
echo ============================================
echo.
echo  No microphone permissions required
echo  Playback only - no recording
echo.

REM Check Python version
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher
    pause
    exit /b 1
)

echo Installing dependencies...
echo.

REM Upgrade pip first
python -m pip install --upgrade pip

REM Install core requirements
echo Installing core requirements...
pip install PyQt6==6.6.1 midiutil==1.2.1
if %errorlevel% neq 0 (
    echo ERROR: Failed to install core dependencies
    pause
    exit /b 1
)

echo Installing pygame for preview...
pip install pygame==2.5.2
if %errorlevel% neq 0 (
    echo WARNING: pygame installation failed - Preview will be disabled
)

echo Installing PyInstaller...
pip install pyinstaller==6.3.0
if %errorlevel% neq 0 (
    echo ERROR: Failed to install PyInstaller
    pause
    exit /b 1
)

echo.
echo Building Windows executable...
echo.

REM Clean previous builds
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"
if exist "ChordToMIDI.spec" del "ChordToMIDI.spec"

REM Build executable
pyinstaller --onefile --windowed ^
    --name "ChordToMIDI" ^
    --distpath "./dist" ^
    --workpath "./build" ^
    --hidden-import "PyQt6" ^
    --hidden-import "PyQt6.QtCore" ^
    --hidden-import "PyQt6.QtGui" ^
    --hidden-import "PyQt6.QtWidgets" ^
    --hidden-import "midiutil" ^
    --hidden-import "pygame" ^
    --hidden-import "pygame.mixer" ^
    --add-data "README_v1.md;." ^
    --icon "chord_to_midi.ico" ^
    chord_to_midi_converter_qt_v1.py

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Build failed
    echo.
    echo Troubleshooting:
    echo 1. Ensure all dependencies are installed
    echo 2. Try running: pip install --upgrade PyQt6 pygame
    echo 3. Check for antivirus interference
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Build completed successfully!
echo ============================================
echo.
echo Executable: dist\ChordToMIDI.exe
echo Size: ~50 MB (includes all features)
echo.
echo Version 1.0 Features:
echo   ✓ Extended octave range (2-7, default 4)
echo   ✓ Fixed bass note handling
echo   ✓ BPM Control (1-300)
echo   ✓ MIDI Preview (no mic access needed)
echo   ✓ Drag-to-save functionality
echo   ✓ Cmaj7 chord support
echo.
echo To run: Double-click dist\ChordToMIDI.exe
echo.
echo IMPORTANT: No microphone permissions required!
echo This app uses audio output only.
echo ============================================
echo.

pause