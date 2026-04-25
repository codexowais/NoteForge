"""
YouTube Transcript Extraction Service

Handles video ID parsing and transcript fetching from YouTube.
Supports multiple URL formats and robust error handling.
Uses youtube-transcript-api v1.x (instance-based API).
"""

import logging
import re
from typing import Optional

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

logger = logging.getLogger(__name__)

# All known YouTube URL patterns
_YOUTUBE_PATTERNS = [
    r"(?:youtube\.com\/watch\?v=)([\w-]{11})",
    r"(?:youtu\.be\/)([\w-]{11})",
    r"(?:youtube\.com\/embed\/)([\w-]{11})",
    r"(?:youtube\.com\/v\/)([\w-]{11})",
    r"(?:youtube\.com\/shorts\/)([\w-]{11})",
]

# Reusable API instance
_yt_api = YouTubeTranscriptApi()


class YouTubeServiceError(Exception):
    """Base exception for YouTube service failures."""
    pass


class InvalidURLError(YouTubeServiceError):
    """Raised when the URL is not a valid YouTube link."""
    pass


class TranscriptUnavailableError(YouTubeServiceError):
    """Raised when no transcript can be retrieved."""
    pass


def extract_video_id(url: str) -> str:
    """
    Extract the 11-character video ID from any YouTube URL format.

    Args:
        url: YouTube video URL in any standard format.

    Returns:
        11-character video ID string.

    Raises:
        InvalidURLError: If no valid video ID can be extracted.
    """
    if not url or not isinstance(url, str):
        raise InvalidURLError("URL must be a non-empty string.")

    url = url.strip()

    for pattern in _YOUTUBE_PATTERNS:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    raise InvalidURLError(
        f"Could not extract video ID from URL: {url}. "
        "Supported formats: youtube.com/watch?v=, youtu.be/, "
        "youtube.com/embed/, youtube.com/shorts/"
    )


def fetch_transcript(
    video_id: str,
    languages: Optional[list[str]] = None,
    language: Optional[str] = None,
) -> str:
    """
    Fetch and join the transcript for a YouTube video.

    Uses youtube-transcript-api v1.x instance-based API.

    Args:
        video_id: 11-character YouTube video ID.
        languages: Preferred transcript languages (defaults to English).
        language: Single language code override (takes priority over languages list).

    Returns:
        Full transcript as a single concatenated string.

    Raises:
        TranscriptUnavailableError: If the transcript cannot be fetched.
    """
    if language:
        languages = [language, "en"] if language != "en" else ["en"]
    elif languages is None:
        languages = ["en"]

    try:
        transcript_list = _yt_api.fetch(video_id, languages=languages)
    except TranscriptsDisabled:
        raise TranscriptUnavailableError(
            f"Transcripts are disabled for video: {video_id}"
        )
    except NoTranscriptFound:
        raise TranscriptUnavailableError(
            f"No transcript found for video {video_id} in languages: {languages}"
        )
    except VideoUnavailable:
        raise TranscriptUnavailableError(
            f"Video is unavailable: {video_id}"
        )
    except Exception as e:
        raise TranscriptUnavailableError(
            f"Unexpected error fetching transcript for {video_id}: {e}"
        )

    if not transcript_list:
        raise TranscriptUnavailableError(
            f"Transcript returned empty for video: {video_id}"
        )

    # Join all segments into a single string
    full_text = " ".join(
        snippet.text.strip()
        for snippet in transcript_list
        if snippet.text.strip()
    )

    if not full_text:
        raise TranscriptUnavailableError(
            f"Transcript segments contained no text for video: {video_id}"
        )

    logger.info(
        "Fetched transcript for %s — %d characters, %d segments",
        video_id,
        len(full_text),
        len(transcript_list),
    )

    return full_text


def get_transcript_from_url(
    url: str,
    language: Optional[str] = None,
) -> tuple[str, str]:
    """
    High-level helper: URL → (video_id, transcript_text).

    Args:
        url: Full YouTube URL.
        language: Optional language code for transcript.

    Returns:
        Tuple of (video_id, transcript_text).

    Raises:
        InvalidURLError: If the URL is invalid.
        TranscriptUnavailableError: If the transcript cannot be fetched.
    """
    video_id = extract_video_id(url)
    transcript = fetch_transcript(video_id, language=language)
    return video_id, transcript
