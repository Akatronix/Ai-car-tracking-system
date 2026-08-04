# """
# Dual tracker: Norfair (default) or Centroid+Kalman fallback.
# Maintains vehicle identity across frames.
# """

# import numpy as np
# from collections import OrderedDict
# import config


# # ═══════════════════════════════════════════════════════════
# #  NORFAIR TRACKER WRAPPER
# # ═══════════════════════════════════════════════════════════

# class NorfairTrack:
#     """Lightweight wrapper around a Norfair tracked object."""
#     _next_id = 0

#     def __init__(self, norfair_obj, class_name, confidence):
#         NorfairTrack._next_id += 1
#         self.track_id = NorfairTrack._next_id
#         self.norfair_obj = norfair_obj
#         self.class_name = class_name
#         self.confidence = confidence
#         self.speed_kmh = 0.0
#         self.direction = None
#         self.in_intrusion_zone = False
#         self.crossed_counting_line = False
#         self.history = []
#         self.hits = 1
#         self.confirmed = False
#         self._update_bbox()

#     def _update_bbox(self):
#         pts = self.norfair_obj.estimate[0]
#         self.bbox = (int(pts[0]), int(pts[1]), int(pts[2]), int(pts[3]))
#         self.centroid = (
#             (self.bbox[0] + self.bbox[2]) / 2.0,
#             (self.bbox[1] + self.bbox[3]) / 2.0,
#         )
#         self.history.append(self.centroid)
#         if len(self.history) > 60:
#             self.history.pop(0)

#     def refresh(self, class_name, confidence):
#         self.class_name = class_name
#         self.confidence = confidence
#         self.hits += 1
#         if self.hits >= config.MIN_HITS_TO_CONFIRM:
#             self.confirmed = True
#         self._update_bbox()


# class NorfairTracker:
#     """Wraps Norfair Tracker for the system interface."""

#     def __init__(self):
#         self.tracks = {}  # norfair_id -> NorfairTrack
#         self.tracker = None
#         self._init_norfair()

#     def _init_norfair(self):
#         try:
#             from norfair import Tracker as NorfairTrackerCls
#             self.tracker = NorfairTrackerCls(
#                 distance_function="euclidean",
#                 distance_threshold=config.NORFAIR_DISTANCE_THRESHOLD,
#             )
#             print("[Tracker] Norfair initialized")
#         except ImportError:
#             print("[Tracker] Norfair not installed — falling back to Centroid tracker")
#             self.tracker = None

#     def update(self, detections):
#         """detections: list of {bbox, class_name, confidence}"""
#         if self.tracker is None:
#             return []

#         from norfair import Detection as NorfairDetection

#         norfair_dets = []
#         det_meta = []
#         for d in detections:
#             pts = np.array([[d["bbox"][0], d["bbox"][1]],
#                             [d["bbox"][2], d["bbox"][3]]], dtype=float)
#             scores = np.array([d["confidence"]])
#             norfair_dets.append(NorfairDetection(points=pts, scores=scores))
#             det_meta.append({"class_name": d["class_name"], "confidence": d["confidence"]})

#         tracked_objects = self.tracker.update(detections=norfair_dets)

#         # Build result list and update internal state
#         result = []
#         current_ids = set()

#         for obj in tracked_objects:
#             oid = obj.id
#             current_ids.add(oid)

#             # Find matching detection to get class/confidence
#             best_meta = {"class_name": "unknown", "confidence": 0.0}
#             if obj.last_detection is not None:
#                 idx = None
#                 if hasattr(obj, "last_detection"):
#                     for i, nd in enumerate(norfair_dets):
#                         if np.allclose(nd.points, obj.last_detection.points, atol=1):
#                             idx = i
#                             break
#                 if idx is not None:
#                     best_meta = det_meta[idx]

#             if oid in self.tracks:
#                 self.tracks[oid].refresh(best_meta["class_name"], best_meta["confidence"])
#             else:
#                 self.tracks[oid] = NorfairTrack(obj, best_meta["class_name"], best_meta["confidence"])

#             result.append(self.tracks[oid])
#             if self.tracks[oid].confirmed is False:
#                 self.tracks[oid].confirmed = True

#         # Remove stale tracks
#         stale = [k for k in self.tracks if k not in current_ids]
#         for k in stale:
#             del self.tracks[k]

#         return result

#     def reset(self):
#         self.tracks.clear()
#         NorfairTrack._next_id = 0
#         if self.tracker:
#             try:
#                 from norfair import Tracker as NorfairTrackerCls
#                 self.tracker = NorfairTrackerCls(
#                     distance_function="euclidean",
#                     distance_threshold=config.NORFAIR_DISTANCE_THRESHOLD,
#                 )
#             except Exception:
#                 pass


