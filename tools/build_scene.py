"""The Last Sip. Blender 4.3.2; original geometry and materials; metres, Z-up.
The offline Cycles render and Three.js viewer share one baked Mantaflow liquid.
"""
import bpy, math, os, sys, json, random, argparse, struct, gzip
from mathutils import Vector
import numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'render'; ASSETS=ROOT/'public'/'assets'
FPS,FRAMES,SIM_END=24,528,288
TOP=.545
rng=random.Random(7342)

def argparser():
    p=argparse.ArgumentParser()
    p.add_argument('--mode',choices=['build','bake','preview','render','export'],default='build')
    p.add_argument('--resolution',type=int,default=200)
    p.add_argument('--start',type=int,default=0)
    p.add_argument('--end',type=int,default=528)
    p.add_argument('--samples',type=int,default=40)
    p.add_argument('--width',type=int,default=1920)
    p.add_argument('--engine',default='CYCLES')
    return p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])

def smooth(o):
    if o.type=='MESH':
        for p in o.data.polygons:p.use_smooth=True
    return o

def material(name,color,rough=.5,metallic=0.,coat=0.):
    m=bpy.data.materials.new(name);m.use_nodes=True;m.diffuse_color=(*color,1)
    b=m.node_tree.nodes.get('Principled BSDF')
    for key,val in [('Base Color',(*color,1)),('Roughness',rough),('Metallic',metallic),('Coat Weight',coat),('Coat Roughness',.12)]:b.inputs[key].default_value=val
    return m

def noise_surface(m,scale,strength,distance):
    n=m.node_tree.nodes;l=m.node_tree.links
    a=n.new('ShaderNodeTexNoise');a.inputs['Scale'].default_value=scale;a.inputs['Detail'].default_value=3
    b=n.new('ShaderNodeBump');b.inputs['Strength'].default_value=strength;b.inputs['Distance'].default_value=distance
    l.new(a.outputs['Fac'],b.inputs['Height']);l.new(b.outputs[0],n.get('Principled BSDF').inputs['Normal'])

def image(name,a):
    path=ASSETS/(name+'.png')
    if path.exists():return bpy.data.images.load(str(path),check_existing=True)
    h,w=a.shape[:2];im=bpy.data.images.new(name,width=w,height=h,alpha=True)
    rgba=np.ones((h,w,4),dtype=np.float32);rgba[:,:,:3]=a
    im.pixels.foreach_set(rgba.ravel());im.filepath_raw=str(path);im.file_format='PNG';im.save();return im

def wood(name,walnut=True):
    m=material(name,(.18,.064,.024) if walnut else (.37,.23,.11),.32,coat=.16 if walnut else .03)
    n=m.node_tree.nodes;l=m.node_tree.links;b=n.get('Principled BSDF')
    y,x=np.mgrid[0:1:1024j,0:1:1024j]
    warp=.027*np.sin(x*11+np.sin(y*9))+.012*np.sin(x*27+y*5)
    grain=np.sin((y+warp)*430+2*np.sin(x*8));broad=np.sin((y+warp)*71+.6*np.cos(x*5));fine=np.sin((y+warp)*1460+x*11)*.18
    knot=np.sqrt(((x-.27)*.45)**2+((y-.64)*3.2)**2)
    mask=np.exp(-(((x-.27)/.18)**2+((y-.64)/.095)**2))
    value=np.clip(.55+grain*.20+broad*.18+fine*.10+.17*np.sin(knot*220+warp*30)*mask,.06,.98)
    lo=np.array([.062,.021,.009]) if walnut else np.array([.19,.105,.043]);hi=np.array([.34,.15,.055]) if walnut else np.array([.58,.39,.19])
    tx=n.new('ShaderNodeTexImage');tx.image=image('walnut' if walnut else 'oak',lo[None,None,:]+value[:,:,None]*(hi-lo)[None,None,:])
    l.new(tx.outputs['Color'],b.inputs['Base Color']);bump=n.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.17;bump.inputs['Distance'].default_value=.0007
    l.new(tx.outputs['Color'],bump.inputs['Height']);l.new(bump.outputs['Normal'],b.inputs['Normal']);return m

def box(name,loc,scale,mat,bevel=0.,segments=4):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if mat:o.data.materials.append(mat)
    if bevel:
        b=o.modifiers.new('soft machined edges','BEVEL');b.width=bevel;b.segments=segments;o.modifiers.new('weighted normals','WEIGHTED_NORMAL')
    return o

