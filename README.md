# Chord to MIDI Converter (PyQt6)

A professional desktop application for converting chord progressions into MIDI files with BPM control, real-time preview, and drag-to-save functionality. Now with **bi-directional MIDI support** - convert chords to MIDI or analyze MIDI files to extract chord progressions.

## 🎵 Key Features

### Core Functionality
- **40+ Chord Types**: Major, minor, seventh, suspended, augmented, diminished, and extended chords
- **Smart Notation**: Automatic flat-to-sharp conversion (Bb→A#, Db→C#)
- **Flexible Timing**: Single chords = 1 beat, bracketed chords share beats equally
- **Slash Chord Support**: Bass notes automatically placed one octave lower
- **Extended Octave Range**: Choose from octaves 2-7 (default: 4)
- **Cross-Platform**: Windows, macOS, and Linux compatible
- **BPM Control**: Visual slider and manual input (1-300 BPM)
- **MIDI Preview**: Listen before saving (no microphone access needed)
- **Drag-to-Save**: Drag MIDI display directly to Desktop or folders
- **Smart Naming**: Automatic file naming with progression and BPM
- **🆕 MIDI Drag-In**: Drag external MIDI files into the app to extract chord progressions
- **Reverse Conversion**: Analyze MIDI files and convert them back to chord notation
- **Updated Database**: Including Cmaj7 chord support

## 📦 Installation

### Quick Start

```bash
# Install with preview support
pip install PyQt6 midiutil pygame

# Run the application
python chord_to_midi_converter_qt_v1.py
```

### Using Requirements File

```bash
# Install all dependencies
pip install -r requirements_v1.txt
```

### Minimal Installation (No Preview)

```bash
# Core functionality only
pip install PyQt6 midiutil
```

## 🚀 Usage Guide

### Two-Way Conversion

#### 🎹 Chords → MIDI (Original Feature)

1. **Set Parameters**
   - Select octave (2-7, default: 4)
   - Adjust BPM (1-300, default: 120)

2. **Enter Chord Progression**
   - Use standard chord notation
   - Separate chords with hyphens (-)

3. **Generate MIDI**
   - Click "Proceed" or press Enter

4. **Preview (Optional)**
   - Click "▶ Preview" to listen
   - Click "■ Stop" to end playback

5. **Save Your File**
   - Drag the blue area to any folder
   - File saves automatically with descriptive name

#### 🎼 MIDI → Chords (New Feature)

1. **Drag MIDI File**
   - Drag any .mid or .midi file from your file explorer
   - Drop it anywhere in the application window

2. **Automatic Analysis**
   - App analyzes note patterns
   - Detects chord types and progressions
   - Extracts timing and BPM information

3. **View Results**
   - Chord progression appears in the input field
   - BPM automatically updates to match source file
   - Edit and modify as needed

4. **Re-Export (Optional)**
   - Adjust parameters if desired
   - Generate new MIDI with modified settings

### Chord Notation

#### Basic Examples
```
C - G - Am - F              # Simple progression
Dm7 - G7 - CM7             # Jazz progression
Am7/E - E/G# - Am - F      # With bass notes
```

#### Timing with Brackets
```
[C - G] - Am - F           # C and G share 1 beat
Am - [F - G - C]           # F, G, C each get 1/3 beat
[Dm7 - G7] - [CM7 - C6]    # Each pair shares 1 beat
```

### Supported Chords

| Type | Examples |
|------|----------|
| **Major** | C, D, E, F, G, A, B |
| **Minor** | Cm, Dm, Em, Fm, Gm, Am, Bm |
| **Seventh** | C7, CM7, Cmaj7, Cm7 |
| **Suspended** | Csus2, Csus4, C7sus4 |
| **Extended** | C6, C9, C11, C13, Cadd9 |
| **Altered** | Caug, Cdim, C-5, C+5 |
| **Slash** | C/G, Am7/E, F/C |

## 🎹 Fixed Issues

### Bass Note Handling
- Bass notes in slash chords now correctly transpose
- Example: A/E with octave 4 → E3 bass note (not C#3)

### No Microphone Access
- Removed sounddevice dependency
- Uses pygame default output only
- No recording permissions needed

### Extended Octave Range
- Now supports octaves 2-7
- Default changed to octave 4
- Better range for various instruments

## 🔧 System Requirements

- **Python**: 3.8 or higher
- **OS**: Windows 10+, macOS 10.12+, Linux with Qt6
- **RAM**: 256 MB minimum
- **Storage**: 100 MB for app and dependencies
- **Audio**: Any output device (no input needed)

## 🧪 Testing

### Test Chord to MIDI
```python
# A/E chord should produce:
# - A major chord: A, C#, E
# - E bass note (one octave lower)
# With octave 4: E3, A4, C#5, E5
```

### Test MIDI Drag-In
```
1. Export a simple progression (e.g., C - G - Am - F)
2. Drag the exported .mid file back into the app
3. Verify the chord progression matches
4. Check BPM is correctly detected
```

## 🛠️ Building Executables

### Windows
```cmd
pyinstaller --onefile --windowed ^
  --hidden-import pygame ^
  --name "ChordToMIDI" ^
  chord_to_midi_converter_qt_v1.py
```

### macOS
```bash
pyinstaller --onefile --windowed \
  --hidden-import pygame \
  --name "ChordToMIDI" \
  --osx-bundle-identifier "com.chordtomidi.v1" \
  chord_to_midi_converter_qt_v1.py
```

### Linux
```bash
pyinstaller --onefile --windowed \
  --hidden-import pygame \
  --name "ChordToMIDI" \
  chord_to_midi_converter_qt_v1.py
```

## 📊 Technical Details

### Architecture
- **Main Class**: `ChordToMIDIQt` - Application window and logic
- **Drag Widget**: `DraggableMidiDisplay` - Drag-to-save functionality
- **Drop Handler**: MIDI file drag-in and chord analysis
- **Player Thread**: `MidiPlayerThread` - Non-blocking audio playback
- **Chord Analyzer**: Pattern recognition for MIDI-to-chord conversion
- **No Audio Input**: pygame mixer only, no microphone access

### Chord Processing
1. Parse progression with timing
2. Convert flats to sharps
3. Normalize to C for lookup
4. Transpose to target key
5. Handle bass notes separately
6. Generate MIDI with BPM

### MIDI Analysis
1. Parse MIDI file structure
2. Extract note events and timing
3. Group simultaneous notes into chords
4. Match patterns against chord database
5. Detect slash chords and inversions
6. Calculate BPM from tempo events
7. Generate chord progression notation

## 🐛 Troubleshooting

### Common Issues

**"No audio during preview"**
- Install pygame: `pip install pygame`
- Check system volume
- Verify audio output device

**"Drag-and-drop not saving"**
- Ensure target folder has write permissions
- On Windows: Try running as administrator
- On macOS: Check Security & Privacy settings

**"Wrong bass notes"**
- Update to this version (v1.2)
- Bass notes now correctly placed at octave-1

**"Microphone permission requested"**
- This version doesn't need microphone
- If still prompted, check other running apps

**"MIDI file not recognized when dragged"**
- Ensure file extension is .mid or .midi
- Check file is valid MIDI format
- Try with a simple MIDI file first

**"Chord detection inaccurate"**
- Complex polyphonic MIDI may not convert perfectly
- Works best with clear chord-based arrangements
- Manual editing may be needed for complex files

## 🎵 Examples

### Pop Progression
```
C - G - Am - F
BPM: 120, Octave: 4
```

### Jazz Changes
```
Dm7 - G7 - CM7 - A7
BPM: 140, Octave: 4
```

### Complex with Bass
```
Am7/E - E/G# - [Am - Fmaj7] - F/C
BPM: 90, Octave: 4
```

### Workflow Example
```
1. Drag in: song.mid
2. Extracted: Dm7 - G7 - CM7 - A7
3. Modify: Dm7 - G7 - CM7 - Am7
4. Export: Modified version with new BPM
```

## 📄 Files

- `chord_to_midi_converter_qt_v1.py` - Main application
- `requirements_v1.txt` - Dependencies
- `README_v1.md` - This documentation

## 📧 Support

For issues or questions:
1. Check the troubleshooting section
2. Verify Python version (3.8+)
3. Ensure dependencies are installed
4. Test with simple progressions first
5. For MIDI analysis issues, try simpler MIDI files

---

**Version**: 1.2  
**License**: For educational and personal use  
**Dependencies**: PyQt6 (GPL/Commercial), pygame (LGPL), midiutil (MIT)