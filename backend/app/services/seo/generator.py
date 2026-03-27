import json
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class SEOGenerator:
    def generate_seo_metadata(self, topic: str, script_summary: str, category: str = "tech") -> dict:
        """Use GPT-4o to generate SEO-optimized YouTube metadata."""
        settings = get_settings()

        if settings.llm_provider == "local":
            return self._local_fallback(topic, category)

        from openai import OpenAI  # noqa: PLC0415

        client = OpenAI(api_key=settings.openai_api_key)

        prompt = f"""Generate SEO-optimized YouTube metadata for a video about: "{topic}"
Category: {category}
Script summary: {script_summary[:500]}

Return a JSON object with:
- "title": YouTube title (max 100 chars, include main keyword, engaging, click-worthy)
- "description": YouTube description (300-500 words, include keywords naturally, add timestamps placeholder, include call-to-action, relevant links section)
- "tags": Array of 15-20 relevant tags (mix of broad and specific)
- "hashtags": Array of 3-5 hashtags (most relevant)
- "category_id": YouTube category ID number (e.g., 28 for Science & Tech, 27 for Education)

Make it optimized for YouTube search and discovery. Use proven SEO techniques.
Return ONLY valid JSON, no other text."""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            response_format={"type": "json_object"},
        )

        return json.loads(response.choices[0].message.content)

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
