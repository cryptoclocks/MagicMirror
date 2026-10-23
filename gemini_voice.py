"""Text-to-audio via Gemini Live WebSocket; credentials never enter URLs or logs."""
import asyncio
import base64
import json
import os
import time
from pathlib import Path
import numpy as np
from PySide6.QtCore import QThread, Signal

ROOT=Path(__file__).resolve().parent
ENDPOINT='wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent'


def settings():
    return json.loads((ROOT/'voice_settings.json').read_text())


def api_key():
    value=os.environ.get('GEMINI_API_KEY','').strip()
    if value:
        return value
    path=ROOT/'.secrets/gemini-api-key'
    return path.read_text().strip() if path.exists() else ''


def setup_message(config):
    return {'setup':{
        'model':'models/'+config['model'].removeprefix('models/'),
        'generationConfig':{
            'responseModalities':['AUDIO'],
            'speechConfig':{'voiceConfig':{'prebuiltVoiceConfig':{'voiceName':config['voice']}}},
        },
        'systemInstruction':{'parts':[{'text':
            'คุณชื่อออร่า เป็นผู้ช่วยผู้หญิงของ Smart Mirror พูดภาษาไทยเท่านั้น '+config['style']+
            ' อ่านเฉพาะข้อความที่ผู้ใช้ส่งมาให้ครบถ้วน ห้ามตอบคำถามหรือเติมข้อเท็จจริงใหม่ '+
            'ไม่ต้องเกริ่น ไม่อ่านคำสั่งกำกับ ไม่เพิ่มคำเตือนหรือคำอธิบาย ทำหน้าที่ออกเสียงข้อความเท่านั้น'}]},
    }}


async def stream_speech(text,key,config,on_audio,should_stop=lambda:False):
    import websockets
    if not key:
        raise RuntimeError('GEMINI_KEY_MISSING')
    async with websockets.connect(ENDPOINT,extra_headers={'x-goog-api-key':key},
                                  open_timeout=8,close_timeout=1,max_size=8*1024*1024) as ws:
        await ws.send(json.dumps(setup_message(config),ensure_ascii=False))
        ready=json.loads(await asyncio.wait_for(ws.recv(),timeout=10))
        if 'setupComplete' not in ready:
            raise RuntimeError('GEMINI_SETUP_FAILED')
        await ws.send(json.dumps({'clientContent':{
            'turns':[{'role':'user','parts':[{'text':text}]}],'turnComplete':True}},ensure_ascii=False))
        deadline=time.monotonic()+max(25,min(60,len(text)*.12+10))
        total=0
        while not should_stop():
            if time.monotonic()>deadline:
                raise RuntimeError('GEMINI_AUDIO_TIMEOUT')
            try:
                message=json.loads(await asyncio.wait_for(ws.recv(),timeout=.3))
            except asyncio.TimeoutError:
                continue
            if 'error' in message:
                raise RuntimeError('GEMINI_SERVICE_ERROR')
            content=message.get('serverContent',{})
            for part in content.get('modelTurn',{}).get('parts',[]):
                inline=part.get('inlineData',{})
                if inline.get('data') and inline.get('mimeType','').startswith('audio/pcm'):
                    pcm=base64.b64decode(inline['data'])
                    if len(pcm)%2:
                        raise RuntimeError('GEMINI_INVALID_PCM')
                    total+=len(pcm)
                    on_audio(pcm)
            if content.get('turnComplete'):
                if total==0:
                    raise RuntimeError('GEMINI_EMPTY_AUDIO')
                return total
        return total


class GeminiSpeaker(QThread):
    status=Signal(str)
    level=Signal(float)
    failed=Signal(str)

    def __init__(self,text,parent=None):
        super().__init__(parent)
        self.text=text
        self.loop=None
        self.task=None

    def cancel(self):
        self.requestInterruption()
        loop=self.loop
        if loop and loop.is_running() and self.task:
            try:
                loop.call_soon_threadsafe(self.task.cancel)
            except RuntimeError:
                pass

    def run(self):
        import sounddevice as sd
        stream=None
        started=False
        def play(pcm):
            nonlocal stream,started
            if self.isInterruptionRequested():
                return
            if stream is None:
                stream=sd.RawOutputStream(samplerate=24000,channels=1,dtype='int16')
                stream.start()
            if not started:
                self.status.emit('speaking')
                started=True
            # Emit level from the PCM actually played, not an unrelated animation.
            # Small writes keep both the visual meter and cancellation responsive.
            for start in range(0,len(pcm),2400):
                if self.isInterruptionRequested():
                    break
                chunk=pcm[start:start+2400]
                samples=np.frombuffer(chunk,dtype='<i2').astype(np.float32)/32768
                self.level.emit(min(1.,float(np.sqrt(np.mean(samples*samples)))*5))
                stream.write(chunk)
        try:
            self.status.emit('synthesizing')
            self.loop=asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.task=self.loop.create_task(stream_speech(self.text,api_key(),settings(),play,self.isInterruptionRequested))
            self.loop.run_until_complete(self.task)
        except asyncio.CancelledError:
            pass
        except Exception:
            # Do not forward transport exception text: it can include request headers.
            if not self.isInterruptionRequested():
                self.failed.emit('GEMINI_VOICE_UNAVAILABLE')
        finally:
            if stream:
                if self.isInterruptionRequested():
                    stream.abort()
                else:
                    stream.stop()
                stream.close()
            self.level.emit(0)
            if self.loop:
                self.loop.run_until_complete(self.loop.shutdown_asyncgens())
                self.loop.close()
            self.loop=None
