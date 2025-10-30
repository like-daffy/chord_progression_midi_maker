#!/bin/bash

# Build script for Chord to MIDI Converter v1.0 - macOS
# No microphone permissions required

echo "============================================"
echo " Chord to MIDI Converter v1.0 - macOS Build"
echo "============================================"
echo
echo " No microphone permissions required"
echo " Playback only - no recording"
echo

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

echo "Python version:"
python3 --version
echo

# Check Python version (PyQt6 requires 3.8+)
python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
required_version="3.8"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "ERROR: Python 3.8 or higher is required for PyQt6"
    echo "Current version: $python_version"
    exit 1
fi

echo "Installing dependencies..."
echo

# Upgrade pip first
python3 -m pip install --upgrade pip

# Install core requirements
echo "Installing core requirements..."
pip3 install PyQt6>=6.6.1 midiutil==1.2.1
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install core dependencies"
    exit 1
fi

echo "Installing pygame for preview..."
pip3 install pygame==2.5.2
if [ $? -ne 0 ]; then
    echo "WARNING: pygame installation failed - Preview will be disabled"
fi

echo "Installing PyInstaller..."
pip3 install pyinstaller==6.3.0
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install PyInstaller"
    exit 1
fi

echo
echo "Building macOS application bundle..."
echo

# Clean previous builds
rm -rf dist build ChordToMIDI.spec

# Build using PyInstaller with exclusions
pyinstaller --onefile --windowed \
    --name "ChordToMIDI" \
    --osx-bundle-identifier "com.chordtomidi.converter" \
    --distpath "./dist" \
    --workpath "./build" \
    --specpath "." \
    --hidden-import "PyQt6" \
    --hidden-import "PyQt6.QtCore" \
    --hidden-import "PyQt6.QtGui" \
    --hidden-import "PyQt6.QtWidgets" \
    --hidden-import "midiutil" \
    --hidden-import "pygame.mixer" \
    --hidden-import "pygame.mixer_music" \
    --exclude-module "pygame.sndarray" \
    --exclude-module "pygame.surfarray" \
    --exclude-module "pygame.camera" \
    --exclude-module "pygame.freetype" \
    --exclude-module "numpy" \
    --exclude-module "numpy.core" \
    --exclude-module "scipy" \
    --icon "chord_to_midi.ico" \
    --add-data "README.md:." \
    chord_to_midi_converter.py

if [ $? -ne 0 ]; then
    echo
    echo "ERROR: Build failed"
    echo
    echo "Troubleshooting:"
    echo "1. Ensure all dependencies are installed"
    echo "2. Try running: pip3 install --upgrade PyQt6 pygame"
    echo "3. Check for permission issues"
    exit 1
fi

# Create Info.plist for the app bundle
if [ -d "dist/ChordToMIDI.app" ]; then
    echo
    echo "Configuring application bundle..."
    
    cat > "dist/ChordToMIDI.app/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleExecutable</key>
    <string>ChordToMIDI</string>
    <key>CFBundleIdentifier</key>
    <string>com.chordtomidi.converter</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>ChordToMIDI</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.12</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSHumanReadableCopyright</key>
    <string>Chord to MIDI Converter © 2024</string>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
    <key>NSSupportsAutomaticGraphicsSwitching</key>
    <true/>
</dict>
</plist>
EOF
    
    # Make executable
    chmod +x "dist/ChordToMIDI.app/Contents/MacOS/ChordToMIDI"
    
    echo
    echo "============================================"
    echo " Build completed successfully!"
    echo "============================================"
    echo
    echo "Application: dist/ChordToMIDI.app"
    echo "Size: ~50 MB (includes all features)"
    echo
    echo "Version 1.0 Features:"
    echo "  ✓ Extended octave range (2-7, default 4)"
    echo "  ✓ Fixed bass note handling"
    echo "  ✓ BPM Control (1-300)"
    echo "  ✓ MIDI Preview (no mic access needed)"
    echo "  ✓ Drag-to-save functionality"
    echo "  ✓ Cmaj7 chord support"
    echo
    echo "To run: Double-click dist/ChordToMIDI.app"
    echo
    echo "To distribute:"
    echo "  - Create ZIP: zip -r ChordToMIDI.zip dist/ChordToMIDI.app"
    echo "  - Create DMG: hdiutil create -srcfolder dist/ChordToMIDI.app ChordToMIDI.dmg"
    echo
    echo "IMPORTANT: No microphone permissions required!"
    echo "This app uses audio output only."
    echo "============================================"
    echo
fi