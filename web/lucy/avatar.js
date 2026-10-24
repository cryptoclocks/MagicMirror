import * as THREE from 'three';
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const defaults={11:[-.22,.52,0],12:[.22,.52,0],13:[-.35,.23,0],14:[.35,.23,0],15:[-.40,-.02,0],16:[.40,-.02,0],23:[-.13,0,0],24:[.13,0,0],25:[-.14,-.42,0],26:[.14,-.42,0],27:[-.15,-.82,0],28:[.15,-.82,0]};
export class CartoonAvatar {
  constructor(){
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
    this.robot=false;this.setHat('none');this.rotation=new THREE.Vector3();this.targetRotation=new THREE.Vector3();this.expression={jaw:0,left:0,right:0,smile:0};this.last=0;this.lastTracking=-10000;this.lastPoseTracking=-10000;
  }
  setHat(value){this.cap.visible=value==='cap';this.crown.visible=value==='crown';}
  setOutfit(color){this.cloth.color.set(color);}
  setCharacter(value){this.robot=value==='robot';this.skin.color.set(this.robot?'#a8ccd5':'#e5ae88');this.hair.visible=!this.robot;this.nose.visible=!this.robot;}
  update(data,now){
    if(data.world){this.lastPoseTracking=now;for(const [id,fallback] of Object.entries(defaults)){const p=data.world[id],visible=data.landmarks?.[id]?.visibility??0;if(p&&visible>.45)this.targets[id].set(clamp(-p.x,-1.2,1.2),clamp(-p.y,-1.2,1.2),clamp(-p.z,-.6,.6));else this.targets[id].set(...fallback);}}
    else if(now-this.lastPoseTracking>400)for(const [id,p] of Object.entries(defaults))this.targets[id].set(...p);
    const f=data.face;
    if(f){const left=f[33],right=f[263],nose=f[1];const dx=right.x-left.x,dy=right.y-left.y,width=Math.max(.03,Math.hypot(dx,dy));this.targetRotation.set(clamp(((nose.y-(left.y+right.y)/2)/width-.45)*1.1,-.4,.4),clamp(-(nose.x-(left.x+right.x)/2)/width*2,-.8,.8),clamp(Math.atan2(dy,dx),-.6,.6));const blend=Object.fromEntries(data.blendshapes.map(b=>[b.categoryName,b.score]));this.expression={jaw:blend.jawOpen||0,left:blend.eyeBlinkLeft||0,right:blend.eyeBlinkRight||0,smile:((blend.mouthSmileLeft||0)+(blend.mouthSmileRight||0))/2};this.lastTracking=now;}
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
    this.renderer.render(this.scene,this.camera);return this.renderer.domElement;
  }
  dispose(){const materials=new Set();this.scene.traverse(node=>{node.geometry?.dispose();if(node.material)materials.add(node.material);});for(const material of materials)material.dispose();this.renderer.dispose();this.renderer.forceContextLoss();}
}
