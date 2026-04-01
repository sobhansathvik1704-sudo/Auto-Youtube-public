import logging
from pathlib import Path

from google.cloud import texttospeech

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Map from application language_mode values to BCP-47 language codes used by
# Google Cloud Text-to-Speech.  For Telugu-English code-switching we pick
# Indian English ("en-IN") because it handles the bilingual narration best.
_LANGUAGE_CODE_MAP: dict[str, str] = {
    "te-en": "en-IN",
    "telugu_english": "en-IN",
    "english": "en-US",
    "en": "en-US",
    "en-us": "en-US",
    "telugu": "te-IN",
    "te": "te-IN",
    "te-in": "te-IN",
}

_DEFAULT_LANGUAGE_CODE = "en-US"

# Best voices per language — ordered by quality (Journey > Neural2 > WaveNet > Standard)
# These are the most natural-sounding voices for YouTube narration.
_VOICE_PREFERENCES: dict[str, list[str]] = {
    # Indian English — great for Telugu+English code-switching.
    # Journey voices are the most expressive and handle Indian accents/slang best.
    "en-IN": [
        "en-IN-Journey-D",      # Female, most expressive — best for Indian accent/slang
        "en-IN-Journey-F",      # Female, warm and natural Journey voice
        "en-IN-Neural2-D",      # Female Neural2 fallback, very natural
        "en-IN-Neural2-A",      # Female Neural2, clear and warm
        "en-IN-Neural2-B",      # Male Neural2, conversational
        "en-IN-Neural2-C",      # Male Neural2, authoritative
        "en-IN-Wavenet-D",      # Female WaveNet fallback
        "en-IN-Wavenet-B",      # Male WaveNet fallback
    ],
    # American English — best overall quality
    "en-US": [
        "en-US-Neural2-D",      # Male, warm and natural — best for tech narration
        "en-US-Neural2-J",      # Male, conversational
        "en-US-Neural2-E",      # Female, clear and engaging
        "en-US-Neural2-C",      # Female, warm
        "en-US-Neural2-F",      # Female, gentle
        "en-US-Neural2-A",      # Male, authoritative
        "en-US-Wavenet-D",      # Male fallback
        "en-US-Wavenet-F",      # Female fallback
    ],
    # Telugu
    "te-IN": [
        "te-IN-Standard-A",    # Female
        "te-IN-Standard-B",    # Male
    ],
}


