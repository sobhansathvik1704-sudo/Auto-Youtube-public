import random
from math import ceil

from app.services.llm.base import BaseLLMProvider

# Content point templates: (narration, on_screen_text).
# Each template is filled with {topic} at generation time.
_CONTENT_TEMPLATES = [
    (
        "Let's start with the basics of {topic}. Understanding the fundamentals is the first step "
        "to mastering this subject. Building a solid foundation makes everything else click into place.",
        "Basics of {topic}",
    ),
    (
        "Now let's explore how {topic} works in practice. Real-world examples help you understand "
        "the concepts more clearly and remember them long after the video ends.",
        "How {topic} Works",
    ),
    (
        "One of the most important aspects of {topic} is knowing when and how to apply it. "
        "Let's look at some common use-cases you'll encounter in real projects.",
        "Use-Cases for {topic}",
    ),
    (
        "Let's talk about best practices around {topic}. Following these guidelines will save you "
        "time, prevent common mistakes, and make your work more maintainable.",
        "Best Practices: {topic}",
    ),
    (
        "A common challenge when working with {topic} is handling edge cases. Here's how to deal "
        "with them effectively so your solution is robust and production-ready.",
        "{topic}: Edge Cases",
    ),
    (
        "Let's do a quick recap of everything we've covered about {topic} so far and make sure the "
        "key ideas are crystal clear before we move forward.",
        "{topic} — Quick Recap",
    ),
    (
        "Did you know that {topic} has some fascinating history behind it? Understanding where it "
        "came from helps you appreciate why it works the way it does today.",
        "History of {topic}",
    ),
    (
        "Let's compare {topic} with some alternatives. Knowing the trade-offs helps you choose the "
        "right tool for the right job every single time.",
        "{topic} vs Alternatives",
    ),
    (
        "Here are five pro tips for working with {topic} that most tutorials skip. These insights "
        "come from real-world experience and will level up your skills immediately.",
        "Pro Tips: {topic}",
    ),
    (
        "Let's walk through a step-by-step example with {topic}. Seeing a complete workflow from "
        "start to finish is the fastest way to build real confidence.",
        "{topic}: Step-by-Step",
    ),
    (
        "Common mistakes people make with {topic} — and how to avoid them. Learning from others' "
        "errors is the smartest shortcut to becoming an expert.",
        "Avoid These {topic} Mistakes",
    ),
    (
        "What does the future look like for {topic}? Emerging trends and upcoming changes mean now "
        "is the perfect time to build your expertise in this area.",
        "Future of {topic}",
    ),
    (
        "Let's talk about performance and scalability with {topic}. Small optimisations can lead to "
        "huge improvements in speed and efficiency in production systems.",
        "{topic}: Performance Tips",
    ),
    (
        "Security considerations around {topic} are often overlooked but critically important. "
        "Here's what you need to know to keep your implementation safe and reliable.",
        "{topic} Security Basics",
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
            f"In the next few minutes you'll get a clear, {audience_level}-friendly breakdown "
            f"packed with practical examples and actionable tips."
        )
        intro = (
            f"Welcome! Today we're going to learn about {topic}. "
            f"By the end of this video you'll have a solid understanding of the key concepts "
            f"and know exactly how to apply them in real projects."
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

        # Randomly sample from the available templates so repeated calls vary
        available = list(_CONTENT_TEMPLATES)
        random.shuffle(available)
        selected = available[:content_count]

        # Content segments
        for idx, (narration_tmpl, title_tmpl) in enumerate(selected):
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