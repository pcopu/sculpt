"""Idempotent scene revision following containment and moving-cup tests.
Apply before rebuilding the simulation. Both renderers use the same camera path.
"""
from pathlib import Path
import json,re
root=Path(__file__).resolve().parents[1]
keys=[[0,[1.43,-1.65,1.16],[.05,-.13,.51],49],[94,[.72,-.94,.84],[.27,-.295,.60],59],[164,[.63,-.91,.78],[.28,-.365,.575],58],[194,[.62,-1.05,.55],[.28,-.50,.31],50],[222,[.66,-1.16,.34],[.28,-.61,.045],52],[300,[.69,-1.20,.35],[.28,-.66,.055],54],[384,[.79,-1.22,.40],[.28,-.68,.083],52],[527,[1.42,-1.84,1.13],[.12,-.26,.35],47]]
p=root/'tools/build_scene.py';s=p.read_text()
def change(options,replacement):
    global s
    if replacement in s:return
    for old in options:
        if old in s:
            if s.count(old)!=1:raise RuntimeError('Ambiguous scene revision: '+old)
            s=s.replace(old,replacement);return
    raise RuntimeError('Unknown scene revision: '+repr(options))
change(['effector(cup,.65)'],'effector(cup,.6).effector_settings.subframes=2')
change(['root.location=(.275,-.347,TOP+.001)'],'root.location=(.275,-.322,TOP+.001)')
change(["flow=cylinder('Initial coffee volume',(.275,-.312,TOP+.017),(.275,-.312,TOP+.087),.0365,None,96)","flow=cylinder('Initial coffee volume',(.275,-.312,TOP+.028),(.275,-.312,TOP+.092),.027,None,96,r2=.036)"],"flow=cylinder('Initial coffee volume',(.275,-.287,TOP+.023),(.275,-.287,TOP+.100),.028,None,96,r2=.036)")
change(['fl.flow_settings.surface_distance=1.0;flow.hide_render'],'fl.flow_settings.surface_distance=0.0;flow.hide_render')
change(['ds.use_fractions=True;ds.fractions_threshold=.05'],'ds.use_fractions=False;ds.fractions_threshold=.05')
change(['ds.timesteps_max=6;ds.flip_ratio'],'ds.timesteps_max=8;ds.cfl_condition=2.0;ds.flip_ratio')
s=s.replace('# Approximately 293 mL initial geometry; no artificial stream or expanding puddle.','# Fitted initial volume; no artificial stream or expanding puddle.')
s,n=re.subn(r'^CAMERA_KEYS=.*$', 'CAMERA_KEYS='+json.dumps(keys,separators=(',',':')),s,flags=re.M)
assert n==1;p.write_text(s)
p=root/'src/timeline.mjs';s=p.read_text();s,n=re.subn(r'^export const keys=.*$','export const keys='+json.dumps(keys,separators=(',',':'))+';',s,flags=re.M);assert n==1;p.write_text(s)
p=root/'src/app.js';s=p.read_text();s=s.replace('cup.position.set(.275,-.347,.546)','cup.position.set(.275,-.322,.546)').replace('makeTranslation(-.275,.347,-.546)','makeTranslation(-.275,.322,-.546)').replace('xyz([.275,-.32,.65])','xyz([.275,-.29,.65])');p.write_text(s)
p=root/'tools/bake_checked.py';s=p.read_text().replace('y+.312','y+.287');s=s.replace("[blender,'-b','-t',threads,'--python',", "[blender,'-b','-t',threads,'--python-exit-code','1','--python',");p.write_text(s)
print('Staged fuller contained cup, tabletop-first spill and synchronized floor-impact camera')
