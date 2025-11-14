import logging
import os
from datetime import datetime
from typing import List

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import filters, MessageHandler, ContextTypes, CommandHandler

from adapters.gpt_adapter import OpenAI
from adapters.notion_adapter import NotionAdapter
from adapters.whisper_adapter import transcribe_audio_file
from bot.bot_actions import action_ping
from bot.bot_common import allowed_user, bot_start, run_telegram_bot, reply_builder
from bot.bot_conditions import first_chars_lower_factory, condition_ping, \
    condition_catch_all

load_dotenv()  # Python module to load environment variables from a .env file

my_open_ai = OpenAI()  # OpenAI is a custom class that works as a wrapper/adapter for OpenAI's GPT API
my_notion = NotionAdapter(os.getenv("NOTION_TOKEN"))  # Notion adapter for storing transcripts and summaries

condition_gpt4 = first_chars_lower_factory(4, 'gpt4')
condition_gpt = first_chars_lower_factory(3, 'gpt')


def _format_transcript_for_notion(transcript: str, metadata: dict, timestamp: datetime) -> str:
    """Format transcript with metadata for Notion storage."""
    duration_str = f"{metadata.get('duration', 'Unknown')}s" if metadata.get('duration') else "Unknown"
    file_size_str = f"{metadata.get('file_size', 'Unknown')} bytes" if metadata.get('file_size') else "Unknown"
    
    content = f"🎵 Audio Transcription - {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    content += f"📊 Metadata:\n"
    content += f"• Type: {metadata.get('audio_type', 'Unknown')}\n"
    content += f"• Duration: {duration_str}\n"
    content += f"• File size: {file_size_str}\n"
    
    if metadata.get('file_name'):
        content += f"• File name: {metadata.get('file_name')}\n"
    if metadata.get('mime_type'):
        content += f"• MIME type: {metadata.get('mime_type')}\n"
    if metadata.get('performer'):
        content += f"• Performer: {metadata.get('performer')}\n"
    if metadata.get('title'):
        content += f"• Title: {metadata.get('title')}\n"
    
    content += f"\n📝 Transcription:\n{transcript}"
    return content


def _format_summary_for_notion(summary: str, metadata: dict, timestamp: datetime) -> str:
    """Format summary with metadata for Notion storage."""
    duration_str = f"{metadata.get('duration', 'Unknown')}s" if metadata.get('duration') else "Unknown"
    file_size_str = f"{metadata.get('file_size', 'Unknown')} bytes" if metadata.get('file_size') else "Unknown"
    
    content = f"📋 Audio Summary - {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    content += f"📊 Metadata:\n"
    content += f"• Type: {metadata.get('audio_type', 'Unknown')}\n"
    content += f"• Duration: {duration_str}\n"
    content += f"• File size: {file_size_str}\n"
    
    if metadata.get('file_name'):
        content += f"• File name: {metadata.get('file_name')}\n"
    
    content += f"\n📄 Summary:\n{summary}"
    return content


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
        
        # Collect metadata from audio message
        timestamp = datetime.now()
        audio_metadata = {}
        
        # Acknowledge the audio message so the user knows we're working on it
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Audio received, starting transcription...",
        )
        
        if update.message.audio is not None:
            audio_file = update.message.audio  # Access the audio file
            local_file_path = f"audio_files/{audio_file.file_name}"
            audio_metadata = {
                "duration": getattr(audio_file, 'duration', None),
                "file_size": getattr(audio_file, 'file_size', None),
                "file_name": getattr(audio_file, 'file_name', None),
                "mime_type": getattr(audio_file, 'mime_type', None),
                "performer": getattr(audio_file, 'performer', None),
                "title": getattr(audio_file, 'title', None),
                "audio_type": "audio"
            }
        elif update.message.voice is not None:
            audio_file = update.message.voice
            local_file_path = f"audio_files/{audio_file.file_unique_id}.m4a"
            audio_metadata = {
                "duration": getattr(audio_file, 'duration', None),
                "file_size": getattr(audio_file, 'file_size', None),
                "file_name": f"{audio_file.file_unique_id}.m4a",
                "mime_type": getattr(audio_file, 'mime_type', None),
                "audio_type": "voice"
            }
        else:
            raise Exception("No audio message attached in update as audio or voice")

        logging.info(f"Audio metadata collected: {audio_metadata}")

        # Download the audio file
        file = await context.bot.get_file(file_id=audio_file.file_id)
        await file.download_to_drive(local_file_path)

        # Send the audio file to the OpenAI API endpoint
        try:
            messages: List[str] = transcribe_audio_file(local_file_path)
            logging.info(f"Transcription completed successfully, {len(messages)} message segments")
        except Exception as exc:
            logging.error(f"Transcription failed: {exc}")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=str(exc))
            os.remove(local_file_path)
            return

        # Send each message as a separate message
        for message in messages:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=message)

        single_message: str = " ".join(messages)
        
        # Store transcription in Notion
        try:
            transcript_content = _format_transcript_for_notion(single_message, audio_metadata, timestamp)
            transcript_page_id = os.getenv("NOTION_TRANSCRIPT_PAGE_ID")
            if transcript_page_id:
                my_notion.add_block(
                    parent_id=transcript_page_id,
                    text=transcript_content,
                    block_type="paragraph",
                    date=timestamp
                )
                logging.info("✅ Transcript successfully stored in Notion")
            else:
                logging.warning("⚠️ NOTION_TRANSCRIPT_PAGE_ID not configured, skipping transcript storage")
        except Exception as e:
            logging.error(f"❌ Failed to store transcript in Notion: {e}")
            # Continue with summary generation despite Notion error

        # Generate summary
        summary_prompt = (
            "Please summarise the following message, keep the original language "
            "(if the text is in Spanish, perform the summary in Spanish). "
            f'It will likely be Spanish or English: "{single_message}"\n'
            'Your answer should start with "SUMMARY:" '
            '(use "RESUMEN:" if the language is Spanish).'
        )
        
        try:
            response: str = my_open_ai.answer_message(summary_prompt)
            logging.info("Summary generated successfully")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{response}")
        except Exception as exc:
            logging.error(f"Summary generation failed: {exc}")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Summary generation failed: {exc}")
            os.remove(local_file_path)
            return

        # Store summary in Notion
        try:
            summary_content = _format_summary_for_notion(response, audio_metadata, timestamp)
            summary_page_id = os.getenv("NOTION_SUMMARY_PAGE_ID")
            if summary_page_id:
                my_notion.add_block(
                    parent_id=summary_page_id,
                    text=summary_content,
                    block_type="paragraph",
                    date=timestamp
                )
                logging.info("✅ Summary successfully stored in Notion")
            else:
                logging.warning("⚠️ NOTION_SUMMARY_PAGE_ID not configured, skipping summary storage")
        except Exception as e:
            logging.error(f"❌ Failed to store summary in Notion: {e}")
            # Continue despite Notion error

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
