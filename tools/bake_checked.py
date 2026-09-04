"""Monitor Mantaflow and reject an upright leakage regression before rendering."""
import gzip,struct,math,subprocess,time,sys,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def upright_check(directory,dx=.006,origin=(-.024,-1.12,-.03)):
    reports=[]
    for frame in [1,10,22]:
        raw=gzip.decompress((directory/f'pp_{frame:04d}.uni').read_bytes())
        count=struct.unpack_from('<i',raw,4)[0]
        active=[]
        for x,y,z,flag in struct.iter_unpack('<fffi',raw[292:292+count*16]):
            if flag==0:active.append((origin[0]+dx*x,origin[1]+dx*y,origin[2]+dx*z))
        if len(active)<2000:raise RuntimeError(f'Insufficient liquid at upright frame {frame}')
        leaked=sum(math.hypot(x-.275,y+.312)>.05 or z<.558 for x,y,z in active)
        highest=max(z for x,y,z in active)
        report={'frame':frame,'activeParticles':len(active),'outsideCup':leaked,'highestZ':highest};reports.append(report)
        if leaked/len(active)>.005:raise RuntimeError(f'Upright leakage regression: {report}')
        if highest<.615:raise RuntimeError(f'Upright liquid collapsed: {report}')
    print('UPRIGHT_CONTAINMENT_PASS',reports,flush=True)
    return reports
if __name__=='__main__':
    blender=os.environ.get('BLENDER','blender');threads=os.environ.get('RENDER_THREADS','4')
    process=subprocess.Popen([blender,'-b','-t',threads,'--python-exit-code','1','--python',str(ROOT/'tools'/'build_scene.py'),'--','--mode','bake'])
    checked=False;directory=ROOT/'render'/'cache'/'data'
    try:
        while process.poll() is None:
            if not checked and (directory/'pp_0024.uni').exists():upright_check(directory);checked=True
            data=len(list(directory.glob('pp_*.uni')));mesh=len(list((ROOT/'render'/'cache'/'mesh').glob('*.bobj.gz')))
            print(f'BAKE_PROGRESS data={data}/288 mesh={mesh}/288',flush=True);time.sleep(20)
        if process.returncode:raise RuntimeError(f'Blender exited {process.returncode}')
        upright_check(directory)
    except BaseException:
        if process.poll() is None:process.terminate();process.wait(timeout=20)
        raise
