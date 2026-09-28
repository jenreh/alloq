"""Architecture guard: component packages must not import the host app."""

import ast
from pathlib import Path

COMPONENTS = Path(__file__).resolve().parents[1] / "components"


def _imports_host_app(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        elif isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        else:
            continue
        if any(name == "app" or name.startswith("app.") for name in names):
            return True
    return False


def test_components_do_not_import_host_app() -> None:
    offenders = [
        str(path.relative_to(COMPONENTS))
        for path in COMPONENTS.glob("*/src/**/*.py")
        if _imports_host_app(path)
    ]
    assert offenders == []


def test_app_roles_reexports_commons_roles() -> None:
    from alloq_commons.roles import ALL_ROLES as COMMONS_ROLES  # noqa: PLC0415

    from app.roles import ALL_ROLES  # noqa: PLC0415

    assert ALL_ROLES is COMMONS_ROLES
