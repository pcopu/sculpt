# Floor-impact recovery: isolated wider-domain test

**Status: proposed repair experiment, not a validated simulation or finished film.**
This follows the reproducible 854-particle failure documented in `FLOOR_IMPACT_ISSUE.md` at commit `e8d2bb2`. Keep that report and the failed bake. Do not reinstall the working RTX 2070/OptiX setup or rebake the unchanged baseline.

## What went wrong, and what this changes

The previous handoff correctly blocked final rendering but left the simulation problem unresolved. Successful rendering tests do not prove the fluid passes its acceptance checks. The report shows real floor contact, a peak of 854 floor particles, and liquid within approximately one 6 mm cell of horizontal domain boundaries. Boundary interference is a plausible contributor, not an established sole cause. A particle count is not a direct volume measurement.

`tools/floor_impact_recovery.py prepare` creates a **new sibling source workspace**. It does not touch the original `render/`, `public/assets/`, previews, toolchain, virtual environment, or checkpoint. It refuses to overwrite an existing target directory. No simulation or render runs during setup.

The workspace changes only domain bounds, the build-resolution default/guard, and the corresponding coordinate readers. Cup motion, fill geometry, collision geometry, gravity, time scale, and the existing physics acceptance logic remain unchanged. In particular, `max_floor > 1000` remains exactly the same.

| Parameter | Reproduced baseline | New isolated test |
|---|---:|---:|
| Domain center, metres | `(0.576, -0.640, 0.365)` | `(0.816, -0.640, 0.366)` |
| Domain size, metres | `(1.200, 0.960, 0.790)` | `(1.920, 1.680, 0.792)` |
| Domain minimum, metres | `(-0.024, -1.120, -0.030)` | `(-0.144, -1.480, -0.030)` |
| Domain maximum, metres | `(1.176, -0.160, 0.760)` | `(1.776, 0.200, 0.762)` |
| Longest-axis divisions | `200` | `320` |
| Physical cell size | `0.006 m` | `0.006 m` |
| Simulation frames | `288` | `288` |
| Time scale | `0.25` | `0.25` |
| Floor-count condition | `>1000` | `>1000` |

The 2 mm increase at the top rounds the height to 132 whole cells while preserving the bottom elevation. Horizontal changes are integer multiples of the original cell size. Widening the box without increasing divisions would change the physical resolution; this experiment does not do that. Blender defines fluid resolution by subdivisions along the longest domain dimension, and fluids cannot leave the domain without colliding or disappearing, depending on its settings [1].

**Memory:** this candidate has approximately 2.8 times the baseline grid volume at the same cell size. That is not a measured runtime or RAM multiplier. It needs more host RAM during baking; the GPU's VRAM is not a substitute for adequate bake memory. On the preparation machine, a numerical smoke test was OOM-killed under its 4 GiB process-group memory limit before a particle frame was produced. Check the workstation's available RAM and preserve its existing cache. A 32 GB host is a reasonable planning target, not a measured minimum or a reason to replace the working GPU.

## Start on the existing GPU workstation

Use the working Python environment and **Blender 4.3.2** from the previous successful run. The Blender executable must be on PATH or supplied as an absolute path in `BLENDER`. Keep the same driver and OptiX backend. The existing dependencies remain NumPy, Pillow, Node.js and FFmpeg for later assembly.

Run the block for the workstation's shell **from the original `sculpt` checkout**, not from its cache directory. The sibling workspace is a source copy, not a Git checkout. Its source hashes and revision are recorded in `floor-impact-recovery.json`.

### Linux / Bash

```bash
set -euo pipefail
git pull --ff-only
PY="$(command -v python)"  # Activate your already-working venv first.
export BLENDER="${BLENDER:-blender}"  # Use an absolute path if not on PATH.
export RENDER_THREADS=8
export SCULPT_GPU_BACKEND=OPTIX
export SCULPT_ADAPTIVE_THRESHOLD=0.01
unset SCULPT_GPU_CHECK_ONLY

"$PY" -m unittest discover -s tests -p 'test_*.py' -v
npm test

# Optional: measure the preserved baseline WITHOUT another bake.
# This writes a diagnostic JSON, not an acceptance report.
"$PY" tools/floor_impact_recovery.py analyze --workspace . --legacy

"$PY" tools/floor_impact_recovery.py prepare --workspace ../sculpt-floor-impact-wide
cd ../sculpt-floor-impact-wide

# Do NOT run stage_spill.py here: it is deliberately disabled in the variant.
"$BLENDER" -b -t 8 --python-exit-code 1 --python tools/build_scene.py -- --mode build --resolution 320
"$PY" tools/bake_checked.py

# These are two distinct checks. Stop on either failure.
"$PY" tools/floor_impact_recovery.py analyze
"$PY" tools/validate_physics.py
```

