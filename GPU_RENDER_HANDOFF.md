# GPU render handoff — The Last Sip

**Repository:** `pcopu/sculpt`  
**Handoff date:** September 4, 2026 (America/New_York)  
**Audited starting revision:** `1574d086d78a7c1077f0eba574bac87bb8e28433`  
**Status:** unfinished render project, with a known failed physics acceptance check. This is not an approved film master.

## 1. Objective and the actual starting state

Finish the existing scene rather than replacing it with stock footage, generated video, an animated still, or an expanding-puddle approximation. Render the porcelain cup tipping on the walnut coffee table, coffee crossing the wood and falling onto the oak floor, with the authored interior, camera, materials and liquid simulation.

Required delivery is `public/film/last-sip-1080p.mp4`: **22 seconds, 1920 × 1080, 24 fps, 528 native frames**, H.264 video with the project's original synthesized stereo effects. No interface, titles, watermark or black padding should appear in the picture. Keep the editable scene and Three.js assets alongside it.

The final-quality renderer in this project is **Blender Cycles**. Three.js displays exported geometry, cup transforms and the same baked liquid meshes using different real-time lighting. The MP4 is not a capture of an equivalent path-traced Three.js renderer. `tools/capture_browser.py` is a separate optional export, currently configured for software SwiftShader; do not use it as the GPU/Cycles production path.

### Read this before spending render time

