import {CartoonAvatar} from './avatar.js';
import {drawBackground} from './backgrounds.js';
export class TrackingMirror {
  constructor({video,canvas,mode,onStatus=()=>{},onMetrics=()=>{},onError=()=>{}}){
    Object.assign(this,{video,canvas,mode,onStatus,onMetrics,onError,disposed:false,ready:false,pending:false,lastFrame:-1,lastSubmit:0,maskStamp:0,scene:'studio',custom:null,previousMask:null});
    this.context=canvas.getContext('2d');this.mask=document.createElement('canvas');this.maskContext=this.mask.getContext('2d');
    this.person=document.createElement('canvas');this.personContext=this.person.getContext('2d');this.backdrop=document.createElement('canvas');this.backgroundDirty=true;
    if(mode==='avatar')this.avatar=new CartoonAvatar(video);
  }
  async start(){
    this.worker=new Worker(new URL('tracking-worker.bundle.js',location.href));
    await new Promise((resolve,reject)=>{
      this.loadReject=reject;this.loadTimer=setTimeout(()=>reject(new Error('โหลดโมเดลติดตามนานเกินไป')),25000);
      this.worker.onerror=()=>{if(!this.disposed){reject(new Error('เปิดตัวติดตามไม่สำเร็จ'));this.onError();}};
      this.worker.onmessage=event=>{
        if(this.disposed)return;const data=event.data;
        if(data.kind==='ready'){clearTimeout(this.loadTimer);this.ready=true;resolve();return;}
        if(data.kind==='error'){clearTimeout(this.loadTimer);reject(Error('โมเดลติดตามทำงานไม่สำเร็จ'));this.onError();return;}
        this.pending=false;
        if(data.kind==='mask')this.acceptMask(data);
        if(data.kind==='pose'){
          this.avatar.update(data,performance.now());this.faceFound=!!data.face;this.poseFound=!!data.world;
        }
        this.inferenceMs=data.ms;
      };
      this.worker.postMessage({kind:'init',base:new URL('.',location.href).href,mode:this.mode});
    });
    if(this.disposed)return;
    this.renderFrames=0;this.inferenceFrames=0;this.metricStamp=performance.now();
    const tick=now=>{
      if(this.disposed)return;
      if(this.video.readyState>=2){
        this.render(now);this.renderFrames++;
        if(this.ready&&!this.pending&&this.video.currentTime!==this.lastFrame&&now-this.lastSubmit>65){
          this.lastFrame=this.video.currentTime;this.lastSubmit=now;this.pending=true;void this.submit(now);
        }
      }
      if(now-this.metricStamp>1000){
        this.onMetrics({renderFps:Math.round(this.renderFrames*1000/(now-this.metricStamp)),trackingFps:this.inferenceFrames,inferenceMs:Math.round(this.inferenceMs||0),face:!!this.faceFound,pose:!!this.poseFound});
        this.renderFrames=this.inferenceFrames=0;this.metricStamp=now;
      }
      this.request=requestAnimationFrame(tick);
    };this.request=requestAnimationFrame(tick);
  }
  async submit(time){
    try{
      const width=640,height=Math.max(1,Math.round(this.video.videoHeight*width/this.video.videoWidth));
      const bitmap=await createImageBitmap(this.video,{resizeWidth:width,resizeHeight:height});
      if(this.disposed){bitmap.close();return;}
      this.inferenceFrames++;this.worker.postMessage({kind:'frame',bitmap,time},[bitmap]);
    }catch{if(!this.disposed){this.pending=false;this.onError();}}
  }
  acceptMask(data){
    const {width,height,pixels}=data;
    if(this.mask.width!==width||this.mask.height!==height){this.mask.width=width;this.mask.height=height;this.previousMask=null;}
    const image=this.maskContext.createImageData(width,height),old=this.previousMask;
    for(let i=0;i<pixels.length;i++){
      const confidence=old?pixels[i]*.85+old[i]*.15:pixels[i];pixels[i]=confidence;
      const alpha=Math.min(1,Math.max(0,(confidence-.20)/.60));
      image.data[i*4]=image.data[i*4+1]=image.data[i*4+2]=255;image.data[i*4+3]=Math.round(alpha*255);
    }
    this.previousMask=pixels;this.maskContext.putImageData(image,0,0);this.maskStamp=performance.now();
  }
  setBackground(scene,custom=null){this.scene=scene;this.custom=custom;this.backgroundDirty=true;}
  render(now){
    const w=Math.min(960,this.video.videoWidth),h=Math.round(this.video.videoHeight*w/this.video.videoWidth);
    if(this.canvas.width!==w||this.canvas.height!==h){this.canvas.width=this.person.width=this.backdrop.width=w;this.canvas.height=this.person.height=this.backdrop.height=h;this.backgroundDirty=true;}
    if(this.backgroundDirty){drawBackground(this.backdrop.getContext('2d'),w,h,this.scene,this.custom);this.backgroundDirty=false;}
    this.context.drawImage(this.backdrop,0,0);
    if(this.mode==='avatar'){
      this.context.drawImage(this.avatar.render(w,h,now),0,0);return;
    }
    if(!this.maskStamp||now-this.maskStamp>600)return;
    const ctx=this.personContext;ctx.clearRect(0,0,w,h);ctx.save();ctx.translate(w,0);ctx.scale(-1,1);ctx.drawImage(this.video,0,0,w,h);
    ctx.globalCompositeOperation='destination-in';ctx.filter='blur(1px)';ctx.drawImage(this.mask,0,0,w,h);ctx.restore();
    this.context.drawImage(this.person,0,0);
  }
  dispose(){
    this.disposed=true;clearTimeout(this.loadTimer);cancelAnimationFrame(this.request);this.loadReject?.(new Error('cancelled'));
    this.worker?.terminate();this.avatar?.dispose();this.previousMask=null;this.worker=null;
  }
}
