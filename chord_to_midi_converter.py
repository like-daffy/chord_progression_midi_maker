#!/usr/bin/env python3
"""
Chord Progression to MIDI Converter (PyQt6 Version 1.0)

Features:
- BPM control with slider and manual input
- MIDI preview playback
- Drag-and-drop for both export and import
- MIDI-to-chord conversion
- No microphone/record permissions required (playback only)
"""

import sys
import os
import re
import csv
import tempfile
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTextEdit, QGroupBox,
    QFileDialog, QMessageBox, QGridLayout, QSlider, QFrame, QRadioButton,
    QButtonGroup
)
from PyQt6.QtCore import Qt, QMimeData, QUrl, pyqtSignal, QThread, pyqtSlot, QTimer
from PyQt6.QtGui import QDrag, QDragEnterEvent, QDropEvent, QMouseEvent, QIntValidator

from midiutil import MIDIFile


# =============================================================================
# CONSTANTS
# =============================================================================

# BPM Settings
BPM_MIN = 1
BPM_MAX = 300
BPM_DEFAULT = 120
BPM_SLIDER_TICK_INTERVAL = 50

# MIDI Settings
DEFAULT_OCTAVE = 4
DEFAULT_VELOCITY = 100
DEFAULT_CHANNEL = 0
MIDI_EXTENSIONS = ('.mid', '.midi')

# Timing Settings
CHORD_TIME_THRESHOLD = 0.12  # ~60ms at 120bpm for grouping simultaneous notes
DURATION_ROUND_TOLERANCE = 0.1  # Tolerance for rounding durations
MAX_CHORDS_FROM_MIDI = 32

# UI Settings
STATUS_MESSAGE_DURATION_MS = 3000
WINDOW_DEFAULT_SIZE = (900, 750)

# Unit Settings (beats per unit)
BEATS_PER_BAR = 4.0
BEATS_PER_BEAT = 1.0


# =============================================================================
# AUDIO LIBRARY INITIALIZATION
# =============================================================================

def init_pygame_mixer() -> bool:
    """Initialize pygame mixer for MIDI playback. Returns True if successful."""
    try:
        os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
        import pygame.mixer as mixer
        mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
        return True
    except ImportError:
        print("Warning: pygame not installed. MIDI preview will not be available.")
        print("Install with: pip install pygame")
        return False


def init_mido() -> bool:
    """Check if mido is available for MIDI parsing. Returns True if available."""
    try:
        import mido
        return True
    except ImportError:
        print("Warning: mido not installed. MIDI import will be limited.")
        print("Install with: pip install mido")
        return False


PYGAME_AVAILABLE = init_pygame_mixer()
MIDO_AVAILABLE = init_mido()

# Import mixer reference if available
if PYGAME_AVAILABLE:
    import pygame.mixer as mixer


# =============================================================================
# CHORD DATA
# =============================================================================

CHORD_CSV_DATA = """Chord,Code,BassNote
C,047,
Cm,037,
C7,047a,
C7(13),0479a,
CM7,047b,
Cmaj7,04bj,
Cmaj9,047be,
Cmaj11,047bde,
Cm7,037a,
Cm7(b5),036a,
Cm(b5),036,
Cm7/F,037a,5
Cm7/A#,037a,a
Cm/D#,037,3
Cm/G,037,7
Cblk,06ae,
Cdim7,0369,
Caug,048,
Csus2,027,
Csus4,057,
C7sus2,027m,
C7sus4,057a,
C/D,047,2
C/E,047,4
C/F,047,5
C/G,047,7
C/A#,047,a
C6,0479,
Cm6,0379,
CmM7,037b,
Cm9,037ae,
CM9,047be,
C(add9),047e,
"C(add9,add11)",02457,
C69,0479e,
Cm69,0379e,
C(b5),046,
C7(b5),046a,
C7(b9),047ad,
C7(#5),048a,
CM7(b5),046b,
Cm7(#5),038a,
C11,047ah,
C13,0259a,
C4.4,05af,
C7(b13),0478a,
C7(add9),0247a,
C7sus(b5),046a,
Cm7(b5),036a,
Cm7(b9),0137a,
Cm7(11),0357a,
Cm7(add9),0237a,
Cm7(add11),0357a,
Cdim,036,
C9,047ae,
C9sus4,057ae,
C9(#11),047aei,
Cm11,02357a,
Cm11(b13),023578a,
Cm11(b9),01357a,
"Cm11(b9,b13)",013578a,
Cm13,023579a,"""


# =============================================================================
# NOTE MAPPINGS
# =============================================================================

# Note name to single-character code (base octave)
NOTE_TO_CODE: Dict[str, str] = {
    'C': '0', 'C#': '1', 'D': '2', 'D#': '3',
    'E': '4', 'F': '5', 'F#': '6', 'G': '7',
    'G#': '8', 'A': '9', 'A#': 'a', 'B': 'b'
}

# Code to (note_name, octave_offset) - includes higher octave notes
CODE_TO_NOTE: Dict[str, Tuple[str, int]] = {
    '0': ('C', 0), '1': ('C#', 0), '2': ('D', 0), '3': ('D#', 0),
    '4': ('E', 0), '5': ('F', 0), '6': ('F#', 0), '7': ('G', 0),
    '8': ('G#', 0), '9': ('A', 0), 'a': ('A#', 0), 'b': ('B', 0),
    'c': ('C', 1), 'd': ('C#', 1), 'e': ('D', 1), 'f': ('D#', 1),
    'g': ('E', 1), 'h': ('F', 1), 'i': ('F#', 1), 'j': ('G', 1),
    'k': ('G#', 1), 'l': ('A', 1), 'm': ('A#', 1), 'n': ('B', 1),
    'o': ('C', 2)
}

# Note name to MIDI semitone offset (C = 0)
NOTE_TO_MIDI: Dict[str, int] = {
    'C': 0, 'C#': 1, 'D': 2, 'D#': 3,
    'E': 4, 'F': 5, 'F#': 6, 'G': 7,
    'G#': 8, 'A': 9, 'A#': 10, 'B': 11
}

# Flat to sharp conversions
FLAT_TO_SHARP: Dict[str, str] = {
    'Db': 'C#', 'Eb': 'D#', 'Gb': 'F#',
    'Ab': 'G#', 'Bb': 'A#', 'Cb': 'B'
}

# Enharmonic equivalents for uncommon notations
ENHARMONIC_EQUIVALENTS: Dict[str, str] = {
    'E#': 'F', 'Fb': 'E', 'B#': 'C', 'Cb': 'B'
}


# =============================================================================
# MIDI PLAYER THREAD
# =============================================================================

