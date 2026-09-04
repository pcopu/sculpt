"""Idempotent migration of the initial scene's fluid settings.
The fitted frustum and non-fractional obstacles passed an upright containment test.
This script changes source, not a cached/rendered surface or the motion itself.
"""
from pathlib import Path
p=Path(__file__).with_name('build_scene.py');s=p.read_text()
changes=[
("effector(cup,.65)","effector(cup,.6).effector_settings.subframes=2"),
("flow=cylinder('Initial coffee volume',(.275,-.312,TOP+.017),(.275,-.312,TOP+.087),.0365,None,96)","flow=cylinder('Initial coffee volume',(.275,-.312,TOP+.028),(.275,-.312,TOP+.092),.027,None,96,r2=.036)"),
("fl.flow_settings.surface_distance=1.0;flow.hide_render", "fl.flow_settings.surface_distance=0.0;flow.hide_render"),
("ds.use_fractions=True;ds.fractions_threshold=.05", "ds.use_fractions=False;ds.fractions_threshold=.05"),
("ds.timesteps_max=6;ds.flip_ratio", "ds.timesteps_max=8;ds.cfl_condition=2.0;ds.flip_ratio"),
("# Approximately 293 mL initial geometry; no artificial stream or expanding puddle.", "# Fitted initial volume; no artificial stream or expanding puddle.")]
for old,new in changes:
    if old in s:
        if s.count(old)!=1:raise RuntimeError(f'Ambiguous patch: {old}')
        s=s.replace(old,new)
    elif new not in s:raise RuntimeError(f'Unknown source revision: {old}')
p.write_text(s)
print('Source corrected: contained frustum, no source dilation, stable solid obstacles')
