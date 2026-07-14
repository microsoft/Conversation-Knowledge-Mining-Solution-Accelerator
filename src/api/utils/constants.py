# Supported upload formats, including telecom audio files.
DOCUMENT_EXTENSIONS = {"pdf", "docx", "xlsx", "csv", "txt", "json", "png", "jpg", "jpeg", "wav", "mp3", "mp4"}

# Known audio/video formats (not all are currently accepted by upload validation).
AUDIO_VIDEO_FORMATS = {"wav", "mp3", "mp4", "m4a", "aac", "flac", "ogg"}


def strip_code_fences(text: str) -> str:
    """Strip markdown code fences (```...```) from LLM output."""
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        text = text.rsplit("```", 1)[0]
    return text
