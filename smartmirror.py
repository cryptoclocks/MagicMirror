#!/usr/bin/env python3
"""A camera mirror with a procedural, fictional biometric HUD. No health inference."""
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo
import math
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QApplication, QWidget
from face_landmarks import LandmarkTracker, map_to_view
from beauty_filter import BeautyFilter
import health_graphics
from health_profile import PULSE_BPM,RESPIRATIONS_PER_MINUTE,OXYGEN_PERCENT,TEMPERATURE_C,ENERGY_VISUAL_SCORE,SLEEP_HOURS,SLEEP_GOAL_HOURS,cycle

CYAN = '#56f5ed'
MINT = '#8cffbc'
PINK = '#ff6aa8'
AMBER = '#ffc77a'
MUTED = '#71959d'

# Decorative face topology in normalized bounding-box coordinates.
# These points are artwork, not detected anatomical landmarks.
MARKER_POINTS = (
    (.50,.04), (.25,.08), (.75,.08), (.10,.23), (.90,.23),
    (.05,.43), (.95,.43), (.04,.61), (.96,.61),
    (.11,.79), (.89,.79), (.27,.93), (.73,.93), (.50,.99),
    (.33,.23), (.50,.20), (.67,.23),
    (.18,.36), (.35,.39), (.65,.39), (.82,.36),
    (.14,.48), (.29,.44), (.41,.49), (.30,.54),
    (.59,.49), (.71,.44), (.86,.48), (.70,.54),
    (.50,.43), (.45,.62), (.55,.62), (.50,.65),
    (.24,.64), (.76,.64), (.35,.69), (.65,.69),
    (.29,.79), (.42,.76), (.50,.74), (.58,.76), (.71,.79),
    (.43,.83), (.57,.83), (.50,.89),
)


def marker_edges():
    subdivision = cv2.Subdiv2D((0, 0, 1001, 1001))
    points = np.array(MARKER_POINTS, dtype=np.float32) * 1000
    for point in points:
        subdivision.insert(tuple(float(v) for v in point))
    edges = set()
    for triangle in subdivision.getTriangleList():
        vertices = triangle.reshape(3, 2)
        ids = [int(np.argmin(np.sum((points - v)**2, axis=1))) for v in vertices]
        if any(np.linalg.norm(points[i]-v) > .1 for i,v in zip(ids,vertices)):
            continue
        for a,b in ((ids[0],ids[1]),(ids[1],ids[2]),(ids[2],ids[0])):
            edges.add(tuple(sorted((a,b))))
    return tuple(sorted(edges))


MARKER_EDGES = marker_edges()


def marker_alpha(elapsed):
    """Two-second pulse starting every five seconds, relative to face acquisition."""
    if elapsed < 0:
        return 0.0
    phase = elapsed % 5.0
    return max(0.0, min(1.0, phase / .3, (2.0 - phase) / .4))


def color(value, alpha=255):
    c = QColor(value)
    c.setAlpha(max(0, min(255, int(alpha))))
    return c


class FaceTracker:
    """Smooth one subject; briefly hold missed detections, then explicitly lose lock."""
    def __init__(self):
        self.box = None
        self.last_seen = -100.0
        self.acquired = 0.0

    def update(self, boxes, now):
        if len(boxes):
            if self.box is None or now - self.last_seen > .8:
                chosen = max(boxes, key=lambda b: b[2] * b[3])
                self.box = tuple(float(v) for v in chosen)
                self.acquired = now
            else:
                cx, cy = self.box[0] + self.box[2] / 2, self.box[1] + self.box[3] / 2
                chosen = min(boxes, key=lambda b: (b[0] + b[2] / 2 - cx)**2 + (b[1] + b[3] / 2 - cy)**2)
                self.box = tuple(a * .68 + float(b) * .32 for a, b in zip(self.box, chosen))
            self.last_seen = now
        elif now - self.last_seen > .8:
            self.box = None
        return self.box


