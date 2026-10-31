(() => {
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const CHANNEL = "emotune-face";
  const EMO_META = {
    happy: { zh: "喜", name: "喜悦", color: "#ffd400" },
    angry: { zh: "怒", name: "愤怒", color: "#e02020" },
    sad: { zh: "哀", name: "悲伤", color: "#4e7390" },
    fear: { zh: "惧", name: "恐惧", color: "#6b2d91" },
    surprise: { zh: "惊", name: "惊讶", color: "#ff7a18" },
    disgust: { zh: "厌", name: "厌恶", color: "#6f7d32" },
    neutral: { zh: "中", name: "平静", color: "#4ec6f5" },
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
    overlayTarget: [],
    overlayRaf: 0,
    overlayMiss: 0,
    uiEmo: "",
    uiGuess: "",
    uiGuessHits: 0,
    uiGuessAt: 0,
    theme: localStorage.getItem("emotune-theme") || "night",
    onlineOn: localStorage.getItem("emotune-online") !== "0",
    faceMode: params.get("mode") || localStorage.getItem("emotune-face-mode") || "solo",
    landmarkMode: localStorage.getItem("emotune-landmark") || "overlay",
    camZoom: 1,
    camFill: false,
    camFit: "cover", // 人脸窗始终铺满整窗，不留黑边
    camId: params.get("cam") || localStorage.getItem("emotune-cam") || "",
    mirror: true,
  };
  if (!FACE_MODE_META[state.faceMode]) state.faceMode = "solo";
  if (!["overlay", "mesh", "off"].includes(state.landmarkMode)) state.landmarkMode = "overlay";
  {
    const raw = localStorage.getItem("emotune-cam-zoom");
    const z = raw == null || raw === "" ? NaN : Number(raw);
    state.camZoom = Number.isFinite(z) ? Math.max(1, Math.min(2.5, z)) : 1;
  }
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
    const host = $("#cam-layer") || $("#viewport");
    if (!overlay || !host) return null;
    const cssW = host.clientWidth;
    const cssH = host.clientHeight;
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
    if (window.EmoTuneDraw) return EmoTuneDraw.mapBox(box, imageSize, sized, mirror, state.camFit || "cover");
    if (mirror) x = iw - x - bw;
    const scale =
      state.camFit === "contain"
        ? Math.min(sized.cssW / iw, sized.cssH / ih)
        : Math.max(sized.cssW / iw, sized.cssH / ih);
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
  function mapPoint(pt, imageSize, sized, mirror) {
    if (!pt || !imageSize || !sized) return null;
    let x = Number(Array.isArray(pt) ? pt[0] : pt.x);
    let y = Number(Array.isArray(pt) ? pt[1] : pt.y);
    const [iw, ih] = imageSize.map(Number);
    if (!iw || !ih || !Number.isFinite(x) || !Number.isFinite(y)) return null;
    if (window.EmoTuneDraw) return EmoTuneDraw.mapPoint(pt, imageSize, sized, mirror, state.camFit || "cover");
    if (mirror) x = iw - x;
    const scale =
      state.camFit === "contain"
        ? Math.min(sized.cssW / iw, sized.cssH / ih)
        : Math.max(sized.cssW / iw, sized.cssH / ih);
    const dw = iw * scale;
    const dh = ih * scale;
    const ox = (sized.cssW - dw) / 2;
    const oy = (sized.cssH - dh) / 2;
    return {
      x: (ox + x * scale) * sized.dpr,
      y: (oy + y * scale) * sized.dpr,
    };
  }
  function mirrorZh(zh, mirror) {
    if (!mirror) return zh || "";
    return String(zh || "")
      .replace(/左/g, "\0")
      .replace(/右/g, "左")
      .replace(/\0/g, "右");
  }
  const FACE_POINT_FALLBACK = [
    { id: "le", zh: "左眼", symbol: "p₁", part: "eye" },
    { id: "re", zh: "右眼", symbol: "p₂", part: "eye" },
    { id: "nose", zh: "鼻尖", symbol: "p₃", part: "nose" },
    { id: "ml", zh: "左嘴角", symbol: "p₄", part: "mouth" },
    { id: "mr", zh: "右嘴角", symbol: "p₅", part: "mouth" },
  ];
  const FACE_LINKS = [
    ["lb", "rb"],
    ["le", "re"],
    ["le", "nose"],
    ["re", "nose"],
    ["nose", "ml"],
    ["nose", "mr"],
    ["ml", "mr"],
    ["le", "lb"],
    ["re", "rb"],
  ];
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

  function postCamChrome() {
    post({
      type: "cam-chrome",
      landmark: state.landmarkMode,
      zoom: state.camZoom,
      fill: !!state.camFill,
      fit: state.camFit,
    });
  }

  function applyCamView() {
    const vp = $("#viewport");
    const layer = $("#cam-layer");
    document.body.classList.toggle("is-cam-fill", !!state.camFill);
    if (vp) {
      vp.classList.toggle("is-fill", !!state.camFill);
      vp.classList.toggle("is-contain", state.camFit === "contain");
      vp.dataset.fit = state.camFit || "cover";
    }
    if (layer) layer.style.setProperty("--cam-zoom", String(state.camZoom || 1));
    const zoomVal = $("#cam-zoom-val");
    if (zoomVal) zoomVal.textContent = `${Math.round((state.camZoom || 1) * 100)}%`;
    const zoomInput = $("#cam-zoom");
    if (zoomInput) zoomInput.value = String(Math.round((state.camZoom || 1) * 100));
    $$("#landmark-picks [data-landmark]").forEach((btn) => {
      const on = btn.dataset.landmark === state.landmarkMode;
      btn.classList.toggle("is-on", on);
      btn.setAttribute("aria-checked", on ? "true" : "false");
    });
    const fillBtn = $("#btn-cam-fill");
    if (fillBtn) {
      fillBtn.classList.toggle("is-on", !!state.camFill);
      fillBtn.textContent = state.camFill ? "退出铺满" : "铺满窗口";
    }
    const fitBtn = $("#btn-cam-fit");
    if (fitBtn) {
      const cover = state.camFit !== "contain";
      fitBtn.classList.toggle("is-on", cover);
      fitBtn.textContent = cover ? "铺满画面" : "完整画面";
    }
    sizeOverlay();
    paintOverlay();
    requestAnimationFrame(() => {
      sizeOverlay();
      paintOverlay();
    });
  }

  function setLandmarkMode(id, persist) {
    state.landmarkMode = ["overlay", "mesh", "off"].includes(id) ? id : "overlay";
    if (persist !== false) localStorage.setItem("emotune-landmark", state.landmarkMode);
    applyCamView();
    if (persist) postCamChrome();
  }

  function setCamZoom(value, persist) {
    const n = Number(value);
    state.camZoom = Number.isFinite(n) ? Math.max(1, Math.min(2.5, n)) : 1;
    // 人脸窗不低于 100%，缩小会在四周露出空隙；也不写回主页的比例设置
    applyCamView();
    if (persist) postCamChrome();
  }

  function setCamFill(on, persist) {
    state.camFill = !!on;
    if (state.camFill) window.scrollTo(0, 0);
    applyCamView();
    if (persist) postCamChrome();
  }

  function setCamFit(id, persist) {
    state.camFit = id === "contain" ? "contain" : "cover";
    if (persist !== false) localStorage.setItem("emotune-cam-fit", state.camFit);
    applyCamView();
    if (persist) postCamChrome();
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
    if (state.overlayRaf) {
      cancelAnimationFrame(state.overlayRaf);
      state.overlayRaf = 0;
    }
    if (state.liveTimer) clearInterval(state.liveTimer);
    if (state.stream) state.stream.getTracks().forEach((t) => t.stop());
    state.stream = null;
    cam.srcObject = null;
  }

  function commitHud(emo) {
    const id = emo && emo.id && EMO_META[emo.id] && emo.id !== "idle" ? emo.id : "";
    if (!id) return state.uiEmo || "";
    if (!state.uiEmo) {
      state.uiEmo = id;
      state.uiGuess = id;
      state.uiGuessHits = 0;
      state.uiGuessAt = Date.now();
      return id;
    }
    if (id === state.uiEmo) {
      state.uiGuess = id;
      state.uiGuessHits = 0;
      return id;
    }
    const spike = { surprise: true, fear: true, angry: true, disgust: true };
    const prob = Number(emo.prob) || 0;
    const hitsNeed = spike[id] ? 2 : 3;
    const dwellNeed = spike[id] ? 280 : id === "neutral" && state.uiEmo && state.uiEmo !== "neutral" ? 640 : 480;
    const minProb = spike[id] ? 0.55 : id === "neutral" ? 0 : 0.42;
    if (prob < minProb && id !== "neutral") return state.uiEmo;
    if (state.uiGuess !== id) {
      state.uiGuess = id;
      state.uiGuessHits = 1;
      state.uiGuessAt = Date.now();
      return state.uiEmo;
    }
    state.uiGuessHits += 1;
    if (state.uiGuessHits >= hitsNeed && Date.now() - (state.uiGuessAt || 0) >= dwellNeed) {
      state.uiEmo = id;
      state.uiGuessHits = 0;
      return id;
    }
    return state.uiEmo;
  }

  function updateHud(data) {
    const hud = $("#live-emo-hud");
    if (!hud) return;
    hud.hidden = false;
    const emo = data && data.ok && data.emotion;
    const vote = (data && data.vote) || {};
    const countEl = $("#live-emo-count");
    if (!emo) {
      const keep = state.uiEmo && EMO_META[state.uiEmo] ? state.uiEmo : "";
      if (keep) {
        hud.classList.remove("is-miss");
        hud.dataset.emo = keep;
        const keepMeta = EMO_META[keep] || {};
        hud.style.setProperty("--emo", keepMeta.color || "#c4a574");
        $("#live-emo-zh").textContent = keepMeta.zh || "";
        $("#live-emo-name").textContent = keepMeta.name || "";
        $("#live-emo-pct").textContent = "";
        if (countEl) countEl.textContent = "";
        return;
      }
      hud.dataset.emo = "idle";
      hud.classList.add("is-miss");
      $("#live-emo-zh").textContent = "";
      $("#live-emo-name").textContent = "寻找人脸";
      $("#live-emo-pct").textContent = "";
      if (countEl) countEl.textContent = "";
      return;
    }
    const shown = commitHud(emo) || emo.id || "idle";
    hud.classList.remove("is-miss");
    hud.dataset.emo = shown;
    const color = emoHex(shown, shown === emo.id ? emo.color : "");
    hud.style.setProperty("--emo", color);
    const meta = EMO_META[shown] || {};
    $("#live-emo-zh").textContent = meta.zh || "";
    $("#live-emo-name").textContent = meta.name || "";
    $("#live-emo-pct").textContent = shown === emo.id && Math.round((emo.prob || 0) * 100) ? `${Math.round(emo.prob * 100)}%` : "";
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
    document.body.dataset.emotion = shown || "idle";
  }

  function clonePoint(p) {
    return p ? Object.assign({}, p, { x: p.x, y: p.y }) : p;
  }

  function cloneOverlayItem(item) {
    return {
      box: item.box ? { x: item.box.x, y: item.box.y, w: item.box.w, h: item.box.h } : item.box,
      primary: item.primary,
      emo: item.emo,
      points: (item.points || []).map(clonePoint),
      cues: item.cues || [],
    };
  }

  function lerpPt(a, b, t) {
    if (!a) return b;
    if (!b) return a;
    return Object.assign({}, b, { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t });
  }

  function lerpPoints(prev, next, t) {
    const map = {};
    (prev || []).forEach((p) => {
      if (p && p.id) map[p.id] = p;
    });
    return (next || []).map((p) => {
      const q = map[p.id];
      return q ? lerpPt(q, p, t) : clonePoint(p);
    });
  }

  function blendOverlay(prev, target, t) {
    const used = new Set();
    return (target || []).map((item) => {
      let best = -1;
      let bestIou = 0.22;
      (prev || []).forEach((p, i) => {
        if (used.has(i) || !p || !p.box || !item.box) return;
        const v = iou(p.box, item.box);
        if (v > bestIou) {
          bestIou = v;
          best = i;
        }
      });
      if (best >= 0) {
        used.add(best);
        const old = prev[best];
        return {
          box: lerpBox(old.box, item.box, t),
          primary: item.primary,
          emo: item.emo,
          points: lerpPoints(old.points, item.points, t),
          cues: item.cues || [],
        };
      }
      return cloneOverlayItem(item);
    });
  }

  function paintFaceLandmarks(ctx, item, color) {
    if (window.EmoTuneDraw) {
      if (state.landmarkMode === "mesh") EmoTuneDraw.paintMesh(ctx, item, color);
      else EmoTuneDraw.paintDots(ctx, item, color);
    }
  }

  function paintFaceCues(ctx, item, color) {
    if (window.EmoTuneDraw) EmoTuneDraw.paintAuChips(ctx, item, color, overlay);
  }

  function paintOverlay() {
    const ctx = overlay.getContext("2d");
    const sized = sizeOverlay();
    if (!sized) return;
    ctx.clearRect(0, 0, overlay.width, overlay.height);
    if (state.landmarkMode === "off") return;
    const shown = state.uiEmo && EMO_META[state.uiEmo] ? state.uiEmo : "";
    const shownMeta = EMO_META[shown] || {};
    const mapped = (state.overlaySmooth || []).map((item) => {
      const emo = item.emo || {};
      const solo = item.primary || (state.overlaySmooth || []).length === 1;
      if (!solo || !shown) return item;
      return Object.assign({}, item, {
        emo: Object.assign({}, emo, {
          id: shown,
          zh: shownMeta.zh || emo.zh,
          name: shownMeta.name || emo.name,
          color: shownMeta.color || emo.color,
          prob: emo.id === shown ? emo.prob : 0,
        }),
      });
    });
    if (window.EmoTuneDraw) {
      EmoTuneDraw.paintFaces(ctx, mapped, { mode: state.landmarkMode, canvas: overlay });
      return;
    }
    mapped.forEach((item) => {
      const color = emoHex((item.emo && item.emo.id) || "idle", item.emo && item.emo.color);
      ctx.strokeStyle = color;
      ctx.strokeRect(item.box.x, item.box.y, item.box.w, item.box.h);
      paintFaceLandmarks(ctx, item, color);
      if (item.primary) paintFaceCues(ctx, item, color);
    });
  }

  function ensureOverlayPump() {
    if (state.overlayRaf) return;
    const step = () => {
      state.overlayRaf = 0;
      if (!state.trackOn) return;
      const target = state.overlayTarget || [];
      if (target.length && (state.overlaySmooth || []).length) {
        state.overlaySmooth = blendOverlay(state.overlaySmooth, target, 0.38);
      } else if (target.length) {
        state.overlaySmooth = target.map(cloneOverlayItem);
      }
      paintOverlay();
      if (state.trackOn) state.overlayRaf = requestAnimationFrame(step);
    };
    state.overlayRaf = requestAnimationFrame(step);
  }

  function draw(data) {
    updateHud(data);
    if (!data || !data.ok) {
      state.overlayMiss += 1;
      if (state.overlayMiss >= 4) {
        state.overlayTarget = [];
        state.overlaySmooth = [];
        paintOverlay();
      }
      return;
    }
    const sized = sizeOverlay();
    if (!sized) return;
    const imageSize = (data.face && data.face.image_size) || [shot.width, shot.height];
    const list = (data.faces && data.faces.length ? data.faces : data.face ? [{ ...data.face, primary: true, emotion: data.emotion }] : []).filter((f) => f && f.box);
    const mapped = list
      .map((f) => {
        const box = mapBox(f.box, imageSize, sized, state.mirror);
        if (!box) return null;
        const emo = f.emotion || data.emotion || {};
        const srcPts =
          f.points && f.points.length
            ? f.points
            : (f.landmarks || []).map((xy, i) =>
                Object.assign({}, FACE_POINT_FALLBACK[i] || { id: `p${i}`, zh: "点", symbol: `p${i}`, part: "face" }, {
                  x: xy[0],
                  y: xy[1],
                })
              );
        const points = srcPts
          .map((p) => {
            const xy = mapPoint([p.x, p.y], imageSize, sized, state.mirror);
            if (!xy) return null;
            return Object.assign({}, p, { zh: mirrorZh(p.zh, !!state.mirror), x: xy.x, y: xy.y });
          })
          .filter(Boolean);
        return { box, emo, primary: !!f.primary, points, cues: f.cues || [] };
      })
      .filter(Boolean);
    if (!mapped.length) {
      state.overlayMiss += 1;
      if (state.overlayMiss >= 4) {
        state.overlayTarget = [];
        state.overlaySmooth = [];
        paintOverlay();
      }
      return;
    }
    state.overlayMiss = 0;
    state.overlayTarget = mapped;
    if (!state.overlaySmooth.length) {
      state.overlaySmooth = mapped.map(cloneOverlayItem);
      paintOverlay();
    }
    ensureOverlayPump();
  }

  function faceHeaders(extra) {
    const headers = {
      "X-Emo-Online": state.onlineOn ? "1" : "0",
      "X-Emo-Face-Mode": state.faceMode || "solo",
      "X-Emo-Demo": localStorage.getItem("emotune-demo-mode") === "1" ? "1" : "0",
    };
    if (extra) Object.assign(headers, extra);
    return headers;
  }

  function startTrack() {
    if (state.trackOn) return;
    state.trackOn = true;
    ensureOverlayPump();
    const tick = async () => {
      state.trackTimer = 0;
      if (!state.trackOn || !cameraReady()) return;
      if (!state.trackBusy) {
        state.trackBusy = true;
        try {
          const crowd = state.faceMode === "crowd";
          const blob = await captureBlob(crowd ? 0.78 : 0.8, crowd ? 800 : 640);
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
            const elapsed = Number((data && data.elapsed_ms) || 40);
            if (state.trackOn && cameraReady()) {
              state.trackTimer = setTimeout(tick, Math.max(15, 90 - elapsed));
            }
            return;
          }
        } catch {
          /* next tick */
        } finally {
          state.trackBusy = false;
        }
      }
      if (state.trackOn && cameraReady()) state.trackTimer = setTimeout(tick, 60);
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
        const blob = await captureBlob(0.94, source === "camera-live" ? 720 : 1280);
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
      }, 1400);
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
  $$("#landmark-picks [data-landmark]").forEach((btn) => {
    btn.addEventListener("click", () => setLandmarkMode(btn.dataset.landmark, true));
  });
  const fillBtn = $("#btn-cam-fill");
  if (fillBtn) fillBtn.addEventListener("click", () => setCamFill(!state.camFill, true));
  const fitBtn = $("#btn-cam-fit");
  if (fitBtn) fitBtn.addEventListener("click", () => setCamFit(state.camFit === "contain" ? "cover" : "contain", true));
  const zoomInput = $("#cam-zoom");
  if (zoomInput) zoomInput.addEventListener("input", () => setCamZoom(Number(zoomInput.value) / 100, true));
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
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && state.camFill) {
      e.preventDefault();
      setCamFill(false, true);
    }
  });
  if (channel) {
    channel.addEventListener("message", (ev) => {
      const msg = ev.data || {};
      if (msg.type === "face-mode" && msg.id) setFaceMode(msg.id, false, true);
      if (msg.type === "cam-chrome") {
        if (msg.landmark) setLandmarkMode(msg.landmark, false);
        if (Number.isFinite(Number(msg.zoom))) setCamZoom(Number(msg.zoom), false);
        if (typeof msg.fill === "boolean") setCamFill(msg.fill, false);
      }
    });
  }

  paintFaceMode();
  applyCamView();
  listCameras();
  const wantLive = params.get("live") === "1";
  startCamera().then((ok) => {
    if (ok && wantLive) setLive(true);
  });
})();
