# -*- coding: utf-8 -*-
"""全局识别历史：写入项目 data/ 与 static/history/，复制整夹部署到另一台电脑也会带着。"""
from __future__ import annotations

import base64
import json
import threading
import time
import uuid
from typing import Any

from config import DATA_DIR, EMOTIONS, HISTORY_DIR, THEMES
from backend.songbook import emotion_of_title, title_key

_LOCK = threading.Lock()
_PATH = DATA_DIR / "history.json"
_PREFS = DATA_DIR / "prefs.json"

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


def _load_raw() -> Any:
    if not _PATH.exists():
        return []
    try:
        return json.loads(_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


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
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
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


def _save_store(store: dict) -> None:
    _save(
        {
            "items": store.get("items") or [],
            "played": store.get("played") if isinstance(store.get("played"), dict) else {},
        }
    )


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


def ensure_persistent() -> int:
    """把旧会话格式和内嵌人脸截图落到 data/history.json 与 static/history/，复制项目即可带走。"""
    with _LOCK:
        raw = _load_raw()
        store = _load_store()
        store["items"] = [_migrate_item(dict(x)) for x in store["items"]]
        store["items"].sort(key=lambda x: int(x.get("ts") or 0), reverse=True)
        store["played"] = _decorate_played(store.get("played"))
        if _needs_persist(raw):
            _save_store(store)
        return len(store["items"])


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


def list_records(_session_id: str | None = None) -> list[dict]:
    with _LOCK:
        raw = _load_raw()
        store = _load_store()
        store["items"] = [_migrate_item(dict(x)) for x in store["items"]]
        store["items"].sort(key=lambda x: int(x.get("ts") or 0), reverse=True)
        store["played"] = _decorate_played(store.get("played"))
        if _needs_persist(raw):
            _save_store(store)
        return list(store["items"])


def played_keys(emotion: str) -> list[str]:
    if not emotion:
        return []
    with _LOCK:
        store = _load_store()
        keys = []
        seen = set()
        for row in store.get("played", {}).get(emotion) or []:
            if not isinstance(row, dict):
                continue
            key = row.get("key") or title_key(row.get("title") or "")
            if key and key not in seen:
                seen.add(key)
                keys.append(key)
        return keys


def played_map() -> dict[str, list[str]]:
    with _LOCK:
        store = _load_store()
        out: dict[str, list[str]] = {}
        for emo, rows in (store.get("played") or {}).items():
            keys = []
            seen = set()
            for row in rows or []:
                if not isinstance(row, dict):
                    continue
                key = row.get("key") or title_key(row.get("title") or "")
                if key and key not in seen:
                    seen.add(key)
                    keys.append(key)
            out[str(emo)] = keys
        return out


def add_record(_session_id: str | None, record: dict[str, Any]) -> dict:
    source = record.get("source") or ""
    emo_id = (record.get("emotion") or {}).get("id")
    with _LOCK:
        store = _load_store()
        items = [_migrate_item(dict(x)) for x in store["items"]]
        items.sort(key=lambda x: int(x.get("ts") or 0), reverse=True)
        merge = False
        item_id = uuid.uuid4().hex[:12]
        if source == "camera-live" and emo_id and items:
            last = items[0]
            if last.get("source") == "camera-live" and (last.get("emotion") or {}).get("id") == emo_id:
                merge = True
                item_id = last.get("id") or item_id
        face = _persist_face(item_id, record.get("face") if isinstance(record.get("face"), dict) else {})
        now = int(time.time())
        if merge:
            last["ts"] = now
            last["elapsed_ms"] = record.get("elapsed_ms")
            last["emotion"] = record.get("emotion") or last.get("emotion")
            if face:
                last["face"] = face
            if record.get("songs") and not last.get("songs"):
                last["songs"] = _slim_songs(record.get("songs"))
            store["items"] = items
            _save_store(store)
            return last
        item = {
            "id": item_id,
            "ts": now,
            "source": source,
            "emotion": record.get("emotion") or {},
            "elapsed_ms": record.get("elapsed_ms"),
            "songs": _slim_songs(record.get("songs")),
            "played": [],
            "face": face,
        }
        items.insert(0, item)
        store["items"] = items
        _save_store(store)
        return item


def mark_played(emotion: str, song: dict, history_id: str | None = None) -> dict | None:
    row = _play_row(song or {})
    if not row or not emotion:
        return None
    with _LOCK:
        store = _load_store()
        bucket = [x for x in (store["played"].get(emotion) or []) if isinstance(x, dict)]
        bucket = [x for x in bucket if (x.get("key") or title_key(x.get("title") or "")) != row["key"]]
        bucket.append(row)
        store["played"][emotion] = bucket
        if history_id:
            for item in store["items"]:
                if item.get("id") != history_id:
                    continue
                played = item.get("played") if isinstance(item.get("played"), list) else []
                if not any((p.get("key") or title_key(p.get("title") or "")) == row["key"] for p in played if isinstance(p, dict)):
                    played.append(row)
                item["played"] = played
                break
        _save_store(store)
    return row


def clear_records(_session_id: str | None = None) -> None:
    with _LOCK:
        _save_store({"items": [], "played": {}})
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
