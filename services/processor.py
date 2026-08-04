"""
Video Processor — capture → detect → track → analyze → decide → stream.
Supports: webcam index, IP camera URL, video file path.
"""

import cv2
import time
import threading
import queue
import numpy as np
from datetime import datetime

import config
from core.detector import VehicleDetector
from core.tracker import create_tracker
from core.analytics import (
    VehicleCounter, SpeedEstimator, WrongWayDetector,
    IntrusionDetector, CongestionAnalyzer, ParkingMonitor,
)
from database.models import DatabaseManager


def parse_source(raw):
    """
    Parse user input into a valid OpenCV source.
    - "0" → int 0 (webcam)
    - "1", "2" → int 1, 2 (other webcam indices)
    - Starts with "http" → IP camera URL string
    - Anything else → file path string
    """
    s = str(raw).strip()
    if s.isdigit():
        return int(s)
    return s


class VideoProcessor:
    def __init__(self, socketio=None):
        self.socketio = socketio
        self.cap = None
        self.detector = VehicleDetector()
        self.tracker = None
        self.counter = VehicleCounter()
        self.speed_estimator = SpeedEstimator()
        self.wrong_way = WrongWayDetector()
        self.intrusion = IntrusionDetector()
        self.congestion = CongestionAnalyzer()
        self.parking = ParkingMonitor()
        self.db = DatabaseManager()

        self.frame_queue = queue.Queue(maxsize=30)
        self.running = False
        self.thread = None
        self.fps = 0.0
        self.frame_count = 0
        self.start_time = None
        self.source_raw = "0"
        self.source_parsed = 0
        self._reconnect_attempts = 0
        self._max_reconnect = 5

    @property
    def is_video_file(self):
        return isinstance(self.source_parsed, str) and not self.source_parsed.startswith("http")

    def start(self, source=None):
        if self.running:
            return False
        self.source_raw = source if source is not None else str(config.CAMERA_SOURCE)
        self.source_parsed = parse_source(self.source_raw)
        self._reconnect_attempts = 0
        return self._open_and_start()

    def _open_and_start(self):
        self.cap = cv2.VideoCapture(self.source_parsed)
        if not self.cap.isOpened():
            print(f"[Processor] Cannot open: {self.source_parsed}")
            return False
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
        self.tracker = create_tracker()
        self.counter = VehicleCounter()
        self.running = True
        self.start_time = time.time()
        self.frame_count = 0
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        print(f"[Processor] Started — source: {self.source_parsed} (type: {'file' if self.is_video_file else 'stream' if isinstance(self.source_parsed, str) else 'webcam'})")
        return True

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3)
        if self.cap:
            self.cap.release()
            self.cap = None
        if self.tracker:
            self.tracker.reset()
        print("[Processor] Stopped")

    def get_frame(self):
        try:
            return self.frame_queue.get_nowait()
        except queue.Empty:
            return None

    def _loop(self):
        while self.running:
            try:
                ret, frame = self.cap.read()
            except Exception:
                self.running = False
                break

            if not ret:
                if self.is_video_file:
                    try:
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    except Exception:
                        self.running = False
                        break
                    continue
                elif isinstance(self.source_parsed, str):
                    self._reconnect_attempts += 1
                    if self._reconnect_attempts <= self._max_reconnect:
                        print(f"[Processor] Reconnecting ({self._reconnect_attempts}/{self._max_reconnect})...")
                        time.sleep(2)
                        try:
                            self.cap.open(self.source_parsed)
                        except Exception:
                            pass
                        continue
                    else:
                        print("[Processor] Max reconnection attempts reached.")
                        self.running = False
                        break
                else:
                    self.running = False
                    break

            self._reconnect_attempts = 0
            self.frame_count += 1
            elapsed = time.time() - self.start_time
            self.fps = self.frame_count / max(elapsed, 0.001)

            # 1) Detect
            try:
                detections = self.detector.detect(frame)
            except Exception as e:
                print(f"[Processor] Detection error: {e}")
                detections = []

            # Debug: print detection count every 30 frames
            if self.frame_count % 30 == 0:
                print(f"[Processor] Frame {self.frame_count} | Detections: {len(detections)} | FPS: {self.fps:.1f}")

            # 2) Track
            try:
                tracks = self.tracker.update(detections)
            except Exception as e:
                print(f"[Processor] Tracker error, skipping frame: {e}")
                tracks = []

            # 3) Analytics
            try:
                count_ev = self.counter.process(tracks)
                speed_ev = self.speed_estimator.process(tracks, self.fps)
                ww_ev = self.wrong_way.process(tracks)
                int_ev = self.intrusion.process(tracks)
                cong = self.congestion.process(tracks)
                park = self.parking.process(tracks)
            except Exception as e:
                print(f"[Processor] Analytics error: {e}")
                count_ev, speed_ev, ww_ev, int_ev = [], [], [], []
                cong = {"count": 0, "level": 0, "congested": False}
                park = {}

            # 4) Decisions
            try:
                self._decide(tracks, count_ev, speed_ev, ww_ev, int_ev, cong, frame)
            except Exception as e:
                print(f"[Processor] Decision error: {e}")

            # 5) Draw
            try:
                self._draw(frame, tracks)
            except Exception as e:
                print(f"[Processor] Draw error: {e}")

            # 6) Queue for streaming
            try:
                self.frame_queue.put_nowait(frame.copy())
            except queue.Full:
                pass

            # 7) Socket.IO emit every 5 frames
            if self.frame_count % 5 == 0:
                try:
                    self._emit(tracks, cong, park)
                except Exception:
                    pass

        # Ensure running is False when loop exits
        self.running = False
        print("[Processor] Loop ended")

        
    def _decide(self, tracks, count_ev, speed_ev, ww_ev, int_ev, cong, frame):
        for ev in count_ev:
            t = next((x for x in tracks if x.track_id == ev["track_id"]), None)
            spd = round(t.speed_kmh, 1) if t else 0
            d = t.direction if t else ev["dir"]
            # Save snapshot AND get the path
            snap = None
            if config.AUTO_SAVE_SNAPSHOTS and t:
                snap = self._snap(frame, t, f"count_{ev['track_id']}")
            self.db.log_vehicle(ev["track_id"], ev["type"], spd, d, snap)
            self.db.inc_hourly()

        if config.ALERT_ON_HIGH_SPEED:
            for ev in speed_ev:
                if ev["over_limit"]:
                    snap = None
                    t = next((x for x in tracks if x.track_id == ev["track_id"]), None)
                    if t and config.AUTO_SAVE_SNAPSHOTS:
                        snap = self._snap(frame, t, f"speed_{ev['track_id']}")
                    self.db.add_alert(
                        "speed_violation", "warning",
                        f"Vehicle #{ev['track_id']} ({ev['type']}) at {ev['speed']} km/h (limit: {config.SPEED_LIMIT_KMH})",
                        snap
                    )

        if config.ALERT_ON_WRONG_WAY:
            for ev in ww_ev:
                snap = None
                t = next((x for x in tracks if x.track_id == ev["track_id"]), None)
                if t and config.AUTO_SAVE_SNAPSHOTS:
                    snap = self._snap(frame, t, f"wrongway_{ev['track_id']}")
                self.db.add_alert(
                    "wrong_way", "critical",
                    f"Vehicle #{ev['track_id']} ({ev['type']}) moving {ev['direction']} (expected: {ev['expected']})",
                    snap
                )

        if config.ALERT_ON_INTRUSION:
            for ev in int_ev:
                snap = None
                t = next((x for x in tracks if x.track_id == ev["track_id"]), None)
                if t and config.AUTO_SAVE_SNAPSHOTS:
                    snap = self._snap(frame, t, f"intrusion_{ev['track_id']}")
                self.db.add_alert(
                    "intrusion", "critical",
                    f"Vehicle #{ev['track_id']} ({ev['type']}) entered restricted zone",
                    snap
                )

        if config.ALERT_ON_CONGESTION and cong.get("congested"):
            self.db.add_alert("congestion", "info",
                              f"Congestion: {cong['count']} vehicles ({cong['level']*100:.0f}%)")
   


    def _snap(self, frame, track, prefix):
        """Save a cropped snapshot. Returns the file path or None."""
        try:
            x1, y1, x2, y2 = [int(v) for v in track.bbox]
            x1, y1 = max(0, x1 - 20), max(0, y1 - 20)
            x2, y2 = min(frame.shape[1], x2 + 20), min(frame.shape[0], y2 + 20)
            crop = frame[y1:y2, x1:x2]
            if crop.size > 0:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                path = f"{config.SNAPSHOT_DIR}/{prefix}_{ts}.jpg"
                cv2.imwrite(path, crop)
                return path
        except Exception as e:
            print(f"[Snap] Error: {e}")
        return None


    def _draw(self, frame, tracks):
        frame = self.counter.draw(frame)
        frame = self.intrusion.draw(frame)
        frame = self.congestion.draw(frame)
        frame = self.parking.draw(frame)

        for t in tracks:
            x1, y1, x2, y2 = [int(v) for v in t.bbox]

            # Bright visible colors: cyan for normal, red for intrusion
            if t.in_intrusion_zone:
                color = (0, 0, 255)
                label_color = (0, 0, 255)
            else:
                color = (0, 255, 255)  # Bright cyan — visible on dark video
                label_color = (0, 255, 255)

            # Thick bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)

            # Label background + text
            label = f"#{t.track_id} {t.class_name}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
            cv2.rectangle(frame, (x1, y1 - th - 10), (x1 + tw + 8, y1), (0, 0, 0), -1)
            cv2.putText(frame, label, (x1 + 4, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, label_color, 2)

            # Centroid dot
            cx, cy = int(t.centroid[0]), int(t.centroid[1])
            cv2.circle(frame, (cx, cy), 5, (255, 255, 255), -1)
            cv2.circle(frame, (cx, cy), 5, color, 2)

            # Motion trail
            if len(t.history) > 1:
                pts = t.history[-25:]
                for i in range(1, len(pts)):
                    a = i / len(pts)
                    c = (0, int(255 * a), int(255 * a))
                    cv2.line(frame,
                             (int(pts[i-1][0]), int(pts[i-1][1])),
                             (int(pts[i][0]), int(pts[i][1])), c, 2)

        
        frame = self.speed_estimator.draw(frame, tracks)
        frame = self.wrong_way.draw(frame, tracks)

        # HUD
        cv2.putText(frame, f"FPS: {self.fps:.1f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        active = sum(1 for t in tracks if t.confirmed)
        cv2.putText(frame, f"Active: {active}", (10, 55),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, now, (frame.shape[1] - 280, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

        # Source label
        src_label = f"Source: {self.source_raw}"
        cv2.putText(frame, src_label, (frame.shape[1] - 280, 55),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)

    def _emit(self, tracks, cong, park):
        if not self.socketio:
            return
        active = sum(1 for t in tracks if t.confirmed)
        td = [{"id": t.track_id, "type": t.class_name, "speed": round(t.speed_kmh, 1), "direction": t.direction}
              for t in tracks if t.confirmed]
        self.socketio.emit("tracking_update", {
            "fps": round(self.fps, 1),
            "active_vehicles": active,
            "total_counted": self.counter.count_in + self.counter.count_out,
            "count_in": self.counter.count_in,
            "count_out": self.counter.count_out,
            "congestion": cong,
            "parking": park,
            "tracks": td,
        })