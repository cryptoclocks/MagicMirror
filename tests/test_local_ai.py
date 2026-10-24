import base64
import unittest
from unittest.mock import patch
import cv2
import numpy as np
from local_ai import LocalAI


def encoded(image):
    return base64.b64encode(cv2.imencode('.png',image)[1]).decode()


class LocalAITests(unittest.TestCase):
    def test_invalid_payload_never_starts_worker(self):
        controller=LocalAI()
        with patch.object(controller,'available',return_value=True),patch('local_ai.subprocess.Popen') as spawn:
            for data in ({'prompt':''},{'prompt':'hat','image':'not base64','mask':''},
                         {'prompt':'hat','image':encoded(np.zeros((16,16,3),np.uint8)),'mask':''},
                         {'prompt':'hat','image':encoded(np.zeros((512,512,3),np.uint8)),
                          'mask':encoded(np.zeros((512,512),np.uint8))}):
                with self.subTest(data_length=len(str(data))):
                    with self.assertRaises(ValueError):controller.start(data)
            spawn.assert_not_called()

    def test_only_one_job_can_run_and_unknown_id_has_no_result(self):
        controller=LocalAI();controller.state={'status':'running','id':'existing'}
        data={'prompt':'hat','image':encoded(np.zeros((512,512,3),np.uint8)),
              'mask':encoded(np.full((512,512),255,np.uint8))}
        with patch.object(controller,'available',return_value=True),patch('local_ai.subprocess.Popen') as spawn:
            with self.assertRaises(RuntimeError):controller.start(data)
            spawn.assert_not_called()
        self.assertEqual(controller.snapshot('other'),{'status':'cancelled'})
        controller.close();self.assertEqual(controller.state['status'],'idle')


class MotionBufferTests(unittest.TestCase):
    def test_generated_patch_follows_motion_and_keeps_unselected_camera(self):
        from motion_buffer import MotionBuffer
        rng=np.random.default_rng(73)
        raw=rng.integers(50,190,(512,512,3),dtype=np.uint8)
        mask=np.zeros((512,512),np.uint8);cv2.circle(mask,(230,250),30,255,-1)
        edited=raw.copy();edited[mask>0]=(10,10,250)
        motion=MotionBuffer();motion.begin({'image':encoded(raw),'output':encoded(edited),'mask':encoded(mask)})
        moved=cv2.warpAffine(raw,np.float32([[1,0,8],[0,1,4]]),(512,512),borderMode=cv2.BORDER_REFLECT_101)
        result=cv2.imdecode(np.frombuffer(base64.b64decode(motion.step({'image':encoded(moved)})),np.uint8),1)
        selected=(result[:,:,2]>210)&(result[:,:,0]<60)&(result[:,:,1]<60)
        yy,xx=np.where(selected)
        self.assertAlmostEqual(float(xx.mean()),238,delta=2)
        self.assertAlmostEqual(float(yy.mean()),254,delta=2)
        motion.reset()
        with self.assertRaises(ValueError):motion.step({'image':encoded(moved)})
