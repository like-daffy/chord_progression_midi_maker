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

# Ask user for platform choice
echo "What platform build do you want?"
echo "1. Apple Silicon (arm64)"
echo "2. Intel (x86_64)"
echo
read -p "Enter your choice (1 or 2): " platform_choice

# Ask for version
echo
read -p "Enter version number (e.g., 1.0, 1.1, 2.0): " VERSION

if [ -z "$VERSION" ]; then
    echo "ERROR: Version number cannot be empty"
    exit 1
fi

case $platform_choice in
    1)
        echo
        echo "Building for Apple Silicon (arm64)..."
        VENV_PATH=".venv"
        ARCH_PREFIX="arch -arm64"
        PLATFORM_NAME="Apple Silicon"
        PLATFORM_SUFFIX="arm64"
        ;;
    2)
        echo
        echo "Building for Intel (x86_64)..."
        VENV_PATH=".venv_intel"
        ARCH_PREFIX="arch -x86_64"
        PLATFORM_NAME="Intel"
        PLATFORM_SUFFIX="x86_64"
        ;;
    *)
        echo "ERROR: Invalid choice. Please enter 1 or 2"
        exit 1
        ;;
esac

echo

# Check if the required venv exists
if [ ! -d "$VENV_PATH" ]; then
    echo "ERROR: Virtual environment $VENV_PATH not found"
    echo
    if [ $platform_choice -eq 1 ]; then
        echo "Please create it with: python3 -m venv .venv"
    else
        echo "Please create it with: arch -x86_64 /usr/bin/python3 -m venv .venv_intel"
    fi
    exit 1
fi

# Deactivate any active virtual environment
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "Deactivating current virtual environment..."
    deactivate
fi

# Activate the appropriate virtual environment
echo "Activating $PLATFORM_NAME virtual environment..."
source "$VENV_PATH/bin/activate"

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to activate virtual environment"
    exit 1
fi

# Verify Python is available
if ! command -v python &> /dev/null; then
    echo "ERROR: Python is not available in the virtual environment"
    exit 1
fi

echo "Python version:"
$ARCH_PREFIX python --version
echo

# Verify architecture
echo "Target architecture:"
$ARCH_PREFIX python -c "import platform; print(platform.machine())"
echo

