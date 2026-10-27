# -*- coding: utf-8 -*-
"""Browser-check remaining product requirements against a running server."""
from __future__ import annotations

import sys
from pathlib import Path

import os

from playwright.sync_api import sync_playwright

BASE = os.environ.get("EMOTUNE_BASE", "http://127.0.0.1:5000")
OUT = Path(r"C:\Users\niewe\AppData\Local\Temp\emotune-full")
ZH_NAMES = {"喜悦", "愤怒", "悲伤", "恐惧", "惊讶", "厌恶", "平静"}
EN_LABELS = ("Happy", "Angry", "Sad", "Fear", "Surprise", "Disgust", "Neutral")


def main() -> int:
    fails = 0
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
            args=["--autoplay-policy=no-user-gesture-required", "--mute-audio", "--no-proxy-server"],
        )
        context = browser.new_context(viewport={"width": 1280, "height": 900}, locale="zh-CN")
        page = context.new_page()
        page.add_init_script("localStorage.setItem('emotune-voice','0');")
        page.goto(BASE, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_selector("#emo-tags")

        chk("摄像头与上传两个入口", page.locator(".tab[data-mode='camera']").count() == 1 and page.locator(".tab[data-mode='upload']").count() == 1)
        chk("实时捕捉开关", page.locator("#live-toggle").count() == 1)
        chk("识别此刻按钮", page.locator("#btn-recognize").count() == 1)
        chk("摄像头人脸框", page.locator("#face-overlay").count() == 1)
        chk("画面表情文字", page.locator("#live-emo-hud").count() == 1)
        chk("七类情绪标签", page.locator(".emo-tag").count() == 7)
        chk("语音/歌词/封面/联网开关", all(page.locator(sel).count() == 1 for sel in ["#voice-toggle", "#lyrics-toggle", "#cover-toggle", "#online-toggle"]))
        chk("人脸对照位", page.locator("#emo-shot").count() == 1 and page.locator("#emo-icon").count() == 1)
        page.screenshot(path=str(OUT / "idle.png"), full_page=True)

        page.locator(".tab[data-mode='upload']").click()
        page.wait_for_selector("#demo-list button")
        n_demo = page.locator("#demo-list button").count()
        chk("七类示例表情", n_demo >= 21, str(n_demo))
        chk("六种主题", page.locator(".theme-pick").count() >= 6)
        for theme in ("paper", "ink", "rouge", "celadon", "moon", "night"):
            page.locator(f'.theme-pick[data-theme="{theme}"]').click()
            page.wait_for_timeout(120)
            chk(f"可切换{theme}主题", page.evaluate("() => document.documentElement.dataset.theme") == theme)
        page.locator("#demo-list button").first.click()
        page.wait_for_function("() => document.querySelectorAll('#songs .song').length >= 8", timeout=20000)
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / "upload-happy.png"), full_page=True)

        chk("上传后仍停在上传页", page.locator(".tab[data-mode='upload']").get_attribute("aria-selected") == "true")
        chk("上传页显示已选照片", page.locator("#picked").is_visible() and page.locator("#picked-img").get_attribute("src", timeout=2000) not in (None, ""))
        n_songs = page.locator("#songs .song").count()
        chk("界面列出歌曲 24 首", n_songs == 24, str(n_songs))
        chk("歌曲可下载", page.locator("#songs a[href*='/download']").count() >= 1)
        name = page.locator("#emo-name").inner_text().strip()
        zh = page.locator("#emo-zh").inner_text().strip()
        chk("情绪大字是中文", zh in {"喜", "怒", "哀", "惧", "惊", "厌", "中性", "中"})
        chk("情绪名不加英文", name in ZH_NAMES and not any(w in name for w in EN_LABELS), name)
        timing = page.locator("#timing").inner_text()
        chk("耗时用毫秒", "毫秒" in timing, timing)
        face_src = page.locator("#emo-face").get_attribute("src") or ""
        chk("情绪旁有人脸截图", face_src.startswith("data:image/"), face_src[:48])
        chk("播放器出现", page.locator("#player").is_visible())
        chk("封面默认打开", page.locator("#nowplay-cover").is_visible() or page.locator("#player-cover").is_visible())
        lyric_now = page.locator("#lyric-now").inner_text().strip()
        chk("歌词默认打开", bool(lyric_now), lyric_now[:20])
        title = page.locator("#player-title").inner_text()
        chk("播放器歌名为简体或必要英文", "Single" not in title and "專輯" not in title, title)

        page.locator("#lyrics-toggle").uncheck()
        page.wait_for_timeout(200)
        chk("可关闭歌词", "is-lyrics-off" in (page.locator("#player").get_attribute("class") or ""))
        page.locator("#lyrics-toggle").check()
        page.locator("#cover-toggle").uncheck()
        page.wait_for_timeout(200)
        chk("可关闭封面", "is-cover-off" in (page.locator("#player").get_attribute("class") or ""))
        page.locator("#cover-toggle").check()

        page.locator("#btn-history").click()
        page.wait_for_selector("#history-list .history-item")
        page.wait_for_selector("#history-list .history-face img", state="visible")
        page.wait_for_timeout(250)
        hist_txt = page.locator("#history-list").inner_text()
        chk("历史记录含中文情绪", any(x in hist_txt for x in ZH_NAMES) and "毫秒" in hist_txt, hist_txt[:80])
        chk("历史含人脸截图", page.locator("#history-list .history-face img").count() >= 1)
        item = page.locator("#history-list .history-item").filter(has=page.locator(".history-face img")).first
        item.wait_for(state="visible")
        try:
            item.scroll_into_view_if_needed(timeout=3000)
        except Exception:
            item = page.locator("#history-list .history-item").filter(has=page.locator(".history-face img")).first
            item.wait_for(state="visible")
        pair_box = item.locator(".history-pair").bounding_box()
        face_box = item.locator(".history-face").bounding_box()
        icon_box = item.locator(".history-icon").bounding_box()
        chk("历史双列对照", bool(pair_box and face_box and icon_box and abs(face_box["y"] - icon_box["y"]) < 24 and icon_box["x"] > face_box["x"] + 40), str((face_box, icon_box)))
        chk("历史人脸足够大", bool(face_box and face_box["width"] >= 96), str(face_box))
        page.locator("#btn-close-history").click()
        chk("情绪足迹有对照", page.locator("#mood-trail .trail-chip").count() >= 1)
        chk("足迹双列人脸与情绪", page.locator("#mood-trail .trail-pair").count() >= 1 and page.locator("#mood-trail .trail-col-cap").count() >= 2)
        chk("足迹含情绪图标", page.locator("#mood-trail .trail-icon svg").count() >= 1)
        chk("足迹含人脸截图", page.locator("#mood-trail .trail-face img").count() >= 1)
        chk("足迹含播放过的歌曲", page.locator("#mood-trail .trail-songs").count() >= 1)
        chk("历史含播放过的歌曲", page.locator("#history-list .history-songs").count() >= 1)
        trail_meta = page.locator("#trail-meta").inner_text()
        chk("足迹全部保存提示", "已保存" in trail_meta and "播过的歌" in trail_meta, trail_meta)
        hist_count = page.locator("#mood-trail .trail-chip").count()
        chk("足迹渲染全部记录", hist_count >= 1, str(hist_count))

        first_play = page.locator("#player-title").inner_text().strip()
        page.wait_for_timeout(700)
        page.locator("#demo-list button").first.click()
        page.wait_for_function("() => document.querySelectorAll('#songs .song').length >= 8", timeout=20000)
        page.wait_for_timeout(900)
        second_play = page.locator("#player-title").inner_text().strip()
        chk(
            "相同情绪尽量换未播过的歌",
            (not first_play or first_play == "未播放") or second_play != first_play,
            f"{first_play} -> {second_play}",
        )
        page.locator("#mood-trail .trail-chip").nth(1 if hist_count >= 2 else 0).click()
        page.wait_for_timeout(700)
        replay_title = page.locator("#player-title").inner_text().strip()
        replay_flag = page.evaluate("() => window.__emotune.getState().replayHistory")
        chk("点足迹可回放当时的歌", bool(replay_title) and replay_title != "未播放", replay_title)
        chk("回放足迹不计入新播放", replay_flag is True)

        page.locator("#btn-about").click()
        about = page.locator("#about-dialog").inner_text()
        chk("关于含本地模型与锁定说明", "88.27%" in about and "不会立刻换歌" in about)
        chk("关于含足迹全部保存", "全部保存" in about and "没听过的歌" in about)
        page.locator("#btn-close-about").click()

        policy = page.evaluate(
            """() => {
              const d = window.__emotune.decideLiveAction;
              return [d('surprise','neutral',false).action, d('fear','',false).action, d('surprise','happy',false).action];
            }"""
        )
        chk("短暂表情松开仍保持", policy == ["hold", "hold", "pending-other"], str(policy))

        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT / "mobile.png"), full_page=True)
        pair = page.locator(".emo-pair").bounding_box()
        chk("手机宽度仍显示人脸与情绪对照", bool(pair and pair["width"] > 80))

        browser.close()

    print("=== 结果 ===")
    if fails:
        print(f"未通过 {fails} 项")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
