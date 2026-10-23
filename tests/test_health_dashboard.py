import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import time
import unittest
from unittest.mock import patch
import numpy as np
from PySide6.QtGui import QImage,QPainter
from PySide6.QtWidgets import QApplication
from aura_assistant import AssistantMirror
from smartmirror import Mirror,CYAN


class HealthDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])

    def test_values_visible_without_camera_face_lock_or_scan_delay(self):
        w=AssistantMirror(demo=True,mute=True)
        try:
            w.execute('เข้าหน้าหลัก',speak=False)
            w.execute('เลือกหมวก',speak=False)
            w.execute('ตรวจสุขภาพ',speak=False)
            self.assertFalse(w.hat_picker)
            w.demo=False
            for box in (None,(.3,.2,.3,.5)):
                image=QImage(1280,720,QImage.Format.Format_RGB32)
                image.fill(0)
                w.on_frame(image,box,time.monotonic(),None)
                with patch.object(w,'text',wraps=w.text) as text:
                    self.assertFalse(w.grab().isNull())
                labels={str(call.args[3]) for call in text.call_args_list}
                self.assertTrue({'98','36.6','86','16','5.5'}<=labels,labels)
                self.assertNotIn('--',labels)
        finally: w.close()

    def test_each_infographic_is_different_and_animates_with_fixed_values(self):
        view=Mirror(demo=True)
        icons={}
        try:
            for kind in ('oxygen','breath','temp','energy'):
                snapshots=[]
                for t in (0.,.9):
                    image=QImage(258,139,QImage.Format.Format_ARGB32)
                    image.fill(0)
                    p=QPainter(image)
                    p.setRenderHint(QPainter.RenderHint.Antialiasing)
                    view.draw_metric(p,0,0,'METRIC','98','U',CYAN,t,kind)
                    p.end()
                    raw=np.frombuffer(image.constBits(),np.uint8).reshape(139,image.bytesPerLine())
                    snapshots.append(raw[30:93,170*4:250*4].copy())
                self.assertGreater(np.count_nonzero(snapshots[0]!=snapshots[1]),15,kind)
                icons[kind]=snapshots[0]
            for a,b in (('oxygen','breath'),('oxygen','energy'),('temp','energy'),('breath','temp')):
                self.assertGreater(np.count_nonzero(icons[a]!=icons[b]),100)
        finally: view.close()


if __name__=='__main__': unittest.main()
