def build_script_prompt(
    topic: str,
    category: str,
    audience_level: str,
    language_mode: str,
    duration_seconds: int,
) -> str:
    return (
        f"Generate a YouTube short/video script for topic '{topic}'. "
        f"Category: {category}. Audience: {audience_level}. "
        f"Language mode: {language_mode}. Duration target: {duration_seconds} seconds. "
        "Return structured title, hook, intro, outro, full text, and scene segments. "
        "For each segment, 'on_screen_text' must be 2-3 complete explanatory sentences "
        "(25-40 words) that teach the viewer about the concept — NOT just a heading or label. "
        "For segments where showing a code example adds significant value, include two extra "
        "fields in the segment object: "
        "\"code_snippet\" (a short, self-contained code example as a plain string) and "
        "\"code_language\" (the programming language identifier, e.g. \"python\", "
        "\"javascript\", \"java\", \"bash\"). "
        "Only include code_snippet/code_language for segments that genuinely benefit from "
        "showing code — do NOT add them to every segment."
    )