class MidiPlayerThread(QThread):
    """Background thread for MIDI playback without blocking the UI."""
    
    finished = pyqtSignal()
    error = pyqtSignal(str)
    
    def __init__(self, midi_file: str):
        super().__init__()
        self.midi_file = midi_file
        self.is_playing = False
    
    def run(self):
        """Play the MIDI file in a background thread."""
        if not PYGAME_AVAILABLE:
            self.error.emit("pygame is not installed. Cannot play MIDI.")
            return
        
        try:
            mixer.music.load(self.midi_file)
            mixer.music.play()
            self.is_playing = True
            
            # Poll until playback completes or is stopped
            while mixer.music.get_busy():
                if not self.is_playing:
                    mixer.music.stop()
                    break
                time.sleep(0.1)
            
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))
    
    def stop(self):
        """Signal the thread to stop playback."""
        self.is_playing = False
        if PYGAME_AVAILABLE:
            mixer.music.stop()


# =============================================================================
# DRAGGABLE MIDI DISPLAY WIDGET
# =============================================================================

class DraggableMidiDisplay(QTextEdit):
    """
    Custom QTextEdit with bidirectional drag-and-drop:
    - Drag OUT to save MIDI file to filesystem
    - Drag IN to import MIDI file for chord recognition
    """
    
    midi_file_dropped = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_midi_file: Optional[str] = None
        self.midi_filename = "chord_progression.mid"
        self.drag_start_position = None
        
        self.setReadOnly(True)
        self.setAcceptDrops(True)
        self._apply_styles()
    
    def _apply_styles(self):
        """Apply visual styles to the widget."""
        self.setStyleSheet("""
            QTextEdit {
                background-color: #e8f4f8;
                border: 2px dashed #4a90e2;
                border-radius: 8px;
                padding: 20px;
                font-family: 'Segoe UI', 'Arial', sans-serif;
                font-size: 13px;
            }
            QTextEdit:hover {
                border-color: #2c5aa0;
                background-color: #d9edf7;
            }
        """)
    
    def set_midi_file(self, file_path: Optional[str], filename: str = "chord_progression.mid"):
        """Set the current MIDI file for drag-out operations."""
        self.current_midi_file = file_path
        self.midi_filename = filename
    
    # -------------------------------------------------------------------------
    # Drag-In (Import) Handling
    # -------------------------------------------------------------------------
    
    def _is_valid_midi_url(self, urls: List[QUrl]) -> bool:
        """Check if the dragged URLs contain a valid MIDI file."""
        if not urls:
            return False
        return urls[0].toLocalFile().lower().endswith(MIDI_EXTENSIONS)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Accept drag if it contains a MIDI file."""
        if event.mimeData().hasUrls() and self._is_valid_midi_url(event.mimeData().urls()):
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dragMoveEvent(self, event: QDragEnterEvent):
        """Continue accepting drag over the widget."""
        if event.mimeData().hasUrls() and self._is_valid_midi_url(event.mimeData().urls()):
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dropEvent(self, event: QDropEvent):
        """Handle dropped MIDI file for import."""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path.lower().endswith(MIDI_EXTENSIONS):
                    self.midi_file_dropped.emit(file_path)
                    event.acceptProposedAction()
                    return
        event.ignore()
    
    # -------------------------------------------------------------------------
    # Drag-Out (Export) Handling
    # -------------------------------------------------------------------------
    
    def mousePressEvent(self, event: QMouseEvent):
        """Record drag start position for potential drag-out."""
        if event.button() == Qt.MouseButton.LeftButton and self.current_midi_file:
            self.drag_start_position = event.pos()
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """Initiate drag-out operation if mouse moved beyond threshold."""
        if not self.current_midi_file or not self.drag_start_position:
            super().mouseMoveEvent(event)
            return
        
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            super().mouseMoveEvent(event)
            return
        
        # Check if drag distance threshold met
        if (event.pos() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return
        
        self._start_drag_operation()
        super().mouseMoveEvent(event)
    
    def _start_drag_operation(self):
        """Create and execute a drag operation for the MIDI file."""
        drag = QDrag(self)
        mime_data = QMimeData()
        
        # Set file URL for cross-platform drag
        file_url = QUrl.fromLocalFile(self.current_midi_file)
        mime_data.setUrls([file_url])
        
        # Windows-specific filename data
        mime_data.setData(
            "application/x-qt-windows-mime;value=\"FileName\"",
            self.midi_filename.encode()
        )
        mime_data.setData(
            "application/x-qt-windows-mime;value=\"FileNameW\"",
            self.midi_filename.encode('utf-16le')
        )
        
        drag.setMimeData(mime_data)
        drop_action = drag.exec(Qt.DropAction.CopyAction)
        
        if drop_action == Qt.DropAction.CopyAction:
            self._notify_parent_of_save()
    
    def _notify_parent_of_save(self):
        """Notify parent window that file was saved via drag."""
        # Navigate up widget hierarchy to find main window
        parent = self.parent()
        while parent:
            if hasattr(parent, 'show_status_message'):
                parent.show_status_message("MIDI file saved to destination")
                break
            parent = parent.parent()


# =============================================================================
# CHORD PARSING AND RECOGNITION UTILITIES
# =============================================================================

class ChordParser:
    """Utility class for parsing and recognizing chords."""
    
    def __init__(self):
        self.chord_data: Dict[str, Dict] = {}
        self.bass_chord_data: Dict[str, Dict] = {}
        self.code_to_chord_map: Dict[str, str] = {}
        self._load_chord_data()
    
    def _load_chord_data(self):
        """Parse and load chord definitions from CSV data."""
        lines = CHORD_CSV_DATA.strip().split('\n')
        reader = csv.DictReader(lines)
        
        for row in reader:
            chord_name = row['Chord']
            chord_code = row['Code']
            bass_note = row['BassNote']
            
            chord_info = {'code': chord_code, 'bass': bass_note}
            
            # Store in appropriate dictionaries
            self.chord_data[chord_name] = chord_info
            if bass_note:
                self.bass_chord_data[chord_name] = chord_info
            
            # Create alias without parentheses/commas (e.g., Cm11(b9,b13) -> Cm11b9b13)
            clean_name = chord_name.replace('(', '').replace(')', '').replace(',', '')
            if clean_name != chord_name:
                self.chord_data[clean_name] = chord_info
                if bass_note:
                    self.bass_chord_data[clean_name] = chord_info
            
            # Build reverse lookup (code -> chord name)
            # Prefer non-slash chords for cleaner recognition
            normalized_code = self._normalize_chord_code(chord_code)
            if '/' not in chord_name:
                self.code_to_chord_map[normalized_code] = chord_name
            elif normalized_code not in self.code_to_chord_map:
                self.code_to_chord_map[normalized_code] = chord_name
    
    def _normalize_chord_code(self, code: str) -> str:
        """
        Normalize chord code by converting octave-shifted notes to base octave and sorting.
        This enables matching regardless of voicing.
        """
        normalized = []
        
        for char in code:
            if char in CODE_TO_NOTE:
                note_name, octave = CODE_TO_NOTE[char]
                if octave == 0:
                    normalized.append(char)
                else:
                    # Find equivalent note at octave 0
                    for base_char, (base_note, base_octave) in CODE_TO_NOTE.items():
                        if base_note == note_name and base_octave == 0:
                            normalized.append(base_char)
                            break
        
        # Sort: numbers first, then letters (alphabetically)
        numbers = sorted(c for c in normalized if c.isdigit())
        letters = sorted(c for c in normalized if c.isalpha())
        
        return ''.join(numbers + letters)
    
    @staticmethod
    def code_char_to_semitone(char: str) -> int:
        """Convert a single code character to semitone value (0-23)."""
        if char.isdigit():
            return int(char)
        elif char == 'a':
            return 10
        elif char == 'b':
            return 11
        else:
            # Handle higher octave notes
            if char in CODE_TO_NOTE:
                note_name, octave = CODE_TO_NOTE[char]
                return NOTE_TO_MIDI[note_name] + 12 * octave
        return -1
    
    @staticmethod
    def semitone_to_code_char(semitone: int) -> Optional[str]:
        """Convert a semitone value (0-11) to code character."""
        if 0 <= semitone <= 9:
            return str(semitone)
        elif semitone == 10:
            return 'a'
        elif semitone == 11:
            return 'b'
        return None
    
    @staticmethod
    def convert_flat_to_sharp(note: str) -> str:
        """Convert flat notation (e.g., Bb) to sharp notation (e.g., A#)."""
        if len(note) >= 2 and note[1] == 'b':
            flat_key = note[:2]
            suffix = note[2:] if len(note) > 2 else ''
            
            if flat_key in FLAT_TO_SHARP:
                return FLAT_TO_SHARP[flat_key] + suffix
        
        return note
    
    @staticmethod
    def convert_enharmonic(chord_str: str) -> str:
        """Convert uncommon enharmonic equivalents (E#, Fb, B#, Cb) to standard notation."""
        # Convert root note
        for enharmonic, standard in ENHARMONIC_EQUIVALENTS.items():
            if chord_str.startswith(enharmonic):
                chord_str = standard + chord_str[len(enharmonic):]
                break
        
        # Convert bass note in slash chords
        if '/' in chord_str:
            parts = chord_str.split('/')
            bass_note = parts[1]
            if bass_note in ENHARMONIC_EQUIVALENTS:
                chord_str = parts[0] + '/' + ENHARMONIC_EQUIVALENTS[bass_note]
        
        return chord_str
    
    @staticmethod
    def convert_min_to_m(chord_str: str) -> str:
        """Convert 'min' notation to 'm' notation (e.g., Amin -> Am)."""
        return re.sub(r'([A-G][#b]?)min', r'\1m', chord_str)
    
    def recognize_chord_from_notes(self, notes: List[str]) -> Optional[str]:
        """
        Recognize chord name from a list of note names.
        
        Args:
            notes: List of note names in order from lowest to highest pitch
            
        Returns:
            Recognized chord name or None if unrecognized
        """
        if len(notes) < 3:
            return None
        
        # Remove duplicates while preserving order
        unique_notes = list(dict.fromkeys(notes))
        if len(unique_notes) < 3:
            return None
        
        candidates = []
        
        # Try bass-specific recognition first
        bass_result = self._recognize_chord_with_bass(unique_notes)
        if bass_result:
            score = len(unique_notes) * 10 + (5 if '/' in bass_result else 0)
            candidates.append((score, bass_result))
        
        # Try standard recognition (testing each note as potential root)
        standard_results = self._recognize_chord_standard(unique_notes)
        candidates.extend(standard_results)
        
        if candidates:
            # Return highest-scoring match
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]
        
        return None
    
    def _recognize_chord_with_bass(self, notes: List[str]) -> Optional[str]:
        """Try to recognize chord with explicit bass note handling."""
        if len(notes) < 3:
            return None
        
        # Convert notes to numeric codes
        note_codes = [self.code_char_to_semitone(NOTE_TO_CODE.get(n, '')) 
                      for n in notes if n in NOTE_TO_CODE]
        
        if len(note_codes) < 3:
            return None
        
        bass_code = note_codes[0]  # Lowest note is bass
        chord_codes = note_codes[1:] if len(note_codes) > 3 else note_codes[1:] + [bass_code]
        
        # Try each note as reference for transposition
        for ref_idx, reference_note in enumerate(chord_codes):
            transposed = sorted((code - reference_note) % 12 for code in chord_codes)
            bass_diff = (bass_code - reference_note) % 12
            
            bass_str = self.semitone_to_code_char(bass_diff)
            if not bass_str:
                continue
            
            code_string = ''.join(self.semitone_to_code_char(n) or '' for n in transposed)
            
            # Check against bass chord database
            for chord_name, chord_info in self.bass_chord_data.items():
                if chord_info['bass'] != bass_str:
                    continue
                
                normalized = self._normalize_chord_code(chord_info['code'])
                if normalized != code_string:
                    continue
                
                # Found match - calculate actual chord name
                root_note = self._midi_num_to_note_name(reference_note % 12)
                actual_bass = self._midi_num_to_note_name(bass_code % 12)
                
                if root_note and chord_name.startswith('C'):
                    result = self._transpose_chord_name(chord_name, root_note)
                    if actual_bass:
                        result = self._add_bass_to_chord(result, actual_bass)
                    return self._clean_chord_name(result)
        
        return None
    
    def _recognize_chord_standard(self, notes: List[str]) -> List[Tuple[int, str]]:
        """Standard chord recognition by testing each note as root."""
        note_codes = [self.code_char_to_semitone(NOTE_TO_CODE.get(n, ''))
                      for n in notes if n in NOTE_TO_CODE]
        
        if len(note_codes) < 3:
            return []
        
        candidates = []
        tested_codes: Set[str] = set()
        
        for root_idx, root_code in enumerate(note_codes):
            # Transpose all notes relative to this root
            transposed = sorted((code - root_code) % 12 for code in note_codes)
            code_string = ''.join(self.semitone_to_code_char(n) or '' for n in transposed)
            
            if code_string in tested_codes:
                continue
            tested_codes.add(code_string)
            
            if code_string not in self.code_to_chord_map:
                continue
            
            base_chord = self.code_to_chord_map[code_string]
            root_note = notes[root_idx]
            
            if base_chord.startswith('C'):
                final_chord = self._transpose_chord_name(base_chord, root_note)
                final_chord = self._validate_bass_note(final_chord, notes)
                final_chord = self._clean_chord_name(final_chord)
                
                score = len(code_string) * 10 + (2 if root_idx == 0 else 0)
                candidates.append((score, final_chord))
        
        return candidates
    
    def _midi_num_to_note_name(self, midi_num: int) -> Optional[str]:
        """Convert MIDI note number (0-11) to note name."""
        for name, num in NOTE_TO_MIDI.items():
            if num == midi_num:
                return name
        return None
    
    def _transpose_chord_name(self, chord_name: str, new_root: str) -> str:
        """Transpose a C-based chord name to a new root."""
        if not chord_name.startswith('C'):
            return chord_name
        
        suffix = chord_name[1:]
        if suffix and suffix[0] not in ['/', '#', 'b', 'm']:
            return new_root + suffix
        elif suffix and suffix[0] == 'm':
            return new_root + suffix
        else:
            return new_root + suffix if suffix else new_root
    
    def _add_bass_to_chord(self, chord: str, bass_note: str) -> str:
        """Add or update bass note in chord name."""
        if '/' not in chord:
            return f"{chord}/{bass_note}"
        else:
            parts = chord.split('/')
            return f"{parts[0]}/{bass_note}"
    
    def _validate_bass_note(self, chord: str, available_notes: List[str]) -> str:
        """Remove bass note from chord if it doesn't exist in available notes."""
        if '/' not in chord:
            return chord
        
        parts = chord.split('/')
        if len(parts) != 2:
            return chord
        
        bass_note = parts[1]
        if bass_note not in available_notes:
            return parts[0]
        
        return chord
    
    def _clean_chord_name(self, chord: Optional[str]) -> Optional[str]:
        """Remove redundant slash notation when bass matches chord root."""
        if not chord or '/' not in chord:
            return chord
        
        parts = chord.split('/')
        if len(parts) != 2:
            return chord
        
        chord_part, bass_note = parts
        
        # Extract root note from chord
        if len(chord_part) > 1 and chord_part[1] in ['#', 'b']:
            root = chord_part[:2]
        else:
            root = chord_part[0]
        
        # Check if bass matches root (including enharmonic)
        root_num = NOTE_TO_MIDI.get(root)
        bass_num = NOTE_TO_MIDI.get(bass_note)
        
        if root_num is not None and bass_num is not None and root_num == bass_num:
            return chord_part
        
        return chord


