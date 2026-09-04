"""Render a disjoint film frame range from a relocated, already-baked scene."""
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
