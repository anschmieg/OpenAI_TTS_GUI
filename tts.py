import os
import requests
import time
import logging
from threading import Thread
from decimal import Decimal
from PyQt6.QtWidgets import QMessageBox
from utils import (
    split_text,
    estimate_price,
    read_api_key,
    concatenate_audio_files,
    cleanup_files,
)
from openai import OpenAI

# Read the API key once and initialize the client
api_key = read_api_key()
if not api_key:
    raise ValueError(
        "The API key must be set either by setting the OPENAI_API_KEY environment variable or by providing it in a configuration file."
    )
client = OpenAI(api_key=api_key)

# Constants for price and API calls
TTS_PRICE_PER_1K_CHARS = Decimal("0.015")
TTS_HD_PRICE_PER_1K_CHARS = Decimal("0.030")
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

logging.basicConfig(
    filename="tts_app.log",
    level=logging.DEBUG,
    format="%(asctime)s:%(levelname)s:%(message)s",
)


def create_tts(values, window):
    """
    Creates a Text-to-Speech (TTS) request based on the provided values and updates the window with progress.

    Args:
        values (dict): A dictionary containing the following keys:
            - "text_box" (str): The text to be converted to speech.
            - "path_entry" (str): The file path where the TTS output will be saved.
            - "model_var" (str): The TTS model to be used.
            - "voice_var" (str): The voice to be used for TTS.
            - "format_var" (str): The format of the TTS output.
            - "speed_var" (str): The speed of the speech.
            - "retain_files" (bool): Whether to retain intermediate files.
            - "streaming" (bool, optional): Whether to stream the speech. Defaults to False.
        window (QWidget): The window object to update with messages and progress.

    Returns:
        None
    """
    logging.debug("Starting create_tts function")
    text = values["text_box"].strip()
    path = values["path_entry"]
    if not path or not os.path.isdir(os.path.dirname(path)):
        logging.error("Invalid path provided")
        window.show_message("Invalid path")
        return
    model = values["model_var"]
    voice = values["voice_var"]
    response_format = values["format_var"]
    speed = float(values["speed_var"]) if values["speed_var"] else 1.0
    hd = "hd" in model
    char_count = len(text)
    estimated_price = estimate_price(char_count, hd)
    retain_files = values["retain_files"]
    streaming = values.get("streaming", False)

    logging.info(f"Text length: {char_count} characters")
    logging.info(f"Estimated price: ${estimated_price:.3f}")
    logging.info(
        f"Model: {model}, Voice: {voice}, Format: {response_format}, Speed: {speed}"
    )
    logging.info(f"Retain files: {retain_files}, Streaming: {streaming}")

    msg_box = QMessageBox()
    msg_box.setText(
        f"The estimated cost for this TTS is ${estimated_price:.3f}. Do you want to continue?"
    )
    msg_box.setStandardButtons(
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    result = msg_box.exec()

    if result == QMessageBox.StandardButton.Yes:
        logging.debug("User confirmed to proceed with TTS")
        window.progress_updated.emit(1)  # Set progress to 1% when starting
        if streaming:
            logging.debug("Starting streaming TTS in a new thread")
            Thread(
                target=stream_tts,
                args=(
                    text,
                    path,
                    model,
                    voice,
                    response_format,
                    speed,
                    window,
                ),
            ).start()
        else:
            logging.debug("Starting process TTS in a new thread")
            Thread(
                target=process_tts,
                args=(
                    split_text(text),
                    path,
                    model,
                    voice,
                    response_format,
                    speed,
                    retain_files,
                    window,
                ),
            ).start()
    else:
        logging.debug("User declined to proceed with TTS")


def stream_tts(values, window):
    """
    Streams text-to-speech (TTS) audio from values dictionary and saves to specified file path.

    Args:
        values (dict): Dictionary containing:
            - text_box (str): Text to convert to speech
            - path_entry (str): Output file path
            - model_var (str): TTS model name
            - voice_var (str): Voice ID
            - format_var (str): Audio format
            - speed_var (float): Speech speed
        window (object): GUI window for progress updates

    Raises:
        Exception: If error occurs during TTS streaming
    """
    try:
        text = values["text_box"].strip()
        path = values["path_entry"]
        model = values["model_var"]
        voice = values["voice_var"]
        response_format = values["format_var"]
        speed = float(values["speed_var"]) if values["speed_var"] else 1.0

        logging.debug(f"Streaming TTS request for: {text[:50]}...")

        response = requests.post(
            "https://api.openai.com/v1/audio/speech",
            headers={
                "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "input": text,
                "voice": voice,
                "response_format": response_format,
                "speed": speed,
            },
            stream=True,
        )

        if response.status_code != 200:
            logging.error(f"Failed to stream TTS: {response.status_code}")
            logging.error(response.json())
            window.show_message(f"Failed to stream TTS: {response.status_code}")
            return

        with open(path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file.write(chunk)
                    window.progress_updated.emit(50)

        window.progress_updated.emit(100)
        logging.info(f"Streaming TTS saved to {path}")

    except Exception as e:
        logging.exception(f"Error during streaming TTS: {e}")
        window.show_message(f"Error during streaming TTS: {str(e)}")


def process_tts(
    chunks, path, model, voice, response_format, speed, retain_files, window
):
    """
    Processes speech chunks, saves them as temporary files, and concatenates them into a final audio file.

    Args:
        chunks (list): List of speech chunks to be processed.
        path (str): Path to save the final concatenated audio file.
        model (str): Model to be used for speech processing.
        voice (str): Voice to be used for speech synthesis.
        response_format (str): Format of the response audio files (e.g., 'mp3', 'wav').
        speed (float): Speed of the speech synthesis.
        retain_files (bool): Whether to retain the temporary files after processing.
        window (object): GUI window object to emit progress updates.

    Returns:
        None
    """
    logging.debug("Starting process_tts function")
    temp_files = []
    total_chunks = len(chunks)
    logging.debug(f"Total chunks to process: {total_chunks}")

    for i, chunk in enumerate(chunks):
        progress = (i / total_chunks) * 100
        window.progress_updated.emit(progress)
        logging.debug(f"Processing chunk {i+1}/{total_chunks}, progress: {progress}%")

        temp_filename = os.path.join(
            os.path.dirname(path),
            f"{os.path.splitext(os.path.basename(path))[0]}_{i}.{response_format}",
        )
        temp_files.append(temp_filename)
        logging.debug(f"Temporary filename: {temp_filename}")

        if not save_chunk(chunk, temp_filename, model, voice, response_format, speed):
            logging.error(f"Failed to save chunk {i+1}")
            cleanup_files(temp_files, retain_files)
            return

    logging.debug("All chunks processed, concatenating audio files")
    concatenate_audio_files(temp_files, path)
    window.progress_updated.emit(100)
    logging.debug(f"Final audio file saved to {path}")

    if not retain_files:
        logging.debug("Cleaning up temporary files")
        cleanup_files(temp_files, retain_files)
    logging.debug("Finished process_tts function")


def make_api_request(api_key, data, model):
    """
    Makes a POST request to the OpenAI API to generate text completions.

    Args:
        api_key (str): The API key for authenticating with the OpenAI API.
        data (dict): The payload to send in the request body.
        model (str): The model ID to use for generating completions.

    Returns:
        requests.Response: The response object if the request is successful.
        None: If the request fails after the maximum number of retries.

    Raises:
        requests.RequestException: If a network-related error occurs.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    url = f"https://api.openai.com/v1/models/{model}/completions"

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(url, json=data, headers=headers)
            if response.status_code == 200:
                return response
            elif response.status_code in [429, 500, 502, 503, 504]:
                logging.warning(
                    f"Received status code {response.status_code}. Retrying after delay."
                )
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                logging.error(
                    f"Failed to create TTS: {response.status_code}\n{response.text}"
                )
                return None
        except requests.RequestException as e:
            logging.exception(f"Network error occurred on attempt {attempt + 1}: {e}")
            time.sleep(RETRY_DELAY * (attempt + 1))
    return None


def save_chunk(chunk, filename, model, voice, response_format, speed):
    """
    Save a single chunk of text as an audio file using OpenAI's TTS API.

    Args:
        chunk (str): Text chunk to convert to speech
        filename (str): Output filename for the audio
        model (str): TTS model name
        voice (str): Voice ID to use
        response_format (str): Audio format (mp3, wav, etc)
        speed (float): Speech speed multiplier

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logging.debug(f"Sending TTS request for chunk: {chunk[:50]}...")

        response = requests.post(
            "https://api.openai.com/v1/audio/speech",
            headers={
                "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "input": chunk,
                "voice": voice,
                "response_format": response_format,
                "speed": speed,
            },
        )

        if response.status_code != 200:
            logging.error(f"Failed to create TTS: {response.status_code}")
            logging.error(response.json())
            return False

        with open(filename, "wb") as f:
            f.write(response.content)

        logging.debug(f"Successfully saved chunk to {filename}")
        return True

    except Exception as e:
        logging.exception(f"Error in save_chunk: {str(e)}")
        return False
