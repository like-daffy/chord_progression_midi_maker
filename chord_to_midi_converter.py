#!/usr/bin/env python3
"""
Chord Progression to MIDI Converter (PyQt6 Version 1.0)
Enhanced with BPM control, MIDI preview, and true drag-and-drop functionality
No microphone/record permissions required - playback only
"""

import sys
import os
import re
import csv
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import threading
import time

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
    import pygame
    # Initialize mixer without requesting microphone access
    pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    print("Warning: pygame not installed. MIDI preview will not be available.")
    print("Install with: pip install pygame")

# We'll skip sounddevice to avoid microphone permission issues
# Instead, we'll use pygame's default output
SOUNDDEVICE_AVAILABLE = False


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
            pygame.mixer.music.load(self.midi_file)
            pygame.mixer.music.play()
            self.is_playing = True
            
            # Wait while the music is playing
            while pygame.mixer.music.get_busy():
                if not self.is_playing:
                    pygame.mixer.music.stop()
                    break
                time.sleep(0.1)
            
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))
    
    def stop(self):
        """Stop playing."""
        self.is_playing = False
        if PYGAME_AVAILABLE:
            pygame.mixer.music.stop()


class DraggableMidiDisplay(QTextEdit):
    """Custom QTextEdit widget with drag-to-save functionality."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_midi_file = None
        self.midi_filename = "chord_progression.mid"
        self.setReadOnly(True)
        self.setAcceptDrops(False)  # We only drag out, not in
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
C4.4,05af,"""
        
        # Parse CSV data
        lines = csv_content.strip().split('\n')
        reader = csv.DictReader(lines)
        
        for row in reader:
            chord_name = row['Chord']
            chord_code = row['Code']
            bass_note = row['BassNote']
            self.chord_data[chord_name] = {
                'code': chord_code,
                'bass': bass_note
            }
    
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Chord Progression to MIDI Converter v1.0")
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
        
        # MIDI file section (drag-to-save)
        midi_group = QGroupBox("MIDI File (Drag to Save)")
        midi_layout = QVBoxLayout()
        
        # MIDI display area with drag-to-save
        self.midi_display = DraggableMidiDisplay()
        self.midi_display.setMinimumHeight(150)
        self.update_midi_display("")
        
        midi_layout.addWidget(self.midi_display)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #666; font-style: italic; font-size: 11px;")
        midi_layout.addWidget(self.status_label)
        
        midi_group.setLayout(midi_layout)
        main_layout.addWidget(midi_group)
        
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
        """Convert 'min' notation to 'm' notation in chord names.
        
        Examples:
            Cmin -> Cm
            Cmin7 -> Cm7
            C#min -> C#m
            Amin/E -> Am/E
        """
        # Pattern matches: note name (with optional #/b) + 'min'
        # Replace 'min' with 'm' when it follows a note name
        pattern = r'([A-G][#b]?)min'
        return re.sub(pattern, r'\1m', chord_str)
    
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
                # Split by common delimiters
                chords = re.split(r'[–\-—]+', before_bracket)
                for chord in chords:
                    chord = chord.strip()
                    if chord:
                        progression_items.append({'chord': chord, 'duration': 1.0})
            
            # Process chords in bracket
            bracket_content = match.group(1)
            chords_in_bracket = re.split(r'[–\-—]+', bracket_content)
            chords_in_bracket = [c.strip() for c in chords_in_bracket if c.strip()]
            
            if chords_in_bracket:
                duration = 1.0 / len(chords_in_bracket)
                for chord in chords_in_bracket:
                    progression_items.append({'chord': chord, 'duration': duration})
            
            current_pos = match.end()
        
        # Add any remaining chords after last bracket
        remaining = progression_str[current_pos:].strip()
        if remaining:
            chords = re.split(r'[–\-—]+', remaining)
            for chord in chords:
                chord = chord.strip()
                if chord:
                    progression_items.append({'chord': chord, 'duration': 1.0})
        
        return progression_items
    
    def validate_brackets(self, progression_str: str) -> Tuple[bool, Optional[str]]:
        """Validate that square brackets are properly paired in the chord progression.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
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
                "4. Preview the MIDI or drag to save"
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