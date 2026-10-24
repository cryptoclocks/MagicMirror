import {createDecartClient, models} from '@decartai/sdk';
import {StudioSession} from './session.js';
import {LocalRenderer, localStyle} from './local-renderer.js';
const $ = id => document.getElementById(id);
const prompts = {
  anime: 'Restyle the person and scene as a high-quality animated movie. Preserve pose, expression, composition and movement.',
  cyberpunk: 'Restyle the scene as a cinematic cyberpunk city with cyan and magenta neon. Preserve the person, pose and movement.',
  hologram: 'Restyle the video as a cyan holographic projection with fine scanlines and luminous contours.',
  watercolor: 'Restyle the video as a delicate watercolor painting with flowing pigment, preserving the person and movement.'
};
let run = 0, busy = false, active = false, previewStream = null, deadline = 0, watch = null, lastFrame = 0;
let abort = null, frameCallback = null;
let renderer = null, style = 'anime';
const isLocal = () => $('provider').value === 'local';
const status = text => { $('status').textContent = text; };
function controls() {
  $('start').disabled = busy || active || (!isLocal() && !$('start').dataset.hasKey);
  $('provider').disabled = busy || active || !!previewStream;
  $('preview').disabled = busy || active;
  $('stop').disabled = !busy && !active && !previewStream;
  $('camera').disabled = busy || active || !!previewStream;
  $('apply').disabled = !active;
}
function stop(message = 'หยุดแล้ว · ไม่ส่งภาพ') {
  run++; abort?.abort(); abort = null;
  clearInterval(watch); watch = null;
  renderer?.dispose(); renderer = null;
  $('local-output').hidden = true;
  session.stop(); previewStream?.getTracks().forEach(t => t.stop()); previewStream = null;
  if (frameCallback !== null && $('output').cancelVideoFrameCallback) $('output').cancelVideoFrameCallback(frameCallback);
  frameCallback = null;
  $('output').style.transform = '';
  $('output').srcObject = null; $('input').srcObject = null;
  $('input').style.display = 'none'; $('empty').style.display = '';
  $('timer').textContent = ''; busy = active = false; controls(); status(message);
}
async function capture() {
  const video = {width:{ideal:1280,max:1280},height:{ideal:720,max:720},frameRate:{ideal:30,max:30}};
  if ($('camera').value) video.deviceId = {exact:$('camera').value};
  return navigator.mediaDevices.getUserMedia({audio:false,video});
}
async function cameras() {
  const value = $('camera').value;
  const devices = await navigator.mediaDevices.enumerateDevices();
  $('camera').replaceChildren(new Option('กล้องเริ่มต้น',''));
  devices.filter(d => d.kind === 'videoinput').forEach((d,i) => $('camera').add(new Option(d.label || `กล้อง ${i+1}`,d.deviceId)));
  if ([...$('camera').options].some(o => o.value === value)) $('camera').value = value;
}
function errorText(error) {
  if (['NotAllowedError','SecurityError'].includes(error?.name)) return 'เปิดสิทธิ์กล้องให้แอปใน System Settings แล้วลองใหม่';
  if (['NotReadableError','AbortError'].includes(error?.name)) return 'กล้องไม่พร้อมหรือกำลังถูกใช้งาน ลองใหม่อีกครั้ง';
  if (error?.name === 'NotFoundError') return 'ไม่พบกล้อง กรุณาเสียบเว็บแคม';
  if (error?.name === 'OverconstrainedError') return 'กล้องที่เลือกไม่พร้อม กรุณาเลือกกล้องอื่น';
  // Avoid displaying SDK messages which may contain credentials or transport URLs.
  return 'เชื่อมต่อไม่สำเร็จ ตรวจ API key เครดิต และอินเทอร์เน็ต แล้วลองใหม่';
}
const session = new StudioSession({
  capture,
  connect: async stream => {
    const thisRun = run;
    abort = new AbortController();
    const response = await fetch('token',{method:'POST',signal:abort.signal});
    const data = await response.json();
    if (!response.ok) { $('hint').textContent = data.error || 'ขอโทเคนไม่สำเร็จ'; throw new Error('token'); }
    if (thisRun !== run) throw new Error('cancelled');
    $('input').srcObject = stream; $('input').style.display = 'block';
    void cameras().catch(() => {});
    const client = createDecartClient({apiKey:data.apiKey,logger:{debug(){},info(){},warn(){},error(){}},telemetry:false});
    const realtime = await client.realtime.connect(stream,{
      model:models.realtime('lucy-2.5'), mirror:'auto',
      initialState:{prompt:{text:$('prompt').value.trim(),enhance:true}},
      onRemoteStream: remote => {
        if (thisRun !== run) return;
        $('output').srcObject = remote; $('empty').style.display = 'none';
        $('output').play().catch(() => {});
        lastFrame = Date.now();
        if ($('output').requestVideoFrameCallback && frameCallback === null) {
          const tick = () => { lastFrame = Date.now(); frameCallback = $('output').requestVideoFrameCallback(tick); };
          frameCallback = $('output').requestVideoFrameCallback(tick);
        }
      }
    });
    if (thisRun === run) {
      realtime.on('error',() => stop('การเชื่อมต่อขัดข้อง · หยุดส่งภาพแล้ว'));
      realtime.on('connectionChange',state => { if (thisRun === run && state === 'disconnected') stop('ตัดการเชื่อมต่อแล้ว'); });
    }
    return realtime;
  }
});
window.refreshConfig = async () => {
  try {
    const config = await (await fetch('config')).json();
    $('start').dataset.hasKey = config.hasKey ? 'yes' : '';
    if (isLocal()) { $('hint').textContent = 'พร้อมใช้ในเครื่อง · เลือกสไตล์แล้วกดเริ่ม Local'; controls(); return; }
    $('hint').textContent = config.hasKey ? 'พร้อมใช้งาน · เลือกสไตล์แล้วกดเริ่ม AI' : 'กด “ตั้ง Decart API key” ด้านบนก่อนเริ่ม AI · ดูกล้องในเครื่องได้ทันที';
    controls();
  } catch { status('โหลดการตั้งค่าไม่ได้ กรุณากลับหน้าหลักแล้วเปิดใหม่'); }
};
async function startLocal() {
  stop(); busy = true; controls(); status('กำลังเปิดกล้องในเครื่อง…');
  const thisRun = run;
  try {
    const stream = await capture();
    if (thisRun !== run) { stream.getTracks().forEach(t => t.stop()); return; }
    previewStream = stream;
    $('input').srcObject = stream; $('input').style.display = 'block';
    await $('input').play();
    if (thisRun !== run) return;
    let count = 0, stamp = performance.now();
    renderer = new LocalRenderer($('local-output'),$('input'), time => {
      if (++count >= 30) { $('timer').textContent = `${Math.round(count*1000/(time-stamp))} FPS · LOCAL`; count = 0; stamp = time; }
    }, () => stop('GPU ไม่พร้อม กรุณาเปิดหน้า Studio ใหม่'));
    renderer.style = style; $('local-output').hidden = false;
    $('empty').style.display = 'none'; renderer.start();
    if (!renderer?.running) return;
    busy = false; active = true; controls(); status('LOCAL LIVE · ไม่ส่งภาพออก');
    $('hint').textContent = 'สลับสไตล์ได้ทันที · เอฟเฟกต์ภาพ ไม่ใช่โมเดลสร้างเสื้อผ้าหรือฉากใหม่';
    void cameras().catch(() => {});
  } catch(error) { if (thisRun === run) stop(/WebGL|Shader/.test(error?.message) ? 'เปิด GPU ไม่สำเร็จ ลองเปิดแอปใหม่' : errorText(error)); }
}
$('provider').onchange = () => {
  stop();
  $('start').textContent = isLocal() ? 'เริ่ม Local' : 'เริ่ม AI · ส่งภาพไป Decart';
  $('mode-info').textContent = isLocal() ? 'เอฟเฟกต์ GPU · ไม่ใช้ API key' : 'Generative AI · ใช้ Decart API key';
  $('privacy').textContent = isLocal() ? 'ภาพอยู่ในเครื่อง · ไม่ใช้เครดิต · ไม่ส่งไมโครโฟน' : 'ส่งวิดีโอไป Decart · ใช้เครดิต · หยุดอัตโนมัติใน 2 นาที';
  $('prompt').placeholder = isLocal() ? 'ชื่อสไตล์: อนิเมะ นีออน สีน้ำ โฮโลแกรม' : 'อธิบายเสื้อผ้า ฉาก หรือสไตล์ที่ต้องการ';
  $('prompt').value = isLocal() ? document.querySelector('[data-style].active').textContent : prompts[style];
  void window.refreshConfig();
};
$('start').onclick = async () => {
  if (isLocal()) return startLocal();
  if (!$('prompt').value.trim()) return status('เลือกสไตล์หรือพิมพ์เอฟเฟกต์ก่อน');
  stop(); busy = true; controls(); status('กำลังเปิดกล้องและเชื่อมต่อ…');
  const thisRun = run;
  // Stop also invalidates a late-resolving connection, preventing orphan sessions.
  const setupTimeout = setTimeout(() => stop('เชื่อมต่อนานเกินไป · หยุดส่งภาพแล้ว'),35000);
  try {
    const connected = await session.start();
    if (!connected || thisRun !== run) return;
    busy = false; active = true; deadline = Date.now()+120000; lastFrame = Date.now(); controls(); status('AI LIVE · LUCY 2.5');
    watch = setInterval(() => {
      const left = Math.max(0,Math.ceil((deadline-Date.now())/1000));
      $('timer').textContent = `${left}s`;
      if (!left) stop('ครบ 2 นาที · หยุดแล้ว กดเริ่มเพื่อใช้อีกครั้ง');
      else if ($('output').requestVideoFrameCallback && Date.now()-lastFrame > 20000) stop('ไม่ได้รับภาพใหม่ · หยุดส่งภาพแล้ว');
    },1000);
  } catch(error) { if (thisRun === run) stop(errorText(error)); }
  finally { clearTimeout(setupTimeout); }
};
$('preview').onclick = async () => {
  stop(); busy = true; controls(); const thisRun = run;
  try {
    const stream = await capture();
    if (thisRun !== run) { stream.getTracks().forEach(t => t.stop()); return; }
    previewStream = stream; $('output').srcObject = stream; $('output').style.transform = 'scaleX(-1)';
    $('empty').style.display = 'none'; status('LOCAL PREVIEW · ไม่ส่งภาพ');
    await cameras();
  } catch(error) { if (thisRun === run) status(errorText(error)); }
  finally { if (thisRun === run) { busy = false; controls(); } }
};
$('stop').onclick = () => { $('output').style.transform = ''; stop(); };
$('prompt-form').onsubmit = async event => {
  event.preventDefault();
  const prompt = $('prompt').value.trim();
  if (isLocal()) {
    const next = localStyle(prompt);
    if (!next) return status('Local รองรับอนิเมะ นีออน สีน้ำ และโฮโลแกรม');
    style = next; if (renderer) renderer.style = next;
    document.querySelectorAll('[data-style]').forEach(b => b.classList.toggle('active',b.dataset.style === style));
    return status('LOCAL LIVE · เปลี่ยนสไตล์แล้ว');
  }
  if (!session.client || !prompt) return;
  const thisRun = run; $('apply').disabled = true;
  try { await session.client.set({prompt,enhance:true}); if (thisRun === run) status('AI LIVE · อัปเดตเอฟเฟกต์แล้ว'); }
  catch { if (thisRun === run) status('เปลี่ยนเอฟเฟกต์ไม่สำเร็จ ลองใหม่'); }
  finally { if (thisRun === run) controls(); }
};
for (const button of document.querySelectorAll('[data-style]')) button.onclick = () => {
  style = button.dataset.style;
  $('prompt').value = isLocal() ? button.textContent : prompts[style];
  if (renderer) renderer.style = style;
  document.querySelectorAll('[data-style]').forEach(b => b.classList.toggle('active',b === button));
  if (active) $('prompt-form').requestSubmit();
};
$('presets').firstElementChild.click();
window.shutdownStudio = stop;
window.addEventListener('pagehide',() => stop());
window.addEventListener('beforeunload',() => stop());
document.addEventListener('visibilitychange',() => { if (document.hidden) stop('พัก AI เมื่อซ่อนหน้าจอ'); });
window.addEventListener('keydown',event => { if (event.key === 'Escape') stop(); });
void cameras().catch(() => {});
$('provider').onchange();
