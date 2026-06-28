"""awp_rp_runtime_v2 — ComfyUI RP Runtime V2."""

__version__ = "0.1.0"

from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

# Register management API routes (only when ComfyUI server is available)
try:
    from .runtime import management_api  # noqa: F401
except Exception:
    pass

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
