"""
Notes Formatter Service

Validates and normalizes raw LLM JSON output into the response schema.
Handles wide variation in LLM output formats gracefully.
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


def _safe_list(data: dict[str, Any], key: str) -> list:
    """Extract an optional list field."""
    value = data.get(key)
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        if key == "definitions":
            return [
                {"term": str(term), "definition": str(definition)}
                for term, definition in value.items()
                if str(term).strip() and str(definition).strip()
            ]
        if key in {"topics", "resources", "interview_questions"}:
            return [value]
        return [str(item).strip() for item in value.values() if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _get_text(data: dict[str, Any], key: str, fallback: str = "") -> str:
    """Extract a string field with flexible fallback."""
    value = data.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _coerce_notes_object(raw_data: dict[str, Any]) -> dict[str, Any]:
    """
    Aggressively unwrap and normalize LLM output into a flat notes object.

    Handles many patterns:
      - Already flat: {"title": ..., "summary": ...}
      - Wrapped: {"notes": {"title": ...}}
      - Nested summary: {"summary": {"topic": "...", "key_points": [...]}}
      - Single-key wrapper: {"whatever": {"title": ...}}
    """
    if not isinstance(raw_data, dict):
        raise FormatterError(f"Expected dict from LLM, got {type(raw_data).__name__}")

    # Already a valid flat notes object
    if "title" in raw_data and ("summary" in raw_data or "topics" in raw_data):
        # Make sure summary is a string, not a nested object
        if isinstance(raw_data.get("summary"), dict):
            raw_data["summary"] = _flatten_summary(raw_data["summary"])
        return raw_data

    # Common wrapper keys
    wrapper_keys = (
        "notes", "note", "structured_notes", "lecture_notes",
        "response", "result", "data", "output", "content",
    )
    for key in wrapper_keys:
        nested = raw_data.get(key)
        if isinstance(nested, dict) and ("title" in nested or "summary" in nested):
            logger.debug("Unwrapped LLM notes object from key '%s'", key)
            if isinstance(nested.get("summary"), dict):
                nested["summary"] = _flatten_summary(nested["summary"])
            return nested

    # Handle case where "summary" is a nested object containing the actual notes
    if "summary" in raw_data and isinstance(raw_data["summary"], dict):
        summary_obj = raw_data["summary"]
        # The summary object might contain topic/key_points structure
        result = dict(raw_data)
        result["summary"] = _flatten_summary(summary_obj)
        # Try to extract title from the summary object
        if "title" not in result or not isinstance(result.get("title"), str):
            result["title"] = (
                summary_obj.get("topic", "")
                or summary_obj.get("title", "")
                or summary_obj.get("lecture_title", "")
                or "Lecture Notes"
            )
        return result

    # Single-key dict — unwrap whatever it is
    if len(raw_data) == 1:
        only_value = next(iter(raw_data.values()))
        if isinstance(only_value, dict):
            logger.debug("Unwrapped single-key LLM wrapper")
            if isinstance(only_value.get("summary"), dict):
                only_value["summary"] = _flatten_summary(only_value["summary"])
            return only_value

    # Last resort: try to build a notes object from whatever keys exist
    return raw_data


def _flatten_summary(summary_obj: dict) -> str:
    """Convert a nested summary dict into a readable string."""
    parts = []

    # Try common keys
    for key in ("topic", "title", "lecture_title", "subject"):
        val = summary_obj.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(val.strip())
            break

    for key in ("overview", "description", "content", "text", "main_idea"):
        val = summary_obj.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(val.strip())

    for key in ("key_points", "main_points", "points", "highlights"):
        val = summary_obj.get(key)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, str) and item.strip():
                    parts.append(f"• {item.strip()}")

    if parts:
        return "\n".join(parts)

    # Fallback: just stringify whatever is in there
    try:
        return " ".join(str(v) for v in summary_obj.values() if v)
    except Exception:
        return str(summary_obj)


def _extract_title(data: dict[str, Any]) -> str:
    """Extract title with multiple fallback strategies."""
    # Direct title
    title = data.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()

    # Try lecture_title, topic, subject
    for key in ("lecture_title", "topic", "subject", "heading", "name"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    # Try to get title from summary if it's a dict
    summary = data.get("summary")
    if isinstance(summary, dict):
        for key in ("topic", "title", "lecture_title", "subject"):
            val = summary.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()

    # Try first topic title
    topics = data.get("topics")
    if isinstance(topics, list) and topics:
        first = topics[0]
        if isinstance(first, dict):
            t = first.get("title")
            if isinstance(t, str) and t.strip():
                return f"Lecture: {t.strip()}"

    return "Lecture Notes"


def _extract_summary(data: dict[str, Any]) -> str:
    """Extract summary with multiple fallback strategies."""
    summary = data.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    if isinstance(summary, dict):
        return _flatten_summary(summary)

    # Fallbacks
    for key in ("overview", "description", "abstract", "introduction"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    return "AI-generated lecture notes."


def _parse_topics(raw_topics: list) -> list[Topic]:
    """Parse raw topic dicts into Topic models."""
    topics = []
    for item in raw_topics:
        if isinstance(item, dict):
            title = item.get("title")
            content = item.get("content", "") or item.get("description", "") or item.get("explanation", "")
            if not isinstance(title, str) or not title.strip():
                continue
            if not isinstance(content, str):
                content = str(content) if content else ""
            subtopics = item.get("subtopics")
            if isinstance(subtopics, list):
                subtopics = [str(subtopic).strip() for subtopic in subtopics if str(subtopic).strip()]
            else:
                subtopics = None
            topics.append(
                Topic(
                    title=title.strip(),
                    content=content.strip(),
                    subtopics=subtopics,
                )
            )
        elif isinstance(item, str) and item.strip():
            topics.append(Topic(title=item.strip(), content=""))
    return topics


def _parse_definitions(raw_defs: list) -> list[Definition]:
    """Parse raw definition dicts."""
    definitions = []
    for item in raw_defs:
        if isinstance(item, str) and ":" in item:
            term, definition = item.split(":", 1)
            if term.strip() and definition.strip():
                definitions.append(
                    Definition(term=term.strip(), definition=definition.strip())
                )
            continue
        if not isinstance(item, dict):
            continue
        term = item.get("term")
        definition = item.get("definition")
        if term is None and len(item) == 1:
            term, definition = next(iter(item.items()))
        if not isinstance(term, str) or not term.strip():
            term = str(term) if term is not None else ""
        if not term.strip():
            continue
        if not isinstance(definition, str) or not definition.strip():
            definition = str(definition) if definition is not None else ""
        if not definition.strip():
            continue
        definitions.append(
            Definition(term=term.strip(), definition=definition.strip())
        )
    return definitions


def _parse_interview_questions(raw_qs: list) -> list[InterviewQuestion]:
    """Parse interview question dicts or strings."""
    questions = []
    for item in raw_qs:
        if isinstance(item, dict):
            question = item.get("question")
            answer = item.get("suggested_answer", "") or item.get("answer", "")
            if not isinstance(question, str) or not question.strip():
                continue
            if not isinstance(answer, str):
                answer = ""
            questions.append(
                InterviewQuestion(
                    question=question.strip(),
                    suggested_answer=answer.strip(),
                )
            )
        elif isinstance(item, str) and item.strip():
            questions.append(
                InterviewQuestion(question=item.strip(), suggested_answer="")
            )
    return questions


def _parse_resources(raw_resources: list) -> list[Resource]:
    """Parse resource dicts or strings."""
    resources = []
    for item in raw_resources:
        if isinstance(item, dict):
            title = item.get("title")
            if not isinstance(title, str) or not title.strip():
                continue
            link = item.get("link") or item.get("url")
            if link is not None and not isinstance(link, str):
                link = str(link)
            resources.append(Resource(title=title.strip(), link=link))
        elif isinstance(item, str) and item.strip():
            resources.append(Resource(title=item.strip()))
    return resources


def _string_list(data: dict[str, Any], key: str) -> list[str]:
    """Normalize optional list values into non-empty strings."""
    return [str(item).strip() for item in _safe_list(data, key) if str(item).strip()]


def format_notes(raw_data: dict[str, Any]) -> GenerateNotesResponse:
    """
    Transform raw LLM JSON into a validated GenerateNotesResponse.

    Much more resilient to LLM output variation than before:
    - Handles nested/wrapped structures
    - Falls back gracefully for title/summary
    - Never fails on missing optional fields
    """
    if not isinstance(raw_data, dict):
        raise FormatterError(
            f"Expected dict from LLM, got {type(raw_data).__name__}"
        )

    raw_data = _coerce_notes_object(raw_data)
    logger.debug("Formatting LLM notes object with keys=%s", sorted(raw_data.keys()))

    # Extract required fields with robust fallbacks
    title = _extract_title(raw_data)
    summary = _extract_summary(raw_data)

    try:
        response = GenerateNotesResponse(
            title=title,
            summary=summary,
            topics=_parse_topics(_safe_list(raw_data, "topics")),
            definitions=_parse_definitions(_safe_list(raw_data, "definitions")),
            formulas=_string_list(raw_data, "formulas"),
            examples=_string_list(raw_data, "examples"),
            key_takeaways=_string_list(raw_data, "key_takeaways"),
            interview_questions=_parse_interview_questions(
                _safe_list(raw_data, "interview_questions")
            ),
            resources=_parse_resources(_safe_list(raw_data, "resources")),
        )
    except FormatterError:
        raise
    except Exception as e:
        raise FormatterError(f"Failed to format LLM output: {e}") from e

    logger.info(
        "Formatted notes - title=%r, summary_chars=%d, topics=%d, "
        "definitions=%d, formulas=%d, examples=%d, takeaways=%d, "
        "interview_questions=%d, resources=%d",
        response.title,
        len(response.summary),
        len(response.topics),
        len(response.definitions),
        len(response.formulas),
        len(response.examples),
        len(response.key_takeaways),
        len(response.interview_questions),
        len(response.resources),
    )

    return response
