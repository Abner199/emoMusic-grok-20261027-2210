# -*- coding: utf-8 -*-
"""
在线曲库默认优先：先走苹果音乐、苹果热歌榜、苹果热播、苹果亚洲热歌，不够再补网易云热歌榜、QQ 热歌榜、网易云、咪咕、酷狗、QQ、酷我、Deezer、Audius。
本机 30 秒人声试听随时可手动切回；在线长时间播不了会回落到本地。
"""
from __future__ import annotations

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from urllib.parse import quote, urlparse

import requests

from config import AUDIO_DIR, DATA_DIR, EMOTIONS, ONLINE_APIS, ONLINE_TIMEOUT, RECOMMEND_COUNT
from backend.assets import itunes_lookup_ids, itunes_search_results
from backend.music_emotion import (
    ALGO_NAME as MUSIC_ALGO,
    describe_song,
    face_vector,
    match_score,
    public_music,
    target_vector,
)
from backend.songbook import (
    VOCAL_SONGBOOK,
    emotion_of_title,
    fold_zh,
    front_pin_keys,
    is_vocal_song,
    localize_song,
    play_priority,
    title_key,
    title_seen,
)
from backend.strategy import DEFAULT_STRATEGY, interleave, involved_emotions, normalize, plan, summary

logger = logging.getLogger("emotune.recommender")

