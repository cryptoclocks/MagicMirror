import test from 'node:test';
import assert from 'node:assert/strict';
import {StudioSession} from './session.js';
const deferred = () => { let resolve,reject; const promise = new Promise((a,b) => {resolve=a;reject=b;}); return {promise,resolve,reject}; };
const track = () => ({stops:0,stop(){this.stops++;}});
test('stop releases the camera immediately and disconnects a late connection',async () => {
  const t=track(),stream={getTracks:()=>[t]},connection=deferred(); let disconnected=0;
  const session=new StudioSession({capture:async()=>stream,connect:()=>connection.promise});
  const pending=session.start(); await Promise.resolve();
  session.stop(); assert.equal(t.stops,1);
  connection.resolve({disconnect(){disconnected++;}});
  assert.equal(await pending,false); assert.equal(disconnected,1); assert.equal(session.client,null);
});
test('permission dialog completing after stop never publishes the camera',async () => {
  const t=track(),captured=deferred();let connects=0;
  const session=new StudioSession({capture:()=>captured.promise,connect:async()=>{connects++;}});
  const pending=session.start();session.stop();captured.resolve({getTracks:()=>[t]});
  assert.equal(await pending,false);assert.equal(connects,0);assert.equal(t.stops,1);
});
test('connection failure releases camera for retry',async () => {
  const t=track();
  const session=new StudioSession({capture:async()=>({getTracks:()=>[t]}),connect:async()=>{throw new Error('offline');}});
  await assert.rejects(session.start(),/offline/); assert.equal(t.stops,1);assert.equal(session.stream,null);
});

import {localStyle} from './local-renderer.js';
test('local mode maps supported Thai and English styles without pretending to generate clothes',()=>{
  for(const [input,expected] of [['ขอภาพอนิเมะ','anime'],['neon','cyberpunk'],['สีน้ำ','watercolor'],['โฮโลแกรม','hologram']]) assert.equal(localStyle(input),expected);
  assert.equal(localStyle('change my shirt to a space suit'),null);
});
