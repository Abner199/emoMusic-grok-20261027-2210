(() => {
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

  function fitScale(iw, ih, cssW, cssH, fit) {
    const sx = cssW / iw;
    const sy = cssH / ih;
    return fit === "contain" ? Math.min(sx, sy) : Math.max(sx, sy);
  }

  function mapBox(box, imageSize, sized, mirror, fit) {
    if (!box || !imageSize || !sized) return null;
    let [x, y, bw, bh] = box.map(Number);
    const [iw, ih] = imageSize.map(Number);
    if (!iw || !ih || !bw || !bh) return null;
    if (mirror) x = iw - x - bw;
    const scale = fitScale(iw, ih, sized.cssW, sized.cssH, fit);
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

  function mapPoint(pt, imageSize, sized, mirror, fit) {
    if (!pt || !imageSize || !sized) return null;
    let x = Number(Array.isArray(pt) ? pt[0] : pt.x);
    let y = Number(Array.isArray(pt) ? pt[1] : pt.y);
    const [iw, ih] = imageSize.map(Number);
    if (!iw || !ih || !Number.isFinite(x) || !Number.isFinite(y)) return null;
    if (mirror) x = iw - x;
    const scale = fitScale(iw, ih, sized.cssW, sized.cssH, fit);
    const dw = iw * scale;
    const dh = ih * scale;
    const ox = (sized.cssW - dw) / 2;
    const oy = (sized.cssH - dh) / 2;
    return {
      x: (ox + x * scale) * sized.dpr,
      y: (oy + y * scale) * sized.dpr,
    };
  }

  function indexPoints(pts) {
    const byId = Object.create(null);
    (pts || []).forEach((p) => {
      if (p && p.id) byId[p.id] = p;
    });
    return byId;
  }

  function dist(a, b) {
    if (!a || !b) return 0;
    return Math.hypot(a.x - b.x, a.y - b.y);
  }

  function sampleQuad(a, c, b, n) {
    const out = [];
    if (!a || !b) return out;
    const ctrl = c || { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
    for (let i = 0; i <= n; i += 1) {
      const t = i / n;
      const u = 1 - t;
      out.push({
        x: u * u * a.x + 2 * u * t * ctrl.x + t * t * b.x,
        y: u * u * a.y + 2 * u * t * ctrl.y + t * t * b.y,
      });
    }
    return out;
  }

  function schematicFromBox(box) {
    if (!box) return {};
    const x = box.x;
    const y = box.y;
    const w = box.w;
    const h = box.h;
    return {
      le: { x: x + w * 0.32, y: y + h * 0.4 },
      re: { x: x + w * 0.68, y: y + h * 0.4 },
      nose: { x: x + w * 0.5, y: y + h * 0.58 },
      ml: { x: x + w * 0.36, y: y + h * 0.74 },
      mr: { x: x + w * 0.64, y: y + h * 0.74 },
      lb: { x: x + w * 0.3, y: y + h * 0.26 },
      rb: { x: x + w * 0.7, y: y + h * 0.26 },
    };
  }

  function featurePts(item) {
    const byId = indexPoints(item.points || []);
    const fallback = schematicFromBox(item.box);
    const pick = (id) => byId[id] || fallback[id] || null;
    return {
      le: pick("le"),
      re: pick("re"),
      nose: pick("nose"),
      ml: pick("ml"),
      mr: pick("mr"),
      lb: pick("lb"),
      rb: pick("rb"),
    };
  }

  function cueChip(cue) {
    const raw = `${cue.symbol || ""} ${cue.text || ""} ${cue.hint || ""}`;
    let au = String(cue.symbol || "").replace(/≈/g, "").trim();
    let text = String(cue.text || cue.hint || cue.zh || "").trim();
    if (/AU12/i.test(raw) || /上扬|喜悦/.test(raw)) {
      au = "AU12";
      text = "嘴角上扬";
    } else if (/AU15/i.test(raw) || /偏低|低落|下垂/.test(raw)) {
      au = "AU15";
      text = "嘴角下垂";
    } else if (/AU27/i.test(raw) || /张开|张口|惊讶/.test(raw)) {
      au = "AU27";
      text = "张口";
    } else if (/AU1\/2|AU1/i.test(raw) || /上提|挑眉/.test(raw)) {
      au = "AU1/2";
      text = "挑眉";
    } else if (/AU4/i.test(raw) || /皱眉|眉区偏低|压眉/.test(raw)) {
      au = "AU4";
      text = /压/.test(raw) ? "压眉" : "皱眉";
    } else if (/IOD|眼/.test(raw)) {
      au = /倾/.test(raw) ? "AU4" : "AU5";
      text = /倾/.test(raw) ? "侧倾" : "瞪大眼睛";
    } else if (/抿嘴|偏紧/.test(raw)) {
      au = "AU24";
      text = "抿嘴";
    }
    if (!au) au = cue.zh || "AU";
    if (!text) text = cue.zh || "";
    return { au, text, part: cue.part || "" };
  }

  function isIdleChip(chip) {
    return /平稳|水平|中等|稳定/.test(`${chip.au} ${chip.text}`);
  }

  function extraChipsFromEmo(emo) {
    const id = (emo && emo.id) || "";
    if (id === "surprise") {
      return [
        { au: "AU1/2", text: "挑眉", part: "brow" },
        { au: "AU5", text: "瞪大眼睛", part: "eye" },
        { au: "AU27", text: "张口", part: "mouth" },
      ];
    }
    if (id === "happy") return [{ au: "AU12", text: "嘴角上扬", part: "mouth" }];
    if (id === "sad") {
      return [
        { au: "AU4", text: "皱眉", part: "brow" },
        { au: "AU15", text: "嘴角下垂", part: "mouth" },
      ];
    }
    if (id === "angry") {
      return [
        { au: "AU4", text: "压眉", part: "brow" },
        { au: "AU4", text: "皱眉", part: "brow-r" },
      ];
    }
    if (id === "fear") {
      return [
        { au: "AU1/2", text: "挑眉", part: "brow" },
        { au: "AU5", text: "瞪大眼睛", part: "eye" },
      ];
    }
    if (id === "disgust") {
      return [
        { au: "AU4", text: "皱眉", part: "brow" },
        { au: "AU15", text: "嘴角下垂", part: "mouth" },
      ];
    }
    return [];
  }

  function paintBox(ctx, item, color, style) {
    const box = item.box;
    if (!box) return;
    const radius = Math.max(6, box.w * 0.035);
    ctx.save();
    roundRectPath(ctx, box.x, box.y, box.w, box.h, radius);
    if (style.fill) {
      ctx.fillStyle = hexToRgba(color, item.primary ? 0.07 : 0.03);
      ctx.fill();
    }
    ctx.lineWidth = item.primary ? Math.max(2.6, box.w * 0.014) : 1.6;
    ctx.strokeStyle = color;
    ctx.shadowColor = item.primary ? hexToRgba(color, 0.45) : "transparent";
    ctx.shadowBlur = item.primary ? 8 : 0;
    ctx.stroke();
    ctx.shadowBlur = 0;
    if (style.brackets && item.primary) {
      ctx.lineWidth = Math.max(3, box.w * 0.016);
      drawCornerBrackets(ctx, box.x, box.y, box.w, box.h, color);
    }
    ctx.restore();
  }

  function paintDotList(ctx, dots, color) {
    ctx.save();
    dots.forEach((p) => {
      const r = p.r || 3;
      ctx.beginPath();
      ctx.fillStyle = p.soft ? hexToRgba(color, 0.78) : color;
      ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
      ctx.fill();
    });
    ctx.restore();
  }

  function paintDots(ctx, item, color) {
    const pts = item.points || [];
    const box = item.box;
    const boxW = (box && box.w) || 120;
    const rKey = Math.max(3.4, boxW * 0.016);
    const rSub = Math.max(2.1, boxW * 0.01);
    const dots = [];
    const add = (p, r, soft) => {
      if (p && Number.isFinite(p.x) && Number.isFinite(p.y)) dots.push({ x: p.x, y: p.y, r, soft: !!soft });
    };
    if (box) {
      const cx = box.x + box.w * 0.5;
      const leftCheek = { x: box.x + box.w * 0.08, y: box.y + box.h * 0.42 };
      const chin = { x: cx, y: box.y + box.h * 0.97 };
      const rightCheek = { x: box.x + box.w * 0.92, y: box.y + box.h * 0.42 };
      const leftTemple = { x: box.x + box.w * 0.12, y: box.y + box.h * 0.16 };
      const rightTemple = { x: box.x + box.w * 0.88, y: box.y + box.h * 0.16 };
      sampleQuad(leftTemple, { x: box.x + box.w * 0.04, y: box.y + box.h * 0.28 }, leftCheek, 4).forEach((p) => add(p, rSub, true));
      sampleQuad(leftCheek, { x: box.x + box.w * 0.1, y: box.y + box.h * 0.86 }, chin, 8).forEach((p) => add(p, rSub, true));
      sampleQuad(chin, { x: box.x + box.w * 0.9, y: box.y + box.h * 0.86 }, rightCheek, 8).forEach((p) => add(p, rSub, true));
      sampleQuad(rightCheek, { x: box.x + box.w * 0.96, y: box.y + box.h * 0.28 }, rightTemple, 4).forEach((p) => add(p, rSub, true));
    }
    const f = featurePts(item);
    const iod = dist(f.le, f.re) || boxW * 0.28;
    if (f.lb && f.le) {
      const outer = { x: f.lb.x - iod * 0.2, y: f.lb.y + iod * 0.02 };
      const inner = { x: f.le.x + iod * 0.1, y: f.lb.y + iod * 0.05 };
      sampleQuad(outer, { x: f.lb.x, y: f.lb.y - iod * 0.1 }, inner, 5).forEach((p) => add(p, rSub, true));
    }
    if (f.rb && f.re) {
      const outer = { x: f.rb.x + iod * 0.2, y: f.rb.y + iod * 0.02 };
      const inner = { x: f.re.x - iod * 0.1, y: f.rb.y + iod * 0.05 };
      sampleQuad(outer, { x: f.rb.x, y: f.rb.y - iod * 0.1 }, inner, 5).forEach((p) => add(p, rSub, true));
    }
    ["le", "re"].forEach((id) => {
      const eye = f[id];
      if (!eye) return;
      const ew = iod * 0.2;
      const eh = iod * 0.11;
      for (let i = 0; i < 8; i += 1) {
        const t = (i / 8) * Math.PI * 2;
        add({ x: eye.x + ew * Math.cos(t), y: eye.y + eh * Math.sin(t) }, rSub, true);
      }
    });
    if (f.le && f.re && f.nose) {
      add({ x: (f.le.x + f.re.x) / 2, y: (f.le.y + f.re.y) / 2 + iod * 0.1 }, rSub, true);
      add({ x: f.nose.x - iod * 0.12, y: f.nose.y + iod * 0.03 }, rSub, true);
      add({ x: f.nose.x + iod * 0.12, y: f.nose.y + iod * 0.03 }, rSub, true);
    }
    if (f.ml && f.mr) {
      const mid = { x: (f.ml.x + f.mr.x) / 2, y: (f.ml.y + f.mr.y) / 2 };
      const open = f.nose ? Math.max(iod * 0.05, (mid.y - f.nose.y) * 0.12) : iod * 0.08;
      sampleQuad(f.ml, { x: mid.x, y: mid.y + open }, f.mr, 6).forEach((p) => add(p, rSub, true));
      sampleQuad(f.ml, { x: mid.x, y: mid.y - open * 0.4 }, f.mr, 5).forEach((p) => add(p, rSub, true));
    }
    pts.forEach((p) => add(p, p.inferred ? rSub + 0.4 : rKey, !!p.inferred));
    paintDotList(ctx, dots, color);
  }

  function paintMesh(ctx, item, color) {
    const f = featurePts(item);
    const iod = dist(f.le, f.re) || ((item.box && item.box.w) || 120) * 0.28;
    const lw = Math.max(1.8, iod * 0.048);
    ctx.save();
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.strokeStyle = color;
    ctx.lineWidth = lw;
    ctx.shadowColor = hexToRgba(color, 0.4);
    ctx.shadowBlur = 5;

    const curve = (a, c, b) => {
      if (!a || !b) return;
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      if (c) ctx.quadraticCurveTo(c.x, c.y, b.x, b.y);
      else ctx.lineTo(b.x, b.y);
      ctx.stroke();
    };

    if (f.lb && f.le) {
      const outer = { x: f.lb.x - iod * 0.18, y: f.lb.y + iod * 0.02 };
      const inner = { x: f.le.x + iod * 0.1, y: f.lb.y + (f.le.y - f.lb.y) * 0.28 };
      curve(outer, { x: (outer.x + inner.x) / 2, y: f.lb.y - iod * 0.12 }, inner);
    }
    if (f.rb && f.re) {
      const outer = { x: f.rb.x + iod * 0.18, y: f.rb.y + iod * 0.02 };
      const inner = { x: f.re.x - iod * 0.1, y: f.rb.y + (f.re.y - f.rb.y) * 0.28 };
      curve(outer, { x: (outer.x + inner.x) / 2, y: f.rb.y - iod * 0.12 }, inner);
    }
    if (f.le) {
      const w = iod * 0.22;
      curve({ x: f.le.x - w, y: f.le.y + w * 0.08 }, { x: f.le.x, y: f.le.y - w * 0.72 }, { x: f.le.x + w, y: f.le.y + w * 0.08 });
      curve({ x: f.le.x - w, y: f.le.y + w * 0.08 }, { x: f.le.x, y: f.le.y + w * 0.42 }, { x: f.le.x + w, y: f.le.y + w * 0.08 });
    }
    if (f.re) {
      const w = iod * 0.22;
      curve({ x: f.re.x - w, y: f.re.y + w * 0.08 }, { x: f.re.x, y: f.re.y - w * 0.72 }, { x: f.re.x + w, y: f.re.y + w * 0.08 });
      curve({ x: f.re.x - w, y: f.re.y + w * 0.08 }, { x: f.re.x, y: f.re.y + w * 0.42 }, { x: f.re.x + w, y: f.re.y + w * 0.08 });
    }
    if (f.le && f.re && f.nose) {
      ctx.beginPath();
      ctx.moveTo(f.le.x + iod * 0.08, f.le.y + iod * 0.18);
      ctx.lineTo(f.nose.x, f.nose.y);
      ctx.lineTo(f.re.x - iod * 0.08, f.re.y + iod * 0.18);
      ctx.stroke();
      const wing = iod * 0.13;
      ctx.beginPath();
      ctx.moveTo(f.nose.x - wing, f.nose.y + iod * 0.04);
      ctx.lineTo(f.nose.x + wing, f.nose.y + iod * 0.04);
      ctx.stroke();
    }
    if (f.ml && f.mr) {
      const mid = { x: (f.ml.x + f.mr.x) / 2, y: (f.ml.y + f.mr.y) / 2 };
      const open = f.nose ? Math.max(4, (mid.y - f.nose.y) * 0.12) : iod * 0.08;
      curve(f.ml, { x: mid.x, y: mid.y + open }, f.mr);
      curve(f.ml, { x: mid.x, y: mid.y - open * 0.35 }, f.mr);
    }
    ctx.restore();
  }

  function paintChip(ctx, x, y, au, text, color, canvas) {
    const fontPx = Math.max(11, Math.min(15, (canvas && canvas.width ? canvas.width : 640) * 0.014));
    ctx.save();
    ctx.font = `700 ${fontPx}px "Noto Sans SC","Microsoft YaHei",sans-serif`;
    ctx.textBaseline = "middle";
    const label = `${au} ${text}`.trim();
    const padX = 8;
    const tw = ctx.measureText(label).width;
    const w = tw + padX * 2;
    const h = fontPx + 10;
    let px = x;
    let py = y;
    if (canvas) {
      if (px + w > canvas.width - 6) px = canvas.width - w - 6;
      if (px < 6) px = 6;
      if (py < 6) py = 6;
      if (py + h > canvas.height - 6) py = canvas.height - h - 6;
    }
    roundRectPath(ctx, px, py, w, h, 6);
    ctx.fillStyle = "rgba(8,7,6,0.82)";
    ctx.fill();
    ctx.strokeStyle = hexToRgba(color, 0.45);
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.fillStyle = "#f4efe8";
    ctx.fillText(label, px + padX, py + h / 2);
    ctx.restore();
    return { w, h, x: px, y: py };
  }

  function paintAuChips(ctx, item, color, canvas) {
    const cues = item.cues || [];
    const f = featurePts(item);
    const box = item.box || { x: 12, y: 12, w: 120, h: 160 };
    const chips = [];
    const seen = new Set();
    const pushChip = (chip) => {
      const key = `${chip.au}|${chip.text}`;
      if (!chip.au || seen.has(key) || isIdleChip(chip)) return;
      seen.add(key);
      chips.push(chip);
    };
    cues.forEach((cue) => {
      const chip = cueChip(cue);
      pushChip(chip);
      if (chip.part === "brow" && chip.au === "AU4") {
        pushChip({ au: "AU4", text: chip.text === "皱眉" ? "压眉" : "皱眉", part: "brow-r" });
      }
    });
    if (!chips.length) extraChipsFromEmo(item.emo).forEach(pushChip);
    const placed = [];
    chips.forEach((chip) => {
      let x = box.x;
      let y = box.y;
      if (chip.part === "brow" && f.lb) {
        x = f.lb.x - 78;
        y = f.lb.y - 30;
      } else if ((chip.part === "brow-r" || chip.part === "brow") && f.rb) {
        x = f.rb.x + 8;
        y = f.rb.y - 30;
      } else if (chip.part === "eye" && f.re) {
        x = f.re.x + 18;
        y = f.re.y - 6;
      } else if (chip.part === "mouth" && f.ml && f.mr) {
        x = (f.ml.x + f.mr.x) / 2 - 52;
        y = Math.max(f.ml.y, f.mr.y) + 14;
      } else {
        x = box.x + box.w + 8;
        y = box.y + placed.length * 28;
      }
      placed.push(paintChip(ctx, x, y, chip.au, chip.text, color, canvas));
    });
  }

  function paintBadge(ctx, item, color, canvas, kind) {
    const box = item.box;
    if (!box) return;
    const emo = item.emo || {};
    const meta = EMO_META[emo.id] || {};
    const zhName = meta.name || emo.name || "";
    const pct = Math.round((emo.prob || 0) * 100);
    if (!zhName && !pct) return;
    const bar = kind === "bar";
    const label = bar
      ? [zhName, pct ? `${pct}%` : "", pct ? "✓" : ""].filter(Boolean).join(" ")
      : [zhName, pct ? `${pct}%` : ""].filter(Boolean).join(" ");
    if (!label) return;
    const fontPx = Math.max(13, Math.min(22, box.w * (bar ? 0.11 : 0.09)));
    ctx.save();
    ctx.font = `700 ${fontPx}px "Noto Sans SC","Microsoft YaHei",sans-serif`;
    ctx.textBaseline = "middle";
    const padX = bar ? 14 : 10;
    const tw = ctx.measureText(label).width;
    const w = Math.min(box.w + 8, tw + padX * 2);
    const h = fontPx + (bar ? 12 : 10);
    let px = bar ? box.x + (box.w - w) / 2 : box.x + 6;
    let py = bar ? box.y - h * 0.42 : box.y - h - 6;
    if (py < 4) py = box.y + 4;
    if (canvas && px + w > canvas.width - 4) px = Math.max(4, canvas.width - w - 4);
    if (px < 4) px = 4;
    roundRectPath(ctx, px, py, w, h, bar ? 8 : h / 2);
    if (bar) {
      ctx.fillStyle = color;
      ctx.fill();
      ctx.fillStyle = "rgba(18,12,8,0.92)";
    } else {
      ctx.fillStyle = "rgba(246,236,220,0.92)";
      ctx.fill();
      ctx.strokeStyle = hexToRgba(color, 0.85);
      ctx.lineWidth = 1.2;
      ctx.stroke();
      ctx.fillStyle = color;
    }
    ctx.fillText(label, px + (w - tw) / 2, py + h / 2);
    ctx.restore();
  }

  function paintFaces(ctx, mapped, opts) {
    const mode = (opts && opts.mode) || "overlay";
    const canvas = (opts && opts.canvas) || ctx.canvas;
    if (!ctx || mode === "off") return;
    (mapped || []).forEach((item) => {
      if (!item || !item.box) return;
      const emo = item.emo || {};
      const color = emoHex(emo.id || "idle", emo.color);
      ctx.save();
      if (mode === "mesh") {
        paintBox(ctx, item, color, { fill: false, brackets: false });
        paintMesh(ctx, item, color);
        paintBadge(ctx, item, color, canvas, "chip");
      } else {
        paintBox(ctx, item, color, { fill: true, brackets: false });
        paintDots(ctx, item, color);
        if (item.primary) paintAuChips(ctx, item, color, canvas);
        paintBadge(ctx, item, color, canvas, "bar");
      }
      ctx.restore();
    });
  }

  window.EmoTuneDraw = {
    EMO_META,
    emoHex,
    hexToRgba,
    roundRectPath,
    drawCornerBrackets,
    mapBox,
    mapPoint,
    paintFaces,
    paintDots,
    paintMesh,
    paintAuChips,
    paintBox,
  };
})();
