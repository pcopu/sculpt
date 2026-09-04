"""Idempotent final staging after upright and moving-cup physical tests.
A diagonal tip sends coffee across the wood. The 200-cell, 1.2 m domain keeps
its tested 6 mm cell size while including the floor beyond the right edge.
"""
from pathlib import Path
import json,re
root=Path(__file__).resolve().parents[1]
keys=[[0,[1.43,-1.65,1.16],[.05,-.13,.51],49],[94,[.72,-.94,.84],[.275,-.312,.60],59],[164,[.79,-.91,.78],[.355,-.365,.575],58],[200,[.98,-1.04,.83],[.56,-.41,.535],54],[230,[1.12,-1.15,.56],[.78,-.48,.30],52],[260,[1.18,-1.29,.34],[.88,-.55,.055],52],[340,[1.24,-1.33,.39],[.85,-.61,.06],54],[384,[1.26,-1.36,.44],[.85,-.62,.083],52],[527,[1.85,-1.90,1.22],[.35,-.27,.35],43]]
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
change(['root.location=(.275,-.347,TOP+.001)','root.location=(.275,-.322,TOP+.001)'],'root.location=(.275+math.sin(math.pi/3)*.035,-.312-math.cos(math.pi/3)*.035,TOP+.001)')
change(['root.rotation_euler=(ang,0,0)'],'root.rotation_euler=(ang,0,math.pi/3)')
change(["flow=cylinder('Initial coffee volume',(.275,-.312,TOP+.017),(.275,-.312,TOP+.087),.0365,None,96)","flow=cylinder('Initial coffee volume',(.275,-.312,TOP+.028),(.275,-.312,TOP+.092),.027,None,96,r2=.036)","flow=cylinder('Initial coffee volume',(.275,-.287,TOP+.023),(.275,-.287,TOP+.100),.028,None,96,r2=.036)"],"flow=cylinder('Initial coffee volume',(.275,-.312,TOP+.023),(.275,-.312,TOP+.100),.028,None,96,r2=.036)")
change(["domain=box('COFFEE / Mantaflow FLIP',(.29,-.64,.365),(.94,.96,.79)","domain=box('COFFEE / Mantaflow FLIP',(.446,-.64,.365),(.94,.96,.79)"],"domain=box('COFFEE / Mantaflow FLIP',(.576,-.64,.365),(1.20,.96,.79)")
change(["p.add_argument('--resolution',type=int,default=160)"],"p.add_argument('--resolution',type=int,default=200)")
change(['fl.flow_settings.surface_distance=1.0;flow.hide_render'],'fl.flow_settings.surface_distance=0.0;flow.hide_render')
change(['ds.use_fractions=True;ds.fractions_threshold=.05'],'ds.use_fractions=False;ds.fractions_threshold=.05')
change(['ds.timesteps_max=6;ds.flip_ratio'],'ds.timesteps_max=8;ds.cfl_condition=2.0;ds.flip_ratio')
s=s.replace('# Approximately 293 mL initial geometry; no artificial stream or expanding puddle.','# Fitted initial volume; no artificial stream or expanding puddle.')
s,n=re.subn(r'^CAMERA_KEYS=.*$', 'CAMERA_KEYS='+json.dumps(keys,separators=(',',':')),s,flags=re.M);assert n==1
old="coffee=material('Coffee / dark amber dielectric',(.033,.009,.0028),.16,coat=.22);cb=coffee.node_tree.nodes['Principled BSDF'];cb.inputs['IOR'].default_value=1.333;cb.inputs['Transmission Weight'].default_value=.18;cb.inputs['Coat Roughness'].default_value=.08"
new="coffee=material('Coffee / dark amber dielectric',(1,1,1),.075);cb=coffee.node_tree.nodes['Principled BSDF'];cb.inputs['IOR'].default_value=1.333;cb.inputs['Transmission Weight'].default_value=1.0\n    absorption=coffee.node_tree.nodes.new('ShaderNodeVolumeAbsorption');absorption.name='Coffee absorption';absorption.inputs['Color'].default_value=(.65,.22,.07,1);absorption.inputs['Density'].default_value=200;coffee.node_tree.links.new(absorption.outputs['Volume'],coffee.node_tree.nodes['Material Output'].inputs['Volume'])"
change([old],new);p.write_text(s)
p=root/'src/timeline.mjs';s=p.read_text();s,n=re.subn(r'^export const keys=.*$','export const keys='+json.dumps(keys,separators=(',',':'))+';',s,flags=re.M);assert n==1;p.write_text(s)
p=root/'src/app.js';s=p.read_text()
for y in ('.347','.322'):
    old=f"cup=new THREE.Group();cup.position.set(.275,-{y},.546);stage.add(cup);\n const invPivot=new THREE.Matrix4().makeTranslation(-.275,{y},-.546);"
    new="cup=new THREE.Group();cup.position.fromArray(cupData[0].position);cup.rotation.set(...cupData[0].rotation);cup.updateMatrix();stage.add(cup);\n const invPivot=cup.matrix.clone().invert();"
    s=s.replace(old,new)
assert 'const invPivot=cup.matrix.clone().invert()' in s
s=s.replace('xyz([.275,-.32,.65])','xyz([.275,-.312,.65])').replace('xyz([.275,-.29,.65])','xyz([.275,-.312,.65])');p.write_text(s)
p=root/'tools/bake_checked.py';s=p.read_text().replace('y+.287','y+.312').replace('origin=(-.18,-1.12,-.03)','origin=(-.024,-1.12,-.03)');s=s.replace("[blender,'-b','-t',threads,'--python',", "[blender,'-b','-t',threads,'--python-exit-code','1','--python',");p.write_text(s)
p=root/'tools/validate_physics.py';s=p.read_text().replace('ORIGIN=(-.18,-1.12,-.03)','ORIGIN=(-.024,-1.12,-.03)').replace('y+.287','y+.312');p.write_text(s)
p=root/'tools/bake_wetmaps.py';p.write_text(p.read_text().replace('default=[.94,.96]','default=[1.20,.96]'))
p=root/'README.md';p.write_text(p.read_text().replace('--resolution 160','--resolution 200'))
print('Locked tested diagonal spill, expanded floor coverage, volume optics and impact camera')
