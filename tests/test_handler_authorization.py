"""Guard: every alloq event handler that can reach the database is guarded.

Page guards only affect rendering. Event handlers run over the websocket
regardless, so each handler that reads or writes business data must enforce
rights server-side: ``@requires_admin`` for the administration states,
``@requires_editor`` (admins and project managers) for the planning packages,
or an inline check for background handlers. Handlers that only change UI state
are listed explicitly in ``UI_ONLY_HANDLERS``; they must not reach the
database. Read-only loads of the projects and planning pages are also open to
the employee role (``@requires_viewer``); they are listed in ``VIEWER_HANDLERS``.
"""

import importlib
import inspect
import pkgutil
import re
from collections.abc import Callable, Iterator
from typing import Any

import pytest
import reflex as rx
from alloq_commons.access import ACCESS_LEVEL_ATTR

PACKAGES = (
    "alloq_commons",
    "alloq_dashboard",
    "alloq_offer",
    "alloq_project",
    "alloq_team",
)
EXTRA_MODULES = (
    "app.components.sidebar_state",
    "app.desktop.db_access_state",
    "app.desktop.login_state",
)
OWN_PACKAGES = frozenset({*PACKAGES, "app"})

# Administration needs the admin switch; project managers may not run these.
ADMIN_STATES = frozenset(
    {
        "DailyRateState",
        "PriceListState",
        "DepartmentState",
        "RoleState",
        "HolidayState",
        "DatabaseAccessState",
    }
)
# Planning states are open to project managers, so they use @requires_editor.
EDITOR_PACKAGES = frozenset({"alloq_dashboard", "alloq_project", "alloq_team"})
EDITOR_STATES = frozenset({"SidebarState"})
# Offer states use their own level (admin, project manager, offer editor).
OFFER_PACKAGES = frozenset({"alloq_offer"})

# Reflex adds ``setvar`` to every state; it only sets a declared var.
REFLEX_BUILTINS = frozenset({"setvar"})

# Background handlers cannot use a guard decorator (``get_state`` needs the
# state lock), so they check edit rights inside ``async with self``.
INLINE_ADMIN_CHECK: dict[str, frozenset[str]] = {
    state: frozenset({"load"})
    for state in (
        "ProjectsOverviewState",
        "ProjectHealthState",
        "BudgetBurnState",
        "UtilizationState",
        "UnderUtilizationState",
        "RoleCapacityState",
        "RiskState",
    )
}

# Sign-in and sign-out run without a session by nature (like appkit's
# LoginState). The desktop login checks the user itself: Entra ID decides who
# reaches the database, the alloq account decides who gets a session.
PRE_AUTH_HANDLERS: dict[str, frozenset[str]] = {
    "DesktopLoginState": frozenset({"sign_in_with_microsoft", "sign_out"}),
}

# Loads that only read; the employee role may run them (``@requires_viewer``).
VIEWER_HANDLERS: dict[str, frozenset[str]] = {
    "ProjectState": frozenset(
        {"load_projects", "select_project", "select_project_with_tab"}
    ),
    "ProjectResourceState": frozenset({"load_selected"}),
    "PlanningStore": frozenset({"load", "refresh", "reload_with_time_range"}),
}

