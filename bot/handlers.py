import asyncio
import logging
from datetime import date

from telegram import Update
from telegram.constants import ParseMode, ChatAction
from telegram.ext import ContextTypes

from bot.config import Config
from bot.session import SessionManager
from bot.transcript_fetcher import TranscriptFetcher
from bot.llm import LLMClient
from bot.supabase_client import SupabaseClient, PodcastEntry
from bot.message_utils import (
    send_long_message,
    send_as_file,
    format_insights_for_telegram,
)

logger = logging.getLogger(__name__)


class BotHandlers:
    def __init__(
        self,
        config: Config,
        session_manager: SessionManager,
        transcript_fetcher: TranscriptFetcher,
        llm_client: LLMClient,
        supabase_client: SupabaseClient,
    ):
        self.config = config
        self.sessions = session_manager
        self.fetcher = transcript_fetcher
        self.llm = llm_client
        self.supabase = supabase_client
        self._chat_mode_users: set[int] = set()

    def _is_authorized(self, update: Update) -> bool:
        return update.effective_user.id == self.config.allowed_user_id

    async def _require_auth(self, update: Update) -> bool:
        if not self._is_authorized(update):
            await update.message.reply_text("Unauthorized. This bot is private.")
            return False
        return True

    # === /start ===
    async def start_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        if not await self._require_auth(update):
            return
        await update.message.reply_text(
            "Podcast Transcriber Bot\n\n"
            "Commands:\n"
            "/transcribe <url> - Download and transcribe a podcast\n"
            "/insights - Generate insights from the last transcript\n"
            "/chat - Discuss the episode with AI\n"
            "/done - Exit chat mode\n"
            "/upload - Push insights to your tracker\n"
            "/status - Show current session\n"
            "/clear - Start a fresh session"
        )

    # === /transcribe <url> ===
    async def transcribe_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        if not await self._require_auth(update):
            return

        if not context.args:
            await update.message.reply_text(
                "Please provide a URL.\nUsage: /transcribe <url>"
            )
            return

        url = context.args[0]
        user_id = update.effective_user.id
        session = self.sessions.load(user_id)

        # Send status updates via callback
        status_message = await update.message.reply_text("Starting transcription...")

        async def status_callback(text: str):
            try:
                await status_message.edit_text(text)
            except Exception:
                pass  # Ignore edit failures (message unchanged, etc.)

        # Show typing indicator
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action=ChatAction.TYPING
        )

        # Run the (blocking) fetch in a thread to keep the bot responsive
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: self.fetcher.fetch(
                    url=url,
                    expected_duration=None,  # We don't know duration yet for YT captions
                    quality_threshold=self.config.quality_threshold,
                    status_callback=lambda msg: asyncio.run_coroutine_threadsafe(
                        status_callback(msg), loop
                    ),
                ),
            )
        except Exception as e:
            await update.message.reply_text(f"Transcription failed: {e}")
            return

        # Update session
        session.podcast_title = result.title or _title_from_url(url)
        session.podcast_url = url
        session.podcast_duration = result.duration
        session.transcript_text = result.text
        session.transcript_language = result.language
        session.transcript_source = result.source
        session.state = "has_transcript"
        session.insights = None
        session.conversation_history = []
        self.sessions.save(session)

        # Report result
        source_label = (
            "YouTube captions (instant)"
            if result.source == "youtube_captions"
            else f"Whisper ({self.config.whisper_model_size} model)"
        )
        char_count = len(result.text)
        await update.message.reply_text(
            f"Transcription complete!\n\n"
            f"Source: {source_label}\n"
            f"Quality: {result.quality_score:.0%}\n"
            f"Language: {result.language}\n"
            f"Length: {char_count:,} characters\n\n"
            f"Use /insights to generate insights, or /chat to discuss."
        )

        # Send transcript as file
        filename = f"{session.podcast_title or 'transcript'}.md"
        await send_as_file(update, context, result.text, filename)

    # === /insights ===
    async def insights_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        if not await self._require_auth(update):
            return

        session = self.sessions.load(update.effective_user.id)
        if not session.transcript_text:
            await update.message.reply_text(
                "No transcript loaded. Use /transcribe <url> first."
            )
            return

        await update.message.reply_text(
            "Generating insights... (this takes ~30 seconds)"
        )
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action=ChatAction.TYPING
        )

        loop = asyncio.get_event_loop()
        try:
            insights = await loop.run_in_executor(
                None,
                lambda: self.llm.generate_insights(
                    title=session.podcast_title or "Unknown",
                    transcript=session.transcript_text,
                ),
            )
        except Exception as e:
            await update.message.reply_text(
                f"Failed to generate insights: {e}\n\nPlease try again."
            )
            return

        session.insights = insights
        session.state = "has_insights"
        self.sessions.save(session)

        formatted = format_insights_for_telegram(insights)
        await send_long_message(
            update, context, formatted, parse_mode=ParseMode.HTML
        )
        await update.message.reply_text(
            "Use /chat to refine, or /upload when you're happy."
        )

    # === /chat ===
    async def chat_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        if not await self._require_auth(update):
            return

        session = self.sessions.load(update.effective_user.id)
        if not session.transcript_text:
            await update.message.reply_text(
                "No transcript loaded. Use /transcribe first."
            )
            return

        self._chat_mode_users.add(update.effective_user.id)
        session.state = "chatting"
        self.sessions.save(session)

        await update.message.reply_text(
            "Chat mode activated. Send me any message to discuss the episode.\n"
            "Use /done to exit chat mode."
        )

    # === Plain text messages (chat mode) ===
    async def chat_message_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        if not await self._require_auth(update):
            return

        user_id = update.effective_user.id
        if user_id not in self._chat_mode_users:
            await update.message.reply_text(
                "Send a command to get started. Use /start to see options."
            )
            return

        session = self.sessions.load(user_id)
        user_message = update.message.text

        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action=ChatAction.TYPING
        )

        loop = asyncio.get_event_loop()
        try:
            response_text, updated_history = await loop.run_in_executor(
                None,
                lambda: self.llm.chat(
                    title=session.podcast_title or "Unknown",
                    insights=session.insights or "No insights generated yet.",
                    transcript=session.transcript_text,
                    conversation_history=session.conversation_history,
                    user_message=user_message,
                ),
            )
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")
            return

        session.conversation_history = updated_history
        self.sessions.save(session)

        await send_long_message(update, context, response_text)

    # === /done ===
    async def done_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        if not await self._require_auth(update):
            return
        user_id = update.effective_user.id
        self._chat_mode_users.discard(user_id)
        session = self.sessions.load(user_id)
        if session.insights:
            session.state = "has_insights"
        elif session.transcript_text:
            session.state = "has_transcript"
        else:
            session.state = "idle"
        self.sessions.save(session)
        await update.message.reply_text("Exited chat mode.")

    # === /upload ===
    async def upload_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        if not await self._require_auth(update):
            return

        session = self.sessions.load(update.effective_user.id)

        # If user provided text after /upload, use that as insights
        custom_text = " ".join(context.args) if context.args else None
        insights = custom_text or session.insights

        if not insights:
            await update.message.reply_text(
                "No insights to upload.\n\n"
                "Either:\n"
                "• /insights - Generate with AI first\n"
                "• /upload Your custom text here..."
            )
            return

        # Update session with custom insights if provided
        if custom_text:
            session.insights = custom_text
            self.sessions.save(session)

        await update.message.reply_text("Uploading to Podcast Tracker...")

        try:
            entry = PodcastEntry(
                title=session.podcast_title or "Unknown",
                date=date.today().isoformat(),
                insight=session.insights,
                link=session.podcast_url,
            )
            result = self.supabase.create_entry(entry)
        except Exception as e:
            await update.message.reply_text(f"Upload failed: {e}")
            return

        await update.message.reply_text(
            f"Uploaded successfully!\nTitle: {session.podcast_title}"
        )

    # === /status ===
    async def status_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        if not await self._require_auth(update):
            return

        session = self.sessions.load(update.effective_user.id)
        in_chat = update.effective_user.id in self._chat_mode_users

        lines = ["<b>Session Status</b>", ""]
        lines.append(f"State: {session.state}")
        if session.podcast_title:
            lines.append(f"Podcast: {session.podcast_title}")
        if session.podcast_url:
            lines.append(f"URL: {session.podcast_url}")
        if session.transcript_text:
            lines.append(f"Transcript: {len(session.transcript_text):,} chars")
            lines.append(f"Source: {session.transcript_source or 'unknown'}")
        lines.append(f"Insights: {'Yes' if session.insights else 'No'}")
        lines.append(f"Chat mode: {'Active' if in_chat else 'Off'}")
        lines.append(f"Chat messages: {len(session.conversation_history)}")

        await update.message.reply_text(
            "\n".join(lines), parse_mode=ParseMode.HTML
        )

    # === /clear ===
    async def clear_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        if not await self._require_auth(update):
            return
        user_id = update.effective_user.id
        self.sessions.clear(user_id)
        self._chat_mode_users.discard(user_id)
        await update.message.reply_text("Session cleared. Ready for a new episode.")


def _title_from_url(url: str) -> str:
    """Extract a readable title from a URL as fallback."""
    # Strip protocol and www
    title = url.split("//")[-1].split("www.")[-1]
    # Take the domain + first path segment
    parts = title.split("/")
    return parts[0] if parts else url
