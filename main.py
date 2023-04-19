import os
import logging
import re
from typing import List
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import filters, MessageHandler, ApplicationBuilder, ContextTypes, CommandHandler
from gpt_adapter import OpenAI
import requests

load_dotenv()  # Python module to load environment variables from a .env file

# Configure logging (native python library)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

my_open_ai = OpenAI()  # OpenAI is a custom class that works as a wrapper/adapter for OpenAI's GPT API
allowed_chat_ids: List[int] = [int(chat_id) for chat_id in os.getenv('ALLOWED_CHAT_IDS').split(',')]  # Pythonic way of creating a list, behaves like a loop


# extracted method to only allow verified users
def allowed_user(update: Update) -> bool:
    return update.effective_chat.id in allowed_chat_ids


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if allowed_user(update):
        await update.message.reply_text("Welcome, I'd love to help")


async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if allowed_user(update):
        logging.info(f"Replying message from verified user")
        received_message_text = update.message.text
        if received_message_text == 'ping':
            await context.bot.send_message(chat_id=update.effective_chat.id, text="pong")
        elif received_message_text[:4] == "gpt4":
            response = my_open_ai.answer_message(received_message_text[4:], model="gpt-4")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=response)
        elif received_message_text[:3] == "gpt":
            response = my_open_ai.answer_message(received_message_text[4:])
            await context.bot.send_message(chat_id=update.effective_chat.id, text=response)
        else:
            # reply with welcome message
            await update.message.reply_text("I don't know how to answer to that")


#  This method will be called each time the bot receives an audio file
async def process_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if allowed_user(update):
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
        for message in messages:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=message)

        # Your logic to process the response and caption text goes here
        # os.remove(local_file_path)


# Remove the temporary audio file


if __name__ == '__main__':
    # This comes directly from the telegram bot library
    bot = ApplicationBuilder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()

    # The telegram bot manages events to process through handlers:
    # For each handled event group, the relevant function (defined above) will be invoked
    start_handler = CommandHandler('start', start)
    echo_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), reply)
    audio_handler = MessageHandler(filters.AUDIO, process_audio)

    bot.add_handler(start_handler)
    bot.add_handler(echo_handler)
    bot.add_handler(audio_handler)

    # The app will be running constantly checking for new events
    bot.run_polling()