The last inspected bake, [Actions run 33923032452](https://github.com/pcopu/sculpt/actions/runs/33923032452), built the scene and completed all 288 data and mesh frames. Upright containment passed. It then failed in `tools/validate_physics.py`:

```text
AssertionError: Insufficient physical floor impact: 854
```

The existing condition is `max_floor > 1000`, not `>= 1000`. Material finalization, export, cache packaging and frame rendering were skipped. That run did not upload the intended `render-cache` artifact. At the audited revision, the repository contains source but no committed `public/assets/`, `public/film/`, or `render/coffee.blend`. Earlier README deliverable descriptions are intended outputs, not evidence those files exist.

**A GPU does not fix this failure.** Resolve or rigorously diagnose the floor-impact check before approving a final render. Do not lower its threshold just to get a green result, run Python with `-O`, invent `simulation.json`, or describe a diagnostic movie as finished.

## 2. Workstation and software

Use a local SSD and keep the machine awake and plugged in. A reasonable planning allowance is 32 GB system RAM, 12 GB GPU memory and 100 GB free disk; these are conservative starting allowances, **not measured minimums or guarantees**. The fluid bake uses the existing CPU-side Mantaflow path. Cycles GPU selection affects image rendering, not liquid baking. Preserve the cache so a shading revision does not require another bake.

Install these separately:

| Tool | Requirement / purpose |
| --- | --- |
| Blender | **4.3.2** for source reconstruction and baking; the source was written for this API. Use the official archive, not an arbitrary system Blender. |
| Render Blender | Start with 4.3.2 on supported hardware. See the newer-GPU caveat below. |
| GPU driver | A vendor driver compatible with the chosen Blender/backend. Verify device detection before baking. |
| System Python | Python 3.12 with a project virtual environment containing NumPy and Pillow. |
| Node.js | Version 20 or newer as required by `package.json`; used for timeline tests and the viewer. |
| FFmpeg and ffprobe | Both on PATH; FFmpeg must provide the `libx264` and `aac` encoders. |
| Git | Clone, record the source revision, and preserve changes. GitHub CLI is optional for artifact recovery. |

Blender runs scripts importing `bpy` with its own Python. Do not attempt to install `bpy` into the system virtual environment to execute this project. NumPy/Pillow in the system environment serve the validation, wet-map and assembly scripts.

Backend selection: NVIDIA RTX → `OPTIX`; supported NVIDIA fallback → `CUDA`; supported AMD → `HIP`; supported Intel Arc → `ONEAPI`; supported Apple Silicon → `METAL`. Hardware/OS support varies; see [Blender's GPU documentation](https://docs.blender.org/manual/en/4.3/render/cycles/gpu_rendering.html).

**Newer GPUs:** RTX 50-series and AMD RX 9000-series support was added in [Blender 4.4](https://developer.blender.org/docs/release_notes/4.4/cycles/). Do not assume 4.3.2 can render on these cards. Keep 4.3.2 for build/bake, and test a compatible renderer such as a current [4.5 LTS build](https://www.blender.org/releases/4-5/) on a COPY of the complete project. Set `RenderBlender` / `RENDER_BLENDER` below to that executable. Check cache playback, materials and representative images again; this project's newer-version render compatibility has not been demonstrated. Do not overwrite the only 4.3.2 master by saving it in a newer release.

### Windows PowerShell setup

Install Git, Python 3.12, Node.js and FFmpeg first. Extract the official [Blender 4.3.2 Windows ZIP](https://download.blender.org/release/Blender4.3/blender-4.3.2-windows-x64.zip) under `C:\Tools`, or change the executable path below to the actual installation.

Run in a new project directory. If a working copy already exists, preserve its edits and cache rather than cloning over it. `Check-Exit` is necessary because PowerShell's error preference alone does not reliably stop failed native executables.

```powershell
$ErrorActionPreference = "Stop"
function Check-Exit {
    if ($LASTEXITCODE -ne 0) { throw "Previous command failed: exit $LASTEXITCODE. Stop here." }
}
git clone https://github.com/pcopu/sculpt.git
Check-Exit
Set-Location sculpt
$env:BLENDER = "C:\Tools\blender-4.3.2-windows-x64\blender.exe"
$RenderBlender = $env:BLENDER
$env:RENDER_THREADS = "8"
$env:SCULPT_GPU_BACKEND = "OPTIX"
$env:SCULPT_ADAPTIVE_THRESHOLD = "0.01"
py -3.12 -m venv .venv
Check-Exit
$PY = (Resolve-Path .venv\Scripts\python.exe).Path
& $PY -m pip install numpy pillow
Check-Exit
& $env:BLENDER --version
Check-Exit
node --version
Check-Exit
ffmpeg -version
Check-Exit
ffprobe -version
Check-Exit
& $PY -m unittest discover -s tests -p "test_gpu_config.py" -v
Check-Exit
npm test
Check-Exit
$env:SCULPT_GPU_CHECK_ONLY = "1"
try {
    & $RenderBlender -b --python-exit-code 1 --python tools/render_gpu.py
    Check-Exit
} finally {
    Remove-Item Env:SCULPT_GPU_CHECK_ONLY -ErrorAction SilentlyContinue
}
```

Change `RENDER_THREADS` to an appropriate CPU thread count before the build. Change the backend for non-NVIDIA hardware. `SCULPT_GPU_NAME`, when set, is a case-insensitive substring filter on the device name; leave it unset to enable all GPUs of the selected backend.

### Linux Bash setup

These commands assume an Ubuntu-style workstation with a working vendor driver, Git, Python 3.12/venv, Node 20+, FFmpeg, curl and xz/tar already installed. Install missing prerequisites through the appropriate system package manager first. Do not replace a working GPU driver without checking the target machine's requirements.

```bash
set -euo pipefail
git clone https://github.com/pcopu/sculpt.git
cd sculpt
mkdir -p "$HOME/opt"
curl -fL --retry 3 \
  https://download.blender.org/release/Blender4.3/blender-4.3.2-linux-x64.tar.xz \
  -o "$HOME/opt/blender-4.3.2-linux-x64.tar.xz"
tar -xf "$HOME/opt/blender-4.3.2-linux-x64.tar.xz" -C "$HOME/opt"
export BLENDER="$HOME/opt/blender-4.3.2-linux-x64/blender"
export RENDER_BLENDER="$BLENDER"
export RENDER_THREADS=8
export SCULPT_GPU_BACKEND=OPTIX
export SCULPT_ADAPTIVE_THRESHOLD=0.01
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install numpy pillow
"$BLENDER" --version
node --version
ffmpeg -version
ffprobe -version
python -m unittest discover -s tests -p 'test_gpu_config.py' -v
npm test
SCULPT_GPU_CHECK_ONLY=1 "$RENDER_BLENDER" -b --python-exit-code 1 --python tools/render_gpu.py
```

For NVIDIA, also run `nvidia-smi`. A GPU in that utility but absent from Blender can indicate an unsupported Blender build, driver issue or missing GPU passthrough. Device enumeration is a setup check, not proof a render kernel completed.

## 3. Build, bake, preserve a checkpoint, then validate

**All commands below run from the repository root.** Do not execute build mode against the only copy of an existing authored `coffee.blend`: it reconstructs and overwrites that file. Do not run `stage_spill.py` after making intentional staging changes; it restores authored camera/staging values. For a fresh checkout, it applies the existing project staging.

Keep **resolution 200**, domain dimensions **(1.20, 0.96, 0.79) metres**, domain centre **(0.576, -0.64, 0.365)**, **288 simulation frames** and time scale **0.25** for the first reproduction. Particle readers assume **6 mm cells** and origin **(-0.024, -1.12, -0.03)**. Changing resolution/domain without updating their coordinate conversion invalidates validation and wet maps.

Windows:

```powershell
& $PY tools/stage_spill.py
Check-Exit
& $env:BLENDER -b -t 8 --python-exit-code 1 --python tools/build_scene.py -- --mode build --resolution 200
Check-Exit
& $PY tools/bake_checked.py
Check-Exit
# Preserve the expensive result BEFORE any downstream acceptance check.
$Checkpoint = "../sculpt-bake-$(Get-Date -Format yyyyMMdd-HHmmss).tgz"
tar -czf $Checkpoint render/coffee.blend render/cache public/assets
Check-Exit
& $PY tools/validate_physics.py
Check-Exit
```

Linux:

```bash
python tools/stage_spill.py
"$BLENDER" -b -t "$RENDER_THREADS" --python-exit-code 1 --python tools/build_scene.py -- --mode build --resolution 200
python tools/bake_checked.py
tar -czf "../sculpt-bake-$(date +%Y%m%d-%H%M%S).tgz" render/coffee.blend render/cache public/assets
python tools/validate_physics.py
```

Expect `BAKE_COMPLETE` and `UPRIGHT_CONTAINMENT_PASS` from baking. A successful physics validator writes `public/assets/simulation.json` with all three checks passed. The known baseline can instead fail with the 854-particle floor-impact result. **If it fails, stop the final-delivery sequence and use section 4.** A zero exit from the bake alone is not approval.

## 4. Required handling of the known floor-impact failure

This is an unresolved scene/acceptance issue, not an installation error. The validator counts active particles with `-0.01 < world_z < 0.035`, and requires a peak count above 1,000. Its count is a project heuristic, not a direct volume measurement or proof of mass conservation.

Preserve the failed cache and log. Open `render/coffee.blend` in Blender 4.3.2. Check the domain's cache path points to this checkout's `render/cache`. Inspect the actual liquid mesh, floor collision object, table edge and cup collider. In this scene the visible floor is at Z = 0 and the tabletop is at Z = 0.545.

Render the eight low-sample inspection frames using section 6's **preview** command even when validation fails. These are diagnostic images only, and may not yet have final wetness materials. They help distinguish a genuinely insufficient floor spill, liquid leaving a domain boundary, collider displacement, and an incorrect particle-to-world conversion.

For a developer taking over:

1. Log each frame's active-particle count, world-space bounds, table count and floor count before the final assertions. Inspect frames near first floor contact and the peak floor count. The validator currently fails before writing its report; do not assume an older report belongs to this bake.
2. Cross-check the hard-coded origin/cell scale with the actual domain and compare particle locations with the evaluated liquid mesh. Confirm the receiving floor area lies inside the domain and the collider is correctly positioned.
3. If the spill does not meet the requested visual outcome, adjust the actual setup: cup motion/direction, available liquid, collision geometry, or domain coverage. Rebuild and rebake in a separate working copy. Keep the browser cup/camera export synchronized.
4. If the measurement itself is demonstrably wrong, correct its coordinate logic or acceptance definition with evidence and a regression test. Do not merely change 1,000 to 854, disable assertions or mark an existing report as passed. A changed domain also requires updates to `bake_checked.py`, `validate_physics.py` and the constants in `bake_wetmaps.py`; its origin/size arguments alone do not change its 0.006 m cell scale.

The GPU workstation operator must get a physically and visually defensible pass before treating the remaining commands as a final render. Keep the prior failed result in the handoff record rather than erasing it.

## 5. Finalize materials and generate the matching Three.js assets

Only after physics acceptance passes:

Windows:

```powershell
& $PY tools/bake_wetmaps.py
Check-Exit
& $env:BLENDER -b --python-exit-code 1 --python tools/finalize_materials.py
Check-Exit
& $env:BLENDER -b --python-exit-code 1 --python tools/build_scene.py -- --mode export
Check-Exit
& $PY tools/validate_cache.py
Check-Exit
New-Item -ItemType Directory -Force public/vendor | Out-Null
Invoke-WebRequest "https://cdn.jsdelivr.net/npm/three@0.180.0/build/three.module.js" -OutFile public/vendor/three.module.js
Invoke-WebRequest "https://cdn.jsdelivr.net/npm/three@0.180.0/build/three.core.js" -OutFile public/vendor/three.core.js
Invoke-WebRequest "https://cdn.jsdelivr.net/npm/three@0.180.0/LICENSE" -OutFile public/vendor/THREE-LICENSE.txt
```

Linux:

```bash
python tools/bake_wetmaps.py
"$BLENDER" -b --python-exit-code 1 --python tools/finalize_materials.py
"$BLENDER" -b --python-exit-code 1 --python tools/build_scene.py -- --mode export
python tools/validate_cache.py
mkdir -p public/vendor
curl -fL --retry 3 https://cdn.jsdelivr.net/npm/three@0.180.0/build/three.module.js -o public/vendor/three.module.js
curl -fL --retry 3 https://cdn.jsdelivr.net/npm/three@0.180.0/build/three.core.js -o public/vendor/three.core.js
curl -fL --retry 3 https://cdn.jsdelivr.net/npm/three@0.180.0/LICENSE -o public/vendor/THREE-LICENSE.txt
```

Expected assets include `scene.json`, `scene.bin`, `cup.json`, `liquid.json`, `simulation.json`, walnut/oak textures, **288** `liquid/*.bin.gz` files, and **576** floor/table wetness images plus `wetness/wetness.json`. Keep the entire `public/assets` directory. Sequence textures are external dependencies even when the base wood textures are packed into the master.

Make another checkpoint of `render/coffee.blend`, `render/cache`, `public/assets`, and the source before production rendering. Keep the source commit and any local diff with that checkpoint.

## 6. GPU preview, image approval and full render

Use **`tools/render_gpu.py`**, not a bare `blender -a` and not the original CPU-default command. The wrapper enables the selected device after the saved scene is reopened, disables CPU rendering devices, enables adaptive sampling at the configured threshold and delegates to `render_shard.py`. It does not save machine preferences or modify the liquid cache. It does **not** replace the physics/visual acceptance gates in this document.

The original scene is saved with `sc.cycles.device = 'CPU'`. Merely installing a GPU, passing `-t`, or selecting `--engine CYCLES` does not change that. Do not append `--cycles-device` to the project's script arguments: `build_scene.py` uses its own strict argument parser. Use the environment-backed wrapper instead.

### First: preview, then full-resolution sample frames

Windows:

```powershell
& $RenderBlender -b --python-exit-code 1 --python tools/render_gpu.py -- --mode preview --width 960 --samples 20
Check-Exit
# After section 5 passes, render samples using the SAME settings as the full film.
foreach ($f in @(0, 168, 208, 260, 336, 527)) {
    & $RenderBlender -b --python-exit-code 1 --python tools/render_gpu.py -- --mode render --start $f --end ($f + 1) --width 1920 --samples 256
    Check-Exit
}
```

Linux:

```bash
"$RENDER_BLENDER" -b --python-exit-code 1 --python tools/render_gpu.py -- --mode preview --width 960 --samples 20
for f in 0 168 208 260 336 527; do
  "$RENDER_BLENDER" -b --python-exit-code 1 --python tools/render_gpu.py -- --mode render --start "$f" --end "$((f+1))" --width 1920 --samples 256
done
```

Preview mode writes `render/preview/` and intentionally caps samples at 20. Even `--samples 256` will not lift that preview cap. Native sample frames go into `render/frames/`. Full rendering will overwrite those sample frames, which is safe when the settings are identical.

Look for `GPU_DEVICES` and `GPU_RENDER_SETTINGS` with `sceneDevice: GPU`. During a real render, inspect the Blender/Cycles log and GPU utilization. CPU activity for scene evaluation, denoising or compositing is not by itself evidence of CPU ray tracing.

**Review at 100% image size:** wood grain and bevels, porcelain interior/handle, coffee absorption and reflections, liquid-table/floor contacts, no domain-box artifact, no magenta missing textures, no floating cup, liquid remaining in the camera's view, believable puddle/wetness coverage and useful camera framing. Inspect adjacent moving frames for flicker and denoising instability; still-frame approval alone is insufficient.

The proposed full-render starting point is 256 maximum samples with adaptive threshold 0.01 and denoising. This is an authored quality target, not a promise of film-studio acceptance. Increase samples/tighten the threshold only after inspecting the difficult frames. Extra samples will not fix bad simulation, insufficient mesh detail or staging.

### Then: render all 528 frames with one consistent configuration

Windows:

```powershell
& $RenderBlender -b --python-exit-code 1 --python tools/render_gpu.py -- --mode render --start 0 --end 528 --width 1920 --samples 256
Check-Exit
& $PY tools/validate_physics.py
Check-Exit
& $PY tools/validate_cache.py
Check-Exit
& $PY tools/assemble.py
Check-Exit
```

Linux:

```bash
"$RENDER_BLENDER" -b --python-exit-code 1 --python tools/render_gpu.py -- --mode render --start 0 --end 528 --width 1920 --samples 256
python tools/validate_physics.py
python tools/validate_cache.py
python tools/assemble.py
```

**Frame ranges are `[start,end)`.** Output files are `00000.png` through `00527.png`. The film frame maps to simulation frame `max(1, min(288, film_frame - 95))`, and the camera is updated procedurally for each film frame. Blender's ordinary animation-render button or `-a` does not execute that mapping/camera loop and is not equivalent to this film render.

Assembly requires native **1920 × 1080** frames. Do not substitute 4K frames without updating the assembler and its validation. The current master path uses display-referred PNGs; it is not an ACES/linear-EXR or HDR pipeline, and a later 10-bit transcode cannot recover lost image precision.

## 7. Resume safely and retain useful work

An interrupted image render does not require rebaking. Find the last contiguous, readable PNG of the correct dimensions and restart at the first missing/corrupt frame. For example, if `00000.png` through `00236.png` are good, rerun the full-render command with `--start 237 --end 528`. The existing renderer does not auto-skip completed files and will overwrite anything inside the requested range.

Do not infer progress from file count alone: the earlier sample renders create gaps. Do not mix frames from different Blender versions, samples, thresholds, scene revisions or caches. Archive the frame directory and restart it when those inputs change. Record the source SHA, local diff, Blender/driver versions, selected backend, quality settings and logs with the finished render.

A completed simulation can be reused for material/camera changes. Changes to cup motion, collisions, liquid volume, domain/grid or simulation time require a new bake and matching exports/wet maps. Never run two bake processes into the same cache directory. Keep the CPU-hosted Actions renderer separate; this handoff does not configure a self-hosted GPU runner or launch another Actions render.

### Optional recovery of an actually published cache

First check GitHub Actions for a newer successful run and a nonexpired `render-cache` or `render-ready` artifact. The failed run above is not such a source. Download only the artifact from a specifically identified run, in a separate recovery directory. For example, after replacing `SUCCESSFUL_RUN_ID` with an actual verified numeric ID:

```bash
gh auth status
gh run download SUCCESSFUL_RUN_ID -R pcopu/sculpt -n render-cache -D recovery
# Inspect archive contents before extracting into a clean matching checkout.
tar -tzf recovery/render-cache.tgz
```

Use `-n render-ready` and its actual archive filename for that artifact instead. Restore the blend, raw cache AND assets together, then rerun the validators with matching source. A source-snapshot or Blender-toolchain artifact is not a baked scene. Do not overwrite a modified working copy during extraction. The [GitHub CLI artifact documentation](https://cli.github.com/manual/gh_run_download) describes the explicit run/name selection.

## 8. Verify the actual MP4, not just successful commands

Assembly writes:

| Path | Purpose |
| --- | --- |
| `public/film/last-sip-1080p.mp4` | 22-second H.264/AAC deliverable |
| `public/film/original-foley.wav` | Separate 48 kHz stereo sound effects |
| `public/film/delivery.json` | Report, expected media properties and SHA-256 |
| `public/film/poster.jpg` | Representative still |
| `public/film/contact-sheet.jpg` | Eight-frame overview for review |

Run these in either shell; in PowerShell, run `Check-Exit` after each native command:

```text
ffprobe -v error -count_frames -show_entries stream=codec_type,codec_name,width,height,avg_frame_rate,nb_read_frames,sample_rate,channels -show_entries format=duration -of json public/film/last-sip-1080p.mp4
ffmpeg -v error -xerror -err_detect explode -i public/film/last-sip-1080p.mp4 -f null -
```

Confirm the **video** stream is H.264, 1920 × 1080, `24/1`, **528 decoded video frames**, and container duration approximately 22 seconds. Confirm the audio stream is AAC, 48,000 Hz, two channels. The strict decode must exit zero with no errors. `assemble.py` already makes several checks, but this extra command treats decoding errors as fatal.

Play the entire MP4 with sound, then inspect the tip, tabletop spill, falling liquid, floor impact and ending frame. Check that synthesized clinks/splashes match the final motion. Technical validity is not aesthetic approval or studio certification. Do not silently add fades, repeated frames, time stretching or placeholder audio to hide failures.

Run `npm start` and open `http://localhost:5173` to check the film and interactive Three.js scene. Verify no missing asset requests and inspect timeline seeking. The supplied server binds to all network interfaces; use it on a trusted local network or restrict access. The viewer is a separate approximation of the offline lighting.

## 9. Final handoff and definition of done

Return the actual MP4 plus `delivery.json`, separate WAV and contact sheet. Also retain the editable `render/coffee.blend`, the complete `render/cache`, `public/assets`, `public/vendor` with its license, source revision/diff, renderer settings and review notes. Preserve native PNG frames as the recoverable image master when storage permits. Do not hand over a `.blend` without its external cache/sequence dependencies.

Keep changes in version control, but do not blindly commit a multi-gigabyte cache or frames to ordinary Git. Transfer large outputs as an archive or suitable artifact/release and verify the recipient can actually access them. `render/` is intentionally gitignored. Preserve local files and credentials; do not upload machine secrets or unrelated files.

Completion requires genuine passing physical checks, complete native frames, a strict successful MP4 decode, a full visual/audio review, and an accessible final movie. Until then, report the precise remaining failure and label previews as previews. There is no final render or studio-quality certification attached to this handoff.

### Instructions for a receiving coding/render agent

> Read this document and the existing scripts before changing anything. Preserve the authored 22-second shot and actual Mantaflow liquid. Reproduce and resolve the documented floor-impact failure without falsifying checks. Use the GPU wrapper after cache/material validation, inspect native sample frames, render all 528 frames, assemble and strictly decode the MP4, review the complete movie, and deliver the movie with the editable source/cache and an accurate status report. Do not stop at source code or a workflow link and call it a completed movie.

### Evidence and implementation references

The starting-state findings come from the [audited source revision](https://github.com/pcopu/sculpt/tree/1574d086d78a7c1077f0eba574bac87bb8e28433), the [failed bake job](https://github.com/pcopu/sculpt/actions/runs/33923032452/job/101185432239), and these repository files: `tools/build_scene.py`, `tools/bake_checked.py`, `tools/validate_physics.py`, `tools/bake_wetmaps.py`, `tools/finalize_materials.py`, `tools/render_shard.py`, `tools/validate_cache.py`, `tools/assemble.py`, `src/timeline.mjs` and `tools/capture_browser.py`.

The GPU helper's six configuration-only unit tests and the existing five Node timeline tests passed during handoff preparation. Its `refresh_devices()` call was checked against the bundled Blender 4.3.2 Cycles source. **No physical GPU render or Windows/Linux end-to-end handoff run was performed during this documentation task.** The known failed physics result remains unresolved; the helper does not change that validator.
