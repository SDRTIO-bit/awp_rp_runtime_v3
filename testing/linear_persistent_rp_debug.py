"""linear_persistent_rp_debug.py — 本地线性调试工具

绕过 ComfyUI Queue / PromptExecutor / 前端连线，
直接通过 Python 串行调用 canonical persistent nodes，
定位"节点单独正常、连在一起出错"的问题。

用法:
  python -m testing.linear_persistent_rp_debug --card path/to/card.json
  python -m testing.linear_persistent_rp_debug --card card.json --real-provider
  python -m testing.linear_persistent_rp_debug --card card.json --verbose --breakpoint-after first_turn

默认行为 (fake profiles):
  bootstrap → first_turn → accepted_text_output → turn_result_probe
  → continuation_turn → accepted_text_output → turn_result_probe
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── 将项目根加入 sys.path ──────────────────────────────────────────────
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, str(Path(_PROJECT_ROOT).parent))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_prefix(text: str, n: int = 12) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:n]


def _safe_preview(text: str, max_len: int = 200) -> str:
    if not text:
        return "(empty)"
    t = text.replace("\n", " ").strip()
    return t[:max_len] + ("..." if len(t) > max_len else "")


# ═══════════════════════════════════════════════════════════════════════
# 安全打印
# ═══════════════════════════════════════════════════════════════════════

class SafePrinter:
    """只打印结构、长度、ID、hash、计数、路径。--verbose 才打印正文预览。"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def header(self, title: str) -> None:
        print(f"\n{'='*70}")
        print(f"  {title}")
        print(f"{'='*70}")

    def step(self, name: str, detail: str = "") -> None:
        prefix = f"  [{name}]"
        if detail:
            print(f"{prefix} {detail}")
        else:
            print(prefix)

    def kv(self, key: str, value: Any) -> None:
        print(f"    {key}: {value}")

    def safe_text(self, label: str, text: str) -> None:
        if self.verbose:
            self.kv(label, _safe_preview(text))
        else:
            self.kv(f"{label}_length", len(text) if text else 0)
            if text:
                self.kv(f"{label}_hash", _hash_prefix(text))

    def error(self, stage: str, node_class: str, method: str,
              exc: Exception, input_summary: str = "") -> None:
        print(f"\n  !! EXCEPTION in {stage}")
        print(f"     node_class: {node_class}")
        print(f"     method:     {method}")
        if input_summary:
            print(f"     inputs:     {input_summary}")
        print(f"     error:      {type(exc).__name__}: {exc}")
        traceback.print_exc()

    def ok(self, msg: str = "OK") -> None:
        print(f"    -> {msg}")


# ═══════════════════════════════════════════════════════════════════════
# 节点调用器
# ═══════════════════════════════════════════════════════════════════════

def call_node(node_class: type, inputs: dict[str, Any]) -> Any:
    """调用节点的 FUNCTION 方法，返回原始输出。"""
    func_name = getattr(node_class, "FUNCTION", "execute")
    method = getattr(node_class(), func_name)
    return method(**inputs)


def output_at(result: Any, index: int) -> Any:
    """从节点返回值中取第 index 个输出。
    tuple → 直接索引；dict (OUTPUT_NODE) → 返回整个 dict。
    """
    if isinstance(result, tuple):
        if index < len(result):
            return result[index]
        return None
    if isinstance(result, dict):
        return result
    return result


# ═══════════════════════════════════════════════════════════════════════
# 阶段执行器
# ═══════════════════════════════════════════════════════════════════════

class StageRunner:
    """执行一个阶段，捕获异常并报告。"""

    def __init__(self, printer: SafePrinter):
        self.p = printer

    def run(self, stage_name: str, node_class: type,
            inputs: dict[str, Any]) -> Any | None:
        class_name = node_class.__name__
        func_name = getattr(node_class, "FUNCTION", "execute")
        input_summary = f"keys={list(inputs.keys())}, types={[type(v).__name__ for v in inputs.values()]}"

        self.p.step(stage_name, f"{class_name}.{func_name}()")
        self.p.kv("input_keys", list(inputs.keys()))

        try:
            result = call_node(node_class, inputs)
            result_type = type(result).__name__
            if isinstance(result, tuple):
                self.p.kv("output", f"tuple[{len(result)}]")
            elif isinstance(result, dict):
                self.p.kv("output", f"dict keys={list(result.keys())[:5]}")
            else:
                self.p.kv("output", result_type)
            return result
        except Exception as exc:
            self.p.error(stage_name, class_name, func_name, exc, input_summary)
            return None


