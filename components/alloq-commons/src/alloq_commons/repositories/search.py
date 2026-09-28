"""Helpers for user-supplied search text in SQL LIKE patterns."""

LIKE_ESCAPE_CHAR = "\\"


def escape_like(text: str) -> str:
    """Escape LIKE wildcards so *text* matches literally with LIKE_ESCAPE_CHAR."""
    return (
        text.replace(LIKE_ESCAPE_CHAR, LIKE_ESCAPE_CHAR * 2)
        .replace("%", LIKE_ESCAPE_CHAR + "%")
        .replace("_", LIKE_ESCAPE_CHAR + "_")
    )
