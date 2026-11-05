"""热歌入库：把在线接口搜到的热歌 / 当前流行歌，实时补充进本地曲库。

- 每次在线推荐拿到的歌交给 absorb()；后台定时抓苹果音乐港台美热歌榜（harvest_charts），
  榜单新歌不在手标曲目书里时归入「当前热榜」（emotion="pop"），不硬猜情绪：
  实测按 30 秒试听的曲调判 7 类情绪只有 13%–24%、按歌词关键词 21%，猜错会把伤感情歌塞进喜悦歌单；
- 后台单线程把 30 秒试听和封面下载到 static/audio、static/covers（与本地曲库同一套），
  下载成功才入库，之后离线也能播；
- 元数据存 data/hot_library.json，load_catalog() 会把它并进曲库，推荐、歌词、下载照常可用；
- 和本地曲库同名的歌不重复入库；每类情绪最多 HOT_MAX_PER_EMO 首，超出淘汰最早入库的。
"""
from __future__ import annotations

import json
import logging
import queue
import threading
import time
from pathlib import Path

import requests

from config import AUDIO_DIR, COVER_DIR, DATA_DIR, EMOTIONS

logger = logging.getLogger("emotune.hotlib")

HOT_PATH = DATA_DIR / "hot_library.json"
HOT_MAX_PER_EMO = 200
POP = "pop"  # 当前热榜：情绪未标注的榜单新歌
HOT_NEW_DAYS = 3  # 入库 3 天内算「新歌」，推荐时排在代表曲之后
HOT_REFRESH_S = 1800  # 后台每 30 分钟刷新一次榜单
_LOCK = threading.RLock()
_JOBS: "queue.Queue[dict]" = queue.Queue()
_PENDING: set[str] = set()
_STATE = {"songs": None, "refreshed": 0.0, "worker": None, "refresher": None, "last_error": ""}


def _load() -> list[dict]:
    with _LOCK:
        if _STATE["songs"] is None:
            try:
                data = json.loads(HOT_PATH.read_text(encoding="utf-8")) if HOT_PATH.exists() else {}
                _STATE["songs"] = [s for s in (data.get("songs") or []) if isinstance(s, dict)]
                _STATE["refreshed"] = float(data.get("refreshed") or 0)
            except Exception:
                logger.exception("读取热歌库失败，按空库处理（不覆盖原文件）")
                _STATE["songs"] = []
                _STATE["readonly"] = True
        return _STATE["songs"]


def _save() -> None:
    if _STATE.get("readonly"):
        return
    payload = {"refreshed": _STATE["refreshed"], "songs": _STATE["songs"] or []}
    tmp = HOT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(HOT_PATH)


def hot_songs() -> list[dict]:
    """给 load_catalog() 用：入库的热歌（音频已在本地），带「新歌」标记。"""
    now = time.time()
    out = []
    for s in list(_load()):
        if not (AUDIO_DIR / s.get("file", "")).exists():
            continue
        item = dict(s)
        item["hot_new"] = now - float(s.get("added") or 0) < HOT_NEW_DAYS * 86400
        out.append(item)
    return out


CHART_COUNTRIES = ("hk", "tw", "us")  # 中国区商店没有公开榜单；港台以华语为主，美区补欧美流行


def _known_keys() -> dict[str, set[str]]:
    """曲库里已有的歌：歌名键 -> 歌手键集合。"""
    from backend.recommender import load_catalog
    from backend.songbook import fold_zh, title_key

    out: dict[str, set[str]] = {}
    for s in load_catalog():
        out.setdefault(title_key(s.get("title") or ""), set()).add(fold_zh(s.get("artist") or "").replace(" ", ""))
    return out


def _is_known(key: str, artist: str, known: dict[str, set[str]]) -> bool:
    """同名即算已有；繁简字表没收全时（報/报），同歌手、同长度、只差一两个字也算已有。"""
    from difflib import SequenceMatcher

    from backend.songbook import fold_zh

    if key in known:
        return True
    a = fold_zh(artist or "").replace(" ", "")
    for k, artists in known.items():
        if len(k) == len(key) and a in artists and SequenceMatcher(None, k, key).ratio() >= 0.7:
            return True
    return False


def absorb(emotion: str | None, songs: list[dict]) -> int:
    """把在线歌排进下载队列；返回新排队的首数。不阻塞请求。emotion=None：下载后按歌名 / 曲调判定情绪。"""
    if (emotion is not None and emotion not in EMOTIONS and emotion != POP) or not songs:
        return 0
    from backend.songbook import title_key

    known = _known_keys()
    n = 0
    for s in songs:
        if s.get("source") == "local" or not s.get("remote") or not s.get("playable"):
            continue
        key = title_key(s.get("title") or "")
        if not key or key in _PENDING or _is_known(key, s.get("artist") or "", known):
            continue
        _PENDING.add(key)
        _JOBS.put({"emotion": emotion, "key": key, "song": dict(s)})
        n += 1
    if n:
        _ensure_worker()
    return n


