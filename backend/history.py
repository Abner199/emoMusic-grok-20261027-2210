# -*- coding: utf-8 -*-
"""全局识别历史：主存储 data/history.db（SQLite），并定期导出 data/history.json；人脸截图在 static/history/。复制整夹部署到另一台电脑也会带着。"""
from __future__ import annotations

import base64
import json
import os
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from config import DATA_DIR, EMOTIONS, HISTORY_DIR, THEMES
from backend.songbook import emotion_of_title, title_key

# 跑测试的服务可设 EMOTUNE_HISTORY_FILE / EMOTUNE_PREFS_FILE 指到别处，不写进真实足迹
_PATH = Path(os.environ.get("EMOTUNE_HISTORY_FILE") or DATA_DIR / "history.json")
_BACKUP = _PATH.with_name(_PATH.name + ".bak")
_LOCKFILE = _PATH.with_name(_PATH.stem + ".lock")
_PREFS = Path(os.environ.get("EMOTUNE_PREFS_FILE") or DATA_DIR / "prefs.json")


class HistoryReadError(RuntimeError):
    """history.json 存在但读不出来：宁可这次不写，也不能当成空历史把旧记录覆盖掉。"""


class _ProcessLock:
    """线程锁 + 跨进程文件锁：同一份 data/ 被多个服务进程（或自检）同时读写时不会互相踩坏。"""

    def __init__(self) -> None:
        self._thread = threading.RLock()
        self._fh = None
        self._depth = 0

    def __enter__(self):
        self._thread.acquire()
        self._depth += 1
        if self._depth == 1:
            try:
                _LOCKFILE.parent.mkdir(parents=True, exist_ok=True)
                self._fh = open(_LOCKFILE, "a+b")
                if os.name == "nt":
                    import msvcrt

                    deadline = time.time() + 10
                    while True:
                        try:
                            self._fh.seek(0)
                            msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
                            break
                        except OSError:
                            if time.time() > deadline:
                                raise
                            time.sleep(0.03)
                else:
                    import fcntl

                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX)
            except Exception:
                if self._fh:
                    self._fh.close()
                self._fh = None
        return self

    def __exit__(self, *exc):
        try:
            if self._depth == 1 and self._fh:
                try:
                    if os.name == "nt":
                        import msvcrt

                        self._fh.seek(0)
                        msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
                finally:
                    self._fh.close()
                    self._fh = None
        finally:
            self._depth -= 1
            self._thread.release()
        return False


_LOCK = _ProcessLock()

_SONG_KEYS = (
    "id",
    "title",
    "artist",
    "album",
    "cover",
    "audio",
    "preview",
    "source",
    "source_label",
    "kind",
    "playable",
    "downloadable",
    "duration",
    "emotion",
    "emotion_zh",
    "emotion_name",
    "mime",
)


BACKUP_EVERY_S = 600.0


def _load_raw() -> Any:
    if not _PATH.exists():
        return []
    last: Exception | None = None
    for attempt in range(6):
        try:
            text = _PATH.read_text(encoding="utf-8")
            if not text.strip():
                raise ValueError("history.json 是空文件")
            return json.loads(text)
        except Exception as exc:  # 可能正读到别的进程写了一半
            last = exc
            time.sleep(0.05 * (attempt + 1))
    raise HistoryReadError(f"读取 {_PATH} 失败：{last}")


def _flatten(raw: Any) -> list[dict]:
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        if isinstance(raw.get("items"), list):
            return [x for x in raw["items"] if isinstance(x, dict)]
        items: list[dict] = []
        for val in raw.values():
            if isinstance(val, list):
                items.extend(x for x in val if isinstance(x, dict))
        items.sort(key=lambda x: int(x.get("ts") or 0), reverse=True)
        return items
    return []


def _load_store() -> dict:
    raw = _load_raw()
    if isinstance(raw, dict) and isinstance(raw.get("items"), list):
        played = raw.get("played") if isinstance(raw.get("played"), dict) else {}
        return {
            "items": [x for x in raw["items"] if isinstance(x, dict)],
            "played": {str(k): list(v) for k, v in played.items() if isinstance(v, list)},
        }
    return {"items": _flatten(raw), "played": {}}


