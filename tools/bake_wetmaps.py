"""Derive persistent surface wetting from actual solver particle contacts.
These are material wetness masks, not replacement liquid geometry.
"""
from pathlib import Path
import argparse,gzip,struct,json
import numpy as np
from PIL import Image,ImageFilter

def main():
    root=Path(__file__).resolve().parents[1]
    p=argparse.ArgumentParser();p.add_argument('--cache',type=Path,default=root/'render/cache');p.add_argument('--out',type=Path,default=root/'public/assets/wetness');p.add_argument('--origin',type=float,nargs=3,default=[-.024,-1.12,-.03]);p.add_argument('--size',type=float,nargs=2,default=[.94,.96]);p.add_argument('--frames',type=int,default=288);p.add_argument('--resolution',type=int,default=512);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True);n=a.resolution;origin=np.array(a.origin);extent=np.array(a.size)
    floor=np.zeros((n,n),dtype=np.uint8);table=floor.copy()
    for f in range(1,a.frames+1):
        raw=gzip.decompress((a.cache/'data'/f'pp_{f:04d}.uni').read_bytes());count=struct.unpack_from('<i',raw,4)[0]
        particles=np.frombuffer(raw,offset=292,count=count,dtype=[('p','<f4',(3,)),('flag','<i4')]);co=particles['p'][particles['flag']==0]*.006+origin
        floor_pts=co[(co[:,2]>=-.01)&(co[:,2]<.009)]
        table_pts=co[(co[:,2]>.540)&(co[:,2]<.556)&(np.abs(co[:,0])<.714)&(co[:,1]>-.444)&(co[:,1]<.444)]
        for name,mask,points in [('floor',floor,floor_pts),('table',table,table_pts)]:
            uv=(points[:,:2]-origin[:2])/extent
            ij=np.floor(uv*n).astype(np.int32);valid=(ij[:,0]>=0)&(ij[:,0]<n)&(ij[:,1]>=0)&(ij[:,1]<n);ij=ij[valid]
            mask[n-1-ij[:,1],ij[:,0]]=255
            image=Image.fromarray(mask).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(1.3))
            image.save(a.out/f'{name}_{f:04d}.png',optimize=True)
    (a.out/'wetness.json').write_text(json.dumps({'schema':1,'frames':a.frames,'origin':a.origin[:2],'size':a.size,'resolution':n,'source':'Cumulative floor and tabletop contacts from Mantaflow particles','notLiquidGeometry':True},indent=2)+'\n')
    print('CONTACT_WETMAPS_COMPLETE',a.frames*2)
if __name__=='__main__':main()
