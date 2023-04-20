import os
import re
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
        data = {"model": model}
        response = requests.post(url, headers=headers, data=data, files=files)

    response_text = response.json()["text"]

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
