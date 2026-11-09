# -*- coding: utf-8 -*-
"""实时框跟脸误差：模拟摄像头里一张脸左右来回移动，并把 /api/track 人为延迟（模拟慢电脑），
同时读取「此刻画面里真实的脸位置」与「程序认为的框位置」，比较平均 / 90% 误差（单位：脸宽的百分比）。

对比两种：浏览器逐帧跟脸（默认）与只靠服务器结果 + 速度外推（emotune-track-js=0）。
需要服务已启动（EMOTUNE_BASE，默认 http://127.0.0.1:5000）。参数：--delay 毫秒（默认 250）
"""
from __future__ import annotations

import math
import os
import sys
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("EMOTUNE_BASE", "http://127.0.0.1:5000")
TMP = Path(tempfile.mkdtemp(prefix="emotune-lag-"))
BG = 60
FACE = 240


def make_cam() -> Path:
    face = cv2.resize(cv2.imdecode(np.fromfile(str(ROOT / "static/demo/happy.jpg"), np.uint8), 1), (FACE, FACE))
    out = bytearray()
    n = 120  # 30 帧/秒 → 4 秒一个来回
    for i in range(n):
        x = int(520 + 380 * math.sin(2 * math.pi * i / n))
        img = np.full((720, 1280, 3), BG, np.uint8)
        img[240:240 + FACE, x:x + FACE] = face
        out += cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tobytes()
    path = TMP / "move.mjpeg"
    path.write_bytes(bytes(out))
    return path


TRUTH_JS = """() => {
  const v = document.querySelector('#cam');
  if (!v || !v.videoWidth) return null;
  const probe = window.__emotune.trackProbe();
  const c = document.createElement('canvas');
  c.width = v.videoWidth / 4; c.height = v.videoHeight / 4;
  const g = c.getContext('2d'); g.drawImage(v, 0, 0, c.width, c.height);
  const d = g.getImageData(0, 0, c.width, c.height).data;
  let x0 = 1e9, x1 = -1;
  for (let y = 0; y < c.height; y += 2) for (let x = 0; x < c.width; x += 1) {
    const i = (y * c.width + x) * 4;
    if (Math.abs(d[i] - %d) + Math.abs(d[i+1] - %d) + Math.abs(d[i+2] - %d) > 60) { if (x < x0) x0 = x; if (x > x1) x1 = x; }
  }
  if (x1 < 0 || !probe) return null;
  return { truth: (x0 + x1 + 1) * 2, est: probe.cx, tracker: probe.tracker, w: (x1 - x0 + 1) * 4 };
}""" % (BG, BG, BG)


def run(p, cam, delay_ms, use_js):
    b = p.chromium.launch(args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--mute-audio",
                                "--no-proxy-server", f"--use-file-for-fake-video-capture={cam}"])
    page = b.new_page(viewport={"width": 1440, "height": 900})
    page.add_init_script("localStorage.setItem('emotune-voice','0'); localStorage.setItem('emotune-online','0');"
                         f"localStorage.setItem('emotune-track-js','{'1' if use_js else '0'}');")

    def slow(route):
        time.sleep(delay_ms / 1000.0)
        route.continue_()

    page.route("**/api/track**", slow)
    page.goto(BASE)
    page.wait_for_function("() => window.__emotune && window.__emotune.getState", timeout=15000)
    page.click("#btn-cam")
    page.wait_for_function("() => { const v = document.querySelector('#cam'); return v && v.videoWidth > 0; }", timeout=20000)
    page.wait_for_function("() => window.__emotune.trackProbe()", timeout=20000)
    errs = []
    end = time.time() + 12
    while time.time() < end:
        r = page.evaluate(TRUTH_JS)
        if r and r["w"] > 100:
            errs.append(abs(r["est"] - r["truth"]) / FACE * 100 * (1280 / page.evaluate("document.querySelector('#cam').videoWidth")))
        page.wait_for_timeout(40)
    b.close()
    return errs


def main() -> int:
    delay = 250
    if "--delay" in sys.argv:
        delay = int(sys.argv[sys.argv.index("--delay") + 1])
    cam = make_cam()
    with sync_playwright() as p:
        on = run(p, cam, delay, True)
        off = run(p, cam, delay, False)
    def stat(e):
        return f"平均 {np.mean(e):.0f}% · 90% 分位 {np.percentile(e, 90):.0f}% 脸宽（{len(e)} 次采样）" if e else "无数据"
    print(f"服务器延迟 +{delay} ms，脸来回移动（最快约 600 像素/秒）")
    print("[浏览器逐帧跟脸] ", stat(on))
    print("[只靠服务器结果] ", stat(off))
    ok = bool(on) and bool(off) and np.mean(on) < np.mean(off) * 0.6 and np.percentile(on, 90) < 25
    print("[PASS]" if ok else "[FAIL]", "逐帧跟脸误差明显更小且 90% 分位 < 25% 脸宽")
    print("=== 结果 ===")
    print("全部通过" if ok else "未通过 1 项")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
