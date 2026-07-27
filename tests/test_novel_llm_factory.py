from awp_rp_runtime_v3.runtime.novel_llm_factory import ROLE_CONFIGS, NovelLLMFactory


def test_deepseek_default_uses_v4_pro_for_every_novel_role(monkeypatch):
    monkeypatch.delenv("NOVEL_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("NOVEL_LLM_MODEL", raising=False)

    factory = NovelLLMFactory.get_instance()
    factory.reset()

    assert {config["model"] for config in ROLE_CONFIGS.values()} == {"deepseek-v4-pro"}
    assert {factory.get_model(role) for role in ROLE_CONFIGS} == {"deepseek-v4-pro"}


def test_opencode_global_model_override_applies_to_pi_brain(monkeypatch):
    monkeypatch.setenv("NOVEL_LLM_PROVIDER", "opencode")
    monkeypatch.setenv("NOVEL_LLM_MODEL", "qwen3.7-plus")

    factory = NovelLLMFactory.get_instance()
    factory.reset()
    config = factory.get_pi_agent_connection()

    assert config.model == "qwen3.7-plus"
    assert config.api_key_env == "OPENCODE_API_KEY"
    assert config.api_key is None


def test_opencode_deepseek_writer_disables_thinking(monkeypatch):
    monkeypatch.setenv("NOVEL_LLM_PROVIDER", "opencode")
    monkeypatch.setenv("NOVEL_LLM_MODEL", "deepseek-v4-pro")

    factory = NovelLLMFactory.get_instance()
    factory.reset()
    writer = factory.get_pi_role_connection("writer")

    assert writer.model == "deepseek-v4-pro"
    assert writer.thinking_level == "off"


def test_pi_role_connections_are_role_specific_and_secret_free(monkeypatch):
    monkeypatch.setenv("NOVEL_LLM_PROVIDER", "opencode")
    monkeypatch.setenv("NOVEL_LLM_MODEL", "qwen3.7-plus")

    factory = NovelLLMFactory.get_instance()
    factory.reset()
    configs = factory.get_pi_role_connections()

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


def test_project_overrides_apply_to_role_config(monkeypatch):
    monkeypatch.delenv("NOVEL_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("NOVEL_LLM_MODEL", raising=False)

    factory = NovelLLMFactory.get_instance()
    factory.reset()
    factory.set_project_overrides({
        "writer": {"model": "custom-model", "max_tokens": 12345, "thinking_level": "high"},
    })

    config = factory.get_pi_role_connection("writer")
    assert config.model == "custom-model"
    assert config.max_tokens == 12345
    assert config.thinking_level == "high"


def test_thinking_level_overrides_default_thinking(monkeypatch):
    monkeypatch.delenv("NOVEL_LLM_PROVIDER", raising=False)

    factory = NovelLLMFactory.get_instance()
    factory.reset()
    # Director default is THINKING_HIGH
    original = factory.get_pi_role_connection("director")
    assert original.thinking_level == "high"

    factory.set_project_overrides({
        "director": {"thinking_level": "off"},
    })
    overridden = factory.get_pi_role_connection("director")
    assert overridden.thinking_level == "off"

    # Reset and ensure the override is cleared
    factory.reset()
    reset = factory.get_pi_role_connection("director")
    assert reset.thinking_level == "high"


def test_project_overrides_isolated_between_resets(monkeypatch):
    monkeypatch.delenv("NOVEL_LLM_PROVIDER", raising=False)

    factory = NovelLLMFactory.get_instance()
    factory.reset()
    factory.set_project_overrides({
        "writer": {"model": "project-a-model"},
    })

    config_a = factory.get_pi_role_connection("writer")
    assert config_a.model == "project-a-model"

    # Simulate project B
    factory.reset()
    factory.set_project_overrides({
        "writer": {"model": "project-b-model"},
    })

    config_b = factory.get_pi_role_connection("writer")
    assert config_b.model == "project-b-model"

    # Switch back to project A
    factory.reset()
    factory.set_project_overrides({
        "writer": {"model": "project-a-model"},
    })
    config_a2 = factory.get_pi_role_connection("writer")
    assert config_a2.model == "project-a-model"
