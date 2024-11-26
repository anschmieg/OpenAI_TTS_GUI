import os
import logging
import sys
import subprocess
import time
from ffpyplayer.player import MediaPlayer
from decimal import Decimal
from dotenv import load_dotenv

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


def split_text(text, chunk_size=4096):
    """
    Splits a given text into chunks of a specified maximum size.
    Args:
        text (str): The input text to be split.
        chunk_size (int, optional): The maximum size of each chunk. Defaults to 4096.
    Returns:
        list of str: A list of text chunks, each with a length up to `chunk_size`.
    """
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    while text:
        if len(text) <= chunk_size:
            chunks.append(text)
            break
        split_index = -1
        for punct in [".", "?", "!", ";"]:
            last_punct_index = text[:chunk_size].rfind(punct)
            if last_punct_index != -1:
                split_index = max(split_index, last_punct_index + 1)
                break
        if split_index == -1:
            split_index = text[:chunk_size].rfind(" ")
        if split_index == -1:
            split_index = chunk_size
        chunks.append(text[:split_index])
        text = text[split_index:].lstrip()
    return chunks


def estimate_price(char_count, hd=False):
    """
    Estimate the price for text-to-speech (TTS) service based on character count.

    Args:
        char_count (int): The number of characters in the text.
        hd (bool, optional): If True, use the high-definition (HD) price rate. Defaults to False.

    Returns:
        float: The estimated price for the TTS service, rounded to three decimal places.
    """
    if char_count == 0:
        return 0.000
    token_price = TTS_PRICE_PER_1K_CHARS if not hd else TTS_HD_PRICE_PER_1K_CHARS
    char_blocks = (char_count + 4095) // 4096  # Correct chunk size
    total_price = char_blocks * token_price
    return round(total_price, 3)


def read_api_key():
    """
    Reads the OpenAI API key from the environment variable, .env file, or api_key.txt file (in that order).
    If all attempts fail, it prints an error message and exits the program.

    Returns:
        str: The OpenAI API key.

    Raises:
        SystemExit: If the API key cannot be found in the environment variable, .env file, or api_key.txt file.
    """
    # Check if environment variable OPENAI_API_KEY is set
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        return api_key

    # Try loading from .env file
    print("API key not set. Trying to load from .env file.")
    try:
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            return api_key
    except Exception as e:
        print(f"Error loading .env file: {e}")

    # Try loading from api_key.txt file
    print("Trying api_key.txt file.")
    try:
        with open("api_key.txt", "r") as file:
            api_key = file.read().strip()
            os.environ["OPENAI_API_KEY"] = api_key
            return api_key
    except Exception as e:
        print(f"Error reading api_key.txt file: {e}")

    # If all attempts fail, exit the program
    print(
        "No API key found. Set the API key in the environment variable 'OPENAI_API_KEY'."
    )
    sys.exit(1)


def write_api_key(api_key):
    """
    Writes the provided API key to a file. If a .env file exists, the API key is written to it.
    If a .env file does not exist but an api_key.txt file exists, the API key is written to it instead.

    Args:
        api_key (str): The API key to be written.

    Returns:
        bool: True if the API key was successfully written, False otherwise.
    """
    try:
        if os.path.exists(".env"):
            with open(".env", "r+") as env_file:
                content = env_file.read()
                env_file.seek(0, 0)
                env_file.write(f"OPENAI_API_KEY={api_key}\n" + content)
        elif os.path.exists("api_key.txt"):
            with open("api_key.txt", "r+") as key_file:
                content = key_file.read()
                key_file.seek(0, 0)
                key_file.write(f"{api_key}\n" + content)
        else:
            return False
        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        return False


def concatenate_audio_files(file_list, output_file):
    """
    Concatenates multiple audio files into a single output file.

    Args:
        file_list (list of str): List of paths to the audio files to be concatenated.
        output_file (str): Path to the output file where the concatenated audio will be saved.
    """
    if len(file_list) == 1:
        os.rename(file_list[0], output_file)
        logging.info(f"Renamed single chunk to {output_file}")
        return

    try:
        output_dir = os.path.dirname(output_file)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        output_extension = os.path.splitext(output_file)[1].lower()
        if output_extension == ".mp3":
            codec = "libmp3lame"
        elif output_extension == ".flac":
            codec = "flac"
        elif output_extension == ".aac":
            codec = "aac"
        elif output_extension == ".opus":
            codec = "libopus"
        else:
            codec = "copy"

        concat_command = [
            "ffmpeg",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            "-",
            "-c:a",
            codec,
            output_file,
        ]

        concat_list = "\n".join(
            f"file '{file_path}'"
            for file_path in file_list
            if os.path.exists(file_path)
        )
        if not concat_list:
            logging.error("No valid files to concatenate.")
            return

        logging.info(f"Running ffmpeg command: {' '.join(concat_command)}")
        result = subprocess.run(
            concat_command,
            input=concat_list.encode(),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        logging.info(result.stdout.decode())
        logging.error(result.stderr.decode())
        logging.info(f"Concatenated audio files into {output_file}")
    except Exception as e:
        logging.error(f"Error in concatenating audio files: {e}")


def cleanup_files(file_list, retain_files):
    """
    Deletes files from the provided list if retain_files is False.

    Args:
        file_list (list): List of file paths to be deleted.
        retain_files (bool): Flag indicating whether to retain the files. If False, files will be deleted.

    Logs:
        Info: When a file is successfully deleted.
        Error: When a file does not exist or fails to be deleted.
    """
    if not retain_files:
        for file in file_list:
            if os.path.exists(file):
                try:
                    os.remove(file)
                    logging.info(f"Deleted temporary file {file}")
                except Exception as e:
                    logging.error(f"Failed to delete temporary file {file}: {e}")
            else:
                logging.error(
                    f"Temporary file {file} does not exist and cannot be deleted."
                )


def play_audio(file_path):
    """Play audio file from path using ffpyplayer (ffmpeg `ffplay` wrapper)."""
    player = MediaPlayer(file_path)
    while True:
        frame, val = player.get_frame()
        if val == "eof":
            break
        elif frame is None:
            time.sleep(0.01)
