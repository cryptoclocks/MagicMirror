import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {AvatarFraming} from './avatar-framing.js';
const faceOval=[10,338,297,332,284,251,389,356,454,323,361,288,397,365,379,378,400,377,152,148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109];
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const defaults={11:[-.22,.52,0],12:[.22,.52,0],13:[-.35,.23,0],14:[.35,.23,0],15:[-.40,-.02,0],16:[.40,-.02,0],23:[-.13,0,0],24:[.13,0,0],25:[-.14,-.42,0],26:[.14,-.42,0],27:[-.15,-.82,0],28:[.15,-.82,0]};
export class CartoonAvatar {
  constructor(video){
    this.faceScale=1;this.video=video;this.framing=new AvatarFraming();this.animals=new Map();this.character='human';this.disposed=false;
    this.renderer=new THREE.WebGLRenderer({alpha:true,antialias:true,powerPreference:'low-power'});
    this.renderer.setPixelRatio(1);this.renderer.setClearColor(0,0);
    this.scene=new THREE.Scene();this.camera=new THREE.PerspectiveCamera(33,16/9,.1,20);this.camera.position.set(0,.15,4.1);this.camera.lookAt(0,.15,0);
    this.scene.add(new THREE.HemisphereLight(0xffffff,0x64758c,2.5));const light=new THREE.DirectionalLight(0xfff1df,3.2);light.position.set(-2,4,5);this.scene.add(light);
    this.skin=new THREE.MeshToonMaterial({color:'#e5ae88'});this.cloth=new THREE.MeshToonMaterial({color:'#248b87'});this.dark=new THREE.MeshToonMaterial({color:'#263b59'});this.hairMaterial=new THREE.MeshToonMaterial({color:'#2d252b'});this.white=new THREE.MeshToonMaterial({color:'#faf7ec'});this.black=new THREE.MeshToonMaterial({color:'#18222d'});
    const ball=(r,material,parent=this.scene)=>{const mesh=new THREE.Mesh(new THREE.SphereGeometry(r,24,16),material);parent.add(mesh);return mesh;};this.ball=ball;
    this.positions={};this.targets={};for(const [i,p] of Object.entries(defaults)){this.positions[i]=new THREE.Vector3(...p);this.targets[i]=new THREE.Vector3(...p);}
    this.links=[];
    for(const [a,b,r,material] of [[11,13,.085,this.cloth],[12,14,.085,this.cloth],[13,15,.065,this.skin],[14,16,.065,this.skin],[23,25,.10,this.dark],[24,26,.10,this.dark],[25,27,.085,this.dark],[26,28,.085,this.dark]]){
      const mesh=new THREE.Mesh(new THREE.CapsuleGeometry(r,1,6,12),material);this.scene.add(mesh);this.links.push({a,b,r,mesh});
    }
    this.joints=[];for(const i of [11,12,13,14,15,16,25,26])this.joints.push({i,mesh:ball([15,16].includes(i)?.085:.08,[15,16,13,14].includes(i)?this.skin:this.dark)});
    this.body=new THREE.Mesh(new THREE.CylinderGeometry(.23,.18,.50,20),this.cloth);this.scene.add(this.body);
    this.belt=new THREE.Mesh(new THREE.CylinderGeometry(.19,.19,.06,20),this.dark);this.scene.add(this.belt);
    this.feet=[27,28].map(i=>{const mesh=ball(.12,this.white);mesh.scale.set(.9,.55,1.6);return {i,mesh};});
    this.neck=ball(.10,this.skin);this.head=new THREE.Group();this.scene.add(this.head);
    this.skull=ball(.285,this.skin,this.head);this.skull.scale.set(.92,1.08,.93);
    this.hair=ball(.285,this.hairMaterial,this.head);this.hair.scale.set(.94,.56,.94);this.hair.position.set(0,.205,-.025);
    this.nose=ball(.047,this.skin,this.head);this.nose.position.set(0,-.025,.265);
    this.eyes=[];
    for(const x of [-.105,.105]){const eye=ball(.067,this.white,this.head);eye.scale.set(.85,1,.38);eye.position.set(x,.035,.245);const pupil=ball(.030,this.black,eye);pupil.scale.set(1,1,.5);pupil.position.z=.055;this.eyes.push(eye);const brow=new THREE.Mesh(new THREE.CapsuleGeometry(.014,.07,3,8),this.hairMaterial);brow.rotation.z=Math.PI/2;brow.position.set(x,.13,.25);this.head.add(brow);}
    this.mouth=ball(.065,this.black,this.head);this.mouth.position.set(0,-.13,.245);this.mouth.scale.set(1,.2,.25);
    this.hats=new THREE.Group();this.head.add(this.hats);
    this.cap=new THREE.Group();this.hats.add(this.cap);const cap=ball(.29,this.cloth,this.cap);cap.scale.set(1,.48,1);cap.position.y=.25;const brim=new THREE.Mesh(new THREE.CylinderGeometry(.24,.24,.025,24),this.cloth);brim.scale.set(1,1,.75);brim.position.set(0,.21,.18);this.cap.add(brim);
    this.crown=new THREE.Group();this.hats.add(this.crown);const gold=new THREE.MeshToonMaterial({color:'#eebd4d'});const band=new THREE.Mesh(new THREE.CylinderGeometry(.22,.23,.12,16,true),gold);band.position.y=.30;this.crown.add(band);for(let i=0;i<5;i++){const tooth=new THREE.Mesh(new THREE.ConeGeometry(.065,.18,4),gold);const a=i*Math.PI*2/5;tooth.position.set(Math.sin(a)*.205,.43,Math.cos(a)*.205);this.crown.add(tooth);}
    this.hats.traverse(node=>node.layers.set(1));
    this.scene.traverse(node=>{if(node.isLight)node.layers.enable(1);});
    this.faceCanvas=document.createElement('canvas');this.faceCanvas.width=this.faceCanvas.height=512;
    this.faceTexture=new THREE.CanvasTexture(this.faceCanvas);this.faceTexture.colorSpace=THREE.SRGBColorSpace;
    this.faceGeometry=new THREE.BufferGeometry();this.faceGeometry.setAttribute('position',new THREE.BufferAttribute(new Float32Array((faceOval.length+1)*3),3));this.faceGeometry.setAttribute('uv',new THREE.BufferAttribute(new Float32Array((faceOval.length+1)*2),2));
    const indices=[];for(let i=0;i<faceOval.length;i++)indices.push(0,i+1,(i+1)%faceOval.length+1);this.faceGeometry.setIndex(indices);
    this.realFace=new THREE.Mesh(this.faceGeometry,new THREE.MeshBasicMaterial({map:this.faceTexture,side:THREE.DoubleSide,transparent:true}));this.realFace.visible=false;this.realFace.frustumCulled=false;this.head.add(this.realFace);
    this.cartoonFeatures=this.head.children.filter(n=>n!==this.hats&&n!==this.skull&&n!==this.hair&&n!==this.realFace);
    this.robot=false;this.setHat('none');this.rotation=new THREE.Vector3();this.targetRotation=new THREE.Vector3();this.expression={jaw:0,left:0,right:0,smile:0};this.last=0;this.lastTracking=-10000;this.lastPoseTracking=-10000;
  }
  setHat(value){this.cap.visible=value==='cap';this.crown.visible=value==='crown';}
  setOutfit(color){this.cloth.color.set(color);}
  setFaceScale(value){this.faceScale=Number.isFinite(value)?clamp(value,.6,1.5):1;this.realFace.scale.set(this.faceScale,this.faceScale,1);this.hats.scale.setScalar(this.faceScale);}
  setOwnFace(value){this.ownFace=!!value;if(!value)this.realFace.visible=false;this.refreshHead();}
  refreshHead(){
    const animal=!['human','robot'].includes(this.character),real=this.realFace.visible;
    for(const feature of this.cartoonFeatures)feature.visible=!animal&&!real;
    this.nose.visible=!animal&&!real&&!this.robot;this.skull.visible=!animal;this.hair.visible=!animal&&!this.robot;
    for(const [name,group] of this.animals)group.visible=name===this.character;
  }
  async setCharacter(value){
    this.character=value;this.robot=value==='robot';this.skin.color.set(this.robot?'#a8ccd5':'#e5ae88');this.refreshHead();
    if(['human','robot'].includes(value)||this.animals.has(value))return;
    if(!['cat','dog','bunny','fox','panda'].includes(value))return;
    try{
      const gltf=await new GLTFLoader().loadAsync(new URL('animals/'+value+'.glb',location.href).href);
      const root=gltf.scene;
      root.traverse(node=>{if(/^(leg|tail)/.test(node.name))node.visible=false;});
      const box=new THREE.Box3().setFromObject(root),size=box.getSize(new THREE.Vector3()),center=box.getCenter(new THREE.Vector3());
      // Cube Pets' face and ears form a mascot head; legs are replaced by tracked limbs.
      const scale=.65/Math.max(size.x,size.y,size.z);root.scale.setScalar(scale);root.position.copy(center).multiplyScalar(-scale);
      const group=new THREE.Group();group.add(root);
      if(this.disposed||this.animals.has(value)){root.traverse(n=>{n.geometry?.dispose();for(const m of [].concat(n.material||[])){m.map?.dispose();m.dispose();}});return;}
      this.animals.set(value,group);this.head.add(group);this.refreshHead();
    }catch{if(!this.disposed&&this.character===value){this.character='human';this.refreshHead();}}
  }
  updateFaceTexture(now){
    const face=this.faceLandmarks;
    this.realFace.visible=!!(this.ownFace&&face&&now-this.lastTracking<350&&this.video?.readyState>=2);
    this.refreshHead();if(!this.realFace.visible)return;
    const ctx=this.faceCanvas.getContext('2d');ctx.drawImage(this.video,0,0,512,512);this.faceTexture.needsUpdate=true;
    const contour=faceOval.map(i=>face[i]),xs=contour.map(p=>p.x),ys=contour.map(p=>p.y),cx=(Math.min(...xs)+Math.max(...xs))/2,cy=(Math.min(...ys)+Math.max(...ys))/2;
    const width=Math.max(.03,Math.max(...xs)-Math.min(...xs)),height=Math.max(.03,Math.max(...ys)-Math.min(...ys));
    const vertices=[{x:cx,y:cy},...contour],positions=this.faceGeometry.attributes.position,uv=this.faceGeometry.attributes.uv;
    vertices.forEach((p,i)=>{const x=(cx-p.x)/width*.51,y=(cy-p.y)/height*.57;positions.setXYZ(i,x,y,(['human','robot'].includes(this.character)?.295:.38)+Math.max(0,1-(x/.27)**2-(y/.30)**2)*.035);uv.setXY(i,p.x,1-p.y);});
    positions.needsUpdate=uv.needsUpdate=true;
  }
  update(data,now){
    this.framing.update(data.landmarks,now);
    if(data.world){this.lastPoseTracking=now;for(const [id,fallback] of Object.entries(defaults)){const p=data.world[id],visible=data.landmarks?.[id]?.visibility??0;if(p&&visible>.45)this.targets[id].set(clamp(-p.x,-1.2,1.2),clamp(-p.y,-1.2,1.2),clamp(-p.z,-.6,.6));else this.targets[id].set(...fallback);}}
    else if(now-this.lastPoseTracking>400)for(const [id,p] of Object.entries(defaults))this.targets[id].set(...p);
    const f=data.face;
    if(f){this.faceLandmarks=f;const left=f[33],right=f[263],nose=f[1];const dx=right.x-left.x,dy=right.y-left.y,width=Math.max(.03,Math.hypot(dx,dy));this.targetRotation.set(clamp(((nose.y-(left.y+right.y)/2)/width-.45)*1.1,-.4,.4),clamp(-(nose.x-(left.x+right.x)/2)/width*2,-.8,.8),clamp(Math.atan2(dy,dx),-.6,.6));const blend=Object.fromEntries(data.blendshapes.map(b=>[b.categoryName,b.score]));this.expression={jaw:blend.jawOpen||0,left:blend.eyeBlinkLeft||0,right:blend.eyeBlinkRight||0,smile:((blend.mouthSmileLeft||0)+(blend.mouthSmileRight||0))/2};this.lastTracking=now;}
  }
  render(w,h,now){
    if(this.renderer.domElement.width!==w||this.renderer.domElement.height!==h){this.renderer.setSize(w,h,false);this.camera.aspect=w/h;this.camera.updateProjectionMatrix();}
    const dt=this.last?Math.min(.1,(now-this.last)/1000):.016;this.last=now;const alpha=1-Math.exp(-dt/.07);
    for(const id of Object.keys(defaults))this.positions[id].lerp(this.targets[id],alpha);
    const shoulders=this.positions[11].clone().add(this.positions[12]).multiplyScalar(.5),hips=this.positions[23].clone().add(this.positions[24]).multiplyScalar(.5);
    for(const {a,b,r,mesh} of this.links){const direction=this.positions[b].clone().sub(this.positions[a]);mesh.position.copy(this.positions[a]).add(this.positions[b]).multiplyScalar(.5);mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),direction.clone().normalize());mesh.scale.set(1,Math.max(.03,direction.length())/(1+2*r),1);}
    for(const {i,mesh} of this.joints)mesh.position.copy(this.positions[i]);
    this.body.position.copy(shoulders).add(hips).multiplyScalar(.5);this.body.scale.y=shoulders.distanceTo(hips)/.50;this.body.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),shoulders.clone().sub(hips).normalize());
    this.belt.position.copy(hips);for(const {i,mesh} of this.feet){mesh.position.copy(this.positions[i]);mesh.position.z+=.06;}
    this.neck.position.copy(shoulders).add(new THREE.Vector3(0,.08,0));this.head.position.copy(shoulders).add(new THREE.Vector3(0,.32,0));
    if(now-this.lastTracking>500){this.targetRotation.set(0,0,0);this.expression={jaw:0,left:0,right:0,smile:0};}
    this.rotation.lerp(this.targetRotation,alpha);this.head.rotation.set(this.rotation.x,this.rotation.y,this.rotation.z);
    this.eyes[0].scale.y=Math.max(.10,1-this.expression.left*.95);this.eyes[1].scale.y=Math.max(.10,1-this.expression.right*.95);this.mouth.scale.y=.13+this.expression.jaw*1.4;this.mouth.scale.x=1+this.expression.smile*.5;
    const half=this.framing.mode==='half',extra=Math.max(0,this.faceScale-1),targetY=half?.56:.15+extra*.12,targetZ=(half?2.9:4.1)+extra*1.5;
    const frameAlpha=1-Math.exp(-dt/.24);this.camera.position.y+=(targetY-this.camera.position.y)*frameAlpha;this.camera.position.z+=(targetZ-this.camera.position.z)*frameAlpha;this.camera.lookAt(0,this.camera.position.y,0);
    this.updateFaceTexture(now);
    this.renderer.render(this.scene,this.camera);
    // Draw hats after the face/body, with their own depth buffer for correct hat geometry.
    if(this.cap.visible||this.crown.visible){this.renderer.autoClear=false;this.renderer.clearDepth();this.camera.layers.set(1);this.renderer.render(this.scene,this.camera);this.camera.layers.set(0);this.renderer.autoClear=true;}
    return this.renderer.domElement;
  }
  dispose(){this.disposed=true;this.faceTexture.dispose();const materials=new Set();this.scene.traverse(node=>{node.geometry?.dispose();if(node.material)materials.add(node.material);});for(const material of materials){material.map?.dispose();material.dispose();}this.renderer.dispose();this.renderer.forceContextLoss();}
}