_CATALOG_PATH = DATA_DIR / "catalog.json"
_CACHE: dict[str, tuple[float, list[dict]]] = {}
_CACHE_TTL = 600.0
_EMPTY_CACHE_TTL = 12.0
_SKIP_DEEZER = False
_SESSION = requests.Session()
_SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json,text/plain,*/*",
    }
)
_DIRECT = requests.Session()
_DIRECT.trust_env = False
_DIRECT.headers.update(_SESSION.headers)
_TRACK_ID_RE = re.compile(r"[?&]i=(\d+)")
_SPAM_MARK = re.compile(r"[♚★☆●♪♫◆■□♣♥♠]")
_SONGBOOK_ARTIST = {title_key(spec["title"]): spec["artist"] for spec in VOCAL_SONGBOOK}
_ARTIST_TITLES: dict[str, set[str]] = {}
_ALL_TITLES: set[str] = set()
for _spec in VOCAL_SONGBOOK:
    _akey = fold_zh(_spec["artist"])
    _ARTIST_TITLES.setdefault(_akey, set()).add(title_key(_spec["title"]))
    _ALL_TITLES.add(title_key(_spec["title"]))
_SKIP_APIS: set[str] = set()
_FLAKY_APIS = {"kuwo", "kugou", "deezer", "audius"}
_API_TIMEOUTS = {
    "itunes": 5.0,
    "itunes_chart": 2.4,
    "apple_hot": 2.4,
    "apple_asia": 2.6,
    "netease": 1.2,
    "netease_hot": 1.3,
    "qq": 1.1,
    "qq_hot": 1.3,
    "migu": 0.9,
    "kugou": 0.8,
    "kuwo": 0.7,
    "deezer": 1.0,
    "audius": 1.2,
}
_APPLE_APIS = ("itunes", "itunes_chart", "apple_hot", "apple_asia")

_STREAM_SUFFIXES = (
    "itunes.apple.com",
    "mzstatic.com",
    "apple.com",
    "music.163.com",
    "126.net",
    "migu.cn",
    "kugou.com",
    "kugou.net",
    "kgimg.com",
    "kuwo.cn",
    "koowo.com",
    "y.qq.com",
    "gtimg.cn",
    "tc.qq.com",
    "qqmusic.qq.com",
    "stream.qqmusic.qq.com",
    "dzcdn.net",
    "deezer.com",
    "audius.co",
    "audiuscdn.com",
)

SOURCE_LABEL = {
    "itunes": "在线 · 苹果音乐",
    "itunes_chart": "在线 · 苹果热歌",
    "apple_hot": "在线 · 苹果热播",
    "netease": "在线 · 网易云",
    "migu": "在线 · 咪咕",
    "kugou": "在线 · 酷狗",
    "qq": "在线 · QQ 音乐",
    "kuwo": "在线 · 酷我",
    "deezer": "在线 · 国际曲库",
    "apple_asia": "在线 · 苹果亚洲热歌",
    "netease_hot": "在线 · 网易云热歌榜",
    "qq_hot": "在线 · QQ 热歌榜",
    "audius": "在线 · Audius",
    "local": "本地曲库",
}


def _artist_match(got: str, wanted: str) -> bool:
    g, w = fold_zh(got or ""), fold_zh(wanted or "")
    if not w:
        return True
    if not g:
        return False
    if w in g or g in w:
        return True
    parts = [p.strip() for p in re.split(r"[/,&]|、", w) if len(p.strip()) >= 2]
    return any(p in g for p in parts)


def _artist_ok(title: str, artist: str) -> bool:
    want = _SONGBOOK_ARTIST.get(title_key(title or ""))
    if not want:
        return True
    return _artist_match(artist, want)


def _known_artist_key(artist: str) -> str:
    a = fold_zh(artist or "")
    if not a:
        return ""
    if a in _ARTIST_TITLES:
        return a
    for known in _ARTIST_TITLES:
        if known and (known in a or a in known):
            return known
    return ""


def _title_fits_artist(title: str, artist: str) -> bool:
    known = _known_artist_key(artist)
    if not known:
        return True
    key = title_key(title or "")
    return key in _ARTIST_TITLES.get(known, set()) or key in _ALL_TITLES


def _is_spam_track(title: str, artist: str) -> bool:
    name = (title or "").strip()
    who = (artist or "").strip()
    if not name:
        return True
    blob = f"{name} {who}"
    if _SPAM_MARK.search(blob):
        return True
    if who.endswith(".") or who.endswith("。"):
        return True
    if "，" in name or "！" in name:
        return True
    if len(name) > 22:
        return True
    return False


def _accept_online(title: str, artist: str, genre: str = "", strict: bool = True) -> bool:
    if not is_vocal_song(title, artist, genre):
        return False
    if _is_spam_track(title, artist):
        return False
    if not strict:
        return True
    if not _artist_ok(title, artist):
        return False
    if not _title_fits_artist(title, artist):
        return False
    return True


def _apple_ids_for(emotion: str) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for row in load_catalog():
        if row.get("emotion") != emotion:
            continue
        found = _TRACK_ID_RE.search(row.get("external_url") or "")
        tid = found.group(1) if found else ""
        if tid and tid not in seen:
            seen.add(tid)
            ids.append(tid)
    return ids


def load_catalog() -> list[dict]:
    if not _CATALOG_PATH.exists():
        return []
    try:
        data = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
        songs = data.get("songs", data if isinstance(data, list) else [])
        return [localize_song(s) for s in songs]
    except Exception:
        logger.exception("读取本地曲库失败")
        return []


def stream_allowed(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        return False
    return any(host == suffix or host.endswith("." + suffix) for suffix in _STREAM_SUFFIXES)


def wrap_audio(url: str) -> str:
    if not url:
        return ""
    if url.startswith("/") and not url.startswith("//"):
        return url
    if not stream_allowed(url):
        return url
    return "/api/stream?u=" + quote(url, safe="")


def attach_stream(song: dict) -> dict:
    remote = song.get("audio") or song.get("preview") or ""
    if remote:
        song["remote"] = remote
        wrapped = wrap_audio(remote)
        song["audio"] = wrapped
        song["preview"] = wrapped
        song["playable"] = True
    return song


def open_remote_audio(url: str, range_header: Optional[str] = None):
    """Fetch a remote preview for same-origin playback. Caller must close the response."""
    if not stream_allowed(url):
        return None
    headers = dict(_SESSION.headers)
    if range_header:
        headers["Range"] = range_header
    try:
        resp = _SESSION.get(url, stream=True, timeout=20, headers=headers, allow_redirects=True)
    except Exception as exc:
        logger.warning("音源代理失败: %s", exc)
        return None
    if not stream_allowed(resp.url):
        resp.close()
        return None
    if resp.status_code not in (200, 206, 304):
        resp.close()
        return None
    return resp


def local_songs(emotion: str, limit: int = 96) -> list[dict]:
    catalog = [s for s in load_catalog() if s.get("source") == "local"]
    matched = [s for s in catalog if s.get("emotion") == emotion]
    vocals = [s for s in matched if s.get("kind") == "vocal"]
    others = [s for s in matched if s.get("kind") != "vocal"]
    songs = vocals + others
    if not songs:
        songs = list(catalog)
    return songs[:limit]


def _get_json(
    url: str,
    timeout: float,
    headers: Optional[dict] = None,
    params: Optional[dict] = None,
    session: Optional[requests.Session] = None,
) -> Optional[dict]:
    if timeout <= 0.2:
        return None
    sess = session or _SESSION
    try:
        r = sess.get(url, timeout=timeout, headers=headers, params=params)
        if r.status_code != 200:
            return None
        raw = (r.text or "").strip()
        if raw.startswith("IPDeny"):
            return None
        try:
            return r.json()
        except Exception:
            if raw.startswith("http"):
                return {"url": raw.split()[0]}
            return json.loads(raw.replace("'", '"'))
    except Exception as exc:
        logger.warning("在线请求失败 %s: %s", url[:80], exc)
        return None


def _remain(deadline: float) -> float:
    return max(0.0, deadline - time.time())


def _from_deezer(emotion: str, timeout: float) -> list[dict]:
    global _SKIP_DEEZER
    if _SKIP_DEEZER:
        return []
    meta = EMOTIONS[emotion]
    songs: list[dict] = []
    seen = set()
    deadline = time.time() + timeout
    for q in (meta["search"][:2] or _song_queries(emotion)[:2]):
        url = f"https://api.deezer.com/search?q={quote(q)}&limit=12"
        try:
            wait = _remain(deadline)
            if wait < 0.3:
                break
            r = _SESSION.get(url, timeout=wait)
            if r.status_code == 403:
                _SKIP_DEEZER = True
                logger.info("Deezer 当前不可用，已跳过")
                return []
            if r.status_code != 200:
                continue
            data = r.json()
        except Exception as exc:
            logger.warning("Deezer 请求失败: %s", exc)
            continue
        if not data:
            continue
        for item in data.get("data", []):
            tid = item.get("id")
            preview = item.get("preview") or ""
            title = (item.get("title") or "").strip()
            if not tid or not title or tid in seen:
                continue
            artist = ((item.get("artist") or {}).get("name")) or "未知艺术家"
            if not _accept_online(title, artist):
                continue
            seen.add(tid)
            album = item.get("album") or {}
            songs.append(
                {
                    "id": f"deezer-{tid}",
                    "title": title,
                    "artist": artist,
                    "album": album.get("title") or "",
                    "emotion": emotion,
                    "genre": meta["genre"],
                    "source": "deezer",
                    "source_label": SOURCE_LABEL["deezer"],
                    "preview": preview,
                    "audio": preview,
                    "cover": album.get("cover_medium") or album.get("cover") or "",
                    "external_url": item.get("link") or f"https://www.deezer.com/track/{tid}",
                    "duration": float(item.get("duration") or 30),
                    "playable": bool(preview),
                    "downloadable": False,
                }
            )
        if len(songs) >= 8:
            break
    return songs


def _from_audius(emotion: str, timeout: float) -> list[dict]:
    """Audius 公开检索，结果带可播音频流，作国际试听补充。"""
    meta = EMOTIONS[emotion]
    songs: list[dict] = []
    seen = set()
    deadline = time.time() + timeout
    queries = _song_queries(emotion)[:3]
    for q in queries:
        wait = _remain(deadline)
        if wait < 0.35:
            break
        data = _get_json(
            "https://discoveryprovider.audius.co/v1/tracks/search",
            wait,
            params={"query": q, "app_name": "emotune"},
        )
        rows = (data or {}).get("data") or []
        for item in rows:
            tid = str(item.get("id") or "").strip()
            title = (item.get("title") or "").strip()
            if not tid or not title or tid in seen:
                continue
            user = item.get("user") or {}
            artist = (user.get("name") or user.get("handle") or "未知艺术家").strip()
            if not _accept_online(title, artist, strict=False):
                continue
            seen.add(tid)
            art = item.get("artwork") or {}
            cover = art.get("480x480") or art.get("150x150") or ""
            stream = f"https://discoveryprovider.audius.co/v1/tracks/{tid}/stream?app_name=emotune"
            songs.append(
                {
                    "id": f"audius-{tid}",
                    "title": title,
                    "artist": artist,
                    "album": "",
                    "emotion": emotion,
                    "genre": meta["genre"],
                    "source": "audius",
                    "source_label": SOURCE_LABEL["audius"],
                    "preview": stream,
                    "audio": stream,
                    "cover": cover,
                    "external_url": item.get("permalink") or f"https://audius.co{item.get('permalink', '')}",
                    "duration": float(item.get("duration") or 30),
                    "playable": True,
                    "downloadable": False,
                }
            )
            if len(songs) >= 8:
                return songs
    return songs


def _song_queries(emotion: str) -> list[str]:
    queries: list[str] = []
    seen: set[str] = set()
    for q in EMOTIONS[emotion]["search"]:
        if q not in seen:
            seen.add(q)
            queries.append(q)
    for spec in VOCAL_SONGBOOK:
        if spec["emotion"] != emotion:
            continue
        q = spec.get("query") or f"{spec['title']} {spec['artist']}"
        if q not in seen:
            seen.add(q)
            queries.append(q)
    return queries


def _netease_pack(emotion: str, meta: dict, item: dict, seen: set) -> Optional[dict]:
    tid = item.get("id")
    title = (item.get("name") or "").strip()
    if not tid or not title or tid in seen:
        return None
    artists = item.get("artists") or item.get("ar") or []
    artist = " / ".join(a.get("name") or "" for a in artists if a.get("name")) or "未知艺术家"
    if not _accept_online(title, artist):
        return None
    seen.add(tid)
    album = (item.get("album") or item.get("al") or {}).get("name") or ""
    duration = item.get("duration") or item.get("dt") or 0
    return {
        "id": f"netease-{tid}",
        "nid": tid,
        "title": title,
        "artist": artist,
        "album": album,
        "emotion": emotion,
        "genre": meta["genre"],
        "source": "netease",
        "source_label": SOURCE_LABEL["netease"],
        "preview": "",
        "audio": "",
        "cover": "",
        "external_url": f"https://music.163.com/#/song?id={tid}",
        "duration": float(duration or 0) / 1000.0,
        "playable": False,
        "downloadable": False,
    }


def _itunes_item(emotion: str, item: dict) -> Optional[dict]:
    meta = EMOTIONS[emotion]
    tid = item.get("trackId")
    title = (item.get("trackName") or "").strip()
    preview = item.get("previewUrl") or ""
    if not tid or not title:
        return None
    artist_name = item.get("artistName") or "未知艺术家"
    genre = item.get("primaryGenreName") or ""
    if not _accept_online(title, artist_name, genre, strict=False):
        return None
    blob = fold_zh(f"{title} {artist_name}")
    if "karaoke" in blob or "伴奏" in title:
        return None
    art = item.get("artworkUrl100") or ""
    if art:
        art = art.replace("100x100bb", "300x300bb").replace("100x100", "300x300")
    return {
        "id": f"itunes-{tid}",
        "title": title,
        "artist": artist_name,
        "album": item.get("collectionName") or "",
        "emotion": emotion,
        "genre": genre or meta["genre"],
        "source": "itunes",
        "source_label": SOURCE_LABEL["itunes"],
        "preview": preview,
        "audio": preview,
        "cover": art,
        "external_url": item.get("trackViewUrl") or "",
        "duration": float(item.get("trackTimeMillis") or 30000) / 1000.0,
        "playable": bool(preview),
        "downloadable": False,
    }


def _from_itunes(emotion: str, timeout: float) -> list[dict]:
    songs: list[dict] = []
    seen: set[str] = set()
    deadline = time.time() + timeout

    def take(item: dict) -> None:
        parsed = _itunes_item(emotion, item)
        if not parsed or parsed["id"] in seen:
            return
        seen.add(parsed["id"])
        songs.append(parsed)

    apple_ids = _apple_ids_for(emotion)
    for i in range(0, min(len(apple_ids), 16), 4):
        wait = _remain(deadline)
        if wait < 0.45 or len(songs) >= 8:
            break
        chunk = apple_ids[i : i + 4]
        for item in itunes_lookup_ids(chunk, country="HK", timeout=min(2.2, wait)):
            take(item)
        if len(songs) >= 8:
            return songs[:12]

    queries = _song_queries(emotion)[:8]
    ascii_q = [q for q in queries if any(ch.isascii() and ch.isalpha() for ch in q)]
    jobs = (
        [(q, "HK") for q in queries[:3]]
        + [(q, "TW") for q in queries[:1]]
        + [(q, "US") for q in ascii_q[:2]]
    )

    def fetch(pair):
        q, country = pair
        remain = _remain(deadline)
        if remain < 0.4 or len(songs) >= 12:
            return []
        return itunes_search_results(q, country, timeout=remain, limit=6, attempts=1)

    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for found in pool.map(fetch, jobs):
            rows.extend(found)
    for item in rows:
        take(item)
        if len(songs) >= 12:
            break
    return songs[:12]


def _from_itunes_chart(emotion: str, timeout: float) -> list[dict]:
    """苹果商店热歌榜：只保留曲目书里已标过典型情绪的人声热歌。"""
    songs: list[dict] = []
    seen_ids: set[str] = set()
    deadline = time.time() + timeout
    by_country: dict[str, list[str]] = {}
    for country in ("HK", "TW", "JP", "US"):
        wait = _remain(deadline)
        if wait < 0.35:
            break
        data = _get_json(f"https://itunes.apple.com/{country.lower()}/rss/topsongs/limit=50/json", wait)
        entries = ((data or {}).get("feed") or {}).get("entry") or []
        if isinstance(entries, dict):
            entries = [entries]
        for entry in entries:
            title = ((entry.get("im:name") or {}).get("label") or "").strip()
            artist = ((entry.get("im:artist") or {}).get("label") or "").strip()
            if not title or emotion_of_title(title) != emotion:
                continue
            if not _accept_online(title, artist, strict=False):
                continue
            tid = str(((entry.get("id") or {}).get("attributes") or {}).get("im:id") or "")
            if not tid or tid in seen_ids:
                continue
            seen_ids.add(tid)
            by_country.setdefault(country, []).append(tid)
    seen_song: set[str] = set()
    for country, ids in by_country.items():
        wait = _remain(deadline)
        if wait < 0.35 or not ids:
            continue
        data = _get_json(
            "https://itunes.apple.com/lookup?id=" + ",".join(ids[:20]) + f"&country={country}",
            wait,
        )
        for item in (data or {}).get("results") or []:
            parsed = _itunes_item(emotion, item)
            if not parsed or parsed["id"] in seen_song:
                continue
            if emotion_of_title(parsed.get("title") or "") not in (emotion, None):
                continue
            seen_song.add(parsed["id"])
            parsed["source"] = "itunes_chart"
            parsed["source_label"] = SOURCE_LABEL["itunes_chart"]
            songs.append(parsed)
            if len(songs) >= 8:
                return songs
    return songs


def _from_apple_hot(emotion: str, timeout: float) -> list[dict]:
    """苹果商店当前最热播：只保留曲目书里已标过典型情绪的人声热歌。"""
    songs: list[dict] = []
    seen: set[str] = set()
    deadline = time.time() + timeout
    ids: list[str] = []
    for country in ("hk", "tw", "jp", "us"):
        wait = _remain(deadline)
        if wait < 0.4:
            break
        data = _get_json(
            f"https://rss.applemarketingtools.com/api/v2/{country}/music/most-played/50/songs.json",
            wait,
        )
        for item in ((data or {}).get("feed") or {}).get("results") or []:
            title = (item.get("name") or "").strip()
            artist = (item.get("artistName") or "").strip()
            tid = str(item.get("id") or "").strip()
            if not title or not tid or tid in seen:
                continue
            if emotion_of_title(title) != emotion:
                continue
            if not _accept_online(title, artist, strict=False):
                continue
            seen.add(tid)
            ids.append(tid)
            if len(ids) >= 16:
                break
        if len(ids) >= 16:
            break
    wait = _remain(deadline)
    if not ids or wait < 0.4:
        return songs
    found: set[str] = set()
    for item in itunes_lookup_ids(ids[:16], country="HK", timeout=min(2.2, wait)):
        parsed = _itunes_item(emotion, item)
        if not parsed or parsed["id"] in found:
            continue
        found.add(parsed["id"])
        parsed["source"] = "apple_hot"
        parsed["source_label"] = SOURCE_LABEL["apple_hot"]
        songs.append(parsed)
        if len(songs) >= 8:
            break
    return songs


def _from_apple_asia(emotion: str, timeout: float) -> list[dict]:
    """苹果日本/韩国/新加坡热歌与热播，补亚洲网红曲。"""
    songs: list[dict] = []
    seen: set[str] = set()
    deadline = time.time() + timeout
    ids: list[tuple[str, str]] = []
    for country in ("jp", "kr", "sg"):
        wait = _remain(deadline)
        if wait < 0.35:
            break
        data = _get_json(
            f"https://rss.applemarketingtools.com/api/v2/{country}/music/most-played/50/songs.json",
            wait,
        )
        for item in ((data or {}).get("feed") or {}).get("results") or []:
            title = (item.get("name") or "").strip()
            artist = (item.get("artistName") or "").strip()
            tid = str(item.get("id") or "").strip()
            if not title or not tid or tid in seen:
                continue
            if emotion_of_title(title) != emotion:
                continue
            if not _accept_online(title, artist, strict=False):
                continue
            seen.add(tid)
            ids.append((tid, country.upper()))
            if len(ids) >= 16:
                break
        wait = _remain(deadline)
        if wait < 0.35 or len(ids) >= 16:
            continue
        rss = _get_json(f"https://itunes.apple.com/{country}/rss/topsongs/limit=50/json", wait)
        entries = ((rss or {}).get("feed") or {}).get("entry") or []
        if isinstance(entries, dict):
            entries = [entries]
        for entry in entries:
            title = ((entry.get("im:name") or {}).get("label") or "").strip()
            artist = ((entry.get("im:artist") or {}).get("label") or "").strip()
            tid = str(((entry.get("id") or {}).get("attributes") or {}).get("im:id") or "")
            if not title or not tid or tid in seen:
                continue
            if emotion_of_title(title) != emotion:
                continue
            if not _accept_online(title, artist, strict=False):
                continue
            seen.add(tid)
            ids.append((tid, country.upper()))
            if len(ids) >= 16:
                break
        if len(ids) >= 16:
            break
    found: set[str] = set()
    by_country: dict[str, list[str]] = {}
    for tid, country in ids:
        by_country.setdefault(country, []).append(tid)
    for country, chunk in by_country.items():
        wait = _remain(deadline)
        if wait < 0.35 or not chunk:
            continue
        for item in itunes_lookup_ids(chunk[:12], country=country, timeout=min(2.2, wait)):
            parsed = _itunes_item(emotion, item)
            if not parsed or parsed["id"] in found:
                continue
            found.add(parsed["id"])
            parsed["source"] = "apple_asia"
            parsed["source_label"] = SOURCE_LABEL["apple_asia"]
            songs.append(parsed)
            if len(songs) >= 8:
                return songs
    return songs


def _from_netease(emotion: str, timeout: float) -> list[dict]:
    """网易云公开搜索接口，外链音频可作试听；封面走歌曲详情批量接口。"""
    meta = EMOTIONS[emotion]
    headers = {"Referer": "https://music.163.com/"}
    songs: list[dict] = []
    seen = set()
    queries = [q for q in _song_queries(emotion) if any("\u4e00" <= ch <= "\u9fff" for ch in q)]
    if not queries:
        queries = [q for q in meta["search"] if any("\u4e00" <= ch <= "\u9fff" for ch in q)]
    if not queries:
        queries = [meta["name"]]
    raw_items = []
    deadline = time.time() + timeout
    for q in queries[:4]:
        wait = _remain(deadline)
        if wait < 0.3:
            break
        try:
            r = _DIRECT.get(
                "https://music.163.com/api/search/get/web",
                params={"s": q, "type": 1, "offset": 0, "limit": 8},
                headers=headers,
                timeout=wait,
            )
            if r.status_code != 200:
                continue
            data = r.json()
        except Exception as exc:
            logger.warning("网易云搜索失败: %s", exc)
            continue
        for item in ((data.get("result") or {}).get("songs") or []):
            packed = _netease_pack(emotion, meta, item, seen)
            if packed:
                raw_items.append(packed)
        if len(raw_items) >= 8:
            break
    if len(raw_items) < 4:
        for q in queries[:3]:
            wait = _remain(deadline)
            if wait < 0.3:
                break
            data = _get_json(
                "https://music.163.com/api/cloudsearch/pc",
                wait,
                headers=headers,
                params={"s": q, "type": 1, "limit": 8, "offset": 0},
                session=_DIRECT,
            )
            for item in ((data or {}).get("result") or {}).get("songs") or []:
                packed = _netease_pack(emotion, meta, item, seen)
                if packed:
                    raw_items.append(packed)
            if len(raw_items) >= 8:
                break
    if raw_items:
        ids = [int(s["nid"]) for s in raw_items[:12]]
        try:
            det = _DIRECT.get(
                "https://music.163.com/api/song/detail",
                params={"ids": json.dumps(ids)},
                headers=headers,
                timeout=max(0.4, _remain(deadline)),
            )
            if det.status_code == 200:
                covers = {}
                for song in det.json().get("songs") or []:
                    covers[song.get("id")] = ((song.get("album") or {}).get("picUrl")) or ""
                for s in raw_items:
                    s["cover"] = covers.get(s["nid"], "")
        except Exception as exc:
            logger.warning("网易云封面获取失败: %s", exc)
        try:
            wait = max(0.4, _remain(deadline))
            pr = _DIRECT.get(
                "https://music.163.com/api/song/enhance/player/url",
                params={"ids": json.dumps(ids), "br": 128000},
                headers=headers,
                timeout=wait,
            )
            if pr.status_code == 200:
                by_id = {row.get("id"): (row.get("url") or "") for row in (pr.json().get("data") or [])}
                for s in raw_items:
                    url = by_id.get(s["nid"]) or ""
                    if url:
                        s["preview"] = url
                        s["audio"] = url
                        s["playable"] = True
        except Exception as exc:
            logger.warning("网易云试听获取失败: %s", exc)
        if any(not s.get("playable") for s in raw_items):
            try:
                wait = max(0.4, _remain(deadline))
                pr2 = _DIRECT.get(
                    "https://music.163.com/api/song/enhance/player/url/v1",
                    params={"ids": json.dumps(ids), "level": "standard", "encodeType": "aac"},
                    headers=headers,
                    timeout=wait,
                )
                if pr2.status_code == 200:
                    by_id = {row.get("id"): (row.get("url") or "") for row in (pr2.json().get("data") or [])}
                    for s in raw_items:
                        if s.get("playable"):
                            continue
                        url = by_id.get(s["nid"]) or ""
                        if url:
                            s["preview"] = url
                            s["audio"] = url
                            s["playable"] = True
            except Exception as exc:
                logger.warning("网易云试听 v1 失败: %s", exc)
        for s in raw_items:
            s.pop("nid", None)
            if s.get("playable"):
                songs.append(s)
    return songs


def _netease_fill_playable(raw_items: list[dict], deadline: float) -> list[dict]:
    songs: list[dict] = []
    if not raw_items:
        return songs
    ids = [int(s["nid"]) for s in raw_items[:12] if s.get("nid")]
    headers = {"Referer": "https://music.163.com/"}
    if not ids:
        return songs
    try:
        wait = max(0.4, _remain(deadline))
        pr = _DIRECT.get(
            "https://music.163.com/api/song/enhance/player/url",
            params={"ids": json.dumps(ids), "br": 128000},
            headers=headers,
            timeout=wait,
        )
        if pr.status_code == 200:
            by_id = {row.get("id"): (row.get("url") or "") for row in (pr.json().get("data") or [])}
            for s in raw_items:
                url = by_id.get(s["nid"]) or ""
                if url:
                    s["preview"] = url
                    s["audio"] = url
                    s["playable"] = True
    except Exception as exc:
        logger.warning("网易云热歌试听失败: %s", exc)
    for s in raw_items:
        s.pop("nid", None)
        if s.get("playable"):
            songs.append(s)
    return songs


def _from_netease_hot(emotion: str, timeout: float) -> list[dict]:
    """网易云热歌榜 / 新歌榜，只保留曲目书已标情绪的人声。"""
    meta = EMOTIONS[emotion]
    seen = set()
    raw_items: list[dict] = []
    deadline = time.time() + timeout
    headers = {"Referer": "https://music.163.com/"}
    for pid in (3778678, 3779629):
        wait = _remain(deadline)
        if wait < 0.35 or len(raw_items) >= 8:
            break
        data = _get_json(
            "https://music.163.com/api/playlist/detail",
            wait,
            headers=headers,
            params={"id": pid},
            session=_DIRECT,
        )
        tracks = ((data or {}).get("result") or {}).get("tracks") or []
        if not tracks:
            data = _get_json(
                "https://music.163.com/api/v6/playlist/detail",
                _remain(deadline),
                headers=headers,
                params={"id": pid, "n": 50},
                session=_DIRECT,
            )
            tracks = ((data or {}).get("playlist") or {}).get("tracks") or []
        for item in tracks:
            title = (item.get("name") or "").strip()
            if emotion_of_title(title) != emotion:
                continue
            packed = _netease_pack(emotion, meta, item, seen)
            if packed:
                packed["source"] = "netease_hot"
                packed["source_label"] = SOURCE_LABEL["netease_hot"]
                raw_items.append(packed)
            if len(raw_items) >= 8:
                break
    return _netease_fill_playable(raw_items, deadline)


def _from_migu(emotion: str, timeout: float) -> list[dict]:
    """咪咕公开检索，部分结果带试听地址，作为华语热歌补充。"""
    meta = EMOTIONS[emotion]
    songs: list[dict] = []
    seen = set()
    deadline = time.time() + timeout
    headers = {
        "Referer": "https://m.music.migu.cn/",
        "Accept": "application/json,text/plain,*/*",
    }
    for q in ():
        wait = _remain(deadline)
        if wait < 0.35:
            break
        url = (
            "https://m.music.migu.cn/migu/remoting/scr_search_tag"
            f"?rows=8&type=2&keyword={quote(q)}&pgc=1"
        )
        data = _get_json(url, wait, headers=headers, session=_DIRECT)
        if not data:
            continue
        for item in data.get("songs") or data.get("musics") or []:
            tid = item.get("copyrightId") or item.get("id") or item.get("songId")
            title = (item.get("songName") or item.get("title") or "").strip()
            artist = (item.get("singerName") or item.get("artist") or "未知艺术家").strip()
            preview = item.get("mp3") or item.get("listenUrl") or item.get("hqUrl") or ""
            if not tid or not title or tid in seen:
                continue
            if not _accept_online(title, artist):
                continue
            seen.add(tid)
            cover = item.get("cover") or item.get("albumPic") or item.get("poster") or ""
            songs.append(
                {
                    "id": f"migu-{tid}",
                    "title": title,
                    "artist": artist,
                    "album": item.get("albumName") or item.get("album") or "",
                    "emotion": emotion,
                    "genre": meta["genre"],
                    "source": "migu",
                    "source_label": SOURCE_LABEL["migu"],
                    "preview": preview,
                    "audio": preview,
                    "cover": cover,
                    "external_url": item.get("songUrl")
                    or f"https://music.migu.cn/v3/music/song/{tid}",
                    "duration": 30.0,
                    "playable": bool(preview),
                    "downloadable": False,
                }
            )
        if len(songs) >= 8:
            break
    if sum(1 for s in songs if s.get("playable")) < 4:
        migu_headers = {
            "Referer": "https://music.migu.cn/",
            "Accept": "application/json,text/plain,*/*",
        }
        for q in _song_queries(emotion)[:3]:
            wait = _remain(deadline)
            if wait < 0.35:
                break
            data = _get_json(
                "https://pd.musicapp.migu.cn/MIGUM3.0/v1.0/content/search_all.do",
                wait,
                headers=migu_headers,
                params={"text": q, "pageNo": 1, "pageSize": 8, "searchSwitch": '{"song":1}'},
                session=_DIRECT,
            )
            rows = (((data or {}).get("songResultData") or {}).get("result") or [])
            for item in rows:
                tid = item.get("copyrightId") or item.get("id") or item.get("contentId")
                title = (item.get("name") or item.get("songName") or "").strip()
                singers = item.get("singers") or item.get("artists") or []
                if isinstance(singers, list) and singers and isinstance(singers[0], dict):
                    artist = " / ".join(s.get("name") or "" for s in singers if s.get("name")) or "未知艺术家"
                else:
                    artist = str(item.get("singerName") or item.get("artist") or "未知艺术家").strip()
                preview = item.get("listenUrl") or item.get("mp3") or item.get("hqUrl") or ""
                if not tid or not title or tid in seen:
                    continue
                if not _accept_online(title, artist):
                    continue
                seen.add(tid)
                cover = ""
                imgs = item.get("imgItems") or []
                if imgs and isinstance(imgs[0], dict):
                    cover = imgs[0].get("img") or ""
                cover = cover or item.get("cover") or item.get("albumImg") or ""
                songs.append(
                    {
                        "id": f"migu-{tid}",
                        "title": title,
                        "artist": artist,
                        "album": (item.get("albums") or [{}])[0].get("name") if item.get("albums") else item.get("album") or "",
                        "emotion": emotion,
                        "genre": meta["genre"],
                        "source": "migu",
                        "source_label": SOURCE_LABEL["migu"],
                        "preview": preview,
                        "audio": preview,
                        "cover": cover,
                        "external_url": f"https://music.migu.cn/v3/music/song/{tid}",
                        "duration": 30.0,
                        "playable": bool(preview),
                        "downloadable": False,
                    }
                )
            if len(songs) >= 8:
                break
    return songs


