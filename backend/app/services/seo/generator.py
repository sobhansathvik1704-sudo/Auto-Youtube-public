import json
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# The SEO prompt — shared between providers
_SEO_PROMPT_TEMPLATE = """Generate SEO-optimized YouTube metadata for a video about: "{topic}"
Category: {category}
Script summary (first 500 chars): {script_summary}

Return a JSON object with:
- "title": YouTube title (max 100 chars, include main keyword, engaging, click-worthy)
- "description": YouTube description (300-500 words, include keywords naturally, add timestamps placeholder, include call-to-action, relevant links section)
- "tags": Array of 15-20 relevant tags (mix of broad and specific)
- "hashtags": Array of 3-5 hashtags (most relevant)
- "category_id": YouTube category ID number (e.g., 28 for Science & Tech, 27 for Education)

Make it optimized for YouTube search and discovery. Use proven SEO techniques.
Return ONLY valid JSON, no other text."""


class SEOGenerator:
    def generate_seo_metadata(self, topic: str, script_summary: str, category: str = "tech") -> dict:
        """Generate SEO-optimized YouTube metadata using the configured LLM provider."""
        settings = get_settings()

        if settings.llm_provider == "local":
            return self._local_fallback(topic, category)

        prompt = _SEO_PROMPT_TEMPLATE.format(
            topic=topic,
            category=category,
            script_summary=script_summary[:500],
        )

        # Try Gemini first (when configured), then OpenAI, then local fallback
        if settings.llm_provider == "gemini" and settings.gemini_api_key:
            result = self._generate_with_gemini(prompt, settings)
            if result is not None:
                return result
            logger.warning("Gemini SEO generation failed, trying OpenAI fallback…")

        # Try OpenAI (when configured and has API key)
        if settings.openai_api_key:
            result = self._generate_with_openai(prompt, settings)
            if result is not None:
                return result
            logger.warning("OpenAI SEO generation failed, using local fallback…")

        return self._local_fallback(topic, category)

    def _generate_with_gemini(self, prompt: str, settings) -> dict | None:
        """Generate SEO metadata using Google Gemini."""
        try:
            from google import genai  # noqa: PLC0415
            from google.genai import types  # noqa: PLC0415

            client = genai.Client(api_key=settings.gemini_api_key)
            response = client.models.generate_content(
                model=settings.gemini_model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    response_mime_type="application/json",
                ),
            )
            raw = response.text or ""

            # Strip markdown fences
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                lines = cleaned.splitlines()
                cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

            result = json.loads(cleaned)
            logger.info("SEO metadata generated via Gemini")
            return result
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gemini SEO generation error: %s", exc)
            return None

    def _generate_with_openai(self, prompt: str, settings) -> dict | None:
        """Generate SEO metadata using OpenAI GPT."""
        try:
            from openai import OpenAI  # noqa: PLC0415

            client = OpenAI(api_key=settings.openai_api_key)
            response = client.chat.completions.create(
                model=settings.openai_model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                response_format={"type": "json_object"},
            )
            result = json.loads(response.choices[0].message.content)
            logger.info("SEO metadata generated via OpenAI")
            return result
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenAI SEO generation error: %s", exc)
            return None

    def _local_fallback(self, topic: str, category: str) -> dict:
        """Generate basic SEO metadata without AI."""
        return {
            "title": f"{topic} - Complete Guide",
            "description": (
                f"In this video, we cover everything about {topic}. "
                f"Learn the key concepts, best practices, and practical tips.\n\n"
                f"Topics covered:\n"
                f"- Introduction to {topic}\n"
                f"- Key concepts and fundamentals\n"
                f"- Practical examples\n"
                f"- Best practices and tips\n\n"
                f"Don't forget to like, subscribe, and hit the bell! \U0001f514"
            ),
            "tags": [topic.lower(), category, "tutorial", "guide", "learn", "explained", "how to"],
            "hashtags": [f"#{topic.replace(' ', '')}", f"#{category}", "#tutorial"],
            "category_id": 28,  # Science & Technology
        }
