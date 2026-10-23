import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from unittest.mock import patch
from PySide6.QtCore import QObject,Signal,Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication
from assistant_logic import CommandEngine,SALES,match_command,sales_spoken_report
from aura_assistant import AssistantMirror


class FakeVoice(QObject):
    status=Signal(str)
    level=Signal(float)
    heard=Signal(str)
    failed=Signal(str)
    finished=Signal()
    def __init__(self,parent=None):
        super().__init__(parent)
        self.running=False
        self.interrupted=False
        self.wait_forever=False
    def start(self):
        self.running=True
        self.status.emit('listening')
    def isRunning(self): return self.running
    def requestInterruption(self): self.interrupted=True
    def isInterruptionRequested(self): return self.interrupted
    def wait(self,*args): return True
    def command(self,text):
        self.heard.emit(text)
        self.running=False
        self.finished.emit()


class ReportTests(unittest.TestCase):
    def test_health_report_is_scripted_and_has_sleep_and_water_advice(self):
        e=CommandEngine();e.handle('เข้าหน้าหลัก')
        for phrase in ('รายงานสุขภาพ','ช่วยสรุปสุขภาพให้หน่อย','รายงานผลสุขภาพ'):
            self.assertEqual(match_command(phrase),'health_report')
            action,reply=e.handle(phrase)
            self.assertEqual(action,'health_report')
            self.assertEqual(e.state,'health')
            self.assertIn('เจ็ดชั่วโมง',reply)
            self.assertIn('น้ำ',reply)
            self.assertIn('เดโม',reply)
        self.assertIsNone(match_command('ไม่ต้องรายงานสุขภาพ'))

    def test_spoken_sales_and_dashboard_snapshot_use_the_same_figures(self):
        e=CommandEngine();e.handle('เข้าหน้าหลัก')
        for variant in range(2):
            action,reply=e.handle('เช็คยอดขายนาฬิกาคริปโต')
            self.assertEqual(action,'sales')
            for period in ('daily','monthly','yearly'):
                self.assertIn(f"{SALES[period]['current'][-1]:,.0f}",reply)
            self.assertNotIn('ตัวอย่าง',reply)
            self.assertNotIn('โฮโลแกรม',reply)
            self.assertNotIn('มาแล้ว',reply)
            self.assertEqual(reply,sales_spoken_report(variant))


class LatchedMicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])

    def test_hold_latches_release_keeps_listening_reply_pauses_and_next_m_stops(self):
        with patch('aura_assistant.VoiceInput',FakeVoice):
            w=AssistantMirror(demo=True,mute=True)
            press=QKeyEvent(QKeyEvent.Type.KeyPress,Qt.Key.Key_M,Qt.KeyboardModifier.NoModifier)
            release=QKeyEvent(QKeyEvent.Type.KeyRelease,Qt.Key.Key_M,Qt.KeyboardModifier.NoModifier)
            try:
                w.keyPressEvent(press);w.begin_capture()
                first=w.voice
                w.lock_microphone() # Equivalent to the half-second timer firing.
                self.assertTrue(w.mic_latched)
                self.assertTrue(first.wait_forever)
                w.keyReleaseEvent(release)
                self.assertTrue(w.mic_latched)
                first.command('เข้าหน้าหลัก')
                self.assertEqual(w.mode,'home')
                self.assertTrue(w.mic_resume_timer.isActive())
                busy=object();w.speaker=busy
                w.resume_continuous_mic()
                self.assertIs(w.voice,first)
                w.speaker=None
                w.resume_continuous_mic();w.begin_capture()
                second=w.voice
                self.assertIsNot(second,first)
                self.assertTrue(second.wait_forever)
                w.keyPressEvent(press)
                self.assertFalse(w.mic_latched)
                self.assertTrue(second.interrupted)
                self.assertFalse(w.mic_resume_timer.isActive())
                w.keyReleaseEvent(release)
            finally:
                w.speaker=None
                w.close()

    def test_short_tap_stays_one_shot_and_repeated_key_events_do_not_toggle(self):
        with patch('aura_assistant.VoiceInput',FakeVoice):
            w=AssistantMirror(demo=True,mute=True)
            try:
                w.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress,Qt.Key.Key_M,Qt.KeyboardModifier.NoModifier))
                voice=w.voice
                w.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress,Qt.Key.Key_M,Qt.KeyboardModifier.NoModifier,'m',True))
                self.assertIs(w.voice,voice)
                w.keyReleaseEvent(QKeyEvent(QKeyEvent.Type.KeyRelease,Qt.Key.Key_M,Qt.KeyboardModifier.NoModifier))
                self.assertFalse(w.m_hold_timer.isActive())
                self.assertFalse(w.mic_latched)
                self.assertFalse(voice.wait_forever)
            finally: w.close()


if __name__=='__main__': unittest.main()
