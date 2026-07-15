from awp_rp_runtime_v3.runtime.novel_llm_factory import NovelLLMFactory


def test_opencode_global_model_override_applies_to_pi_brain(monkeypatch):
    monkeypatch.setenv("NOVEL_LLM_PROVIDER", "opencode")
    monkeypatch.setenv("NOVEL_LLM_MODEL", "qwen3.7-plus")

    factory = NovelLLMFactory()
    config = factory.get_pi_agent_connection()

    assert config.model == "qwen3.7-plus"
    assert config.api_key_env == "OPENCODE_API_KEY"
    assert config.api_key is None


def test_pi_role_connections_are_role_specific_and_secret_free(monkeypatch):
    monkeypatch.setenv("NOVEL_LLM_PROVIDER", "opencode")
    monkeypatch.setenv("NOVEL_LLM_MODEL", "qwen3.7-plus")

    configs = NovelLLMFactory().get_pi_role_connections()

    assert set(configs) == {
        "architect",
        "director",
        "writer",
        "continuity_checker",
        "style_cleaner",
        "ledger_curator",
        "npc_planner",
    }
    assert configs["writer"].model == "qwen3.7-plus"
    assert configs["writer"].max_tokens == 4000
    assert configs["writer"].thinking_level == "off"
    assert configs["ledger_curator"].max_tokens == 4000
    assert configs["director"].max_tokens == 8000
    assert configs["continuity_checker"].max_tokens == 4000
    assert configs["style_cleaner"].max_tokens == 2000
    assert configs["architect"].thinking_level == "off"
    assert configs["director"].thinking_level == "high"
    assert all(config.api_key is None for config in configs.values())