UI_ONLY_HANDLERS: dict[str, frozenset[str]] = {
    "SplashState": frozenset({"finish"}),
    "SidebarState": frozenset({"invalidate"}),
    "DashboardState": frozenset({"close_drill_down", "open_drill_down"}),
    "OfferState": frozenset(
        {
            "close_modal",
            "inspect",
            "open_create_modal",
            "open_edit_modal",
            "reset_filters",
            "set_form_field",
            "set_inspected_sent_date",
            "set_list_filter",
            "set_search_filter",
            "set_sent_date_today",
            "toggle_inspector",
            "toggle_sort",
        }
    ),
    "RoleState": frozenset(
        {
            "close_add_modal",
            "close_edit_modal",
            "open_add_modal",
            "open_edit_modal",
            "set_search_filter",
        }
    ),
    "DailyRateState": frozenset(
        {"set_margin_draft", "set_min_margin_draft", "set_search_filter"}
    ),
    "DepartmentState": frozenset(
        {
            "close_add_modal",
            "close_edit_modal",
            "open_add_modal",
            "set_search_filter",
        }
    ),
    "HolidayState": frozenset(
        {
            "close_add_modal",
            "close_edit_modal",
            "open_add_modal",
            "open_edit_modal",
            "set_search_filter",
            "set_selected_year",
        }
    ),
    "TeamState": frozenset(
        {
            "inspect",
            "set_list_filter",
            "toggle_inspector",
            "close_absence_modal",
            "close_add_modal",
            "close_add_project_modal",
            "close_detail_drawer",
            "open_absence_modal",
            "open_add_modal",
            "set_absence_date_range",
            "set_add_project_selected",
            "set_quick_project_code",
            "set_quick_project_name",
            "set_search_filter",
            "set_view_mode",
            "toggle_section_expanded",
            "toggle_sort",
        }
    ),
    "EmployeeValidationState": frozenset(
        {
            "initialize",
            "set_department_id",
            "set_email",
            "set_first_name",
            "set_hours_per_week",
            "set_internal_hours",
            "set_job_title",
            "set_last_name",
            "set_location",
            "set_manager_id",
            "set_key_role_id",
            "set_role_ids",
            "set_seniority",
            "validate_email",
            "validate_first_name",
            "validate_hours_per_week",
            "validate_internal_hours",
            "validate_last_name",
            "validate_key_role_id",
        }
    ),
    "ProjectState": frozenset(
        {
            "inspect",
            "set_list_filter",
            "toggle_inspector",
            "add_project_risk",
            "close_add_modal",
            "close_detail_drawer",
            "collapse_risk_edit",
            "collapse_status_edit",
            "expand_risk",
            "expand_status",
            "open_add_modal",
            "set_active_tab",
            "set_inspected_date_draft",
            "set_inspected_date_today",
            "set_risk_draft_description",
            "set_risk_draft_impact",
            "set_risk_draft_measures",
            "set_risk_draft_mitigation_status",
            "set_risk_draft_name",
            "set_risk_draft_probability",
            "set_search_filter",
            "set_status_budget_usage",
            "set_status_date",
            "set_status_draft_budget_usage",
            "set_status_draft_date",
            "set_status_draft_notes",
            "set_status_draft_progress",
            "set_status_notes",
            "set_status_progress",
            "set_view_mode",
            "toggle_sort",
        }
    ),
    "ProjectValidationState": frozenset(
        {
            "has_errors",
            "initialize",
            "set_budget",
            "set_booking_number",
            "set_code",
            "set_color",
            "set_customer",
            "set_end_date",
            "set_name_de",
            "set_owner_ids",
            "set_role_capacity",
            "set_start_date",
            "set_state",
            "validate_budget",
            "validate_code",
            "validate_dates",
            "validate_name_de",
        }
    ),
    "ProjectResourceState": frozenset(
        {
            "cancel_edit",
            "edit_period",
            "set_days_per_week",
            "set_end",
            "set_role_id",
            "set_start",
            "sync_days_input",
        }
    ),
    "ProjectPlanState": frozenset(
        {
            "clear_employee_selection",
            "close_modal",
            "next_step",
            "num_weeks_from",
            "prev_step",
            "select_all_filtered",
            "set_emp_planned_pct",
            "set_emp_planned_pt",
            "set_emp_role",
            "set_employee_role_filter",
            "set_gtk_count",
            "set_ramp_down",
            "set_ramp_up",
            "set_search",
            "set_total_pt",
            "toggle_employee",
        }
    ),
    "PlanningStore": frozenset(
        {
            "apply_cell_changes",
            "apply_view_settings",
            "close_add_project_for_employee",
            "notify_rejected",
            "open_add_project_for_employee",
            "open_project",
            "set_absence_show_all",
            "set_add_project_selected",
            "set_available_only",
            "set_employee_filter",
            "set_hide_internal",
            "set_project_filter",
            "set_quick_project_code",
            "set_quick_project_name",
            "set_role_filter",
            "set_time_range",
            "set_view_mode",
            "toggle_all_sections",
            "toggle_employee",
            "toggle_employee_scope",
            "toggle_grid_density",
            "toggle_project",
            "toggle_project_scope",
            "toggle_unhighlighted",
        }
    ),
}

# Source markers of database access (directly or through a service).
DB_MARKERS = (
    "get_asyncdb_session",
    "_repo.",
    "aggregation.",
    "apply_resource_plan",
    "create_quick_project",
)
_SELF_CALL = re.compile(r"self\.(\w+)\(")
WRITE_MARKERS = re.compile(r"\.(?:commit|add|delete|merge|create|update|save)\w*\(")


