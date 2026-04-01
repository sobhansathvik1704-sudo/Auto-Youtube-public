import random
from math import ceil

from app.services.ai.domain_rules import get_domain_rules
from app.services.llm.base import BaseLLMProvider

# Target seconds per beat segment when calculating the default beat count.
# Shorts segments should be short (2–5 s), so each beat covers roughly this
# many seconds of the overall requested duration.
_TARGET_SECONDS_PER_BEAT = 7

# Beat templates: (narration, on_screen_text, visual_concept_template).
# Each template is filled with {topic} and {visual_vocab} at generation time.
# on_screen_text: 3-7 words in "Concept: detail" format for educational precision.
# visual_concept_template: uses {topic} and {visual_vocab} placeholders.
_BEAT_TEMPLATES = [
    (
        "Let's start with the basics of {topic}. This is where it all begins.",
        "{topic}: the basics",
        "educational diagram showing the basic structure of {topic}, {visual_vocab}, dark background",
    ),
    (
        "Here's how {topic} actually works under the hood.",
        "How {topic} works",
        "technical diagram or illustration of internal workings of {topic}, {visual_vocab}",
    ),
    (
        "The most important use-case for {topic} is in real-world projects.",
        "{topic}: real-world use case",
        "real-world example of {topic} in action, {visual_vocab}, dark screen",
    ),
    (
        "There are key best practices every developer should follow with {topic}.",
        "{topic}: best practices",
        "well-structured illustration of {topic} best practices, {visual_vocab}",
    ),
    (
        "One common mistake with {topic} that beginners make every time.",
        "{topic}: avoid this mistake",
        "warning or error illustration related to {topic}, {visual_vocab}, red indicator",
    ),
    (
        "Here's a quick comparison: {topic} versus the alternatives.",
        "{topic} vs alternatives",
        "side-by-side comparison diagram of {topic} against an alternative, {visual_vocab}",
    ),
    (
        "Pro tip: this one trick with {topic} will save you hours of debugging.",
        "{topic}: pro tip",
        "pro tip illustration for {topic}, {visual_vocab}, dark background",
    ),
    (
        "Step-by-step: how you'd implement {topic} in a real project.",
        "{topic}: step by step",
        "flowchart or step diagram for {topic} workflow, {visual_vocab}",
    ),
    (
        "Performance matters — here's how {topic} affects speed and efficiency.",
        "{topic}: performance impact",
        "performance benchmark or metrics illustration for {topic}, {visual_vocab}",
    ),
    (
        "Security with {topic} is something most tutorials completely skip.",
        "{topic}: security basics",
        "security-relevant illustration for {topic}, {visual_vocab}, shield icon",
    ),
    (
        "The history of {topic} explains why it works the way it does today.",
        "{topic}: origin story",
        "timeline or evolution diagram of {topic}, {visual_vocab}, retro aesthetic",
    ),
    (
        "These are the three things every beginner gets wrong about {topic}.",
        "{topic}: 3 common mistakes",
        "three numbered cards showing common {topic} mistakes, {visual_vocab}",
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
        subcategory: str | None = None,
    ) -> dict:
        # Shorts-first: 1 hook + N beats + 1 takeaway, targeting 2-4s per segment
        beats_count = max(3, min(5, ceil(duration_seconds / _TARGET_SECONDS_PER_BEAT)))
        segments_count = beats_count + 2  # +1 hook +1 takeaway

        # Retrieve domain-specific visual vocabulary for the category/subcategory
        domain_rules = get_domain_rules(category, subcategory)
        visual_vocab = domain_rules.visual_vocab
        avoid_visuals = domain_rules.avoid_visuals

        title = f"{topic} in {duration_seconds} seconds"
        hook_narration = (
            f"Did you know most people misunderstand {topic}? Here's what you actually need to know."
        )
        hook_on_screen = f"What is {topic}, really?"
        takeaway_narration = (
            f"Now you know the key ideas behind {topic}. Follow for more quick breakdowns!"
        )
        takeaway_on_screen = f"{topic}: now you know"
        cta = f"Follow for more {category} Shorts!"

        per_segment = max(2, duration_seconds // segments_count)
        segments: list[dict] = []
        current = 0

        # Hook segment
        segments.append(
            {
                "order": 1,
                "purpose": "hook",
                "narration": hook_narration,
                "on_screen_text": hook_on_screen,
                "visual_concept": (
                    f"bold question about {topic}, {visual_vocab}, "
                    "dark educational background, no text, no watermarks"
                ),
                "duration_seconds": per_segment,
                "start_seconds": current,
                "end_seconds": current + per_segment,
            }
        )
        current += per_segment

        # Randomly sample beat templates so repeated calls vary
        available = list(_BEAT_TEMPLATES)
        random.shuffle(available)
        selected = available[:beats_count]

        # Beat segments
        for idx, (narration_tmpl, on_screen_tmpl, visual_tmpl) in enumerate(selected):
            segments.append(
                {
                    "order": idx + 2,
                    "purpose": "beat",
                    "narration": narration_tmpl.format(topic=topic),
                    "on_screen_text": on_screen_tmpl.format(topic=topic),
                    "visual_concept": visual_tmpl.format(topic=topic, visual_vocab=visual_vocab),
                    "duration_seconds": per_segment,
                    "start_seconds": current,
                    "end_seconds": current + per_segment,
                }
            )
            current += per_segment

        # Takeaway segment
        segments.append(
            {
                "order": len(segments) + 1,
                "purpose": "takeaway",
                "narration": takeaway_narration,
                "on_screen_text": takeaway_on_screen,
                "visual_concept": (
                    f"{topic} concept summary, {visual_vocab}, "
                    "clean dark background, no watermarks"
                ),
                "duration_seconds": per_segment,
                "start_seconds": current,
                "end_seconds": current + per_segment,
            }
        )

        full_text = " ".join(seg["narration"] for seg in segments)
        outro = takeaway_narration

        return {
            "title_options": [title, f"What is {topic}? Quick breakdown"],
            "title": title,
            "hook": hook_narration,
            "intro": "",
            "outro": outro,
            "full_text": full_text,
            "language_mode": language_mode,
            "estimated_duration_seconds": duration_seconds,
            "segments": segments,
            "cta": cta,
            "category": category,
            "subcategory": subcategory or "",
        }