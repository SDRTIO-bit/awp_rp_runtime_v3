"""AWPV2CardImportDiagnostics — 导入诊断信息."""

from __future__ import annotations
from typing import Any


class AWPV2CardImportDiagnostics:
    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {"required": {"import_report": ("CARD_IMPORT_REPORT",)},
                "optional": {"card_definition": ("CARD_DEFINITION",)}}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("diagnostics",)
    FUNCTION = "execute"
    CATEGORY = "AWP/CardImport"

    def execute(self, import_report: dict, card_definition: dict | None = None) -> tuple[str]:
        lines = ["# 角色卡导入诊断报告", ""]
        lines.append(f"**报告 ID**: {import_report.get('report_id', 'N/A')}")
        lines.append(f"**状态**: {import_report.get('status', 'N/A')}")
        lines.append(f"**角色名**: {import_report.get('name', 'N/A')}")
        lines += ["", "## 统计",
                  f"- 问候语: {import_report.get('greeting_count', 0)}",
                  f"- 世界书条目: {import_report.get('worldbook_entry_count', 0)}",
                  f"- 世界书分块: {import_report.get('worldbook_chunk_count', 0)}",
                  f"- 隔离记录: {import_report.get('quarantine_count', 0)}",
                  f"- 结构提示: {import_report.get('structure_hint_count', 0)}"]
        qs = import_report.get("quarantine_summary", {})
        if qs.get("quarantine_count", 0) > 0 or qs.get("total", 0) > 0:
            lines += ["", "## 隔离摘要", f"- 总计: {qs.get('quarantine_count', qs.get('total', 0))}"]
            for k, v in qs.get("kind_counts", {}).items():
                lines.append(f"  - {k}: {v}")
            if qs.get("variables_detected"):
                lines.append("- ⚠️ 检测到变量模式")
        if card_definition:
            lines += ["", "## CardDefinition",
                      f"- card_id: {card_definition.get('card_id', 'N/A')}",
                      f"- status: {card_definition.get('status', 'N/A')}"]
        return ("\n".join(lines),)