def ball(name,loc,scale,mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,location=loc);o=bpy.context.object;o.name=name;o.scale=scale;o.data.materials.append(mat);return smooth(o)

def cylinder(name,a,b,r,mat,vertices=32,r2=None):
    d=Vector(b)-Vector(a);bpy.ops.mesh.primitive_cone_add(vertices=vertices,radius1=r,radius2=r if r2 is None else r2,depth=d.length,location=(Vector(a)+Vector(b))/2)
    o=bpy.context.object;o.name=name;o.rotation_euler=d.to_track_quat('Z','Y').to_euler()
    if mat:o.data.materials.append(mat)
    return smooth(o)

def lathe(name,profile,mat,steps=96):
    verts=[];faces=[]
    for r,z in profile:
        for j in range(steps):
            t=j*math.tau/steps;verts.append((r*math.cos(t),r*math.sin(t),z))
    for i in range(len(profile)-1):
        for j in range(steps):
            a=i*steps+j;b=i*steps+(j+1)%steps;faces.append((a,b,b+steps,a+steps))
    me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update();o=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(o)
    if mat:me.materials.append(mat)
    return smooth(o)

def curve(name,points,r,mat):
    cu=bpy.data.curves.new(name,'CURVE');cu.dimensions='3D';cu.resolution_u=16;cu.bevel_depth=r;cu.bevel_resolution=4
    sp=cu.splines.new('BEZIER');sp.bezier_points.add(len(points)-1)
    for p,co in zip(sp.bezier_points,points):p.co=co;p.handle_left_type='AUTO';p.handle_right_type='AUTO'
    o=bpy.data.objects.new(name,cu);bpy.context.collection.objects.link(o);o.data.materials.append(mat);return o

def area(name,loc,target,power,color,size,size_y=None):
    d=bpy.data.lights.new(name,'AREA');d.energy=power;d.color=color
    if size_y:d.shape='RECTANGLE';d.size=size;d.size_y=size_y
    else:d.shape='DISK';d.size=size
    o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();return o

def effector(o,thickness=0):
    bpy.context.view_layer.objects.active=o;m=o.modifiers.new('fluid collision','FLUID');m.fluid_type='EFFECTOR';m.effector_settings.surface_distance=thickness;return m

