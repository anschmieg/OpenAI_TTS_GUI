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
from tts import create_tts, stream_tts
from utils import split_text, estimate_price, read_api_key, write_api_key


class TTSWindow(QWidget):
    """
    TTSWindow is a QWidget-based class that provides a GUI for a Text-to-Speech application using OpenAI's API.

    Attributes:
        progress_updated (pyqtSignal): Signal to update the progress bar.

    Methods:
        __init__():
            Initializes the GUI application.
        initUI():
            Initializes the user interface for the OpenAI TTS application.
        set_light_theme():
            Sets the light theme for the GUI.
        set_dark_theme():
            Sets the dark theme for the GUI.
        use_system_api_key():
            Reads the API key from the system and sets it for the application.
        set_custom_api_key():
            Prompts the user to enter a custom API key and saves it.
        update_counts():
            Updates the character count, number of chunks, and estimated price labels based on the current text in the text editor.
        select_path():
            Opens QFileDialog to select a path for saving a file in the selected format.
        create_tts():
            Gathers user inputs and calls the `create_tts` function from `tts.py`.
        stream_tts():
            Gathers user inputs and calls the `stream_tts` function from `tts.py`.
        update_progress(value):
            Updates the progress bar widget to the provided value.
        show_message(message):
            Displays a message in a message box.
        check_api_key():
            Checks if the API key is set and displays an error message if not.
    """

    progress_updated = pyqtSignal(int)

    def __init__(self):
        """
        Initializes the GUI application.

        This constructor method performs the following actions:
        1. Calls the parent class initializer.
        2. Reads the API key using the `read_api_key` function.
        3. Initializes the user interface by calling `initUI`.
        4. Checks the validity of the API key with `check_api_key`.
        5. Sets the application theme to dark by default using `set_dark_theme`.
        """
        super().__init__()
        self.api_key = read_api_key()
        self.initUI()
        self.check_api_key()
        self.set_dark_theme()  # Set dark theme by default

    def initUI(self):
        """
        Initializes the user interface for the OpenAI TTS application.

        This method sets up the main window, including the title, geometry, and various widgets such as text edit,
        labels, dropdowns, input fields, progress bar, and buttons. It also configures the layout of these widgets
        and connects signals to their respective slots.

        Menu Bar contains:
            - Settings: Contains options for themes and API key management.
            - Themes: Sub-menu for selecting light or dark theme.
            - API Key: Sub-menu for using system or setting custom API key.

        Signals are:
            - textChanged: Updates character and chunk counts when text changes.
            - clicked: Handles button clicks for selecting path, creating TTS, and streaming/playing.
            - progress_updated: Updates progress bar during TTS creation.
        """
        self.setWindowTitle("OpenAI TTS")
        self.setGeometry(100, 100, 600, 400)

        self.text_edit = QTextEdit(self)
        self.text_edit.setStyleSheet("QTextEdit { background-color: #F5F5F5; }")
        self.char_count_label = QLabel("Character Count: 0", self)
        self.chunk_count_label = QLabel("Number of Chunks: 0", self)
        self.price_label = QLabel("Estimated Price: $0.015", self)

        # Dropdown: Model
        self.model_combo = QComboBox(self)
        self.model_combo.addItems(["tts-1", "tts-1-hd"])

        # Dropdown: Voice
        self.voice_combo = QComboBox(self)
        self.voice_combo.addItems(["alloy", "echo", "fable", "onyx", "nova", "shimmer"])

        # Input: Speed
        self.speed_input = QLineEdit(self)
        self.speed_input.setText("1.0")

        # Dropdown: Output format
        self.format_combo = QComboBox(self)
        self.format_combo.addItems(["mp3", "opus", "aac", "flac"])

        # File selection: Output path
        self.path_entry = QLineEdit(self)
        self.select_path_button = QPushButton("Select Path", self)

        self.progress_bar = QProgressBar(self)

        # Buttons: Create TTS and Save, Stream and Play
        self.create_button = QPushButton("Create TTS", self)
        self.stream_button = QPushButton("Stream and Play", self)

        self.layout = QVBoxLayout()

        # Input: Main Text (to be converted)
        self.layout.addWidget(QLabel("Text for TTS:"))
        self.layout.addWidget(self.text_edit)

        # Arrange labels
        char_chunk_layout = QHBoxLayout()
        char_chunk_layout.addWidget(self.char_count_label)
        char_chunk_layout.addWidget(self.chunk_count_label)
        char_chunk_layout.addWidget(self.price_label)
        self.layout.addLayout(char_chunk_layout)

        # Arrange selectors
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

        # Arrange path and buttons
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Save Path:"))
        path_layout.addWidget(self.path_entry)
        path_layout.addWidget(self.select_path_button)
        self.layout.addLayout(path_layout)

        self.layout.addWidget(self.progress_bar)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.create_button)
        button_layout.addWidget(self.stream_button)
        self.layout.addLayout(button_layout)

        self.setLayout(self.layout)

        # Menu Bar
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

        light_action.triggered.connect(self.set_light_theme)
        dark_action.triggered.connect(self.set_dark_theme)
        use_system_action.triggered.connect(self.use_system_api_key)
        set_custom_action.triggered.connect(self.set_custom_api_key)

        self.text_edit.textChanged.connect(self.update_counts)
        self.select_path_button.clicked.connect(self.select_path)
        self.create_button.clicked.connect(self.create_tts)
        self.stream_button.clicked.connect(self.stream_tts)
        self.progress_updated.connect(self.update_progress)

    def set_light_theme(self):
        """
        Sets the light theme for the GUI.
        """
        self.setStyleSheet("QWidget { background-color: #FFFFFF; color: #000000; }")
        self.text_edit.setStyleSheet(
            "QTextEdit { background-color: #F0F0F0; color: #000000; }"
        )

    def set_dark_theme(self):
        """
        Sets the dark theme for the GUI.
        """
        self.setStyleSheet("QWidget { background-color: #2E2E2E; color: #FFFFFF; }")
        self.text_edit.setStyleSheet(
            "QTextEdit { background-color: #3E3E3E; color: #FFFFFF; }"
        )

    def use_system_api_key(self):
        """
        Reads the API key from the system (using `read_api_key`) and sets it for the application.
        """
        self.api_key = read_api_key()
        QMessageBox.information(self, "API Key", "Using system API key.")

    def set_custom_api_key(self):
        """
        Prompts the user to enter a custom API key and saves it as `self.api_key`
        as well as the `.env` or `api_key.txt` file if exists.

        This method displays a dialog box for the user to input a custom API key. If the user confirms the input,
        the API key is saved to the instance variable `self.api_key` and written to a file. The API key is written
        to a .env file if it exists, otherwise to an api_key.txt file if it exists.
        """
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
        """
        Updates the character count, number of chunks, and estimated price labels
        based on the current text in the text editor.
        """
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
        """
        Opens QFileDialog to select a path for saving a file in the selected format.
        """
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
        """
        Gathers user inputs and calls the `create_tts` function from `tts.py`.
        If the API key is not set, it displays an error message and exits.
        """
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

    def stream_tts(self):
        """
        Gathers user inputs and calls the `stream_tts` function from `tts.py` for streaming.
        If the API key is not set, it displays an error message and exits.
        """
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

        stream_tts(values, self)

    @pyqtSlot(int)
    def update_progress(self, value):
        """
        Updates the progress bar widget to the provided value.
        """
        self.progress_bar.setValue(value)

    def show_message(self, message):
        """
        Displays a message in a message box.
        Args:
            message (str): The message to be displayed.
        """
        msg_box = QMessageBox()
        msg_box.setText(message)
        msg_box.exec()

    def check_api_key(self):
        """
        Checks if the API key is set. If not, it displays an error message.
        """
        if not self.api_key:
            self.show_message(
                "No API key found. Please set the API key in the environment variable 'OPENAI_API_KEY' or in the app's settings."
            )
            return False
        return True
