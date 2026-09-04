import * as THREE from '../public/vendor/three.module.js';
import {FPS,FRAMES,simFrame,cameraAt,cupAt} from './timeline.mjs';
const $=s=>document.querySelector(s),assets=new URL('../public/assets/',import.meta.url);
const status=$('#status'),video=$('#film'),slider=$('#scrub'),play=$('#play'),sceneHost=$('#scene');
let mode='film',playing=false,frame=0,busy=false,last=0,initialized=false;
let renderer,scene,camera,stage,cup,liquid,exactCup=[],orbit=false,orbitStart=null;
const cache=new Map(),pending=new Map();
const rowMatrix=a=>new THREE.Matrix4().fromArray(a).transpose();
const xyz=a=>new THREE.Vector3(a[0],a[2],-a[1]);
async function getJSON(path){const r=await fetch(new URL(path,assets));if(!r.ok)throw Error(`${path}: HTTP ${r.status}`);return r.json();}
function updateHUD(){slider.value=frame;$('#time').textContent=`${(frame/FPS).toFixed(2).padStart(5,'0')} / 22.00`;play.textContent=playing?'Pause':'Play';}
async function initialize(){
 if(initialized)return;
 status.textContent='Loading the original 3D scene…';
 const [data,meta,raw,cupData]=await Promise.all([getJSON('scene.json'),getJSON('liquid.json'),fetch(new URL('scene.bin',assets)).then(r=>{if(!r.ok)throw Error('Scene binary unavailable');return r.arrayBuffer();}),getJSON('cup.json')]);
 exactCup=cupData;
 renderer=new THREE.WebGLRenderer({antialias:true,alpha:false,preserveDrawingBuffer:true,powerPreference:'high-performance'});
 renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.setSize(innerWidth,innerHeight);
 renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.2;renderer.outputColorSpace=THREE.SRGBColorSpace;
 renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;sceneHost.appendChild(renderer.domElement);
 scene=new THREE.Scene();scene.background=new THREE.Color('#ada292');stage=new THREE.Group();stage.rotation.x=-Math.PI/2;scene.add(stage);
 camera=new THREE.PerspectiveCamera(40,innerWidth/innerHeight,.012,100);camera.filmGauge=36;
 const textures=new THREE.TextureLoader(),loads=[];
 const mats=data.materials.map(m=>{
  const mat=new THREE.MeshPhysicalMaterial({color:new THREE.Color(...m.color),roughness:m.roughness,metalness:m.metalness,clearcoat:m.coat,clearcoatRoughness:.15});
  if(m.texture){loads.push(textures.loadAsync(new URL(m.texture,assets).href).then(tx=>{tx.colorSpace=THREE.SRGBColorSpace;tx.anisotropy=8;mat.map=tx;mat.color.setRGB(1,1,1);mat.bumpMap=tx;mat.bumpScale=.0006;mat.needsUpdate=true;}));}
  return mat;
 });
 await Promise.all(loads);
 cup=new THREE.Group();cup.position.fromArray(cupData[0].position);cup.rotation.set(...cupData[0].rotation);cup.updateMatrix();stage.add(cup);
 const invPivot=cup.matrix.clone().invert();
 for(const obj of data.objects){
  const g=new THREE.BufferGeometry(),n=obj.vertices;
  g.setAttribute('position',new THREE.BufferAttribute(new Float32Array(raw,obj.offset,n*3),3));g.setAttribute('normal',new THREE.BufferAttribute(new Float32Array(raw,obj.offset+n*12,n*3),3));g.setAttribute('uv',new THREE.BufferAttribute(new Float32Array(raw,obj.offset+n*24,n*2),2));
  const mesh=new THREE.Mesh(g,mats[obj.material]);mesh.name=obj.name;mesh.castShadow=true;mesh.receiveShadow=true;
  const matrix=rowMatrix(obj.matrix);if(obj.cup){matrix.premultiply(invPivot);cup.add(mesh);}else stage.add(mesh);matrix.decompose(mesh.position,mesh.quaternion,mesh.scale);
 }
 scene.add(new THREE.HemisphereLight(0xd4e5ff,0x47311a,1));
 const sun=new THREE.DirectionalLight(0xffdbab,3.2);sun.position.set(-3,5,1.5);sun.target.position.set(.2,.3,.3);sun.castShadow=true;
 Object.assign(sun.shadow.camera,{left:-2,right:2,top:2,bottom:-2,near:.1,far:12});sun.shadow.mapSize.set(2048,2048);sun.shadow.normalBias=.003;sun.shadow.bias=-.0002;scene.add(sun,sun.target);
 const fill=new THREE.DirectionalLight(0xbcd4ff,.9);fill.position.set(2,3,2);scene.add(fill);
 const practical=new THREE.PointLight(0xffb76b,8,4,2);practical.position.copy(xyz([-1.53,1.22,1.38]));scene.add(practical);
 const reflection=new THREE.WebGLCubeRenderTarget(128,{type:THREE.HalfFloatType});const capture=new THREE.CubeCamera(.03,15,reflection);capture.position.copy(xyz([.275,-.312,.65]));scene.add(capture);cup.visible=false;capture.update(renderer,scene);cup.visible=true;scene.environment=reflection.texture;
 liquid=new THREE.Mesh(new THREE.BufferGeometry(),new THREE.MeshPhysicalMaterial({color:0x321207,roughness:.13,metalness:0,clearcoat:.8,clearcoatRoughness:.08,ior:1.333,transmission:.17,thickness:.02,attenuationColor:new THREE.Color('#843c12'),attenuationDistance:.06}));
 rowMatrix(meta.matrix).decompose(liquid.position,liquid.quaternion,liquid.scale);liquid.castShadow=true;liquid.receiveShadow=true;stage.add(liquid);
 initialized=true;
 await draw(frame);
 window.sculpt={ready:true,renderAt:async f=>{playing=false;orbit=false;await draw(f);return true;},resize:(w,h)=>{renderer.setPixelRatio(1);renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();},renderer};
 status.textContent='Original scene · baked FLIP liquid';
 renderer.domElement.addEventListener('pointerdown',e=>{if(!orbit)return;orbitStart=[e.clientX,e.clientY];renderer.domElement.setPointerCapture(e.pointerId);});
 renderer.domElement.addEventListener('pointermove',e=>{if(!orbitStart||!orbit)return;const dx=(e.clientX-orbitStart[0])*.006,dy=(e.clientY-orbitStart[1])*.006;orbitStart=[e.clientX,e.clientY];const target=xyz([.25,-.45,.35]);const offset=camera.position.clone().sub(target);const s=new THREE.Spherical().setFromVector3(offset);s.theta-=dx;s.phi=Math.max(.08,Math.min(1.55,s.phi+dy));camera.position.copy(new THREE.Vector3().setFromSpherical(s).add(target));camera.lookAt(target);renderer.render(scene,camera);});
 renderer.domElement.addEventListener('pointerup',()=>orbitStart=null);
 renderer.domElement.addEventListener('wheel',e=>{if(!orbit)return;e.preventDefault();const target=xyz([.25,-.45,.35]);camera.position.sub(target).multiplyScalar(Math.exp(e.deltaY*.001)).add(target);renderer.render(scene,camera);},{passive:false});
}
async function liquidFrame(f){
 if(cache.has(f))return cache.get(f);if(pending.has(f))return pending.get(f);
 const promise=(async()=>{
  const res=await fetch(new URL(`liquid/${String(f).padStart(3,'0')}.bin.gz`,assets));if(!res.ok)throw Error(`Liquid frame ${f} unavailable`);
  const zipped=await res.arrayBuffer();let data;
  if(new Uint8Array(zipped)[0]===31){data=await new Response(new Blob([zipped]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();}else data=zipped;
  const header=new DataView(data),n=header.getUint32(0,true),tri=header.getUint32(4,true);
  if(data.byteLength!==8+n*24+tri*12)throw Error(`Corrupt liquid frame ${f}`);
  const geom=new THREE.BufferGeometry();geom.setAttribute('position',new THREE.BufferAttribute(new Float32Array(data,8,n*3),3));geom.setAttribute('normal',new THREE.BufferAttribute(new Float32Array(data,8+n*12,n*3),3));geom.setIndex(new THREE.BufferAttribute(new Uint32Array(data,8+n*24,tri*3),1));geom.computeBoundingSphere();cache.set(f,geom);pending.delete(f);
  while(cache.size>48){const oldest=cache.keys().next().value;if(oldest===f)break;const old=cache.get(oldest);if(old!==liquid?.geometry)old.dispose();cache.delete(oldest);}
  return geom;
 })();pending.set(f,promise);promise.catch(()=>pending.delete(f));return promise;
}
async function draw(f){
 frame=Math.max(0,Math.min(FRAMES-1,f));const sim=simFrame(frame);liquid.geometry=await liquidFrame(sim);
 const transform=exactCup[sim-1];if(transform){cup.position.fromArray(transform.position);cup.rotation.fromArray([...transform.rotation,'XYZ']);}else{const c=cupAt(sim);cup.rotation.x=c.angle;cup.position.z=c.z;}
 if(!orbit){const c=cameraAt(frame);camera.position.copy(xyz(c.position));camera.lookAt(xyz(c.target));camera.setFocalLength(c.lens);}
 renderer.render(scene,camera);updateHUD();for(let i=1;i<=3;i++)if(sim+i<=288)liquidFrame(sim+i).catch(()=>{});
}
async function tick(t){
 requestAnimationFrame(tick);
 if(mode==='film'){if(playing){frame=Math.min(FRAMES-1,video.currentTime*FPS);updateHUD();}return;}
 if(!initialized||!playing||busy||t-last<1000/FPS)return;last=t;busy=true;
 try{await draw(frame+1);if(frame>=FRAMES-1){playing=false;updateHUD();}}catch(e){status.textContent=e.message;playing=false;}finally{busy=false;}
}
play.onclick=async()=>{try{if(mode==='film'){if(video.ended)video.currentTime=0;playing=!playing;if(playing)await video.play();else video.pause();}else{if(frame>=FRAMES-1)frame=0;playing=!playing;}updateHUD();}catch(e){playing=false;status.textContent=e.message;updateHUD();}};
slider.oninput=async()=>{frame=Number(slider.value);if(mode==='film')video.currentTime=frame/FPS;else if(initialized)await draw(frame);updateHUD();};
video.onended=()=>{playing=false;updateHUD();};video.onloadedmetadata=()=>{status.textContent='Final film · 1920 × 1080 · 24 fps';};
$('#mode').onclick=async()=>{playing=false;video.pause();mode=mode==='film'?'scene':'film';document.body.dataset.mode=mode;$('#mode').textContent=mode==='film'?'Explore 3D scene':'Watch final film';$('#orbit').hidden=mode==='film';updateHUD();if(mode==='scene'){try{await initialize();}catch(e){status.textContent=`Scene loading failed: ${e.message}`;}}else{video.currentTime=frame/FPS;status.textContent='Final film · 1920 × 1080 · 24 fps';}};
$('#orbit').onclick=()=>{orbit=!orbit;playing=false;$('#orbit').textContent=orbit?'Return to film camera':'Orbit scene';if(!orbit)draw(frame);updateHUD();};
$('#fullscreen').onclick=()=>{if(document.fullscreenElement)document.exitFullscreen();else document.documentElement.requestFullscreen();};
addEventListener('resize',()=>{if(renderer){renderer.setSize(innerWidth,innerHeight);camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();renderer.render(scene,camera);}});
addEventListener('keydown',e=>{if(e.code==='Space'&&e.target.tagName!=='INPUT'){e.preventDefault();play.click();}});
if(new URLSearchParams(location.search).has('capture')){$('#mode').click();document.body.classList.add('capture');}
requestAnimationFrame(tick);updateHUD();
