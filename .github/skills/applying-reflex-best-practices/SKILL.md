# Reflex Best Practices — KnowledgeAI-Admin

This skill guides development in this Reflex.dev project. Read it before writing any new feature.

---

## 1. Project Architecture

Every feature lives in its own workspace package under `components/alloq-<name>/`. The main `app/` is the shell that assembles packages into a running application.

```
components/alloq-<feature>/
└── src/alloq_<feature>/
    ├── __init__.py          # public exports only
    ├── configuration.py     # Pydantic config schemas
    ├── backend/             # or backend.py — pure Python, no Reflex
    │   ├── models.py        # SQLModel table + UI models
    │   ├── repository.py    # async DB access
    │   └── services/        # business logic
    ├── state/               # or state.py — rx.State subclasses
    ├── components/          # or components.py — UI functions
    └── pages.py             # page factory functions

app/
├── app.py                   # assembles packages, creates rx.App
├── configuration.py         # root AppConfig + configure()
├── roles.py                 # Role definitions for RBAC
├── styles.py                # global style dicts + stylesheets
├── states/                  # app-level states (HomeState, etc.)
├── components/              # app-level reusable components
└── pages/                   # app-level pages
```

**Rule**: business logic belongs in `backend/`, reactive state in `state/`, UI in `components/`, routing in `pages.py`. Never mix concerns.

---

## 2. State Management

### Base class

All states inherit from `rx.State`. When you need the authenticated user, inherit from `UserSession` (from `appkit_user`):

```python
import reflex as rx
from appkit_user.authentication.states import UserSession

class MyFeatureState(rx.State):  # no auth needed
    ...

class MyFeatureState(UserSession):  # auth needed
    user = await self.authenticated_user
```

### State variable conventions

```python
class MyFeatureState(rx.State):
    # Data — typed, always with a default
    items: list[MyModel] = []
    selected_item: MyModel | None = None

    # Loading / UI flags
    is_loading: bool = False
    is_saving: bool = False

    # Filters / form fields
    search_query: str = ""
    selected_month: int = datetime.now(UTC).month

    # Private (not serialized to frontend) — prefix with _
    _initialized: bool = False

    # Browser-persisted — use rx.LocalStorage
    selected_tab: str = rx.LocalStorage("default", name="my-tab", sync=True)
```

### Computed vars

Use `@rx.var` for derived values. Avoid heavy computation — keep these O(n) at most.
Use `@rx.var(cache=True)` when the computation is more expensive or depends on a subset of state:

```python
@rx.var
def filtered_items(self) -> list[MyModel]:
    q = self.search_query.lower()
    return [i for i in self.items if q in i.name.lower()]

@rx.var
def total_count(self) -> int:
    return len(self.items)

@rx.var
def selected_year_str(self) -> str:
    # Bridge int → str for select components
    return str(self.selected_year)
```

Use async `@rx.var` only for DB queries that must stay reactive:

```python
@rx.var
async def chart_data(self) -> list[dict]:
    user = await self.authenticated_user
    async with rx.asession() as session:
        ...
```

### Event handlers

```python
# Simple sync handler
@rx.event
def set_filter(self, value: str) -> None:
    self.search_query = value

# Async handler with loading guard
@rx.event
async def load_data(self) -> AsyncGenerator:
    self.is_loading = True
    yield                         # push loading=True to frontend immediately

    try:
        results = await my_repo.get_all()
        self.items = results
    except Exception:
        logger.exception("Failed to load data")
        yield rx.toast.error("Laden fehlgeschlagen", position="top-right")
    finally:
        self.is_loading = False   # always clears, even on error

# Chaining: call another event handler from within a handler
@rx.event
async def set_year(self, year: str) -> AsyncGenerator:
    self.selected_year = int(year)
    self._clear_caches()
    async for _ in self.load_data():
        yield

# Background task (long-running, does not block UI)
@rx.event(background=True)
async def export_data(self) -> AsyncGenerator:
    async with self:
        self.is_exporting = True
    yield

    # ... heavy work here ...

    async with self:
        self.is_exporting = False
    yield rx.toast.success("Export abgeschlossen", position="top-right")
```

### Page on_load pattern

```python
@rx.event
async def on_load(self) -> AsyncGenerator:
    """Called via on_load=[MyState.on_load] in the page factory."""
    await self._load_secondary_data()
    async for _ in self.load_data():
        yield
```

### Cache invalidation

When filters or navigation change, always clear caches before reloading:

```python
def _clear_caches(self) -> None:
    self.items.clear()
    self.expanded_rows.clear()
    self.detail_cache.clear()
```

---

## 3. UI Components — appkit_mantine

### The rule

**Use `appkit_mantine` (`mn.*`) for all visible UI.**
`rx.*` is fine for logic, conditionals, iteration, and primitives with no direct Mantine equivalent:

