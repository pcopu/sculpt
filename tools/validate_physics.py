"""Validate physical events in the solver's particle cache, not just pictures."""
from pathlib import Path
import gzip,struct,math,json
ROOT=Path(__file__).resolve().parents[1]
DX=.006;ORIGIN=(-.024,-1.12,-.03);FRAMES=288
history=[]
for frame in range(1,FRAMES+1):
    p=ROOT/'render/cache/data'/f'pp_{frame:04d}.uni'
    raw=gzip.decompress(p.read_bytes())
    assert raw[:4]==b'PB02',f'Unexpected particle format: {p}'
    count=struct.unpack_from('<i',raw,4)[0]
    assert len(raw)>=292+count*16,f'Truncated particle cache: {p}'
    active=table=floor=leaked=0
    for x,y,z,flag in struct.iter_unpack('<fffi',raw[292:292+count*16]):
        if flag:continue
        x=ORIGIN[0]+x*DX;y=ORIGIN[1]+y*DX;z=ORIGIN[2]+z*DX
        assert math.isfinite(x+y+z),f'Non-finite particle at {frame}'
        active+=1
        if .540<z<.555 and y>-.445 and -.70<x<.70:table+=1
        if -.01<z<.035:floor+=1
        if frame in (1,10,22) and (math.hypot(x-.275,y+.312)>.05 or z<.558):leaked+=1
    assert active>1000,f'Liquid lost at frame {frame}'
    if frame in (1,10,22):assert leaked/active<.005,f'Upright cup leaked at {frame}: {leaked}/{active}'
    history.append({'frame':frame,'activeParticles':active,'tableParticles':table,'floorParticles':floor,'uprightEscaped':leaked})
max_table=max(f['tableParticles'] for f in history);max_floor=max(f['floorParticles'] for f in history)
assert max_table>200,f'Insufficient physical tabletop contact: {max_table}'
assert max_floor>1000,f'Insufficient physical floor impact: {max_floor}'
report={'schema':1,'sceneRevision':3,'solver':'Mantaflow FLIP','gridCellMetres':DX,'simulationFrames':FRAMES,'timeScale':.25,'uprightContainment':'passed','tabletopContact':'passed','floorImpact':'passed','firstTableFrame':next(f['frame'] for f in history if f['tableParticles']>20),'firstFloorFrame':next(f['frame'] for f in history if f['floorParticles']>20),'peakTableParticles':max_table,'peakFloorParticles':max_floor,'history':history}
(ROOT/'public/assets/simulation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='history'},indent=2))
