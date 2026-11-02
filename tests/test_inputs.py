# -*- coding: utf-8 -*-
"""五种输入方式端到端：摄像头单人 / 多人大会堂、照片、本地视频、屏幕分享、弹出人脸窗。

需要服务已启动（EMOTUNE_BASE，默认 http://127.0.0.1:5000）。
视频用例要 imageio-ffmpeg（pip install imageio-ffmpeg）生成测试视频，没有就跳过。
"""
from __future__ import annotations

import glob
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("EMOTUNE_BASE", "http://127.0.0.1:5000")
TMP = Path(tempfile.mkdtemp(prefix="emotune-inputs-"))
fails = 0


def chk(name, ok, detail=""):
    global fails
    print(("[PASS] " if ok else "[FAIL] ") + name + (f" — {detail}" if detail else ""))
    if not ok:
        fails += 1


def demo(name: str) -> Path:
    return ROOT / "static" / "demo" / name


def make_mjpeg(img: np.ndarray, path: Path) -> Path:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    path.write_bytes(buf.tobytes() * 60)
    return path


def make_hall() -> np.ndarray:
    faces = [cv2.imdecode(np.fromfile(f, np.uint8), 1) for f in sorted(glob.glob(str(ROOT / "static/demo/[0-4][0-9]-*.jpg")))]
    hall = np.full((1080, 1920, 3), 40, np.uint8)
    k = 0
    for y, side in ((40, 180), (240, 150), (410, 120), (550, 96), (670, 80), (770, 64)):
        for i in range(10):
            x = i * 192 + (192 - side) // 2
            hall[y:y + side, x:x + side] = cv2.resize(faces[k % len(faces)], (side, side))
            k += 1
    return hall


def make_webm() -> Path | None:
    try:
        import imageio_ffmpeg

        ff = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None
    out = TMP / "faces.webm"
    h, s = TMP / "h.jpg", TMP / "s.jpg"
    h.write_bytes(demo("happy.jpg").read_bytes())
    s.write_bytes(demo("surprise.jpg").read_bytes())
    cmd = [ff, "-y", "-loglevel", "error", "-loop", "1", "-t", "5", "-i", str(h), "-loop", "1", "-t", "5", "-i", str(s),
           "-filter_complex", "[0:v]scale=640:640[a];[1:v]scale=640:640[b];[a][b]concat=n=2:v=1:a=0,format=yuv420p",
           "-c:v", "libvpx", "-b:v", "1M", str(out)]
    return out if subprocess.run(cmd).returncode == 0 and out.exists() else None


def launch(p, video_file: Path | None = None):
    args = ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--mute-audio",
            "--autoplay-policy=no-user-gesture-required", "--auto-select-desktop-capture-source=Entire screen", "--no-proxy-server"]
    if video_file:
        args.append(f"--use-file-for-fake-video-capture={video_file}")
    return p.chromium.launch(args=args)


def open_page(browser, extra=""):
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.add_init_script("localStorage.setItem('emotune-voice','0'); localStorage.setItem('emotune-online','0');" + extra)
    page.goto(BASE, wait_until="domcontentloaded", timeout=20000)
    page.wait_for_function("() => window.__emotune && window.__emotune.getState", timeout=15000)
    return page, errs


def set_face_mode(page, mode):
    page.click("#btn-settings")
    blk = page.locator('details[data-set="detect"]')
    if blk.get_attribute("open") is None:
        blk.locator("summary").click()
    page.click(f'[data-face-mode="{mode}"]')
    if page.locator("#settings-panel").is_visible():
        page.click("#btn-close-settings")


