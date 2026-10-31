# -*- coding: utf-8 -*-
"""
心弦 EmoTune — 人脸情绪识别歌曲推荐系统
Flask 入口：路由（C）调用识别/推荐（M），模板与静态资源为视图（V）。
"""
from __future__ import annotations

import base64
import logging
import sys
import threading
import time

from flask import (
    Flask,
    Response,
    jsonify,
    render_template,
    request,
    send_file,
    session,
)

from config import (
    DEMO_DIR,
    EMOTIONS,
    HOST,
    MAX_CONTENT_MB,
    PORT,
    SECRET_KEY,
    STATIC_DIR,
    TEMPLATE_DIR,
)
from backend import history
from backend.recommender import recommend, song_file
from backend.songbook import front_pin_keys
from backend.strategy import DEFAULT_STRATEGY, public_catalog

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("emotune")

app = Flask(__name__, static_folder=str(STATIC_DIR), template_folder=str(TEMPLATE_DIR))
app.secret_key = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_MB * 1024 * 1024
app.config["JSON_AS_ASCII"] = False
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.json.ensure_ascii = False


def _session_id() -> str:
    sid = session.get("sid")
    if not sid:
        sid = history.new_session_id()
        session["sid"] = sid
    return sid


@app.after_request
def allow_local_lecture(resp):
    """讲堂页面从文件夹打开时，仍可调用本机识别接口。"""
    origin = request.headers.get("Origin")
    if origin:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Vary"] = "Origin"
        resp.headers["Access-Control-Allow-Headers"] = (
            "Content-Type, X-Emo-Source, X-Emo-Online, X-Emo-Strategy, X-Emo-Face-Mode"
        )
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return resp


@app.before_request
def lecture_preflight():
    if request.method == "OPTIONS" and request.path.startswith("/api/"):
        return app.make_response(("", 204))
    return None


@app.before_request
def classroom_demo_mode():
    """网页设置「课堂演示模式」时，这次识别按演示规则校正（见 backend.emotion._demo_adjust）。"""
    from backend.emotion import DEMO_MODE

    DEMO_MODE.set((request.headers.get("X-Emo-Demo") or request.args.get("demo") or "0").strip() == "1")


@app.before_request
def live_fast_mode():
    """实时识别（摄像头 / 视频 / 屏幕的 -live 来源）走快速路径；识别此刻、上传照片仍用完整精度。"""
    from backend.emotion import FAST_MODE

    src = (request.headers.get("X-Emo-Source") or request.args.get("source") or "").strip()
    FAST_MODE.set(src.endswith("-live"))


def _b64_to_bytes(raw: str) -> bytes:
    if not raw:
        return b""
    if "," in raw and raw.strip().startswith("data:"):
        raw = raw.split(",", 1)[1]
    return base64.b64decode(raw)


def _read_face_mode() -> str:
    from backend.emotion import DEFAULT_FACE_MODE, normalize_face_mode

    raw = (
        request.headers.get("X-Emo-Face-Mode")
        or request.args.get("mode")
        or request.args.get("face_mode")
        or ""
    ).strip()
    if not raw and request.is_json:
        raw = str((request.get_json(silent=True) or {}).get("mode") or "")
    return normalize_face_mode(raw) if raw else DEFAULT_FACE_MODE


def _history_exclude(emotion: str) -> list[str]:
    """已播跳过不含置顶曲；显式 exclude= 仍由 recommend() 处理。"""
    pins = front_pin_keys()
    return [key for key in history.played_keys(emotion) if key not in pins]


def _collect_frames() -> list[bytes]:
    frames: list[bytes] = []
    if request.files:
        for key in ("image", "file", "photo"):
            f = request.files.get(key)
            if f:
                frames.append(f.read())
        for fs in request.files.getlist("images"):
            frames.append(fs.read())
    if request.is_json:
        data = request.get_json(silent=True) or {}
        if data.get("image"):
            frames.append(_b64_to_bytes(data["image"]))
        for item in data.get("images") or []:
            frames.append(_b64_to_bytes(item))
    if request.form.get("image"):
        frames.append(_b64_to_bytes(request.form.get("image")))
    return [f for f in frames if f]


@app.errorhandler(413)
def too_large(_e):
    return jsonify({"ok": False, "error": f"图片过大，请压缩到 {MAX_CONTENT_MB}MB 以内", "code": "TOO_LARGE"}), 413