# Check Python version (PyQt6 requires 3.8+)
python_version=$($ARCH_PREFIX python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
required_version="3.8"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "ERROR: Python 3.8 or higher is required for PyQt6"
    echo "Current version: $python_version"
    exit 1
fi

echo "Installing dependencies..."
echo

# Upgrade pip first
$ARCH_PREFIX pip install --upgrade pip

# Install core requirements
echo "Installing core requirements..."
$ARCH_PREFIX pip install PyQt6>=6.6.1 midiutil==1.2.1
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install core dependencies"
    exit 1
fi

echo "Installing pygame for preview..."
$ARCH_PREFIX pip install pygame==2.5.2
if [ $? -ne 0 ]; then
    echo "WARNING: pygame installation failed - Preview will be disabled"
fi

echo "Installing PyInstaller..."
$ARCH_PREFIX pip install pyinstaller==6.3.0
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install PyInstaller"
    exit 1
fi

echo
echo "Building macOS application bundle for $PLATFORM_NAME..."
echo

# Clean previous builds
rm -rf dist build

# Verify ChordToMIDI.spec exists and has target_arch=None
if [ ! -f "ChordToMIDI.spec" ]; then
    echo "ERROR: ChordToMIDI.spec not found"
    echo "Please ensure the spec file exists with target_arch=None"
    exit 1
fi

# Build using PyInstaller with the spec file
$ARCH_PREFIX pyinstaller ChordToMIDI.spec

if [ $? -ne 0 ]; then
    echo
    echo "ERROR: Build failed"
    echo
    echo "Troubleshooting:"
    echo "1. Ensure all dependencies are installed"
    echo "2. Try running: $ARCH_PREFIX pip install --upgrade PyQt6 pygame"
    echo "3. Check for permission issues"
    echo "4. Verify ChordToMIDI.spec has target_arch=None"
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
    <string>${VERSION}</string>
    <key>CFBundleVersion</key>
    <string>${VERSION}</string>
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
    echo "Platform: $PLATFORM_NAME"
    echo "Version: $VERSION"
    echo "Application: dist/ChordToMIDI.app"
    echo
    
    # Start DMG packaging
    echo
    echo "============================================"
    echo " Creating DMG package..."
    echo "============================================"
    echo
    
    APP_NAME="ChordToMIDI"
    SOURCE_APP="dist/ChordToMIDI.app"
    VOLUME_NAME="ChordToMIDI ${VERSION}"
    VOLUME_ICON="chord_to_midi.icns"
    OUTPUT_DMG="dist/ChordToMIDI-${VERSION}-macos-${PLATFORM_SUFFIX}.dmg"
    TEMP_DMG="temp.dmg"
    
    # Check if icon file exists
    if [ ! -f "${VOLUME_ICON}" ]; then
        echo "WARNING: Icon file ${VOLUME_ICON} not found. Skipping custom icon."
        VOLUME_ICON=""
    fi
    
    # Remove existing DMG if it exists
    if [ -f "${OUTPUT_DMG}" ]; then
        echo "Removing existing DMG..."
        rm "${OUTPUT_DMG}"
    fi
    
    # Create a read-write DMG
    echo "Creating temporary DMG..."
    hdiutil create -volname "${VOLUME_NAME}" -srcfolder "${SOURCE_APP}" -ov -format UDRW "${TEMP_DMG}"
    
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create temporary DMG"
        exit 1
    fi
    
    # Mount the DMG
    echo "Mounting DMG..."
    MOUNT_DIR=$(hdiutil attach -readwrite -noverify -noautoopen "${TEMP_DMG}" | grep Volumes | sed 's/.*\/Volumes/\/Volumes/')
    
    if [ -z "$MOUNT_DIR" ]; then
        echo "ERROR: Failed to mount DMG"
        rm "${TEMP_DMG}"
        exit 1
    fi
    
    # Copy the icon file to the volume if it exists
    if [ -n "${VOLUME_ICON}" ] && [ -f "${VOLUME_ICON}" ]; then
        echo "Adding custom icon..."
        cp "${VOLUME_ICON}" "${MOUNT_DIR}/.VolumeIcon.icns"
        
        # Set the custom icon attribute (requires Xcode Command Line Tools)
        if command -v SetFile &> /dev/null; then
            SetFile -c icnC "${MOUNT_DIR}/.VolumeIcon.icns"
            SetFile -a C "${MOUNT_DIR}"
        else
            echo "WARNING: SetFile not found. Custom icon may not display correctly."
            echo "Install Xcode Command Line Tools with: xcode-select --install"
        fi
    fi
    
    # Unmount the DMG
    echo "Unmounting DMG..."
    hdiutil detach "${MOUNT_DIR}"
    
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to unmount DMG"
        rm "${TEMP_DMG}"
        exit 1
    fi
    
    # Convert to compressed read-only DMG
    echo "Compressing DMG..."
    hdiutil convert "${TEMP_DMG}" -format UDZO -o "${OUTPUT_DMG}"
    
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to compress DMG"
        rm "${TEMP_DMG}"
        exit 1
    fi
    
    # Clean up
    rm "${TEMP_DMG}"
    
    echo
    echo "============================================"
    echo " Package completed successfully!"
    echo "============================================"
    echo
    echo "Platform: $PLATFORM_NAME ($PLATFORM_SUFFIX)"
    echo "Version: $VERSION"
    echo "DMG Package: ${OUTPUT_DMG}"
    echo "Size: $(du -h "${OUTPUT_DMG}" | cut -f1)"
    echo
    echo
    echo "To distribute:"
    echo "  - Share the DMG file: ${OUTPUT_DMG}"
    echo "  - Users can drag the app to Applications folder"
    echo
    echo "IMPORTANT: No microphone permissions required!"
    echo "This app uses audio output only."
    echo "============================================"
    echo
fi