def make_scene(resolution):
    OUT.mkdir(exist_ok=True,parents=True);ASSETS.mkdir(exist_ok=True,parents=True)
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    sc=bpy.context.scene;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.render.fps=FPS;sc.frame_start=1;sc.frame_end=SIM_END
    sc.render.resolution_x=1920;sc.render.resolution_y=1080;sc.render.resolution_percentage=100
    sc.render.image_settings.file_format='PNG';sc.render.image_settings.color_mode='RGB';sc.render.image_settings.color_depth='8'
    sc.cycles.samples=40;sc.cycles.use_denoising=True;sc.cycles.adaptive_threshold=.06
    sc.cycles.max_bounces=7;sc.cycles.diffuse_bounces=3;sc.cycles.glossy_bounces=4;sc.cycles.transmission_bounces=5
    sc.render.threads_mode='FIXED';sc.render.threads=int(os.environ.get('RENDER_THREADS','4'))
    sc.view_settings.view_transform='AgX';sc.view_settings.look='AgX - Medium High Contrast';sc.view_settings.exposure=.35
    world=bpy.data.worlds.new('Quiet morning atmosphere');world.use_nodes=True
    world.node_tree.nodes['Background'].inputs[0].default_value=(.38,.48,.62,1);world.node_tree.nodes['Background'].inputs[1].default_value=.25;sc.world=world
    walnut=wood('Oiled American walnut / original grain',True);oak=wood('Warm white oak planks / original grain',False)
    brass=material('Aged satin brass',(.32,.18,.065),.28,.8);dark=material('Charcoal powdercoat',(.018,.022,.019),.32,.25)
    plaster=material('Warm limewash',(.64,.59,.50),.9);noise_surface(plaster,110,.18,.002)
    cream=material('Ivory porcelain glaze',(.78,.76,.68),.18,coat=.3);noise_surface(cream,550,.08,.00015)
    clay=material('Unglazed stoneware foot',(.24,.088,.033),.67)
    fabric=material('Natural linen',(.51,.47,.39),.96);noise_surface(fabric,320,.3,.0008);fabric.node_tree.nodes['Principled BSDF'].inputs['Sheen Weight'].default_value=.35
    sage=material('Sage wool',(.115,.17,.12),.95);noise_surface(sage,300,.28,.0007)
    ochre=material('Ochre woven cushion',(.37,.17,.048),.92);noise_surface(ochre,300,.3,.0007)
    for row in range(26):
        y=-2.6+row*.205
        for col in range(5):
            x=-3.1+col*1.22+(row%3)*.405;box('Oak plank %02d %02d'%(row,col),(x,y,-.022),(1.216,.201,.044),oak,.0016,2)
    floor=box('Floor collision',(0,0,-.065),(6,6,.13),None);floor.hide_render=True;floor.display_type='WIRE';effector(floor)
    box('Limewash back wall',(0,2.20,1.55),(5,.14,3.1),plaster)
    box('Window wall upper',(-2.48,-.15,2.77),(.14,4.8,.66),plaster);box('Window wall lower',(-2.48,-.15,.24),(.14,4.8,.48),plaster)
    box('Window wall far pier',(-2.48,1.68,1.46),(.14,1.04,1.98),plaster);box('Window wall near pier',(-2.48,-2.00,1.46),(.14,.82,1.98),plaster)
    box('Baseboard back',(0,2.10,.06),(5,.028,.12),cream,.007)
    for y in [-1.56,-.19,1.18]:box('Window upright',(-2.36,y,1.46),(.09,.045,2.04),cream,.006)
    for z in [.47,1.47,2.47]:box('Window crossbar',(-2.36,-.19,z),(.09,2.80,.04),cream,.006)
    box('Window sill',(-2.25,-.19,.455),(.38,2.97,.06),oak,.008)
    foliage=material('Exterior muted foliage',(.12,.19,.09),.95)
    for i in range(18):ball('Garden canopy',(-3.7-rng.random()*2,rng.uniform(-3,3),rng.uniform(.2,2.5)),(rng.uniform(.4,.8),.7,.7),foliage)
    table=box('Walnut coffee table',(0,0,TOP-.035),(1.44,.90,.07),walnut,.022,8);effector(table)
    for x in [-.52,.52]:
        for y in [-.29,.29]:
            cylinder('Tapered walnut leg',(x*1.10,y*1.10,.045),(x,y,TOP-.065),.024,walnut,48,r2=.034)
            cylinder('Brass foot',(x*1.10,y*1.10,.012),(x*1.09,y*1.09,.065),.0245,brass,48)
    box('Sofa walnut base',(0,1.12,.22),(2.14,.80,.12),walnut,.045,6)
    for x in [-.83,.83]:
        for y in [.83,1.43]:cylinder('Sofa foot',(x,y,.02),(x,y,.23),.027,dark)
    box('Sofa back',(0,1.52,.73),(2.20,.25,.88),fabric,.12,8)
    for x in [-.51,.51]:box('Linen seat cushion',(x,1.07,.43),(.99,.75,.24),fabric,.10,8)
    for x in [-1.1,1.1]:box('Linen rounded arm',(x,1.13,.61),(.24,.88,.59),fabric,.1,8)
    p=box('Sage pillow',(-.66,1.25,.77),(.44,.16,.43),sage,.065,8);p.rotation_euler=(math.radians(-17),.08,-.1)
    p=box('Ochre pillow',(.63,1.24,.78),(.40,.18,.43),ochre,.067,8);p.rotation_euler=(math.radians(-15),-.12,.12)
    box('Art walnut frame',(.05,2.094,1.65),(1.44,.055,.87),walnut,.014)
    canvas=material('Art handmade paper',(.71,.67,.56),.98);box('Art paper',(.05,2.058,1.65),(1.39,.01,.82),canvas)
    artclay=material('Art terracotta pigment',(.37,.15,.077),.98);artink=material('Art umber pigment',(.061,.064,.049),.98)
    ball('Art sun',(-.26,2.043,1.79),(.25,.009,.25),artclay);ball('Art arc',(.33,2.031,1.53),(.42,.009,.17),artink)
    cylinder('Lamp stem',(-1.53,1.22,.035),(-1.53,1.22,1.62),.011,brass);cylinder('Lamp base',(-1.53,1.22,.006),(-1.53,1.22,.036),.18,dark,64)
    shade=material('Woven glowing lampshade',(.65,.49,.29),.9);b=shade.node_tree.nodes['Principled BSDF'];b.inputs['Emission Color'].default_value=(1,.57,.23,1);b.inputs['Emission Strength'].default_value=.14
    o=lathe('Linen lamp shade',[(.195,1.29),(.21,1.31),(.145,1.66),(.13,1.68),(.126,1.67),(.20,1.31),(.195,1.29)],shade);o.location=(-1.53,1.22,0)
    area('Lamp glow',(-1.53,1.22,1.38),(-1.53,1.22,.3),28,(1,.59,.28),.18)
    pages=material('Book cream pages',(.58,.55,.46),.92);cover=material('Book cloth cover',(.063,.10,.089),.78)
    for z,dim,mat in [(TOP+.005,(.28,.21,.008),cover),(TOP+.025,(.272,.201,.034),pages),(TOP+.046,(.28,.21,.007),cover)]:
        o=box('Clothbound book',(-.37,.11,z),dim,mat,.002);o.rotation_euler[2]=-.10
    vase=lathe('Stoneware bud vase',[(0,0),(.033,0),(.039,.012),(.043,.05),(.028,.08),(.014,.10),(.014,.13),(.010,.131),(.010,.105),(.022,.084),(.035,.05),(.03,.014),(0,.014)],clay,64);vase.location=(-.41,.20,TOP+.05)
    leaves=material('Olive leaf',(.07,.105,.038),.73)
    for j in range(3):
        start=(-.41,.20,TOP+.14);end=(-.44+j*.035,.21+j*.015,TOP+.33+j*.012);cylinder('Olive stem',start,end,.0013,walnut,12)
        for k in range(4):
            v=Vector(start).lerp(Vector(end),.35+k*.17)
            for side in [-1,1]:
                o=ball('Olive leaf',v+Vector((side*.012,0,.005)),(.018,.004,.006),leaves);o.rotation_euler[1]=side*.5
    pot=lathe('Large terracotta planter',[(0,0),(.17,0),(.19,.025),(.215,.34),(.20,.36),(.19,.35),(.176,.05),(0,.05)],clay,64);pot.location=(1.52,1.40,0)
    cylinder('Olive trunk',(1.52,1.40,.29),(1.49,1.42,1.54),.017,walnut,24,r2=.009)
    for j in range(11):
        angle=j*2.4;z=.78+j*.065;end=(1.5+math.cos(angle)*.36,1.4+math.sin(angle)*.31,z+.22)
        cylinder('Olive branch',(1.5,1.4,z-.10),end,.004,walnut,12,r2=.001)
        for k in range(9):
            v=Vector((1.5,1.4,z-.1)).lerp(Vector(end),.2+k*.09)
            for side in [-1,1]:
                o=ball('Tree leaf',v+Vector((math.cos(angle+side)*.025,math.sin(angle+side)*.025,.012)),(.045,.009,.017),leaves);o.rotation_euler=(rng.random(),rng.random(),angle+side*.7)
    root=bpy.data.objects.new('Cup pivot',None);bpy.context.collection.objects.link(root);root.location=(.275+math.sin(math.pi/3)*.035,-.312-math.cos(math.pi/3)*.035,TOP+.001)
    profile=[(0,0),(.032,0),(.037,.003),(.040,.016),(.046,.090),(.0468,.104),(.0456,.108),(.0416,.108),(.0402,.103),(.039,.091),(.034,.020),(.032,.014),(0,.014)]
    cup=lathe('Ivory coffee cup',profile,cream,128);cup.parent=root;cup.location=(0,.035,0)
    bpy.context.view_layer.objects.active=cup;cup.select_set(True);bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.mesh.remove_doubles(threshold=.00001);bpy.ops.mesh.normals_make_consistent(inside=False);bpy.ops.object.mode_set(mode='OBJECT');cup.select_set(False);effector(cup,.6).effector_settings.subframes=2
    pts=[]
    for j in range(25):
        a=-math.pi*.5+j/24*math.pi;pts.append((.040+.030*math.cos(a),.035,.060+.032*math.sin(a)))
    handle=curve('Porcelain loop handle',pts,.007,cream);handle.parent=root
    foot=lathe('Unglazed cup foot',[(.0305,.0005),(.032,.001),(.033,.003),(.032,.005),(.0305,.005)],clay,96);foot.parent=root;foot.location=(0,.035,0)
    for f,ang in [(1,0),(22,0),(34,.075),(48,.32),(64,.83),(80,1.42),(88,1.57),(98,1.50),(112,1.535),(130,1.525),(288,1.525)]:
        root.rotation_euler=(ang,0,math.pi/3);root.location.z=TOP+.001+.012*math.sin(ang);root.keyframe_insert(data_path='rotation_euler',frame=f);root.keyframe_insert(data_path='location',frame=f)
    for fc in root.animation_data.action.fcurves:
        for kp in fc.keyframe_points:kp.interpolation='BEZIER';kp.handle_left_type='AUTO_CLAMPED';kp.handle_right_type='AUTO_CLAMPED'
    # Fitted initial volume; no artificial stream or expanding puddle.
    coffee=material('Coffee / dark amber dielectric',(1,1,1),.075);cb=coffee.node_tree.nodes['Principled BSDF'];cb.inputs['IOR'].default_value=1.333;cb.inputs['Transmission Weight'].default_value=1.0
    absorption=coffee.node_tree.nodes.new('ShaderNodeVolumeAbsorption');absorption.name='Coffee absorption';absorption.inputs['Color'].default_value=(.65,.22,.07,1);absorption.inputs['Density'].default_value=200;coffee.node_tree.links.new(absorption.outputs['Volume'],coffee.node_tree.nodes['Material Output'].inputs['Volume'])
    flow=cylinder('Initial coffee volume',(.275,-.312,TOP+.023),(.275,-.312,TOP+.100),.028,None,96,r2=.036);bpy.context.view_layer.objects.active=flow
    fl=flow.modifiers.new('Initial volume','FLUID');fl.fluid_type='FLOW';fl.flow_settings.flow_type='LIQUID';fl.flow_settings.flow_behavior='GEOMETRY';fl.flow_settings.surface_distance=0.0;flow.hide_render=True;flow.display_type='WIRE'
    domain=box('COFFEE / Mantaflow FLIP',(.576,-.64,.365),(1.20,.96,.79),coffee);bpy.context.view_layer.objects.active=domain
    dm=domain.modifiers.new('Liquid solver','FLUID');dm.fluid_type='DOMAIN';ds=dm.domain_settings;ds.domain_type='LIQUID';ds.resolution_max=resolution;ds.cache_type='MODULAR'
    ds.cache_frame_start=1;ds.cache_frame_end=SIM_END;ds.cache_directory=str(OUT/'cache');ds.cache_data_format='UNI';ds.cache_mesh_format='BOBJECT';ds.use_mesh=True;ds.mesh_scale=2;ds.mesh_particle_radius=1.7;ds.mesh_smoothen_pos=2;ds.mesh_smoothen_neg=2
    ds.time_scale=.25;ds.timesteps_min=2;ds.timesteps_max=8;ds.cfl_condition=2.0;ds.flip_ratio=.94;ds.particle_randomness=.1;ds.use_fractions=False;ds.fractions_threshold=.05;ds.use_collision_border_bottom=True;sc.gravity=(0,0,-9.81)
    domain['simulation']='Mantaflow FLIP; initial volume; moving cup collider; gravity; floor and table collisions'
    area('Window daylight',(-2.20,-.55,1.95),(.2,-.3,.4),420,(1,.84,.63),2.25,1.65);area('Large cool bounce',(1.3,-.5,2.4),(.1,-.2,.4),95,(.72,.83,1),2.0);area('Coffee rim strip',(.35,.25,1.7),(.27,-.36,.5),48,(1,.83,.60),.62,.14)
    sun=bpy.data.lights.new('Late afternoon sun','SUN');sun.energy=1.35;sun.angle=.075;sun.color=(1,.79,.52);o=bpy.data.objects.new('Late afternoon sun',sun);bpy.context.collection.objects.link(o);o.rotation_euler=(math.radians(29),math.radians(-34),math.radians(-65))
    camera_data=bpy.data.cameras.new('Cinema camera');cam=bpy.data.objects.new('Cinema camera',camera_data);bpy.context.collection.objects.link(cam);sc.camera=cam;camera_data.lens=52;camera_data.sensor_width=36;camera_data.clip_start=.012;camera_data.clip_end=100;camera_data.dof.use_dof=True;camera_data.dof.aperture_fstop=5.6;camera_data.dof.aperture_blades=9
    focus=bpy.data.objects.new('Focus target',None);bpy.context.collection.objects.link(focus);camera_data.dof.focus_object=focus
    sc.use_nodes=True;n=sc.node_tree.nodes;n.clear();l=sc.node_tree.links;rl=n.new('CompositorNodeRLayers');gl=n.new('CompositorNodeGlare');gl.glare_type='FOG_GLOW';gl.quality='HIGH';gl.threshold=2;gl.mix=-.97;out=n.new('CompositorNodeComposite');l.new(rl.outputs['Image'],gl.inputs['Image']);l.new(gl.outputs['Image'],out.inputs['Image'])
    sc.frame_set(1);set_camera(0);bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'coffee.blend'));print('SCENE_BUILT',len(sc.objects),flush=True)

