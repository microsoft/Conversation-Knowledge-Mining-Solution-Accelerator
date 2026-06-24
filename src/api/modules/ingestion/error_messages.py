"""User-friendly error message formatting for file upload failures."""

import logging
from src.api.utils.constants import DOCUMENT_EXTENSIONS

logger = logging.getLogger(__name__)


def _supported_formats_text() -> str:
    ordered = ["pdf", "docx", "xlsx", "csv", "txt", "png", "jpg", "jpeg", "wav", "mp3", "mp4"]
    labels = [ext.upper() for ext in ordered if ext in DOCUMENT_EXTENSIONS]
    return ", ".join(labels)


def format_error_for_user(error_msg: str, filename: str = "", file_type: str = "") -> str:
    """
    Convert technical error messages into user-friendly, actionable messages.
    
    Args:
        error_msg: The technical error message from the system
        filename: Original filename (optional, for context)
        file_type: File extension or type (optional, for context)
    
    Returns:
        User-friendly error message suitable for UI display
    """
    error_lower = error_msg.lower()
    effective_file_type = (file_type or filename.rsplit(".", 1)[-1] if "." in filename else file_type).lower()
    supported = _supported_formats_text()
    
    # Category 1: Format/Corruption issues
    if any(term in error_lower for term in ["corrupted", "invalid format", "not a valid", "unsupported format"]):
        return (
            "This file format is not supported or the file is corrupted. "
            f"Please upload one of the supported formats: {supported}."
        )
    
    # Category 2: Unsupported audio/video formats
    if effective_file_type in ["flac", "aac", "ogg", "m4a"] or any(term in error_lower for term in ["flac", "aac", "ogg", "m4a"]):
        return (
            "This audio format is not currently supported. "
            f"Please upload one of the supported formats: {supported}."
        )
    
    # Category 3: Empty file
    if any(term in error_lower for term in ["empty", "no content", "zero bytes", "no text"]):
        return f"The file '{filename}' appears to be empty. Please ensure the file contains text content."
    
    # Category 4: Timeout/Service issues
    if "timeout" in error_lower or "max_wait" in error_lower:
        return f"Processing '{filename}' took longer than expected. Please try uploading again in a moment. If this persists, try splitting the file into smaller documents."
    
    # Category 5: File size issues  
    if any(term in error_lower for term in ["too large", "exceeds", "size limit", "max_bytes"]):
        return "The file is too large. Please reduce the file size and try again."
    
    # Category 6: Extraction failure
    if "chunk indexing produced 0" in error_lower:
        return f"The file '{filename}' was read but could not be processed into searchable content. The file may be empty or contain only images. Please try a different file."
    
    if "extraction failed" in error_lower or "could not extract" in error_lower:
        return f"The system could not read the content from '{filename}'. Please verify the file is not corrupted and try again."
    
    # Category 7: Indexing failure
    if "indexing" in error_lower or "index" in error_lower:
        return "The file was processed but could not be indexed for search. Please try uploading a different file."
    
    # Category 8: Generic fallback
    if len(error_msg) > 200:
        # Truncate very long technical messages
        return "An error occurred while processing this file. Please verify the file is valid and try again. Contact support if the issue persists."
    
    return f"Could not process this file. Please verify it is one of the supported formats: {supported}, then try again."


def categorize_error(error_msg: str) -> str:
    """
    Categorize an error for logging and monitoring purposes.
    
    Returns one of: "format", "timeout", "size", "empty", "service", "unknown"
    """
    error_lower = error_msg.lower()
    
    if any(term in error_lower for term in ["format", "corrupted", "invalid", "unsupported"]):
        return "format"
    if "timeout" in error_lower or "max_wait" in error_lower:
        return "timeout"
    if any(term in error_lower for term in ["too large", "size limit", "exceeds"]):
        return "size"
    if any(term in error_lower for term in ["empty", "no content", "no text"]):
        return "empty"
    if any(term in error_lower for term in ["index", "embed", "search"]):
        return "service"
    
    return "unknown"