class TTSClient:
    """Google Cloud Text-to-Speech client with Journey and Neural2 voice support.

    Uses the highest quality voices available for natural, human-like narration
    optimized for YouTube content. For Indian English the newer Journey voices
    (``en-IN-Journey-D``, ``en-IN-Journey-F``) are preferred because they handle
    Indian accents and code-switching slang far more expressively than Neural2.
    Falls back gracefully through voice quality tiers if the preferred voice is
    unavailable.

    Authentication is handled automatically by the Google Cloud client library
    using the ``GOOGLE_APPLICATION_CREDENTIALS`` environment variable, which
    should point to a service account JSON key file.
    """

    def __init__(self) -> None:
        self._client = texttospeech.TextToSpeechClient()
        self._settings = get_settings()

    def synthesize_speech(self, text: str, language: str, output_path: Path) -> Path:
        """Convert *text* to a high-quality MP3 audio file at *output_path*.

        Uses Journey voices (for Indian English) and Neural2 voices for near-human
        narration quality, with automatic fallback to WaveNet and Standard voices
        if needed.

        Args:
            text: The narration text to convert to speech.
            language: The application language mode (e.g. ``"te-en"``,
                ``"english"``, ``"telugu"``).
            output_path: Destination path for the generated MP3 file.

        Returns:
            The resolved path to the generated MP3 file.

        Raises:
            google.api_core.exceptions.GoogleAPIError: If the API call fails
                and all fallback voices are exhausted.
        """
        language_code = _LANGUAGE_CODE_MAP.get(language.lower(), _DEFAULT_LANGUAGE_CODE)

        synthesis_input = texttospeech.SynthesisInput(text=text)

        # Build voice selection — try configured voice, then best available
        voice = self._select_voice(language_code)

        # Use the voice's actual language_code for fallback lookup so that,
        # e.g., a configured "en-IN-Neural2-B" voice (language_code="en-IN")
        # falls back through the en-IN preference list instead of en-US.
        actual_language_code = voice.language_code

        # YouTube-optimized audio config
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=self._settings.tts_speaking_rate,  # Configurable pace
            pitch=0.0,               # Natural pitch (-20.0 to 20.0)
            # Audio effects profile optimized for video/headphone playback
            effects_profile_id=["headphone-class-device"],
        )

        logger.info(
            "Synthesizing speech: voice=%s, language_code=%s, text_length=%d, output=%s",
            voice.name or "auto",
            actual_language_code,
            len(text),
            output_path,
        )

        # Try with preferred voice, fall back on error
        response = self._synthesize_with_fallback(
            synthesis_input, voice, audio_config, actual_language_code
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.audio_content)

        logger.info(
            "Saved TTS audio to %s (%d bytes)", output_path, len(response.audio_content)
        )
        return output_path

    def _select_voice(self, language_code: str) -> texttospeech.VoiceSelectionParams:
        """Select the best voice for the given language.

        Priority:
        1. User-configured voice name (TTS_VOICE setting, if it looks like a named voice)
        2. First voice in the preference list for this language
        3. Generic fallback with NEUTRAL gender
        """
        configured_voice = self._settings.tts_voice

        # If user configured a specific named voice (e.g., "en-IN-Neural2-B")
        if configured_voice and "-" in configured_voice and configured_voice.count("-") >= 2:
            # Extract the language code from the voice name itself so it always
            # matches: "en-IN-Neural2-B" → "en-IN", "en-US-Neural2-D" → "en-US"
            voice_lang = "-".join(configured_voice.split("-")[:2])
            logger.debug("Using configured TTS voice: %s (language: %s)", configured_voice, voice_lang)
            return texttospeech.VoiceSelectionParams(
                language_code=voice_lang,
                name=configured_voice,
            )

        # Use the best voice from our preference list
        preferences = _VOICE_PREFERENCES.get(language_code, [])
        if preferences:
            voice_name = preferences[0]
            logger.debug("Using preferred voice: %s for language %s", voice_name, language_code)
            return texttospeech.VoiceSelectionParams(
                language_code=language_code,
                name=voice_name,
            )

        # Generic fallback
        return texttospeech.VoiceSelectionParams(
            language_code=language_code,
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
        )

    def _synthesize_with_fallback(
        self,
        synthesis_input: texttospeech.SynthesisInput,
        voice: texttospeech.VoiceSelectionParams,
        audio_config: texttospeech.AudioConfig,
        language_code: str,
    ) -> texttospeech.SynthesizeSpeechResponse:
        """Try synthesis with the preferred voice, falling back through alternatives."""

        # First try: preferred voice
        try:
            return self._client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config,
            )
        except Exception as exc:
            logger.warning(
                "Preferred voice %s failed: %s — trying fallback voices",
                voice.name,
                exc,
            )

        # Try each fallback voice in the preference list
        preferences = _VOICE_PREFERENCES.get(language_code, [])
        tried_voice = voice.name
        for fallback_name in preferences:
            if fallback_name == tried_voice:
                continue
            try:
                fallback_voice = texttospeech.VoiceSelectionParams(
                    language_code=language_code,
                    name=fallback_name,
                )
                response = self._client.synthesize_speech(
                    input=synthesis_input,
                    voice=fallback_voice,
                    audio_config=audio_config,
                )
                logger.info("Successfully used fallback voice: %s", fallback_name)
                return response
            except Exception as exc:
                logger.debug("Fallback voice %s failed: %s", fallback_name, exc)

        # Last resort: generic voice without specific name
        logger.warning("All named voices failed for %s, using generic fallback", language_code)
        generic_voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
        )
        # Remove effects profile for maximum compatibility
        basic_audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
        )
        return self._client.synthesize_speech(
            input=synthesis_input,
            voice=generic_voice,
            audio_config=basic_audio_config,
        )
