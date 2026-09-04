export const FPS=24,FRAMES=528,DURATION=22,SIM_FRAMES=288;
export const simFrame=f=>Math.max(1,Math.min(SIM_FRAMES,Math.floor(f)-95));
export const keys=[[0,[1.43,-1.65,1.16],[.05,-.13,.51],49],[94,[.72,-.94,.84],[.27,-.32,.588],59],[174,[.63,-.93,.78],[.28,-.37,.568],60],[240,[.62,-1,.61],[.29,-.48,.385],55],[316,[.67,-1.14,.36],[.28,-.68,.074],54],[384,[.79,-1.22,.40],[.28,-.68,.083],52],[527,[1.42,-1.84,1.13],[.12,-.26,.35],47]];
const cat=(a,b,c,d,t)=>.5*(2*b+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t);
export function cameraAt(frame){const f=Math.max(0,Math.min(FRAMES-1,frame));let k=0;while(k<keys.length-2&&f>keys[k+1][0])k++;const t=(f-keys[k][0])/(keys[k+1][0]-keys[k][0]);const p=[keys[Math.max(0,k-1)],keys[k],keys[k+1],keys[Math.min(keys.length-1,k+2)]];return {position:[0,1,2].map(i=>cat(...p.map(x=>x[1][i]),t)),target:[0,1,2].map(i=>cat(...p.map(x=>x[2][i]),t)),lens:cat(...p.map(x=>x[3]),t)};}
// Fallback only. Playback uses exact evaluated Blender transforms from cup.json.
export function cupAt(sim){const k=[[1,0],[22,0],[34,.075],[48,.32],[64,.83],[80,1.42],[88,1.57],[98,1.50],[112,1.535],[130,1.525],[288,1.525]];let i=0;while(i<k.length-2&&sim>k[i+1][0])i++;let t=Math.max(0,Math.min(1,(sim-k[i][0])/(k[i+1][0]-k[i][0])));t=t*t*(3-2*t);const angle=k[i][1]+(k[i+1][1]-k[i][1])*t;return {angle,z:.546+.012*Math.sin(angle)};}