def _save(payload: Any) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    tmp = _PATH.with_suffix(".tmp")
    last_err: Exception | None = None
    for attempt in range(8):
        try:
            tmp.write_text(text, encoding="utf-8")
            try:
                tmp.replace(_PATH)
            except PermissionError:
                _PATH.write_text(text, encoding="utf-8")
                tmp.unlink(missing_ok=True)
            return
        except OSError as exc:
            last_err = exc
            time.sleep(0.04 * (attempt + 1))
    try:
        _PATH.write_text(text, encoding="utf-8")
    except OSError:
        if last_err:
            raise last_err


def _song_emotion(song: dict) -> str:
    eid = str(song.get("emotion") or "").strip()
    if eid in EMOTIONS:
        return eid
    music = song.get("music") if isinstance(song.get("music"), dict) else {}
    eid = str(music.get("emotion") or "").strip()
    if eid in EMOTIONS:
        return eid
    eid = emotion_of_title(song.get("title") or "") or ""
    return eid if eid in EMOTIONS else ""


def _decorate_song(row: dict, src: dict | None = None) -> dict:
    src = src if isinstance(src, dict) else row
    eid = _song_emotion(src) or _song_emotion(row)
    if not eid:
        return row
    meta = EMOTIONS.get(eid) or {}
    row["emotion"] = eid
    row["emotion_zh"] = src.get("emotion_zh") or row.get("emotion_zh") or meta.get("zh") or ""
    row["emotion_name"] = src.get("emotion_name") or row.get("emotion_name") or meta.get("name") or ""
    return row


def _slim_songs(songs: list[dict] | None) -> list[dict]:
    out = []
    for song in songs or []:
        if not isinstance(song, dict):
            continue
        row = {k: song[k] for k in _SONG_KEYS if k in song}
        out.append(_decorate_song(row, song))
    return out


def _play_row(song: dict) -> dict | None:
    if not isinstance(song, dict):
        return None
    title = (song.get("title") or "").strip()
    key = title_key(title) or title_key(song.get("key") or "")
    if not key:
        return None
    row = {k: song[k] for k in _SONG_KEYS if k in song}
    row["title"] = title or row.get("title") or ""
    row["key"] = key
    row["ts"] = int(song.get("ts") or time.time())
    return _decorate_song(row, song)


def _persist_face(item_id: str, face: dict | None) -> dict:
    if not isinstance(face, dict):
        return {}
    out = dict(face)
    crop = out.get("crop") or ""
    if not isinstance(crop, str) or not crop.startswith("data:image"):
        return out
    try:
        header, b64 = crop.split(",", 1)
        ext = "png" if "png" in header.lower() else "jpg"
        raw = base64.b64decode(b64)
        if len(raw) < 400:
            return out
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        name = f"{item_id}.{ext}"
        (HISTORY_DIR / name).write_bytes(raw)
        out["crop"] = f"/static/history/{name}"
    except Exception:
        return out
    return out


def _migrate_item(item: dict) -> dict:
    item_id = item.get("id") or uuid.uuid4().hex[:12]
    item["id"] = item_id
    face = item.get("face")
    if isinstance(face, dict) and str(face.get("crop") or "").startswith("data:image"):
        item["face"] = _persist_face(item_id, face)
    if item.get("songs"):
        item["songs"] = _slim_songs(item.get("songs"))
    played = item.get("played")
    if played:
        rows = []
        seen = set()
        for song in played:
            row = _play_row(song) if isinstance(song, dict) else None
            if not row or row["key"] in seen:
                continue
            seen.add(row["key"])
            rows.append(row)
        item["played"] = rows
    else:
        item["played"] = []
    return item


def new_session_id() -> str:
    return uuid.uuid4().hex


def _needs_persist(raw: Any) -> bool:
    if not isinstance(raw, dict) or not isinstance(raw.get("items"), list):
        return True
    for src in _flatten(raw):
        crop = str((src.get("face") or {}).get("crop") or "")
        if crop.startswith("data:image"):
            return True
        for song in list(src.get("songs") or []) + list(src.get("played") or []):
            if isinstance(song, dict) and (song.get("title") or "") and not song.get("emotion"):
                return True
    played = raw.get("played") if isinstance(raw.get("played"), dict) else {}
    for rows in played.values():
        for song in rows or []:
            if isinstance(song, dict) and (song.get("title") or "") and not song.get("emotion"):
                return True
    return False


def _decorate_played(played: dict | None) -> dict:
    out: dict[str, list[dict]] = {}
    for emo, rows in (played or {}).items():
        cleaned: list[dict] = []
        seen: set[str] = set()
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            item = _play_row(row)
            if not item or item["key"] in seen:
                continue
            seen.add(item["key"])
            cleaned.append(item)
        out[str(emo)] = cleaned
    return out


