"""
YOLO-based Vehicle Detector.
"""

import torch

# ── Patch for PyTorch 2.6+ weights_only change ──────────────
_orig = torch.load
def _patched(*a, **kw):
    kw.setdefault("weights_only", False)
    return _orig(*a, **kw)
torch.load = _patched
# ──────────────────────────────────────────────────────────────

import cv2
import numpy as np
from ultralytics import YOLO
import config


class VehicleDetector:

    def __init__(self):
        self.conf = config.YOLO_CONFIDENCE_THRESHOLD
        self.iou = config.YOLO_IOU_THRESHOLD
        self.vehicle_classes = config.VEHICLE_CLASSES
        self.model = None
        self._load()

    def _load(self):
        try:
            self.model = YOLO(config.YOLO_MODEL_PATH)
            print(f"[Detector] Loaded: {config.YOLO_MODEL_PATH}")
        except Exception as e:
            print(f"[Detector] ERROR: {e}")
            print("[Detector] Running in demo mode (no detections).")
            self.model = None

    def detect(self, frame):
        if self.model is None:
            return []
        results = self.model(
            frame, conf=self.conf, iou=self.iou,
            verbose=False, classes=list(self.vehicle_classes.keys())
        )
        detections = []
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                cls_id = int(box.cls[0].cpu().numpy())
                conf = float(box.conf[0].cpu().numpy())
                detections.append({
                    "bbox": (x1, y1, x2, y2),
                    "class_id": cls_id,
                    "class_name": self.vehicle_classes.get(cls_id, "unknown"),
                    "confidence": conf,
                })
        return detections