"""
Analytics: counting, speed, wrong-way, intrusion, congestion, parking.
"""

import cv2
import numpy as np
from datetime import datetime
import config


class VehicleCounter:
    def __init__(self):
        self.line_y = config.COUNTING_LINE_Y
        self.direction = config.COUNTING_DIRECTION
        self.count_in = 0
        self.count_out = 0
        self.total = 0
        self._counted_ids = set()

    def process(self, tracks):
        events = []
        for t in tracks:
            if t.track_id in self._counted_ids or len(t.history) < 2:
                continue
            prev_y = t.history[-2][1]
            curr_y = t.history[-1][1]
            crossed_down = prev_y < self.line_y <= curr_y
            crossed_up = prev_y > self.line_y >= curr_y
            if crossed_down and self.direction in ("down", "both"):
                self.count_in += 1
                self.total += 1
                self._counted_ids.add(t.track_id)
                events.append({"track_id": t.track_id, "dir": "in", "type": t.class_name})
            elif crossed_up and self.direction in ("up", "both"):
                self.count_out += 1
                self.total += 1
                self._counted_ids.add(t.track_id)
                events.append({"track_id": t.track_id, "dir": "out", "type": t.class_name})
        return events

    def draw(self, frame):
        cv2.line(frame, (0, self.line_y), (frame.shape[1], self.line_y), (0, 255, 136), 2)
        cv2.putText(frame, f"IN: {self.count_in}  OUT: {self.count_out}",
                    (20, self.line_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 136), 2)
        return frame