def _download(url: str, path: Path, timeout: float = 12.0) -> bool:
    from backend.recommender import stream_allowed

    # 试听走在线白名单；封面来自 mzstatic / 网易云等图片域名，只要求 https
    if not url or not (stream_allowed(url) or url.startswith("https://")):
        return False
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200 or len(r.content) < 2048:
            return False
        tmp = path.with_suffix(path.suffix + ".part")
        tmp.write_bytes(r.content)
        tmp.replace(path)
        return True
    except Exception as exc:
        _STATE["last_error"] = str(exc)[:200]
        return False


def _ingest(job: dict) -> bool:
    s, emo, key = job["song"], job["emotion"], job["key"]
    if _is_known(key, s.get("artist") or "", _known_keys()):
        return False
    sid = "hot-" + "".join(ch for ch in str(s.get("id") or key) if ch.isalnum() or ch in "-_")[:48]
    ext = ".mp3" if ".mp3" in s["remote"].split("?")[0].lower() else ".m4a"
    audio = AUDIO_DIR / f"{sid}{ext}"
    if not _download(s["remote"], audio):
        return False
    emo_by = "在线情绪检索"
    if emo is None:
        emo, emo_by = _judge_emotion(s.get("title") or "")
    cover = ""
    if str(s.get("cover") or "").startswith("http") and _download(s["cover"], COVER_DIR / f"{sid}.jpg", 8.0):
        cover = f"/static/covers/{sid}.jpg"
    item = {
        "id": sid,
        "title": s.get("title") or "",
        "artist": s.get("artist") or "",
        "album": s.get("album") or "",
        "emotion": emo,
        "genre": s.get("genre") or "",
        "source": "local",
        "source_label": "热歌入库 · " + (s.get("source_label") or "在线").replace("在线 · ", ""),
        "kind": "vocal",
        "hot": True,
        "file": audio.name,
        "audio": f"/api/audio/{sid}",
        "preview": f"/api/audio/{sid}",
        "cover": cover or s.get("cover") or "",
        "external_url": s.get("external_url") or "",
        "duration": 30.0,
        "playable": True,
        "downloadable": True,
        "mime": "audio/mpeg" if ext == ".mp3" else "audio/mp4",
        "added": time.time(),
        "from": s.get("source") or "",
        "emotion_by": emo_by,
        "chart": s.get("chart") or "",
        "rank": int(s.get("rank") or 999),
        "chart_seen": time.time() if s.get("chart") else 0,
    }
    with _LOCK:
        songs = _load()
        songs.append(item)
        same = [x for x in songs if x.get("emotion") == emo]
        cap = HOT_MAX_PER_EMO * (2 if emo == POP else 1)
        if len(same) > cap:  # 淘汰这一类最早入库的
            drop = {x["id"] for x in sorted(same, key=lambda x: x.get("chart_seen") or x.get("added") or 0)[: len(same) - cap]}
            for x in songs:
                if x["id"] in drop:
                    for p in (AUDIO_DIR / x.get("file", ""), COVER_DIR / f"{x['id']}.jpg"):
                        p.unlink(missing_ok=True)
            songs[:] = [x for x in songs if x["id"] not in drop]
        _save()
    _bump_catalog()
    logger.info("热歌入库：%s - %s（%s）", item["title"], item["artist"], emo)
    return True


def _judge_emotion(title: str) -> tuple[str, str]:
    """榜单歌的情绪：曲目书里有这首歌名就用手标的；否则归入当前热榜，不猜。"""
    from backend.songbook import emotion_of_title

    emo = emotion_of_title(title)
    if emo in EMOTIONS:
        return emo, "曲目书"
    return POP, "未标注"


