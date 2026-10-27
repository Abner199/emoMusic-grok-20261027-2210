# -*- coding: utf-8 -*-
"""Verify default online source, manual local toggle, and auto fallback."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5000"
OUT = Path(r"C:\Users\niewe\AppData\Local\Temp\emotune-online-source")
CROP = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"


def payload(mode: str) -> dict:
    local = {
        "id": "vocal-happy-01",
        "title": "热爱105°C的你",
        "artist": "阿肆",
        "album": "热爱105°C的你 - 单曲",
        "audio": "/api/audio/vocal-happy-01",
        "cover": "/static/covers/vocal-happy-01.jpg",
        "playable": True,
        "source": "local",
        "source_label": "本地曲库 · 歌曲试听",
        "downloadable": True,
    }
    online = {
        "id": "itunes-broken",
        "title": "在线热歌",
        "artist": "测试",
        "album": "在线",
        "audio": "/api/stream?u=https://example.invalid/nope.m4a",
        "cover": "/static/covers/vocal-happy-01.jpg",
        "playable": True,
        "source": "itunes",
        "source_label": "在线 · 苹果音乐",
        "downloadable": False,
    }
    songs = [online, online] if mode == "online" else [local]
    return {
        "ok": True,
        "emotion": "happy",
        "genre": "阳光蹦跳 · 开口就笑",
        "songs": songs,
        "local_count": 0 if mode == "online" else 1,
        "online_count": 1 if mode == "online" else 0,
        "providers": ["在线 · 苹果音乐"] if mode == "online" else [],
        "mode": "online" if mode == "online" else "local",
        "copy": "",
    }


def main() -> int:
    fails = 0
    OUT.mkdir(exist_ok=True)
    mode = {"online": True}

    def chk(name, cond, detail=""):
        nonlocal fails
        mark = "PASS" if cond else "FAIL"
        print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))
        if not cond:
            fails += 1

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--autoplay-policy=no-user-gesture-required", "--mute-audio"])
        context = browser.new_context(viewport={"width": 1280, "height": 900}, locale="zh-CN")
        page = context.new_page()
        page.add_init_script("localStorage.removeItem('emotune-online'); localStorage.setItem('emotune-voice','0');")

        def handle_recommend(route):
            want = "online=1" in route.request.url
            body = payload("online" if want and mode["online"] else "local")
            route.fulfill(status=200, content_type="application/json; charset=utf-8", body=json.dumps(body, ensure_ascii=False).encode("utf-8"))

        page.route("**/api/recommend**", handle_recommend)
        page.goto(BASE, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_selector("#online-toggle")
        chk("默认打开在线曲库", page.locator("#online-toggle").is_checked())
        chk("状态默认在线", page.evaluate("() => window.__emotune.getState().onlineOn") is True)

        page.locator("#online-toggle").uncheck()
        page.wait_for_timeout(200)
        chk("可手动切到本地", page.evaluate("() => localStorage.getItem('emotune-online')") == "0")
        chk("状态已关闭在线", page.evaluate("() => window.__emotune.getState().onlineOn") is False)

        page.locator("#online-toggle").check()
        page.wait_for_timeout(200)
        chk("可再打开在线", page.evaluate("() => window.__emotune.getState().onlineOn") is True)

        page.evaluate("() => window.__emotune.fallbackToLocal('在线歌曲长时间播放失败，已自动切换到本地曲库。')")
        page.wait_for_timeout(600)
        st = page.evaluate("() => window.__emotune.getState()")
        chk("失败后开关关闭", st.get("onlineOn") is False and page.locator("#online-toggle").is_checked() is False)
        chk("失败后改播本地歌", st.get("titles") == ["热爱105°C的你"], str(st.get("titles")))
        page.screenshot(path=str(OUT / "fallback.png"), full_page=True)

        live = context.new_page()
        live.add_init_script("localStorage.removeItem('emotune-online'); localStorage.setItem('emotune-voice','0');")
        live.goto(BASE, wait_until="domcontentloaded", timeout=20000)
        live.locator(".tab[data-mode='upload']").click()
        live.wait_for_selector("#demo-list button")
        live.locator("#demo-list button").first.click()
        live.wait_for_function("() => document.querySelectorAll('#songs .song').length >= 8", timeout=25000)
        live.wait_for_timeout(400)
        badges = live.locator("#songs .song").evaluate_all("els => els.map(e => (e.innerText || ''))")
        online_badges = [t for t in badges if "在线" in t]
        local_badges = [t for t in badges if "本地" in t]
        chk("上传后列出歌曲", len(badges) == 24, str(len(badges)))
        chk("默认在线优先或本地兜底", bool(online_badges) or bool(local_badges), f"online={len(online_badges)} local={len(local_badges)}")
        live.locator("#online-toggle").uncheck()
        live.wait_for_function("() => document.querySelectorAll('#songs .song').length >= 8", timeout=15000)
        live.wait_for_timeout(300)
        after = live.locator("#songs .song").evaluate_all("els => els.map(e => (e.innerText || ''))")
        chk("手动切本地后仍有歌", len(after) >= 8, str(len(after)))
        chk("手动切本地后不再标在线", all("在线 ·" not in t and "苹果音乐" not in t for t in after), str(after[:2]))
        live.screenshot(path=str(OUT / "upload-local.png"), full_page=True)
        browser.close()

    print("=== 结果 ===")
    if fails:
        print(f"未通过 {fails} 项")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
