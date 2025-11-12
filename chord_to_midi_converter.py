#!/usr/bin/env python3
"""
Chord Progression to MIDI Converter (PyQt6 Version 1.0)
Enhanced with BPM control, MIDI preview, drag-and-drop, and MIDI-to-chord conversion
No microphone/record permissions required - playback only
"""

import sys
import os
import re
import csv
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set
import threading
import time
from collections import defaultdict

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTextEdit, QGroupBox,
    QFileDialog, QMessageBox, QGridLayout, QSlider, QFrame
)
from PyQt6.QtCore import Qt, QMimeData, QUrl, QPoint, pyqtSignal, QThread, pyqtSlot, QTimer
from PyQt6.QtGui import QDrag, QDragEnterEvent, QDropEvent, QMouseEvent, QFont, QIntValidator

import midiutil
from midiutil import MIDIFile

# Import audio libraries for preview functionality
try:
    # Avoid importing pygame.sndarray which pulls in numpy
    import os
    os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
    
    # Import only the mixer module to avoid numpy dependency
    import pygame.mixer as mixer
    
    # Initialize mixer without requesting microphone access
    mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
    PYGAME_AVAILABLE = True
    
    # Create a dummy pygame module reference for compatibility
    class PygameCompat:
        mixer = mixer
    pygame = PygameCompat()
    
except ImportError:
    PYGAME_AVAILABLE = False
    print("Warning: pygame not installed. MIDI preview will not be available.")
    print("Install with: pip install pygame")

# Try to import mido for MIDI parsing
try:
    import mido
    MIDO_AVAILABLE = True
except ImportError:
    MIDO_AVAILABLE = False
    print("Warning: mido not installed. MIDI import will be limited.")
    print("Install with: pip install mido")

# We'll skip sounddevice to avoid microphone permission issues
SOUNDDEVICE_AVAILABLE = False

# Maximum chords to extract from MIDI
MAX_CHORDS_FROM_MIDI = 32


class MidiPlayerThread(QThread):
    """Thread for playing MIDI files without blocking the UI."""
    
    finished = pyqtSignal()
    error = pyqtSignal(str)
    
    def __init__(self, midi_file):
        super().__init__()
        self.midi_file = midi_file
        self.is_playing = False
        
    def run(self):
        """Play the MIDI file."""
        if not PYGAME_AVAILABLE:
            self.error.emit("pygame is not installed. Cannot play MIDI.")
            return
            
        try:
            mixer.music.load(self.midi_file)
            mixer.music.play()
            self.is_playing = True
            
            # Wait while the music is playing
            while mixer.music.get_busy():
                if not self.is_playing:
                    mixer.music.stop()
                    break
                time.sleep(0.1)
            
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))
    
    def stop(self):
        """Stop playing."""
        self.is_playing = False
        if PYGAME_AVAILABLE:
            mixer.music.stop()


class DraggableMidiDisplay(QTextEdit):
    """Custom QTextEdit widget with drag-to-save and drag-to-import functionality."""
    
    midi_file_dropped = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_midi_file = None
        self.midi_filename = "chord_progression.mid"
        self.setReadOnly(True)
        self.setAcceptDrops(True)  # Now accepting drops for MIDI import
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
    
    def set_midi_file(self, file_path: str, filename: str = "chord_progression.mid"):
        """Set the current MIDI file path."""
        self.current_midi_file = file_path
        self.midi_filename = filename
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter event for MIDI import."""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].toLocalFile().lower().endswith(('.mid', '.midi')):
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()
    
    def dragMoveEvent(self, event: QDragEnterEvent):
        """Handle drag move event to maintain the drag operation."""
        if event.mimeData().hasUrls():  
            urls = event.mimeData().urls()
            if urls and urls[0].toLocalFile().lower().endswith(('.mid', '.midi')):
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        """Handle drop event for MIDI import."""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path.lower().endswith(('.mid', '.midi')):
                    self.midi_file_dropped.emit(file_path)
                    event.acceptProposedAction()
                    return
        event.ignore()
    
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press for drag initiation."""
        if event.button() == Qt.MouseButton.LeftButton and self.current_midi_file:
            self.drag_start_position = event.pos()
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move for drag operation."""
        if not self.current_midi_file:
            super().mouseMoveEvent(event)
            return
            
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            super().mouseMoveEvent(event)
            return
            
        if hasattr(self, 'drag_start_position'):
            if (event.pos() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
                super().mouseMoveEvent(event)
                return
            
            # Create drag operation
            drag = QDrag(self)
            mime_data = QMimeData()
            
            # Set the file URL for the drag operation
            file_url = QUrl.fromLocalFile(self.current_midi_file)
            mime_data.setUrls([file_url])
            
            # Set additional data for the drop operation
            mime_data.setData("application/x-qt-windows-mime;value=\"FileName\"", 
                            self.midi_filename.encode())
            mime_data.setData("application/x-qt-windows-mime;value=\"FileNameW\"", 
                            self.midi_filename.encode('utf-16le'))
            
            drag.setMimeData(mime_data)
            
            # Execute the drag - this will actually copy the file when dropped
            dropAction = drag.exec(Qt.DropAction.CopyAction)
            
            if dropAction == Qt.DropAction.CopyAction:
                # File was successfully dragged and dropped
                self.parent().parent().parent().show_status_message("MIDI file saved to destination")
        
        super().mouseMoveEvent(event)


class ChordToMIDIQt(QMainWindow):
    """Main application window for chord to MIDI conversion using PyQt6."""
    
    def __init__(self):
        """Initialize the application with chord data and GUI components."""
        super().__init__()
        
        # Handle PyInstaller bundled files
        if hasattr(sys, '_MEIPASS'):
            self.base_path = Path(sys._MEIPASS)
        else:
            self.base_path = Path(__file__).parent
        
        # Note mapping system
        self.note_to_code = {
            'C': '0', 'C#': '1', 'D': '2', 'D#': '3',
            'E': '4', 'F': '5', 'F#': '6', 'G': '7',
            'G#': '8', 'A': '9', 'A#': 'a', 'B': 'b'
        }
        
        # Code to note mapping (including octave up notes)
        self.code_to_note = {
            '0': ('C', 0), '1': ('C#', 0), '2': ('D', 0), '3': ('D#', 0),
            '4': ('E', 0), '5': ('F', 0), '6': ('F#', 0), '7': ('G', 0),
            '8': ('G#', 0), '9': ('A', 0), 'a': ('A#', 0), 'b': ('B', 0),
            'c': ('C', 1), 'd': ('C#', 1), 'e': ('D', 1), 'f': ('D#', 1),
            'g': ('E', 1), 'h': ('F', 1), 'i': ('F#', 1), 'j': ('G', 1),
            'k': ('G#', 1), 'l': ('A', 1), 'm': ('A#', 1), 'n': ('B', 1),
            'o': ('C', 2)
        }
        
        # Note to MIDI number mapping (C3 = 60)
        self.note_to_midi = {
            'C': 0, 'C#': 1, 'D': 2, 'D#': 3,
            'E': 4, 'F': 5, 'F#': 6, 'G': 7,
            'G#': 8, 'A': 9, 'A#': 10, 'B': 11
        }
        
        # Flat to sharp conversion
        self.flat_to_sharp = {
            'Db': 'C#', 'Eb': 'D#', 'Gb': 'F#', 
            'Ab': 'G#', 'Bb': 'A#', 'Cb': 'B'
        }

        # Enharmonic equivalents for uncommon notations
        self.enharmonic_equivalents = {
            'E#': 'F', 'Fb': 'E', 'B#': 'C', 'Cb': 'B'
        }
        
        # For chord recognition
        self.code_to_chord_map = {}  # Will be populated from CSV
        
        self.chord_data = {}
        self.current_midi_file = None
        self.bpm = 120  # Default BPM
        self.player_thread = None
        self.load_chord_data()
        self.init_ui()
    
    def load_chord_data(self):
        """Load chord data from CSV file."""
        csv_content = """Chord,Code,BassNote
