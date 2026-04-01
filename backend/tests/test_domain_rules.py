"""Tests for domain_rules module — verifies category/subcategory-driven generation rules."""

import pytest

from app.services.ai.domain_rules import (
    CATEGORY_SUBCATEGORIES,
    build_domain_context,
    get_domain_rules,
)


class TestCategorySubcategoryHierarchy:
    def test_all_expected_categories_present(self):
        expected = {"tech", "finance", "education", "science", "history", "health",
                    "motivation", "business", "entertainment", "gaming", "lifestyle"}
        assert expected.issubset(set(CATEGORY_SUBCATEGORIES.keys()))

    def test_tech_has_subcategories(self):
        assert len(CATEGORY_SUBCATEGORIES["tech"]) >= 5

    def test_finance_has_subcategories(self):
        assert len(CATEGORY_SUBCATEGORIES["finance"]) >= 3

    def test_tech_subcategories_include_key_areas(self):
        tech_subs = [s.lower() for s in CATEGORY_SUBCATEGORIES["tech"]]
        for required in ["programming", "operating systems", "databases"]:
            assert any(required in s for s in tech_subs), f"Missing subcategory containing '{required}'"


class TestGetDomainRules:
    def test_tech_os_subcategory_returns_specific_rules(self):
        rules = get_domain_rules("tech", "Operating Systems")
        assert "terminal" in rules.visual_vocab.lower() or "linux" in rules.visual_vocab.lower()

    def test_tech_programming_subcategory_returns_specific_rules(self):
        rules = get_domain_rules("tech", "Programming")
        assert "code" in rules.visual_vocab.lower() or "editor" in rules.visual_vocab.lower()

    def test_tech_category_default_returns_rules(self):
        rules = get_domain_rules("tech")
        assert "terminal" in rules.visual_vocab.lower() or "code" in rules.visual_vocab.lower()

    def test_finance_category_avoids_tech_terminals(self):
        rules = get_domain_rules("finance")
        # finance visual vocab should include charts/graphs, not linux terminals
        assert "chart" in rules.visual_vocab.lower() or "graph" in rules.visual_vocab.lower()

    def test_tech_rules_avoid_finance_charts(self):
        rules = get_domain_rules("tech")
        assert "finance" in rules.avoid_visuals.lower() or "trading" in rules.avoid_visuals.lower()

    def test_tech_os_rules_avoid_finance_charts(self):
        rules = get_domain_rules("tech", "Operating Systems")
        assert "finance" in rules.avoid_visuals.lower() or "trading" in rules.avoid_visuals.lower()

    def test_unknown_category_returns_default_rules(self):
        rules = get_domain_rules("unknown_category_xyz")
        assert rules is not None
        assert rules.visual_vocab
        assert rules.script_style

    def test_empty_category_returns_default_rules(self):
        rules = get_domain_rules("")
        assert rules is not None

    def test_case_insensitive_lookup(self):
        rules_lower = get_domain_rules("tech", "operating systems")
        rules_title = get_domain_rules("TECH", "Operating Systems")
        assert rules_lower.visual_vocab == rules_title.visual_vocab

    def test_history_category_has_timeline_visuals(self):
        rules = get_domain_rules("history")
        assert "map" in rules.visual_vocab.lower() or "timeline" in rules.visual_vocab.lower()

    def test_science_category_has_diagram_visuals(self):
        rules = get_domain_rules("science")
        assert "diagram" in rules.visual_vocab.lower()

    def test_health_category_rules_exist(self):
        rules = get_domain_rules("health")
        assert rules.script_style
        assert rules.narration_tone

    def test_all_rules_have_required_fields(self):
        for cat in CATEGORY_SUBCATEGORIES:
            rules = get_domain_rules(cat)
            assert rules.visual_vocab, f"Empty visual_vocab for category '{cat}'"
            assert rules.avoid_visuals, f"Empty avoid_visuals for category '{cat}'"
            assert rules.script_style, f"Empty script_style for category '{cat}'"
            assert rules.narration_tone, f"Empty narration_tone for category '{cat}'"
            assert rules.on_screen_style, f"Empty on_screen_style for category '{cat}'"


class TestBuildDomainContext:
    def test_returns_non_empty_string(self):
        ctx = build_domain_context("tech")
        assert isinstance(ctx, str)
        assert ctx.strip()

    def test_includes_category(self):
        ctx = build_domain_context("tech")
        assert "tech" in ctx.lower()

    def test_includes_subcategory_when_provided(self):
        ctx = build_domain_context("tech", "Operating Systems")
        assert "operating systems" in ctx.lower()

    def test_no_subcategory_line_when_not_provided(self):
        ctx = build_domain_context("finance")
        assert "Subcategory:" not in ctx or "None" not in ctx

    def test_includes_visual_vocab(self):
        ctx = build_domain_context("tech", "Operating Systems")
        assert "terminal" in ctx.lower() or "linux" in ctx.lower()

    def test_includes_avoid_visuals(self):
        ctx = build_domain_context("tech")
        assert "avoid" in ctx.lower() or "finance" in ctx.lower()

    def test_finance_context_mentions_charts(self):
        ctx = build_domain_context("finance")
        assert "chart" in ctx.lower() or "graph" in ctx.lower()

    def test_domain_context_format_has_section_headers(self):
        ctx = build_domain_context("tech", "Programming")
        assert "DOMAIN CONTEXT" in ctx
        assert "Category:" in ctx
        assert "Subcategory:" in ctx


class TestLocalProviderUsesdomainRules:
    """Verify that LocalLLMProvider injects domain-specific visual vocab."""

    def _generate(self, category: str, subcategory: str | None = None, topic: str = "Test topic") -> dict:
        from app.services.llm.local_provider import LocalLLMProvider
        return LocalLLMProvider().generate_script_payload(
            topic=topic,
            category=category,
            audience_level="beginner",
            language_mode="english",
            duration_seconds=60,
            subcategory=subcategory,
        )

    def test_tech_os_segments_contain_terminal_or_linux_vocabulary(self):
        payload = self._generate("tech", "Operating Systems", "Linux Process Management")
        for seg in payload["segments"]:
            vc = seg.get("visual_concept", "").lower()
            # At least one visual concept should reference OS/terminal vocabulary
            if "terminal" in vc or "linux" in vc or "process" in vc or "diagram" in vc:
                return
        pytest.fail("No segment had OS-relevant visual vocabulary for tech/OS category")

    def test_finance_segments_do_not_have_terminal_vocabulary(self):
        payload = self._generate("finance", "Investing", "Compound Interest")
        for seg in payload["segments"]:
            vc = seg.get("visual_concept", "").lower()
            assert "linux terminal" not in vc, (
                f"Finance segment has linux terminal vocabulary: {vc!r}"
            )

    def test_subcategory_stored_in_payload(self):
        payload = self._generate("tech", "Programming")
        assert payload["subcategory"] == "Programming"

    def test_no_subcategory_stored_as_empty_string(self):
        payload = self._generate("tech", None)
        assert payload["subcategory"] == ""

    def test_cta_reflects_category(self):
        payload = self._generate("finance")
        assert "finance" in payload["cta"].lower()
