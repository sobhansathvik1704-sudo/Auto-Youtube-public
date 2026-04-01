"""Unit tests for text deduplication and normalisation logic in create_scene_image.

These tests validate the normalisation + show/hide header decisions in isolation
without requiring real fonts, images, or external services.  They mirror the
logic in the ``_norm`` helper and ``show_header`` derivation inside
``create_scene_image``.
"""

import pytest


# ---------------------------------------------------------------------------
# Reproduce the normalisation helper from create_scene_image so that these
# tests are self-contained and stable.  The helper is defined as a nested
# function inside create_scene_image (per the constraint of not adding new
# module-level helpers), so it cannot be imported directly.  Any change to
# the production helper must be reflected here.
# ---------------------------------------------------------------------------

def _norm(t: str) -> str:
    """Lowercase → strip non-alphanumeric → collapse whitespace."""
    lowered = t.lower()
    alphanum = "".join(ch if ch.isalnum() or ch == " " else " " for ch in lowered)
    return " ".join(alphanum.split())


def _show_header(scene_type: str, body_text: str) -> bool:
    """Return True when the scene-type badge should be rendered."""
    scene_label = scene_type.replace("_", " ").title()
    norm_label = _norm(scene_label)
    norm_body = _norm(body_text)
    return (
        bool(norm_label)
        and bool(norm_body)
        and norm_label not in norm_body
        and norm_body not in norm_label
    )


# ---------------------------------------------------------------------------
# Normalisation tests
# ---------------------------------------------------------------------------

class TestNorm:
    def test_lowercase(self):
        assert _norm("Hello World") == "hello world"

    def test_strips_punctuation(self):
        assert _norm("User Space vs. Kernel Space") == "user space vs kernel space"

    def test_collapses_whitespace(self):
        assert _norm("  two   spaces  ") == "two spaces"

    def test_strips_colons_and_hyphens(self):
        assert _norm("RAM: Control-Flow") == "ram control flow"

    def test_empty_string(self):
        assert _norm("") == ""

    def test_only_punctuation(self):
        assert _norm("...!!!") == ""

    def test_mixed(self):
        # The key acceptance-criteria phrase from the issue
        assert _norm("User Space vs. Kernel Space") == "user space vs kernel space"
        assert _norm("Bullet Explainer") == "bullet explainer"


# ---------------------------------------------------------------------------
# show_header dedupe decisions
# ---------------------------------------------------------------------------

class TestShowHeader:
    # Acceptance-criteria case from the issue report -------------------------

    def test_different_label_and_body_shows_header(self):
        """'Bullet Explainer' vs 'User Space vs. Kernel Space' → different → show badge."""
        assert _show_header("bullet_explainer", "User Space vs. Kernel Space") is True

    def test_identical_normalised_label_and_body_hides_header(self):
        """When normalised forms are equal, badge is hidden."""
        assert _show_header("content", "Content") is False

    # Substring containment -------------------------------------------------

    def test_label_substring_of_body_hides_header(self):
        """'Title Card' appears inside body text → hide badge."""
        assert _show_header("title_card", "title card explains everything") is False

    def test_body_substring_of_label_hides_header(self):
        """Body text is fully contained in the label → hide badge."""
        assert _show_header("user_space_vs_kernel_space", "User Space") is False

    # Punctuation differences should not fool the check ----------------------

    def test_punctuation_difference_still_deduplicates(self):
        """'RAM: Control' body vs 'Ram Control' normalise the same → hide."""
        assert _show_header("ram_control", "RAM: Control") is False

    def test_case_difference_still_deduplicates(self):
        assert _show_header("intro", "Intro") is False

    # Empty text edge cases --------------------------------------------------

    def test_empty_body_hides_header(self):
        assert _show_header("bullet_explainer", "") is False

    def test_empty_scene_type_hides_header(self):
        # Degenerate: scene_type shouldn't be empty in production, but guard it.
        assert _show_header("", "Some body text") is False

    # Independent labels and bodies always show header -----------------------

    @pytest.mark.parametrize("scene_type,body", [
        ("icon_compare", "Memory Management Explained"),
        ("bullet_explainer", "User Space vs. Kernel Space"),
        ("outro", "Subscribe for more content"),
        ("intro", "Welcome to this deep dive"),
    ])
    def test_independent_label_and_body_shows_header(self, scene_type, body):
        assert _show_header(scene_type, body) is True