# # ═══════════════════════════════════════════════════════════
# #  CENTROID + KALMAN FILTER TRACKER (fallback)
# # ═══════════════════════════════════════════════════════════

# class KalmanFilter1D:
#     def __init__(self, pos):
#         self.x = np.array([[pos], [0.0]])
#         self.P = np.array([[100.0, 0.0], [0.0, 100.0]])
#         self.F = np.array([[1.0, 1.0], [0.0, 1.0]])
#         self.H = np.array([[1.0, 0.0]])
#         self.R = np.array([[9.0]])
#         self.Q = np.array([[1.0, 0.0], [0.0, 0.01]])

#     def predict(self):
#         self.x = self.F @ self.x
#         self.P = self.F @ self.P @ self.F.T + self.Q
#         return self.x[0, 0]

#     def update(self, m):
#         y = m - self.H @ self.x
#         S = self.H @ self.P @ self.H.T + self.R
#         K = self.P @ self.H.T / S[0, 0]
#         self.x = self.x + K * y
#         self.P = (np.eye(2) - K @ self.H) @ self.P


# class CentroidTrack:
#     _next_id = 1

#     def __init__(self, centroid, bbox, class_name, confidence):
#         self.track_id = CentroidTrack._next_id
#         CentroidTrack._next_id += 1
#         self.centroid = centroid
#         self.bbox = bbox
#         self.class_name = class_name
#         self.confidence = confidence
#         self.disappeared = 0
#         self.hits = 1
#         self.confirmed = False
#         self.history = [centroid]
#         self.kf_x = KalmanFilter1D(centroid[0])
#         self.kf_y = KalmanFilter1D(centroid[1])
#         self.speed_kmh = 0.0
#         self.direction = None
#         self.in_intrusion_zone = False
#         self.crossed_counting_line = False

#     def update(self, centroid, bbox, class_name, confidence):
#         self.centroid = centroid
#         self.bbox = bbox
#         self.class_name = class_name
#         self.confidence = confidence
#         self.disappeared = 0
#         self.hits += 1
#         if self.hits >= config.MIN_HITS_TO_CONFIRM:
#             self.confirmed = True
#         self.history.append(centroid)
#         if len(self.history) > 60:
#             self.history.pop(0)
#         self.kf_x.update(centroid[0])
#         self.kf_y.update(centroid[1])

#     def predict(self):
#         return (self.kf_x.predict(), self.kf_y.predict())

#     def mark_disappeared(self):
#         self.disappeared += 1


# class CentroidTracker:
#     def __init__(self):
#         self.tracks = OrderedDict()

#     def update(self, detections):
#         predictions = {tid: t.predict() for tid, t in self.tracks.items()}

#         if not detections:
#             for tid in list(self.tracks):
#                 self.tracks[tid].mark_disappeared()
#                 if self.tracks[tid].disappeared > config.MAX_DISAPPEARED:
#                     del self.tracks[tid]
#             return [t for t in self.tracks.values() if t.confirmed]

#         centroids = []
#         for d in detections:
#             x1, y1, x2, y2 = d["bbox"]
#             centroids.append(((x1 + x2) / 2.0, (y1 + y2) / 2.0))

#         if not self.tracks:
#             for i, d in enumerate(detections):
#                 t = CentroidTrack(centroids[i], d["bbox"], d["class_name"], d["confidence"])
#                 self.tracks[t.track_id] = t
#             return [t for t in self.tracks.values() if t.confirmed]

#         tids = list(self.tracks.keys())
#         preds = [predictions[tid] for tid in tids]
#         D = np.zeros((len(tids), len(centroids)))
#         for i, p in enumerate(preds):
#             for j, c in enumerate(centroids):
#                 D[i, j] = np.linalg.norm(np.array(p) - np.array(c))

#         used_r, used_c = set(), set()
#         asgn = {}
#         for idx in np.argsort(D, axis=None):
#             i, j = divmod(idx, len(centroids))
#             if i in used_r or j in used_c:
#                 continue
#             if D[i, j] > config.MAX_DISTANCE:
#                 break
#             asgn[tids[i]] = j
#             used_r.add(i)
#             used_c.add(j)

#         for tid, ci in asgn.items():
#             self.tracks[tid].update(centroids[ci], detections[ci]["bbox"],
#                                      detections[ci]["class_name"], detections[ci]["confidence"])

#         for tid in tids:
#             if tid not in asgn:
#                 self.tracks[tid].mark_disappeared()
#                 if self.tracks[tid].disappeared > config.MAX_DISAPPEARED:
#                     del self.tracks[tid]

#         for j in range(len(centroids)):
#             if j not in used_c:
#                 t = CentroidTrack(centroids[j], detections[j]["bbox"],
#                                    detections[j]["class_name"], detections[j]["confidence"])
#                 self.tracks[t.track_id] = t

