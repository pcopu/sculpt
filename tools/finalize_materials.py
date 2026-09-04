"""Finalize volume optics and particle-derived wood wetness in the editable master."""
import bpy,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_scene as film

def add_wetting(material_name,prefix,height,folder):
    m=bpy.data.materials[material_name];n=m.node_tree.nodes;l=m.node_tree.links;b=n.get('Principled BSDF')
    if n.get('Contact wetness'):return
    meta=json.loads((folder/'wetness.json').read_text());origin=meta['origin'];size=meta['size']
    geo=n.new('ShaderNodeNewGeometry');sub=n.new('ShaderNodeVectorMath');sub.operation='SUBTRACT';sub.inputs[1].default_value=(*origin,0);l.new(geo.outputs['Position'],sub.inputs[0])
    scale=n.new('ShaderNodeVectorMath');scale.operation='MULTIPLY';scale.inputs[1].default_value=(1/size[0],1/size[1],0);l.new(sub.outputs['Vector'],scale.inputs[0])
    tex=n.new('ShaderNodeTexImage');tex.name='Contact wetness';tex.image=bpy.data.images.load(str(folder/f'{prefix}_0001.png'),check_existing=True);tex.image.colorspace_settings.name='Non-Color';tex.image.source='SEQUENCE';tex.extension='CLIP';tex.image_user.frame_duration=meta['frames'];tex.image_user.frame_start=1;tex.image_user.use_auto_refresh=True;l.new(scale.outputs['Vector'],tex.inputs['Vector'])
    xyz=n.new('ShaderNodeSeparateXYZ');l.new(geo.outputs['Position'],xyz.inputs[0]);dist=n.new('ShaderNodeMath');dist.operation='SUBTRACT';dist.inputs[1].default_value=height;l.new(xyz.outputs['Z'],dist.inputs[0]);ab=n.new('ShaderNodeMath');ab.operation='ABSOLUTE';l.new(dist.outputs[0],ab.inputs[0]);near=n.new('ShaderNodeMath');near.operation='LESS_THAN';near.inputs[1].default_value=.011;l.new(ab.outputs[0],near.inputs[0])
    wet=n.new('ShaderNodeMath');wet.operation='MULTIPLY';l.new(tex.outputs['Color'],wet.inputs[0]);l.new(near.outputs[0],wet.inputs[1])
    strength=n.new('ShaderNodeMath');strength.operation='MULTIPLY';strength.inputs[1].default_value=.72;l.new(wet.outputs[0],strength.inputs[0])
    source=b.inputs['Base Color'].links[0].from_socket
    mix=n.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[2].default_value=(.30,.23,.17,1);l.new(strength.outputs[0],mix.inputs[0]);l.new(source,mix.inputs[1]);l.new(mix.outputs[0],b.inputs['Base Color'])
    rough=n.new('ShaderNodeMapRange');rough.inputs['From Min'].default_value=0;rough.inputs['From Max'].default_value=1;rough.inputs['To Min'].default_value=b.inputs['Roughness'].default_value;rough.inputs['To Max'].default_value=.085;l.new(wet.outputs[0],rough.inputs['Value']);l.new(rough.outputs['Result'],b.inputs['Roughness'])
    coat=n.new('ShaderNodeMath');coat.operation='MULTIPLY_ADD';coat.inputs[1].default_value=.4;coat.inputs[2].default_value=b.inputs['Coat Weight'].default_value;l.new(wet.outputs[0],coat.inputs[0]);l.new(coat.outputs[0],b.inputs['Coat Weight'])

def finalize():
    film.load();sc=bpy.context.scene;sc.frame_set(1)
    m=bpy.data.materials['Coffee / dark amber dielectric'];b=m.node_tree.nodes['Principled BSDF'];b.inputs['Base Color'].default_value=(1,1,1,1);b.inputs['Roughness'].default_value=.075;b.inputs['IOR'].default_value=1.333;b.inputs['Transmission Weight'].default_value=1;b.inputs['Coat Weight'].default_value=0
    vol=m.node_tree.nodes.get('Coffee absorption') or m.node_tree.nodes.new('ShaderNodeVolumeAbsorption');vol.name='Coffee absorption';vol.inputs['Color'].default_value=(.65,.22,.07,1);vol.inputs['Density'].default_value=200;m.node_tree.links.new(vol.outputs['Volume'],m.node_tree.nodes['Material Output'].inputs['Volume'])
    wet=film.ASSETS/'wetness'
    add_wetting('Warm white oak planks / original grain','floor',0,wet)
    add_wetting('Oiled American walnut / original grain','table',.545,wet)
    for p in bpy.data.objects['COFFEE / Mantaflow FLIP'].data.polygons:p.use_smooth=True
    bpy.ops.file.make_paths_relative();bpy.ops.wm.save_as_mainfile(filepath=str(film.OUT/'coffee.blend'));print('FINAL_MATERIALS_SAVED',flush=True)
if __name__=='__main__':finalize()
