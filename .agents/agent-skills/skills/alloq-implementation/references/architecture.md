# Alloq architecture

## Contents

1. Package map
2. The department reference slice
3. Large states: mixins
4. Background loads: `_CardLoadMixin`
5. Services and loaders
6. Pages and registration

All snippets are copied from the repo. Paths under `commons/` mean
`components/alloq-commons/src/alloq_commons/`.

## 1. Package map

| Path | Role |
| --- | --- |
| `app/app.py` | entry point; calls every page factory with `sidebar()` |
| `app/pages/*.py` | admin pages of the host app (users, roles, departments, holidays, profile, login) |
| `app/components/sidebar.py` | navigation entries `(route, label, icon)` |
| `app/desktop/` | Tauri desktop app: Entra sign-in, DB access, `schema.py` revision check |
| `commons/entities/` | SQLAlchemy entities, exported from `entities/__init__.py` |
| `commons/models/` | Pydantic read models and `*Create` write models, exported from `models/__init__.py` |
| `commons/repositories/` | one repository plus singleton per entity, exported from `repositories/__init__.py` |
| `commons/services/` | shared pure logic (`utilization.py`, `quick_project.py`) |
| `commons/components/` | shared UI: `list_view`, `modal_layout`, `dialogs`, `toolbar`, `forms`, `shell.app_page`, `formatters` |
| `commons/theme.py` | color scales, tokens (`theme.TEXT_MUTED`), `CARD`, `RADIUS`, `NUMERIC` |
| `commons/roles.py`, `commons/access.py` | app roles; `requires_editor`, `requires_viewer`, `editor_only`, `IS_ADMIN`, `CAN_EDIT`, `CAN_VIEW` |
| `components/alloq-<feature>/src/alloq_<feature>/` | `components/`, `services/`, `states/`, `pages.py` |

Import rules: feature packages import `alloq_commons` and appkit, never `app`
(guarded by `tests/test_component_boundaries.py`). When a new entity, model or
repository is added, export it from the package `__init__.py` like its neighbours,
because states import `from alloq_commons.repositories import department_repo`.

## 2. The department reference slice

Commit `02021a3` added departments end to end. Read these files when you add a
similar feature:

| Layer | File |
| --- | --- |
| Entity | `commons/entities/department.py` |
| Models | `commons/models/department.py` |
| Repository | `commons/repositories/department_repository.py` |
| State | `commons/state/department_states.py` |
| Components | `commons/components/department.py` |
| Page | `app/pages/departments.py`, registered in `app/app.py` |
| Migration | `alembic/versions/2026_10_18_departments.py` |
| Tests | `components/alloq-commons/tests/test_departments.py` |

Entity (`to_dict` feeds the Pydantic read model; keep it complete):

```python
class DepartmentEntity(Entity, Base):
    """Department of the organization; employees belong to at most one."""

    __tablename__ = "departments"

    name: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    abbreviation: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "abbreviation": self.abbreviation,
            "created": self.created,
            "updated": self.updated,
        }
```

Models (read model has defaults; write model validates):

```python
class Department(BaseModel):
    id: int = 0
    name: str = ""
    abbreviation: str = ""
    created: datetime | None = None
    updated: datetime | None = None


class DepartmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    abbreviation: str = Field(..., min_length=1, max_length=10)
```

Repository:

```python
class DepartmentRepository(BaseRepository[DepartmentEntity, AsyncSession]):
    @property
    def model_class(self) -> type[DepartmentEntity]:
        return DepartmentEntity

    async def find_all_paginated(self, session: AsyncSession, limit: int = 200,
                                 offset: int = 0) -> list[DepartmentEntity]: ...


department_repo = DepartmentRepository()
```

`BaseRepository` already gives `find_by_id`, `create`, `update`, `delete_by_id`.

State: a module-level loader returns read models, handlers are guarded, form data is
parsed into the write model, errors become German toasts:

```python
async def load_departments() -> list[Department]:
    async with get_asyncdb_session() as session:
        entities = await department_repo.find_all_paginated(session)
        return [Department(**e.to_dict()) for e in entities]


class DepartmentState(rx.State):
    departments: rx.Field[list[Department]] = rx.field(default_factory=list)
    search_filter: rx.Field[str] = rx.field("")

    @rx.event
    def set_search_filter(self, value: str) -> None:   # UI-only, in allowlist
        self.search_filter = value

    @rx.event
    @requires_admin
    async def create_department(self, form_data: dict) -> AsyncGenerator[Any]:
        try:
            data = _department_from_form(form_data)
            async with get_asyncdb_session() as session:
                await department_repo.create(session, DepartmentEntity(...))
        except ValidationError:
            yield rx.toast.error("Name und Kürzel angeben.", position="top-right")
            return
        except IntegrityError:
            yield rx.toast.error(DUPLICATE_MESSAGE, position="top-right")
            return
        except Exception:
            logger.exception("Failed to create department")
            yield rx.toast.error(
                "Fehler beim Erstellen der Abteilung.", position="top-right"
            )
            return
        self.departments = await load_departments()
```

