"""
NoteForge Pydantic Models

Request/Response schemas for the notes generation API.
Strict validation ensures clean data flow throughout the system.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl


# ── Request Models ───────────────────────────────────────────────


class GenerateNotesRequest(BaseModel):
    """Incoming request to generate notes from a YouTube lecture."""

    youtube_url: str = Field(
        ...,
        min_length=10,
        description="Full YouTube video URL",
        examples=["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
    )
    language: Optional[str] = Field(
        default=None,
        description="Preferred transcript language code (e.g. 'en', 'es', 'hi'). Auto-detected if not specified.",
        examples=["en", "es", "hi", "fr"],
    )


# ── Response Models ──────────────────────────────────────────────


class Topic(BaseModel):
    """A single topic extracted from the lecture."""

    title: str = Field(..., description="Topic heading")
    content: str = Field(..., description="Detailed explanation of the topic")
    subtopics: Optional[List[str]] = Field(
        default=None, description="Breakdown of subtopics"
    )


class Definition(BaseModel):
    """A key term and its definition."""

    term: str
    definition: str


class InterviewQuestion(BaseModel):
    """Interview-style question derived from lecture content."""

    question: str
    suggested_answer: str


class Resource(BaseModel):
    """Recommended learning resource."""

    title: str
    link: Optional[str] = Field(
        default=None, description="URL to the resource (if available)"
    )


class GenerateNotesResponse(BaseModel):
    """Structured notes returned to the client."""

    title: str = Field(..., description="Lecture title")
    summary: str = Field(..., description="Concise lecture summary")
    topics: List[Topic] = Field(
        default_factory=list, description="Main topics covered"
    )
    definitions: List[Definition] = Field(
        default_factory=list, description="Key terms and definitions"
    )
    formulas: List[str] = Field(
        default_factory=list,
        description="Important formulas mentioned in the lecture",
    )
    examples: List[str] = Field(
        default_factory=list,
        description="Real-world examples from the lecture",
    )
    key_takeaways: List[str] = Field(
        default_factory=list, description="Critical points to remember"
    )
    interview_questions: List[InterviewQuestion] = Field(
        default_factory=list,
        description="Interview questions based on lecture content",
    )
    resources: List[Resource] = Field(
        default_factory=list,
        description="Recommended learning resources",
    )


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str
    ollama_status: str


class SavedNoteMetadata(BaseModel):
    """Lightweight metadata for sidebar listing."""

    id: str
    video_id: str
    youtube_url: str
    title: str
    created_at: str


class SavedNoteResponse(GenerateNotesResponse):
    """Full note with persistence metadata."""

    id: str
    video_id: str
    youtube_url: str
    created_at: str


class ErrorResponse(BaseModel):
    """Standardized error response."""

    error: str
    detail: Optional[str] = None


# ── Batch Processing Models ──────────────────────────────────────


class BatchGenerateRequest(BaseModel):
    """Request to generate notes for multiple YouTube URLs."""

    youtube_urls: List[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="List of YouTube URLs (max 10)",
    )
    language: Optional[str] = Field(
        default=None,
        description="Preferred transcript language code for all videos",
    )


class BatchItemResult(BaseModel):
    """Result for a single URL in a batch."""

    youtube_url: str
    status: Literal["success", "error"]
    note: Optional[SavedNoteResponse] = None
    error: Optional[str] = None


class BatchGenerateResponse(BaseModel):
    """Response from batch note generation."""

    total: int
    succeeded: int
    failed: int
    results: List[BatchItemResult]


# ── Quiz Models ──────────────────────────────────────────────────


class QuizQuestion(BaseModel):
    """A single multiple-choice quiz question."""

    question: str
    options: List[str] = Field(..., min_length=4, max_length=4)
    correct_index: int = Field(..., ge=0, le=3)
    explanation: str


class QuizResponse(BaseModel):
    """Quiz generated from a saved note."""

    note_id: str
    note_title: str
    questions: List[QuizQuestion]
