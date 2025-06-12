import logging
import os
from typing import List

from config import setup
from telegram import Update
from telegram.ext import filters, MessageHandler, ContextTypes, CommandHandler

from adapters.gpt_adapter import OpenAI
from adapters.whisper_adapter import transcribe_audio_file
from bot.bot_actions import action_ping
from bot.bot_common import allowed_user, bot_start, run_telegram_bot, reply_builder
from bot.bot_conditions import first_chars_lower_factory, condition_ping, \
    condition_catch_all

setup()

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
        my_open_ai.clear_messages()  # TODO improve treatment of message history
        logging.info(f"Transcribing audio file from verified user")
        # Acknowledge the audio message so the user knows we're working on it
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Audio received, starting transcription...",
        )
        if update.message.audio is not None:
            audio_file = update.message.audio  # Access the audio file
            local_file_path = f"audio_files/{audio_file.file_name}"
        elif update.message.voice is not None:
            audio_file = update.message.voice
            local_file_path = f"audio_files/{audio_file.file_unique_id}.m4a"
        else:
            raise Exception("No audio message attached in update as audio or voice")

        # Download the audio file

        file = await context.bot.get_file(file_id=audio_file.file_id)
        await file.download_to_drive(local_file_path)  #

        # Send the audio file to the OpenAI API endpoint
        try:
            messages: List[str] = await transcribe_audio_file(local_file_path)
        except Exception as exc:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=str(exc))
            os.remove(local_file_path)
            return

        # Send each message as a separate message
        for message in messages:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=message)

        single_message: str = " ".join(messages)
        summary_prompt = (
            "Please summarise the following message, keep the original language "
            "(if the text is in Spanish, perform the summary in Spanish). "
            f'It will likely be Spanish or English: "{single_message}"\n'
            'Your answer should start with "SUMMARY:" '
            '(use "RESUMEN:" if the language is Spanish).'
        )
        response: str = my_open_ai.answer_message(summary_prompt)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{response}")

        os.remove(local_file_path)


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