# ═══════════════════════════════════════════════════════════════════════
# Bootstrap 阶段
# ═══════════════════════════════════════════════════════════════════════

def run_bootstrap(args, p: SafePrinter, runner: StageRunner) -> dict[str, Any] | None:
    p.header("1. BOOTSTRAP (AWPV2PersistentBootstrap)")

    from awp_rp_runtime_v3.nodes.persistent_bootstrap_node import AWPV2PersistentBootstrap

    inputs = {
        "source_path": args.card,
        "session_id": args.session_id,
        "greeting_id": args.greeting_id,
        "request_id": f"req_bootstrap_{args.session_id}",
        "run_id": f"run_{args.session_id}",
    }

    result = runner.run("bootstrap", AWPV2PersistentBootstrap, inputs)
    if result is None:
        return None

    # 解包 5 元组: (session_binding, opening_record, worldbook_binding, bootstrap_receipt, diagnostics)
    binding = output_at(result, 0) or {}
    opening = output_at(result, 1) or {}
    worldbook = output_at(result, 2) or {}
    receipt = output_at(result, 3) or {}
    diag = output_at(result, 4) or {}

    # 安全摘要
    p.kv("logical_card_id", binding.get("logical_card_id", "?")[:20])
    p.kv("card_version", binding.get("card_version", "?"))
    p.kv("source_hash_prefix", str(binding.get("source_hash", ""))[:12])
    p.kv("session_id", binding.get("session_id", "?"))
    p.kv("opening_record_id", opening.get("opening_record_id", "?"))
    p.kv("worldbook_entry_count", len(worldbook.get("entries", [])))
    p.kv("bootstrap_status", diag.get("outcome", "?"))

    return {
        "binding": binding,
        "opening": opening,
        "worldbook": worldbook,
        "receipt": receipt,
        "diagnostics": diag,
    }


# ═══════════════════════════════════════════════════════════════════════
# First Turn 阶段
# ═══════════════════════════════════════════════════════════════════════

def run_first_turn(args, p: SafePrinter, runner: StageRunner) -> dict[str, Any] | None:
    p.header("2. FIRST TURN (AWPV2PersistentFirstTurn)")

    from awp_rp_runtime_v3.nodes.persistent_first_turn_node import AWPV2PersistentFirstTurn

    inputs = {
        "session_id": args.session_id,
        "player_input": args.first_input,
        "director_profile_id": args.director_profile,
        "writer_profile_id": args.writer_profile,
    }

    result = runner.run("first_turn", AWPV2PersistentFirstTurn, inputs)
    if result is None:
        return None

    # 解包 6 元组
    receipt = output_at(result, 0) or {}
    ctx = output_at(result, 1) or {}
    diag = output_at(result, 2) or {}
    card_state = output_at(result, 3) or {}
    turn_record = output_at(result, 4) or {}
    round_snapshot = output_at(result, 5) or {}

    _print_turn_summary(p, "first_turn", receipt, ctx, diag, card_state, turn_record)

    return {
        "receipt": receipt,
        "context": ctx,
        "diagnostics": diag,
        "card_state": card_state,
        "turn_record": turn_record,
        "round_snapshot": round_snapshot,
    }


# ═══════════════════════════════════════════════════════════════════════
# AcceptedTextOutput 阶段
# ═══════════════════════════════════════════════════════════════════════

