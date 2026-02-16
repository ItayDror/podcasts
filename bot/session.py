import json
import logging
import os
import tempfile
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Session:
    user_id: int
    # Podcast metadata
    podcast_title: Optional[str] = None
    podcast_url: Optional[str] = None
    podcast_duration: Optional[float] = None
    # Transcript
    transcript_text: Optional[str] = None
    transcript_language: Optional[str] = None
    transcript_source: Optional[str] = None  # "youtube_captions" | "whisper"
    # Insights
    insights: Optional[str] = None
    # User notes (quick comments while listening)
    notes: list = field(default_factory=list)
    # Conversation history for /chat mode (list of {role, content} dicts)
    conversation_history: list = field(default_factory=list)
    # State tracking
    state: str = "idle"  # idle | has_transcript | has_insights | chatting
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SessionManager:
    def __init__(self, sessions_dir: str = "sessions"):
        self.sessions_dir = sessions_dir
        os.makedirs(sessions_dir, exist_ok=True)

    def _session_path(self, user_id: int) -> str:
        return os.path.join(self.sessions_dir, f"{user_id}.json")

    def load(self, user_id: int) -> Session:
        """Load session from disk, or create a new empty one.

        If the session file is corrupted (invalid JSON), logs a warning
        and returns a fresh session so the bot stays operational.
        """
        path = self._session_path(user_id)
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                # Filter to only known Session fields to handle schema changes
                valid_fields = {f.name for f in Session.__dataclass_fields__.values()}
                filtered = {k: v for k, v in data.items() if k in valid_fields}
                return Session(**filtered)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.warning(
                    "Corrupted session file for user %s, starting fresh: %s",
                    user_id, e,
                )
        return Session(user_id=user_id, created_at=datetime.now().isoformat())

    def save(self, session: Session) -> None:
        """Persist session to disk as JSON.

        Uses atomic write (write to temp file, then rename) so a crash
        mid-write never leaves a corrupted session file.
        """
        session.updated_at = datetime.now().isoformat()
        path = self._session_path(session.user_id)
        # Write to a temp file in the same directory, then atomically rename.
        fd, tmp_path = tempfile.mkstemp(dir=self.sessions_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(asdict(session), f, indent=2)
            os.replace(tmp_path, path)  # atomic on POSIX
        except BaseException:
            # Clean up the temp file if anything goes wrong
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def clear(self, user_id: int) -> None:
        """Delete session file (start fresh)."""
        path = self._session_path(user_id)
        if os.path.exists(path):
            os.remove(path)
