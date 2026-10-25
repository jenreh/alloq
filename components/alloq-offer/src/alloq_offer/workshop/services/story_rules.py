"""The simple story format: one sentence, no acceptance criteria (spec 8.4)."""

import re

STORY_FIELDS = ("title", "role", "goal", "benefit")
FORBIDDEN_PATTERNS = (
    re.compile(r"\b(given|when|then)\b", re.IGNORECASE),
    re.compile(r"\b(gegeben sei|wenn|dann)\b.*\b(dann|wenn)\b", re.IGNORECASE),
    re.compile(r"akzeptanzkriteri", re.IGNORECASE),
    re.compile(r"abnahmekriteri", re.IGNORECASE),
    re.compile(r"^\s*([-*•]|\d+[.)])\s", re.MULTILINE),
)
MAX_FIELD_LENGTH = 300
MAX_DESCRIPTION_LENGTH = 4000
SENTENCE_PATTERN = re.compile(
    r"^\s*als\s+(?P<role>\S.*?)\s+möchte ich\s+(?P<goal>\S.*?),\s*um\s+"
    r"(?P<benefit>\S.*?)\.?\s*$",
    re.IGNORECASE,
)


def story_sentence(role: str, goal: str, benefit: str) -> str:
    return f"Als {role} möchte ich {goal}, um {benefit}."


def parse_story_sentence(text: str) -> tuple[str, str, str] | None:
    """Role, goal and benefit of an "Als … möchte ich …, um …" sentence."""
    match = SENTENCE_PATTERN.match(text)
    if match is None:
        return None
    return match["role"], match["goal"], match["benefit"]


def story_problems(title: str, role: str, goal: str, benefit: str) -> list[str]:
    """Why the story does not fit the format; empty when it does."""
    problems: list[str] = []
    for name, value in zip(STORY_FIELDS, (title, role, goal, benefit), strict=True):
        text = value.strip()
        if not text:
            problems.append(f"Das Feld „{name}“ ist leer.")
        elif "\n" in text:
            problems.append(f"Das Feld „{name}“ darf nur eine Zeile haben.")
        elif len(text) > MAX_FIELD_LENGTH:
            problems.append(f"Das Feld „{name}“ ist zu lang.")
        elif any(pattern.search(text) for pattern in FORBIDDEN_PATTERNS):
            problems.append(
                f"Das Feld „{name}“ enthält Akzeptanzkriterien oder Prüflisten."
            )
    if role.strip().lower().startswith("als "):
        problems.append("Die Rolle steht ohne „Als“.")
    return problems
