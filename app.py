# """
# TrackVision — AI Car Tracking System
# """

# import os
# import time
# import cv2
# import numpy as np
# from flask import Flask, render_template, request, jsonify, Response, send_from_directory
# from flask_socketio import SocketIO

# import config
# from services.processor import VideoProcessor, parse_source
# from database.models import DatabaseManager

# app = Flask(__name__)
# app.config["SECRET_KEY"] = config.SECRET_KEY
# socketio = SocketIO(app, async_mode="threading", cors_allowed_origins="*")

# processor = VideoProcessor(socketio=socketio)
# db = DatabaseManager()
# _stream_version = 0
# _last_frame = None


# @app.route("/")
# def index():
#     return render_template("index.html")

# @app.route("/camera")
# def camera():
#     return render_template("camera.html")

# @app.route("/analytics")
# def analytics():
#     return render_template("analytics.html")

# @app.route("/vehicles")
# def vehicles():
#     return render_template("vehicles.html")

# @app.route("/alerts")
# def alerts():
#     return render_template("alerts.html")

# @app.route("/settings")
# def settings():
#     return render_template("settings.html")


# # Store the last good frame globally
# _last_frame = None


# def gen_frames():
#     global _last_frame
#     my_version = _stream_version
#     while True:
#         # Kill old streams when camera stops or restarts
#         if my_version != _stream_version:
#             break

#         if not processor.running:
#             # Camera off — keep showing last frame, don't spam
#             if _last_frame is not None:
#                 ret, buf = cv2.imencode(".jpg", _last_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
#                 yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")
#             else:
#                 blank = np.zeros((720, 1280, 3), dtype=np.uint8)
#                 cv2.putText(blank, "Camera Offline", (440, 360),
#                             cv2.FONT_HERSHEY_SIMPLEX, 1.2, (120, 120, 120), 2)
#                 ret, buf = cv2.imencode(".jpg", blank, [cv2.IMWRITE_JPEG_QUALITY, 85])
#                 yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")
#             time.sleep(0.5)
#             continue

#         frame = processor.get_frame()
#         if frame is not None:
#             _last_frame = frame

#         if _last_frame is not None:
#             ret, buf = cv2.imencode(".jpg", _last_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
#             yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")

#         time.sleep(0.033)


# @app.route("/video_feed")
# def video_feed():
#     return Response(
#         gen_frames(),
#         mimetype="multipart/x-mixed-replace; boundary=frame",
#         headers={
#             "Cache-Control": "no-cache, no-store, must-revalidate",
#             "Pragma": "no-cache",
#             "Expires": "0",
#         }
#     )

# @app.route("/api/status")
# def api_status():
#     return jsonify({
#         "running": processor.running,
#         "fps": round(processor.fps, 1),
#         "source": processor.source_raw,
#         "active_vehicles": sum(1 for t in processor.tracker.tracks.values() if t.confirmed) if processor.tracker else 0,
#         "total_counted": processor.counter.count_in + processor.counter.count_out,
#         "unacknowledged_alerts": db.unack_count(),
#     })

# @app.route("/api/camera/start", methods=["POST"])
# def api_start():
#     global _stream_version
#     data = request.get_json(silent=True) or {}
#     source = data.get("source", "0")

#     # Force stop if running, even if thread is dead
#     processor.running = False
#     if processor.thread and processor.thread.is_alive():
#         processor.thread.join(timeout=2)
#     if processor.cap:
#         try:
#             processor.cap.release()
#         except Exception:
#             pass
#         processor.cap = None
#     time.sleep(0.3)

#     _stream_version += 1
#     ok = processor.start(source)
#     return jsonify({"success": ok, "source": processor.source_raw})


# @app.route("/api/camera/stop", methods=["POST"])
# def api_stop():
#     global _stream_version
#     processor.stop()
#     _stream_version += 1          # ← ADD THIS LINE
#     return jsonify({"success": True})

#     processor.stop()
#     return jsonify({"success": True})

# @app.route("/api/camera/test", methods=["POST"])
# def api_test():
#     data = request.get_json(silent=True) or {}
#     raw = data.get("source", "0")
#     parsed = parse_source(raw)
#     cap = cv2.VideoCapture(parsed)
#     ok = cap.isOpened()
#     result = {"success": False, "source": raw}
#     if ok:
#         ret, _ = cap.read()
#         w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
#         h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
#         fps = cap.get(cv2.CAP_PROP_FPS)
#         cap.release()
#         result.update({"success": True, "resolution": f"{w}x{h}", "fps": round(fps, 1) if fps > 0 else "N/A", "test_frame": ret})
#     else:
#         try: cap.release()
#         except: pass
#         result["error"] = "Cannot open source"
#     return jsonify(result)

