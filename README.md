# Telegram Bot with GPT-3 and Audio Transcription

This Telegram bot is designed to interact with users by providing GPT-3 generated responses and transcribing audio messages using the OpenAI Whisper API.

## Features

* GPT-3 integration for generating text responses
* Audio transcription using OpenAI Whisper API
* Restricted access to specific chat IDs

## Setup

1. Install the required Python packages:

```bash
pip install -r requirements.txt
```

2. Create a `.env` file in the project directory with the following variables:

```
TELEGRAM_BOT_TOKEN=<your_telegram_bot_token>
OPEN_AI_API_KEY=<your_openai_api_key>
ALLOWED_CHAT_IDS=<comma_separated_list_of_allowed_chat_ids>
```

3. Run the script:

```bash
python main.py
```

## Usage

* To get a GPT-3 generated response, send a message starting with "gpt":

```
gpt What is the meaning of life?
```

* Send an audio message to the bot, and it will transcribe the audio using the OpenAI Whisper API.

* Use the `/start` command to receive a welcome message.

## Restrictions

The bot only responds to users whose chat IDs are listed in the `ALLOWED_CHAT_IDS` environment variable. This helps prevent unauthorized usage.

## Alternative usage - Docker

The bot can also be installed either via a bash script that will run a Docker container, or by loading the container (for instance from an IDE)