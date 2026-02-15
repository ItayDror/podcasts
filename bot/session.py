import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


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
        """Load session from disk, or create a new empty one."""
        path = self._session_path(user_id)
        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)
            # Filter to only known Session fields to handle schema changes
            valid_fields = {f.name for f in Session.__dataclass_fields__.values()}
            filtered = {k: v for k, v in data.items() if k in valid_fields}
            return Session(**filtered)
        return Session(user_id=user_id, created_at=datetime.now().isoformat())

    def save(self, session: Session) -> None:
        """Persist session to disk as JSON."""
        session.updated_at = datetime.now().isoformat()
        path = self._session_path(session.user_id)
        with open(path, "w") as f:
            json.dump(asdict(session), f, indent=2)

    def clear(self, user_id: int) -> None:
        """Delete session file (start fresh)."""
        path = self._session_path(user_id)
        if os.path.exists(path):
            os.remove(path)
