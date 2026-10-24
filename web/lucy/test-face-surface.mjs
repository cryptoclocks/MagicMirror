import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import {buildFaceSurface} from './face-surface.js';

test('face stays on curved and box heads at different scales and side angles',()=>{
 for(const shape of ['sphere','animal']){
  const head=new THREE.Group();head.position.set(.1,.84,-.1);head.rotation.set(.1,.7,.1);
  const mesh=new THREE.Mesh(shape==='sphere'?new THREE.SphereGeometry(.285,24,16):new THREE.BoxGeometry(.48,.48,.42),new THREE.MeshBasicMaterial());
  mesh.scale.set(.92,1.08,.93);head.add(mesh);
  for(const scale of [.6,1,1.5]){
   const geometry=buildFaceSurface(head,[mesh],scale),positions=geometry.attributes.position,normals=geometry.attributes.normal;
   assert.ok(positions.count>0);
   for(const yaw of [-1.3,0,1.3]){
    head.rotation.y=yaw;head.updateWorldMatrix(true,true);
    for(let i=0;i<positions.count;i+=3){
     const point=new THREE.Vector3(),normal=new THREE.Vector3();
     for(let j=0;j<3;j++){point.add(new THREE.Vector3().fromBufferAttribute(positions,i+j));normal.add(new THREE.Vector3().fromBufferAttribute(normals,i+j));}
     point.multiplyScalar(1/3).applyMatrix4(head.matrixWorld);normal.normalize().transformDirection(head.matrixWorld);
     const ray=new THREE.Raycaster(point.clone().addScaledVector(normal,.01),normal.clone().negate());
     const hits=ray.intersectObject(mesh,false);
     assert.ok(hits.some(hit=>Math.abs(hit.distance-.01)<.00001),`${shape} scale ${scale} yaw ${yaw} triangle ${i/3} detached`);
    }
   }
   geometry.dispose();
  }
  mesh.geometry.dispose();mesh.material.dispose();
 }
});