# =============================================================================
# MIDI FILE PARSING
# =============================================================================

class MidiFileParser:
    """Utility class for parsing MIDI files into chord events."""
    
    def __init__(self, chord_parser: ChordParser):
        self.chord_parser = chord_parser
    
    def parse_file(self, filepath: str) -> List[Dict]:
        """
        Parse a MIDI file and extract chord events.
        
        Returns:
            List of dicts with 'notes', 'time', and 'duration' keys
        """
        if not MIDO_AVAILABLE:
            return []
        
        import mido
        
        try:
            mid = mido.MidiFile(filepath)
            note_events = self._extract_note_events(mid)
            chord_events = self._group_notes_into_chords(note_events)
            return chord_events[:MAX_CHORDS_FROM_MIDI]
        except Exception as e:
            raise RuntimeError(f"Failed to parse MIDI file: {e}")
    
    def _extract_note_events(self, mid) -> List[Dict]:
        """Extract all note-on events with timing from MIDI file."""
        note_events = []
        
        for track in mid.tracks:
            current_time = 0
            for msg in track:
                current_time += msg.time
                
                if msg.type == 'note_on' and msg.velocity > 0:
                    beat_time = current_time / mid.ticks_per_beat
                    note_events.append({
                        'time': beat_time,
                        'note': msg.note,
                        'velocity': msg.velocity
                    })
        
        note_events.sort(key=lambda x: x['time'])
        return note_events
    
    def _group_notes_into_chords(self, note_events: List[Dict]) -> List[Dict]:
        """Group simultaneous notes into chord events."""
        chord_events = []
        current_chord = []
        current_time = -1
        
        for event in note_events:
            if current_time < 0:
                current_time = event['time']
                current_chord.append(event)
            elif abs(event['time'] - current_time) < CHORD_TIME_THRESHOLD:
                current_chord.append(event)
            else:
                # Process completed chord group
                chord_event = self._process_chord_group(
                    current_chord, current_time, event['time'] - current_time
                )
                if chord_event:
                    chord_events.append(chord_event)
                
                # Start new chord
                current_chord = [event]
                current_time = event['time']
        
        # Process final chord
        if current_chord:
            chord_event = self._process_chord_group(current_chord, current_time, 1.0)
            if chord_event:
                chord_events.append(chord_event)
        
        # Recalculate durations based on next chord timing
        self._normalize_durations(chord_events)
        
        return chord_events
    
    def _process_chord_group(self, notes: List[Dict], timestamp: float, 
                             duration: float) -> Optional[Dict]:
        """
        Process a group of simultaneous notes into a chord event.
        Tries progressively smaller subsets to find a recognizable chord.
        """
        if len(notes) < 3:
            return None
        
        # Sort by pitch (lowest first for bass detection)
        notes.sort(key=lambda x: x['note'])
        
        # Try from largest subset down to 3 notes
        for n_notes in range(min(9, len(notes)), 2, -1):
            subset = notes[:n_notes]
            note_names = self._midi_notes_to_names(subset)
            
            if self.chord_parser.recognize_chord_from_notes(note_names):
                return {
                    'notes': note_names,
                    'time': timestamp,
                    'duration': duration
                }
        
        return None
    
    def _midi_notes_to_names(self, notes: List[Dict]) -> List[str]:
        """Convert MIDI note numbers to note names."""
        note_names = []
        for note_info in notes:
            midi_num = note_info['note'] % 12
            for name, num in NOTE_TO_MIDI.items():
                if num == midi_num:
                    note_names.append(name)
                    break
        return note_names
    
    def _normalize_durations(self, chord_events: List[Dict]):
        """Recalculate durations based on timing between chords."""
        for i in range(len(chord_events) - 1):
            chord_events[i]['duration'] = (
                chord_events[i + 1]['time'] - chord_events[i]['time']
            )
    
    @staticmethod
    def round_duration(duration: float, tolerance: float = DURATION_ROUND_TOLERANCE) -> float:
        """
        Round duration to nearest common musical subdivision.
        Handles timing drift (e.g., 0.49 beat -> 0.5 beat).
        """
        subdivisions = [1.0, 0.5, 0.25, 0.125]
        
        for subdiv in subdivisions:
            if abs(duration - subdiv) <= tolerance:
                return subdiv
            
            if subdiv < duration:
                multiple = round(duration / subdiv)
                if abs(duration - multiple * subdiv) <= tolerance:
                    return multiple * subdiv
        
        # Default: round to nearest 1/8 beat
        return round(duration * 8) / 8


