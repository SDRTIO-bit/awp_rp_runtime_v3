"""Regression test: ComfyUI node discovery.

ComfyUI loads custom nodes by importing the top-level package and looking
for NODE_CLASS_MAPPINGS.  If these are missing the entire module is skipped
with 'IMPORT FAILED'.
"""

import importlib


def test_root_exports_node_class_mappings():
    """Root __init__.py must expose NODE_CLASS_MAPPINGS for ComfyUI."""
    pkg = importlib.import_module("awp_rp_runtime_v3")
    assert hasattr(pkg, "NODE_CLASS_MAPPINGS"), (
        "NODE_CLASS_MAPPINGS not found in top-level package. "
        "ComfyUI will skip this custom node module."
    )
    assert isinstance(pkg.NODE_CLASS_MAPPINGS, dict)
    assert len(pkg.NODE_CLASS_MAPPINGS) > 0


def test_root_exports_node_display_name_mappings():
    """Root __init__.py must expose NODE_DISPLAY_NAME_MAPPINGS for ComfyUI."""
    pkg = importlib.import_module("awp_rp_runtime_v3")
    assert hasattr(pkg, "NODE_DISPLAY_NAME_MAPPINGS"), (
        "NODE_DISPLAY_NAME_MAPPINGS not found in top-level package."
    )
    assert isinstance(pkg.NODE_DISPLAY_NAME_MAPPINGS, dict)


def test_node_class_and_display_names_match():
    """Every entry in NODE_CLASS_MAPPINGS should have a display name."""
    pkg = importlib.import_module("awp_rp_runtime_v3")
    for key in pkg.NODE_CLASS_MAPPINGS:
        assert key in pkg.NODE_DISPLAY_NAME_MAPPINGS, (
            f"Node '{key}' has class mapping but no display name."
        )
