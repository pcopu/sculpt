"""Isolated boundary-margin experiment; never edits the source checkout's bake.

prepare: copy source to a NEW sibling workspace and patch all grid readers together.
analyze: read a completed cache and save measurements even if acceptance will fail.
The production floor threshold remains >1000. This is a candidate, not a proven fix.
"""
from __future__ import annotations
import argparse
import ast
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'floor-impact-recovery.json'

@dataclass(frozen=True)
class Grid:
    center: tuple[float, float, float]
    size: tuple[float, float, float]
    divisions: int

    @property
    def cell(self) -> float:
        return max(self.size) / self.divisions

    @property
    def origin(self) -> tuple[float, float, float]:
        return tuple(c - s / 2 for c, s in zip(self.center, self.size))

    @property
    def upper(self) -> tuple[float, float, float]:
        return tuple(c + s / 2 for c, s in zip(self.center, self.size))

LEGACY = Grid((.576, -.64, .365), (1.20, .96, .79), 200)
WIDE = Grid((.816, -.64, .366), (1.92, 1.68, .792), 320)
# Same 6 mm grid, integer-cell horizontal shifts, unchanged floor at Z=0.
# Z extent is rounded UP by 2 mm to 132 whole cells, with the bottom unchanged.
EDITS = {
    'tools/build_scene.py': [
        ('def make_scene(resolution):\n',
         'def make_scene(resolution):\n    if resolution != 320:raise ValueError("This isolated 6 mm domain requires resolution 320")\n'),
        ("domain=box('COFFEE / Mantaflow FLIP',(.576,-.64,.365),(1.20,.96,.79),coffee)",
         "domain=box('COFFEE / Mantaflow FLIP',(.816,-.64,.366),(1.92,1.68,.792),coffee)"),
        ("p.add_argument('--resolution',type=int,default=200)",
         "p.add_argument('--resolution',type=int,default=320)"),
    ],
    'tools/bake_checked.py': [('origin=(-.024,-1.12,-.03)', 'origin=(-.144,-1.48,-.03)')],
    'tools/validate_physics.py': [('ORIGIN=(-.024,-1.12,-.03)', 'ORIGIN=(-.144,-1.48,-.03)')],
    'tools/bake_wetmaps.py': [
        ('default=[-.024,-1.12,-.03]', 'default=[-.144,-1.48,-.03]'),
        ('default=[1.20,.96]', 'default=[1.92,1.68]'),
    ],
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def patches(source: Path) -> dict[str, str]:
    """Prepare all edits in memory first. Unknown source revisions fail closed."""
    result = {}
    for name, replacements in EDITS.items():
        text = (source / name).read_text(encoding='utf-8')
        for old, new in replacements:
            if text.count(old) != 1:
                raise RuntimeError(f'{name}: expected exactly one {old!r}; source changed. No variant created.')
            text = text.replace(old, new, 1)
        ast.parse(text, filename=name)
        result[name] = text
    # Only its coordinate origin may change; acceptance logic must stay byte-for-byte intact.
    validator = (source / 'tools/validate_physics.py').read_text(encoding='utf-8')
    if "assert max_floor>1000" not in validator:
        raise RuntimeError('Unknown floor validator. Review the source instead of auto-patching it.')
    if result['tools/validate_physics.py'].replace('ORIGIN=(-.144,-1.48,-.03)',
                                                 'ORIGIN=(-.024,-1.12,-.03)') != validator:
        raise RuntimeError('Unexpected validator change')
    return result


def prepare(source: Path, target: Path) -> dict:
    source, target = source.resolve(), target.resolve()
    if target == source or source in target.parents or target in source.parents:
        raise ValueError('Use a NEW sibling directory, not the source checkout or its parent/child.')
    if target.exists():
        raise FileExistsError(f'{target} already exists. Nothing overwritten. Use a new workspace name.')
    if not (source / 'tools/render_gpu.py').is_file():
        raise RuntimeError('GPU handoff source is missing. Pull main before preparing the variant.')
    revised = patches(source)  # Verify before copying anything.
    hashes = {}
    target.mkdir(parents=True)
    for directory in ('tools', 'src', 'tests'):
        shutil.copytree(source / directory, target / directory,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.pytest_cache'))
    for name in ('package.json', 'index.html', 'README.md', 'GPU_RENDER_HANDOFF.md',
                 'FLOOR_IMPACT_ISSUE.md', 'FLOOR_IMPACT_RECOVERY.md'):
        if (source / name).is_file():
            shutil.copy2(source / name, target / name)
    # Existing pinned browser modules can be reused. No cache, textures, previews,
    # checkpoint, virtual environment or Blender executable is copied/modified.
    for name in ('three.module.js', 'three.core.js', 'THREE-LICENSE.txt'):
        p = source / 'public/vendor' / name
        if p.is_file():
            (target / 'public/vendor').mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target / 'public/vendor' / name)
    for name, text in revised.items():
        hashes[name] = digest(source / name)
        (target / name).write_text(text, encoding='utf-8')
    # Historical stage_spill.py restores baseline constants and must not be rerun here.
    stage = target / 'tools/stage_spill.py'
    stage.write_text('raise RuntimeError("Already staged as an isolated wider-domain experiment. '
                     'Do not run legacy stage_spill.py in this workspace.")\n', encoding='utf-8')
    try:
        revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'],
                                           stderr=subprocess.DEVNULL, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        revision = None
    manifest = {
        'schema': 1, 'variant': 'boundary-margin-6mm-v1', 'status': 'unbaked_candidate',
        'createdUTC': datetime.now(timezone.utc).isoformat(), 'sourceCheckout': str(source),
        'sourceRevision': revision, 'sourceHashes': hashes,
        'grid': asdict(WIDE), 'origin': WIDE.origin, 'cellMetres': WIDE.cell,
        'simulationFrames': 288, 'floorThresholdExclusive': 1000,
        'minimumHorizontalMarginCells': 3,
        'changes': 'Domain coverage and coordinate readers only; no trajectory/volume/threshold change.',
        'note': 'Wider boundaries are a hypothesis, not a demonstrated fix. Existing bake is untouched.',
    }
    # Bind diagnostics to the actual patched source, not just the declared grid.
    manifest['variantHashes'] = {name: digest(target / name) for name in revised}
    (target / MANIFEST).write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    (target / 'EXPERIMENT_NOT_A_FINAL.txt').write_text(
        'Unvalidated boundary-margin experiment. Use FLOOR_IMPACT_RECOVERY.md.\n'
        'Do not run legacy stage_spill.py. Build at resolution 320.\n', encoding='utf-8')
    return manifest


def particles(path: Path):
    """Read the pinned PB02 format used by the existing Blender 4.3.2 validator."""
    raw = gzip.decompress(path.read_bytes())
    if len(raw) < 292 or raw[:4] != b'PB02':
        raise ValueError(f'Unexpected particle header: {path}')
    count = struct.unpack_from('<i', raw, 4)[0]
    if count < 0 or len(raw) != 292 + count * 16:
        raise ValueError(f'Truncated or unexpected particle payload: {path}')
    for x, y, z, flag in struct.iter_unpack('<fffi', raw[292:]):
        if flag == 0:
            if not all(math.isfinite(v) for v in (x, y, z)):
                raise ValueError(f'Non-finite active particle: {path}')
            yield (x, y, z)


def frame_metrics(path: Path, grid: Grid) -> dict:
    lower, upper, cell = grid.origin, grid.upper, grid.cell
    lo, hi = [math.inf] * 3, [-math.inf] * 3
    active = floor = table = near = outside = 0
    min_margin = math.inf
    for p in particles(path):
        x, y, z = co = tuple(o + cell * v for o, v in zip(lower, p))
        active += 1
        for axis in range(3):
            lo[axis], hi[axis] = min(lo[axis], co[axis]), max(hi[axis], co[axis])
        margin = min(x - lower[0], upper[0] - x, y - lower[1], upper[1] - y)
        min_margin = min(min_margin, margin)
        near += margin < 3 * cell
        outside += margin < 0
        # EXACT original project predicates: particle count is not a volume measurement.
        floor += -.01 < z < .035
        table += .540 < z < .555 and y > -.445 and -.70 < x < .70
    return {'activeParticles': active, 'floorParticles': floor, 'tableParticles': table,
            'boundsMin': lo if active else None, 'boundsMax': hi if active else None,
            'nearHorizontalBoundaryParticles': near, 'outsideHorizontalDomainParticles': outside,
            'minimumHorizontalMarginMetres': min_margin if active else None}


def analyze(workspace: Path, legacy: bool = False) -> dict:
    workspace = workspace.resolve()
    if legacy:
        if (workspace / MANIFEST).exists():
            raise ValueError('Do not interpret a widened cache using --legacy.')
        grid = LEGACY
        provenance = 'Explicit --legacy: known 200-division source; compare against the saved blend.'
    else:
        manifest = json.loads((workspace / MANIFEST).read_text(encoding='utf-8'))
        grid = Grid(tuple(manifest['grid']['center']), tuple(manifest['grid']['size']),
                    manifest['grid']['divisions'])
        if grid != WIDE or manifest['cellMetres'] != WIDE.cell:
            raise ValueError('Unknown variant manifest. Review grid conversion before measuring.')
        for name, expected in manifest['variantHashes'].items():
            if digest(workspace / name) != expected:
                raise RuntimeError(f'{name} changed after setup; refusing stale grid assumptions.')
        provenance = manifest['variant']
    report = {'schema': 1, 'purpose': 'Diagnostic only; NOT physics acceptance or visual approval',
              'provenance': provenance, 'grid': asdict(grid), 'cellMetres': grid.cell,
              'floorThresholdExclusive': 1000, 'history': [], 'errors': []}
    cache = workspace / 'render/cache/data'
    for frame in range(1, 289):
        try:
            m = frame_metrics(cache / f'pp_{frame:04d}.uni', grid)
            report['history'].append({'frame': frame, **m})
        except (OSError, ValueError, EOFError, struct.error) as exc:
            report['errors'].append({'frame': frame, 'error': str(exc)})
    history = report['history']
    report['complete'] = len(history) == 288 and not report['errors']
    report['peakFloorParticles'] = max((r['floorParticles'] for r in history), default=0)
    report['peakFloorFrame'] = max(history, key=lambda r: r['floorParticles'])['frame'] if history else None
    report['peakTableParticles'] = max((r['tableParticles'] for r in history), default=0)
    report['firstFloorFrame'] = next((r['frame'] for r in history if r['floorParticles'] > 20), None)
    report['peakBoundaryParticles'] = max((r['nearHorizontalBoundaryParticles'] for r in history), default=0)
    report['minimumHorizontalMarginMetres'] = min(
        (r['minimumHorizontalMarginMetres'] for r in history if r['activeParticles']), default=None)
    report['floorCountConditionMet'] = report['complete'] and report['peakFloorParticles'] > 1000
    report['horizontalClearanceConditionMet'] = report['complete'] and report['peakBoundaryParticles'] == 0
    output = workspace / 'render/floor-impact-diagnostics.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    return report


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    setup = sub.add_parser('prepare', help='Create an isolated, unbaked wider-domain source workspace')
    setup.add_argument('--workspace', type=Path, default=ROOT.parent / 'sculpt-floor-impact-wide')
    inspect = sub.add_parser('analyze', help='Save cache diagnostics; never creates a passing simulation.json')
    inspect.add_argument('--workspace', type=Path, default=ROOT)
    inspect.add_argument('--legacy', action='store_true', help='Explicitly use the old 6 mm grid/origin')
    args = p.parse_args(argv)
    try:
        if args.command == 'prepare':
            data = prepare(ROOT, args.workspace)
            print(json.dumps({'workspace': str(args.workspace.resolve()), **data}, indent=2))
            print('SETUP_ONLY: no simulation or render has run. Follow FLOOR_IMPACT_RECOVERY.md.')
            return 0
        data = analyze(args.workspace, args.legacy)
        print(json.dumps({k: v for k, v in data.items() if k != 'history'}, indent=2))
        print('Saved render/floor-impact-diagnostics.json; run the ORIGINAL physics validator separately.')
        # Fail on invalid data. Complete diagnostic reports remain readable even when physical
        # counts fail; the unchanged validator is mandatory. The extra boundary check is enforced
        # for this isolated experiment, not retroactively on the historical baseline.
        if not data['complete']:
            return 2
        return 0 if args.legacy or data['horizontalClearanceConditionMet'] else 3
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
