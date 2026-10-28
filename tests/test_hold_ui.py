# -*- coding: utf-8 -*-
"""Verify hold-window copy and live-follow policy in the browser."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import os

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(r"C:\Users\niewe\AppData\Local\Temp")
BASE = os.environ.get("EMOTUNE_BASE", "http://127.0.0.1:5000")
CROP = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"

EMOTION = {
    "surprise": {"id": "surprise", "zh": "惊", "name": "惊讶", "prob": 0.93, "copy": "惊", "genre": "突然爆开", "scores": []},
    "neutral": {"id": "neutral", "zh": "中", "name": "平静", "prob": 0.88, "copy": "中", "genre": "平走日常", "scores": []},
    "happy": {"id": "happy", "zh": "喜", "name": "喜悦", "prob": 0.91, "copy": "喜", "genre": "阳光蹦跳", "scores": []},
}
SONGS = {
    "surprise": [{
        "id": "vocal-surprise-01",
        "title": "本草纲目",
        "artist": "周杰伦",
        "album": "霍元甲",
        "audio": "/api/audio/vocal-surprise-01",
        "cover": "/static/covers/vocal-surprise-01.jpg",
        "playable": True,
        "source": "local",
        "source_label": "本地曲库",
    }],
    "neutral": [{
        "id": "vocal-neutral-01",
        "title": "成都",
        "artist": "赵雷",
        "album": "无法长大",
        "audio": "/api/audio/vocal-neutral-01",
        "cover": "/static/covers/vocal-neutral-01.jpg",
        "playable": True,
        "source": "local",
        "source_label": "本地曲库",
    }],
    "happy": [{
        "id": "vocal-happy-01",
        "title": "热爱105°C的你",
        "artist": "阿肆",
        "album": "热爱105°C的你 - 单曲",
        "audio": "/api/audio/vocal-happy-01",
        "cover": "/static/covers/vocal-happy-01.jpg",
        "playable": True,
        "source": "local",
        "source_label": "本地曲库",
    }],
}


def payload(emo: str) -> dict:
    e = EMOTION[emo]
    songs = SONGS[emo]
    return {
        "ok": True,
        "emotion": e,
        "face": {"crop": CROP, "score": 0.9},
        "recommendations": {
            "songs": songs,
            "local_count": len(songs),
            "online_count": 0,
            "genre": e["genre"],
            "mode": "local",
        },
        "elapsed_ms": 40,
        "total_ms": 50,
        "source": "camera-live",
    }


def main() -> int:
    fails = 0
    queue = ["surprise"]
    shots = OUT / "emotune-hold"
    shots.mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--use-fake-ui-for-media-stream",
                "--use-fake-device-for-media-stream",
                "--autoplay-policy=no-user-gesture-required",
                "--mute-audio",
                "--no-proxy-server",
            ],
        )
        context = browser.new_context(viewport={"width": 1280, "height": 900}, locale="zh-CN")
        page = context.new_page()
        page.add_init_script("localStorage.setItem('emotune-voice','0');")

        def handle_recognize(route):
            emo = queue[0] if queue else "neutral"
            route.fulfill(
                status=200,
                content_type="application/json; charset=utf-8",
                body=json.dumps(payload(emo), ensure_ascii=False).encode("utf-8"),
            )

        def handle_track(route):
            emo = queue[0] if queue else "neutral"
            e = EMOTION.get(emo) or EMOTION["neutral"]
            body = {
                "ok": True,
                "track": True,
                "emotion": e,
                "face": {"box": [90, 36, 210, 250], "score": 0.93, "image_size": [400, 300]},
                "faces": [{"box": [90, 36, 210, 250], "score": 0.93, "primary": True}],
                "elapsed_ms": 20,
            }
            route.fulfill(
                status=200,
                content_type="application/json; charset=utf-8",
                body=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            )

        page.route("**/api/track**", handle_track)
        page.route("**/api/recognize**", handle_recognize)
        page.goto(BASE, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_selector("#live-hint", state="attached")
        page.locator(".live-wrap").hover()
        page.wait_for_timeout(180)
        live_hint = page.locator("#live-hint").text_content() or ""
        hold_note = page.locator("#hold-note").inner_text()
        recs_meta = page.locator("#recs-meta").inner_text()
        print("live-hint:", live_hint)
        print("hold-note:", hold_note)

        def chk(name, cond, detail=""):
            nonlocal fails
            mark = "PASS" if cond else "FAIL"
            print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))
            if not cond:
                fails += 1

        chk("实时捕捉说明在悬停提示里", "脸松开也不会换歌" in live_hint and "惊讶" in live_hint and "识别此刻" in live_hint, live_hint)
        chk("摄像头人脸框画布", page.locator("#face-overlay").count() == 1)
        chk("画面实时表情文字", page.locator("#live-emo-hud").count() == 1)
        chk("情绪区说明可见", "不会立刻换歌" in hold_note and "惊讶、恐惧" in hold_note, hold_note)
        chk("歌曲区说明可见", "松开后也不会马上换歌" in recs_meta, recs_meta)

        page.locator("#btn-about").click()
        about = page.locator("#about-dialog").inner_text()
        chk("关于里说明保持播放", "不会立刻换歌" in about and "另一种明显表情" in about)
        page.locator("#btn-close-about").click()

        page.screenshot(path=str(shots / "copy.png"), full_page=True)

        policy = page.evaluate(
            """() => {
              const d = window.__emotune.decideLiveAction;
              return {
                first: d('', 'surprise', false),
                relax: d('surprise', 'neutral', false),
                weak: d('surprise', 'happy', true),
                other: d('surprise', 'happy', false),
                same: d('surprise', 'surprise', false),
                noface: d('fear', '', false),
                transient: window.__emotune.transient,
              };
            }"""
        )
        chk("首次惊讶会切歌单", policy["first"]["action"] == "apply", str(policy["first"]))
        chk("惊讶后变平静仍保持", policy["relax"]["action"] == "hold", str(policy["relax"]))
        chk("惊讶后弱喜悦仍保持", policy["weak"]["action"] == "hold", str(policy["weak"]))
        chk("惊讶后明显喜悦准备切换", policy["other"]["action"] == "pending-other", str(policy["other"]))
        chk("同一惊讶保持锁定", policy["same"]["action"] == "same", str(policy["same"]))
        chk("恐惧后没表情仍保持", policy["noface"]["action"] == "hold", str(policy["noface"]))
        chk("短暂表情包含惊惧怒厌", all(policy["transient"].get(k) for k in ("surprise", "fear", "angry", "disgust")))

        cam_ok = False
        try:
            page.locator("#btn-cam").click()
            page.wait_for_function(
                "() => { const v = document.querySelector('#cam'); return v && v.readyState >= 2 && v.videoWidth > 0; }",
                timeout=8000,
            )
            cam_ok = True
        except Exception as exc:
            print("[WARN] 假摄像头未就绪，跳过实时跟随端到端:", exc)

        if cam_ok:
            page.wait_for_selector("#live-emo-hud", state="visible", timeout=8000)
            hud = page.locator("#live-emo-hud").inner_text()
            chk("画面动态显示表情文字", any(x in hud for x in ("惊", "惊讶", "寻找人脸", "喜", "平静")), hud)
            page.wait_for_function(
                "() => document.querySelector('#live-emo-hud')?.dataset.emo === 'surprise'",
                timeout=8000,
            )
            color_info = page.evaluate(
                """() => {
                  const zh = document.querySelector('#live-emo-zh');
                  const name = document.querySelector('#live-emo-name');
                  return {
                    zh: getComputedStyle(zh).color,
                    name: getComputedStyle(name).color,
                    overlay: window.__emotune.getState().overlay,
                  };
                }"""
            )
            chk(
                "惊讶人脸框与文字用粉色",
                "255, 107, 157" in color_info["zh"]
                and "255, 107, 157" in color_info["name"]
                and str(color_info.get("overlay", {}).get("color", "")).lower() == "#ff6b9d",
                str(color_info),
            )
            page.screenshot(path=str(shots / "overlay.png"))
            page.locator("#live-toggle").check()
            page.wait_for_function("() => window.__emotune.getState().lock === 'surprise'", timeout=12000)
            page.wait_for_timeout(400)
            page.screenshot(path=str(shots / "locked.png"), full_page=True)
            hold_txt = page.locator("#emo-hold").inner_text()
            titles = page.evaluate("() => window.__emotune.getState().titles")
            chk("锁定惊讶后显示状态条", "锁定" in hold_txt and "惊讶" in hold_txt, hold_txt)
            chk("锁定后歌单是惊讶曲", titles == ["本草纲目"], str(titles))
            chk("情绪字仍是惊", page.locator("#emo-zh").inner_text().strip() == "惊")

            queue[:] = ["neutral"]
            page.wait_for_timeout(7000)
            page.screenshot(path=str(shots / "relaxed.png"), full_page=True)
            st = page.evaluate("() => window.__emotune.getState()")
            hold_txt = page.locator("#emo-hold").inner_text()
            chk("松开后仍锁定惊讶", st["lock"] == "surprise", str(st))
            chk("松开后仍播惊讶歌", st["titles"] == ["本草纲目"], str(st["titles"]))
            chk("松开后提示不换歌", "脸已松开" in hold_txt and "换歌" in hold_txt, hold_txt)
            chk("松开后标题仍是歌曲锁定或惊讶", "锁定" in page.locator("#emo-kicker").inner_text() or page.locator("#emo-zh").inner_text().strip() == "惊")

            queue[:] = ["happy"]
            page.wait_for_function("() => window.__emotune.getState().lock === 'happy'", timeout=12000)
            st = page.evaluate("() => window.__emotune.getState()")
            page.screenshot(path=str(shots / "switched.png"), full_page=True)
            chk("明显喜悦后才切歌", st["lock"] == "happy" and st["titles"] == ["热爱105°C的你"], str(st))

            page.locator("#btn-recognize").click()
            page.wait_for_timeout(600)
            st = page.evaluate("() => window.__emotune.getState()")
            live_on = page.locator("#live-toggle").is_checked()
            chk("识别此刻后实时捕捉关闭", st.get("live") is False and live_on is False, str(st))

        browser.close()

    print("=== 结果 ===")
    if fails:
        print(f"未通过 {fails} 项")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
