"""Derive persistent wood wetness from actual solver contacts.
The masks are material wetness, not replacement liquid geometry. Reconstruct at
6 mm solver-cell scale before upsampling so particle samples do not print dots.
"""
from pathlib import Path
import argparse,gzip,struct,json
import numpy as np
from PIL import Image,ImageFilter

def main():
    root=Path(__file__).resolve().parents[1]
    p=argparse.ArgumentParser();p.add_argument('--cache',type=Path,default=root/'render/cache');p.add_argument('--out',type=Path,default=root/'public/assets/wetness');p.add_argument('--origin',type=float,nargs=3,default=[-.024,-1.12,-.03]);p.add_argument('--size',type=float,nargs=2,default=[1.20,.96]);p.add_argument('--frames',type=int,default=288);p.add_argument('--resolution',type=int,default=512);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True);n=a.resolution;origin=np.array(a.origin);extent=np.array(a.size)
    grid=np.rint(extent/.006).astype(int);width,height=int(grid[0]),int(grid[1]);target=tuple(np.rint(extent/max(extent)*n).astype(int))
    floor=np.zeros((height,width),dtype=np.uint8);table=floor.copy()
    for f in range(1,a.frames+1):
        raw=gzip.decompress((a.cache/'data'/f'pp_{f:04d}.uni').read_bytes());count=struct.unpack_from('<i',raw,4)[0]
        if raw[:4]!=b'PB02' or len(raw)<292+count*16:raise RuntimeError(f'Invalid particle cache at frame {f}')
        particles=np.frombuffer(raw,offset=292,count=count,dtype=[('p','<f4',(3,)),('flag','<i4')]);co=particles['p'][particles['flag']==0]*.006+origin
        floor_pts=co[(co[:,2]>=-.01)&(co[:,2]<.009)]
        table_pts=co[(co[:,2]>.540)&(co[:,2]<.556)&(np.abs(co[:,0])<.714)&(co[:,1]>-.444)&(co[:,1]<.444)]
        for name,mask,points in [('floor',floor,floor_pts),('table',table,table_pts)]:
            uv=(points[:,:2]-origin[:2])/extent
            ij=np.floor(uv*grid).astype(np.int32);valid=(ij[:,0]>=0)&(ij[:,0]<width)&(ij[:,1]>=0)&(ij[:,1]<height);ij=ij[valid]
            mask[height-1-ij[:,1],ij[:,0]]=255
            image=Image.fromarray(mask).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(.8)).resize(target,Image.Resampling.BICUBIC)
            image.save(a.out/f'{name}_{f:04d}.png',optimize=True)
    (a.out/'wetness.json').write_text(json.dumps({'schema':2,'frames':a.frames,'origin':a.origin[:2],'size':a.size,'resolution':n,'source':'Cumulative floor and tabletop contacts from Mantaflow particles','reconstruction':'6 mm cells, morphological closing and subcell filtering','notLiquidGeometry':True},indent=2)+'\n')
    print('CONTACT_WETMAPS_COMPLETE',a.frames*2)
if __name__=='__main__':main()
