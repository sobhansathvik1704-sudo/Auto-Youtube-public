import random
from math import ceil

from app.services.llm.base import BaseLLMProvider

# Beat templates: (narration, on_screen_text, visual_concept).
# Each template is filled with {topic} at generation time.
# on_screen_text: 3-7 words (punchy phrase).
# visual_concept: specific image description tied to the beat's concept.
_BEAT_TEMPLATES = [
    (
        "Let's start with the basics of {topic}. This is where it all begins.",
        "{topic} fundamentals",
        "educational diagram showing the basic structure of {topic}, clean dark background",
    ),
    (
        "Here's how {topic} actually works under the hood.",
        "How {topic} works",
        "technical diagram or code showing internal workings of {topic}, developer view",
    ),
    (
        "The most important use-case for {topic} is in real-world projects.",
        "Real-world {topic} use-case",
        "developer working on a project that uses {topic}, laptop screen with code",
    ),
    (
        "There are key best practices every developer should follow with {topic}.",
        "{topic} best practices",
        "clean code editor showing well-structured {topic} implementation",
    ),
    (
        "One common mistake with {topic} that beginners make every time.",
        "Avoid this {topic} mistake",
        "red error message or broken code related to {topic}, dark terminal",
    ),
    (
        "Here's a quick comparison: {topic} versus the alternatives.",
        "{topic} vs alternatives",
        "side-by-side comparison diagram showing {topic} against a competing approach",
    ),
    (
        "Pro tip: this one trick with {topic} will save you hours of debugging.",
        "Pro {topic} tip",
        "lightbulb or tip graphic with {topic} code snippet on dark background",
    ),
    (
        "Step-by-step: how you'd implement {topic} in a real project.",
        "{topic} step by step",
        "flowchart or step diagram illustrating the {topic} workflow",
    ),
    (
        "Performance matters — here's how {topic} affects speed and efficiency.",
        "{topic} performance impact",
        "performance graph or speedometer showing {topic} benchmarks, tech aesthetic",
    ),
    (
        "Security with {topic} is something most tutorials completely skip.",
        "{topic} security basics",
        "padlock and shield icon with {topic} code, cybersecurity dark theme",
    ),
    (
        "The history of {topic} explains why it works the way it does today.",
        "{topic} origin story",
        "timeline graphic showing the evolution of {topic}, retro tech aesthetic",
    ),
    (
        "These are the three things every beginner gets wrong about {topic}.",
        "3 {topic} beginner mistakes",
        "three numbered cards showing common mistakes with {topic}, minimal design",
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
        # Shorts-first: 1 hook + N beats + 1 takeaway, targeting 2-4s per segment
        beats_count = max(3, min(5, ceil(duration_seconds / 7)))
        segments_count = beats_count + 2  # +1 hook +1 takeaway

        title = f"{topic} in {duration_seconds} seconds"
        hook_narration = (
            f"Did you know most people misunderstand {topic}? Here's what you actually need to know."
        )
        hook_on_screen = f"Most people misunderstand {topic}"
        takeaway_narration = (
            f"Now you know the key ideas behind {topic}. Follow for more quick tech breakdowns!"
        )
        takeaway_on_screen = f"Now you know {topic}"
        cta = "Follow for daily tech Shorts!"

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
                    f"question mark graphic with {topic} text, bold cinematic dark background, "
                    "dramatic lighting, no watermarks"
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
                    "visual_concept": visual_tmpl.format(topic=topic),
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
                    f"{topic} concept summarised, glowing light or success moment, "
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
        }