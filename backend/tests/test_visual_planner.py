"""Tests for visual prompt generation in planner.py.

Covers _detect_topic_vocabulary and _build_visual_prompt, which are the
core functions responsible for Part 1 (improved image relevancy):
  - LLM-generated visual_concept is used as the primary prompt
  - Topic-specific vocabulary is injected when the concept is generic
  - Domain rules provide a secondary vocabulary source
  - Negative keywords prevent stock-market/finance imagery for tech topics
"""

import pytest

from app.services.visuals.planner import _build_visual_prompt, _detect_topic_vocabulary


# ---------------------------------------------------------------------------
# Tests: _detect_topic_vocabulary
# ---------------------------------------------------------------------------

class TestDetectTopicVocabulary:
    def test_linux_process_topic_returns_terminal_vocab(self):
        vocab = _detect_topic_vocabulary("Linux process management")
        assert vocab is not None
        assert "terminal" in vocab.lower() or "linux" in vocab.lower()

    def test_operating_system_kernel_topic_returns_os_vocab(self):
        vocab = _detect_topic_vocabulary("Operating System kernel architecture")
        assert vocab is not None
        assert "operating system" in vocab.lower() or "kernel" in vocab.lower()

    def test_python_topic_returns_python_vocab(self):
        vocab = _detect_topic_vocabulary("Python programming fundamentals")
        assert vocab is not None
        assert "python" in vocab.lower()

    def test_javascript_topic_returns_js_vocab(self):
        vocab = _detect_topic_vocabulary("JavaScript promises and async/await")
        assert vocab is not None
        assert "javascript" in vocab.lower() or "typescript" in vocab.lower()

    def test_database_sql_topic_returns_db_vocab(self):
        vocab = _detect_topic_vocabulary("SQL database queries and indexing")
        assert vocab is not None
        assert "sql" in vocab.lower() or "database" in vocab.lower()

    def test_git_version_control_returns_git_vocab(self):
        vocab = _detect_topic_vocabulary("git version control branching strategy")
        assert vocab is not None
        assert "git" in vocab.lower() or "branch" in vocab.lower()

    def test_docker_container_returns_docker_vocab(self):
        vocab = _detect_topic_vocabulary("Docker container deployment")
        assert vocab is not None
        assert "docker" in vocab.lower() or "container" in vocab.lower()

    def test_algorithm_data_structure_returns_algo_vocab(self):
        vocab = _detect_topic_vocabulary("sorting algorithm complexity Big O")
        assert vocab is not None
        assert "algorithm" in vocab.lower() or "flowchart" in vocab.lower()

    def test_unrecognised_topic_returns_none(self):
        vocab = _detect_topic_vocabulary("cooking pasta recipes with vegetables")
        assert vocab is None

    def test_unrelated_finance_topic_returns_none(self):
        vocab = _detect_topic_vocabulary("stock market investment strategies")
        assert vocab is None

    def test_word_boundary_prevents_false_match_skill_kill(self):
        """'skill' should NOT match the 'kill' signal keyword."""
        vocab = _detect_topic_vocabulary("skill development and career growth")
        assert vocab is None

    def test_word_boundary_prevents_false_match_rapid_pid(self):
        """'rapid' should NOT match the 'pid' process ID keyword."""
        vocab = _detect_topic_vocabulary("rapid software development methodology")
        assert vocab is None

    def test_pid_keyword_matches_linux_category(self):
        vocab = _detect_topic_vocabulary("Understanding PIDs in Linux")
        assert vocab is not None
        assert "terminal" in vocab.lower() or "linux" in vocab.lower()

    def test_htop_keyword_matches_linux_category(self):
        vocab = _detect_topic_vocabulary("Using htop to monitor processes")
        assert vocab is not None

    def test_compiler_keyword_matches_c_category(self):
        vocab = _detect_topic_vocabulary("C++ compiler optimisations")
        assert vocab is not None
        assert "compiler" in vocab.lower() or "terminal" in vocab.lower()

    def test_returns_string_when_matched(self):
        vocab = _detect_topic_vocabulary("python decorators")
        assert isinstance(vocab, str)
        assert len(vocab) > 0

    def test_case_insensitive_matching(self):
        vocab_lower = _detect_topic_vocabulary("linux process")
        vocab_upper = _detect_topic_vocabulary("LINUX PROCESS")
        assert vocab_lower == vocab_upper


# ---------------------------------------------------------------------------
# Tests: _build_visual_prompt
# ---------------------------------------------------------------------------

