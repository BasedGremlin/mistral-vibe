"""
UltraRenderer package (integrated v13.6).
=========================================
A real software rasterizer/renderer: visibility rasterization, clustered
lighting, Cook-Torrance PBR, shadow atlas + PCF, TAA, plus a Vulkan skeleton
and a Godot GDExtension guide.

PORTABILITY NOTE (honest):
  - Requires numpy + Pillow (light, portable).
  - numba is OPTIONAL. With numba: 10-40x faster JIT kernels. Without numba:
    every module still runs in pure-Python/numpy serial mode (slower, but
    fully portable -- works on any USB target with no compilation step).
  - The Vulkan path is a skeleton/reference, not a live GPU pipeline.

Use `renderer_status()` to see what acceleration is actually available.
"""

from __future__ import annotations


def renderer_status() -> dict:
    """Honest report of what the renderer can actually do in this environment."""
    status = {"available": False, "numba": False, "numpy": False,
              "pillow": False, "mode": "unavailable", "note": ""}
    try:
        import numpy  # noqa
        status["numpy"] = True
    except Exception:
        status["note"] = "numpy missing -- renderer cannot run. pip install numpy"
        return status
    try:
        import PIL  # noqa
        status["pillow"] = True
    except Exception:
        status["note"] = "Pillow missing -- image output disabled. pip install Pillow"
    try:
        import numba  # noqa
        status["numba"] = True
    except Exception:
        pass

    status["available"] = status["numpy"]
    if status["numba"]:
        status["mode"] = "accelerated (numba JIT)"
        status["note"] = "Full speed: numba JIT kernels active."
    else:
        status["mode"] = "portable (pure-python/numpy serial)"
        status["note"] = ("Running without numba -- correct results, slower. "
                          "Install numba for 10-40x speedup (optional).")
    return status


__all__ = ["renderer_status"]