# ===== SQLite 主存储 =====
# 每条足迹一行（id, ts, JSON），已播索引按情绪一行。新增一条只插入一行、记一首播过的歌只改一行，
# 不再整份重写几十 MB 的 history.json；SQLite 自己处理多进程并发。
# history.json 仍保留为导出快照（最多每 10 分钟一次、退出时一次），GitHub 备份、整夹复制、打包工具照常可用。
_DB_PATH = _PATH.with_suffix(".db")
EXPORT_EVERY_S = 600.0
_DB_STATE: dict = {"conn": None, "ver": None, "items": None, "by_id": None, "played": None, "dirty": False, "exported": 0.0}


def _db():
    conn = _DB_STATE["conn"]
    if conn is not None:
        return conn
    import sqlite3

    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), timeout=15, check_same_thread=False, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("CREATE TABLE IF NOT EXISTS items (id TEXT PRIMARY KEY, ts INTEGER NOT NULL, body TEXT NOT NULL)")
    conn.execute("CREATE INDEX IF NOT EXISTS items_ts ON items(ts DESC)")
    conn.execute("CREATE TABLE IF NOT EXISTS played (emo TEXT PRIMARY KEY, body TEXT NOT NULL)")
    if not conn.execute("SELECT 1 FROM items LIMIT 1").fetchone() and _PATH.exists():
        _import_json(conn)  # 失败会抛错，下次再试；成功后才登记连接
    _DB_STATE["conn"] = conn
    _DB_STATE["exported"] = time.time()  # 启动后 10 分钟内不急着导出，新增足迹只写一行
    return conn


