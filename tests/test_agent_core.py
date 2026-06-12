"""Agent core: prompt assembly, disclosure, language (EPIC-002 plan B1/B2)."""

from assistant_shared.schemas import StructuredGoal
from assistant_worker.call.agent import (
    DISCLOSURE,
    AgentConfig,
    ProfileFactView,
    allowed_facts,
    approval_filler,
    build_system_prompt,
    disclosure_text,
    resolve_language,
)


def _goal(**kwargs) -> StructuredGoal:
    return StructuredGoal(
        objective=kwargs.get("objective", "Записаться к стоматологу"),
        constraints=kwargs.get("constraints", ["после 17:00"]),
        allowed_facts=kwargs.get("allowed_facts", ["имя"]),
        autonomy_level=kwargs.get("autonomy_level", 1),
    )


def test_disclosure_exists_for_all_supported_languages():
    for lang in ("es", "en", "ru"):
        assert "AI" in DISCLOSURE[lang] or "ИИ" in DISCLOSURE[lang] or "inteligencia" in DISCLOSURE[lang]
        assert disclosure_text(lang) == DISCLOSURE[lang]
        assert approval_filler(lang)


def test_unknown_language_falls_back_to_spanish():
    assert disclosure_text("de") == DISCLOSURE["es"]
    config = AgentConfig(goal=_goal(), language="de")
    assert config.language == "es"


def test_resolve_language():
    assert resolve_language("ru", "+34911222333") == "ru"  # explicit pref wins
    assert resolve_language(None, "+34911222333") == "es"
    assert resolve_language(None, "+15551234567") == "es"  # default
    assert resolve_language("en", None) == "en"


def test_allowed_facts_filtering():
    config = AgentConfig(
        goal=_goal(allowed_facts=["passport"]),
        facts=[
            ProfileFactView(key="name", value="Nikita", allowed_by_default=True),
            ProfileFactView(key="passport", value="X123", sensitivity="high"),
            ProfileFactView(key="address", value="Calle Mayor 1", sensitivity="medium"),
        ],
    )
    keys = {f.key for f in allowed_facts(config)}
    assert keys == {"name", "passport"}  # address not whitelisted, not default


def test_prompt_contains_rules_objective_and_facts():
    config = AgentConfig(
        goal=_goal(),
        language="es",
        target_name="Clínica Denta",
        facts=[ProfileFactView(key="имя", value="Никита", allowed_by_default=True)],
    )
    prompt = build_system_prompt(config)
    assert "Never claim to be human" in prompt
    assert "Записаться к стоматологу" in prompt
    assert "Clínica Denta" in prompt
    assert "имя: Никита" in prompt
    assert "после 17:00" in prompt
    assert "Spanish" in prompt
    assert "AUTONOMY LEVEL: 1/3" in prompt


def test_prompt_states_caller_role_explicitly():
    # Regression: haiku introduced itself as calling FROM the callee
    # ("llamando desde Denta") because the prompt only said "CALLING: Дента".
    config = AgentConfig(goal=_goal(), language="es", target_name="Дента")
    prompt = build_system_prompt(config)
    assert "NOT your client" in prompt
    assert "on behalf of your client" in prompt
    assert "never introduce yourself as calling from" in prompt


def test_high_sensitivity_facts_marked_for_approval_in_prompt():
    # High facts may be visible to the agent but must be gated behind
    # request_approval(share_sensitive_data) - the prompt must say so.
    config = AgentConfig(
        goal=_goal(),
        facts=[
            ProfileFactView(key="nie", value="Y1715405X", sensitivity="high", allowed_by_default=True),
            ProfileFactView(key="имя", value="Никита", sensitivity="low", allowed_by_default=True),
        ],
    )
    prompt = build_system_prompt(config)
    assert "nie: Y1715405X [SENSITIVE" in prompt
    assert "имя: Никита [SENSITIVE" not in prompt
    assert "share_sensitive_data" in prompt


def test_whispers_appended_to_prompt():
    config = AgentConfig(goal=_goal(), whispers=["Соглашайся только до 50 евро"])
    prompt = build_system_prompt(config)
    assert "Соглашайся только до 50 евро" in prompt
    assert "LIVE INSTRUCTIONS" in prompt


def test_prompt_includes_role_fewshot_for_es():
    from assistant_worker.call.agent import AgentConfig, build_system_prompt, ProfileFactView
    from assistant_shared.schemas import StructuredGoal

    config = AgentConfig(
        goal=StructuredGoal(objective="Reservar cita", scenario="doctor"),
        language="es",
        target_name="Clínica Dental",
        facts=[ProfileFactView(key="Nombre", value="Nikita", sensitivity="low",
                               allowed_by_default=True)],
    )
    prompt = build_system_prompt(config)
    assert "EXAMPLE" in prompt
    assert "a nombre de" in prompt.lower()


def test_prompt_renders_call_facts_block():
    config = AgentConfig(
        goal=StructuredGoal(objective="Reservar", call_facts={"имя брони": "Victoria"}),
    )
    prompt = build_system_prompt(config)
    assert "DETAILS FOR THIS CALL" in prompt
    assert "имя брони: Victoria" in prompt


def test_prompt_omits_call_facts_block_when_empty():
    config = AgentConfig(goal=StructuredGoal(objective="Reservar"))
    # The block header (with parenthetical) must not appear; the fewshot may still
    # reference "DETAILS FOR THIS CALL" as a concept.
    assert "DETAILS FOR THIS CALL (state these" not in build_system_prompt(config)


def test_role_fewshot_points_to_call_details_not_only_allowed_facts():
    from assistant_worker.call.agent import ROLE_FEWSHOT
    for lang in ("es", "en", "ru"):
        assert "DETAILS FOR THIS CALL" in ROLE_FEWSHOT[lang]


def test_termination_wrapup_exists_for_all_languages():
    from assistant_worker.call.agent import termination_wrapup
    for lang in ("es", "en", "ru"):
        assert termination_wrapup(lang)
    assert termination_wrapup("de") == termination_wrapup("es")  # fallback


def test_preamble_requires_end_call():
    config = AgentConfig(goal=_goal())
    prompt = build_system_prompt(config).lower()
    assert "end_call" in prompt and "must" in prompt