@app.errorhandler(404)
def not_found(_e):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "接口不存在", "code": "NOT_FOUND"}), 404
    return render_template("index.html", emotions=EMOTIONS), 404


@app.errorhandler(500)
def server_error(_e):
    logger.exception("服务器错误")
    return jsonify({"ok": False, "error": "服务暂时不可用，请稍后重试", "code": "INTERNAL"}), 500


@app.route("/")
def index():
    _session_id()
    return render_template("index.html", emotions=EMOTIONS)


@app.route("/face")
def face_pop():
    _session_id()
    return render_template("face.html", emotions=EMOTIONS)


@app.route("/guide")
def guide():
    _session_id()
    return render_template("guide.html", emotions=EMOTIONS, strategies=public_catalog())


@app.route("/pose")
def pose():
    """表情演示教程：学生怎么扮出系统认得出的七类表情。"""
    from backend.pose_guide import NEUTRAL, POSES, TIPS, demo_photos

    _session_id()
    return render_template("pose.html", poses=POSES, neutral=NEUTRAL, tips=TIPS, photos=demo_photos())


@app.route("/api/health")
def health():
    from config import DEFAULT_FACE_MODE, FER_FILE, MODEL_DIR, ONLINE_APIS, YUNET_FILE
    from backend.recommender import load_catalog

    yunet = (MODEL_DIR / YUNET_FILE).exists()
    fer = (MODEL_DIR / FER_FILE).exists()
    catalog = load_catalog()
    local_n = len(catalog)
    return jsonify(
        {
            "ok": True,
            "name": "心弦 EmoTune",
            "models": {"yunet": yunet, "fer": fer},
            "local_songs": local_n,
            "offline_ready": bool(yunet and fer and local_n >= 20),
            "online_apis": list(ONLINE_APIS),
            "emotions": list(EMOTIONS.keys()),
            "algorithms": {
                "face": "YuNet + MobileFaceNet FER × HSEmotion，可切换单人精检 / 多人远场",
                "music": "Thayer 二维模型 + Krumhansl–Kessler 调式",
                "recommend": "可选多种推荐方式（默认同频）",
            },
            "face_mode": DEFAULT_FACE_MODE,
        }
    )


@app.route("/api/emotions")
def emotions_api():
    items = []
    for key in ["happy", "angry", "sad", "fear", "surprise", "disgust", "neutral"]:
        m = EMOTIONS[key]
        items.append(
            {
                "id": m["id"],
                "zh": m["zh"],
                "name": m["name"],
                "english": m["english"],
                "genre": m["genre"],
                "copy": m["copy"],
                "color": m["color"],
                "hint": m["hint"],
            }
        )
    return jsonify({"ok": True, "emotions": items})


LIVE_SAVE_GAP_S = 30.0
_LIVE_SAVE: dict[str, dict] = {}
_LIVE_SAVE_LOCK = threading.Lock()


