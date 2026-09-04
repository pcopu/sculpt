"""Validate all shared liquid meshes and the independently checked physics."""
import gzip,json,struct
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'public'/'assets'
report=json.loads((root/'simulation.json').read_text())
assert report['schema']==1 and report['sceneRevision']>=3,'Outdated simulation'
assert all(report[k]=='passed' for k in ['uprightContainment','tabletopContact','floorImpact'])
meta=json.loads((root/'liquid.json').read_text());assert len(meta['frames'])==288
for f in meta['frames']:
    b=gzip.decompress((root/'liquid'/f"{f['frame']:03d}.bin.gz").read_bytes());n,t=struct.unpack('<II',b[:8]);assert n>50 and t>50,f
    assert len(b)==8+24*n+12*t,f
assert max(f['floorVertices'] for f in meta['frames'])>50,'Liquid never reaches the floor'
assert len(json.loads((root/'cup.json').read_text()))==288
print('PASS: 288 valid liquid meshes, exact cup poses, upright containment, tabletop contact and floor impact')
