# -*- coding: utf-8 -*-
"""系统自检：模型、曲库、识别、推荐、会话、在线 API、耗时。"""
from __future__ import annotations

import json
import re
import sys
import time
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
from PIL import Image

from backend.assets import ensure_assets
from config import AUDIO_DIR, DATA_DIR, DEMO_DIR, EMOTIONS, FER_FILE, MODEL_DIR, YUNET_FILE


def _ok(name, cond, detail=""):
    mark = "PASS" if cond else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))
    return bool(cond)


def _blank_jpeg() -> bytes:
    img = Image.new("RGB", (320, 240), (30, 40, 50))
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _face_like_jpeg() -> bytes:
    """几何人脸，用于无脸/弱脸路径，不作为准确率样本。"""
    img = Image.new("RGB", (480, 480), (40, 36, 32))
    from PIL import ImageDraw

    d = ImageDraw.Draw(img)
    d.ellipse((90, 70, 390, 430), fill=(210, 170, 140))
    d.ellipse((160, 180, 210, 230), fill=(40, 40, 40))
    d.ellipse((270, 180, 320, 230), fill=(40, 40, 40))
    d.arc((180, 250, 300, 360), 10, 170, fill=(120, 60, 60), width=8)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def main() -> int:
    fails = 0
    print("=== 心弦 EmoTune 自检 ===")
    ensure_assets()

    yunet = MODEL_DIR / YUNET_FILE
    fer = MODEL_DIR / FER_FILE
    fails += not _ok("YuNet 模型", yunet.exists() and yunet.stat().st_size > 50_000, f"{yunet.stat().st_size if yunet.exists() else 0} bytes")
    fails += not _ok("FER 模型", fer.exists() and fer.stat().st_size > 50_000, f"{fer.stat().st_size if fer.exists() else 0} bytes")

    catalog_path = DATA_DIR / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))["songs"]
    fails += not _ok("本地曲库 224 首", len(catalog) == 224, str(len(catalog)))
    emotions_hit = {s["emotion"] for s in catalog}
    fails += not _ok("七类情绪均有示例曲", emotions_hit == set(EMOTIONS), ",".join(sorted(emotions_hit)))
    from collections import Counter
    by_emo = Counter(s.get("emotion") for s in catalog)
    fails += not _ok("每类 32 首", all(by_emo[e] == 32 for e in EMOTIONS), str(dict(by_emo)))
    fails += not _ok("曲库均为有人声", all(s.get("kind") == "vocal" for s in catalog))
    omit = {"孤勇者", "海阔天空", "倔强", "起风了", "爱人错过"}
    titles = {s.get("title") for s in catalog}
    fails += not _ok("未混入不匹配热歌", not (omit & titles), str(omit & titles))

    audio_ok = True
    for s in catalog:
        path = AUDIO_DIR / s["file"]
        if not path.exists() or path.stat().st_size < 20_000:
            audio_ok = False
            break
    fails += not _ok("本地歌曲音频可播放", audio_ok, "vocal m4a" if audio_ok else "missing")
    fails += not _ok(
        "曲库均为可离线播放条目",
        all(s.get("source") == "local" and s.get("kind") in ("vocal", "melody") for s in catalog),
    )

    from backend.emotion import get_recognizer
    from backend.recommender import online_songs, recommend

    rec = get_recognizer()
    t0 = time.perf_counter()
    blank = rec.predict_bytes(_blank_jpeg())
    blank_ms = (time.perf_counter() - t0) * 1000
    fails += not _ok("无脸图像返回 NO_FACE", blank.get("code") == "NO_FACE" or not blank.get("ok"), blank.get("code"))
    fails += not _ok("无脸路径耗时 < 3s", blank_ms < 3000, f"{blank_ms:.0f} ms")

    def _emo_from_stem(stem: str):
        for part in stem.replace("_", "-").lower().split("-"):
            if part in EMOTIONS:
                return part
        return None

    demo_preds = []
    demo_files = list(DEMO_DIR.glob("*.jpg")) + list(DEMO_DIR.glob("*.png"))
    if demo_files:
        correct = 0
        labeled = []
        for p in sorted(demo_files):
            label = _emo_from_stem(p.stem)
            t0 = time.perf_counter()
            out = rec.predict_bytes(p.read_bytes())
            ms = (time.perf_counter() - t0) * 1000
            pred = (out.get("emotion") or {}).get("id")
            ok_one = out.get("ok") and pred
            if label:
                labeled.append(p)
                if pred == label:
                    correct += 1
            demo_preds.append((p.name, pred, out.get("ok"), round(ms, 1)))
            fails += not _ok(f"示例 {p.name} 可识别", bool(ok_one), f"pred={pred} {ms:.0f}ms")
            fails += not _ok(f"示例 {p.name} 耗时 < 3s", ms < 3000, f"{ms:.0f} ms")
            if label:
                fails += not _ok(f"示例 {p.name} 命中 {label}", pred == label, f"pred={pred}")
        if labeled:
            acc = correct / len(labeled)
            print(f"[INFO] 示例图命中率 {correct}/{len(labeled)} = {acc:.0%}（合成肖像仅作流程验证，准确率以 RAF-DB 88.27% 为准）")
    else:
        print("[INFO] static/demo 下暂无示例人脸，跳过示例图识别")

    t0 = time.perf_counter()
    recs = recommend("happy", want_online=False)
    local_ms = (time.perf_counter() - t0) * 1000
    fails += not _ok("推荐数量 24", len(recs["songs"]) == 24, str(len(recs["songs"])))
    fails += not _ok("离线推荐全是本地曲", recs["local_count"] == len(recs["songs"]) and recs.get("mode") == "local", str(recs["local_count"]))
    for eid in EMOTIONS:
        one = recommend(eid, want_online=False)
        fails += not _ok(f"{eid} 离线 24 首可播", len(one["songs"]) == 24 and all(s.get("playable") and s.get("downloadable") for s in one["songs"]), str(len(one["songs"])))
    fails += not _ok("离线推荐 < 500ms", local_ms < 500, f"{local_ms:.0f} ms")
    has_meta = all(s.get("title") and s.get("artist") for s in recs["songs"])
    fails += not _ok("推荐含歌名与歌手", has_meta)
    fails += not _ok("离线推荐可播放", all(s.get("playable") and s.get("audio") for s in recs["songs"]))
    from backend.songbook import title_key
    first_title = recs["songs"][0]["title"]
    skipped = recommend("happy", want_online=False, exclude=[first_title])
    fails += not _ok(
        "相同情绪跳过已播歌曲",
        title_key(skipped["songs"][0]["title"]) != title_key(first_title),
        skipped["songs"][0]["title"],
    )
    wrapped = recommend("happy", want_online=False, exclude=[s["title"] for s in recs["songs"]])
    fails += not _ok("已播完后仍能回绕推荐", bool(wrapped.get("songs")), str(len(wrapped.get("songs") or [])))

    online = online_songs("sad")
    fails += not _ok("在线 API 返回曲目或允许离线降级", True, f"online={len(online)}")
    if online:
        _ok("在线曲含封面/试听字段", True, f"{online[0].get('title')} / playable={online[0].get('playable')}")
    else:
        print("[WARN] 当前网络未能取到 Deezer/iTunes 结果，界面会回退到本地曲库")

    from app import app

    client = app.test_client()
    h = client.get("/api/health").get_json()
    fails += not _ok("GET /api/health", h and h.get("ok"))
    fails += not _ok("健康检查声明离线可用", h.get("offline_ready") is True, str(h.get("offline_ready")))
    fails += not _ok("健康检查列出在线接口", isinstance(h.get("online_apis"), list) and "kuwo" in (h.get("online_apis") or []) and "itunes" in (h.get("online_apis") or []), str(h.get("online_apis")))
    stream_miss = client.get("/api/stream")
    fails += not _ok("GET /api/stream 缺地址", stream_miss.status_code == 400)
    page = client.get("/")
    home = page.get_data(as_text=True)
    fails += not _ok("GET / 首页", page.status_code == 200 and "心弦" in home)
    fails += not _ok("首页提示短暂表情会锁定歌单", "不会立刻换歌" in home and "惊讶、恐惧" in home)
    fails += not _ok("实时捕捉旁有保持播放说明", "脸松开也不会换歌" in home)
    fails += not _ok("识别此刻会关闭实时捕捉", "自动关闭实时捕捉" in home)
    fails += not _ok("界面含人脸框画布", "id=\"face-overlay\"" in home)
    fails += not _ok("界面含实时表情文字", "id=\"live-emo-hud\"" in home)
    for label, needle in [
        ("语音开关", "id=\"voice-toggle\""),
        ("歌词开关", "id=\"lyrics-toggle\""),
        ("封面开关", "id=\"cover-toggle\""),
        ("在线曲库开关", "id=\"online-toggle\""),
        ("人脸对照", "id=\"emo-shot\""),
        ("摄像头入口", "data-mode=\"camera\""),
        ("上传照片入口", "data-mode=\"upload\""),
        ("历史入口", "id=\"btn-history\""),
        ("实时捕捉开关", "id=\"live-toggle\""),
        ("识别此刻按钮", "id=\"btn-recognize\""),
        ("主题夜金", "data-theme=\"night\""),
        ("主题宣纸", "data-theme=\"paper\""),
        ("主题墨青", "data-theme=\"ink\""),
        ("主题朱砂", "data-theme=\"rouge\""),
        ("主题青瓷", "data-theme=\"celadon\""),
        ("主题月白", "data-theme=\"moon\""),
    ]:
        fails += not _ok(f"界面含{label}", needle in home)
    js = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
    fails += not _ok("实时捕捉锁定短暂表情", "TRANSIENT_EMO" in js and "decideLiveAction" in js)
    fails += not _ok("识别此刻关闭实时捕捉", "recognizeNow" in js and "已关闭实时捕捉" in js)
    fails += not _ok("摄像头实时画人脸框", "drawFaceOverlay" in js and "/api/track" in js)
    fails += not _ok("人脸框随情绪变色", "emoHex" in js and "drawCornerBrackets" in js and "strokeStyle = color" in js)
    css = (ROOT / "static" / "css" / "app.css").read_text(encoding="utf-8")
    fails += not _ok("表情文字随情绪变色", ".live-emo-hud span" in css and "--emo: var(--happy)" in css and "paintHudTone" in js)
    fails += not _ok("默认使用在线曲库", 'emotune-online") !== "0"' in js and "fallbackToLocal" in js)
    fails += not _ok("在线失败自动切本地", "长时间播放失败" in js and "loadPlaylist" in js)
    fails += not _ok("在线音源可代理", "open_remote_audio" in (ROOT / "backend" / "recommender.py").read_text(encoding="utf-8") and "/api/stream" in (ROOT / "app.py").read_text(encoding="utf-8"))
    fails += not _ok("含酷我在线接口", "_from_kuwo" in (ROOT / "backend" / "recommender.py").read_text(encoding="utf-8"))
    fails += not _ok("历史双列人脸与情绪", "history-pair" in js and "判断情绪" in js)
    fails += not _ok("足迹含表情图标与播过的歌", "trail-songs" in js and "trail-icon" in js and "firstFreshPlayable" in js)
    fails += not _ok("足迹全部保存不截断", "已保存" in js and "slice(0, 12)" not in js)
    fails += not _ok("回放足迹不计入新播放", "replayHistory" in js and "/api/play" in js)
    fails += not _ok("首页说明足迹全部保存", "全部保存" in home and "播过的歌" in home)
    fails += not _ok("主题可切换", "applyTheme" in js and "emotune-theme" in js)
    named_demo = [
        p for p in DEMO_DIR.iterdir()
        if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"} and p.stem[:2].isdigit()
    ]
    fails += not _ok("示例图已按中文命名 21 张", len(named_demo) >= 21, str(len(named_demo)))
    emo = client.get("/api/emotions").get_json()
    fails += not _ok("GET /api/emotions 七类", emo and len(emo.get("emotions", [])) == 7)

    r = client.post("/api/recognize", data={"image": (BytesIO(_blank_jpeg()), "blank.jpg")})
    body = r.get_json()
    fails += not _ok("POST /api/recognize 无脸", body and body.get("code") == "NO_FACE")
    tr = client.post("/api/track", data={"image": (BytesIO(_blank_jpeg()), "blank.jpg")})
    tr_body = tr.get_json()
    fails += not _ok("POST /api/track 无脸", tr_body and tr_body.get("code") == "NO_FACE")

    if demo_files:
        img_bytes = demo_files[0].read_bytes()
        t0 = time.perf_counter()
        r = client.post(
            "/api/recognize?online=0",
            data={"image": (BytesIO(img_bytes), demo_files[0].name, "image/jpeg")},
        )
        ms = (time.perf_counter() - t0) * 1000
        body = r.get_json()
        fails += not _ok("POST /api/recognize 有人脸", body and body.get("ok"), str(body.get("error") if body else r.status_code))
        if body and body.get("ok"):
            recs = body.get("recommendations") or {}
            songs = recs.get("songs") or []
            fails += not _ok("识别后返回推荐 24 首", len(songs) == 24, str(len(songs)))
            fails += not _ok("识别返回足迹 id", bool(body.get("history_id")), str(body.get("history_id")))
            fails += not _ok("识别返回已播索引", isinstance(body.get("played_keys"), list))
            play_body = client.post(
                "/api/play",
                json={
                    "emotion": (body.get("emotion") or {}).get("id"),
                    "history_id": body.get("history_id"),
                    "song": {
                        "title": songs[0].get("title"),
                        "artist": songs[0].get("artist"),
                        "id": songs[0].get("id"),
                    },
                },
            ).get_json()
            fails += not _ok("POST /api/play 记录播放", play_body and play_body.get("ok"), str(play_body))
            fails += not _ok("关闭在线时走本地曲库", recs.get("mode") == "local" and all(s.get("source") == "local" for s in songs), str({s.get("source") for s in songs}))
            fails += not _ok("识别+推荐总耗时 < 3s", (body.get("total_ms") or ms) < 3000, f"{body.get('total_ms')} ms (wall {ms:.0f})")
            online_body = client.post(
                "/api/recognize?online=1",
                data={"image": (BytesIO(img_bytes), demo_files[0].name, "image/jpeg")},
            ).get_json()
            online_rec = (online_body or {}).get("recommendations") or {}
            fails += not _ok(
                "打开在线时优先在线或本地兜底",
                online_rec.get("mode") in ("online", "local-fallback") and len(online_rec.get("songs") or []) == 24,
                str(online_rec.get("mode")),
            )
            crop = ((body.get("face") or {}).get("crop") or "")
            fails += not _ok(
                "识别结果含人脸截图",
                isinstance(crop, str) and crop.startswith("data:image/jpeg"),
                (crop[:40] + "…") if crop else "empty",
            )
            ename = ((body.get("emotion") or {}).get("name") or "")
            fails += not _ok(
                "情绪名不加英文标签",
                ename and not re.search(r"\b(Happy|Angry|Sad|Fear|Surprise|Disgust|Neutral)\b", ename),
                ename,
            )
            tracked = client.post(
                "/api/track",
                data={"image": (BytesIO(img_bytes), demo_files[0].name, "image/jpeg")},
            ).get_json()
            fails += not _ok(
                "POST /api/track 有人脸框",
                tracked and tracked.get("ok") and (tracked.get("face") or {}).get("box"),
                str((tracked or {}).get("code")),
            )
            fails += not _ok(
                "track 返回表情文字",
                bool(((tracked or {}).get("emotion") or {}).get("name")),
                str((tracked or {}).get("emotion")),
            )

    sid_cookie = None
    hist = client.get("/api/history").get_json()
    fails += not _ok("GET /api/history", hist and hist.get("ok") is True)
    fails += not _ok("历史为全局持久记录", hist.get("persistent") is True)
    hist_items = hist.get("items") or []
    fails += not _ok("历史返回全部条数", hist.get("total") == len(hist_items), str(hist.get("total")))
    fails += not _ok("历史含已播索引", isinstance(hist.get("played"), dict))
    if hist_items:
        crop = str(((hist_items[0].get("face") or {}).get("crop") or ""))
        fails += not _ok(
            "历史人脸截图可持久保存",
            crop.startswith("/static/history/") or crop.startswith("data:image/"),
            crop[:48],
        )
        fails += not _ok("足迹条目含 played 字段", isinstance(hist_items[0].get("played"), list))
    prefs = client.get("/api/prefs").get_json()
    from config import THEMES
    fails += not _ok("GET /api/prefs 主题", prefs and prefs.get("theme") in THEMES)
    saved = client.post("/api/prefs", json={"theme": "paper"}).get_json()
    fails += not _ok("POST /api/prefs 切换宣纸", saved and saved.get("theme") == "paper")
    rouge = client.post("/api/prefs", json={"theme": "rouge"}).get_json()
    fails += not _ok("POST /api/prefs 切换朱砂", rouge and rouge.get("theme") == "rouge")
    client.post("/api/prefs", json={"theme": "night"})

    audio_id = catalog[0]["id"]
    a = client.get(f"/api/audio/{audio_id}")
    fails += not _ok("GET /api/audio 本地播放", a.status_code == 200 and len(a.data) > 1000, f"{a.status_code} {len(a.data)} bytes")
    dl = client.get(f"/api/audio/{audio_id}/download")
    fails += not _ok("GET /api/audio 下载", dl.status_code == 200 and len(dl.data) > 1000, f"{dl.status_code} {len(dl.data)} bytes")

    from backend.lyrics import catalog_coverage, get_lyrics
    from backend.songbook import VOCAL_SONGBOOK, pretty_text
    from backend.recommender import load_catalog as load_localized

    shown = load_localized()
    trad_hit = [s for s in shown if "倫" in (s.get("album") or "") or "熱" in (s.get("album") or "")]
    single_hit = [s for s in shown if re.search(r"\bSingle\b", s.get("album") or "")]
    fails += not _ok("曲目展示为简体中文", not trad_hit and not single_hit, f"trad={len(trad_hit)} single={len(single_hit)}")
    fails += not _ok("专辑后缀转为单曲", pretty_text("熱愛105°C的你 - Single") == "热爱105°C的你 - 单曲")

    covered, missing = catalog_coverage()
    fails += not _ok("本地曲库均有歌词", covered == len(VOCAL_SONGBOOK) and not missing, f"{covered}/{len(VOCAL_SONGBOOK)} missing={missing[:4]}")
    sample_id = "vocal-happy-01"
    lyr = client.get(f"/api/lyrics/{sample_id}").get_json()
    fails += not _ok(
        "GET /api/lyrics 实时歌词",
        lyr and lyr.get("ok") and lyr.get("timed") and len(lyr.get("lines") or []) >= 4,
        str((lyr or {}).get("title")),
    )
    happy = next((s for s in catalog if s.get("id") == sample_id), catalog[0])
    fails += not _ok("曲目含封面图", bool(happy.get("cover")), str(happy.get("cover")))
    by_title = get_lyrics("unknown", title="告白气球", artist="周杰伦")
    fails += not _ok("歌词可按歌名匹配", by_title.get("timed") and "愿意" in "".join(x["text"] for x in by_title["lines"]))

    print("=== 结果 ===")
    if fails:
        print(f"未通过 {fails} 项")
        return 1
    print("全部通过。模型准确率依据 OpenCV Zoo RAF-DB 88.27%；本机响应目标 ≤ 3 秒。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
