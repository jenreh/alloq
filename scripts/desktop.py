"""Run the reflex-desktop CLI for alloq.

Adjustments to reflex-desktop 0.1.0 (as in vermoegen):

- It always bundles CPython 3.12; alloq needs 3.14, so the version of
  `runtime.assemble` is pinned and a runtime extracted for another version is
  dropped.
- Its app payload holds only `rxconfig.py` and the `app` package; the backend
  also reads the YAML profiles, so the base config and the desktop profile are
  copied along: no `.env`, no server profiles, no secrets.

Usage: uv run --group desktop python scripts/desktop.py <reflex-desktop args>
"""

import functools
import json
import re
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from reflex_desktop import cli, runtime

PYTHON_VERSION = "3.14.6"
ROOT = Path(__file__).resolve().parents[1]
SRC_TAURI = ROOT / "tauri" / "src-tauri"
CONFIG_DIR = "configuration"
DESKTOP_PROFILE = "config.desktop.yaml"
CONFIG_FILES = ("config.yaml", DESKTOP_PROFILE, "logging.yaml")
"""Base config, the desktop profile and its logging; server profiles stay out."""
BUILD_TIME_KEYS = frozenset({"tenant_id", "client_id", "host", "name"})
"""Public identifiers a `secret:` reference in the desktop profile may stand
for. They are resolved on the build machine and shipped as plain values; the
app on the user's Mac never talks to the Key Vault."""
SECRET_LINE = re.compile(r"^(\s*)([A-Za-z_]+):\s*secret:([\w.-]*)\s*(?:#.*)?$")


class BuildError(SystemExit):
    """The desktop profile would ship a secret."""


def resolve_build_time_values(text: str, lookup: Callable[[str], str]) -> str:
    """Replace `key: secret:name` lines for public identifiers by their value."""
    lines = []
    for line in text.splitlines():
        match = SECRET_LINE.match(line)
        if match is None:
            if "secret:" in line.split("#", 1)[0]:
                raise BuildError(f"Unsupported secret reference: {line.strip()}")
            lines.append(line)
            continue
        indent, key, name = match.groups()
        if key not in BUILD_TIME_KEYS:
            raise BuildError(f"{key}: secrets must not ship with the desktop app")
        lines.append(f"{indent}{key}: {json.dumps(lookup(name or key))}")
    return "\n".join(lines) + "\n"


def drop_stale_runtime(src_tauri: Path, python_version: str) -> bool:
    """Remove bundled interpreter and packages unless they match `python_version`."""
    python_dir = src_tauri / "python"
    minor = python_version.rsplit(".", 1)[0]
    stdlib = python_dir / "python" / "lib" / f"python{minor}"
    if not python_dir.exists() or stdlib.is_dir():
        return False
    shutil.rmtree(python_dir)
    shutil.rmtree(src_tauri / "site-packages", ignore_errors=True)
    return True


def copy_configuration(
    app_root: Path, dest: Path, lookup: Callable[[str], str] | None = None
) -> list[Path]:
    """Copy the YAML profiles next to `rxconfig.py` in the payload."""
    target = dest / CONFIG_DIR
    target.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in CONFIG_FILES:
        source = app_root / CONFIG_DIR / name
        if not source.exists():
            continue
        if name == DESKTOP_PROFILE:
            resolved = resolve_build_time_values(
                source.read_text(encoding="utf-8"), lookup or _secret_lookup()
            )
            (target / name).write_text(resolved, encoding="utf-8")
        else:
            shutil.copy2(source, target / name)
        copied.append(target / name)
    return copied


def _secret_lookup() -> Callable[[str], str]:
    """appkit's secret provider of the build machine (.env or Key Vault)."""
    from appkit_commons.configuration.secret_provider import (  # noqa: PLC0415
        get_secret,
    )

    return get_secret


def with_configuration(copy_payload: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap `runtime.copy_app_payload` so the payload has the profiles."""

    @functools.wraps(copy_payload)
    def copy(app_root: Path, dest: Path) -> Any:
        result = copy_payload(app_root, dest)
        copy_configuration(Path(app_root), Path(dest))
        # The stamp decides whether the app refreshes its per-user copy of the
        # payload; it must cover the profiles too.
        runtime._write_payload_stamp(Path(dest))  # noqa: SLF001
        return result

    return copy


def main() -> None:
    drop_stale_runtime(SRC_TAURI, PYTHON_VERSION)
    runtime.assemble = functools.partial(
        runtime.assemble, python_version=PYTHON_VERSION
    )
    runtime.copy_app_payload = with_configuration(runtime.copy_app_payload)
    cli.main()


if __name__ == "__main__":
    main()