def run_accepted_text(p: SafePrinter, runner: StageRunner,
                      turn_record: dict, label: str = "first") -> dict | None:
    p.header(f"3. ACCEPTED TEXT OUTPUT ({label})")

    from awp_rp_runtime_v3.nodes.accepted_text_output_node import AWPV2AcceptedTextOutput

    result = runner.run(f"accepted_text_{label}", AWPV2AcceptedTextOutput,
                        {"turn_record": turn_record})
    if result is None:
        return None

    # OUTPUT_NODE 返回 dict {"ui": {...}}
    ui = result.get("ui", {}) if isinstance(result, dict) else {}
    texts = ui.get("awp_accepted_text", [])
    text = texts[0] if texts else ""
    p.kv("output_type", "ui/awp_accepted_text")
    p.safe_text("accepted_text", text)

    return result


# ═══════════════════════════════════════════════════════════════════════
# TurnResultProbe 阶段
# ═══════════════════════════════════════════════════════════════════════

def run_turn_result_probe(p: SafePrinter, runner: StageRunner,
                          receipt: dict, diagnostics: dict,
                          turn_record: dict,
                          turn_kind: str = "first") -> dict | None:
    p.header(f"4. TURN RESULT PROBE ({turn_kind})")

    from awp_rp_runtime_v3.nodes.turn_result_probe_node import AWPV2TurnResultProbe

    inputs = {
        "receipt": receipt,
        "diagnostics": diagnostics,
        "turn_record": turn_record,
        "turn_kind": turn_kind,
    }

    result = runner.run(f"probe_{turn_kind}", AWPV2TurnResultProbe, inputs)
    if result is None:
        return None

    # OUTPUT_NODE 返回 dict {"ui": {...}}
    ui = result.get("ui", {}) if isinstance(result, dict) else {}
    json_str = ui.get("awp_turn_result_json", [""])[0]
    if json_str:
        try:
            proj = json.loads(json_str)
            p.kv("projection.turn_id", proj.get("turn_id", "?"))
            p.kv("projection.quality_status", proj.get("quality_status", "?"))
            p.kv("projection.accepted_text_length", proj.get("accepted_text_length", 0))
            p.kv("projection.accepted_text_hash_prefix", str(proj.get("accepted_text_hash", ""))[:12])
            p.kv("projection.card_state_revision_before", proj.get("card_state_revision_before", 0))
            p.kv("projection.card_state_revision_after", proj.get("card_state_revision_after", 0))
            p.kv("projection.memory_disposition", proj.get("memory_disposition", "?"))
            p.kv("projection.idempotency_status", proj.get("idempotency_status", "?"))
            p.kv("projection.state_effects", proj.get("state_effects", {}))
            p.kv("projection.memory_effects", proj.get("memory_effects", {}))
            p.kv("projection.delegation_effects", proj.get("delegation_effects", {}))
        except json.JSONDecodeError:
            p.kv("projection_parse", "failed")

    return result


# ═══════════════════════════════════════════════════════════════════════
# Continuation Turn 阶段
# ═══════════════════════════════════════════════════════════════════════

def run_continuation_turn(args, p: SafePrinter, runner: StageRunner) -> dict[str, Any] | None:
    p.header("5. CONTINUATION TURN (AWPV2PersistentContinuationTurn)")

    from awp_rp_runtime_v3.nodes.persistent_continuation_turn_node import AWPV2PersistentContinuationTurn

    inputs = {
        "session_id": args.session_id,
        "player_input": args.continuation_input,
        "director_profile_id": args.director_profile,
        "writer_profile_id": args.writer_profile,
    }

    result = runner.run("continuation_turn", AWPV2PersistentContinuationTurn, inputs)
    if result is None:
        return None

    # 解包 6 元组
    receipt = output_at(result, 0) or {}
    ctx = output_at(result, 1) or {}
    diag = output_at(result, 2) or {}
    card_state = output_at(result, 3) or {}
    turn_record = output_at(result, 4) or {}
    round_snapshot = output_at(result, 5) or {}

    _print_turn_summary(p, "continuation", receipt, ctx, diag, card_state, turn_record)

    return {
        "receipt": receipt,
        "context": ctx,
        "diagnostics": diag,
        "card_state": card_state,
        "turn_record": turn_record,
        "round_snapshot": round_snapshot,
    }


