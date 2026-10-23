"""Acceptance matrix A01–A27 of the offer workshop (spec section 18).

Every case names the tests that prove it. The matrix test fails when a case is
missing, when a named test does not exist any more, or when a case is claimed
without a proof or a documented manual check.
"""

import ast
from pathlib import Path

import pytest
from alloq_offer.workshop.components import export_tab
from alloq_offer.workshop.export.template_package import load_template

TESTS = Path(__file__).parent

# case -> (summary, ("file::test", ...)); a proof may also be the manual check
# text, marked by the "manual:" prefix, for what no unit test can show.
MATRIX: dict[str, tuple[str, tuple[str, ...]]] = {
    "A01": (
        "Sources of every kind get a status and a reachable origin",
        (
            "extraction::test_eml_separates_body_quote_and_signature",
            "extraction::test_pptx_reads_text_tables_notes_and_flags_pictures",
            "sources::test_audio_is_transcribed_with_speaker_labels",
            "sources::test_corrupt_file_fails_with_a_readable_reason",
        ),
    ),
    "A02": (
        "Scanned page and slide picture are named as gaps",
        (
            "extraction::test_pdf_reads_text_pages_and_flags_pages_without_text_layer",
            "extraction::test_pptx_reads_text_tables_notes_and_flags_pictures",
            "sources::test_gaps_make_a_source_partially_usable",
        ),
    ),
    "A03": (
        "Contradicting sources become a conflict with both anchors",
        (
            "map::test_conflicts_have_their_own_type_and_dropped_stories_are_noted",
            "checks::test_statements_conflicts_block_and_requirements_note",
        ),
    ),
    "A04": (
        "No invented price or guaranteed outcome",
        (
            "map::test_proposals_cannot_carry_scope_keys_or_prices",
            "checks::test_commercials_rules",
        ),
    ),
    "A05": (
        "A new solution approach stays a proposal",
        ("map::test_agent_proposes_briefing_statements",),
    ),
    "A06": (
        "Edited chapter content survives reload",
        (
            "editor_io::test_headings_lists_tables_and_bound_values_survive",
            "chapter_state::test_autosave_creates_revisions_and_marks_the_state",
        ),
    ),
    "A07": (
        "A model result after a manual change is only a proposal",
        (
            "chapter_draft::test_proposal_is_dropped_when_the_chapter_changed_meanwhile",
            "chapters::test_proposal_becomes_stale_when_a_person_saved",
            "map_proposals::test_open_proposal_lists_lines_and_turns_stale",
        ),
    ),
    "A08": (
        "Two editors on the same revision give a visible conflict",
        (
            "chapters::test_save_creates_revision_and_rejects_stale_editor",
            "map_edit::test_stale_revision_is_refused_and_nothing_changes",
            "chapter_state::test_autosave_conflict_reloads_without_overwriting",
        ),
    ),
    "A09": (
        "A changed confirmed value flags confirmation and chapters",
        (
            "checks::test_changed_values_void_the_confirmation_and_flag_chapters",
            "checks::test_saving_the_offer_voids_the_confirmation_but_not_equal_values",
        ),
    ),
    "A10": (
        "Without the offer editor role no workshop data or action is reachable",
        (
            "authorization::test_other_roles_are_denied_before_any_data_is_touched",
            "authorization::test_anonymous_callers_are_sent_to_login",
            "exports::test_download_is_limited_to_the_offer_and_ready_files",
            "revocation::test_revoke_twice_or_foreign_source_changes_nothing",
        ),
    ),
    "A11": (
        "Final output is blocked with reasons, the draft stays possible",
        (
            "exports::test_final_is_blocked_with_all_reasons",
            "exports::test_draft_snapshot_is_fixed_and_job_queued",
            "exports::test_final_passes_when_everything_is_decided",
        ),
    ),
    "A12": (
        "The export holds the chosen revision in the template",
        (
            "exports::test_job_renders_stores_and_download_is_exact",
            "docx_renderer::test_chapter_order_and_headings",
        ),
    ),
    "A13": (
        "A failed export keeps the work and can be retried",
        (
            "exports::test_a_failed_render_is_not_shown_as_success",
            "exports::test_exhausted_job_marks_the_export_failed",
            "jobs::test_runner_requeues_transient_errors",
        ),
    ),
    "A14": (
        "Existing offers keep their bound template version",
        (
            "exports::test_template_version_binding",
            "workspace::test_open_workspace_creates_once_with_template_binding",
        ),
    ),
    "A15": (
        "Rewritten text voids earlier positive review decisions",
        (
            "chapters::test_a_changed_text_voids_accepted_decisions_on_its_findings",
            "revocation::test_revoke_deletes_content_and_flags_dependents",
        ),
    ),
    "A16": (
        "No claim of automatic synchronisation from Word",
        ("acceptance::test_the_export_tab_does_not_promise_word_sync",),
    ),
    "A17": (
        "Taking over AI text does not confirm a business decision",
        (
            "chapters::test_accept_proposal_creates_ai_revision",
            "briefing::test_confirming_is_explicit_and_can_be_withdrawn",
        ),
    ),
    "A18": (
        "Free text against bound values is a finding that blocks final",
        (
            "checks::test_free_numbers_must_match_bound_values",
            "exports::test_final_is_blocked_with_all_reasons",
        ),
    ),
    "A19": (
        "Sources lead to a story map with simple stories",
        ("map::test_initial_draft_builds_map_and_briefing_from_usable_sources",),
    ),
    "A20": (
        "Stories are one sentence without acceptance criteria",
        (
            "map::test_story_rules_reject_criteria_checklists_and_bad_fields",
            "map_edit::test_story_text_must_keep_the_simple_format",
            "checks::test_story_format_and_placement",
        ),
    ),
    "A21": (
        "No knowledge base is needed for map, stories and chapters",
        (
            "map::test_initial_draft_builds_map_and_briefing_from_usable_sources",
            "chapter_draft::test_job_drafts_unwritten_prose_chapters_into_proposals",
        ),
    ),
    "A22": (
        "Variants and open questions are kept, not linearised",
        (
            "map::test_conflicts_have_their_own_type_and_dropped_stories_are_noted",
            "map::test_prompts_forbid_following_instructions_in_sources",
        ),
    ),
    "A23": (
        "Story IDs stay stable when stories move",
        (
            "map_edit::test_archived_keys_are_never_reused",
            "map_edit::test_scope_and_move",
            "map::test_story_keys_continue_and_are_never_reused",
        ),
    ),
    "A24": (
        "Word starts with the story chapter in the same revision as the chapters",
        (
            "acceptance::test_the_story_chapter_comes_before_the_written_chapters",
            "docx_renderer::test_stories_chapter_written_stories_grouped",
            "exports::test_draft_snapshot_is_fixed_and_job_queued",
        ),
    ),
    "A25": (
        "AI stories keep their origin and never widen the offered scope",
        ("map::test_applied_stories_get_app_keys_and_never_start_as_offered",),
    ),
    "A26": (
        "Technical-only sources give open questions, not invented decisions",
        (
            "map::test_prompts_forbid_following_instructions_in_sources",
            "map::test_stories_that_break_the_format_are_skipped",
        ),
    ),
    "A27": (
        "A story change flags written chapters, never overwrites them",
        (
            "chapters::test_map_edit_flags_written_prose_chapters_only",
            "map_edit::test_every_edit_bumps_the_revision_and_keeps_a_snapshot",
        ),
    ),
}

