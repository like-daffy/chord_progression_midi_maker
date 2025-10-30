#!/bin/bash

APP_NAME="ChordToMIDI"
VERSION="1.0"
SOURCE_APP="dist/ChordToMIDI.app"
VOLUME_NAME="ChordToMIDI 1.0"
VOLUME_ICON="chord_to_midi.icns"  # Path to your .icns file
OUTPUT_DMG="dist/ChordToMIDI-1.0.dmg"

# Create a read-write DMG
echo "Creating temporary DMG..."
hdiutil create -volname "${VOLUME_NAME}" -srcfolder "${SOURCE_APP}" -ov -format UDRW temp.dmg

# Mount the DMG
echo "Mounting DMG..."
MOUNT_DIR=$(hdiutil attach -readwrite -noverify -noautoopen temp.dmg | grep Volumes | sed 's/.*\/Volumes/\/Volumes/')

# Copy the icon file to the volume
echo "Adding custom icon..."
cp "${VOLUME_ICON}" "${MOUNT_DIR}/.VolumeIcon.icns"

# Set the custom icon attribute
SetFile -c icnC "${MOUNT_DIR}/.VolumeIcon.icns"
SetFile -a C "${MOUNT_DIR}"

# Unmount the DMG
echo "Unmounting DMG..."
hdiutil detach "${MOUNT_DIR}"

# Convert to compressed read-only DMG
echo "Compressing DMG..."
hdiutil convert temp.dmg -format UDZO -o "${OUTPUT_DMG}"

# Clean up
rm temp.dmg

echo "Done! Created: ${OUTPUT_DMG}"