class Camera(QThread):
    frame = Signal(QImage, object, float, object)
    issue = Signal(str)

    def __init__(self, index):
        super().__init__()
        self.index = index

    def run(self):
        backend = cv2.CAP_AVFOUNDATION if sys.platform == 'darwin' else cv2.CAP_ANY
        cap = cv2.VideoCapture(self.index, backend)
        try:
            # macOS may return before its first camera permission prompt is answered.
            for attempt in range(10):
                if cap.isOpened() or self.isInterruptionRequested():
                    break
                cap.release()
                self.msleep(500)
                cap = cv2.VideoCapture(self.index, backend)
            if self.isInterruptionRequested():
                return
            if not cap.isOpened():
                self.issue.emit('CAMERA BLOCKED / Press C for camera settings, then R to retry')
                return
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            cap.set(cv2.CAP_PROP_FPS, 30)
            detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_alt2.xml')
            if detector.empty():
                self.issue.emit('Face detector missing. Reinstall opencv-python.')
                return
            tracker = FaceTracker()
            beauty = BeautyFilter()
            try:
                landmark_tracker = LandmarkTracker()
                landmark_error = ''
            except (RuntimeError, cv2.error) as exc:
                landmark_tracker = None
                landmark_error = str(exc)
            count = 0
            failures = 0
            while not self.isInterruptionRequested():
                ok, raw = cap.read()
                if not ok:
                    failures += 1
                    if failures >= 10:
                        self.issue.emit('CAMERA DISCONNECTED / Press R to retry or D for demo')
                        break
                    self.msleep(50)
                    continue
                failures = 0
                raw = cv2.flip(raw, 1)
                # Bound detection cost independently of the capture resolution.
                h, w = raw.shape[:2]
                scale = 640 / w
                now = time.monotonic()
                small = cv2.resize(raw, (640, max(1, round(h * scale))))
                gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                selected = None
                if count % 3 == 0:
                    boxes = detector.detectMultiScale(cv2.equalizeHist(gray), scaleFactor=1.12, minNeighbors=5, minSize=(60, 60))
                    old_acquired = tracker.acquired
                    tracker.update([tuple(float(v) / scale for v in b) for b in boxes], now)
                    if landmark_tracker and old_acquired != tracker.acquired:
                        landmark_tracker.reset()
                        beauty.reset()
                    if len(boxes) and tracker.box:
                        tx,ty,tw,th = [v*scale for v in tracker.box]
                        selected = min(boxes,key=lambda b:(b[0]+b[2]/2-tx-tw/2)**2+(b[1]+b[3]/2-ty-th/2)**2)
                landmark_data = None
                if landmark_tracker:
                    landmark_data = landmark_tracker.process(gray, selected, now)
                elif landmark_error:
                    landmark_data = {'points':None, 'error':landmark_error}
                raw, landmark_data = beauty.apply(raw, landmark_data, now)
                rgb = cv2.cvtColor(raw, cv2.COLOR_BGR2RGB)
                image = QImage(rgb.data, w, h, rgb.strides[0], QImage.Format.Format_RGB888).copy()
                normalized = tuple(v / (w if i % 2 == 0 else h) for i, v in enumerate(tracker.box)) if tracker.box else None
                self.frame.emit(image, normalized, tracker.acquired, landmark_data)
                count += 1
                self.msleep(12)
        except Exception as exc:
            self.issue.emit('CAMERA ERROR / ' + str(exc))
        finally:
            cap.release()


