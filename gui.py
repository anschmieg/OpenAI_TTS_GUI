from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QFileDialog,
    QComboBox,
    QMessageBox,
    QMenuBar,
    QMenu,
    QInputDialog,
)
from PyQt6.QtCore import pyqtSignal, pyqtSlot
from PyQt6.QtGui import QAction
from threading import Thread

from tts import create_tts, stream_tts
from utils import split_text, estimate_price, read_api_key, write_api_key
from audio_player import AudioPlayer


class TTSWindow(QWidget):
    """TTSWindow is a QWidget-based class that provides a GUI for a Text-to-Speech application using OpenAI's API."""

    progress_updated = pyqtSignal(int)
    show_message_signal = pyqtSignal(str)  # New signal for messages

    def __init__(self):
        super().__init__()
        self.api_key = read_api_key()
        self.player = None
        self.playback_control = None
        self.initUI()
        self.check_api_key()
        self.set_dark_theme()

        # Connect message signal to slot
        self.show_message_signal.connect(self.show_message_slot)

        # Update signal connections
        self.play_pause_button.clicked.connect(self.on_play_pause_clicked)
        self.abort_button.clicked.connect(self.on_abort_clicked)

    # Modify existing show_message to emit signal
    def show_message(self, message):
        self.show_message_signal.emit(message)

    def initUI(self):
        self.setWindowTitle("OpenAI TTS")
        self.setGeometry(100, 100, 600, 400)

        # Main layout
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Text area
        self.text_edit = QTextEdit(self)
        self.char_count_label = QLabel("Character Count: 0", self)
        self.chunk_count_label = QLabel("Number of Chunks: 0", self)
        self.price_label = QLabel("Estimated Price: $0.015", self)

        # Controls
        self.model_combo = QComboBox(self)
        self.model_combo.addItems(["tts-1", "tts-1-hd"])

        self.voice_combo = QComboBox(self)
        self.voice_combo.addItems(["alloy", "echo", "fable", "onyx", "nova", "shimmer"])

        self.speed_input = QLineEdit(self)
        self.speed_input.setText("1.0")

        self.format_combo = QComboBox(self)
        self.format_combo.addItems(["mp3", "opus", "aac", "flac"])

        self.path_entry = QLineEdit(self)
        self.select_path_button = QPushButton("Select Path", self)

        self.progress_bar = QProgressBar(self)

        # Action buttons
        self.create_button = QPushButton("Create TTS", self)
        self.stream_button = QPushButton("Stream and Play", self)
        self.play_pause_button = QPushButton("Play", self)
        self.abort_button = QPushButton("Abort", self)

        # Initially hide playback controls
        self.play_pause_button.hide()
        self.abort_button.hide()

        # Layout arrangement
        self.layout.addWidget(QLabel("Text for TTS:"))
        self.layout.addWidget(self.text_edit)

        char_chunk_layout = QHBoxLayout()
        char_chunk_layout.addWidget(self.char_count_label)
        char_chunk_layout.addWidget(self.chunk_count_label)
        char_chunk_layout.addWidget(self.price_label)
        self.layout.addLayout(char_chunk_layout)

        settings_layout = QHBoxLayout()
        settings_layout.addWidget(QLabel("Model:"))
        settings_layout.addWidget(self.model_combo)
        settings_layout.addWidget(QLabel("Voice:"))
        settings_layout.addWidget(self.voice_combo)
        settings_layout.addWidget(QLabel("Speed:"))
        settings_layout.addWidget(self.speed_input)
        settings_layout.addWidget(QLabel("Format:"))
        settings_layout.addWidget(self.format_combo)
        self.layout.addLayout(settings_layout)

        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Save Path:"))
        path_layout.addWidget(self.path_entry)
        path_layout.addWidget(self.select_path_button)
        self.layout.addLayout(path_layout)

        self.layout.addWidget(self.progress_bar)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.create_button)
        button_layout.addWidget(self.stream_button)
        button_layout.addWidget(self.play_pause_button)
        button_layout.addWidget(self.abort_button)
        self.layout.addLayout(button_layout)

        # Menu setup
        menubar = QMenuBar(self)
        self.layout.setMenuBar(menubar)

        settings_menu = QMenu("Settings", self)
        menubar.addMenu(settings_menu)

        theme_menu = QMenu("Themes", self)
        settings_menu.addMenu(theme_menu)

        light_action = QAction("Light", self)
        dark_action = QAction("Dark", self)
        theme_menu.addAction(light_action)
        theme_menu.addAction(dark_action)

        self.retain_files_checkbox_action = QAction(
            "Retain individual audio files", self, checkable=True
        )
        settings_menu.addAction(self.retain_files_checkbox_action)

        api_key_menu = QMenu("API Key", self)
        settings_menu.addMenu(api_key_menu)

        use_system_action = QAction("Use System", self)
        set_custom_action = QAction("Set Custom", self)
        api_key_menu.addAction(use_system_action)
        api_key_menu.addAction(set_custom_action)

        # Connect signals
        self.text_edit.textChanged.connect(self.update_counts)
        self.select_path_button.clicked.connect(self.select_path)
        self.create_button.clicked.connect(self.create_tts)
        self.stream_button.clicked.connect(self.stream_tts)
        light_action.triggered.connect(self.set_light_theme)
        dark_action.triggered.connect(self.set_dark_theme)
        use_system_action.triggered.connect(self.use_system_api_key)
        set_custom_action.triggered.connect(self.set_custom_api_key)
        self.progress_updated.connect(self.update_progress)

        # Connect playback control buttons
        self.play_pause_button.clicked.connect(self.on_play_pause_clicked)
        self.abort_button.clicked.connect(self.on_abort_clicked)

    # New slot to show messages on main thread
    @pyqtSlot(str)
    def show_message_slot(self, message):
        msg_box = QMessageBox(self)
        msg_box.setText(message)
        msg_box.exec()

    def closeEvent(self, event):
        """Clean up resources before closing"""
        if self.player:
            self.player.cleanup()
        if self.playback_control:
            self.playback_control = None
        event.accept()

    def stream_tts(self):
        try:
            if not self.api_key:
                self.show_message_signal.emit("No API key found...")
                return

            self.stream_button.hide()
            self.play_pause_button.show()
            self.abort_button.show()

            values = {
                "text_box": self.text_edit.toPlainText(),
                "model_var": self.model_combo.currentText(),
                "voice_var": self.voice_combo.currentText(),
                "format_var": "wav",  # Force WAV for streaming
                "speed_var": self.speed_input.text(),
            }

            if not values["text_box"].strip():
                self.show_message_signal.emit("Please enter some text first")
                return

            self.player = AudioPlayer()
            self.playback_control = self.player  # Set additional reference
            self.player.playback_finished.connect(lambda: self.reset_playback_ui())
            self.player.playback_error.connect(self.show_message_signal)
            self.player.state_changed.connect(self.on_player_state_changed)

            Thread(target=stream_tts, args=(values, self)).start()
        except Exception as e:
            self.show_message_signal.emit(f"Error: {str(e)}")
            self.reset_playback_ui()

    @pyqtSlot()
    def on_play_pause_clicked(self):
        """Handle play/pause button clicks"""
        if self.player:
            self.player.toggle_playback()

    @pyqtSlot()
    def on_abort_clicked(self):
        """Handle abort button clicks"""
        if self.player:
            self.player.abort()
            self.reset_playback_ui()

    @pyqtSlot(bool)
    def on_player_state_changed(self, is_playing):
        """Update UI based on player state"""
        self.play_pause_button.setText("Pause" if is_playing else "Play")

    @pyqtSlot(int)
    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def check_api_key(self):
        if not self.api_key:
            self.show_message(
                "No API key found. Please set the API key in the environment variable 'OPENAI_API_KEY' or in the app's settings."
            )
            return False
        return True

    def reset_playback_ui(self):
        self.stream_button.show()
        self.play_pause_button.hide()
        self.abort_button.hide()

    # New slot to show messages on main thread
    @pyqtSlot(bool)
    def set_light_theme(self):
        self.setStyleSheet("QWidget { background-color: #FFFFFF; color: #000000; }")
        self.text_edit.setStyleSheet(
            "QTextEdit { background-color: #F0F0F0; color: #000000; }"
        )

    @pyqtSlot(bool)
    def set_dark_theme(self):
        self.setStyleSheet("QWidget { background-color: #2E2E2E; color: #FFFFFF; }")
        self.text_edit.setStyleSheet(
            "QTextEdit { background-color: #3E3E3E; color: #FFFFFF; }"
        )

    @pyqtSlot(bool)
    def use_system_api_key(self):
        self.api_key = read_api_key()
        QMessageBox.information(self, "API Key", "Using system API key.")

    @pyqtSlot(bool)
    def set_custom_api_key(self):
        api_key, ok = QInputDialog.getText(
            self, "Set Custom API Key", "Enter your API key:"
        )
        if ok:
            self.api_key = api_key
            if write_api_key(api_key):
                QMessageBox.information(self, "Key", "Custom API key set.")
            else:
                QMessageBox.warning(self, "Key", "Failed to save custom API key.")

    def update_counts(self):
        text = self.text_edit.toPlainText()
        char_count = len(text)
        chunks = split_text(text)
        num_chunks = len(chunks)
        hd = "hd" in self.model_combo.currentText()
        price = estimate_price(char_count, hd)
        self.char_count_label.setText(f"Character Count: {char_count}")
        self.chunk_count_label.setText(f"Number of Chunks: {num_chunks}")
        self.price_label.setText(f"Estimated Price: ${price:.3f}")

    def select_path(self):
        format_map = {
            "mp3": "MP3 Files (*.mp3)",
            "opus": "Opus Files (*.opus)",
            "aac": "AAC Files (*.aac)",
            "flac": "FLAC Files (*.flac)",
        }
        selected_format = self.format_combo.currentText()
        file_filter = format_map.get(selected_format, "All Files (*.*)")
        file_path, _ = QFileDialog.getSaveFileName(self, "Save As", "", file_filter)
        if file_path:
            self.path_entry.setText(file_path)

    def create_tts(self):
        if not self.api_key:
            self.show_message(
                "No API key found. Set the API key in the environment, `.env` file or the app's settings."
            )
            return

        values = {
            "text_box": self.text_edit.toPlainText(),
            "path_entry": self.path_entry.text(),
            "model_var": self.model_combo.currentText(),
            "voice_var": self.voice_combo.currentText(),
            "format_var": self.format_combo.currentText(),
            "speed_var": self.speed_input.text(),
            "retain_files": self.retain_files_checkbox_action.isChecked(),
        }

        create_tts(values, self)
