import logging
from pathlib import Path

from google.cloud import texttospeech

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


class TTSClient:
    """Google Cloud Text-to-Speech client for generating voiceover audio.

    Authentication is handled automatically by the Google Cloud client library
    using the ``GOOGLE_APPLICATION_CREDENTIALS`` environment variable, which
    should point to a service account JSON key file.
    """

    def __init__(self) -> None:
        self._client = texttospeech.TextToSpeechClient()

    def synthesize_speech(self, text: str, language: str, output_path: Path) -> Path:
        """Convert *text* to an MP3 audio file at *output_path*.

        Args:
            text: The narration text to convert to speech.
            language: The application language mode (e.g. ``"te-en"``,
                ``"english"``, ``"telugu"``).
            output_path: Destination path for the generated MP3 file.

        Returns:
            The resolved path to the generated MP3 file.

        Raises:
            google.api_core.exceptions.GoogleAPIError: If the API call fails.
        """
        language_code = _LANGUAGE_CODE_MAP.get(language.lower(), _DEFAULT_LANGUAGE_CODE)

        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
        )

        logger.info(
            "Synthesizing speech: language_code=%s, text_length=%d, output=%s",
            language_code,
            len(text),
            output_path,
        )

        response = self._client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.audio_content)

        logger.info(
            "Saved TTS audio to %s (%d bytes)", output_path, len(response.audio_content)
        )
        return output_path