# @app.route("/api/vehicles")
# def api_vehicles():
#     lim = request.args.get("limit", 100, type=int)
#     off = request.args.get("offset", 0, type=int)
#     return jsonify(db.get_vehicles(lim, off, request.args.get("date"), request.args.get("type")))

# @app.route("/api/alerts")
# def api_alerts():
#     return jsonify(db.get_alerts(request.args.get("limit", 50, type=int), request.args.get("unacknowledged", "false").lower() == "true"))

# @app.route("/api/alerts/<int:aid>/ack", methods=["POST"])
# def api_ack(aid):
#     db.ack_alert(aid)
#     return jsonify({"success": True})

# @app.route("/api/analytics/hourly")
# def api_hourly():
#     return jsonify(db.get_hourly(request.args.get("days", 1, type=int)))

# @app.route("/api/analytics/summary")
# def api_summary():
#     alerts = db.get_alerts(limit=10000)
#     return jsonify({
#         "today_count": db.get_today_count(),
#         "total_logged": db.get_total_today(),
#         "speed_violations": sum(1 for a in alerts if a["alert_type"] == "speed_violation"),
#         "wrong_way_violations": sum(1 for a in alerts if a["alert_type"] == "wrong_way"),
#         "intrusions": sum(1 for a in alerts if a["alert_type"] == "intrusion"),
#         "total_alerts": len(alerts),
#         "unacknowledged": db.unack_count(),
#     })

# @app.route("/api/settings", methods=["POST"])
# def api_save_settings():
#     data = request.get_json()
#     for k, v in data.items():
#         db.set_setting(k, str(v))
#     if "confidence_threshold" in data:
#         # Settings slider is 10-90 (percentage), YOLO needs 0.0-1.0
#         raw = float(data["confidence_threshold"])
#         config.YOLO_CONFIDENCE_THRESHOLD = max(0.01, min(1.0, raw / 100.0))
#         processor.detector.conf = config.YOLO_CONFIDENCE_THRESHOLD
#     if "speed_limit" in data:
#         config.SPEED_LIMIT_KMH = float(data["speed_limit"])
#         processor.speed_estimator.speed_limit = config.SPEED_LIMIT_KMH
#     if "counting_line_y" in data:
#         config.COUNTING_LINE_Y = int(data["counting_line_y"])
#         processor.counter.line_y = config.COUNTING_LINE_Y
#     return jsonify({"success": True})
#     keys = ["confidence_threshold","speed_limit","counting_direction","expected_direction","congestion_threshold","auto_snapshots","wrong_way_enabled","intrusion_enabled","congestion_enabled","parking_enabled","tracker_type","camera_source","counting_line_y"]
#     return jsonify({k: db.get_setting(k, "") for k in keys})

# @app.route("/api/settings", methods=["POST"])
# def api_save_settings():
#     data = request.get_json()
#     for k, v in data.items():
#         db.set_setting(k, str(v))
#     if "confidence_threshold" in data:
#         config.YOLO_CONFIDENCE_THRESHOLD = float(data["confidence_threshold"])
#         processor.detector.conf = config.YOLO_CONFIDENCE_THRESHOLD
#     if "speed_limit" in data:
#         config.SPEED_LIMIT_KMH = float(data["speed_limit"])
#         processor.speed_estimator.speed_limit = config.SPEED_LIMIT_KMH
#     if "counting_line_y" in data:
#         config.COUNTING_LINE_Y = int(data["counting_line_y"])
#         processor.counter.line_y = config.COUNTING_LINE_Y
#     return jsonify({"success": True})

# @app.route("/snapshots/<path:fn>")
# def serve_snap(fn):
#     return send_from_directory(config.SNAPSHOT_DIR, fn)


# @socketio.on("connect")
# def on_connect():
#     socketio.emit("tracking_update", {
#         "fps": 0, "active_vehicles": 0,
#         "total_counted": processor.counter.count_in + processor.counter.count_out,
#         "count_in": processor.counter.count_in, "count_out": processor.counter.count_out,
#         "congestion": {"count": 0, "level": 0, "congested": False},
#         "parking": {}, "tracks": [],
#     })

# if __name__ == "__main__":
#     print("=" * 60)
#     print("  TrackVision — AI Car Tracking System")
#     print("  Open http://localhost:5000 in your browser")
#     print("=" * 60)
#     socketio.run(app, host=config.FLASK_HOST, port=config.FLASK_PORT,
#                  debug=config.FLASK_DEBUG, allow_unsafe_werkzeug=True)






"""
TrackVision — AI Car Tracking System
"""

import os
import time
import cv2
import numpy as np
from flask import Flask, render_template, request, jsonify, Response, send_from_directory
from flask_socketio import SocketIO

