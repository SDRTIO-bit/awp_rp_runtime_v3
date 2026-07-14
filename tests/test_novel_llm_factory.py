from awp_rp_runtime_v3.runtime.novel_llm_factory import NovelLLMFactory


def test_opencode_global_model_override_applies_to_pi_brain(monkeypatch):
    monkeypatch.setenv("NOVEL_LLM_PROVIDER", "opencode")
    monkeypatch.setenv("NOVEL_LLM_MODEL", "kimi-k2.6")

    factory = NovelLLMFactory()
    config = factory.get_pi_agent_connection()

    assert config.model == "kimi-k2.6"
    assert config.api_key_env == "OPENCODE_API_KEY"
    assert config.api_key is None