#         return [t for t in self.tracks.values() if t.confirmed]

#     def reset(self):
#         self.tracks.clear()
#         CentroidTrack._next_id = 1


# # ═══════════════════════════════════════════════════════════
# #  FACTORY
# # ═══════════════════════════════════════════════════════════

# def create_tracker():
#     """Create tracker based on config setting."""
#     if config.TRACKER_TYPE == "norfair":
#         nt = NorfairTracker()
#         if nt.tracker is not None:
#             return nt
#         print("[Tracker] Norfair unavailable, using Centroid")
#     return CentroidTracker()





"""
Dual tracker: Norfair (default) or Centroid+Kalman fallback.
Maintains vehicle identity across frames.
"""

import numpy as np
from collections import OrderedDict
import config


# ═══════════════════════════════════════════════════════════
#  NORFAIR TRACKER WRAPPER
# ═══════════════════════════════════════════════════════════

class NorfairTrack:
    """Lightweight wrapper around a Norfair tracked object."""
    _next_id = 0

    def __init__(self, norfair_obj, class_name, confidence):
        NorfairTrack._next_id += 1
        self.track_id = NorfairTrack._next_id
        self.norfair_obj = norfair_obj
        self.class_name = class_name
        self.confidence = confidence
        self.speed_kmh = 0.0
        self.direction = None
        self.in_intrusion_zone = False
        self.crossed_counting_line = False
        self.history = []
        self.hits = 1
        self.confirmed = True
        self._update_bbox()

    def _update_bbox(self):
        # Flatten whatever shape Norfair returns into [x1, y1, x2, y2]
        pts = np.array(self.norfair_obj.estimate).flatten()
        self.bbox = (int(pts[0]), int(pts[1]), int(pts[2]), int(pts[3]))
        self.centroid = (
            (self.bbox[0] + self.bbox[2]) / 2.0,
            (self.bbox[1] + self.bbox[3]) / 2.0,
        )
        self.history.append(self.centroid)
        if len(self.history) > 60:
            self.history.pop(0)

    def refresh(self, class_name, confidence):
        self.class_name = class_name
        self.confidence = confidence
        self.hits += 1
        self._update_bbox()


class NorfairTracker:
    """Wraps Norfair Tracker for the system interface."""

    def __init__(self):
        self.tracks = {}
        self.tracker = None
        self._init_norfair()

    def _init_norfair(self):
        try:
            from norfair import Tracker as NorfairTrackerCls
            self.tracker = NorfairTrackerCls(
                distance_function="euclidean",
                distance_threshold=config.NORFAIR_DISTANCE_THRESHOLD,
            )
            print("[Tracker] Norfair initialized")
        except ImportError:
            print("[Tracker] Norfair not installed — falling back to Centroid")
            self.tracker = None

    def update(self, detections):
        if self.tracker is None:
            return []

        from norfair import Detection as NorfairDetection

        norfair_dets = []
        det_meta = []
        for d in detections:
            # CRITICAL: flat (4,) array — [x1, y1, x2, y2]
            # This matches your original code: box.xyxy.cpu().numpy()
            pts = np.array([
                d["bbox"][0], d["bbox"][1],
                d["bbox"][2], d["bbox"][3]
            ], dtype=float)
            scores = np.array([d["confidence"]])
            norfair_dets.append(NorfairDetection(points=pts, scores=scores))
            det_meta.append({"class_name": d["class_name"], "confidence": d["confidence"]})

        tracked_objects = self.tracker.update(detections=norfair_dets)

        result = []
        current_ids = set()

        for obj in tracked_objects:
            oid = obj.id
            current_ids.add(oid)

            best_meta = {"class_name": "unknown", "confidence": 0.0}
            if obj.last_detection is not None:
                for idx, nd in enumerate(norfair_dets):
                    try:
                        if np.allclose(nd.points, obj.last_detection.points, atol=5):
                            best_meta = det_meta[idx]
                            break
                    except Exception:
                        pass

            if oid in self.tracks:
                self.tracks[oid].refresh(best_meta["class_name"], best_meta["confidence"])
            else:
                self.tracks[oid] = NorfairTrack(obj, best_meta["class_name"], best_meta["confidence"])

            result.append(self.tracks[oid])

        stale = [k for k in self.tracks if k not in current_ids]
        for k in stale:
            del self.tracks[k]

        return result

    def reset(self):
        self.tracks.clear()
        NorfairTrack._next_id = 0
        if self.tracker:
            try:
                from norfair import Tracker as NorfairTrackerCls
                self.tracker = NorfairTrackerCls(
                    distance_function="euclidean",
                    distance_threshold=config.NORFAIR_DISTANCE_THRESHOLD,
                )
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════
#  CENTROID + KALMAN FILTER TRACKER (fallback)
# ═══════════════════════════════════════════════════════════

