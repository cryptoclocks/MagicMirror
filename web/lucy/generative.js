// Local model keyframes with bounded buffering and same-seed edits.
export function createGenerative({capture,status,changed}) {
  const $=id=>document.getElementById(id);
  const photo=$('ai-photo'),overlay=$('ai-mask'),mask=document.createElement('canvas');
  photo.width=photo.height=overlay.width=overlay.height=mask.width=mask.height=512;
  const source=document.createElement('canvas');source.width=source.height=512;
  const sourceContext=source.getContext('2d'),ctx=photo.getContext('2d'),paint=overlay.getContext('2d'),m=mask.getContext('2d');
  let generation=0,stream=null,image=null,poll=null,face=null,drag=false,automatic=false,busy=false,transition=null;
  let captureTimer=null,playTimer=null,frames=[],clips=[],playing=false;
  async function post(route,data){const response=await fetch(route,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const value=await response.json();if(!response.ok)throw Error(value.error||'Local motion error');return value;}
  function frameImage(){
    const video=$('input'),scale=Math.min(512/video.videoWidth,512/video.videoHeight),w=video.videoWidth*scale,h=video.videoHeight*scale;
    sourceContext.fillStyle='#10151c';sourceContext.fillRect(0,0,512,512);
    sourceContext.save();sourceContext.translate(512,0);sourceContext.scale(-1,1);sourceContext.drawImage(video,(512-w)/2,(512-h)/2,w,h);sourceContext.restore();
    return source.toDataURL('image/jpeg',.80).split(',')[1];
  }
  async function playClips(){
    if(playing||!clips.length)return;playing=true;const token=generation;
    try{
      while(clips.length&&token===generation){
        const clip=clips.shift();await post('ai/motion/begin',{image:clip.image,output:clip.output,mask:clip.mask});
        for(const frame of clip.frames){
          if(token!==generation)return;const started=performance.now();
          const result=await post('ai/motion/step',{image:frame});if(token!==generation)return;
          const picture=new Image();await new Promise((resolve,reject)=>{picture.onload=resolve;picture.onerror=reject;picture.src='data:image/jpeg;base64,'+result.image;});
          if(token!==generation)return;ctx.drawImage(picture,0,0);
          $('timer').textContent=`LOCAL · หน่วง ${clip.seconds}s · motion 8 FPS`;
          await new Promise(resolve=>{playTimer=setTimeout(resolve,Math.max(0,125-(performance.now()-started)));});
        }
      }
    }catch{if(token===generation)status('ภาพเคลื่อนไหวสะดุด · ภาพ AI ล่าสุดยังอยู่');}
    finally{if(token===generation)playing=false;}
  }
  const prompts={hat:'A realistic black leather baseball cap worn naturally on the head, detailed fabric, natural lighting, photograph',clothes:'A tailored dark navy business suit jacket over a white shirt, realistic fabric folds, photograph',face:'A friendly humanoid robot face made of brushed silver metal, realistic photographic lighting',background:'A futuristic space station interior with large windows overlooking planet Earth, realistic cinematic photograph'};
  function clear(){m.fillStyle='black';m.fillRect(0,0,512,512);refresh();}
  function refresh(){
    const pixels=m.getImageData(0,0,512,512),out=paint.createImageData(512,512);
    for(let i=0;i<pixels.data.length;i+=4){out.data[i]=75;out.data[i+1]=245;out.data[i+2]=205;out.data[i+3]=pixels.data[i]*.35;}
    paint.putImageData(out,0,0);
  }
  function suggested(){
    clear();if(!face)return status('ไม่พบหน้า · ระบายบริเวณที่ต้องการเปลี่ยนบนภาพ');
    const [x,y,w,h]=face,region=$('ai-region').value;
    m.fillStyle='white';m.beginPath();
    if(region==='hat')m.ellipse(x+w*.5,y-h*.10,w*.75,h*.43,0,0,Math.PI*2);
    else if(region==='face')m.ellipse(x+w*.5,y+h*.52,w*.47,h*.56,0,0,Math.PI*2);
    else if(region==='clothes'){m.moveTo(x-w*.70,y+h*1.18);m.lineTo(x+w*1.70,y+h*1.18);m.lineTo(x+w*2.3,512);m.lineTo(x-w*1.3,512);m.closePath();}
    else {m.fillRect(0,0,512,512);m.globalCompositeOperation='destination-out';m.ellipse(x+w*.5,y+h*.55,w*.72,h*.85,0,0,Math.PI*2);m.fill();m.fillRect(x-w*.9,y+h*.90,w*2.8,512);m.globalCompositeOperation='source-over';refresh();return;}
    m.fill();refresh();
  }
  function setPrompt(){$('ai-prompt').value=prompts[$('ai-region').value];suggested();}
  async function freeze(){
    if(!stream)return;const video=$('input');
    sourceContext.fillStyle='#10151c';sourceContext.fillRect(0,0,512,512);
    const scale=Math.min(512/video.videoWidth,512/video.videoHeight),w=video.videoWidth*scale,h=video.videoHeight*scale;
    sourceContext.save();sourceContext.translate(512,0);sourceContext.scale(-1,1);sourceContext.drawImage(video,(512-w)/2,(512-h)/2,w,h);sourceContext.restore();
    if(!automatic)ctx.drawImage(source,0,0);
    image=source.toDataURL('image/png').split(',')[1];face=null;
    const reply=await fetch('ai/face',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image})});
    if(reply.ok)face=(await reply.json()).face;
    suggested();
  }
  function position(event){
    const r=overlay.getBoundingClientRect(),scale=Math.min(r.width/512,r.height/512);
    return [(event.clientX-r.left-(r.width-512*scale)/2)/scale,(event.clientY-r.top-(r.height-512*scale)/2)/scale];
  }
  function brush(event){if(busy)return;const [x,y]=position(event);m.fillStyle=$('ai-erase').checked?'black':'white';m.beginPath();m.arc(x,y,Number($('ai-brush').value),0,Math.PI*2);m.fill();refresh();}
  overlay.onpointerdown=event=>{drag=true;overlay.setPointerCapture(event.pointerId);brush(event);};
  overlay.onpointermove=event=>{if(drag)brush(event);};
  overlay.onpointerup=()=>{drag=false;};overlay.onpointercancel=()=>{drag=false;};
  $('ai-region').onchange=setPrompt;$('ai-clear').onclick=clear;
  $('ai-freeze').onclick=()=>{if(!busy)void freeze();};
  $('ai-generate').onclick=()=>void generate();
  $('ai-continuous').onchange=()=>{automatic=$('ai-continuous').checked;};
  function buttons(){for(const id of ['ai-generate','ai-freeze','ai-region','ai-clear'])$(id).disabled=busy;}
  async function generate(){
    if(busy||!image)return;busy=true;buttons();const token=generation;
    const anchor=image,selected=mask.toDataURL('image/png').split(',')[1];frames=[];
    if(automatic){clearInterval(captureTimer);captureTimer=setInterval(()=>{if(token===generation&&stream&&frames.length<128)frames.push(frameImage());},125);}
    overlay.hidden=true;status('กำลังสร้างภาพด้วย Metal · โปรดรอ');
    try{
      const response=await fetch('ai/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image,mask:mask.toDataURL('image/png').split(',')[1],prompt:$('ai-prompt').value,steps:Number($('ai-steps').value),seed:42})});
      const data=await response.json();if(token!==generation)return;
      if(!response.ok)throw Error(data.error||'เริ่มโมเดลไม่สำเร็จ');
      const check=async()=>{
        try{
          const state=await(await fetch(`ai/status/${data.id}`)).json();if(token!==generation)return;
          if(state.status==='done'){
            clearInterval(captureTimer);captureTimer=null;
            if(automatic){
              clips.push({image:anchor,output:state.image,mask:selected,frames:frames.slice(),seconds:state.seconds});
              // Keep at most one waiting clip; variable inference time never grows
              // an unbounded video delay or frame queue.
              if(clips.length>1)clips.splice(0,clips.length-1);
              void playClips();busy=false;buttons();
              await freeze();if(token===generation&&automatic)poll=setTimeout(()=>void generate(),100);
              return;
            }
            const next=new Image();next.onload=()=>{
              if(token!==generation)return;
              const previous=ctx.getImageData(0,0,512,512),old=document.createElement('canvas');old.width=old.height=512;old.getContext('2d').putImageData(previous,0,0);
              const start=performance.now();
              const blend=time=>{
                if(token!==generation)return;
                const alpha=Math.min(1,(time-start)/650);ctx.globalAlpha=1;ctx.drawImage(old,0,0);ctx.globalAlpha=alpha*alpha*(3-2*alpha);ctx.drawImage(next,0,0);ctx.globalAlpha=1;
                if(alpha<1)transition=requestAnimationFrame(blend);else{transition=null;busy=false;buttons();status(`LOCAL AI · ${state.seconds} วินาที/ภาพ`);if(automatic){poll=setTimeout(async()=>{await freeze();if(token===generation)void generate();},1000);}else overlay.hidden=false;}
              };transition=requestAnimationFrame(blend);
            };next.src='data:image/png;base64,'+state.image;
          }else if(state.status==='error'||state.status==='cancelled'){throw Error(state.message||'ยกเลิกแล้ว');}
          else{status(state.status==='loading'?'กำลังโหลดโมเดลเข้า Metal…':`กำลังสร้าง ${state.step||0}/${state.total||16} · ภาพจะค่อย ๆ เปลี่ยนเมื่อพร้อม`);poll=setTimeout(check,750);}
        }catch(error){if(token===generation){clearInterval(captureTimer);captureTimer=null;busy=false;buttons();overlay.hidden=false;status(error.message);}}
      };void check();
    }catch(error){if(token===generation){clearInterval(captureTimer);captureTimer=null;busy=false;buttons();overlay.hidden=false;status(error.message);}}
  }
  return {
    async start(){
      const token=++generation;status('กำลังเปิดกล้องสำหรับ Local AI…');
      const captured=await capture();if(token!==generation){captured.getTracks().forEach(t=>t.stop());return;}
      stream=captured;$('input').srcObject=stream;$('input').style.display='block';await $('input').play();
      if(token!==generation)return;
      photo.hidden=overlay.hidden=false;$('empty').style.display='none';$('ai-controls').hidden=false;
      await freeze();if(token!==generation)return;
      $('ai-prompt').value=prompts[$('ai-region').value];changed(true);status('เลือกพื้นที่สีเขียว แล้วกดสร้างภาพ · ประมวลผลในเครื่อง');
    },
    stop(){generation++;clearTimeout(poll);clearInterval(captureTimer);captureTimer=null;frames=[];clips=[];playing=false;cancelAnimationFrame(transition);transition=null;busy=false;automatic=false;$('ai-continuous').checked=false;buttons();stream?.getTracks().forEach(t=>t.stop());stream=null;photo.hidden=overlay.hidden=true;$('ai-controls').hidden=true;void fetch('ai/cancel',{method:'POST'}).catch(()=>{});}
  };
}