import config
from services.processor import VideoProcessor, parse_source
from database.models import DatabaseManager

app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY
socketio = SocketIO(app, async_mode="threading", cors_allowed_origins="*")

processor = VideoProcessor(socketio=socketio)
db = DatabaseManager()

_stream_version = 0
_last_frame = None


# ═══════════════════════════════════════════════════════════
#  PAGE ROUTES
# ═══════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/camera")
def camera():
    return render_template("camera.html")

@app.route("/analytics")
def analytics():
    return render_template("analytics.html")

@app.route("/vehicles")
def vehicles():
    return render_template("vehicles.html")

@app.route("/vehicles/<int:track_id>")
def vehicle_detail(track_id):
    return render_template("vehicle_detail.html", track_id=track_id)


@app.route("/api/vehicles/<int:track_id>")
def api_vehicle_detail(track_id):
    try:
        data = db.get_vehicle_detail(track_id)
        return jsonify(data)
    except Exception as e:
        print(f"[API] Vehicle detail error: {e}")
        return jsonify({
            "track_id": track_id,
            "vehicle_type": "unknown",
            "snapshot": None,
            "first_seen": None,
            "last_seen": None,
            "avg_speed": 0,
            "max_speed": 0,
            "direction": "—",
            "detection_count": 0,
            "logs": [],
            "alerts": [],
        }), 500


@app.route("/alerts")
def alerts():
    return render_template("alerts.html")

@app.route("/settings")
def settings():
    return render_template("settings.html")


# ═══════════════════════════════════════════════════════════
#  VIDEO STREAMING
# ═══════════════════════════════════════════════════════════

