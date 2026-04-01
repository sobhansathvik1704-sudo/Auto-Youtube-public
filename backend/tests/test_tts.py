"""Tests for TTSClient — verifies voice/language_code matching and fallback chain."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.ai.tts import TTSClient, _LANGUAGE_CODE_MAP, _VOICE_PREFERENCES


def _make_settings(tts_voice="", tts_speaking_rate=1.0):
    s = MagicMock()
    s.tts_voice = tts_voice
    s.tts_speaking_rate = tts_speaking_rate
    return s


@pytest.fixture
def tts_client():
    """TTSClient with a mocked Google Cloud TTS client."""
    with patch("app.services.ai.tts.texttospeech.TextToSpeechClient"):
        with patch("app.services.ai.tts.get_settings", return_value=_make_settings()):
            client = TTSClient()
    return client


# ---------------------------------------------------------------------------
# _select_voice — language code extraction from configured voice name
# ---------------------------------------------------------------------------

class TestSelectVoice:
    def test_configured_indian_english_voice_uses_en_in_language_code(self, tts_client):
        """en-IN-Neural2-B should produce language_code='en-IN', not the map default."""
        tts_client._settings = _make_settings(tts_voice="en-IN-Neural2-B")
        voice = tts_client._select_voice("en-US")  # map gave en-US, but voice is en-IN
        assert voice.language_code == "en-IN"
        assert voice.name == "en-IN-Neural2-B"

    def test_configured_us_english_voice_uses_en_us_language_code(self, tts_client):
        tts_client._settings = _make_settings(tts_voice="en-US-Neural2-D")
        voice = tts_client._select_voice("en-IN")  # even if map says en-IN
        assert voice.language_code == "en-US"
        assert voice.name == "en-US-Neural2-D"

    def test_configured_telugu_voice_uses_te_in_language_code(self, tts_client):
        tts_client._settings = _make_settings(tts_voice="te-IN-Standard-A")
        voice = tts_client._select_voice("en-US")
        assert voice.language_code == "te-IN"
        assert voice.name == "te-IN-Standard-A"

    def test_no_configured_voice_uses_preference_list(self, tts_client):
        tts_client._settings = _make_settings(tts_voice="")
        voice = tts_client._select_voice("en-IN")
        assert voice.language_code == "en-IN"
        assert voice.name == _VOICE_PREFERENCES["en-IN"][0]

    def test_no_configured_voice_uses_generic_fallback_for_unknown_lang(self, tts_client):
        tts_client._settings = _make_settings(tts_voice="")
        voice = tts_client._select_voice("xx-XX")
        assert voice.language_code == "xx-XX"
        # Generic fallback: no name, only ssml_gender
        assert not voice.name


# ---------------------------------------------------------------------------
# synthesize_speech — actual_language_code passed to _synthesize_with_fallback
# ---------------------------------------------------------------------------

class TestSynthesizeSpeechLanguageCode:
    def test_synthesize_uses_voice_language_code_not_map_language(self, tts_client, tmp_path):
        """When TTS_VOICE=en-IN-Neural2-B but job language maps to en-US, the
        fallback chain must use en-IN (from the voice), not en-US (from the map)."""
        tts_client._settings = _make_settings(tts_voice="en-IN-Neural2-B")
        output = tmp_path / "out.mp3"

        mock_response = MagicMock()
        mock_response.audio_content = b"fake-mp3-data"

        with patch.object(tts_client, "_synthesize_with_fallback", return_value=mock_response) as mock_fallback:
            tts_client.synthesize_speech("Hello world", "english", output)

        # The language_code arg passed to _synthesize_with_fallback must be "en-IN"
        _, _, _, lang_arg = mock_fallback.call_args.args
        assert lang_arg == "en-IN", (
            f"Expected 'en-IN' (from voice name), got '{lang_arg}'. "
            "The fallback chain would incorrectly use the en-US voice list."
        )

    def test_synthesize_uses_map_language_code_when_no_configured_voice(self, tts_client, tmp_path):
        """Without TTS_VOICE set, language_code from the map should drive everything."""
        tts_client._settings = _make_settings(tts_voice="")
        output = tmp_path / "out.mp3"

        mock_response = MagicMock()
        mock_response.audio_content = b"fake-mp3-data"

        with patch.object(tts_client, "_synthesize_with_fallback", return_value=mock_response) as mock_fallback:
            tts_client.synthesize_speech("Hello world", "te-en", output)

        _, _, _, lang_arg = mock_fallback.call_args.args
        assert lang_arg == "en-IN"  # te-en → en-IN per _LANGUAGE_CODE_MAP


# ---------------------------------------------------------------------------
# Language code map
# ---------------------------------------------------------------------------

class TestLanguageCodeMap:
    def test_te_en_maps_to_en_in(self):
        assert _LANGUAGE_CODE_MAP["te-en"] == "en-IN"

    def test_english_maps_to_en_us(self):
        assert _LANGUAGE_CODE_MAP["english"] == "en-US"

    def test_telugu_maps_to_te_in(self):
        assert _LANGUAGE_CODE_MAP["telugu"] == "te-IN"