class Mirror(QWidget):
    def __init__(self, camera=0, demo=False, fullscreen=False):
        super().__init__()
        self.setWindowTitle('AURA / Smart Mirror')
        self.resize(1440, 900)
        self.setMinimumSize(800, 500)
        self.start = time.monotonic()
        self.demo = demo
        self.camera_index = camera
        self.camera = None
        self.image = None
        self.box = None
        self.landmarks = None
        self.acquired = self.start
        self.last_frame = 0.0
        self.message = ''
        self.opacity = .9
        self.target = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(33)
        if not demo:
            self.start_camera()
        if fullscreen:
            self.showFullScreen()

    def start_camera(self):
        self.stop_camera()
        self.message = 'CONNECTING CAMERA'
        self.image = None
        self.box = None
        self.landmarks = None
        self.camera = Camera(self.camera_index)
        self.camera.frame.connect(self.on_frame)
        self.camera.issue.connect(self.on_issue)
        self.camera.start()

    def stop_camera(self):
        if self.camera:
            self.camera.requestInterruption()
            # Keep ownership until capture releases; never destroy a live QThread.
            self.camera.wait()
            self.camera = None

    def on_frame(self, image, box, acquired, landmarks=None):
        self.image, self.box, self.acquired = image, box, acquired
        self.landmarks = landmarks
        self.last_frame = time.monotonic()
        self.message = ''

    def on_issue(self, message):
        self.message = message
        self.box = None
        self.landmarks = None

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Q, Qt.Key.Key_Escape):
            if key == Qt.Key.Key_Escape and self.isFullScreen():
                self.showNormal()
            else:
                self.close()
        elif key == Qt.Key.Key_F:
            self.showNormal() if self.isFullScreen() else self.showFullScreen()
        elif key == Qt.Key.Key_D:
            self.demo = not self.demo
            self.target = None
            if self.demo:
                self.stop_camera()
                self.acquired = time.monotonic()
            else:
                self.start_camera()
        elif key == Qt.Key.Key_C and sys.platform == 'darwin':
            QDesktopServices.openUrl(QUrl('x-apple.systempreferences:com.apple.preference.security?Privacy_Camera'))
        elif key == Qt.Key.Key_R and not self.demo:
            self.start_camera()
        elif key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.opacity = min(1, self.opacity + .1)
        elif key == Qt.Key.Key_Minus:
            self.opacity = max(.2, self.opacity - .1)

    def closeEvent(self, event):
        self.timer.stop()
        self.stop_camera()
        event.accept()

    def pen(self, shade=CYAN, width=1, alpha=255):
        return QPen(color(shade, alpha), width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)

    def text(self, p, x, y, value, size=12, shade=CYAN, spacing=1.5, bold=False):
        font = QFont('Menlo', size)
        font.setPixelSize(size)
        font.setBold(bold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
        p.setFont(font)
        p.setPen(color(shade))
        p.drawText(QPointF(x, y), str(value))

    def path(self, p, points, shade=CYAN, width=1.2, glow=True):
        if not points:
            return
        line = QPainterPath(QPointF(*points[0]))
        for point in points[1:]:
            line.lineTo(*point)
        if glow:
            p.setPen(self.pen(shade, width + 7, 12))
            p.drawPath(line)
            p.setPen(self.pen(shade, width + 3, 28))
            p.drawPath(line)
        p.setPen(self.pen(shade, width))
        p.drawPath(line)

    def panel(self, p, x, y, w, h, shade=CYAN):
        p.fillRect(QRectF(x, y, w, h), color('#04171e', 155))
        p.setPen(self.pen(shade, .7, 65))
        p.drawRect(QRectF(x, y, w, h))
        self.path(p, [(x, y + 14), (x, y), (x + 28, y)], shade, 1.7)
        self.path(p, [(x + w - 28, y + h), (x + w, y + h), (x + w, y + h - 14)], shade, 1.7)

    def heart(self, p, cx, cy, size, t):
        beat = max(0, math.cos(math.tau * cycle(t,PULSE_BPM))) ** 12
        s = size * (1 + .13 * beat)
        pts = []
        for i in range(81):
            a = i * math.tau / 80
            x = 16 * math.sin(a)**3
            y = 13 * math.cos(a) - 5 * math.cos(2*a) - 2 * math.cos(3*a) - math.cos(4*a)
            pts.append((cx + x * s / 32, cy - y * s / 32))
        self.path(p, pts, PINK, 1.5 + beat)
        self.path(p, [(cx-s*.6, cy), (cx-s*.22, cy), (cx-s*.11, cy-s*.12), (cx, cy+s*.16), (cx+s*.12, cy-s*.25), (cx+s*.24, cy), (cx+s*.6, cy)], PINK, 1)

    def ecg(self, p, x, y, w, t):
        pts = []
        for i in range(int(w)):
            phase = ((i-(w-1)) / 125 + cycle(t,PULSE_BPM) + .4) % 1
            v = (5 * math.exp(-((phase-.18)/.05)**2)
                 - 8 * math.exp(-((phase-.35)/.025)**2)
                 + 32 * math.exp(-((phase-.4)/.018)**2)
                 - 13 * math.exp(-((phase-.45)/.025)**2)
                 + 8 * math.exp(-((phase-.68)/.08)**2))
            pts.append((x+i, y-v))
        self.path(p, pts, PINK, 1.4)

    def demo_background(self, p, t):
        # A deliberately abstract mannequin: no sample face images or recorded camera frames.
        grad = QLinearGradient(0, 0, 1440, 900)
        grad.setColorAt(0, QColor('#081720'))
        grad.setColorAt(.5, QColor('#152c36'))
        grad.setColorAt(1, QColor('#050c16'))
        p.fillRect(QRectF(0, 0, 1440, 900), grad)
        cx = 720 + 36 * math.sin(t * .4)
        cy = 395 + 12 * math.sin(t * .65)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#1c3640'))
        p.drawEllipse(QRectF(cx-225, cy+190, 450, 410))
        p.setBrush(QColor('#29434b'))
        p.drawRoundedRect(QRectF(cx-53, cy+100, 106, 165), 40, 40)
        p.drawEllipse(QRectF(cx-118, cy-154, 236, 310))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(self.pen('#45616a', 1, 100))
        p.drawArc(QRectF(cx-88, cy-80, 176, 205), 195*16, 150*16)
        self.path(p, [(cx-69,cy-20),(cx-35,cy-25),(cx-20,cy-19)], '#637e85', 1, False)
        self.path(p, [(cx+20,cy-19),(cx+35,cy-25),(cx+69,cy-20)], '#637e85', 1, False)
        self.path(p, [(cx,cy-9),(cx-10,cy+40),(cx+10,cy+43)], '#637e85', 1, False)
        self.path(p, [(cx-33,cy+78),(cx,cy+83),(cx+33,cy+78)], '#637e85', 1, False)
        return (cx-118, cy-154, 236, 310)

    def face_markers(self, p, box, elapsed, t):
        alpha = marker_alpha(elapsed)
        if alpha <= 0:
            return
        x,y,w,h = box
        if self.demo:
            points = [(x+u*w,y+v*h) for u,v in MARKER_POINTS]
            edges = MARKER_EDGES
        elif self.landmarks and self.landmarks.get('points') and self.image:
            points = map_to_view(self.landmarks['points'],(self.image.width(),self.image.height()))
            edges = self.landmarks['edges']
        else:
            return
        p.save()
        p.setOpacity(p.opacity()*alpha)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for a,b in edges:
            self.path(p,[points[a],points[b]],CYAN,.85)
        for index,(px,py) in enumerate(points):
            pulse = .8+.2*math.sin(t*4+index*.7)
            radius = 10*pulse
            gradient = QRadialGradient(QPointF(px,py),radius)
            gradient.setColorAt(0,color('#caffff',235))
            gradient.setColorAt(.22,color(CYAN,185))
            gradient.setColorAt(1,color(CYAN,0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(gradient)
            p.drawEllipse(QRectF(px-radius,py-radius,radius*2,radius*2))
            p.setBrush(color('#e0ffff',240))
            p.drawEllipse(QRectF(px-1.7,py-1.7,3.4,3.4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        self.text(p,x+w/2-94,y+h+104,'DEMO MESH' if self.demo else '68 LANDMARKS / OPENCV',9,CYAN,.6)
        p.restore()

    def face_hud(self, p, box, t, scan):
        x, y, w, h = box
        cx, cy = x+w/2, y+h/2
        r = max(w*.72, h*.61)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for radius, speed, shade in [(r, 14, CYAN), (r+13, -19, CYAN), (r+27, 7, MINT)]:
            p.setPen(self.pen(shade, 1, 140))
            for a in (0, 120, 240):
                p.drawArc(QRectF(cx-radius,cy-radius,radius*2,radius*2), int((a+t*speed)*16), 78*16)
        for i in range(60):
            a = i * math.tau/60
            rr = r + 33
            length = 9 if i % 5 == 0 else 3
            self.path(p, [(cx+rr*math.cos(a),cy+rr*math.sin(a)), (cx+(rr+length)*math.cos(a),cy+(rr+length)*math.sin(a))], CYAN, .7, False)
        for sx, sy in [(-1,-1),(1,-1),(-1,1),(1,1)]:
            xx, yy = cx+sx*w*.57, cy+sy*h*.56
            self.path(p, [(xx-sx*22,yy),(xx,yy),(xx,yy-sy*22)], CYAN, 2)
        sy = y + (math.sin(t*1.5)*.5+.5)*h
        gradient = QLinearGradient(0,sy-25,0,sy+3)
        gradient.setColorAt(0,color(CYAN,0))
        gradient.setColorAt(1,color(CYAN,40))
        p.fillRect(QRectF(x,sy-25,w,28),gradient)
        self.path(p, [(x,sy),(x+w,sy)], CYAN, 1.2)
        self.text(p, cx-86, y+h+65, 'SUBJECT 01 / LOCKED', 10, MINT)
        self.text(p, cx-88, y+h+84, 'VISUAL TRACKING ONLY', 9, MUTED)

    def draw_metric(self, p, x, y, title, value, unit, shade, t, kind):
        self.panel(p, x,y,258,139,shade)
        self.text(p,x+18,y+25,title,10,MUTED)
        self.text(p,x+18,y+72,value,39,shade,0,True)
        self.text(p,x+112,y+69,unit,10,shade)
        self.text(p,x+18,y+123,'SIMULATED',8,MUTED)
        health_graphics.draw(self,p,x,y,shade,t,kind)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor('#050e15'))
        scale = min(self.width()/1440, self.height()/900)
        p.translate((self.width()-1440*scale)/2,(self.height()-900*scale)/2)
        p.scale(scale,scale)
        t = time.monotonic()-self.start
        now = time.monotonic()
        box = None
        if self.demo:
            box = self.demo_background(p,t)
        elif self.image:
            iw, ih = self.image.width(), self.image.height()
            s = max(1440/iw,900/ih)
            dx,dy=(1440-iw*s)/2,(900-ih*s)/2
            p.save()
            p.setClipRect(QRectF(0,0,1440,900))
            p.drawImage(QRectF(dx,dy,iw*s,ih*s),self.image)
            p.restore()
            if self.box and now-self.last_frame < 1.5 and not self.message:
                a,b,c,d = self.box
                box = (dx+a*iw*s,dy+b*ih*s,c*iw*s,d*ih*s)
            p.fillRect(QRectF(0,0,1440,900),color('#03141e',65))
        # Edge shades preserve contrast while leaving the face visible.
        for left in (True,False):
            grad=QLinearGradient(0 if left else 1440,0,450 if left else 990,0)
            grad.setColorAt(0,color('#020d15',220))
            grad.setColorAt(1,color('#020d15',0))
            p.fillRect(QRectF(0 if left else 990,0,450,900),grad)
        p.setOpacity(self.opacity)
        p.setBrush(Qt.BrushStyle.NoBrush)
        # Fine technical background grid.
        p.setPen(self.pen(CYAN,.5,14))
        for x in range(40,1440,40):
            p.drawLine(QPointF(x,100),QPointF(x,810))
        for y in range(100,811,40):
            p.drawLine(QPointF(40,y),QPointF(1400,y))
        self.text(p,46,51,'A U R A',28,'#e0fffc',2,True)
        self.text(p,47,74,'BIO-INTERFACE / SMART MIRROR',9,MUTED,2)
        self.text(p,545,48,'HUMAN SYSTEMS / LIVE INTERFACE',11,CYAN,2)
        self.text(p,593,70,'DEMO VALUES  /  NO HEALTH ANALYSIS',9,AMBER)
        self.text(p,1195,49,datetime.now(ZoneInfo('Asia/Bangkok')).strftime('%H:%M:%S'),19,'#d9fffa')
        self.text(p,1195,72,'BANGKOK / OFFLINE',9,MUTED)
        self.path(p,[(46,94),(1394,94)],CYAN,.7,False)
        p.fillRect(QRectF(46,94,102,2),color(CYAN))
        active = box is not None
        elapsed = now-self.acquired
        tracking_ready = active and elapsed >= 2.4
        status = 'SIMULATION / TRACKING' if self.demo else ('DEMO HEALTH / FACE LOCK' if active else 'DEMO HEALTH / SEARCHING FACE')
        p.setBrush(color(MINT if active else AMBER))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(49,119,5,5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        self.text(p,65,127,status,10,MINT if active else AMBER)
        self.text(p,1120,127,'SESSION 01 / PRIVATE',10,MUTED)
        if not self.demo and active and not (self.landmarks and self.landmarks.get('points')):
            note = 'LANDMARK MODEL UNAVAILABLE / RUN SETUP' if self.landmarks and self.landmarks.get('error') else 'ACQUIRING FACIAL LANDMARKS'
            self.text(p,490,151,note,9,AMBER,.3)
        if active:
            # Smooth display geometry separately from detection cadence.
            if self.target is None:
                self.target=box
            self.target=tuple(a*.78+b*.22 for a,b in zip(self.target,box))
            self.face_hud(p,self.target,t,min(1,elapsed/2.4))
            self.face_markers(p,self.target,elapsed,t)
            cx=self.target[0]+self.target[2]/2
            cy=self.target[1]+self.target[3]/2
            for endx,endy,side in [(310,266,-1),(310,477,-1),(1130,257,1),(1130,427,1),(1130,597,1)]:
                startx=cx+side*self.target[2]*.6
                self.path(p,[(startx,cy),(endx-side*32,endy),(endx,endy)],CYAN,.8,False)
                p.setPen(self.pen(CYAN,1))
                p.drawEllipse(QRectF(startx-3,cy-3,6,6))
        else:
            self.target=None
            p.setPen(self.pen(CYAN,1,90))
            p.drawEllipse(QRectF(570,245,300,355))
            self.text(p,580,580,'ALIGN FACE FOR TRACKING',12,CYAN)
        # Display values are independent of face lock: this is a visual health demo.
        val = str
        self.panel(p,52,185,258,191,PINK)
        self.text(p,70,212,'CARDIAC ACTIVITY',10,MUTED)
        self.heart(p,258,250,43,t)
        self.text(p,70,268,val(PULSE_BPM),49,PINK,0,True)
        self.text(p,158,265,'BPM',12,PINK)
        self.ecg(p,70,322,221,t)
        self.text(p,70,358,'SIMULATED ECG / NOT A SENSOR',8,MUTED)
        self.draw_metric(p,52,407,'RESPIRATORY RATE',val(RESPIRATIONS_PER_MINUTE),'/ MIN',CYAN,t,'breath')
        self.panel(p,52,578,258,128,'#bba2ff')
        self.text(p,70,605,'REST & RECOVERY',10,MUTED)
        self.text(p,70,652,f'{SLEEP_HOURS:.1f}',39,'#bba2ff',0,True)
        self.text(p,164,649,'HRS',10,'#bba2ff')
        health_graphics.sleep(self,p,52,578,t,'#bba2ff')
        p.fillRect(QRectF(70,674,219,3),color('#bba2ff',35))
        p.fillRect(QRectF(70,674,219*SLEEP_HOURS/SLEEP_GOAL_HOURS,3),color('#bba2ff'))
        self.text(p,70,695,f'SIMULATED / GOAL {SLEEP_GOAL_HOURS} HOURS',8,MUTED)
        self.draw_metric(p,1130,185,'OXYGEN SATURATION',val(OXYGEN_PERCENT),'% SpO2',MINT,t,'oxygen')
        self.draw_metric(p,1130,355,'BODY TEMPERATURE',val(f'{TEMPERATURE_C:.1f}'),'C',AMBER,t,'temp')
        self.draw_metric(p,1130,525,'ENERGY / DEMO SCORE',val(ENERGY_VISUAL_SCORE),'/ 100',CYAN,t,'energy')
        self.text(p,1146,697,'FICTIONAL WELLNESS TELEMETRY',8,MUTED)
        self.panel(p,480,753,480,54,CYAN)
        if active:
            self.text(p,503,775,'INTERFACE SYNCHRONIZED' if tracking_ready else 'BUILDING VISUAL PROFILE',10,CYAN)
            self.text(p,503,794,'Breathe slowly. Take a moment for yourself.',9,'#bed9d9',.3)
        else:
            self.text(p,503,775,'READY WHEN YOU ARE',10,CYAN)
            self.text(p,503,794,'Look toward the camera to activate the HUD.',9,'#bed9d9',.3)
        if self.message and not self.demo:
            self.text(p,390,726,self.message[:85],10,AMBER,.1)
        self.path(p,[(46,833),(1394,833)],CYAN,.7,False)
        self.text(p,47,860,'F  FULLSCREEN     D  DEMO / CAMERA     R  RETRY   C  CAMERA SETTINGS   - / +  HUD     Q  QUIT',10,MUTED,.5)
        self.text(p,47,883,'SIMULATED DATA / FOR VISUAL EXPERIENCE ONLY / NO RECORDING',8,AMBER,.6)
        self.text(p,1203,862,'AURA / v1.0',10,CYAN)
        self.text(p,1203,882,'FACE TRACKING HUD',8,MUTED)
        p.end()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--camera',type=int,default=0,help='Camera device index')
    parser.add_argument('--fullscreen',action='store_true')
    parser.add_argument('--demo',action='store_true',help='Animated mannequin preview without a camera')
    parser.add_argument('--preview',type=Path,help='Save a demo PNG and exit (no camera)')
    parser.add_argument('--page', choices=('standby','home','health','sales','today','dark'), default='standby', help='Initial preview/presentation page')
    parser.add_argument('--mute', action='store_true', help='Disable spoken responses and interface sounds')
    args=parser.parse_args()
    app=QApplication(sys.argv[:1])
    sys.modules.setdefault('smartmirror', sys.modules[__name__])
    from aura_assistant import AssistantMirror
    from assistant_logic import COMMANDS
    window=AssistantMirror(args.camera,args.demo or bool(args.preview),args.fullscreen,args.mute or bool(args.preview))
    if args.page != 'standby':
        window.engine.state='home'
        key={'home':'enter','health':'health','sales':'sales','today':'tasks','dark':'dark'}[args.page]
        window.execute(COMMANDS[key]['phrase'],speak=False)
    window.show()
    if args.preview:
        window.start-=6
        window.acquired-=6
        window.changed-=4.6
        window.period_changed-=4
        def capture():
            args.preview.parent.mkdir(parents=True,exist_ok=True)
            ok=window.grab().save(str(args.preview))
            window.close()
            app.exit(0 if ok else 1)
        QTimer.singleShot(180,capture)
    return app.exec()


if __name__=='__main__':
    sys.exit(main())
