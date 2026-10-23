import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from PySide6.QtWidgets import QApplication
from assistant_logic import CommandEngine,match_command
from daily_tasks import DailyTasks
from aura_assistant import AssistantMirror


class TodayTests(unittest.TestCase):
    def test_natural_task_queries_and_ambiguity(self):
        for phrase in ('ขอสิ่งที่ต้องทำวันนี้','วันนี้ต้องทำอะไร','ช่วยเช็คงานวันนี้ให้หน่อย','ตารางงานวันนี้'):
            self.assertEqual(match_command(phrase),'tasks')
        self.assertIsNone(match_command('ไม่ต้องเปิดงานวันนี้'))
        self.assertIsNone(match_command('งานวันนี้แล้วตรวจสุขภาพ'))
        e=CommandEngine()
        self.assertIsNone(e.handle('ขอสิ่งที่ต้องทำวันนี้')[0])
        e.handle('เข้าหน้าหลัก')
        action,reply=e.handle('ขอสิ่งที่ต้องทำวันนี้')
        self.assertEqual((action,e.state),('tasks','today'))
        self.assertIn('เดโม',reply)

    def test_completed_tasks_persist_per_day_and_are_removed_from_voice_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'tasks.json';state=Path(directory)/'state.json'
            source.write_text(json.dumps({'is_demo':True,'tasks':[{'id':'a','time':'09:00','title':'ตรวจออเดอร์'}]},ensure_ascii=False))
            store=DailyTasks(source,state)
            self.assertIn('9 นาฬิกา ตรวจออเดอร์',store.spoken_report())
            store.toggle('a','2026-10-22')
            self.assertEqual(DailyTasks(source,state).completed('2026-10-22'),{'a'})
            self.assertEqual(store.completed('2026-10-23'),set())
            store.toggle('a','2026-10-22')
            self.assertEqual(store.completed('2026-10-22'),set())
            with patch('daily_tasks.today',return_value='2026-10-22'):
                store.toggle('a')
                self.assertIn('ทำครบแล้ว',store.spoken_report())
                self.assertNotIn('ตรวจออเดอร์',store.spoken_report())
                store.toggle('a')
            store.toggle('unknown','2026-10-22')
            self.assertEqual(store.completed('2026-10-22'),set())

    def test_agenda_renders_without_camera(self):
        app=QApplication.instance() or QApplication([])
        window=AssistantMirror(demo=True,mute=True)
        try:
            window.execute('เข้าหน้าหลัก',speak=False)
            window.execute('ขอสิ่งที่ต้องทำวันนี้',speak=False)
            self.assertEqual(window.mode,'today')
            self.assertIsNone(window.camera)
            for width,height in ((1440,900),(800,500)):
                window.resize(width,height)
                self.assertFalse(window.grab().isNull())
        finally:window.close()


if __name__=='__main__':unittest.main()