| Purpose | Use |
|---|---|
| Layout containers (stack, group, grid, card) | `mn.stack`, `mn.group`, `mn.simple_grid`, `mn.card` |
| Typography | `mn.text`, `mn.heading` |
| Inputs (button, select, text input, switch, slider) | `mn.button`, `mn.select`, `mn.text_input`, `mn.switch`, `mn.slider` |
| Feedback (toast, progress, spinner, badge) | `rx.toast`, `mn.progress`, `mn.loader`, `mn.badge` |
| Data display (table, charts) | `mn.table`, `mn.bar_chart`, `mn.line_chart` |
| Overlay (dialog, drawer, popover) | `mn.modal`, `mn.drawer`, `mn.popover` |
| Icons | `rx.icon(tag="...", size=N)` — Lucide, no mn equivalent |
| Conditional rendering | `rx.cond(condition, true_comp, false_comp)` |
| List rendering | `rx.foreach(State.items, render_fn)` |
| File upload | `rx.upload(...)` — no mn equivalent |
| SVG / canvas | `rx.el.svg`, `rx.el.g`, `rx.el.line` |

**Never use** `rx.vstack`, `rx.hstack`, `rx.box` where a Mantine equivalent exists. Prefer `mn.stack`, `mn.group`, `mn.card`.

### Core layout patterns

```python
import appkit_mantine as mn

# Vertical stack
mn.stack(child1, child2, gap="md", w="100%")

# Horizontal group
mn.group(child1, child2, gap="xs", align="center", justify="space-between")

# Card container
mn.card(content, shadow="sm", padding="lg", radius="md", with_border=True)

# Responsive grid
mn.simple_grid(
    card1, card2, card3,
    cols={"base": 1, "sm": 2, "lg": 3},
    spacing="md",
)

# Scroll area
mn.scroll_area(content, h=400, type="auto")
```

### Typography

```python
mn.text("Label", size="2", c="dimmed")       # size: 1–7
mn.heading("Title", size="5", fw=600)        # fw: font-weight
mn.text("Value", size="4", fw="bold")
```

### Buttons and actions

```python
mn.button(
    "Laden",
    on_click=MyState.load_data,
    loading=MyState.is_loading,    # shows spinner, disables click
    variant="filled",              # filled | outline | subtle | light
    size="2",
)

mn.action_icon(
    rx.icon(tag="refresh-cw", size=18),
    on_click=MyState.load_data,
    loading=MyState.is_loading,
    variant="subtle",
)
```

### Selects and inputs

```python
mn.select(
    data=["Option A", "Option B"],        # or list[dict] with label/value
    value=MyState.selected_option,
    on_change=MyState.set_option,
    placeholder="Bitte wählen...",
    clearable=True,
)

mn.text_input(
    value=MyState.search_query,
    on_change=MyState.set_search_query,
    placeholder="Suchen...",
    left_section=rx.icon(tag="search", size=16),
)
```

### Charts (mn.bar_chart, mn.line_chart)

```python
mn.bar_chart(
    data=MyState.chart_data,        # list[dict]
    data_key="month",               # x-axis key
    series=[
        {"name": "Billable", "color": "blue.5"},
        {"name": "Intern",   "color": "gray.4"},
    ],
    chart_type="stacked",
    with_legend=True,
    with_tooltip=True,
    h=280,
    w="100%",
)
```

### Colors

Use Radix color scale (name + shade 1–12). Higher = darker in light mode:

```python
c="blue.6"          # text color
bg="gray.1"         # background
"color": "red.4"    # in chart series
rx.color("blue", 4) # programmatic color (for rx.cond results)
```

### Conditional rendering

```python
rx.cond(
    MyState.is_loading,
    mn.loader(size="sm"),
    content_component(),
)

# With no false branch (renders nothing)
rx.cond(MyState.has_error, error_message())
```

### List rendering

```python
rx.foreach(MyState.items, lambda item: item_row(item))
```

---

## 4. Component Functions

### Always functions, never classes

```python
def my_card(title: str, value: rx.Var | str) -> rx.Component:
    """One card. Accepts state vars as arguments."""
    return mn.card(
        mn.group(
            mn.stack(
                mn.text(title, size="2", c="dimmed"),
                mn.heading(value, size="6", fw="bold"),
                gap="2",
            ),
            gap="md",
            align="center",
        ),
        shadow="sm",
        padding="md",
        radius="md",
        with_border=True,
    )
```

### Composition hierarchy

Build small → compose big. Name private helpers with a leading underscore:

```python
def _filter_bar() -> rx.Component: ...
def _data_table() -> rx.Component: ...
def _empty_state() -> rx.Component: ...

def my_page_content() -> rx.Component:
    """Top-level component — assembles the others."""
    return mn.stack(
        _filter_bar(),
        rx.cond(
            MyState.is_loading,
            mn.loader(),
            rx.cond(
                MyState.items,
                _data_table(),
                _empty_state(),
            ),
        ),
        gap="md",
        w="100%",
    )
```

### Passing state vars, not raw values

```python
# Correct: reactive binding
my_card(title="Users", value=MyState.user_count)

# Wrong: value won't update when state changes
my_card(title="Users", value=42)
```

### Responsive layout

Use Mantine breakpoint dicts for responsive props:

```python
mn.simple_grid(cols={"base": 1, "sm": 2, "lg": 4}, spacing="md")
rx.flex(direction=["column", "column", "row"], gap="4")
```

