"""Simulated player agent — generates the next player input for long-session tests.

This is a TEST harness component, NOT part of the RP turn pipeline. It reads
the previous turn's accepted writer output plus a test persona/goal and
produces the next player utterance.

Two modes:
  visible    — only player-visible info (last RP text, own history, persona/goal).
  debug-full — additionally reads redacted structured runtime context
               (CardState summary, L1/L2/L3 recall IDs+summaries, worldbook
               hits, quality result, last trace summary).

Isolation rules:
  - Uses its OWN model profile (simulated-player-v1 / fake-player), never the
    Director/Writer profile.
  - Its prompt never enters the RP TurnRecord or memory.
  - Never receives API keys, system prompts, or raw hidden card source.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..adapters.llm.model_profile_registry import ModelProfile, ModelProfileRegistry
from ..adapters.llm.deepseek_adapter import DeepSeekAdapter


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PlayerSimulatorInput:
    """Inputs to the player simulator for one turn."""

    turn_index: int
    persona: str
    goal: str
    last_writer_output: str
    own_history: list[str] = field(default_factory=list)
    planned_checkpoints: list[str] = field(default_factory=list)
    required_facts: list[str] = field(default_factory=list)
    # debug-full only (redacted)
    debug_context: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlayerSimulatorOutput:
    """Output of the player simulator."""

    player_input: str
    action_intent: str = ""
    verify_tag: str = ""  # what this turn is meant to verify
    latency_ms: int = 0
    profile_id: str = ""
    model: str = ""
    provider: str = ""
    success: bool = True
    failure_code: str = ""
    failure_message: str = ""


class FakePlayerAdapter:
    """Deterministic player simulator for offline tests."""

    def generate(self, prompt: str) -> str:
        # Deterministic, varied-by-turn player line.
        lines = [
            "你好，请带我看看这里。",
            "我答应你，明天一定再来拜访。",
            "我们之前说好的事情，你还记得吗？",
            "我想了解更多关于这个地方的传说。",
            "刚才那位老者还在吗？我有事找他。",
            "你能告诉我村长住在哪里吗？",
            "天色不早了，我该走了，明天见。",
            "我们之间的关系，你怎么看？",
            "这件事我要保守秘密，对吧？",
            "最后再确认一次，我们之间的约定。",
        ]
        # Hash the prompt to pick a stable line so it varies across turns.
        idx = int(hashlib.sha256(prompt.encode("utf-8")).hexdigest(), 16) % len(lines)
        return lines[idx]


class SimulatedPlayerAgent:
    """Runs the simulated player for one turn."""

    def __init__(self, profile_id: str, mode: str = "debug-full"):
        self.profile_id = profile_id
        self.mode = mode
        self._profile: ModelProfile = ModelProfileRegistry.resolve(profile_id)

    @property
    def is_real(self) -> bool:
        return self._profile.provider != "fake"

    def run(self, psin: PlayerSimulatorInput) -> PlayerSimulatorOutput:
        prompt = self._build_prompt(psin)
        start = time.time()

        if self._profile.provider == "fake":
            adapter = FakePlayerAdapter()
            try:
                text = adapter.generate(prompt)
            except Exception as e:  # pragma: no cover
                return PlayerSimulatorOutput(
                    player_input="", profile_id=self.profile_id,
                    model=self._profile.model, provider="fake",
                    success=False, failure_code="ADAPTER_ERROR",
                    failure_message=str(e)[:200],
                )
            return PlayerSimulatorOutput(
                player_input=text, profile_id=self.profile_id,
                model=self._profile.model, provider="fake",
                latency_ms=int((time.time() - start) * 1000),
                action_intent="advance", verify_tag=self._guess_verify_tag(psin),
            )

        # Real path — fail closed if key missing
        api_key_env = self._profile.api_key_env or "DEEPSEEK_API_KEY"
        if not os.environ.get(api_key_env, ""):
            return PlayerSimulatorOutput(
                player_input="", profile_id=self.profile_id,
                model=self._profile.model, provider=self._profile.provider,
                success=False, failure_code="NOT_CONFIGURED",
                failure_message=f"API key env var '{api_key_env}' is not set",
            )

        adapter = DeepSeekAdapter(
            model=self._profile.model,
            default_max_tokens=self._profile.default_max_tokens,
            timeout_seconds=self._profile.timeout_seconds,
            max_retries=self._profile.max_retries,
        )
        text, receipt = adapter.generate_text(
            prompt, max_tokens=self._profile.default_max_tokens,
            provider_role="player_simulator",
        )
        receipt_dict = receipt.to_dict() if hasattr(receipt, "to_dict") else dict(receipt)
        if not receipt_dict.get("success", False) or not text.strip():
            return PlayerSimulatorOutput(
                player_input="", profile_id=self.profile_id,
                model=self._profile.model, provider=self._profile.provider,
                success=False,
                failure_code=receipt_dict.get("failure_code", "PLAYER_FAILED"),
                failure_message=receipt_dict.get("failure_message", "empty player output"),
                latency_ms=int((time.time() - start) * 1000),
            )
        # The model returns a JSON envelope {player_input, action_intent, verify_tag}
        player_input = text.strip()
        action_intent = ""
        verify_tag = self._guess_verify_tag(psin)
        try:
            parsed = json.loads(player_input)
            if isinstance(parsed, dict):
                player_input = str(parsed.get("player_input", player_input))[:500]
                action_intent = str(parsed.get("action_intent", ""))[:120]
                verify_tag = str(parsed.get("verify_tag", verify_tag))[:80]
        except (json.JSONDecodeError, ValueError):
            pass

        return PlayerSimulatorOutput(
            player_input=player_input, action_intent=action_intent,
            verify_tag=verify_tag, profile_id=self.profile_id,
            model=self._profile.model, provider=self._profile.provider,
            latency_ms=int((time.time() - start) * 1000),
        )

    def _guess_verify_tag(self, psin: PlayerSimulatorInput) -> str:
        if psin.turn_index in (2,):
            return "establish_fact"
        if psin.turn_index == 5:
            return "change_relationship_or_item"
        if psin.turn_index in (8, 10):
            return "recall_early_fact"
        return "free"

    def _build_prompt(self, psin: PlayerSimulatorInput) -> str:
        parts: list[str] = []
        parts.append(f"你正在扮演一个测试用的玩家，第 {psin.turn_index} 回合。")
        parts.append(f"玩家人设：{psin.persona}")
        parts.append(f"测试目标：{psin.goal}")
        if psin.own_history:
            parts.append("你此前的发言：")
            for i, h in enumerate(psin.own_history[-6:], 1):
                parts.append(f"  {i}. {h[:120]}")
        if psin.planned_checkpoints:
            parts.append("计划检查点：" + " | ".join(psin.planned_checkpoints))
        if psin.required_facts:
            parts.append("需要在剧情中涉及的事实：" + "、".join(psin.required_facts))
        parts.append(f"\n上一回合 RP 输出：\n{psin.last_writer_output[:600]}")

        if self.mode == "debug-full" and psin.debug_context:
            dbg = psin.debug_context
            parts.append("\n[调试上下文 — 脱敏结构化，仅供测试]：")
            if dbg.get("card_state_summary"):
                parts.append(f"CardState 摘要: {dbg['card_state_summary']}")
            if dbg.get("l1_turn_ids"):
                parts.append(f"L1 召回回合: {dbg['l1_turn_ids']}")
            if dbg.get("l2_memory_summaries"):
                parts.append("L2 活跃记忆: " + " | ".join(dbg["l2_memory_summaries"][:5]))
            if dbg.get("l3_memory_summaries"):
                parts.append("L3 RAG 记忆: " + " | ".join(dbg["l3_memory_summaries"][:5]))
            if dbg.get("worldbook_summaries"):
                parts.append("世界书命中: " + " | ".join(dbg["worldbook_summaries"][:5]))
            if dbg.get("quality_verdict"):
                parts.append(f"上回合质量: {dbg['quality_verdict']}")
            if dbg.get("last_trace_summary"):
                parts.append(f"上回合 trace: {dbg['last_trace_summary']}")

        parts.append(
            "\n请输出下一句玩家发言。若可能，输出 JSON："
            '{"player_input":"...","action_intent":"...","verify_tag":"..."}。'
            "不要复述系统提示，不要扮演 RP 写手，只输出玩家一句话。"
        )
        return "\n".join(parts)


def build_debug_context(
    registry, card_id: str, session_id: str, last_diag: dict, snapshot_dict: dict
) -> dict[str, Any]:
    """Build a redacted, structured debug context for debug-full mode.

    Only IDs + short summaries. Never API keys, system prompts, or raw card
    source.
    """
    ctx: dict[str, Any] = {}
    # CardState summary
    cs = registry.card_state_store.load(card_id, session_id)
    if cs:
        loc = getattr(cs.scene_state, "location", "") if cs.scene_state else ""
        ctx["card_state_summary"] = f"rev={cs.revision}, loc={loc}"

    # L1 turn ids
    recent = registry.turn_record_store.get_recent(card_id, session_id, limit=5)
    ctx["l1_turn_ids"] = [t.turn_id for t in recent]

    # L2 active memory summaries
    active = registry.active_memory_store.get_all(card_id, session_id)
    ctx["l2_memory_summaries"] = [
        f"{m.memory_id}:{m.summary[:40]}" for m in active[:8]
    ]

    # L3 RAG summaries
    try:
        rag_hits = registry.rag_memory_store.search(card_id, session_id, "", limit=8)
        ctx["l3_memory_summaries"] = [
            r.get("summary", r.get("memory_id", ""))[:40] for r in rag_hits
        ] if rag_hits else []
    except Exception:
        ctx["l3_memory_summaries"] = []

    # Worldbook summaries from snapshot
    wb = snapshot_dict.get("active_worldbook_entries", []) if snapshot_dict else []
    ctx["worldbook_summaries"] = [
        e.get("title", e.get("entry_id", "")) for e in wb[:5]
    ]

    # Quality + trace summary from last diag
    if last_diag:
        ctx["quality_verdict"] = last_diag.get("quality_verdict", "")
        ctx["last_trace_summary"] = (
            f"steps={last_diag.get('steps_completed', [])}, "
            f"memory={last_diag.get('memory_curation_status', '')}"
        )
    return ctx