def _import_all() -> None:
    for package in PACKAGES:
        module = importlib.import_module(package)
        for info in pkgutil.walk_packages(module.__path__, f"{package}."):
            importlib.import_module(info.name)
    for name in EXTRA_MODULES:
        importlib.import_module(name)


def _subclasses[T](cls: type[T]) -> Iterator[type[T]]:
    for sub in cls.__subclasses__():
        yield sub
        yield from _subclasses(sub)


def _own_states() -> dict[str, type[rx.State]]:
    _import_all()
    return {
        cls.__name__: cls
        for cls in _subclasses(rx.State)
        if cls.__module__.split(".")[0] in OWN_PACKAGES
        # Mixins are checked through the states they are mixed into.
        and not cls._mixin
    }


def _handlers(state: type[rx.State]) -> dict[str, Any]:
    return {
        name: handler
        for name, handler in state.event_handlers.items()
        if name not in REFLEX_BUILTINS
    }


def _wrapper_chain(fn: Callable[..., Any]) -> Iterator[Callable[..., Any]]:
    current: Any = fn
    while current is not None:
        yield current
        current = getattr(current, "__wrapped__", None)


def _is_decorated_by(fn: Callable[..., Any], decorator: str) -> bool:
    # functools.wraps copies __qualname__, but not the wrapper's code object.
    return any(
        getattr(getattr(f, "__code__", None), "co_qualname", "").startswith(
            f"{decorator}."
        )
        for f in _wrapper_chain(fn)
    )


def _access_level(fn: Callable[..., Any], level: str) -> bool:
    return any(getattr(f, ACCESS_LEVEL_ATTR, None) == level for f in _wrapper_chain(fn))


def _is_requires_admin(fn: Callable[..., Any]) -> bool:
    return _is_decorated_by(fn, "requires_admin")


def _is_requires_editor(fn: Callable[..., Any]) -> bool:
    return _access_level(fn, "editor")


def _is_requires_viewer(fn: Callable[..., Any]) -> bool:
    return _access_level(fn, "viewer")


def _is_requires_offer_editor(fn: Callable[..., Any]) -> bool:
    return _access_level(fn, "offer_editor")


def _is_guarded(fn: Callable[..., Any]) -> bool:
    return (
        _is_requires_admin(fn)
        or _is_requires_editor(fn)
        or _is_requires_offer_editor(fn)
    )


def _db_markers(
    state: type[rx.State], fn: Callable[..., Any], seen: set[str]
) -> list[str]:
    """DB markers in ``fn`` and in the non-handler ``self.`` helpers it calls."""
    try:
        source = inspect.getsource(inspect.unwrap(fn))
    except OSError, TypeError:
        return []
    hits = [marker for marker in DB_MARKERS if marker in source]
    for name in sorted(set(_SELF_CALL.findall(source)) - seen):
        seen.add(name)
        attr = inspect.getattr_static(state, name, None)
        helper = getattr(attr, "fget", getattr(attr, "__func__", attr))
        if name in state.event_handlers or not inspect.isfunction(helper):
            continue
        hits += [f"{name} -> {hit}" for hit in _db_markers(state, helper, seen)]
    return hits


STATES = _own_states()


def test_states_are_discovered() -> None:
    assert {"TeamState", "PlanningStore", "RoleState", "RiskState"} <= set(STATES)


def test_every_handler_is_admin_guarded_or_ui_only() -> None:
    unguarded = sorted(
        f"{state_name}.{name}"
        for state_name, state in STATES.items()
        for name, handler in _handlers(state).items()
        if not _is_guarded(handler.fn)
        and not (
            _is_requires_viewer(handler.fn)
            and name in VIEWER_HANDLERS.get(state_name, frozenset())
        )
        and name not in INLINE_ADMIN_CHECK.get(state_name, frozenset())
        and name not in UI_ONLY_HANDLERS.get(state_name, frozenset())
        and name not in PRE_AUTH_HANDLERS.get(state_name, frozenset())
    )
    assert unguarded == [], (
        "Guard these handlers with @requires_editor (@requires_admin in the "
        "administration), or add them to UI_ONLY_HANDLERS if they only change "
        "UI state"
    )


def _is_editor_state(state_name: str, state: type[rx.State]) -> bool:
    return (
        state.__module__.split(".")[0] in EDITOR_PACKAGES or state_name in EDITOR_STATES
    )


