# -*- coding: utf-8 -*-
"""Voice follows confirmed 此刻; flicker stays silent; 识别此刻 speaks once."""
from __future__ import annotations

import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("EMOTUNE_BASE", "http://127.0.0.1:5000")
CROP = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"


def payload(emo_id: str, name: str, zh: str, source: str) -> dict:
    return {
        "ok": True,
        "emotion": {"id": emo_id, "zh": zh, "name": name, "prob": 0.92, "copy": name, "genre": "", "scores": []},
        "face": {"crop": CROP, "score": 0.9},
        "recommendations": {
            "songs": [],
            "local_count": 0,
            "online_count": 0,
            "genre": "",
            "mode": "local",
            "strategy": {"id": "iso", "zh": "同频", "name": "同频"},
        },
        "elapsed_ms": 40,
        "total_ms": 50,
        "source": source,
    }


def main() -> int:
    fails = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--mute-audio", "--autoplay-policy=no-user-gesture-required", "--no-proxy-server"],
        )
        context = browser.new_context(viewport={"width": 1100, "height": 800}, locale="zh-CN")
        page = context.new_page()
        page.add_init_script("localStorage.setItem('emotune-voice','1');")
        page.goto(BASE, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_function("() => window.__emotune && window.__emotune.tickUiSpeak", timeout=15000)

        result = page.evaluate(
            """({ surpriseLive, happyLive, angryShot, surpriseEmo, happyEmo, sadEmo }) => {
              window.__spoken = [];
              const proto = window.SpeechSynthesis && window.SpeechSynthesis.prototype;
              const target = proto && proto.speak ? proto : window.speechSynthesis;
              const orig = target.speak.bind(window.speechSynthesis);
              target.speak = function (u) {
                window.__spoken.push((u && u.text) || "");
                try { window.speechSynthesis.cancel(); } catch (e) {}
              };
              const g = window.__emotune;
              g.setLiveForTest(true);
              g.handleRecognizeData(surpriseLive, "camera-live", 0);
              for (let i = 0; i < 5; i += 1) g.handleRecognizeData(surpriseLive, "camera-live", 0);
              const afterLockTicks = window.__spoken.slice();

              g.resetUiForTest();
              g.setLiveForTest(true);
              g.commitLiveUi(surpriseEmo);
              g.commitLiveUi(happyEmo);
              const afterFlicker = window.__spoken.slice();
              const flickerUi = g.getState().uiEmo;

              g.setSpeakForTest("surprise", 2600, 0);
              g.commitLiveUi(surpriseEmo);
              const afterConfirm = window.__spoken.slice();

              for (let i = 0; i < 4; i += 1) g.commitLiveUi(surpriseEmo);
              g.setUiGuessForTest("happy", 600, 2);
              g.commitLiveUi(happyEmo);
              const afterSwitchNoDwell = window.__spoken.slice();
              g.setSpeakForTest("happy", 2600, 0);
              g.commitLiveUi(happyEmo);
              const afterHappy = window.__spoken.slice();

              const spikeMark = window.__spoken.length;
              g.resetUiForTest();
              g.setLiveForTest(true);
              g.commitLiveUi(surpriseEmo);
              g.setSpeakForTest("surprise", 500, 0);
              g.commitLiveUi(surpriseEmo);
              const afterSpikeQuick = window.__spoken.slice(spikeMark);
              const dailyMark = window.__spoken.length;
              g.resetUiForTest();
              g.setLiveForTest(true);
              g.commitLiveUi(happyEmo);
              g.setSpeakForTest("happy", 500, 0);
              g.commitLiveUi(happyEmo);
              const afterDailyQuick = window.__spoken.slice(dailyMark);
              window.__spoken.length = spikeMark;

              const mark = window.__spoken.length;
              g.resetUiForTest();
              g.setLiveForTest(true);
              g.commitLiveUi(happyEmo);
              g.setLockForTest("angry", 0);
              g.setSpeakForTest("happy", 2600, 0);
              g.tickUiSpeak({ id: "angry", zh: "怒", name: "愤怒" });
              const afterLockMismatch = window.__spoken.slice(mark);
              const mismatchUi = g.getState().uiEmo;
              g.setTrackForTest("sad");
              const displayId = g.displayEmotionId();
              window.__spoken.length = mark;

              g.setLiveForTest(false);
              g.handleRecognizeData(angryShot, "camera", 0);
              const afterShot = window.__spoken.slice();
              g.handleRecognizeData(angryShot, "camera", 0);
              const afterShotAgain = window.__spoken.slice();

              g.resetUiForTest();
              g.commitLiveUi(happyEmo);
              const first = g.getState().uiEmo;
              g.commitLiveUi(sadEmo);
              const flicker = g.getState().uiEmo;
              g.setUiGuessForTest("sad", 600, 2);
              g.commitLiveUi(sadEmo);
              const stable = g.getState().uiEmo;

              target.speak = orig;
              return {
                afterLockTicks,
                afterFlicker,
                flickerUi,
                afterConfirm,
                afterSwitchNoDwell,
                afterHappy,
                afterSpikeQuick,
                afterDailyQuick,
                afterLockMismatch,
                mismatchUi,
                displayId,
                afterShot,
                afterShotAgain,
                first,
                flicker,
                stable,
                last: g.getState().lastSpoken,
              };
            }""",
            {
                "surpriseLive": payload("surprise", "惊讶", "惊", "camera-live"),
                "happyLive": payload("happy", "喜悦", "喜", "camera-live"),
                "angryShot": payload("angry", "愤怒", "怒", "camera"),
                "surpriseEmo": {"id": "surprise", "zh": "惊", "name": "惊讶", "prob": 0.92, "scores": []},
                "happyEmo": {"id": "happy", "zh": "喜", "name": "喜悦", "prob": 0.92, "scores": []},
                "sadEmo": {"id": "sad", "zh": "哀", "name": "悲伤", "prob": 0.9, "scores": []},
            },
        )
        print("voice", result)

        def chk(name, cond, detail=""):
            nonlocal fails
            if cond:
                print(f"[PASS] {name}")
            else:
                print(f"[FAIL] {name}" + (f" — {detail}" if detail else ""))
                fails += 1

        chk("歌单锁定连拍不说话", result.get("afterLockTicks") == [])
        chk("此刻单帧闪动不说话", result.get("afterFlicker") == [] and result.get("flickerUi") == "surprise")
        chk("此刻稳住后说一次", result.get("afterConfirm") == ["情绪标签变为惊，惊讶"])
        chk("换标签未稳住不说话", result.get("afterSwitchNoDwell") == ["情绪标签变为惊，惊讶"])
        chk("新此刻稳住后说一次", result.get("afterHappy") == ["情绪标签变为惊，惊讶", "情绪标签变为喜，喜悦"])
        chk("高潮情绪很快说", result.get("afterSpikeQuick") == ["情绪标签变为惊，惊讶"])
        chk("日常情绪半秒不说", result.get("afterDailyQuick") == [])
        chk(
            "歌单滞后仍说此刻",
            result.get("afterLockMismatch") == ["情绪标签变为喜，喜悦"] and result.get("mismatchUi") == "happy",
        )
        chk("显示标签跟此刻不跟闪动帧", result.get("displayId") == "happy")
        chk(
            "识别此刻立刻说一次",
            result.get("afterShot")
            == ["情绪标签变为惊，惊讶", "情绪标签变为喜，喜悦", "情绪标签变为怒，愤怒"],
        )
        chk(
            "识别此刻相同情绪再点再说一次",
            result.get("afterShotAgain")
            == [
                "情绪标签变为惊，惊讶",
                "情绪标签变为喜，喜悦",
                "情绪标签变为怒，愤怒",
                "情绪标签变为怒，愤怒",
            ],
        )
        chk("此刻首次可显示", result.get("first") == "happy")
        chk("此刻单帧闪动不切换", result.get("flicker") == "happy")
        chk("此刻连续确认后切换", result.get("stable") == "sad")

        context.close()
        browser.close()
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
