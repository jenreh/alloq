"""Names and hints of the chapter types, shared by outline, document and panel."""

import reflex as rx

TYPE_SHORT = {
    "prose": "Text",
    "table": "Tabelle",
    "stories": "Stories",
    "calc": "Werte",
    "image": "Bild",
}
TYPE_LABELS = {
    "prose": "Fließtext",
    "table": "Tabelle",
    "stories": "User Stories",
    "calc": "Kalkulation",
    "image": "Bild",
}
TYPE_HINTS = {
    "prose": (
        "Freier Text mit Absätzen, Listen und Hervorhebungen. Die KI liefert "
        "Vorschläge, Sie übernehmen sie."
    ),
    "table": (
        "Tabelle mit Kopfzeile unter dem Kapitel davor, ohne eigene Überschrift. "
        "Eine Beschreibung darunter ist freiwillig."
    ),
    "image": (
        "Ein Bild (PNG oder JPEG) unter dem Kapitel davor, ohne eigene Überschrift. "
        "Alternativtext und Beschreibung helfen beim Lesen."
    ),
    "stories": (
        "Geschriebene Stories aus der Story Map: Schlüssel, Titel und ein Satz je "
        "Story, ohne Akzeptanzkriterien. Die Gruppierung legen Sie hier fest."
    ),
    "calc": (
        "Gebundene Werte aus der bestätigten Kalkulation. Zahlen ändern Sie nur in "
        "der Kalkulation."
    ),
}
# Names in "+ Kapitel" and the block editor; stories are spelled out there.
TYPE_OPTIONS = [
    {"value": kind, "label": "User Stories" if kind == "stories" else name}
    for kind, name in TYPE_SHORT.items()
]
FRAME_NOTE = "Aus der Word-Vorlage"


def by_type(kind: rx.Var, names: dict[str, str]) -> rx.Var:
    """The entry of ``names`` for the chapter type ``kind`` (a state var)."""
    return rx.Var.create(names)[kind.to(str)].to(str)
