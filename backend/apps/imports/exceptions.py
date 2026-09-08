class LetterboxdImportError(Exception):
    """Controlled import error: corrupt zip, malformed CSV, a CSV
    with an unexpected header for what it claims to be, an unwanted file
    uploaded standalone, or a required CSV missing."""