def sim_frame(f):return max(1,min(SIM_END,f-95))
CAMERA_KEYS=[[0,[1.43,-1.65,1.16],[0.05,-0.13,0.51],49],[94,[0.72,-0.94,0.84],[0.275,-0.312,0.6],59],[164,[0.79,-0.91,0.78],[0.355,-0.365,0.575],58],[200,[0.98,-1.04,0.83],[0.56,-0.41,0.535],54],[230,[1.12,-1.15,0.56],[0.78,-0.48,0.3],52],[260,[1.18,-1.29,0.34],[0.88,-0.55,0.055],52],[340,[1.24,-1.33,0.39],[0.85,-0.61,0.06],54],[384,[1.26,-1.36,0.44],[0.85,-0.62,0.083],52],[527,[1.85,-1.9,1.22],[0.35,-0.27,0.35],43]]
def catmull(p0,p1,p2,p3,t):return .5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t*t*t)
def camera_values(f):
    k=0
    while k<len(CAMERA_KEYS)-2 and f>CAMERA_KEYS[k+1][0]:k+=1
    a=CAMERA_KEYS[k];b=CAMERA_KEYS[k+1];t=max(0,min(1,(f-a[0])/(b[0]-a[0])));vals=[]
    for j in [1,2,3]:vals.append(catmull(np.array(CAMERA_KEYS[max(0,k-1)][j]),np.array(a[j]),np.array(b[j]),np.array(CAMERA_KEYS[min(len(CAMERA_KEYS)-1,k+2)][j]),t))
    return vals

