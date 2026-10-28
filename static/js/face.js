(() => {
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const CHANNEL = "emotune-face";
  const EMO_META = {
    happy: { zh: "喜", name: "喜悦", color: "#f0c14b" },
    angry: { zh: "怒", name: "愤怒", color: "#e23d3d" },
    sad: { zh: "哀", name: "悲伤", color: "#5b8cff" },
    fear: { zh: "惧", name: "恐惧", color: "#8b6ccf" },
    surprise: { zh: "惊", name: "惊讶", color: "#ff6b9d" },
    disgust: { zh: "厌", name: "厌恶", color: "#3d8b6e" },
    neutral: { zh: "中", name: "平静", color: "#8b9bb4" },
    idle: { zh: "待", name: "待识别", color: "#c4a574" },
  };
  const FACE_MODE_META = {
    solo: { id: "solo", zh: "单人精检", blurb: "只取画面里最大、最稳的一张脸。近景融合两套表情模型。" },
    crowd: { id: "crowd", zh: "多人远场", blurb: "同时框出多张脸和远景小脸，歌曲按人数最多的情绪来。" },
  };

  const params = new URLSearchParams(location.search);
  const state = {
    stream: null,
    live: false,
    liveTimer: 0,
    trackOn: false,
    trackTimer: 0,
    trackBusy: false,
    recognizing: false,
    overlaySmooth: [],
    theme: localStorage.getItem("emotune-theme") || "night",
    onlineOn: localStorage.getItem("emotune-online") !== "0",
    faceMode: params.get("mode") || localStorage.getItem("emotune-face-mode") || "solo",
    camId: params.get("cam") || localStorage.getItem("emotune-cam") || "",
    mirror: true,
  };
  if (!FACE_MODE_META[state.faceMode]) state.faceMode = "solo";
  const channel = "BroadcastChannel" in window ? new BroadcastChannel(CHANNEL) : null;
  const cam = $("#cam");
  const overlay = $("#face-overlay");
  const shot = $("#shot");
  const empty = $("#cam-empty");

  document.documentElement.dataset.theme = state.theme;
  if (cam) cam.classList.toggle("is-mirror", state.mirror);

  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );
  }
  function emoHex(id, fromApi) {
    if (fromApi && /^#[0-9a-fA-F]{3,8}$/.test(String(fromApi))) return fromApi;
    return (EMO_META[id] || EMO_META.idle).color;
  }
  function hexToRgba(hex, alpha) {
    const h = String(hex || "").replace("#", "");
    const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
    const n = parseInt(full, 16);
    if (!Number.isFinite(n)) return `rgba(196,165,116,${alpha})`;
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`;
  }
  function roundRectPath(ctx, x, y, w, h, r) {
    const rr = Math.max(0, Math.min(r, w / 2, h / 2));
    ctx.beginPath();
    ctx.moveTo(x + rr, y);
    ctx.arcTo(x + w, y, x + w, y + h, rr);
    ctx.arcTo(x + w, y + h, x, y + h, rr);
    ctx.arcTo(x, y + h, x, y, rr);
    ctx.arcTo(x, y, x + w, y, rr);
    ctx.closePath();
  }
  function sizeOverlay() {
    const vp = $("#viewport");
    if (!overlay || !vp) return null;
    const cssW = vp.clientWidth;
    const cssH = vp.clientHeight;
    if (cssW < 8 || cssH < 8) return null;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const w = Math.round(cssW * dpr);
    const h = Math.round(cssH * dpr);
    if (overlay.width !== w || overlay.height !== h) {
      overlay.width = w;
      overlay.height = h;
      overlay.style.width = `${cssW}px`;
      overlay.style.height = `${cssH}px`;
    }
    return { cssW, cssH, dpr };
  }
  function mapBox(box, imageSize, sized, mirror) {
    let [x, y, bw, bh] = box.map(Number);
    const [iw, ih] = imageSize.map(Number);
    if (!iw || !ih || !bw || !bh) return null;
    if (mirror) x = iw - x - bw;
    const scale = Math.max(sized.cssW / iw, sized.cssH / ih);
    const dw = iw * scale;
    const dh = ih * scale;
    const ox = (sized.cssW - dw) / 2;
    const oy = (sized.cssH - dh) / 2;
    return {
      x: (ox + x * scale) * sized.dpr,
      y: (oy + y * scale) * sized.dpr,
      w: bw * scale * sized.dpr,
      h: bh * scale * sized.dpr,
    };
  }
  function iou(a, b) {
    const x1 = Math.max(a.x, b.x);
    const y1 = Math.max(a.y, b.y);
    const x2 = Math.min(a.x + a.w, b.x + b.w);
    const y2 = Math.min(a.y + a.h, b.y + b.h);
    const inter = Math.max(0, x2 - x1) * Math.max(0, y2 - y1);
    const ua = a.w * a.h + b.w * b.h - inter;
    return ua > 0 ? inter / ua : 0;
  }
  function lerpBox(a, b, t) {
    if (!a) return b;
    return {
      x: a.x + (b.x - a.x) * t,
      y: a.y + (b.y - a.y) * t,
      w: a.w + (b.w - a.w) * t,
      h: a.h + (b.h - a.h) * t,
    };
  }

  function post(msg) {
    try {
      channel && channel.postMessage(msg);
    } catch {
      /* ignore */
    }
  }

  function paintFaceMode() {
    const meta = FACE_MODE_META[state.faceMode] || FACE_MODE_META.solo;
    $$("#face-mode-picks [data-face-mode]").forEach((btn) => {
      const on = btn.dataset.faceMode === meta.id;
      btn.classList.toggle("is-on", on);
      btn.setAttribute("aria-checked", on ? "true" : "false");
    });
    const lead = $("#face-lead");
    if (lead) {
      lead.textContent =
        meta.id === "crowd"
          ? "多人远场：可同时框出多张脸，包括远景小脸。歌曲按人数最多的情绪来。"
          : "单人精检：只认近景里最大最稳的一张脸。需要合影或远镜头时再切多人远场。";
    }
  }

  function setFaceMode(id, persist, silent) {
    const meta = FACE_MODE_META[id] || FACE_MODE_META.solo;
    const changed = state.faceMode !== meta.id;
    state.faceMode = meta.id;
    localStorage.setItem("emotune-face-mode", state.faceMode);
    paintFaceMode();
    if (persist) {
      fetch("/api/prefs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ face_mode: state.faceMode }),
      }).catch(() => {});
      post({ type: "face-mode", id: state.faceMode });
    }
    if (changed && persist && !silent) {
      /* 主页会 toast；弹窗只改说明 */
    }
  }

  function cameraReady() {
    return Boolean(state.stream && cam && cam.videoWidth > 0);
  }

  function captureBlob(quality = 0.92, maxSide = 1280) {
    if (!cam.videoWidth) return Promise.resolve(null);
    const scale = Math.min(1, maxSide / Math.max(cam.videoWidth, cam.videoHeight));
    const w = Math.round(cam.videoWidth * scale);
    const h = Math.round(cam.videoHeight * scale);
    shot.width = w;
    shot.height = h;
    shot.getContext("2d").drawImage(cam, 0, 0, w, h);
    return new Promise((resolve) => shot.toBlob((b) => resolve(b), "image/jpeg", quality));
  }

  function setHint(text) {
    const el = $("#cam-empty-text");
    if (el) el.textContent = text;
  }

  async function listCameras() {
    const sel = $("#cam-select");
    if (!sel || !navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return;
    const devices = await navigator.mediaDevices.enumerateDevices().catch(() => []);
    const cams = devices.filter((d) => d.kind === "videoinput");
    const current = sel.value || state.camId || "";
    if (!cams.length) {
      sel.innerHTML = `<option value="">没有找到摄像头</option>`;
      return;
    }
    sel.innerHTML = cams
      .map((d, i) => {
        const label = d.label || `摄像头 ${i + 1}`;
        return `<option value="${esc(d.deviceId)}">${esc(label)}</option>`;
      })
      .join("");
    if (current && [...sel.options].some((o) => o.value === current)) sel.value = current;
    else if (state.camId && [...sel.options].some((o) => o.value === state.camId)) sel.value = state.camId;
    state.camId = sel.value || state.camId;
  }

  async function requestCameraStream() {
    const picked = ($("#cam-select") && $("#cam-select").value) || state.camId || "";
    const byId = (id, extra) => ({ video: Object.assign({ deviceId: { exact: id } }, extra || {}), audio: false });
    const attempts = [];
    if (picked) {
      attempts.push(byId(picked, { width: { ideal: 1920 }, height: { ideal: 1080 } }));
      attempts.push(byId(picked));
    }
    attempts.push(
      { video: { facingMode: { ideal: "user" }, width: { ideal: 1920 }, height: { ideal: 1080 } }, audio: false },
      { video: { facingMode: { ideal: "user" } }, audio: false },
      { video: true, audio: false }
    );
    let lastErr = null;
    for (const constraints of attempts) {
      try {
        return await navigator.mediaDevices.getUserMedia(constraints);
      } catch (err) {
        lastErr = err;
        if (err && (err.name === "NotAllowedError" || err.name === "PermissionDeniedError" || err.name === "SecurityError")) {
          throw err;
        }
      }
    }
    throw lastErr || new Error("无法打开摄像头");
  }

  async function startCamera() {
    if (cameraReady()) {
      empty.hidden = true;
      startTrack();
      return true;
    }
    try {
      if (state.stream) {
        state.stream.getTracks().forEach((t) => t.stop());
        state.stream = null;
      }
      const stream = await requestCameraStream();
      state.stream = stream;
      cam.srcObject = stream;
      cam.muted = true;
      cam.classList.toggle("is-mirror", state.mirror);
      await cam.play().catch(() => {});
      empty.hidden = true;
      const track = stream.getVideoTracks()[0];
      if (track && track.getSettings) {
        const id = track.getSettings().deviceId;
        if (id) {
          state.camId = id;
          localStorage.setItem("emotune-cam", id);
        }
      }
      await listCameras();
      startTrack();
      post({ type: "hello" });
      return true;
    } catch (err) {
      setHint(err && err.message ? err.message : "无法打开摄像头。请允许权限，或先关掉主页里的摄像头。");
      empty.hidden = false;
      return false;
    }
  }

  function stopCamera() {
    state.trackOn = false;
    if (state.trackTimer) clearTimeout(state.trackTimer);
    if (state.liveTimer) clearInterval(state.liveTimer);
    if (state.stream) state.stream.getTracks().forEach((t) => t.stop());
    state.stream = null;
    cam.srcObject = null;
  }

  function updateHud(data) {
    const hud = $("#live-emo-hud");
    if (!hud) return;
    hud.hidden = false;
    const emo = data && data.ok && data.emotion;
    const vote = (data && data.vote) || {};
    const countEl = $("#live-emo-count");
    if (!emo) {
      hud.dataset.emo = "idle";
      hud.classList.add("is-miss");
      $("#live-emo-zh").textContent = "";
      $("#live-emo-name").textContent = "寻找人脸";
      $("#live-emo-pct").textContent = "";
      if (countEl) countEl.textContent = "";
      return;
    }
    hud.classList.remove("is-miss");
    hud.dataset.emo = emo.id || "idle";
    const color = emoHex(emo.id, emo.color);
    hud.style.setProperty("--emo", color);
    const meta = EMO_META[emo.id] || {};
    $("#live-emo-zh").textContent = meta.zh || emo.zh || "";
    $("#live-emo-name").textContent = meta.name || emo.name || "";
    $("#live-emo-pct").textContent = Math.round((emo.prob || 0) * 100) ? `${Math.round(emo.prob * 100)}%` : "";
    const n = vote.total || data.face_count || 0;
    if (countEl) countEl.textContent = n > 1 ? `${n} 张 · 多数 ${vote.majority || n}` : n === 1 ? "1 张脸" : "";
    const bar = $("#vote-bar");
    if (bar) {
      const counts = vote.counts || {};
      const keys = Object.keys(counts);
      if (keys.length && (state.faceMode === "crowd" || keys.length > 1)) {
        bar.hidden = false;
        bar.innerHTML = keys
          .sort((a, b) => counts[b] - counts[a])
          .map((id) => {
            const m = EMO_META[id] || {};
            const on = id === vote.id;
            return `<span class="vote-chip${on ? " is-on" : ""}" style="--emo:${m.color || "#c4a574"}">${m.zh || id} × ${counts[id]}</span>`;
          })
          .join("");
      } else bar.hidden = true;
    }
    document.body.dataset.emotion = emo.id || "idle";
  }

  function draw(data) {
    const ctx = overlay.getContext("2d");
    const sized = sizeOverlay();
    if (!sized) return;
    ctx.clearRect(0, 0, overlay.width, overlay.height);
    updateHud(data);
    if (!data || !data.ok) {
      state.overlaySmooth = [];
      return;
    }
    const imageSize = (data.face && data.face.image_size) || [shot.width, shot.height];
    const list = (data.faces && data.faces.length ? data.faces : data.face ? [{ ...data.face, primary: true, emotion: data.emotion }] : []).filter((f) => f && f.box);
    const mapped = list
      .map((f) => {
        const box = mapBox(f.box, imageSize, sized, state.mirror);
        if (!box) return null;
        const emo = f.emotion || data.emotion || {};
        return { box, emo, primary: !!f.primary };
      })
      .filter(Boolean);
    const prev = state.overlaySmooth || [];
    const used = new Set();
    mapped.forEach((item) => {
      let best = -1;
      let bestIou = 0.28;
      prev.forEach((p, i) => {
        if (used.has(i)) return;
        const v = iou(p.box, item.box);
        if (v > bestIou) {
          bestIou = v;
          best = i;
        }
      });
      if (best >= 0) {
        used.add(best);
        item.box = lerpBox(prev[best].box, item.box, 0.46);
      }
    });
    state.overlaySmooth = mapped;
    mapped.forEach((item) => {
      const { box, emo, primary } = item;
      const id = emo.id || "idle";
      const color = emoHex(id, emo.color);
      const radius = Math.max(8, box.w * 0.08);
      ctx.save();
      roundRectPath(ctx, box.x, box.y, box.w, box.h, radius);
      ctx.fillStyle = hexToRgba(color, primary ? 0.14 : 0.08);
      ctx.fill();
      ctx.lineWidth = primary ? Math.max(3.2, box.w * 0.018) : 2;
      ctx.strokeStyle = color;
      ctx.globalAlpha = primary ? 1 : 0.82;
      ctx.stroke();
      const meta = EMO_META[id] || {};
      const pct = Math.round((emo.prob || 0) * 100);
      const label = [meta.zh || emo.zh || "", meta.name || emo.name || "", pct ? `${pct}%` : ""].filter(Boolean).join(" ");
      if (label) {
        const fontPx = Math.max(13, Math.min(22, box.w * 0.16));
        ctx.font = `700 ${fontPx}px "Noto Sans SC","Microsoft YaHei",sans-serif`;
        ctx.textBaseline = "middle";
        const padX = 10;
        const tw = ctx.measureText(label).width;
        const pillW = tw + padX * 2;
        const pillH = fontPx + 12;
        let px = box.x;
        let py = box.y - pillH - 8;
        if (py < 6) py = box.y + 6;
        if (px + pillW > overlay.width - 6) px = Math.max(6, overlay.width - pillW - 6);
        roundRectPath(ctx, px, py, pillW, pillH, pillH / 2);
        ctx.globalAlpha = 1;
        ctx.fillStyle = "rgba(8,7,6,0.78)";
        ctx.fill();
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.6;
        ctx.stroke();
        ctx.fillStyle = color;
        ctx.fillText(label, px + padX, py + pillH / 2);
      }
      ctx.restore();
    });
  }

  function faceHeaders(extra) {
    const headers = {
      "X-Emo-Online": state.onlineOn ? "1" : "0",
      "X-Emo-Face-Mode": state.faceMode || "solo",
    };
    if (extra) Object.assign(headers, extra);
    return headers;
  }

  function startTrack() {
    if (state.trackOn) return;
    state.trackOn = true;
    const tick = async () => {
      state.trackTimer = 0;
      if (!state.trackOn || !cameraReady()) return;
      if (!state.trackBusy && !state.recognizing) {
        state.trackBusy = true;
        try {
          const blob = await captureBlob(0.92, 1280);
          if (blob && state.trackOn) {
            const fd = new FormData();
            fd.append("image", blob, "track.jpg");
            const data = await (
              await fetch("/api/track?mode=" + encodeURIComponent(state.faceMode || "solo"), {
                method: "POST",
                body: fd,
                headers: faceHeaders({ "X-Emo-Source": "camera" }),
              })
            ).json();
            if (state.trackOn) {
              draw(data);
              post({ type: "track", data });
            }
          }
        } catch {
          /* next tick */
        } finally {
          state.trackBusy = false;
        }
      }
      if (state.trackOn && cameraReady()) state.trackTimer = setTimeout(tick, state.live ? 420 : 260);
    };
    state.trackTimer = setTimeout(tick, 80);
  }

  async function recognize(source) {
    if (state.recognizing || !cameraReady()) return;
    state.recognizing = true;
    try {
      const burst = [];
      const n = source === "camera-live" ? 1 : 3;
      for (let i = 0; i < n; i += 1) {
        const blob = await captureBlob(0.94, 1280);
        if (blob) burst.push(blob);
        if (i < n - 1) await new Promise((r) => setTimeout(r, 80));
      }
      if (!burst.length) return;
      const fd = new FormData();
      burst.forEach((b, i) => fd.append(i === 0 ? "image" : "images", b, `frame${i}.jpg`));
      const data = await (
        await fetch(
          "/api/recognize?source=" +
            encodeURIComponent(source) +
            "&online=" +
            (state.onlineOn ? "1" : "0") +
            "&mode=" +
            encodeURIComponent(state.faceMode || "solo"),
          {
            method: "POST",
            body: fd,
            headers: faceHeaders({ "X-Emo-Source": source }),
          }
        )
      ).json();
      if (data && data.ok) draw(data);
      post({ type: "result", data, source, live: state.live });
      const lead = $("#face-lead");
      if (lead && data && data.ok) {
        const vote = data.vote || {};
        const emo = data.emotion || {};
        lead.textContent =
          vote.total > 1
            ? `${vote.total} 张脸 · 多数「${emo.name || ""}」${vote.majority}/${vote.total}，已按此推荐歌曲`
            : `识别为「${emo.name || ""}」，已同步到主页播放`;
      }
    } catch {
      /* ignore */
    } finally {
      state.recognizing = false;
    }
  }

  function setLive(on) {
    state.live = !!on;
    $("#live-toggle").checked = state.live;
    $("#live-emo-dot").hidden = !state.live;
    if (state.liveTimer) {
      clearInterval(state.liveTimer);
      state.liveTimer = 0;
    }
    post({ type: "live", on: state.live });
    if (state.live) {
      state.liveTimer = setInterval(() => {
        if (!state.recognizing && cameraReady()) recognize("camera-live");
      }, 1600);
    }
  }

  $("#btn-cam").addEventListener("click", startCamera);
  $("#btn-cam-empty").addEventListener("click", startCamera);
  $("#btn-recognize").addEventListener("click", async () => {
    setLive(false);
    if (!cameraReady()) {
      const ok = await startCamera();
      if (!ok) return;
    }
    recognize("camera");
  });
  $("#live-toggle").addEventListener("change", async (e) => {
    if (e.target.checked) {
      const ok = await startCamera();
      if (!ok) {
        e.target.checked = false;
        return;
      }
      setLive(true);
    } else setLive(false);
  });
  $$("#face-mode-picks [data-face-mode]").forEach((btn) => {
    btn.addEventListener("click", () => setFaceMode(btn.dataset.faceMode, true));
  });
  const camSelect = $("#cam-select");
  if (camSelect) {
    camSelect.addEventListener("change", async () => {
      const id = camSelect.value || "";
      state.camId = id;
      localStorage.setItem("emotune-cam", id);
      const keepLive = state.live;
      stopCamera();
      const ok = await startCamera();
      if (ok && keepLive) setLive(true);
    });
  }
  if (navigator.mediaDevices && navigator.mediaDevices.addEventListener) {
    navigator.mediaDevices.addEventListener("devicechange", () => listCameras());
  }
  $("#btn-close").addEventListener("click", () => window.close());
  window.addEventListener("beforeunload", () => {
    post({ type: "bye" });
    stopCamera();
  });
  window.addEventListener("resize", () => sizeOverlay());
  if (channel) {
    channel.addEventListener("message", (ev) => {
      const msg = ev.data || {};
      if (msg.type === "face-mode" && msg.id) setFaceMode(msg.id, false, true);
    });
  }

  paintFaceMode();
  listCameras();
  const wantLive = params.get("live") === "1";
  startCamera().then((ok) => {
    if (ok && wantLive) setLive(true);
  });
})();
