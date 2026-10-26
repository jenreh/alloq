"""Chapter numbers of an outline (1, 2, 2.1, 3) from order and level."""


def outline_numbers(levels: list[int]) -> list[str]:
    """One number per chapter; a sub chapter before any main one counts under 1."""
    numbers: list[str] = []
    main = sub = 0
    for level in levels:
        if level == 1:
            main += 1
            sub = 0
            numbers.append(str(main))
        else:
            main = max(main, 1)
            sub += 1
            numbers.append(f"{main}.{sub}")
    return numbers
