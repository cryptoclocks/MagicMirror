import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import math
import time
import unittest
import numpy as np
from PySide6.QtGui import QImage,QPainter
from PySide6.QtWidgets import QApplication
from assistant_logic import CommandEngine,match_command
from aura_assistant import AssistantMirror
from hats import HatRenderer,head_pose
from hat_catalog import parse_hat_choice


def sample_points():
    points=np.full((68,2),.5)
    points[36:42]=(.4,.4)
    points[42:48]=(.6,.4)
    points[8]=(.5,.8)
    points[0]=(.25,.55)
    points[16]=(.75,.55)
    return points


class HatGeometryTests(unittest.TestCase):
    def test_pose_tracks_measured_translation_scale_and_roll(self):
        points=sample_points()
        before=head_pose({'points':points.tolist()},(1000,1000))
        shifted=head_pose({'points':(points+[.03,.04]).tolist()},(1000,1000))
        np.testing.assert_allclose(np.array(shifted['anchor'])-before['anchor'],[43.2,57.6])
        angle=math.radians(22)
        rotation=np.array([[math.cos(angle),-math.sin(angle)],[math.sin(angle),math.cos(angle)]])
        rotated=(points-.5)@rotation.T+.5
        after=head_pose({'points':rotated.tolist()},(1000,1000))
        self.assertAlmostEqual(after['angle'],22)
        self.assertAlmostEqual(after['width'],before['width'])
        enlarged=head_pose({'points':((points-.5)*1.2+.5).tolist()},(1000,1000))
        self.assertAlmostEqual(enlarged['width']/before['width'],1.2)
        self.assertIsNone(head_pose(None,(1000,1000)))

    def test_hat_intents_and_removal_keep_other_modes(self):
        for text in ('เลือกหมวก','ช่วยลองหมวกให้หน่อย','ขอใส่หมวก','เลือกหมวด'):
            self.assertEqual(match_command(text),'hats')
        for text,index in (('หมวกเบอร์สอง',1),('เลือกหมวกใบที่สาม',2),('ใส่หมวกแก๊ป',0),('ลองมงกุฎ',4),('หมวก๕',4)):
            self.assertEqual(match_command(text),'hat_select')
            self.assertEqual(parse_hat_choice(text),index)
        self.assertEqual(match_command('เอาหมวกออก'),'hat_off')
        self.assertEqual(match_command('ถอดหมวกให้หน่อย'),'hat_off')
        self.assertIsNone(match_command('ไม่ต้องเอาหมวกออก'))
        self.assertIsNone(match_command('เลือกหมวกแล้วดูยอดขาย'))
        engine=CommandEngine()
        self.assertIsNone(engine.handle('เลือกหมวก')[0])
        engine.handle('เข้าหน้าหลัก');engine.handle('หมวกเบอร์สอง')
        self.assertEqual(engine.hat_choice,1)
        engine.handle('ตรวจสุขภาพ');engine.handle('เอาหมวกออก')
        self.assertEqual(engine.state,'health')


class HatRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_five_transparent_assets_render(self):
        hats=HatRenderer()
        self.assertEqual(len(hats.art),5)
        for index,art in enumerate(hats.art):
            self.assertTrue(art.isValid())
            image=QImage(600,600,QImage.Format.Format_ARGB32)
            image.fill(0)
            p=QPainter(image)
            hats.draw(p,index,{'anchor':(300,350),'width':170,'angle':15})
            p.end()
            self.assertEqual(image.pixelColor(0,0).alpha(),0)
            raw=np.frombuffer(image.constBits(),np.uint8).reshape(600,image.bytesPerLine())
            self.assertGreater(np.count_nonzero(raw[:,3::4]),100)

    def test_selection_and_removal_and_no_frozen_hat_after_face_loss(self):
        w=AssistantMirror(demo=True,mute=True)
        try:
            w.execute('เข้าหน้าหลัก',speak=False)
            w.execute('เลือกหมวก',speak=False)
            self.assertTrue(w.hat_enabled)
            w.grab()
            self.assertIsNotNone(w.hat_pose)
            w.execute('หมวกเบอร์สี่',speak=False)
            self.assertEqual(w.hat_index,3)
            w.demo=False
            w.image=QImage(1000,1000,QImage.Format.Format_RGB32)
            w.image.fill(0)
            w.last_frame=time.monotonic()
            w.landmarks={'points':sample_points().tolist()}
            w.grab()
            self.assertIsNotNone(w.hat_pose)
            w.landmarks=None
            w.grab()
            self.assertIsNone(w.hat_pose)
            w.execute('เอาหมวกออก',speak=False)
            self.assertFalse(w.hat_enabled)
            self.assertFalse(w.hat_picker)
        finally:
            w.close()


if __name__=='__main__':
    unittest.main()
