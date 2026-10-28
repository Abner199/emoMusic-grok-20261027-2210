# -*- coding: utf-8 -*-
"""
在线曲库默认优先：并行检索苹果音乐、网易云、咪咕、酷狗、QQ、酷我。
本机 30 秒人声试听随时可手动切回；在线长时间播不了会回落到本地。
"""
from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from urllib.parse import quote, urlparse

import requests

from config import AUDIO_DIR, DATA_DIR, EMOTIONS, ONLINE_TIMEOUT, RECOMMEND_COUNT
from backend.music_emotion import (
    ALGO_NAME as MUSIC_ALGO,
    describe_song,
    face_vector,
    match_score,
    public_music,
    target_vector,
)
from backend.songbook import VOCAL_SONGBOOK, fold_zh, is_vocal_song, localize_song, title_key, title_seen
from backend.strategy import DEFAULT_STRATEGY, interleave, involved_emotions, normalize, plan, summary

logger = logging.getLogger("emotune.recommender")

_CATALOG_PATH = DATA_DIR / "catalog.json"
_CACHE: dict[str, tuple[float, list[dict]]] = {}
_CACHE_TTL = 600.0
_EMPTY_CACHE_TTL = 45.0
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
)

SOURCE_LABEL = {
    "itunes": "在线 · 苹果音乐",
    "netease": "在线 · 网易云",
    "migu": "在线 · 咪咕",
    "kugou": "在线 · 酷狗",
    "qq": "在线 · QQ 音乐",
    "kuwo": "在线 · 酷我",
    "deezer": "在线 · 国际曲库",
    "local": "本地曲库",
}


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


def local_songs(emotion: str, limit: int = 48) -> list[dict]:
    catalog = [s for s in load_catalog() if s.get("source") == "local"]
    matched = [s for s in catalog if s.get("emotion") == emotion]
    vocals = [s for s in matched if s.get("kind") == "vocal"]
    others = [s for s in matched if s.get("kind") != "vocal"]
    songs = vocals + others
    if not songs:
        songs = list(catalog)
    return songs[:limit]


def _get_json(url: str, timeout: float, headers: Optional[dict] = None, params: Optional[dict] = None) -> Optional[dict]:
    if timeout <= 0.2:
        return None
    try:
        r = _SESSION.get(url, timeout=timeout, headers=headers, params=params)
        if r.status_code != 200:
            return None
        try:
            return r.json()
        except Exception:
            text = (r.text or "").strip()
            if text.startswith("http"):
                return {"url": text.split()[0]}
            text = text.replace("'", '"')
            return json.loads(text)
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
    for q in meta["search"][:1]:
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
            if not is_vocal_song(title, artist):
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


