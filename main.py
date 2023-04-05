import os
import logging
from typing import List
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import filters, MessageHandler, ApplicationBuilder, ContextTypes, CommandHandler
from gpt_adapter import OpenAI
import requests

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

my_open_ai = OpenAI()
allowed_chat_ids: List[int] = [int(chat_id) for chat_id in os.getenv('ALLOWED_CHAT_IDS').split(',')]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id in allowed_chat_ids:
        await update.message.reply_text("Welcome, I'd love to help")


async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id in allowed_chat_ids:
        logging.info(f"Replying message from verified user")
        received_message_text = update.message.text
        if received_message_text == 'ping':
            await context.bot.send_message(chat_id=update.effective_chat.id, text="pong")
        elif received_message_text[:3] == "gpt":
            response = my_open_ai.answer_message(received_message_text[4:])
            await context.bot.send_message(chat_id=update.effective_chat.id, text=response)
        else:
            # reply with welcome message
            await update.message.reply_text("Welcome, I'd love to help")


async def process_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id in allowed_chat_ids:
        logging.info(f"Transcribing audio file from verified user")
        audio_file = update.message.audio  # Access the audio file

        # Download the audio file
        local_file_path = f"audio_files/{audio_file.file_name}"
        file = await context.bot.get_file(file_id=audio_file.file_id)
        await file.download_to_drive(local_file_path)  #

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

        # Split the response text into smaller chunks
        response_chunks = []
        max_length = 1000
        for sentence in response_text.split('.'):
            sentence += '.'
            while len(sentence) > max_length:
                last_space = sentence[:max_length].rfind(' ')
                response_chunks.append(sentence[:last_space])
                sentence = sentence[last_space + 1:]
            response_chunks.append(sentence)

        # Send each chunk as a separate message
        for chunk in response_chunks:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=chunk)

        # Your logic to process the response and caption text goes here
        os.remove(local_file_path)


# Remove the temporary audio file


if __name__ == '__main__':
    application = ApplicationBuilder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()

    start_handler = CommandHandler('start', start)
    echo_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), reply)
    audio_handler = MessageHandler(filters.AUDIO, process_audio)

    application.add_handler(start_handler)
    application.add_handler(echo_handler)
    application.add_handler(audio_handler)

    application.run_polling()
