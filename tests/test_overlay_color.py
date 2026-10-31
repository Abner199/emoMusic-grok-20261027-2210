# -*- coding: utf-8 -*-
"""Verify live face-box and HUD text colors follow the current emotion."""
from __future__ import annotations

import os

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(r"C:\Users\niewe\AppData\Local\Temp\emotune-overlay-color")
BASE = os.environ.get("EMOTUNE_BASE", "http://127.0.0.1:5000")

EMOS = [
    ("happy", "喜", "喜悦", (255, 212, 0), "#ffd400"),
    ("angry", "怒", "愤怒", (224, 32, 32), "#e02020"),
    ("sad", "哀", "悲伤", (78, 115, 144), "#4e7390"),
    ("fear", "惧", "恐惧", (107, 45, 145), "#6b2d91"),
    ("surprise", "惊", "惊讶", (255, 122, 24), "#ff7a18"),
    ("disgust", "厌", "厌恶", (111, 125, 50), "#6f7d32"),
    ("neutral", "中", "平静", (78, 198, 245), "#4ec6f5"),
]


def _rgb(css: str) -> tuple[int, int, int] | None:
    m = re.search(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", css or "")
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def _near(a, b, tol=18) -> bool:
    if not a or not b:
        return False
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def payload(emo_id: str) -> dict:
    row = next(item for item in EMOS if item[0] == emo_id)
    return {
        "ok": True,
        "track": True,
        "emotion": {
            "id": row[0],
            "zh": row[1],
            "name": row[2],
            "prob": 0.94,
            "color": row[4],
        },
        "face": {"box": [90, 36, 210, 250], "score": 0.93, "image_size": [400, 300]},
        "faces": [{"box": [90, 36, 210, 250], "score": 0.93, "primary": True}],
        "elapsed_ms": 18,
    }


def main() -> int:
    fails = 0
    queue = ["happy"]
    OUT.mkdir(exist_ok=True)

    def chk(name, cond, detail=""):
        nonlocal fails
        mark = "PASS" if cond else "FAIL"
        print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))
        if not cond:
            fails += 1

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--use-fake-ui-for-media-stream",
                "--use-fake-device-for-media-stream",
                "--autoplay-policy=no-user-gesture-required",
                "--mute-audio",
            ],
        )
        context = browser.new_context(viewport={"width": 1280, "height": 900}, locale="zh-CN")
        page = context.new_page()
        page.add_init_script("localStorage.setItem('emotune-voice','0'); localStorage.setItem('emotune-auto-live','0');")

        def handle_track(route):
            emo = queue[0] if queue else "neutral"
            route.fulfill(
                status=200,
                content_type="application/json; charset=utf-8",
                body=json.dumps(payload(emo), ensure_ascii=False).encode("utf-8"),
            )

        page.route("**/api/track**", handle_track)
        page.route(
            "**/api/recognize**",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json; charset=utf-8",
                body=json.dumps({"ok": True, "emotion": payload(queue[0])["emotion"], "face": {}, "recommendations": {"songs": []}}).encode("utf-8"),
            ),
        )
        page.goto(BASE, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_selector("#btn-cam")
        page.locator("#btn-cam").click()
        page.wait_for_function(
            "() => { const v = document.querySelector('#cam'); return v && v.readyState >= 2 && v.videoWidth > 0; }",
            timeout=12000,
        )
        page.wait_for_selector("#live-emo-hud", state="visible", timeout=8000)

        for emo_id, zh, name, rgb, hex_color in EMOS:
            queue[:] = [emo_id]
            page.wait_for_function(
                """(id) => {
                  const hud = document.querySelector('#live-emo-hud');
                  const st = window.__emotune && window.__emotune.getState();
                  return hud && hud.dataset.emo === id && st && st.overlay && st.overlay.id === id;
                }""",
                arg=emo_id,
                timeout=8000,
            )
            page.wait_for_timeout(700)  # 边框颜色有 280ms 渐变，等它走完再读
            info = page.evaluate(
                """(expected) => {
                  const [r, g, b] = expected;
                  const hud = document.querySelector('#live-emo-hud');
                  const zhEl = document.querySelector('#live-emo-zh');
                  const nameEl = document.querySelector('#live-emo-name');
                  const canvas = document.querySelector('#face-overlay');
                  const ctx = canvas.getContext('2d');
                  const { width, height } = canvas;
                  let hit = 0;
                  if (width > 8 && height > 8) {
                    const data = ctx.getImageData(0, 0, width, height).data;
                    for (let i = 0; i < data.length; i += 4) {
                      if (data[i + 3] < 180) continue;
                      if (Math.abs(data[i] - r) <= 36 && Math.abs(data[i + 1] - g) <= 36 && Math.abs(data[i + 2] - b) <= 36) {
                        hit += 1;
                        if (hit >= 80) break;
                      }
                    }
                  }
                  return {
                    emo: hud.dataset.emo,
                    zh: zhEl.textContent,
                    name: nameEl.textContent,
                    hudColor: getComputedStyle(hud).color,
                    zhColor: getComputedStyle(zhEl).color,
                    nameColor: getComputedStyle(nameEl).color,
                    border: getComputedStyle(hud).borderTopColor,
                    overlay: window.__emotune.getState().overlay,
                    hit,
                    width,
                    height,
                  };
                }""",
                rgb,
            )
            page.locator("#viewport").screenshot(path=str(OUT / f"{emo_id}.png"))
            chk(f"{name} HUD 文案", zh in info["zh"] and name in info["name"], f"{info['zh']} {info['name']}")
            chk(f"{name} HUD 文字色", _near(_rgb(info["zhColor"]), rgb) and _near(_rgb(info["nameColor"]), rgb), f"{info['zhColor']} / {info['nameColor']}")
            chk(f"{name} HUD 边框色", _near(_rgb(info["border"]), rgb), info["border"])
            overlay_hex = (info.get("overlay") or {}).get("color") or ""
            chk(f"{name} 画布记录色", overlay_hex.lower() == hex_color.lower(), overlay_hex)
            chk(f"{name} 人脸框像素色", info["hit"] >= 80, f"hits={info['hit']} size={info['width']}x{info['height']}")

        browser.close()

    print("=== 结果 ===")
    if fails:
        print(f"未通过 {fails} 项")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
