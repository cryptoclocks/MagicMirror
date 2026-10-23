import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
import cv2
import numpy as np
from PySide6.QtWidgets import QApplication
from smartmirror import FaceTracker, Mirror, marker_alpha, MARKER_EDGES, MARKER_POINTS


class TrackingTests(unittest.TestCase):
    def test_acquisition_smoothing_and_loss(self):
        tracker = FaceTracker()
        self.assertEqual(tracker.update([(20, 20, 100, 100), (250, 20, 50, 50)], 1), (20, 20, 100, 100))
        updated = tracker.update([(30, 20, 100, 100)], 1.1)
        self.assertGreater(updated[0], 20)
        self.assertLess(updated[0], 30)
        self.assertIsNotNone(tracker.update([], 1.5))
        self.assertIsNone(tracker.update([], 2))
        tracker.update([(400, 0, 80, 80)], 3)
        self.assertEqual(tracker.acquired, 3)

    def test_bundled_detector_runs(self):
        detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.assertFalse(detector.empty())
        self.assertEqual(len(detector.detectMultiScale(np.zeros((480, 640), dtype=np.uint8))), 0)


class MarkerTests(unittest.TestCase):
    def test_five_second_cycle_with_fade_and_hidden_gap(self):
        self.assertEqual(marker_alpha(-1),0)
        self.assertEqual(marker_alpha(0),0)
        self.assertAlmostEqual(marker_alpha(.15),.5)
        self.assertEqual(marker_alpha(1),1)
        self.assertAlmostEqual(marker_alpha(1.8),.5)
        for t in (2,3,4.99):
            self.assertEqual(marker_alpha(t),0)
        for t in (.15,1,1.8,3):
            self.assertAlmostEqual(marker_alpha(t),marker_alpha(t+5))
        self.assertTrue(MARKER_EDGES)
        self.assertTrue(all(0 <= a < b < len(MARKER_POINTS) for a,b in MARKER_EDGES))


class RenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_demo_and_search_render_at_different_sizes(self):
        mirror = Mirror(demo=True)
        mirror.acquired -= 5
        try:
            for demo in (True, False):
                mirror.demo = demo
                for w, h in ((1440, 900), (800, 500), (1920, 1080)):
                    mirror.resize(w, h)
                    image = mirror.grab().toImage()
                    self.assertFalse(image.isNull())
                    self.assertEqual(image.width(), w)
        finally:
            mirror.close()


if __name__ == '__main__':
    unittest.main()