# ═══════════════════════════════════════════════════════════════════════
# 辅助打印
# ═══════════════════════════════════════════════════════════════════════

def _print_turn_summary(p: SafePrinter, label: str,
                        receipt: dict, ctx: dict, diag: dict,
                        card_state: dict, turn_record: dict) -> None:
    p.kv("turn_id", receipt.get("turn_id", "?"))
    p.kv("request_id", receipt.get("request_id", "?"))
    p.kv("turn_index", receipt.get("turn_index", "?"))
    p.kv("idempotency_status", receipt.get("idempotency_status", "?"))
    p.kv("quality_verdict", receipt.get("quality_verdict", "?"))
    p.kv("accepted_text_length", len(turn_record.get("writer_output", "")))
    p.safe_text("accepted_text", turn_record.get("writer_output", ""))
    p.kv("card_state_revision", card_state.get("revision", "?"))
    p.kv("card_state_commit_status", diag.get("card_state_commit_status", "?"))
    p.kv("turn_record_commit_status", diag.get("turn_record_commit_status", "?"))
    p.kv("memory_curation_status", diag.get("memory_curation_status", "?"))
    p.kv("active_memory_committed", len(diag.get("active_memory_committed_ids", [])))
    p.kv("rag_memory_committed", len(diag.get("rag_memory_committed_ids", [])))

    # effects 从 ctx 中取
    effects = ctx.get("effects", {})
    se = effects.get("state_effects", {})
    me = effects.get("memory_effects", {})
    de = effects.get("delegation", {})
    p.kv("state_effects.status", se.get("status", "?"))
    p.kv("state_effects.changed_paths", se.get("changed_paths", []))
    p.kv("memory_effects.active_added", me.get("active_added", 0))
    p.kv("memory_effects.rag_added", me.get("rag_added", 0))
    p.kv("delegation.requested", de.get("requested", []))
    p.kv("delegation.executed", de.get("executed", []))

    # worldbook entry IDs
    p.kv("worldbook_entry_ids", diag.get("worldbook_entry_ids_activated", []))


# ═══════════════════════════════════════════════════════════════════════
# Replay 验证
# ═══════════════════════════════════════════════════════════════════════

def run_replay_verification(args, p: SafePrinter, runner: StageRunner,
                            first_turn_result: dict) -> bool:
    """用完全相同的 session_id + turn_id + request_id 再调用一次 first turn，
    断言结果是 replayed。"""
    p.header("REPLAY VERIFICATION")

    from awp_rp_runtime_v3.nodes.persistent_first_turn_node import AWPV2PersistentFirstTurn

    # 复用第一次的 turn_id / request_id
    original_receipt = first_turn_result.get("receipt", {})
    original_turn_id = original_receipt.get("turn_id", "turn_first_001")
    original_request_id = original_receipt.get("request_id", "req_first_001")
    p.kv("replaying_turn_id", original_turn_id)
    p.kv("replaying_request_id", original_request_id)

    inputs = {
        "session_id": args.session_id,
        "player_input": args.first_input,
        "director_profile_id": args.director_profile,
        "writer_profile_id": args.writer_profile,
        "turn_id": original_turn_id,
        "request_id": original_request_id,
    }

    result = runner.run("replay_first_turn", AWPV2PersistentFirstTurn, inputs)
    if result is None:
        p.kv("replay_status", "FAILED (exception)")
        return False

    receipt = output_at(result, 0) or {}
    status = receipt.get("idempotency_status", "?")
    p.kv("replay_idempotency_status", status)
    ok = status == "replayed"
    p.kv("replay_verified", ok)
    return ok


# ═══════════════════════════════════════════════════════════════════════
# Restart 验证
# ═══════════════════════════════════════════════════════════════════════