class SpeedEstimator:
    def __init__(self):
        self.ppm = config.PIXELS_PER_METER
        self.smoothing = config.SPEED_ESTIMATION_SMOOTHING
        self.speed_limit = config.SPEED_LIMIT_KMH

    def process(self, tracks, fps=30):
        results = []
        for t in tracks:
            if len(t.history) < 3:
                t.speed_kmh = 0.0
                continue
            n = min(10, len(t.history))
            dx = t.history[-1][0] - t.history[-n][0]
            dy = t.history[-1][1] - t.history[-n][1]
            dist = np.sqrt(dx ** 2 + dy ** 2)
            dt = n / max(fps, 1)
            speed_kmh = (dist / self.ppm) / dt * 3.6
            t.speed_kmh = self.smoothing * speed_kmh + (1 - self.smoothing) * t.speed_kmh
            if len(t.history) >= 2:
                ddx = t.history[-1][0] - t.history[-2][0]
                ddy = t.history[-1][1] - t.history[-2][1]
                if abs(ddx) > abs(ddy):
                    t.direction = "left-to-right" if ddx > 0 else "right-to-left"
                else:
                    t.direction = "top-to-bottom" if ddy > 0 else "bottom-to-top"
            if t.speed_kmh > 5:
                results.append({
                    "track_id": t.track_id,
                    "speed": round(t.speed_kmh, 1),
                    "over_limit": t.speed_kmh > self.speed_limit,
                    "type": t.class_name,
                })
        return results

    def draw(self, frame, tracks):
        for t in tracks:
            if t.speed_kmh > 5 and t.confirmed:
                x1, y1 = int(t.bbox[0]), int(t.bbox[1])
                color = (0, 0, 255) if t.speed_kmh > self.speed_limit else (0, 255, 136)
                cv2.putText(frame, f"{t.speed_kmh:.0f} km/h",
                            (x1, y1 - 28), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        return frame


class WrongWayDetector:
    def __init__(self):
        self.expected = config.EXPECTED_DIRECTION
        self.enabled = config.WRONG_WAY_ENABLED
        self._flagged = set()

    def process(self, tracks):
        if not self.enabled:
            return []
        events = []
        for t in tracks:
            if not t.direction or not t.confirmed or t.speed_kmh < 10:
                continue
            if t.direction != self.expected and t.track_id not in self._flagged:
                self._flagged.add(t.track_id)
                events.append({
                    "track_id": t.track_id,
                    "direction": t.direction,
                    "expected": self.expected,
                    "type": t.class_name,
                })
        return events

    def draw(self, frame, tracks):
        if not self.enabled:
            return frame
        for t in tracks:
            if t.direction and t.direction != self.expected and t.speed_kmh > 10:
                x1, y1, x2, y2 = [int(v) for v in t.bbox]
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                cv2.putText(frame, "WRONG WAY!", (x1, y1 - 45),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        return frame


class IntrusionDetector:
    def __init__(self):
        self.zone = config.INTRUSION_ZONE
        self.enabled = config.INTRUSION_ENABLED

    def _point_in_poly(self, pt, poly):
        x, y = pt
        n = len(poly)
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = poly[i]
            xj, yj = poly[j]
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside

    def process(self, tracks):
        if not self.enabled:
            return []
        events = []
        for t in tracks:
            if not t.confirmed:
                continue
            inside = self._point_in_poly(t.centroid, self.zone)
            if inside and not t.in_intrusion_zone:
                t.in_intrusion_zone = True
                events.append({"track_id": t.track_id, "type": t.class_name, "position": t.centroid})
            elif not inside:
                t.in_intrusion_zone = False
        return events

    def draw(self, frame):
        if not self.enabled:
            return frame
        pts = np.array(self.zone, np.int32).reshape((-1, 1, 2))
        cv2.polylines(frame, [pts], True, (0, 0, 255), 2)
        overlay = frame.copy()
        cv2.fillPoly(overlay, [pts], (0, 0, 100))
        cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)
        cv2.putText(frame, "RESTRICTED ZONE",
                    (self.zone[0][0], self.zone[0][1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        return frame


class CongestionAnalyzer:
    def __init__(self):
        self.threshold = config.CONGESTION_THRESHOLD
        self.enabled = config.CONGESTION_ENABLED
        self.congestion_level = 0.0
        self.is_congested = False

    def process(self, tracks):
        if not self.enabled:
            return {"count": 0, "level": 0.0, "congested": False}
        count = len([t for t in tracks if t.confirmed])
        self.congestion_level = min(1.0, count / max(1, self.threshold))
        self.is_congested = count >= self.threshold
        return {"count": count, "level": round(self.congestion_level, 2), "congested": self.is_congested}

    def draw(self, frame):
        if not self.enabled:
            return frame
        color = (0, 0, 255) if self.is_congested else (0, 255, 136)
        label = f"CONGESTED ({self.congestion_level * 100:.0f}%)" if self.is_congested \
            else f"Flow: {self.congestion_level * 100:.0f}%"
        cv2.putText(frame, label, (frame.shape[1] - 350, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        return frame


class ParkingMonitor:
    def __init__(self):
        self.spots = config.PARKING_SPOTS
        self.enabled = config.PARKING_ENABLED
        self.occupancy = {s[1]: False for s in self.spots}

    def _iou(self, a, b):
        x1 = max(a[0], b[0]); y1 = max(a[1], b[1])
        x2 = min(a[2], b[2]); y2 = min(a[3], b[3])
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        ua = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter
        return inter / max(ua, 1e-6)

    def process(self, tracks):
        if not self.enabled:
            return {}
        for sb, sid in self.spots:
            self.occupancy[sid] = any(self._iou(sb, t.bbox) > 0.3 for t in tracks)
        return self.occupancy.copy()

    def draw(self, frame):
        if not self.enabled:
            return frame
        for (x1, y1, x2, y2), sid in self.spots:
            occ = self.occupancy.get(sid, False)
            c = (0, 0, 255) if occ else (0, 255, 136)
            cv2.rectangle(frame, (x1, y1), (x2, y2), c, 2)
            cv2.putText(frame, f"{sid} {'OCCUPIED' if occ else 'FREE'}",
                        (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, c, 1)
        return frame