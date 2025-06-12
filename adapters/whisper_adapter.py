import os
import re
import logging
from typing import List
import requests
from dotenv import load_dotenv

load_dotenv()


# TODO convert to class
def transcribe_audio_file(local_file_path: str) -> List[str]:
    # Send the audio file to the OpenAI API endpoint
    openai_api_key = os.getenv("OPEN_AI_API_KEY")
    headers = {
        "Authorization": f"Bearer {openai_api_key}",
    }
    url = "https://api.openai.com/v1/audio/transcriptions"
    model = "whisper-1"

    with open(local_file_path, "rb") as audio_data:
        files = {"file": (local_file_path, audio_data)}
        data = {"model": model, "response_format": "json"}
        response = requests.post(url, headers=headers, data=data, files=files)

    logging.info("Whisper API status: %s", response.status_code)
    if response.status_code != 200:
        logging.error("Whisper API error: %s", response.text)
    try:
        response_text = response.json().get("text")
    except Exception:  # JSON decoding failed
        logging.exception("Failed to decode Whisper response: %s", response.text)
        raise

    if response_text is None:
        logging.error("Unexpected Whisper response payload: %s", response.text)
        raise ValueError("No transcription text returned")

    # Split the response text into sentences using a regular expression
    sentences = re.split("(?<=[.!?]) +", response_text)

    # Combine the sentences into messages of no more than 1000 characters each
    messages = []
    current_message = ""
    for sentence in sentences[:-1]:
        if len(current_message) + len(sentence) <= 1000:
            current_message += sentence
        else:
            messages.append(current_message)
            current_message = sentence
    if len(current_message) > 1000:
        messages.append(current_message)
        current_message = ""
    messages.append(current_message + sentences[-1])

    # Send each message as a separate message
    return messages
