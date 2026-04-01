"""Tests for SEOGenerator — verifies provider selection and fallback chain."""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.seo.generator import SEOGenerator, _SEO_PROMPT_TEMPLATE

_SAMPLE_SEO = {
    "title": "Python Decorators - Complete Guide",
    "description": "Learn all about Python decorators in this comprehensive tutorial.",
    "tags": ["python", "decorators", "tutorial"],
    "hashtags": ["#python", "#tutorial"],
    "category_id": 28,
}


@pytest.fixture
def generator() -> SEOGenerator:
    return SEOGenerator()


def _make_settings(llm_provider="local", gemini_api_key=None, openai_api_key=None):
    s = MagicMock()
    s.llm_provider = llm_provider
    s.gemini_api_key = gemini_api_key
    s.openai_api_key = openai_api_key
    s.gemini_model_name = "gemini-2.0-flash"
    s.openai_model_name = "gpt-4o"
    return s


# ---------------------------------------------------------------------------
# Local provider path
# ---------------------------------------------------------------------------

class TestLocalPath:
    def test_local_provider_returns_dict(self, generator):
        with patch("app.services.seo.generator.get_settings", return_value=_make_settings(llm_provider="local")):
            result = generator.generate_seo_metadata("Python decorators", "A script about decorators", "tech")
        assert isinstance(result, dict)

    def test_local_provider_required_keys(self, generator):
        with patch("app.services.seo.generator.get_settings", return_value=_make_settings(llm_provider="local")):
            result = generator.generate_seo_metadata("Python decorators", "summary", "tech")
        for key in ("title", "description", "tags", "hashtags", "category_id"):
            assert key in result, f"Missing key: {key}"

    def test_local_provider_title_contains_topic(self, generator):
        with patch("app.services.seo.generator.get_settings", return_value=_make_settings(llm_provider="local")):
            result = generator.generate_seo_metadata("Machine Learning", "summary", "ai")
        assert "Machine Learning" in result["title"]

    def test_local_provider_tags_is_list(self, generator):
        with patch("app.services.seo.generator.get_settings", return_value=_make_settings(llm_provider="local")):
            result = generator.generate_seo_metadata("Docker", "summary", "devops")
        assert isinstance(result["tags"], list)

    def test_local_provider_hashtags_is_list(self, generator):
        with patch("app.services.seo.generator.get_settings", return_value=_make_settings(llm_provider="local")):
            result = generator.generate_seo_metadata("Docker", "summary", "devops")
        assert isinstance(result["hashtags"], list)

    def test_local_fallback_directly(self, generator):
        result = generator._local_fallback("React", "frontend")
        assert result["title"] == "React - Complete Guide"
        assert result["category_id"] == 28
        assert "#React" in result["hashtags"]


# ---------------------------------------------------------------------------
# Gemini provider path
# ---------------------------------------------------------------------------

class TestGeminiPath:
    def test_gemini_returns_result_when_successful(self, generator):
        settings = _make_settings(llm_provider="gemini", gemini_api_key="test-key")

        with patch("app.services.seo.generator.get_settings", return_value=settings):
            with patch.object(generator, "_generate_with_gemini", return_value=_SAMPLE_SEO) as mock_gemini:
                result = generator.generate_seo_metadata("Python decorators", "script summary", "tech")
                mock_gemini.assert_called_once()

        assert result == _SAMPLE_SEO

    def test_gemini_strips_markdown_fences(self, generator):
        settings = _make_settings(llm_provider="gemini", gemini_api_key="test-key")
        fenced_json = f"```json\n{json.dumps(_SAMPLE_SEO)}\n```"
        mock_response = MagicMock()
        mock_response.text = fenced_json

        with patch("app.services.seo.generator.get_settings", return_value=settings):
            with patch("google.genai.Client") as mock_client_cls:
                mock_client = MagicMock()
                mock_client_cls.return_value = mock_client
                mock_client.models.generate_content.return_value = mock_response

                with patch("google.genai.types") as mock_types:
                    result = generator._generate_with_gemini("prompt", settings)

        assert result == _SAMPLE_SEO

    def test_gemini_returns_none_on_exception(self, generator):
        settings = _make_settings(llm_provider="gemini", gemini_api_key="test-key")

        with patch("app.services.seo.generator.get_settings", return_value=settings):
            with patch("google.genai.Client", side_effect=Exception("API error")):
                result = generator._generate_with_gemini("prompt", settings)

        assert result is None

    def test_gemini_skipped_when_no_api_key(self, generator):
        settings = _make_settings(llm_provider="gemini", gemini_api_key=None, openai_api_key=None)

        with patch("app.services.seo.generator.get_settings", return_value=settings):
            with patch.object(generator, "_generate_with_gemini") as mock_gemini:
                with patch.object(generator, "_generate_with_openai") as mock_openai:
                    result = generator.generate_seo_metadata("Topic", "summary", "tech")
                    mock_gemini.assert_not_called()
                    mock_openai.assert_not_called()

        # Should fall through to local fallback
        assert "title" in result


