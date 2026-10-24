"""Bounded, cancellable single-job controller for a separate local AI process."""
import base64
import json
import os
from pathlib import Path
import subprocess
import threading
import uuid

ROOT = Path(__file__).resolve().parent


class LocalAI:
    def __init__(self):
        self.lock=threading.RLock()
        self.process=None
        self.state={'status':'idle'}

    def available(self):
        required=('model_index.json','unet/diffusion_pytorch_model.fp16.safetensors',
                  'vae/diffusion_pytorch_model.fp16.safetensors',
                  'text_encoder/model.fp16.safetensors','safety_checker/model.fp16.safetensors')
        return (ROOT/'.venv-ai/bin/python').is_file() and (ROOT/'.local-ai/lcm/pytorch_lora_weights.safetensors').is_file() and all(
            (ROOT/'.local-ai/model'/name).is_file() for name in required)

    def start(self, data):
        import cv2
        import numpy as np
        if not self.available():
            raise RuntimeError('ยังไม่ติดตั้งโมเดล Local AI')
        prompt=data.get('prompt','')
        if not isinstance(prompt,str) or not prompt.strip() or len(prompt)>1000:
            raise ValueError('กรุณาระบุ prompt ภาษาอังกฤษ ไม่เกิน 1000 ตัวอักษร')
        for key in ('image','mask'):
            raw=base64.b64decode(data.get(key,''),validate=True)
            if len(raw)>2*1024*1024:
                raise ValueError('ภาพใหญ่เกินไป')
            image=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_UNCHANGED)
            if image is None or image.shape[:2]!=(512,512):
                raise ValueError('ภาพและ mask ต้องมีขนาด 512x512')
            if key=='mask' and np.max(image[:,:,:3] if image.ndim==3 else image)<20:
                raise ValueError('ระบายพื้นที่ที่ต้องการเปลี่ยนก่อน')
        request={key:data[key] for key in ('image','mask','prompt')}
        request['steps']=max(4,min(8,int(data.get('steps',6))))
        request['seed']=max(0,min(2147483647,int(data.get('seed',42))))
        with self.lock:
            if self.state['status'] in ('loading','running'):
                raise RuntimeError('กำลังสร้างภาพอยู่ กรุณารอหรือยกเลิกก่อน')
            job=uuid.uuid4().hex
            request['id']=job
            self.state={'status':'loading','id':job,'step':0,'total':request['steps']}
            if self.process is None or self.process.poll() is not None:
                env=dict(os.environ,HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
                    PYTHONDONTWRITEBYTECODE='1',PYTORCH_ENABLE_MPS_FALLBACK='1',TOKENIZERS_PARALLELISM='false')
                self.process=subprocess.Popen([str(ROOT/'.venv-ai/bin/python'),str(ROOT/'local_ai_worker.py')],
                    stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                    text=True,bufsize=1,env=env,cwd=str(ROOT))
                threading.Thread(target=self.read,args=(self.process,),daemon=True).start()
            threading.Thread(target=self.send,args=(self.process,request),daemon=True).start()
            return job

    def send(self, process, request):
        try:
            process.stdin.write(json.dumps(request)+'\n');process.stdin.flush()
        except (BrokenPipeError,OSError,ValueError):
            with self.lock:
                if process is self.process:
                    self.state.update(status='error',message='เปิด Local AI ไม่สำเร็จ กรุณาตรวจการติดตั้งโมเดล')

    def read(self, process):
        try:
            for line in process.stdout:
                try: message=json.loads(line)
                except ValueError: continue
                with self.lock:
                    if process is not self.process: return
                    kind=message.get('kind')
                    if kind=='ready':self.state['status']='running'
                    elif kind=='progress' and message.get('id')==self.state.get('id'):
                        self.state.update(status='running',step=message['step'])
                    elif kind=='result' and message.get('id')==self.state.get('id'):
                        self.state.update(status='done',image=message['image'],seconds=message['seconds'])
                    elif kind=='error':
                        self.state.update(status='error',message=message.get('message','สร้างภาพไม่สำเร็จ'))
        finally:
            with self.lock:
                if process is self.process and self.state['status'] in ('running','loading'):
                    self.state.update(status='error',message='Local AI หยุดทำงาน ลองลดแอปที่ใช้แรมแล้วเริ่มใหม่')

    def snapshot(self, job):
        with self.lock:
            if job!=self.state.get('id'):return {'status':'cancelled'}
            return dict(self.state)

    def close(self):
        with self.lock:
            process=self.process;self.process=None
            self.state={'status':'idle'}
        if process is not None:
            process.terminate()
            try:process.wait(timeout=3)
            except subprocess.TimeoutExpired:process.kill();process.wait()
            if process.stdin:process.stdin.close()
            if process.stdout:process.stdout.close()