def _import_json(conn) -> None:
    """第一次启动：把 history.json 全部导入 SQLite（一条不少）；读不出来就报错，绝不当成空历史。"""
    raw = _load_raw()
    store = _load_store()
    items = [_migrate_item(dict(x)) for x in store["items"]]
    played = _decorate_played(store.get("played"))
    conn.execute("BEGIN")
    try:
        conn.executemany(
            "INSERT OR REPLACE INTO items(id, ts, body) VALUES (?, ?, ?)",
            [(str(it.get("id") or uuid.uuid4().hex[:12]), int(it.get("ts") or 0), json.dumps(it, ensure_ascii=False)) for it in items],
        )
        conn.executemany(
            "INSERT OR REPLACE INTO played(emo, body) VALUES (?, ?)",
            [(emo, json.dumps(rows, ensure_ascii=False)) for emo, rows in played.items()],
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    if _needs_persist(raw):
        _DB_STATE["dirty"] = True  # 旧格式已在导入时规范化，下次导出写回 JSON


def _cache() -> dict:
    """进程内缓存全部足迹；别的进程写过（data_version 变了）才重新读库。"""
    conn = _db()
    ver = conn.execute("PRAGMA data_version").fetchone()[0]
    if _DB_STATE["items"] is None or _DB_STATE["ver"] != ver:
        items = [json.loads(body) for (body,) in conn.execute("SELECT body FROM items ORDER BY ts DESC")]
        _DB_STATE["items"] = items
        _DB_STATE["by_id"] = {str(it.get("id")): it for it in items}
        _DB_STATE["played"] = {emo: json.loads(body) for emo, body in conn.execute("SELECT emo, body FROM played")}
        _DB_STATE["ver"] = ver
    return _DB_STATE


def _put_item(item: dict) -> None:
    _db().execute(
        "INSERT OR REPLACE INTO items(id, ts, body) VALUES (?, ?, ?)",
        (str(item["id"]), int(item.get("ts") or 0), json.dumps(item, ensure_ascii=False)),
    )
    _DB_STATE["dirty"] = True


def _put_played(emo: str, rows: list[dict]) -> None:
    _db().execute("INSERT OR REPLACE INTO played(emo, body) VALUES (?, ?)", (emo, json.dumps(rows, ensure_ascii=False)))
    _DB_STATE["dirty"] = True


def export_json(force: bool = False) -> bool:
    """把 SQLite 里的足迹导出成 history.json（给 GitHub 备份、整夹复制、打包工具用）。"""
    if not force and (not _DB_STATE["dirty"] or time.time() - _DB_STATE["exported"] < EXPORT_EVERY_S):
        return False
    with _LOCK:
        st = _cache()
        payload = {"items": list(st["items"]), "played": dict(st["played"])}
        if _PATH.exists():
            try:
                if not _BACKUP.exists() or time.time() - _BACKUP.stat().st_mtime > BACKUP_EVERY_S:
                    shutil.copyfile(_PATH, _BACKUP)
            except OSError:
                pass
        _save(payload)
        _DB_STATE["dirty"] = False
        _DB_STATE["exported"] = time.time()
    return True


def _maybe_export() -> None:
    try:
        export_json(False)
    except Exception:
        pass


import atexit  # noqa: E402

atexit.register(lambda: _DB_STATE["dirty"] and export_json(True))


def ensure_persistent() -> int:
    """确保足迹库就绪（首次自动从 history.json 导入），返回条数。"""
    with _LOCK:
        return len(_cache()["items"])


def list_records(_session_id: str | None = None) -> list[dict]:
    with _LOCK:
        return list(_cache()["items"])


def _keys_of(rows) -> list[str]:
    keys, seen = [], set()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        key = row.get("key") or title_key(row.get("title") or "")
        if key and key not in seen:
            seen.add(key)
            keys.append(key)
    return keys


def played_keys(emotion: str) -> list[str]:
    if not emotion:
        return []
    with _LOCK:
        return _keys_of(_cache()["played"].get(emotion))


def played_map() -> dict[str, list[str]]:
    with _LOCK:
        return {str(emo): _keys_of(rows) for emo, rows in _cache()["played"].items()}


def add_record(_session_id: str | None, record: dict[str, Any]) -> dict:
    source = record.get("source") or ""
    emo_id = (record.get("emotion") or {}).get("id")
    with _LOCK:
        st = _cache()
        items = st["items"]
        now = int(time.time())
        last = items[0] if items else None
        if source == "camera-live" and emo_id and last and last.get("source") == "camera-live" and (last.get("emotion") or {}).get("id") == emo_id:
            face = _persist_face(last.get("id"), record.get("face") if isinstance(record.get("face"), dict) else {})
            last["ts"] = now
            last["elapsed_ms"] = record.get("elapsed_ms")
            last["emotion"] = record.get("emotion") or last.get("emotion")
            if face:
                last["face"] = face
            if record.get("songs") and not last.get("songs"):
                last["songs"] = _slim_songs(record.get("songs"))
            _put_item(last)
            _maybe_export()
            return last
        item_id = uuid.uuid4().hex[:12]
        item = {
            "id": item_id,
            "ts": now,
            "source": source,
            "emotion": record.get("emotion") or {},
            "elapsed_ms": record.get("elapsed_ms"),
            "songs": _slim_songs(record.get("songs")),
            "played": [],
            "face": _persist_face(item_id, record.get("face") if isinstance(record.get("face"), dict) else {}),
        }
        _put_item(item)
        items.insert(0, item)
        st["by_id"][item_id] = item
        _maybe_export()
        return item


def mark_played(emotion: str, song: dict, history_id: str | None = None) -> dict | None:
    row = _play_row(song or {})
    if not row or not emotion:
        return None
    with _LOCK:
        st = _cache()
        bucket = [x for x in (st["played"].get(emotion) or []) if isinstance(x, dict)]
        bucket = [x for x in bucket if (x.get("key") or title_key(x.get("title") or "")) != row["key"]]
        bucket.append(row)
        st["played"][emotion] = bucket
        _put_played(emotion, bucket)
        item = st["by_id"].get(str(history_id)) if history_id else None
        if item is not None:
            played = item.get("played") if isinstance(item.get("played"), list) else []
            if not any((p.get("key") or title_key(p.get("title") or "")) == row["key"] for p in played if isinstance(p, dict)):
                played.append(row)
                item["played"] = played
                _put_item(item)
        _maybe_export()
    return row


def stats(since: int = 0, until: int = 0) -> dict:
    """课堂情绪统计：各情绪次数与累计时长、情绪变化次数、播放最多的歌、来源分布。"""
    with _LOCK:
        items = [it for it in _cache()["items"] if int(it.get("ts") or 0) >= since and (not until or int(it.get("ts") or 0) <= until)]
    items = sorted(items, key=lambda x: int(x.get("ts") or 0))
    counts: dict[str, int] = {}
    seconds: dict[str, float] = {}
    sources: dict[str, int] = {}
    songs: dict[str, dict] = {}
    switches = 0
    last = ""
    for i, it in enumerate(items):
        eid = (it.get("emotion") or {}).get("id") or ""
        if eid not in EMOTIONS:
            continue
        counts[eid] = counts.get(eid, 0) + 1
        nxt = items[i + 1] if i + 1 < len(items) else None
        span = (int(nxt.get("ts") or 0) - int(it.get("ts") or 0)) if nxt else 5
        seconds[eid] = seconds.get(eid, 0.0) + float(max(1, min(60, span)))  # 两条之间最多算 60 秒
        if last and eid != last:
            switches += 1
        last = eid
        src = str(it.get("source") or "upload")
        sources[src] = sources.get(src, 0) + 1
        for p in it.get("played") or []:
            if not isinstance(p, dict):
                continue
            key = p.get("key") or title_key(p.get("title") or "")
            if not key:
                continue
            row = songs.setdefault(key, {"title": p.get("title") or "", "artist": p.get("artist") or "", "emotion": p.get("emotion") or eid, "n": 0})
            row["n"] += 1
    top = sorted(songs.values(), key=lambda r: -r["n"])[:5]
    first = int(items[0].get("ts") or 0) if items else 0
    final = int(items[-1].get("ts") or 0) if items else 0
    return {
        "total": sum(counts.values()),
        "counts": counts,
        "seconds": {k: round(v) for k, v in seconds.items()},
        "switches": switches,
        "sources": sources,
        "top_songs": top,
        "from": first,
        "to": final,
        "dominant": max(counts, key=lambda k: counts[k]) if counts else "",
    }


def clear_records(_session_id: str | None = None) -> None:
    with _LOCK:
        conn = _db()
        conn.execute("DELETE FROM items")
        conn.execute("DELETE FROM played")
        _DB_STATE.update(items=None, ver=None)
        _save({"items": [], "played": {}})
        _DB_STATE["dirty"] = False
        if HISTORY_DIR.exists():
            for path in HISTORY_DIR.glob("*"):
                if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                    try:
                        path.unlink()
                    except OSError:
                        pass


def load_prefs() -> dict:
    data = {"theme": "night", "strategy": "iso", "face_mode": "solo"}
    if _PREFS.exists():
        try:
            loaded = json.loads(_PREFS.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data.update(loaded)
        except Exception:
            pass
    return data


def save_prefs(patch: dict) -> dict:
    data = load_prefs()
    if "theme" in patch and patch["theme"] in THEMES:
        data["theme"] = patch["theme"]
    if "strategy" in patch:
        from backend.strategy import normalize

        data["strategy"] = normalize(patch.get("strategy"))
    if "face_mode" in patch:
        from backend.emotion import normalize_face_mode

        data["face_mode"] = normalize_face_mode(patch.get("face_mode"))
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _PREFS.with_suffix(".tmp")
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    last_err: OSError | None = None
    for attempt in range(6):
        try:
            tmp.write_text(payload, encoding="utf-8")
            tmp.replace(_PREFS)
            last_err = None
            break
        except OSError as err:
            last_err = err
            time.sleep(0.04 * (attempt + 1))
    if last_err:
        raise last_err
    return data


def seed_history_from_demo() -> int:
    """新部署若还没有历史，用七张示例表情预置对照记录，复制项目时会一起带走。"""
    if ensure_persistent():
        return 0
    from config import DEMO_DIR
    from backend.emotion import get_recognizer
    from backend.recommender import recommend

    rec = get_recognizer()
    mapping = [
        ("happy", "01-喜-喜悦-happy.jpg"),
        ("angry", "02-怒-愤怒-angry.jpg"),
        ("sad", "03-哀-悲伤-sad.jpg"),
        ("fear", "04-惧-恐惧-fear.jpg"),
        ("surprise", "05-惊-惊讶-surprise.jpg"),
        ("disgust", "06-厌-厌恶-disgust.jpg"),
        ("neutral", "07-中性-平静-neutral.jpg"),
    ]
    added = 0
    for eid, named in reversed(mapping):
        path = DEMO_DIR / named
        if not path.exists():
            path = DEMO_DIR / f"{eid}.jpg"
        if not path.exists():
            continue
        result = rec.predict_bytes(path.read_bytes())
        if not result.get("ok"):
            continue
        emotion_id = (result.get("emotion") or {}).get("id") or eid
        recs = recommend(emotion_id, want_online=False)
        add_record(
            None,
            {
                "source": "upload",
                "emotion": result.get("emotion"),
                "face": result.get("face"),
                "songs": recs.get("songs", []),
                "elapsed_ms": result.get("elapsed_ms"),
            },
        )
        added += 1
    return added
