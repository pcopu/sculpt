"""Assemble the native frames into a clean 22-second MP4 and validate it."""
import json, subprocess, hashlib, wave
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'public'/'film';OUT.mkdir(parents=True,exist_ok=True)
FPS=24;FRAMES=528;SR=48000;frames=ROOT/'render'/'frames'
missing=[i for i in range(FRAMES) if not (frames/f'{i:05d}.png').is_file()]
if missing:raise RuntimeError(f'Missing film frames: {missing}')
for i in range(FRAMES):
    with Image.open(frames/f'{i:05d}.png') as im:
        if im.size!=(1920,1080):raise RuntimeError(f'Frame {i}: expected native 1920x1080, got {im.size}')
rng=np.random.default_rng(7342);n=22*SR;t=np.arange(n)/SR
room=rng.normal(0,.001,n);audio=np.convolve(room,np.ones(19)/19,mode='same')
def clink(at,amp=.035):
    start=int(at*SR);u=np.arange(min(int(SR*.8),n-start))/SR
    x=sum(np.sin(2*np.pi*freq*u+ph)*w for freq,ph,w in [(1770,0,1),(2450,.4,.55),(3510,1.2,.2),(650,.1,.18)])
    audio[start:start+len(u)]+=amp*x*np.exp(-u*13)*(1-np.exp(-u*400))
clink(5.55,.008);clink(7.6,.04);clink(8.02,.012)
start,end=int(6.1*SR),int(13.6*SR);u=np.arange(end-start)/SR
low=np.convolve(rng.normal(0,1,len(u)),np.ones(9)/9,mode='same')
env=np.minimum(1,u/.5)*np.minimum(1,(u[-1]-u)/1.8)*(.014+.014*np.exp(-((u-1.5)/.65)**2));audio[start:end]+=low*env
for at in [9.5,10.35,11.2,12.0,13.4,14.3,15.1]:
    start=int(at*SR);u=np.arange(int(.16*SR))/SR;freq=850+700*np.exp(-u*35)
    audio[start:start+len(u)]+=np.sin(2*np.pi*np.cumsum(freq)/SR)*np.exp(-u*32)*.008
stereo=np.stack([audio*.96,np.roll(audio,37)*.91],axis=1);stereo*=np.minimum(1,t/.7)[:,None]*np.minimum(1,(22-t)/1.1)[:,None];stereo=np.clip(stereo,-.98,.98)
with wave.open(str(OUT/'original-foley.wav'),'wb') as f:
    f.setnchannels(2);f.setsampwidth(2);f.setframerate(SR);f.writeframes((stereo*32767).astype('<i2').tobytes())
movie=OUT/'last-sip-1080p.mp4'
subprocess.run(['ffmpeg','-hide_banner','-y','-framerate','24','-start_number','0','-i',str(frames/'%05d.png'),'-i',str(OUT/'original-foley.wav'),'-map','0:v','-map','1:a','-vf','scale=out_color_matrix=bt709:out_range=tv,format=yuv420p','-c:v','libx264','-preset','slow','-crf','16','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-t','22','-r','24','-movflags','+faststart','-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709','-metadata','title=The Last Sip','-metadata','comment=Original CG interior and Mantaflow FLIP liquid. 528 native frames at 24 fps.',str(movie)],check=True)
with Image.open(frames/'00168.png') as im:im.save(OUT/'poster.jpg',quality=94)
select=[0,94,144,192,240,300,384,527];sheet=Image.new('RGB',(960,1168),'#171715');d=ImageDraw.Draw(sheet)
for k,f in enumerate(select):
    with Image.open(frames/f'{f:05d}.png') as im:
        x=(k%2)*480;y=(k//2)*292;sheet.paste(im.resize((480,270)),(x,y));d.text((x+8,y+276),f'{f/24:05.2f}s / frame {f:03d}',fill='#eee6d9')
sheet.save(OUT/'contact-sheet.jpg',quality=94)
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(movie)]));v=next(s for s in probe['streams'] if s['codec_type']=='video')
assert (v['width'],v['height'],int(v['nb_frames']),v['r_frame_rate'])==(1920,1080,528,'24/1')
assert abs(float(probe['format']['duration'])-22)<.05
subprocess.run(['ffmpeg','-v','error','-i',str(movie),'-f','null','-'],check=True)
report={'file':movie.name,'durationSeconds':22,'fps':24,'frames':528,'width':1920,'height':1080,'codec':'H.264','pixelFormat':v['pix_fmt'],'audio':'Original stereo synthesis / AAC 48 kHz','sha256':hashlib.sha256(movie.read_bytes()).hexdigest(),'decodeValidation':'passed','renderer':'Blender Cycles','simulation':'Mantaflow FLIP; 288 cached frames; quarter-speed physics','noExternalCreativeAssets':True}
(OUT/'delivery.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
