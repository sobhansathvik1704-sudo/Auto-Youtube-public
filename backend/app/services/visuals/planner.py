import json
import re

from sqlalchemy.orm import Session

from app.db.models.scene import Scene
from app.db.models.script import Script
from app.db.models.video_job import VideoJob
from app.services.ai.domain_rules import get_domain_rules

# Mapping of topic keyword groups → preferred visual vocabulary.
# Each entry is (keywords_list, preferred_vocabulary_string).
# The first matching entry wins.
_TOPIC_VISUAL_VOCAB: list[tuple[list[str], str]] = [
    (
        ["linux", "process", "pid", "signal", "kill", "htop", "scheduler",
         "zombie", "nice", "renice", "sigterm", "sigkill", "fork", "exec"],
        (
            "linux terminal window, htop or top command output, ps aux listing, "
            "PID numbers, process tree, shell prompt, dark terminal theme"
        ),
    ),
    (
        ["operating system", "kernel", "memory management", "syscall",
         "context switch", "interrupt", "virtual memory", "page table"],
        (
            "operating system architecture diagram, kernel vs user space, "
            "memory map, system call flow, process scheduler diagram"
        ),
    ),
    (
        ["c++", "c programming", "compiler", "compilation", "assembly",
         "linker", "preprocessor", "makefile", "gcc", "g++"],
        (
            "C or C++ source code file in dark editor, terminal compiler output, "
            "assembly listing, object file linking, gcc g++ command"
        ),
    ),
    (
        ["python", "django", "flask", "fastapi", "pip", "virtualenv"],
        (
            "python source code with syntax highlighting, terminal with python REPL, "
            "pip install command, dark developer theme"
        ),
    ),
    (
        ["javascript", "typescript", "react", "node", "frontend",
         "css", "html", "dom", "browser"],
        (
            "JavaScript or TypeScript source code, browser developer tools console, "
            "node.js terminal output, code editor dark theme"
        ),
    ),
    (
        ["network", "tcp", "http", "socket", "dns", "tls", "ssl",
         "packet", "ip address", "firewall"],
        (
            "network topology diagram, packet flow visualization, TCP/IP layer stack, "
            "curl or ping command output, terminal network tools"
        ),
    ),
    (
        ["database", "sql", "postgres", "mysql", "mongodb", "redis",
         "query", "transaction", "schema"],
        (
            "SQL query in terminal, database schema diagram, table structure, "
            "query execution plan, dark themed database terminal"
        ),
    ),
    (
        ["git", "version control", "github", "commit", "branch", "merge",
         "pull request", "rebase", "diff"],
        (
            "git command in terminal, branch diagram, commit history graph, "
            "diff output, dark terminal with git log"
        ),
    ),
    (
        ["docker", "kubernetes", "container", "deployment", "devops",
         "ci/cd", "microservice"],
        (
            "docker command in terminal, container architecture diagram, "
            "Kubernetes pod diagram, deployment pipeline, dark terminal"
        ),
    ),
    (
        ["algorithm", "data structure", "sorting", "linked list",
         "recursion", "big o", "complexity"],
        (
            "algorithm flowchart or pseudocode, data structure visualization "
            "(tree nodes, linked list boxes), complexity graph, dark background"
        ),
    ),
]

# Quality and style modifiers — educational/technical illustration style,
# avoiding the generic "cinematic portrait" look that stock generators default to.
_QUALITY_MODIFIERS = (
    "high quality, sharp, educational illustration style, "
    "dark background, developer aesthetic, 4K"
)

# Negative keywords to steer generators away from misleading/off-topic imagery.
_NEGATIVE_KEYWORDS = (
    "no finance charts, no trading dashboard, no stock market monitor, "
    "no vague cyber corridor, no random glowing orbs, no generic human portrait, "
    "no text, no letters, no watermarks"
)

# Words/phrases whose presence in a visual_concept indicate it is already
# grounded in a specific technical idea. Used to skip injecting extra vocabulary
# when the LLM already produced a precise description.
_CONCEPT_GROUNDING_KEYWORDS = frozenset([
    "terminal", "process", "code", "shell", "diagram", "command", "screen",
    "window", "script", "compiler", "source", "signal", "kill", "pid",
    "htop", "top", "ps", "tree", "socket", "packet", "sql", "git",
    "docker", "container", "algorithm", "flowchart", "chart", "graph",
    "map", "illustration", "budget", "timeline",
])

# Pre-compiled word-boundary patterns for grounding keyword detection.
# Using word boundaries avoids false positives (e.g. "pid" inside "rapid").
_CONCEPT_GROUNDING_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b" + re.escape(kw) + r"\b") for kw in _CONCEPT_GROUNDING_KEYWORDS
]


def _detect_topic_vocabulary(topic: str) -> str | None:
    """Return preferred visual vocabulary string for recognised technical topics.

    Uses word-boundary regex matching so that short keywords (e.g. ``kill``,
    ``pid``, ``api``) do not produce false positives against words that merely
    contain them as substrings (e.g. ``skill``, ``rapid``).  Multi-word phrases
    in the keyword list are also matched correctly.

    Returns ``None`` if the topic does not match any known category.
    """
    topic_lower = topic.lower()
    for keywords, vocab in _TOPIC_VISUAL_VOCAB:
        for kw in keywords:
            pattern = r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, topic_lower):
                return vocab
    return None


