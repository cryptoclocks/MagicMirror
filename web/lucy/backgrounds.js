// Procedural scenery is original artwork; user uploads remain local browser data.
export function drawBackground(ctx,w,h,style,custom){
  if(style==='custom'&&custom){
    const scale=Math.max(w/custom.width,h/custom.height);ctx.drawImage(custom,(w-custom.width*scale)/2,(h-custom.height*scale)/2,custom.width*scale,custom.height*scale);return;
  }
  const g=ctx.createLinearGradient(0,0,0,h);
  if(style==='space'){
    g.addColorStop(0,'#030820');g.addColorStop(1,'#172154');ctx.fillStyle=g;ctx.fillRect(0,0,w,h);
    for(let i=0;i<110;i++){const x=((i*97+31)%997)/997*w,y=((i*157+71)%991)/991*h;ctx.fillStyle=i%3?'#a1c2f5':'#ffffff';ctx.fillRect(x,y,i%4===0?2:1,i%4===0?2:1);}
    const planet=ctx.createRadialGradient(w*.76,h*.35,0,w*.76,h*.35,h*.3);planet.addColorStop(0,'#9cf3df');planet.addColorStop(.55,'#278ed8');planet.addColorStop(1,'#183a86');ctx.fillStyle=planet;ctx.beginPath();ctx.arc(w*.78,h*.4,h*.27,0,Math.PI*2);ctx.fill();
  }else if(style==='sky'){
    g.addColorStop(0,'#6cafe2');g.addColorStop(.7,'#d7edf1');g.addColorStop(1,'#eadfcf');ctx.fillStyle=g;ctx.fillRect(0,0,w,h);
    for(let j=0;j<3;j++){ctx.fillStyle=['#a2bdc9','#7d9d9f','#527b78'][j];ctx.beginPath();ctx.moveTo(0,h);for(let i=0;i<=12;i++)ctx.lineTo(w*i/12,h*(.65+j*.10)-Math.sin(i*1.4+j)*h*.09);ctx.lineTo(w,h);ctx.fill();}
  }else{
    g.addColorStop(0,'#e9dfd3');g.addColorStop(1,'#bdb1a6');ctx.fillStyle=g;ctx.fillRect(0,0,w,h);
    const window=ctx.createLinearGradient(0,0,0,h*.65);window.addColorStop(0,'#a9d0dc');window.addColorStop(1,'#ebf3e6');ctx.fillStyle=window;ctx.fillRect(w*.07,h*.08,w*.27,h*.58);
    ctx.strokeStyle='#f5eee3';ctx.lineWidth=w*.014;ctx.strokeRect(w*.07,h*.08,w*.27,h*.58);ctx.beginPath();ctx.moveTo(w*.205,h*.08);ctx.lineTo(w*.205,h*.66);ctx.moveTo(w*.07,h*.37);ctx.lineTo(w*.34,h*.37);ctx.stroke();
    ctx.fillStyle='#9b7960';ctx.fillRect(0,h*.83,w,h*.17);ctx.fillStyle='#5d7054';for(let i=0;i<7;i++){ctx.beginPath();ctx.ellipse(w*.88+(i%2?1:-1)*w*.035,h*(.43+i*.045),w*.055,h*.022,(i%2?-.5:.5),0,Math.PI*2);ctx.fill();}ctx.fillStyle='#be8970';ctx.fillRect(w*.84,h*.70,w*.09,h*.13);
  }
}
