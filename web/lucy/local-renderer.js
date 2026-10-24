// All pixels stay in the embedded browser. No model/service/API dependency.
export const LOCAL_STYLES = ['anime','cyberpunk','watercolor','hologram'];
export function localStyle(text) {
  const value = text.toLowerCase();
  if (/อนิเม|การ์ตูน|anime|cartoon/.test(value)) return 'anime';
  if (/ไซเบอร์|นีออน|cyber|neon/.test(value)) return 'cyberpunk';
  if (/สีน้ำ|watercolor|watercolour/.test(value)) return 'watercolor';
  if (/โฮโลแกรม|hologram|blueprint/.test(value)) return 'hologram';
  return null;
}
const vertex = `attribute vec2 position; varying vec2 uv;
void main(){uv=position*.5+.5;gl_Position=vec4(position,0.,1.);}`;
const fragment = `precision mediump float;
uniform sampler2D image; uniform vec2 stepSize; uniform int style; uniform float clock;
varying vec2 uv;
vec3 sampleAt(vec2 p){return texture2D(image,clamp(p,vec2(0.),vec2(1.))).rgb;}
float lum(vec3 c){return dot(c,vec3(.299,.587,.114));}
void main(){
 vec2 p=vec2(1.-uv.x,1.-uv.y);vec3 c=sampleAt(p),smoothColor=c*4.;float total=4.;
 for(int y=-1;y<=1;y++){for(int x=-1;x<=1;x++){
  vec3 n=sampleAt(p+vec2(float(x),float(y))*stepSize*2.);
  float w=exp(-dot(n-c,n-c)*18.);smoothColor+=n*w;total+=w;
 }}smoothColor/=total;
 float left=lum(sampleAt(p-vec2(stepSize.x*1.5,0.)));
 float right=lum(sampleAt(p+vec2(stepSize.x*1.5,0.)));
 float top=lum(sampleAt(p-vec2(0.,stepSize.y*1.5)));
 float bottom=lum(sampleAt(p+vec2(0.,stepSize.y*1.5)));
 float edge=length(vec2(right-left,bottom-top));float l=lum(c);vec3 result;
 if(style==0){
  vec3 toon=floor(smoothColor*8.+.5)/8.;toon=mix(vec3(lum(toon)),toon,1.18);
  result=toon*(1.-smoothstep(.055,.26,edge)*.72);
 }else if(style==1){
  vec3 base=pow(c,vec3(.86))*vec3(.77,.91,1.15);
  vec3 neon=mix(vec3(.0,1.,.88),vec3(1.,.1,.65),smoothstep(.25,.7,l));
  result=base*.70+neon*smoothstep(.03,.24,edge)*.65;
  result+=vec3(.07,.0,.12)*(1.-l);
 }else if(style==2){
  vec3 wash=floor(smoothColor*10.+.5)/10.;
  float paper=sin(p.x*1800.)*sin(p.y*1400.)*.012;
  result=mix(wash,vec3(1.,.97,.90),.19)-vec3(edge*.20)+paper;
 }else{
  float lines=.90+.10*sin(p.y*900.+clock*2.);
  float grid=step(.975,fract(p.x*30.))*.025+step(.975,fract(p.y*20.))*.025;
  result=vec3(.02,.40,.50)*l+vec3(.10,1.,.90)*smoothstep(.025,.24,edge);
  result=result*lines+grid;
 }gl_FragColor=vec4(clamp(result,0.,1.),1.);
}`;
export class LocalRenderer {
  constructor(canvas,video,onFrame=()=>{},onError=()=>{}) {
    Object.assign(this,{canvas,video,onFrame,onError,style:'anime',request:null,running:false});
    const gl=canvas.getContext('webgl',{alpha:false,antialias:false,preserveDrawingBuffer:false});
    if(!gl) throw new Error('WebGL unavailable');
    this.gl=gl;
    const shader=(type,source)=>{
      const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);
      if(!gl.getShaderParameter(s,gl.COMPILE_STATUS)) {gl.deleteShader(s);throw new Error('Shader compile failed');}return s;
    };
    const vs=shader(gl.VERTEX_SHADER,vertex),fs=shader(gl.FRAGMENT_SHADER,fragment);
    const program=gl.createProgram();gl.attachShader(program,vs);gl.attachShader(program,fs);gl.linkProgram(program);
    gl.deleteShader(vs);gl.deleteShader(fs);
    if(!gl.getProgramParameter(program,gl.LINK_STATUS)) throw new Error('Shader link failed');
    this.program=program;gl.useProgram(program);
    this.buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,this.buffer);
    gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,1,1]),gl.STATIC_DRAW);
    const position=gl.getAttribLocation(program,'position');gl.enableVertexAttribArray(position);gl.vertexAttribPointer(position,2,gl.FLOAT,false,0,0);
    this.texture=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,this.texture);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
    this.uniforms=Object.fromEntries(['stepSize','style','clock'].map(name=>[name,gl.getUniformLocation(program,name)]));
    this.onContextLost=event=>{event.preventDefault();this.stop();onError();};
    canvas.addEventListener('webglcontextlost',this.onContextLost);
  }
  start(){
    this.running=true;
    const tick=time=>{
      if(!this.running)return;
      try {if(this.video.readyState>=2){this.render(time);this.onFrame(time);}}
      catch {this.stop();this.onError();return;}
      if(this.video.requestVideoFrameCallback){this.videoCallback=true;this.request=this.video.requestVideoFrameCallback(tick);}
      else {this.videoCallback=false;this.request=requestAnimationFrame(tick);}
    };tick(performance.now());
  }
  render(time){
    const {gl,canvas,video,uniforms}=this;
    // Cap processing at camera-native 720p; never allocate display-scale textures.
    const factor=Math.min(1,1280/video.videoWidth,720/video.videoHeight);
    const w=Math.max(1,Math.round(video.videoWidth*factor)),h=Math.max(1,Math.round(video.videoHeight*factor));
    if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;}
    gl.viewport(0,0,w,h);gl.useProgram(this.program);gl.bindTexture(gl.TEXTURE_2D,this.texture);
    gl.texImage2D(gl.TEXTURE_2D,0,gl.RGB,gl.RGB,gl.UNSIGNED_BYTE,video);
    gl.uniform2f(uniforms.stepSize,1/video.videoWidth,1/video.videoHeight);
    gl.uniform1i(uniforms.style,Math.max(0,LOCAL_STYLES.indexOf(this.style)));
    gl.uniform1f(uniforms.clock,time/1000);gl.drawArrays(gl.TRIANGLE_STRIP,0,4);
  }
  stop(){
    this.running=false;
    if(this.request!==null){if(this.videoCallback)this.video.cancelVideoFrameCallback(this.request);else cancelAnimationFrame(this.request);}
    this.request=null;
  }
  dispose(){
    this.stop();this.canvas.removeEventListener('webglcontextlost',this.onContextLost);
    this.gl.deleteTexture(this.texture);this.gl.deleteBuffer(this.buffer);this.gl.deleteProgram(this.program);
    this.gl.getExtension('WEBGL_lose_context')?.loseContext();
  }
}
