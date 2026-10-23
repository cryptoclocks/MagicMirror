import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication
from assistant_logic import COMMANDS, CommandEngine, SALES, match_command, sales_summary
from aura_assistant import AssistantMirror
from smartmirror import Mirror


class CommandTests(unittest.TestCase):
    def test_startup_gate_and_complete_route(self):
        engine=CommandEngine()
        self.assertIsNone(engine.handle('ตรวจสุขภาพ')[0])
        self.assertEqual(engine.state,'standby')
        for phrase,state in [('เข้าหน้าหลัก','home'),('เช็คยอดขายนาฬิกาคริปโต','sales'),
                             ('กลับหน้าหลัก','home'),('ตรวจสอขภาพ','health'),('ขอส่องกระจก','dark')]:
            self.assertIsNotNone(engine.handle(phrase)[0])
            self.assertEqual(engine.state,state)
        self.assertIsNone(engine.handle('ตรวจสุขภาพ')[0])
        self.assertEqual(engine.state,'dark')
        engine.handle('กลับหน้าหลัก')
        self.assertEqual(engine.state,'home')

    def test_ten_replies_rotate_and_unmatched_text_stays_put(self):
        self.assertEqual(sum(len(COMMANDS[key]['replies']) for key in ('enter','sales','home','health','dark')),10)
        engine=CommandEngine()
        first=engine.handle('เข้าหน้าหลัก')[1]
        second=engine.handle('เข้าหน้าหลัก')[1]
        self.assertNotEqual(first,second)
        self.assertEqual(engine.handle('เข้าหน้าหลัก')[1],first)
        self.assertIsNone(engine.handle('ไม่ต้องตรวจสุขภาพ')[0])
        self.assertEqual(engine.state,'home')
        self.assertEqual(match_command('เช็กยอดขายนาฬิกาคริปโตครับ'),'sales')
        self.assertEqual(match_command('กลับหน้า'),'home')

    def test_financial_cards_match_their_bars(self):
        for period,data in SALES.items():
            total,growth=sales_summary(period)
            self.assertEqual(total,sum(data['current']))
            self.assertAlmostEqual(growth,(sum(data['current'])/sum(data['previous'])-1)*100)
            self.assertEqual(len(data['labels']),len(data['current']))
            self.assertEqual(len(data['current']),len(data['previous']))


class AssistantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_camera_off_at_startup_until_entry_command(self):
        with patch.object(Mirror,'start_camera') as start:
            window=AssistantMirror(demo=False,mute=True)
            try:
                start.assert_not_called()
                window.execute('ตรวจสุขภาพ',speak=False)
                start.assert_not_called()
                window.execute('เข้าหน้าหลัก',speak=False)
                start.assert_called_once()
                self.assertEqual(window.mode,'home')
                window.execute('ขอส่องกระจก',speak=False)
                self.assertIsNone(window.image)
                self.assertIsNone(window.camera)
            finally:
                window.close()

    def test_pages_render_and_health_only_when_requested(self):
        window=AssistantMirror(demo=True,mute=True)
        try:
            self.assertEqual(window.mode,'standby')
            self.assertFalse(window.grab().isNull())
            for phrase in ('เข้าหน้าหลัก','เช็คยอดขาย','กลับหน้าหลัก','ตรวจสุขภาพ','ขอส่องกระจก'):
                window.execute(phrase,speak=False)
                for w,h in ((1440,900),(800,500)):
                    window.resize(w,h)
                    self.assertFalse(window.grab().isNull())
            # Black mirror really is black after controls and spoken effect disappear.
            image=window.grab().toImage()
            self.assertEqual(image.pixelColor(400,200).name(),'#000000')
            self.assertFalse(window.mic_button.isVisible())
        finally:
            window.close()

    def test_webcam_selection_defers_capture_until_home(self):
        devices=[(0,'MacBook Camera',b'internal'),(1,'USB Webcam',b'usb')]
        with patch('aura_assistant.list_camera_devices',return_value=devices), patch.object(Mirror,'start_camera') as start:
            window=AssistantMirror(mute=True)
            try:
                window.select_camera(1)
                self.assertEqual(window.camera_index,1)
                start.assert_not_called()
                self.assertIn('USB Webcam',window.camera_button.text())
                window.execute('เข้าหน้าหลัก',speak=False)
                start.assert_called_once()
                window.select_camera(0)
                self.assertEqual(window.camera_index,0)
                self.assertEqual(start.call_count,2)
                window.execute('ขอส่องกระจก',speak=False)
                window.select_camera(1)
                self.assertEqual(start.call_count,2)
                window.grab()
                self.assertFalse(window.camera_button.isVisible())
            finally:
                window.close()

    def test_device_identity_survives_index_change(self):
        devices=[(0,'MacBook Camera',b'internal'),(1,'USB Webcam',b'usb')]
        with patch('aura_assistant.list_camera_devices',return_value=devices) as listing, patch.object(Mirror,'start_camera') as start:
            window=AssistantMirror(mute=True)
            try:
                window.select_camera(1)
                listing.return_value=[(0,'USB Webcam',b'usb')]
                window.refresh_camera_devices()
                self.assertEqual(window.camera_index,0)
                self.assertEqual(window.selected_camera_id,b'usb')
                start.assert_not_called()
                listing.return_value=[(0,'MacBook Camera',b'internal')]
                window.refresh_camera_devices()
                self.assertEqual(window.selected_camera_id,b'internal')
            finally:
                window.close()

    def test_sales_tabs_and_suppressed_double_mic_start(self):
        window=AssistantMirror(demo=True,mute=True)
        try:
            window.execute('เข้าหน้าหลัก',speak=False)
            window.execute('เช็คยอดขาย',speak=False)
            key=QKeyEvent(QKeyEvent.Type.KeyPress,Qt.Key.Key_3,Qt.KeyboardModifier.NoModifier)
            window.keyPressEvent(key)
            self.assertEqual(window.period,'yearly')
            window.toggle_mic()
            self.assertEqual(window.voice_status,'starting')
            window.toggle_mic()
            self.assertEqual(window.voice_status,'idle')
            self.assertFalse(window.voice.isRunning())
        finally:
            window.close()


if __name__=='__main__':
    unittest.main()
