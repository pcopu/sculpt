"""Synthetic cache/setup regressions. These do NOT claim a new fluid bake passed."""
import gzip
import importlib.util
import json
import math
from pathlib import Path
import struct
import sys
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('floor_impact_recovery',
    Path(__file__).resolve().parents[1] / 'tools/floor_impact_recovery.py')
r = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = r
spec.loader.exec_module(r)


def fake_source(root):
    for directory in ('tools', 'src', 'tests', 'render/cache', 'public/assets'):
        (root / directory).mkdir(parents=True, exist_ok=True)
    (root / 'tools/build_scene.py').write_text(
        "def make_scene(resolution):\n"
        "    domain=box('COFFEE / Mantaflow FLIP',(.576,-.64,.365),(1.20,.96,.79),coffee)\n"
        "p.add_argument('--resolution',type=int,default=200)\n")
    (root / 'tools/bake_checked.py').write_text(
        'def upright_check(directory,dx=.006,origin=(-.024,-1.12,-.03)):\n    pass\n')
    (root / 'tools/validate_physics.py').write_text(
        "DX=.006;ORIGIN=(-.024,-1.12,-.03);FRAMES=288\n"
        "assert max_floor>1000,f'Insufficient physical floor impact: {max_floor}'\n")
    (root / 'tools/bake_wetmaps.py').write_text(
        'p.add_argument("--origin",default=[-.024,-1.12,-.03])\n'
        'p.add_argument("--size",default=[1.20,.96])\n')
    (root / 'tools/render_gpu.py').write_text('# existing GPU wrapper\n')
    (root / 'tools/stage_spill.py').write_text('# baseline staging\n')
    (root / 'render/cache/KEEP').write_text('preserved expensive cache')
    (root / 'public/assets/KEEP').write_text('preserved original assets')
    return root


def cache_file(path, points, grid=r.WIDE):
    header = bytearray(292)
    header[:4] = b'PB02'
    struct.pack_into('<i', header, 4, len(points))
    body = b''
    for world, flag in points:
        p = [(v - o) / grid.cell for v, o in zip(world, grid.origin)]
        body += struct.pack('<fffi', *p, flag)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(bytes(header) + body))


class FloorRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.source = fake_source(self.base / 'source')
        self.target = self.base / 'variant'

    def tearDown(self):
        self.tmp.cleanup()

    def test_preserves_six_mm_and_lattice_alignment(self):
        self.assertAlmostEqual(r.WIDE.cell, .006)
        self.assertAlmostEqual(r.LEGACY.cell, .006)
        for old, new in zip(r.LEGACY.origin, r.WIDE.origin):
            cells = (new - old) / .006
            self.assertAlmostEqual(cells, round(cells))
        self.assertEqual(tuple(round(x / .006) for x in r.WIDE.size), (320, 280, 132))

    def test_reported_peak_bounds_get_horizontal_margin(self):
        # Reported evidence from FLOOR_IMPACT_ISSUE.md, not a new simulation.
        world = (1.170, -.166, .01)
        old_margin = min(world[0] - r.LEGACY.origin[0], r.LEGACY.upper[0] - world[0],
                         world[1] - r.LEGACY.origin[1], r.LEGACY.upper[1] - world[1])
        new_margin = min(world[0] - r.WIDE.origin[0], r.WIDE.upper[0] - world[0],
                         world[1] - r.WIDE.origin[1], r.WIDE.upper[1] - world[1])
        self.assertLess(old_margin, .018)
        self.assertGreater(new_margin, .3)

    def test_prepares_synchronized_readers_without_changing_acceptance(self):
        m = r.prepare(self.source, self.target)
        for name, replacements in r.EDITS.items():
            actual = (self.target / name).read_text()
            for _, new in replacements:
                self.assertIn(new, actual)
        self.assertIn('assert max_floor>1000', (self.target / 'tools/validate_physics.py').read_text())
        self.assertEqual(m['floorThresholdExclusive'], 1000)
        self.assertEqual(m['status'], 'unbaked_candidate')

    def test_source_bake_and_assets_untouched_not_copied(self):
        before = {str(p.relative_to(self.source)): r.digest(p) for p in self.source.rglob('*') if p.is_file()}
        r.prepare(self.source, self.target)
        after = {str(p.relative_to(self.source)): r.digest(p) for p in self.source.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertFalse((self.target / 'render').exists())
        self.assertFalse((self.target / 'public/assets').exists())

    def test_existing_target_refused_without_changes(self):
        self.target.mkdir()
        (self.target / 'KEEP').write_text('do not overwrite')
        with self.assertRaises(FileExistsError): r.prepare(self.source, self.target)
        self.assertEqual((self.target / 'KEEP').read_text(), 'do not overwrite')

    def test_overlapping_paths_refused(self):
        for target in (self.source, self.source / 'child', self.base):
            with self.subTest(target=target), self.assertRaises(ValueError):
                r.prepare(self.source, target)

    def test_unknown_revision_fails_before_creating_workspace(self):
        (self.source / 'tools/build_scene.py').write_text('# newer incompatible scene\n')
        with self.assertRaises(RuntimeError): r.prepare(self.source, self.target)
        self.assertFalse(self.target.exists())

    def test_prevents_legacy_staging_in_variant(self):
        r.prepare(self.source, self.target)
        with self.assertRaisesRegex(RuntimeError, 'Already staged'):
            exec((self.target / 'tools/stage_spill.py').read_text(), {})

    def test_coordinates_flags_and_contacts(self):
        path = self.base / 'test.uni'
        cache_file(path, [((.9, -.6, .005), 0), ((.3, -.3, .546), 0), ((.9, -.6, .005), 1)])
        m = r.frame_metrics(path, r.WIDE)
        self.assertEqual((m['activeParticles'], m['floorParticles'], m['tableParticles']), (2, 1, 1))
        self.assertEqual(m['nearHorizontalBoundaryParticles'], 0)

    def test_reports_three_cell_boundary_intrusion(self):
        path = self.base / 'test.uni'
        cache_file(path, [((r.WIDE.upper[0] - .006, -.6, .01), 0)])
        self.assertEqual(r.frame_metrics(path, r.WIDE)['nearHorizontalBoundaryParticles'], 1)

    def test_bad_header_and_truncation_fail(self):
        path = self.base / 'test.uni'
        for data in (b'wrong', b'PB02' + struct.pack('<i', 1) + b'\0' * 284):
            with self.subTest(data=data[:5]):
                path.write_bytes(gzip.compress(data))
                with self.assertRaises(ValueError): list(r.particles(path))

    def test_nonfinite_particles_fail(self):
        path = self.base / 'test.uni'
        cache_file(path, [((math.nan, 0, 0), 0)])
        with self.assertRaises(ValueError): list(r.particles(path))

    def test_incomplete_cache_still_writes_failure_diagnostics_not_acceptance(self):
        r.prepare(self.source, self.target)
        cache_file(self.target / 'render/cache/data/pp_0001.uni', [((.9, -.6, .01), 0)])
        data = r.analyze(self.target)
        self.assertFalse(data['complete'])
        self.assertEqual(len(data['errors']), 287)
        self.assertTrue((self.target / 'render/floor-impact-diagnostics.json').is_file())
        self.assertFalse((self.target / 'public/assets/simulation.json').exists())

    def test_threshold_remains_strictly_greater_than_1000(self):
        r.prepare(self.source, self.target)
        path = self.target / 'render/cache/data/pp_0001.uni'
        cache_file(path, [((.9, -.6, .01), 0)] * 1000)
        compressed = path.read_bytes()
        for i in range(2, 289):
            path.with_name(f'pp_{i:04d}.uni').write_bytes(compressed)
        data = r.analyze(self.target)
        self.assertTrue(data['complete'])
        self.assertFalse(data['floorCountConditionMet'])
        cache_file(path, [((.9, -.6, .01), 0)] * 1001)
        self.assertTrue(r.analyze(self.target)['floorCountConditionMet'])
        self.assertFalse((self.target / 'public/assets/simulation.json').exists())

    def test_changed_sources_reject_stale_grid_assumptions(self):
        r.prepare(self.source, self.target)
        with (self.target / 'tools/validate_physics.py').open('a') as f: f.write('# changed\n')
        with self.assertRaisesRegex(RuntimeError, 'changed after setup'): r.analyze(self.target)

    def test_wide_cache_cannot_be_read_as_legacy(self):
        r.prepare(self.source, self.target)
        with self.assertRaises(ValueError): r.analyze(self.target, legacy=True)

if __name__ == '__main__':
    unittest.main()
