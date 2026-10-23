"""Subtle automatic camera retouch using the existing 68 tracked landmarks."""
import time
import cv2
import numpy as np


class BeautyFilter:
    def __init__(self):
        self.reset()

    def reset(self):
        self.last_points = None
        self.last_seen = -100.
        self.previous_time = None
        self.frame_shape = None
        self.strength = 0.
        self.last_strength = 0.

    def apply(self, frame, payload, now=None):
        now = time.monotonic() if now is None else now
        if self.frame_shape != frame.shape:
            self.reset()
            self.frame_shape = frame.shape
        dt = min(.1, max(0., now-self.previous_time)) if self.previous_time is not None else 1./30
        self.previous_time = now
        tracked = bool(payload is not None and payload.get('points') is not None)
        normalized = np.asarray(payload['points'], dtype=np.float32) if tracked else None
        if tracked and (normalized.shape != (68, 2) or not np.isfinite(normalized).all()):
            tracked = False
        if tracked:
            # Reset on a different subject/large jump instead of warping between faces.
            if self.last_points is not None:
                span = np.linalg.norm(self.last_points[16]-self.last_points[0])
                if np.linalg.norm(normalized.mean(axis=0)-self.last_points.mean(axis=0))>span*.65:
                    self.strength = 0.
            self.strength += (1.-self.strength) * (1.-np.exp(-dt/.09))
            self.last_seen = now
            self.last_points = normalized.copy()
            self.last_strength = self.strength
        elif self.last_points is not None and 0 <= now-self.last_seen < .16:
            # Bridge a brief missed frame with a short fade, never an indefinite
            # frozen face. Do not expose held landmarks to HUD/hat consumers.
            normalized = self.last_points
            self.strength = self.last_strength * (1.-(now-self.last_seen)/.16)
        else:
            self.last_points = None
            self.strength = 0.
            return frame, payload
        height, width = frame.shape[:2]
        points = normalized * (width, height)
        span = float(np.linalg.norm(points[16] - points[0]))
        if span < 45:
            return frame, payload
        eye = (points[36:42].mean(axis=0) + points[42:48].mean(axis=0)) / 2
        up = eye - points[8]
        # Extend the skin mask to the forehead without touching hair/background.
        forehead = points[17:27] + up * .35
        outline = cv2.convexHull(np.vstack((points[:17], forehead)).astype(np.float32))
        all_points = np.vstack((outline.reshape(-1, 2), points))
        lo = np.maximum(np.floor(all_points.min(axis=0) - span * .22), 0).astype(int)
        hi = np.minimum(np.ceil(all_points.max(axis=0) + span * .22), (width, height)).astype(int)
        x0, y0 = lo; x1, y1 = hi
        if x1 <= x0 or y1 <= y0:
            return frame, payload
        # Work on a bounded face crop; all detection still uses the original pixels.
        crop = frame[y0:y1, x0:x1]
        factor = min(1., 400. / max(crop.shape[:2]))
        size = (max(1, round(crop.shape[1] * factor)), max(1, round(crop.shape[0] * factor)))
        work = cv2.resize(crop, size)
        p = ((points - lo) * factor).astype(np.float32)
        face_width = span * factor
        mask = np.zeros(work.shape[:2], np.float32)
        hull = ((outline.reshape(-1, 2) - lo) * factor).astype(np.int32)
        cv2.fillConvexPoly(mask, hull, 1.)
        # Protect features from smoothing and brightening.
        for ids in (range(36, 42), range(42, 48), range(48, 60), range(31, 36)):
            cv2.fillConvexPoly(mask, cv2.convexHull(p[list(ids)].astype(np.int32)), 0.)
        brows = np.zeros_like(mask)
        for ids in (range(17, 22), range(22, 27)):
            cv2.polylines(brows, [p[list(ids)].astype(np.int32)], False, 1., max(1, round(face_width * .017)), cv2.LINE_AA)
        brows = cv2.GaussianBlur(brows, (0, 0), max(.7, face_width * .006))
        mask *= 1. - np.minimum(1., brows * 2.)
        mask = cv2.GaussianBlur(mask, (0, 0), max(1., face_width * .014))
        smooth = cv2.bilateralFilter(work, 5, 22, 5).astype(np.float32)
        original = work.astype(np.float32)
        # Gentle luminance lift with highlight protection, retaining the skin hue.
        lab = cv2.cvtColor(work, cv2.COLOR_BGR2LAB).astype(np.float32)
        lab[:, :, 0] += 4. * (1. - lab[:, :, 0] / 255.)
        bright = cv2.cvtColor(np.clip(lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR).astype(np.float32)
        retouched = original + mask[:, :, None] * ((smooth - original) * .22 + (bright - original)) * self.strength
        retouched *= 1. - brows[:, :, None] * (.12 * self.strength)
        # Local inverse cheek warp. Compact support leaves the rest of the frame intact.
        axis = p[16] - p[0]
        axis /= max(float(np.linalg.norm(axis)), 1.)
        centers = [(p[2] + p[4]) / 2, (p[12] + p[14]) / 2]
        radius = face_width * .30
        def displacement(coords):
            delta = np.zeros_like(coords, dtype=np.float32)
            for center, sign in zip(centers, (-1., 1.)):
                distance = np.sum((coords - center) ** 2, axis=-1) / (radius * radius)
                weight = np.maximum(0., 1. - distance) ** 2
                delta += weight[..., None] * axis * (sign * face_width * .018 * self.strength)
            return delta
        yy, xx = np.indices(work.shape[:2], dtype=np.float32)
        grid = np.stack((xx, yy), axis=-1)
        source = grid + displacement(grid)
        warped = cv2.remap(np.clip(retouched, 0, 255).astype(np.uint8), source[:, :, 0], source[:, :, 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
        result = frame.copy()
        # Upscale only the effect delta, preserving the original image detail
        # and avoiding resampling flicker when the crop changes by one pixel.
        delta = warped.astype(np.float32) - work.astype(np.float32)
        result[y0:y1, x0:x1] = np.clip(crop.astype(np.float32) +
            cv2.resize(delta, (x1-x0, y1-y0)), 0, 255).astype(np.uint8)
        if not tracked:
            return result, payload
        # Solve source = destination + displacement(destination) for overlays.
        destination = p.copy()
        for _ in range(5):
            destination = p - displacement(destination)
        adjusted = dict(payload)
        adjusted['points'] = ((destination / factor + lo) / (width, height)).tolist()
        return result, adjusted