Computed views use `@rx.var` (`filtered_departments`). Components read those.

Components: form fields take an optional `ObjectVar` so add and edit share code; the
table uses `rx.foreach(DepartmentState.filtered_departments, departments_table_row)`;
the toolbar is a list of `toolbar_search(...)` and `primary_button(...)`.

Migration: hand-written, `batch_alter_table` for column changes on existing tables,
data moves with `op.execute`, a `downgrade()` that undoes all of it. The file header
holds `revision` and `down_revision`; the newest revision goes first into
`KNOWN_REVISIONS` in `app/desktop/schema.py` (`tests/test_desktop_login.py` compares
it with the Alembic history).

## 3. Large states: mixins

`ProjectState` and `TeamState` are big. New list or UI logic goes into a mixin that
the concrete state inherits:

```python
class TeamListState(rx.State, mixin=True):
    """List filter, utilization, selection and inspector; mixed into `TeamState`.

    A mixin rather than a substate: its computed vars read `TeamState` vars.
    """

    if TYPE_CHECKING:  # Provided by TeamState.
        employees: list[Employee]

    list_filter: str = FILTER_ALL
    sort_column: rx.Field[str] = rx.field(DEFAULT_SORT_COLUMN)
```

`class TeamState(TeamListState, UserSession)`. Declare the parent's vars only under
`TYPE_CHECKING`; plain annotations would create duplicate state vars. Other mixins:
`alloq_project/states/project_list_state.py`, `planning_filter_mixin.py`,
`planning_display_mixin.py`, `planning_absence_view_mixin.py`
(`PlanningStore(PlanningDisplayState, PlanningFilterMixin, PlanningAbsenceViewMixin, UserSession)`).

## 4. Background loads: `_CardLoadMixin`

Dashboard cards load in the background. `alloq_dashboard/states/dashboard_states.py`
has a plain Python mixin that checks admin inside the state lock and drops results of
superseded loads with a sequence number:

```python
class RiskState(_CardLoadMixin, UserSession):
    data: rx.Field[RiskKpi] = rx.field(default_factory=RiskKpi)
    is_loading: rx.Field[bool] = rx.field(False)
    last_loaded: rx.Field[str] = rx.field("")
    error_message: rx.Field[str] = rx.field("")
    _load_seq: int = 0

    @rx.event(background=True)
    async def load(self, *, force: bool = False) -> None:
        await self._run_card_load(aggregation.load_risks, "risks", force=force)
```

`_run_card_load` does `async with self:` → `await _is_admin(self, action)` →
`await loader()`. A new card copies this and is added to `INLINE_ADMIN_CHECK`.

## 5. Services and loaders

Keep calculation apart from loading so it can be tested without a database:

- `alloq_dashboard/services/portfolio_inputs.py` loads rows; `portfolio.py` and
  `resource_path.py` compute from them.
- `alloq_team/services/team_overview.py`: `load_inputs(...)` loads,
  `build_overview(...)` computes.
- `alloq_dashboard/services/aggregation.py` loads rows (`_load_risk_rows`) and maps
  entities to small row dataclasses (`_risk_to_row`) before computing KPIs.

## 6. Pages and registration

Admin page in the host app:

```python
def create_departments_page(
    sidebar: rx.Component,
    route: str = "/admin/departments",
    title: str = "Abteilungen",
) -> rx.Component:
    @app_page(
        route=route,
        title=title,
        sidebar=sidebar,
        toolbar=window_toolbar(
            "Abteilungen",
            "Administration · Abteilungen anlegen, bearbeiten und löschen",
            actions=departments_toolbar(),
        ),
        admin_only=True,
        on_load=[DepartmentState.load_departments],
    )
    def _departments_page() -> rx.Component:
        return requires_admin(mn.box(departments_table(), style=theme.CARD, ...))

    return _departments_page
```

Feature pages live in `alloq_<feature>/pages.py` (`create_projects_overview_page`,
`create_planning_page`, `create_dashboard_page`, `create_team_overview_page`).
Register with `create_x_page(sidebar())` in `app/app.py` and add
`("/route", "Label", "icon")` to the list in `app/components/sidebar.py`.
