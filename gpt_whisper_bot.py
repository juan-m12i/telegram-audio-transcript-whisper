import logging
import os
from typing import List

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import filters, MessageHandler, ContextTypes, CommandHandler

from adapters.gpt_adapter import OpenAI
from adapters.whisper_adapter import transcribe_audio_file
from bot.bot_actions import action_ping
from bot.bot_common import allowed_user, bot_start, run_telegram_bot, reply_builder
from bot.bot_conditions import first_chars_lower_factory, condition_ping, \
    condition_catch_all
from pydub import AudioSegment
import math

load_dotenv()  # Python module to load environment variables from a .env file

my_open_ai = OpenAI()  # OpenAI is a custom class that works as a wrapper/adapter for OpenAI's GPT API

condition_gpt4 = first_chars_lower_factory(4, 'gpt4')
condition_gpt = first_chars_lower_factory(3, 'gpt')


async def action_gpt4(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f"Answering with GPT4")
    response = my_open_ai.answer_message(update.message.text[4:], model="gpt-4")
    await context.bot.send_message(chat_id=update.effective_chat.id, text=response)


async def action_gpt3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f"Answering with GPT3")
    response = my_open_ai.answer_message(update.message.text[3:])
    await context.bot.send_message(chat_id=update.effective_chat.id, text=response)


async def action_catch_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("I don't know how to answer to that")


reply = reply_builder({
    condition_ping: action_ping,
    condition_gpt4: action_gpt4,
    condition_gpt: action_gpt3,
    condition_catch_all: action_catch_all,  # This should be the last entry in the dictionary
})


#  This method will be called each time the bot receives an audio file
async def process_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if allowed_user(update):
        my_open_ai.clear_messages()
        if update.message.audio is not None:
            audio_file = update.message.audio
            local_file_path = f"audio_files/{audio_file.file_name}"
            duration = audio_file.duration  # Duration in seconds
            file_size = audio_file.file_size  # Size in bytes
        elif update.message.voice is not None:
            audio_file = update.message.voice
            local_file_path = f"audio_files/{audio_file.file_unique_id}.m4a"
            duration = audio_file.duration
            file_size = audio_file.file_size
        else:
            raise Exception("No audio message attached in update as audio or voice")

        # Log file details
        logging.info(f"Processing audio file: {local_file_path}")
        logging.info(f"Duration: {duration} seconds ({duration/60:.2f} minutes)")
        logging.info(f"File size: {file_size/1024/1024:.2f} MB")

        # Check limitations
        if duration > 1800:  # 30 minutes in seconds
            await context.bot.send_message(
                chat_id=update.effective_chat.id, 
                text="⚠️ Audio file exceeds 30 minutes limit. Please send a shorter recording."
            )
            return

        if file_size > 25 * 1024 * 1024:  # 25MB in bytes
            await context.bot.send_message(
                chat_id=update.effective_chat.id, 
                text="⚠️ Audio file exceeds 25MB size limit. Please send a smaller file."
            )
            return

        # Download the audio file

        file = await context.bot.get_file(file_id=audio_file.file_id)
        await file.download_to_drive(local_file_path)  #

        # Send the audio file to the OpenAI API endpoint
        messages: List[str] = transcribe_audio_file(local_file_path)

        # Send each message as a separate message
        for message in messages:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=message)

        single_message: str = " ".join(messages)
        response: str = my_open_ai.answer_message(
            f'Please summarise the following message, keep the original language (if the text is in Spanish, '
            f'perform the summary in Spanish),'
            f'which will likely be spanish or english:"{single_message}" \n Your '
            f'answer should start with "SUMMARY:\n" (in the original language, so it would be "RESUMEN: for Spanish')
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{response}")

        os.remove(local_file_path)


def split_audio_file(file_path: str, max_duration_seconds: int = 1700) -> List[str]:
    """
    Split an audio file into chunks of max_duration_seconds
    Returns list of paths to the chunk files
    """
    audio = AudioSegment.from_file(file_path)
    duration_ms = len(audio)
    chunk_size_ms = max_duration_seconds * 1000  # Convert to milliseconds
    chunks = []
    
    # If file is shorter than max duration, return original
    if duration_ms <= chunk_size_ms:
        return [file_path]
    
    # Split into chunks
    number_of_chunks = math.ceil(duration_ms / chunk_size_ms)
    for i in range(number_of_chunks):
        start_ms = i * chunk_size_ms
        end_ms = min((i + 1) * chunk_size_ms, duration_ms)
        chunk = audio[start_ms:end_ms]
        chunk_path = f"{file_path}_chunk_{i}.mp3"
        chunk.export(chunk_path, format="mp3")
        chunks.append(chunk_path)
    
    return chunks


def run_whisper_bot():
    # The telegram bot manages events to process through handlers:
    # For each handled event group, the relevant function (defined above) will be invoked
    start_command = bot_start("Welcome, I'd love to help with questions to GPT or audio transcriptions")
    start_handler = CommandHandler('start', start_command)
    echo_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), reply)
    audio_handler = MessageHandler(filters.AUDIO | filters.VOICE, process_audio)

    # Run the bot
    logging.info("Starting Whisper/GPT bot")
    run_telegram_bot(os.getenv('TELEGRAM_BOT_TOKEN'), [start_handler, echo_handler, audio_handler])


if __name__ == '__main__':
    run_whisper_bot()
