"""Tests for LocalLLMProvider — verifies that local fallback produces valid,
visible-content Shorts-format scripts (hook → beats → takeaway)."""

import pytest

from app.services.llm.local_provider import LocalLLMProvider


@pytest.fixture
def provider() -> LocalLLMProvider:
    return LocalLLMProvider()


def _generate(provider: LocalLLMProvider, duration: int = 60) -> dict:
    return provider.generate_script_payload(
        topic="Python decorators",
        category="programming",
        audience_level="beginner",
        language_mode="english",
        duration_seconds=duration,
    )


class TestLocalProviderStructure:
    def test_returns_dict(self, provider):
        payload = _generate(provider)
        assert isinstance(payload, dict)

    def test_required_top_level_keys(self, provider):
        payload = _generate(provider)
        for key in ("title", "hook", "intro", "outro", "full_text", "segments", "cta", "category"):
            assert key in payload, f"Missing key: {key}"

    def test_title_is_non_empty(self, provider):
        payload = _generate(provider)
        assert payload["title"].strip()

    def test_segments_is_list(self, provider):
        payload = _generate(provider)
        assert isinstance(payload["segments"], list)

    def test_segments_count_in_range(self, provider):
        payload = _generate(provider, duration=60)
        # Shorts format: 1 hook + 3-5 beats + 1 takeaway = 5-7 segments
        assert 5 <= len(payload["segments"]) <= 7

    def test_first_segment_is_hook(self, provider):
        payload = _generate(provider)
        assert payload["segments"][0]["purpose"] == "hook"

    def test_last_segment_is_takeaway(self, provider):
        payload = _generate(provider)
        assert payload["segments"][-1]["purpose"] == "takeaway"

    def test_middle_segments_are_beats(self, provider):
        payload = _generate(provider)
        # All segments between hook and takeaway must be beats
        for seg in payload["segments"][1:-1]:
            assert seg["purpose"] == "beat", f"Expected beat, got: {seg['purpose']}"

    def test_no_segment_has_empty_narration(self, provider):
        payload = _generate(provider)
        for seg in payload["segments"]:
            assert seg.get("narration", "").strip(), f"Empty narration in segment: {seg}"

    def test_no_segment_has_empty_on_screen_text(self, provider):
        payload = _generate(provider)
        for seg in payload["segments"]:
            assert seg.get("on_screen_text", "").strip(), f"Empty on_screen_text in segment: {seg}"

    def test_all_segments_have_visual_concept(self, provider):
        """Every segment should include a visual_concept for image generation."""
        payload = _generate(provider)
        for seg in payload["segments"]:
            assert seg.get("visual_concept", "").strip(), (
                f"Missing visual_concept in segment: {seg}"
            )

    def test_no_code_snippet_in_local_segments(self, provider):
        """Local provider must never produce code_snippet — prevents blank code_card scenes."""
        payload = _generate(provider)
        for seg in payload["segments"]:
            assert not seg.get("code_snippet", ""), (
                f"Unexpected code_snippet in local segment: {seg}"
            )

    def test_full_text_is_non_empty(self, provider):
        payload = _generate(provider)
        assert payload["full_text"].strip()

    def test_segment_duration_seconds_positive(self, provider):
        payload = _generate(provider)
        for seg in payload["segments"]:
            assert seg["duration_seconds"] > 0, f"Non-positive duration in segment: {seg}"

    def test_short_on_screen_text(self, provider):
        """on_screen_text should be brief (≤ 10 words) for mobile readability."""
        payload = _generate(provider)
        for seg in payload["segments"]:
            word_count = len(seg.get("on_screen_text", "").split())
            assert word_count <= 10, (
                f"on_screen_text too long ({word_count} words): {seg['on_screen_text']!r}"
            )


class TestLocalProviderVariety:
    def test_beat_segments_have_unique_on_screen_texts(self, provider):
        """Beat templates are selected without replacement, so on_screen texts differ."""
        payload = _generate(provider)
        beat_texts = [
            seg["on_screen_text"]
            for seg in payload["segments"]
            if seg["purpose"] == "beat"
        ]
        assert len(beat_texts) == len(set(beat_texts)), (
            "Beat segments should have unique on_screen_text values (no-replacement selection)"
        )

    def test_different_topics_produce_different_titles(self, provider):
        payload1 = provider.generate_script_payload("Python", "programming", "beginner", "english", 60)
        payload2 = provider.generate_script_payload("Machine Learning", "AI", "beginner", "english", 60)
        assert payload1["title"] != payload2["title"]


class TestLocalProviderDurations:
    @pytest.mark.parametrize("duration", [30, 60, 90, 120])
    def test_valid_segment_count_for_duration(self, provider, duration):
        payload = provider.generate_script_payload(
            topic="Test topic",
            category="general",
            audience_level="beginner",
            language_mode="english",
            duration_seconds=duration,
        )
        # Shorts format: 5-7 segments (1 hook + 3-5 beats + 1 takeaway)
        assert 5 <= len(payload["segments"]) <= 7
