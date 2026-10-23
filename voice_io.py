"""Push-to-talk capture; audio stays in memory and is sent only for recognition."""
import queue
import time
import numpy as np
from PySide6.QtCore import QThread, Signal
from assistant_logic import select_transcript


class VoiceInput(QThread):
    heard = Signal(str)
    status = Signal(str)
    failed = Signal(str)
    level = Signal(float)

    def __init__(self,parent=None):
        super().__init__(parent)
        self.wait_forever=False

    def run(self):
        try:
            import sounddevice as sd
            import speech_recognition as sr
            sample_rate = int(sd.query_devices(kind='input')['default_samplerate'])
            packets = queue.Queue(maxsize=160)
            def callback(data, frames, timing, flags):
                try:
                    packets.put_nowait(data.copy())
                except queue.Full:
                    pass
            chunks = []
            voiced = False
            quiet = 0.0
            captured = 0.0
            noise = .002
            with sd.InputStream(samplerate=sample_rate, channels=1, dtype='int16',
                                blocksize=max(256,int(sample_rate*.05)), callback=callback):
                self.status.emit('listening')
                deadline = time.monotonic()+9
                while (time.monotonic()<deadline or (self.wait_forever and not voiced)) and not self.isInterruptionRequested():
                    try:
                        data = packets.get(timeout=.2)
                    except queue.Empty:
                        continue
                    chunks.append(data)
                    duration = len(data)/sample_rate
                    captured += duration
                    rms = float(np.sqrt(np.mean((data.astype(np.float32)/32768)**2)))
                    self.level.emit(min(1.0,rms*18))
                    if captured<.35:
                        noise = max(.001,noise*.8+rms*.2)
                    elif rms>max(.004,noise*2.4):
                        if not voiced and self.wait_forever:
                            deadline=time.monotonic()+9
                        voiced = True
                        quiet = 0
                    else:
                        quiet += duration
                    if not voiced and captured>.5:
                        # Keep only pre-roll while latched and waiting; silence cannot grow memory.
                        chunks=chunks[-8:]
                    if voiced and quiet>1.15 and captured>1:
                        break
            self.level.emit(0)
            if self.isInterruptionRequested():
                return
            if not voiced:
                self.failed.emit('ยังไม่ได้ยินเสียง กด M แล้วลองพูดใหม่ได้ค่ะ')
                return
            self.status.emit('thinking')
            audio = np.concatenate(chunks).ravel()
            if sample_rate != 16000:
                target = np.arange(int(len(audio)*16000/sample_rate))*sample_rate/16000
                audio = np.interp(target,np.arange(len(audio)),audio).astype(np.int16)
            recognizer = sr.Recognizer()
            recognizer.operation_timeout = 8
            result = recognizer.recognize_google(sr.AudioData(audio.tobytes(),16000,2), language='th-TH', show_all=True, endpoint='https://www.google.com/speech-api/v2/recognize')
            if not self.isInterruptionRequested():
                text = select_transcript(result)
                if text:
                    self.heard.emit(text)
                else:
                    self.failed.emit('ฟังคำพูดไม่ชัด กด M แล้วลองพูดอีกครั้งค่ะ')
        except Exception as exc:
            # Avoid blank exception messages from UnknownValueError.
            name = type(exc).__name__
            if name == 'UnknownValueError':
                message = 'ฟังคำพูดไม่ชัด กด M แล้วลองพูดอีกครั้งค่ะ'
            elif name == 'RequestError':
                message = 'เชื่อมต่อบริการถอดเสียงไม่ได้ ตรวจอินเทอร์เน็ต หรือพิมพ์คำสั่งแทนค่ะ'
            else:
                message = 'เปิดไมค์ไม่ได้ ตรวจสิทธิ์ Microphone ใน macOS: '+str(exc)
            if not self.isInterruptionRequested():
                self.failed.emit(message)