@app.route("/api/recognize", methods=["POST"])
def recognize():
    t0 = time.perf_counter()
    frames = _collect_frames()
    if not frames:
        return jsonify({"ok": False, "error": "请先开启摄像头、分享屏幕、打开视频，或上传一张人脸照片", "code": "NO_IMAGE"}), 400
    source = (request.headers.get("X-Emo-Source") or request.args.get("source") or "upload").strip()
    if request.is_json:
        source = (request.get_json(silent=True) or {}).get("source", source)

    from backend.emotion import get_recognizer

    rec = get_recognizer()
    face_mode = _read_face_mode()
    if len(frames) == 1:
        result = rec.predict_bytes(frames[0], mode=face_mode)
    else:
        result = rec.predict_many_bytes(frames[:5], mode=face_mode)

    if not result.get("ok"):
        result["elapsed_ms"] = round(result.get("elapsed_ms") or (time.perf_counter() - t0) * 1000.0, 1)
        return jsonify(result)

    emotion_id = result["emotion"]["id"]
    want_online = (
        (request.args.get("online") or request.headers.get("X-Emo-Online") or "1").strip() == "1"
    )
    strategy = (request.args.get("strategy") or request.headers.get("X-Emo-Strategy") or DEFAULT_STRATEGY).strip()
    played = history.played_keys(emotion_id)
    fresh = (request.args.get("fresh") or request.headers.get("X-Emo-Fresh") or "1").strip() == "1"
    exclude = _history_exclude(emotion_id) if fresh else []
    # 两段式：先用本地曲库立刻出歌单开播，在线热歌由网页随后在后台补进来（网络慢也不耽误换歌）
    two_phase = want_online and (request.args.get("two_phase") or request.headers.get("X-Emo-Two-Phase") or "1").strip() == "1"
    recs = recommend(
        emotion_id,
        want_online=want_online and not two_phase,
        exclude=exclude,
        skip_played=fresh,
        face_scores=(result.get("emotion") or {}).get("scores"),
        strategy=strategy,
    )
    result["recommendations"] = recs
    result["online_pending"] = bool(two_phase)
    result["algorithms"] = {
        "face": "YuNet + MobileFaceNet FER",
        "music": recs.get("strategy", {}).get("music"),
        "recommend": recs.get("strategy", {}).get("name"),
        "strategy": recs.get("strategy"),
    }
    result["source"] = source
    result["played_keys"] = played
    total_ms = (time.perf_counter() - t0) * 1000.0
    result["total_ms"] = round(total_ms, 1)

    # 实时识别每 1.4 秒一帧：同一情绪 30 秒内只记一条，情绪变了才新记，免得足迹被重复记录淹没
    if source.endswith("-live"):
        with _LIVE_SAVE_LOCK:
            last = _LIVE_SAVE.get(source) or {}
            same = last.get("emo") == emotion_id and time.time() - float(last.get("ts") or 0) < LIVE_SAVE_GAP_S
            if same and last.get("id"):
                result["history_id"] = last["id"]
                result["history_saved"] = False
                return jsonify(result)
    try:
        item = history.add_record(
            _session_id(),
            {
                "source": source,
                "emotion": result["emotion"],
                "face": result.get("face"),
                "songs": recs.get("songs", []),
                "elapsed_ms": result.get("elapsed_ms"),
            },
        )
        result["history_id"] = item.get("id")
        result["history_saved"] = True
        if source.endswith("-live"):
            with _LIVE_SAVE_LOCK:
                _LIVE_SAVE[source] = {"emo": emotion_id, "ts": time.time(), "id": item.get("id")}
    except Exception:
        logger.exception("写入识别历史失败")
    return jsonify(result)


@app.route("/api/track", methods=["POST"])
def track():
    """摄像头实时追踪：只做人脸框与表情，不推荐歌曲、不写历史。"""
    frames = _collect_frames()
    if not frames:
        return jsonify({"ok": False, "error": "没有画面", "code": "NO_IMAGE", "track": True, "faces": []}), 400
    from backend.emotion import get_recognizer

    rec = get_recognizer()
    face_mode = _read_face_mode()
    result = rec.predict_track_bytes(frames[0], mode=face_mode)
    result["track"] = True
    return jsonify(result)


@app.route("/api/recommend")
def recommend_api():
    emotion = (request.args.get("emotion") or "neutral").strip()
    want_online = request.args.get("online", "1") == "1"
    strategy = (request.args.get("strategy") or DEFAULT_STRATEGY).strip()
    played = history.played_keys(emotion)
    fresh = (request.args.get("fresh") or "1").strip() == "1"
    exclude = _history_exclude(emotion) if fresh else []
    data = recommend(emotion, want_online=want_online, exclude=exclude, strategy=strategy, skip_played=fresh)
    data["played_keys"] = played
    return jsonify({"ok": True, **data})


@app.route("/api/strategies")
def strategies_api():
    return jsonify({"ok": True, "default": DEFAULT_STRATEGY, "strategies": public_catalog()})


@app.route("/api/face-modes")
def face_modes_api():
    from backend.emotion import DEFAULT_FACE_MODE, public_face_modes

    return jsonify({"ok": True, "default": DEFAULT_FACE_MODE, "modes": public_face_modes()})


@app.route("/api/algorithms")
def algorithms_api():
    from backend.music_emotion import ALGO_NAME
    from backend.emotion import DEFAULT_FACE_MODE, public_face_modes

    catalog = public_catalog()
    return jsonify(
        {
            "ok": True,
            "guide": "/guide",
            "face": {
                "name": "YuNet + MobileFaceNet FER × HSEmotion B0",
                "classic": "Ekman 七类基本情绪；OpenCV Zoo 人脸表情识别；HSEmotion AffectNet",
                "acc": "RAF-DB 88.27%（MobileFaceNet）；单人精检叠加 TTA 与 HSEmotion 融合，本机稳健测试 ≥90%",
                "where": "本机 ONNX，不上传图像",
                "default_mode": DEFAULT_FACE_MODE,
                "modes": public_face_modes(),
            },
            "music": {
                "name": ALGO_NAME,
                "classic": "Thayer 1989 效价-唤醒 + Krumhansl–Kessler 1982 调式 + Juslin 2001 声学线索",
                "where": "本机 numpy / scipy，不依赖云端",
            },
            "recommend": {
                "name": "多种可选推荐方式",
                "classic": "ISO 原则、心境管理、Russell 环面、Thayer 唤醒调节",
                "rule": "主页点选同频 / 修复 / 先同频再修复等；完整理论见 /guide",
                "default": DEFAULT_STRATEGY,
                "strategies": catalog,
            },
        }
    )