def harvest_charts(timeout: float = 10.0) -> int:
    """抓苹果音乐热歌榜（港 / 台 / 美各前 100），没入库的排进下载队列；返回排队首数。"""
    from backend.recommender import _accept_online, _itunes_item

    n = 0
    for cc in CHART_COUNTRIES:
        try:
            feed = requests.get(f"https://itunes.apple.com/{cc}/rss/topsongs/limit=100/json", timeout=timeout).json()
            entries = (feed.get("feed") or {}).get("entry") or []
            ids, rank = [], {}
            for e in entries if isinstance(entries, list) else [entries]:
                title = ((e.get("im:name") or {}).get("label") or "").strip()
                artist = ((e.get("im:artist") or {}).get("label") or "").strip()
                tid = str(((e.get("id") or {}).get("attributes") or {}).get("im:id") or "")
                if tid and title and _accept_online(title, artist, strict=False):
                    ids.append(tid)
                    rank[tid] = len(rank) + 1
            songs = []
            for i in range(0, len(ids), 50):
                data = requests.get(f"https://itunes.apple.com/lookup?id={','.join(ids[i:i + 50])}&country={cc}", timeout=timeout).json()
                for item in data.get("results") or []:
                    song = _itunes_item("neutral", item)
                    if song and song.get("preview"):
                        song.update(remote=song["preview"], source="itunes_chart", chart=cc.upper(), rank=rank.get(str(item.get("trackId")), 999),
                                    source_label=f"在线 · 苹果音乐{ {'hk': '香港', 'tw': '台湾', 'us': '美国'}[cc]}热歌榜")
                        songs.append(song)
            _mark_seen(songs)
            n += absorb(None, songs)
        except Exception as exc:
            _STATE["last_error"] = f"{cc}: {str(exc)[:160]}"
            logger.warning("抓热歌榜失败 %s: %s", cc, exc)
    return n


def _mark_seen(songs: list[dict]) -> None:
    """已入库的歌这次又上榜：刷新上榜时间和名次，热榜按这个排。"""
    from backend.songbook import title_key

    fresh = {title_key(s.get("title") or ""): s for s in songs}
    with _LOCK:
        changed = False
        for x in _load():
            s = fresh.get(title_key(x.get("title") or ""))
            if s and x.get("chart"):
                x.update(chart_seen=time.time(), rank=int(s.get("rank") or 999), chart=s.get("chart") or x["chart"])
                changed = True
        if changed:
            _save()


def chart_songs(limit: int = 60) -> list[dict]:
    """当前热榜：最近 2 天还在榜上的入库歌（含已标情绪的），按名次排。"""
    now = time.time()
    rows = [s for s in hot_songs() if s.get("chart") and now - float(s.get("chart_seen") or 0) < 2 * 86400]
    rows.sort(key=lambda s: (int(s.get("rank") or 999), -(s.get("chart_seen") or 0)))
    return rows[:limit]


def _bump_catalog() -> None:
    try:
        from backend import recommender

        recommender.invalidate_catalog()
    except Exception:
        pass


def _worker() -> None:
    while True:
        job = _JOBS.get()
        try:
            _ingest(job)
        except Exception:
            logger.exception("热歌入库失败")
        finally:
            _PENDING.discard(job["key"])


def _ensure_worker() -> None:
    with _LOCK:
        if _STATE["worker"] is None:
            _STATE["worker"] = threading.Thread(target=_worker, name="hotlib", daemon=True)
            _STATE["worker"].start()


def refresh_now() -> int:
    """抓一遍热歌榜，再拉 7 类情绪的在线热歌，排进入库队列；返回排队首数。"""
    from backend.recommender import online_songs

    n = harvest_charts()
    for emo in EMOTIONS:
        try:
            n += absorb(emo, online_songs(emo, timeout=8.0))
        except Exception as exc:
            _STATE["last_error"] = str(exc)[:200]
    with _LOCK:
        _load()
        _STATE["refreshed"] = time.time()
        _save()
    return n


def start_refresher() -> None:
    """后台定时刷新；EMOTUNE_HOT=0 关闭（测试服务器用）。"""
    import os

    if os.environ.get("EMOTUNE_HOT", "1") == "0" or _STATE["refresher"] is not None:
        return

    def loop():
        time.sleep(20)  # 让服务先起来
        while True:
            if time.time() - (_STATE["refreshed"] or 0) >= HOT_REFRESH_S:
                try:
                    refresh_now()
                except Exception:
                    logger.exception("热歌定时刷新失败")
            time.sleep(60)

    _load()
    _STATE["refresher"] = threading.Thread(target=loop, name="hotlib-refresh", daemon=True)
    _STATE["refresher"].start()


def status() -> dict:
    songs = _load()
    by = {e: 0 for e in (*EMOTIONS, POP)}
    for s in songs:
        by[s.get("emotion")] = by.get(s.get("emotion"), 0) + 1
    now = time.time()
    newest = sorted(songs, key=lambda x: -(x.get("added") or 0))[:8]
    return {
        "total": len(songs),
        "by_emotion": by,
        "chart": len(chart_songs(1000)),
        "new": sum(1 for s in songs if now - float(s.get("added") or 0) < HOT_NEW_DAYS * 86400),
        "pending": len(_PENDING),
        "refreshed": _STATE["refreshed"],
        "auto": _STATE["refresher"] is not None,
        "last_error": _STATE["last_error"],
        "latest": [{"title": s["title"], "artist": s["artist"], "emotion": s["emotion"], "added": s.get("added")} for s in newest],
    }
