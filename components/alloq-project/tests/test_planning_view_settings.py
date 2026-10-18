import json

from alloq_project.services.planning_view_settings import (
    READ_SCRIPT,
    STORAGE_KEY,
    ViewSettings,
    parse_view_settings,
    view_settings_script,
)


def test_parse_reads_flags() -> None:
    raw = json.dumps({"compact": True, "collapsed": False, "project_scope": True})
    assert parse_view_settings(raw) == ViewSettings(compact=True, project_scope=True)


def test_parse_treats_unreadable_values_as_off() -> None:
    for raw in (None, "", "not json", "[1]", 5):
        assert parse_view_settings(raw) == ViewSettings()
    assert parse_view_settings(json.dumps({"compact": "yes"})) == ViewSettings()


def test_script_round_trips_through_json() -> None:
    settings = ViewSettings(compact=True, employee_scope=True)
    script = view_settings_script(settings)
    assert STORAGE_KEY in script
    assert "try {" in script
    stored = script.split(", ", 1)[1].rsplit("); }", 1)[0]
    assert parse_view_settings(json.loads(stored)) == settings


def test_read_script_survives_blocked_storage() -> None:
    assert STORAGE_KEY in READ_SCRIPT
    assert "catch" in READ_SCRIPT
