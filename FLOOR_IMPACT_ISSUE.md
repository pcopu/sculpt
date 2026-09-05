# Floor-impact validation blocks the final render

## Status

Reproduced locally on September 4, 2026 from `main` at `fa531a7` using Blender 4.3.2. The source scene builds and the complete 288-frame Mantaflow data and mesh bake finishes, but the required physical floor-impact validation fails. The 528-frame final render and MP4 assembly must remain blocked until a revised simulation passes.

```text
AssertionError: Insufficient physical floor impact: 854
```

The acceptance condition in `tools/validate_physics.py` is intentionally `peakFloorParticles > 1000`. Do not lower or bypass it, run Python with `-O`, or fabricate `public/assets/simulation.json`.

## Reproduction

The failure was reproduced with the repository's documented 6 mm grid and authored diagonal spill:

```bash
python tools/stage_spill.py
blender -b -t 8 --python-exit-code 1 --python tools/build_scene.py -- --mode build --resolution 200
BLENDER=blender RENDER_THREADS=8 python tools/bake_checked.py
python tools/validate_physics.py
```

Observed successful bake gates:

- 288 of 288 particle-data frames completed.
- 288 of 288 liquid-mesh frames completed.
- Upright containment passed at frames 1, 10, and 22 with zero escaped particles.
- The eight-frame Cycles diagnostic preview completed on an RTX 2070 through OPTIX.

## Cache evidence

Analysis of `render/cache/data/pp_0001.uni` through `pp_0288.uni`, using the validator's `DX=0.006` and `ORIGIN=(-0.024, -1.12, -0.03)`, found:

| Measurement | Result |
| --- | ---: |
| First tabletop count above 20 | frame 82 |
| Peak tabletop particles | 7,369 at frame 245 |
| First floor count above 20 | frame 120 |
| Peak floor particles | 854 at frame 187 |
| Active particles at peak floor frame | 12,620 |
| Active-particle range over the bake | 9,634–14,181 |

The floor contact is real but insufficient under the current acceptance rule: it rises from 24 particles at frame 120 to 705 at frame 160, peaks narrowly at 854 on frame 187, and then declines.

## Boundary finding

At the peak floor frame, active particles span approximately:

```text
x:  0.084 to 1.170 m
y: -0.912 to -0.166 m
z:  0.00008 to 0.594 m
```

The current domain spans:

```text
x: -0.024 to 1.176 m
y: -1.120 to -0.160 m
z: -0.030 to 0.760 m
```

Particles therefore approach within roughly one 6 mm cell of the positive-X and positive-Y domain faces, and later approach the negative-Y face. This is evidence of inadequate boundary margin, not proof that boundary loss alone causes the 854 result. The cache also retains thousands of particles on the tabletop after floor contact, so spill volume, tip trajectory, collision behavior, and the duration of the falling stream remain plausible contributors.

## Required next investigation

1. Preserve this failed cache and compare its evaluated liquid mesh with the particle coordinates near frames 117–205.
2. Rebake a wider-domain variant while preserving the 6 mm cell size. Update resolution, domain origin/size, `bake_checked.py`, `validate_physics.py`, and `bake_wetmaps.py` together; add a regression test for boundary clearance before changing production configuration.
3. If boundary clearance does not produce a defensible pass, test physical scene changes such as cup trajectory/direction or available liquid volume in separate caches.
4. Require both `peakFloorParticles > 1000` and visual approval of the tabletop spill, falling stream, and floor impact before material finalization or the full render.

The final deliverable remains unavailable until a new cache passes these checks and all 528 native 1920×1080 frames are rendered, assembled, strictly decoded, and reviewed.
