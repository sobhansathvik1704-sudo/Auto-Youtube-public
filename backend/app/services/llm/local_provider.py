from math import ceil

from app.services.llm.base import BaseLLMProvider


class LocalLLMProvider(BaseLLMProvider):
    def generate_script_payload(
        self,
        topic: str,
        category: str,
        audience_level: str,
        language_mode: str,
        duration_seconds: int,
    ) -> dict:
        segments_count = max(4, min(8, ceil(duration_seconds / 10)))
        intro = f"{topic} ni simple ga ardham chesukundam."
        hook = f"{topic} gurinchi beginners ki clear ga cheptha."
        outro = "Inka ilaanti tech and coding videos kosam follow avvandi."
        title = f"{topic} Explained in Telugu + English"

        segments = []
        per_segment = max(5, duration_seconds // segments_count)
        current = 0

        for index in range(segments_count):
            narration = (
                f"Segment {index + 1}: {topic} lo important point {index + 1}. "
                f"Idi {audience_level} audience kosam simple explanation."
            )
            on_screen = f"{topic} - point {index + 1}"
            segments.append(
                {
                    "order": index + 1,
                    "purpose": "explanation",
                    "narration": narration,
                    "on_screen_text": on_screen,
                    "duration_seconds": per_segment,
                    "start_seconds": current,
                    "end_seconds": current + per_segment,
                }
            )
            current += per_segment

        full_text = " ".join(
            [
                hook,
                intro,
                *[segment["narration"] for segment in segments],
                outro,
            ]
        )

        return {
            "title_options": [title, f"What is {topic}? Telugu Tech Short"],
            "title": title,
            "hook": hook,
            "intro": intro,
            "outro": outro,
            "full_text": full_text,
            "language_mode": language_mode,
            "estimated_duration_seconds": duration_seconds,
            "segments": segments,
            "cta": outro,
            "category": category,
        }