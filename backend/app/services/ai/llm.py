import json
import logging

from openai import OpenAI, OpenAIError

from app.core.config import get_settings
from app.services.ai.prompts import SCRIPT_SYSTEM_PROMPT, SCRIPT_USER_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)

_DEFAULT_DURATION_SECONDS = 60


class LLMClient:
    """OpenAI-backed client for generating structured video scripts."""

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is not configured. "
                "Set it in your .env file or environment before using the OpenAI provider."
            )
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model_name

    def generate_script_from_topic(
        self,
        topic: str,
        niche: str,
        language: str,
        duration_seconds: int = _DEFAULT_DURATION_SECONDS,
        audience_level: str = "beginner",
    ) -> dict:
        """Call the OpenAI API and return a structured script payload dict.

        Args:
            topic: The video topic (e.g. "Python decorators").
            niche: The content niche / category (e.g. "programming").
            language: Language mode – "telugu_english", "english", or "telugu".
            duration_seconds: Approximate target video duration in seconds.
            audience_level: Target audience expertise (e.g. "beginner", "intermediate").

        Returns:
            A dict matching the script JSON schema defined in prompts.py.

        Raises:
            OpenAIError: If the API call fails.
            ValueError: If the API response cannot be parsed as valid JSON.
        """
        user_prompt = SCRIPT_USER_PROMPT_TEMPLATE.format(
            topic=topic,
            niche=niche,
            language=language,
            duration_seconds=duration_seconds,
            audience_level=audience_level,
        )

        logger.info(
            "Requesting script from OpenAI model=%s topic=%r niche=%r language=%s audience_level=%s",
            self._model,
            topic,
            niche,
            language,
            audience_level,
        )

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": SCRIPT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                response_format={"type": "json_object"},
            )
        except OpenAIError as exc:
            logger.error("OpenAI API error: %s", exc)
            raise

        raw_content = response.choices[0].message.content or ""
        logger.debug("Raw OpenAI response: %s", raw_content)

        try:
            payload = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"OpenAI returned non-JSON content: {raw_content!r}"
            ) from exc

        self._normalise_payload(payload, topic, niche, language, duration_seconds)
        return payload

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_payload(
        payload: dict,
        topic: str,
        niche: str,
        language: str,
        duration_seconds: int,
    ) -> None:
        """Fill in any missing fields with safe defaults so the rest of the
        pipeline can rely on a consistent structure."""
        payload.setdefault("title", topic)
        payload.setdefault("title_options", [payload["title"]])
        payload.setdefault("hook", "")
        payload.setdefault("intro", "")
        payload.setdefault("outro", "")
        payload.setdefault("cta", payload.get("outro", ""))
        payload.setdefault("language_mode", language)
        payload.setdefault("estimated_duration_seconds", duration_seconds)
        payload.setdefault("category", niche)

        segments = payload.get("segments", [])
        if not isinstance(segments, list):
            segments = []
            payload["segments"] = segments

        # Ensure start/end seconds are populated
        current = 0
        for idx, seg in enumerate(segments):
            seg.setdefault("order", idx + 1)
            seg.setdefault("purpose", "explanation")
            seg.setdefault("narration", "")
            seg.setdefault("on_screen_text", "")
            seg_duration = int(seg.get("duration_seconds", 10))
            seg["duration_seconds"] = seg_duration
            seg["start_seconds"] = current
            seg["end_seconds"] = current + seg_duration
            current += seg_duration

        # Build full_text if not provided
        if not payload.get("full_text"):
            parts = [
                payload.get("hook", ""),
                payload.get("intro", ""),
                *[s.get("narration", "") for s in segments],
                payload.get("outro", ""),
            ]
            payload["full_text"] = " ".join(p for p in parts if p)
