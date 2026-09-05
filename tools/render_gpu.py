"""GPU entry point for the existing render_shard.py film renderer.

Run with Blender, not system Python. See GPU_RENDER_HANDOFF.md.
Device selection is applied AFTER the saved scene is loaded. This wrapper
never saves user preferences, rebakes liquid, or weakens physics validation.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import runpy
import sys

BACKENDS = {"OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"}


def configure_gpu(bpy_module, backend: str, name_filter: str = "") -> list[str]:
    """Enable only matching GPUs; fail instead of silently selecting the CPU."""
    backend = backend.upper()
    if backend not in BACKENDS:
        raise ValueError(f"Unsupported GPU backend {backend!r}; choose {sorted(BACKENDS)}")
    preferences = bpy_module.context.preferences.addons["cycles"].preferences
    preferences.compute_device_type = backend
    preferences.refresh_devices()
    selected = []
    for device in preferences.devices:
        matches = (device.type == backend and
                   (not name_filter or name_filter.casefold() in device.name.casefold()))
        device.use = matches
        if matches:
            selected.append(device.name)
    if not selected:
        available = [(d.name, d.type) for d in preferences.devices]
        raise RuntimeError(
            f"No usable {backend} GPU matches {name_filter!r}. Detected: {available}. "
            "Check GPU drivers, Blender version and device passthrough. CPU fallback is disabled."
        )
    print("GPU_DEVICES " + json.dumps({"backend": backend, "selected": selected}), flush=True)
    return selected


def main() -> None:
    import bpy

    backend = os.environ.get("SCULPT_GPU_BACKEND", "OPTIX").upper()
    selected = configure_gpu(bpy, backend, os.environ.get("SCULPT_GPU_NAME", ""))
    print("BLENDER_VERSION " + bpy.app.version_string, flush=True)
    if os.environ.get("SCULPT_GPU_CHECK_ONLY") == "1":
        print("GPU_CONFIGURATION_OK (enumeration only; no image rendered)", flush=True)
        return
    threshold = float(os.environ.get("SCULPT_ADAPTIVE_THRESHOLD", "0.01"))
    if not math.isfinite(threshold) or not 0 < threshold < 1:
        raise ValueError("SCULPT_ADAPTIVE_THRESHOLD must be a finite number between 0 and 1")

    tools = Path(__file__).resolve().parent
    sys.path.insert(0, str(tools))
    import build_scene as film

    args = film.argparser()
    if args.mode not in {"render", "preview"} or args.engine != "CYCLES":
        raise ValueError("This GPU wrapper accepts only --mode render/preview with --engine CYCLES")
    if not 0 <= args.start < args.end <= film.FRAMES:
        raise ValueError(f"Expected 0 <= start < end <= {film.FRAMES}")
    if args.samples < 1 or args.width < 16:
        raise ValueError("Samples must be positive and width must be at least 16")

    original_load = film.load

    def load_on_gpu() -> None:
        original_load()
        scene = bpy.context.scene
        scene.render.engine = "CYCLES"
        scene.cycles.device = "GPU"
        scene.cycles.use_adaptive_sampling = True
        scene.cycles.adaptive_threshold = threshold
        scene.cycles.use_denoising = True
        scene.render.resolution_percentage = 100
        scene.render.threads_mode = "AUTO"
        print("GPU_RENDER_SETTINGS " + json.dumps({
            "backend": backend, "devices": selected, "sceneDevice": scene.cycles.device,
            "maxSamples": min(args.samples, 20) if args.mode == "preview" else args.samples,
            "adaptiveThreshold": threshold, "width": args.width,
            "height": round(args.width * 9 / 16), "mode": args.mode,
        }), flush=True)

    film.load = load_on_gpu
    # render_shard adds its own load hook; it chains through load_on_gpu.
    runpy.run_path(str(tools / "render_shard.py"), run_name="__main__")


if __name__ == "__main__":
    main()
