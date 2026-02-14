import logging
import os
import re
from dataclasses import dataclass
from typing import Optional

from bot.quality_check import check_transcript_quality

logger = logging.getLogger(__name__)


@dataclass
class TranscriptResult:
    text: str
    language: str
    source: str  # "youtube_captions" | "whisper"
    quality_score: float
    title: Optional[str] = None
    duration: Optional[float] = None


def _extract_youtube_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
        r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def _fetch_youtube_captions(video_id: str) -> Optional[tuple[str, str]]:
    """
    Try to fetch YouTube captions using youtube-transcript-api.
    Returns (text, language) or None if unavailable.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api.formatters import TextFormatter

        ytt_api = YouTubeTranscriptApi()
        transcript_data = ytt_api.fetch(video_id)

        # Join all text segments
        text = " ".join(entry.text for entry in transcript_data)
        # Try to get language from the snippet (default to "en")
        language = "en"

        return text, language
    except Exception as e:
        logger.info(f"YouTube captions not available for {video_id}: {e}")
        return None


class TranscriptFetcher:
    """
    Fetches transcripts using a waterfall strategy:
    1. YouTube URL? → Try youtube-transcript-api (free, instant)
    2. Quality check on YouTube captions
    3. Fall back to faster-whisper if captions unavailable or poor quality
    """

    def __init__(self, whisper_model_size: str = "base", temp_dir: str = "temp"):
        self._whisper_model_size = whisper_model_size
        self._temp_dir = temp_dir
        self._whisper_model = None  # Lazy-loaded

    def _get_whisper_model(self):
        """Lazy-load the faster-whisper model (heavy, only when needed)."""
        if self._whisper_model is None:
            from faster_whisper import WhisperModel

            logger.info(
                f"Loading faster-whisper {self._whisper_model_size} model..."
            )
            self._whisper_model = WhisperModel(
                self._whisper_model_size,
                device="cpu",
                compute_type="int8",
            )
            logger.info("Whisper model loaded.")
        return self._whisper_model

    def fetch(
        self,
        url: str,
        expected_duration: Optional[float] = None,
        quality_threshold: float = 0.7,
        status_callback=None,
    ) -> TranscriptResult:
        """
        Fetch transcript for the given URL.

        Args:
            url: Podcast/video URL
            expected_duration: Expected duration in seconds (for quality check)
            quality_threshold: Minimum quality score to accept YouTube captions
            status_callback: Optional callable(str) for progress updates

        Returns:
            TranscriptResult with transcript text and metadata
        """
        video_id = _extract_youtube_video_id(url)

        # Step 1: Try YouTube captions if applicable
        if video_id:
            if status_callback:
                status_callback("Checking for YouTube captions...")

            result = _fetch_youtube_captions(video_id)
            if result:
                text, language = result
                quality = check_transcript_quality(
                    text, expected_duration, quality_threshold
                )

                if quality.passed:
                    logger.info(
                        f"YouTube captions accepted (score: {quality.score})"
                    )
                    return TranscriptResult(
                        text=text,
                        language=language,
                        source="youtube_captions",
                        quality_score=quality.score,
                    )
                else:
                    logger.info(
                        f"YouTube captions quality too low "
                        f"(score: {quality.score}, issues: {quality.issues}). "
                        f"Falling back to Whisper."
                    )
                    if status_callback:
                        status_callback(
                            f"YouTube captions quality too low "
                            f"(score: {quality.score:.0%}). "
                            f"Falling back to Whisper transcription..."
                        )

        # Step 2: Download audio and transcribe with faster-whisper
        if status_callback:
            status_callback("Downloading audio...")

        from downloader import PodcastDownloader

        downloader = PodcastDownloader(output_dir=self._temp_dir)
        audio_file, title, duration, file_size_mb = downloader.download_audio(url)

        try:
            if status_callback:
                duration_min = duration / 60 if duration else 0
                status_callback(
                    f"Downloaded: {title}\n"
                    f"Duration: {duration_min:.0f} min | Size: {file_size_mb:.1f} MB\n\n"
                    f"Transcribing with Whisper ({self._whisper_model_size} model)... "
                    f"This may take a while."
                )

            model = self._get_whisper_model()
            segments, info = model.transcribe(audio_file)

            # Collect all segment texts
            text_parts = []
            for segment in segments:
                text_parts.append(segment.text.strip())
            text = " ".join(text_parts)

            quality = check_transcript_quality(text, duration)

            return TranscriptResult(
                text=text,
                language=info.language,
                source="whisper",
                quality_score=quality.score,
                title=title,
                duration=duration,
            )
        finally:
            downloader.cleanup(audio_file)
