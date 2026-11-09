/* 浏览器端逐帧跟脸：服务器每隔一段时间给出准确的人脸框（但拍下那一刻到结果回来有延迟），
 * 这里在两次结果之间用缩小灰度图做模板匹配，每帧算出每张脸实际移动了多少，
 * 并把“拍下那一刻 → 现在”这段时间里脸的位移补到服务器框上。电脑越慢、网络越慢，效果越明显。
 *
 * 用法：
 *   const tr = EmoTuneTrack.create(videoEl);
 *   tr.sample();                               // 每个动画帧调用（内部限制约 30 次/秒）
 *   const shifts = tr.anchor(vboxes, t0);      // 服务器结果回来：vboxes 为视频像素坐标 [x,y,w,h]，t0 为截帧时刻
 *   tr.delta(i)                                // 第 i 张脸当前应平移的量 {dx,dy}（视频像素），相对服务器框
 */
(function () {
  "use strict";

  const SMALL_W = 320; // 缩小图宽度：320 宽时 1280 视频里 1 格约 4 像素
  const MAX_TARGETS = 6; // 最多逐帧跟 6 张脸（按面积），其余靠服务器结果
  const MIN_GAP_MS = 30;
  const HIST_MS = 2000;

  function create(video) {
    const cv = document.createElement("canvas");
    const ctx = cv.getContext("2d", { willReadFrequently: true });
    let gray = null;
    let sw = 0;
    let sh = 0;
    let scale = 1; // 视频像素 → 缩小图像素
    let lastAt = 0;
    let targets = [];
    let nSamples = 0;

    // 把视频（或截帧画布）缩到 SMALL_W 宽的灰度图
    function toGray(src, out) {
      const vw = src.videoWidth || src.width;
      const vh = src.videoHeight || src.height;
      if (!vw || !vh || (src.readyState !== undefined && src.readyState < 2)) return null;
      const w = SMALL_W;
      const h = Math.max(8, Math.round((vh * SMALL_W) / vw));
      if (cv.width !== w || cv.height !== h) {
        cv.width = w;
        cv.height = h;
      }
      try {
        ctx.drawImage(src, 0, 0, w, h);
        const px = ctx.getImageData(0, 0, w, h).data;
        const g = out && out.length === w * h ? out : new Float32Array(w * h);
        for (let i = 0, j = 0; i < g.length; i += 1, j += 4) {
          g[i] = px[j] * 0.299 + px[j + 1] * 0.587 + px[j + 2] * 0.114;
        }
        return { g, w, h };
      } catch {
        return null;
      }
    }

    function grab() {
      const r = toGray(video, gray);
      if (!r) return false;
      gray = r.g;
      sw = r.w;
      sh = r.h;
      scale = SMALL_W / video.videoWidth;
      return true;
    }

    // 取脸中部 70% 区域做模板，最多约 24×24 个采样点；减去均值，抗明暗变化
    function makeTemplate(cx, cy, bw, bh, src) {
      const img = src || gray;
      const tw = Math.max(6, bw * 0.7);
      const th = Math.max(6, bh * 0.7);
      const step = Math.max(1, Math.round(Math.max(tw, th) / 24));
      const nx = Math.max(3, Math.floor(tw / step));
      const ny = Math.max(3, Math.floor(th / step));
      const ox = Math.round(cx - (nx * step) / 2);
      const oy = Math.round(cy - (ny * step) / 2);
      if (ox < 0 || oy < 0 || ox + nx * step >= sw || oy + ny * step >= sh) return null;
      const vals = new Float32Array(nx * ny);
      let sum = 0;
      for (let y = 0; y < ny; y += 1) {
        for (let x = 0; x < nx; x += 1) {
          const v = img[(oy + y * step) * sw + ox + x * step];
          vals[y * nx + x] = v;
          sum += v;
        }
      }
      const mean = sum / vals.length;
      let energy = 0;
      for (let i = 0; i < vals.length; i += 1) {
        vals[i] -= mean;
        energy += Math.abs(vals[i]);
      }
      if (energy / vals.length < 2.5) return null; // 太平（无纹理）：没法可靠匹配
      return { vals, nx, ny, step, dx0: ox - cx, dy0: oy - cy };
    }

    function cost(t, cx, cy, limit) {
      const ox = Math.round(cx + t.dx0);
      const oy = Math.round(cy + t.dy0);
      if (ox < 0 || oy < 0 || ox + t.nx * t.step >= sw || oy + t.ny * t.step >= sh) return Infinity;
      let sum = 0;
      for (let y = 0; y < t.ny; y += 1) {
        const row = (oy + y * t.step) * sw + ox;
        for (let x = 0; x < t.nx; x += 1) sum += gray[row + x * t.step];
      }
      const mean = sum / (t.nx * t.ny);
      let sad = 0;
      for (let y = 0; y < t.ny; y += 1) {
        const row = (oy + y * t.step) * sw + ox;
        const base = y * t.nx;
        for (let x = 0; x < t.nx; x += 1) {
          sad += Math.abs(gray[row + x * t.step] - mean - t.vals[base + x]);
        }
        if (sad > limit) return Infinity;
      }
      return sad;
    }

    function track(tg, wideMs) {
      const t = tg.tpl;
      // 平时每帧最多移动约 0.6 个脸宽；刚拿到服务器结果时，按“截帧以来过了多久”放宽
      // （按每秒最多走 1.2 个画面宽估算，最多搜到画面宽的 60%）
      let r = Math.max(6, Math.round(tg.bw * 0.6));
      if (wideMs) r = Math.max(r, Math.round(tg.bw * 1.5), Math.min(sw * 0.6, (wideMs / 1000) * sw * 1.2));
      r = Math.round(r);
      const st = r > 40 ? 3 : 2; // 人脸模板只在 2–3 格内才对得上，粗搜步长不能再大
      let best = cost(t, tg.cx, tg.cy, Infinity);
      let bx = tg.cx;
      let by = tg.cy;
      // 由粗到细：4 格 → 2 格 → 1 格
      const pass = (cx0, cy0, rad, st) => {
        for (let dy = -rad; dy <= rad; dy += st) {
          for (let dx = -rad; dx <= rad; dx += st) {
            if (!dx && !dy) continue;
            const c = cost(t, cx0 + dx, cy0 + dy, best);
            if (c < best) {
              best = c;
              bx = cx0 + dx;
              by = cy0 + dy;
            }
          }
        }
      };
      pass(tg.cx, tg.cy, r, st);
      pass(bx, by, st, 1);
      const per = best / t.vals.length;
      tg.lastPer = Math.round(per * 10) / 10;
      tg.lastMove = [bx - tg.cx, by - tg.cy];
      // 匹配太差（被挡住、转头、离开）：不动，等服务器下一次结果
      if (!Number.isFinite(per) || per > Math.max(14, tg.ref * 2.2)) {
        tg.lost += 1;
        return;
      }
      tg.lost = 0;
      tg.ref = tg.ref * 0.9 + per * 0.1;
      tg.cx = bx;
      tg.cy = by;
    }

    function push(tg, now) {
      tg.hist.push([now, tg.cx, tg.cy]);
      while (tg.hist.length > 2 && now - tg.hist[0][0] > HIST_MS) tg.hist.shift();
    }

    function posAt(tg, t) {
      const h = tg.hist;
      if (!h.length) return [tg.cx, tg.cy];
      if (t <= h[0][0]) return [h[0][1], h[0][2]];
      for (let i = h.length - 1; i >= 0; i -= 1) {
        if (h[i][0] <= t) {
          const a = h[i];
          const b = h[i + 1];
          if (!b) return [a[1], a[2]];
          const k = (t - a[0]) / Math.max(1, b[0] - a[0]);
          return [a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k];
        }
      }
      return [h[0][1], h[0][2]];
    }

    function sample(force) {
      const now = performance.now();
      if (!force && now - lastAt < MIN_GAP_MS) return false;
      if (!targets.length && !force) return false;
      if (!grab()) return false;
      lastAt = now;
      nSamples += 1;
      targets.forEach((tg) => {
        if (tg.tpl) track(tg);
        push(tg, now);
      });
      return true;
    }

    function iou(a, b) {
      const x1 = Math.max(a[0], b[0]);
      const y1 = Math.max(a[1], b[1]);
      const x2 = Math.min(a[0] + a[2], b[0] + b[2]);
      const y2 = Math.min(a[1] + a[3], b[1] + b[3]);
      const inter = Math.max(0, x2 - x1) * Math.max(0, y2 - y1);
      const u = a[2] * a[3] + b[2] * b[3] - inter;
      return u > 0 ? inter / u : 0;
    }

    /* 服务器结果到了：vboxes 为截帧时刻（t0）的人脸框（视频像素）。
     * 与已有跟踪目标配对，补上 t0 → 现在 的位移，再以当前画面重建模板。 */
    function anchor(vboxes, t0, shot) {
      const now = performance.now();
      const fresh = grab();
      if (fresh) lastAt = now;
      // 模板取自“截帧那一刻”的画面：服务器框正好框在那张图的脸上，模板一定准
      const snap = fresh && shot ? toGray(shot, null) : null;
      const snapOk = !!(snap && snap.w === sw && snap.h === sh);
      const old = targets;
      const used = new Set();
      const order = vboxes
        .map((b, i) => ({ b, i }))
        .sort((p, q) => q.b[2] * q.b[3] - p.b[2] * p.b[3]);
      const next = new Array(vboxes.length).fill(null);
      order.forEach(({ b, i }, rank) => {
        const bw = b[2] * scale;
        const bh = b[3] * scale;
        const sx = (b[0] + b[2] / 2) * scale;
        const sy = (b[1] + b[3] / 2) * scale;
        let cx = sx;
        let cy = sy;
        let best = -1;
        let bestIou = 0.2;
        old.forEach((tg, k) => {
          if (used.has(k) || !tg) return;
          const [px, py] = posAt(tg, t0);
          const v = iou([px - tg.bw / 2, py - tg.bh / 2, tg.bw, tg.bh], [sx - bw / 2, sy - bh / 2, bw, bh]);
          if (v > bestIou) {
            bestIou = v;
            best = k;
          }
        });
        if (best >= 0) {
          used.add(best);
          const tg = old[best];
          const [px, py] = posAt(tg, t0);
          cx += tg.cx - px; // 截帧之后脸又走了多少（来自逐帧跟踪）
          cy += tg.cy - py;
        }
        if (best >= 0 && old[best].lost && old[best].sv) {
          // 上一个目标跟丢了：按服务器前后两次框的速度推算现在的位置作为搜索起点
          const v = old[best].sv;
          cx = sx + v[0] * (now - t0);
          cy = sy + v[1] * (now - t0);
        }
        const tg = { sx, sy, cx, cy, bw, bh, tpl: null, hist: [], ref: 6, lost: 0, t0 };
        if (best >= 0) {
          const o = old[best];
          const dt = t0 - (o.t0 || t0);
          if (dt > 20 && dt < 1500) {
            const vx = (sx - o.sx) / dt;
            const vy = (sy - o.sy) / dt;
            tg.sv = o.sv ? [o.sv[0] * 0.4 + vx * 0.6, o.sv[1] * 0.4 + vy * 0.6] : [vx, vy];
          }
        }
        next[i] = tg;
        if (rank >= MAX_TARGETS || !fresh || bw < 8) return; // 太小的脸纹理不够，交给服务器结果
        if (snapOk) {
          tg.tpl = makeTemplate(sx, sy, bw, bh, snap.g);
          if (tg.tpl) {
            const keep = [tg.cx, tg.cy];
            track(tg, Math.max(1, now - t0)); // 在当前画面里把这张脸找出来
            if (tg.lost) [tg.cx, tg.cy] = keep;
          }
        } else {
          tg.tpl = makeTemplate(cx, cy, bw, bh);
        }
        push(tg, now);
      });
      targets = next;
      return targets.map((_, i) => delta(i));
    }

    // 相对服务器框应平移的量（视频像素）
    function delta(i) {
      const tg = targets[i];
      if (!tg || !scale) return { dx: 0, dy: 0 };
      return { dx: (tg.cx - tg.sx) / scale, dy: (tg.cy - tg.sy) / scale };
    }

    function reset() {
      targets = [];
    }

    function debug() {
      return targets.map((t) => t && { per: t.lastPer, mv: t.lastMove, n: nSamples, lost: t.lost, ref: Math.round(t.ref * 10) / 10, cx: Math.round(t.cx), sx: Math.round(t.sx), tpl: !!t.tpl });
    }

    return { sample, anchor, delta, reset, debug, get count() { return targets.length; } };
  }

  window.EmoTuneTrack = { create };
})();
