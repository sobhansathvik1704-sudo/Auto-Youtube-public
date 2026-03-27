def build_script_prompt(
    topic: str,
    category: str,
    audience_level: str,
    language_mode: str,
    duration_seconds: int,
) -> str:
    return (
        f"Generate a bilingual Telugu-English YouTube script for topic '{topic}'. "
        f"Category: {category}. Audience: {audience_level}. "
        f"Language mode: {language_mode}. Duration target: {duration_seconds} seconds. "
        "Return structured title, hook, intro, outro, full text, and scene segments."
    )