import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    # Telegram
    telegram_bot_token: str
    allowed_user_id: int

    # Whisper (local faster-whisper)
    whisper_model_size: str

    # LLM (Claude)
    anthropic_api_key: str

    # Supabase
    supabase_endpoint: str
    supabase_api_key: str

    # Transcript quality
    quality_threshold: float

    # Paths
    temp_dir: str
    transcripts_dir: str
    sessions_dir: str


def load_config() -> Config:
    """Load config from env vars. Raises ValueError for missing required vars."""
    return Config(
        telegram_bot_token=_require("TELEGRAM_BOT_TOKEN"),
        allowed_user_id=int(_require("ALLOWED_USER_ID")),
        whisper_model_size=os.getenv("WHISPER_MODEL_SIZE", "base"),
        anthropic_api_key=_require("ANTHROPIC_API_KEY"),
        supabase_endpoint=os.getenv(
            "SUPABASE_ENDPOINT",
            "https://oorvkgosblwmjwfbfszo.supabase.co/functions/v1/podcasts-api",
        ),
        supabase_api_key=_require("SUPABASE_API_KEY"),
        quality_threshold=float(os.getenv("QUALITY_THRESHOLD", "0.7")),
        temp_dir=os.getenv("TEMP_DIR", "temp"),
        transcripts_dir=os.getenv("TRANSCRIPTS_DIR", "transcripts"),
        sessions_dir=os.getenv("SESSIONS_DIR", "sessions"),
    )


def _require(var_name: str) -> str:
    val = os.getenv(var_name)
    if not val:
        raise ValueError(f"Missing required environment variable: {var_name}")
    return val
