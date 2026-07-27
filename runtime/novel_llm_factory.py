"""Novel LLM Factory —— shared DeepSeek adapter instances for novel mode.

Provides configured DeepSeekAdapter instances for each novel agent role.
Thinking is controlled via extra_body, not ModelProfile.

max_tokens 与计划文档一致（plan 1040-1047 行）。之前误设为 0 会触发
DeepSeekAdapter 的 "thinking 吃光 content 后 max_tokens=16000 重试" 分支，
单次调用烧 1-3 万 token。务必保持显式上界。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from ..adapters.llm.deepseek_adapter import DeepSeekAdapter

# Thinking configurations per agent role
THINKING_HIGH = {"thinking": {"type": "enabled", "reasoning_effort": "high"}}
THINKING_MEDIUM = {"thinking": {"type": "enabled", "reasoning_effort": "medium"}}
THINKING_LOW = {"thinking": {"type": "enabled", "reasoning_effort": "low"}}
THINKING_DISABLED = {"thinking": {"type": "disabled"}}

# Model configurations per agent role
# max_tokens 对齐 plan 表格，避免无限消耗。
ROLE_CONFIGS = {
    "director":          {"model": "deepseek-v4-pro",   "max_tokens": 8000, "thinking": THINKING_HIGH},
    "architect":         {"model": "deepseek-v4-pro",    "max_tokens": 20000, "thinking": THINKING_DISABLED},
    "npc_planner":       {"model": "deepseek-v4-pro",    "max_tokens": 4000, "thinking": THINKING_HIGH},
    "writer":            {"model": "deepseek-v4-pro",   "max_tokens": 4000, "thinking": THINKING_DISABLED},
    "continuity_checker": {"model": "deepseek-v4-pro",   "max_tokens": 4000, "thinking": THINKING_DISABLED},
    "brain":              {"model": "deepseek-v4-pro",   "max_tokens": 2000, "thinking": THINKING_LOW},
    "style_cleaner":     {"model": "deepseek-v4-pro",   "max_tokens": 2000, "thinking": THINKING_DISABLED},
    "ledger_curator":    {"model": "deepseek-v4-pro",   "max_tokens": 4000, "thinking": THINKING_DISABLED},
    # ── 三段式 Polish 管线专用角色 ──
    "polish_audit":      {"model": "deepseek-v4-pro",   "max_tokens": 8000, "thinking": THINKING_HIGH},
    "polish_repair":     {"model": "deepseek-v4-pro",   "max_tokens": 16000, "thinking": THINKING_DISABLED},
    "polish_verify":     {"model": "deepseek-v4-pro",   "max_tokens": 8000, "thinking": THINKING_HIGH},
    # ── V4: 精确补丁生成，不需要强推理，走 Writer 同款模型节省 DeepSeek 配额 ──
    "mechanical_patch":  {"model": "deepseek-v4-pro",   "max_tokens": 4000, "thinking": THINKING_DISABLED},
    # ── V3 新增：Writer Low + DESIGN 审计 ──
    "writer_low":        {"model": "deepseek-v4-pro",   "max_tokens": 4000, "thinking": THINKING_DISABLED},
    "design_audit":      {"model": "deepseek-v4-pro",   "max_tokens": 8000, "thinking": THINKING_HIGH},
}


@dataclass(frozen=True)
class NovelPiConnectionConfig:
    """Non-secret model settings passed to the embedded Pi host."""

    provider: str
    model: str
    base_url: str
    api_key_env: str
    thinking_level: str = "low"
    max_tokens: int = 4000
    api_key: None = None


class NovelLLMFactory:
    """Factory for creating LLM adapter instances for novel agents.

    Provider selection (env-driven, default = deepseek to preserve tests):
      NOVEL_LLM_PROVIDER=opencode  -> OpenAICompatibleAdapter @ OpenCode Zen gateway
      NOVEL_LLM_PROVIDER=deepseek  -> DeepSeekAdapter (default)
      unset or other              -> DeepSeekAdapter (default)

    Per-project overrides are a dict of role→config merged on top of
    the hardcoded ROLE_CONFIGS.  They are stored in novel_projects.config
    under the "llm_overrides" key and applied via set_project_overrides().
    """

    _instance: NovelLLMFactory | None = None
    _adapters: dict[str, Any] = {}
    _project_overrides: dict[str, Any] = {}  # merged into _role_config

    @classmethod
    def get_instance(cls) -> NovelLLMFactory:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @staticmethod
    def _provider_choice(role: str = "") -> str:
        """Return provider for role, falling back to global NOVEL_LLM_PROVIDER.
        Project overrides take priority over env."""
        instance = NovelLLMFactory.get_instance()
        project = instance._project_overrides.get(role, {})
        p_provider = project.get("provider", "")
        if p_provider:
            return p_provider
        import os
        if role:
            per_role = os.environ.get(f"NOVEL_LLM_PROVIDER_{role.upper()}")
            if per_role:
                return per_role.lower()
        return (os.environ.get("NOVEL_LLM_PROVIDER") or "deepseek").lower()

    @staticmethod
    def _is_siliconflow() -> bool:
        import os
        return (os.environ.get("NOVEL_LLM_PROVIDER") or "").lower() == "siliconflow"

    def get_adapter(self, role: str):
        """Get or create an adapter for the given role.

        Provider is chosen from env NOVEL_LLM_PROVIDER. DeepSeek-only
        extra_body keys (e.g. ``thinking``) are stripped by OpenAICompatibleAdapter.
        """
        if role not in self._adapters:
            config = self._role_config(role)
            provider = self._provider_choice(role)

            if provider == "mimo":
                from ..adapters.llm.openai_compatible import OpenAICompatibleAdapter
                self._adapters[role] = OpenAICompatibleAdapter(
                    model=os.environ.get("NOVEL_LLM_MODEL", "mimo-v2.5-pro"),
                    base_url=os.environ.get(
                        "NOVEL_LLM_BASE_URL",
                        "https://token-plan-cn.xiaomimimo.com/v1",
                    ),
                    api_key_env=os.environ.get(
                        "NOVEL_LLM_API_KEY_ENV", "MIMO_API_KEY",
                    ),
                    default_max_tokens=config["max_tokens"],
                    timeout_seconds=180,
                    max_retries=2,
                )
            elif provider == "siliconflow":
                from ..adapters.llm.openai_compatible import OpenAICompatibleAdapter
                import os, sys
                default_model = os.environ.get("NOVEL_LLM_MODEL", "Pro/deepseek-ai/DeepSeek-R1")
                self._adapters[role] = OpenAICompatibleAdapter(
                    model=default_model,
                    base_url=os.environ.get(
                        "NOVEL_LLM_BASE_URL",
                        "https://api.siliconflow.cn/v1",
                    ),
                    api_key_env=os.environ.get(
                        "NOVEL_LLM_API_KEY_ENV", "SILICONFLOW_API_KEY",
                    ),
                    default_max_tokens=config["max_tokens"],
                    timeout_seconds=120,
                    max_retries=2,
                )
            elif provider == "opencode":
                from ..adapters.llm.openai_compatible import OpenAICompatibleAdapter
                self._adapters[role] = OpenAICompatibleAdapter(
                    model=config["model"],
                    base_url=os.environ.get(
                        "NOVEL_LLM_BASE_URL",
                        "https://opencode.ai/zen/go/v1",
                    ),
                    api_key_env=os.environ.get(
                        "NOVEL_LLM_API_KEY_ENV", "OPENCODE_API_KEY",
                    ),
                    default_max_tokens=config["max_tokens"],
                    timeout_seconds=120,
                    max_retries=2,
                )
            else:
                self._adapters[role] = DeepSeekAdapter(
                    model=config["model"],
                    default_max_tokens=config["max_tokens"],
                )
        return self._adapters[role]

    @staticmethod
    def _override_thinking_from_level(config: dict[str, Any], level: str) -> dict[str, Any]:
        """Apply a thinking_level string (low/medium/high/off) to a config dict."""
        overridden = dict(config)
        level = str(level or "").strip().lower()
        if level == "off":
            overridden["thinking"] = THINKING_DISABLED
        elif level == "low":
            overridden["thinking"] = THINKING_LOW
        elif level == "medium":
            overridden["thinking"] = THINKING_MEDIUM
        elif level == "high":
            overridden["thinking"] = THINKING_HIGH
        return overridden

    def _role_config(self, role: str) -> dict[str, Any]:
        """Return the merged role config, applying project overrides and
        provider-specific model defaults.

        Per-project overrides (model, max_tokens, thinking_level) take
        precedence over hardcoded ROLE_CONFIGS.
        """
        base = ROLE_CONFIGS.get(role, ROLE_CONFIGS["writer"])
        project = self._project_overrides.get(role, {})
        if project:
            overridden = dict(base)
            for key in ("model", "max_tokens"):
                if key in project:
                    overridden[key] = project[key]
            thinking_level = project.get("thinking_level") or project.get("thinking", "")
            if thinking_level:
                overridden = self._override_thinking_from_level(
                    overridden, str(thinking_level)
                )
            elif "thinking" in project:
                overridden["thinking"] = project["thinking"]
            base = overridden
        if self._provider_choice(role) not in ("opencode", "mimo", "siliconflow"):
            return base

        provider = self._provider_choice(role)
        if provider == "mimo":
            default_map = {
                "director":           "mimo-v2.5-pro",
                "architect":          "mimo-v2.5-pro",
                "writer":             "mimo-v2.5-pro",
                "continuity_checker": "mimo-v2.5-pro",
                "style_cleaner":      "mimo-v2.5-pro",
                "ledger_curator":     "mimo-v2.5-pro",
            }
            model_id = (
                os.environ.get(f"NOVEL_LLM_MODEL_{role.upper()}")
                or os.environ.get("NOVEL_LLM_MODEL")
                or default_map.get(role, "mimo-v2.5-pro")
            )
            config = {**base, "model": model_id}
            self._adjust_for_thinking_models(config, model_id)
            return config

        # Override model names with OpenCode-available ids.
        # 2026-07-05: max 长程一致性暴露问题（8K 输出窗内同句重复、48h→72h 自相矛盾），
        # 且单次调用价格是 plus 的数倍。短篇/中篇 plus 实测更稳。
        # max 仍可通过 NOVEL_LLM_MODEL_WRITER=qwen3.7-max 显式覆盖。
        # V4: ledger_curator and mechanical_patch use gemini (via opencode) to
        # save DeepSeek quota. They don't need strong reasoning — structured
        # extraction and mechanical patching are sufficient.
        default_map = {
            "director":           "qwen3.7-plus",
            "architect":          "qwen3.7-plus",
            "writer":             "qwen3.7-plus",
            "continuity_checker": "qwen3.7-plus",
            "style_cleaner":      "qwen3.7-plus",
            "ledger_curator":     "qwen3.7-plus",
            "mechanical_patch":   "qwen3.7-plus",
        }
        model_id = (
            os.environ.get(f"NOVEL_LLM_MODEL_{role.upper()}")
            or os.environ.get("NOVEL_LLM_MODEL")
            or default_map.get(role, "qwen3.7-max")
        )
        config = {**base, "model": model_id}
        self._adjust_for_thinking_models(config, model_id)
        return config

    @staticmethod
    def _adjust_for_thinking_models(config: dict[str, Any], model_id: str) -> None:
        """GLM 等内置思考模型会吃掉约 90% 的 max_tokens 做 internal reasoning。
        放大 max_tokens 以避免 content 部分被挤压为 0。"""
        if "glm" in model_id.lower():
            config["max_tokens"] = config["max_tokens"] * 4

    def get_pi_agent_connection(self) -> NovelPiConnectionConfig:
        """Resolve model connection metadata without reading or returning a key."""

        return self.get_pi_role_connection("brain")

    def get_pi_role_connection(self, role: str) -> NovelPiConnectionConfig:
        """Resolve one role's non-secret Pi provider and generation settings."""

        provider = self._provider_choice(role)
        project = self._project_overrides.get(role, {})
        role_suffix = role.upper()
        thinking = self.get_thinking_config(role).get("thinking", {})
        thinking_level = (
            "off"
            if thinking.get("type") == "disabled"
            else str(thinking.get("reasoning_effort", "low"))
        )
        model = self.get_model(role)
        max_tokens = self.get_max_tokens(role)
        # OpenCode's Qwen 3.7 Plus route reserves a fixed 32K thinking budget.
        # A 2K-character Writer has a 4K completion cap, so leaving thinking
        # on makes Alibaba reject the request before prose generation.
        if role == "writer" and "qwen3.7-plus" in model.lower():
            thinking_level = "off"
        # Kimi reasoning models charge their visible thinking against the same
        # completion window as the final answer.  Keep the legacy adapters
        # untouched; expand only Pi's Kimi sessions according to the actual
        # amount of final content each role must return.
        if "kimi" in model.lower():
            kimi_budget_multiplier = {
                "director": 2,
                # Kimi may emit 8k+ reasoning tokens before a 2k-character
                # chapter.  Its gateway currently ignores Pi's off switch,
                # so reserve a full 16k completion window for Writer prose.
                "writer": 4,
                "continuity_checker": 2,
                "style_cleaner": 4,
                "ledger_curator": 2,
            }.get(role, 1)
            max_tokens *= kimi_budget_multiplier

        # Per-project overrides for connection-level fields
        p_provider = project.get("provider", "")
        p_base = project.get("api_base", "")
        p_key_env = project.get("api_key_env", "")

        if provider == "opencode":
            return NovelPiConnectionConfig(
                provider=p_provider or "awp-opencode",
                model=model,
                base_url=p_base or os.environ.get(
                    f"NOVEL_LLM_BASE_URL_{role_suffix}",
                    os.environ.get("NOVEL_LLM_BASE_URL", "https://opencode.ai/zen/go/v1"),
                ),
                api_key_env=p_key_env or os.environ.get(
                    f"NOVEL_LLM_API_KEY_ENV_{role_suffix}",
                    os.environ.get("NOVEL_LLM_API_KEY_ENV", "OPENCODE_API_KEY"),
                ),
                thinking_level=thinking_level,
                max_tokens=max_tokens,
            )
        if provider == "mimo":
            return NovelPiConnectionConfig(
                provider=p_provider or "awp-mimo",
                model=model,
                base_url=p_base or os.environ.get(
                    f"NOVEL_LLM_BASE_URL_{role_suffix}",
                    os.environ.get(
                        "NOVEL_LLM_BASE_URL",
                        "https://token-plan-cn.xiaomimimo.com/v1",
                    ),
                ),
                api_key_env=p_key_env or os.environ.get(
                    f"NOVEL_LLM_API_KEY_ENV_{role_suffix}",
                    os.environ.get("NOVEL_LLM_API_KEY_ENV", "MIMO_API_KEY"),
                ),
                thinking_level=thinking_level,
                max_tokens=max_tokens,
            )
        if provider == "siliconflow":
            return NovelPiConnectionConfig(
                provider=p_provider or "awp-siliconflow",
                model=model,
                base_url=p_base or os.environ.get(
                    f"NOVEL_LLM_BASE_URL_{role_suffix}",
                    os.environ.get("NOVEL_LLM_BASE_URL", "https://api.siliconflow.cn/v1"),
                ),
                api_key_env=p_key_env or os.environ.get(
                    f"NOVEL_LLM_API_KEY_ENV_{role_suffix}",
                    os.environ.get("NOVEL_LLM_API_KEY_ENV", "SILICONFLOW_API_KEY"),
                ),
                thinking_level=thinking_level,
                max_tokens=max_tokens,
            )
        return NovelPiConnectionConfig(
            provider=p_provider or "awp-deepseek",
            model=model,
            base_url=p_base or os.environ.get(
                f"NOVEL_LLM_BASE_URL_{role_suffix}",
                os.environ.get("NOVEL_LLM_BASE_URL", "https://api.deepseek.com/v1"),
            ),
            api_key_env=p_key_env or os.environ.get(
                f"NOVEL_LLM_API_KEY_ENV_{role_suffix}",
                os.environ.get("NOVEL_LLM_API_KEY_ENV", "DEEPSEEK_API_KEY"),
            ),
            thinking_level=thinking_level,
            max_tokens=max_tokens,
        )

    def get_pi_role_connections(self) -> dict[str, NovelPiConnectionConfig]:
        """Return non-secret Pi settings for every automated novel role."""

        roles = (
            "architect",
            "npc_planner",
            "director",
            "writer",
            "continuity_checker",
            "style_cleaner",
            "ledger_curator",
        )
        return {role: self.get_pi_role_connection(role) for role in roles}

    def get_thinking_config(self, role: str) -> dict[str, Any]:
        config = self._role_config(role)
        return config["thinking"]

    def get_model(self, role: str) -> str:
        config = self._role_config(role)
        return config["model"]

    def get_max_tokens(self, role: str) -> int:
        config = self._role_config(role)
        return config["max_tokens"]

    def is_available(self) -> bool:
        try:
            adapter = self.get_adapter("writer")
            return adapter.is_available
        except Exception:
            return False

    def reset(self) -> None:
        """Reset all adapters and project overrides (for testing)."""
        self._adapters.clear()
        self._project_overrides.clear()

    def set_project_overrides(self, overrides: dict[str, dict[str, Any]]) -> None:
        """Replace all per-project role overrides.  Clear adapter cache so
        next get_adapter() picks up new config."""
        self._project_overrides = dict(overrides or {})
        self._adapters.clear()

    def get_project_overrides(self) -> dict[str, dict[str, Any]]:
        return dict(self._project_overrides)


ROLE_NAMES = tuple(ROLE_CONFIGS.keys())
"""All known role names for API introspection."""
