#!/bin/bash

# Build script for Chord to MIDI Converter - macOS
# This script builds a standalone macOS application bundle

echo "========================================"
echo "Chord to MIDI Converter - macOS Build"
echo "========================================"
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

# Create virtual environment (recommended for clean build)
echo "Creating virtual environment..."
python3 -m venv build_env
source build_env/bin/activate

# Install dependencies
echo "Installing required dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies"
    deactivate
    exit 1
fi

echo
echo "Building macOS application bundle..."
echo

# Clean previous builds
rm -rf dist build

# Build using PyInstaller
pyinstaller --onefile --windowed \
    --name "ChordToMIDI" \
    --osx-bundle-identifier "com.chordtomidi.converter" \
    --distpath "./dist" \
    --workpath "./build" \
    --specpath "." \
    --hidden-import "midiutil" \
    --hidden-import "tkinter" \
    --add-data "README.md:." \
    chord_to_midi_converter.py

if [ $? -ne 0 ]; then
    echo
    echo "ERROR: Build failed"
    deactivate
    exit 1
fi

# Create a proper macOS app bundle structure
if [ -f "dist/ChordToMIDI" ]; then
    echo
    echo "Creating application bundle..."
    
    # Create app bundle structure
    mkdir -p "dist/ChordToMIDI.app/Contents/MacOS"
    mkdir -p "dist/ChordToMIDI.app/Contents/Resources"
    
    # Move executable to app bundle
    mv "dist/ChordToMIDI" "dist/ChordToMIDI.app/Contents/MacOS/"
    
    # Create Info.plist
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
</dict>
</plist>
EOF
    
    # Make executable
    chmod +x "dist/ChordToMIDI.app/Contents/MacOS/ChordToMIDI"
    
    # Code sign the app (if certificate is available)
    # Uncomment the following line if you have a developer certificate
    # codesign --force --deep --sign "Developer ID Application: Your Name" "dist/ChordToMIDI.app"
    
    echo
    echo "========================================"
    echo "Build completed successfully!"
    echo
    echo "Application location: dist/ChordToMIDI.app"
    echo
    echo "You can now run the application by:"
    echo "  1. Double-clicking dist/ChordToMIDI.app in Finder"
    echo "  2. Or from Terminal: open dist/ChordToMIDI.app"
    echo
    echo "To distribute the app, you can:"
    echo "  - Compress it: zip -r ChordToMIDI.zip dist/ChordToMIDI.app"
    echo "  - Create a DMG: hdiutil create -srcfolder dist/ChordToMIDI.app ChordToMIDI.dmg"
    echo "========================================"
    echo
fi

# Deactivate virtual environment
deactivate
