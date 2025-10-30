# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Chord to MIDI Converter
Builds for both Windows and macOS
"""

import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

a = Analysis(
    ['chord_to_midi_converter.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Add any data files here if needed
        # For example: ('chords.csv', '.'),
    ],
    hiddenimports=[
        'midiutil',
        'midiutil.MidiFile',
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'tkinter.filedialog',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Configure executable settings based on platform
if sys.platform == 'win32':
    # Windows configuration
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name='ChordToMIDI',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,  # Set to False for GUI application
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon='chord_icon.ico' if os.path.exists('chord_icon.ico') else None,
    )
elif sys.platform == 'darwin':
    # macOS configuration
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name='ChordToMIDI',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,  # Set to False for GUI application
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon='chord_icon.icns' if os.path.exists('chord_icon.icns') else None,
    )
    
    # Create macOS app bundle
    app = BUNDLE(
        exe,
        name='ChordToMIDI.app',
        icon='chord_icon.icns' if os.path.exists('chord_icon.icns') else None,
        bundle_identifier='com.chordtomidi.converter',
        info_plist={
            'CFBundleName': 'Chord to MIDI Converter',
            'CFBundleDisplayName': 'Chord to MIDI Converter',
            'CFBundleGetInfoString': "Convert chord progressions to MIDI files",
            'CFBundleIdentifier': "com.chordtomidi.converter",
            'CFBundleVersion': "1.0.0",
            'CFBundleShortVersionString': "1.0.0",
            'NSHighResolutionCapable': 'True',
            'LSMinimumSystemVersion': '10.12.0',
        }
    )
else:
    # Linux/Other configuration
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name='ChordToMIDI',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