def set_camera(f):
    pos,target,lens=camera_values(f);sc=bpy.context.scene;cam=sc.camera;cam.location=pos;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=float(lens);bpy.data.objects['Focus target'].location=target;cam.data.dof.aperture_fstop=5.6 if f<225 or f>400 else 7.1

def load():
    bpy.ops.wm.open_mainfile(filepath=str(OUT/'coffee.blend'));bpy.data.objects['COFFEE / Mantaflow FLIP'].modifiers['Liquid solver'].domain_settings.cache_directory=str(OUT/'cache')

def bake():
    load();o=bpy.data.objects['COFFEE / Mantaflow FLIP'];bpy.context.view_layer.objects.active=o;bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.scene.frame_set(1)
    print('BAKE_DATA_BEGIN',flush=True);bpy.ops.fluid.bake_data();print('BAKE_MESH_BEGIN',flush=True);bpy.ops.fluid.bake_mesh();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'coffee.blend'));print('BAKE_COMPLETE',flush=True)

def render(args,preview=False):
    load();sc=bpy.context.scene;sc.render.engine=args.engine;sc.cycles.samples=args.samples;sc.render.resolution_x=args.width;sc.render.resolution_y=round(args.width*9/16)
    frames=[0,120,168,208,260,336,420,527] if preview else range(args.start,args.end);directory=OUT/('preview' if preview else 'frames');directory.mkdir(exist_ok=True,parents=True)
    if preview:sc.cycles.samples=min(args.samples,20)
    for f in frames:
        sc.frame_set(sim_frame(f));set_camera(f);sc.render.filepath=str(directory/('%05d.png'%f));bpy.ops.render.render(write_still=True);print('FILM_FRAME',f,flush=True)

