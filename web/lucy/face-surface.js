import * as THREE from 'three';
import {DecalGeometry} from 'three/addons/geometries/DecalGeometry.js';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';

// Project onto existing triangles, then store vertices in head coordinates.
// Moving, rotating or resizing the face must never create a second floating plane.
export function buildFaceSurface(head,meshes,scale,animal=false){
  head.updateWorldMatrix(true,true);
  if(!meshes.length)return new THREE.BufferGeometry();
  const inverse=head.matrixWorld.clone().invert(),localBox=new THREE.Box3();
  for(const mesh of meshes){
    mesh.geometry.computeBoundingBox();
    localBox.union(mesh.geometry.boundingBox.clone().applyMatrix4(inverse.clone().multiply(mesh.matrixWorld)));
  }
  const depth=localBox.max.z-localBox.min.z;
  const worldCenter=new THREE.Vector3(0,animal?-.07:0,localBox.max.z).applyMatrix4(head.matrixWorld);
  const rotation=new THREE.Euler().setFromRotationMatrix(new THREE.Matrix4().extractRotation(head.matrixWorld));
  const size=new THREE.Vector3((animal?.48:.51)*scale,(animal?.40:.57)*scale,Math.max(.1,depth*1.05));
  const parts=[];
  for(const mesh of meshes){
    const part=new DecalGeometry(mesh,worldCenter,rotation,size).applyMatrix4(inverse);
    if(part.attributes.position.count)parts.push(part);else part.dispose();
  }
  const geometry=parts.length?mergeGeometries(parts):new THREE.BufferGeometry();
  for(const part of parts)part.dispose();
  return geometry;
}
