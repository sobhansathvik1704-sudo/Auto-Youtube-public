from math import ceil

from app.services.llm.base import BaseLLMProvider

# Content point templates filled in with the topic and an index.
_CONTENT_TEMPLATES = [
    (
        "Let's start with the basics of {topic}. Understanding the fundamentals is the first step "
        "to mastering this subject.",
        "Basics of {topic}",
    ),
    (
        "Now let's explore how {topic} works in practice. Real-world examples help you understand "
        "the concepts more clearly.",
        "How {topic} Works",
    ),
    (
        "One of the most important aspects of {topic} is knowing when and how to apply it. "
        "Let's look at some common use-cases.",
        "Use-Cases for {topic}",
    ),
    (
        "Let's talk about best practices around {topic}. Following these guidelines will save you "
        "time and prevent common mistakes.",
        "Best Practices: {topic}",
    ),
    (
        "A common challenge when working with {topic} is handling edge cases. Here's how to deal "
        "with them effectively.",
        "{topic}: Edge Cases",
    ),
    (
        "Let's do a quick recap of everything we've covered about {topic} so far and make sure the "
        "key ideas are crystal clear.",
        "{topic} — Quick Recap",
    ),
]


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
        content_count = max(1, segments_count - 2)  # subtract intro + outro

        title = f"{topic}: A Complete Guide"
        hook = (
            f"Have you ever wondered how {topic} really works? "
            f"In the next few minutes you'll get a clear, {audience_level}-friendly breakdown."
        )
        intro = (
            f"Welcome! Today we're going to learn about {topic}. "
            f"By the end of this video you'll have a solid understanding of the key concepts "
            f"and how to apply them in real projects."
        )
        outro = (
            f"And that wraps up our guide on {topic}! "
            f"If you found this helpful, make sure to like, subscribe, and hit the notification bell "
            f"so you never miss a future video. Drop your questions in the comments below!"
        )

        segments: list[dict] = []
        per_segment = max(5, duration_seconds // segments_count)
        current = 0

        # Intro segment
        segments.append(
            {
                "order": 1,
                "purpose": "intro",
                "narration": f"{hook} {intro}",
                "on_screen_text": f"Welcome to: {topic}",
                "duration_seconds": per_segment,
                "start_seconds": current,
                "end_seconds": current + per_segment,
            }
        )
        current += per_segment

        # Content segments
        templates = _CONTENT_TEMPLATES[:content_count]
        for idx, (narration_tmpl, title_tmpl) in enumerate(templates):
            narration = narration_tmpl.format(topic=topic)
            on_screen = title_tmpl.format(topic=topic)
            segments.append(
                {
                    "order": idx + 2,
                    "purpose": "explanation",
                    "narration": narration,
                    "on_screen_text": on_screen,
                    "duration_seconds": per_segment,
                    "start_seconds": current,
                    "end_seconds": current + per_segment,
                }
            )
            current += per_segment

        # Outro segment
        segments.append(
            {
                "order": len(segments) + 1,
                "purpose": "outro",
                "narration": outro,
                "on_screen_text": "Thanks for watching! Like & Subscribe",
                "duration_seconds": per_segment,
                "start_seconds": current,
                "end_seconds": current + per_segment,
            }
        )

        full_text = " ".join(seg["narration"] for seg in segments)

        return {
            "title_options": [title, f"Understanding {topic} — Beginner to Pro"],
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