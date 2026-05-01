"""Text chunking for document processing pipeline."""

import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Defaults aligned with text-embedding-ada-002 (8191 token limit, ~4 chars/token)
DEFAULT_CHUNK_SIZE = 1000  # characters
DEFAULT_CHUNK_OVERLAP = 200  # characters


def content_hash(text: str) -> str:
    """Generate a short deterministic hash from text content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def chunk_id(doc_id: str, chunk_index: int, chunk_text: str) -> str:
    """Generate a deterministic chunk ID based on doc ID and content hash.
    Same content always produces the same ID — safe for upserts."""
    return f"{doc_id}_c{chunk_index}_{content_hash(chunk_text)}"


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Split text into overlapping chunks by paragraph boundaries.

    Tries to split at paragraph/sentence boundaries for better context.
    Falls back to character-level splitting for very long paragraphs.
    """
    if not text or not text.strip():
        return []

    # If text fits in a single chunk, return as-is
    if len(text) <= chunk_size:
        return [text.strip()]

    # Split by paragraphs first
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: list[str] = []
    current_chunk = ""

    for para in paragraphs:
        # If adding this paragraph exceeds chunk size, finalize current chunk
        if current_chunk and len(current_chunk) + len(para) + 2 > chunk_size:
            chunks.append(current_chunk.strip())
            # Keep overlap from end of current chunk
            if chunk_overlap > 0 and len(current_chunk) > chunk_overlap:
                current_chunk = current_chunk[-chunk_overlap:]
            else:
                current_chunk = ""

        # If a single paragraph exceeds chunk size, split it by sentences
        if len(para) > chunk_size:
            sub_chunks = _split_long_paragraph(para, chunk_size, chunk_overlap)
            for sc in sub_chunks:
                if current_chunk and len(current_chunk) + len(sc) + 2 > chunk_size:
                    chunks.append(current_chunk.strip())
                    current_chunk = current_chunk[-chunk_overlap:] if chunk_overlap > 0 else ""
                current_chunk = (current_chunk + "\n\n" + sc).strip() if current_chunk else sc
        else:
            current_chunk = (current_chunk + "\n\n" + para).strip() if current_chunk else para

    # Don't forget the last chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


def _split_long_paragraph(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Split a long paragraph by sentence boundaries."""
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text)

    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        if current and len(current) + len(sentence) + 1 > chunk_size:
            chunks.append(current.strip())
            current = current[-chunk_overlap:] if chunk_overlap > 0 else ""
        current = (current + " " + sentence).strip() if current else sentence

    if current.strip():
        chunks.append(current.strip())

    return chunks