class KalmanFilter1D:
    def __init__(self, pos):
        self.x = np.array([[float(pos)], [0.0]])
        self.P = np.array([[100.0, 0.0], [0.0, 100.0]])
        self.F = np.array([[1.0, 1.0], [0.0, 1.0]])
        self.H = np.array([[1.0, 0.0]])
        self.R = np.array([[9.0]])
        self.Q = np.array([[1.0, 0.0], [0.0, 0.01]])

    def predict(self):
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        return float(self.x[0, 0])

    def update(self, val):
        m = float(val)
        y = np.array([[m]]) - self.H @ self.x
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T / S[0, 0]
        self.x = self.x + K * y
        self.P = (np.eye(2) - K @ self.H) @ self.P


class CentroidTrack:
    _next_id = 1

    def __init__(self, centroid, bbox, class_name, confidence):
        self.track_id = CentroidTrack._next_id
        CentroidTrack._next_id += 1
        self.centroid = centroid
        self.bbox = bbox
        self.class_name = class_name
        self.confidence = confidence
        self.disappeared = 0
        self.hits = 1
        self.confirmed = True
        self.history = [centroid]
        self.kf_x = KalmanFilter1D(centroid[0])
        self.kf_y = KalmanFilter1D(centroid[1])
        self.speed_kmh = 0.0
        self.direction = None
        self.in_intrusion_zone = False
        self.crossed_counting_line = False

    def update(self, centroid, bbox, class_name, confidence):
        self.centroid = centroid
        self.bbox = bbox
        self.class_name = class_name
        self.confidence = confidence
        self.disappeared = 0
        self.hits += 1
        self.history.append(centroid)
        if len(self.history) > 60:
            self.history.pop(0)
        self.kf_x.update(centroid[0])
        self.kf_y.update(centroid[1])

    def predict(self):
        return (self.kf_x.predict(), self.kf_y.predict())

    def mark_disappeared(self):
        self.disappeared += 1


class CentroidTracker:
    def __init__(self):
        self.tracks = OrderedDict()

    def update(self, detections):
        predictions = {tid: t.predict() for tid, t in self.tracks.items()}

        if not detections:
            for tid in list(self.tracks):
                self.tracks[tid].mark_disappeared()
                if self.tracks[tid].disappeared > config.MAX_DISAPPEARED:
                    del self.tracks[tid]
            return list(self.tracks.values())

        centroids = []
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            centroids.append(((x1 + x2) / 2.0, (y1 + y2) / 2.0))

        if not self.tracks:
            for i, det in enumerate(detections):
                t = CentroidTrack(centroids[i], det["bbox"], det["class_name"], det["confidence"])
                self.tracks[t.track_id] = t
            return list(self.tracks.values())

        tids = list(self.tracks.keys())
        preds = [predictions[tid] for tid in tids]
        D = np.zeros((len(tids), len(centroids)))
        for row, p in enumerate(preds):
            for col, c in enumerate(centroids):
                D[row, col] = np.linalg.norm(np.array(p) - np.array(c))

        used_r, used_c = set(), set()
        asgn = {}
        for idx in np.argsort(D, axis=None):
            row, col = divmod(idx, len(centroids))
            if row in used_r or col in used_c:
                continue
            if D[row, col] > config.MAX_DISTANCE:
                break
            asgn[tids[row]] = col
            used_r.add(row)
            used_c.add(col)

        for tid, col in asgn.items():
            self.tracks[tid].update(
                centroids[col], detections[col]["bbox"],
                detections[col]["class_name"], detections[col]["confidence"],
            )

        for tid in tids:
            if tid not in asgn:
                self.tracks[tid].mark_disappeared()
                if self.tracks[tid].disappeared > config.MAX_DISAPPEARED:
                    del self.tracks[tid]

        for j in range(len(centroids)):
            if j not in used_c:
                t = CentroidTrack(
                    centroids[j], detections[j]["bbox"],
                    detections[j]["class_name"], detections[j]["confidence"],
                )
                self.tracks[t.track_id] = t

        return list(self.tracks.values())

    def reset(self):
        self.tracks.clear()
        CentroidTrack._next_id = 1


# ═══════════════════════════════════════════════════════════
#  FACTORY
# ═══════════════════════════════════════════════════════════

def create_tracker():
    """Create tracker based on config setting."""
    if config.TRACKER_TYPE == "norfair":
        nt = NorfairTracker()
        if nt.tracker is not None:
            return nt
        print("[Tracker] Norfair unavailable, using Centroid")
    return CentroidTracker()