@app.route("/api/play", methods=["POST"])
def play_mark():
    data = request.get_json(silent=True) or {}
    song = data.get("song") if isinstance(data.get("song"), dict) else {}
    emotion = (data.get("emotion") or song.get("emotion") or "").strip()
    history_id = (data.get("history_id") or "").strip() or None
    row = history.mark_played(emotion, song, history_id=history_id)
    if not row:
        return jsonify({"ok": False, "error": "缺少歌曲", "code": "NO_PLAY"}), 400
    return jsonify({"ok": True, "played": row, "keys": history.played_keys(emotion)})


@app.route("/api/stream")
def stream_audio():
    """Same-origin proxy for online 30s previews so the browser can play them."""
    from backend.recommender import open_remote_audio

    url = (request.args.get("u") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "缺少音源", "code": "NO_STREAM"}), 400
    remote = open_remote_audio(url, request.headers.get("Range"))
    if remote is None:
        return jsonify({"ok": False, "error": "该在线音源暂时不可播放", "code": "BAD_STREAM"}), 502

    def generate():
        try:
            for chunk in remote.iter_content(65536):
                if chunk:
                    yield chunk
        finally:
            remote.close()

    resp = Response(generate(), status=remote.status_code)
    resp.headers["Content-Type"] = remote.headers.get("Content-Type", "audio/mpeg")
    for key in ("Content-Length", "Content-Range", "Accept-Ranges"):
        if remote.headers.get(key):
            resp.headers[key] = remote.headers[key]
    resp.headers["Cache-Control"] = "public, max-age=120"
    return resp


@app.route("/api/audio/<song_id>")
def audio(song_id: str):
    found = song_file(song_id)
    if not found:
        return jsonify({"ok": False, "error": "歌曲不存在", "code": "NO_SONG"}), 404
    path, mime = found
    return send_file(path, mimetype=mime, as_attachment=False, download_name=path.name, conditional=True)


@app.route("/api/audio/<song_id>/download")
def audio_download(song_id: str):
    found = song_file(song_id)
    if not found:
        return jsonify({"ok": False, "error": "歌曲不存在", "code": "NO_SONG"}), 404
    path, mime = found
    return send_file(path, mimetype=mime, as_attachment=True, download_name=path.name)


@app.route("/api/lyrics/<song_id>")
def lyrics_api(song_id: str):
    from backend.lyrics import get_lyrics

    title = (request.args.get("title") or "").strip()
    artist = (request.args.get("artist") or "").strip()
    duration = 0.0
    raw_dur = (request.args.get("duration") or "").strip()
    try:
        duration = float(raw_dur or 0.0)
    except ValueError:
        duration = 0.0
    return jsonify(get_lyrics(song_id, title=title, artist=artist, duration=duration))


@app.route("/api/history")
def history_list():
    items = history.list_records()
    total = len(items)
    try:
        limit = int(request.args.get("limit") or 0)
        offset = max(0, int(request.args.get("offset") or 0))
    except ValueError:
        limit, offset = 0, 0
    if limit > 0:
        # 分页（按时间倒序）：网页先拿最新一页，往下翻再拿更早的；第一页附带已播索引
        body = {"ok": True, "items": items[offset : offset + limit], "persistent": True, "total": total, "offset": offset}
        if offset == 0 and request.args.get("played", "1") == "1":
            body["played"] = history.played_map()
        return jsonify(body)
    return jsonify(
        {
            "ok": True,
            "items": items,
            "persistent": True,
            "total": total,
            "played": history.played_map(),
        }
    )


@app.route("/api/history", methods=["DELETE"])
def history_clear():
    history.clear_records()
    return jsonify({"ok": True})


@app.route("/api/prefs", methods=["GET"])
def prefs_get():
    return jsonify({"ok": True, **history.load_prefs()})


@app.route("/api/prefs", methods=["POST"])
def prefs_post():
    data = request.get_json(silent=True) or {}
    prefs = history.save_prefs(data)
    return jsonify({"ok": True, **prefs})