# =============================================================================
# PROGRESSION PARSING
# =============================================================================

class ProgressionParser:
    """Utility class for parsing chord progression strings."""
    
    # Separator pattern: en-dash, em-dash, or hyphen with spaces
    SEPARATOR_PATTERN = r'[–—]+|\s+-\s+'
    
    @classmethod
    def parse(cls, progression_str: str) -> List[Dict]:
        """
        Parse a chord progression string into timing items.
        
        Supports:
        - Simple chords: Am - G - C
        - Brackets for subdivision: [Am - G] - C
        - Duration multipliers: Am(x2) - G
        
        Returns:
            List of dicts with 'chord' and 'duration' keys
        """
        items = []
        current_pos = 0
        bracket_pattern = r'\[([^\]]+)\]'
        
        for match in re.finditer(bracket_pattern, progression_str):
            # Process chords before this bracket
            before = progression_str[current_pos:match.start()].strip()
            items.extend(cls._parse_simple_chords(before))
            
            # Process bracketed chords (subdivided within one beat)
            bracket_content = match.group(1)
            items.extend(cls._parse_bracketed_chords(bracket_content))
            
            current_pos = match.end()
        
        # Process remaining chords after last bracket
        remaining = progression_str[current_pos:].strip()
        items.extend(cls._parse_simple_chords(remaining))
        
        return items
    
    @classmethod
    def _parse_simple_chords(cls, text: str) -> List[Dict]:
        """Parse simple (non-bracketed) chords."""
        items = []
        
        if not text:
            return items
        
        chords = re.split(cls.SEPARATOR_PATTERN, text)
        
        for token in chords:
            token = cls._clean_token(token)
            if not token:
                continue
            
            chord, multiplier = cls._extract_multiplier(token)
            items.append({'chord': chord, 'duration': 1.0 * multiplier})
        
        return items
    
    @classmethod
    def _parse_bracketed_chords(cls, content: str) -> List[Dict]:
        """Parse chords within brackets (share one beat proportionally)."""
        items = []
        tokens = re.split(cls.SEPARATOR_PATTERN, content)
        
        # First pass: calculate total weight
        parsed = []
        total_weight = 0
        
        for token in tokens:
            token = cls._clean_token(token)
            if not token:
                continue
            
            chord, weight = cls._extract_multiplier(token)
            parsed.append({'chord': chord, 'weight': weight})
            total_weight += weight
        
        # Second pass: assign proportional durations
        if parsed and total_weight > 0:
            for item in parsed:
                duration = item['weight'] / total_weight
                items.append({'chord': item['chord'], 'duration': duration})
        
        return items
    
    @staticmethod
    def _clean_token(token: str) -> str:
        """Remove leading/trailing separators from a token."""
        if not token:
            return ""
        
        cleaned = token.strip()
        
        # Remove leading separators
        while cleaned and cleaned[0] in ['-', '–', '—']:
            cleaned = cleaned[1:].lstrip()
        
        # Remove trailing separators
        while cleaned and cleaned[-1] in ['-', '–', '—']:
            cleaned = cleaned[:-1].rstrip()
        
        return cleaned
    
    @staticmethod
    def _extract_multiplier(token: str) -> Tuple[str, int]:
        """Extract duration multiplier suffix (e.g., 'Am(x2)' -> ('Am', 2))."""
        match = re.search(r'\(x(\d+)\)$', token, re.IGNORECASE)
        if match:
            return token[:match.start()].strip(), int(match.group(1))
        return token, 1
    
    @classmethod
    def validate_brackets(cls, progression_str: str) -> Tuple[bool, Optional[str]]:
        """
        Validate that square brackets are properly paired.
        
        Returns:
            (is_valid, error_message) tuple
        """
        bracket_count = 0
        last_chord = None
        current_segment = ""
        
        for char in progression_str:
            if char in ['–', '-', '—', '[', ']']:
                if current_segment.strip():
                    last_chord = current_segment.strip()
                
                if char == '[':
                    bracket_count += 1
                elif char == ']':
                    bracket_count -= 1
                    if bracket_count < 0:
                        error = "The opening square bracket '[' is missing."
                        if last_chord:
                            error += f"\nCheck the chord '{last_chord}' or the previous chord."
                        return False, error
                
                current_segment = ""
            else:
                current_segment += char
        
        if bracket_count > 0:
            error = "The closing square bracket ']' is missing."
            if last_chord:
                error += f"\nCheck the chord '{last_chord}' or the previous chord."
            return False, error
        
        return True, None


