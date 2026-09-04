"""Render a disjoint film frame range from a relocated, already-baked scene."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
import build_scene as film
original_load=film.load
def load_for_render():
    original_load()
    sc=bpy.context.scene
    sc.render.use_persistent_data=True
    domain=bpy.data.objects['COFFEE / Mantaflow FLIP']
    for face in domain.data.polygons:face.use_smooth=True
    sc.cycles.use_denoising=True
film.load=load_for_render
if __name__=='__main__':
    args=film.argparser()
    film.render(args,preview=args.mode=='preview')
    directory=film.OUT/('preview' if args.mode=='preview' else 'frames')
    expected=[0,120,168,208,260,336,420,527] if args.mode=='preview' else range(args.start,args.end)
    for f in expected:
        path=directory/f'{f:05d}.png'
        if not path.exists() or path.stat().st_size<10000:raise RuntimeError(f'Missing rendered frame: {f}')
