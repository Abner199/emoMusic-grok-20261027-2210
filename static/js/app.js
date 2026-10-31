(() => {
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  /* app.js 章节目录（搜索中文标题即可跳到对应位置）
   *   工具与常量 ........ core.js（EmoCore）
   *   状态 state ........ const state = {
   *   语音播报 .......... function speakText / speakEmotionChange / switchAfterSpeech
   *   摄像头与画面 ...... async function startCamera / attachStream / captureBlob
   *   实时判断 .......... decideLiveAction / lockPlaylist / updateHoldUi
   *   人脸框绘制 ........ paintFaceOverlay / startTrackLoop（face-draw.js 负责具体画法）
   *   歌单与播放 ........ renderSongs / playAt / autoPlayList / fillOnlineLater
   *   声学可视化 ........ drawVizFrame / setVizSize
   *   播放器三档 ........ setPlayerMode；投影大屏 setProjector；情绪时间线 sampleTimeline
   *   换歌原因提示 ...... showSwitchReason
   *   识别结果处理 ...... handleRecognizeData
   *   照片模式 .......... useFile / paintPhotoOverlay / loadDemo
   *   情绪足迹 .......... loadHistory / loadMoreHistory / refreshTrailLive / renderTrail
   *   事件绑定 .......... function bind()
   */
  const { EMO_ORDER, EMO_META, EMO_HEX, SOURCE_ZH, FACE_MODE_META, TRAD, SIMP, TRAD_MAP, FACE, prettyText, esc, faceSvg, fmt, hexToRgba, foldTitle, clampNum, normRange } = window.EmoCore;


  const state = {
    mode: "camera",
    stream: null,
    live: false,
    liveTimer: 0,
    trackTimer: 0,
    trackOn: false,
    trackBusy: false,
    overlaySmooth: [],
    overlayTarget: [],
    overlayRaf: 0,
    overlayMiss: 0,
    lastOverlay: { id: "idle", color: "#c4a574" },
    lastVote: null,
    facePop: null,
    facePopWatch: 0,
    facePopActive: false,
    recognizing: false,
    camBusy: false,
    songs: [],
    index: 0,
    lastFile: null,
    audioUnlocked: false,
    autoplayWarned: false,
    lastEmotion: "",
    uiEmo: "",
    uiTagSig: "",
    uiGuess: "",
    uiGuessHits: 0,
    uiGuessAt: 0,
    lockEmotion: "",
    lockAt: 0,
    holdRelaxed: false,
    holdTick: 0,
    liveGuess: "",
    liveGuessCount: 0,
    trackEmo: "",
    trackEmoAt: 0,
    liveKickAt: 0,
    failed: new Set(),
    history: [],
    historyId: "",
    playedByEmotion: {},
    lastPlayedStamp: "",
    replayHistory: false,
    voiceOn: localStorage.getItem("emotune-voice") !== "0",
    skipPlayed: localStorage.getItem("emotune-skip-played") !== "0",
    demoMode: localStorage.getItem("emotune-demo-mode") === "1",
    // 1–6：在前 N 首代表曲之间轮换；0：歌单里全部歌曲轮流当第一首
    pinRotate: (() => {
      const raw = localStorage.getItem("emotune-pin-rotate");
      if (raw === "0") return 0;
      return Math.max(1, Math.min(6, Number(raw) || 3));
    })(),
    lastSpokenEmo: "",
    lastSpokenAt: 0,
    lastSpokenText: "",
    speaking: false,
    speakPending: "",
    speakHits: 0,
    speakSince: 0,
    onlineOn: localStorage.getItem("emotune-online") !== "0",
    onlineFailCount: 0,
    onlineFailAt: 0,
    fallbackBusy: false,
    playWatch: 0,
    lyricsOn: localStorage.getItem("emotune-lyrics") !== "0",
    coverOn: localStorage.getItem("emotune-cover") !== "0",
    vizOn: localStorage.getItem("emotune-viz") !== "0",
    strategy: localStorage.getItem("emotune-strategy") || "iso",
    strategies: [],
    faceMode: localStorage.getItem("emotune-face-mode") || "solo",
    landmarkMode: localStorage.getItem("emotune-landmark") || "overlay",
    camZoom: 1,
    camFill: localStorage.getItem("emotune-cam-size") !== "default",
    camFit: localStorage.getItem("emotune-cam-fit") === "contain" ? "contain" : "cover",
    camId: localStorage.getItem("emotune-cam") || "",
    mirror: true,
    videoUrl: "",
    audioCtx: null,
    analyser: null,
    vizRaf: 0,
    vizEnv: [],
    vizBpm: 0,
    vizTextAt: 0,
    vizTextSig: "",
    vizLastF0: 0,
    vizLastC: 0,
    theme: localStorage.getItem("emotune-theme") || "night",
    lyricLines: [],
    lyricToken: 0,
    ducking: false,
    zhVoice: null,
  };
  const lyricCache = new Map();
  const THEMES = ["night", "paper", "ink", "rouge", "celadon", "moon"];
  const LANDMARK_MODES = ["overlay", "mesh", "off"];
  if (!LANDMARK_MODES.includes(state.landmarkMode)) state.landmarkMode = "overlay";
  {
    const raw = localStorage.getItem("emotune-cam-zoom");
    const z = raw == null || raw === "" ? NaN : Number(raw);
    state.camZoom = Number.isFinite(z) ? Math.max(0.5, Math.min(2.5, z)) : 1;
  }

  function applyTheme(id, persist) {
    const theme = THEMES.includes(id) ? id : "night";
    state.theme = theme;
    document.documentElement.dataset.theme = theme;
    $$(".theme-pick").forEach((btn) => {
      const on = btn.dataset.theme === theme;
      btn.classList.toggle("is-on", on);
      btn.setAttribute("aria-checked", on ? "true" : "false");
    });
    localStorage.setItem("emotune-theme", theme);
    if (persist) {
      fetch("/api/prefs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ theme }),
      }).catch(() => {});
    }
  }

  const FALLBACK_STRATS = [
    { id: "iso", zh: "同频", name: "同频匹配", blurb: "贴着当前表情，播同一类最贴的歌。" },
    { id: "repair", zh: "修复", name: "心境修复", blurb: "不继续泡在负面里，直接播修复目标类。" },
    { id: "iso-repair", zh: "先同频再修复", name: "同频后修复", blurb: "先同频接住，再过渡，最后走到修复。" },
    { id: "contrast", zh: "对比", name: "对极反差", blurb: "整单取对极情绪，听反差。" },
    { id: "circumplex", zh: "回暖", name: "环面回暖", blurb: "在情绪环面上邻格走，慢慢亮起来。" },
    { id: "calm", zh: "降唤醒", name: "先把劲卸掉", blurb: "先用低唤醒把劲卸掉。" },
    { id: "uplift", zh: "升效价", name: "平行抬亮", blurb: "唤醒差不多，把效价抬亮。" },
    { id: "amplify", zh: "强化", name: "把这类情绪听满", blurb: "不换类，把这一类听得更典型。" },
    { id: "balance", zh: "平衡", name: "同频与修复交错", blurb: "一半同频、一半修复，交错着听。" },
  ];

  function strategyMeta(id) {
    const key = id || state.strategy || "iso";
    return (state.strategies || []).find((s) => s.id === key) || FALLBACK_STRATS.find((s) => s.id === key) || FALLBACK_STRATS[0];
  }

  function paintStrategyNow(strat) {
    const meta = strat && (strat.zh || strat.name) ? strat : strategyMeta(state.strategy);
    const now = $("#strat-now");
    if (now) now.textContent = meta.zh || meta.name || "同频";
    const hint = $("#strat-hint");
    if (hint) hint.textContent = meta.blurb || meta.how || "";
    $$(".strat-pick").forEach((btn) => {
      const on = btn.dataset.strategy === (meta.id || state.strategy);
      btn.classList.toggle("is-on", on);
      btn.setAttribute("aria-checked", on ? "true" : "false");
    });
  }

  function renderStrategyPicks() {
    const box = $("#strat-picks");
    if (!box) return;
    const list = state.strategies.length ? state.strategies : FALLBACK_STRATS;
    box.innerHTML = list
      .map(
        (s) =>
          `<button type="button" class="strat-pick${s.id === state.strategy ? " is-on" : ""}" data-strategy="${esc(s.id)}" role="radio" aria-checked="${s.id === state.strategy ? "true" : "false"}" title="${esc(s.name || s.zh)}">${esc(s.zh)}</button>`
      )
      .join("");
    paintStrategyNow();
  }

  function setStrategy(id, persist, reload) {
    const meta = strategyMeta(id);
    state.strategy = meta.id || "iso";
    localStorage.setItem("emotune-strategy", state.strategy);
    paintStrategyNow(meta);
    if (persist) {
      fetch("/api/prefs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy: state.strategy }),
      }).catch(() => {});
    }
    if (reload && (state.lastEmotion || state.lockEmotion)) {
      loadPlaylist(currentEmotionId(), true);
      toast(`已改用「${meta.zh}」推荐：${meta.name || ""}`.trim());
    }
  }

  function bindStrategyPicks() {
    const box = $("#strat-picks");
    if (!box) return;
    box.addEventListener("click", (e) => {
      const btn = e.target.closest(".strat-pick");
      if (!btn) return;
      setStrategy(btn.dataset.strategy, true, true);
    });
    renderStrategyPicks();
  }

  async function loadStrategies() {
    try {
      const data = await (await fetch("/api/strategies")).json();
      if (data && Array.isArray(data.strategies) && data.strategies.length) {
        state.strategies = data.strategies;
        if (data.default && !localStorage.getItem("emotune-strategy")) state.strategy = data.default;
        renderStrategyPicks();
      }
    } catch {
      renderStrategyPicks();
    }
  }

  const audio = new Audio();
  audio.preload = "auto";
  audio.playsInline = true;
  audio.crossOrigin = "anonymous";
  audio.setAttribute("playsinline", "true");
  audio.setAttribute("crossorigin", "anonymous");
  audio.volume = Number(localStorage.getItem("emotune-vol") || 0.86);

  const SILENT_WAV =
    "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA";

  function isSilentOrEmpty() {
    const s = audio.currentSrc || audio.src || "";
    if (!s || s === location.href) return true;
    return sameAudio(SILENT_WAV);
  }

  function pickZhVoice() {
    if (!("speechSynthesis" in window)) return null;
    const voices = window.speechSynthesis.getVoices() || [];
    const score = (v) => {
      const s = `${v.lang} ${v.name}`.toLowerCase();
      if (/zh-cn|zh_cn/.test(s) && /huihui|xiaoxiao|yaoyao|kangkang|microsoft/.test(s)) return 4;
      if (/zh-cn|zh_cn/.test(s)) return 3;
      if (/^zh/.test(v.lang) || /chinese|中文|普通话/.test(s)) return 2;
      return 0;
    };
    return voices.slice().sort((a, b) => score(b) - score(a)).find((v) => score(v) > 0) || null;
  }

  function refreshZhVoice() {
    state.zhVoice = pickZhVoice();
  }

  function duckMusic(on) {
    if (on) {
      state.ducking = true;
      const base = Number(ui.vol && ui.vol.value != null ? ui.vol.value : audio.volume);
      audio.volume = Math.min(base, 0.18);
      return;
    }
    if (!state.ducking) return;
    state.ducking = false;
    audio.volume = Number(ui.vol && ui.vol.value != null ? ui.vol.value : 0.86);
  }

  const LIVE_SPEAK_DWELL_MS = 2500;
  const SPIKE_SPEAK_DWELL_MS = 400; // 高潮表情：画面已确认两次，再稳 0.4 秒就播报，播报完立刻换歌

  function speakDwellMs(id) {
    return TRANSIENT_EMO[id] ? SPIKE_SPEAK_DWELL_MS : LIVE_SPEAK_DWELL_MS;
  }

  function cancelSpeech() {
    state.speaking = false;
    try {
      window.speechSynthesis && window.speechSynthesis.cancel();
    } catch {
      /* ignore */
    }
    duckMusic(false);
  }

  function hushVoice() {
    cancelSpeech();
    resetLiveSpeak("");
  }

  function resetLiveSpeak(id) {
    const next = id && EMO_META[id] && id !== "idle" ? id : "";
    const current = state.speakPending || state.lastSpokenEmo || "";
    if (state.speaking && next !== current) cancelSpeech();
    state.speakPending = next;
    state.speakHits = 0;
    state.speakSince = next ? Date.now() : 0;
  }

  function tickUiSpeak(emotion) {
    if ((!state.live && !state.facePopActive) || !state.voiceOn) return;
    const id = state.uiEmo;
    if (!id || id === "idle") {
      if (state.speakPending) resetLiveSpeak("");
      return;
    }
    if (id === state.lastSpokenEmo) {
      if (state.speakPending && state.speakPending !== id) resetLiveSpeak("");
      return;
    }
    if (state.speakPending !== id) {
      resetLiveSpeak(id);
      return;
    }
    if (Date.now() - (state.speakSince || 0) >= speakDwellMs(id)) {
      const meta = EMO_META[id] || {};
      const same = emotion && emotion.id === id ? emotion : null;
      speakEmotionChange(
        {
          id,
          zh: (same && same.zh) || meta.zh,
          name: (same && same.name) || meta.name,
        },
        false,
        () => switchAfterSpeech(id)
      );
      state.speakPending = "";
      state.speakHits = 0;
    }
  }

  /* 语音播报一结束就换成该情绪的歌：有几秒内的识别结果直接用，没有就当场截一帧确认 */
  const LIVE_DATA_FRESH_MS = 5000;
  function switchAfterSpeech(id) {
    if (!state.live || !id || id === "idle") return;
    if (id === state.lockEmotion) return;
    if (state.uiEmo && state.uiEmo !== id) return; // 播报被新表情打断：以新表情为准
    const cached = (state.liveLatest || {})[id];
    state.forceApplyEmo = id;
    state.forceApplyAt = Date.now();
    if (cached && Date.now() - cached.at <= LIVE_DATA_FRESH_MS) {
      handleRecognizeData(cached.data, cached.source, 0);
      return;
    }
    if (!state.recognizing && frameReady()) {
      captureBlob(0.9, 720).then((blob) => {
        if (blob && state.live) recognize(blob, liveSource());
      });
    }
  }

  function speakText(text, force, onDone) {
    if (!state.voiceOn || !text) return false;
    if (!("speechSynthesis" in window)) return false;
    const synth = window.speechSynthesis;
    if (!force && state.speaking && state.lastSpokenText === text) return false;
    try {
      synth.cancel();
    } catch {
      /* ignore */
    }
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = "zh-CN";
    utter.rate = 1.02;
    utter.pitch = 1;
    utter.volume = 1;
    if (!state.zhVoice) refreshZhVoice();
    if (state.zhVoice) utter.voice = state.zhVoice;
    let finished = false;
    const done = () => {
      if (finished) return;
      finished = true;
      clearTimeout(guard);
      state.speaking = false;
      duckMusic(false);
      if (typeof onDone === "function") onDone();
    };
    /* 个别浏览器不触发 onend：按字数估一个上限兜底 */
    const guard = setTimeout(done, 1200 + text.length * 260);
    utter.onend = done;
    utter.onerror = done;
    state.speaking = true;
    state.lastSpokenText = text;
    duckMusic(true);
    synth.speak(utter);
    return true;
  }

  function speakEmotionChange(emotion, force, onDone) {
    if (!emotion || !emotion.id || emotion.id === "idle") return;
    const now = Date.now();
    if (!force && emotion.id === state.lastSpokenEmo) return;
    const zh = emotion.zh || (EMO_META[emotion.id] || {}).zh || "";
    const name = emotion.name || (EMO_META[emotion.id] || {}).name || "";
    if (!speakText(`情绪标签变为${zh}，${name}`, force, onDone)) return;
    state.lastSpokenEmo = emotion.id;
    state.lastSpokenAt = now;
  }

  function unlockSpeech() {
    if (!("speechSynthesis" in window)) return;
    refreshZhVoice();
    try {
      const warm = new SpeechSynthesisUtterance(" ");
      warm.volume = 0;
      warm.lang = "zh-CN";
      window.speechSynthesis.speak(warm);
      window.speechSynthesis.cancel();
    } catch {
      /* 部分浏览器需用户手势后才允许播报 */
    }
  }

  function unlockAudio() {
    unlockSpeech();
    if (state.audioUnlocked) return;
    if (!audio.paused && !isSilentOrEmpty()) {
      audio.muted = false;
      state.audioUnlocked = true;
      return;
    }
    audio.muted = true;
    audio.src = SILENT_WAV;
    audio
      .play()
      .then(() => {
        state.audioUnlocked = true;
      })
      .catch(() => {});
  }

  const ui = {
    cam: $("#cam"),
    shot: $("#shot"),
    overlay: $("#face-overlay"),
    preview: $("#preview"),
    empty: $("#cam-empty"),
    scan: $("#scan"),
    file: $("#file-input"),
    drop: $("#photo-stage"),
    songs: $("#songs"),
    tags: $("#emo-tags"),
    icon: $("#emo-icon"),
    hero: $("#emo-hero"),
    emoShot: $("#emo-shot"),
    emoFace: $("#emo-face"),
    emoShotEmpty: $("#emo-shot-empty"),
    emoFaceCap: $("#emo-face-cap"),
    trail: $("#mood-trail"),
    player: $("#player"),
    seek: $("#seek"),
    vol: $("#vol"),
  };



  function toast(msg, kind = "") {
    const box = $("#toasts");
    const el = document.createElement("div");
    el.className = `toast ${kind}`;
    el.textContent = msg;
    box.appendChild(el);
    setTimeout(() => el.remove(), 4200);
  }


  function isLocalHost() {
    const h = location.hostname;
    return h === "localhost" || h === "127.0.0.1" || h === "[::1]";
  }

  function isCameraSecure() {
    return window.isSecureContext || isLocalHost();
  }

  function isLiveMode(mode = state.mode) {
    return mode === "camera" || mode === "video" || mode === "screen";
  }

  function liveSource() {
    if (state.mode === "video") return state.live ? "video-live" : "video";
    if (state.mode === "screen") return state.live ? "screen-live" : "screen";
    return state.live ? "camera-live" : "camera";
  }

  function isLiveSource(source) {
    return /(?:camera|video|screen)-live$/.test(String(source || ""));
  }

  function frameReady() {
    const v = ui.cam;
    return Boolean(v && !v.hidden && v.videoWidth > 0);
  }

  function cameraReady() {
    const stream = state.stream;
    const live = stream && stream.active && stream.getVideoTracks().some((t) => t.readyState === "live");
    return Boolean(live && ui.cam && ui.cam.videoWidth > 0);
  }

  function faceHeaders(extra) {
    const headers = {
      "X-Emo-Online": state.onlineOn ? "1" : "0",
      "X-Emo-Strategy": state.strategy || "iso",
      "X-Emo-Face-Mode": state.faceMode || "solo",
      "X-Emo-Fresh": state.skipPlayed ? "1" : "0",
      "X-Emo-Demo": state.demoMode ? "1" : "0",
    };
    if (extra) Object.assign(headers, extra);
    return headers;
  }

  function paintFaceMode() {
    const meta = FACE_MODE_META[state.faceMode] || FACE_MODE_META.solo;
    const hint = $("#face-mode-hint");
    if (hint) hint.textContent = meta.blurb || "";
    $$("#face-mode-picks [data-face-mode]").forEach((btn) => {
      const on = btn.dataset.faceMode === meta.id;
      btn.classList.toggle("is-on", on);
      btn.setAttribute("aria-checked", on ? "true" : "false");
    });
  }

  function setFaceMode(id, persist) {
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
    }
    if (typeof faceChannel !== "undefined" && faceChannel && state.facePopActive) {
      try {
        faceChannel.postMessage({ type: "face-mode", id: state.faceMode });
      } catch {
        /* ignore */
      }
    }
    if (changed && persist) {
      toast(meta.id === "crowd" ? "已切到多人远场：可检多张脸和远景小脸。" : "已切到单人精检：只认近景主脸。");
    }
  }

  function setMirror(on) {
    state.mirror = !!on;
    if (ui.cam) ui.cam.classList.toggle("is-mirror", state.mirror);
  }

  function updateLiveChrome() {
    const mode = state.mode;
    const camRow = $("#cam-select-row");
    const videoRow = $("#video-row");
    const guide = $("#cam-guide");
    const btnCam = $("#btn-cam");
    const btnScreen = $("#btn-screen");
    const btnVideo = $("#btn-video");
    if (camRow) camRow.hidden = mode !== "camera";
    if (videoRow) videoRow.hidden = mode !== "video";
    if (guide) guide.hidden = mode !== "camera";
    if (btnCam) btnCam.hidden = mode !== "camera";
    if (btnScreen) btnScreen.hidden = mode !== "screen";
    if (btnVideo) btnVideo.hidden = mode !== "video";
    const copy = {
      camera: "点下面的按钮开启摄像头，把面部落在椭圆里",
      video: "选择本地视频，播放后可识别此刻或打开实时捕捉",
      screen: "点「分享屏幕」，选择窗口或整块屏幕后再识别",
    };
    if (mode in copy) setCamHint(copy[mode]);
  }

  function setCamHint(text) {
    const el = $("#cam-empty-text");
    if (el) el.textContent = text;
  }

  function cameraErrorText(err) {
    const name = (err && err.name) || "";
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      if (!isCameraSecure()) {
        return "当前地址不能使用摄像头。请用 http://127.0.0.1:5000 打开，不要用局域网地址。";
      }
      return "浏览器不支持摄像头，请换 Chrome 或 Edge 后再试。";
    }
    if (name === "NotAllowedError" || name === "PermissionDeniedError") {
      return "摄像头权限被拒绝。请点击地址栏右侧的摄像头图标，允许本站访问后再点「开启摄像头」。";
    }
    if (name === "NotFoundError" || name === "DevicesNotFoundError") {
      return "没有找到摄像头。请确认系统里已启用相机，或改用照片、视频、屏幕。";
    }
    if (name === "NotReadableError" || name === "TrackStartError") {
      return "摄像头被其他程序占用（会议软件、系统相机等）。请关闭占用后再试。";
    }
    if (name === "OverconstrainedError" || name === "ConstraintNotSatisfiedError") {
      return "当前摄像头不支持默认参数，已尝试兼容模式仍失败。请换一台设备或改用上传照片。";
    }
    if (name === "SecurityError") {
      return "浏览器把当前页面视为非安全环境。请改用 http://127.0.0.1:5000 打开。";
    }
    if (name === "NotSupportedError") {
      return "浏览器不支持摄像头，请换 Chrome 或 Edge 后再试。";
    }
    if (name === "AbortError") {
      return "打开摄像头被中断，请再点一次「开启摄像头」。";
    }
    return (err && err.message) || "无法打开摄像头，请允许权限，或改用上传照片。";
  }

  function stopCameraStream() {
    stopTrackLoop();
    clearFaceOverlay();
    if (state.stream) {
      state.stream.getTracks().forEach((t) => t.stop());
      state.stream = null;
    }
    const v = ui.cam;
    if (!v) return;
    try {
      v.pause();
    } catch {
      /* ignore */
    }
    v.srcObject = null;
    if (state.videoUrl) {
      try {
        URL.revokeObjectURL(state.videoUrl);
      } catch {
        /* ignore */
      }
      state.videoUrl = "";
    }
    if (v.getAttribute("src")) {
      v.removeAttribute("src");
      try {
        v.load();
      } catch {
        /* ignore */
      }
    }
    v.loop = false;
    v.controls = false;
  }

  function captureBlob(quality = 0.92, maxSide = 1280) {
    const video = ui.cam;
    if (!video.videoWidth) return Promise.resolve(null);
    const scale = Math.min(1, maxSide / Math.max(video.videoWidth, video.videoHeight));
    const w = Math.round(video.videoWidth * scale);
    const h = Math.round(video.videoHeight * scale);
    ui.shot.width = w;
    ui.shot.height = h;
    ui.shot.getContext("2d").drawImage(video, 0, 0, w, h);
    return new Promise((resolve) => ui.shot.toBlob((b) => resolve(b), "image/jpeg", quality));
  }

  function waitForVideo(timeout = 5000) {
    const v = ui.cam;
    if (v.readyState >= 2 && v.videoWidth > 0) return Promise.resolve(true);
    return new Promise((resolve) => {
      let done = false;
      const finish = (ok) => {
        if (done) return;
        done = true;
        clearTimeout(timer);
        v.removeEventListener("loadedmetadata", onReady);
        v.removeEventListener("playing", onReady);
        resolve(ok);
      };
      const onReady = () => {
        if (v.videoWidth > 0) finish(true);
      };
      const timer = setTimeout(() => finish(v.videoWidth > 0), timeout);
      v.addEventListener("loadedmetadata", onReady);
      v.addEventListener("playing", onReady);
    });
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
      { video: { facingMode: { ideal: "user" }, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false },
      { video: { facingMode: { ideal: "user" } }, audio: false },
      { video: { width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false },
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
    const devices = await navigator.mediaDevices.enumerateDevices().catch(() => []);
    const cams = devices.filter((d) => d.kind === "videoinput" && d.deviceId);
    for (const cam of cams) {
      try {
        return await navigator.mediaDevices.getUserMedia({
          video: { deviceId: { exact: cam.deviceId } },
          audio: false,
        });
      } catch (err) {
        lastErr = err;
      }
    }
    throw lastErr || new Error("没有可用的摄像头");
  }

  async function attachStream(stream) {
    state.stream = stream;
    ui.cam.muted = true;
    ui.cam.defaultMuted = true;
    ui.cam.autoplay = true;
    ui.cam.playsInline = true;
    ui.cam.setAttribute("playsinline", "true");
    ui.cam.setAttribute("webkit-playsinline", "true");
    ui.cam.srcObject = stream;
    ui.cam.loop = false;
    ui.cam.controls = false;
    ui.cam.hidden = false;
    ui.preview.hidden = true;
    try {
      await ui.cam.play();
    } catch {
      /* 部分浏览器在已 muted 时仍会抛 AbortError，等 loadedmetadata 即可 */
    }
    const ok = await waitForVideo();
    if (!ok) throw new Error("摄像头已连接，但没有画面。请检查隐私盖板或系统相机权限。");
    ui.empty.hidden = true;
    const track = stream.getVideoTracks()[0];
    if (track && track.getSettings) {
      const id = track.getSettings().deviceId;
      if (id) {
        state.camId = id;
        localStorage.setItem("emotune-cam", id);
      }
    }
    if (state.mode === "camera") await listCameras();
    startTrackLoop();
  }

  async function startCamera() {
    if (state.facePopActive) {
      toast("人脸窗正在使用摄像头。关闭人脸窗后可回到本页检测。");
      return false;
    }
    if (state.camBusy) return false;
    if (cameraReady()) {
      ui.empty.hidden = true;
      ui.preview.hidden = true;
      ui.cam.hidden = false;
      startTrackLoop();
      return true;
    }
    const btn = $("#btn-cam");
    state.camBusy = true;
    if (btn) {
      btn.disabled = true;
      btn.textContent = "正在打开…";
    }
    setCamHint("正在请求摄像头权限…");
    try {
      if (!isCameraSecure()) {
        throw Object.assign(new Error("insecure"), { name: "SecurityError" });
      }
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw Object.assign(new Error("unsupported"), { name: "NotSupportedError" });
      }
      stopCameraStream();
      const stream = await requestCameraStream();
      setMirror(true);
      await attachStream(stream);
      setCamHint("点下面的按钮开启摄像头，把面部落在椭圆里");
      setTimeout(autoLive, 0); // 等 finally 清掉 camBusy 后再开实时捕捉
      return true;
    } catch (err) {
      stopCameraStream();
      ui.empty.hidden = false;
      const text = cameraErrorText(err);
      setCamHint(text);
      toast(text, "err");
      return false;
    } finally {
      state.camBusy = false;
      if (btn) {
        btn.disabled = false;
        btn.textContent = "开启摄像头";
      }
    }
  }

  /* 摄像头一开就默认实时捕捉：持续识别表情并自动连播 */
  function autoLive() {
    const tog = $("#live-toggle");
    if (!tog || tog.checked || state.live || state.facePopActive) return;
    if (localStorage.getItem("emotune-auto-live") === "0") return;
    tog.checked = true;
    tog.dispatchEvent(new Event("change", { bubbles: true }));
  }

  async function startScreen() {
    if (state.facePopActive) {
      toast("人脸窗正在使用画面。关闭人脸窗后再分享屏幕。");
      return false;
    }
    if (!isCameraSecure()) {
      toast("屏幕分享需要在 http://127.0.0.1 打开。", "err");
      return false;
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia) {
      toast("当前浏览器不支持屏幕分享，请用 Chrome 或 Edge。", "err");
      return false;
    }
    try {
      stopCameraStream();
      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: { frameRate: { ideal: 12 }, cursor: "never" },
        audio: false,
      });
      const track = stream.getVideoTracks()[0];
      if (track) {
        track.addEventListener("ended", () => {
          if (state.mode === "screen") {
            stopLive();
            stopCameraStream();
            ui.empty.hidden = false;
            setCamHint("屏幕分享已结束。可再点「分享屏幕」。");
          }
        });
      }
      setMirror(false);
      await attachStream(stream);
      setCamHint("正在读取屏幕画面");
      toast("已开始屏幕分享，可识别此刻或打开实时捕捉。");
      return true;
    } catch (err) {
      stopCameraStream();
      ui.empty.hidden = false;
      if (err && (err.name === "NotAllowedError" || err.name === "AbortError")) {
        setCamHint("未选择屏幕。再点「分享屏幕」选择窗口或整屏。");
        return false;
      }
      const text = (err && err.message) || "无法分享屏幕。";
      setCamHint(text);
      toast(text, "err");
      return false;
    }
  }

  async function useVideoFile(file) {
    if (!file) return false;
    const okType = (file.type || "").startsWith("video/") || /\.(mp4|webm|mov|mkv|avi)$/i.test(file.name || "");
    if (!okType) {
      toast("请选择视频文件，例如 MP4 / WEBM。", "err");
      return false;
    }
    unlockAudio();
    stopLive();
    stopCameraStream();
    const url = URL.createObjectURL(file);
    state.videoUrl = url;
    const v = ui.cam;
    v.muted = true;
    v.loop = true;
    v.controls = true;
    v.srcObject = null;
    v.src = url;
    v.hidden = false;
    ui.preview.hidden = true;
    setMirror(false);
    try {
      await v.play();
    } catch {
      /* 用户可再点播放 */
    }
    const ok = await waitForVideo(8000);
    if (!ok) {
      ui.empty.hidden = false;
      toast("视频没有画面，请换一段文件。", "err");
      return false;
    }
    ui.empty.hidden = true;
    startTrackLoop();
    toast("视频已打开，可识别此刻或打开实时捕捉。");
    return true;
  }

  async function ensureLiveSource() {
    if (state.mode === "camera") return startCamera();
    if (state.mode === "screen") return cameraReady() ? true : startScreen();
    if (state.mode === "video") {
      if (frameReady()) return true;
      toast("请先选择一段本地视频。", "err");
      return false;
    }
    toast("实时捕捉用于摄像头、视频或屏幕。", "err");
    return false;
  }

  const TRANSIENT_EMO = { surprise: true, fear: true, angry: true, disgust: true };
  const DAILY_EMO = { happy: true, sad: true, neutral: true };
  /* 换歌前的最短保持：防止一闪而过的表情来回切歌，但表情变了几秒内就要换到对应的歌 */
  const EMO_HOLD_MS = {
    surprise: 6000,
    fear: 6000,
    angry: 6000,
    disgust: 6000,
    happy: 3000,
    sad: 3000,
    neutral: 0,
  };
  const LIVE_SWITCH_HITS = 2;
  const LIVE_NEUTRAL_HITS = 2;
  const LIVE_MIN_PROB = 0.52;
  const LIVE_FIRST_PROB = { surprise: 0.7, happy: 0.6, fear: 0.64, angry: 0.58, disgust: 0.6, sad: 0.52 };
  const LIVE_TICK_MS = 1400;
  const TRACK_PERIOD_MS = 90; // 框与关键点约 10 帧/秒取样，网页 60fps 插值
  const TRACK_RETRY_MS = 60;
  const TRACK_KICK_OTHER_MS = 1000;
  const TRACK_KICK_SPIKE_MS = 480;
  const TRACK_KICK_NEUTRAL_MS = 1200;
  const TRACK_KICK_GAP_MS = 1100;
  const UI_EMO_HITS = 3;
  const UI_EMO_DWELL_MS = 480;
  const UI_SPIKE_HITS = 2;
  const UI_SPIKE_DWELL_MS = 280;
  const UI_DAILY_NEUTRAL_DWELL_MS = 640;

  /* 课堂演示模式：惊讶更容易认出；喜悦要更有把握（孩子紧张时的微笑不算） */
  const DEMO_FIRST_PROB = { surprise: 0.5, fear: 0.56, happy: 0.68 };

  function liveProbBar(locked, emoId) {
    if (state.demoMode && DEMO_FIRST_PROB[emoId]) {
      if (emoId === "happy") return DEMO_FIRST_PROB.happy;
      if (TRANSIENT_EMO[emoId] || !locked) return DEMO_FIRST_PROB[emoId];
    }
    if (TRANSIENT_EMO[emoId]) return LIVE_FIRST_PROB[emoId] || 0.68;
    if (!locked) return LIVE_FIRST_PROB[emoId] || LIVE_MIN_PROB;
    return LIVE_MIN_PROB;
  }

  function uiSwitchNeed(fromId, toId, prob) {
    if (TRANSIENT_EMO[toId]) {
      return { hits: UI_SPIKE_HITS, dwell: UI_SPIKE_DWELL_MS, minProb: state.demoMode ? 0.45 : 0.55 };
    }
    if (toId === "neutral" && fromId && fromId !== "neutral" && DAILY_EMO[fromId]) {
      return { hits: UI_EMO_HITS, dwell: UI_DAILY_NEUTRAL_DWELL_MS, minProb: 0 };
    }
    return { hits: UI_EMO_HITS, dwell: UI_EMO_DWELL_MS, minProb: toId === "neutral" ? 0 : 0.42 };
  }

  function playlistSwitchNeed(locked, emoId, low) {
    if (!locked && low) return 3;
    if (TRANSIENT_EMO[emoId] && !low && (!locked || locked === "neutral")) return 1;
    return LIVE_SWITCH_HITS;
  }

  function holdLeftMs(id) {
    if (!id || id === "neutral") return 0;
    const span = EMO_HOLD_MS[id] || 0;
    if (!span) return 0;
    if (!state.lockAt) return TRANSIENT_EMO[id] ? 1 : 0;
    return Math.max(0, span - (Date.now() - state.lockAt));
  }

  function decideLiveAction(locked, emoId, low) {
    const isSame = !!(emoId && emoId === locked);
    const isStrongOther = !!(emoId && emoId !== locked && emoId !== "neutral" && !low);
    if (!locked) {
      if (low && emoId && emoId !== "neutral") return { action: "pending-other", reason: "weak-first" };
      return { action: "apply", reason: "first" };
    }
    if (isSame) return { action: "same", reason: locked };
    if (isStrongOther) return { action: "pending-other", reason: emoId };
    if (holdLeftMs(locked) > 0) return { action: "hold", reason: "relax" };
    return { action: "pending-neutral", reason: "sustain-expired" };
  }

  function lockPlaylist(id) {
    state.lockEmotion = id || "";
    state.lockAt = Date.now();
    state.lastEmotion = id || "";
    state.holdRelaxed = false;
    state.liveGuess = "";
    state.liveGuessCount = 0;
    updateHoldUi(false);
  }

  function startHoldTick() {
    if (state.holdTick) return;
    state.holdTick = setInterval(() => {
      if (!state.live) return;
      tickUiSpeak();
      /* 兜底：已经播报过当前表情但歌还没换（例如截帧没认出同一情绪），3 秒后再换一次 */
      const faceEmo = state.uiEmo;
      if (
        state.voiceOn &&
        faceEmo && faceEmo !== "idle" && faceEmo !== state.lockEmotion &&
        faceEmo === state.lastSpokenEmo && !state.speaking && !state.forceApplyEmo &&
        Date.now() - (state.lastSpokenAt || 0) > 3000
      ) {
        switchAfterSpeech(faceEmo);
      }
      const pendingId = state.liveGuess;
      if (pendingId && pendingId !== "neutral" && pendingId !== state.lockEmotion) {
        updateHoldUi(false, (EMO_META[pendingId] || {}).name || "");
        return;
      }
      updateHoldUi(state.holdRelaxed);
    }, 1000);
  }

  function stopHoldTick() {
    if (!state.holdTick) return;
    clearInterval(state.holdTick);
    state.holdTick = 0;
  }

  function updateHoldUi(relaxed, pendingName) {
    const hold = $("#emo-hold");
    const id = state.lockEmotion;
    const live = state.live;
    state.holdRelaxed = pendingName ? false : !!relaxed;
    const climax = !!(live && TRANSIENT_EMO[id]);
    if (ui.hero) {
      ui.hero.classList.toggle("is-hold", !!(live && id && id !== "neutral"));
      ui.hero.classList.toggle("is-climax", climax);
      ui.hero.classList.toggle("is-relaxed", !!(live && state.holdRelaxed && id && id !== "neutral"));
    }
    const note = $("#hold-note");
    if (note) note.hidden = !!(live && id);
    if (!hold) return;
    if (!live || !id) {
      hold.hidden = true;
      hold.textContent = "";
      hold.classList.remove("is-relaxed", "is-climax");
      return;
    }
    const meta = EMO_META[id] || {};
    const name = meta.name || "";
    const left = Math.ceil(holdLeftMs(id) / 1000);
    hold.hidden = false;
    hold.classList.toggle("is-relaxed", !!(state.holdRelaxed && !pendingName));
    hold.classList.toggle("is-climax", climax && !pendingName);
    if (pendingName) {
      hold.textContent = `好像在变成「${pendingName}」，再保持一下就会切歌`;
    } else if (id === "neutral") {
      hold.textContent = "当前按平静连播。摆出喜、怒、哀、惧、惊、厌等更明显的表情，确认后才会切歌。";
    } else if (state.holdRelaxed) {
      hold.textContent =
        left > 0
          ? `脸已松开，歌曲仍锁定「${name}」· 约 ${left} 秒内不会因平静换歌`
          : `脸已松开，歌曲仍按「${name}」播放 · 持续平静才会换歌到中性歌单`;
      $("#emo-kicker").textContent = "歌曲锁定";
      $("#emo-conf").textContent = `画面此刻平静 · 继续播放${name}歌单`;
    } else if (TRANSIENT_EMO[id] && left > 0) {
      hold.textContent = `已锁定「${name}」反差歌 · 约 ${left} 秒内松开脸也不会立刻换歌`;
    } else if (left > 0) {
      hold.textContent = `按「${name}」连播 · 约 ${left} 秒内短暂松开也不会换歌`;
    } else {
      hold.textContent = `按「${name}」连播 · 换一种明显表情或持续平静才会切歌`;
    }
  }

  function stopLive() {
    hushVoice();
    state.live = false;
    const tog = $("#live-toggle");
    if (tog) tog.checked = false;
    if (state.liveTimer) {
      clearInterval(state.liveTimer);
      state.liveTimer = 0;
    }
    stopHoldTick();
    updateHoldUi(false);
    syncLiveHudDot();
    syncDetectBtn();
  }

  function syncDemoBadge() {
    const badge = $("#demo-badge");
    if (badge) badge.hidden = !state.demoMode;
  }

  function syncDetectBtn() {
    const btn = $("#btn-detect");
    if (!btn) return;
    const on = !!state.live && !state.detectOff;
    btn.classList.toggle("is-on", on);
    btn.setAttribute("aria-pressed", on ? "true" : "false");
    btn.querySelector("span").textContent = on ? "实时检测 开" : "实时检测 关";
  }

  /* 顶栏开关：关 = 停实时识别 + 停人脸框跟踪（画面保留）；开 = 一起恢复 */
  function setDetect(on) {
    const tog = $("#live-toggle");
    if (on) {
      state.detectOff = false;
      startTrackLoop();
      if (tog && !tog.checked) {
        tog.checked = true;
        tog.dispatchEvent(new Event("change", { bubbles: true }));
      }
    } else {
      state.detectOff = true;
      stopLive();
      stopTrackLoop();
      clearFaceOverlay();
      const hud = $("#live-emo-hud");
      if (hud) hud.hidden = true;
    }
    syncDetectBtn();
  }

  function syncLiveHudDot() {
    const dot = $("#live-emo-dot");
    if (dot) dot.hidden = !state.live;
  }

  function sizeFaceOverlay() {
    const canvas = ui.overlay;
    const host = $("#cam-layer") || $("#viewport");
    if (!canvas || !host) return null;
    const cssW = host.clientWidth;
    const cssH = host.clientHeight;
    if (cssW < 8 || cssH < 8) return null;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const w = Math.round(cssW * dpr);
    const h = Math.round(cssH * dpr);
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
      canvas.style.width = `${cssW}px`;
      canvas.style.height = `${cssH}px`;
    }
    return { cssW, cssH, dpr };
  }

  function mapBoxToCanvas(box, imageSize, mirror) {
    const sized = sizeFaceOverlay();
    if (!sized || !box || !imageSize) return null;
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

  function lerpBox(a, b, t) {
    if (!a) return b;
    return {
      x: a.x + (b.x - a.x) * t,
      y: a.y + (b.y - a.y) * t,
      w: a.w + (b.w - a.w) * t,
      h: a.h + (b.h - a.h) * t,
    };
  }

  function boxIou(a, b) {
    const x1 = Math.max(a.x, b.x);
    const y1 = Math.max(a.y, b.y);
    const x2 = Math.min(a.x + a.w, b.x + b.w);
    const y2 = Math.min(a.y + a.h, b.y + b.h);
    const inter = Math.max(0, x2 - x1) * Math.max(0, y2 - y1);
    const ua = a.w * a.h + b.w * b.h - inter;
    return ua > 0 ? inter / ua : 0;
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


  function emoHex(id, fromApi) {
    if (fromApi && /^#[0-9a-fA-F]{3,8}$/.test(String(fromApi))) return fromApi;
    return EMO_HEX[id] || EMO_HEX.idle;
  }

  function drawCornerBrackets(ctx, x, y, w, h, color) {
    const len = Math.max(16, Math.min(w, h) * 0.22);
    ctx.strokeStyle = color;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.beginPath();
    ctx.moveTo(x, y + len);
    ctx.lineTo(x, y);
    ctx.lineTo(x + len, y);
    ctx.moveTo(x + w - len, y);
    ctx.lineTo(x + w, y);
    ctx.lineTo(x + w, y + len);
    ctx.moveTo(x + w, y + h - len);
    ctx.lineTo(x + w, y + h);
    ctx.lineTo(x + w - len, y + h);
    ctx.moveTo(x + len, y + h);
    ctx.lineTo(x, y + h);
    ctx.lineTo(x, y + h - len);
    ctx.stroke();
  }

  function paintHudTone(hud, emoId, fromApi, miss) {
    if (!hud) return;
    if (miss) {
      hud.style.removeProperty("--emo");
      hud.style.color = "";
      hud.style.borderColor = "";
      return;
    }
    const color = emoHex(emoId, fromApi);
    hud.style.setProperty("--emo", color);
    hud.style.color = color;
    hud.style.borderColor = color;
  }

  function flashLiveHud(hud) {
    if (!hud) return;
    hud.classList.remove("is-flash");
    void hud.offsetWidth;
    hud.classList.add("is-flash");
  }

  function clearFaceOverlay() {
    const canvas = ui.overlay;
    if (canvas) {
      const ctx = canvas.getContext("2d");
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
    state.overlaySmooth = [];
    state.overlayTarget = [];
    state.overlayMiss = 0;
    state.lastOverlay = { id: "idle", color: EMO_HEX.idle };
    state.lastVote = null;
    const hud = $("#live-emo-hud");
    if (hud) {
      hud.hidden = true;
      paintHudTone(hud, "idle", "", true);
    }
  }

  function paintEmoNow(data) {
    const el = $("#emo-now");
    if (!el) return;
    if (!isLiveMode() || (ui.empty && !ui.empty.hidden)) {
      el.hidden = true;
      return;
    }
    const emo = (data && data.ok && data.emotion) || null;
    const locked = state.lockEmotion;
    el.hidden = false;
    if (!emo && !state.uiEmo) {
      el.textContent = "画面此刻 · 寻找人脸";
      return;
    }
    const id = state.uiEmo || (emo && emo.id) || "";
    const meta = EMO_META[id] || {};
    const nm = meta.name || (emo && emo.name) || "";
    const pct = Math.round(((emo && id === emo.id && emo.prob) || 0) * 100);
    const lockName = (EMO_META[locked] || {}).name || "";
    if (locked && id && id !== locked) {
      el.textContent = `画面此刻 · ${nm}${pct ? " " + pct + "%" : ""} · 歌单仍按${lockName}`;
    } else {
      el.textContent = `画面此刻 · ${nm}${pct ? " " + pct + "%" : ""}`;
    }
  }

  function commitLiveUi(emo) {
    const id = emo && emo.id && EMO_META[emo.id] && emo.id !== "idle" ? emo.id : "";
    if (!id) return state.uiEmo || "";
    const extra = { name: emo.name, scores: emo.scores };
    if (!state.uiEmo) {
      paintUiEmotion(id, extra);
      state.uiGuess = id;
      state.uiGuessHits = 0;
      state.uiGuessAt = Date.now();
      resetLiveSpeak(id);
      if (state.live && TRANSIENT_EMO[id]) kickLiveRecognize();
      return id;
    }
    if (id === state.uiEmo) {
      paintUiEmotion(id, extra);
      state.uiGuess = id;
      state.uiGuessHits = 0;
      tickUiSpeak(emo);
      return id;
    }
    const prob = Number(emo.prob) || 0;
    const need = uiSwitchNeed(state.uiEmo, id, prob);
    if (prob < need.minProb && id !== "neutral") return state.uiEmo;
    if (state.uiGuess !== id) {
      state.uiGuess = id;
      state.uiGuessHits = 1;
      state.uiGuessAt = Date.now();
      return state.uiEmo;
    }
    state.uiGuessHits += 1;
    if (state.uiGuessHits >= need.hits && Date.now() - (state.uiGuessAt || 0) >= need.dwell) {
      paintUiEmotion(id, extra);
      state.uiGuessHits = 0;
      resetLiveSpeak(id);
      tickUiSpeak(emo);
      if (state.live && TRANSIENT_EMO[id]) kickLiveRecognize();
      return id;
    }
    return state.uiEmo;
  }

  async function kickLiveRecognize() {
    if (!state.live || !isLiveMode() || state.recognizing || !frameReady()) return;
    const now = Date.now();
    if (now - (state.liveKickAt || 0) < TRACK_KICK_GAP_MS) return;
    state.liveKickAt = now;
    const blob = await captureBlob(0.9, 720);
    if (blob && state.live) recognize(blob, liveSource());
  }

  function noteTrackEmotion(data) {
    const id = (data && data.ok && data.emotion && data.emotion.id) || "";
    const now = Date.now();
    if (id !== state.trackEmo) {
      state.trackEmo = id;
      state.trackEmoAt = now;
    }
    if (!state.live) return;
    const locked = state.lockEmotion;
    const stable = now - (state.trackEmoAt || now);
    if (!id) return;
    if (id !== locked && TRANSIENT_EMO[id] && stable >= TRACK_KICK_SPIKE_MS) kickLiveRecognize();
    else if (id !== locked && id !== "neutral" && stable >= TRACK_KICK_OTHER_MS) kickLiveRecognize();
    else if (
      id === "neutral" &&
      locked &&
      locked !== "neutral" &&
      holdLeftMs(locked) <= 0 &&
      stable >= TRACK_KICK_NEUTRAL_MS
    ) {
      kickLiveRecognize();
    }
  }

  function updateLiveHud(data) {
    noteTrackEmotion(data);
    if (data && data.ok && data.emotion) {
      state.uiEmoAt = Date.now(); // 时间线：有人脸就持续记录
      const sc = (data.emotion.scores || []).find((x) => x && x.id === state.uiEmo);
      state.uiEmoProb = sc ? Number(sc.prob) || 0 : data.emotion.id === state.uiEmo ? Number(data.emotion.prob) || 0 : state.uiEmoProb;
    }
    const hud = $("#live-emo-hud");
    if (!hud) return;
    if (ui.empty && !ui.empty.hidden) {
      hud.hidden = true;
      paintEmoNow(data);
      return;
    }
    hud.hidden = false;
    syncLiveHudDot();
    const emo = (data && data.ok && data.emotion) || null;
    if (!emo) {
      const keep = state.uiEmo && EMO_META[state.uiEmo] ? state.uiEmo : "";
      if (keep) {
        hud.classList.remove("is-miss");
        hud.dataset.emo = keep;
        paintHudTone(hud, keep, "", false);
        const keepMeta = EMO_META[keep] || {};
        $("#live-emo-zh").textContent = keepMeta.zh || "";
        $("#live-emo-name").textContent = keepMeta.name || "";
        $("#live-emo-pct").textContent = "";
        paintEmoNow(data);
        return;
      }
      const changed = hud.dataset.emo !== "idle" || !hud.classList.contains("is-miss");
      hud.dataset.emo = "idle";
      hud.classList.add("is-miss");
      paintHudTone(hud, "idle", "", true);
      $("#live-emo-zh").textContent = "";
      $("#live-emo-name").textContent = "寻找人脸";
      $("#live-emo-pct").textContent = "";
      const countMiss = $("#live-emo-count");
      if (countMiss) countMiss.textContent = "";
      state.lastOverlay = { id: "idle", color: EMO_HEX.idle };
      state.lastVote = null;
      if (changed) flashLiveHud(hud);
      paintEmoNow(data);
      return;
    }
    const shownId = commitLiveUi(emo) || emo.id || "idle";
    const color = emoHex(shownId, (EMO_META[shownId] || {}).color || emo.color);
    const changed = hud.dataset.emo !== shownId || hud.classList.contains("is-miss");
    hud.classList.remove("is-miss");
    hud.dataset.emo = shownId;
    paintHudTone(hud, shownId, color, false);
    if (changed) flashLiveHud(hud);
    const meta = EMO_META[shownId] || {};
    $("#live-emo-zh").textContent = meta.zh || "";
    $("#live-emo-name").textContent = meta.name || "";
    const pct = Math.round((emo.prob || 0) * 100);
    $("#live-emo-pct").textContent = shownId === emo.id && pct ? `${pct}%` : "";
    const vote = (data && data.vote) || {};
    const n = vote.total || data.face_count || 0;
    const countEl = $("#live-emo-count");
    if (countEl) {
      countEl.textContent = n > 1 ? `${n} 张 · 多数 ${vote.majority || n}` : n === 1 ? "1 张脸" : "";
    }
    state.lastOverlay = { id: shownId, color };
    state.lastVote = vote;
    paintEmoNow(data);
    if (Array.isArray(emo.scores) && emo.scores.length) renderProbAndVa(emo.scores, shownId);
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
        const v = boxIou(p.box, item.box);
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

  function mapPointToCanvas(pt, imageSize, mirror) {
    const sized = sizeFaceOverlay();
    if (!sized || pt == null || !imageSize) return null;
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

  function mapTrackItems(data) {
    const imageSize = (data.face && data.face.image_size) || [ui.shot.width, ui.shot.height];
    const raw = (data.faces && data.faces.length
      ? data.faces
      : data.face && data.face.box
        ? [{ box: data.face.box, primary: true, emotion: data.emotion }]
        : []
    ).filter((f) => f && f.box);
    const mapped = [];
    raw.forEach((f) => {
      const box = mapBoxToCanvas(f.box, imageSize, !!state.mirror);
      if (!box) return;
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
          const xy = mapPointToCanvas([p.x, p.y], imageSize, !!state.mirror);
          if (!xy) return null;
          return Object.assign({}, p, { zh: mirrorZh(p.zh, !!state.mirror), x: xy.x, y: xy.y });
        })
        .filter(Boolean);
      mapped.push({
        box,
        primary: !!f.primary,
        emo: f.emotion || data.emotion || {},
        points,
        cues: f.cues || [],
      });
    });
    return mapped;
  }

  function paintFaceLandmarks(ctx, item, color) {
    if (window.EmoTuneDraw) {
      if (state.landmarkMode === "mesh") EmoTuneDraw.paintMesh(ctx, item, color);
      else EmoTuneDraw.paintDots(ctx, item, color);
      return;
    }
    const pts = item.points || [];
    if (!pts.length) return;
    pts.forEach((p) => {
      ctx.beginPath();
      ctx.fillStyle = color;
      ctx.arc(p.x, p.y, 3.2, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  function paintFaceCues(ctx, item, color) {
    if (window.EmoTuneDraw) {
      EmoTuneDraw.paintAuChips(ctx, item, color, ctx.canvas);
      return;
    }
    const cues = item.cues || [];
    if (!cues.length) return;
    ctx.fillStyle = color;
    ctx.font = '600 12px "Noto Sans SC","Microsoft YaHei",sans-serif';
    cues.forEach((c, i) => {
      ctx.fillText(`${c.symbol || ""} ${c.text || ""}`.trim(), 12, 18 + i * 16);
    });
  }

  function overlayDisplayItems(mapped) {
    const shown = state.uiEmo && EMO_META[state.uiEmo] ? state.uiEmo : (state.lastOverlay && state.lastOverlay.id) || "";
    const shownMeta = EMO_META[shown] || {};
    const color = (state.lastOverlay && state.lastOverlay.color) || shownMeta.color;
    return (mapped || []).map((item) => {
      const emo = item.emo || {};
      const solo = item.primary || (mapped && mapped.length === 1);
      if (!solo || !shown || shown === "idle") {
        if (emo.id && emo.color) return item;
        return Object.assign({}, item, {
          emo: Object.assign({}, emo, {
            id: emo.id || shown || "idle",
            color: emo.color || color,
          }),
        });
      }
      return Object.assign({}, item, {
        emo: Object.assign({}, emo, {
          id: shown,
          zh: shownMeta.zh || emo.zh,
          name: shownMeta.name || emo.name,
          color: color || emo.color,
          prob: emo.id === shown ? emo.prob : 0,
        }),
      });
    });
  }

  function paintFaceOverlay() {
    const canvas = ui.overlay;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    sizeFaceOverlay();
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (state.landmarkMode === "off") return;
    const mapped = overlayDisplayItems(state.overlaySmooth || []);
    if (!mapped.length) return;
    const majority = state.lastOverlay || {};
    if (window.EmoTuneDraw) {
      EmoTuneDraw.paintFaces(ctx, mapped, { mode: state.landmarkMode, canvas });
      return;
    }
    mapped.forEach((item) => {
      const color = emoHex((item.emo && item.emo.id) || majority.id, item.emo && item.emo.color);
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
      paintFaceOverlay();
      if (state.trackOn) state.overlayRaf = requestAnimationFrame(step);
    };
    state.overlayRaf = requestAnimationFrame(step);
  }

  function drawFaceOverlay(data) {
    updateLiveHud(data);
    if (!data || !data.ok) {
      state.overlayMiss += 1;
      if (state.overlayMiss >= 4) {
        state.overlayTarget = [];
        state.overlaySmooth = [];
        paintFaceOverlay();
      }
      return;
    }
    const mapped = mapTrackItems(data);
    if (!mapped.length) {
      state.overlayMiss += 1;
      if (state.overlayMiss >= 4) {
        state.overlayTarget = [];
        state.overlaySmooth = [];
        paintFaceOverlay();
      }
      return;
    }
    state.overlayMiss = 0;
    state.overlayTarget = mapped;
    if (!state.overlaySmooth.length) {
      state.overlaySmooth = mapped.map(cloneOverlayItem);
      paintFaceOverlay();
    }
    ensureOverlayPump();
  }

  function stopTrackLoop() {
    state.trackOn = false;
    if (state.trackTimer) {
      clearTimeout(state.trackTimer);
      state.trackTimer = 0;
    }
    if (state.overlayRaf) {
      cancelAnimationFrame(state.overlayRaf);
      state.overlayRaf = 0;
    }
    state.trackBusy = false;
  }

  function startTrackLoop() {
    if (state.facePopActive) return;
    if (state.detectOff) return; // 用户关掉了实时检测
    if (state.trackOn) return;
    state.trackOn = true;
    ensureOverlayPump();
    const tick = async () => {
      state.trackTimer = 0;
      if (!state.trackOn) return;
      const liveOk = isLiveMode() && frameReady() && !(ui.empty && !ui.empty.hidden);
      if (!liveOk) {
        clearFaceOverlay();
        if (state.trackOn && isLiveMode() && frameReady()) {
          state.trackTimer = setTimeout(tick, TRACK_PERIOD_MS);
        }
        return;
      }
      if (!state.trackBusy) {
        state.trackBusy = true;
        try {
          const crowd = state.faceMode === "crowd";
          const blob = await captureBlob(crowd ? 0.78 : 0.8, crowd ? 800 : 640);
          if (blob && state.trackOn && isLiveMode()) {
            const fd = new FormData();
            fd.append("image", blob, "track.jpg");
            const res = await fetch("/api/track?mode=" + encodeURIComponent(state.faceMode || "solo"), {
              method: "POST",
              body: fd,
              headers: faceHeaders({ "X-Emo-Source": liveSource() }),
            });
            const data = await res.json();
            if (state.trackOn && isLiveMode()) drawFaceOverlay(data);
            const elapsed = Number((data && data.elapsed_ms) || 40);
            if (state.trackOn && isLiveMode() && frameReady()) {
              state.trackTimer = setTimeout(tick, Math.max(15, TRACK_PERIOD_MS - elapsed));
            }
            return;
          }
        } catch {
          /* 追踪失败时下一拍再试 */
        } finally {
          state.trackBusy = false;
        }
      }
      if (state.trackOn && isLiveMode() && frameReady()) {
        state.trackTimer = setTimeout(tick, TRACK_RETRY_MS);
      }
    };
    state.trackTimer = setTimeout(tick, 80);
  }

  function showPanel(mode) {
    state.mode = mode;
    $$(".tab").forEach((t) => {
      const on = t.dataset.mode === mode;
      t.classList.toggle("is-on", on);
      t.setAttribute("aria-selected", on ? "true" : "false");
    });
    const view = isLiveMode(mode) ? "live" : "upload";
    $$(".stage-body").forEach((v) => {
      v.hidden = v.dataset.view !== view;
    });
  }

  function setMode(mode) {
    const next = ["camera", "upload", "video", "screen"].includes(mode) ? mode : "camera";
    const prev = state.mode;
    if (prev === next) {
      showPanel(next);
      updateLiveChrome();
      return;
    }
    stopLive();
    if (isLiveMode(prev) || isLiveMode(next)) stopCameraStream();
    showPanel(next);
    setMirror(next === "camera");
    updateLiveChrome();
    ui.preview.hidden = true;
    if (isLiveMode(next)) {
      ui.cam.hidden = false;
      if (ui.empty) ui.empty.hidden = frameReady();
      if (frameReady()) startTrackLoop();
    }
    if (next === "camera") startCamera();
  }

  function renderEmoTags(scores = [], currentId = "") {
    if (!ui.tags) return;
    const map = Object.fromEntries((scores || []).map((s) => [s.id, s]));
    ui.tags.innerHTML = EMO_ORDER.map((id) => {
      const meta = EMO_META[id];
      const s = map[id] || {};
      const pct = Math.round((s.prob || 0) * 100);
      const on = id === currentId;
      return `<div class="emo-tag${on ? " is-on is-pulse" : ""}" data-emo="${id}" role="listitem" aria-current="${on ? "true" : "false"}">
        <span class="emo-tag-icon">${faceSvg(id, on ? 68 : 52)}</span>
        <span class="emo-tag-zh">${meta.zh}</span>
        <span class="emo-tag-pct">${scores.length ? pct + "%" : meta.name}</span>
      </div>`;
    }).join("");
  }

  function isCameraSource(source) {
    return source === "camera" || source === "camera-live";
  }

  function faceCropSrc(face) {
    const crop = face && typeof face.crop === "string" ? face.crop.trim() : "";
    if (!crop) return "";
    if (crop.indexOf("data:image/") === 0) return crop;
    if (crop.indexOf("/static/") === 0) return crop;
    if (/\.(jpe?g|png|webp)(\?.*)?$/i.test(crop)) return crop;
    return "";
  }

  function showFaceCrop(payload) {
    const shot = ui.emoShot;
    const img = ui.emoFace;
    const empty = ui.emoShotEmpty;
    const cap = ui.emoFaceCap;
    if (!shot || !img) return;
    const face = (payload && payload.face) || {};
    const crop = faceCropSrc(face);
    shot.classList.toggle("is-mirror", isCameraSource(payload && payload.source));
    if (crop) {
      img.src = crop;
      img.hidden = false;
      shot.classList.add("has-face");
      if (empty) empty.hidden = true;
      const score = Number(face.score);
      if (cap) {
        cap.textContent =
          Number.isFinite(score) && score > 0
            ? `识别人脸 · ${Math.round(score * 100)}%`
            : "识别人脸";
      }
    } else {
      img.removeAttribute("src");
      img.hidden = true;
      shot.classList.remove("has-face");
      if (empty) empty.hidden = false;
      if (cap) cap.textContent = "识别人脸";
    }
  }

  function showIdle() {
    document.body.dataset.emotion = "idle";
    state.uiEmo = "";
    state.uiTagSig = "";
    state.uiGuess = "";
    state.uiGuessHits = 0;
    state.uiGuessAt = 0;
    if (ui.hero) ui.hero.dataset.emo = "idle";
    const viz = $("#audio-viz");
    if (viz) viz.dataset.emo = "idle";
    if (ui.icon) ui.icon.innerHTML = faceSvg("idle", 180);
    showFaceCrop({});
    $("#emo-kicker").textContent = "YuNet · MobileFaceNet FER";
    $("#emo-zh").textContent = "待识别";
    $("#emo-name").textContent = "面向镜头，点识别此刻";
    $("#emo-conf").textContent = "";
    $("#emo-copy").textContent =
      "识别后人脸、此刻情绪、歌曲、音乐可视化和语音提示共用同一套七类标签。推荐默认同频。日常平静、喜悦、悲伤会稳住再换歌；惊讶、恐惧、愤怒、厌恶认到就锁反差歌。识别此刻或上传立刻说。";
    const nowEl = $("#emo-now");
    if (nowEl) {
      nowEl.hidden = true;
      nowEl.textContent = "";
    }
    paintStrategyNow();
    const genre = $("#emo-genre");
    genre.hidden = true;
    genre.textContent = "";
    renderEmoTags([], "");
    renderProbAndVa([], "");
  }

  function showEmotion(payload, opts) {
    opts = opts || {};
    const e = payload.emotion;
    const prev = state.uiEmo;
    const liveTick = isLiveSource(payload && payload.source);
    if (!liveTick || opts.commitUi) {
      paintUiEmotion(e.id, { name: e.name, scores: e.scores });
      if (e && e.id) {
        state.uiGuess = e.id;
        state.uiGuessHits = 0;
        state.uiGuessAt = Date.now();
        if (liveTick) {
          if (e.id !== prev) resetLiveSpeak(e.id);
          else tickUiSpeak(e);
        }
      }
    }
    showFaceCrop(payload);
    $("#emo-kicker").textContent = "YuNet · MobileFaceNet FER";
    const rec = payload.recommendations || {};
    if (rec.strategy && rec.strategy.id) state.strategy = rec.strategy.id;
    paintStrategyNow(rec.strategy);
    const meta = EMO_META[e.id] || {};
    const conf = Math.round(e.prob * 100);
    const vote = payload.vote || {};
    const many = (vote.total || payload.face_count || 0) > 1;
    if (many) {
      $("#emo-conf").textContent = e.low_confidence
        ? `${vote.total} 张脸 · 多数「${meta.name || e.name || ""}」${vote.majority}/${vote.total} · 光线一般仅供参考`
        : `${vote.total} 张脸 · 多数「${meta.name || e.name || ""}」${vote.majority}/${vote.total}`;
    } else {
      $("#emo-conf").textContent = e.low_confidence
        ? `置信度 ${conf}% · 光线或角度一般，结果仅供参考`
        : `置信度 ${conf}%`;
    }
    $("#emo-copy").textContent = e.copy;
    const genre = $("#emo-genre");
    genre.hidden = !e.genre;
    genre.textContent = e.genre || "";
    const ms = payload.elapsed_ms || payload.total_ms;
    $("#timing").textContent = ms ? `识别 ${Math.round(ms)} 毫秒` : "";
    if (!liveTick && (opts.speak === true || (opts.speak !== false && prev !== e.id))) {
      speakEmotionChange(e, opts.speak === true);
    }
    if (!liveTick) {
      const narrow = window.matchMedia("(max-width: 980px)").matches;
      if (narrow && ui.hero) {
        requestAnimationFrame(() => {
          ui.hero.scrollIntoView({ behavior: "smooth", block: "center" });
        });
      }
    }
  }


  function uniqueSongs(list) {
    const seen = new Set();
    const out = [];
    for (const song of list || []) {
      const key = foldTitle(song.title);
      if (key && seen.has(key)) continue;
      if (key) seen.add(key);
      out.push(song);
    }
    return out;
  }

  function songEmotionId(song) {
    if (!song) return "";
    const cand = [song.emotion, song.music && song.music.emotion];
    for (const raw of cand) {
      const id = String(raw || "").trim();
      if (id && EMO_META[id] && id !== "idle") return id;
    }
    const m = /^vocal-([a-z]+)-\d+$/.exec(String(song.id || ""));
    return m && EMO_META[m[1]] ? m[1] : "";
  }

  function songEmoChip(song, faceId) {
    const id = songEmotionId(song);
    if (!id) return "";
    const meta = EMO_META[id] || {};
    const zh = String(song.emotion_zh || meta.zh || "");
    const name = String(song.emotion_name || meta.name || "");
    const mismatch = Boolean(faceId) && faceId !== id && EMO_META[faceId] && faceId !== "idle";
    const label = mismatch ? `歌曲情绪：${name}，与识别情绪不同` : `歌曲情绪：${name}`;
    return `<span class="song-emo${mismatch ? " is-off" : ""}" data-emo="${esc(id)}" title="${esc(label)}" aria-label="${esc(label)}"><b>${esc(zh)}</b><i>${esc(name)}</i></span>`;
  }

  function songCard(song, idx) {
    const cover = esc(song.cover || "");
    const title = esc(prettyText(song.title));
    const artist = esc(prettyText(song.artist));
    const album = song.album ? " · " + esc(prettyText(song.album)) : "";
    const playable = song.playable && song.audio;
    const badge = esc(prettyText(song.source_label || SOURCE_ZH[song.source] || song.source || ""));
    const faceId = displayEmotionId() || state.lockEmotion || state.lastEmotion || "";
    const emoId = songEmotionId(song);
    return `<article class="song" data-idx="${idx}" data-emo="${esc(emoId)}">
      <img src="${cover}" alt="${title} 封面" onerror="this.style.opacity=.2" />
      <div class="body">
        <div class="song-head">
          <strong>${title}</strong>
          ${songEmoChip(song, faceId)}
        </div>
        <em>${artist}${album}</em>
        ${song.rec_role_zh ? `<p class="song-algo">${esc(song.rec_role_zh)}${song.music ? " · 曲调 " + esc(song.music.emotion_zh || "") + " · " + esc(song.music.tempo_label || "") + " · " + esc(song.music.mode_zh || "") : ""}${song.match != null ? " · 匹配 " + Math.round(Number(song.match) * 100) + "%" : ""}</p>` : song.music ? `<p class="song-algo">曲调 ${esc(song.music.emotion_zh || "")} · ${esc(song.music.tempo_label || "")} · ${esc(song.music.mode_zh || "")}${song.match != null ? " · 匹配 " + Math.round(Number(song.match) * 100) + "%" : ""}</p>` : ""}
      </div>
      <div class="ops">
        <span class="badge">${badge}</span>
        <span>
          ${playable ? `<button type="button" class="ghost mini" data-play="${idx}">播放</button>` : ""}
          ${song.downloadable ? `<a class="ghost mini" href="/api/audio/${esc(song.id)}/download">下载</a>` : ""}
          ${song.external_url ? `<a class="ghost mini" href="${esc(song.external_url)}" target="_blank" rel="noopener">源页</a>` : ""}
        </span>
      </div>
    </article>`;
  }

  function renderSongs(list, meta) {
    state.songs = uniqueSongs(list);
    state.failed = new Set();
    $("#recs-meta").textContent =
      meta ||
      (state.songs.length
        ? `本地曲库 ${state.songs.length} 首 · 自动连续播放`
        : "默认同频 · 识别后自动连播；日常平静喜悦悲伤稳住再换歌，惊讶恐惧愤怒厌恶锁反差歌，松开后也不会马上换歌");
    if (!state.songs.length) {
      ui.songs.innerHTML = `<p class="empty-songs">还没有歌曲。完成识别后，这里会列出并自动播放匹配曲目。</p>`;
      paintBoardCounts(null, 0);
      return;
    }
    ui.songs.innerHTML = state.songs.map(songCard).join("");
    paintBoardCounts(null, state.songs.length);
  }

  /* 换歌原因：画面上浮出「检测到 惊讶 → 同频 → 《最炫民族风》」约 4 秒 */
  function showSwitchReason(emoId, rec) {
    const box = $("#switch-reason");
    const meta = EMO_META[emoId];
    if (!box || !meta) return;
    const song = state.songs[state.index] || state.songs[0];
    if (!song) return;
    const strat = ((rec && rec.strategy) || {}).zh || ((rec && rec.strategy) || {}).name || "";
    box.dataset.emo = emoId;
    box.innerHTML =
      `<span class="sr-emo"><b>${esc(meta.zh)}</b>检测到 ${esc(meta.name)}</span>` +
      `<i aria-hidden="true">→</i>${strat ? `<span class="sr-strat">${esc(strat)}</span><i aria-hidden="true">→</i>` : ""}` +
      `<span class="sr-song">《${esc(prettyText(song.title))}》</span>`;
    box.hidden = false;
    box.classList.remove("is-in");
    void box.offsetWidth;
    box.classList.add("is-in");
    clearTimeout(state.switchReasonTimer);
    state.switchReasonTimer = setTimeout(() => {
      box.classList.remove("is-in");
      setTimeout(() => (box.hidden = true), 400);
    }, 4200);
  }

  /* 两段式推荐的第二段：后台拿含在线热歌的歌单，合并进来；正在播的歌不打断、位置不变 */
  async function fillOnlineLater(emoId) {
    const token = (state.onlineFillToken = (state.onlineFillToken || 0) + 1);
    try {
      const q = new URLSearchParams({
        emotion: emoId,
        online: "1",
        strategy: state.strategy || "iso",
        fresh: state.skipPlayed ? "1" : "0",
      });
      const data = await (await fetch(`/api/recommend?${q}`)).json();
      if (token !== state.onlineFillToken || !state.onlineOn || state.lockEmotion !== emoId) return;
      const incoming = uniqueSongs((data && data.songs) || []);
      if (!incoming.some((s) => isOnlineSong(s))) return;
      const playing = state.songs[state.index];
      const merged = incoming.slice();
      if (playing) {
        const at = merged.findIndex((s) => foldTitle(s.title) === foldTitle(playing.title));
        if (at >= 0) merged.splice(at, 1);
        merged.unshift(playing);
      }
      const failed = state.failed;
      renderSongs(merged, recsCaption(data));
      state.failed = failed;
      state.index = playing ? 0 : state.index;
      markCurrent();
    } catch {
      /* 在线补充失败就继续用本地歌单 */
    }
  }

  function markCurrent() {
    $$(".song").forEach((el) => el.classList.toggle("is-on", Number(el.dataset.idx) === state.index));
  }

  function songKey(song) {
    return (song && (song.id || song.audio)) || "";
  }

  function isPlayable(song) {
    return Boolean(song && song.audio && !state.failed.has(songKey(song)));
  }

  function isOnlineSong(song) {
    return Boolean(song && song.source && song.source !== "local");
  }

  function currentEmotionId() {
    return state.lockEmotion || state.lastEmotion || "neutral";
  }

  function displayEmotionId() {
    if (state.uiEmo && EMO_META[state.uiEmo] && state.uiEmo !== "idle") return state.uiEmo;
    if (isLiveMode() && state.trackEmo && EMO_META[state.trackEmo] && state.trackEmo !== "idle") {
      return state.trackEmo;
    }
    const locked = state.lockEmotion || state.lastEmotion || "";
    return locked && EMO_META[locked] ? locked : "";
  }

  function paintPlayerEmo(id) {
    const emoEl = $("#player-emo");
    if (!emoEl) return;
    /* 播放器标签只标这首歌自己的情绪，不跟着人脸变，免得看起来像歌被改了标签 */
    const playing = state.songs[state.index];
    const emoId = (playing && songEmotionId(playing)) || id || displayEmotionId();
    if (!emoId || !EMO_META[emoId] || emoId === "idle") return;
    const meta = EMO_META[emoId];
    emoEl.hidden = false;
    emoEl.dataset.emo = emoId;
    emoEl.className = "song-emo";
    emoEl.title = `情绪：${meta.name}`;
    emoEl.setAttribute("aria-label", `情绪：${meta.name}`);
    emoEl.innerHTML = `<b>${esc(meta.zh)}</b><i>${esc(meta.name)}</i>`;
  }

  function paintUiEmotion(id, extra) {
    extra = extra || {};
    const emoId = id && EMO_META[id] && id !== "idle" ? id : "";
    if (!emoId) return;
    const meta = EMO_META[emoId];
    const prev = state.uiEmo;
    state.uiEmo = emoId;
    state.uiEmoAt = Date.now();
    if (Array.isArray(extra.scores)) {
      const hit = extra.scores.find((x) => x && x.id === emoId);
      if (hit) state.uiEmoProb = Number(hit.prob) || 0;
    } else if (extra.prob != null) state.uiEmoProb = Number(extra.prob) || 0;
    document.body.dataset.emotion = emoId;
    if (ui.hero) ui.hero.dataset.emo = emoId;
    const zhEl = $("#emo-zh");
    const nameEl = $("#emo-name");
    if (zhEl) zhEl.textContent = meta.zh;
    if (nameEl) nameEl.textContent = extra.name || meta.name;
    if (ui.icon && prev !== emoId) {
      ui.icon.classList.remove("is-pop");
      ui.icon.innerHTML = faceSvg(emoId, 180);
      void ui.icon.offsetWidth;
      ui.icon.classList.add("is-pop");
    } else if (ui.icon && prev === emoId && !String(ui.icon.innerHTML || "").trim()) {
      ui.icon.innerHTML = faceSvg(emoId, 180);
    }
    const panel = $("#audio-viz");
    if (panel && panel.dataset.emo !== emoId) panel.dataset.emo = emoId;
    paintPlayerEmo(emoId);
    const scores = extra.scores;
    if (Array.isArray(scores) && scores.length) {
      const sig = `${emoId}|${scores.map((s) => `${s.id}:${Math.round((Number(s.prob) || 0) * 10)}`).join(",")}`;
      if (sig !== state.uiTagSig) {
        state.uiTagSig = sig;
        renderEmoTags(scores, emoId);
        renderProbAndVa(scores, emoId);
      }
    } else if (prev !== emoId) {
      $$("#emo-tags .emo-tag").forEach((el) => {
        const on = el.dataset.emo === emoId;
        el.classList.toggle("is-on", on);
        el.classList.toggle("is-pulse", on);
        el.setAttribute("aria-current", on ? "true" : "false");
      });
    }
  }

  function recsCaption(rec) {
    const n = (rec.songs || []).length;
    const providers = (rec.providers || []).map((s) => String(s).replace(/^在线 · /, "")).filter(Boolean);
    const strat = (rec.strategy && (rec.strategy.zh || rec.strategy.name)) || "同频";
    if (rec.online_count > 0) {
      const src = providers.length ? providers.join("、") : "在线";
      return `${rec.genre || ""} · ${src} ${rec.online_count} / 本地 ${rec.local_count || 0} · ${n} 首 · ${strat}`;
    }
    return `${rec.genre || ""} · 本地曲库 ${n} 首 · ${strat}`;
  }

  async function loadPlaylist(emo, play) {
    const id = emo || currentEmotionId();
    try {
      const data = await (await fetch(`/api/recommend?emotion=${encodeURIComponent(id)}&online=${state.onlineOn ? "1" : "0"}&strategy=${encodeURIComponent(state.strategy || "iso")}&fresh=${state.skipPlayed ? "1" : "0"}`)).json();
      if (data.strategy && data.strategy.id) {
        state.strategy = data.strategy.id;
        paintStrategyNow(data.strategy);
      }
      renderSongs(data.songs || [], recsCaption(data));
      if (state.onlineOn && data.online_count === 0) {
        toast("在线曲库暂时没有可播歌曲，已改用本地歌曲。");
      }
      if (id && Array.isArray(data.played_keys)) rememberPlayedKeys(id, data.played_keys);
      if (play) autoPlayList(true);
      return data;
    } catch {
      toast("切换曲库失败，请再试一次。", "err");
      return null;
    }
  }

  function noteOnlinePlayOk() {
    state.onlineFailCount = 0;
    state.onlineFailAt = 0;
  }

  async function fallbackToLocal(reason) {
    if (state.fallbackBusy || !state.onlineOn) return;
    state.fallbackBusy = true;
    clearTimeout(state.playWatch);
    state.onlineOn = false;
    localStorage.setItem("emotune-online", "0");
    const toggle = $("#online-toggle");
    if (toggle) toggle.checked = false;
    toast(reason || "在线歌曲长时间播放失败，已自动切换到本地曲库。", "err");
    try {
      await loadPlaylist(currentEmotionId(), true);
    } finally {
      state.fallbackBusy = false;
      state.onlineFailCount = 0;
      state.onlineFailAt = 0;
    }
  }

  function playlistOnlineStuck() {
    const songs = state.songs || [];
    const online = songs.filter(isOnlineSong);
    if (!online.length) return true;
    const failedOnline = online.filter((s) => state.failed.has(songKey(s)));
    return failedOnline.length >= Math.min(3, online.length) || failedOnline.length === online.length;
  }

  function noteOnlinePlayFail(song) {
    if (!state.onlineOn || !isOnlineSong(song) || state.fallbackBusy) return;
    const now = Date.now();
    if (!state.onlineFailAt) state.onlineFailAt = now;
    state.onlineFailCount += 1;
    const long = now - state.onlineFailAt >= 10000;
    if (state.onlineFailCount >= 3 || (state.onlineFailCount >= 2 && long) || playlistOnlineStuck()) {
      fallbackToLocal("在线歌曲长时间播放失败，已自动切换到本地曲库。");
    }
  }

  function armPlayWatch(song) {
    clearTimeout(state.playWatch);
    if (!isOnlineSong(song) || !state.onlineOn) return;
    state.playWatch = setTimeout(() => {
      if (state.userPaused) return;
      if (!sameAudio(song.audio)) return;
      if (audio.readyState >= 3 && audio.currentTime >= 0.2) return;
      state.failed.add(songKey(song));
      noteOnlinePlayFail(song);
      if (state.onlineOn) playNext();
    }, 8000);
  }

  function firstPlayable(start = 0, dir = 1) {
    const n = state.songs.length;
    if (!n) return -1;
    const from = ((start % n) + n) % n;
    const step = dir < 0 ? -1 : 1;
    for (let k = 0; k < n; k += 1) {
      const i = (from + step * k + n * 8) % n;
      if (isPlayable(state.songs[i])) return i;
    }
    return -1;
  }

  function applyPlayerView() {
    ui.player.classList.toggle("is-lyrics-off", !state.lyricsOn);
    ui.player.classList.toggle("is-cover-off", !state.coverOn);
    ui.player.classList.toggle("is-viz-off", !state.vizOn);
  }

  /* 情绪时间线：每 250ms 记一次此刻情绪与把握度，画最近 60 秒色带 + 曲线 */
  const TIMELINE_MS = 60000;
  function sampleTimeline() {
    const now = Date.now();
    const list = (state.timeline = state.timeline || []);
    const fresh = now - (state.uiEmoAt || 0) < 3000;
    const id = fresh && state.uiEmo && EMO_META[state.uiEmo] && state.uiEmo !== "idle" ? state.uiEmo : "";
    list.push({ t: now, id, p: id ? Number(state.uiEmoProb || 0) : 0 });
    while (list.length && now - list[0].t > TIMELINE_MS + 1000) list.shift();
    drawTimeline();
  }

  function drawTimeline() {
    const canvas = $("#emo-timeline");
    if (!canvas || !canvas.clientWidth) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const w = Math.max(10, Math.round(canvas.clientWidth * dpr));
    const h = Math.max(10, Math.round(canvas.clientHeight * dpr));
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, w, h);
    const list = state.timeline || [];
    const now = Date.now();
    const x = (t) => ((t - (now - TIMELINE_MS)) / TIMELINE_MS) * w;
    const bandTop = h * 0.42;
    const bandH = h * 0.5;
    ctx.fillStyle = "rgba(255,255,255,0.05)";
    ctx.fillRect(0, bandTop, w, bandH);
    for (let i = 0; i < list.length; i += 1) {
      const a = list[i];
      if (!a.id) continue;
      const b = list[i + 1];
      const x0 = Math.max(0, x(a.t));
      const x1 = Math.min(w, b ? x(b.t) : w);
      if (x1 <= x0) continue;
      ctx.fillStyle = EMO_META[a.id].color;
      ctx.globalAlpha = 0.35 + 0.55 * Math.min(1, a.p || 0.5);
      ctx.fillRect(x0, bandTop, x1 - x0 + 0.5, bandH);
    }
    ctx.globalAlpha = 1;
    ctx.beginPath();
    let started = false;
    list.forEach((a) => {
      if (!a.id) {
        started = false;
        return;
      }
      const px = x(a.t);
      const py = bandTop - 4 * dpr - (bandTop - 10 * dpr) * Math.min(1, a.p || 0);
      if (!started) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
      started = true;
    });
    ctx.strokeStyle = "rgba(255,255,255,0.85)";
    ctx.lineWidth = 1.5 * dpr;
    ctx.stroke();
    ctx.font = `700 ${Math.round(11 * dpr)}px "Noto Sans SC","Microsoft YaHei",sans-serif`;
    ctx.textBaseline = "middle";
    let last = "";
    list.forEach((a) => {
      if (a.id && a.id !== last) {
        const px = Math.min(w - 14 * dpr, Math.max(2, x(a.t) + 2));
        ctx.fillStyle = "#0b0c12";
        ctx.fillText(EMO_META[a.id].zh, px + 2 * dpr, bandTop + bandH / 2);
      }
      last = a.id;
    });
  }

  /* 投影大屏：全屏 + 大字 + 只留人脸、此刻情绪、时间线与迷你播放条 */
  function setProjector(on) {
    state.projector = !!on;
    document.body.classList.toggle("is-projector", state.projector);
    const btn = $("#btn-projector");
    if (btn) {
      btn.classList.toggle("is-on", state.projector);
      btn.textContent = state.projector ? "退出投影" : "投影";
    }
    if (state.projector) {
      state.playerModeBeforeProjector = ui.player ? ui.player.dataset.mode : "mini";
      setPlayerMode("mini");
      if (document.documentElement.requestFullscreen && !document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(() => {});
      }
    } else {
      if (state.playerModeBeforeProjector) setPlayerMode(state.playerModeBeforeProjector);
      if (document.fullscreenElement && document.exitFullscreen) document.exitFullscreen().catch(() => {});
    }
    requestAnimationFrame(() => {
      sizeFaceOverlay();
      paintFaceOverlay();
      drawTimeline();
    });
  }

  /* 播放器三档：展开 / 迷你（默认，一行）/ 折叠（右下角小胶囊），记在本机 */
  function setPlayerMode(mode) {
    const next = ["full", "mini", "fold"].includes(mode) ? mode : "mini";
    localStorage.setItem("emotune-player-mode", next);
    if (ui.player) ui.player.dataset.mode = next;
    document.body.dataset.player = next;
    $$("[data-player-mode]").forEach((b) => b.classList.toggle("is-on", b.dataset.playerMode === next));
    if (next === "full") startVizLoop();
  }

  /* 声学分析三档：展开 / 缩小（默认）/ 折叠，记在本机 */
  function setVizSize(size) {
    const next = ["full", "compact", "fold"].includes(size) ? size : "compact";
    localStorage.setItem("emotune-viz-size", next);
    const box = $("#audio-viz");
    if (box) box.dataset.size = next;
    $$("[data-viz-size]").forEach((b) => b.classList.toggle("is-on", b.dataset.vizSize === next));
  }

  function postCamChrome() {
    if (!faceChannel) return;
    try {
      faceChannel.postMessage({
        type: "cam-chrome",
        landmark: state.landmarkMode,
        zoom: state.camZoom,
        fit: state.camFit,
      });
    } catch {
      /* ignore */
    }
  }

  function applyCamView() {
    const vp = $("#viewport");
    const layer = $("#cam-layer");
    document.body.classList.toggle("is-block-fill", !!state.camFill);
    if (vp) {
      vp.classList.toggle("is-fill", !!state.camFill);
      vp.classList.toggle("is-contain", state.camFit === "contain");
      vp.dataset.fit = state.camFit || "cover";
    }
    if (layer) layer.style.setProperty("--cam-zoom", String(state.camZoom || 1));
    const zoomVal = $("#cam-zoom-val");
    if (zoomVal) zoomVal.textContent = `${Math.round((state.camZoom || 1) * 100)}%`;
    const zoomInput = $("#cam-zoom");
    if (zoomInput && Number(zoomInput.value) !== Math.round((state.camZoom || 1) * 100)) {
      zoomInput.value = String(Math.round((state.camZoom || 1) * 100));
    }
    $$("#landmark-picks [data-landmark]").forEach((btn) => {
      const on = btn.dataset.landmark === state.landmarkMode;
      btn.classList.toggle("is-on", on);
      btn.setAttribute("aria-checked", on ? "true" : "false");
    });
    const fillBtn = $("#btn-cam-fill");
    if (fillBtn) {
      fillBtn.classList.toggle("is-on", !state.camFill);
      fillBtn.textContent = state.camFill ? "默认尺寸" : "铺满区块";
    }
    $$("#cam-size-picks [data-cam-size]").forEach((btn) => {
      const on = (btn.dataset.camSize === "fill") === !!state.camFill;
      btn.classList.toggle("is-on", on);
      btn.setAttribute("aria-checked", on ? "true" : "false");
    });
    const zoomChip = $("#cam-zoom-chip");
    if (zoomChip) zoomChip.textContent = `${Math.round((state.camZoom || 1) * 100)}%`;
    const fitBtn = $("#btn-cam-fit");
    if (fitBtn) {
      const cover = state.camFit !== "contain";
      fitBtn.classList.toggle("is-on", cover);
      fitBtn.textContent = cover ? "铺满画面" : "完整画面";
      fitBtn.dataset.fit = state.camFit;
    }
    sizeFaceOverlay();
    paintFaceOverlay();
    requestAnimationFrame(() => {
      sizeFaceOverlay();
      paintFaceOverlay();
      paintPhotoOverlay();
    });
  }

  /* 照片模式：在照片上画人脸框、关键点与表情标签（完整画面，不镜像） */
  function paintPhotoOverlay(data) {
    if (data !== undefined) state.photoData = data;
    const canvas = $("#photo-overlay");
    const img = $("#picked-img");
    if (!canvas || !img) return;
    const host = canvas.parentElement;
    const cssW = img.clientWidth;
    const cssH = img.clientHeight;
    const ctx = canvas.getContext("2d");
    if (!host || cssW < 8 || cssH < 8) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    canvas.width = Math.round(cssW * dpr);
    canvas.height = Math.round(cssH * dpr);
    canvas.style.width = `${cssW}px`;
    canvas.style.height = `${cssH}px`;
    canvas.style.left = `${img.offsetLeft}px`;
    canvas.style.top = `${img.offsetTop}px`;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const d = state.photoData;
    if (!d || !d.ok || state.landmarkMode === "off" || !window.EmoTuneDraw) return;
    const imageSize = (d.face && d.face.image_size) || [img.naturalWidth, img.naturalHeight];
    const sized = { cssW, cssH, dpr };
    const raw = (d.faces && d.faces.length
      ? d.faces
      : d.face && d.face.box
        ? [{ box: d.face.box, primary: true, emotion: d.emotion }]
        : []
    ).filter((f) => f && f.box);
    const mapped = raw
      .map((f) => {
        const box = EmoTuneDraw.mapBox(f.box, imageSize, sized, false, "contain");
        if (!box) return null;
        const srcPts =
          f.points && f.points.length
            ? f.points
            : (f.landmarks || []).map((xy, i) =>
                Object.assign({}, FACE_POINT_FALLBACK[i] || { id: `p${i}`, zh: "点", symbol: `p${i}`, part: "face" }, { x: xy[0], y: xy[1] })
              );
        const points = srcPts
          .map((p) => {
            const xy = EmoTuneDraw.mapPoint([p.x, p.y], imageSize, sized, false, "contain");
            return xy ? Object.assign({}, p, { x: xy.x, y: xy.y }) : null;
          })
          .filter(Boolean);
        return { box, primary: !!f.primary || raw.length === 1, emo: f.emotion || d.emotion || {}, points, cues: f.cues || [] };
      })
      .filter(Boolean);
    if (mapped.length) EmoTuneDraw.paintFaces(ctx, mapped, { mode: state.landmarkMode, canvas });
  }

  function setLandmarkMode(id, persist) {
    const next = LANDMARK_MODES.includes(id) ? id : "overlay";
    state.landmarkMode = next;
    if (persist !== false) localStorage.setItem("emotune-landmark", next);
    applyCamView();
    if (persist) postCamChrome();
  }

  function setCamZoom(value, persist) {
    const n = Number(value);
    state.camZoom = Number.isFinite(n) ? Math.max(0.5, Math.min(2.5, n)) : 1;
    if (persist !== false) localStorage.setItem("emotune-cam-zoom", String(state.camZoom));
    applyCamView();
    if (persist) postCamChrome();
  }

  function setCamFill(on, persist) {
    state.camFill = !!on;
    if (persist !== false) localStorage.setItem("emotune-cam-size", state.camFill ? "fill" : "default");
    applyCamView();
    if (persist) postCamChrome();
  }

  function setCamFit(id, persist) {
    state.camFit = id === "contain" ? "contain" : "cover";
    if (persist !== false) localStorage.setItem("emotune-cam-fit", state.camFit);
    applyCamView();
    if (persist) postCamChrome();
  }

  function bindCamDock() {
    $$("#landmark-picks [data-landmark]").forEach((btn) => {
      btn.addEventListener("click", () => setLandmarkMode(btn.dataset.landmark, true));
    });
    const fillBtn = $("#btn-cam-fill");
    if (fillBtn) fillBtn.addEventListener("click", () => setCamFill(!state.camFill, true));
    $$("#cam-size-picks [data-cam-size]").forEach((btn) => {
      btn.addEventListener("click", () => setCamFill(btn.dataset.camSize === "fill", true));
    });
    const stepZoom = (d) => setCamZoom(Math.round(((state.camZoom || 1) + d) * 20) / 20, true);
    const zin = $("#btn-zoom-in");
    if (zin) zin.addEventListener("click", () => stepZoom(0.1));
    const zout = $("#btn-zoom-out");
    if (zout) zout.addEventListener("click", () => stepZoom(-0.1));
    const zreset = $("#btn-zoom-reset");
    if (zreset) zreset.addEventListener("click", () => setCamZoom(1, true));
    const chip = $("#cam-zoom-chip");
    if (chip) chip.addEventListener("dblclick", () => setCamZoom(1, true));
    const fitBtn = $("#btn-cam-fit");
    if (fitBtn) {
      fitBtn.addEventListener("click", () => setCamFit(state.camFit === "contain" ? "cover" : "contain", true));
    }
    const zoomInput = $("#cam-zoom");
    if (zoomInput) {
      zoomInput.addEventListener("input", () => setCamZoom(Number(zoomInput.value) / 100, true));
    }
    window.addEventListener("resize", () => {
      sizeFaceOverlay();
      paintFaceOverlay();
      paintPhotoOverlay();
    });
  }

  function setSettingsOpen(on) {
    const panel = $("#settings-panel");
    const btn = $("#btn-settings");
    if (!panel) return;
    panel.hidden = !on;
    if (btn) btn.setAttribute("aria-expanded", on ? "true" : "false");
  }

  function paintBoardCounts(trailN, songN) {
    const t = $("#jump-trail-count");
    const s = $("#jump-recs-count");
    if (t && trailN != null) t.textContent = String(trailN);
    if (s && songN != null) s.textContent = String(songN);
  }

  function applyBoardHide() {
    const hideTrail = localStorage.getItem("emotune-hide-trail") === "1";
    const hideRecs = localStorage.getItem("emotune-hide-recs") === "1";
    const trail = $("#trail-panel");
    const recs = $("#recs");
    if (trail) trail.classList.toggle("is-collapsed", hideTrail);
    if (recs) recs.classList.toggle("is-collapsed", hideRecs);
    const bt = $("#btn-hide-trail");
    const br = $("#btn-hide-recs");
    if (bt) {
      bt.textContent = hideTrail ? "展开" : "隐藏";
      bt.setAttribute("aria-expanded", hideTrail ? "false" : "true");
    }
    if (br) {
      br.textContent = hideRecs ? "展开" : "隐藏";
      br.setAttribute("aria-expanded", hideRecs ? "false" : "true");
    }
    $("#jump-trail")?.classList.toggle("is-off", hideTrail);
    $("#jump-recs")?.classList.toggle("is-off", hideRecs);
  }

  function setBoardHide(which, on) {
    const key = which === "trail" ? "emotune-hide-trail" : "emotune-hide-recs";
    localStorage.setItem(key, on ? "1" : "0");
    applyBoardHide();
  }

  function bindChromeUi() {
    const panel = $("#settings-panel");
    const btn = $("#btn-settings");
    const close = $("#btn-close-settings");
    if (btn) {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        setSettingsOpen(panel ? panel.hidden : true);
      });
    }
    if (close) close.addEventListener("click", () => setSettingsOpen(false));
    document.addEventListener("click", (e) => {
      if (!panel || panel.hidden) return;
      if (panel.contains(e.target) || (btn && btn.contains(e.target))) return;
      setSettingsOpen(false);
    });
    const hideTrail = $("#btn-hide-trail");
    const hideRecs = $("#btn-hide-recs");
    if (hideTrail) {
      hideTrail.addEventListener("click", () => {
        const now = localStorage.getItem("emotune-hide-trail") === "1";
        setBoardHide("trail", !now);
      });
    }
    if (hideRecs) {
      hideRecs.addEventListener("click", () => {
        const now = localStorage.getItem("emotune-hide-recs") === "1";
        setBoardHide("recs", !now);
      });
    }
    const jumpTrail = $("#jump-trail");
    const jumpRecs = $("#jump-recs");
    if (jumpTrail) {
      jumpTrail.addEventListener("click", (e) => {
        e.preventDefault();
        if (localStorage.getItem("emotune-hide-trail") === "1") setBoardHide("trail", false);
        $("#trail-panel")?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
    if (jumpRecs) {
      jumpRecs.addEventListener("click", (e) => {
        e.preventDefault();
        if (localStorage.getItem("emotune-hide-recs") === "1") setBoardHide("recs", false);
        $("#recs")?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
    applyBoardHide();
  }

  const VIZ_ALGO = "STFT · Scheirer/Ellis · Krumhansl · Thayer";
  const THAYER_VA = {
    happy: [0.78, 0.7],
    angry: [-0.62, 0.84],
    sad: [-0.72, -0.58],
    fear: [-0.52, 0.58],
    surprise: [0.32, 0.88],
    disgust: [-0.58, 0.12],
    neutral: [0.04, 0.02],
  };

  function renderProbAndVa(scores, currentId) {
    const box = $("#prob-bars");
    const svg = $("#va-map");
    const map = Object.fromEntries((scores || []).map((s) => [s.id, Number(s.prob) || 0]));
    if (box) {
      box.innerHTML = EMO_ORDER.map((id) => {
        const meta = EMO_META[id];
        const p = map[id] || 0;
        const pct = (p * 100).toFixed(1);
        const on = id === currentId ? " is-on" : "";
        return `<div class="prob-row${on}" data-emo="${id}" style="--emo:${meta.color}">
          <b>${meta.name}</b>
          <span class="prob-track"><i class="prob-fill" style="width:${Math.max(0, Math.min(100, p * 100))}%"></i></span>
          <em>${pct}%</em>
        </div>`;
      }).join("");
    }
    if (!svg) return;
    const cx = 110;
    const cy = 110;
    const r = 88;
    const toXY = (va) => [cx + (va[0] || 0) * r, cy - (va[1] || 0) * r];
    let wv = 0;
    let wa = 0;
    let w = 0;
    EMO_ORDER.forEach((id) => {
      const p = map[id] || 0;
      const va = THAYER_VA[id];
      if (!va || p <= 0) return;
      wv += va[0] * p;
      wa += va[1] * p;
      w += p;
    });
    const nowVa = w > 0.04 ? [wv / w, wa / w] : THAYER_VA[currentId] || [0, 0];
    const now = toXY(nowVa);
    const dots = EMO_ORDER.map((id) => {
      const va = THAYER_VA[id];
      const meta = EMO_META[id];
      const [x, y] = toXY(va);
      return `<circle class="va-dot" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="6.2" fill="${meta.color}"/>
        <text class="va-label" x="${(x + 8).toFixed(1)}" y="${(y - 7).toFixed(1)}">${meta.zh}</text>`;
    }).join("");
    svg.innerHTML = `
      <rect x="8" y="8" width="204" height="204" rx="16" fill="none" class="va-axis"/>
      <line class="va-axis" x1="18" y1="${cy}" x2="202" y2="${cy}"/>
      <line class="va-axis" x1="${cx}" y1="18" x2="${cx}" y2="202"/>
      <text class="va-label" x="186" y="104">效价 V+</text>
      <text class="va-label" x="116" y="22">唤醒 A+</text>
      <text class="va-label" x="14" y="104">V−</text>
      <text class="va-label" x="116" y="210">A−</text>
      ${dots}
      <circle class="va-now" cx="${now[0].toFixed(1)}" cy="${now[1].toFixed(1)}" r="7.4"/>
    `;
  }



  function speedWord(bpm) {
    if (bpm < 76) return "缓慢";
    if (bpm < 100) return "从容";
    if (bpm < 120) return "中速";
    if (bpm < 140) return "轻快";
    return "急促";
  }

  function pitchWord(f0) {
    if (f0 < 160) return "低沉";
    if (f0 < 260) return "中音";
    if (f0 < 380) return "偏高";
    return "高亢";
  }

  function ampWord(energy) {
    if (energy < 0.22) return "轻柔";
    if (energy < 0.45) return "适中";
    if (energy < 0.7) return "有力";
    return "强烈";
  }

  function brightWord(centroidHz) {
    if (centroidHz < 800) return "暗淡";
    if (centroidHz < 1800) return "柔和";
    if (centroidHz < 2800) return "明亮";
    return "尖亮";
  }

  function nearestThayer(V, A) {
    let best = "neutral";
    let bestD = 99;
    Object.keys(THAYER_VA).forEach((id) => {
      const pair = THAYER_VA[id];
      const d = (V - pair[0]) * (V - pair[0]) + (A - pair[1]) * (A - pair[1]);
      if (d < bestD) {
        bestD = d;
        best = id;
      }
    });
    return best;
  }

  const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

  function hzToNote(hz) {
    if (!hz || hz < 32) return "—";
    const midi = Math.round(69 + 12 * Math.log2(hz / 440));
    return `${NOTE_NAMES[(midi % 12 + 12) % 12]}${Math.floor(midi / 12) - 1}`;
  }

  function energyDb(rms) {
    return 20 * Math.log10(Math.max(rms, 1e-5));
  }

  function chromaFromFd(fd, binHz) {
    const chroma = new Array(12).fill(0);
    for (let i = 1; i < fd.length; i += 1) {
      const hz = i * binHz;
      if (hz < 70 || hz > 5000) continue;
      const midi = 69 + 12 * Math.log2(hz / 440);
      const pc = ((Math.round(midi) % 12) + 12) % 12;
      chroma[pc] += fd[i] * fd[i];
    }
    const max = Math.max(...chroma, 1);
    return chroma.map((v) => v / max);
  }

  function vaMoodWord(V, A) {
    const v = V >= 0.18 ? "积极" : V <= -0.18 ? "消极" : "平稳";
    const a = A >= 0.28 ? "激昂" : A <= -0.22 ? "低落" : "平静";
    return `${v}·${a}`;
  }

  function energyWordDb(db) {
    if (db < -28) return "轻柔";
    if (db < -18) return "适中";
    if (db < -12) return "澎湃";
    return "强烈";
  }

  function bandWord(hz) {
    if (hz < 180) return "低音区";
    if (hz < 520) return "中音区";
    return "高音区";
  }

  function fluxDensity(env, now) {
    if (!env || env.length < 8) return 0;
    const windowMs = 2000;
    const recent = env.filter((s) => now - s.t <= windowMs);
    if (recent.length < 6) return 0;
    let mean = 0;
    recent.forEach((s) => {
      mean += s.v;
    });
    mean /= recent.length;
    let peaks = 0;
    for (let i = 1; i < recent.length - 1; i += 1) {
      if (recent[i].v > mean * 1.18 && recent[i].v >= recent[i - 1].v && recent[i].v >= recent[i + 1].v) peaks += 1;
    }
    return peaks / (windowMs / 1000);
  }

  function estimateBpmFromPeaks(samples) {
    if (!samples || samples.length < 24) return 0;
    let sum = 0;
    let peak = 0;
    samples.forEach((s) => {
      sum += s.v;
      if (s.v > peak) peak = s.v;
    });
    const mean = sum / samples.length;
    const thr = mean + 0.14 * (peak - mean);
    const peaks = [];
    for (let i = 2; i < samples.length - 2; i += 1) {
      const s = samples[i];
      if (s.v >= thr && s.v >= samples[i - 1].v && s.v >= samples[i + 1].v) {
        if (!peaks.length || s.t - peaks[peaks.length - 1] > 180) peaks.push(s.t);
      }
    }
    if (peaks.length < 3) return 0;
    const iv = [];
    for (let i = 1; i < peaks.length; i += 1) iv.push(peaks[i] - peaks[i - 1]);
    iv.sort((a, b) => a - b);
    const med = iv[Math.floor(iv.length / 2)];
    if (med < 340 || med > 1110) return 0;
    return 60000 / med;
  }

  function sizeVizCanvas(canvas) {
    if (!canvas) return null;
    const cssW = canvas.clientWidth || 320;
    const cssH = canvas.clientHeight || 72;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const w = Math.max(8, Math.round(cssW * dpr));
    const h = Math.max(8, Math.round(cssH * dpr));
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }
    return { w, h, dpr };
  }

  function vizColor() {
    const el = $("#audio-viz");
    if (el) {
      const v = getComputedStyle(el).getPropertyValue("--viz").trim();
      if (v) return v;
    }
    return getComputedStyle(document.body).getPropertyValue("--accent").trim() || "#c4a574";
  }

  function drawCanvasWords(ctx, size, lines, color) {
    if (!lines || !lines.length) return;
    const fontPx = Math.max(10, Math.round(11 * size.dpr));
    ctx.save();
    ctx.font = `600 ${fontPx}px "Noto Sans SC","Microsoft YaHei",sans-serif`;
    ctx.textBaseline = "bottom";
    ctx.fillStyle = color;
    const pad = 6 * size.dpr;
    lines.forEach((line, i) => {
      const y = size.h - pad - (lines.length - 1 - i) * (fontPx + 2);
      ctx.fillText(line, pad, y, size.w - pad * 2);
    });
    ctx.restore();
  }

  function currentSongMusic() {
    const song = state.songs[state.index] || {};
    return song.music && typeof song.music === "object" ? song.music : {};
  }

  function paintVizReadout(feat) {
    const el = $("#viz-readout");
    const panel = $("#audio-viz");
    if (!el) return;
    const analyzing = !!feat.analyzing;
    const emoId = feat.emoId || (analyzing ? "idle" : "neutral");
    if (panel && panel.dataset.emo !== emoId) panel.dataset.emo = emoId;
    const meta = EMO_META[emoId] || EMO_META.neutral;
    const keyName = feat.keyName || "C";
    const cards = [
      {
        k: "速度",
        v: analyzing ? "—" : String(Math.round(feat.bpm)),
        u: "BPM",
        s: analyzing ? "分析中..." : feat.speedWord,
      },
      {
        k: "调性",
        v: analyzing ? "—" : `${keyName} ${feat.modeZh || ""}`.trim(),
        u: "Key",
        s: analyzing ? "" : feat.modeZh === "小调" ? "阴郁" : "明朗",
      },
      {
        k: "音高",
        v: analyzing ? "—" : `${feat.note} ${Math.round(feat.f0)}Hz`,
        u: "f₀",
        s: analyzing ? "" : bandWord(feat.f0),
      },
      {
        k: "能量",
        v: analyzing ? "—" : `${feat.db.toFixed(1)} dB`,
        u: "E",
        s: analyzing ? "" : energyWordDb(feat.db),
      },
      {
        k: "音色",
        v: analyzing ? "—" : `${(feat.centroidHz / 1000).toFixed(2)} kHz`,
        u: "C",
        s: analyzing ? "" : feat.brightWord,
      },
      {
        k: "节奏密度",
        v: analyzing ? "—" : `${feat.density.toFixed(1)} /s`,
        u: "O",
        s: analyzing ? "平稳" : feat.density >= 2.2 ? "律动" : feat.density >= 1 ? "清晰" : "平稳",
      },
      {
        k: "愉悦·唤醒",
        v: analyzing ? "—" : `${feat.V >= 0 ? "+" : ""}${feat.V.toFixed(2)} · ${feat.A >= 0 ? "+" : ""}${feat.A.toFixed(2)}`,
        u: "V · A",
        s: analyzing ? "积极·平静" : vaMoodWord(feat.V, feat.A),
      },
      {
        k: "情绪",
        v: analyzing ? `${meta.zh} · ${meta.name}` : `${meta.zh} · ${meta.name}`,
        u: "同步",
        s: analyzing ? "分析中..." : feat.emoSub || "与人脸、此刻、语音同一标签",
        hot: true,
      },
    ];
    const sig = `${emoId}|${cards.map((c) => c.v + c.s).join("|")}`;
    if (sig === state.vizTextSig) return;
    state.vizTextSig = sig;
    el.innerHTML = cards
      .map(
        (c) =>
          `<article class="viz-metric${c.hot ? " is-hot" : ""}"><em>${esc(c.k)}</em><b>${esc(c.v)}</b><i>${esc(c.u)}</i><span>${esc(c.s)}</span></article>`
      )
      .join("");
  }

  function ensureViz() {
    if (state.analyser) return state.analyser;
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    try {
      state.audioCtx = new AC();
      const src = state.audioCtx.createMediaElementSource(audio);
      state.analyser = state.audioCtx.createAnalyser();
      state.analyser.fftSize = 2048;
      state.analyser.smoothingTimeConstant = 0.72;
      src.connect(state.analyser);
      state.analyser.connect(state.audioCtx.destination);
      return state.analyser;
    } catch {
      return null;
    }
  }

  function drawVizFrame() {
    state.vizRaf = 0;
    const analyser = state.analyser;
    const wave = $("#viz-wave");
    const freq = $("#viz-freq");
    const tempo = $("#viz-tempo");
    const chromaEl = $("#viz-chroma");
    if (!analyser || !wave || !freq || !state.vizOn || (ui.player && ui.player.hidden)) return;
    const td = new Uint8Array(analyser.fftSize);
    analyser.getByteTimeDomainData(td);
    const fd = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(fd);
    const sr = (state.audioCtx && state.audioCtx.sampleRate) || 44100;
    const binHz = sr / analyser.fftSize;
    let rms = 0;
    for (let i = 0; i < td.length; i += 1) {
      const v = (td[i] - 128) / 128;
      rms += v * v;
    }
    rms = Math.sqrt(rms / td.length);
    const energy = clampNum(rms * 2.4, 0, 1);
    let magSum = 0;
    let fSum = 0;
    for (let i = 1; i < fd.length; i += 1) {
      const m = fd[i];
      magSum += m;
      fSum += m * i * binHz;
    }
    const fLo = Math.max(1, Math.floor(80 / binHz));
    const fHi = Math.min(fd.length - 1, Math.floor(500 / binHz));
    let peakI = fLo;
    let peakV = 0;
    for (let i = fLo; i <= fHi; i += 1) {
      if (fd[i] > peakV) {
        peakV = fd[i];
        peakI = i;
      }
    }
    const silent = energy < 0.03 || magSum < 80 || peakV < 10;
    let centroidHz = silent ? state.vizLastC || 0 : magSum > 0 ? fSum / magSum : 0;
    let f0 = silent ? state.vizLastF0 || 0 : peakI * binHz;
    if (!silent) {
      if (state.vizLastF0) f0 = 0.38 * f0 + 0.62 * state.vizLastF0;
      if (state.vizLastC) centroidHz = 0.38 * centroidHz + 0.62 * state.vizLastC;
      state.vizLastF0 = f0;
      state.vizLastC = centroidHz;
    }
    const now = performance.now();
    state.vizEnv.push({ t: now, v: energy });
    if (state.vizEnv.length > 160) state.vizEnv.shift();
    const liveBpm = estimateBpmFromPeaks(state.vizEnv);
    const music = currentSongMusic();
    const priorBpm = Number(music.tempo) || 0;
    let bpm = liveBpm || priorBpm || 96;
    if (liveBpm && priorBpm) bpm = 0.58 * liveBpm + 0.42 * priorBpm;
    if (state.vizBpm) bpm = 0.22 * bpm + 0.78 * state.vizBpm;
    state.vizBpm = bpm;
    const mode = music.mode === "minor" ? "minor" : music.mode === "major" ? "major" : "";
    const modeZh = music.mode_zh || (mode === "minor" ? "小调" : mode === "major" ? "大调" : "调式中");
    const modeSign = mode === "minor" ? -1 : mode === "major" ? 1 : 0;
    const liveA = clampNum(0.7 * (normRange(bpm, 54, 168) * 2 - 1) + 0.3 * (energy * 2 - 1), -1, 1);
    const liveV = clampNum(0.62 * modeSign + 0.38 * (normRange(centroidHz, 200, 3200) * 2 - 1), -1, 1);
    const priorV = Number(music.valence);
    const priorA = Number(music.arousal);
    const V = Number.isFinite(priorV) ? 0.55 * priorV + 0.45 * liveV : liveV;
    const A = Number.isFinite(priorA) ? 0.35 * priorA + 0.65 * liveA : liveA;
    const chroma = chromaFromFd(fd, binHz);
    let keyPc = 0;
    chroma.forEach((v, i) => {
      if (v > chroma[keyPc]) keyPc = i;
    });
    const recEmo = songEmotionId(state.songs[state.index]) || "";
    const thayerEmo = silent ? displayEmotionId() || recEmo || "neutral" : nearestThayer(V, A);
    const emoId = displayEmotionId() || recEmo || (silent ? "idle" : "neutral");
    const recMeta = EMO_META[emoId] || EMO_META.neutral;
    let emoSub = "与人脸、此刻、语音同一标签";
    const feat = {
      energy,
      bpm,
      f0,
      centroidHz,
      V,
      A,
      ampWord: ampWord(energy),
      speedWord: speedWord(bpm),
      pitchWord: pitchWord(f0),
      brightWord: brightWord(centroidHz),
      modeZh,
      emoId,
      recEmo,
      thayerEmo,
      emoSub,
      emoZh: recMeta.zh || "中",
      analyzing: silent,
      note: hzToNote(f0),
      db: energyDb(rms),
      density: fluxDensity(state.vizEnv, now),
      keyName: NOTE_NAMES[keyPc],
      chroma,
    };
    const panel = $("#audio-viz");
    if (panel) panel.dataset.emo = emoId || "idle";
    const color = vizColor();

    const waveSize = sizeVizCanvas(wave);
    const wctx = wave.getContext("2d");
    wctx.clearRect(0, 0, waveSize.w, waveSize.h);
    wctx.strokeStyle = hexToRgba(color, 0.22);
    wctx.lineWidth = 1;
    wctx.beginPath();
    wctx.moveTo(0, waveSize.h / 2);
    wctx.lineTo(waveSize.w, waveSize.h / 2);
    wctx.stroke();
    wctx.beginPath();
    const step = Math.max(1, Math.floor(td.length / waveSize.w));
    const mid = waveSize.h / 2;
    for (let x = 0, i = 0; x < waveSize.w; x += 1, i += step) {
      const v = (td[Math.min(i, td.length - 1)] - 128) / 128;
      const y = mid + v * (waveSize.h * 0.42);
      if (x === 0) wctx.moveTo(x, y);
      else wctx.lineTo(x, y);
    }
    wctx.lineTo(waveSize.w, waveSize.h);
    wctx.lineTo(0, waveSize.h);
    wctx.closePath();
    wctx.fillStyle = hexToRgba(color, 0.16);
    wctx.fill();
    wctx.beginPath();
    for (let x = 0, i = 0; x < waveSize.w; x += 1, i += step) {
      const v = (td[Math.min(i, td.length - 1)] - 128) / 128;
      const y = mid + v * (waveSize.h * 0.42);
      if (x === 0) wctx.moveTo(x, y);
      else wctx.lineTo(x, y);
    }
    wctx.strokeStyle = color;
    wctx.lineWidth = Math.max(1.6, waveSize.dpr * 1.15);
    wctx.stroke();
    drawCanvasWords(wctx, waveSize, [`${feat.ampWord}  RMS=${energy.toFixed(2)}`], color);

    if (tempo) {
      const tSize = sizeVizCanvas(tempo);
      const tctx = tempo.getContext("2d");
      tctx.clearRect(0, 0, tSize.w, tSize.h);
      const env = state.vizEnv;
      if (env.length > 1) {
        const spikeW = Math.max(1.4, tSize.dpr);
        env.forEach((s, i) => {
          const x = (i / Math.max(1, env.length - 1)) * tSize.w;
          const h = s.v * tSize.h * 0.86;
          tctx.fillStyle = hexToRgba(color, 0.35 + s.v * 0.6);
          tctx.fillRect(x, tSize.h - h, spikeW, h);
        });
        let mean = 0;
        env.forEach((s) => {
          mean += s.v;
        });
        mean /= env.length;
        tctx.strokeStyle = hexToRgba(color, 0.28);
        tctx.lineWidth = Math.max(1, tSize.dpr);
        env.forEach((s, i) => {
          if (i < 1 || i >= env.length - 1) return;
          if (s.v > mean * 1.22 && s.v >= env[i - 1].v && s.v >= env[i + 1].v) {
            const x = (i / Math.max(1, env.length - 1)) * tSize.w;
            tctx.beginPath();
            tctx.moveTo(x, 8 * tSize.dpr);
            tctx.lineTo(x, tSize.h - 4 * tSize.dpr);
            tctx.stroke();
          }
        });
      }
    }

    const freqSize = sizeVizCanvas(freq);
    const fctx = freq.getContext("2d");
    fctx.clearRect(0, 0, freqSize.w, freqSize.h);
    const bars = Math.min(72, Math.max(28, Math.floor(freqSize.w / 7)));
    const gap = Math.max(1, Math.round(1.1 * freqSize.dpr));
    const barW = Math.max(2, (freqSize.w - gap * bars) / bars);
    let cBar = 0;
    for (let i = 0; i < bars; i += 1) {
      const lo = Math.floor((i / bars) ** 1.6 * fd.length);
      const hi = Math.max(lo + 1, Math.floor(((i + 1) / bars) ** 1.6 * fd.length));
      let sum = 0;
      for (let k = lo; k < hi && k < fd.length; k += 1) sum += fd[k];
      const mag = sum / Math.max(1, hi - lo) / 255;
      const bh = Math.max(2, mag * freqSize.h * 0.86);
      const x = i * (barW + gap);
      const y = freqSize.h - bh;
      fctx.fillStyle = hexToRgba(color, 0.35 + mag * 0.55);
      fctx.fillRect(x, y, barW, bh);
      const hzMid = ((lo + hi) / 2) * binHz;
      if (Math.abs(hzMid - centroidHz) < Math.abs(((cBar + 0.5) / bars) ** 1.6 * (fd.length * binHz) - centroidHz)) {
        cBar = i;
      }
    }
    const nyquist = binHz * fd.length;
    fctx.fillStyle = hexToRgba(color, 0.55);
    fctx.font = `600 ${Math.round(9 * freqSize.dpr)}px "Noto Sans SC","Microsoft YaHei",sans-serif`;
    fctx.textBaseline = "bottom";
    [100, 1000, 10000].forEach((hz) => {
      if (hz >= nyquist) return;
      const x = Math.pow(clampNum(hz / nyquist, 0, 1), 1 / 1.6) * freqSize.w;
      const label = hz >= 1000 ? `${hz / 1000}k` : String(hz);
      fctx.fillText(label, x + 2 * freqSize.dpr, freqSize.h - 3 * freqSize.dpr);
    });
    if (centroidHz > 0) {
      const t = Math.pow(clampNum(centroidHz / nyquist, 0, 1), 1 / 1.6);
      const cx = t * freqSize.w;
      fctx.strokeStyle = hexToRgba(color, 0.9);
      fctx.setLineDash([4 * freqSize.dpr, 4 * freqSize.dpr]);
      fctx.beginPath();
      fctx.moveTo(cx, 16 * freqSize.dpr);
      fctx.lineTo(cx, freqSize.h);
      fctx.stroke();
      fctx.setLineDash([]);
      fctx.fillStyle = color;
      fctx.font = `600 ${Math.round(10 * freqSize.dpr)}px "Noto Sans SC","Microsoft YaHei",sans-serif`;
      fctx.textBaseline = "alphabetic";
      fctx.fillText(`C=${centroidHz >= 1000 ? (centroidHz / 1000).toFixed(1) + "kHz" : Math.round(centroidHz) + "Hz"}`, cx + 4, 28 * freqSize.dpr);
    }

    if (chromaEl) {
      const cSize = sizeVizCanvas(chromaEl);
      const cctx = chromaEl.getContext("2d");
      cctx.clearRect(0, 0, cSize.w, cSize.h);
      const labels = NOTE_NAMES;
      const padL = 8 * cSize.dpr;
      const padB = 16 * cSize.dpr;
      const slot = (cSize.w - padL * 2) / 12;
      const maxH = cSize.h - padB - 10 * cSize.dpr;
      cctx.font = `600 ${Math.round(9 * cSize.dpr)}px "Noto Sans SC","Microsoft YaHei",sans-serif`;
      cctx.textAlign = "center";
      cctx.textBaseline = "top";
      feat.chroma.forEach((v, i) => {
        const x = padL + i * slot;
        const h = Math.max(2, v * maxH);
        const y = cSize.h - padB - h;
        cctx.fillStyle = hexToRgba(color, i === keyPc ? 0.95 : 0.35 + v * 0.5);
        cctx.fillRect(x + slot * 0.18, y, slot * 0.64, h);
        cctx.fillStyle = i === keyPc ? color : hexToRgba(color, 0.7);
        cctx.fillText(labels[i], x + slot / 2, cSize.h - padB + 2 * cSize.dpr);
      });
    }

    if (now - (state.vizTextAt || 0) > 120) {
      state.vizTextAt = now;
      paintVizReadout(feat);
    }
    if (!audio.paused && !audio.ended && state.vizOn) {
      state.vizRaf = requestAnimationFrame(drawVizFrame);
    }
  }

  function startVizLoop() {
    if (!state.vizOn) return;
    const analyser = ensureViz();
    if (!analyser) return;
    if (state.audioCtx && state.audioCtx.state === "suspended") state.audioCtx.resume().catch(() => {});
    if (!state.vizRaf) state.vizRaf = requestAnimationFrame(drawVizFrame);
  }

  function renderLyric(t) {
    const lines = state.lyricLines || [];
    const prev = $("#lyric-prev");
    const now = $("#lyric-now");
    const next = $("#lyric-next");
    if (!prev || !now || !next) return;
    if (!lines.length) {
      prev.textContent = "";
      now.textContent = "♪";
      next.textContent = "";
      return;
    }
    if (lines.length > 1 && t + 0.25 < Number(lines[0].t)) {
      prev.textContent = "";
      now.textContent = "♪";
      next.textContent = lines[0].text || "";
      return;
    }
    let i = 0;
    for (let k = 0; k < lines.length; k += 1) {
      if (Number(lines[k].t) <= t) i = k;
      else break;
    }
    const cur = lines[i] || {};
    prev.textContent = i > 0 ? lines[i - 1].text || "" : "";
    now.textContent = cur.text || "♪";
    const mini = $("#mini-lyric");
    if (mini) mini.textContent = cur.text || "";
    now.classList.add("is-on");
    next.textContent = i + 1 < lines.length ? lines[i + 1].text || "" : "";
  }

  function lyricDuration(song) {
    /* 切歌时 audio 还是上一首，不能拿上一首的时长去对齐 */
    const d = song && sameAudio(song.audio) ? Number(audio.duration) : 0;
    if (d && isFinite(d) && d > 1) return d;
    const id = (song && song.id) || "";
    if (/^(vocal|itunes|local)-/.test(id)) return 30;
    return 0;
  }

  function lyricBucket(dur) {
    if (dur > 42) return "f";
    if (dur > 1) return "p";
    return "u";
  }

  async function loadLyrics(song) {
    const token = (state.lyricToken += 1);
    const dur = lyricDuration(song);
    const key = `${song.id || ""}|${song.title || ""}|${lyricBucket(dur)}`;
    if (lyricCache.has(key)) {
      state.lyricLines = lyricCache.get(key);
      renderLyric(audio.currentTime || 0);
      return;
    }
    state.lyricLines = [];
    renderLyric(0);
    try {
      const q = new URLSearchParams({
        title: song.title || "",
        artist: song.artist || "",
        duration: String(dur || 0),
      });
      const data = await (await fetch(`/api/lyrics/${encodeURIComponent(song.id || "unknown")}?${q}`)).json();
      if (token !== state.lyricToken) return;
      const lines = (data && data.lines) || [{ t: 0, text: "暂无歌词" }];
      lyricCache.set(key, lines);
      state.lyricLines = lines;
      renderLyric(audio.currentTime || 0);
    } catch {
      if (token !== state.lyricToken) return;
      state.lyricLines = [{ t: 0, text: "暂无歌词" }];
      renderLyric(0);
    }
  }

  function fillPlayer(song) {
    ui.player.hidden = false;
    state.vizEnv = [];
    state.vizBpm = Number((song.music || {}).tempo) || 0;
    state.vizLastF0 = 0;
    state.vizLastC = 0;
    state.vizTextSig = "";
    applyPlayerView();
    const cover = song.cover || "";
    const coverEl = $("#player-cover");
    const nowCover = $("#nowplay-cover");
    coverEl.src = cover;
    coverEl.alt = song.title ? `${prettyText(song.title)} 封面` : "";
    if (nowCover) {
      nowCover.src = cover;
      nowCover.alt = song.title ? `${prettyText(song.title)} 封面` : "正在播放的封面";
    }
    $("#player-title").textContent = prettyText(song.title);
    $("#player-sub").textContent = `${prettyText(song.artist)}${song.album ? " · " + prettyText(song.album) : ""} · 连续播放`;
    paintPlayerEmo(displayEmotionId() || songEmotionId(song));
    const dl = $("#btn-download");
    const open = $("#btn-open");
    if (song.downloadable) {
      dl.hidden = false;
      dl.href = `/api/audio/${song.id}/download`;
    } else dl.hidden = true;
    if (song.external_url) {
      open.hidden = false;
      open.href = song.external_url;
    } else open.hidden = true;
    loadLyrics(song);
  }

  function sameAudio(url) {
    if (!url || !audio.src) return false;
    try {
      return audio.src === new URL(url, location.href).href;
    } catch {
      return audio.src === url;
    }
  }

  function playAt(idx, hops = 0) {
    const n = state.songs.length;
    if (!n || hops > n) {
      if (state.onlineOn && !state.fallbackBusy && playlistOnlineStuck()) {
        fallbackToLocal("在线歌曲长时间播放失败，已自动切换到本地曲库。");
      }
      return;
    }
    const song = state.songs[idx];
    if (!isPlayable(song)) {
      if (hops === 0 && song && !song.audio && song.external_url) {
        toast("这首歌没有可播放音频，已为你打开来源页面。");
        window.open(song.external_url, "_blank");
        return;
      }
      const next = firstPlayable(idx + 1);
      if (next >= 0 && next !== idx) playAt(next, hops + 1);
      return;
    }
    state.index = idx;
    fillPlayer(song);
    markCurrent();
    if (sameAudio(song.audio) && !audio.paused && !audio.ended) return;
    audio.muted = false;
    audio.src = song.audio;
    armPlayWatch(song);
    audio.play().then(() => {
      state.audioUnlocked = true;
      state.autoplayWarned = false;
    }).catch((err) => {
      const name = String((err && err.name) || "");
      if (name === "NotAllowedError") {
        if (!state.autoplayWarned) {
          state.autoplayWarned = true;
          toast("浏览器拦截了自动播放，请点一次播放键。", "err");
        }
        return;
      }
      state.failed.add(songKey(song));
      noteOnlinePlayFail(song);
      if (hops < n) playNext();
    });
  }

  function playNext() {
    const next = firstPlayable(state.index + 1);
    if (next < 0) {
      if (state.onlineOn && playlistOnlineStuck()) {
        fallbackToLocal("在线歌曲长时间播放失败，已自动切换到本地曲库。");
      }
      return;
    }
    playAt(next);
  }

  function syncPlayingHighlight() {
    const idx = state.songs.findIndex((s) => s && s.audio && sameAudio(s.audio));
    if (idx >= 0) {
      state.index = idx;
      markCurrent();
    }
  }

  /* 歌单开头是该情绪的代表曲（小苹果、后来、同桌的你……）：每次认出这个情绪轮到下一首代表曲 */
  function nextPinnedPlayable(emo) {
    const pinned = [];
    const all = state.pinRotate === 0;
    state.songs.forEach((song, i) => {
      if (!song || !isPlayable(song)) return;
      if (all ? true : song.pin && songEmotionId(song) === emo) pinned.push(i);
    });
    if (!pinned.length) return -1;
    if (!all) pinned.splice(state.pinRotate || 3); // 只在前 N 首代表曲之间轮换（设置里可调）
    const store = JSON.parse(localStorage.getItem("emotune-pin-cursor") || "{}");
    const cur = Number(store[emo]) || 0;
    store[emo] = (cur + 1) % pinned.length;
    localStorage.setItem("emotune-pin-cursor", JSON.stringify(store));
    return pinned[cur % pinned.length];
  }

  function firstFreshPlayable() {
    const emo = currentEmotionId();
    const pinnedIdx = nextPinnedPlayable(emo);
    if (pinnedIdx >= 0) return pinnedIdx;
    if (!state.skipPlayed) return firstPlayable(0);
    const played = new Set(state.playedByEmotion[emo] || []);
    const n = state.songs.length;
    for (let i = 0; i < n; i += 1) {
      const song = state.songs[i];
      if (!isPlayable(song)) continue;
      const key = foldTitle(song.title);
      if (!key || !played.has(key)) return i;
    }
    return firstPlayable(0);
  }

  function rememberPlayedKeys(emo, keys) {
    if (!emo) return;
    const local = state.playedByEmotion[emo] || [];
    const next = [];
    const seen = new Set();
    for (const key of [...(keys || []), ...local]) {
      const k = String(key || "");
      if (!k || seen.has(k)) continue;
      seen.add(k);
      next.push(k);
    }
    state.playedByEmotion[emo] = next;
  }

  function withSongEmotion(song, fallbackId) {
    if (!song || songEmotionId(song)) return song;
    if (!fallbackId || !EMO_META[fallbackId] || fallbackId === "idle") return song;
    const meta = EMO_META[fallbackId];
    return Object.assign({}, song, {
      emotion: fallbackId,
      emotion_zh: song.emotion_zh || meta.zh || "",
      emotion_name: song.emotion_name || meta.name || "",
    });
  }

  function footprintSongs(it) {
    const played = Array.isArray(it && it.played) ? it.played : [];
    const recs = Array.isArray(it && it.songs) ? it.songs : [];
    const byKey = new Map();
    for (const song of recs) {
      const key = foldTitle(song && song.title);
      const id = songEmotionId(song);
      if (key && id && !byKey.has(key)) byKey.set(key, id);
    }
    const enrich = (song) => withSongEmotion(song, byKey.get(foldTitle(song && song.title)));
    if (played.length) return uniqueSongs(played.map(enrich).concat(recs.map(enrich)));
    return uniqueSongs(recs.map(enrich));
  }

  function songsLine(it, limit = 3) {
    const songs = footprintSongs(it);
    if (!songs.length) return "";
    const faceId = (it && it.emotion && it.emotion.id) || "";
    const shown = songs.slice(0, limit).map((song) => {
      const title = esc(prettyText(song.title || ""));
      const artist = song.artist ? ` · ${esc(prettyText(song.artist))}` : "";
      return `<span class="trail-song">${songEmoChip(song, faceId)}<strong>${title}</strong><em>${artist}</em></span>`;
    });
    const more = songs.length > limit ? `<span class="more">共 ${songs.length} 首</span>` : "";
    return `<span class="trail-songs">${shown.join("")}${more}</span>`;
  }

  function notePlayed(song) {
    if (!song || state.replayHistory) return;
    const emo = currentEmotionId();
    const key = foldTitle(song.title);
    if (!emo || !key) return;
    const stamp = `${emo}:${key}:${state.historyId || ""}`;
    if (state.lastPlayedStamp === stamp) return;
    state.lastPlayedStamp = stamp;
    const bucket = (state.playedByEmotion[emo] || []).filter((k) => k !== key);
    bucket.push(key);
    state.playedByEmotion[emo] = bucket;
    const it = state.history.find((x) => x.id === state.historyId);
    if (it) {
      const played = Array.isArray(it.played) ? it.played : [];
      if (!played.some((p) => foldTitle(p.title) === key)) {
        it.played = played.concat([song]);
        const box = ui.trail;
        const top = box ? box.scrollTop : 0;
        renderTrail(state.history);
        if (box) box.scrollTop = top;
      }
    }
    fetch("/api/play", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        emotion: emo,
        history_id: state.historyId || "",
        song: {
          id: song.id,
          title: song.title,
          artist: song.artist,
          album: song.album,
          cover: song.cover,
          audio: song.audio,
          source: song.source,
          source_label: song.source_label,
          emotion: songEmotionId(song),
          emotion_zh: song.emotion_zh || (EMO_META[songEmotionId(song)] || {}).zh || "",
          emotion_name: song.emotion_name || (EMO_META[songEmotionId(song)] || {}).name || "",
          key,
        },
      }),
    }).catch(() => {});
  }

  function autoPlayList(force, fromHistory) {
    /* 用户按了暂停 / 停止：识别照常更新歌单，但不再自动出声，直到用户自己点播放 */
    if (state.userPaused) {
      syncPlayingHighlight();
      return;
    }
    const i = fromHistory ? firstPlayable(0) : firstFreshPlayable();
    if (i < 0) {
      if (force) toast("这次没有可自动播放的歌曲。");
      return;
    }
    if (!force && !audio.paused && !isSilentOrEmpty()) {
      syncPlayingHighlight();
      return;
    }
    playAt(i);
  }

  function handleRecognizeData(data, source, t0) {
    if (source === "upload") paintPhotoOverlay(data && data.ok ? data : null);
    const live = isLiveSource(source) || isLiveSource(data && data.source);
    if (!data || !data.ok) {
      if (live) {
        if (state.lockEmotion) updateHoldUi(true);
        return;
      }
      toast((data && data.error) || "识别失败", "err");
      return;
    }
    const rec = data.recommendations || {};
    const emoId = (data.emotion && data.emotion.id) || "";
    const mix = recsCaption(rec);
    if (data.history_id) {
      state.historyId = data.history_id;
      if (data.history_saved !== false) scheduleTrailRefresh(); // 实时同一情绪不新记，就不刷新
    }
    if (emoId && Array.isArray(data.played_keys)) rememberPlayedKeys(emoId, data.played_keys);
    if (data.vote) state.lastVote = data.vote;

    const applyNew = () => {
      state.replayHistory = false;
      if (emoId && EMO_META[emoId]) {
        state.trackEmo = emoId;
        state.trackEmoAt = Date.now();
      }
      showEmotion(data, { speak: !live, commitUi: !live });
      if (live && state.facePopActive) commitLiveUi(data.emotion);
      renderSongs(rec.songs, mix);
      lockPlaylist(emoId);
      autoPlayList(true);
      if (data.online_pending && state.onlineOn) fillOnlineLater(emoId);
      showSwitchReason(emoId, rec);
      startVizLoop();
      if (live && TRANSIENT_EMO[emoId]) {
        const nm = (EMO_META[emoId] || {}).name || "";
        toast(`已锁定「${nm}」反差歌单，脸松开也不会马上换歌；持续平静几秒后会切到平静`);
      }
      if (state.onlineOn && rec.mode === "local-fallback") toast("在线曲库暂时不可用，已改用本地歌曲。");
    };

    if (!live) {
      applyNew();
      const cost = Math.round(data.total_ms || (t0 ? performance.now() - t0 : 0));
      if (state.onlineOn && cost > 3000) toast(`本次总耗时 ${cost} 毫秒，略慢于 3 秒目标。`);
      scheduleTrailRefresh(200);
      return;
    }

    const locked = state.lockEmotion;
    const prob = Number((data.emotion && data.emotion.prob) || 0);
    const bar = liveProbBar(locked, emoId);
    const low = !!(data.emotion && (data.emotion.low_confidence || prob < bar));

    if (emoId) {
      state.liveLatest = state.liveLatest || {};
      state.liveLatest[emoId] = { data, source, at: Date.now() };
    }
    /* 语音刚播报完这个情绪：立刻换歌 */
    if (state.forceApplyEmo) {
      if (Date.now() - (state.forceApplyAt || 0) > 8000) state.forceApplyEmo = "";
      else if (emoId === state.forceApplyEmo) {
        state.forceApplyEmo = "";
        applyNew();
        return;
      }
    }
    /* 语音开着时，换歌统一等播报结束（播报前已有稳定时间），这里只更新画面 */
    const voiceDriven = !!(state.voiceOn && locked && "speechSynthesis" in window);
    const decision = decideLiveAction(locked, emoId, low);

    if (decision.action === "apply") {
      applyNew();
    } else if (decision.action === "same") {
      showEmotion(data, { speak: false, commitUi: false });
      if (state.facePopActive) commitLiveUi(data.emotion);
      else tickUiSpeak(data.emotion);
      updateHoldUi(false);
      syncPlayingHighlight();
    } else if (decision.action === "hold") {
      showFaceCrop(data);
      state.liveGuess = "";
      state.liveGuessCount = 0;
      updateHoldUi(true);
    } else if (decision.action === "pending-neutral") {
      if (state.liveGuess !== "neutral") {
        state.liveGuess = "neutral";
        state.liveGuessCount = 1;
      } else {
        state.liveGuessCount += 1;
      }
      if (state.liveGuessCount >= LIVE_NEUTRAL_HITS && !voiceDriven) applyNew();
      else {
        showFaceCrop(data);
        updateHoldUi(true);
      }
    } else {
      if (state.liveGuess !== emoId) {
        state.liveGuess = emoId;
        state.liveGuessCount = 1;
      } else {
        state.liveGuessCount += 1;
      }
      const need = playlistSwitchNeed(locked, emoId, low);
      if (state.liveGuessCount >= need && !voiceDriven) applyNew();
      else {
        showFaceCrop(data);
        const pending = (EMO_META[emoId] || {}).name || "";
        updateHoldUi(false, pending);
      }
    }
    const cost = Math.round(data.total_ms || (t0 ? performance.now() - t0 : 0));
    if (state.onlineOn && cost > 3000) toast(`本次总耗时 ${cost} 毫秒，略慢于 3 秒目标。`);
  }

  async function recognize(blobs, source) {
    if (state.recognizing) return;
    const files = (Array.isArray(blobs) ? blobs : [blobs]).filter(Boolean);
    if (!files.length) {
      toast("还没有可识别的画面。", "err");
      return;
    }
    state.recognizing = true;
    ui.scan.hidden = false;
    $("#btn-recognize").disabled = true;
    try {
      const fd = new FormData();
      files.forEach((b, i) => fd.append(i === 0 ? "image" : "images", b, `frame${i}.jpg`));
      const t0 = performance.now();
      const res = await fetch(
        "/api/recognize?source=" +
          encodeURIComponent(source) +
          "&online=" +
          (state.onlineOn ? "1" : "0") +
          "&strategy=" +
          encodeURIComponent(state.strategy || "iso") +
          "&mode=" +
          encodeURIComponent(state.faceMode || "solo"),
        {
          method: "POST",
          body: fd,
          headers: faceHeaders({ "X-Emo-Source": source }),
        }
      );
      const data = await res.json();
      handleRecognizeData(data, source, t0);
    } catch (err) {
      toast("网络或服务异常，请确认已启动后端。", "err");
    } finally {
      state.recognizing = false;
      ui.scan.hidden = true;
      $("#btn-recognize").disabled = false;
    }
  }

  async function recognizeNow() {
    unlockAudio();
    if (isLiveMode()) {
      if (state.live) {
        stopLive();
        toast("已关闭实时捕捉，改为识别此刻的截图");
      }
      const ok = await ensureLiveSource();
      if (!ok) return;
      const burst = [];
      for (let i = 0; i < 4; i += 1) {
        const blob = await captureBlob(0.94, 1280);
        if (blob) burst.push(blob);
        if (i < 3) await new Promise((r) => setTimeout(r, 70));
      }
      if (!burst.length) {
        const miss = {
          camera: "还没有画面。请先点「开启摄像头」，看到自己后再识别。",
          video: "还没有画面。请先选择一段本地视频。",
          screen: "还没有画面。请先分享屏幕。",
        };
        toast(miss[state.mode] || "还没有可识别的画面。", "err");
        return;
      }
      await recognize(burst, liveSource());
    } else if (state.lastFile) {
      await recognize(state.lastFile, "upload");
    } else {
      toast("请先选择或拖入一张人脸照片。", "err");
    }
  }

  function useFile(file) {
    if (!file || !file.type.startsWith("image/")) {
      toast("请上传图片文件。", "err");
      return;
    }
    unlockAudio();
    stopLive();
    state.userPaused = false;
    state.lastFile = file;
    showPanel("upload");
    const url = URL.createObjectURL(file);
    const picked = $("#picked");
    const img = $("#picked-img");
    const cap = $("#picked-cap");
    paintPhotoOverlay(null);
    if (img) {
      img.onload = () => paintPhotoOverlay();
      img.src = url;
    }
    if (picked) picked.hidden = false;
    const drop = $("#dropzone");
    if (drop) drop.hidden = true;
    const stage = $("#photo-stage");
    if (stage) {
      stage.classList.add("has-photo");
      if (stage.getBoundingClientRect().top < 0) stage.scrollIntoView({ block: "start", behavior: "smooth" });
    }
    if (cap) cap.textContent = "已选择照片，正在识别…";
    Promise.resolve(recognize(file, "upload")).finally(() => {
      if (cap) cap.textContent = "已选择照片";
    });
  }

  function applyHistoryItem(it) {
    unlockAudio();
    state.userPaused = false;
    state.replayHistory = true;
    state.historyId = it.id || "";
    if (it.emotion) {
      showEmotion(
        {
          emotion: it.emotion,
          elapsed_ms: it.elapsed_ms,
          face: it.face,
          source: it.source,
        },
        { speak: false }
      );
    }
    const songs = footprintSongs(it);
    const n = (it.played || []).length;
    renderSongs(songs, n ? `来自情绪足迹 · 当时听过 ${n} 首` : "来自情绪足迹 · 回放当时的歌");
    $("#history-drawer").hidden = true;
    lockPlaylist((it.emotion && it.emotion.id) || "");
    autoPlayList(true, true);
  }

  /* 足迹时间标签：2026-10-31 08:16:05 */
  function trailTime(ts) {
    const n = Number(ts);
    if (!n) return null;
    const d = new Date(n * 1000);
    const p = (x) => String(x).padStart(2, "0");
    return {
      iso: d.toISOString(),
      text: `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`,
    };
  }

  function trailChipHtml(it) {
    const e = it.emotion || {};
    const id = e.id || "idle";
    const emeta = EMO_META[id] || EMO_META.idle;
    const zh = esc(e.zh || emeta.zh);
    const name = esc(e.name || emeta.name);
    const crop = faceCropSrc(it.face);
    const mirror = isCameraSource(it.source) ? " is-mirror" : "";
    const faceInner = crop
      ? `<img src="${crop}" alt="用于判断${name}的人脸">`
      : `<span class="trail-face-empty">无人脸</span>`;
    const pair = `<span class="trail-pair">
          <span class="trail-col">
            <span class="trail-face${mirror}">${faceInner}</span>
            <span class="trail-col-cap">识别人脸</span>
          </span>
          <span class="trail-col">
            <span class="trail-icon">${faceSvg(id, 96)}</span>
            <span class="trail-col-cap">判断情绪</span>
          </span>
        </span>`;
    const when = trailTime(it.ts);
    return `<button type="button" class="trail-chip has-face" data-id="${esc(it.id)}" data-emo="${esc(id)}" role="listitem">
      ${when ? `<time class="trail-time" datetime="${esc(when.iso)}">${esc(when.text)}</time>` : ""}
      ${pair}
      <b>${zh}</b>
      <span class="trail-name">${name}</span>
      ${songsLine(it)}
    </button>`;
  }

  function paintTrailMeta(n) {
    const meta = $("#trail-meta");
    if (meta) meta.textContent = `已保存 ${n} 次 · 人脸、情绪图标和播过的歌都会留下 · 实时更新 · 点选可回放`;
    paintBoardCounts(n, null);
  }

  function renderTrail(items) {
    if (!ui.trail) return;
    const meta = $("#trail-meta");
    if (!items || !items.length) {
      ui.trail.innerHTML = `<p class="trail-empty">识别几次后，这里会留下人脸、情绪图标和听过的歌。</p>`;
      if (meta) meta.textContent = "全部保存 · 人脸、情绪图标和播过的歌都会留下";
      paintBoardCounts(0, null);
      return;
    }
    paintTrailMeta(items.length);
    ui.trail.innerHTML = items.map(trailChipHtml).join("");
  }

  /* 实时足迹：只拉最新几条，新的插到最前，已有的只替换变化的那张卡片，不用刷新页面 */
  function scheduleTrailRefresh(delay) {
    clearTimeout(state.trailRefreshTimer);
    state.trailRefreshTimer = setTimeout(refreshTrailLive, delay == null ? 800 : delay);
  }

  async function refreshTrailLive() {
    if (!ui.trail || state.trailRefreshBusy) return;
    state.trailRefreshBusy = true;
    try {
      const data = await (await fetch("/api/history?limit=12&played=0")).json();
      const fresh = (data && data.items) || [];
      if (!fresh.length) return;
      const list = state.history || [];
      const byId = new Map(list.map((x, i) => [x.id, i]));
      const added = [];
      fresh.forEach((it) => {
        if (!byId.has(it.id)) {
          added.push(it);
          return;
        }
        const idx = byId.get(it.id);
        const old = list[idx];
        if (JSON.stringify(old.played || []) === JSON.stringify(it.played || [])) return;
        list[idx] = it;
        const chip = ui.trail.querySelector(`.trail-chip[data-id="${CSS.escape(it.id)}"]`);
        if (chip) chip.outerHTML = trailChipHtml(it);
      });
      if (added.length) {
        added.sort((a, b) => Number(b.ts || 0) - Number(a.ts || 0));
        state.history = added.concat(list);
        state.historyTotal = Math.max(Number(data.total) || 0, (state.historyTotal || 0) + added.length);
        const box = $("#history-list");
        if (box) {
          const emptyNote = box.querySelector("p.meta");
          if (emptyNote) emptyNote.remove();
          box.insertAdjacentHTML("afterbegin", added.map(historyItemHtml).join(""));
        }
        const empty = ui.trail.querySelector(".trail-empty");
        if (empty) empty.remove();
        ui.trail.insertAdjacentHTML("afterbegin", added.map(trailChipHtml).join(""));
        added.forEach((it) => {
          const chip = ui.trail.querySelector(`.trail-chip[data-id="${CSS.escape(it.id)}"]`);
          if (chip) chip.classList.add("is-new");
        });
      }
      paintTrailMeta(Math.max(Number(data.total) || 0, state.historyTotal || 0, (state.history || []).length));
    } catch {
      /* 下一次再刷新 */
    } finally {
      state.trailRefreshBusy = false;
    }
  }


  const HISTORY_PAGE = 60;

  function historyItemHtml(it) {
    const e = it.emotion || {};
    const id = e.id || "idle";
    const t = new Date((it.ts || 0) * 1000).toLocaleString("zh-CN", { hour12: false });
    const src = SOURCE_ZH[it.source] || "";
    const ms = it.elapsed_ms ? `${Math.round(it.elapsed_ms)} 毫秒` : "";
    const crop = faceCropSrc(it.face);
    const mirror = isCameraSource(it.source) ? " is-mirror" : "";
    const nm = esc(e.name || (EMO_META[id] || {}).name || "");
    const faceInner = crop
      ? `<img src="${crop}" alt="用于判断${nm}的人脸" loading="lazy">`
      : `<span class="history-face-empty">无人脸</span>`;
    const songs = songsLine(it, 4).replace("trail-songs", "history-songs");
    return `<button type="button" class="history-item has-face" data-id="${esc(it.id)}" data-emo="${esc(id)}">
      <span class="history-pair">
        <span class="history-col">
          <span class="history-face${mirror}">${faceInner}</span>
          <span class="history-col-cap">识别人脸</span>
        </span>
        <span class="history-col">
          <span class="history-icon">${faceSvg(id, 124)}</span>
          <span class="history-col-cap">判断情绪</span>
        </span>
      </span>
      <span class="history-meta">
        <b>${esc(e.zh || "")}</b>${esc(e.name || "")}${src ? " · " + src : ""}
        <span>${esc(t)}${ms ? " · " + ms : ""}</span>
        ${songs}
      </span>
    </button>`;
  }

  function moreButtonHtml() {
    const left = Math.max(0, (state.historyTotal || 0) - (state.history || []).length);
    return left > 0
      ? `<button type="button" class="history-more" data-more="1">加载更早的记录（还有 ${left} 条）</button>`
      : "";
  }

  function paintHistoryLists(items, append) {
    const box = $("#history-list");
    if (!append) {
      renderTrail(items);
      if (box) box.innerHTML = items.length ? items.map(historyItemHtml).join("") : `<p class="meta">还没有记录。</p>`;
    } else {
      if (ui.trail) ui.trail.insertAdjacentHTML("beforeend", items.map(trailChipHtml).join(""));
      if (box) box.insertAdjacentHTML("beforeend", items.map(historyItemHtml).join(""));
    }
    [ui.trail, box].forEach((host) => {
      if (!host) return;
      host.querySelectorAll(".history-more").forEach((b) => b.remove());
      host.insertAdjacentHTML("beforeend", moreButtonHtml());
    });
    paintTrailMeta(state.historyTotal || items.length);
    watchHistoryEnd();
  }

  /* 足迹分页：先拿最新一页（附带已播索引），往下翻再拿更早的 */
  async function loadHistory() {
    try {
      const data = await (await fetch(`/api/history?limit=${HISTORY_PAGE}&offset=0`)).json();
      const items = data.items || [];
      state.history = items;
      state.historyTotal = Number(data.total) || items.length;
      if (data.played && typeof data.played === "object") {
        Object.keys(data.played).forEach((emo) => rememberPlayedKeys(emo, data.played[emo]));
      }
      paintHistoryLists(items, false);
    } catch {
      /* ignore */
    }
  }

  async function loadMoreHistory() {
    if (state.historyLoading) return;
    const have = (state.history || []).length;
    if (have >= (state.historyTotal || 0)) return;
    state.historyLoading = true;
    try {
      const data = await (await fetch(`/api/history?limit=${HISTORY_PAGE}&offset=${have}`)).json();
      const seen = new Set((state.history || []).map((x) => x.id));
      const items = (data.items || []).filter((x) => !seen.has(x.id));
      state.historyTotal = Number(data.total) || state.historyTotal;
      state.history = (state.history || []).concat(items);
      paintHistoryLists(items, true);
    } catch {
      /* 下次再试 */
    } finally {
      state.historyLoading = false;
    }
  }

  function watchHistoryEnd() {
    if (!("IntersectionObserver" in window)) return;
    if (!state.historyObserver) {
      state.historyObserver = new IntersectionObserver((rows) => {
        if (rows.some((r) => r.isIntersecting)) loadMoreHistory();
      }, { rootMargin: "200px" });
    }
    state.historyObserver.disconnect();
    $$(".history-more").forEach((b) => state.historyObserver.observe(b));
  }

  async function loadDemo() {
    try {
      const data = await (await fetch("/api/demo")).json();
      if (!data.items || !data.items.length) return;
      $("#demo-row").hidden = false;
      $("#demo-list").innerHTML = data.items
        .map(
          (it) =>
            `<button type="button" title="${esc(it.file || it.label)}" data-url="${esc(it.url)}" data-id="${esc(it.id)}" data-file="${esc(it.file || it.id + ".jpg")}">
               <img src="${esc(it.url)}" alt="${esc(it.label)}" /><span>${esc(it.label)}</span>
             </button>`
        )
        .join("");
      $$("#demo-list button").forEach((btn) => {
        const pick = async () => {
          if (btn.dataset.busy) return;
          btn.dataset.busy = "1";
          try {
            unlockAudio();
            const blob = await (await fetch(btn.dataset.url)).blob();
            const file = new File([blob], btn.dataset.file || `${btn.dataset.id}.jpg`, { type: blob.type || "image/jpeg" });
            $$("#demo-list button").forEach((b) => b.classList.toggle("is-on", b === btn));
            useFile(file);
          } finally {
            setTimeout(() => delete btn.dataset.busy, 400);
          }
        };
        btn.addEventListener("click", pick);
        btn.addEventListener("dblclick", (e) => {
          e.preventDefault();
          const stage = $("#photo-stage");
          if (stage) stage.scrollIntoView({ block: "start", behavior: "smooth" });
        });
      });
    } catch {
      /* demo 可选 */
    }
  }

  const faceChannel = "BroadcastChannel" in window ? new BroadcastChannel("emotune-face") : null;

  function onFacePopClosed() {
    if (state.facePopWatch) {
      clearInterval(state.facePopWatch);
      state.facePopWatch = 0;
    }
    state.facePop = null;
    state.facePopActive = false;
    const btn = $("#btn-face-pop");
    if (btn) btn.textContent = "弹出人脸窗";
    updateLiveChrome();
    if (state.mode === "camera") startCamera();
  }

  function openFacePop() {
    const live = state.live;
    stopLive();
    stopCameraStream();
    state.facePopActive = true;
    ui.empty.hidden = false;
    setCamHint("人脸检测已移到弹出窗口。关闭人脸窗后可回到本页。");
    const params = new URLSearchParams();
    if (live) params.set("live", "1");
    if (state.faceMode) params.set("mode", state.faceMode);
    if (state.camId) params.set("cam", state.camId);
    const qs = params.toString();
    const url = `/face${qs ? `?${qs}` : ""}`;
    const win = window.open(url, "emotune-face", "popup=yes,width=1024,height=600,left=48,top=48");
    if (!win) {
      state.facePopActive = false;
      toast("浏览器拦住了弹出窗口，请允许本站弹出窗口后再试。", "err");
      return;
    }
    state.facePop = win;
    const btn = $("#btn-face-pop");
    if (btn) btn.textContent = "人脸窗已打开";
    try {
      win.focus();
    } catch {
      /* ignore */
    }
    if (state.facePopWatch) clearInterval(state.facePopWatch);
    state.facePopWatch = setInterval(() => {
      if (!state.facePop || state.facePop.closed) onFacePopClosed();
    }, 700);
    toast(
      state.faceMode === "crowd"
        ? "已弹出人脸窗：当前为多人远场，歌曲按人数最多的情绪来。"
        : "已弹出人脸窗：当前为单人精检，只认近景主脸。"
    );
  }

  if (faceChannel) {
    faceChannel.addEventListener("message", (ev) => {
      const msg = ev.data || {};
      if (msg.type === "hello") {
        state.facePopActive = true;
        stopCameraStream();
        ui.empty.hidden = false;
        setCamHint("人脸检测已移到弹出窗口。关闭人脸窗后可回到本页。");
      } else if (msg.type === "bye") {
        onFacePopClosed();
      } else if (msg.type === "live") {
        if (msg.on) {
          state.live = true;
          syncDetectBtn();
          state.lastSpokenEmo = "";
          hushVoice();
          startHoldTick();
          syncLiveHudDot();
        } else stopLive();
      } else if (msg.type === "track") {
        /* 主画面已让出摄像头，结果在人脸窗里看 */
      } else if (msg.type === "result") {
        handleRecognizeData(msg.data, msg.source || "camera", 0);
      } else if (msg.type === "face-mode" && msg.id) {
        setFaceMode(msg.id, false);
      } else if (msg.type === "cam-chrome") {
        if (msg.landmark) setLandmarkMode(msg.landmark, false);
        if (Number.isFinite(Number(msg.zoom))) setCamZoom(Number(msg.zoom), false);
        if (msg.fit) setCamFit(msg.fit, false);
      }
    });
  }

  function bind() {
    const demoTog = $("#demo-mode-toggle");
    if (demoTog) {
      demoTog.checked = state.demoMode;
      demoTog.addEventListener("change", () => {
        state.demoMode = demoTog.checked;
        localStorage.setItem("emotune-demo-mode", state.demoMode ? "1" : "0");
        syncDemoBadge();
        toast(
          state.demoMode
            ? "已打开课堂演示模式：惊讶更容易认出，喜悦要真的笑开才算，抿嘴微笑算平静。"
            : "已关闭课堂演示模式，恢复标准识别。"
        );
      });
    }
    syncDemoBadge();
    const skipTog = $("#skip-played-toggle");
    if (skipTog) {
      skipTog.checked = state.skipPlayed;
      skipTog.addEventListener("change", () => {
        state.skipPlayed = skipTog.checked;
        localStorage.setItem("emotune-skip-played", state.skipPlayed ? "1" : "0");
        toast(state.skipPlayed ? "已打开排除已播：听过的歌排到后面。" : "已关闭排除已播：按匹配度排，听过的也照常靠前。");
      });
    }
    const rot = $("#pin-rotate");
    if (rot) {
      rot.value = String(state.pinRotate);
      rot.addEventListener("change", () => {
        state.pinRotate = rot.value === "0" ? 0 : Math.max(1, Math.min(6, Number(rot.value) || 3));
        localStorage.setItem("emotune-pin-rotate", String(state.pinRotate));
        localStorage.removeItem("emotune-pin-cursor");
        const label =
          state.pinRotate === 0 ? "歌单全部歌曲轮换" : state.pinRotate === 1 ? "只播第 1 首代表曲" : `前 ${state.pinRotate} 首代表曲轮换`;
        toast(`已改为${label}。`);
      });
    }
    $$("[data-viz-size]").forEach((b) => b.addEventListener("click", () => setVizSize(b.dataset.vizSize)));
    $$("[data-player-mode]").forEach((b) => b.addEventListener("click", () => setPlayerMode(b.dataset.playerMode)));
    const unfold = $("#btn-player-unfold");
    if (unfold) unfold.addEventListener("click", () => setPlayerMode("mini"));
    setPlayerMode(localStorage.getItem("emotune-player-mode") || "mini");
    setInterval(sampleTimeline, 250);
    const projBtn = $("#btn-projector");
    if (projBtn) projBtn.addEventListener("click", () => setProjector(!state.projector));
    document.addEventListener("fullscreenchange", () => {
      if (!document.fullscreenElement && state.projector) setProjector(false);
    });
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && state.projector) setProjector(false);
    });
    setVizSize(localStorage.getItem("emotune-viz-size") || "compact");
    const hintBtn = $("#live-hint-btn");
    const hintBox = $("#live-hint");
    if (hintBtn && hintBox) {
      const show = (on) => hintBox.classList.toggle("is-show", on);
      hintBtn.addEventListener("mouseenter", () => show(true));
      hintBtn.addEventListener("mouseleave", () => show(document.activeElement === hintBtn && hintBtn.matches(":focus-visible")));
      hintBtn.addEventListener("focus", () => show(true));
      hintBtn.addEventListener("blur", () => show(false));
    }
    $$(".tab").forEach((t) => t.addEventListener("click", () => setMode(t.dataset.mode)));
    $("#btn-cam").addEventListener("click", () => {
      unlockAudio();
      startCamera();
    });
    const btnScreen = $("#btn-screen");
    if (btnScreen) {
      btnScreen.addEventListener("click", () => {
        unlockAudio();
        startScreen();
      });
    }
    const videoInput = $("#video-input");
    if (videoInput) {
      videoInput.addEventListener("change", () => {
        const file = videoInput.files && videoInput.files[0];
        if (file) useVideoFile(file);
      });
    }
    const camSelect = $("#cam-select");
    if (camSelect) {
      camSelect.addEventListener("change", async () => {
        const id = camSelect.value || "";
        state.camId = id;
        localStorage.setItem("emotune-cam", id);
        if (state.mode === "camera") {
          stopCameraStream();
          await startCamera();
        }
      });
    }
    $$("#face-mode-picks [data-face-mode]").forEach((btn) => {
      btn.addEventListener("click", () => setFaceMode(btn.dataset.faceMode, true));
    });
    bindCamDock();
    applyCamView();
    if (navigator.mediaDevices && navigator.mediaDevices.addEventListener) {
      navigator.mediaDevices.addEventListener("devicechange", () => {
        listCameras();
      });
    }
    $("#btn-recognize").addEventListener("click", () => {
      state.userPaused = false;
      recognizeNow();
    });
    $("#live-toggle").addEventListener("change", async (e) => {
      if (e.target.checked) {
        unlockAudio();
        state.userPaused = false;
        state.detectOff = false;
        const ok = await ensureLiveSource();
        if (!ok) {
          e.target.checked = false;
          return;
        }
        state.live = true;
        syncDetectBtn();
        state.lastSpokenEmo = "";
        hushVoice();
        startHoldTick();
        updateHoldUi(false);
        syncLiveHudDot();
        toast("实时捕捉已打开：平静、喜悦、悲伤会稳住再换歌；惊讶、恐惧、愤怒、厌恶认到就锁反差歌，松开也不会马上换。");
        if (state.liveTimer) clearInterval(state.liveTimer); // 重复打开时不叠两个计时器
        state.liveTimer = setInterval(async () => {
          if (!isLiveMode() || state.recognizing || !frameReady()) return;
          const blob = await captureBlob(0.9, 720);
          if (blob) recognize(blob, liveSource());
        }, LIVE_TICK_MS);
      } else stopLive();
    });

    const historyBox = $("#history-list");
    [ui.trail, historyBox].forEach((host) => {
      if (!host) return;
      host.addEventListener("click", (e) => {
        if (e.target.closest(".history-more")) {
          loadMoreHistory();
          return;
        }
        const item = e.target.closest(".history-item");
        if (!item) return;
        const it = (state.history || []).find((x) => x.id === item.dataset.id);
        if (it) applyHistoryItem(it);
      });
    });
    if (ui.trail) {
      ui.trail.addEventListener("click", (e) => {
        const btn = e.target.closest(".trail-chip");
        if (!btn) return;
        const it = (state.history || []).find((x) => x.id === btn.dataset.id);
        if (it) applyHistoryItem(it);
      });
    }
    ui.file.addEventListener("change", () => {
      const f = ui.file.files[0];
      if (f) useFile(f);
      ui.file.value = "";
    });
    ["dragenter", "dragover"].forEach((ev) =>
      ui.drop.addEventListener(ev, (e) => {
        e.preventDefault();
        ui.drop.classList.add("over");
      })
    );
    ["dragleave", "drop"].forEach((ev) =>
      ui.drop.addEventListener(ev, (e) => {
        e.preventDefault();
        ui.drop.classList.remove("over");
      })
    );
    ui.drop.addEventListener("drop", (e) => useFile(e.dataTransfer.files[0]));
    const pickedImg = $("#picked-img");
    if (pickedImg) {
      pickedImg.addEventListener("dblclick", () => {
        if (state.lastFile) recognize(state.lastFile, "upload");
      });
    }

    ui.songs.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-play]");
      const card = e.target.closest(".song");
      if (btn || card) state.userPaused = false;
      if (btn) playAt(Number(btn.dataset.play));
      else if (card) playAt(Number(card.dataset.idx));
    });

    $("#btn-play").addEventListener("click", () => {
      unlockAudio();
      if (isSilentOrEmpty()) {
        const i = firstPlayable(state.index);
        if (i >= 0) playAt(i);
        return;
      }
      if (audio.paused) {
        state.userPaused = false;
        audio.play().catch(() => toast("请再点一次播放。", "err"));
      } else {
        state.userPaused = true;
        audio.pause();
      }
    });
    $("#btn-stop").addEventListener("click", () => {
      state.userPaused = true;
      clearTimeout(state.playWatch);
      audio.pause();
      setDetect(false);
      toast("已停止播放并关闭实时检测。点 ▶ 继续听歌，点顶栏「实时检测」恢复识别。");
    });
    $("#btn-detect").addEventListener("click", () => {
      const on = !!state.live && !state.detectOff;
      setDetect(!on);
      if (on) toast("已关闭实时检测：不再识别表情、不画人脸框。需要时点「识别此刻」或重新打开。");
    });
    $("#btn-prev").addEventListener("click", () => {
      const n = state.songs.length;
      if (!n) return;
      const prev = firstPlayable(state.index - 1, -1);
      state.userPaused = false;
      if (prev >= 0) playAt(prev);
    });
    $("#btn-next").addEventListener("click", () => {
      state.userPaused = false;
      playNext();
    });
    audio.addEventListener("play", () => {
      ui.player.classList.add("is-playing");
      $("#btn-play").textContent = "❚❚";
      startVizLoop();
    });
    audio.addEventListener("pause", () => {
      ui.player.classList.remove("is-playing");
      $("#btn-play").textContent = "▶";
    });
    audio.addEventListener("ended", () => {
      if (isSilentOrEmpty()) return;
      playNext();
    });
    audio.addEventListener("playing", () => {
      clearTimeout(state.playWatch);
      const song = state.songs[state.index];
      if (isOnlineSong(song)) noteOnlinePlayOk();
      notePlayed(song);
      scheduleTrailRefresh(1500);
    });
    audio.addEventListener("error", () => {
      if (isSilentOrEmpty()) return;
      const song = state.songs[state.index];
      if (song) state.failed.add(songKey(song));
      noteOnlinePlayFail(song);
      playNext();
    });
    audio.addEventListener("loadedmetadata", () => {
      const song = state.songs[state.index];
      if (song) loadLyrics(song);
    });
    audio.addEventListener("timeupdate", () => {
      if (state.lyricsOn) renderLyric(audio.currentTime || 0);
      if (!audio.duration) return;
      ui.seek.value = Math.round((audio.currentTime / audio.duration) * 1000);
      $("#time").textContent = `${fmt(audio.currentTime)} / ${fmt(audio.duration)}`;
    });
    ui.seek.addEventListener("input", () => {
      if (audio.duration) audio.currentTime = (ui.seek.value / 1000) * audio.duration;
      if (state.lyricsOn) renderLyric(audio.currentTime || 0);
    });
    ui.vol.value = audio.volume;
    ui.vol.addEventListener("input", () => {
      if (!state.ducking) audio.volume = Number(ui.vol.value);
      localStorage.setItem("emotune-vol", ui.vol.value);
    });

    $("#btn-history").addEventListener("click", () => {
      $("#history-drawer").hidden = !$("#history-drawer").hidden;
      if (!state.history) loadHistory();
    });
    $("#btn-close-history").addEventListener("click", () => ($("#history-drawer").hidden = true));
    $("#btn-clear-history").addEventListener("click", async () => {
      await fetch("/api/history", { method: "DELETE" });
      loadHistory();
    });
    const onlineToggle = $("#online-toggle");
    if (onlineToggle) {
      onlineToggle.checked = state.onlineOn;
      onlineToggle.addEventListener("change", async () => {
        state.onlineOn = onlineToggle.checked;
        localStorage.setItem("emotune-online", state.onlineOn ? "1" : "0");
        state.onlineFailCount = 0;
        state.onlineFailAt = 0;
        toast(state.onlineOn ? "已改用在线热歌，识别后优先播在线接口。" : "已改用本地曲库，断网也能听。");
        if (state.lastEmotion || state.lockEmotion) await loadPlaylist(currentEmotionId(), true);
      });
    }
    const lyricsToggle = $("#lyrics-toggle");
    if (lyricsToggle) {
      lyricsToggle.checked = state.lyricsOn;
      lyricsToggle.addEventListener("change", () => {
        state.lyricsOn = lyricsToggle.checked;
        localStorage.setItem("emotune-lyrics", state.lyricsOn ? "1" : "0");
        applyPlayerView();
        if (state.lyricsOn) renderLyric(audio.currentTime || 0);
        toast(state.lyricsOn ? "歌词已打开，播放时会随进度显示。" : "歌词已关闭。");
      });
    }
    const coverToggle = $("#cover-toggle");
    if (coverToggle) {
      coverToggle.checked = state.coverOn;
      coverToggle.addEventListener("change", () => {
        state.coverOn = coverToggle.checked;
        localStorage.setItem("emotune-cover", state.coverOn ? "1" : "0");
        applyPlayerView();
        toast(state.coverOn ? "封面已打开，播放时会显示歌曲封面。" : "封面已关闭。");
      });
    }
    const vizToggle = $("#viz-toggle");
    if (vizToggle) {
      vizToggle.checked = state.vizOn;
      vizToggle.addEventListener("change", () => {
        state.vizOn = vizToggle.checked;
        localStorage.setItem("emotune-viz", state.vizOn ? "1" : "0");
        applyPlayerView();
        if (state.vizOn) {
          startVizLoop();
          toast("波形已打开，播放时显示实时波形和频率。");
        } else toast("波形已关闭。");
      });
    }
    const btnFacePop = $("#btn-face-pop");
    if (btnFacePop) {
      btnFacePop.addEventListener("click", () => {
        if (state.facePop && !state.facePop.closed) {
          try {
            state.facePop.focus();
          } catch {
            /* ignore */
          }
          return;
        }
        openFacePop();
      });
    }
    applyPlayerView();
    const voiceToggle = $("#voice-toggle");
    if (voiceToggle) {
      if (!("speechSynthesis" in window)) {
        state.voiceOn = false;
        voiceToggle.checked = false;
        voiceToggle.disabled = true;
        voiceToggle.parentElement.title = "当前浏览器不支持语音提示";
      }
      voiceToggle.checked = state.voiceOn;
      voiceToggle.addEventListener("change", () => {
        state.voiceOn = voiceToggle.checked;
        localStorage.setItem("emotune-voice", state.voiceOn ? "1" : "0");
        if (!state.voiceOn) {
          hushVoice();
          toast("语音提示已关闭");
          return;
        }
        if (!("speechSynthesis" in window)) {
          voiceToggle.checked = false;
          state.voiceOn = false;
          toast("当前浏览器不支持语音提示。", "err");
          return;
        }
        unlockSpeech();
        const ok = speakText("语音提示已打开");
        toast(ok ? "语音提示已打开。平静喜悦悲伤稳住约 3 秒说；惊讶恐惧愤怒厌恶认到后很快说；识别此刻或上传立刻说。" : "语音提示已打开。");
      });
    }
    if ("speechSynthesis" in window) {
      refreshZhVoice();
      try {
        window.speechSynthesis.cancel();
      } catch {
        /* ignore */
      }
      window.speechSynthesis.addEventListener("voiceschanged", refreshZhVoice);
    }

    $$(".theme-pick").forEach((btn) => {
      btn.setAttribute("role", "radio");
      btn.addEventListener("click", () => applyTheme(btn.dataset.theme, true));
    });
    $("#btn-about").addEventListener("click", () => $("#about-dialog").showModal());
    $("#btn-close-about").addEventListener("click", () => $("#about-dialog").close());
    bindStrategyPicks();
    bindChromeUi();

    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        setSettingsOpen(false);
      }
      if (e.code === "Space" && e.target === document.body) {
        e.preventDefault();
        recognizeNow();
      }
    });
  }

  async function boot() {
    showIdle();
    renderSongs([]);
    bind();
    applyTheme(state.theme, false);
    paintFaceMode();
    updateLiveChrome();
    listCameras();
    try {
      const prefs = await (await fetch("/api/prefs")).json();
      if (prefs && prefs.theme) applyTheme(prefs.theme, false);
      if (prefs && prefs.strategy) setStrategy(prefs.strategy, false, false);
      if (prefs && prefs.face_mode) setFaceMode(prefs.face_mode, false);
    } catch {
      /* 主题可只用本机记忆 */
    }
    loadDemo();
    loadHistory();
    loadStrategies();
    try {
      const health = await (await fetch("/api/health")).json();
      if (!health.ok) toast("服务未就绪", "err");
      else if (!health.models.yunet || !health.models.fer) toast("本地模型文件缺失，请查看运行说明。", "err");
      else if (health.offline_ready) {
        const n = health.local_songs || 0;
        const hint = $("#stage-hint");
        if (hint) hint.textContent = `本机模型已就绪，本地曲库 ${n} 首。没有网络也能识别和播放。算法与理论见「说明」。摄像头请用 http://127.0.0.1:5000 打开。`;
      }
    } catch {
      toast("后端未连接。请先启动本机服务。", "err");
    }
    if (!isCameraSecure()) {
      setCamHint("当前地址不能使用摄像头。请用 http://127.0.0.1:5000 打开本页，不要用局域网 IP。");
    }
  }

  window.__emotune = {
    decideLiveAction,
    isLiveSource,
    handleRecognizeData,
    commitLiveUi,
    tickUiSpeak,
    displayEmotionId,
    speakDwellMs,
    uiSwitchNeed,
    playlistSwitchNeed,
    setLiveForTest: (on) => {
      state.live = !!on;
    },
    transient: TRANSIENT_EMO,
    holdMs: EMO_HOLD_MS,
    setLockForTest: (id, ageMs) => {
      state.lockEmotion = id || "";
      state.lockAt = id ? Date.now() - Math.max(0, Number(ageMs) || 0) : 0;
    },
    setSpeakForTest: (id, ageMs, hits) => {
      state.speakPending = id || state.uiEmo || "";
      state.speakSince = Date.now() - Math.max(0, Number(ageMs) || 0);
      state.speakHits = Number(hits) || 0;
    },
    setTrackForTest: (id) => {
      state.trackEmo = id || "";
      state.trackEmoAt = id ? Date.now() : 0;
    },
    setUiGuessForTest: (id, ageMs, hits) => {
      state.uiGuess = id || "";
      state.uiGuessAt = Date.now() - Math.max(0, Number(ageMs) || 0);
      state.uiGuessHits = Number(hits) || 0;
    },
    resetUiForTest: () => {
      cancelSpeech();
      state.uiEmo = "";
      state.uiGuess = "";
      state.uiGuessHits = 0;
      state.uiGuessAt = 0;
      state.lastSpokenEmo = "";
      state.lastSpokenAt = 0;
      state.speakPending = "";
      state.speakHits = 0;
      state.speakSince = 0;
      state.trackEmo = "";
      state.trackEmoAt = 0;
    },
    emoHex,
    getState: () => ({
      lock: state.lockEmotion,
      relaxed: state.holdRelaxed,
      guess: state.liveGuess,
      guessCount: state.liveGuessCount,
      live: state.live,
      titles: state.songs.map((s) => s.title),
      overlay: state.lastOverlay,
      uiEmo: state.uiEmo,
      trackEmo: state.trackEmo,
      vote: state.lastVote,
      facePop: state.facePopActive,
      vizOn: state.vizOn,
      strategy: state.strategy,
      lastSpoken: state.lastSpokenEmo,
      speakPending: state.speakPending,
      speakHits: state.speakHits,
      voiceOn: state.voiceOn,
      onlineOn: state.onlineOn,
      historyId: state.historyId,
      trailCount: (state.history || []).length,
      replayHistory: state.replayHistory,
      played: state.playedByEmotion,
      faceMode: state.faceMode,
      landmarkMode: state.landmarkMode,
      camZoom: state.camZoom,
      camFill: state.camFill,
      camFit: state.camFit,
      mode: state.mode,
    }),
    fallbackToLocal,
    stopLive,
  };

  boot();
})();