def _from_kugou(emotion: str, timeout: float) -> list[dict]:
    """酷狗移动端公开搜索，补充华语热歌；试听地址视接口返回而定。"""
    meta = EMOTIONS[emotion]
    songs: list[dict] = []
    seen = set()
    deadline = time.time() + timeout
    for q in _song_queries(emotion)[:4]:
        wait = _remain(deadline)
        if wait < 0.35:
            break
        url = (
            "http://mobilecdn.kugou.com/api/v3/search/song"
            f"?format=json&keyword={quote(q)}&page=1&pagesize=8"
        )
        data = _get_json(url, wait, session=_DIRECT)
        for item in ((data or {}).get("data") or {}).get("info") or []:
            tid = item.get("hash") or item.get("audio_id")
            title = (item.get("songname") or item.get("filename") or "").strip()
            artist = (item.get("singername") or "未知艺术家").strip()
            if not tid or not title or tid in seen:
                continue
            if not _accept_online(title, artist):
                continue
            seen.add(tid)
            cover = (item.get("album_img") or item.get("imgUrl") or "").replace("{size}", "400")
            preview = item.get("url") or item.get("m4aurl") or ""
            songs.append(
                {
                    "id": f"kugou-{tid}",
                    "hash": tid,
                    "title": title,
                    "artist": artist,
                    "album": item.get("album_name") or "",
                    "emotion": emotion,
                    "genre": meta["genre"],
                    "source": "kugou",
                    "source_label": SOURCE_LABEL["kugou"],
                    "preview": preview,
                    "audio": preview,
                    "cover": cover,
                    "external_url": f"https://www.kugou.com/song/#hash={tid}",
                    "duration": float(item.get("duration") or 30),
                    "playable": bool(preview),
                    "downloadable": False,
                }
            )
        if len(songs) >= 8:
            break
    if len(songs) < 4:
        for q in _song_queries(emotion)[:3]:
            wait = _remain(deadline)
            if wait < 0.35:
                break
            data = _get_json(
                "https://songsearch.kugou.com/song_search_v2",
                wait,
                params={"keyword": q, "page": 1, "pagesize": 8, "platform": "WebFilter"},
                session=_DIRECT,
            )
            for item in ((data or {}).get("data") or {}).get("lists") or []:
                tid = item.get("FileHash") or item.get("HQFileHash") or item.get("SQFileHash")
                title = (item.get("SongName") or item.get("FileName") or "").strip()
                artist = (item.get("SingerName") or "未知艺术家").strip()
                if not tid or not title or tid in seen:
                    continue
                if not _accept_online(title, artist):
                    continue
                seen.add(tid)
                cover = (item.get("Image") or item.get("AlbumID") or "")
                if "{size}" in str(cover):
                    cover = str(cover).replace("{size}", "400")
                songs.append(
                    {
                        "id": f"kugou-{tid}",
                        "hash": tid,
                        "title": title,
                        "artist": artist,
                        "album": item.get("AlbumName") or "",
                        "emotion": emotion,
                        "genre": meta["genre"],
                        "source": "kugou",
                        "source_label": SOURCE_LABEL["kugou"],
                        "preview": "",
                        "audio": "",
                        "cover": cover if str(cover).startswith("http") else "",
                        "external_url": f"https://www.kugou.com/song/#hash={tid}",
                        "duration": float(item.get("Duration") or 30),
                        "playable": False,
                        "downloadable": False,
                    }
                )
            if len(songs) >= 8:
                break

    def play_one(song: dict) -> dict:
        if song.get("audio"):
            song.pop("hash", None)
            return song
        hid = song.pop("hash", "")
        wait = max(0.3, _remain(deadline))
        data = _get_json(
            "http://m.kugou.com/app/i/getSongInfo.php",
            wait,
            params={"cmd": "playInfo", "hash": hid},
            session=_DIRECT,
        )
        url = (data or {}).get("url") or ""
        if url:
            song["preview"] = url
            song["audio"] = url
            song["playable"] = True
        return song

    with ThreadPoolExecutor(max_workers=4) as pool:
        songs = list(pool.map(play_one, songs[:8]))
    return [s for s in songs if s.get("playable")]


