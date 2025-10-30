#!/bin/bash

# Build script for Chord to MIDI Converter (PyQt6) - macOS
# This script builds a standalone macOS application bundle with PyQt6

echo "============================================"
echo "Chord to MIDI Converter (PyQt6) - macOS Build"
echo "============================================"
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

# Create virtual environment (recommended for clean build)
echo "Creating virtual environment..."
python3 -m venv build_env_qt
source build_env_qt/bin/activate

# Upgrade pip first
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing required dependencies..."
pip install -r requirements_qt.txt
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies"
    echo ""
    echo "If PyQt6 installation fails, try:"
    echo "  pip install --upgrade pip setuptools wheel"
    echo "  pip install PyQt6 midiutil pyinstaller"
    deactivate
    exit 1
fi

echo
echo "Building macOS application bundle with PyQt6..."
echo

# Clean previous builds
rm -rf dist build

# Build using PyInstaller with PyQt6-specific options
pyinstaller --onefile --windowed \
    --name "ChordToMIDI_Qt" \
    --osx-bundle-identifier "com.chordtomidi.converter.qt" \
    --distpath "./dist" \
    --workpath "./build" \
    --specpath "." \
    --hidden-import "PyQt6" \
    --hidden-import "PyQt6.QtCore" \
    --hidden-import "PyQt6.QtGui" \
    --hidden-import "PyQt6.QtWidgets" \
    --hidden-import "midiutil" \
    --icon "chord_to_midi.ico" \
    --add-data "README_Qt.md:." \
    chord_to_midi_converter_qt.py

if [ $? -ne 0 ]; then
    echo
    echo "ERROR: Build failed"
    echo "Common issues:"
    echo "- Ensure PyQt6 is properly installed"
    echo "- Try: pip install --upgrade PyQt6"
    echo "- Check all dependencies are satisfied"
    deactivate
    exit 1
fi

# Create a proper macOS app bundle structure
if [ -f "dist/ChordToMIDI_Qt" ]; then
    echo
    echo "Creating application bundle..."
    
    # Create app bundle structure
    mkdir -p "dist/ChordToMIDI_Qt.app/Contents/MacOS"
    mkdir -p "dist/ChordToMIDI_Qt.app/Contents/Resources"
    mkdir -p "dist/ChordToMIDI_Qt.app/Contents/Frameworks"
    
    # Move executable to app bundle
    mv "dist/ChordToMIDI_Qt" "dist/ChordToMIDI_Qt.app/Contents/MacOS/"
    
    # Create Info.plist with PyQt6 specific settings
    cat > "dist/ChordToMIDI_Qt.app/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleExecutable</key>
    <string>ChordToMIDI_Qt</string>
    <key>CFBundleIdentifier</key>
    <string>com.chordtomidi.converter.qt</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>ChordToMIDI Qt</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>2.0.0</string>
    <key>CFBundleVersion</key>
    <string>2</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.12</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSHumanReadableCopyright</key>
    <string>Chord to MIDI Converter (PyQt6) © 2024</string>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
    <key>NSSupportsAutomaticGraphicsSwitching</key>
    <true/>
</dict>
</plist>
EOF
    
    # Make executable
    chmod +x "dist/ChordToMIDI_Qt.app/Contents/MacOS/ChordToMIDI_Qt"
    
    # Code sign the app (if certificate is available)
    # Uncomment the following line if you have a developer certificate
    # codesign --force --deep --sign "Developer ID Application: Your Name" "dist/ChordToMIDI_Qt.app"
    
    echo
    echo "============================================"
    echo "Build completed successfully!"
    echo
    echo "Application location: dist/ChordToMIDI_Qt.app"
    echo
    echo "Features of PyQt6 version:"
    echo "- Modern, native macOS interface"
    echo "- Enhanced drag-and-drop support"
    echo "- Better Retina display support"
    echo "- Improved performance"
    echo
    echo "You can now run the application by:"
    echo "  1. Double-clicking dist/ChordToMIDI_Qt.app in Finder"
    echo "  2. Or from Terminal: open dist/ChordToMIDI_Qt.app"
    echo
    echo "To distribute the app, you can:"
    echo "  - Compress it: zip -r ChordToMIDI_Qt.zip dist/ChordToMIDI_Qt.app"
    echo "  - Create a DMG: hdiutil create -srcfolder dist/ChordToMIDI_Qt.app ChordToMIDI_Qt.dmg"
    echo "============================================"
    echo
fi

# Deactivate virtual environment
deactivate