C,047,
Cm,037,
C7,047a,
CM7,047b,
Cmaj7,04bj,
Cm7,037a,
Cm7-5,036a,
Cm-5,036,
Cm7/F,037a,5
Cm7/A#,037a,a
Cm/D#,037,3
Cm/G,037,7
Cblk,06ae,
Cdim7,0369,
Caug,048,
Csus2,027,
Csus4,057,
C7sus4,057a,
C/D,047,2
C/E,047,4
C/F,047,5
C/G,047,7
C/A#,047,a
C6,0479,
Cm6,0379,
CmM7,037b,
C9,047ae,
Cm9,037ae,
CM9,047be,
C9sus4,057ae,
Cadd9,047e,
C69,0479e,
Cm69,0379e,
C-5,046,
C7-5,046a,
C7+5,048a,
CM7-5,046b,
Cm7+5,038a,
C11,047ah,
C4.4,05af,
C7b13,0478a,
C7add9,0247a,
C7sus2,027a,
C7susb5,046a,
Cm7b5,036a,
Cm7b9,0137a,
Cm7-11,0357a,
Cm7add9,0237a,
Cm7add11,0357a,
Cdim,036,
Cm11,02357a,
Cm11b13,023578a,
Cm11b9,01357a,
Cm11b9b13,013578a,
Cm13,023579a,"""
        
        # Parse CSV data
        lines = csv_content.strip().split('\n')
        reader = csv.DictReader(lines)
        
        # Separate storage for chords with bass notes
        self.bass_chord_data = {}
        
        for row in reader:
            chord_name = row['Chord']
            chord_code = row['Code']
            bass_note = row['BassNote']
            
            if bass_note:  # Store chords with bass notes separately
                self.bass_chord_data[chord_name] = {
                    'code': chord_code,
                    'bass': bass_note
                }
            
            self.chord_data[chord_name] = {
                'code': chord_code,
                'bass': bass_note
            }
            
            # Create normalized code for chord recognition
            normalized_code = self.normalize_chord_code(chord_code)
            self.code_to_chord_map[normalized_code] = chord_name
    
    def normalize_chord_code(self, code: str) -> str:
        """Normalize chord code by converting octave-shifted notes to base octave and sorting."""
        normalized = []
        
        for char in code:
            if char in self.code_to_note:
                note_name, octave = self.code_to_note[char]
                if octave == 0:
                    normalized.append(char)
                else:
                    # Find equivalent note at octave 0
                    for base_char, (base_note, base_octave) in self.code_to_note.items():
                        if base_note == note_name and base_octave == 0:
                            normalized.append(base_char)
                            break
        
        # Sort: numbers first, then alphabets
        numbers = sorted([c for c in normalized if c.isdigit()])
        letters = sorted([c for c in normalized if c.isalpha()])
        
        return ''.join(numbers + letters)
    
    def alphabet_to_number(self, char: str) -> int:
        """Convert alphabet code to number for chord recognition."""
        if char.isdigit():
            return int(char)
        elif char == 'a':
            return 10
        elif char == 'b':
            return 11
        else:
            # Handle higher octave notes
            for code, (note, octave) in self.code_to_note.items():
                if code == char:
                    return self.note_to_midi[note] + 12 * octave
        return -1
    
    def parse_midi_file(self, filepath: str) -> List[Dict]:
        """Parse MIDI file and extract chord information."""
        if not MIDO_AVAILABLE:
            QMessageBox.warning(self, "MIDI Import", 
                            "Advanced MIDI parsing requires 'mido' library.\n"
                            "Install with: pip install mido")
            return []
        
        try:
            mid = mido.MidiFile(filepath)
            
            # Collect all note events with timing
            note_events = []
            current_time = 0
            
            for track in mid.tracks:
                current_time = 0
                for msg in track:
                    current_time += msg.time
                    
                    if msg.type == 'note_on' and msg.velocity > 0:
                        # Convert ticks to beats
                        beat_time = current_time / mid.ticks_per_beat
                        note_events.append({
                            'time': beat_time,
                            'note': msg.note,
                            'velocity': msg.velocity
                        })
            
            # Sort by time
            note_events.sort(key=lambda x: x['time'])
            
            # Group notes that start at similar times into chords
            chord_events = []
            current_chord = []
            current_time = -1
            time_threshold = 0.05  # Notes within this time are considered simultaneous
            
            for event in note_events:
                if current_time < 0 or abs(event['time'] - current_time) < time_threshold:
                    current_chord.append(event)
                    if current_time < 0:
                        current_time = event['time']
                else:
                    # Process current chord
                    if len(current_chord) >= 3:  # Need at least 3 notes
                        # Sort by pitch (LOWEST first for bass detection)
                        current_chord.sort(key=lambda x: x['note'])  # Removed reverse=True
                        
                        # Try progressively from 4 to 8 notes for efficiency
                        chord_found = False
                        for max_notes in range(4, min(9, len(current_chord) + 1)):
                            chord_notes = current_chord[:max_notes]
                            
                            # Extract note names (ignoring octave) 
                            # Keep the order: lowest to highest
                            note_names = []
                            for note_info in chord_notes:
                                midi_num = note_info['note']
                                note_num = midi_num % 12
                                
                                # Convert to note name
                                for name, num in self.note_to_midi.items():
                                    if num == note_num:
                                        note_names.append(name)
                                        break
                            
                            # Try to recognize chord with current number of notes
                            test_chord = self.recognize_chord_from_notes(note_names)
                            if test_chord:
                                chord_events.append({
                                    'notes': note_names,
                                    'time': current_time,
                                    'duration': event['time'] - current_time
                                })
                                chord_found = True
                                break
                        
                        # If no chord found with up to 8 notes, use first 4
                        if not chord_found:
                            chord_notes = current_chord[:4]
                            note_names = []
                            for note_info in chord_notes:
                                midi_num = note_info['note']
                                note_num = midi_num % 12
                                for name, num in self.note_to_midi.items():
                                    if num == note_num:
                                        note_names.append(name)
                                        break
                            
                            chord_events.append({
                                'notes': note_names,
                                'time': current_time,
                                'duration': event['time'] - current_time
                            })
                    
                    # Start new chord
                    current_chord = [event]
                    current_time = event['time']
            
            # Process last chord (similar logic with 4-8 note checking)
            if len(current_chord) >= 3:
                current_chord.sort(key=lambda x: x['note'])  # Removed reverse=True
                
                chord_found = False
                for max_notes in range(4, min(9, len(current_chord) + 1)):
                    chord_notes = current_chord[:max_notes]
                    note_names = []
                    for note_info in chord_notes:
                        midi_num = note_info['note']
                        note_num = midi_num % 12
                        for name, num in self.note_to_midi.items():
                            if num == note_num:
                                note_names.append(name)
                                break
                    
                    test_chord = self.recognize_chord_from_notes(note_names)
                    if test_chord:
                        chord_events.append({
                            'notes': note_names,
                            'time': current_time,
                            'duration': 1.0
                        })
                        chord_found = True
                        break
                
                if not chord_found:
                    chord_notes = current_chord[:4]
                    note_names = []
                    for note_info in chord_notes:
                        midi_num = note_info['note']
                        note_num = midi_num % 12
                        for name, num in self.note_to_midi.items():
                            if num == note_num:
                                note_names.append(name)
                                break
                    chord_events.append({
                        'notes': note_names,
                        'time': current_time,
                        'duration': 1.0
                    })
            
            # Normalize durations
            if len(chord_events) > 1:
                for i in range(len(chord_events) - 1):
                    if i + 1 < len(chord_events):
                        chord_events[i]['duration'] = chord_events[i+1]['time'] - chord_events[i]['time']
            
            # Limit to MAX_CHORDS_FROM_MIDI
            return chord_events[:MAX_CHORDS_FROM_MIDI]
            
        except Exception as e:
            QMessageBox.critical(self, "MIDI Import Error", 
                            f"Failed to parse MIDI file: {str(e)}")
            return []
    
    def recognize_chord_with_bass(self, notes: List[str]) -> Optional[str]:
        """Try to recognize chord with bass note first."""
        if len(notes) < 3:
            return None
        
        # Remove duplicates while preserving order
        unique_notes = []
        seen = set()
        for note in notes:
            if note not in seen:
                unique_notes.append(note)
                seen.add(note)
        
        if len(unique_notes) < 3:
            return None
        
        # Convert notes to numeric codes
        note_codes = []
        for note in unique_notes:
            if note in self.note_to_code:
                code = self.note_to_code[note]
                note_codes.append(self.alphabet_to_number(code))
        
        if len(note_codes) < 3:
            return None
        
        # The FIRST note in the list is the bass (lowest pitch)
        bass_code = note_codes[0]
        bass_note_name = unique_notes[0]
        
        # If we only have 3 notes total, duplicate the bass note for chord recognition
        if len(note_codes) == 3:
            # Add bass note to the chord notes (as if it appears in a higher octave)
            note_codes_for_chord = note_codes[1:] + [bass_code]
            unique_notes_for_chord = unique_notes[1:] + [bass_note_name]
        else:
            # Use all notes except bass for chord recognition
            note_codes_for_chord = note_codes[1:]
            unique_notes_for_chord = unique_notes[1:]
        
        # Try using different notes as reference for transposition
        for ref_idx in range(len(note_codes_for_chord)):
            reference_note = note_codes_for_chord[ref_idx]
            
            # Transpose all chord notes relative to reference note
            transposed = []
            for code in note_codes_for_chord:
                diff = code - reference_note
                if diff < 0:
                    diff += 12
                transposed.append(diff)
            
            # Also transpose the bass note relative to reference
            bass_diff = bass_code - reference_note
            if bass_diff < 0:
                bass_diff += 12
            
            # Convert bass to string code
            if bass_diff < 10:
                bass_str = str(bass_diff)
            elif bass_diff == 10:
                bass_str = 'a'
            elif bass_diff == 11:
                bass_str = 'b'
            else:
                continue
            
            # Sort the transposed chord notes
            transposed.sort()
            
            # Convert to code string
            code_string = ''
            for num in transposed:
                if num < 10:
                    code_string += str(num)
                elif num == 10:
                    code_string += 'a'
                elif num == 11:
                    code_string += 'b'
            
            # Check bass chord database
            for chord_name, chord_info in self.bass_chord_data.items():
                if chord_info['bass'] == bass_str:
                    # Check if chord notes match the chord code
                    normalized = self.normalize_chord_code(chord_info['code'])
                    if normalized == code_string:
                        # Found a match! Now transpose to actual key
                        root_note = None
                        for name, num in self.note_to_midi.items():
                            if num == reference_note % 12:
                                root_note = name
                                break
                        
                        if root_note and chord_name.startswith('C'):
                            # Calculate actual bass note
                            actual_bass = None
                            for name, num in self.note_to_midi.items():
                                if num == bass_code % 12:
                                    actual_bass = name
                                    break
                            
                            # Build chord name
                            result = root_note + chord_name[1:]
                            
                            # Replace bass note placeholder with actual bass
                            if '/' in result and actual_bass:
                                parts = result.split('/')
                                result = parts[0] + '/' + actual_bass
                            
                            # FIX 1: Check if bass note is same as root note
                            # If so, remove the redundant bass notation
                            if '/' in result:
                                parts = result.split('/')
                                chord_root = parts[0]
                                chord_bass = parts[1]
                                
                                # Extract just the root note from the chord name
                                if len(chord_root) > 1 and chord_root[1] == '#':
                                    root_only = chord_root[:2]
                                else:
                                    root_only = chord_root[0]
                                
                                # If bass equals root, return chord without bass
                                if chord_bass == root_only:
                                    return parts[0]  # Return just the chord without /bass
                            
                            return result
        
        return None

    def recognize_chord_from_notes(self, notes: List[str]) -> Optional[str]:
        """Recognize chord from list of note names."""
        if len(notes) < 3:
            return None
        
        # Try bass note recognition first ONLY if we have 4+ unique notes
        # or if the lowest note doesn't match typical chord roots
        unique_notes = []
        seen = set()
        for note in notes:
            if note not in seen:
                unique_notes.append(note)
                seen.add(note)
        
        if len(unique_notes) < 3:
            return None
        
        # Only try bass recognition if we have enough notes or unusual bass
        if len(unique_notes) >= 4:  # Changed: only try bass recognition with 4+ unique notes
            bass_chord = self.recognize_chord_with_bass(notes)
            if bass_chord:
                return bass_chord
        
        # Convert notes to codes
        note_codes = []
        for note in unique_notes:
            if note in self.note_to_code:
                code = self.note_to_code[note]
                note_codes.append(self.alphabet_to_number(code))
        
        # Try each note as potential root
        tested_codes = set()
        
        for root_idx, root_code in enumerate(note_codes):
            # Transpose all notes relative to this root
            transposed = []
            for code in note_codes:
                diff = code - root_code
                if diff < 0:
                    diff += 12
                transposed.append(diff)
            
            # Sort and convert back to code string
            transposed.sort()
            code_string = ''
            for num in transposed:
                if num < 10:
                    code_string += str(num)
                elif num == 10:
                    code_string += 'a'
                elif num == 11:
                    code_string += 'b'
            
            # Skip if we've already tested this code
            if code_string in tested_codes:
                continue
            tested_codes.add(code_string)
            
            # Check if this code matches any known chord
            if code_string in self.code_to_chord_map:
                # Get the chord name and transpose it
                base_chord = self.code_to_chord_map[code_string]
                root_note = unique_notes[root_idx]
                
                # Replace C with actual root
                if base_chord.startswith('C'):
                    if len(base_chord) > 1 and base_chord[1] not in ['/', '#', 'b', 'm']:
                        return root_note + base_chord[1:]
                    elif len(base_chord) > 1 and base_chord[1] == 'm':
                        return root_note + base_chord[1:]
                    else:
                        return root_note if len(base_chord) == 1 else root_note + base_chord[1:]
        
        return None
    
    def import_midi_to_progression(self, filepath: str):
        """Import MIDI file and convert to chord progression."""
        chord_events = self.parse_midi_file(filepath)
        
        if not chord_events:
            QMessageBox.warning(self, "MIDI Import", 
                            "No valid chords found in MIDI file.\n"
                            "Make sure the MIDI file contains at least 3 simultaneous notes to form chords.")
            return
        
        # Convert chord events to progression string with proper bracketing
        progression_parts = []
        skipped_chords = []
        
        i = 0
        while i < len(chord_events):
            event = chord_events[i]
            chord_name = self.recognize_chord_from_notes(event['notes'])
            
            if not chord_name:
                skipped_chords.append(i + 1)
                i += 1
                continue
            
            duration = event.get('duration', 1.0)
            
            # Check if this single chord is approximately one beat
            if abs(duration - 1.0) < 0.1:  # Tolerance for one beat
                progression_parts.append(chord_name)
                i += 1
            else:
                # Try to find combinations that sum to one beat
                found_group = False
                
                # Check up to 4 notes ahead for combinations
                for group_size in range(2, min(5, len(chord_events) - i + 1)):
                    total_duration = 0
                    group_chords = []
                    all_valid = True
                    
                    # Sum durations for this group
                    for j in range(group_size):
                        if i + j < len(chord_events):
                            evt = chord_events[i + j]
                            name = self.recognize_chord_from_notes(evt['notes'])
                            if name:
                                total_duration += evt.get('duration', 1.0)
                                group_chords.append(name)
                            else:
                                all_valid = False
                                break
                    
                    # Check if this group sums to approximately one beat
                    if all_valid and abs(total_duration - 1.0) < 0.1:
                        # Found a group that equals one beat
                        progression_parts.append('[' + ' - '.join(group_chords) + ']')
                        i += group_size
                        found_group = True
                        break
                
                # If no group found, treat as single chord (one beat)
                if not found_group:
                    progression_parts.append(chord_name)
                    i += 1
        
        if skipped_chords:
            skipped_str = ', '.join(map(str, skipped_chords))
            QMessageBox.information(self, "Import Notice", 
                                f"The following chord positions did not have enough notes and were skipped: {skipped_str}")
        
        if progression_parts:
            progression_str = ' - '.join(progression_parts)
            self.chord_input.setText(progression_str)
            self.show_status_message(f"Imported {len(progression_parts)} chords from MIDI")
        else:
            QMessageBox.warning(self, "MIDI Import", 
                            "Could not recognize any valid chords from the MIDI file.")

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Chord Progression to MIDI Converter v1.2")
        self.setGeometry(100, 100, 900, 750)
        
        # Set application style
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QLabel {
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 500;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            QPushButton#resetButton {
                background-color: #6c757d;
            }
            QPushButton#resetButton:hover {
                background-color: #5a6268;
            }
            QPushButton#previewButton {
                background-color: #28a745;
            }
            QPushButton#previewButton:hover {
                background-color: #218838;
            }
            QPushButton#stopButton {
                background-color: #dc3545;
            }
            QPushButton#stopButton:hover {
                background-color: #c82333;
            }
            QLineEdit {
                padding: 8px;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-size: 12px;
            }
            QComboBox {
                padding: 6px;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-size: 12px;
                min-width: 150px;
            }
            QSlider {
                min-height: 20px;
            }
            QSlider::groove:horizontal {
                border: 1px solid #bbb;
                background: white;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #0078d4;
                border: 1px solid #5c7cbb;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
            QSlider::handle:horizontal:hover {
                background: #106ebe;
            }
            QGroupBox {
                font-size: 13px;
                font-weight: 600;
                border: 2px solid #ddd;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Input section
        input_group = QGroupBox("Chord Progression Input")
        input_layout = QGridLayout()
        
        # Row 0: Octave selection (extended to include 6 and 7)
        octave_label = QLabel("Octave:")
        self.octave_combo = QComboBox()
        self.octave_combo.addItems(["2", "3", "4", "5", "6", "7"])
        self.octave_combo.setCurrentText("4")  # Default changed to 4
        self.octave_combo.setMaximumWidth(100)
        
        input_layout.addWidget(octave_label, 0, 0)
        input_layout.addWidget(self.octave_combo, 0, 1)
        
        # Row 1: BPM control
        bpm_label = QLabel("BPM:")
        
        # BPM Slider
        self.bpm_slider = QSlider(Qt.Orientation.Horizontal)
        self.bpm_slider.setMinimum(1)
        self.bpm_slider.setMaximum(300)
        self.bpm_slider.setValue(120)
        self.bpm_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.bpm_slider.setTickInterval(50)
        self.bpm_slider.valueChanged.connect(self.on_bpm_slider_changed)
        
        # BPM Manual Input
        self.bpm_input = QLineEdit("120")
        self.bpm_input.setMaximumWidth(60)
        self.bpm_input.setValidator(QIntValidator(1, 999))  # Allow up to 999 for input
        self.bpm_input.textChanged.connect(self.on_bpm_input_changed)
        
        # BPM display label
        self.bpm_display = QLabel("120")
        self.bpm_display.setMinimumWidth(30)
        
        input_layout.addWidget(bpm_label, 1, 0)
        input_layout.addWidget(self.bpm_slider, 1, 1, 1, 2)
        input_layout.addWidget(self.bpm_input, 1, 3)
        input_layout.addWidget(self.bpm_display, 1, 4)
        
        # Row 2: Chord progression input
        chord_label = QLabel("Chord Progression:")
        self.chord_input = QLineEdit()
        self.chord_input.setPlaceholderText("Enter chord progression (e.g., Am7/E – E/G# – [Am – Fmaj7] – [F/A – Dm/A – E])")
        
        input_layout.addWidget(chord_label, 2, 0)
        input_layout.addWidget(self.chord_input, 2, 1, 1, 4)
        
        # Row 3: Buttons
        button_layout = QHBoxLayout()
        
        self.proceed_btn = QPushButton("Proceed")
        self.proceed_btn.clicked.connect(self.process_chords)
        
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setObjectName("resetButton")
        self.reset_btn.clicked.connect(self.reset_fields)
        
        button_layout.addWidget(self.proceed_btn)
        button_layout.addWidget(self.reset_btn)
        button_layout.addStretch()
        
        input_layout.addLayout(button_layout, 3, 1)
        input_layout.setColumnStretch(1, 1)
        
        input_group.setLayout(input_layout)
        main_layout.addWidget(input_group)
        
        # Preview section
        preview_group = QGroupBox("Preview")
        preview_layout = QHBoxLayout()
        
        # Simple label for audio output
        output_label = QLabel("Sound Output: System Default")
        
        # Preview and Stop buttons
        self.preview_btn = QPushButton("▶ Preview")
        self.preview_btn.setObjectName("previewButton")
        self.preview_btn.clicked.connect(self.preview_midi)
        self.preview_btn.setEnabled(False)
        
        self.stop_btn = QPushButton("■ Stop")
        self.stop_btn.setObjectName("stopButton")
        self.stop_btn.clicked.connect(self.stop_preview)
        self.stop_btn.setEnabled(False)
        
        preview_layout.addWidget(output_label)
        preview_layout.addWidget(self.preview_btn)
        preview_layout.addWidget(self.stop_btn)
        preview_layout.addStretch()
        
        preview_group.setLayout(preview_layout)
        main_layout.addWidget(preview_group)
        
        # MIDI file section (drag section - bidirectional)
        midi_group = QGroupBox("MIDI File (Drag Section)")
        midi_layout = QVBoxLayout()
        
        # MIDI display area with drag-to-save and drag-to-import
        self.midi_display = DraggableMidiDisplay()
        self.midi_display.setMinimumHeight(150)
        self.midi_display.midi_file_dropped.connect(self.import_midi_to_progression)
        self.update_midi_display("")
        
        midi_layout.addWidget(self.midi_display)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #666; font-style: italic; font-size: 11px;")
        midi_layout.addWidget(self.status_label)
        
        midi_group.setLayout(midi_layout)
        main_layout.addWidget(midi_group)
        
        # Footer section
        footer_layout = QHBoxLayout()
        footer_layout.addStretch()
        
        copyright_label = QLabel('Copyright © 2025 Sochan, X (Twitter): <a href="#" style="color: #1DA1F2; text-decoration: none;">@sochan_life</a> For personal use')
        copyright_label.setStyleSheet("color: #666; font-size: 14px;")
        copyright_label.setOpenExternalLinks(False)
        copyright_label.linkActivated.connect(lambda: self.open_twitter())
        copyright_label.setCursor(Qt.CursorShape.PointingHandCursor)
        
        footer_layout.addWidget(copyright_label)
        footer_layout.addStretch()
        
        main_layout.addLayout(footer_layout)
        
        # Set up keyboard shortcuts
        self.chord_input.returnPressed.connect(self.process_chords)
    
    def on_bpm_slider_changed(self, value):
        """Handle BPM slider changes."""
        self.bpm = value
        self.bpm_display.setText(str(value))
        self.bpm_input.blockSignals(True)
        self.bpm_input.setText(str(value))
        self.bpm_input.blockSignals(False)
    
    def on_bpm_input_changed(self, text):
        """Handle manual BPM input changes."""
        if text and text.isdigit():
            value = int(text)
            if value > 300:
                QMessageBox.warning(self, "BPM Warning", 
                                   "BPM value cannot exceed 300. Setting to 300.")
                self.bpm_input.setText("300")
                value = 300
            elif value < 1:
                value = 1
                self.bpm_input.setText("1")
            
            self.bpm = value
            self.bpm_display.setText(str(value))
            
            # Update slider if within range
            if 1 <= value <= 300:
                self.bpm_slider.blockSignals(True)
                self.bpm_slider.setValue(value)
                self.bpm_slider.blockSignals(False)
    
    def convert_min_to_m(self, chord_str: str) -> str:
        """Convert 'min' notation to 'm' notation in chord names."""
        pattern = r'([A-G][#b]?)min'
        return re.sub(pattern, r'\1m', chord_str)
    
    def remove_parentheses(self, chord_str: str) -> str:
        """Remove parentheses from chord notation."""
        return chord_str.replace('(', '').replace(')', '')

    def convert_enharmonic(self, chord_str: str) -> str:
        """Convert uncommon enharmonic equivalents to standard notation."""
        for enharmonic, standard in self.enharmonic_equivalents.items():
            if chord_str.startswith(enharmonic):
                suffix = chord_str[len(enharmonic):]
                chord_str = standard + suffix
                break
        
        # Also handle in slash chords (bass note)
        if '/' in chord_str:
            parts = chord_str.split('/')
            main_chord = parts[0]
            bass_note = parts[1]
            
            # Convert bass note if it's an enharmonic equivalent
            if bass_note in self.enharmonic_equivalents:
                bass_note = self.enharmonic_equivalents[bass_note]
                chord_str = main_chord + '/' + bass_note
        
        return chord_str

    def convert_flat_to_sharp(self, note: str) -> str:
        """Convert flat notation to sharp notation."""
        if len(note) >= 2 and note[1] == 'b':
            root = note[0]
            suffix = note[2:] if len(note) > 2 else ''
            
            if root + 'b' in self.flat_to_sharp:
                return self.flat_to_sharp[root + 'b'] + suffix
            
            # Handle special case Cb
            if root == 'C':
                return 'B' + suffix
                
            # Calculate sharp equivalent
            root_num = self.note_to_midi.get(root, 0)
            sharp_num = (root_num - 1) % 12
            
            for note_name, midi_num in self.note_to_midi.items():
                if midi_num == sharp_num and '#' in note_name:
                    return note_name + suffix
        
        return note
    
    def normalize_chord_name(self, chord: str) -> Optional[Tuple[str, str, str]]:
        """Normalize chord name for flexible matching."""
        if not chord:
            return None
        
        # Convert enharmonic equivalents first
        chord = self.convert_enharmonic(chord)
        
        # Handle flat notation
        chord = self.convert_flat_to_sharp(chord)
        
        # Extract root note and suffix
        if len(chord) >= 2 and chord[1] == '#':
            root = chord[:2]
            suffix = chord[2:]
        else:
            root = chord[0]
            suffix = chord[1:] if len(chord) > 1 else ''
        
        # Normalize to C for lookup
        normalized = 'C' + suffix
        
        return root, normalized, suffix
    
    def code_to_notes(self, code: str, octave: int) -> List[int]:
        """Convert code string to MIDI note numbers."""
        notes = []
        for char in code:
            if char in self.code_to_note:
                note_name, octave_offset = self.code_to_note[char]
                midi_num = self.note_to_midi[note_name] + (octave + octave_offset) * 12
                notes.append(midi_num)
        return notes
    
    def transpose_notes(self, notes: List[int], from_note: str, to_note: str, octave: int) -> List[int]:
        """Transpose notes from one key to another."""
        from_midi = self.note_to_midi.get(from_note, 0)
        to_midi = self.note_to_midi.get(to_note, 0)
        transpose_amount = to_midi - from_midi
        
        transposed = []
        for note in notes:
            new_note = note + transpose_amount
            transposed.append(new_note)
        
        return transposed
    
    def parse_chord_with_bass(self, chord_str: str) -> Tuple[str, Optional[str]]:
        """Parse chord string and extract main chord and bass note."""
        parts = chord_str.split('/')
        main_chord = parts[0].strip()
        bass_note = parts[1].strip() if len(parts) > 1 else None
        
        if bass_note:
            bass_note = self.convert_flat_to_sharp(bass_note)
        
        return main_chord, bass_note
    
    def get_chord_notes(self, chord_str: str, octave: int) -> Optional[List[int]]:
        """Get MIDI notes for a chord string."""
        # Convert enharmonic equivalents
        chord_str = self.convert_enharmonic(chord_str)
        
        # Convert 'min' notation to 'm' notation
        chord_str = self.convert_min_to_m(chord_str)
        
        # Parse chord and bass note
        main_chord, bass_note_str = self.parse_chord_with_bass(chord_str)
        
        # Normalize chord name
        chord_parts = self.normalize_chord_name(main_chord)
        if not chord_parts:
            return None
        
        root_note, normalized_chord, suffix = chord_parts
        
        # Look up chord in database
        chord_info = None
        bass_code = None
        
        # Try exact match with bass note
        if bass_note_str and normalized_chord + '/' + bass_note_str in self.chord_data:
            chord_info = self.chord_data[normalized_chord + '/' + bass_note_str]
        # Try chord without bass note
        elif normalized_chord in self.chord_data:
            chord_info = self.chord_data[normalized_chord]
            if bass_note_str:
                # Convert bass note to code
                if bass_note_str in self.note_to_code:
                    bass_code = self.note_to_code[bass_note_str]
        else:
            # Try to find base chord (without suffix) if complex chord not found
            base_chord = 'C'
            if base_chord in self.chord_data:
                QMessageBox.warning(self, "Chord Not Found", 
                                f"Chord '{main_chord}' not found. Using basic chord instead.")
                chord_info = self.chord_data[base_chord]
            else:
                return None
        
        if not chord_info:
            return None
        
        # Get notes from chord code
        notes = self.code_to_notes(chord_info['code'], octave)
        
        # Transpose from C to actual root
        if root_note != 'C':
            notes = self.transpose_notes(notes, 'C', root_note, octave)
        
        # Add bass note - FIXED LOGIC
        bass_notes = []
        if chord_info.get('bass'):
            # Bass note from chord definition (already in C)
            bass_note_code = chord_info['bass']
            bass_notes = self.code_to_notes(bass_note_code, octave - 1)
            if root_note != 'C':
                bass_notes = self.transpose_notes(bass_notes, 'C', root_note, octave - 1)
        elif bass_note_str:
            # Bass note explicitly specified (e.g., A/E means E bass)
            # Convert bass note string directly to MIDI without transposition
            if bass_note_str in self.note_to_midi:
                bass_midi = self.note_to_midi[bass_note_str] + (octave - 1) * 12
                bass_notes = [bass_midi]
        
        return bass_notes + notes
    
    def parse_progression(self, progression_str: str) -> List[Dict[str, any]]:
        """Parse chord progression string with timing information."""
        # Regular expression to find brackets
        bracket_pattern = r'\[([^\]]+)\]'
        
        progression_items = []
        current_pos = 0
        
        for match in re.finditer(bracket_pattern, progression_str):
            # Add any chords before this bracket
            before_bracket = progression_str[current_pos:match.start()].strip()
            if before_bracket:
                # Split by separators: en/em dashes, or hyphen with spaces on both sides
                # This preserves chord names like "Cm7-11" while splitting "Cm7 - Am"
                chords = re.split(r'[–—]+|\s+-\s+', before_bracket)
                for chord in chords:
                    chord = chord.strip()
                    if chord:
                        progression_items.append({'chord': chord, 'duration': 1.0})
            
            # Process chords in bracket
            bracket_content = match.group(1)
            chords_in_bracket = re.split(r'[–—]+|\s+-\s+', bracket_content)
            chords_in_bracket = [c.strip() for c in chords_in_bracket if c.strip()]
            
            if chords_in_bracket:
                duration = 1.0 / len(chords_in_bracket)
                for chord in chords_in_bracket:
                    progression_items.append({'chord': chord, 'duration': duration})
            
            current_pos = match.end()
        
        # Add any remaining chords after last bracket
        remaining = progression_str[current_pos:].strip()
        if remaining:
            chords = re.split(r'[–—]+|\s+-\s+', remaining)
            for chord in chords:
                chord = chord.strip()
                if chord:
                    progression_items.append({'chord': chord, 'duration': 1.0})
        
        return progression_items
    
    def validate_brackets(self, progression_str: str) -> Tuple[bool, Optional[str]]:
        """Validate that square brackets are properly paired in the chord progression."""
        bracket_count = 0
        last_chord_before_any_bracket = None
        last_chord_seen = None
        current_segment = ""
        
        for char in progression_str:
            if char in ['–', '-', '—', '[', ']']:
                # Save the chord we just finished reading
                if current_segment.strip():
                    last_chord_seen = current_segment.strip()
                
                if char == '[':
                    # Remember the most recent chord before any opening bracket
                    if last_chord_seen:
                        last_chord_before_any_bracket = last_chord_seen
                    bracket_count += 1
                elif char == ']':
                    bracket_count -= 1
                    if bracket_count < 0:
                        # More closing brackets than opening
                        error_msg = "The opening square bracket '[' is missing."
                        if last_chord_seen:
                            error_msg += f"\nCheck the chord '{last_chord_seen}' or the previous chord."
                        return False, error_msg
                
                current_segment = ""
            else:
                current_segment += char
        
        # Check for unmatched opening brackets
        if bracket_count > 0:
            if last_chord_before_any_bracket:
                error_msg = f"The closing square bracket ']' is missing.\nCheck the chord '{last_chord_before_any_bracket}' or the previous chord."
            else:
                error_msg = "The closing square bracket ']' is missing.\nCheck your chord progression."
            return False, error_msg
        
        return True, None

    def create_midi(self, progression_items: List[Dict], octave: int, bpm: int = 120) -> Optional[MIDIFile]:
        """Create MIDI file from progression items with specified BPM."""
        midi = MIDIFile(1)
        track = 0
        channel = 0
        tempo = bpm  # Use the specified BPM
        volume = 100
        
        midi.addTempo(track, 0, tempo)
        
        current_time = 0
        
        for item in progression_items:
            chord_name = item['chord']
            duration = item['duration']
            
            notes = self.get_chord_notes(chord_name, octave)
            
            if notes is None:
                QMessageBox.critical(self, "Error", 
                                    f"Chord '{chord_name}' is not recognized or does not exist.")
                return None
            
            # Add all notes of the chord
            for note in notes:
                midi.addNote(track, channel, note, current_time, duration, volume)
            
            current_time += duration
        
        return midi
    
    def process_chords(self):
        """Process the input chord progression and create MIDI file."""
        progression_str = self.chord_input.text()
        
        if not progression_str:
            QMessageBox.warning(self, "Input Required", "Please enter a chord progression.")
            return
        
        # Validate square brackets
        is_valid, error_msg = self.validate_brackets(progression_str)
        if not is_valid:
            QMessageBox.warning(self, "Bracket Error", error_msg)
            return
    
        try:
            octave = int(self.octave_combo.currentText())
            bpm = self.bpm
            progression_items = self.parse_progression(progression_str)
            
            if not progression_items:
                QMessageBox.warning(self, "No Chords", "No valid chords found in the progression.")
                return
            
            midi_file = self.create_midi(progression_items, octave, bpm)
            
            if midi_file:
                # Generate filename based on progression
                safe_filename = re.sub(r'[^\w\s-]', '', progression_str[:30])
                safe_filename = re.sub(r'[-\s]+', '_', safe_filename)
                filename = f"{safe_filename}_BPM{bpm}.mid"
                
                # Save to temporary file
                temp_file = tempfile.NamedTemporaryFile(mode='wb', suffix='.mid', delete=False)
                midi_file.writeFile(temp_file)
                temp_file.close()
                
                self.current_midi_file = temp_file.name
                self.midi_display.set_midi_file(temp_file.name, filename)
                
                # Update display
                info_text = f"✓ MIDI File Created Successfully!\n\n"
                info_text += f"Chord Progression: {progression_str}\n"
                info_text += f"Octave: {octave} | BPM: {bpm}\n"
                info_text += f"Number of chords: {len(progression_items)}\n\n"
                info_text += "🎵 Click 'Preview' to listen to the MIDI\n"
                info_text += "📁 Drag this area to Desktop or any folder to save the MIDI file\n"
                info_text += "📥 Or drag a MIDI file here to convert it to chord progression\n"
                info_text += f"   File will be saved as: {filename}"
                
                self.update_midi_display(info_text)
                
                # Enable preview button
                self.preview_btn.setEnabled(True)
                
                self.show_status_message("MIDI file created successfully")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")
    
    def reset_fields(self):
        """Reset input fields and MIDI display."""
        self.chord_input.clear()
        self.current_midi_file = None
        self.midi_display.set_midi_file(None)
        self.update_midi_display("")
        self.preview_btn.setEnabled(False)
        self.stop_preview()  # Stop any playing audio
        self.show_status_message("")
    
    def update_midi_display(self, text: str):
        """Update the MIDI display area."""
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
    
    def preview_midi(self):
        """Preview the generated MIDI file."""
        if not self.current_midi_file:
            QMessageBox.warning(self, "No File", "Please create a MIDI file first.")
            return
        
        if not PYGAME_AVAILABLE:
            QMessageBox.warning(self, "Preview Unavailable", 
                               "pygame is not installed. Install it with: pip install pygame")
            return
        
        try:
            # Stop any currently playing audio
            self.stop_preview()
            
            # Start new playback thread
            self.player_thread = MidiPlayerThread(self.current_midi_file)
            self.player_thread.finished.connect(self.on_preview_finished)
            self.player_thread.error.connect(self.on_preview_error)
            self.player_thread.start()
            
            # Update UI
            self.preview_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.show_status_message("Playing MIDI...")
            
        except Exception as e:
            QMessageBox.critical(self, "Playback Error", f"Failed to play MIDI: {str(e)}")
    
    def stop_preview(self):
        """Stop MIDI preview playback."""
        if self.player_thread and self.player_thread.isRunning():
            self.player_thread.stop()
            self.player_thread.wait()
        
        self.preview_btn.setEnabled(self.current_midi_file is not None)
        self.stop_btn.setEnabled(False)
        self.show_status_message("Playback stopped")
    
    @pyqtSlot()
    def on_preview_finished(self):
        """Handle preview playback completion."""
        self.preview_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.show_status_message("Playback finished")
    
    @pyqtSlot(str)
    def on_preview_error(self, error_msg):
        """Handle preview playback errors."""
        QMessageBox.critical(self, "Playback Error", error_msg)
        self.preview_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
    
    def show_status_message(self, message: str):
        """Show a status message."""
        self.status_label.setText(message)
        if message:
            # Clear message after 3 seconds
            QTimer.singleShot(3000, lambda: self.status_label.setText(""))
    
    def open_twitter(self):
        """Open Twitter profile in default browser."""
        import webbrowser
        webbrowser.open("https://x.com/sochan_life")


def main():
    """Main entry point for the application."""
    app = QApplication(sys.argv)
    
    # Set application metadata
    app.setApplicationName("Chord to MIDI Converter")
    app.setOrganizationName("ChordToMIDI")
    
    # Create and show main window
    window = ChordToMIDIQt()
    window.show()
    
    # Run the application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()