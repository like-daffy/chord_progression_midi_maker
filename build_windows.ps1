# Build script for Chord to MIDI Converter v1.0 - PowerShell
# No microphone permissions required

Write-Host "============================================" -ForegroundColor Cyan
Write-Host " Chord to MIDI Converter v1.0 - Windows Build" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host " No microphone permissions required" -ForegroundColor Green
Write-Host " Playback only - no recording" -ForegroundColor Green
Write-Host ""

# Check Python version
try {
    python --version | Out-Null
    if ($LASTEXITCODE -ne 0) { throw }
} catch {
    Write-Host "ERROR: Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Python 3.8 or higher"
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Installing dependencies..." -ForegroundColor Yellow
Write-Host ""

# Upgrade pip first
python -m pip install --upgrade pip

# Install core requirements
Write-Host "Installing core requirements..." -ForegroundColor Yellow
pip install PyQt6>=6.6.1 midiutil==1.2.1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to install core dependencies" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Installing pygame for preview..." -ForegroundColor Yellow
pip install pygame==2.5.2
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: pygame installation failed - Preview will be disabled" -ForegroundColor Yellow
}

Write-Host "Installing PyInstaller..." -ForegroundColor Yellow
pip install pyinstaller==6.3.0
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to install PyInstaller" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "Building Windows executable..." -ForegroundColor Yellow
Write-Host ""

# Clean previous builds
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "ChordToMIDI.spec") { Remove-Item -Force "ChordToMIDI.spec" }

# Build executable
pyinstaller --onefile --windowed `
    --name "ChordToMIDI" `
    --distpath "./dist" `
    --workpath "./build" `
    --hidden-import "PyQt6" `
    --hidden-import "PyQt6.QtCore" `
    --hidden-import "PyQt6.QtGui" `
    --hidden-import "PyQt6.QtWidgets" `
    --hidden-import "midiutil" `
    --hidden-import "pygame.mixer" `
    --hidden-import "pygame.mixer_music" `
    --exclude-module "pygame.sndarray" `
    --exclude-module "pygame.surfarray" `
    --exclude-module "pygame.camera" `
    --exclude-module "pygame.freetype" `
    --exclude-module "numpy" `
    --exclude-module "numpy.core" `
    --exclude-module "scipy" `
    --add-data "README.md;." `
    --icon "chord_to_midi.ico" `
    chord_to_midi_converter.py

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Build failed" -ForegroundColor Red
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "1. Ensure all dependencies are installed"
    Write-Host "2. Try running: pip install --upgrade PyQt6 pygame"
    Write-Host "3. Check for antivirus interference"
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host " Build completed successfully!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Executable: dist\ChordToMIDI.exe"
Write-Host "Size: ~50 MB (includes all features)"
Write-Host ""
Write-Host "Version 1.0 Features:" -ForegroundColor Cyan
Write-Host "  ✓ Extended octave range (2-7, default 4)"
Write-Host "  ✓ Fixed bass note handling"
Write-Host "  ✓ BPM Control (1-300)"
Write-Host "  ✓ MIDI Preview (no mic access needed)"
Write-Host "  ✓ Drag-to-save functionality"
Write-Host "  ✓ Cmaj7 chord support"
Write-Host ""
Write-Host "To run: Double-click dist\ChordToMIDI.exe"
Write-Host ""
Write-Host "IMPORTANT: No microphone permissions required!" -ForegroundColor Green
Write-Host "This app uses audio output only."
Write-Host "============================================"
Write-Host ""

Read-Host "Press Enter to exit"