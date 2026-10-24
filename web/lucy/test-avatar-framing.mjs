import test from 'node:test';
import assert from 'node:assert/strict';
import {AvatarFraming} from './avatar-framing.js';
const pose=()=>Array.from({length:33},()=>({x:.5,y:.5,visibility:.95}));
test('framing follows the visible body, waits for stable changes, and holds on loss',()=>{
 const framing=new AvatarFraming(),points=pose();
 points[27].y=1.2;points[28].visibility=.1;
 assert.equal(framing.update(points,0),'half');
 assert.equal(framing.update(points,700),'half');
 points[27].y=.9;points[28].visibility=.95;
 assert.equal(framing.update(points,800),'half');
 assert.equal(framing.update(points,1100),'half');
 assert.equal(framing.update(points,1300),'full');
 assert.equal(framing.update(null,2400),'full');
 points[27].y=1.1;points[28].y=1.1;
 assert.equal(framing.update(points,2500),'full');
 assert.equal(framing.update(points,3000),'half');
});