def _from_qq(emotion: str, timeout: float) -> list[dict]:
    """QQ 音乐公开搜索，封面稳定；能拿到 vkey 时附带试听。"""
    meta = EMOTIONS[emotion]
    songs: list[dict] = []
    seen = set()
    deadline = time.time() + timeout
    raw: list[dict] = []
    headers = {"Referer": "https://y.qq.com/"}
    for q in _song_queries(emotion)[:4]:
        wait = _remain(deadline)
        if wait < 0.35:
            break
        url = (
            "https://c.y.qq.com/soso/fcgi-bin/client_search_cp"
            f"?p=1&n=8&w={quote(q)}&format=json&inCharset=utf8&outCharset=utf-8"
        )
        data = _get_json(url, wait, headers=headers, session=_DIRECT)
        for item in (((data or {}).get("data") or {}).get("song") or {}).get("list") or []:
            mid = item.get("songmid")
            title = (item.get("songname") or "").strip()
            if not mid or not title or mid in seen:
                continue
            singers = item.get("singer") or []
            artist = " / ".join(s.get("name") or "" for s in singers if s.get("name")) or "未知艺术家"
            if not _accept_online(title, artist):
                continue
            seen.add(mid)
            albummid = item.get("albummid") or ""
            cover = (
                f"https://y.gtimg.cn/music/photo_new/T002R300x300M000{albummid}.jpg"
                if albummid
                else ""
            )
            raw.append(
                {
                    "id": f"qq-{mid}",
                    "mid": mid,
                    "title": title,
                    "artist": artist,
                    "album": item.get("albumname") or "",
                    "emotion": emotion,
                    "genre": meta["genre"],
                    "source": "qq",
                    "source_label": SOURCE_LABEL["qq"],
                    "preview": "",
                    "audio": "",
                    "cover": cover,
                    "external_url": f"https://y.qq.com/n/ryqq/songDetail/{mid}",
                    "duration": float(item.get("interval") or 30),
                    "playable": False,
                    "downloadable": False,
                }
            )
        if len(raw) >= 8:
            break
    mids = [s["mid"] for s in raw[:8]]
    wait = _remain(deadline)
    if mids and wait >= 0.4:
        payload = {
            "req_0": {
                "module": "vkey.GetVkeyServer",
                "method": "CgiGetVkey",
                "param": {
                    "guid": "10000",
                    "songmid": mids,
                    "songtype": [0] * len(mids),
                    "uin": "0",
                    "loginflag": 0,
                    "platform": "20",
                },
            },
            "comm": {"uin": 0, "format": "json", "ct": 24, "cv": 0},
        }
        try:
            r = _DIRECT.get(
                "https://u.y.qq.com/cgi-bin/musicu.fcg",
                params={"data": json.dumps(payload, separators=(",", ":"))},
                headers=headers,
                timeout=wait,
            )
            if r.status_code == 200:
                block = ((r.json().get("req_0") or {}).get("data") or {})
                sip = (block.get("sip") or [""])[0]
                by_mid = {info.get("songmid"): info for info in (block.get("midurlinfo") or [])}
                for s in raw:
                    info = by_mid.get(s.get("mid")) or {}
                    purl = info.get("purl") or ""
                    if sip and purl:
                        url = sip + purl
                        s["preview"] = url
                        s["audio"] = url
                        s["playable"] = True
        except Exception as exc:
            logger.warning("QQ 试听地址失败: %s", exc)
    for s in raw:
        s.pop("mid", None)
        if s.get("playable"):
            songs.append(s)
    return songs