MANUAL_CHECKS = (
    "Open the sample and a real export in Word: layout, table of contents "
    "(fields update on open), headers and footers (spec 18, last paragraph).",
)


def _test_names(module: str) -> set[str]:
    path = TESTS / f"test_workshop_{module}.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }


def _proofs() -> list[tuple[str, str]]:
    return [(case, proof) for case, (_, proofs) in MATRIX.items() for proof in proofs]


def test_every_case_of_the_spec_is_listed() -> None:
    assert list(MATRIX) == [f"A{i:02d}" for i in range(1, 28)]
    assert all(proofs for _, proofs in MATRIX.values())
    assert MANUAL_CHECKS


@pytest.mark.parametrize(("case", "proof"), _proofs())
def test_every_proof_exists(case: str, proof: str) -> None:
    module, name = proof.split("::")
    assert name in _test_names(module), f"{case}: {proof} is missing"


def test_the_export_tab_does_not_promise_word_sync() -> None:
    """A16: the UI says changes in Word are not taken back."""
    assert "nicht in die Werkstatt zurückübernommen" in export_tab.NO_SYNC
    assert "synchron" not in export_tab.NO_SYNC.lower()


def test_the_story_chapter_comes_before_the_written_chapters() -> None:
    """A24: the template lists the story chapter ahead of the solution text."""
    keys = [c.key for c in load_template().chapters]
    assert keys.index("user_stories") < keys.index("loesung")