def _build_visual_prompt(
    segment: dict,
    topic: str,
    category: str = "",
    subcategory: str | None = None,
) -> str:
    """Build an image generation prompt for a segment.

    Prefers the segment's ``visual_concept`` field (set by the LLM) over a
    generic fallback so that each scene gets a distinct, concept-driven image.
    Injects topic-specific vocabulary when the LLM concept is not already
    grounded in technical terminology, and appends negative keywords to prevent
    generic finance/corridor/portrait imagery.

    Category/subcategory domain rules are used as a secondary vocabulary source
    when neither the topic keyword lookup nor the LLM concept itself provides
    adequate grounding.
    """
    visual_concept = (segment.get("visual_concept") or "").strip()

    # Fetch domain rules once and reuse
    domain_rules = get_domain_rules(category, subcategory) if category else None

    # 1. Try topic-keyword vocabulary (most specific)
    topic_vocab = _detect_topic_vocabulary(topic)

    # 2. Fall back to category/subcategory domain rules vocabulary
    if not topic_vocab and domain_rules:
        topic_vocab = domain_rules.visual_vocab

    # Build domain-specific negative keywords
    domain_avoid = domain_rules.avoid_visuals if domain_rules else ""
    combined_negative = _NEGATIVE_KEYWORDS
    if domain_avoid:
        combined_negative = f"{_NEGATIVE_KEYWORDS}, {domain_avoid}"

    if visual_concept:
        # Check if the concept already contains any grounding keyword using
        # word-boundary matching to avoid spurious substring hits.
        concept_lower = visual_concept.lower()
        already_grounded = any(
            pat.search(concept_lower) for pat in _CONCEPT_GROUNDING_PATTERNS
        )
        if topic_vocab and not already_grounded:
            base = f"{visual_concept}, {topic_vocab}"
        else:
            base = visual_concept
        return f"{base}, {_QUALITY_MODIFIERS}, {combined_negative}"

    # Fallback: derive from on_screen_text / topic
    subject = (segment.get("on_screen_text") or "").strip() or topic
    vocab_part = f", {topic_vocab}" if topic_vocab else ""
    return (
        f"{topic}, {subject}{vocab_part}, "
        f"{_QUALITY_MODIFIERS}, {combined_negative}"
    )


def _scene_type_for_segment(idx: int, total: int, purpose: str, has_code: bool = False) -> str:
    """Return the scene type for a 1-based segment index out of *total*.

    Shorts-format purposes (``hook``, ``beat``, ``takeaway``) are mapped
    directly.  Legacy purpose values (``intro``, ``explanation``, ``outro``,
    etc.) fall back to the old alternating scheme so existing content is
    unaffected.
    """
    if has_code:
        return "code_card"

    purpose_lower = (purpose or "").lower()

    # Shorts-format mapping
    if purpose_lower == "hook":
        return "hook"
    if purpose_lower == "takeaway":
        return "takeaway"
    if purpose_lower == "beat":
        return "beat"

    # Legacy fallback (intro / outro / explanation / comparison / …)
    if idx == 1:
        return "intro"
    if idx == total:
        return "outro"
    return "bullet_explainer" if (idx % 2 == 0) else "icon_compare"


def generate_scenes_from_script(db: Session, job: VideoJob, script: Script) -> list[Scene]:
    payload = json.loads(script.structured_json)
    segments = payload.get("segments", [])
    total = len(segments)

    scenes: list[Scene] = []
    current_ms = 0

    for idx, segment in enumerate(segments, start=1):
        has_code = bool(segment.get("code_snippet", "").strip())
        purpose = segment.get("purpose", "beat")
        scene_type = _scene_type_for_segment(idx, total, purpose, has_code)
        # Default 4 s per segment matches the Shorts-format target (2–5 s beats).
        # Legacy scripts that omit duration_seconds will use this 4 s default.
        duration_ms = int(segment.get("duration_seconds", 4) * 1000)

        asset_config: dict = {
            "template": scene_type,
            "background": "gradient_blue",
            "accent": "#00E5FF",
        }
        if scene_type == "code_card":
            asset_config["code_snippet"] = segment.get("code_snippet", "")
            asset_config["code_language"] = segment.get("code_language", "")

        scene = Scene(
            video_job_id=job.id,
            scene_index=idx,
            scene_type=scene_type,
            narration_text=segment["narration"],
            on_screen_text=segment.get("on_screen_text"),
            visual_prompt=_build_visual_prompt(
                segment, job.topic, job.category, job.subcategory
            ),
            asset_config_json=json.dumps(asset_config, ensure_ascii=False),
            duration_ms=duration_ms,
            start_ms=current_ms,
            end_ms=current_ms + duration_ms,
        )
        db.add(scene)
        db.flush()
        scenes.append(scene)
        current_ms += duration_ms

    return scenes