# ---------------------------------------------------------------------------
# OpenAI provider path
# ---------------------------------------------------------------------------

class TestOpenAIPath:
    def test_openai_returns_result_when_successful(self, generator):
        settings = _make_settings(llm_provider="openai", openai_api_key="sk-test")

        with patch("app.services.seo.generator.get_settings", return_value=settings):
            with patch.object(generator, "_generate_with_openai", return_value=_SAMPLE_SEO) as mock_openai:
                result = generator.generate_seo_metadata("Python decorators", "script summary", "tech")
                mock_openai.assert_called_once()

        assert result == _SAMPLE_SEO

    def test_openai_returns_none_on_exception(self, generator):
        settings = _make_settings(llm_provider="openai", openai_api_key="sk-test")

        with patch("app.services.seo.generator.get_settings", return_value=settings):
            with patch("openai.OpenAI", side_effect=Exception("quota exceeded")):
                result = generator._generate_with_openai("prompt", settings)

        assert result is None

    def test_openai_uses_configured_model_name(self, generator):
        settings = _make_settings(llm_provider="openai", openai_api_key="sk-test")
        settings.openai_model_name = "gpt-4-turbo"

        mock_message = MagicMock()
        mock_message.content = json.dumps(_SAMPLE_SEO)
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]
        mock_openai_client = MagicMock()
        mock_openai_client.chat.completions.create.return_value = mock_completion

        with patch("app.services.seo.generator.get_settings", return_value=settings):
            with patch("openai.OpenAI", return_value=mock_openai_client):
                result = generator._generate_with_openai("prompt", settings)

        mock_openai_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_openai_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["model"] == "gpt-4-turbo"
        assert result == _SAMPLE_SEO


# ---------------------------------------------------------------------------
# Fallback chain
# ---------------------------------------------------------------------------

class TestFallbackChain:
    def test_gemini_fails_falls_back_to_openai(self, generator):
        settings = _make_settings(llm_provider="gemini", gemini_api_key="test-key", openai_api_key="sk-test")

        with patch("app.services.seo.generator.get_settings", return_value=settings):
            with patch.object(generator, "_generate_with_gemini", return_value=None):
                with patch.object(generator, "_generate_with_openai", return_value=_SAMPLE_SEO) as mock_openai:
                    result = generator.generate_seo_metadata("Topic", "summary", "tech")
                    mock_openai.assert_called_once()

        assert result == _SAMPLE_SEO

    def test_gemini_and_openai_fail_falls_back_to_local(self, generator):
        settings = _make_settings(llm_provider="gemini", gemini_api_key="test-key", openai_api_key="sk-test")

        with patch("app.services.seo.generator.get_settings", return_value=settings):
            with patch.object(generator, "_generate_with_gemini", return_value=None):
                with patch.object(generator, "_generate_with_openai", return_value=None):
                    result = generator.generate_seo_metadata("Kubernetes", "script summary", "devops")

        for key in ("title", "description", "tags", "hashtags", "category_id"):
            assert key in result

    def test_openai_fails_falls_back_to_local(self, generator):
        settings = _make_settings(llm_provider="openai", openai_api_key="sk-test")

        with patch("app.services.seo.generator.get_settings", return_value=settings):
            with patch.object(generator, "_generate_with_openai", return_value=None):
                result = generator.generate_seo_metadata("React hooks", "summary", "frontend")

        assert "title" in result
        assert "React hooks" in result["title"]


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

class TestPromptTemplate:
    def test_prompt_template_contains_topic(self):
        prompt = _SEO_PROMPT_TEMPLATE.format(
            topic="Python decorators",
            category="programming",
            script_summary="A script about decorators",
        )
        assert "Python decorators" in prompt

    def test_prompt_template_requests_json(self):
        prompt = _SEO_PROMPT_TEMPLATE.format(
            topic="Docker",
            category="devops",
            script_summary="Docker tutorial",
        )
        assert "JSON" in prompt