class TestBuildVisualPrompt:
    # --- Primary path: visual_concept is populated ---

    def test_uses_visual_concept_when_available(self):
        segment = {
            "visual_concept": "htop terminal showing PID list, dark background",
            "on_screen_text": "Process management",
        }
        prompt = _build_visual_prompt(segment, "Linux processes")
        assert "htop terminal showing PID list" in prompt

    def test_injects_topic_vocab_when_concept_not_grounded(self):
        """A generic visual_concept without grounding keywords gets topic vocab injected."""
        segment = {
            "visual_concept": "a colorful abstract background with gradient",
        }
        prompt = _build_visual_prompt(segment, "Linux process")
        # Should inject linux/terminal vocabulary
        assert "terminal" in prompt.lower() or "linux" in prompt.lower()

    def test_no_double_injection_when_concept_already_grounded(self):
        """A visual_concept with grounding keywords (e.g. 'terminal') should not
        be duplicated with extra vocabulary."""
        segment = {
            "visual_concept": "a dark terminal window showing process tree, PID numbers",
        }
        prompt = _build_visual_prompt(segment, "Operating System")
        # The concept itself should appear intact
        assert "a dark terminal window showing process tree, PID numbers" in prompt

    def test_grounded_concept_with_code_keyword(self):
        segment = {
            "visual_concept": "Python source code file with syntax highlighting",
        }
        prompt = _build_visual_prompt(segment, "Python decorators")
        assert "Python source code file with syntax highlighting" in prompt

    def test_grounded_concept_with_diagram_keyword(self):
        segment = {
            "visual_concept": "operating system architecture diagram with kernel layers",
        }
        prompt = _build_visual_prompt(segment, "Operating System kernel")
        assert "operating system architecture diagram" in prompt

    # --- Fallback path: visual_concept is empty ---

    def test_fallback_uses_on_screen_text_when_concept_empty(self):
        segment = {
            "visual_concept": "",
            "on_screen_text": "Memory management",
        }
        prompt = _build_visual_prompt(segment, "Operating System")
        assert "Memory management" in prompt or "operating system" in prompt.lower()

    def test_fallback_uses_topic_when_both_concept_and_text_empty(self):
        segment = {
            "visual_concept": "",
            "on_screen_text": "",
        }
        prompt = _build_visual_prompt(segment, "Python decorators")
        assert "Python decorators" in prompt

    def test_fallback_injects_topic_vocab_for_known_topic(self):
        """Even in fallback mode, recognised topics should get their vocab injected."""
        segment = {
            "visual_concept": "",
            "on_screen_text": "process states",
        }
        prompt = _build_visual_prompt(segment, "Linux process")
        assert "terminal" in prompt.lower() or "linux" in prompt.lower()

    # --- Quality modifiers and negative keywords (always appended) ---

    def test_always_includes_negative_finance_keyword(self):
        segment = {"visual_concept": "htop terminal showing process tree"}
        prompt = _build_visual_prompt(segment, "Linux")
        assert "no finance charts" in prompt.lower()

    def test_always_includes_no_text_negative_keyword(self):
        segment = {"visual_concept": "htop terminal showing process tree"}
        prompt = _build_visual_prompt(segment, "Linux")
        assert "no text" in prompt.lower()

    def test_always_includes_quality_modifiers(self):
        segment = {"visual_concept": "htop terminal showing process tree"}
        prompt = _build_visual_prompt(segment, "Linux")
        assert "high quality" in prompt.lower()

    def test_always_includes_educational_style(self):
        segment = {"visual_concept": "some terminal window"}
        prompt = _build_visual_prompt(segment, "Linux")
        assert "educational" in prompt.lower()

    # --- Domain rules integration ---

    def test_with_tech_os_category_includes_domain_avoid_visuals(self):
        segment = {"visual_concept": "some abstract visual"}
        prompt = _build_visual_prompt(
            segment, "operating system", category="tech", subcategory="Operating Systems"
        )
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        # Should NOT have finance chart keywords in positive context
        assert "stock market monitor" not in prompt.lower() or "no stock market monitor" in prompt.lower()

    def test_with_finance_category_uses_finance_domain_vocab(self):
        segment = {"visual_concept": "compound interest growth curve"}
        prompt = _build_visual_prompt(
            segment, "compound interest", category="finance"
        )
        # Compound interest concept should pass through intact
        assert "compound interest growth curve" in prompt

    # --- Return type and basic contract ---

    def test_returns_non_empty_string(self):
        segment = {"visual_concept": "some visual concept"}
        prompt = _build_visual_prompt(segment, "any topic")
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_missing_keys_do_not_crash(self):
        """The function must not crash when optional keys are absent from segment."""
        prompt = _build_visual_prompt({}, "Linux process")
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_none_values_do_not_crash(self):
        """The function must handle None values gracefully."""
        segment = {"visual_concept": None, "on_screen_text": None}
        prompt = _build_visual_prompt(segment, "Linux process")
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    # --- Integration: prompt is specific enough to avoid finance imagery ---

    def test_os_topic_prompt_excludes_stock_market(self):
        """The canonical problem: OS concept should not generate stock market imagery."""
        segment = {
            "visual_concept": "process scheduler round-robin diagram",
        }
        prompt = _build_visual_prompt(
            segment, "Operating System", category="tech", subcategory="Operating Systems"
        )
        # Negative keyword should explicitly exclude finance charts
        assert "no finance charts" in prompt.lower() or "no trading" in prompt.lower()

    def test_different_topics_produce_different_prompts(self):
        seg_linux = {"visual_concept": "linux process states diagram"}
        seg_finance = {"visual_concept": "compound interest chart"}
        prompt_linux = _build_visual_prompt(seg_linux, "Linux")
        prompt_finance = _build_visual_prompt(seg_finance, "Finance")
        assert prompt_linux != prompt_finance
