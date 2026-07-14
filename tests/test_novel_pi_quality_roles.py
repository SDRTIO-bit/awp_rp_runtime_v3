from __future__ import annotations

import json
from types import SimpleNamespace

from awp_rp_runtime_v3.contracts.novel_chapter import ChapterPlan
from awp_rp_runtime_v3.contracts.novel_pi_role_protocol import NovelPiRoleResult
from awp_rp_runtime_v3.runtime.novel_continuity_checker import NovelContinuityChecker
from awp_rp_runtime_v3.runtime.novel_ledger_curator import NovelLedgerCurator
from awp_rp_runtime_v3.runtime.novel_role_context import novel_role_scope
from awp_rp_runtime_v3.runtime.novel_style_cleaner import NovelStyleCleaner


class RecordingRuntime:
    def __init__(self, text: str):
        self.text = text
        self.tasks = []

    def run(self, task, *, context, on_chunk=None):
        del context, on_chunk
        self.tasks.append(task)
        return NovelPiRoleResult(
            request_id=f"r{len(self.tasks)}",
            role=task.role,
            session_key=task.session_key,
            text=self.text,
            model="kimi-k2.6",
        )


def _scope(registry=SimpleNamespace()):
    return novel_role_scope(
        registry=registry,
        project_id="p1",
        chapter_index=3,
        revision=1,
    )


def test_continuity_checker_uses_pi_role_runtime(monkeypatch):
    runtime = RecordingRuntime(json.dumps({
        "issues": ["上一章答应归还钥匙，本章没有推进"],
        "severity": "warning",
        "suggestions": ["补一次对话交代"],
    }, ensure_ascii=False))
    monkeypatch.setattr(
        "awp_rp_runtime_v3.runtime.novel_continuity_checker.get_novel_role_runtime",
        lambda: runtime,
        raising=False,
    )

    with _scope():
        result = NovelContinuityChecker(SimpleNamespace()).check_chapter(
            "正文", ChapterPlan(project_id="p1", chapter_index=3), [], {}, "",
        )

    assert runtime.tasks[0].role == "continuity_checker"
    assert runtime.tasks[0].session_key.startswith("task:")
    assert runtime.tasks[0].input_payload["response_format"] == "continuity_json"
    assert result["severity"] == "warning"


def test_style_cleaner_uses_toolless_pi_role_runtime(monkeypatch):
    original = "陈默推门。陈默停下。唐梨抬头。她没说话。" * 8
    rewritten = (
        "陈默推门后停住，唐梨抬起头，却没说话。"
        "门轴还在响，他先把手从门把上松开。"
        "唐梨低头整理桌上的纸，最上面那张被她折了一个角。"
        "陈默问她是不是在等人，她说只是教室比较安静。"
        "走廊传来脚步声，两个人同时朝门口看了一眼。"
        "来的是值日生，抱着一摞刚收回来的作业。"
        "唐梨把那张纸压进书里，顺手将椅子往旁边挪了半步。"
        "陈默没再追问，只把门轻轻带上。"
    )
    runtime = RecordingRuntime(rewritten)
    monkeypatch.setattr(
        "awp_rp_runtime_v3.runtime.novel_style_cleaner.get_novel_role_runtime",
        lambda: runtime,
        raising=False,
    )

    with _scope():
        result = NovelStyleCleaner(SimpleNamespace()).rewrite_for_issues(
            original,
            [{"type": "drumbeat", "severity": "blocking", "detail": "短句过密"}],
            max_retries=0,
        )

    assert runtime.tasks[0].role == "style_cleaner"
    assert runtime.tasks[0].session_key.startswith("task:")
    assert runtime.tasks[0].input_payload["response_format"] == "rewritten_prose"
    assert result == rewritten


def test_ledger_curator_uses_pi_role_runtime(monkeypatch):
    runtime = RecordingRuntime(json.dumps({
        "chapter_summary": "陈默与唐梨被迫共同处理告白字幕事故。",
        "ledger_updates": [],
        "ledger_resolves": [],
        "foreshadowing_changes": [],
    }, ensure_ascii=False))
    monkeypatch.setattr(
        "awp_rp_runtime_v3.runtime.novel_ledger_curator.get_novel_role_runtime",
        lambda: runtime,
        raising=False,
    )

    with _scope():
        result = NovelLedgerCurator(SimpleNamespace()).curate(
            "正文", ChapterPlan(project_id="p1", chapter_index=3), [],
        )

    assert runtime.tasks[0].role == "ledger_curator"
    assert runtime.tasks[0].session_key.startswith("task:")
    assert runtime.tasks[0].input_payload["response_format"] == "ledger_update_json"
    assert result["chapter_summary"]