Omit the optional legacy analysis command when no baseline cache exists at `render/cache/data` in this checkout. `PY` remains the absolute path of the original environment's interpreter after changing directories; do not create another virtual environment inside the variant. Ensure any custom `BLENDER` path also remains valid after changing directories.

### Windows / PowerShell

The existing handoff creates `.venv` in the original checkout. Set `$PY` to the already-working interpreter when your environment is elsewhere. Keep `$env:BLENDER` set to the working absolute Blender executable, or use `blender` when on PATH.

```powershell
$ErrorActionPreference = "Stop"
function Check-Exit {
    if ($LASTEXITCODE -ne 0) { throw "Previous command failed: exit $LASTEXITCODE. Stop here." }
}
git pull --ff-only
Check-Exit
$PY = (Resolve-Path .venv\Scripts\python.exe).Path
if (-not $env:BLENDER) { $env:BLENDER = "blender" }
$env:RENDER_THREADS = "8"
$env:SCULPT_GPU_BACKEND = "OPTIX"
$env:SCULPT_ADAPTIVE_THRESHOLD = "0.01"
Remove-Item Env:SCULPT_GPU_CHECK_ONLY -ErrorAction SilentlyContinue

& $PY -m unittest discover -s tests -p "test_*.py" -v
Check-Exit
npm test
Check-Exit

# Optional: use only when the original cache is present in this checkout.
& $PY tools/floor_impact_recovery.py analyze --workspace . --legacy
Check-Exit

& $PY tools/floor_impact_recovery.py prepare --workspace ../sculpt-floor-impact-wide
Check-Exit
Set-Location ../sculpt-floor-impact-wide

# Do NOT run stage_spill.py inside this variant.
& $env:BLENDER -b -t 8 --python-exit-code 1 --python tools/build_scene.py -- --mode build --resolution 320
Check-Exit
& $PY tools/bake_checked.py
Check-Exit
& $PY tools/floor_impact_recovery.py analyze
Check-Exit
& $PY tools/validate_physics.py
Check-Exit
```

The helper refuses unknown source shapes instead of silently applying a partial patch. Existing production scripts are not edited on `main`; their coordinate changes exist only in the generated experiment workspace. Do not run legacy staging after the patch. An explicit resolution other than 320 is also rejected before scene construction.

## Interpreting the result

`render/floor-impact-diagnostics.json` is written even when data is missing, malformed or the floor count is insufficient. It contains all readable frame measurements, active-particle bounds, table/floor counts, the peak floor frame, and horizontal boundary proximity. It never writes or invents `public/assets/simulation.json`.

For this experiment, `analyze` additionally requires all 288 particle frames and **no active particles within three cells (18 mm) of a horizontal domain face**. This is an extra conservative boundary-isolation criterion, not a replacement for the floor validator. The explicit `--legacy` mode reports baseline boundary problems without imposing this new criterion retroactively. Exit 2 means incomplete/invalid cache data; exit 3 means the widened experiment still has inadequate horizontal clearance. A successful diagnostic exit alone does not mean physics acceptance passed.

The unchanged `tools/validate_physics.py` must then pass upright containment, active-particle, tabletop and `peakFloorParticles > 1000` checks. Do not run Python with `-O`, lower thresholds, fabricate reports, or reuse any prior passing `simulation.json` as evidence for a new cache. The fresh workspace has no previous simulation report to inherit.

**If the new floor count still fails:** keep the new cache and diagnostic JSON. Compare its counts and bounds against the baseline. The boundary hypothesis has not solved the problem. The next controlled experiment should change cup placement/tip direction or fill geometry, one factor at a time, while preserving containment and the 6 mm grid. Do not repeatedly rerun the identical configuration or automatically launch the final render.

