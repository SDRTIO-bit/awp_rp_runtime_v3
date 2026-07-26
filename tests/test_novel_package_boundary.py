"""Boundary tests for the novel-only product package."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_root_package_import_has_no_comfy_or_server_side_effects() -> None:
    code = """
import json
import sys
import awp_rp_runtime_v3 as package
print(json.dumps({
    "has_node_mappings": hasattr(package, "NODE_CLASS_MAPPINGS"),
    "management_loaded": "awp_rp_runtime_v3.runtime.management_api" in sys.modules,
    "server_loaded": "awp_rp_runtime_v3.scripts.awp_server" in sys.modules,
}))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload == {
        "has_node_mappings": False,
        "management_loaded": False,
        "server_loaded": False,
    }


def test_setuptools_excludes_retired_rp_packages() -> None:
    text = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    for retired in (
        "awp_rp_runtime_v3.nodes",
        "awp_rp_runtime_v3.policies",
        "awp_rp_runtime_v3.services",
        "awp_rp_runtime_v3.testing",
    ):
        assert f'"{retired}"' not in text


def test_retired_rp_source_trees_are_absent() -> None:
    for retired in ("nodes", "policies", "services", "testing", "workflows"):
        root = PROJECT_ROOT / retired
        assert not root.exists() or not any(root.rglob("*.py"))


def test_novel_product_source_has_no_retired_rp_imports() -> None:
    forbidden = (
        "awp_rp_runtime_v3.nodes",
        "awp_rp_runtime_v3.policies",
        "awp_rp_runtime_v3.services",
        "awp_rp_runtime_v3.testing",
        "runtime.persistent_turn_engine",
        "runtime.execution_dispatcher",
        "runtime.management_api",
    )
    roots = (
        PROJECT_ROOT / "runtime",
        PROJECT_ROOT / "contracts",
        PROJECT_ROOT / "scripts",
    )

    for root in roots:
        for path in root.glob("novel_*.py"):
            text = path.read_text(encoding="utf-8")
            assert not any(name in text for name in forbidden), path