def export():
    load();sc=bpy.context.scene;sc.frame_set(1);domain=bpy.data.objects['COFFEE / Mantaflow FLIP']
    data={'version':1,'fps':FPS,'frames':FRAMES,'simulationFrames':SIM_END,'cameraKeys':CAMERA_KEYS,'materials':[],'objects':[]};mats={}
    for m in bpy.data.materials:
        if not m.use_nodes:continue
        b=m.node_tree.nodes.get('Principled BSDF')
        if not b:continue
        tx=next((n.image for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image),None);mats[m.name]=len(data['materials'])
        data['materials'].append({'name':m.name,'color':list(b.inputs['Base Color'].default_value[:3]),'roughness':b.inputs['Roughness'].default_value,'metalness':b.inputs['Metallic'].default_value,'coat':b.inputs['Coat Weight'].default_value,'texture':Path(tx.filepath).name if tx else None})
    deps=bpy.context.evaluated_depsgraph_get();buffer=bytearray()
    for ob in sc.objects:
        if ob.type not in ['MESH','CURVE'] or ob.hide_render or ob==domain:continue
        ev=ob.evaluated_get(deps);me=ev.to_mesh();me.calc_loop_triangles();ntri=len(me.loop_triangles)
        if not ntri:ev.to_mesh_clear();continue
        v=[];norm=[];uv=[]
        for tri in me.loop_triangles:
            for li in tri.loops:
                loop=me.loops[li];vert=me.vertices[loop.vertex_index];v.extend(vert.co);norm.extend(vert.normal);uv.extend(me.uv_layers.active.data[li].uv if me.uv_layers.active else (0,0))
        arr=np.concatenate([np.array(v,dtype='<f4'),np.array(norm,dtype='<f4'),np.array(uv,dtype='<f4')]);off=len(buffer);buffer.extend(arr.tobytes())
        data['objects'].append({'name':ob.name,'offset':off,'vertices':ntri*3,'matrix':[x for row in ob.matrix_world for x in row],'material':mats.get(ob.data.materials[0].name,0) if len(ob.data.materials) else 0,'cup':bool(ob.parent and ob.parent.name=='Cup pivot')});ev.to_mesh_clear()
    (ASSETS/'scene.bin').write_bytes(buffer);(ASSETS/'scene.json').write_text(json.dumps(data,separators=(',',':')))
    liquid_dir=ASSETS/'liquid';liquid_dir.mkdir(exist_ok=True);stats=[];transforms=[]
    for frame in range(1,SIM_END+1):
        sc.frame_set(frame);deps=bpy.context.evaluated_depsgraph_get();ev=domain.evaluated_get(deps);me=ev.to_mesh();me.calc_loop_triangles()
        co=np.empty(len(me.vertices)*3,dtype=np.float32);me.vertices.foreach_get('co',co);normal=np.empty(len(me.vertices)*3,dtype=np.float32);me.vertices.foreach_get('normal',normal);idx=np.empty(len(me.loop_triangles)*3,dtype=np.int32);me.loop_triangles.foreach_get('vertices',idx)
        with gzip.open(liquid_dir/('%03d.bin.gz'%frame),'wb',compresslevel=6) as f:f.write(struct.pack('<II',len(me.vertices),len(me.loop_triangles)));f.write(co.astype('<f4').tobytes());f.write(normal.astype('<f4').tobytes());f.write(idx.astype('<u4').tobytes())
        coords=co.reshape(-1,3);world_z=coords[:,2]+domain.location.z if len(coords) else np.array([])
        stats.append({'frame':frame,'vertices':len(me.vertices),'triangles':len(me.loop_triangles),'floorVertices':int(np.count_nonzero(world_z<.025))});cp=bpy.data.objects['Cup pivot'];transforms.append({'position':list(cp.location),'rotation':list(cp.rotation_euler)});ev.to_mesh_clear()
    (ASSETS/'cup.json').write_text(json.dumps(transforms,separators=(',',':')));(ASSETS/'liquid.json').write_text(json.dumps({'matrix':[x for row in domain.matrix_world for x in row],'frames':stats},separators=(',',':')));print('EXPORTED_THREE_SCENE',len(data['objects']),len(buffer),flush=True)

if __name__=='__main__':
    a=argparser()
    if a.mode=='build':make_scene(a.resolution)
    elif a.mode=='bake':bake()
    elif a.mode=='preview':render(a,True)
    elif a.mode=='render':render(a)
    elif a.mode=='export':export()
