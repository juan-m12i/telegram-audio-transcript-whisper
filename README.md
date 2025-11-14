# Telegram Bot with GPT-3 and Audio Transcription

This Telegram bot is designed to interact with users by providing GPT-3 generated responses and transcribing audio messages using the OpenAI Whisper API.

## Features

* GPT-3 integration for generating text responses
* Audio transcription using OpenAI Whisper API
* **NEW**: Notion integration for storing transcriptions and summaries with metadata
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

# Timezone Configuration (Optional)
# Default: "America/Argentina/Buenos_Aires" (GMT-3)
# Override with any valid timezone name (e.g., "America/New_York", "Europe/London", "Asia/Tokyo")
TIMEZONE=America/Argentina/Buenos_Aires

# Notion Integration (Optional)
NOTION_TOKEN=<your_notion_integration_token>
NOTION_TRANSCRIPT_PAGE_ID=<notion_page_id_for_transcripts>
NOTION_SUMMARY_PAGE_ID=<notion_page_id_for_summaries>
```

### Notion Integration Setup

To enable automatic storage of transcriptions and summaries in Notion:

1. **Create a Notion Integration:**
   - Go to [Notion Developers](https://developers.notion.com/)
   - Create a new integration and copy the token
   - Set `NOTION_TOKEN` in your `.env` file

2. **Create Notion Pages:**
   - Create two separate pages in Notion (one for transcripts, one for summaries)
   - Share both pages with your integration
   - Copy the page IDs from the URLs and set:
     - `NOTION_TRANSCRIPT_PAGE_ID` for storing full transcriptions with metadata
     - `NOTION_SUMMARY_PAGE_ID` for storing summaries with metadata

3. **Stored Metadata:**
   - Timestamp of processing
   - Audio duration (in seconds)
   - File size (in bytes)
   - File name
   - MIME type
   - Audio type (audio vs voice message)
   - For audio files: performer and title (if available)

**Note:** If Notion environment variables are not configured, the bot will continue to work normally but won't store data in Notion. Notion storage errors won't affect the main transcription functionality.

3. Run the script:

```bash
python gpt_whisper_bot.py
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