# =============================================================================
# MIDI GENERATION
# =============================================================================

class MidiGenerator:
    """Utility class for generating MIDI files from chord progressions."""
    
    def __init__(self, chord_parser: ChordParser):
        self.chord_parser = chord_parser
    
    def create_midi(self, progression_items: List[Dict], octave: int,
                    bpm: int = BPM_DEFAULT, unit_beats: float = BEATS_PER_BEAT) -> MIDIFile:
        """
        Create a MIDI file from progression items.
        
        Args:
            progression_items: List of dicts with 'chord' and 'duration'
            octave: Base octave for notes
            bpm: Beats per minute
            unit_beats: Time unit multiplier (1.0 for beat, 4.0 for bar)
            
        Returns:
            MIDIFile object
            
        Raises:
            ValueError: If a chord is not recognized
        """
        midi = MIDIFile(1)
        midi.addTempo(0, 0, bpm)
        
        current_time = 0
        
        for item in progression_items:
            chord_name = item['chord']
            duration = item['duration'] * unit_beats
            
            notes = self._get_chord_notes(chord_name, octave)
            if notes is None:
                raise ValueError(f"Chord '{chord_name}' is not recognized")
            
            for note in notes:
                midi.addNote(
                    track=0,
                    channel=DEFAULT_CHANNEL,
                    pitch=note,
                    time=current_time,
                    duration=duration,
                    volume=DEFAULT_VELOCITY
                )
            
            current_time += duration
        
        return midi
    
    def _get_chord_notes(self, chord_str: str, octave: int) -> Optional[List[int]]:
        """Get MIDI note numbers for a chord."""
        # Normalize chord notation
        chord_str = ChordParser.convert_enharmonic(chord_str)
        chord_str = ChordParser.convert_min_to_m(chord_str)
        
        # Parse main chord and bass note
        main_chord, bass_note_str = self._parse_slash_chord(chord_str)
        
        # Normalize and lookup
        chord_parts = self._normalize_chord_name(main_chord)
        if not chord_parts:
            return None
        
        root_note, normalized_chord, suffix = chord_parts
        
        # Find chord in database
        chord_info = self.chord_parser.chord_data.get(normalized_chord)
        if not chord_info:
            # Try basic chord as fallback
            chord_info = self.chord_parser.chord_data.get('C')
            if not chord_info:
                return None
        
        # Convert code to MIDI notes
        notes = self._code_to_midi_notes(chord_info['code'], octave)
        
        # Transpose from C to actual root
        if root_note != 'C':
            notes = self._transpose_notes(notes, 'C', root_note)
        
        # Add bass note
        bass_notes = self._get_bass_notes(chord_info, bass_note_str, root_note, octave)
        
        return bass_notes + notes
    
    def _parse_slash_chord(self, chord_str: str) -> Tuple[str, Optional[str]]:
        """Split chord into main chord and bass note."""
        parts = chord_str.split('/')
        main_chord = parts[0].strip()
        bass_note = ChordParser.convert_flat_to_sharp(parts[1].strip()) if len(parts) > 1 else None
        return main_chord, bass_note
    
    def _normalize_chord_name(self, chord: str) -> Optional[Tuple[str, str, str]]:
        """
        Normalize chord name for database lookup.
        
        Returns:
            (root_note, normalized_C_chord, suffix) tuple
        """
        if not chord:
            return None
        
        chord = ChordParser.convert_enharmonic(chord)
        chord = ChordParser.convert_flat_to_sharp(chord)
        
        # Extract root and suffix
        if len(chord) >= 2 and chord[1] == '#':
            root = chord[:2]
            suffix = chord[2:]
        else:
            root = chord[0]
            suffix = chord[1:] if len(chord) > 1 else ''
        
        normalized = 'C' + suffix
        return root, normalized, suffix
    
    def _code_to_midi_notes(self, code: str, octave: int) -> List[int]:
        """Convert chord code string to MIDI note numbers."""
        notes = []
        for char in code:
            if char in CODE_TO_NOTE:
                note_name, octave_offset = CODE_TO_NOTE[char]
                midi_num = NOTE_TO_MIDI[note_name] + (octave + octave_offset) * 12
                notes.append(midi_num)
        return notes
    
    def _transpose_notes(self, notes: List[int], from_note: str, to_note: str) -> List[int]:
        """Transpose notes from one key to another."""
        from_midi = NOTE_TO_MIDI.get(from_note, 0)
        to_midi = NOTE_TO_MIDI.get(to_note, 0)
        transpose = to_midi - from_midi
        return [note + transpose for note in notes]
    
    def _get_bass_notes(self, chord_info: Dict, bass_note_str: Optional[str],
                        root_note: str, octave: int) -> List[int]:
        """Get bass notes for a chord."""
        if chord_info.get('bass'):
            # Bass from chord definition
            bass_notes = self._code_to_midi_notes(chord_info['bass'], octave - 1)
            if root_note != 'C':
                bass_notes = self._transpose_notes(bass_notes, 'C', root_note)
            return bass_notes
        elif bass_note_str and bass_note_str in NOTE_TO_MIDI:
            # Explicit bass note
            return [NOTE_TO_MIDI[bass_note_str] + (octave - 1) * 12]
        
        return []


