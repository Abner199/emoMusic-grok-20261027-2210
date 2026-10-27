(() => {
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  const EMO_ORDER = ["happy", "angry", "sad", "fear", "surprise", "disgust", "neutral"];
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
  const EMO_HEX = Object.fromEntries(Object.keys(EMO_META).map((k) => [k, EMO_META[k].color]));
  const SOURCE_ZH = {
    upload: "上传照片",
    camera: "摄像头",
    "camera-live": "实时捕捉",
  };
  const TRAD =
    "愛後為國樂發時長門開東風雲點實現與無這個們來對會體醜強獨戰鐘煙湧陰貓樹傑銘謙飛兒鄧陳趙歲戀聽記過錯氣龍捲義術單簡當從業書華語經總應該說讓給還進運關問題歡熱陽離獸團傳蘭齊劉買綱願乾燦爛態戲劇觀覺優傷殤俠雙盧樸馮靜倫誇闆裡麼線將畫憶懷邊條孫隻隻臺蘋麼麼聲帶專輯場錄選數賜碼銀鏡際內寫讀請區灣標準寶貝頁頭題顏館廣廳響處歷據產權號級類組員並確滿漢彙視藝職網質價電務間葉滾搖見絲詩迴蕭驚顫慄溫學認島黃嘆髮孃煉園遊盤騎亂羅曖榮詞話親變萬遠換擇證驗聯習鳳車馬魚錢賣鬆麵廠鐵億儀慶禮節責曆絡織閉係裏詠曉鴻穎聰艷偉麗鵬濤潔純紅機軍殺謝鋒殘竅極誘計動軌跡約橋興嗎雞嵐張妳瑋議の層樓寶暢";
  const SIMP =
    "爱后为国乐发时长门开东风云点实现与无这个们来对会体丑强独战钟烟涌阴猫树杰铭谦飞儿邓陈赵岁恋听记过错气龙卷义术单简当从业书华语经总应该说让给还进运关问题欢热阳离兽团传兰齐刘买纲愿干灿烂态戏剧观觉优伤殇侠双卢朴冯静伦夸板里么线将画忆怀边条孙只只台苹么么声带专辑场录选数赐码银镜际内写读请区湾标准宝贝页头题颜馆广厅响处历据产权号级类组员并确满汉汇视艺职网质价电务间叶滚摇见丝诗回萧惊颤栗温学认岛黄叹发娘炼园游盘骑乱罗暧荣词话亲变万远换择证验联习凤车马鱼钱卖松面厂铁亿仪庆礼节责历络织闭系里咏晓鸿颖聪艳伟丽鹏涛洁纯红机军杀谢锋残窍极诱计动轨迹约桥兴吗鸡岚张你玮议之层楼宝畅";
  const TRAD_MAP = (() => {
    const map = Object.create(null);
    for (let i = 0; i < TRAD.length; i += 1) map[TRAD[i]] = SIMP[i];
    return map;
  })();

  function prettyText(text) {
    let t = String(text || "")
      .replace(/[^\u0000-\u007F]/g, (ch) => TRAD_MAP[ch] || ch)
      .trim();
    if (!t) return "";
    t = t.replace(/\s*[-–—]\s*Single\b/gi, " - 单曲");
    t = t.replace(/\(\s*Single\s*\)/gi, "(单曲)");
    t = t.replace(/\s*[-–—]\s*EP\s*$/i, " - 迷你专辑");
    t = t.replace(/\s*[-–—]\s*Album\s*$/i, " - 专辑");
    t = t.replace(/\(\s*Live\s*\)/gi, "(现场)");
    t = t.replace(/(第\d+期)Live/gi, "$1现场");
    t = t.replace(/\(\s*Hong Kong Version\s*\)/gi, "(香港版)");
    t = t.replace(/\bVersion\b/g, "版");
    t = t.replace(/iTunes/g, "苹果音乐");
    t = t.replace(/Deezer/g, "国际曲库");
    return t;
  }

  const FACE = {
    idle: `
      <circle cx="50" cy="50" r="42" fill="currentColor" opacity=".1"/>
      <circle cx="32" cy="42" r="6.4" fill="currentColor"/>
      <circle cx="68" cy="42" r="6.4" fill="currentColor"/>
      <path d="M26 70h48" stroke="currentColor" stroke-width="6" stroke-linecap="round"/>`,
    happy: `
      <circle cx="50" cy="50" r="42" fill="currentColor" opacity=".14"/>
      <path d="M10 50c12-30 30-30 36 8" stroke="currentColor" stroke-width="8" stroke-linecap="round"/>
      <path d="M54 50c12-30 30-30 36 8" stroke="currentColor" stroke-width="8" stroke-linecap="round"/>
      <path d="M10 56c12 40 68 40 80 0" stroke="currentColor" stroke-width="8" stroke-linecap="round"/>
      <path d="M20 64c10 28 50 28 60 0" fill="currentColor" opacity=".32"/>
      <ellipse cx="12" cy="66" rx="12" ry="8" fill="currentColor" opacity=".48"/>
      <ellipse cx="88" cy="66" rx="12" ry="8" fill="currentColor" opacity=".48"/>`,
    angry: `
      <circle cx="50" cy="50" r="42" fill="currentColor" opacity=".16"/>
      <path d="M4 12l46 36" stroke="currentColor" stroke-width="9" stroke-linecap="round"/>
      <path d="M96 12l-46 36" stroke="currentColor" stroke-width="9" stroke-linecap="round"/>
      <ellipse cx="30" cy="58" rx="12" ry="8" fill="currentColor"/>
      <ellipse cx="70" cy="58" rx="12" ry="8" fill="currentColor"/>
      <circle cx="35" cy="55" r="3" fill="#fff" opacity=".92"/>
      <circle cx="75" cy="55" r="3" fill="#fff" opacity=".92"/>
      <path d="M16 76l10-20 8 18 8-18 8 18 8-18 10 20" stroke="currentColor" stroke-width="6.4" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="M10 8c2-12 14-12 14 2M76 8c2-12 14-12 14 2" stroke="currentColor" stroke-width="3.6" stroke-linecap="round" opacity=".8"/>`,
    sad: `
      <circle cx="50" cy="50" r="42" fill="currentColor" opacity=".12"/>
      <path d="M8 20c20-16 34 4 36 24" stroke="currentColor" stroke-width="7" stroke-linecap="round"/>
      <path d="M92 20c-20-16-34 4-36 24" stroke="currentColor" stroke-width="7" stroke-linecap="round"/>
      <ellipse cx="32" cy="56" rx="9" ry="11" fill="currentColor"/>
      <ellipse cx="68" cy="56" rx="9" ry="11" fill="currentColor"/>
      <path d="M16 88c16-34 52-34 68 0" stroke="currentColor" stroke-width="7.2" stroke-linecap="round"/>
      <path d="M16 62c-5 18 2 30 14 34" stroke="currentColor" stroke-width="5" stroke-linecap="round"/>
      <ellipse cx="12" cy="94" rx="7" ry="9" fill="currentColor"/>
      <circle cx="88" cy="74" r="4.6" fill="currentColor" opacity=".8"/>`,
    fear: `
      <circle cx="50" cy="50" r="42" fill="currentColor" opacity=".12"/>
      <path d="M8 12c18-6 32 10 34 28" stroke="currentColor" stroke-width="6.4" stroke-linecap="round"/>
      <path d="M92 12c-18-6-32 10-34 28" stroke="currentColor" stroke-width="6.4" stroke-linecap="round"/>
      <ellipse cx="32" cy="50" rx="17" ry="21" stroke="currentColor" stroke-width="5" fill="currentColor" fill-opacity=".08"/>
      <ellipse cx="68" cy="50" rx="17" ry="21" stroke="currentColor" stroke-width="5" fill="currentColor" fill-opacity=".08"/>
      <circle cx="32" cy="58" r="4.6" fill="currentColor"/>
      <circle cx="68" cy="58" r="4.6" fill="currentColor"/>
      <path d="M28 80c6 14 12-14 16 0s12-14 16 0 12-14 16 0" stroke="currentColor" stroke-width="5.6" stroke-linecap="round"/>
      <ellipse cx="92" cy="42" rx="6" ry="10" fill="currentColor" opacity=".88"/>
      <ellipse cx="8" cy="48" rx="4" ry="7" fill="currentColor" opacity=".7"/>`,
    surprise: `
      <circle cx="50" cy="50" r="42" fill="currentColor" opacity=".12"/>
      <path d="M6 10h30" stroke="currentColor" stroke-width="8" stroke-linecap="round"/>
      <path d="M64 10h30" stroke="currentColor" stroke-width="8" stroke-linecap="round"/>
      <circle cx="32" cy="38" r="18" stroke="currentColor" stroke-width="5.4"/>
      <circle cx="68" cy="38" r="18" stroke="currentColor" stroke-width="5.4"/>
      <circle cx="32" cy="38" r="7" fill="currentColor"/>
      <circle cx="68" cy="38" r="7" fill="currentColor"/>
      <ellipse cx="50" cy="82" rx="18" ry="16" stroke="currentColor" stroke-width="6"/>`,
    disgust: `
      <circle cx="50" cy="50" r="42" fill="currentColor" opacity=".14"/>
      <path d="M6 22c22-14 38 8 40 20" stroke="currentColor" stroke-width="7" stroke-linecap="round"/>
      <path d="M94 10c-16 16-26 32-30 40" stroke="currentColor" stroke-width="7" stroke-linecap="round"/>
      <path d="M12 50h26" stroke="currentColor" stroke-width="7.2" stroke-linecap="round"/>
      <path d="M54 60h28" stroke="currentColor" stroke-width="7.2" stroke-linecap="round"/>
      <path d="M38 40c3 12 12 16 18 6" stroke="currentColor" stroke-width="4.6" stroke-linecap="round"/>
      <path d="M18 70c12-18 24-8 32 2 18 12 30-10 34-20" stroke="currentColor" stroke-width="6.4" stroke-linecap="round"/>
      <path d="M42 74c10 20 24 22 32 4" stroke="currentColor" stroke-width="6" stroke-linecap="round" fill="currentColor" fill-opacity=".3"/>`,
    neutral: `
      <circle cx="50" cy="50" r="42" fill="currentColor" opacity=".1"/>
      <path d="M14 44h26" stroke="currentColor" stroke-width="8" stroke-linecap="round"/>
      <path d="M60 44h26" stroke="currentColor" stroke-width="8" stroke-linecap="round"/>
      <path d="M28 72h44" stroke="currentColor" stroke-width="6.2" stroke-linecap="round"/>`,
  };

  const state = {
    mode: "camera",
    stream: null,
    live: false,
    liveTimer: 0,
    trackTimer: 0,
    trackOn: false,
    trackBusy: false,
    overlaySmooth: null,
    lastOverlay: { id: "idle", color: "#c4a574" },
    recognizing: false,
    camBusy: false,
    songs: [],
    index: 0,
    lastFile: null,
    audioUnlocked: false,
    autoplayWarned: false,
    lastEmotion: "",
    lockEmotion: "",
    lockAt: 0,
    holdRelaxed: false,
    holdTick: 0,
    liveGuess: "",
    liveGuessCount: 0,
    failed: new Set(),
    history: [],
    historyId: "",
    playedByEmotion: {},
    lastPlayedStamp: "",
    replayHistory: false,
    voiceOn: localStorage.getItem("emotune-voice") !== "0",
    onlineOn: localStorage.getItem("emotune-online") !== "0",
    onlineFailCount: 0,
    onlineFailAt: 0,
    fallbackBusy: false,
    playWatch: 0,
    lyricsOn: localStorage.getItem("emotune-lyrics") !== "0",
    coverOn: localStorage.getItem("emotune-cover") !== "0",
    theme: localStorage.getItem("emotune-theme") || "night",
    lyricLines: [],
    lyricToken: 0,
    ducking: false,
    zhVoice: null,
  };
  const lyricCache = new Map();
  const THEMES = ["night", "paper", "ink", "rouge", "celadon", "moon"];

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

  const audio = new Audio();
  audio.preload = "auto";
  audio.playsInline = true;
  audio.setAttribute("playsinline", "true");
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

  function speakText(text) {
    if (!state.voiceOn || !text) return false;
    if (!("speechSynthesis" in window)) return false;
    const synth = window.speechSynthesis;
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
    utter.onend = () => duckMusic(false);
    utter.onerror = () => duckMusic(false);
    duckMusic(true);
    synth.speak(utter);
    return true;
  }

  function speakEmotionChange(emotion) {
    if (!emotion || !emotion.id || emotion.id === "idle") return;
    const zh = emotion.zh || (EMO_META[emotion.id] || {}).zh || "";
    const name = emotion.name || (EMO_META[emotion.id] || {}).name || "";
    speakText(`情绪标签变为${zh}，${name}`);
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
    drop: $("#dropzone"),
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

  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );
  }

  function faceSvg(id, size = 160) {
    const inner = FACE[id] || FACE.idle;
    return `<svg viewBox="0 0 100 100" width="${size}" height="${size}" fill="none" aria-hidden="true">
      <circle cx="50" cy="50" r="46" stroke="currentColor" stroke-width="4.2" opacity=".45"/>
      ${inner}
    </svg>`;
  }

  function toast(msg, kind = "") {
    const box = $("#toasts");
    const el = document.createElement("div");
    el.className = `toast ${kind}`;
    el.textContent = msg;
    box.appendChild(el);
    setTimeout(() => el.remove(), 4200);
  }

  function fmt(t) {
    if (!Number.isFinite(t) || t < 0) t = 0;
    const m = Math.floor(t / 60);
    const s = Math.floor(t % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
  }

  function isLocalHost() {
    const h = location.hostname;
    return h === "localhost" || h === "127.0.0.1" || h === "[::1]";
  }

  function isCameraSecure() {
    return window.isSecureContext || isLocalHost();
  }

  function cameraReady() {
    const stream = state.stream;
    const live = stream && stream.active && stream.getVideoTracks().some((t) => t.readyState === "live");
    return Boolean(live && ui.cam.videoWidth > 0);
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
      return "没有找到摄像头。请确认系统里已启用相机，或改用上传照片。";
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
    ui.cam.srcObject = null;
  }

  function captureBlob(quality = 0.86, maxSide = 720) {
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

  async function requestCameraStream() {
    const attempts = [
      { video: { facingMode: { ideal: "user" }, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false },
      { video: { facingMode: { ideal: "user" } }, audio: false },
      { video: { width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false },
      { video: true, audio: false },
    ];
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
    startTrackLoop();
  }

  async function startCamera() {
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
      await attachStream(stream);
      setCamHint("点下面的按钮开启摄像头，把面部落在椭圆里");
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

  const TRANSIENT_EMO = { surprise: true, fear: true, angry: true, disgust: true };
  const EMO_HOLD_MS = {
    surprise: 48000,
    fear: 48000,
    angry: 36000,
    disgust: 36000,
    happy: 18000,
    sad: 18000,
    neutral: 0,
  };
  const LIVE_SWITCH_HITS = 2;
  const LIVE_NEUTRAL_HITS = 6;

  function holdLeftMs(id) {
    if (!id || !state.lockAt) return 0;
    if (TRANSIENT_EMO[id]) return 1;
    const span = EMO_HOLD_MS[id];
    if (!span) return 0;
    return Math.max(0, span - (Date.now() - state.lockAt));
  }

  function decideLiveAction(locked, emoId, low) {
    const isSame = !!(emoId && emoId === locked);
    const isStrongOther = !!(emoId && emoId !== locked && emoId !== "neutral" && !low);
    if (!locked) return { action: "apply", reason: "first" };
    if (isSame) return { action: "same", reason: locked };
    if (isStrongOther) return { action: "pending-other", reason: emoId };
    if (TRANSIENT_EMO[locked] || holdLeftMs(locked) > 0) return { action: "hold", reason: "relax" };
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
    if (ui.hero) {
      ui.hero.classList.toggle("is-hold", !!(live && id && id !== "neutral"));
      ui.hero.classList.toggle("is-relaxed", !!(live && state.holdRelaxed && id && id !== "neutral"));
    }
    const note = $("#hold-note");
    if (note) note.hidden = !!(live && id);
    if (!hold) return;
    if (!live || !id) {
      hold.hidden = true;
      hold.textContent = "";
      hold.classList.remove("is-relaxed");
      return;
    }
    const meta = EMO_META[id] || {};
    const name = meta.name || "";
    const left = Math.ceil(holdLeftMs(id) / 1000);
    hold.hidden = false;
    hold.classList.toggle("is-relaxed", !!(state.holdRelaxed && !pendingName));
    if (pendingName) {
      hold.textContent = `好像在变成「${pendingName}」，再保持一下就会切歌`;
    } else if (id === "neutral") {
      hold.textContent = "当前按平静连播。摆出喜、怒、哀、惧、惊、厌等更明显的表情，确认后才会切歌。";
    } else if (state.holdRelaxed) {
      hold.textContent = TRANSIENT_EMO[id]
        ? `脸已松开，歌曲仍锁定「${name}」· 做出另一种明显表情才会换歌`
        : left > 0
          ? `脸已松开，歌曲仍锁定「${name}」· 约 ${left} 秒内不会因平静换歌`
          : `脸已松开，歌曲仍按「${name}」播放 · 持续平静才会切到中性歌单`;
      $("#emo-kicker").textContent = "歌曲锁定";
      $("#emo-conf").textContent = `表情已松开 · 继续播放${name}歌单`;
    } else if (TRANSIENT_EMO[id]) {
      hold.textContent = `已锁定「${name}」· 惊讶、恐惧很难一直保持，松开脸也会继续播`;
    } else {
      hold.textContent = `按「${name}」连播 · 换一种明显表情才会切歌`;
    }
  }

  function stopLive() {
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
  }

  function syncLiveHudDot() {
    const dot = $("#live-emo-dot");
    if (dot) dot.hidden = !state.live;
  }

  function sizeFaceOverlay() {
    const canvas = ui.overlay;
    const vp = $("#viewport");
    if (!canvas || !vp) return null;
    const cssW = vp.clientWidth;
    const cssH = vp.clientHeight;
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

  function lerpBox(a, b, t) {
    if (!a) return b;
    return {
      x: a.x + (b.x - a.x) * t,
      y: a.y + (b.y - a.y) * t,
      w: a.w + (b.w - a.w) * t,
      h: a.h + (b.h - a.h) * t,
    };
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

  function hexToRgba(hex, alpha) {
    const h = String(hex || "").replace("#", "");
    const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
    const n = parseInt(full, 16);
    if (!Number.isFinite(n)) return `rgba(196,165,116,${alpha})`;
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`;
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
    state.overlaySmooth = null;
    state.lastOverlay = { id: "idle", color: EMO_HEX.idle };
    const hud = $("#live-emo-hud");
    if (hud) {
      hud.hidden = true;
      paintHudTone(hud, "idle", "", true);
    }
  }

  function updateLiveHud(data) {
    const hud = $("#live-emo-hud");
    if (!hud) return;
    if (ui.empty && !ui.empty.hidden) {
      hud.hidden = true;
      return;
    }
    hud.hidden = false;
    syncLiveHudDot();
    const emo = (data && data.ok && data.emotion) || null;
    if (!emo) {
      const changed = hud.dataset.emo !== "idle" || !hud.classList.contains("is-miss");
      hud.dataset.emo = "idle";
      hud.classList.add("is-miss");
      paintHudTone(hud, "idle", "", true);
      $("#live-emo-zh").textContent = "";
      $("#live-emo-name").textContent = "寻找人脸";
      $("#live-emo-pct").textContent = "";
      state.lastOverlay = { id: "idle", color: EMO_HEX.idle };
      if (changed) flashLiveHud(hud);
      return;
    }
    const nextId = emo.id || "idle";
    const color = emoHex(nextId, emo.color);
    const changed = hud.dataset.emo !== nextId || hud.classList.contains("is-miss");
    hud.classList.remove("is-miss");
    hud.dataset.emo = nextId;
    paintHudTone(hud, nextId, emo.color, false);
    if (changed) flashLiveHud(hud);
    const meta = EMO_META[nextId] || {};
    $("#live-emo-zh").textContent = meta.zh || emo.zh || "";
    $("#live-emo-name").textContent = meta.name || emo.name || "";
    const pct = Math.round((emo.prob || 0) * 100);
    $("#live-emo-pct").textContent = pct ? `${pct}%` : "";
    state.lastOverlay = { id: nextId, color };
  }

  function drawFaceOverlay(data) {
    const canvas = ui.overlay;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    sizeFaceOverlay();
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    updateLiveHud(data);
    if (!data || !data.ok || !data.face || !data.face.box) {
      state.overlaySmooth = null;
      return;
    }
    const imageSize = data.face.image_size || [ui.shot.width, ui.shot.height];
    const mapped = mapBoxToCanvas(data.face.box, imageSize, true);
    if (!mapped) return;
    state.overlaySmooth = lerpBox(state.overlaySmooth, mapped, 0.42);
    const box = state.overlaySmooth;
    const emo = data.emotion || {};
    const emoId = emo.id || "idle";
    const color = emoHex(emoId, emo.color);
    state.lastOverlay = { id: emoId, color };
    const radius = Math.max(10, box.w * 0.08);
    ctx.save();
    roundRectPath(ctx, box.x, box.y, box.w, box.h, radius);
    ctx.fillStyle = hexToRgba(color, 0.14);
    ctx.fill();
    ctx.lineWidth = Math.max(3.5, box.w * 0.018);
    ctx.strokeStyle = color;
    ctx.shadowColor = color;
    ctx.shadowBlur = 18;
    ctx.stroke();
    ctx.shadowBlur = 0;
    ctx.lineWidth = Math.max(5, box.w * 0.03);
    drawCornerBrackets(ctx, box.x, box.y, box.w, box.h, color);
    const extras = (data.faces || []).filter((f) => !f.primary && f.box);
    extras.forEach((f) => {
      const extra = mapBoxToCanvas(f.box, imageSize, true);
      if (!extra) return;
      ctx.globalAlpha = 0.4;
      ctx.lineWidth = 2;
      ctx.strokeStyle = hexToRgba(color, 0.55);
      roundRectPath(ctx, extra.x, extra.y, extra.w, extra.h, 8);
      ctx.stroke();
      ctx.globalAlpha = 1;
    });
    const meta = EMO_META[emoId] || {};
    const zh = meta.zh || emo.zh || "";
    const name = meta.name || emo.name || "";
    const pct = Math.round((emo.prob || 0) * 100);
    const label = [zh, name, pct ? `${pct}%` : ""].filter(Boolean).join("  ");
    if (label) {
      const fontPx = Math.max(15, Math.min(24, box.w * 0.14));
      ctx.font = `700 ${fontPx}px "Noto Sans SC","Microsoft YaHei",sans-serif`;
      ctx.textBaseline = "middle";
      const padX = 12;
      const tw = ctx.measureText(label).width;
      const pillW = tw + padX * 2;
      const pillH = fontPx + 14;
      let px = box.x;
      let py = box.y - pillH - 10;
      if (py < 8) py = box.y + 8;
      if (px + pillW > canvas.width - 8) px = Math.max(8, canvas.width - pillW - 8);
      roundRectPath(ctx, px, py, pillW, pillH, pillH / 2);
      ctx.fillStyle = "rgba(8,7,6,0.78)";
      ctx.fill();
      ctx.fillStyle = hexToRgba(color, 0.22);
      ctx.fill();
      ctx.lineWidth = 1.8;
      ctx.strokeStyle = color;
      ctx.stroke();
      ctx.shadowColor = "rgba(0,0,0,0.65)";
      ctx.shadowBlur = 8;
      ctx.fillStyle = color;
      ctx.fillText(label, px + padX, py + pillH / 2);
    }
    ctx.restore();
  }

  function stopTrackLoop() {
    state.trackOn = false;
    if (state.trackTimer) {
      clearTimeout(state.trackTimer);
      state.trackTimer = 0;
    }
    state.trackBusy = false;
  }

  function startTrackLoop() {
    if (state.trackOn) return;
    state.trackOn = true;
    const tick = async () => {
      state.trackTimer = 0;
      if (!state.trackOn) return;
      if (state.mode !== "camera" || !cameraReady() || (ui.empty && !ui.empty.hidden)) {
        clearFaceOverlay();
        if (state.trackOn && state.mode === "camera" && cameraReady()) {
          state.trackTimer = setTimeout(tick, 400);
        }
        return;
      }
      if (!state.trackBusy && !state.recognizing) {
        state.trackBusy = true;
        try {
          const blob = await captureBlob(0.56, 480);
          if (blob && state.trackOn && state.mode === "camera") {
            const fd = new FormData();
            fd.append("image", blob, "track.jpg");
            const res = await fetch("/api/track", { method: "POST", body: fd });
            const data = await res.json();
            if (state.trackOn && state.mode === "camera") drawFaceOverlay(data);
          }
        } catch {
          /* 追踪失败时下一拍再试 */
        } finally {
          state.trackBusy = false;
        }
      }
      if (state.trackOn && state.mode === "camera" && cameraReady()) {
        state.trackTimer = setTimeout(tick, state.live ? 420 : 280);
      }
    };
    state.trackTimer = setTimeout(tick, 120);
  }

  function showPanel(mode) {
    state.mode = mode;
    $$(".tab").forEach((t) => {
      const on = t.dataset.mode === mode;
      t.classList.toggle("is-on", on);
      t.setAttribute("aria-selected", on ? "true" : "false");
    });
    $$(".stage-body").forEach((v) => {
      v.hidden = v.dataset.view !== mode;
    });
  }

  function setMode(mode) {
    showPanel(mode);
    if (mode === "camera") {
      ui.preview.hidden = true;
      ui.cam.hidden = false;
      startCamera();
    } else {
      stopLive();
      stopTrackLoop();
      clearFaceOverlay();
    }
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
    if (ui.hero) ui.hero.dataset.emo = "idle";
    if (ui.icon) ui.icon.innerHTML = faceSvg("idle", 180);
    showFaceCrop({});
    $("#emo-kicker").textContent = "等待识别";
    $("#emo-zh").textContent = "待识别";
    $("#emo-name").textContent = "面向镜头，点识别此刻";
    $("#emo-conf").textContent = "";
    $("#emo-copy").textContent = "识别后会对照人脸与情绪，并自动连播匹配歌曲。惊讶、恐惧等表情松开后，歌曲仍会按这次情绪继续播。";
    const genre = $("#emo-genre");
    genre.hidden = true;
    genre.textContent = "";
    renderEmoTags([], "");
  }

  function showEmotion(payload) {
    const e = payload.emotion;
    const changed = document.body.dataset.emotion !== e.id;
    document.body.dataset.emotion = e.id;
    if (ui.hero) ui.hero.dataset.emo = e.id;
    showFaceCrop(payload);
    if (ui.icon) {
      ui.icon.classList.remove("is-pop");
      ui.icon.innerHTML = faceSvg(e.id, 180);
      if (changed) {
        void ui.icon.offsetWidth;
        ui.icon.classList.add("is-pop");
      }
    }
    $("#emo-kicker").textContent = "当前情绪";
    const meta = EMO_META[e.id] || {};
    $("#emo-zh").textContent = meta.zh || e.zh || "";
    $("#emo-name").textContent = meta.name || e.name || "";
    const conf = Math.round(e.prob * 100);
    $("#emo-conf").textContent = e.low_confidence
      ? `置信度 ${conf}% · 光线或角度一般，结果仅供参考`
      : `置信度 ${conf}%`;
    $("#emo-copy").textContent = e.copy;
    const genre = $("#emo-genre");
    genre.hidden = !e.genre;
    genre.textContent = e.genre || "";
    const ms = payload.elapsed_ms || payload.total_ms;
    $("#timing").textContent = ms ? `识别 ${Math.round(ms)} 毫秒` : "";
    renderEmoTags(e.scores, e.id);
    if (changed) speakEmotionChange(e);
    if ((payload && payload.source) !== "camera-live") {
      const narrow = window.matchMedia("(max-width: 980px)").matches;
      if (narrow && ui.hero) {
        requestAnimationFrame(() => {
          ui.hero.scrollIntoView({ behavior: "smooth", block: "center" });
        });
      }
    }
  }

  function foldTitle(title) {
    let t = prettyText(String(title || "")).toLowerCase();
    t = t.replace(/°c|℃|°/g, "度");
    t = t.replace(/[ ,，]/g, "");
    t = t.split(/[\/（(|]/)[0];
    return t.trim();
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

  function songCard(song, idx) {
    const cover = esc(song.cover || "");
    const title = esc(prettyText(song.title));
    const artist = esc(prettyText(song.artist));
    const album = song.album ? " · " + esc(prettyText(song.album)) : "";
    const playable = song.playable && song.audio;
    const badge = esc(prettyText(song.source_label || SOURCE_ZH[song.source] || song.source || ""));
    return `<article class="song" data-idx="${idx}">
      <img src="${cover}" alt="${title} 封面" onerror="this.style.opacity=.2" />
      <div class="body">
        <strong>${title}</strong>
        <em>${artist}${album}</em>
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
        : "识别后自动连播；惊讶、恐惧松开后也不会马上换歌");
    if (!state.songs.length) {
      ui.songs.innerHTML = `<p class="empty-songs">还没有歌曲。完成识别后，这里会列出并自动播放匹配曲目。</p>`;
      return;
    }
    ui.songs.innerHTML = state.songs.map(songCard).join("");
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

  function recsCaption(rec) {
    const n = (rec.songs || []).length;
    const providers = (rec.providers || []).map((s) => String(s).replace(/^在线 · /, "")).filter(Boolean);
    if (rec.online_count > 0) {
      const src = providers.length ? providers.join("、") : "在线";
      return `${rec.genre || ""} · ${src} ${rec.online_count} / 本地 ${rec.local_count || 0} · ${n} 首 · 表情松开也会继续播`;
    }
    return `${rec.genre || ""} · 本地曲库 ${n} 首 · 表情松开也会继续播`;
  }

  async function loadPlaylist(emo, play) {
    const id = emo || currentEmotionId();
    try {
      const data = await (await fetch(`/api/recommend?emotion=${encodeURIComponent(id)}&online=${state.onlineOn ? "1" : "0"}`)).json();
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

  function noteOnlinePlayFail(song) {
    if (!state.onlineOn || !isOnlineSong(song) || state.fallbackBusy) return;
    const now = Date.now();
    if (!state.onlineFailAt) state.onlineFailAt = now;
    state.onlineFailCount += 1;
    const long = now - state.onlineFailAt >= 12000;
    if (state.onlineFailCount >= 3 || (state.onlineFailCount >= 2 && long)) {
      fallbackToLocal("在线歌曲长时间播放失败，已自动切换到本地曲库。");
    }
  }

  function armPlayWatch(song) {
    clearTimeout(state.playWatch);
    if (!isOnlineSong(song) || !state.onlineOn) return;
    state.playWatch = setTimeout(() => {
      if (!sameAudio(song.audio)) return;
      if (audio.readyState >= 3 && audio.currentTime >= 0.2) return;
      state.failed.add(songKey(song));
      noteOnlinePlayFail(song);
      if (state.onlineOn) playNext();
    }, 10000);
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
    let i = 0;
    for (let k = 0; k < lines.length; k += 1) {
      if (Number(lines[k].t) <= t) i = k;
      else break;
    }
    const cur = lines[i] || {};
    prev.textContent = i > 0 ? lines[i - 1].text || "" : "";
    now.textContent = cur.text || "♪";
    now.classList.add("is-on");
    next.textContent = i + 1 < lines.length ? lines[i + 1].text || "" : "";
  }

  async function loadLyrics(song) {
    const token = (state.lyricToken += 1);
    const key = `${song.id || ""}|${song.title || ""}`;
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
    if (!n || hops > n) return;
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
    if (next < 0) return;
    playAt(next);
  }

  function syncPlayingHighlight() {
    const idx = state.songs.findIndex((s) => s && s.audio && sameAudio(s.audio));
    if (idx >= 0) {
      state.index = idx;
      markCurrent();
    }
  }

  function firstFreshPlayable() {
    const emo = currentEmotionId();
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

  function footprintSongs(it) {
    const played = Array.isArray(it && it.played) ? it.played : [];
    const recs = Array.isArray(it && it.songs) ? it.songs : [];
    if (played.length) return uniqueSongs(played.concat(recs));
    return uniqueSongs(recs);
  }

  function songsLine(it, limit = 3) {
    const songs = footprintSongs(it);
    if (!songs.length) return "";
    const shown = songs.slice(0, limit).map((song) => {
      const title = esc(prettyText(song.title || ""));
      const artist = song.artist ? ` · ${esc(prettyText(song.artist))}` : "";
      return `<span class="trail-song"><strong>${title}</strong><em>${artist}</em></span>`;
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
          key,
        },
      }),
    }).catch(() => {});
  }

  function autoPlayList(force, fromHistory) {
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
        "/api/recognize?source=" + encodeURIComponent(source) + "&online=" + (state.onlineOn ? "1" : "0"),
        {
          method: "POST",
          body: fd,
          headers: {
            "X-Emo-Source": source,
            "X-Emo-Online": state.onlineOn ? "1" : "0",
          },
        }
      );
      const data = await res.json();
      const live = source === "camera-live";
      if (!data.ok) {
        if (live) {
          if (state.lockEmotion) updateHoldUi(true);
          return;
        }
        toast(data.error || "识别失败", "err");
        return;
      }
      const rec = data.recommendations || {};
      const emoId = (data.emotion && data.emotion.id) || "";
      const mix = recsCaption(rec);
      if (data.history_id) state.historyId = data.history_id;
      if (emoId && Array.isArray(data.played_keys)) rememberPlayedKeys(emoId, data.played_keys);

      const applyNew = () => {
        state.replayHistory = false;
        showEmotion(data);
        renderSongs(rec.songs, mix);
        lockPlaylist(emoId);
        autoPlayList(true);
        if (live && TRANSIENT_EMO[emoId]) {
          const nm = (EMO_META[emoId] || {}).name || "";
          toast(`已锁定「${nm}」歌单，脸松开也不会马上换歌`);
        }
        if (state.onlineOn && rec.mode === "local-fallback") toast("在线曲库暂时不可用，已改用本地歌曲。");
      };

      if (!live) {
        applyNew();
        const cost = Math.round(data.total_ms || performance.now() - t0);
        if (state.onlineOn && cost > 3000) toast(`本次总耗时 ${cost} 毫秒，略慢于 3 秒目标。`);
        loadHistory();
        return;
      }

      const locked = state.lockEmotion;
      const low = !!(data.emotion && data.emotion.low_confidence);
      const decision = decideLiveAction(locked, emoId, low);

      if (decision.action === "apply") {
        applyNew();
      } else if (decision.action === "same") {
        if (emoId && emoId !== "neutral") state.lockAt = Date.now();
        showEmotion(data);
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
        if (state.liveGuessCount >= LIVE_NEUTRAL_HITS) applyNew();
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
        if (state.liveGuessCount >= LIVE_SWITCH_HITS) applyNew();
        else {
          showFaceCrop(data);
          const pending = (EMO_META[emoId] || {}).name || "";
          updateHoldUi(false, pending);
        }
      }
      const cost = Math.round(data.total_ms || performance.now() - t0);
      if (state.onlineOn && cost > 3000) toast(`本次总耗时 ${cost} 毫秒，略慢于 3 秒目标。`);
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
    if (state.mode === "camera") {
      if (state.live) {
        stopLive();
        toast("已关闭实时捕捉，改为识别此刻的截图");
      }
      if (!cameraReady()) {
        const ok = await startCamera();
        if (!ok) return;
      }
      const burst = [];
      for (let i = 0; i < 3; i += 1) {
        const blob = await captureBlob();
        if (blob) burst.push(blob);
        if (i < 2) await new Promise((r) => setTimeout(r, 90));
      }
      if (!burst.length) {
        toast("还没有画面。请先点「开启摄像头」，看到自己后再识别。", "err");
        return;
      }
      await recognize(burst, "camera");
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
    state.lastFile = file;
    showPanel("upload");
    const url = URL.createObjectURL(file);
    const picked = $("#picked");
    const img = $("#picked-img");
    const cap = $("#picked-cap");
    if (img) img.src = url;
    if (picked) picked.hidden = false;
    if (cap) cap.textContent = "已选择照片，正在识别…";
    Promise.resolve(recognize(file, "upload")).finally(() => {
      if (cap) cap.textContent = "已选择照片";
    });
  }

  function applyHistoryItem(it) {
    unlockAudio();
    state.replayHistory = true;
    state.historyId = it.id || "";
    if (it.emotion) {
      showEmotion({
        emotion: it.emotion,
        elapsed_ms: it.elapsed_ms,
        face: it.face,
        source: it.source,
      });
    }
    const songs = footprintSongs(it);
    const n = (it.played || []).length;
    renderSongs(songs, n ? `来自情绪足迹 · 当时听过 ${n} 首` : "来自情绪足迹 · 回放当时的歌");
    $("#history-drawer").hidden = true;
    lockPlaylist((it.emotion && it.emotion.id) || "");
    autoPlayList(true, true);
  }

  function renderTrail(items) {
    if (!ui.trail) return;
    const meta = $("#trail-meta");
    if (!items || !items.length) {
      ui.trail.innerHTML = `<p class="trail-empty">识别几次后，这里会留下人脸、情绪图标和听过的歌。</p>`;
      if (meta) meta.textContent = "全部保存 · 人脸、情绪图标和播过的歌都会留下";
      return;
    }
    if (meta) meta.textContent = `已保存 ${items.length} 次 · 人脸、情绪图标和播过的歌都会留下 · 点选可回放`;
    ui.trail.innerHTML = items
      .map((it) => {
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
        return `<button type="button" class="trail-chip has-face" data-id="${esc(it.id)}" data-emo="${esc(id)}" role="listitem">
          ${pair}
          <b>${zh}</b>
          <span class="trail-name">${name}</span>
          ${songsLine(it)}
        </button>`;
      })
      .join("");
    $$(".trail-chip", ui.trail).forEach((btn) => {
      btn.addEventListener("click", () => {
        const it = state.history.find((x) => x.id === btn.dataset.id);
        if (it) applyHistoryItem(it);
      });
    });
  }

  async function loadHistory() {
    try {
      const data = await (await fetch("/api/history")).json();
      const items = data.items || [];
      state.history = items;
      if (data.played && typeof data.played === "object") {
        Object.keys(data.played).forEach((emo) => rememberPlayedKeys(emo, data.played[emo]));
      }
      renderTrail(items);
      const box = $("#history-list");
      if (!items.length) {
        box.innerHTML = `<p class="meta">还没有记录。</p>`;
        return;
      }
      box.innerHTML = items
        .map((it) => {
          const e = it.emotion || {};
          const id = e.id || "idle";
          const t = new Date((it.ts || 0) * 1000).toLocaleString("zh-CN", { hour12: false });
          const src = SOURCE_ZH[it.source] || "";
          const ms = it.elapsed_ms ? `${Math.round(it.elapsed_ms)} 毫秒` : "";
          const crop = faceCropSrc(it.face);
          const mirror = isCameraSource(it.source) ? " is-mirror" : "";
          const nm = esc(e.name || (EMO_META[id] || {}).name || "");
          const faceInner = crop
            ? `<img src="${crop}" alt="用于判断${nm}的人脸">`
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
        })
        .join("");
      $$(".history-item", box).forEach((btn) => {
        btn.addEventListener("click", () => {
          const it = state.history.find((x) => x.id === btn.dataset.id);
          if (it) applyHistoryItem(it);
        });
      });
    } catch {
      /* ignore */
    }
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
        btn.addEventListener("click", async () => {
          unlockAudio();
          const blob = await (await fetch(btn.dataset.url)).blob();
          const file = new File([blob], btn.dataset.file || `${btn.dataset.id}.jpg`, { type: blob.type || "image/jpeg" });
          useFile(file);
        });
      });
    } catch {
      /* demo 可选 */
    }
  }

  function bind() {
    $$(".tab").forEach((t) => t.addEventListener("click", () => setMode(t.dataset.mode)));
    $("#btn-cam").addEventListener("click", () => {
      unlockAudio();
      startCamera();
    });
    $("#btn-recognize").addEventListener("click", recognizeNow);
    $("#live-toggle").addEventListener("change", async (e) => {
      if (e.target.checked) {
        unlockAudio();
        const ok = await startCamera();
        if (!ok) {
          e.target.checked = false;
          return;
        }
        state.live = true;
        startHoldTick();
        updateHoldUi(false);
        syncLiveHudDot();
        toast("实时捕捉已打开：画面会标出人脸框，认到表情就推荐歌曲。惊讶、恐惧松开后也不会马上换歌。");
        state.liveTimer = setInterval(async () => {
          if (state.mode !== "camera" || state.recognizing || !cameraReady()) return;
          const blob = await captureBlob(0.8);
          if (blob) recognize(blob, "camera-live");
        }, 1600);
      } else stopLive();
    });

    ui.file.addEventListener("change", () => useFile(ui.file.files[0]));
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

    ui.songs.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-play]");
      const card = e.target.closest(".song");
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
      if (audio.paused) audio.play().catch(() => toast("请再点一次播放。", "err"));
      else audio.pause();
    });
    $("#btn-prev").addEventListener("click", () => {
      const n = state.songs.length;
      if (!n) return;
      const prev = firstPlayable(state.index - 1, -1);
      if (prev >= 0) playAt(prev);
    });
    $("#btn-next").addEventListener("click", playNext);
    audio.addEventListener("play", () => ($("#btn-play").textContent = "❚❚"));
    audio.addEventListener("pause", () => ($("#btn-play").textContent = "▶"));
    audio.addEventListener("ended", () => {
      if (isSilentOrEmpty()) return;
      playNext();
    });
    audio.addEventListener("playing", () => {
      clearTimeout(state.playWatch);
      const song = state.songs[state.index];
      if (isOnlineSong(song)) noteOnlinePlayOk();
      notePlayed(song);
    });
    audio.addEventListener("error", () => {
      if (isSilentOrEmpty()) return;
      const song = state.songs[state.index];
      if (song) state.failed.add(songKey(song));
      noteOnlinePlayFail(song);
      playNext();
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
      loadHistory();
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
        toast(state.onlineOn ? "已改用在线热歌，识别后优先播在线曲库。" : "已改用本地曲库，断网也能听。");
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
          try {
            window.speechSynthesis && window.speechSynthesis.cancel();
          } catch {
            /* ignore */
          }
          duckMusic(false);
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
        toast(ok ? "语音提示已打开，情绪标签变化时会播报。" : "语音提示已打开。");
      });
    }
    if ("speechSynthesis" in window) {
      refreshZhVoice();
      window.speechSynthesis.addEventListener("voiceschanged", refreshZhVoice);
    }

    $$(".theme-pick").forEach((btn) => {
      btn.setAttribute("role", "radio");
      btn.addEventListener("click", () => applyTheme(btn.dataset.theme, true));
    });
    $("#btn-about").addEventListener("click", () => $("#about-dialog").showModal());
    $("#btn-close-about").addEventListener("click", () => $("#about-dialog").close());

    window.addEventListener("keydown", (e) => {
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
    try {
      const prefs = await (await fetch("/api/prefs")).json();
      if (prefs && prefs.theme) applyTheme(prefs.theme, false);
    } catch {
      /* 主题可只用本机记忆 */
    }
    loadDemo();
    loadHistory();
    try {
      const health = await (await fetch("/api/health")).json();
      if (!health.ok) toast("服务未就绪", "err");
      else if (!health.models.yunet || !health.models.fer) toast("本地模型文件缺失，请查看运行说明。", "err");
      else if (health.offline_ready) {
        const n = health.local_songs || 0;
        const hint = $("#stage-hint");
        if (hint) hint.textContent = `本机模型已就绪，本地曲库 ${n} 首。没有网络也能识别和播放。摄像头请用 http://127.0.0.1:5000 打开。`;
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
    transient: TRANSIENT_EMO,
    emoHex,
    getState: () => ({
      lock: state.lockEmotion,
      relaxed: state.holdRelaxed,
      guess: state.liveGuess,
      guessCount: state.liveGuessCount,
      live: state.live,
      titles: state.songs.map((s) => s.title),
      overlay: state.lastOverlay,
      onlineOn: state.onlineOn,
      historyId: state.historyId,
      trailCount: (state.history || []).length,
      replayHistory: state.replayHistory,
      played: state.playedByEmotion,
    }),
    fallbackToLocal,
    stopLive,
  };

  boot();
})();
