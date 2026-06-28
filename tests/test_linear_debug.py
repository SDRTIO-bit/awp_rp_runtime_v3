"""Smoke test for linear_persistent_rp_debug.py.

验证:
  1. 脚本可 import
  2. fake profile 能完整跑 bootstrap → first turn → continuation
  3. AcceptedTextOutput 与 TurnResultProbe 都能消费真实上游输出
  4. 不会误调用旧 fake 链
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


def _card_path() -> str:
    return str(Path(__file__).resolve().parent.parent / "test_fixtures" / "test_card.json")


class TestLinearDebugImport:
    """脚本可 import。"""

    def test_01_import_succeeds(self):
        from awp_rp_runtime_v2.testing import linear_persistent_rp_debug
        assert hasattr(linear_persistent_rp_debug, "main")
        assert hasattr(linear_persistent_rp_debug, "run_bootstrap")
        assert hasattr(linear_persistent_rp_debug, "run_first_turn")
        assert hasattr(linear_persistent_rp_debug, "run_continuation_turn")
        assert hasattr(linear_persistent_rp_debug, "run_accepted_text")
        assert hasattr(linear_persistent_rp_debug, "run_turn_result_probe")

    def test_02_safe_printer(self):
        from awp_rp_runtime_v2.testing.linear_persistent_rp_debug import SafePrinter
        p = SafePrinter(verbose=False)
        p.kv("test_key", "test_value")
        p.safe_text("label", "some text here")

    def test_03_call_node_returns_tuple(self):
        from awp_rp_runtime_v2.testing.linear_persistent_rp_debug import call_node, output_at
        from awp_rp_runtime_v2.nodes.persistent_bootstrap_node import AWPV2PersistentBootstrap

        tmpdir = tempfile.mkdtemp()
        os.environ["AWP_RUNTIME_PROFILE"] = "test"
        os.environ["AWP_TEST_STORE_ROOT"] = tmpdir
        os.environ["AWP_TEST_RUNTIME_NAMESPACE"] = "smoke_import"
        from awp_rp_runtime_v2.runtime.runtime_store_factory import clear_registry_cache
        clear_registry_cache()
        try:
            result = call_node(AWPV2PersistentBootstrap, {
                "source_path": _card_path(),
                "session_id": "smoke-sess",
                "greeting_id": "g0",
                "request_id": "smoke-req",
                "run_id": "smoke-run",
            })
            assert isinstance(result, tuple)
            assert len(result) == 5
            binding = output_at(result, 0)
            assert isinstance(binding, dict)
            assert "logical_card_id" in binding
        finally:
            clear_registry_cache()
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestLinearDebugFullPipeline:
    """Fake profile 完整跑 bootstrap → first turn → continuation。"""

    def test_04_full_pipeline_fake_profile(self):
        from awp_rp_runtime_v2.testing.linear_persistent_rp_debug import (
            SafePrinter, StageRunner, call_node, output_at,
        )

        tmpdir = tempfile.mkdtemp()
        os.environ["AWP_RUNTIME_PROFILE"] = "test"
        os.environ["AWP_TEST_STORE_ROOT"] = tmpdir
        os.environ["AWP_TEST_RUNTIME_NAMESPACE"] = "smoke_full"
        from awp_rp_runtime_v2.runtime.runtime_store_factory import clear_registry_cache
        clear_registry_cache()
        try:
            p = SafePrinter(verbose=False)
            runner = StageRunner(p)
            card = _card_path()
            session_id = "smoke-full-001"

            # Bootstrap
            from awp_rp_runtime_v2.nodes.persistent_bootstrap_node import AWPV2PersistentBootstrap
            bootstrap = runner.run("bootstrap", AWPV2PersistentBootstrap, {
                "source_path": card,
                "session_id": session_id,
                "greeting_id": "g0",
                "request_id": "req-bs",
                "run_id": "run-bs",
            })
            assert bootstrap is not None
            binding = output_at(bootstrap, 0)
            assert binding.get("session_id") == session_id

            # First Turn
            from awp_rp_runtime_v2.nodes.persistent_first_turn_node import AWPV2PersistentFirstTurn
            first = runner.run("first_turn", AWPV2PersistentFirstTurn, {
                "session_id": session_id,
                "player_input": "你好",
                "director_profile_id": "fake-director",
                "writer_profile_id": "fake-writer",
            })
            assert first is not None
            receipt1 = output_at(first, 0)
            assert receipt1.get("idempotency_status") == "fresh"
            turn_record1 = output_at(first, 4)
            assert len(turn_record1.get("writer_output", "")) > 0

            # AcceptedTextOutput
            from awp_rp_runtime_v2.nodes.accepted_text_output_node import AWPV2AcceptedTextOutput
            ato = runner.run("accepted_text", AWPV2AcceptedTextOutput, {
                "turn_record": turn_record1,
            })
            assert ato is not None
            assert isinstance(ato, dict)
            assert "ui" in ato
            texts = ato.get("ui", {}).get("awp_accepted_text", [])
            assert len(texts) > 0
            assert len(texts[0]) > 0

            # TurnResultProbe
            from awp_rp_runtime_v2.nodes.turn_result_probe_node import AWPV2TurnResultProbe
            diag1 = output_at(first, 2)
            probe = runner.run("probe", AWPV2TurnResultProbe, {
                "receipt": receipt1,
                "diagnostics": diag1,
                "turn_record": turn_record1,
                "turn_kind": "first",
            })
            assert probe is not None
            assert isinstance(probe, dict)
            assert "ui" in probe
            json_str = probe.get("ui", {}).get("awp_turn_result_json", [""])[0]
            import json
            proj = json.loads(json_str)
            assert proj.get("quality_status") == "accept"

            # Continuation
            from awp_rp_runtime_v2.nodes.persistent_continuation_turn_node import AWPV2PersistentContinuationTurn
            cont = runner.run("continuation", AWPV2PersistentContinuationTurn, {
                "session_id": session_id,
                "player_input": "继续",
                "director_profile_id": "fake-director",
                "writer_profile_id": "fake-writer",
            })
            assert cont is not None
            receipt2 = output_at(cont, 0)
            assert receipt2.get("idempotency_status") == "fresh"
            turn_record2 = output_at(cont, 4)
            assert len(turn_record2.get("writer_output", "")) > 0

            # Continuation AcceptedTextOutput
            ato2 = runner.run("accepted_text_cont", AWPV2AcceptedTextOutput, {
                "turn_record": turn_record2,
            })
            assert ato2 is not None
            assert "ui" in ato2

            # Continuation TurnResultProbe
            diag2 = output_at(cont, 2)
            probe2 = runner.run("probe_cont", AWPV2TurnResultProbe, {
                "receipt": receipt2,
                "diagnostics": diag2,
                "turn_record": turn_record2,
                "turn_kind": "continuation",
            })
            assert probe2 is not None
            assert "ui" in probe2

        finally:
            clear_registry_cache()
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestNoOldFakeChainCalls:
    """验证不会误调用旧 fake 链。"""

    def test_05_does_not_import_old_nodes(self):
        """线性调试工具的源码中不应包含旧 fake 链节点的 import。"""
        from pathlib import Path
        src = Path(__file__).resolve().parent.parent / "testing" / "linear_persistent_rp_debug.py"
        content = src.read_text(encoding="utf-8")

        old_chain_nodes = [
            "AWPV2CardImportAndBootstrap",
            "AWPV2FirstTurnExecution",
            "AWPV2ContinuationTurnExecution",
        ]
        for old_node in old_chain_nodes:
            assert old_node not in content, f"不应引用旧 fake 链节点: {old_node}"
