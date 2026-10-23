import unittest
import cv2
import numpy as np
from beauty_filter import BeautyFilter
from assistant_logic import CommandEngine


class BeautyTests(unittest.TestCase):
    def test_no_face_and_invalid_tracking_leave_camera_untouched(self):
        frame = np.full((240, 320, 3), 100, np.uint8)
        for payload in (None, {'points': None}, {'points': [[float('nan'), 0]] * 68}):
            image, data = BeautyFilter().apply(frame, payload)
            np.testing.assert_array_equal(image, frame)
            self.assertIs(data, payload)

    def test_unmatched_command_is_silent_and_preserves_page(self):
        engine = CommandEngine()
        engine.handle('เข้าหน้าหลัก')
        self.assertEqual(engine.handle('สวัสดีครับ'), (None, ''))
        self.assertEqual(engine.state, 'home')


class BeautyContinuityTests(unittest.TestCase):
    def test_brief_loss_fades_then_removes_effect_without_held_overlay(self):
        rng=np.random.default_rng(29)
        frame=rng.integers(60,180,(240,320,3),dtype=np.uint8)
        points=rng.uniform((.32,.30),(.65,.70),(68,2)).astype(np.float32)
        points[0]=(.25,.45);points[16]=(.75,.45);points[8]=(.5,.82)
        payload={'points':points.tolist(),'edges':((0,1),)}
        beauty=BeautyFilter()
        for i in range(12):
            active,adjusted=beauty.apply(frame,payload,now=1+i/30)
        self.assertGreater(beauty.strength,.95)
        last=beauty.last_seen
        fading,hidden=beauty.apply(frame,None,now=last+.08)
        self.assertIsNone(hidden)
        self.assertGreater(np.abs(fading.astype(float)-frame).sum(),0)
        self.assertLess(beauty.strength,.51)
        off,hidden=beauty.apply(frame,None,now=last+.20)
        np.testing.assert_array_equal(off,frame)
        self.assertIsNone(hidden)
        self.assertIsNone(beauty.last_points)
        # Outside the face remains exactly the original camera image.
        np.testing.assert_array_equal(active[:5],frame[:5])

    def test_new_camera_resolution_clears_previous_face(self):
        beauty=BeautyFilter()
        beauty.last_points=np.full((68,2),.5,np.float32)
        beauty.last_seen=1.
        beauty.frame_shape=(480,640,3)
        frame=np.full((240,320,3),120,np.uint8)
        output,payload=beauty.apply(frame,None,now=1.01)
        self.assertIs(output,frame)
        self.assertIsNone(beauty.last_points)