def run_restart_verification(args, p: SafePrinter, runner: StageRunner) -> bool:
    """清除 RuntimeStoreFactory 缓存，重新实例化，再执行 continuation。"""
    p.header("RESTART + CONTINUATION VERIFICATION")

    from awp_rp_runtime_v3.runtime.runtime_store_factory import clear_registry_cache
    clear_registry_cache()
    p.step("restart", "Registry cache cleared")

    from awp_rp_runtime_v3.nodes.persistent_continuation_turn_node import AWPV2PersistentContinuationTurn

    inputs = {
        "session_id": args.session_id,
        "player_input": args.continuation_input,
        "director_profile_id": args.director_profile,
        "writer_profile_id": args.writer_profile,
        "turn_id": "turn_restart_001",
        "request_id": "req_restart_001",
    }

    result = runner.run("restart_continuation", AWPV2PersistentContinuationTurn, inputs)
    if result is None:
        p.kv("restart_status", "FAILED (exception)")
        return False

    receipt = output_at(result, 0) or {}
    diag = output_at(result, 2) or {}
    card_state = output_at(result, 3) or {}

    p.kv("restart_outcome", diag.get("outcome", "?"))
    p.kv("restart_idempotency", receipt.get("idempotency_status", "?"))
    p.kv("restart_card_state_revision", card_state.get("revision", "?"))
    p.kv("restart_l1_count", len(diag.get("l1_turn_ids_recalled", [])))

    ok = diag.get("outcome", "") == "success"
    p.kv("restart_verified", ok)
    return ok


