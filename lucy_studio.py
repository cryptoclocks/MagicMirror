"""Optional embedded Decart studio. Keys stay in Python; browser gets a short-lived token."""
import json
import os
import secrets
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KEY_FILE = ROOT / '.secrets/decart-api-key'
ASSETS = ROOT / 'web/lucy'


def api_key():
    value = os.environ.get('DECART_API_KEY', '').strip()
    if value:
        return value
    try:
        return KEY_FILE.read_text().strip()
    except FileNotFoundError:
        return ''


def save_key(value):
    value = value.strip()
    if not value or any(c.isspace() for c in value):
        raise ValueError('API key ต้องไม่มีช่องว่าง')
    KEY_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(str(KEY_FILE), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as target:
        target.write(value)
    KEY_FILE.chmod(0o600)


def mint_token(key, origin):
    body = json.dumps({'expiresIn': 120, 'allowedModels': ['lucy-2.5'],
                       'allowedOrigins': [origin],
                       'constraints': {'realtime': {'maxSessionDuration': 120}}}).encode()
    request = urllib.request.Request('https://api.decart.ai/v1/client/tokens', data=body,
        headers={'X-API-KEY': key, 'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(request, timeout=20) as response:
        result = json.load(response)
    token = result.get('apiKey') or result.get('token')
    if not isinstance(token, str) or not token:
        raise ValueError('Invalid token response')
    return token


class StudioServer:
    """Loopback-only, unguessable URL, exact assets, same-origin token endpoint."""
    def __init__(self):
        from local_ai import LocalAI
        from motion_buffer import MotionBuffer
        self.ai = LocalAI()
        self.motion = MotionBuffer()
        self.prefix = '/' + secrets.token_urlsafe(24) + '/'
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def respond(self, status, data, content_type='application/json'):
                self.send_response(status)
                self.send_header('Content-Type', content_type)
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Referrer-Policy', 'no-referrer')
                self.end_headers()
                try:
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def valid_host(self):
                return self.headers.get('Host') == owner.host

            def do_GET(self):
                if not self.valid_host() or not self.path.startswith(owner.prefix):
                    return self.respond(404, b'{}')
                name = self.path[len(owner.prefix):]
                if name == 'config':
                    return self.respond(200, json.dumps({'hasKey': bool(api_key()),'localAI':owner.ai.available()}).encode())
                if name.startswith('ai/status/'):
                    return self.respond(200,json.dumps(owner.ai.snapshot(name.split('/')[-1])).encode())
                files = {'': ('index.html', 'text/html; charset=utf-8'),
                         'studio.bundle.js': ('studio.bundle.js', 'text/javascript'),
                         'studio.bundle.js.LEGAL.txt': ('studio.bundle.js.LEGAL.txt', 'text/plain'),
                         'style.css': ('style.css', 'text/css')}
                if name not in files:
                    return self.respond(404, b'{}')
                file, mime = files[name]
                try:
                    self.respond(200, (ASSETS / file).read_bytes(), mime)
                except FileNotFoundError:
                    self.respond(404, b'{}')

            def do_POST(self):
                route=self.path[len(owner.prefix):] if self.path.startswith(owner.prefix) else ''
                if (not self.valid_host() or route not in ('token','ai/start','ai/cancel','ai/face','ai/motion/begin','ai/motion/step')
                        or self.headers.get('Origin') != owner.origin):
                    return self.respond(403, b'{}')
                if route=='ai/cancel':
                    owner.ai.close()
                    owner.motion.reset()
                    return self.respond(200,b'{}')
                if route in ('ai/start','ai/face','ai/motion/begin','ai/motion/step'):
                    try:
                        length=int(self.headers.get('Content-Length','0'))
                        if not 0<length<4*1024*1024:raise ValueError('ขนาดคำขอไม่ถูกต้อง')
                        data=json.loads(self.rfile.read(length))
                        if not isinstance(data,dict):raise ValueError('คำขอไม่ถูกต้อง')
                        if route=='ai/motion/begin':
                            owner.motion.begin(data)
                            return self.respond(200,b'{}')
                        if route=='ai/motion/step':
                            return self.respond(200,json.dumps({'image':owner.motion.step(data)}).encode())
                        if route=='ai/face':
                            import base64,cv2,numpy as np
                            frame=cv2.imdecode(np.frombuffer(base64.b64decode(data.get('image',''),validate=True),np.uint8),cv2.IMREAD_COLOR)
                            if frame is None or frame.shape[:2]!=(512,512):raise ValueError('ภาพต้องมีขนาด 512x512')
                            detector=cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_frontalface_alt2.xml')
                            faces=detector.detectMultiScale(cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY),1.1,5)
                            face=[int(v) for v in max(faces,key=lambda b:b[2]*b[3])] if len(faces) else None
                            return self.respond(200,json.dumps({'face':face}).encode())
                        job=owner.ai.start(data)
                        return self.respond(200,json.dumps({'id':job}).encode())
                    except (ValueError,RuntimeError,KeyError,TypeError) as exc:
                        return self.respond(400,json.dumps({'error':str(exc)}).encode())
                key = api_key()
                if not key:
                    return self.respond(409, json.dumps({'error':'กรุณาตั้ง Decart API key จากปุ่มด้านบน'}).encode())
                try:
                    token = mint_token(key, owner.origin)
                    self.respond(200, json.dumps({'apiKey': token}).encode())
                except urllib.error.HTTPError as exc:
                    message = ('API key ไม่ถูกต้องหรือไม่มีสิทธิ์' if exc.code in (401,403)
                               else 'Decart ปฏิเสธคำขอ โปรดตรวจเครดิตหรือสถานะบริการ')
                    self.respond(502, json.dumps({'error':message}).encode())
                except Exception:
                    # Never return upstream exception bodies, URLs, or credentials.
                    self.respond(502, json.dumps({'error':'เชื่อมต่อ Decart ไม่สำเร็จ กรุณาลองใหม่'}).encode())
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        self.host = '127.0.0.1:' + str(self.server.server_port)
        self.origin = 'http://' + self.host
        self.url = self.origin + self.prefix
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.ai.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)


def create_studio(parent, on_back):
    # Optional imports: a missing WebEngine must not prevent ordinary mirror startup.
    from PySide6.QtCore import QUrl, Qt
    from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QInputDialog, QLineEdit, QApplication
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
    from PySide6.QtWebEngineWidgets import QWebEngineView

    class LocalPage(QWebEnginePage):
        def acceptNavigationRequest(self, url, *_):
            return url.toString().startswith(self.studio_url) or url.toString() == 'about:blank'

        def javaScriptConsoleMessage(self, *_):
            pass  # SDK diagnostic messages can include connection identifiers.

    class Studio(QWidget):
        def __init__(self):
            super().__init__(parent)
            self.server = StudioServer()
            self.closed = False
            layout = QVBoxLayout(self)
            layout.setContentsMargins(14, 8, 14, 4)
            bar = QHBoxLayout()
            bar.addWidget(QLabel('AURA · STYLE STUDIO / LOCAL + LUCY'))
            bar.addStretch()
            key = QPushButton('ตั้ง API key · เฉพาะ Cloud')
            key.clicked.connect(self.configure_key)
            back = QPushButton('กลับหน้าหลัก')
            back.clicked.connect(on_back)
            bar.addWidget(key); bar.addWidget(back)
            layout.addLayout(bar)
            self.view = QWebEngineView(self)
            self.profile = QWebEngineProfile(QApplication.instance())
            self.page = LocalPage(self.profile, self.view)
            self.page.destroyed.connect(self.profile.deleteLater)
            self.page.studio_url = self.server.url
            self.page.featurePermissionRequested.connect(self.permission)
            self.view.setPage(self.page)
            self.view.setUrl(QUrl(self.server.url))
            layout.addWidget(self.view)
            self.setStyleSheet('QLabel {color:#77fff1;} QWidget {background:#050e15;}')

        def permission(self, origin, feature):
            allowed = (origin.toString().rstrip('/') == self.server.origin and
                       feature == QWebEnginePage.Feature.MediaVideoCapture)
            self.page.setFeaturePermission(origin, feature,
                QWebEnginePage.PermissionPolicy.PermissionGrantedByUser if allowed else
                QWebEnginePage.PermissionPolicy.PermissionDeniedByUser)

        def configure_key(self):
            text, ok = QInputDialog.getText(self, 'Decart API key',
                'คีย์จาก platform.decart.ai · เก็บเฉพาะเครื่องนี้', QLineEdit.EchoMode.Password)
            if ok and text.strip():
                try:
                    save_key(text)
                except (ValueError, OSError):
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.warning(self, 'บันทึกคีย์ไม่ได้', 'ตรวจว่าคีย์ไม่มีช่องว่าง และโฟลเดอร์ .secrets เขียนได้')
                    return
                self.page.runJavaScript('window.refreshConfig && window.refreshConfig()')

        def shutdown(self):
            if self.closed:
                return
            self.closed = True
            self.page.runJavaScript('window.shutdownStudio && window.shutdownStudio()')
            self.view.setUrl(QUrl('about:blank'))
            self.server.close()
            self.hide()
            self.deleteLater()

    return Studio()
