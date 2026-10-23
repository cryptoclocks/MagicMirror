import unittest
import cv2
import numpy as np
from unittest.mock import patch
from face_landmarks import LandmarkTracker, map_to_view, mesh_edges


class LandmarkTests(unittest.TestCase):
    def test_camera_crop_coordinates_land_in_exact_video_positions(self):
        result=map_to_view([(0,0),(.5,.5),(1,1)],(1280,720))
        np.testing.assert_allclose(result,[(-80,0),(720,450),(1520,900)])
        portrait=map_to_view([(.5,.5)],(720,1280))
        np.testing.assert_allclose(portrait,[(720,450)])

    def test_failed_fits_and_lost_optical_flow_hide_points(self):
        tracker=LandmarkTracker()
        tracker.facemark=type('FailedFit',(),{'fit':lambda *args:(False,[])})()
        gray=np.zeros((360,640),np.uint8)
        self.assertIsNone(tracker.process(gray,(100,100,100,100),now=1))
        tracker.points=np.zeros((68,2),np.float32)
        tracker.last_fit=1
        tracker.edges=((0,1),)
        with patch('cv2.calcOpticalFlowPyrLK',return_value=(None,None,None)):
            self.assertIsNone(tracker.process(gray,now=2))
        self.assertEqual(tracker.edges,())

    def test_mesh_connectivity_keeps_eye_and_lip_contours(self):
        rng=np.random.default_rng(13)
        edges=mesh_edges(rng.uniform(20,300,(68,2)).astype(np.float32))
        for edge in ((36,41),(42,47),(48,59),(60,67),(0,1),(15,16)):
            self.assertIn(edge,edges)
        self.assertTrue(all(0<=a<b<68 for a,b in edges))


class TrackingContinuityTests(unittest.TestCase):
    def make_tracker(self):
        tracker=LandmarkTracker.__new__(LandmarkTracker)
        tracker.reset()
        tracker.facemark=type('MissedFit',(),{'fit':lambda *args:(False,[])})()
        rng=np.random.default_rng(17)
        tracker.points=rng.uniform((120,100),(270,250),(68,2)).astype(np.float32)
        tracker.previous_gray=rng.integers(0,256,(360,640),dtype=np.uint8)
        tracker.last_fit=tracker.last_detection=1.
        tracker.edges=((0,1),)
        return tracker

    def test_partial_flow_loss_recovers_jaw_from_remaining_points(self):
        tracker=self.make_tracker()
        before=tracker.points.copy()
        moved=(before+(5.,2.)).astype(np.float32).reshape(-1,1,2)
        status=np.zeros((68,1),np.uint8);status[:32]=1
        backward=before.reshape(-1,1,2)
        returns=[(moved,status,None),(backward,np.ones_like(status),None)]
        with patch('cv2.calcOpticalFlowPyrLK',side_effect=returns):
            payload=tracker.process(tracker.previous_gray,now=1.1)
        self.assertIsNotNone(payload)
        np.testing.assert_allclose(tracker.points,before+(5.,2.),atol=.001)

    def test_moving_face_survives_detector_gap_and_expires_without_refit(self):
        tracker=self.make_tracker()
        initial=tracker.points.copy()
        first=tracker.previous_gray.copy()
        for i in range(1,11):
            matrix=np.float32([[1,0,i*2],[0,1,i]])
            gray=cv2.warpAffine(first,matrix,(640,360))
            self.assertIsNotNone(tracker.process(gray,now=1.+i*.066))
        np.testing.assert_allclose(tracker.points,initial+(20.,10.),atol=1.)
        self.assertIsNone(tracker.process(gray,now=2.2))

    def test_bad_fit_does_not_jump_away_from_valid_flow(self):
        tracker=self.make_tracker()
        before=tracker.points.copy()
        candidate=before+(60,0)
        tracker.facemark=type('BadFit',(),{'fit':lambda *args:(True,[candidate[None]])})()
        shape=(68,1)
        with patch('cv2.calcOpticalFlowPyrLK',side_effect=[
                (before.reshape(-1,1,2),np.ones(shape,np.uint8),None),
                (before.reshape(-1,1,2),np.ones(shape,np.uint8),None)]):
            self.assertIsNotNone(tracker.process(tracker.previous_gray,(70,50,280,280),now=1.1))
        np.testing.assert_allclose(tracker.points,before,atol=.001)


if __name__=='__main__':
    unittest.main()
