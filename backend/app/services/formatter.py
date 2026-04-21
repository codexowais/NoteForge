"""
Notes Formatter Service

Validates and normalizes the raw LLM JSON output into
a clean GenerateNotesResponse Pydantic model.

This layer ensures the API always returns a consistent schema,
even if the LLM output is messy or incomplete.
"""

import logging
from typing import Any

from app.models.note import (
    Definition,
    GenerateNotesResponse,
    InterviewQuestion,
    Resource,
    Topic,
)

logger = logging.getLogger(__name__)


class FormatterError(Exception):
    """Raised when LLM output cannot be formatted into the response schema."""

    pass


def _safe_list(data: dict, key: str, default: list | None = None) -> list:
    """Safely extract a list from a dict, returning default if missing or wrong type."""
    value = data.get(key)
    if isinstance(value, list):
        return value
    return default if default is not None else []


def _parse_topics(raw_topics: list) -> list[Topic]:
    """Parse raw topic dicts into Topic models with safe defaults."""
    topics = []
    for item in raw_topics:
        if isinstance(item, dict):
            topics.append(
                Topic(
                    title=item.get("title", "Untitled Topic"),
                    content=item.get("content", ""),
                    subtopics=item.get("subtopics"),
                )
            )
        elif isinstance(item, str):
            topics.append(Topic(title=item, content=""))
    return topics


def _parse_definitions(raw_defs: list) -> list[Definition]:
    """Parse raw definition dicts."""
    definitions = []
    for item in raw_defs:
        if isinstance(item, dict):
            definitions.append(
                Definition(
                    term=item.get("term", "Unknown"),
                    definition=item.get("definition", ""),
                )
            )
    return definitions


def _parse_interview_questions(raw_qs: list) -> list[InterviewQuestion]:
    """Parse interview question dicts."""
    questions = []
    for item in raw_qs:
        if isinstance(item, dict):
            questions.append(
                InterviewQuestion(
                    question=item.get("question", ""),
                    suggested_answer=item.get("suggested_answer", ""),
                )
            )
        elif isinstance(item, str):
            questions.append(
                InterviewQuestion(question=item, suggested_answer="")
            )
    return questions


def _parse_resources(raw_resources: list) -> list[Resource]:
    """Parse resource dicts."""
    resources = []
    for item in raw_resources:
        if isinstance(item, dict):
            resources.append(
                Resource(
                    title=item.get("title", "Resource"),
                    link=item.get("link"),
                )
            )
        elif isinstance(item, str):
            resources.append(Resource(title=item))
    return resources


def format_notes(raw_data: dict[str, Any]) -> GenerateNotesResponse:
    """
    Transform raw LLM JSON into a validated GenerateNotesResponse.

    Handles missing fields, wrong types, and malformed entries gracefully.

    Args:
        raw_data: Parsed JSON dict from the LLM.

    Returns:
        GenerateNotesResponse with all fields normalized.

    Raises:
        FormatterError: If the data is fundamentally unusable.
    """
    if not isinstance(raw_data, dict):
        raise FormatterError(
            f"Expected dict from LLM, got {type(raw_data).__name__}"
        )

    try:
        response = GenerateNotesResponse(
            title=raw_data.get("title", "Untitled Lecture"),
            summary=raw_data.get("summary", "No summary generated."),
            topics=_parse_topics(_safe_list(raw_data, "topics")),
            definitions=_parse_definitions(_safe_list(raw_data, "definitions")),
            formulas=[
                str(f)
                for f in _safe_list(raw_data, "formulas")
                if f
            ],
            examples=[
                str(e)
                for e in _safe_list(raw_data, "examples")
                if e
            ],
            key_takeaways=[
                str(kt)
                for kt in _safe_list(raw_data, "key_takeaways")
                if kt
            ],
            interview_questions=_parse_interview_questions(
                _safe_list(raw_data, "interview_questions")
            ),
            resources=_parse_resources(_safe_list(raw_data, "resources")),
        )

        logger.info(
            "Formatted notes — %d topics, %d definitions, %d formulas, "
            "%d examples, %d takeaways, %d interview Qs, %d resources",
            len(response.topics),
            len(response.definitions),
            len(response.formulas),
            len(response.examples),
            len(response.key_takeaways),
            len(response.interview_questions),
            len(response.resources),
        )

        return response

    except Exception as e:
        raise FormatterError(f"Failed to format LLM output: {e}")