def _qq_attach_preview(raw: list[dict], deadline: float) -> list[dict]:
    songs: list[dict] = []
    mids = [s.get("mid") for s in raw[:8] if s.get("mid")]
    wait = _remain(deadline)
    headers = {"Referer": "https://y.qq.com/"}
    if mids and wait >= 0.4:
        payload = {
            "req_0": {
                "module": "vkey.GetVkeyServer",
                "method": "CgiGetVkey",
                "param": {
                    "guid": "10000",
                    "songmid": mids,
                    "songtype": [0] * len(mids),
                    "uin": "0",
                    "loginflag": 0,
                    "platform": "20",
                },
            },
            "comm": {"uin": 0, "format": "json", "ct": 24, "cv": 0},
        }
        try:
            r = _DIRECT.get(
                "https://u.y.qq.com/cgi-bin/musicu.fcg",
                params={"data": json.dumps(payload, separators=(",", ":"))},
                headers=headers,
                timeout=wait,
            )
            if r.status_code == 200:
                block = ((r.json().get("req_0") or {}).get("data") or {})
                sip = (block.get("sip") or [""])[0]
                by_mid = {info.get("songmid"): info for info in (block.get("midurlinfo") or [])}
                for s in raw:
                    info = by_mid.get(s.get("mid")) or {}
                    purl = info.get("purl") or ""
                    if sip and purl:
                        url = sip + purl
                        s["preview"] = url
                        s["audio"] = url
                        s["playable"] = True
        except Exception as exc:
            logger.warning("QQ 热歌试听失败: %s", exc)
    for s in raw:
        s.pop("mid", None)
        if s.get("playable"):
            songs.append(s)
    return songs


