# TrackVision — AI-Powered Car Tracking System

## Table of Contents
- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Folder Structure](#folder-structure)
- [How It Works — Step by Step](#how-it-works--step-by-step)
  - [1. Video Capture](#1-video-capture)
  - [2. AI Vehicle Detection](#2-ai-vehicle-detection)
  - [3. Object Tracking](#3-object-tracking)
  - [4. Analytics Pipeline](#4-analytics-pipeline)
  - [5. Decision Engine](#5-decision-engine)
  - [6. Real-Time Streaming](#6-real-time-streaming)
  - [7. Web Interface](#7-web-interface)
- [Analytics Modules in Detail](#analytics-modules-in-detail)
  - [Vehicle Counting](#vehicle-counting)
  - [Speed Estimation](#speed-estimation)
  - [Wrong-Way Detection](#wrong-way-detection)
  - [Intrusion Detection](#intrusion-detection)
  - [Congestion Analysis](#congestion-analysis)
  - [Parking Monitoring](#parking-monitoring)
- [Tracker Options](#tracker-options)
  - [Norfair (Default)](#norfair-default)
  - [Centroid + Kalman Filter (Fallback)](#centroid--kalman-filter-fallback)
- [Camera Source Options](#camera-source-options)
- [Database Schema](#database-schema)
- [Web Pages](#web-pages)
- [API Reference](#api-reference)
- [Installation](#installation)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Technical Decisions](#technical-decisions)
- [Extending the System](#extending-the-system)

---

## Overview

TrackVision is a complete, professional AI-powered vehicle tracking system built with Python and Flask. It captures video from any camera source, detects and tracks vehicles in real-time using deep learning, runs 6 different analytics modules simultaneously, makes local decisions (alerts, snapshots), and presents everything through a modern real-time web dashboard.

### Key Features

| Feature | Description |
| :--- | :--- |
| **AI Detection** | YOLOv8n identifies cars, trucks, buses, motorcycles |
| **Object Tracking** | Norfair maintains unique vehicle IDs across frames |
| **Vehicle Counting** | Counts vehicles crossing a configurable line |
| **Speed Estimation** | Calculates speed using pixel-to-meter calibration |
| **Wrong-Way Detection** | Flags vehicles moving in the wrong direction |
| **Intrusion Detection** | Detects vehicles entering forbidden zones |
| **Congestion Analysis** | Monitors traffic density in real-time |
| **Parking Monitoring** | Tracks occupancy of defined parking spots |
| **Real-Time Streaming** | MJPEG stream to browser via WebSocket |
| **Vehicle Detail Pages** | Per-vehicle timeline, snapshot, speed chart |
| **Alert Management** | Categorized alerts with acknowledge system |
| **Data Management** | SQLite storage, clear data with confirmation |
| **Flexible Camera** | Webcam, IP camera, RTSP, video files — all switchable from UI |

---

## System Architecture

```text
┌─────────────────────────────────────────────────────┐
│                   BROWSER (Client)                  │
│                                                     │
│ ┌──────────┐     ┌──────────┐     ┌──────────────┐  │
│ │ Dashboard│     │  Camera  │     │  Analytics   │  │
│ │   Page   │     │   Page   │     │     Page     │  │
│ └────┬─────┘     └────┬─────┘     └──────┬───────┘  │
│      │                │                  │          │
│      └────────────────┼──────────────────┘          │
│                       │ Socket.IO (real-time data)  │
│                       │                             │
└───────────────────────┼─────────────────────────────┘
                        │
          Flask + Socket.IO (threading)
                        │
┌───────────────────────┼─────────────────────────────┐
│                       │                             │
│ ┌──────────┐     ┌────┴─────┐     ┌──────┐  ┌────┐  │
│ │  Video   │     │ Tracker  │     │Alerts│  │ DB │  │
│ │  Stream  │     │ Engine   │     │Engine│  │Mgr │  │
│ └────┬─────┘     └────┬─────┘     └──┬───┘  └──┬─┘  │
│      │                │              │         │    │
│ ┌────┴─────┐     ┌────┴─────┐     ┌──┴───┐          │
│ │   YOLO   │     │ Analytics│     │  DB  │          │
│ │  Detect  │     │  Engine  │     │SQLite│          │
│ └──────────┘     └──────────┘     └──────┘          │
│                       │                             │
│ ┌─────────────────────┴───────────────┐             │
│ │             Camera Source           │             │
│ │ • Webcam (0, 1, 2...)               │             │
│ │ • IP Camera (http://...)            │             │
│ │ • RTSP Stream (rtsp://...)          │             │
│ │ • Video File (video.mp4)            │             │
│ └─────────────────────────────────────┘             │
└─────────────────────────────────────────────────────┘
```

**Data flow per frame:**

```text
Camera Frame
     │
     ▼
YOLO Detection
     │ Outputs: [{bbox, class_name, confidence}, ...]
     ▼
Object Tracker
     │ Outputs: [Track#1, Track#2, ...] with history
     ▼
Analytics Pipeline (all 6 modules run in parallel)
     │
     ├── Vehicle Counter ───> count_in, count_out
     ├── Speed Estimator ───> speed_kmh per track
     ├── Wrong-Way Det. ────> violations list
     ├── Intrusion Det. ────> intrusions list
     ├── Congestion Ana. ───> level, is_congested
     └── Parking Monitor ───> occupancy dict
     │
     ▼
Decision Engine
     │ • Log vehicles to database
     │ • Fire alerts for violations
     │ • Save snapshot images
     │ • Update hourly counts
     │
     ▼
Draw Overlays ──> Frame Queue ──> MJPEG Stream ──> Browser
     │
     ▼
Socket.IO Emit (every 5 frames) ──> Dashboard Updates
```

---

## Folder Structure

```text
ai-car-tracking-system/
│
├── app.py                  # Flask app — routes, API endpoints, video streaming
├── config.py               # All configurable parameters
├── requirements.txt        # Python dependencies
├── README.md               # Documentation file
│
├── core/                   # AI and tracking logic
│   ├── __init__.py
│   ├── detector.py         # YOLOv8 vehicle detection
│   ├── tracker.py          # Norfair + Centroid+Kalman trackers
│   └── analytics.py        # All 6 analytics modules
│
├── database/               # SQLite storage
│   ├── __init__.py
│   └── models.py           # Schema, CRUD operations
│
├── services/               # Video processing pipeline
│   ├── __init__.py
│   └── processor.py        # Capture -> Detect -> Track -> Analyze -> Decide -> Stream
│
├── static/
│   ├── css/
│   │   └── style.css       # Complete light theme UI
│   └── js/
│       └── app.js          # Socket.IO, camera controls, toasts, state sync
│
├── templates/              # HTML pages (Jinja2)
│   ├── base.html           # Layout: sidebar + topbar + content area
│   ├── index.html          # Dashboard: stats, camera preview, charts, active tracks
│   ├── camera.html         # Full-screen camera with HUD overlay + quick source switcher
│   ├── analytics.html      # Charts: hourly traffic, violations, speed distribution
│   ├── vehicles.html       # Paginated detection log table
│   ├── vehicle_detail.html # Per-vehicle: snapshot, speed, timeline, alerts
│   ├── alerts.html         # Alert list with filters and acknowledge
│   └── settings.html       # Camera source, detection params, feature toggles, danger zone
│
├── models/                 # YOLO model weights (auto-downloaded on first run)
│   └── yolov8n.pt
│
├── snapshots/              # Saved vehicle images (auto-generated)
├── clips/                  # Saved video clips (future feature)
└── uploads/                # Uploaded files (future feature)
```

---

## How It Works — Step by Step

### 1. Video Capture

The `VideoProcessor` class opens a video source using OpenCV's `cv2.VideoCapture()`. It accepts:

| Input | Interpretation | Example |
| :--- | :--- | :--- |
| `"0"` | Default webcam | Built-in laptop camera |
| `"1"`, `"2"` | Other webcam indices | USB cameras |
| `"http://192.168.1.100:8080/video"` | IP camera HTTP stream | Phone app, security cam |
| `"http://192.168.0.100/cam-hi.jpg"` | ESP32-CAM | Arduino camera module |
| `"rtsp://admin:pass@192.168.1.100:554/stream"` | RTSP stream | Professional IP camera |
| `"traffic.mp4"` | Local video file | Loops automatically |

**Error handling:** IP cameras get up to 5 automatic reconnection attempts with 2-second delays. Video files loop back to the beginning when they reach the end.

### 2. AI Vehicle Detection

The `VehicleDetector` class wraps Ultralytics YOLOv8-nano (the smallest, fastest YOLO model). On initialization:

```python
model = YOLO("yolov8n.pt")  # Downloads automatically on first run (~6MB)
```

Each frame is passed to the model with these filters:
- **Class filter:** Only COCO classes 2 (car), 3 (motorcycle), 5 (bus), 7 (truck)
- **Confidence threshold:** Default 45% (configurable via Settings page, 0.01–0.99 internally)
- **IoU threshold:** Default 0.45 (removes overlapping duplicate boxes)

**Output per frame:**
```python
[
    {"bbox": (100, 200, 350, 400), "class_name": "car", "confidence": 0.87},
    {"bbox": (500, 150, 700, 300), "class_name": "truck", "confidence": 0.92},
    ...
]
```

*Performance:* On a modern GPU, YOLOv8n runs at ~100+ FPS. On CPU, expect 5-15 FPS depending on resolution.

### 3. Object Tracking

Tracking maintains a persistent identity for each vehicle across frames. Two options:

#### Norfair (Default)
Uses Euclidean distance between bounding box centers. Each detection gets matched to the nearest existing track. If no match is found, a new track is created. Tracks that aren't seen for 30 frames are removed.

**How it works internally:**
```text
Frame 1: Detect [Car_A, Car_B]
         ──> Create Track#1 (Car_A), Create Track#2 (Car_B)

Frame 2: Detect [Car_A, Car_C]
         ──> Match Car_A to Track#1 (close distance ──> same car)
         ──> No match for Car_C ──> Create Track#3

Frame 3: Detect [Car_A, Car_B]
         ──> Match Car_A to Track#1
         ──> Match Car_B to Track#2
         ──> Track#3 not seen ──> increment disappeared counter
         ──> After 30 frames without match ──> remove Track#3
```

#### Centroid + Kalman Filter (Fallback)
If Norfair isn't installed, this uses a simpler algorithm:
1. Calculate center point (centroid) of each bounding box
2. Match new centroids to predicted positions from Kalman Filter
3. Same lifecycle: create -> update -> disappear -> remove

### 4. Analytics Pipeline

All 6 modules run on every confirmed track, every frame:

- **Vehicle Counting:** A horizontal line is drawn on the frame at a configurable Y-coordinate. When a vehicle's centroid crosses this line, it's counted (in/out). Each track is only counted once.
- **Speed Estimation:** Measures pixel distance moved over N frames and converts to real-world speed using `pixels_per_meter` calibration. Applies exponential smoothing for stable readings.  
  $$\text{speed\_kmh} = \frac{\text{pixel\_distance} / \text{pixels\_per\_meter}}{\text{time\_seconds}} \times 3.6$$
- **Wrong-Way Detection:** Tracks movement direction (left-to-right vs right-to-left) and compares against configured direction. Only triggers after speed > 10 km/h.
- **Intrusion Detection:** Defines a polygon zone and uses ray-casting to check if a vehicle's centroid is inside. Triggers an alert on first entry.
- **Congestion Analysis:** Counts confirmed vehicles in a region and calculates congestion level as percentage of threshold.
- **Parking Monitoring:** Uses pre-defined rectangular spots and checks Intersection over Union (IoU) > 0.3 to flag spots as occupied.

### 5. Decision Engine

After analytics, the system makes local decisions:

| Condition | Action |
| :--- | :--- |
| Vehicle crosses counting line | Log to database + increment hourly count + save snapshot |
| Speed exceeds limit | Create `speed_violation` alert + save snapshot |
| Wrong-way detected | Create `wrong_way` alert + save snapshot |
| Vehicle enters restricted zone | Create `intrusion` alert + save snapshot |
| Congestion threshold exceeded | Create `congestion` alert |
| `AUTO_SAVE_SNAPSHOTS = True` | Crop and save bounding box as JPEG image |

Alerts are stored in SQLite with severity levels:
- `critical` — Wrong-way, intrusion (red)
- `warning` — Speed violations (amber)
- `info` — Congestion (blue)

### 6. Real-Time Streaming

The processed frame (with bounding boxes, trails, HUD text) is:
1. Copied and placed in a thread-safe queue (max 30 frames buffered)
2. Encoded as JPEG at 85% quality
3. Yielded as MJPEG multipart stream via Flask Response
4. Served at `/video_feed` endpoint
5. Received by `<img>` tags in the browser

Data updates are pushed via Socket.IO every 5 frames.

### 7. Web Interface

The web layer provides a dashboard, live camera HUD view, analytics charts, vehicle logs, detail views, alert controls, and system configuration tools.

---

## Analytics Modules in Detail

### Vehicle Counting

```text
    ───────────────────── y=300 ─────────────────────
    │                                               │
    │  ▓  ▓  ▓  ▓  ▓  ▓  ▓  ▓  ▓  ▓  ▓  ▓  ▓  ▓  ▓  │
    │  IN: 12                                       │
    │  OUT: 3                                       │
    ─────────────────────────────────────────────────
```

- **Line position:** Configurable Y coordinate (default `300`).
- **Direction filter:** Can count only "down", "up", or "both".
- **Deduplication:** Uses a set of tracked IDs to prevent re-counting.
- **Database:** Each count increments the `hourly_counts` table.

### Speed Estimation

```text
    Track #5 history:
    Frame 100: (120, 300)
    Frame 105: (122, 302)  ──> moved 2.2px in 5 frames
    Frame 110: (126, 306)  ──> 6.6px in 10 frames

    Distance: 6.6 pixels
    Time: 10/30 = 0.33 seconds
    Speed: (6.6 / 15.0) / 0.33 × 3.6 = 4.8 km/h
    Smoothed: 0.4 × 4.8 + 0.6 × previous_speed = 2.88 km/h
```

- **Calibration:** `pixels_per_meter = 15.0` (measure a known-length object in frame).
- **Smoothing:** Exponential moving average prevents jitter.
- **Direction detection:** Compares last 2 centroid positions to determine direction.

### Wrong-Way Detection

```text
    Expected: left-to-right
    Actual:   right-to-left  <── WRONG WAY!
```

- Only triggers when speed > 10 km/h (avoids false positives on parked/stopped vehicles).
- Only one alert per vehicle per tracking session (no spam).
- Shows red bounding box + "WRONG WAY!" label on the frame.

### Intrusion Detection

```text
    ┌──────────────────────┐
    │   RESTRICTED ZONE    │
    │   (user-defined      │
    │    polygon)          │
    │                      │
    │      🚗 Car enters   │
    │                      │
    └──────────────────────┘
```

- Uses ray-casting point-in-polygon algorithm.
- Only triggers on first entry.
- Visual: Red dashed polygon drawn on frame, red bounding box when inside.

### Congestion Analysis

```text
    Region: full frame (default)
    Threshold: 8 vehicles
    Current: 10 vehicles
    Level: 10/8 = 1.25 ──> CONGESTED
```

- Counts confirmed vehicles in a defined region.
- Calculates percentage of threshold and updates in real-time.

### Parking Monitoring

```text
    ┌──────┐  ┌──────┐  ┌──────┐
    │ P1   │  │ P2   │  │ P3   │
    │ FREE │  │OCCUPIED│  │ FREE │
    └──────┘  └──────┘  └──────┘
```

- Pre-defined rectangular spots with IDs.
- IoU > 0.3 = occupied.
- Shows green (free) or red (occupied) on frame.

---

## Tracker Options

### Norfair (Default)
- **Pros:** More accurate matching with Euclidean distance, handles occlusions better, maintains smooth IDs.
- **Cons:** Requires `norfair` package, slightly more CPU usage.

### Centroid + Kalman Filter (Fallback)
- **Pros:** No external dependencies beyond numpy, very fast and lightweight.
- **Cons:** No built-in occlusion handling, less stable on fast-moving objects.

---

## Camera Source Options

The Settings page provides preset buttons plus free-form input:

| Preset | Value / Format | Description |
| :--- | :--- | :--- |
| **Webcam** | `0`, `1`, `2` | Local USB or built-in webcam |
| **IP Camera** | `http://192.168.1.100:8080/video` | Network HTTP video stream |
| **Video File** | `traffic.mp4` | Local pre-recorded video file |
| **RTSP** | `rtsp://admin:pass@192.168.1.100:554/stream` | Security camera stream |
| **ESP32-CAM** | `http://192.168.0.100/cam-hi.jpg` | Embedded Wi-Fi camera |

---

## Database Schema

```sql
-- Vehicle detection logs
CREATE TABLE vehicle_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER NOT NULL,
    vehicle_type TEXT NOT NULL,
    speed REAL DEFAULT 0,
    direction TEXT,
    timestamp TEXT NOT NULL,
    snapshot_path TEXT
);

-- Alert records
CREATE TABLE alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type TEXT NOT NULL,      -- 'speed_violation', 'wrong_way', 'intrusion', 'congestion'
    severity TEXT NOT NULL,        -- 'critical', 'warning', 'info'
    message TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    acknowledged INTEGER DEFAULT 0,
    snapshot_path TEXT
);

-- Hourly aggregated counts for charts
CREATE TABLE hourly_counts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,            -- '2025-07-30'
    hour INTEGER NOT NULL,          -- 0-23
    count INTEGER DEFAULT 0,
    UNIQUE(date, hour)
);

-- Key-value settings
CREATE TABLE system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

---

## Web Pages

| Page | Purpose |
| :--- | :--- |
| **Dashboard** | Overview: 4 stat cards, live camera preview, hourly chart, vehicle type donut chart, active tracks table |
| **Live Camera** | Full-screen camera view with HUD overlay, quick source switcher, track list, snapshot button |
| **Analytics** | Hourly traffic bar/line chart, violation breakdown donut, speed distribution bar chart, peak hours list |
| **Vehicles** | Paginated table of all detected vehicles with date/type filters, clickable track IDs |
| **Vehicle Detail** | Per-vehicle page: snapshot, speed analysis, tracking info, associated alerts, timeline |
| **Alerts** | Filterable alert list (All/Critical/Warning/Info/Unacknowledged), acknowledge buttons |
| **Settings** | Camera source, detection parameters, feature toggles, system info, clear data options |

---

## API Reference

### System
- `GET /api/status` — Running state, FPS, source, active vehicles, unacknowledged alerts
- `POST /api/camera/start` — Start camera. Body: `{"source": "0"}`
- `POST /api/camera/stop` — Stop camera
- `POST /api/camera/test` — Test if a source works. Body: `{"source": "0"}`

### Vehicles
- `GET /api/vehicles?limit=20&offset=0&date=2025-07-30&type=car` — Paginated vehicle log with filters
- `GET /api/vehicles/<track_id>` — Full detail for one vehicle

### Analytics
- `GET /api/analytics/hourly?days=1` — Hourly counts for chart
- `GET /api/analytics/summary` — Today's total, violation counts, unacknowledged alert count

### Alerts
- `GET /api/alerts?limit=50&unacknowledged=true` — Alert list with filters
- `POST /api/alerts/<id>/ack` — Acknowledge an alert

### Settings & Data
- `GET /api/settings` — Get all saved settings
- `POST /api/settings` — Save settings
- `POST /api/clear-data` — Delete all snapshots + clear database tables
- `GET /video_feed` — MJPEG video stream

---

## Installation

### Step-by-Step Setup

```bash
# 1. Create project directory
mkdir ai-car-tracking-system && cd ai-car-tracking-system
mkdir -p core database services static/css static/js templates
mkdir -p snapshots clips uploads models

# 2. Create virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Download YOLOv8n model
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

# 5. Run the server
python app.py
```

Open `http://localhost:5000` in your browser.

---

## Configuration

Main parameters in `config.py`:

| Setting | Default | Description |
| :--- | :--- | :--- |
| `CAMERA_SOURCE` | `0` | Default camera index or stream URL |
| `YOLO_CONFIDENCE_THRESHOLD` | `0.45` | Min confidence threshold (0.01–0.99) |
| `COUNTING_LINE_Y` | `300` | Y coordinate for counting line |
| `PIXELS_PER_METER` | `15.0` | Calibration factor for speed estimation |
| `SPEED_LIMIT_KMH` | `60.0` | Speed threshold for alerts |
| `NORFAIR_DISTANCE_THRESHOLD` | `30` | Max pixel distance to match tracks |
| `MAX_DISAPPEARED` | `30` | Frames before removing a track |
| `CONGESTION_THRESHOLD` | `8` | Vehicles above this threshold = congested |
| `WRONG_WAY_ENABLED` | `True` | Enable wrong-way detection |
| `INTRUSION_ENABLED` | `True` | Enable intrusion detection |
| `CONGESTION_ENABLED` | `True` | Enable congestion analysis |
| `PARKING_ENABLED` | `False` | Enable parking monitoring |
| `AUTO_SAVE_SNAPSHOTS` | `True` | Auto-save vehicle images |
| `TRACKER_TYPE` | `"norfair"` | `"norfair"` or `"centroid"` |
| `FLASK_PORT` | `5000` | Web server port |
| `FLASK_DEBUG` | `False` | Set `True` for detailed error messages |

---

## Troubleshooting

- **"Model not found" error:**  
  Run `python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"` and place `yolov8n.pt` into `models/`.
- **Camera shows "Camera Offline":**  
  Click "Start Camera" in the top bar or verify video source URL/index.
- **No bounding boxes detected:**  
  Check camera positioning or lower confidence threshold to `0.20` in Settings.
- **Green line shows but no cars counted:**  
  Adjust `COUNTING_LINE_Y` in Settings to align with vehicle movement across the screen.
- **Performance is slow:**  
  Reduce resolution (`CAMERA_WIDTH = 640`) or use GPU acceleration if available.

---

## Technical Decisions

| Decision | Reason |
| :--- | :--- |
| **YOLOv8n** | Smallest model (6MB), fast on CPU, sufficient detection accuracy |
| **Norfair** | Superior tracking stability vs simple centroid distance |
| **SQLite** | Zero configuration, local single-file database for edge deployment |
| **Threading Mode** | Keeps web server responsive while background thread captures video |
| **MJPEG Stream** | Lightweight stream format, compatible across all browsers |
| **Socket.IO** | Real-time data updates without polling overhead |
| **Light Theme** | Professional look, easy to read in presentations |
| **`allow_unsafe_werkzeug=True`** | Required for threading mode in development |
| **`weights_only=False`** | Required for PyTorch 2.6+ model loading |

---

## Extending the System

1. **Adding a new analytics module:**  
   Define method in `core/analytics.py` -> call in `services/processor.py` -> emit payload via Socket.IO -> add UI component.
2. **Adding a new web page:**  
   Create template in `templates/newpage.html` -> add route in `app.py` -> add navigation link in `templates/base.html`.
3. **Database modifications:**  
   Update schema in `database/models.py` -> update relevant CRUD queries.
