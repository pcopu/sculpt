# The Last Sip

> **Already reproduced the 854-particle blocker?** Use [FLOOR_IMPACT_RECOVERY.md](FLOOR_IMPACT_RECOVERY.md), not another identical baseline bake. The recovery helper creates an isolated wider-domain experiment, preserves the 6 mm cell size and original floor threshold, and leaves your existing cache untouched. The candidate still requires a complete rebake and physical/visual acceptance.
>
> **GPU workstation handoff:** Start with [GPU_RENDER_HANDOFF.md](GPU_RENDER_HANDOFF.md). It contains the Windows/PowerShell and Linux/Bash setup, explicit GPU selection, cache recovery/rebuild, diagnosis of the known physics failure, preview and final rendering, resumable frame ranges, and MP4 verification.
>
> **Status as of the September 4, 2026 handoff:** No verified finished MP4 has been delivered. The inspected bake completed its data/mesh stages but failed the floor-impact acceptance check (`854`, with a required peak above `1000`). Export and final rendering did not complete. The deliverables below are targets, not a claim that generated files exist. The handoff documents the failure rather than bypassing it.

Source for an intended 22-second coffee-spill film and a matching editable Three.js scene. A porcelain cup tips on a walnut table; the authored simulation is intended to spread coffee on the tabletop, carry it over the edge, and land it on an oak floor. The camera follows it through a fully modelled warm interior.

## Target deliverables

- `public/film/last-sip-1080p.mp4`: 1920 × 1080 H.264 film, 24 fps, 528 native frames, 22 seconds, original stereo foley. No titles, interface, branding or watermark in the film.
- `public/film/original-foley.wav`: separate original sound effects for editing.
- `public/film/delivery.json`: encoding properties, frame count, decode validation and SHA-256.
- `public/assets/`: original geometry, textures, exact cup transforms and baked liquid.
- An editable Blender master together with its full simulation cache and external sequence textures.

The intended MP4 is the **offline Blender Cycles render**. The web app is a **Three.js reconstruction of the evaluated geometry and liquid cache**, not a video plane pretending to be a simulation. Its real-time lighting approximates the offline lighting. The browser-capture script exports the Three.js renderer itself to a separate MP4; it is currently configured for software SwiftShader and is not the GPU/Cycles production path.

## Play and explore after generating the assets

Requires Node.js 20 or newer. The handoff includes commands to obtain Three.js 0.180.0 and its upstream MIT license in `public/vendor`; no Node package installation is needed for the viewer after the assets and vendor files exist.

```sh
npm start
```

Open the printed local address. After delivery files exist, watch the film or switch to the interactive scene. Seek on the timeline or use orbit mode to inspect geometry. The local server binds to all network interfaces; use it on a trusted network or restrict access.

## Rebuild and render on a GPU

For first-time setup, follow [GPU_RENDER_HANDOFF.md](GPU_RENDER_HANDOFF.md). After reproducing the known floor-impact failure, use [FLOOR_IMPACT_RECOVERY.md](FLOOR_IMPACT_RECOVERY.md) rather than rerunning the unchanged baseline. These documents supersede the previous short rebuild recipe, which omitted the physics-report and wet-material stages and left Cycles configured for CPU rendering.

The [tools/render_gpu.py](tools/render_gpu.py) wrapper applies GPU selection **after** the saved scene is loaded. It uses the existing camera/simulation mapping and frame renderer. It does not change the liquid simulation, save machine preferences, or weaken the physics validator. The wrapper alone does not establish that the scene passed validation.

Frame ranges are `[start,end)`. The intended image sequence is `00000.png` through `00527.png`. A bare `blender -a` does not reproduce the scripted film-camera/timeline mapping. Preserve a completed simulation checkpoint before running downstream validation.

## Physics and artistic choices

The project uses Mantaflow FLIP with an initial liquid volume, a moving cup collision mesh, gravity, and table/floor collision meshes. No expanding-puddle substitute is authored. The timeline expects 288 cached liquid frames, with quarter-speed physics and held liquid states during the opening and closing camera moves.

The cup tipping is art-directed keyframe animation, not a rigid-body solve or two-way coupled solid/fluid dynamics. Geometry, procedural textures and synthesized foley are original to this project. The current offline pipeline is display-referred AgX with Rec.709 delivery metadata; it is not an ACES EXR package or a DCP. Studio acceptance requires visual review and the production's delivery specifications, not just passing technical tests.

## Validation

```sh
npm test
python -m unittest discover -s tests -p 'test_*.py' -v
```

The five Node tests check camera/timeline invariants. The six GPU configuration tests use mock devices; they do not prove a physical GPU render succeeded. The 16 recovery tests use synthetic caches and temporary source fixtures; they do not establish that the wider-domain simulation passes. After a real bake, `tools/validate_physics.py` checks physical events and writes the simulation report. After export, `tools/validate_cache.py` checks the shared liquid buffers and cup poses. Assembly checks native resolution, frame count, duration and frame rate; the handoff also specifies a strict FFmpeg decode and full visual/audio review.

## Rights and provenance

No stock footage, purchased models, external music or generated human likenesses are used in the authored scene. Original scene, textures, animation and foley were created for this project. Third-party software retains its applicable license: Three.js MIT, Blender GPL, and FFmpeg/codecs under their respective licenses. Rendered creative assets are distinct from those software licenses.
