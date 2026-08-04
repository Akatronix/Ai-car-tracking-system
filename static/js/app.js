/**
 * TrackVision — Main JS
 * Handles camera state, Socket.IO, clock, toasts, sidebar.
 */

const socket = io();
let cameraRunning = false;

// ── On page load: sync button state with actual server state ──
document.addEventListener("DOMContentLoaded", () => {
  syncCameraState();
  setInterval(syncCameraState, 2000);
});

async function syncCameraState() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    const wasRunning = cameraRunning;
    cameraRunning = data.running;

    // ── Update start/stop button ──
    const btn = document.getElementById("cameraToggleBtn");
    if (btn) {
      if (cameraRunning) {
        btn.innerHTML =
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg><span>Stop Camera</span>';
        btn.classList.add("btn-active");
      } else {
        btn.innerHTML =
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polygon points="5 3 19 12 5 21 5 3"/></svg><span>Start Camera</span>';
        btn.classList.remove("btn-active");
      }
      btn.disabled = false;
    }

    // ── Update source label in top bar ──
    const si = document.getElementById("sourceIndicator");
    const sl = document.getElementById("sourceLabel");
    if (si && sl) {
      if (data.running) {
        si.style.display = "inline-flex";
        const label =
          data.source && data.source.length > 30
            ? data.source.substring(0, 30) + "..."
            : data.source;
        sl.textContent = label;
      } else {
        si.style.display = "none";
      }
    }

    // ── Update FPS ──
    const fEl = document.getElementById("fpsValue");
    const fDisp = document.getElementById("fpsDisplay");
    if (fEl) fEl.textContent = data.fps;
    if (fDisp)
      fDisp.style.display = data.running && data.fps > 0 ? "block" : "none";

    // ── Update live indicators ──
    showLiveIndicators(data.running);

    // ── Update sidebar status ──
    setStatus(data.running);

    // ── Update alert badge ──
    const badge = document.getElementById("alertBadge");
    if (badge) {
      if (data.unacknowledged_alerts > 0) {
        badge.style.display = "inline-flex";
        badge.textContent = data.unacknowledged_alerts;
      } else {
        badge.style.display = "none";
      }
    }

    // ── If camera just turned on, force browser to reconnect stream ──
    if (!wasRunning && cameraRunning) {
      reloadAllFeeds();
    }

    // ── Update camera page source display ──
    const camSrc = document.getElementById("camSource");
    if (camSrc && data.running) {
      const s = data.source || "—";
      camSrc.textContent = s.length > 20 ? s.substring(0, 20) + "..." : s;
    }
  } catch (e) {
    // Server might not be ready yet
  }
}

function reloadAllFeeds() {
  const t = Date.now();
  document
    .querySelectorAll(".camera-feed, .camera-feed-full")
    .forEach((img) => {
      const currentSrc = img.src;
      img.src = "";
      // Small delay ensures browser treats it as a new stream
      setTimeout(() => {
        img.src = "/video_feed?t=" + t;
      }, 100);
    });
}

// ── Camera toggle (top bar button) ──
function toggleCamera() {
  if (cameraRunning) stopCamera();
  else startCamera();
}

function startCamera() {
  const srcEl = document.getElementById("cameraSource");
  const src = srcEl ? srcEl.value : "0";
  const btn = document.getElementById("cameraToggleBtn");
  btn.innerHTML =
    '<svg class="spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M21 12a9 9 0 11-6.219-8.56"/></svg><span>Starting...</span>';
  btn.disabled = true;

  fetch("/api/camera/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source: src }),
  })
    .then((r) => r.json())
    .then((d) => {
      btn.disabled = false;
      if (d.success) {
        cameraRunning = true;
        btn.innerHTML =
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg><span>Stop Camera</span>';
        btn.classList.add("btn-active");
        showLiveIndicators(true);
        reloadAllFeeds();
        const si = document.getElementById("sourceIndicator");
        const sl = document.getElementById("sourceLabel");
        if (si && sl) {
          si.style.display = "inline-flex";
          sl.textContent = d.source;
        }
        showToast("Camera started: " + d.source, "success");
      } else {
        btn.innerHTML =
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polygon points="5 3 19 12 5 21 5 3"/></svg><span>Start Camera</span>';
        showToast("Failed to open source", "error");
      }
    })
    .catch(() => {
      btn.disabled = false;
      btn.innerHTML =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polygon points="5 3 19 12 5 21 5 3"/></svg><span>Start Camera</span>';
      showToast("Connection error", "error");
    });
}

function stopCamera() {
  const btn = document.getElementById("cameraToggleBtn");
  btn.innerHTML =
    '<svg class="spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M21 12a9 9 0 11-6.219-8.56"/></svg><span>Stopping...</span>';
  btn.disabled = true;

  fetch("/api/camera/stop", { method: "POST" }).then(() => {
    cameraRunning = false;
    btn.disabled = false;
    btn.innerHTML =
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polygon points="5 3 19 12 5 21 5 3"/></svg><span>Start Camera</span>';
    btn.classList.remove("btn-active");
    showLiveIndicators(false);
    const si = document.getElementById("sourceIndicator");
    if (si) si.style.display = "none";
    const fDisp = document.getElementById("fpsDisplay");
    if (fDisp) fDisp.style.display = "none";
    showToast("Camera stopped", "info");
  });
}

function showLiveIndicators(show) {
  document.querySelectorAll("#liveIndicator, #camLive").forEach((el) => {
    el.style.display = show ? "inline-flex" : "none";
  });
}

function setStatus(on) {
  const dot = document.querySelector(".status-dot");
  const txt = document.querySelector(".status-text");
  if (dot && txt) {
    dot.className = "status-dot " + (on ? "online" : "offline");
    txt.textContent = on ? "System Online" : "System Offline";
  }
}

// ── Live Clock ──
function tick() {
  const now = new Date();
  const el = document.getElementById("liveClock");
  if (el) el.textContent = now.toLocaleTimeString("en-US", { hour12: false });
  const ct = document.getElementById("camTs");
  if (ct)
    ct.textContent = now.toLocaleString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
}
setInterval(tick, 1000);
tick();

// ── Toast Notifications ──
function showToast(msg, type) {
  type = type || "info";
  const c = document.getElementById("toastContainer");
  const t = document.createElement("div");
  t.className = "toast " + type;
  const icons = {
    success:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
    error:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
    info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
    warning:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
  };
  t.innerHTML = (icons[type] || icons.info) + "<span>" + msg + "</span>";
  c.appendChild(t);
  setTimeout(() => {
    t.style.animation = "toastOut 0.3s ease forwards";
    setTimeout(() => t.remove(), 300);
  }, 3500);
}

// ── Time Formatter ──
function formatTime(ts) {
  if (!ts) return "—";
  return new Date(ts).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

// ── Sidebar Toggle (mobile) ──
document.getElementById("menuToggle").addEventListener("click", () => {
  document.getElementById("sidebar").classList.toggle("open");
});

// ── Socket.IO ──
socket.on("connect", () => {
  console.log("[IO] Connected");
});
socket.on("disconnect", () => {
  console.log("[IO] Disconnected");
});
socket.on("tracking_update", (data) => {
  const fEl = document.getElementById("fpsValue");
  if (fEl) fEl.textContent = data.fps;
  const fd = document.getElementById("fpsDisplay");
  if (fd && data.fps > 0) fd.style.display = "block";
  if (window.onTrackingUpdate) window.onTrackingUpdate(data);
});
