"""Chapter numbers of an outline (1, 2, 2.1, 3) from order and level."""

from alloq_offer.workshop.content.schema import ATTACHED_TYPES


def outline_numbers(levels: list[int], types: list[str] | None = None) -> list[str]:
    """One number per chapter; a sub chapter before any main one counts under 1.

    Attached chapters (``ATTACHED_TYPES``) get an empty number.
    """
    numbers: list[str] = []
    main = sub = 0
    for index, level in enumerate(levels):
        if types is not None and types[index] in ATTACHED_TYPES:
            numbers.append("")
        elif level == 1:
            main += 1
            sub = 0
            numbers.append(str(main))
        else:
            main = max(main, 1)
            sub += 1
            numbers.append(f"{main}.{sub}")
    return numbers
