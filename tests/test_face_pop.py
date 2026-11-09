# -*- coding: utf-8 -*-
"""弹出人脸窗与主页联动：

1. 先弹窗、再在主页顶栏打开「实时检测」→ 人脸窗开始定时识别
2. 人脸窗的表情同步到主页右侧（情绪字 / 情绪脸），并自动换歌
3. 画面里表情变化（喜悦 ↔ 惊讶循环）→ 主页歌单跟着切换，记录切换耗时
4. 主页「识别此刻」→ 由人脸窗截帧识别
5. 主页关闭实时检测 → 人脸窗同步关闭；关窗后主页恢复

需要服务已启动（EMOTUNE_BASE，默认 http://127.0.0.1:5000）。
"""
from __future__ import annotations

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
TMP = Path(tempfile.mkdtemp(prefix="emotune-pop-"))
fails = 0


def chk(name, ok, detail=""):
    global fails
    print(("[PASS] " if ok else "[FAIL] ") + name + (f" — {detail}" if detail else ""), flush=True)
    if not ok:
        fails += 1


def frame(name: str) -> bytes:
    img = cv2.imdecode(np.fromfile(str(ROOT / "static" / "demo" / name), np.uint8), 1)
    img = cv2.resize(img, (720, 720))
    canvas = np.full((720, 1280, 3), 60, np.uint8)
    canvas[:, 280:1000] = img
    return cv2.imencode(".jpg", canvas, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tobytes()


def make_cam() -> Path:
    # 约 30 帧/秒：喜悦 6 秒 → 惊讶 6 秒，循环
    path = TMP / "pop.mjpeg"
    path.write_bytes(frame("happy.jpg") * 180 + frame("surprise.jpg") * 180)
    return path


def main() -> int:
    cam = make_cam()
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--mute-audio",
                                    "--autoplay-policy=no-user-gesture-required", "--no-proxy-server",
                                    f"--use-file-for-fake-video-capture={cam}"])
        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.add_init_script("localStorage.setItem('emotune-voice','0'); localStorage.setItem('emotune-online','0'); localStorage.setItem('emotune-auto-live','0');")
        page.goto(BASE)
        page.wait_for_function("() => window.__emotune && window.__emotune.getState", timeout=15000)
        state = lambda: page.evaluate("() => window.__emotune.getState()")

        # 1) 实时检测关着时弹窗
        with ctx.expect_page() as info:
            page.click("#btn-face-pop")
        pop = info.value
        pop.on("pageerror", lambda e: errs.append("pop: " + str(e)))
        pop.wait_for_function("() => { const v = document.querySelector('#cam'); return v && v.videoWidth > 0; }", timeout=20000)
        chk("人脸窗打开并拿到摄像头", True)
        live0 = pop.evaluate("() => document.querySelector('#live-toggle').checked")

        # 2) 在主页顶栏打开实时检测 → 人脸窗跟着开
        page.click("#btn-detect")
        try:
            pop.wait_for_function("() => document.querySelector('#live-toggle').checked", timeout=5000)
            chk("主页打开实时检测 → 人脸窗同步开启", True, f"开启前 {live0}")
        except Exception:
            chk("主页打开实时检测 → 人脸窗同步开启", False)

        # 3) 右侧情绪与歌单跟上
        try:
            page.wait_for_function("() => ['喜','惊'].includes(document.querySelector('#emo-zh').textContent.trim())", timeout=20000)
            chk("右侧情绪更新", True, page.locator("#emo-zh").inner_text())
        except Exception:
            chk("右侧情绪更新", False, page.locator("#emo-zh").inner_text())
        try:
            page.wait_for_function("() => ['happy','surprise'].includes(window.__emotune.getState().lock)", timeout=20000)
            chk("自动按表情出歌", True, str(state().get("lock")))
        except Exception:
            chk("自动按表情出歌", False, str(state().get("lock")))

        # 4) 表情变化 → 换歌（记录切换耗时）
        seq, t_last, switches = [], time.time(), []
        end = time.time() + 40
        last = state().get("lock")
        while time.time() < end and len(switches) < 3:
            cur = state().get("lock")
            if cur != last:
                switches.append((last, cur))
                seq.append(cur)
                last = cur
            time.sleep(0.1)
        chk("表情变化后自动换歌（40 秒内至少 2 次）", len(switches) >= 2, " → ".join(f"{a}→{c}" for a, c in switches))
        ui_ok = page.evaluate("() => window.__emotune.getState().uiEmo")
        chk("右侧情绪脸 uiEmo 有值", ui_ok in ("happy", "surprise"), str(ui_ok))

        # 5) 主页识别此刻 → 人脸窗识别
        page.evaluate("() => { window.__popResult = 0; new BroadcastChannel('emotune-face').onmessage = (e) => { if (e.data && e.data.type === 'result' && e.data.source === 'camera') window.__popResult += 1; }; }")
        try:
            with pop.expect_response(lambda r: "/api/recognize?source=camera&" in r.url, timeout=15000):
                page.click("#btn-recognize")
            page.wait_for_function("() => window.__popResult > 0", timeout=8000)
            chk("主页「识别此刻」由人脸窗完成并回传", True)
        except Exception as exc:
            chk("主页「识别此刻」由人脸窗完成并回传", False, str(exc)[:120])
        chk("识别此刻后实时检测关闭（两边一致）", not state().get("live") and not pop.evaluate("() => document.querySelector('#live-toggle').checked"))

        # 6) 再开、再从主页关
        page.click("#btn-detect")
        pop.wait_for_function("() => document.querySelector('#live-toggle').checked", timeout=5000)
        page.click("#btn-detect")
        try:
            pop.wait_for_function("() => !document.querySelector('#live-toggle').checked", timeout=5000)
            chk("主页关闭实时检测 → 人脸窗同步关闭", True)
        except Exception:
            chk("主页关闭实时检测 → 人脸窗同步关闭", False)

        # 7) 关窗
        pop.close()
        try:
            page.wait_for_function("() => !window.__emotune.getState().facePop", timeout=5000)
            chk("关闭人脸窗后主页恢复", True)
        except Exception:
            chk("关闭人脸窗后主页恢复", False)
        chk("无脚本错误", not errs, str(errs[:3]))
        b.close()
    print("=== 结果 ===")
    print("全部通过" if not fails else f"未通过 {fails} 项")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