def _itunes_item(emotion: str, item: dict) -> Optional[dict]:
    meta = EMOTIONS[emotion]
    tid = item.get("trackId")
    title = (item.get("trackName") or "").strip()
    preview = item.get("previewUrl") or ""
    if not tid or not title:
        return None
    artist_name = item.get("artistName") or "未知艺术家"
    genre = item.get("primaryGenreName") or ""
    if not is_vocal_song(title, artist_name, genre):
        return None
    blob = fold_zh(f"{title} {artist_name}")
    if "karaoke" in blob or "伴奏" in title or "live" in blob:
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
    seen = set()
    deadline = time.time() + timeout
    queries = _song_queries(emotion)[:10]
    ascii_q = [q for q in queries if any(ch.isascii() and ch.isalpha() for ch in q)]
    jobs = [(q, "HK") for q in queries[:4]] + [(q, "TW") for q in queries[:2]] + [(q, "US") for q in ascii_q[:1]]

    def fetch(pair):
        q, country = pair
        wait = _remain(deadline)
        if wait < 0.35:
            return []
        url = (
            "https://itunes.apple.com/search"
            f"?term={quote(q)}&media=music&entity=song&limit=8&country={country}"
        )
        data = _get_json(url, wait)
        return (data or {}).get("results") or []

    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for found in pool.map(fetch, jobs):
            rows.extend(found)

    for item in rows:
        parsed = _itunes_item(emotion, item)
        if not parsed or parsed["id"] in seen:
            continue
        seen.add(parsed["id"])
        songs.append(parsed)
        if len(songs) >= 12:
            break
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
            r = _SESSION.get(
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
            tid = item.get("id")
            title = (item.get("name") or "").strip()
            if not tid or not title or tid in seen:
                continue
            artists = item.get("artists") or []
            artist = " / ".join(a.get("name") or "" for a in artists if a.get("name")) or "未知艺术家"
            if not is_vocal_song(title, artist):
                continue
            seen.add(tid)
            album = (item.get("album") or {}).get("name") or ""
            raw_items.append(
                {
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
                    "duration": float(item.get("duration") or 0) / 1000.0,
                    "playable": False,
                    "downloadable": False,
                }
            )
        if len(raw_items) >= 8:
            break
    if raw_items:
        ids = [int(s["nid"]) for s in raw_items[:12]]
        try:
            det = _SESSION.get(
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
            pr = _SESSION.get(
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
        for s in raw_items:
            s.pop("nid", None)
            if s.get("playable"):
                songs.append(s)
    return songs


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
    for q in _song_queries(emotion)[:4]:
        wait = _remain(deadline)
        if wait < 0.35:
            break
        url = (
            "https://m.music.migu.cn/migu/remoting/scr_search_tag"
            f"?rows=8&type=2&keyword={quote(q)}&pgc=1"
        )
        data = _get_json(url, wait, headers=headers)
        if not data:
            continue
        for item in data.get("songs") or data.get("musics") or []:
            tid = item.get("copyrightId") or item.get("id") or item.get("songId")
            title = (item.get("songName") or item.get("title") or "").strip()
            artist = (item.get("singerName") or item.get("artist") or "未知艺术家").strip()
            preview = item.get("mp3") or item.get("listenUrl") or item.get("hqUrl") or ""
            if not tid or not title or tid in seen:
                continue
            if not is_vocal_song(title, artist):
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
        data = _get_json(url, wait)
        for item in ((data or {}).get("data") or {}).get("info") or []:
            tid = item.get("hash") or item.get("audio_id")
            title = (item.get("songname") or item.get("filename") or "").strip()
            artist = (item.get("singername") or "未知艺术家").strip()
            if not tid or not title or tid in seen:
                continue
            if not is_vocal_song(title, artist):
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
        data = _get_json(url, wait, headers=headers)
        for item in (((data or {}).get("data") or {}).get("song") or {}).get("list") or []:
            mid = item.get("songmid")
            title = (item.get("songname") or "").strip()
            if not mid or not title or mid in seen:
                continue
            singers = item.get("singer") or []
            artist = " / ".join(s.get("name") or "" for s in singers if s.get("name")) or "未知艺术家"
            if not is_vocal_song(title, artist):
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
            r = _SESSION.get(
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
        data = _get_json(url, wait)
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
            if not is_vocal_song(title, artist):
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
        data = _get_json(play, wait)
        url = ""
        if isinstance(data, dict):
            url = data.get("url") or ""
        if url:
            song["preview"] = url
            song["audio"] = url
            song["playable"] = True
        return song

    with ThreadPoolExecutor(max_workers=4) as pool:
        cooked = list(pool.map(play_one, raw[:8]))
    return [s for s in cooked if s.get("playable")]


def online_songs(emotion: str, timeout: float = ONLINE_TIMEOUT) -> list[dict]:
    now = time.time()
    cached = _CACHE.get(emotion)
    if cached:
        ttl = _CACHE_TTL if cached[1] else _EMPTY_CACHE_TTL
        if now - cached[0] < ttl:
            return cached[1]

    each = max(1.6, timeout)
    buckets: dict[str, list[dict]] = {
        "itunes": [],
        "qq": [],
        "kugou": [],
        "kuwo": [],
        "netease": [],
        "migu": [],
    }
    jobs = {
        "itunes": _from_itunes,
        "qq": _from_qq,
        "kugou": _from_kugou,
        "kuwo": _from_kuwo,
        "netease": _from_netease,
        "migu": _from_migu,
    }
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {name: pool.submit(fn, emotion, each) for name, fn in jobs.items()}
        for name, fut in futures.items():
            try:
                buckets[name] = fut.result(timeout=each + 0.5) or []
            except Exception:
                buckets[name] = []

    merged: list[dict] = []
    titles = set()
    for item in buckets["itunes"] + buckets["qq"] + buckets["kugou"] + buckets["kuwo"] + buckets["netease"] + buckets["migu"]:
        if not is_vocal_song(item.get("title") or "", item.get("artist") or "", item.get("genre") or ""):
            continue
        if not (item.get("audio") or item.get("preview")):
            continue
        key = title_key(item.get("title") or "")
        if title_seen(key, titles):
            continue
        if item.get("source") != "itunes" and len(key) < 3:
            continue
        titles.add(key)
        merged.append(attach_stream(item))
    result = [localize_song(s) for s in merged[:16]]
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
        scored.append((match, item))
    scored.sort(key=lambda x: -x[0])
    return [item for _, item in scored]


def _pool_songs(emotions: list[str], want_online: bool, limit: int) -> tuple[dict[str, list[dict]], dict[str, list[dict]], Optional[str]]:
    local_map: dict[str, list[dict]] = {eid: local_songs(eid, limit=limit) for eid in emotions}
    online_map: dict[str, list[dict]] = {eid: [] for eid in emotions}
    online_error = None
    if not want_online:
        return local_map, online_map, None
    with ThreadPoolExecutor(max_workers=min(6, max(1, len(emotions)))) as pool:
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
        from backend.history import played_keys

        for eid in EMOTIONS:
            skip_src.extend(played_keys(eid))
    except Exception:
        pass
    skip = _exclude_keys(skip_src)
    skip_at = {key: idx for idx, key in enumerate(skip)}
    face_vec = face_vector(face_scores, emotion)

    local_map, online_map, online_error = _pool_songs(emos, want_online, limit=max(count, 48))

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
            take(online_fresh)
            take(local_fresh)
            take(online_used)
            take(local_used)
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
