"""
Resources Service (Placeholder)

Future home of:
- related resource lookup via web scraping
- vector-based resource matching
- integration with external educational APIs

For Phase 1, resources are generated directly by the LLM.
"""

import logging

logger = logging.getLogger(__name__)


async def enrich_resources(notes: dict) -> dict:
    """
    Placeholder for future resource enrichment.

    In later phases, this will:
    - validate resource links
    - add additional curated resources from a knowledge base
    - rank resources by relevance using embeddings

    For now, returns the notes dict unchanged.
    """
    logger.debug("Resource enrichment skipped (Phase 1)")
    return notes