# =============================================================================
# MAIN APPLICATION WINDOW
# =============================================================================

class ChordToMIDIQt(QMainWindow):
    """Main application window for chord to MIDI conversion."""
    
    def __init__(self):
        super().__init__()
        
        # Initialize utility classes
        self.chord_parser = ChordParser()
        self.midi_parser = MidiFileParser(self.chord_parser)
        self.midi_generator = MidiGenerator(self.chord_parser)
        
        # State
        self.current_midi_file: Optional[str] = None
        self.bpm = BPM_DEFAULT
        self.player_thread: Optional[MidiPlayerThread] = None
        
        self._init_ui()
    
    # -------------------------------------------------------------------------
    # UI Initialization
    # -------------------------------------------------------------------------
    
    def _init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Chord Progression to MIDI Converter v1.5")
        self.setGeometry(100, 100, *WINDOW_DEFAULT_SIZE)
        self._apply_styles()
        
        # Central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Add sections
        main_layout.addWidget(self._create_input_section())
        main_layout.addWidget(self._create_preview_section())
        main_layout.addWidget(self._create_midi_section())
        main_layout.addLayout(self._create_footer())
        
        # Set default focus
        self.chord_input.setFocus()
    
    def _apply_styles(self):
        """Apply application-wide stylesheet."""
        self.setStyleSheet("""
            QMainWindow { background-color: #f5f5f5; }
            QLabel { font-size: 12px; font-weight: 500; }
            QPushButton {
                background-color: #0078d4; color: white; border: none;
                padding: 8px 16px; border-radius: 4px;
                font-size: 12px; font-weight: 500; min-width: 80px;
            }
            QPushButton:hover { background-color: #106ebe; }
            QPushButton:pressed { background-color: #005a9e; }
            QPushButton:disabled { background-color: #cccccc; color: #666666; }
            QPushButton#resetButton { background-color: #6c757d; }
            QPushButton#resetButton:hover { background-color: #5a6268; }
            QPushButton#previewButton { background-color: #28a745; }
            QPushButton#previewButton:hover { background-color: #218838; }
            QPushButton#stopButton { background-color: #dc3545; }
            QPushButton#stopButton:hover { background-color: #c82333; }
            QLineEdit {
                padding: 8px; border: 1px solid #ccc;
                border-radius: 4px; font-size: 12px;
            }
            QComboBox {
                padding: 6px; border: 1px solid #ccc;
                border-radius: 4px; font-size: 12px; min-width: 150px;
            }
            QSlider { min-height: 20px; }
            QSlider::groove:horizontal {
                border: 1px solid #bbb; background: white;
                height: 8px; border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #0078d4; border: 1px solid #5c7cbb;
                width: 18px; margin: -5px 0; border-radius: 9px;
            }
            QSlider::handle:horizontal:hover { background: #106ebe; }
            QGroupBox {
                font-size: 13px; font-weight: 600;
                border: 2px solid #ddd; border-radius: 5px;
                margin-top: 10px; padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 10px; padding: 0 5px;
            }
        """)
    
    def _create_input_section(self) -> QGroupBox:
        """Create the chord progression input section."""
        group = QGroupBox("Chord Progression Input")
        layout = QGridLayout()
        
        # Row 0: Octave and Unit selection
        layout.addLayout(self._create_octave_unit_row(), 0, 0, 1, 5)
        
        # Row 1: BPM control
        layout.addWidget(QLabel("BPM:"), 1, 0)
        layout.addLayout(self._create_bpm_controls(), 1, 1, 1, 4)
        
        # Row 2: Chord input
        layout.addWidget(QLabel("Chord Progression:"), 2, 0)
        self.chord_input = QLineEdit()
        self.chord_input.setPlaceholderText(
            "Enter chord progression (e.g., Am7/E – E/G# – [Am – Fmaj7] – [F/A – Dm/A – E])"
        )
        self.chord_input.returnPressed.connect(self.process_chords)
        layout.addWidget(self.chord_input, 2, 1, 1, 4)
        
        # Row 3: Buttons
        layout.addLayout(self._create_action_buttons(), 3, 1)
        layout.setColumnStretch(1, 1)
        
        group.setLayout(layout)
        return group
    
    def _create_octave_unit_row(self) -> QHBoxLayout:
        """Create octave and unit selection controls."""
        layout = QHBoxLayout()
        
        # Octave
        layout.addWidget(QLabel("Octave:"))
        self.octave_combo = QComboBox()
        self.octave_combo.addItems(["2", "3", "4", "5", "6", "7"])
        self.octave_combo.setCurrentText(str(DEFAULT_OCTAVE))
        self.octave_combo.setMaximumWidth(100)
        layout.addWidget(self.octave_combo)
        
        # Unit (Bar/Beat)
        unit_label = QLabel("  Unit:")
        unit_label.setStyleSheet("margin-left: 20px;")
        layout.addWidget(unit_label)
        
        self.bar_radio = QRadioButton("Bar")
        self.beat_radio = QRadioButton("Beat")
        self.bar_radio.setChecked(True)
        
        self.import_unit_group = QButtonGroup(self)
        self.import_unit_group.addButton(self.bar_radio, 0)
        self.import_unit_group.addButton(self.beat_radio, 1)
        
        layout.addWidget(self.bar_radio)
        layout.addWidget(self.beat_radio)
        layout.addStretch()
        
        return layout
    
    def _create_bpm_controls(self) -> QHBoxLayout:
        """Create BPM slider and input controls."""
        layout = QHBoxLayout()
        
        # Slider
        self.bpm_slider = QSlider(Qt.Orientation.Horizontal)
        self.bpm_slider.setMinimum(BPM_MIN)
        self.bpm_slider.setMaximum(BPM_MAX)
        self.bpm_slider.setValue(BPM_DEFAULT)
        self.bpm_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.bpm_slider.setTickInterval(BPM_SLIDER_TICK_INTERVAL)
        self.bpm_slider.valueChanged.connect(self._on_bpm_slider_changed)
        layout.addWidget(self.bpm_slider)
        
        # Manual input
        self.bpm_input = QLineEdit(str(BPM_DEFAULT))
        self.bpm_input.setMaximumWidth(60)
        self.bpm_input.setValidator(QIntValidator(BPM_MIN, 999))
        self.bpm_input.textChanged.connect(self._on_bpm_input_changed)
        layout.addWidget(self.bpm_input)
        
        # Display label
        self.bpm_display = QLabel(str(BPM_DEFAULT))
        self.bpm_display.setMinimumWidth(30)
        layout.addWidget(self.bpm_display)
        
        return layout
    
    def _create_action_buttons(self) -> QHBoxLayout:
        """Create Proceed and Reset buttons."""
        layout = QHBoxLayout()
        
        self.proceed_btn = QPushButton("Proceed")
        self.proceed_btn.clicked.connect(self.process_chords)
        layout.addWidget(self.proceed_btn)
        
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setObjectName("resetButton")
        self.reset_btn.clicked.connect(self.reset_fields)
        layout.addWidget(self.reset_btn)
        
        layout.addStretch()
        return layout
    
    def _create_preview_section(self) -> QGroupBox:
        """Create the preview playback section."""
        group = QGroupBox("Preview")
        layout = QHBoxLayout()
        
        layout.addWidget(QLabel("Sound Output: System Default"))
        
        self.preview_btn = QPushButton("▶ Preview")
        self.preview_btn.setObjectName("previewButton")
        self.preview_btn.clicked.connect(self.preview_midi)
        self.preview_btn.setEnabled(False)
        layout.addWidget(self.preview_btn)
        
        self.stop_btn = QPushButton("■ Stop")
        self.stop_btn.setObjectName("stopButton")
        self.stop_btn.clicked.connect(self.stop_preview)
        self.stop_btn.setEnabled(False)
        layout.addWidget(self.stop_btn)
        
        layout.addStretch()
        group.setLayout(layout)
        return group
    
    def _create_midi_section(self) -> QGroupBox:
        """Create the MIDI file display/drag section."""
        group = QGroupBox("MIDI File (Drag Section)")
        layout = QVBoxLayout()
        
        self.midi_display = DraggableMidiDisplay()
        self.midi_display.setMinimumHeight(150)
        self.midi_display.midi_file_dropped.connect(self.import_midi_to_progression)
        layout.addWidget(self.midi_display)
        
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #666; font-style: italic; font-size: 11px;")
        layout.addWidget(self.status_label)
        
        self._update_midi_display("")
        
        group.setLayout(layout)
        return group
    
    def _create_footer(self) -> QHBoxLayout:
        """Create the footer with copyright info."""
        layout = QHBoxLayout()
        layout.addStretch()
        
        copyright_label = QLabel(
            'Copyright © 2025 Sochan, X (Twitter): '
            '<a href="#" style="color: #1DA1F2; text-decoration: none;">@sochan_life</a> '
            'For personal use'
        )
        copyright_label.setStyleSheet("color: #666; font-size: 14px;")
        copyright_label.setOpenExternalLinks(False)
        copyright_label.linkActivated.connect(self._open_twitter)
        copyright_label.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(copyright_label)
        
        layout.addStretch()
        return layout
    
    # -------------------------------------------------------------------------
    # BPM Handling
    # -------------------------------------------------------------------------
    
    def _on_bpm_slider_changed(self, value: int):
        """Handle BPM slider value changes."""
        self.bpm = value
        self.bpm_display.setText(str(value))
        
        self.bpm_input.blockSignals(True)
        self.bpm_input.setText(str(value))
        self.bpm_input.blockSignals(False)
    
    def _on_bpm_input_changed(self, text: str):
        """Handle manual BPM input changes."""
        if not text or not text.isdigit():
            return
        
        value = int(text)
        
        if value > BPM_MAX:
            QMessageBox.warning(self, "BPM Warning",
                                f"BPM value cannot exceed {BPM_MAX}. Setting to {BPM_MAX}.")
            value = BPM_MAX
            self.bpm_input.setText(str(BPM_MAX))
        elif value < BPM_MIN:
            value = BPM_MIN
            self.bpm_input.setText(str(BPM_MIN))
        
        self.bpm = value
        self.bpm_display.setText(str(value))
        
        if BPM_MIN <= value <= BPM_MAX:
            self.bpm_slider.blockSignals(True)
            self.bpm_slider.setValue(value)
            self.bpm_slider.blockSignals(False)
    
    # -------------------------------------------------------------------------
    # Chord Processing
    # -------------------------------------------------------------------------
    
    def process_chords(self):
        """Process the input chord progression and create MIDI file."""
        progression_str = self.chord_input.text()
        
        if not progression_str:
            QMessageBox.warning(self, "Input Required", "Please enter a chord progression.")
            return
        
        # Validate brackets
        is_valid, error_msg = ProgressionParser.validate_brackets(progression_str)
        if not is_valid:
            QMessageBox.warning(self, "Bracket Error", error_msg)
            return
        
        try:
            octave = int(self.octave_combo.currentText())
            unit_beats = BEATS_PER_BAR if self.bar_radio.isChecked() else BEATS_PER_BEAT
            
            progression_items = ProgressionParser.parse(progression_str)
            
            if not progression_items:
                QMessageBox.warning(self, "No Chords", "No valid chords found in the progression.")
                return
            
            midi_file = self.midi_generator.create_midi(
                progression_items, octave, self.bpm, unit_beats
            )
            
            self._save_and_display_midi(midi_file, progression_str, octave, unit_beats,
                                        len(progression_items))
            
        except ValueError as e:
            QMessageBox.critical(self, "Error", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {e}")
    
    def _save_and_display_midi(self, midi_file: MIDIFile, progression_str: str,
                               octave: int, unit_beats: float, chord_count: int):
        """Save MIDI to temp file and update display."""
        # Generate filename
        safe_filename = re.sub(r'[^\w\s-]', '', progression_str[:30])
        safe_filename = re.sub(r'[-\s]+', '_', safe_filename)
        filename = f"{safe_filename}_BPM{self.bpm}.mid"
        
        # Save to temp file
        temp_file = tempfile.NamedTemporaryFile(mode='wb', suffix='.mid', delete=False)
        midi_file.writeFile(temp_file)
        temp_file.close()
        
        self.current_midi_file = temp_file.name
        self.midi_display.set_midi_file(temp_file.name, filename)
        
        # Update display
        unit_name = "Bar" if unit_beats == BEATS_PER_BAR else "Beat"
        info_text = (
            f"✓ MIDI File Created Successfully!\n\n"
            f"Chord Progression: {progression_str}\n"
            f"Octave: {octave} | BPM: {self.bpm} | Unit: {unit_name}\n"
            f"Number of chords: {chord_count}\n\n"
            f"🎵 Click 'Preview' to listen to the MIDI\n"
            f"📁 Drag this area to Desktop or any folder to save the MIDI file\n"
            f"📥 Or drag a MIDI file here to convert it to chord progression\n"
            f"   File will be saved as: {filename}"
        )
        
        self._update_midi_display(info_text)
        self.preview_btn.setEnabled(True)
        self.show_status_message("MIDI file created successfully")
    
    # -------------------------------------------------------------------------
    # MIDI Import
    # -------------------------------------------------------------------------
    
    def import_midi_to_progression(self, filepath: str):
        """Import MIDI file and convert to chord progression string."""
        if not MIDO_AVAILABLE:
            QMessageBox.warning(self, "MIDI Import",
                                "Advanced MIDI parsing requires 'mido' library.\n"
                                "Install with: pip install mido")
            return
        
        try:
            chord_events = self.midi_parser.parse_file(filepath)
        except RuntimeError as e:
            QMessageBox.critical(self, "MIDI Import Error", str(e))
            return
        
        if not chord_events:
            QMessageBox.warning(self, "MIDI Import",
                                "No valid chords found in MIDI file.\n"
                                "Make sure the MIDI file contains at least 3 simultaneous notes.")
            return
        
        progression_str, skipped = self._convert_events_to_progression(chord_events)
        
        if skipped:
            QMessageBox.information(self, "Import Notice",
                                    f"The following chord positions were skipped: {', '.join(map(str, skipped))}")
        
        if progression_str:
            self.chord_input.setText(progression_str)
            self.process_chords()
            self.show_status_message(f"Imported chords from MIDI and updated preview")
        else:
            QMessageBox.warning(self, "MIDI Import",
                                "Could not recognize any valid chords from the MIDI file.")
    
    def _convert_events_to_progression(self, chord_events: List[Dict]) -> Tuple[str, List[int]]:
        """
        Convert chord events to a progression string with bracket notation.
        
        Returns:
            (progression_string, list_of_skipped_positions)
        """
        recognized = []
        skipped = []
        
        for idx, event in enumerate(chord_events):
            chord_name = self.chord_parser.recognize_chord_from_notes(event['notes'])
            if not chord_name:
                skipped.append(idx + 1)
                continue
            
            duration = MidiFileParser.round_duration(event.get('duration', 1.0))
            recognized.append({'name': chord_name, 'duration': duration})
        
        if not recognized:
            return "", skipped
        
        # Group into progression string with brackets
        unit_beats = BEATS_PER_BAR if self.bar_radio.isChecked() else BEATS_PER_BEAT
        tolerance = 0.15 * unit_beats
        
        parts = []
        i = 0
        
        while i < len(recognized):
            current = recognized[i]
            
            # Full unit or longer -> standalone
            if current['duration'] >= unit_beats - tolerance:
                parts.append(current['name'])
                i += 1
                continue
            
            # Shorter duration -> group with following chords
            group = [current['name']]
            cumulative = current['duration']
            j = i + 1
            
            while j < len(recognized):
                next_event = recognized[j]
                
                if cumulative + next_event['duration'] > unit_beats + tolerance:
                    break
                if next_event['duration'] >= unit_beats - tolerance:
                    break
                
                group.append(next_event['name'])
                cumulative += next_event['duration']
                j += 1
                
                if cumulative >= unit_beats - tolerance:
                    break
            
            if len(group) == 1:
                parts.append(group[0])
            else:
                parts.append('[' + ' - '.join(group) + ']')
            
            i = j
        
        return ' - '.join(parts), skipped
    
    # -------------------------------------------------------------------------
    # Preview Playback
    # -------------------------------------------------------------------------
    
    def preview_midi(self):
        """Start MIDI preview playback."""
        if not self.current_midi_file:
            QMessageBox.warning(self, "No File", "Please create a MIDI file first.")
            return
        
        if not PYGAME_AVAILABLE:
            QMessageBox.warning(self, "Preview Unavailable",
                                "pygame is not installed. Install with: pip install pygame")
            return
        
        try:
            self.stop_preview()
            
            self.player_thread = MidiPlayerThread(self.current_midi_file)
            self.player_thread.finished.connect(self._on_preview_finished)
            self.player_thread.error.connect(self._on_preview_error)
            self.player_thread.start()
            
            self.preview_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.show_status_message("Playing MIDI...")
            
        except Exception as e:
            QMessageBox.critical(self, "Playback Error", f"Failed to play MIDI: {e}")
    
    def stop_preview(self):
        """Stop MIDI preview playback."""
        if self.player_thread and self.player_thread.isRunning():
            self.player_thread.stop()
            self.player_thread.wait()
        
        self.preview_btn.setEnabled(self.current_midi_file is not None)
        self.stop_btn.setEnabled(False)
        self.show_status_message("Playback stopped")
    
    @pyqtSlot()
    def _on_preview_finished(self):
        """Handle preview playback completion."""
        self.preview_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.show_status_message("Playback finished")
    
    @pyqtSlot(str)
    def _on_preview_error(self, error_msg: str):
        """Handle preview playback errors."""
        QMessageBox.critical(self, "Playback Error", error_msg)
        self.preview_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
    
    # -------------------------------------------------------------------------
    # UI Utilities
    # -------------------------------------------------------------------------
    
    def reset_fields(self):
        """Reset all input fields and MIDI display."""
        self.chord_input.clear()
        self.current_midi_file = None
        self.midi_display.set_midi_file(None)
        self._update_midi_display("")
        self.preview_btn.setEnabled(False)
        self.stop_preview()
        self.show_status_message("")
    
    def _update_midi_display(self, text: str):
        """Update the MIDI display area content."""
        self.midi_display.clear()
        
        if text:
            self.midi_display.setPlainText(text)
        else:
            self.midi_display.setPlainText(
                "No MIDI file created yet.\n\n"
                "1. Enter a chord progression\n"
                "2. Set your desired BPM (1-300)\n"
                "3. Click 'Proceed' to generate\n"
                "4. Preview the MIDI or drag to save\n\n"
                "📥 You can also drag a MIDI file here to convert it to chord progression"
            )
    
    def show_status_message(self, message: str):
        """Show a temporary status message."""
        self.status_label.setText(message)
        if message:
            QTimer.singleShot(STATUS_MESSAGE_DURATION_MS, lambda: self.status_label.setText(""))
    
    @staticmethod
    def _open_twitter():
        """Open Twitter profile in default browser."""
        import webbrowser
        webbrowser.open("https://x.com/sochan_life")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Main entry point for the application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Chord to MIDI Converter")
    app.setOrganizationName("ChordToMIDI")
    
    window = ChordToMIDIQt()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()