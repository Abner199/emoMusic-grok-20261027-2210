/* 当AI遇见旋律 · stats.js：课堂情绪统计看板（环形图、时长、换歌、热门歌曲），可导出 PNG / 打印 PDF。
 * 依赖 core.js（EmoCore），数据来自 /api/stats。 */
(() => {
  const { EMO_ORDER, EMO_META, esc } = window.EmoCore;
  const $ = (sel, root = document) => root.querySelector(sel);
  const PAGE_OPENED = Math.floor(Date.now() / 1000);
  const SOURCE_ZH = { upload: "上传照片", camera: "识别此刻", "camera-live": "实时摄像头", video: "视频", "video-live": "视频实时", screen: "屏幕", "screen-live": "屏幕实时" };
  let range = "session";
  let last = null;

  function since() {
    if (range === "session") return PAGE_OPENED;
    if (range === "today") {
      const d = new Date();
      d.setHours(0, 0, 0, 0);
      return Math.floor(d.getTime() / 1000);
    }
    return 0;
  }

  function fmtDur(s) {
    s = Math.round(Number(s) || 0);
    if (s < 60) return `${s} 秒`;
    const m = Math.floor(s / 60);
    return m < 60 ? `${m} 分 ${s % 60} 秒` : `${Math.floor(m / 60)} 小时 ${m % 60} 分`;
  }

  function donut(counts, total) {
    const r = 70;
    const c = 2 * Math.PI * r;
    let off = 0;
    const arcs = EMO_ORDER.filter((id) => counts[id]).map((id) => {
      const frac = counts[id] / total;
      const seg = `<circle r="${r}" cx="90" cy="90" fill="none" stroke="${EMO_META[id].color}" stroke-width="26"
        stroke-dasharray="${(frac * c).toFixed(2)} ${c.toFixed(2)}" stroke-dashoffset="${(-off * c).toFixed(2)}"
        transform="rotate(-90 90 90)"><title>${EMO_META[id].name} ${Math.round(frac * 100)}%</title></circle>`;
      off += frac;
      return seg;
    });
    return `<svg viewBox="0 0 180 180" class="st-donut" role="img" aria-label="各情绪占比">
      <circle r="${r}" cx="90" cy="90" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="26"/>
      ${arcs.join("")}
    </svg>`;
  }

  function render(d) {
    last = d;
    const body = $("#stats-body");
    if (!body) return;
    const total = d.total || 0;
    if (!total) {
      body.innerHTML = `<p class="st-empty">这个时间段还没有识别记录。打开摄像头或上传照片试试。</p>`;
      return;
    }
    const dom = EMO_META[d.dominant] || EMO_META.neutral;
    const rows = EMO_ORDER.filter((id) => d.counts[id])
      .sort((a, b) => d.counts[b] - d.counts[a])
      .map((id) => {
        const pct = Math.round((d.counts[id] / total) * 100);
        return `<div class="st-row" style="--emo:${EMO_META[id].color}">
          <b>${EMO_META[id].zh}</b><span>${EMO_META[id].name}</span>
          <i><s style="width:${pct}%"></s></i><em>${pct}%</em><small>${fmtDur((d.seconds || {})[id])}</small>
        </div>`;
      })
      .join("");
    const songs = (d.top_songs || [])
      .map((s, i) => `<li><b>${i + 1}</b><span>${esc(s.title)}</span><small>${esc(s.artist || "")}</small><em>${s.n} 次</em></li>`)
      .join("") || `<li class="st-none">还没有播放记录</li>`;
    const sources = Object.entries(d.sources || {})
      .sort((a, b) => b[1] - a[1])
      .map(([k, v]) => `<span>${esc(SOURCE_ZH[k] || k)} <b>${v}</b></span>`)
      .join("");
    const span = d.from && d.to ? `${new Date(d.from * 1000).toLocaleString("zh-CN", { hour12: false })} — ${new Date(d.to * 1000).toLocaleTimeString("zh-CN", { hour12: false })}` : "";
    body.innerHTML = `
      <div class="st-hero">
        <div class="st-donut-wrap">${donut(d.counts, total)}<div class="st-center"><b style="color:${dom.color}">${dom.zh}</b><span>主要情绪</span></div></div>
        <div class="st-kpis">
          <div><b>${total}</b><span>次识别</span></div>
          <div><b>${d.switches}</b><span>次情绪变化</span></div>
          <div><b style="color:${dom.color}">${dom.name}</b><span>占比最高</span></div>
          <div class="st-span">${esc(span)}</div>
        </div>
      </div>
      <h3>各情绪占比与持续时长</h3>
      <div class="st-rows">${rows}</div>
      <div class="st-grid">
        <div><h3>播放最多的歌</h3><ol class="st-songs">${songs}</ol></div>
        <div><h3>识别来源</h3><p class="st-sources">${sources}</p></div>
      </div>`;
  }

  async function load() {
    const body = $("#stats-body");
    if (body) body.innerHTML = `<p class="st-empty">正在统计…</p>`;
    try {
      const d = await (await fetch(`/api/stats?since=${since()}`)).json();
      render(d);
    } catch {
      if (body) body.innerHTML = `<p class="st-empty">统计失败，请稍后再试。</p>`;
    }
  }

  /* 导出 PNG：用画布重画一份简洁的统计图（不依赖截图库，断网可用） */
  function exportPng() {
    const d = last;
    if (!d || !d.total) return;
    const W = 1200, H = 760, cv = document.createElement("canvas");
    cv.width = W;
    cv.height = H;
    const g = cv.getContext("2d");
    const grad = g.createLinearGradient(0, 0, W, H);
    grad.addColorStop(0, "#0b0d1a");
    grad.addColorStop(1, "#1a1020");
    g.fillStyle = grad;
    g.fillRect(0, 0, W, H);
    g.fillStyle = "#fff";
    g.font = '700 40px "Noto Serif SC","Microsoft YaHei",serif';
    g.fillText("课堂情绪统计 · 当AI遇见旋律", 60, 86);
    g.font = '400 20px "Microsoft YaHei",sans-serif';
    g.fillStyle = "rgba(255,255,255,0.65)";
    const label = { session: "本节课", today: "今天", all: "全部" }[range];
    g.fillText(`${label} · 共 ${d.total} 次识别 · ${d.switches} 次情绪变化 · ${new Date().toLocaleString("zh-CN", { hour12: false })}`, 60, 124);
    let a0 = -Math.PI / 2;
    EMO_ORDER.filter((id) => d.counts[id]).forEach((id) => {
      const a1 = a0 + (d.counts[id] / d.total) * Math.PI * 2;
      g.beginPath();
      g.strokeStyle = EMO_META[id].color;
      g.lineWidth = 56;
      g.arc(250, 420, 150, a0, a1);
      g.stroke();
      a0 = a1;
    });
    const dom = EMO_META[d.dominant] || EMO_META.neutral;
    g.fillStyle = dom.color;
    g.font = '700 72px "Noto Serif SC",serif';
    g.textAlign = "center";
    g.fillText(dom.zh, 250, 440);
    g.textAlign = "left";
    let y = 220;
    EMO_ORDER.filter((id) => d.counts[id]).sort((a, b) => d.counts[b] - d.counts[a]).forEach((id) => {
      const pct = d.counts[id] / d.total;
      g.fillStyle = EMO_META[id].color;
      g.font = '700 26px "Microsoft YaHei",sans-serif';
      g.fillText(EMO_META[id].name, 520, y);
      g.fillStyle = "rgba(255,255,255,0.12)";
      g.fillRect(620, y - 20, 380, 22);
      g.fillStyle = EMO_META[id].color;
      g.fillRect(620, y - 20, 380 * pct, 22);
      g.fillStyle = "#fff";
      g.font = '400 20px "Microsoft YaHei",sans-serif';
      g.fillText(`${Math.round(pct * 100)}% · ${fmtDur((d.seconds || {})[id])}`, 1012, y - 2);
      y += 50;
    });
    g.fillStyle = "rgba(255,255,255,0.8)";
    g.font = '700 22px "Microsoft YaHei",sans-serif';
    g.fillText("播放最多的歌", 520, y + 30);
    g.font = '400 20px "Microsoft YaHei",sans-serif';
    (d.top_songs || []).slice(0, 4).forEach((s, i) => g.fillText(`${i + 1}. ${s.title} · ${s.n} 次`, 520, y + 66 + i * 32));
    const a = document.createElement("a");
    a.download = `课堂情绪统计-${new Date().toISOString().slice(0, 10)}.png`;
    a.href = cv.toDataURL("image/png");
    a.click();
  }

  function open() {
    const dlg = $("#stats-dialog");
    if (!dlg) return;
    if (!dlg.open) dlg.showModal();
    load();
  }

  document.addEventListener("DOMContentLoaded", () => {
    const btn = $("#btn-stats");
    if (btn) btn.addEventListener("click", open);
    document.querySelectorAll("[data-stats-range]").forEach((b) =>
      b.addEventListener("click", () => {
        range = b.dataset.statsRange;
        document.querySelectorAll("[data-stats-range]").forEach((x) => x.classList.toggle("is-on", x === b));
        load();
      })
    );
    const png = $("#btn-stats-png");
    if (png) png.addEventListener("click", exportPng);
    const pr = $("#btn-stats-print");
    if (pr) pr.addEventListener("click", () => window.print());
    const close = $("#btn-stats-close");
    if (close) close.addEventListener("click", () => $("#stats-dialog").close());
  });
  window.EmoStats = { open, load };
})();
