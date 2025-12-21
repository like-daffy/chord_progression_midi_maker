# Build script for Chord to MIDI Converter - PowerShell
# No microphone permissions required

Write-Host "============================================" -ForegroundColor Cyan
Write-Host " Chord to MIDI Converter - Windows Build" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host " No microphone permissions required" -ForegroundColor Green
Write-Host " Playback only - no recording" -ForegroundColor Green
Write-Host ""

# Ask for version
$VERSION = Read-Host "Enter version number (e.g., 1.0, 1.1, 2.0)"
if ([string]::IsNullOrWhiteSpace($VERSION)) {
    Write-Host "ERROR: Version number cannot be empty" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "Building version: $VERSION" -ForegroundColor Yellow
Write-Host "Platform: Windows x64" -ForegroundColor Yellow
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

# Check if virtual environment is activated
Write-Host "Checking virtual environment..." -ForegroundColor Yellow
if (-not $env:VIRTUAL_ENV) {
    Write-Host "Virtual environment is not activated" -ForegroundColor Yellow
    
    # Check if .venv exists
    $VENV_PATH = ".\.venv\Scripts\Activate.ps1"
    if (Test-Path $VENV_PATH) {
        Write-Host "Activating virtual environment: $VENV_PATH" -ForegroundColor Yellow
        try {
            & $VENV_PATH
            if ($LASTEXITCODE -eq 0 -or $env:VIRTUAL_ENV) {
                Write-Host "Virtual environment activated successfully!" -ForegroundColor Green
            } else {
                Write-Host "WARNING: Failed to activate virtual environment" -ForegroundColor Yellow
                Write-Host "Proceeding with system Python..." -ForegroundColor Yellow
            }
        } catch {
            Write-Host "WARNING: Error activating virtual environment" -ForegroundColor Yellow
            Write-Host $_.Exception.Message -ForegroundColor Yellow
            Write-Host "Proceeding with system Python..." -ForegroundColor Yellow
        }
    } else {
        Write-Host "WARNING: Virtual environment not found at $VENV_PATH" -ForegroundColor Yellow
        Write-Host "Proceeding with system Python..." -ForegroundColor Yellow
    }
} else {
    Write-Host "Virtual environment is already activated: $env:VIRTUAL_ENV" -ForegroundColor Green
}
Write-Host ""

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
Write-Host "Version: $VERSION" -ForegroundColor Cyan
Write-Host "Platform: Windows x64" -ForegroundColor Cyan
Write-Host "Executable: dist\ChordToMIDI.exe"
Write-Host ""

# Create ZIP package
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " Creating ZIP package..." -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$ZIP_NAME = "ChordToMIDI-$VERSION-win-x64.zip"
$ZIP_PATH = "dist\$ZIP_NAME"

# Remove existing ZIP if it exists
if (Test-Path $ZIP_PATH) {
    Write-Host "Removing existing ZIP..." -ForegroundColor Yellow
    Remove-Item -Force $ZIP_PATH
}

# Create ZIP archive
Write-Host "Compressing files..." -ForegroundColor Yellow
try {
    # Create a temporary folder for packaging
    $TEMP_FOLDER = "dist\ChordToMIDI-$VERSION"
    if (Test-Path $TEMP_FOLDER) {
        Remove-Item -Recurse -Force $TEMP_FOLDER
    }
    New-Item -ItemType Directory -Path $TEMP_FOLDER | Out-Null
    
    # Copy executable and README
    Copy-Item "dist\ChordToMIDI.exe" $TEMP_FOLDER
    if (Test-Path "README.md") {
        Copy-Item "README.md" $TEMP_FOLDER
    }
    
    # Create ZIP
    Compress-Archive -Path $TEMP_FOLDER -DestinationPath $ZIP_PATH -Force
    
    # Clean up temp folder
    Remove-Item -Recurse -Force $TEMP_FOLDER
    
    $FILE_SIZE = (Get-Item $ZIP_PATH).Length / 1MB
    $FILE_SIZE = [math]::Round($FILE_SIZE, 2)
    
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host " Package completed successfully!" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Version: $VERSION" -ForegroundColor Cyan
    Write-Host "Platform: Windows x64" -ForegroundColor Cyan
    Write-Host "ZIP Package: $ZIP_PATH" -ForegroundColor Green
    Write-Host "Size: $FILE_SIZE MB"
    Write-Host ""

    Write-Host "To distribute:" -ForegroundColor Yellow
    Write-Host "  - Share the ZIP file: $ZIP_PATH"
    Write-Host "  - Users can extract and run ChordToMIDI.exe"
    Write-Host ""
    Write-Host "IMPORTANT: No microphone permissions required!" -ForegroundColor Green
    Write-Host "This app uses audio output only."
    Write-Host "============================================"
    Write-Host ""
    
} catch {
    Write-Host "ERROR: Failed to create ZIP package" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
}

Read-Host "Press Enter to exit"