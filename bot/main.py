import logging
import sys

from dotenv import load_dotenv
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
)

from bot.config import load_config
from bot.session import SessionManager
from bot.transcript_fetcher import TranscriptFetcher
from bot.llm import LLMClient
from bot.supabase_client import SupabaseClient
from bot.handlers import BotHandlers

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main():
    load_dotenv(override=True)

    # Load and validate configuration
    try:
        config = load_config()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    logger.info(f"Whisper model: {config.whisper_model_size}")
    logger.info(f"Allowed user ID: {config.allowed_user_id}")

    # Initialize components
    session_manager = SessionManager(sessions_dir=config.sessions_dir)
    transcript_fetcher = TranscriptFetcher(
        whisper_model_size=config.whisper_model_size,
        temp_dir=config.temp_dir,
    )
    llm_client = LLMClient(api_key=config.anthropic_api_key)
    supabase_client = SupabaseClient(
        endpoint=config.supabase_endpoint,
        api_key=config.supabase_api_key,
    )

    # Initialize handlers
    handlers = BotHandlers(
        config=config,
        session_manager=session_manager,
        transcript_fetcher=transcript_fetcher,
        llm_client=llm_client,
        supabase_client=supabase_client,
    )

    # Build the Telegram application
    app = ApplicationBuilder().token(config.telegram_bot_token).build()

    # Register command handlers
    app.add_handler(CommandHandler("start", handlers.start_handler))
    app.add_handler(CommandHandler("transcribe", handlers.transcribe_handler))
    app.add_handler(CommandHandler("insights", handlers.insights_handler))
    app.add_handler(CommandHandler("chat", handlers.chat_handler))
    app.add_handler(CommandHandler("done", handlers.done_handler))
    app.add_handler(CommandHandler("upload", handlers.upload_handler))
    app.add_handler(CommandHandler("status", handlers.status_handler))
    app.add_handler(CommandHandler("clear", handlers.clear_handler))

    # Plain text handler (for chat mode)
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handlers.chat_message_handler,
        )
    )

    # Start polling
    logger.info("Bot starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
