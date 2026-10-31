# -*- coding: utf-8 -*-
"""实时捕捉 + 语音开：表情变了先稳住、再播报，播报一结束就换成该情绪的歌。"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright  # noqa: E402

from test_hold_ui import EMOTION, payload  # noqa: E402

BASE = os.environ.get("EMOTUNE_BASE", "http://127.0.0.1:5000")

# 用假的 speechSynthesis：记录播报内容和时刻，600ms 后触发 onend
FAKE_SPEECH = """
localStorage.setItem('emotune-voice','1');
window.__spoken = [];
Object.defineProperty(window, 'speechSynthesis', { configurable: true, value: {
  getVoices: () => [{ lang: 'zh-CN', name: 'fake' }],
  cancel: () => {},
  addEventListener: () => {},
  speak: (u) => {
    window.__spoken.push({ text: u.text, at: Date.now() });
    if (!u.text.trim()) return;
    setTimeout(() => { window.__spokenEnd = Date.now(); u.onend && u.onend(); }, 600);
  },
} });
Object.defineProperty(window, 'SpeechSynthesisUtterance', { configurable: true, value: function (t) { this.text = t; } });
"""


def main() -> int:
    fails = 0

    def chk(name, ok, detail=""):
        nonlocal fails
        print(("[PASS] " if ok else "[FAIL] ") + name + (f" — {detail}" if detail else ""))
        if not ok:
            fails += 1

    queue = ["surprise"]
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=[
                "--use-fake-ui-for-media-stream",
                "--use-fake-device-for-media-stream",
                "--autoplay-policy=no-user-gesture-required",
                "--mute-audio",
                "--no-proxy-server",
            ]
        )
        page = browser.new_context(viewport={"width": 1280, "height": 900}, locale="zh-CN").new_page()
        page.add_init_script(FAKE_SPEECH)

        def handle_recognize(route):
            body = payload(queue[0])
            route.fulfill(status=200, content_type="application/json; charset=utf-8",
                          body=json.dumps(body, ensure_ascii=False).encode("utf-8"))

        def handle_track(route):
            e = EMOTION[queue[0]]
            body = {
                "ok": True, "track": True, "emotion": e,
                "face": {"box": [90, 36, 210, 250], "score": 0.93, "image_size": [400, 300]},
                "faces": [{"box": [90, 36, 210, 250], "score": 0.93, "primary": True}],
                "elapsed_ms": 20,
            }
            route.fulfill(status=200, content_type="application/json; charset=utf-8",
                          body=json.dumps(body, ensure_ascii=False).encode("utf-8"))

        page.route("**/api/track**", handle_track)
        page.route("**/api/recognize**", handle_recognize)
        page.goto(BASE, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_function("() => window.__emotune && window.__emotune.getState", timeout=15000)
        page.click("#btn-cam")
        page.wait_for_function("() => window.__emotune.getState().live === true", timeout=15000)
        page.wait_for_function("() => window.__emotune.getState().lock === 'surprise'", timeout=15000)
        chk("先锁惊讶歌", page.evaluate("() => window.__emotune.getState().titles") == ["本草纲目"])

        queue[0] = "happy"
        t0 = time.time()
        page.wait_for_function("() => window.__emotune.getState().lock === 'happy'", timeout=20000)
        st = page.evaluate("() => window.__emotune.getState()")
        spoken = page.evaluate("() => window.__spoken.filter((x) => x.text.trim())")
        end_at = page.evaluate("() => window.__spokenEnd || 0")
        switched_at = page.evaluate("() => Date.now()")
        said_happy = any("喜悦" in x["text"] for x in spoken)
        chk("换歌前播报了喜悦", said_happy, str([x["text"] for x in spoken]))
        chk("播报后换成喜悦歌", st["titles"] == ["热爱105°C的你"], str(st["titles"]))
        gap = (switched_at - end_at) / 1000.0 if end_at else 99
        chk("播报结束后很快换歌（≤1.5 秒）", 0 <= gap <= 1.5, f"{gap:.2f}s")
        chk("表情变化到换歌总用时合理（≤12 秒，正常约 6 秒）", time.time() - t0 <= 12, f"{time.time() - t0:.1f}s")
        browser.close()

    print("=== 结果 ===")
    print("全部通过" if not fails else f"未通过 {fails} 项")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
