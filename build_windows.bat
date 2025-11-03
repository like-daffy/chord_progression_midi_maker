@echo off
REM Build script for Chord to MIDI Converter - Windows
REM No microphone permissions required

echo ============================================
echo  Chord to MIDI Converter - Windows Build
echo ============================================
echo.
echo  No microphone permissions required
echo  Playback only - no recording
echo.

REM Ask for version
set /p VERSION="Enter version number (e.g., 1.0, 1.1, 2.0): "
if "%VERSION%"=="" (
    echo ERROR: Version number cannot be empty
    pause
    exit /b 1
)

echo.
echo Building version: %VERSION%
echo Platform: Windows x64
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
pip install PyQt6>=6.6.1 midiutil==1.2.1
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
    --hidden-import "pygame.mixer" ^
    --hidden-import "pygame.mixer_music" ^
    --exclude-module "pygame.sndarray" ^
    --exclude-module "pygame.surfarray" ^
    --exclude-module "pygame.camera" ^
    --exclude-module "pygame.freetype" ^
    --exclude-module "numpy" ^
    --exclude-module "numpy.core" ^
    --exclude-module "scipy" ^
    --add-data "README.md;." ^
    --icon "chord_to_midi.ico" ^
    chord_to_midi_converter.py

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
echo Version: %VERSION%
echo Platform: Windows x64
echo Executable: dist\ChordToMIDI.exe
echo.

REM Create ZIP package
echo.
echo ============================================
echo  Creating ZIP package...
echo ============================================
echo.

set ZIP_NAME=ChordToMIDI-%VERSION%-win-x64.zip
set ZIP_PATH=dist\%ZIP_NAME%

REM Remove existing ZIP if it exists
if exist "%ZIP_PATH%" (
    echo Removing existing ZIP...
    del "%ZIP_PATH%"
)

REM Create temporary folder for packaging
set TEMP_FOLDER=dist\ChordToMIDI-%VERSION%
if exist "%TEMP_FOLDER%" rmdir /s /q "%TEMP_FOLDER%"
mkdir "%TEMP_FOLDER%"

REM Copy files
echo Copying files...
copy "dist\ChordToMIDI.exe" "%TEMP_FOLDER%\"
if exist "README.md" copy "README.md" "%TEMP_FOLDER%\"

REM Create ZIP using PowerShell (available on Windows 7+)
echo Compressing files...
powershell -command "Compress-Archive -Path '%TEMP_FOLDER%' -DestinationPath '%ZIP_PATH%' -Force"

if %errorlevel% neq 0 (
    echo ERROR: Failed to create ZIP package
    echo Please ensure PowerShell is available
    rmdir /s /q "%TEMP_FOLDER%"
    pause
    exit /b 1
)

REM Clean up temp folder
rmdir /s /q "%TEMP_FOLDER%"

echo.
echo ============================================
echo  Package completed successfully!
echo ============================================
echo.
echo Version: %VERSION%
echo Platform: Windows x64
echo ZIP Package: %ZIP_PATH%
echo.
echo Features:
echo   ✓ Extended octave range (2-7, default 4)
echo   ✓ Fixed bass note handling
echo   ✓ BPM Control (1-300)
echo   ✓ MIDI Preview (no mic access needed)
echo   ✓ Drag-to-save functionality
echo   ✓ Cmaj7 chord support
echo.
echo To distribute:
echo   - Share the ZIP file: %ZIP_PATH%
echo   - Users can extract and run ChordToMIDI.exe
echo.
echo IMPORTANT: No microphone permissions required!
echo This app uses audio output only.
echo ============================================
echo.

pause