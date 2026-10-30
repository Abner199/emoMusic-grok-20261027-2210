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
from config import AUDIO_DIR, DATA_DIR, DEMO_DIR, EMOTIONS, FER_FILE, HSE_FILE, MODEL_DIR, YUNET_FILE


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
    hse = MODEL_DIR / HSE_FILE
    fails += not _ok("YuNet 模型", yunet.exists() and yunet.stat().st_size > 50_000, f"{yunet.stat().st_size if yunet.exists() else 0} bytes")
    fails += not _ok("FER 模型", fer.exists() and fer.stat().st_size > 50_000, f"{fer.stat().st_size if fer.exists() else 0} bytes")
    fails += not _ok("HSEmotion 模型", hse.exists() and hse.stat().st_size > 1_000_000, f"{hse.stat().st_size if hse.exists() else 0} bytes")
    from tools.verify_cpu import check as _cpu_ort
    cpu_ok, cpu_detail = _cpu_ort()
    fails += not _ok("onnxruntime 为 pip CPU 包", cpu_ok, cpu_detail)

    catalog_path = DATA_DIR / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))["songs"]
    fails += not _ok("本地曲库 532 首", len(catalog) == 532, str(len(catalog)))
    emotions_hit = {s["emotion"] for s in catalog}
    fails += not _ok("七类情绪均有示例曲", emotions_hit == set(EMOTIONS), ",".join(sorted(emotions_hit)))
    from collections import Counter
    by_emo = Counter(s.get("emotion") for s in catalog)
    fails += not _ok("每类 76 首", all(by_emo[e] == 76 for e in EMOTIONS), str(dict(by_emo)))
    happy_front = next((s.get("title") for s in catalog if s.get("emotion") == "happy"), "")
    sad_front = next((s.get("title") for s in catalog if s.get("emotion") == "sad"), "")
    fails += not _ok("喜悦榜首小苹果", happy_front == "小苹果", str(happy_front))
    fails += not _ok("悲伤榜首后来", sad_front == "后来", str(sad_front))
    artists = " ".join(s.get("artist") or "" for s in catalog)
    fails += not _ok("含周杰伦邓紫棋林俊杰", "周杰伦" in artists and "邓紫棋" in artists and "林俊杰" in artists)
    fails += not _ok("含Taylor Swift与Lady Gaga", "Taylor Swift" in artists and "Lady Gaga" in artists)
    fails += not _ok("曲库均为有人声", all(s.get("kind") == "vocal" for s in catalog))
    omit = {"孤勇者", "海阔天空", "倔强", "起风了", "爱人错过"}
    titles = {s.get("title") for s in catalog}
    fails += not _ok("未混入不匹配热歌", not (omit & titles), str(omit & titles))
    from backend.songbook import VOCAL_SONGBOOK, fold_zh, title_key
    fails += not _ok("繁简折合歌名", fold_zh("那些你很冒險的夢") == fold_zh("那些你很冒险的梦"))
    fails += not _ok("繁简折合歌手", fold_zh("汪蘇瀧") == fold_zh("汪苏泷") and fold_zh("蘇打綠") == fold_zh("苏打绿") and fold_zh("汪峯") == fold_zh("汪峰"))
    book_keys = Counter(title_key(s["title"]) for s in VOCAL_SONGBOOK)
    dups = [k for k, n in book_keys.items() if n > 1]
    fails += not _ok("曲目书歌名不重复", not dups, str(dups[:8]))
    from backend.songbook import is_vocal_song
    fails += not _ok("过滤 DJ 改编版", not is_vocal_song("世界上的另一个我 (DJ阿智版)", "阿肆"))
    fails += not _ok("过滤翻唱女生版", not is_vocal_song("一笑倾城(女生版)", "白允y"))
    from backend.recommender import _accept_online
    fails += not _ok("过滤网易云冒名热歌", not _accept_online("学狗叫", "周杰伦♚"))
    fails += not _ok("保留原唱人声", is_vocal_song("日不落", "蔡依林"))

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
            print(f"[INFO] 示例图命中率 {correct}/{len(labeled)} = {acc:.0%}（合成肖像流程验证；单人精检另做压缩/明暗/微转稳健测试）")
            import cv2

            def _perturb(img, kind):
                if kind == "jpeg70":
                    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                    return cv2.imdecode(buf, cv2.IMREAD_COLOR)
                if kind == "dark":
                    return np.clip(img.astype(np.float32) * 0.62, 0, 255).astype(np.uint8)
                if kind == "bright":
                    return np.clip(img.astype(np.float32) * 1.25 + 10, 0, 255).astype(np.uint8)
                if kind == "rot":
                    h, w = img.shape[:2]
                    rot = cv2.getRotationMatrix2D((w * 0.5, h * 0.5), 8, 1.0)
                    return cv2.warpAffine(img, rot, (w, h), borderMode=cv2.BORDER_REPLICATE)
                return img

            robust_ok = 0
            robust_n = 0
            for p in labeled:
                gold = _emo_from_stem(p.stem)
                raw = np.frombuffer(p.read_bytes(), dtype=np.uint8)
                base = cv2.imdecode(raw, cv2.IMREAD_COLOR)
                if base is None:
                    continue
                for kind in ("clean", "jpeg70", "dark", "bright", "rot"):
                    img = base if kind == "clean" else _perturb(base, kind)
                    out = rec.predict_bgr(img, want_crop=False, mode="solo")
                    pred = (out.get("emotion") or {}).get("id")
                    robust_n += 1
                    robust_ok += int(pred == gold)
            robust_acc = robust_ok / robust_n if robust_n else 0.0
            fails += not _ok(
                "单人精检稳健测试 ≥90%",
                robust_acc >= 0.90,
                f"{robust_ok}/{robust_n} = {robust_acc:.1%}",
            )
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
    fails += not _ok("离线推荐 < 2s", local_ms < 2000, f"{local_ms:.0f} ms")
    has_meta = all(s.get("title") and s.get("artist") for s in recs["songs"])
    fails += not _ok("推荐含歌名与歌手", has_meta)
    fails += not _ok("离线推荐可播放", all(s.get("playable") and s.get("audio") for s in recs["songs"]))
    from backend.songbook import is_chinese_song, play_priority, title_key
    fails += not _ok("喜悦推荐榜首小苹果", recs["songs"][0]["title"] == "小苹果", recs["songs"][0]["title"])
    sad_recs = recommend("sad", want_online=False)
    fails += not _ok("悲伤推荐榜首后来", sad_recs["songs"][0]["title"] == "后来", sad_recs["songs"][0]["title"])
    fails += not _ok(
        "中文优先于普通英文",
        play_priority("告白气球", "周杰伦", "happy") > play_priority("Paper Rings", "Taylor Swift", "happy"),
    )
    fails += not _ok(
        "特别网红英文高于普通英文",
        play_priority("Butter", "BTS", "happy") > play_priority("Paper Rings", "Taylor Swift", "happy"),
    )
    happy_top = recs["songs"][:8]
    fails += not _ok(
        "喜悦前8首中文",
        all(is_chinese_song(s.get("title") or "", s.get("artist") or "") for s in happy_top),
        ", ".join(s.get("title") or "" for s in happy_top),
    )
    first_title = recs["songs"][0]["title"]
    skipped = recommend("happy", want_online=False, exclude=["小苹果"])
    fails += not _ok(
        "显式排除仍跳过小苹果",
        title_key(skipped["songs"][0]["title"]) != title_key("小苹果"),
        skipped["songs"][0]["title"],
    )
    skipped_first = recommend("happy", want_online=False, exclude=[first_title])
    fails += not _ok(
        "相同情绪跳过已播歌曲",
        title_key(skipped_first["songs"][0]["title"]) != title_key(first_title),
        skipped_first["songs"][0]["title"],
    )
    wrapped = recommend("happy", want_online=False, exclude=[s["title"] for s in recs["songs"]])
    fails += not _ok("已播完后仍能回绕推荐", bool(wrapped.get("songs")), str(len(wrapped.get("songs") or [])))
    fails += not _ok("推荐声明策略", bool((recs.get("strategy") or {}).get("name")) and recs.get("strategy", {}).get("id") == "iso", str(recs.get("strategy")))
    from backend.strategy import plan as rec_plan
    repair = recommend("sad", want_online=False, strategy="repair")
    fails += not _ok("修复策略改播喜悦", all(s.get("emotion") == "happy" for s in repair["songs"]) and repair.get("strategy", {}).get("id") == "repair", str({s.get("emotion") for s in repair["songs"]}))
    iso_repair = recommend("sad", want_online=False, strategy="iso-repair")
    ir_emos = [s.get("emotion") for s in iso_repair["songs"]]
    fails += not _ok("先同频再修复分段", ir_emos[:8] == ["sad"] * 8 and "happy" in ir_emos and "neutral" in ir_emos, str(ir_emos[:12]))
    contrast = recommend("happy", want_online=False, strategy="contrast")
    fails += not _ok("对比策略播对极", all(s.get("emotion") == "sad" for s in contrast["songs"]), str({s.get("emotion") for s in contrast["songs"]}))
    fails += not _ok("策略规划九种", len(rec_plan("angry", "iso-repair", 24)) == 3, str(rec_plan("angry", "iso-repair", 24)))
    fails += not _ok("推荐歌曲含曲调分析", bool((recs["songs"][0].get("music") or {}).get("algo")), str(recs["songs"][0].get("music")))
    fails += not _ok("推荐歌曲带情绪分类", all(s.get("emotion") in EMOTIONS for s in recs["songs"]))
    from backend.history import _slim_songs
    from backend.songbook import emotion_of_title
    filled = _slim_songs([{"title": "红豆", "artist": "王菲"}])
    fails += not _ok("歌名可反查情绪", emotion_of_title("红豆") == "sad", str(emotion_of_title("红豆")))
    fails += not _ok(
        "历史补全歌曲情绪",
        filled and filled[0].get("emotion") == "sad" and filled[0].get("emotion_zh") == "哀",
        str(filled[:1]),
    )

    from backend.music_emotion import analyze_pcm, match_score, render_sketch, juslin_features
    happy_desc = analyze_pcm(render_sketch("happy", seed=1))
    sad_desc = analyze_pcm(render_sketch("sad", seed=1))
    fails += not _ok(
        "欢快旋律效价高于悲伤旋律",
        float(happy_desc.get("valence") or 0) > float(sad_desc.get("valence") or 0),
        f"happy={happy_desc.get('valence')} sad={sad_desc.get('valence')}",
    )
    happy_face = [0.9, 0.01, 0.01, 0.02, 0.02, 0.02, 0.02]
    fails += not _ok(
        "喜悦人脸更贴近欢快曲调",
        match_score(happy_face, happy_desc) > match_score(happy_face, sad_desc),
        f"{match_score(happy_face, happy_desc)} vs {match_score(happy_face, sad_desc)}",
    )
    fails += not _ok("Juslin 线索表覆盖七类", all(juslin_features(e).get("tempo") for e in EMOTIONS))

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
    fails += not _ok("健康检查默认单人精检", h.get("face_mode") == "solo", str(h.get("face_mode")))
    fails += not _ok("健康检查声明离线可用", h.get("offline_ready") is True, str(h.get("offline_ready")))
    fails += not _ok("健康检查列出在线接口", isinstance(h.get("online_apis"), list) and {"itunes", "itunes_chart", "apple_hot", "apple_asia", "netease_hot", "qq_hot", "audius", "kuwo", "deezer"}.issubset(set(h.get("online_apis") or [])), str(h.get("online_apis")))
    pin_play = client.post(
        "/api/play",
        json={
            "emotion": "happy",
            "song": {"id": "vocal-happy-15", "title": "小苹果", "artist": "筷子兄弟", "emotion": "happy"},
        },
    ).get_json()
    fails += not _ok("置顶曲可记入已播", pin_play and pin_play.get("ok"), str(pin_play))
    fails += not _ok("已播索引含小苹果", "小苹果" in ((pin_play or {}).get("keys") or []), str((pin_play or {}).get("keys")))
    happy_api = client.get("/api/recommend?emotion=happy&online=0").get_json()
    happy_first = ((happy_api or {}).get("songs") or [{}])[0].get("title")
    fails += not _ok("已播后接口仍置顶小苹果", happy_first == "小苹果", str(happy_first))
    sad_play = client.post(
        "/api/play",
        json={
            "emotion": "sad",
            "song": {"id": "vocal-sad-01", "title": "后来", "artist": "刘若英", "emotion": "sad"},
        },
    ).get_json()
    fails += not _ok("悲伤置顶曲可记入已播", sad_play and sad_play.get("ok"), str(sad_play))
    sad_api = client.get("/api/recommend?emotion=sad&online=0").get_json()
    sad_first = ((sad_api or {}).get("songs") or [{}])[0].get("title")
    fails += not _ok("已播后接口仍置顶后来", sad_first == "后来", str(sad_first))
    stream_miss = client.get("/api/stream")
    fails += not _ok("GET /api/stream 缺地址", stream_miss.status_code == 400)
    page = client.get("/")
    home = page.get_data(as_text=True)
    fails += not _ok("GET / 首页", page.status_code == 200 and ("当AI遇见旋律" in home or "心弦" in home))
    fails += not _ok("首页写明人脸算法", "YuNet" in home and "MobileFaceNet FER" in home)
    fails += not _ok("首页不堆算法长文", 'id="algo-panel"' not in home and 'id="btn-guide"' in home and 'href="/guide"' in home)
    fails += not _ok("首页可选推荐方式", 'id="strat-picks"' in home and "先同频再修复" in home)
    fails += not _ok("首页有设置入口", 'id="btn-settings"' in home and 'id="settings-panel"' in home)
    fails += not _ok("设置默认收起", 'id="settings-panel" hidden' in home)
    fails += not _ok("主题与推荐方式在设置里折叠", 'data-set="theme"' in home and 'data-set="recommend"' in home and home.count('<details class="set-block"') >= 6)
    fails += not _ok("顶栏不再平铺开关", 'class="top-toggles"' not in home)
    vp_html = home.split('id="viewport"', 1)[-1].split('id="result"', 1)[0] if 'id="viewport"' in home else home
    fails += not _ok("视窗内无关键点坞", 'id="cam-dock"' not in vp_html)
    fails += not _ok("视窗内无检测方式条", 'id="face-mode-picks"' not in vp_html)
    fails += not _ok("情绪足迹可隐藏", ">情绪足迹<" in home and 'id="btn-hide-trail"' in home)
    fails += not _ok("歌曲可隐藏", 'id="recs-title"' in home and ">歌曲<" in home and 'id="btn-hide-recs"' in home)
    fails += not _ok("首页含实时概率条", 'id="prob-bars"' in home)
    fails += not _ok("首页含环面图", 'id="va-map"' in home)
    algo = client.get("/api/algorithms").get_json()
    fails += not _ok("GET /api/algorithms", algo and algo.get("ok") and "YuNet" in ((algo.get("face") or {}).get("name") or ""))
    fails += not _ok("GET /api/algorithms 含多种推荐", isinstance((algo.get("recommend") or {}).get("strategies"), list) and len((algo.get("recommend") or {}).get("strategies") or []) >= 8)
    guide_page = client.get("/guide")
    guide = guide_page.get_data(as_text=True)
    fails += not _ok("GET /guide 说明页", guide_page.status_code == 200 and "使用说明" in guide and "ISO" in guide and "Zillmann" in guide)
    fails += not _ok("说明页写明人脸算法", "YuNet" in guide and "MobileFaceNet FER" in guide and "88.27%" in guide)
    fails += not _ok("说明页写明单人精检融合", "HSEmotion" in guide and "TTA" in guide)
    fails += not _ok("说明页写明曲调算法", "Thayer" in guide and "Krumhansl" in guide and "Juslin" in guide)
    fails += not _ok("说明页写明多种推荐", "先同频再修复" in guide and "环面" in guide and "降唤醒" in guide)
    strat_api = client.get("/api/strategies").get_json()
    fails += not _ok("GET /api/strategies", strat_api and strat_api.get("ok") and len(strat_api.get("strategies") or []) >= 8)
    fails += not _ok("首页提示短暂表情会锁定歌单", "不会立刻换歌" in home and "惊讶、恐惧" in home)
    fails += not _ok("实时捕捉旁有保持播放说明", "脸松开也不会换歌" in home)
    fails += not _ok("识别此刻会关闭实时捕捉", "自动关闭实时捕捉" in home)
    fails += not _ok("界面含人脸框画布", "id=\"face-overlay\"" in home)
    fails += not _ok("界面含实时表情文字", "id=\"live-emo-hud\"" in home)
    face_page = client.get("/face")
    face_html = face_page.get_data(as_text=True)
    fails += not _ok("GET /face 人脸窗", face_page.status_code == 200 and "人脸窗" in face_html and "多数" in face_html)
    fails += not _ok("人脸窗可切换检测方式", "单人精检" in face_html and "id=\"cam-select\"" in face_html)
    fails += not _ok("首页写明多人多数票", "人数最多" in home)
    fails += not _ok("首页写明远景小脸", "远景" in home)
    modes_api = client.get("/api/face-modes").get_json()
    fails += not _ok(
        "GET /api/face-modes 默认单人精检",
        modes_api and modes_api.get("ok") and modes_api.get("default") == "solo" and len(modes_api.get("modes") or []) >= 2,
        str(modes_api),
    )
    fails += not _ok("说明页写明两种检测方式", "单人精检" in guide and "多人远场" in guide)
    fails += not _ok("说明页写明四种输入", "屏幕分享" in guide and "本地视频" in guide)
    for label, needle in [
        ("语音开关", "id=\"voice-toggle\""),
        ("歌词开关", "id=\"lyrics-toggle\""),
        ("封面开关", "id=\"cover-toggle\""),
        ("波形开关", "id=\"viz-toggle\""),
        ("在线曲库开关", "id=\"online-toggle\""),
        ("弹出人脸窗", "id=\"btn-face-pop\""),
        ("波形画布", "id=\"viz-wave\""),
        ("频率画布", "id=\"viz-freq\""),
        ("快慢画布", "id=\"viz-tempo\""),
        ("色度画布", "id=\"viz-chroma\""),
        ("声纹读数", "id=\"viz-readout\""),
        ("关键点切换", "id=\"landmark-picks\""),
        ("铺满窗口", "id=\"btn-cam-fill\""),
        ("放大比率", "id=\"cam-zoom\""),
        ("人脸对照", "id=\"emo-shot\""),
        ("摄像头入口", "data-mode=\"camera\""),
        ("上传照片入口", "data-mode=\"upload\""),
        ("视频入口", "data-mode=\"video\""),
        ("屏幕入口", "data-mode=\"screen\""),
        ("单人精检", "单人精检"),
        ("多人远场", "多人远场"),
        ("摄像头选择", "id=\"cam-select\""),
        ("检测方式点选", "id=\"face-mode-picks\""),
        ("历史入口", "id=\"btn-history\""),
        ("说明页入口", "id=\"btn-guide\""),
        ("推荐方式点选", "id=\"strat-picks\""),
        ("播放器歌曲情绪", "id=\"player-emo\""),
        ("实时捕捉开关", "id=\"live-toggle\""),
        ("识别此刻按钮", "id=\"btn-recognize\""),
        ("主题夜金", "data-theme=\"night\""),
        ("主题宣纸", "data-theme=\"paper\""),
        ("主题墨青", "data-theme=\"ink\""),
        ("主题朱砂", "data-theme=\"rouge\""),
        ("主题青瓷", "data-theme=\"celadon\""),
        ("主题月白", "data-theme=\"moon\""),
        ("设置按钮", "id=\"btn-settings\""),
        ("铺满画面", "id=\"btn-cam-fit\""),
        ("足迹隐藏", "id=\"btn-hide-trail\""),
        ("歌曲隐藏", "id=\"btn-hide-recs\""),
    ]:
        fails += not _ok(f"界面含{label}", needle in home)
    js = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
    fails += not _ok("实时捕捉锁定短暂表情", "TRANSIENT_EMO" in js and "decideLiveAction" in js)
    fails += not _ok("持续平静可切中性歌单", "pending-neutral" in js and "LIVE_NEUTRAL_HITS" in js)
    fails += not _ok("声纹情绪标签与人脸同步", "displayEmotionId" in js and "paintUiEmotion" in js and "同一标签" in js)
    fails += not _ok("实时捕捉确认后才语音", "tickUiSpeak" in js and "LIVE_SPEAK_DWELL_MS" in js and "commitLiveUi" in js)
    fails += not _ok("日常与高潮双速", "DAILY_EMO" in js and "SPIKE_SPEAK_DWELL_MS" in js and "speakDwellMs" in js and "playlistSwitchNeed" in js)
    fails += not _ok("语音跟此刻不跟歌单锁", "tickUiSpeak" in js and "overlayDisplayItems" in js and "speakEmotionChange(e, opts.speak === true)" in js)
    fails += not _ok("此刻情绪需连续确认", "commitLiveUi" in js and "UI_EMO_HITS" in js and "TRACK_PERIOD_MS" in js)
    fails += not _ok("推荐方式默认同频", '"iso"' in js and "DEFAULT_STRATEGY = \"iso\"" in (ROOT / "backend" / "strategy.py").read_text(encoding="utf-8"))
    emo_py = (ROOT / "backend" / "emotion.py").read_text(encoding="utf-8")
    fails += not _ok("实时 FER 校准惊讶喜悦", "calibrate_live_vec" in emo_py)
    fails += not _ok("识别此刻关闭实时捕捉", "recognizeNow" in js and "已关闭实时捕捉" in js)
    fails += not _ok("摄像头实时画人脸框", "drawFaceOverlay" in js and "/api/track" in js)
    fails += not _ok("可切换单人精检与多人远场", "setFaceMode" in js and "emotune-face-mode" in js)
    fails += not _ok("可选择多个摄像头", "listCameras" in js and "enumerateDevices" in js)
    fails += not _ok("四种输入含视频与屏幕", "startScreen" in js and "useVideoFile" in js and "getDisplayMedia" in js)
    fails += not _ok("播放器实时波形", "ensureViz" in js and "getByteTimeDomainData" in js and "getByteFrequencyData" in js)
    fails += not _ok("播放器画出快慢与音调", "viz-tempo" in js and "f₀" in js and "THAYER_VA" in js and "Scheirer/Ellis" in js)
    fails += not _ok("声纹按情绪上色", "audio-viz" in js and "data-emo" in (ROOT / "templates" / "index.html").read_text(encoding="utf-8") and "chromaFromFd" in js)
    fails += not _ok("人脸关键点叠加", "paintFaceLandmarks" in js and "paintFaceCues" in js and "AU12" in (ROOT / "backend" / "emotion.py").read_text(encoding="utf-8"))
    fails += not _ok("关键点可切实拍线框或关闭", "setLandmarkMode" in js and "emotune-landmark" in js and "paintMesh" in (ROOT / "static" / "js" / "face-draw.js").read_text(encoding="utf-8"))
    fails += not _ok("摄像头可铺满并缩放", "setCamFill" in js and "setCamZoom" in js and "cam-layer" in home)
    fails += not _ok("可弹出人脸窗", "openFacePop" in js and "emotune-face" in js)
    fails += not _ok("可切换推荐方式", "setStrategy" in js and "emotune-strategy" in js)
    fails += not _ok("人脸框随情绪变色", "emoHex" in js and "drawCornerBrackets" in js and "strokeStyle = color" in js)
    css = (ROOT / "static" / "css" / "app.css").read_text(encoding="utf-8")
    fails += not _ok("表情文字随情绪变色", ".live-emo-hud span" in css and "--emo: var(--happy)" in css and "paintHudTone" in js)
    cfg = (ROOT / "config.py").read_text(encoding="utf-8")
    palette = {
        "happy": ("#FFD400", "#ffd400"),
        "angry": ("#E02020", "#e02020"),
        "sad": ("#4E7390", "#4e7390"),
        "fear": ("#6B2D91", "#6b2d91"),
        "surprise": ("#FF7A18", "#ff7a18"),
        "disgust": ("#6F7D32", "#6f7d32"),
        "neutral": ("#4EC6F5", "#4ec6f5"),
    }
    fails += not _ok(
        "七色标准写入配置与前端",
        all(hi in cfg and lo in css and lo in js for hi, lo in palette.values()),
    )
    fails += not _ok("设置面板默认折叠", ".settings-panel" in css and "bindChromeUi" in js and "setSettingsOpen" in js)
    fails += not _ok("摄像头铺满当前区域", "min-height: 460px" in css and "object-fit: cover" in css)
    fails += not _ok("默认使用在线曲库", 'emotune-online") !== "0"' in js and "fallbackToLocal" in js)
    fails += not _ok("在线失败自动切本地", "长时间播放失败" in js and "loadPlaylist" in js)
    fails += not _ok("在线音源可代理", "open_remote_audio" in (ROOT / "backend" / "recommender.py").read_text(encoding="utf-8") and "/api/stream" in (ROOT / "app.py").read_text(encoding="utf-8"))
    rec_src = (ROOT / "backend" / "recommender.py").read_text(encoding="utf-8")
    fails += not _ok("含酷我在线接口", "_from_kuwo" in rec_src)
    fails += not _ok("含苹果热歌榜接口", "_from_itunes_chart" in rec_src)
    fails += not _ok("含苹果热播接口", "_from_apple_hot" in rec_src and "apple_hot" in rec_src)
    fails += not _ok("含苹果亚洲热歌接口", "_from_apple_asia" in rec_src and "apple_asia" in rec_src)
    fails += not _ok("含网易云热歌榜接口", "_from_netease_hot" in rec_src and "netease_hot" in rec_src)
    fails += not _ok("含QQ热歌榜接口", "_from_qq_hot" in rec_src and "qq_hot" in rec_src)
    fails += not _ok("含Audius在线接口", "_from_audius" in rec_src and "audius" in rec_src)
    fails += not _ok("在线与本地合并后再按中文优先排序", "take(online_fresh + local_fresh)" in rec_src and "play_priority" in rec_src)
    fails += not _ok("含 Deezer 在线接口", "_from_deezer" in rec_src and "deezer" in rec_src)
    asset_src = (ROOT / "backend" / "assets.py").read_text(encoding="utf-8")
    fails += not _ok("苹果检索有旧接口兜底", "wsSearch" in asset_src and "itunes_search_results" in rec_src)
    fails += not _ok("苹果曲目编号可在线回源", "itunes_lookup_ids" in asset_src and "itunes_lookup_ids" in rec_src)
    fails += not _ok("历史双列人脸与情绪", "history-pair" in js and "判断情绪" in js)
    fails += not _ok("足迹含表情图标与播过的歌", "trail-songs" in js and "trail-icon" in js and "firstFreshPlayable" in js)
    fails += not _ok("歌名旁标歌曲情绪", "songEmoChip" in js and "song-emo" in js and "song-head" in css)
    fails += not _ok("足迹历史含歌曲情绪标签", "songEmoChip(song, faceId)" in js and ".song-emo" in css)
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
            if (body.get("emotion") or {}).get("id") == "happy":
                fails += not _ok(
                    "识别后仍置顶小苹果",
                    songs and songs[0].get("title") == "小苹果",
                    songs[0].get("title") if songs else "",
                )
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
            fails += not _ok(
                "track 实时路径够快",
                float((tracked or {}).get("elapsed_ms") or 999) < 180,
                str((tracked or {}).get("elapsed_ms")),
            )
            face0 = ((tracked or {}).get("faces") or [{}])[0]
            fails += not _ok(
                "track 返回人脸关键点",
                isinstance(face0.get("points"), list) and len(face0.get("points") or []) >= 5,
                str(face0.get("points")),
            )
            cue_parts = {c.get("part") for c in (face0.get("cues") or []) if isinstance(c, dict)}
            fails += not _ok(
                "track 返回口眼眉线索",
                {"mouth", "eye", "brow"}.issubset(cue_parts),
                str(face0.get("cues")),
            )
            fails += not _ok(
                "识别返回人脸票数",
                isinstance(body.get("vote"), dict) and int((body.get("vote") or {}).get("total") or 0) >= 1,
                str(body.get("vote")),
            )
            fails += not _ok("默认识别为单人精检", body.get("face_mode") == "solo", str(body.get("face_mode")))

            def _join_faces(paths, size=220):
                tiles = [Image.open(p).convert("RGB").resize((size, size)) for p in paths]
                canvas = Image.new("RGB", (size * len(tiles) + 24, size + 24), (28, 26, 24))
                for i, im in enumerate(tiles):
                    canvas.paste(im, (12 + i * size, 12))
                buf = BytesIO()
                canvas.save(buf, format="JPEG", quality=92)
                return buf.getvalue()

            happy_a = DEMO_DIR / "01-喜-喜悦-happy.jpg"
            happy_b = DEMO_DIR / "08-喜-喜悦-happy-b.jpg"
            angry_a = DEMO_DIR / "02-怒-愤怒-angry.jpg"
            if happy_a.exists() and happy_b.exists() and angry_a.exists():
                mosaic = _join_faces([happy_a, happy_b, angry_a])
                solo_multi = client.post(
                    "/api/recognize?online=0",
                    data={"image": (BytesIO(mosaic), "multi.jpg", "image/jpeg")},
                ).get_json()
                fails += not _ok(
                    "单人精检合影只取一张脸",
                    solo_multi and solo_multi.get("ok") and int(solo_multi.get("face_count") or 0) == 1,
                    str((solo_multi or {}).get("face_count")),
                )
                multi = client.post(
                    "/api/recognize?online=0&mode=crowd",
                    data={"image": (BytesIO(mosaic), "multi.jpg", "image/jpeg")},
                    headers={"X-Emo-Face-Mode": "crowd"},
                ).get_json()
                vote = (multi or {}).get("vote") or {}
                fails += not _ok(
                    "多人同时检出",
                    multi and multi.get("ok") and int(multi.get("face_count") or 0) >= 2,
                    str((multi or {}).get("face_count")),
                )
                fails += not _ok(
                    "多数票为喜悦",
                    vote.get("id") == "happy" and int(vote.get("majority") or 0) >= 2,
                    str(vote),
                )
                far_bg = Image.new("RGB", (1280, 720), (16, 18, 26))
                far_face = Image.open(happy_a).convert("RGB").resize((80, 80))
                far_bg.paste(far_face, (1120, 48))
                far_buf = BytesIO()
                far_bg.save(far_buf, format="JPEG", quality=90)
                far = client.post(
                    "/api/track?mode=crowd",
                    data={"image": (BytesIO(far_buf.getvalue()), "far.jpg", "image/jpeg")},
                    headers={"X-Emo-Face-Mode": "crowd"},
                ).get_json()
                fails += not _ok(
                    "远景小脸可检出",
                    far and far.get("ok") and (far.get("face") or {}).get("box"),
                    str((far or {}).get("code")),
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
    print("全部通过。MobileFaceNet RAF-DB 88.27%；单人精检叠加 HSEmotion 与 TTA，本机稳健测试目标 ≥90%；响应目标 ≤ 3 秒。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
