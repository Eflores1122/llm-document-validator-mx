"""Errors raised by the validation pipeline."""


class DocvalError(Exception):
    """Base error for expected, user-facing failures."""


class ParserError(DocvalError):
    """A document could not be read into text."""


class ExtractionError(DocvalError):
    """Structured fields could not be produced from document text."""


class MissingCredentialError(DocvalError):
    """A requested backend needs an API key that is not configured."""