**If boundary clearance fails:** retain the per-frame bounds; do not mark the wide simulation as approved just because the floor count happens to pass. Expand around the measured extent in a new experiment and synchronize its readers again. This helper intentionally refuses arbitrary manual edits to its variant's recorded files; new variants need their own reviewed configuration and provenance.

An interrupted build/bake is not automatically resumed by `prepare`. That command refuses existing directories. Preserve the interrupted workspace and use a new name for a clean retry; do not overwrite the only expensive checkpoint.

## Continue to the MP4 only after both checks pass

Use the same interpreter/executable variables from above, in **the new workspace**. Complete `GPU_RENDER_HANDOFF.md` sections 5–7: bake wet maps, finalize materials, export the matching Three.js assets, validate the exported cache, and render the eight-frame GPU preview. Those commands operate on the variant's patched coordinate readers. Do not rerun sections 1–4's baseline build or resolution-200 commands.

Bash example:

```bash
"$PY" tools/bake_wetmaps.py
"$BLENDER" -b --python-exit-code 1 --python tools/finalize_materials.py
"$BLENDER" -b --python-exit-code 1 --python tools/build_scene.py -- --mode export
"$PY" tools/validate_cache.py
"$BLENDER" -b --python-exit-code 1 --python tools/render_gpu.py -- --mode preview --width 960 --samples 20
```

For PowerShell use `& $PY` / `& $env:BLENDER` and `Check-Exit` after every command, as in the previous handoff. Copy or obtain the pinned Three.js vendor files using handoff section 5 if they were absent in the original checkout; this is needed for the browser viewer, not Cycles image generation.

Review the liquid remaining inside the upright cup, a continuous tabletop spill, the stream clearing the actual table edge, and a visible floor impact without clipping, hovering, or obvious volume loss. Check materials, framing and focus. **The 1,000-particle threshold is necessary under this project's current rules, not sufficient for visual quality.**

For close inspection, distinguish simulation frame numbers from movie frame numbers: `sim_frame(f) = clamp(f - 95, 1, 288)`. The reported baseline peak at simulation frame 187 is movie frame **282**, at **11.75 seconds**. The new peak may differ; read it from the new diagnostic report. The standard eight-frame preview does not include every possible impact peak.

Only after reviewing and approving the new preview, render every final frame and assemble:

```bash
"$BLENDER" -b --python-exit-code 1 --python tools/render_gpu.py -- --mode render --start 0 --end 528 --width 1920 --samples 256
"$PY" tools/assemble.py
```

The target is `../sculpt-floor-impact-wide/public/film/last-sip-1080p.mp4`, **22 seconds, 1920×1080, 24 fps, 528 frames**. Assembly validates dimensions/frame count/duration and decodes the result. Reuse handoff section 7 for interrupted image-render recovery, but never mix frames from different simulation variants or quality settings. Keep the variant's source files, manifest, blend, full cache, exported assets and delivery JSON together. Do not replace the tracked production source with the experiment until its physical and visual results have been reviewed.

## What was tested while preparing this recovery

- 16 new synthetic/setup regression tests passed, plus the existing six GPU-configuration tests and five timeline tests: 27 total. These tests include coordinate conversion, strict `>1000` behavior, preservation of source data, unknown-source rejection and boundary-margin detection.
- The actual wider scene built in Blender 4.3.2 with 445 objects. Inspection confirmed 320 divisions, approximately 0.006 m cells, the listed bounds, 288 configured frames and time scale 0.25.
- A numerical smoke bake in a separate local cache hit the environment's 4 GiB memory limit (`oom_kill=1`) before producing a particle frame. No wider-domain numerical result, complete rebake, new floor-count pass, GPU image or MP4 is claimed by this recovery patch.

## Sources

[1] Blender 4.3 Manual, Fluid Domain Settings — domain boundaries and longest-dimension resolution: https://docs.blender.org/manual/zh-hant/4.3/physics/fluid/type/domain/settings.html

[2] Repository evidence: `FLOOR_IMPACT_ISSUE.md`, `tools/build_scene.py`, `tools/bake_checked.py`, `tools/validate_physics.py`, `tools/bake_wetmaps.py`, `tools/render_gpu.py`, `tools/assemble.py`, audited against source at `e8d2bb2`. The recovery test does not supersede the original issue report's unresolved status.
