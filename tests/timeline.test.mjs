import test from 'node:test';import assert from 'node:assert/strict';import {FPS,FRAMES,DURATION,simFrame,cameraAt,cupAt,keys} from '../src/timeline.mjs';
test('exactly 22 seconds at 24 fps',()=>assert.equal(FRAMES/FPS,DURATION));
test('simulation bounded through anticipation and aftermath',()=>{assert.equal(simFrame(0),1);assert.equal(simFrame(96),1);assert.equal(simFrame(383),288);assert.equal(simFrame(527),288);});
test('all camera samples finite',()=>{for(let f=0;f<FRAMES;f++){const c=cameraAt(f);assert.ok([...c.position,...c.target,c.lens].every(Number.isFinite));assert.ok(c.lens>20);}});
test('camera passes through authored keys',()=>{for(const k of keys){const c=cameraAt(k[0]);for(let i=0;i<3;i++)assert.ok(Math.abs(c.position[i]-k[1][i])<1e-7);}});
test('cup starts upright and ends resting on its side',()=>{assert.equal(cupAt(1).angle,0);assert.ok(cupAt(288).angle>1.5);});