def gen_frames():
    global _last_frame
    my_version = _stream_version
    while True:
        if my_version != _stream_version:
            break

        if not processor.running:
            if _last_frame is not None:
                ret, buf = cv2.imencode(".jpg", _last_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")
            else:
                blank = np.zeros((720, 1280, 3), dtype=np.uint8)
                cv2.putText(blank, "Camera Offline", (440, 360),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.2, (120, 120, 120), 2)
                ret, buf = cv2.imencode(".jpg", blank, [cv2.IMWRITE_JPEG_QUALITY, 85])
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")
            time.sleep(0.5)
            continue

        frame = processor.get_frame()
        if frame is not None:
            _last_frame = frame

        if _last_frame is not None:
            ret, buf = cv2.imencode(".jpg", _last_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")

        time.sleep(0.033)


@app.route("/video_feed")
def video_feed():
    return Response(
        gen_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
    )


# ═══════════════════════════════════════════════════════════
#  API ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.route("/api/status")
def api_status():
    return jsonify({
        "running": processor.running,
        "fps": round(processor.fps, 1),
        "source": processor.source_raw,
        "active_vehicles": sum(1 for t in processor.tracker.tracks.values() if t.confirmed) if processor.tracker else 0,
        "total_counted": processor.counter.count_in + processor.counter.count_out,
        "unacknowledged_alerts": db.unack_count(),
    })


@app.route("/api/camera/start", methods=["POST"])
def api_start():
    global _stream_version
    data = request.get_json(silent=True) or {}
    source = data.get("source", "0")

    # Force stop if running
    processor.running = False
    if processor.thread and processor.thread.is_alive():
        processor.thread.join(timeout=2)
    if processor.cap:
        try:
            processor.cap.release()
        except Exception:
            pass
        processor.cap = None
    time.sleep(0.3)

    _stream_version += 1
    ok = processor.start(source)
    return jsonify({"success": ok, "source": processor.source_raw})


@app.route("/api/camera/stop", methods=["POST"])
def api_stop():
    global _stream_version
    processor.stop()
    _stream_version += 1
    return jsonify({"success": True})


@app.route("/api/camera/test", methods=["POST"])
def api_test():
    data = request.get_json(silent=True) or {}
    raw = data.get("source", "0")
    parsed = parse_source(raw)
    cap = cv2.VideoCapture(parsed)
    ok = cap.isOpened()
    result = {"success": False, "source": raw}
    if ok:
        ret, _ = cap.read()
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()
        result.update({"success": True, "resolution": f"{w}x{h}", "fps": round(fps, 1) if fps > 0 else "N/A", "test_frame": ret})
    else:
        try:
            cap.release()
        except Exception:
            pass
        result["error"] = "Cannot open source"
    return jsonify(result)


@app.route("/api/vehicles")
def api_vehicles():
    lim = request.args.get("limit", 100, type=int)
    off = request.args.get("offset", 0, type=int)
    return jsonify(db.get_vehicles(lim, off, request.args.get("date"), request.args.get("type")))


@app.route("/api/alerts")
def api_alerts():
    return jsonify(db.get_alerts(request.args.get("limit", 50, type=int), request.args.get("unacknowledged", "false").lower() == "true"))


@app.route("/api/alerts/<int:aid>/ack", methods=["POST"])
def api_ack(aid):
    db.ack_alert(aid)
    return jsonify({"success": True})


@app.route("/api/analytics/hourly")
def api_hourly():
    return jsonify(db.get_hourly(request.args.get("days", 1, type=int)))


@app.route("/api/analytics/summary")
def api_summary():
    alerts = db.get_alerts(limit=10000)
    return jsonify({
        "today_count": db.get_today_count(),
        "total_logged": db.get_total_today(),
        "speed_violations": sum(1 for a in alerts if a["alert_type"] == "speed_violation"),
        "wrong_way_violations": sum(1 for a in alerts if a["alert_type"] == "wrong_way"),
        "intrusions": sum(1 for a in alerts if a["alert_type"] == "intrusion"),
        "total_alerts": len(alerts),
        "unacknowledged": db.unack_count(),
    })


@app.route("/api/settings", methods=["GET"])
def api_get_settings():
    keys = [
        "confidence_threshold", "speed_limit", "counting_direction",
        "expected_direction", "congestion_threshold", "auto_snapshots",
        "wrong_way_enabled", "intrusion_enabled", "congestion_enabled",
        "parking_enabled", "tracker_type", "camera_source", "counting_line_y"
    ]
    return jsonify({k: db.get_setting(k, "") for k in keys})


@app.route("/api/settings", methods=["POST"])
def api_save_settings():
    data = request.get_json()
    for k, v in data.items():
        db.set_setting(k, str(v))
    if "confidence_threshold" in data:
        raw = float(data["confidence_threshold"])
        config.YOLO_CONFIDENCE_THRESHOLD = max(0.01, min(1.0, raw / 100.0))
        processor.detector.conf = config.YOLO_CONFIDENCE_THRESHOLD
    if "speed_limit" in data:
        config.SPEED_LIMIT_KMH = float(data["speed_limit"])
        processor.speed_estimator.speed_limit = config.SPEED_LIMIT_KMH
    if "counting_line_y" in data:
        config.COUNTING_LINE_Y = int(data["counting_line_y"])
        processor.counter.line_y = config.COUNTING_LINE_Y
    return jsonify({"success": True})

@app.route("/api/snapshots")
def api_snapshots():
    import os
    snap_dir = config.SNAPSHOT_DIR
    files = []
    if os.path.exists(snap_dir):
        for f in sorted(os.listdir(snap_dir), reverse=True)[:50]:
            if f.endswith((".jpg", ".png")):
                files.append(f)
    return jsonify(files)


@app.route("/api/clear-data", methods=["POST"])
def api_clear_data():
    import os
    try:
        # Clear snapshots
        snap_dir = config.SNAPSHOT_DIR
        count = 0
        if os.path.exists(snap_dir):
            for f in os.listdir(snap_dir):
                fp = os.path.join(snap_dir, f)
                if os.path.isfile(fp):
                    os.remove(fp)
                    count += 1

        # Clear clips
        clip_dir = config.CLIP_DIR
        if os.path.exists(clip_dir):
            for f in os.listdir(clip_dir):
                fp = os.path.join(clip_dir, f)
                if os.path.isfile(fp):
                    os.remove(fp)

        # Clear database tables
        c = db._conn()
        c.execute("DELETE FROM vehicle_logs")
        c.execute("DELETE FROM alerts")
        c.execute("DELETE FROM hourly_counts")
        c.commit()
        c.execute("VACUUM")
        c.commit()
        c.close()

        return jsonify({"success": True, "deleted_files": count})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})



@app.route("/snapshots/<path:fn>")
def serve_snap(fn):
    return send_from_directory(config.SNAPSHOT_DIR, fn)




# ═══════════════════════════════════════════════════════════
#  SOCKET.IO
# ═══════════════════════════════════════════════════════════

@socketio.on("connect")
def on_connect():
    socketio.emit("tracking_update", {
        "fps": 0, "active_vehicles": 0,
        "total_counted": processor.counter.count_in + processor.counter.count_out,
        "count_in": processor.counter.count_in, "count_out": processor.counter.count_out,
        "congestion": {"count": 0, "level": 0, "congested": False},
        "parking": {}, "tracks": [],
    })


# ═══════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  TrackVision — AI Car Tracking System")
    print("  Open http://localhost:5000 in your browser")
    print("=" * 60)
    # socketio.run(app, host=config.FLASK_HOST, port=config.FLASK_PORT,
    #              debug=config.FLASK_DEBUG, allow_unsafe_werkzeug=True)
    socketio.run(app, host=config.FLASK_HOST, port=config.FLASK_PORT,
             debug=True, allow_unsafe_werkzeug=True)