def test_planning_handlers_are_open_to_project_managers() -> None:
    admin_guarded = sorted(
        f"{state_name}.{name}"
        for state_name, state in STATES.items()
        if _is_editor_state(state_name, state)
        for name, handler in _handlers(state).items()
        if _is_requires_admin(handler.fn)
    )
    assert admin_guarded == [], "Use @requires_editor outside the administration"


def _is_offer_state(state: type[rx.State]) -> bool:
    return state.__module__.split(".")[0] in OFFER_PACKAGES


def test_offer_handlers_use_the_offer_editor_level() -> None:
    wrong = sorted(
        f"{state_name}.{name}"
        for state_name, state in STATES.items()
        if _is_offer_state(state)
        for name, handler in _handlers(state).items()
        if not _is_requires_offer_editor(handler.fn)
        and name not in UI_ONLY_HANDLERS.get(state_name, frozenset())
    )
    assert wrong == [], "Guard offer handlers with @requires_offer_editor"


def test_offer_handlers_are_not_admin_or_editor_guarded() -> None:
    wrong = sorted(
        f"{state_name}.{name}"
        for state_name, state in STATES.items()
        if _is_offer_state(state)
        for name, handler in _handlers(state).items()
        if _is_requires_admin(handler.fn)
        or _is_requires_editor(handler.fn)
        or _is_requires_viewer(handler.fn)
    )
    assert wrong == []


def test_administration_handlers_stay_admin_only() -> None:
    assert ADMIN_STATES <= set(STATES)
    opened = sorted(
        f"{state_name}.{name}"
        for state_name in ADMIN_STATES
        for name, handler in _handlers(STATES[state_name]).items()
        if _is_requires_editor(handler.fn) or _is_requires_viewer(handler.fn)
    )
    assert opened == []


def test_viewer_handlers_are_exactly_the_allowlist() -> None:
    viewer_guarded = {
        (state_name, name)
        for state_name, state in STATES.items()
        for name, handler in _handlers(state).items()
        if _is_requires_viewer(handler.fn)
    }
    allowed = {(s, n) for s, names in VIEWER_HANDLERS.items() for n in names}
    assert viewer_guarded == allowed


@pytest.mark.parametrize(
    ("state_name", "name"),
    sorted((s, n) for s, names in VIEWER_HANDLERS.items() for n in names),
)
def test_viewer_handler_does_not_write(state_name: str, name: str) -> None:
    source = inspect.getsource(inspect.unwrap(_handlers(STATES[state_name])[name].fn))
    assert not WRITE_MARKERS.findall(source)


def test_allowlists_have_no_stale_entries() -> None:
    stale = []
    for allowlist in (UI_ONLY_HANDLERS, INLINE_ADMIN_CHECK, PRE_AUTH_HANDLERS):
        for state_name, names in allowlist.items():
            handlers = _handlers(STATES[state_name]) if state_name in STATES else {}
            stale += [
                f"{state_name}.{name}"
                for name in names
                if name not in handlers or _is_guarded(handlers[name].fn)
            ]
    assert stale == []


@pytest.mark.parametrize(
    ("state_name", "name"),
    sorted((s, n) for s, names in UI_ONLY_HANDLERS.items() for n in names),
)
def test_ui_only_handler_does_not_reach_database(state_name: str, name: str) -> None:
    state = STATES[state_name]
    assert _db_markers(state, _handlers(state)[name].fn, set()) == []


@pytest.mark.parametrize(
    ("state_name", "name"),
    sorted((s, n) for s, names in INLINE_ADMIN_CHECK.items() for n in names),
)
def test_background_handlers_check_edit_rights_inside_state_lock(
    state_name: str, name: str
) -> None:
    state = STATES[state_name]
    handler = _handlers(state)[name]
    assert handler.is_background
    assert "self._run_card_load(" in inspect.getsource(inspect.unwrap(handler.fn))
    runner = inspect.getsource(inspect.getattr_static(state, "_run_card_load"))
    lock = runner.index("async with self:")
    check = runner.index("await _can_edit(self")
    load = runner.index("await loader()")
    assert lock < check < load


def test_guards_are_not_used_on_background_handlers() -> None:
    # A background StateProxy only allows get_state while holding the lock,
    # which the guard decorators do not take.
    offenders = sorted(
        f"{state_name}.{name}"
        for state_name, state in STATES.items()
        for name, handler in _handlers(state).items()
        if handler.is_background
        and (_is_guarded(handler.fn) or _is_requires_viewer(handler.fn))
    )
    assert offenders == []
