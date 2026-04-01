"""Domain-specific generation rules for category/subcategory-driven content.

This module defines visual vocabularies, script-style hints, and guardrails
for each broad category and its subcategories.  It is shared between the LLM
prompt builder and the visual-prompt planner so that both layers always agree
on what is appropriate for a given domain.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Category → subcategory hierarchy
# ---------------------------------------------------------------------------

CATEGORY_SUBCATEGORIES: dict[str, list[str]] = {
    "tech": [
        "Programming",
        "Web Development",
        "Operating Systems",
        "AI / ML",
        "DevOps / Cloud",
        "Databases",
        "Cybersecurity",
        "Networking",
        "System Design",
        "Mobile Development",
    ],
    "finance": [
        "Investing",
        "Budgeting",
        "Trading",
        "Economics",
        "Personal Finance",
        "Crypto",
        "Real Estate",
    ],
    "education": [
        "Physics",
        "Chemistry",
        "Biology",
        "Mathematics",
        "General Science",
        "History",
        "Geography",
        "Literature",
    ],
    "science": [
        "Physics",
        "Chemistry",
        "Biology",
        "Astronomy",
        "Earth Science",
        "Environmental Science",
    ],
    "history": [
        "Ancient History",
        "Medieval History",
        "Modern History",
        "Wars & Conflicts",
        "Biographies",
        "Civilizations",
    ],
    "health": [
        "Fitness",
        "Nutrition",
        "Mental Health",
        "Medical Basics",
        "Wellness",
        "Sleep & Recovery",
    ],
    "motivation": [
        "Productivity",
        "Mindset",
        "Habits",
        "Discipline",
        "Communication",
        "Personal Growth",
    ],
    "business": [
        "Startups",
        "Marketing",
        "Leadership",
        "Career",
        "Freelancing",
        "Interview Prep",
    ],
    "entertainment": [
        "Movies",
        "Anime",
        "Gaming",
        "Pop Culture",
        "Music",
        "Storytelling",
    ],
    "gaming": [
        "Game Reviews",
        "Esports",
        "Game Development",
        "Game Guides",
        "Gaming History",
    ],
    "lifestyle": [
        "Travel",
        "Food",
        "Fashion",
        "Home & Decor",
        "Relationships",
    ],
}


# ---------------------------------------------------------------------------
# Per-category domain rules
# ---------------------------------------------------------------------------

class DomainRules:
    """Holds domain-specific rules for a category/subcategory pair."""

    def __init__(
        self,
        *,
        visual_vocab: str,
        avoid_visuals: str,
        script_style: str,
        narration_tone: str,
        on_screen_style: str,
    ) -> None:
        self.visual_vocab = visual_vocab
        self.avoid_visuals = avoid_visuals
        self.script_style = script_style
        self.narration_tone = narration_tone
        self.on_screen_style = on_screen_style


# Subcategory-level overrides: (category, subcategory_lower) → DomainRules
_SUBCATEGORY_RULES: dict[tuple[str, str], DomainRules] = {
    ("tech", "programming"): DomainRules(
        visual_vocab=(
            "source code file in dark editor with syntax highlighting, "
            "terminal compiler output, code editor window, algorithm flowchart, "
            "function definition, class diagram, dark developer theme"
        ),
        avoid_visuals=(
            "finance charts, trading dashboards, stock market monitors, "
            "vague glowing corridors, generic human portraits"
        ),
        script_style=(
            "step-by-step technical explainer; start with the why, "
            "show the code concept, then the result; concise and practical"
        ),
        narration_tone="clear, precise, developer-friendly; avoid marketing language",
        on_screen_style="short code-concept phrases, e.g. 'Function: define once, call many'",
    ),
    ("tech", "web development"): DomainRules(
        visual_vocab=(
            "browser developer tools, HTML/CSS/JavaScript code in editor, "
            "DOM tree diagram, HTTP request/response flow, REST API diagram, "
            "dark code editor, network tab screenshot"
        ),
        avoid_visuals="finance charts, trading dashboards, unrelated stock imagery",
        script_style="practical web-dev explainer; show browser vs server distinction; real examples",
        narration_tone="friendly and practical; web developer audience",
        on_screen_style="e.g. 'DOM: browser's object model', 'HTTP: request → response'",
    ),
    ("tech", "operating systems"): DomainRules(
        visual_vocab=(
            "linux terminal window, htop or top command output, ps aux listing, "
            "PID numbers, process tree with parent-child nodes, CPU scheduler queue, "
            "process state diagram (running/sleeping/zombie), kill command terminal, "
            "SIGTERM SIGKILL signal flow, context switch diagram, /proc filesystem, "
            "shell prompt, system architecture diagram, kernel vs user space"
        ),
        avoid_visuals=(
            "finance charts, trading dashboards, stock market monitors, "
            "random glowing orbs, vague cyber corridor, generic human portrait"
        ),
        script_style=(
            "systematic OS explainer; cover concept → mechanism → real command; "
            "step-by-step with concrete examples; beginner-friendly but precise"
        ),
        narration_tone="educational and precise; use concrete Linux command examples",
        on_screen_style="e.g. 'Process states: running, sleeping, zombie'",
    ),
    ("tech", "ai / ml"): DomainRules(
        visual_vocab=(
            "neural network diagram with nodes and layers, training loss curve, "
            "confusion matrix, python code with numpy/torch, Jupyter notebook, "
            "decision tree visualization, gradient descent graph, dark technical theme"
        ),
        avoid_visuals="trading dashboards, finance charts, generic stock photos",
        script_style="concept-first AI/ML explainer; intuition before math; practical examples",
        narration_tone="enthusiastic but precise; accessible to intermediate audience",
        on_screen_style="e.g. 'Gradient descent: minimize loss step by step'",
    ),
    ("tech", "devops / cloud"): DomainRules(
        visual_vocab=(
            "docker command in terminal, container architecture diagram, "
            "Kubernetes pod diagram, CI/CD pipeline flowchart, "
            "cloud infrastructure diagram (AWS/GCP/Azure icons), deployment script, "
            "dark terminal, server rack illustration"
        ),
        avoid_visuals="finance charts, trading dashboards, stock market monitors",
        script_style="infrastructure-focused explainer; automation mindset; show pipeline or workflow",
        narration_tone="confident, practical, DevOps engineer perspective",
        on_screen_style="e.g. 'Docker: package app + dependencies'",
    ),
    ("tech", "databases"): DomainRules(
        visual_vocab=(
            "SQL query in terminal, database schema diagram, "
            "table structure with rows/columns, query execution plan, "
            "ERD diagram, index visualization, dark themed database terminal"
        ),
        avoid_visuals="finance charts, trading dashboards, generic tech stock imagery",
        script_style="data-first explainer; show schema, query, result progression",
        narration_tone="precise and structured; database practitioner tone",
        on_screen_style="e.g. 'SQL JOIN: combine rows from two tables'",
    ),
    ("tech", "cybersecurity"): DomainRules(
        visual_vocab=(
            "terminal with security commands, firewall rule diagram, "
            "network packet capture, encryption key diagram, "
            "penetration testing terminal, lock/shield icon, dark security aesthetic"
        ),
        avoid_visuals="trading dashboards, finance charts, vague glowing cyber corridors",
        script_style="threat-aware explainer; attack → defense framing; concrete examples",
        narration_tone="serious and cautionary; clear about risks",
        on_screen_style="e.g. 'HTTPS: encrypts data in transit'",
    ),
    ("tech", "networking"): DomainRules(
        visual_vocab=(
            "network topology diagram, packet flow visualization, TCP/IP layer stack, "
            "curl or ping command output, socket connection diagram, "
            "DNS resolution flow, firewall diagram, dark technical background"
        ),
        avoid_visuals="finance charts, trading dashboards, stock market imagery",
        script_style="layer-by-layer explainer; OSI or TCP/IP model awareness; practical commands",
        narration_tone="technical but accessible; networking engineer perspective",
        on_screen_style="e.g. 'DNS: translates names to IP addresses'",
    ),
    ("tech", "system design"): DomainRules(
        visual_vocab=(
            "system architecture block diagram, microservices diagram, "
            "load balancer diagram, database sharding visualization, "
            "cache layer diagram, API gateway, dark background whiteboard-style"
        ),
        avoid_visuals="finance charts, trading dashboards, unrelated stock imagery",
        script_style="top-down design explainer; scale → components → trade-offs",
        narration_tone="architect-level thinking; practical trade-off framing",
        on_screen_style="e.g. 'Load balancer: distribute traffic evenly'",
    ),
}

# Category-level defaults (used when no subcategory match is found)
_CATEGORY_RULES: dict[str, DomainRules] = {
    "tech": DomainRules(
        visual_vocab=(
            "terminal window, code editor with syntax highlighting, "
            "technical diagram, architecture graphic, command-line UI, "
            "developer workspace, dark background"
        ),
        avoid_visuals=(
            "finance charts, trading dashboards, stock market monitors, "
            "random glowing orbs, vague cyber corridor, generic human portrait"
        ),
        script_style="concise technical explainer; step-by-step; practical; concept then example",
        narration_tone="clear, developer-friendly, educational",
        on_screen_style="short technical concept phrases in 'Term: explanation' format",
    ),
    "finance": DomainRules(
        visual_vocab=(
            "money flow diagram, market chart, budgeting spreadsheet, "
            "investment metaphor, coins and wallet, percent/growth graph, "
            "clean financial infographic"
        ),
        avoid_visuals="unrelated tech terminals, code editors, Linux commands",
        script_style="simple analogies; comparison-friendly; practical advice; risk disclaimers where needed",
        narration_tone="trustworthy, straightforward, financially literate but accessible",
        on_screen_style="e.g. 'Compound interest: earn interest on interest'",
    ),
    "education": DomainRules(
        visual_vocab=(
            "labeled educational diagram, concept illustration, "
            "scientific visualization, textbook-style graphic, "
            "clean dark background with clear labels"
        ),
        avoid_visuals="trading dashboards, finance charts, unrelated tech imagery",
        script_style="concept-first; intuition before formula; classroom-friendly; clear analogies",
        narration_tone="encouraging and educational; student-friendly",
        on_screen_style="e.g. 'Newton's 2nd Law: F = ma'",
    ),
    "science": DomainRules(
        visual_vocab=(
            "scientific diagram, atom or molecule illustration, "
            "physics force diagram, chemical equation visualization, "
            "biology cell diagram, dark educational background"
        ),
        avoid_visuals="trading dashboards, finance charts, unrelated business imagery",
        script_style="observation → explanation → implication; intuitive examples; fact-driven",
        narration_tone="curious and precise; science communicator tone",
        on_screen_style="e.g. 'Photosynthesis: sunlight → glucose + oxygen'",
    ),
    "history": DomainRules(
        visual_vocab=(
            "historical map, timeline diagram, archival-style illustration, "
            "period-accurate scene, civilization symbol, dark vintage aesthetic"
        ),
        avoid_visuals="modern tech terminals, trading dashboards, contemporary stock photos",
        script_style="chronological; cause → event → consequence; engaging narrative",
        narration_tone="storytelling, chronological, cause-and-effect focused",
        on_screen_style="e.g. 'Fall of Rome: 476 AD — internal decay'",
    ),
    "health": DomainRules(
        visual_vocab=(
            "human body diagram, workout illustration, nutrition chart, "
            "medical infographic, muscle group diagram, clean health visual"
        ),
        avoid_visuals="trading dashboards, finance charts, unrelated tech imagery",
        script_style="practical health advice; beginner-safe language; avoid over-claiming",
        narration_tone="supportive and credible; health-literate but accessible",
        on_screen_style="e.g. 'Protein: repairs and builds muscle tissue'",
    ),
    "motivation": DomainRules(
        visual_vocab=(
            "clean minimalist lifestyle visual, symbolic imagery, "
            "person achieving goal, simple motivational graphic, "
            "sunrise or progress metaphor, warm tones"
        ),
        avoid_visuals="trading dashboards, finance charts, unrelated tech imagery",
        script_style="punchy and emotional; practical tips; short sentences; high energy",
        narration_tone="energetic, inspiring, direct",
        on_screen_style="e.g. 'Discipline: do it even when you don't feel like it'",
    ),
    "business": DomainRules(
        visual_vocab=(
            "office or professional setting, presentation slide style, "
            "business diagram, career path graphic, professional portrait context, "
            "clean corporate aesthetic"
        ),
        avoid_visuals="random glowing orbs, vague cyber corridor, unrelated tech terminals",
        script_style="actionable; concise; authority-driven; real-world applicable",
        narration_tone="confident, professional, authoritative",
        on_screen_style="e.g. 'Burn rate: how fast a startup spends cash'",
    ),
    "entertainment": DomainRules(
        visual_vocab=(
            "cinematic scene, stylized genre art, movie poster aesthetic, "
            "dynamic action frame, story-driven visual, vibrant colors"
        ),
        avoid_visuals="boring white backgrounds, overly corporate imagery",
        script_style="engaging narrative; dramatic hooks; curiosity-driven; fan-friendly",
        narration_tone="dramatic and engaging; pop-culture savvy",
        on_screen_style="e.g. 'Plot twist: the villain was right all along'",
    ),
    "gaming": DomainRules(
        visual_vocab=(
            "game screenshot or UI element, game character or environment, "
            "esports setup, game controller graphic, pixel art or game engine visual"
        ),
        avoid_visuals="trading dashboards, finance charts, unrelated business imagery",
        script_style="gamer-friendly tone; tips and insights; review or breakdown format",
        narration_tone="casual, enthusiastic, gamer-native vocabulary",
        on_screen_style="e.g. 'Speedrun: beat the game as fast as possible'",
    ),
    "lifestyle": DomainRules(
        visual_vocab=(
            "lifestyle photo, travel destination, food plating, "
            "home décor aesthetic, fashion flat lay, warm inviting tones"
        ),
        avoid_visuals="trading dashboards, finance charts, cold corporate imagery",
        script_style="conversational and relatable; personal and practical",
        narration_tone="warm, friendly, personal",
        on_screen_style="e.g. 'Morning routine: sets the tone for your day'",
    ),
}

_DEFAULT_RULES = DomainRules(
    visual_vocab=(
        "relevant educational diagram, clear concept illustration, dark background"
    ),
    avoid_visuals=(
        "finance charts, trading dashboards, random glowing orbs, "
        "vague cyber corridor, generic human portrait"
    ),
    script_style="clear explainer; concept → example → takeaway",
    narration_tone="educational and engaging",
    on_screen_style="short punchy phrase summarizing the concept",
)


def get_domain_rules(category: str, subcategory: str | None = None) -> DomainRules:
    """Return the most specific DomainRules for the given category/subcategory.

    Lookup order:
    1. (category_lower, subcategory_lower) exact match in _SUBCATEGORY_RULES
    2. category_lower match in _CATEGORY_RULES
    3. _DEFAULT_RULES
    """
    cat = (category or "").lower().strip()
    sub = (subcategory or "").lower().strip()

    if cat and sub:
        rules = _SUBCATEGORY_RULES.get((cat, sub))
        if rules:
            return rules

    if cat:
        rules = _CATEGORY_RULES.get(cat)
        if rules:
            return rules

    return _DEFAULT_RULES


def build_domain_context(category: str, subcategory: str | None = None) -> str:
    """Return a formatted domain-context string for injection into LLM prompts.

    The string describes script style, narration tone, on-screen text style,
    preferred visual vocabulary, and imagery to avoid — all tailored to the
    given category/subcategory.
    """
    rules = get_domain_rules(category, subcategory)
    sub_line = f"Subcategory: {subcategory}\n" if subcategory else ""
    return (
        f"DOMAIN CONTEXT\n"
        f"Category: {category}\n"
        f"{sub_line}"
        f"Script style: {rules.script_style}\n"
        f"Narration tone: {rules.narration_tone}\n"
        f"On-screen text style: {rules.on_screen_style}\n"
        f"Preferred visual vocabulary: {rules.visual_vocab}\n"
        f"Avoid these visuals: {rules.avoid_visuals}"
    )
