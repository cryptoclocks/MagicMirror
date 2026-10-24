"""Voice-driven presentation shell around the existing health mirror."""
import math
import sys
import time
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, QProcess, QUrl
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QRadialGradient
from PySide6.QtWidgets import QLineEdit, QPushButton, QMenu
from PySide6.QtMultimedia import QSoundEffect, QMediaDevices

from smartmirror import Mirror, color, CYAN, MINT, MUTED, AMBER, PINK
from assistant_logic import COMMANDS, CommandEngine, SALES, sales_snapshot
from voice_io import VoiceInput
from hats import HatRenderer, head_pose
from hat_catalog import HATS
from daily_tasks import DailyTasks, today
from gemini_voice import GeminiSpeaker, settings as voice_settings

ROOT = Path(__file__).resolve().parent


def list_camera_devices():
    # Qt enumerates AVFoundation devices without opening a capture session.
    return [(index, device.description(), bytes(device.id()))
            for index, device in enumerate(QMediaDevices.videoInputs())]


def ease(value):
    value = max(0., min(1., value))
    return 1-(1-value)**3


class AssistantMirror(Mirror):
    def __init__(self, camera=0, demo=False, fullscreen=False, mute=False):
        # Parent initializes its demo mode, so startup never opens the camera.
        super().__init__(camera=camera, demo=True, fullscreen=False)
        self.demo = demo
        self.engine = CommandEngine()
        self.studio = None
        self.tasks = DailyTasks()
        self.hat_renderer = HatRenderer()
        self.hat_enabled = False
        self.hat_picker = False
        self.hat_index = 0
        self.hat_scale = 1.
        self.hat_offset = 0.
        self.hat_pose = None
        self.hat_frame_stamp = None
        self.mute = mute
        self.changed = time.monotonic()
        self.period_changed = self.changed
        self.period = 'daily'
        self.voice = None
        self.mic_latched = False
        self.m_key_down = False
        self.closing = False
        self.m_hold_timer = QTimer(self)
        self.m_hold_timer.setSingleShot(True)
        self.m_hold_timer.setInterval(500)
        self.m_hold_timer.timeout.connect(self.lock_microphone)
        self.mic_resume_timer = QTimer(self)
        self.mic_resume_timer.setInterval(300)
        self.mic_resume_timer.timeout.connect(self.resume_continuous_mic)
        self.mic_retry_delay = 300
        self.voice_status = 'idle'
        self.voice_level = 0.
        self.heard_text = ''
        self.response = 'สวัสดีค่ะ ออร่าพร้อมแล้ว กดไมค์แล้วพูด “เข้าหน้าหลัก” ได้เลยค่ะ'
        self.notice = ''
        self.notice_until = 0.
        self.dark_controls_until = 0.
        self.frames = [QImage(str(p)) for p in sorted((ROOT/'assets/clock').glob('*.png'))]
        self.frames = [f for f in self.frames if not f.isNull()]
        self.speaker = None
        self.speech_workers = []
        self.speech = QProcess(self)
        self.speech.finished.connect(self.speech_done)
        self.speech.errorOccurred.connect(self.speech_error)
        self.effects = {}
        if not mute:
            for name in ('listen','confirm'):
                cue = ROOT/'assets'/f'{name}.wav'
                if cue.exists():
                    effect = QSoundEffect(self)
                    effect.setSource(QUrl.fromLocalFile(str(cue)))
                    effect.setVolume(.18)
                    self.effects[name] = effect
        self.mic_button = QPushButton('●  เปิดไมค์ · M',self)
        self.mic_button.clicked.connect(self.toggle_mic)
        self.mic_button.setToolTip('กด M สั้น: ฟังหนึ่งคำสั่ง · กด M ค้างครึ่งวินาที: ล็อกฟังต่อเนื่อง · กด M อีกครั้ง: ปิด')
        self.input = QLineEdit(self)
        self.input.setPlaceholderText('พิมพ์คำสั่งภาษาไทย แล้วกด Enter …')
        self.input.returnPressed.connect(self.submit_text)
        self.send_button = QPushButton('ส่ง ↗',self)
        self.send_button.clicked.connect(self.submit_text)
        self.camera_button = QPushButton('กล้อง / เว็บแคม ▾',self)
        self.camera_button.clicked.connect(self.show_camera_menu)
        self.studio_button = QPushButton('AI Studio · L',self)
        self.studio_button.clicked.connect(lambda: self.execute('เปิดเอไอสตูดิโอ'))
        self.camera_menu = QMenu(self)
        self.media_devices = QMediaDevices(self)
        self.selected_camera_id = None
        self.available_cameras = []
        self.refresh_camera_devices()
        self.media_devices.videoInputsChanged.connect(self.refresh_camera_devices)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setStyleSheet('''
            QPushButton { color:#77fff1; background:#09262d; border:1px solid #29616a;
                border-radius:9px; padding:4px; font-family:Thonburi; }
            QPushButton:hover { background:#14404a; border-color:#77fff1; }
            QMenu { color:#d4f6ef; background:#09212a; border:1px solid #29616a;
                padding:7px; font-family:Thonburi; font-size:14px; }
            QMenu::item { padding:10px 22px; }
            QMenu::item:selected { background:#16434d; }
            QMenu::item:disabled { color:#71959d; }
            QLineEdit { color:#d4f6ef; background:#07151d; border:1px solid #24444d;
                border-radius:9px; padding-left:15px; font-family:Thonburi; }
            QLineEdit:focus { border-color:#69f5e8; }
        ''')
        self.layout_controls()
        self.setFocus()
        if fullscreen:
            self.showFullScreen()

    @property
    def mode(self):
        return self.engine.state

    def layout_controls(self):
        if not hasattr(self,'mic_button'):
            return
        s=min(self.width()/1440,self.height()/900)
        dx=(self.width()-1440*s)/2
        dy=(self.height()-900*s)/2
        if getattr(self,'studio',None):
            self.studio.setGeometry(0,0,self.width(),self.height())
        for widget,x,y,w,h in ((self.studio_button,1215,16,180,38),(self.mic_button,46,839,185,42),
                                (self.camera_button,245,839,260,42),
                                (self.input,519,839,756,42),(self.send_button,1288,839,106,42)):
            widget.setGeometry(round(dx+x*s),round(dy+y*s),round(w*s),round(h*s))
            font=QFont('Thonburi')
            font.setPixelSize(max(10,round(13*s)))
            widget.setFont(font)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.layout_controls()

    def refresh_camera_devices(self):
        self.available_cameras = list_camera_devices()
        previous_id = self.selected_camera_id
        if previous_id is not None:
            matching = next((c for c in self.available_cameras if c[2] == previous_id), None)
            if matching is not None and matching[0] != self.camera_index:
                self.select_camera(matching[0])
                return
            if matching is None and self.available_cameras:
                self.select_camera(self.available_cameras[0][0])
                return
        current = next((c for c in self.available_cameras if c[0] == self.camera_index), None)
        if current:
            self.selected_camera_id = current[2]
            name = current[1]
            short = name if len(name) <= 21 else name[:19]+'…'
            self.camera_button.setText('กล้อง: '+short+' ▾')
            self.camera_button.setToolTip(f'กล้อง #{current[0]}: {name} — เลือกเว็บแคมหรือกด V')
        else:
            self.camera_button.setText('กล้อง / เว็บแคม ▾')
            self.camera_button.setToolTip('เสียบเว็บแคม แล้วกดเพื่อเลือกกล้อง (V)')

    def show_camera_menu(self):
        self.refresh_camera_devices()
        self.camera_menu.clear()
        for index, name, device_id in self.available_cameras:
            action = self.camera_menu.addAction(f'{name}  ·  #{index}')
            action.setCheckable(True)
            action.setChecked(index == self.camera_index and not self.demo)
            action.triggered.connect(lambda checked=False, selected=index: self.select_camera(selected))
        if not self.available_cameras:
            self.camera_menu.addAction('ไม่พบกล้อง — เสียบเว็บแคมแล้วลองใหม่').setEnabled(False)
        elif len(self.available_cameras) == 1:
            self.camera_menu.addAction('พบกล้องเดียว · เสียบเว็บแคมเพื่อเพิ่มตัวเลือก').setEnabled(False)
        self.camera_menu.addSeparator()
        refresh = self.camera_menu.addAction('รีเฟรชรายการกล้อง')
        refresh.triggered.connect(self.show_camera_menu)
        self.camera_menu.popup(self.camera_button.mapToGlobal(QPoint(0,-self.camera_menu.sizeHint().height())))

    def select_camera(self,index):
        selected = next((c for c in self.available_cameras if c[0] == index), None)
        if selected is None:
            return
        # Update selection in standby/sales/dark without activating capture.
        changed = index != self.camera_index or self.demo or selected[2] != self.selected_camera_id
        self.camera_index = index
        self.selected_camera_id = selected[2]
        self.demo = False
        self.camera_button.setToolTip(f'กล้อง #{index}: {selected[1]} — เลือกเว็บแคมหรือกด V')
        short = selected[1] if len(selected[1]) <= 21 else selected[1][:19]+'…'
        self.camera_button.setText('กล้อง: '+short+' ▾')
        if changed:
            self.stop_camera()
            self.image = None
            self.box = None
            self.landmarks = None
            self.target = None
            self.acquired = time.monotonic()
            if self.mode in ('home','health'):
                self.start_camera()
        self.notice = 'เลือกกล้อง: '+selected[1]+(' — พร้อมเปิดเมื่อเข้าหน้าหลัก' if self.mode not in ('home','health') else '')
        self.notice_until = time.monotonic()+6
        self.update()
        self.setFocus()

    def on_frame(self,image,box,acquired,landmarks=None):
        if self.sender() is not None and self.sender() is not self.camera:
            return
        super().on_frame(image,box,acquired,landmarks)

    def on_issue(self,message):
        if self.sender() is not None and self.sender() is not self.camera:
            return
        super().on_issue(message)

    def stop_speech(self):
        if self.speaker:
            speaker = self.speaker
            self.speaker = None
            speaker.cancel()
        self.voice_level = 0
        if self.speech.state() != QProcess.ProcessState.NotRunning:
            self.speech.kill()
            self.speech.waitForFinished(1000)

    def mic_button_text(self):
        return '■  ไมค์ค้าง · M ปิด' if self.mic_latched else '●  เปิดไมค์ · M'

    def stop_microphone(self):
        self.mic_latched=False
        self.m_hold_timer.stop()
        self.mic_resume_timer.stop()
        if self.voice:
            self.voice.requestInterruption()
        if self.voice_status not in ('speaking','synthesizing'):
            self.voice_status='cancelled' if self.voice and self.voice.isRunning() else 'idle'
        self.mic_button.setText(self.mic_button_text())

    def lock_microphone(self):
        if not self.m_key_down or self.closing:
            return
        self.mic_latched=True
        if self.voice:
            self.voice.wait_forever=True
        self.mic_button.setText(self.mic_button_text())
        self.notice='ไมค์ค้างเปิดอยู่ค่ะ พูดคำสั่งต่อได้ กด M อีกครั้งเพื่อปิด'
        self.notice_until=time.monotonic()+4
        self.mic_resume_timer.start(300)

    def resume_continuous_mic(self):
        if self.closing or not self.mic_latched:
            self.mic_resume_timer.stop()
            return
        if self.speaker or self.speech.state()!=QProcess.ProcessState.NotRunning:
            return
        if self.voice and self.voice.isRunning():
            return
        if self.voice_status=='starting':
            return
        self.mic_resume_timer.stop()
        self.toggle_mic(resume=True)

    def toggle_mic(self, resume=False):
        if self.mic_latched and not resume:
            self.stop_microphone()
            return
        if self.voice_status == 'starting':
            self.voice_status='idle'
            self.mic_button.setText('●  เปิดไมค์ · M')
            return
        if self.voice and self.voice.isRunning():
            self.voice.requestInterruption()
            self.voice_status='cancelled'
            self.mic_button.setText('กำลังปิดไมค์ …')
            return
        if self.voice:
            self.voice.deleteLater()
        self.stop_speech()
        self.voice_status='starting'
        self.voice_level=0
        self.notice=''
        self.dark_controls_until=time.monotonic()+12
        if 'listen' in self.effects:
            self.effects['listen'].play()
        self.voice=VoiceInput(self)
        self.voice.wait_forever=self.mic_latched
        self.mic_retry_delay=300
        self.voice.status.connect(self.set_voice_status)
        self.voice.level.connect(self.set_level)
        self.voice.heard.connect(self.voice_heard)
        self.voice.failed.connect(self.voice_failed)
        self.voice.finished.connect(self.voice_finished)
        self.mic_button.setText(self.mic_button_text() if self.mic_latched else '■  หยุดฟัง · M')
        # Finish the brief cue before opening microphone capture.
        QTimer.singleShot(220,self.begin_capture)
        self.setFocus()

    def begin_capture(self):
        if self.voice_status == 'starting' and self.voice:
            self.voice.start()

    def set_voice_status(self,status):
        if self.voice and self.voice.isInterruptionRequested():
            return
        if self.voice_status != 'cancelled':
            self.voice_status=status

    def set_level(self,level):
        self.voice_level=level

    def voice_heard(self,text):
        if self.voice and self.voice.isInterruptionRequested():
            return
        if self.voice_status != 'cancelled':
            self.execute(text)

    def voice_failed(self,message):
        if self.voice_status == 'cancelled':
            return
        self.voice_status='idle'
        self.notice=message
        self.notice_until=time.monotonic()+12
        self.mic_retry_delay=2000

    def voice_finished(self):
        self.voice_level=0
        if self.voice_status in ('listening','thinking','cancelled','starting'):
            self.voice_status='idle'
        self.mic_button.setText(self.mic_button_text())
        if self.mic_latched and not self.closing:
            self.mic_resume_timer.start(self.mic_retry_delay)

    def submit_text(self):
        text=self.input.text().strip()
        if text:
            # Ignore any in-flight recognition result after typed command submission.
            if self.voice and self.voice.isRunning():
                self.voice.requestInterruption()
            self.input.clear()
            self.execute(text)
            self.setFocus()

    def execute(self,text,speak=True):
        self.heard_text=text
        old_mode=self.mode
        action,reply=self.engine.handle(text)
        self.response=reply
        if action:
            if old_mode=='studio' and self.mode!='studio':
                self.close_studio()
            if action in ('health','health_report'):
                self.hat_picker = False
            if action == 'hats':
                self.hat_enabled = True
                self.hat_picker = True
            elif action == 'hat_select':
                if self.engine.hat_choice is not None:
                    self.hat_index = self.engine.hat_choice
                self.hat_enabled = True
                self.hat_picker = True
            elif action == 'hat_off':
                self.hat_enabled = False
                self.hat_picker = False
                self.hat_pose = None
            if 'confirm' in self.effects:
                self.effects['confirm'].play()
            self.changed=time.monotonic()
            if self.mode in ('home','health'):
                if self.demo:
                    if action in ('health','health_report'):
                        self.acquired=time.monotonic()
                elif action != 'hat_off' and (not self.camera or not self.camera.isRunning()):
                    self.start_camera()
            else:
                self.stop_camera()
                self.image=None
                self.box=None
                self.landmarks=None
                self.target=None
            if action=='studio':
                self.open_studio()
            if action=='sales':
                self.period_changed=time.monotonic()
            if self.mode=='dark':
                self.dark_controls_until=0
        if speak and reply:
            self.speak(reply)
        self.update()
        return action

    def open_studio(self):
        if self.studio is not None:
            return
        try:
            from lucy_studio import create_studio
            self.studio=create_studio(self,lambda: self.execute('กลับหน้าหลัก'))
            self.layout_controls()
            self.studio.show()
            self.studio.raise_()
            for widget in (self.studio_button,self.mic_button,self.camera_button,self.input,self.send_button):
                widget.hide()
        except (ImportError,RuntimeError) as exc:
            self.notice='เปิด AI Studio ไม่สำเร็จ ตรวจการติดตั้ง PySide6 WebEngine'
            self.notice_until=time.monotonic()+12
            self.engine.state='home'
            if not self.demo:
                self.start_camera()

    def close_studio(self):
        if self.studio is not None:
            studio=self.studio
            self.studio=None
            studio.shutdown()

    def speak(self,text):
        self.stop_speech()
        if self.mute:
            self.voice_status='idle'
            return
        self.voice_status='synthesizing'
        worker=GeminiSpeaker(text,self)
        self.speaker=worker
        self.speech_workers.append(worker)
        worker.status.connect(lambda status,w=worker:self.gemini_status(w,status))
        worker.level.connect(lambda level,w=worker:self.gemini_level(w,level))
        worker.failed.connect(lambda error,w=worker:self.gemini_failed(w))
        worker.finished.connect(lambda w=worker:self.gemini_finished(w))
        worker.start()

    def gemini_status(self,worker,status):
        if worker is self.speaker:
            self.voice_status=status

    def gemini_level(self,worker,level):
        if worker is self.speaker:
            self.voice_level=level

    def gemini_failed(self,worker):
        if worker is not self.speaker:
            return
        self.speaker=None
        self.notice='Gemini Live เชื่อมต่อไม่ได้ กำลังใช้เสียงผู้หญิงในเครื่องแทนค่ะ'
        self.notice_until=time.monotonic()+7
        if sys.platform=='darwin':
            self.voice_status='speaking'
            self.speech.start('/usr/bin/say',['-v','Kanya','-r',str(voice_settings().get('fallback_rate',225)),worker.text])
        else:
            self.voice_status='idle'

    def gemini_finished(self,worker):
        if worker is self.speaker:
            self.speaker=None
            self.voice_level=0
            if self.voice_status in ('speaking','synthesizing'):
                self.voice_status='idle'
        if worker in self.speech_workers:
            self.speech_workers.remove(worker)
        worker.deleteLater()

    def speech_done(self,*args):
        if self.voice_status=='speaking':
            self.voice_status='idle'

    def speech_error(self,*args):
        if self.voice_status=='speaking':
            self.voice_status='idle'
            self.notice='เล่นเสียงตอบกลับไม่ได้ โปรดตรวจเสียง Kanya ใน macOS'
            self.notice_until=time.monotonic()+10

    def set_period(self,period):
        if period != self.period:
            self.period=period
            self.period_changed=time.monotonic()

    def keyPressEvent(self,event):
        key=event.key()
        if key==Qt.Key.Key_M:
            if not event.isAutoRepeat() and not self.m_key_down:
                self.m_key_down=True
                if self.mic_latched:
                    self.stop_microphone()
                else:
                    self.toggle_mic()
                    self.m_hold_timer.start()
        elif key==Qt.Key.Key_Space:
            if not event.isAutoRepeat():
                self.toggle_mic()
        elif key==Qt.Key.Key_D:
            self.demo=not self.demo
            self.stop_camera()
            self.image=None
            self.box=None
            self.landmarks=None
            if self.mode in ('home','health') and not self.demo:
                self.start_camera()
            self.acquired=time.monotonic()
        elif key==Qt.Key.Key_R:
            if self.mode in ('home','health') and not self.demo:
                self.start_camera()
        elif key in (Qt.Key.Key_1,Qt.Key.Key_2,Qt.Key.Key_3) and self.mode=='sales':
            self.set_period(('daily','monthly','yearly')[key-Qt.Key.Key_1])
        elif key==Qt.Key.Key_L:
            self.execute('เปิดเอไอสตูดิโอ')
        elif key==Qt.Key.Key_B:
            self.execute('เลือกหมวก')
        elif self.hat_picker and self.mode in ('home','health') and Qt.Key.Key_1<=key<=Qt.Key.Key_5:
            self.execute('หมวกเบอร์'+str(key-Qt.Key.Key_1+1))
        elif self.hat_picker and key in (Qt.Key.Key_Up,Qt.Key.Key_Down):
            self.hat_offset=max(-.55,min(.55,self.hat_offset+(-.025 if key==Qt.Key.Key_Up else .025)))
        elif self.hat_picker and key in (Qt.Key.Key_BracketLeft,Qt.Key.Key_BracketRight):
            self.hat_scale=max(.6,min(1.8,self.hat_scale+(-.05 if key==Qt.Key.Key_BracketLeft else .05)))
        elif key==Qt.Key.Key_V:
            self.show_camera_menu()
        elif key==Qt.Key.Key_H:
            self.input.setFocus()
        elif key==Qt.Key.Key_I and sys.platform=='darwin':
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl('x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone'))
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self,event):
        if event.key()==Qt.Key.Key_M:
            if not event.isAutoRepeat():
                self.m_key_down=False
                self.m_hold_timer.stop()
            return
        super().keyReleaseEvent(event)

    def mousePressEvent(self,event):
        s=min(self.width()/1440,self.height()/900)
        dx=(self.width()-1440*s)/2
        dy=(self.height()-900*s)/2
        x,y=(event.position().x()-dx)/s,(event.position().y()-dy)/s
        if self.mode=='today':
            tasks=self.tasks.data()['tasks']
            for index,task in enumerate(tasks[:5]):
                yy=178+index*108
                if 480<=x<=1385 and yy<=y<=yy+94:
                    self.tasks.toggle(task['id'])
                    if 'confirm' in self.effects:
                        self.effects['confirm'].play()
                    self.update()
                    return
        if self.hat_picker and self.mode in ('home','health'):
            if 615<=y<=730:
                for index in range(5):
                    if 300+index*218<=x<=500+index*218:
                        self.execute('หมวกเบอร์'+str(index+1))
                        return
                if 62<=x<=230 and 700<=y<=728:
                    self.execute('เอาหมวกออก')
                    return
                if 665<=y<=692:
                    if 62<=x<=137:
                        self.hat_offset=max(-.55,self.hat_offset-.025)
                        return
                    if 145<=x<=220:
                        self.hat_offset=min(.55,self.hat_offset+.025)
                        return
        if self.mode=='sales' and 286<=y<=324:
            for i,period in enumerate(('daily','monthly','yearly')):
                if 610+i*155<=x<=750+i*155:
                    self.set_period(period)
        self.setFocus()
        super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        if self.mode=='dark' and event.position().y()>self.height()*.85:
            self.dark_controls_until=time.monotonic()+4
        super().mouseMoveEvent(event)

    def closeEvent(self,event):
        self.closing=True
        self.close_studio()
        self.mic_latched=False
        self.m_hold_timer.stop()
        self.mic_resume_timer.stop()
        self.stop_speech()
        for worker in list(self.speech_workers):
            worker.cancel()
            worker.wait()
        if self.voice:
            self.voice.requestInterruption()
            self.voice.wait()
        super().closeEvent(event)

    def thai(self,p,x,y,text,size=18,shade='#d5efed',width=None):
        font=QFont('Thonburi')
        font.setPixelSize(size)
        p.setFont(font)
        p.setPen(color(shade))
        if width:
            p.drawText(QRectF(x,y-size,width,size*3),Qt.TextFlag.TextWordWrap,text)
        else:
            p.drawText(QPointF(x,y),text)

    def draw_orb(self,p,cx,cy,r,t):
        level=self.voice_level if self.voice_status in ('listening','speaking') else (.22 if self.voice_status=='synthesizing' else .12)
        shade=MINT if self.voice_status=='speaking' else CYAN
        grad=QRadialGradient(QPointF(cx,cy),r*1.6)
        grad.setColorAt(0,color(shade,25+level*45))
        grad.setColorAt(.55,color(shade,13))
        grad.setColorAt(1,color(shade,0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawEllipse(QRectF(cx-r*1.6,cy-r*1.6,r*3.2,r*3.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for index in range(4):
            radius=r*(.72+index*.11)
            p.setPen(self.pen(shade,1.2 if index==0 else .7,180-index*30))
            for offset in (0,120,240):
                p.drawArc(QRectF(cx-radius,cy-radius,radius*2,radius*2),int((offset+t*(14 if index%2 else -21))*16),87*16)
        for i in range(72):
            a=i*math.tau/72
            h=3+level*(9+12*(.5+.5*math.sin(i*.73+t*10)))
            self.path(p,[(cx+math.cos(a)*(r+9),cy+math.sin(a)*(r+9)),
                         (cx+math.cos(a)*(r+9+h),cy+math.sin(a)*(r+9+h))],shade,1,False)
        pts=[]
        for i in range(100):
            x=(i/99-.5)*r*1.1
            v=math.sin(i*.27+t*7)*math.sin(i/99*math.pi)*r*.20*(.4+level)
            pts.append((cx+x,cy+v))
        self.path(p,pts,shade,1.5)
        self.text(p,cx-r*.33,cy+r*.39,'A U R A',max(8,int(r*.12)),shade,1)

    def background(self,p,t):
        gradient=QLinearGradient(0,0,1440,900)
        gradient.setColorAt(0,QColor('#061720'))
        gradient.setColorAt(.5,QColor('#050e19'))
        gradient.setColorAt(1,QColor('#081c23'))
        p.fillRect(QRectF(0,0,1440,900),gradient)
        p.setPen(self.pen(CYAN,.5,18))
        for x in range(46,1440,48):
            p.drawLine(QPointF(x,105),QPointF(x,750))
        for y in range(106,751,48):
            p.drawLine(QPointF(46,y),QPointF(1394,y))
        for i in range(28):
            x=(i*137+math.sin(t*.2+i)*30)%1360+40
            y=(i*79-t*(3+i%3))%620+110
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color(CYAN,40))
            p.drawEllipse(QRectF(x,y,1.5,1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)

    def header(self,p,label):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        self.text(p,46,51,'A U R A',28,'#dcfff6',3,True)
        self.text(p,47,75,'PERSONAL INTELLIGENCE / MIRROR OS',9,MUTED,1.6)
        self.text(p,552,50,label,11,CYAN,2)
        self.text(p,1196,49,datetime.now(ZoneInfo('Asia/Bangkok')).strftime('%H:%M:%S'),19,'#d9fffa')
        self.text(p,1195,72,'BANGKOK / VOICE READY',9,MUTED)
        self.path(p,[(46,94),(1394,94)],CYAN,.7,False)
        self.path(p,[(46,94),(175,94)],CYAN,2)

    def standby_page(self,p,t):
        self.header(p,'ASSISTANT / AWAITING YOUR VOICE')
        self.text(p,47,128,'CAMERA OFF / MICROPHONE ON DEMAND',10,MUTED)
        self.text(p,1170,128,'SYSTEM STANDBY',10,MINT)
        self.draw_orb(p,720,325,113,t)
        self.thai(p,566,501,'ยินดีต้อนรับกลับมา',33,'#e2fff6')
        self.thai(p,506,541,'กด M หรือปุ่มไมค์ แล้วพูด “เข้าหน้าหลัก”',20,CYAN)
        self.text(p,576,567,'YOUR REFLECTION. REIMAGINED.',11,MUTED,2)
        # Command reference remains visible before activation.
        for index,(key,command) in enumerate(list(COMMANDS.items())[:5]):
            xx=130+index*242
            self.panel(p,xx,620,224,85,CYAN)
            self.text(p,xx+16,646,f'0{index+1} / VOICE COMMAND',8,MUTED)
            self.thai(p,xx+16,679,command['phrase'],14,'#c9f5ef')

    def home_page(self,p,t):
        if self.demo:
            self.demo_background(p,t)
        elif self.image:
            image=self.image
            scale=max(1440/image.width(),900/image.height())
            p.save()
            p.setClipRect(QRectF(0,0,1440,900))
            p.drawImage(QRectF((1440-image.width()*scale)/2,(900-image.height()*scale)/2,
                              image.width()*scale,image.height()*scale),image)
            p.restore()
        else:
            self.background(p,t)
        grad=QLinearGradient(0,0,0,900)
        grad.setColorAt(0,color('#020e16',210))
        grad.setColorAt(.4,color('#020e16',0))
        grad.setColorAt(.7,color('#020e16',0))
        grad.setColorAt(1,color('#020e16',220))
        p.fillRect(QRectF(0,0,1440,900),grad)
        self.header(p,'PERSONAL SPACE / MAIN INTERFACE')
        self.thai(p,49,160,'สวัสดีค่ะ วันนี้พร้อมไปด้วยกัน',24,'#d7fff7')
        self.text(p,50,187,'MIRROR ONLINE / HEALTH OVERLAY OFF',9,MUTED)
        if self.message and not self.demo:
            self.text(p,50,217,self.message[:100],10,AMBER,.2)
        if not self.hat_picker:
            self.draw_orb(p,1280,642,55,t)
        if not self.hat_picker:
            self.thai(p,48,690,'“งานวันนี้”  ·  “เลือกหมวก”  ·  “ตรวจสุขภาพ”  ·  “เช็คยอดขาย”  ·  “ขอส่องกระจก”',17,'#c1e7e2')

    def sales_page(self,p,t):
        self.header(p,'COMMERCE INTELLIGENCE / DEMO')
        elapsed=time.monotonic()-self.changed
        move=ease(elapsed/1.8)
        cx=720-420*move
        self.text(p,48,136,'CRYPTOCLOCK / EMERALD EDITION',12,MINT,1.4)
        self.thai(p,48,173,'ยอดขายนาฬิกาคริปโต',29,'#d9fff4')
        # Holographic floor and product turntable, initially at center then left.
        p.save()
        p.setOpacity(.5+.5*move)
        p.setPen(self.pen(CYAN,1,100))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(cx-207,533,414,68))
        p.drawEllipse(QRectF(cx-174,542,348,49))
        for i in range(28):
            a=i*math.tau/28+t*.14
            self.path(p,[(cx+190*math.cos(a),567+30*math.sin(a)),
                         (cx+204*math.cos(a),567+34*math.sin(a))],CYAN,1,False)
        if self.frames:
            image=self.frames[int(elapsed*10)%len(self.frames)]
            p.drawImage(QRectF(cx-270,115,540,540),image)
        else:
            # Visible fallback rather than silently dropping missing product artwork.
            self.panel(p,cx-170,294,340,230,MINT)
            self.text(p,cx-135,398,'CRYPTOCLOCK',28,MINT,1)
            self.text(p,cx-135,431,'PRODUCT ASSET UNAVAILABLE',9,AMBER)
        p.restore()
        self.panel(p,62,638,474,88,MINT)
        self.text(p,82,664,'EMERALD / PRODUCT HOLOGRAM',10,MINT)
        self.thai(p,82,697,'โมเดลจาก Production · ภาพหมุน 360°',17,'#c9e5df')
        p.save()
        p.setOpacity(ease((elapsed-.65)/.9))
        for i,period in enumerate(('daily','monthly','yearly')):
            current,growth=sales_snapshot(period)
            x=600+i*267
            self.panel(p,x,174,250,99,CYAN)
            self.thai(p,x+16,201,{'daily':'วันนี้','monthly':'เดือนนี้','yearly':'ปีนี้'}[period],13,MUTED)
            self.text(p,x+16,237,f'{current:,.0f}',25,'#dffff5',0,True)
            self.text(p,x+16,257,f'THB  /  +{growth:.1f}% VS COMPARISON',8,MINT,.2)
        for i,period in enumerate(('daily','monthly','yearly')):
            x=610+i*155
            selected=period==self.period
            p.fillRect(QRectF(x,286,140,37),color(CYAN,35 if selected else 7))
            self.thai(p,x+18,311,SALES[period]['title']+f'  [{i+1}]',15,CYAN if selected else MUTED)
        self.text(p,1130,309,'DEMO DATA / THB',10,AMBER)
        self.draw_chart(p,600,340,784,371,t)
        p.restore()

    def today_page(self,p,t):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        self.header(p,'TODAY / PERSONAL AGENDA')
        self.thai(p,48,145,'สิ่งที่ต้องทำวันนี้',29,'#dcfff7')
        data=self.tasks.data()
        tasks=data['tasks']
        completed=self.tasks.completed()
        total=len(tasks)
        done=sum(task['id'] in completed for task in tasks)
        self.panel(p,46,178,397,526,CYAN)
        self.text(p,70,209,datetime.now(ZoneInfo('Asia/Bangkok')).strftime('%d / %m / %Y'),16,MINT,1)
        self.text(p,70,234,'DEMO TASKS / EDITABLE LOCAL LIST' if data.get('is_demo') else 'PERSONAL TASK LIST',9,AMBER if data.get('is_demo') else MUTED,.5)
        cx,cy,r=244,399,106
        p.setPen(self.pen(CYAN,6,25))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(cx-r,cy-r,2*r,2*r))
        p.setPen(self.pen(MINT,6,220))
        p.drawArc(QRectF(cx-r,cy-r,2*r,2*r),90*16,-int(360*16*done/max(1,total)))
        self.text(p,cx-61,cy+11,f'{done} / {total}',42,'#dcfff7',0,True)
        self.text(p,cx-52,cy+39,'COMPLETED',10,MUTED,1)
        for i in range(36):
            a=i*math.tau/36+t*.07
            self.path(p,[(cx+119*math.cos(a),cy+119*math.sin(a)),
                         (cx+124*math.cos(a),cy+124*math.sin(a))],CYAN,.8,False)
        self.thai(p,70,576,'ค่อย ๆ ทำทีละอย่างก็พอค่ะ',21,'#c9f2ec')
        self.thai(p,70,612,'กดรายการเพื่อทำเครื่องหมายว่าเสร็จแล้ว',14,MUTED)
        self.thai(p,70,645,'“กลับหน้าหลัก” เพื่อเปิดกระจก',14,CYAN)
        self.text(p,70,682,'BANGKOK / DAILY PROGRESS',9,MUTED,.8)
        for index,task in enumerate(tasks[:5]):
            y=178+index*108
            checked=task['id'] in completed
            shade=MINT if checked else CYAN
            self.panel(p,480,y,905,94,shade)
            p.setPen(self.pen(shade,1.5,210))
            p.setBrush(color(shade,28 if checked else 0))
            p.drawEllipse(QRectF(503,y+29,32,32))
            p.setBrush(Qt.BrushStyle.NoBrush)
            if checked:
                self.path(p,[(510,y+45),(517,y+52),(529,y+37)],MINT,2)
            else:
                self.text(p,513,y+51,str(index+1),14,CYAN,0)
            self.text(p,557,y+31,task['time'],12,MUTED,.8)
            self.thai(p,557,y+64,task['title'],21,MUTED if checked else '#d6f7f0')
            self.text(p,1257,y+52,'DONE' if checked else 'TO DO',10,shade)

    def draw_chart(self,p,x,y,w,h,t):
        self.panel(p,x,y,w,h,CYAN)
        data=SALES[self.period]
        self.text(p,x+23,y+28,data['subtitle'],9,MUTED,.6)
        p.fillRect(QRectF(x+390,y+18,9,9),color(CYAN))
        self.thai(p,x+406,y+29,'ช่วงปัจจุบัน',12,CYAN)
        p.fillRect(QRectF(x+530,y+18,9,9),color('#ae83ff'))
        self.thai(p,x+546,y+29,'ช่วงเปรียบเทียบ',12,'#b69be9')
        max_value=max(*data['current'],*data['previous'])*1.23
        chartx=x+76
        base=y+h-47
        chartw=w-105
        charth=h-113
        for i in range(5):
            yy=base-charth*i/4
            self.path(p,[(chartx,yy),(chartx+chartw,yy)],CYAN,.6,False)
            v=max_value*i/4
            label=f'{v/1e6:.1f}M' if max_value>1e6 else f'{v/1000:.0f}K'
            self.text(p,x+16,yy+4,label,9,MUTED,.1)
        count=len(data['labels'])
        spacing=chartw/count
        bw=min(27,spacing*.28)
        elapsed=min(time.monotonic()-self.period_changed,time.monotonic()-self.changed-.65)
        for i,label in enumerate(data['labels']):
            group=chartx+spacing*(i+.5)
            progress=ease((elapsed-i*.09)/1.2)
            for side,(series,shade) in enumerate((('previous','#ae83ff'),('current',CYAN))):
                value=data[series][i]
                height=charth*value/max_value*progress
                xx=group+(side-.5)*(bw+5)-bw/2
                grad=QLinearGradient(0,base-height,0,base)
                grad.setColorAt(0,color(shade,235))
                grad.setColorAt(1,color(shade,45))
                p.fillRect(QRectF(xx,base-height,bw,height),grad)
                p.fillRect(QRectF(xx,base-height,bw,2),color(shade))
                if side==1 and progress>.95:
                    amount=f'{value/1e6:.2f}M' if value>=1e6 else f'{value/1000:.1f}K'
                    self.text(p,group-17,base-height-12,amount,9,CYAN,0)
            self.text(p,group-14,base+26,label,9,MUTED,0)
        self.text(p,x+23,y+h-12,'ILLUSTRATIVE SALES / NO LIVE BUSINESS CONNECTION',8,AMBER,.3)

    def draw_hat_layer(self,p,t):
        pose = None
        if self.hat_enabled:
            if self.demo:
                pose={'anchor':(720+36*math.sin(t*.4),300+12*math.sin(t*.65)),
                      'width':236.,'angle':0.}
            elif self.image and time.monotonic()-self.last_frame<.4 and not self.message:
                pose=head_pose(self.landmarks,(self.image.width(),self.image.height()))
            if pose is None:
                self.hat_pose=None
            elif self.hat_pose is None or self.demo:
                self.hat_pose=pose
                self.hat_frame_stamp=self.last_frame
            elif self.hat_frame_stamp != self.last_frame:
                old=self.hat_pose
                delta=(pose['angle']-old['angle']+180)%360-180
                self.hat_pose={'anchor':tuple(a*.35+b*.65 for a,b in zip(old['anchor'],pose['anchor'])),
                               'width':old['width']*.35+pose['width']*.65,
                               'angle':old['angle']+delta*.65}
                self.hat_frame_stamp=self.last_frame
            p.save()
            p.setClipRect(QRectF(0,96,1440,649))
            self.hat_renderer.draw(p,self.hat_index,self.hat_pose,self.hat_scale,self.hat_offset)
            p.restore()
        if self.hat_picker:
            self.panel(p,46,615,224,116,CYAN)
            self.text(p,62,637,'HAT STUDIO / 1-5',10,CYAN)
            self.thai(p,62,655,'เลือกแบบที่ชอบได้เลย' if self.hat_pose else 'หันหน้าเข้ากล้องเพื่อลองหมวก',11,MUTED)
            for xx,label in ((62,'↑ สูงขึ้น'),(145,'↓ ต่ำลง')):
                p.fillRect(QRectF(xx,665,75,27),color(CYAN,28))
                self.thai(p,xx+7,684,label,12,CYAN)
            p.fillRect(QRectF(62,700,168,27),color(PINK,25))
            self.thai(p,85,719,'เอาหมวกออก  ×',13,PINK)
            for index,hat in enumerate(HATS):
                x=300+index*218
                self.panel(p,x,615,200,116,MINT if index==self.hat_index else CYAN)
                self.hat_renderer.art[index].render(p,QRectF(x+65,623,72,66))
                self.thai(p,x+16,714,str(index+1)+'  '+hat['name'],14,MINT if index==self.hat_index else '#c1e7e2')
            self.text(p,48,605,'AR HATS / OPENCV HEAD TRACKING    [ ] SIZE',9,MUTED,.6)

    def voice_footer(self,p,t):
        p.fillRect(QRectF(0,745,1440,155),color('#030e17',255))
        self.path(p,[(46,746),(1394,746)],CYAN,.7,False)
        self.draw_orb(p,83,787,21,t)
        labels={'idle':'READY','starting':'OPENING MIC','listening':'LISTENING',
                'thinking':'PROCESSING','synthesizing':'GEMINI LIVE / VOICE','speaking':'SPEAKING','cancelled':'STOPPING'}
        label=labels.get(self.voice_status,'READY')
        if self.mic_latched:
            label += ' / MIC LOCKED'
        self.text(p,124,770,label,9,MINT if self.voice_status=='speaking' else CYAN,1.4)
        text=self.notice if time.monotonic()<self.notice_until else self.response
        if self.mode=='today' and time.monotonic()>=self.notice_until:
            data=self.tasks.data()
            left=sum(task['id'] not in self.tasks.completed() for task in data['tasks'])
            text=f'วันนี้เหลือ {left} รายการตามตารางด้านบนค่ะ กดรายการเพื่อทำเครื่องหมายว่าเสร็จแล้ว'
        self.thai(p,124,794,text,14,AMBER if time.monotonic()<self.notice_until else '#c4e4df',1190)
        if self.heard_text:
            self.thai(p,124,824,'คุณ: '+self.heard_text[:80],11,MUTED)
        else:
            self.thai(p,124,824,'M สั้น: คำสั่งเดียว · M ค้าง: ฟังต่อเนื่อง · M อีกครั้ง: ปิด · ส่งเสียงให้ Google Speech เมื่อเปิดไมค์',10,MUTED)

    def paintEvent(self,event):
        # During QWidget construction resize/paint can occur before shell fields exist.
        if not hasattr(self,'engine'):
            return
        self.studio_button.setVisible(self.mode not in ('dark','studio'))
        dark=self.mode=='dark'
        visible=not dark or time.monotonic()<self.dark_controls_until or self.voice_status in ('listening','thinking','starting')
        for widget in (self.mic_button,self.camera_button,self.input,self.send_button):
            widget.setVisible(visible and not (self.mode=='studio'))
        if self.mode=='health':
            super().paintEvent(event)
        p=QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.mode!='health':
            p.fillRect(self.rect(),QColor('#000000' if dark else '#050e15'))
        s=min(self.width()/1440,self.height()/900)
        p.translate((self.width()-1440*s)/2,(self.height()-900*s)/2)
        p.scale(s,s)
        t=time.monotonic()-self.start
        if dark:
            if self.voice_status=='speaking':
                fade=1-ease((time.monotonic()-self.changed)/2)
                p.setOpacity(fade)
                self.draw_orb(p,720,425,62,t)
                p.setOpacity(1)
            if visible:
                self.voice_footer(p,t)
        else:
            if self.mode=='standby':
                self.background(p,t)
                self.standby_page(p,t)
            elif self.mode=='home':
                self.home_page(p,t)
            elif self.mode=='sales':
                self.background(p,t)
                self.sales_page(p,t)
            elif self.mode=='today':
                self.background(p,t)
                self.today_page(p,t)
            if self.mode in ('home','health'):
                self.draw_hat_layer(p,t)
            if not (self.mode=='studio'):
                self.voice_footer(p,t)
        p.end()