---

## 5. Page Factory Pattern

Every feature package exports a factory function (not a bare page):

```python
# pages.py
from appkit_user.authentication.templates import authenticated

def create_my_feature_page(
    navbar: rx.Component,
    route: str = "/my-feature",
    title: str = "My Feature",
) -> Callable:
    @authenticated(
        route=route,
        title=title,
        navbar=navbar,
        on_load=MyFeatureState.on_load,
        admin_only=True,          # or role="role-name"
    )
    def my_feature_page() -> rx.Component:
        return rx.flex(
            header(title),
            my_page_content(),
            direction="column",
            gap="4",
            w="100%",
            p="2rem",
        )

    return my_feature_page
```

Register in `app/app.py`:

```python
from knai_myfeature.pages import create_my_feature_page

create_my_feature_page(app_navbar())
```

---

## 6. Service Registry & Dependency Injection

Use `service_registry()` (from `appkit_commons`) as the single IoC container.

### Configuration

```python
# configuration.py
from appkit_commons.registry import service_registry

class MyFeatureConfig(BaseConfig):
    api_url: str | None = None
    api_key: SecretStr | None = None
```

Register in `configure()` in `app/configuration.py` by adding to `AppConfig`:

```python
class AppConfig(ApplicationConfig):
    my_feature: MyFeatureConfig | None = None
```

### Services

```python
class MyService:
    def __init__(self) -> None:
        self._config = service_registry().get(MyFeatureConfig)
```

Register in `app/app.py` `_initialize_services()` in dependency order.

### Accessing in state

```python
def _do_work(self) -> None:
    config = service_registry().get(MyFeatureConfig)
    svc = service_registry().get(MyService)
```

---

## 7. Repository Pattern

```python
# backend/repository.py — use static/class methods, no instance needed

class MyModelRepository:
    @staticmethod
    async def get_all(user_id: int) -> list[MyModel]:
        async with rx.asession() as session:
            result = await session.exec(
                select(MyModel).where(MyModel.user_id == user_id)
            )
            return list(result.all())

    @staticmethod
    async def create(user_id: int, data: dict) -> MyModel:
        async with rx.asession() as session:
            item = MyModel(user_id=user_id, **data)
            session.add(item)
            await session.commit()
            await session.refresh(item)
            return item
```

Use `rx.asession()` for async operations. Reserve raw `get_asyncdb_session()` for cases where you need transaction control across multiple operations.

---

## 8. Database Models

```python
# backend/models.py

class MyModel(rx.Model, table=True):
    """DB table."""
    __tablename__ = "my_feature_items"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    name: str = Field(max_length=200)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

class MyModelDisplay(rx.Base):
    """UI-only model (not a table) — safe to store in state."""
    name: str
    formatted_date: str
    color_indicator: str
```

**Important**: Never store SQLModel `table=True` objects directly in state if they contain lazy-loaded relationships. Use display models (`rx.Base`) as the state-layer DTO.

---

## 9. Roles & Authorization

Define new roles in `app/roles.py`:

```python
MY_FEATURE_ROLE = Role(name="my-feature", label="My Feature", group=MY_GROUP)
ALL_ROLES = [..., MY_FEATURE_ROLE]
```

Use in page factory: `admin_only=True` or `role=MY_FEATURE_ROLE.name`.

Use in navbar:

```python
requires_role(
    sidebar_item(label="My Feature", icon="star", url="/my-feature"),
    role=MY_FEATURE_ROLE.name,
)
```

---

## 10. Anti-Patterns

| Anti-pattern | Correct approach |
|---|---|
| `rx.vstack` / `rx.hstack` for layout | `mn.stack` / `mn.group` |
| `rx.box` as a container | `mn.card` or `mn.paper` |
| `rx.text` / `rx.heading` | `mn.text` / `mn.heading` |
| Inline styles as strings `style="..."` | Props: `c="blue.6"`, `fw="bold"`, `p="md"` |
| Storing table=True models in state | Use `rx.Base` display models |
| Calling `service_registry()` at module level | Call inside functions/methods |
| Mutating state without `yield` in async gen | Always `yield` after mutations |
| Fat page functions | Decompose into `_section()` helpers |
| Logic in components | Move to state event handlers or `@rx.var` |

---

## 11. File & Naming Conventions

```
state/my_feature_state.py        → MyFeatureState(rx.State)
components/my_feature_table.py   → my_feature_table() → rx.Component
components/my_feature_dialogs.py → create_dialog(), delete_dialog()
backend/models.py                → MyModel, MyModelDisplay
backend/repository.py            → MyModelRepository (static methods)
pages.py                         → create_my_feature_page(navbar)
configuration.py                 → MyFeatureConfig(BaseConfig)
```

---

## 12. Example Files

See the `examples/` folder alongside this SKILL.md:

| File | Demonstrates |
|---|---|
| `state_example.py` | Full state class — loading, computed vars, pagination |
| `components_example.py` | appkit_mantine component patterns — cards, table, chart |
| `pages_example.py` | Page factory with auth, on_load, navbar |
| `background_task_example.py` | File upload + async background processing |