DEMO_PACK = [
    ("happy", "01-喜-喜悦-happy.jpg", "01 喜"),
    ("angry", "02-怒-愤怒-angry.jpg", "02 怒"),
    ("sad", "03-哀-悲伤-sad.jpg", "03 哀"),
    ("fear", "04-惧-恐惧-fear.jpg", "04 惧"),
    ("surprise", "05-惊-惊讶-surprise.jpg", "05 惊"),
    ("disgust", "06-厌-厌恶-disgust.jpg", "06 厌"),
    ("neutral", "07-中性-平静-neutral.jpg", "07 中性"),
    ("happy", "08-喜-喜悦-happy-b.jpg", "08 喜"),
    ("angry", "09-怒-愤怒-angry-b.jpg", "09 怒"),
    ("sad", "10-哀-悲伤-sad-b.jpg", "10 哀"),
    ("fear", "11-惧-恐惧-fear-b.jpg", "11 惧"),
    ("surprise", "12-惊-惊讶-surprise-b.jpg", "12 惊"),
    ("disgust", "13-厌-厌恶-disgust-b.jpg", "13 厌"),
    ("neutral", "14-中性-平静-neutral-b.jpg", "14 中性"),
    ("happy", "15-喜-喜悦-happy-c.jpg", "15 喜"),
    ("angry", "16-怒-愤怒-angry-c.jpg", "16 怒"),
    ("sad", "17-哀-悲伤-sad-c.jpg", "17 哀"),
    ("fear", "18-惧-恐惧-fear-c.jpg", "18 惧"),
    ("surprise", "19-惊-惊讶-surprise-c.jpg", "19 惊"),
    ("disgust", "20-厌-厌恶-disgust-c.jpg", "20 厌"),
    ("neutral", "21-中性-平静-neutral-c.jpg", "21 中性"),
]
# 第 4、5、6 组：真人照片，每类 3 张（Wikimedia Commons / Unsplash，见 static/demo/示例照片来源与授权.txt）
for _suffix, _start in (("d", 22), ("e", 29), ("f", 36)):
    for _i, (_eid, _zh, _name) in enumerate(
        (("happy", "喜", "喜悦"), ("angry", "怒", "愤怒"), ("sad", "哀", "悲伤"), ("fear", "惧", "恐惧"),
         ("surprise", "惊", "惊讶"), ("disgust", "厌", "厌恶"), ("neutral", "中性", "平静"))
    ):
        _n = _start + _i
        DEMO_PACK.append((_eid, f"{_n:02d}-{_zh}-{_name}-{_eid}-{_suffix}.jpg", f"{_n:02d} {_zh} · 真人"))


@app.route("/api/demo")
def demo_images():
    items = []
    for eid, filename, label in DEMO_PACK:
        p = DEMO_DIR / filename
        if not p.exists() and filename[0:2] in {"01", "02", "03", "04", "05", "06", "07"}:
            for ext in (".jpg", ".jpeg", ".png", ".webp"):
                fallback = DEMO_DIR / f"{eid}{ext}"
                if fallback.exists():
                    p = fallback
                    break
        if p.exists():
            items.append(
                {
                    "id": eid,
                    "label": label,
                    "file": p.name,
                    "url": f"/static/demo/{p.name}?v={int(p.stat().st_mtime)}",
                }
            )
    return jsonify({"ok": True, "items": items})


def create_app():
    return app


if __name__ == "__main__":
    from backend.assets import ensure_assets
    from backend.emotion import get_recognizer

    logger.info("Python %s  |  %s", sys.version.split()[0], sys.prefix)
    try:
        from tools.verify_cpu import check as _cpu_ort
        cpu_ok, cpu_detail = _cpu_ort()
        if cpu_ok:
            logger.info("onnxruntime CPU %s", cpu_detail)
        else:
            logger.warning("onnxruntime 不是 CPU 包：%s", cpu_detail)
    except Exception:
        logger.exception("未能核对 onnxruntime CPU 包")
    logger.info("正在准备模型与本地曲库…")
    ensure_assets()
    get_recognizer()
    seeded = history.seed_history_from_demo()
    if seeded:
        logger.info("已预置 %s 条示例识别历史，复制项目部署时会一起带走", seeded)
    logger.info("打开浏览器访问 http://127.0.0.1:%s", PORT)
    app.run(host=HOST, port=PORT, threaded=True, debug=False)
