"""List Python files over the 1000-line limit in app/ and components/*/src.

Run from the repo root:
    python .claude/skills/alloq-implementation/scripts/check_file_sizes.py
Exit code 1 when any file is over the limit.
"""

import sys
from pathlib import Path

LIMIT = 1000


def oversized(root: Path) -> list[tuple[int, Path]]:
    files = [*root.glob("app/**/*.py"), *root.glob("components/*/src/**/*.py")]
    sizes = [(len(p.read_text(encoding="utf-8").splitlines()), p) for p in files]
    return sorted(((n, p) for n, p in sizes if n > LIMIT), reverse=True)


def main() -> int:
    root = Path.cwd()
    found = oversized(root)
    for lines, path in found:
        sys.stdout.write(f"{lines:5d}  {path.relative_to(root)}\n")
    if not found:
        sys.stdout.write(f"No file over {LIMIT} lines.\n")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