def _from_qq_hot(emotion: str, timeout: float) -> list[dict]:
    """QQ 音乐热歌榜 / 流行指数榜，只保留曲目书已标情绪的人声。"""
    meta = EMOTIONS[emotion]
    seen = set()
    raw: list[dict] = []
    deadline = time.time() + timeout
    headers = {"Referer": "https://y.qq.com/"}
    for topid in (26, 4):
        wait = _remain(deadline)
        if wait < 0.35 or len(raw) >= 8:
            break
        data = _get_json(
            "https://c.y.qq.com/v8/fcg-bin/fcg_v8_toplist_cp.fcg",
            wait,
            headers=headers,
            params={"topid": topid, "song_begin": 0, "song_num": 40, "format": "json", "inCharset": "utf8", "outCharset": "utf-8"},
            session=_DIRECT,
        )
        rows = ((data or {}).get("songlist") or [])
        for wrap in rows:
            item = wrap.get("data") if isinstance(wrap, dict) and "data" in wrap else wrap
            if not isinstance(item, dict):
                continue
            mid = item.get("songmid") or item.get("mid")
            title = (item.get("songname") or item.get("title") or "").strip()
            if not mid or not title or mid in seen:
                continue
            if emotion_of_title(title) != emotion:
                continue
            singers = item.get("singer") or []
            artist = " / ".join(s.get("name") or "" for s in singers if isinstance(s, dict) and s.get("name")) or "未知艺术家"
            if not _accept_online(title, artist, strict=False):
                continue
            seen.add(mid)
            albummid = item.get("albummid") or ""
            cover = (
                f"https://y.gtimg.cn/music/photo_new/T002R300x300M000{albummid}.jpg"
                if albummid
                else ""
            )
            raw.append(
                {
                    "id": f"qqhot-{mid}",
                    "mid": mid,
                    "title": title,
                    "artist": artist,
                    "album": item.get("albumname") or "",
                    "emotion": emotion,
                    "genre": meta["genre"],
                    "source": "qq_hot",
                    "source_label": SOURCE_LABEL["qq_hot"],
                    "preview": "",
                    "audio": "",
                    "cover": cover,
                    "external_url": f"https://y.qq.com/n/ryqq/songDetail/{mid}",
                    "duration": float(item.get("interval") or 30),
                    "playable": False,
                    "downloadable": False,
                }
            )
            if len(raw) >= 8:
                break
    return _qq_attach_preview(raw, deadline)


