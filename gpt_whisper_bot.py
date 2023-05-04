import os
import logging
from typing import List
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import filters, MessageHandler, ContextTypes, CommandHandler
from adapters.gpt_adapter import OpenAI
from adapters.whisper_adapter import transcribe_audio_file
from bot.bot_actions import action_ping
from bot.bot_common import allowed_user, bot_start, run_telegram_bot, reply_builder
from bot.bot_handler_factory import first_chars_lower_factory

load_dotenv()  # Python module to load environment variables from a .env file

my_open_ai = OpenAI()  # OpenAI is a custom class that works as a wrapper/adapter for OpenAI's GPT API


async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if allowed_user(update):
        logging.info(f"Replying message from verified user")
        received_message_text = update.message.text
        if received_message_text == 'ping':
            await context.bot.send_message(chat_id=update.effective_chat.id, text="pong")
        elif received_message_text[:4].lower() == "gpt4":
            response = my_open_ai.answer_message(received_message_text[4:], model="gpt-4")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=response)
        elif received_message_text[:3].lower() == "gpt":
            response = my_open_ai.answer_message(received_message_text[4:])
            await context.bot.send_message(chat_id=update.effective_chat.id, text=response)
        else:
            # reply with welcome message
            await update.message.reply_text("I don't know how to answer to that")



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
        logging.info(f"Transcribing audio file from verified user")
        audio_file = update.message.audio  # Access the audio file

        # Download the audio file
        local_file_path = f"audio_files/{audio_file.file_name}"
        file = await context.bot.get_file(file_id=audio_file.file_id)
        await file.download_to_drive(local_file_path)  #

        # Send the audio file to the OpenAI API endpoint
        messages: List[str] = transcribe_audio_file(local_file_path)

        # Send each message as a separate message
        for message in messages:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=message)

        single_message: str = " ".join(messages)
        response: str = my_open_ai.answer_message(
            f'Please summarise the following message, keep the original language (if the text is in Spanish, perform the summary in Spanish), '
            f'which will likely be spanish or english:"{single_message}" \n Your '
            f'answer should start with "SUMMARY:\n" (in the original language, so it would be "RESUMEN: for Spanish')
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{response}")

        os.remove(local_file_path)

def run_whisper_bot():

    # The telegram bot manages events to process through handlers:
    # For each handled event group, the relevant function (defined above) will be invoked
    start_command = bot_start("Welcome, I'd love to help with questions to GPT or audio transcriptions")
    start_handler = CommandHandler('start', start_command)
    echo_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), reply)
    audio_handler = MessageHandler(filters.AUDIO, process_audio)

    run_telegram_bot(os.getenv('TELEGRAM_BOT_TOKEN'), [start_handler, echo_handler, audio_handler])


if __name__ == '__main__':
    run_whisper_bot()
