DOCUMENT_EXTENSIONS = {"pdf", "docx", "xlsx", "csv", "txt", "png", "jpg", "jpeg", "tiff", "bmp", "wav", "mp3", "mp4"}


def strip_code_fences(text: str) -> str:
    """Strip markdown code fences (```...```) from LLM output."""
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        text = text.rsplit("```", 1)[0]
    return text