def _from_kuwo(emotion: str, timeout: float) -> list[dict]:
    """酷我公开搜索 + anti 试听地址，补充华语热歌。"""
    meta = EMOTIONS[emotion]
    songs: list[dict] = []
    seen = set()
    deadline = time.time() + timeout
    raw: list[dict] = []
    for q in _song_queries(emotion)[:4]:
        wait = _remain(deadline)
        if wait < 0.35:
            break
        url = (
            "http://search.kuwo.cn/r.s"
            f"?all={quote(q)}&ft=music&itemset=web_2013&client=kt&pn=0&rn=8"
            "&rformat=json&encoding=utf8&vipver=1&vermerge=1"
        )
        data = _get_json(url, wait, session=_DIRECT)
        rows = []
        if isinstance(data, dict):
            rows = data.get("abslist") or data.get("list") or []
        for item in rows:
            rid = str(item.get("DC_TARGETID") or item.get("MUSICRID") or item.get("rid") or "")
            rid = rid.replace("MUSIC_", "")
            title = (item.get("SONGNAME") or item.get("NAME") or item.get("name") or "").strip()
            artist = (item.get("ARTIST") or item.get("artist") or "未知艺术家").strip()
            if not rid or not title or rid in seen:
                continue
            if not _accept_online(title, artist):
                continue
            seen.add(rid)
            cover = item.get("web_albumpic_short") or item.get("hts_mvpic") or ""
            if cover and cover.startswith("//"):
                cover = "https:" + cover
            raw.append(
                {
                    "id": f"kuwo-{rid}",
                    "rid": rid,
                    "title": title,
                    "artist": artist,
                    "album": item.get("ALBUM") or item.get("album") or "",
                    "emotion": emotion,
                    "genre": meta["genre"],
                    "source": "kuwo",
                    "source_label": SOURCE_LABEL["kuwo"],
                    "preview": "",
                    "audio": "",
                    "cover": cover,
                    "external_url": f"https://www.kuwo.cn/play_detail/{rid}",
                    "duration": float(item.get("DURATION") or item.get("duration") or 30),
                    "playable": False,
                    "downloadable": False,
                }
            )
        if len(raw) >= 8:
            break

    def play_one(song: dict) -> dict:
        rid = song.pop("rid", "")
        wait = max(0.3, _remain(deadline))
        play = (
            "https://antiserver.kuwo.cn/anti.s"
            f"?type=convert_url3&rid={rid}&format=mp3&response=url&br=128kmp3"
        )
        data = _get_json(play, wait, session=_DIRECT)
        url = ""
        if isinstance(data, dict):
            url = data.get("url") or ""
        if not url:
            wait = max(0.25, _remain(deadline))
            alt = _get_json(
                "https://www.kuwo.cn/api/v1/www/music/playUrl",
                wait,
                params={"mid": rid, "type": "music", "httpsStatus": 1},
                session=_DIRECT,
            )
            if isinstance(alt, dict):
                url = ((alt.get("data") or {}).get("url") if isinstance(alt.get("data"), dict) else "") or alt.get("url") or ""
        if url:
            song["preview"] = url
            song["audio"] = url
            song["playable"] = True
        return song

    with ThreadPoolExecutor(max_workers=4) as pool:
        cooked = list(pool.map(play_one, raw[:8]))
    return [s for s in cooked if s.get("playable")]


def _run_online_fetchers(
    emotion: str,
    names: list[str],
    fetchers: dict,
    each: float,
    buckets: dict[str, list[dict]],
) -> None:
    jobs = {name: fetchers[name] for name in names if name in fetchers and name not in _SKIP_APIS}
    if not jobs:
        return
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(jobs)))) as pool:
        futures = {
            name: pool.submit(fn, emotion, min(each, _API_TIMEOUTS.get(name, each)))
            for name, fn in jobs.items()
        }
        wall = max(_API_TIMEOUTS.get(name, each) for name in jobs) + 0.3
        for name, fut in futures.items():
            try:
                buckets[name] = fut.result(timeout=wall) or []
            except Exception:
                buckets[name] = []
            if name in _FLAKY_APIS and not buckets[name]:
                _SKIP_APIS.add(name)


def _merge_online_buckets(order: list[str], buckets: dict[str, list[dict]]) -> list[dict]:
    merged: list[dict] = []
    titles = set()
    apple_src = set(_APPLE_APIS)
    for name in order:
        for item in buckets.get(name) or []:
            src_name = item.get("source") or ""
            if not _accept_online(
                item.get("title") or "",
                item.get("artist") or "",
                item.get("genre") or "",
                strict=src_name not in apple_src,
            ):
                continue
            if not (item.get("audio") or item.get("preview")):
                continue
            key = title_key(item.get("title") or "")
            if title_seen(key, titles):
                continue
            if item.get("source") not in apple_src and len(key) < 3:
                continue
            titles.add(key)
            merged.append(attach_stream(item))
    return merged


