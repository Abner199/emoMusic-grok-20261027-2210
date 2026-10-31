/* 当AI遇见旋律 · core.js：七类情绪定义、颜色、繁简转换、表情图标与纯工具函数。
 * 不依赖页面状态，供 app.js 使用（window.EmoCore）。 */
(() => {
  const EMO_ORDER = ["happy", "angry", "sad", "fear", "surprise", "disgust", "neutral"];
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
  const EMO_HEX = Object.fromEntries(Object.keys(EMO_META).map((k) => [k, EMO_META[k].color]));
  const SOURCE_ZH = {
    upload: "上传照片",
    camera: "摄像头",
    "camera-live": "实时捕捉",
    video: "本地视频",
    "video-live": "视频捕捉",
    screen: "屏幕",
    "screen-live": "屏幕捕捉",
  };
  const FACE_MODE_META = {
    solo: { id: "solo", zh: "单人精检", blurb: "只取画面里最大、最稳的一张脸，检测阈值更高，不扫远景杂脸。适合自拍和对镜。近景会融合两套表情模型；两模型不一致时更信野外模型。" },
    crowd: { id: "crowd", zh: "多人远场", blurb: "同时框出多张脸，包括远景小脸；歌曲按人数最多的情绪来。适合课堂、合影和远镜头。" },
  };
  const TRAD =
    "愛後為國樂發時長門開東風雲點實現與無這個們來對會體醜強獨戰鐘煙湧陰貓樹傑銘謙飛兒鄧陳趙歲戀聽記過錯氣龍捲義術單簡當從業書華語經總應該說讓給還進運關問題歡熱陽離獸團傳蘭齊劉買綱願乾燦爛態戲劇觀覺優傷殤俠雙盧樸馮靜倫誇闆裡麼線將畫憶懷邊條孫隻隻臺蘋麼麼聲帶專輯場錄選數賜碼銀鏡際內寫讀請區灣標準寶貝頁頭題顏館廣廳響處歷據產權號級類組員並確滿漢彙視藝職網質價電務間葉滾搖見絲詩迴蕭驚顫慄溫學認島黃嘆髮孃煉園遊盤騎亂羅曖榮詞話親變萬遠換擇證驗聯習鳳車馬魚錢賣鬆麵廠鐵億儀慶禮節責曆絡織閉係裏詠曉鴻穎聰艷偉麗鵬濤潔純紅機軍殺謝鋒殘竅極誘計動軌跡約橋興嗎雞嵐張妳瑋議の層樓寶暢蘇綠瀧險夢牆墻剛違獻凍轉蓋結絕劍樣個幾終峯傾喬舊賞韋禮編楊韓吳寧許靚夠彈帥週製複採捨";
  const SIMP =
    "爱后为国乐发时长门开东风云点实现与无这个们来对会体丑强独战钟烟涌阴猫树杰铭谦飞儿邓陈赵岁恋听记过错气龙卷义术单简当从业书华语经总应该说让给还进运关问题欢热阳离兽团传兰齐刘买纲愿干灿烂态戏剧观觉优伤殇侠双卢朴冯静伦夸板里么线将画忆怀边条孙只只台苹么么声带专辑场录选数赐码银镜际内写读请区湾标准宝贝页头题颜馆广厅响处历据产权号级类组员并确满汉汇视艺职网质价电务间叶滚摇见丝诗回萧惊颤栗温学认岛黄叹发娘炼园游盘骑乱罗暧荣词话亲变万远换择证验联习凤车马鱼钱卖松面厂铁亿仪庆礼节责历络织闭系里咏晓鸿颖聪艳伟丽鹏涛洁纯红机军杀谢锋残窍极诱计动轨迹约桥兴吗鸡岚张你玮议之层楼宝畅苏绿泷险梦墙墙刚违献冻转盖结绝剑样个几终峰倾乔旧赏韦礼编杨韩吴宁许靓够弹帅周制复采舍";
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
  function fmt(t) {
    if (!Number.isFinite(t) || t < 0) t = 0;
    const m = Math.floor(t / 60);
    const s = Math.floor(t % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
  }
  function hexToRgba(hex, alpha) {
    const h = String(hex || "").replace("#", "");
    const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
    const n = parseInt(full, 16);
    if (!Number.isFinite(n)) return `rgba(196,165,116,${alpha})`;
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`;
  }
  function foldTitle(title) {
    let t = prettyText(String(title || "")).toLowerCase();
    t = t.replace(/°c|℃|°/g, "度");
    t = t.replace(/[ ,，]/g, "");
    t = t.split(/[\/（(|]/)[0];
    return t.trim();
  }
  function clampNum(v, lo, hi) {
    return Math.max(lo, Math.min(hi, v));
  }
  function normRange(v, lo, hi) {
    if (hi <= lo) return 0.5;
    return clampNum((v - lo) / (hi - lo), 0, 1);
  }

  window.EmoCore = { EMO_ORDER, EMO_META, EMO_HEX, SOURCE_ZH, FACE_MODE_META, TRAD, SIMP, TRAD_MAP, FACE, prettyText, esc, faceSvg, fmt, hexToRgba, foldTitle, clampNum, normRange };
})();