def main() -> int:
    face_cam = make_mjpeg(cv2.resize(cv2.imdecode(np.fromfile(str(demo("happy.jpg")), np.uint8), 1), (1280, 1280))[280:1000], TMP / "face.mjpeg")
    hall_cam = make_mjpeg(make_hall(), TMP / "hall.mjpeg")
    webm = make_webm()
    with sync_playwright() as p:
        # 1) 摄像头 · 单人：开摄像头自动实时检测、画框、认出喜悦并开始放歌
        b = launch(p, face_cam)
        page, errs = open_page(b)
        set_face_mode(page, "solo")
        page.click("#btn-cam")
        page.wait_for_function("() => window.__emotune.getState().live === true", timeout=20000)
        page.wait_for_function("() => window.__emotune.getState().lock === 'happy'", timeout=30000)
        drawn = page.evaluate("""() => { const c = document.querySelector('#face-overlay'); const d = c.getContext('2d').getImageData(0,0,c.width,c.height).data;
            for (let i = 3; i < d.length; i += 4) if (d[i]) return true; return false; }""")
        chk("摄像头·单人：自动实时检测并认出喜悦", True)
        chk("摄像头·单人：画出人脸框", drawn)
        page.wait_for_function("() => document.querySelector('#player-title').textContent !== '未播放'", timeout=20000)
        chk("摄像头·单人：自动放歌（代表曲）", page.locator("#player-title").inner_text() in ("小苹果", "热爱105°C的你", "你笑起来真好看"), page.locator("#player-title").inner_text())
        page.click("#btn-detect")
        page.wait_for_timeout(500)
        chk("实时检测开关：关掉后停止实时识别", page.evaluate("() => window.__emotune.getState().live") is False)
        chk("摄像头·单人：无脚本错误", not errs, str(errs[:2]))
        b.close()

        # 2) 摄像头 · 多人远场大会堂：框出几十张脸，右上角人数分布
        b = launch(p, hall_cam)
        page, errs = open_page(b, "localStorage.setItem('emotune-venue','large');")
        set_face_mode(page, "crowd")
        page.click("#btn-cam")
        page.wait_for_function("() => !document.querySelector('#crowd-stats').hidden", timeout=40000)
        page.wait_for_timeout(3000)
        txt = page.locator("#crowd-stats").inner_text()
        n = int("".join(ch for ch in txt.split("张脸")[0] if ch.isdigit()) or 0)
        chk("摄像头·大会堂：框出 ≥40 张脸并显示人数分布", n >= 40, txt.replace("\n", " | ")[:60])
        chk("摄像头·大会堂：无脚本错误", not errs, str(errs[:2]))
        b.close()

        # 3) 照片 · 双击示例：大图上画框，认对，进足迹
        b = launch(p)
        page, errs = open_page(b, "localStorage.setItem('emotune-auto-live','0');")
        page.click(".tab[data-mode='upload']")
        page.wait_for_selector("#demo-list button")
        n0 = page.evaluate("document.querySelectorAll('.trail-chip').length")
        page.locator("#demo-list button").nth(4).dblclick()
        page.wait_for_function(f"document.querySelectorAll('.trail-chip').length > {n0}", timeout=30000)
        chk("照片：认出惊讶", page.locator("#emo-zh").inner_text().strip() == "惊", page.locator("#emo-zh").inner_text())
        chk("照片：新足迹实时出现在最前（带日期时间）", page.locator(".trail-chip").first.locator(".trail-time").count() == 1)

        # 4) 本地视频：先喜悦后惊讶，实时检测跟着变
        if webm:
            page.click(".tab[data-mode='video']")
            page.set_input_files("#video-input", str(webm))
            page.wait_for_function("() => { const v = document.querySelector('#cam'); return v && v.readyState >= 2; }", timeout=15000)
            page.evaluate("document.querySelector('#live-toggle').checked = true; document.querySelector('#live-toggle').dispatchEvent(new Event('change', {bubbles: true}))")
            page.wait_for_function("() => window.__emotune.getState().lock === 'happy'", timeout=20000)
            chk("本地视频：前段认出喜悦", True)
            page.wait_for_function("() => window.__emotune.getState().lock === 'surprise'", timeout=25000)
            chk("本地视频：画面换成惊讶后跟着换", True)
        else:
            print("[SKIP] 本地视频：没有 imageio-ffmpeg，跳过")

        # 5) 屏幕分享：能拿到画面
        page.click(".tab[data-mode='screen']")
        page.click("#btn-screen")
        ok = True
        try:
            page.wait_for_function("() => { const v = document.querySelector('#cam'); return v && v.videoWidth > 0; }", timeout=15000)
        except Exception:
            ok = False
        chk("屏幕分享：拿到画面", ok)
        chk("照片 / 视频 / 屏幕：无脚本错误", not errs, str(errs[:2]))
        b.close()

        # 6) 弹出人脸窗：独立窗口检测，结果回到主页
        b = launch(p, face_cam)
        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.add_init_script("localStorage.setItem('emotune-voice','0'); localStorage.setItem('emotune-online','0');")
        page.goto(BASE)
        page.wait_for_function("() => window.__emotune && window.__emotune.getState", timeout=15000)
        with ctx.expect_page() as pop_info:
            page.click("#btn-face-pop")
        pop = pop_info.value
        pop.wait_for_function("() => { const v = document.querySelector('#cam'); return v && v.videoWidth > 0; }", timeout=20000)
        clean = pop.evaluate("() => getComputedStyle(document.querySelector('.face-top')).display === 'none'")
        chk("弹出人脸窗：只留画面（无顶栏）", clean)
        page.evaluate("() => {}")
        pop.evaluate("document.querySelector('#live-toggle').checked = true; document.querySelector('#live-toggle').dispatchEvent(new Event('change', {bubbles: true}))")
        try:
            page.wait_for_function("() => document.querySelector('#emo-zh').textContent.trim() === '喜'", timeout=30000)
            chk("弹出人脸窗：识别结果回到主页（喜悦）", True)
        except Exception:
            chk("弹出人脸窗：识别结果回到主页（喜悦）", False, page.locator("#emo-zh").inner_text())
        b.close()

    print("=== 结果 ===")
    print("全部通过" if not fails else f"未通过 {fails} 项")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
