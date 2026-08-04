"""
Configuration — all tunable parameters in one place.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Camera ───────────────────────────────────────────────────
CAMERA_SOURCE = 0
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
CAMERA_FPS = 30

# ── YOLO Detection ───────────────────────────────────────────
YOLO_MODEL_PATH = os.path.join(BASE_DIR, "models", "yolov8n.pt")
YOLO_CONFIDENCE_THRESHOLD = 0.45
YOLO_IOU_THRESHOLD = 0.45
VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

# ── Tracker: "norfair" or "centroid" ─────────────────────────
TRACKER_TYPE = "norfair"
NORFAIR_DISTANCE_THRESHOLD = 30
MAX_DISAPPEARED = 30
MAX_DISTANCE = 80
MIN_HITS_TO_CONFIRM = 1

# ── Speed Estimation ─────────────────────────────────────────
PIXELS_PER_METER = 15.0
SPEED_ESTIMATION_SMOOTHING = 0.4

# ── Counting Line ────────────────────────────────────────────
COUNTING_LINE_Y = 300
COUNTING_DIRECTION = "down"

# ── Wrong-Way Detection ──────────────────────────────────────
WRONG_WAY_ENABLED = True
EXPECTED_DIRECTION = "left-to-right"

# ── Intrusion Detection ──────────────────────────────────────
INTRUSION_ENABLED = True
INTRUSION_ZONE = [(100, 500), (500, 500), (500, 700), (100, 700)]

# ── Congestion Analysis ──────────────────────────────────────
CONGESTION_ENABLED = True
CONGESTION_THRESHOLD = 8

# ── Parking ──────────────────────────────────────────────────
PARKING_ENABLED = False
PARKING_SPOTS = [
    ((50, 50, 200, 150), "P1"),
    ((220, 50, 370, 150), "P2"),
    ((390, 50, 540, 150), "P3"),
]

# ── Decision Engine ──────────────────────────────────────────
ALERT_ON_WRONG_WAY = True
ALERT_ON_INTRUSION = True
ALERT_ON_CONGESTION = True
ALERT_ON_HIGH_SPEED = True
SPEED_LIMIT_KMH = 60.0
AUTO_SAVE_SNAPSHOTS = True

# ── Paths ────────────────────────────────────────────────────
SNAPSHOT_DIR = os.path.join(BASE_DIR, "snapshots")
CLIP_DIR = os.path.join(BASE_DIR, "clips")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")

# ── Database ─────────────────────────────────────────────────
DATABASE_PATH = os.path.join(BASE_DIR, "database", "tracking.db")

# ── Flask ────────────────────────────────────────────────────
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000
FLASK_DEBUG = False
SECRET_KEY = "trackvision-secret-key-change-me"

# ── Ensure directories ───────────────────────────────────────
for _d in [SNAPSHOT_DIR, CLIP_DIR, UPLOADS_DIR,
           os.path.join(BASE_DIR, "models"), os.path.join(BASE_DIR, "database")]:
    os.makedirs(_d, exist_ok=True)