def online_songs(emotion: str, timeout: float = ONLINE_TIMEOUT) -> list[dict]:
    now = time.time()
    cached = _CACHE.get(emotion)
    if cached:
        ttl = _CACHE_TTL if len(cached[1]) >= 8 else _EMPTY_CACHE_TTL
        if now - cached[0] < ttl:
            return cached[1]

    each = max(1.6, timeout)
    fetchers = {
        "itunes": _from_itunes,
        "itunes_chart": _from_itunes_chart,
        "apple_hot": _from_apple_hot,
        "apple_asia": _from_apple_asia,
        "qq": _from_qq,
        "qq_hot": _from_qq_hot,
        "kugou": _from_kugou,
        "kuwo": _from_kuwo,
        "netease": _from_netease,
        "netease_hot": _from_netease_hot,
        "migu": _from_migu,
        "deezer": _from_deezer,
        "audius": _from_audius,
    }
    order = [name for name in ONLINE_APIS if name in fetchers]
    apple_names = [name for name in order if name in _APPLE_APIS]
    other_names = [name for name in order if name not in _APPLE_APIS]
    buckets: dict[str, list[dict]] = {name: [] for name in order}
    _run_online_fetchers(emotion, apple_names, fetchers, each, buckets)
    merged = _merge_online_buckets(order, buckets)
    if len(merged) < 8:
        _run_online_fetchers(emotion, other_names, fetchers, each, buckets)
        merged = _merge_online_buckets(order, buckets)
    if len(merged) < 6:
        extra_ids = _apple_ids_for(emotion)[8:20]
        wait = min(2.0, max(0.6, timeout * 0.4))
        if extra_ids:
            seen = {s.get("id") for s in merged}
            titles = {title_key(s.get("title") or "") for s in merged}
            for item in itunes_lookup_ids(extra_ids[:8], country="HK", timeout=wait):
                parsed = _itunes_item(emotion, item)
                if not parsed or parsed["id"] in seen:
                    continue
                key = title_key(parsed.get("title") or "")
                if title_seen(key, titles):
                    continue
                seen.add(parsed["id"])
                titles.add(key)
                merged.append(attach_stream(parsed))
                if len(merged) >= 8:
                    break
    result = [localize_song(s) for s in merged[:20]]
    _CACHE[emotion] = (now, result)
    return result


def _exclude_keys(exclude) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for item in exclude or []:
        if isinstance(item, dict):
            key = title_key(item.get("key") or "") or title_key(item.get("title") or "")
        else:
            key = title_key(str(item or ""))
        if key and key not in seen:
            seen.add(key)
            keys.append(key)
    return keys


def _rank_bucket(batch: list[dict], face_vec, emotion: str) -> list[dict]:
    scored = []
    for song in batch:
        desc = describe_song(song, emotion)
        match = match_score(face_vec, desc)
        item = dict(song)
        item["music"] = public_music(desc)
        item["match"] = match
        pri = play_priority(item.get("title") or "", item.get("artist") or "", emotion)
        scored.append((pri, match, item))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    return [item for _, _, item in scored]


def _pool_songs(emotions: list[str], want_online: bool, limit: int) -> tuple[dict[str, list[dict]], dict[str, list[dict]], Optional[str]]:
    local_map: dict[str, list[dict]] = {eid: local_songs(eid, limit=limit) for eid in emotions}
    online_map: dict[str, list[dict]] = {eid: [] for eid in emotions}
    online_error = None
    if not want_online:
        return local_map, online_map, None
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(emotions)))) as pool:
        futs = {eid: pool.submit(online_songs, eid) for eid in emotions}
        for eid, fut in futs.items():
            try:
                online_map[eid] = [s for s in (fut.result() or []) if s.get("playable") and s.get("audio")]
            except Exception as exc:
                online_error = str(exc)
                logger.warning("在线推荐失败 %s: %s", eid, exc)
                online_map[eid] = []
    return local_map, online_map, online_error


def recommend(
    emotion: str,
    count: int = RECOMMEND_COUNT,
    want_online: bool = True,
    exclude: Optional[list] = None,
    face_scores=None,
    strategy: str = DEFAULT_STRATEGY,
) -> dict:
    if emotion not in EMOTIONS:
        emotion = "neutral"
    meta = EMOTIONS[emotion]
    sid = normalize(strategy)
    count = max(6, int(count or RECOMMEND_COUNT))
    stages = plan(emotion, sid, count)
    emos = involved_emotions(stages) or [emotion]

    skip_src = list(exclude or [])
    try:
        from backend.history import played_map

        pins = front_pin_keys()
        for rows in (played_map() or {}).values():
            skip_src.extend(key for key in (rows or []) if key not in pins)
    except Exception:
        pass
    skip = _exclude_keys(skip_src)
    skip_at = {key: idx for idx, key in enumerate(skip)}
    face_vec = face_vector(face_scores, emotion)

    local_map, online_map, online_error = _pool_songs(emos, want_online, limit=max(count, 96))

    def split(batch: list[dict]) -> tuple[list[dict], list[dict]]:
        fresh: list[dict] = []
        used: list[dict] = []
        for song in batch:
            key = title_key(song.get("title") or "")
            if key in skip_at:
                used.append(song)
            else:
                fresh.append(song)
        used.sort(key=lambda s: skip_at.get(title_key(s.get("title") or ""), 0))
        return fresh, used

    seen: set[str] = set()

    def fill_stage(stage: dict) -> list[dict]:
        eid = stage["emotion"]
        n = stage["count"]
        rank_vec = face_vec if stage.get("rank") == "face" else target_vector(eid)
        local = local_map.get(eid) or []
        online = online_map.get(eid) or [] if want_online else []
        picked: list[dict] = []

        def take(batch: list[dict]) -> None:
            for song in _rank_bucket(batch, rank_vec, eid):
                if len(picked) >= n:
                    return
                key = title_key(song.get("title") or "")
                if title_seen(key, seen):
                    continue
                seen.add(key)
                item = dict(song)
                item["rec_role"] = stage["role"]
                item["rec_role_zh"] = stage["role_zh"]
                item["rec_from"] = emotion
                picked.append(item)

        online_fresh, online_used = split(online) if want_online else ([], [])
        local_fresh, local_used = split(local)
        if want_online:
            take(online_fresh + local_fresh)
            take(online_used + local_used)
        else:
            take(local_fresh)
            take(local_used)
        return picked

    parts = [fill_stage(stage) for stage in stages]
    mixed = interleave(parts) if sid == "balance" else [song for part in parts for song in part]

    if len(mixed) < count:
        leftover_e = emos[-1]
        extra_stage = dict(stages[-1] if stages else {"emotion": leftover_e, "count": count - len(mixed), "role": "iso", "role_zh": "同频", "rank": "target"})
        extra_stage["count"] = count - len(mixed)
        mixed.extend(fill_stage(extra_stage))

    songs = [localize_song(s) for s in mixed[:count]]
    online_count = sum(1 for s in songs if s.get("source") != "local")
    if want_online and online_count == 0 and not online_error:
        online_error = "在线接口暂无可用试听"
    providers = []
    for s in songs:
        label = s.get("source_label") or ""
        if s.get("source") != "local" and label and label not in providers:
            providers.append(label)
    mode = "online" if want_online and online_count else ("local" if not want_online else "local-fallback")
    strat = summary(sid, emotion, stages)
    strat["music"] = MUSIC_ALGO
    return {
        "emotion": emotion,
        "genre": meta["genre"],
        "copy": meta["copy"],
        "songs": songs,
        "local_count": sum(1 for s in songs if s.get("source") == "local"),
        "online_count": online_count,
        "online_error": online_error,
        "providers": providers,
        "mode": mode,
        "strategy": strat,
        "stages": [
            {"emotion": s["emotion"], "zh": s["zh"], "name": s["name"], "role": s["role"], "role_zh": s["role_zh"], "count": s["count"]}
            for s in stages
        ],
    }


def song_file(song_id: str) -> Optional[tuple[object, str]]:
    for s in load_catalog():
        if s["id"] == song_id:
            name = s.get("file")
            if not name:
                continue
            path = AUDIO_DIR / name
            if path.exists():
                return path, s.get("mime", "audio/wav")
    return None