# ═══════════════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="AWP RP Runtime V2 — 线性调试工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--card", required=True, help="角色卡 JSON 路径")
    parser.add_argument("--session-id", default="debug-session-001", help="Session ID")
    parser.add_argument("--greeting-id", default="g0", help="Greeting ID")
    parser.add_argument("--first-input", default="你好，我想了解一下这个世界。",
                        help="首回合玩家输入")
    parser.add_argument("--continuation-input", default="继续探索这个世界。",
                        help="续回合玩家输入")
    parser.add_argument("--director-profile", default="fake-director",
                        help="Director profile ID")
    parser.add_argument("--writer-profile", default="fake-writer",
                        help="Writer profile ID")
    parser.add_argument("--real-provider", action="store_true",
                        help="使用真实 provider (需要设置 API key)")
    parser.add_argument("--keep-db", action="store_true",
                        help="保留测试数据库")
    parser.add_argument("--verbose", action="store_true",
                        help="打印正文预览 (前 200 字)")
    parser.add_argument("--breakpoint-after", choices=["bootstrap", "first_turn", "continuation"],
                        help="在指定阶段后调用 breakpoint()")
    parser.add_argument("--replay-first-turn", action="store_true",
                        help="验证 first turn 幂等重放")
    parser.add_argument("--restart-runtime-before-continuation", action="store_true",
                        help="验证 SQLite 恢复后的 continuation")
    args = parser.parse_args()

    # ── 环境配置 ────────────────────────────────────────────────────────
    if args.real_provider:
        if not args.director_profile.startswith("fake"):
            pass  # 使用用户指定的 profile
        if not args.writer_profile.startswith("fake"):
            pass
        print("[CONFIG] 使用真实 provider — 需要 API key 环境变量已设置")
    else:
        args.director_profile = "fake-director"
        args.writer_profile = "fake-writer"
        print("[CONFIG] 使用 fake profiles (零成本)")

    # 设置测试数据库
    tmpdir = tempfile.mkdtemp(prefix="awp_debug_")
    os.environ["AWP_RUNTIME_PROFILE"] = "test"
    os.environ["AWP_TEST_STORE_ROOT"] = tmpdir
    os.environ["AWP_TEST_RUNTIME_NAMESPACE"] = args.session_id
    print(f"[CONFIG] 测试数据库: {tmpdir}")
    print(f"[CONFIG] session_id: {args.session_id}")

    p = SafePrinter(verbose=args.verbose)
    runner = StageRunner(p)

    # 验证角色卡存在
    card_path = Path(args.card)
    if not card_path.exists():
        card_path = Path(_PROJECT_ROOT) / args.card
    if not card_path.exists():
        card_path = Path.cwd() / args.card
    if not card_path.exists():
        print(f"[FATAL] 角色卡不存在: {args.card}")
        sys.exit(1)
    args.card = str(card_path.resolve())
    print(f"[CONFIG] 角色卡: {args.card}")

    success = True

    # ── 1. Bootstrap ────────────────────────────────────────────────────
    bootstrap_result = run_bootstrap(args, p, runner)
    if bootstrap_result is None:
        print("\n[FATAL] Bootstrap 失败，无法继续")
        sys.exit(1)

    if args.breakpoint_after == "bootstrap":
        print("\n[BREAKPOINT] Bootstrap 完成，进入 breakpoint()")
        breakpoint()

    # ── 2. First Turn ───────────────────────────────────────────────────
    first_turn_result = run_first_turn(args, p, runner)
    if first_turn_result is None:
        print("\n[FATAL] First Turn 失败")
        success = False

    if args.breakpoint_after == "first_turn":
        print("\n[BREAKPOINT] First Turn 完成，进入 breakpoint()")
        breakpoint()

    # ── 3. AcceptedTextOutput (first turn) ──────────────────────────────
    if first_turn_result:
        accepted_result = run_accepted_text(
            p, runner, first_turn_result["turn_record"], label="first"
        )
        if accepted_result is None:
            print("[WARN] AcceptedTextOutput 失败")
            success = False

        # ── 4. TurnResultProbe (first turn) ─────────────────────────────
        probe_result = run_turn_result_probe(
            p, runner,
            first_turn_result["receipt"],
            first_turn_result["diagnostics"],
            first_turn_result["turn_record"],
            turn_kind="first",
        )
        if probe_result is None:
            print("[WARN] TurnResultProbe 失败")
            success = False

    # ── 5. Replay 验证 (可选) ───────────────────────────────────────────
    if args.replay_first_turn and first_turn_result:
        replay_ok = run_replay_verification(args, p, runner, first_turn_result)
        if not replay_ok:
            success = False

    # ── 6. Continuation Turn ────────────────────────────────────────────
    if args.restart_runtime_before_continuation:
        cont_result = run_restart_verification(args, p, runner)
        if not cont_result:
            success = False
    else:
        cont_result = run_continuation_turn(args, p, runner)
        if cont_result is None:
            print("[FATAL] Continuation Turn 失败")
            success = False

    if args.breakpoint_after == "continuation":
        print("\n[BREAKPOINT] Continuation 完成，进入 breakpoint()")
        breakpoint()

    # ── 7. AcceptedTextOutput (continuation) ────────────────────────────
    if isinstance(cont_result, dict) and "turn_record" in cont_result:
        accepted_result2 = run_accepted_text(
            p, runner, cont_result["turn_record"], label="continuation"
        )
        if accepted_result2 is None:
            print("[WARN] Continuation AcceptedTextOutput 失败")
            success = False

        # ── 8. TurnResultProbe (continuation) ───────────────────────────
        probe_result2 = run_turn_result_probe(
            p, runner,
            cont_result["receipt"],
            cont_result["diagnostics"],
            cont_result["turn_record"],
            turn_kind="continuation",
        )
        if probe_result2 is None:
            print("[WARN] Continuation TurnResultProbe 失败")
            success = False

    # ── 最终报告 ────────────────────────────────────────────────────────
    p.header("SUMMARY")
    p.kv("overall", "PASS" if success else "FAIL")
    p.kv("card", args.card)
    p.kv("session_id", args.session_id)
    p.kv("director_profile", args.director_profile)
    p.kv("writer_profile", args.writer_profile)
    p.kv("db_path", tmpdir)

    # 清理
    if not args.keep_db:
        from awp_rp_runtime_v3.runtime.runtime_store_factory import clear_registry_cache
        clear_registry_cache()
        import shutil
        try:
            shutil.rmtree(tmpdir)
            p.kv("db_cleanup", "removed")
        except Exception:
            p.kv("db_cleanup", "failed (locked?)")
    else:
        p.kv("db_cleanup", f"kept at {tmpdir}")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
