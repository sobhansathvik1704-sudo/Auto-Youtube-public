"""Google Gemini LLM provider.

Free tier: 15 requests/minute, 1500 requests/day.
Get a free API key at https://aistudio.google.com/apikey
"""

import json
import logging
import re
import time

from app.core.config import get_settings
from app.services.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2  # retries for genuine (non-zero) rate limits
_DEFAULT_RETRY_DELAY = 5  # fallback delay when no retry_delay in response
_RETRY_BUFFER_SECONDS = 1  # added buffer on top of the suggested retry delay
_MAX_RETRY_DELAY = 60  # cap on retry delay seconds


def _parse_retry_seconds(error_str: str) -> int:
    """Extract the suggested retry delay (seconds) from a Gemini 429 error message.

    Example error text: "Please retry in 51.386095894s"
    Returns the suggested seconds capped at _MAX_RETRY_DELAY, or *_DEFAULT_RETRY_DELAY* if not found.
    """
    match = re.search(r"retry in\s+([\d.]+)s", error_str, re.IGNORECASE)
    if match:
        return min(int(float(match.group(1))) + _RETRY_BUFFER_SECONDS, _MAX_RETRY_DELAY)
    return _DEFAULT_RETRY_DELAY


class GeminiLLMProvider(BaseLLMProvider):
    """LLM provider backed by Google Gemini (free tier)."""

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is not configured. "
                "Get a free key at https://aistudio.google.com/apikey and set it in .env."
            )
        try:
            from google import genai  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "google-genai package is required for the Gemini provider. "
                "Install it with: pip install google-genai"
            ) from exc

        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._settings = settings

    def generate_script_payload(
        self,
        topic: str,
        category: str,
        audience_level: str,
        language_mode: str,
        duration_seconds: int,
    ) -> dict:
        from app.services.ai.prompts import SCRIPT_SYSTEM_PROMPT, SCRIPT_USER_PROMPT_TEMPLATE  # noqa: PLC0415
        from google.genai import types  # noqa: PLC0415

        user_prompt = SCRIPT_USER_PROMPT_TEMPLATE.format(
            topic=topic,
            niche=category,
            language=language_mode,
            duration_seconds=duration_seconds,
            audience_level=audience_level,
        )

        full_prompt = f"{SCRIPT_SYSTEM_PROMPT}\n\n{user_prompt}"

        logger.info(
            "Requesting script from Gemini model=%s topic=%r category=%r language=%s audience_level=%s",
            self._settings.gemini_model_name,
            topic,
            category,
            language_mode,
            audience_level,
        )

        last_exc: Exception | None = None
        raw_content: str = ""
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = self._client.models.generate_content(
                    model=self._settings.gemini_model_name,
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.7,
                        response_mime_type="application/json",
                    ),
                )
                raw_content = response.text or ""
                break
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                error_str = str(exc)
                error_lower = error_str.lower()

                if "rate" in error_lower or "quota" in error_lower or "429" in error_str:
                    # Check for quota=0 — retrying is pointless
                    if re.search(r"limit:\s*0", error_str):
                        logger.error(
                            "Gemini quota is 0 — your API key may not have free tier enabled. "
                            "Get a new key from https://aistudio.google.com/apikey "
                            "(NOT from Google Cloud Console). "
                            "Falling back to local templates."
                        )
                        return self._local_fallback(
                            topic, category, audience_level, language_mode, duration_seconds
                        )

                    retry_delay = _parse_retry_seconds(error_str)
                    logger.warning(
                        "Gemini rate limit on attempt %d/%d: %s — retrying in %ds",
                        attempt,
                        _MAX_RETRIES,
                        exc,
                        retry_delay,
                    )
                    time.sleep(retry_delay)
                else:
                    logger.error("Gemini API error: %s", exc)
                    break
        else:
            logger.error(
                "Gemini provider failed after %d attempts (%s) — falling back to local templates",
                _MAX_RETRIES,
                last_exc,
            )
            return self._local_fallback(topic, category, audience_level, language_mode, duration_seconds)

        if last_exc is not None and not raw_content:
            logger.error("Gemini provider error: %s — falling back to local templates", last_exc)
            return self._local_fallback(topic, category, audience_level, language_mode, duration_seconds)

        logger.debug("Raw Gemini response: %s", raw_content)

        # Strip markdown fences that some models add despite the mime type setting
        cleaned = raw_content.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error(
                "Gemini returned non-JSON content: %r — falling back to local templates. Error: %s",
                raw_content,
                exc,
            )
            return self._local_fallback(topic, category, audience_level, language_mode, duration_seconds)

        self._normalise_payload(payload, topic, category, language_mode, duration_seconds)
        return payload

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_payload(
        payload: dict,
        topic: str,
        category: str,
        language: str,
        duration_seconds: int,
    ) -> None:
        """Ensure the payload has all required fields with safe defaults."""
        payload.setdefault("title", topic)
        payload.setdefault("title_options", [payload["title"]])
        payload.setdefault("hook", "")
        payload.setdefault("intro", "")
        payload.setdefault("outro", "")
        payload.setdefault("cta", payload.get("outro", ""))
        payload.setdefault("language_mode", language)
        payload.setdefault("estimated_duration_seconds", duration_seconds)
        payload.setdefault("category", category)

        segments = payload.get("segments", [])
        if not isinstance(segments, list):
            segments = []
            payload["segments"] = segments

        current = 0
        for idx, seg in enumerate(segments):
            seg.setdefault("order", idx + 1)
            seg.setdefault("purpose", "beat")
            seg.setdefault("narration", "")
            seg.setdefault("on_screen_text", "")
            seg.setdefault("visual_concept", "")
            seg_duration = int(seg.get("duration_seconds", 4))
            seg["duration_seconds"] = seg_duration
            seg["start_seconds"] = current
            seg["end_seconds"] = current + seg_duration
            current += seg_duration

        if not payload.get("full_text"):
            parts = [
                payload.get("hook", ""),
                payload.get("intro", ""),
                *[s.get("narration", "") for s in segments],
                payload.get("outro", ""),
            ]
            payload["full_text"] = " ".join(p for p in parts if p)

    @staticmethod
    def _local_fallback(
        topic: str,
        category: str,
        audience_level: str,
        language_mode: str,
        duration_seconds: int,
    ) -> dict:
        from app.services.llm.local_provider import LocalLLMProvider  # noqa: PLC0415

        return LocalLLMProvider().generate_script_payload(
            topic=topic,
            category=category,
            audience_level=audience_level,
            language_mode=language_mode,
            duration_seconds=duration_seconds,
        )
