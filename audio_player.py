import time
from pydub.playback import play
from PyQt6.QtCore import pyqtSignal, QObject
from threading import Thread, Event as ThreadEvent

class AudioPlayer(QObject):
    """
    Audio player with playback controls and state management.
    Handles audio playback with pause/resume/abort capabilities.
    """

    # Define signals for state changes and error handling
    playback_started = pyqtSignal()
    playback_paused = pyqtSignal()
    playback_resumed = pyqtSignal()
    playback_finished = pyqtSignal()
    playback_error = pyqtSignal(str)
    state_changed = pyqtSignal(bool)  # True = playing, False = paused/stopped

    def __init__(self):
        super().__init__()
        self.pause_event = ThreadEvent()
        self.abort_event = ThreadEvent()
        self.audio = None
        self.playing = False
        self.playback_thread = None

    def play(self, audio_segment):
        """Play audio with state management and error handling"""
        try:
            if not audio_segment:
                raise ValueError("No audio data provided")

            self.audio = audio_segment
            self.pause_event.clear()
            self.abort_event.clear()
            self.playing = True

            self.playback_started.emit()
            self.state_changed.emit(True)

            while not self.abort_event.is_set():
                if not self.pause_event.is_set():
                    if self.playing:
                        play(self.audio)
                        if not self.abort_event.is_set():
                            self.playing = False
                            self.playback_finished.emit()
                            self.state_changed.emit(False)
                        break
                time.sleep(0.1)

        except Exception as e:
            self.playing = False
            self.playback_error.emit(str(e))
            self.state_changed.emit(False)
        finally:
            if not self.abort_event.is_set():
                self.playback_finished.emit()
                self.state_changed.emit(False)

    def pause(self):
        """Pause audio playback"""
        if self.playing:
            self.pause_event.set()
            self.playing = False
            self.playback_paused.emit()
            self.state_changed.emit(False)

    def resume(self):
        """Resume audio playback"""
        if not self.playing and self.audio:
            self.pause_event.clear()
            self.playing = True
            self.playback_resumed.emit()
            self.state_changed.emit(True)

    def toggle_playback(self):
        """Toggle between play and pause states"""
        if self.playing:
            self.pause()
        else:
            self.resume()

    def abort(self):
        """Abort audio playback"""
        self.abort_event.set()
        self.playing = False
        self.playback_finished.emit()
        self.state_changed.emit(False)

    def cleanup(self):
        """Clean up resources and stop playback"""
        self.abort()
        if self.playback_thread and self.playback_thread.is_alive():
            self.playback_thread.join(timeout=1.0)
        self.audio = None
        self.playing = False

    def is_playing(self):
        """Check if audio is currently playing"""
        return self.playing and not self.pause_event.is_set()

    def has_audio(self):
        """Check if audio data is loaded"""
        return self.audio is not None

    def start_playback_thread(self, audio_segment):
        """Start audio playback in a separate thread"""
        if self.playback_thread and self.playback_thread.is_alive():
            self.abort()
            self.playback_thread.join(timeout=1.0)

        self.playback_thread = Thread(target=self.play, args=(audio_segment,))
        self.playback_thread.daemon = True
        self.playback_thread.start()
