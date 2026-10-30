# -*- coding: utf-8 -*-
"""首次启动：下载 ONNX 模型、缓存有人声歌曲试听、写出 catalog.json。"""
from __future__ import annotations

import json
import logging
import math
import re
import time
from pathlib import Path

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from urllib.parse import quote

from config import AUDIO_DIR, COVER_DIR, DATA_DIR, EMOTIONS, FER_FILE, HSE_FILE, MODEL_DIR, MODEL_URLS, YUNET_FILE
from backend.songbook import VOCAL_SONGBOOK, fold_zh, is_instrumental, is_stock_track, pretty_text

logger = logging.getLogger("emotune.assets")

SR = 22050
DURATION = 14.0

# 至少 21 首，覆盖 7 类情绪
SONG_SPECS = [
    # 喜
    dict(id="local-happy-01", emotion="happy", title="日光漫过窗台", artist="心弦室内乐团", album="晴色速写",
         tempo=126, root=60, scale="major", mood="bright", seed=11),
    dict(id="local-happy-02", emotion="happy", title="柠檬汽水", artist="北岛电台", album="夏日短波",
         tempo=118, root=67, scale="major", mood="bright", seed=23),
    dict(id="local-happy-03", emotion="happy", title="步道开花", artist="城市漫步者", album="周末计划",
         tempo=132, root=62, scale="pent_major", mood="bright", seed=37),
    # 怒
    dict(id="local-angry-01", emotion="angry", title="未竟的辩论", artist="红砖墙", album="高压线",
         tempo=138, root=52, scale="minor", mood="drive", seed=41),
    dict(id="local-angry-02", emotion="angry", title="断裂的节拍", artist="锈蚀引擎", album="火花",
         tempo=148, root=50, scale="pent_minor", mood="drive", seed=53),
    dict(id="local-angry-03", emotion="angry", title="逆流", artist="夜航灯塔", album="对峙",
         tempo=142, root=55, scale="minor", mood="drive", seed=59),
    # 哀
    dict(id="local-sad-01", emotion="sad", title="雨停以前", artist="晚风邮局", album="未寄出的信",
         tempo=68, root=57, scale="minor", mood="soft", seed=61),
    dict(id="local-sad-02", emotion="sad", title="旧围巾", artist="南巷钢琴", album="冬天的房间",
         tempo=72, root=53, scale="harm_minor", mood="soft", seed=67),
    dict(id="local-sad-03", emotion="sad", title="河对岸", artist="青石民谣", album="独自回家",
         tempo=64, root=50, scale="minor", mood="soft", seed=71),
    # 惧
    dict(id="local-fear-01", emotion="fear", title="走廊尽头", artist="低能见度", album="夜班",
         tempo=88, root=54, scale="phrygian", mood="dark", seed=73),
    dict(id="local-fear-02", emotion="fear", title="未命名房间", artist="暗房", album="第三班地铁",
         tempo=80, root=49, scale="locrian", mood="dark", seed=79),
    dict(id="local-fear-03", emotion="fear", title="影子练习", artist="薄雾乐团", album="闭眼倒数",
         tempo=92, root=56, scale="harm_minor", mood="dark", seed=83),
    # 惊
    dict(id="local-surprise-01", emotion="surprise", title="突然的烟花", artist="快门", album="未计划的旅行",
         tempo=122, root=64, scale="major", mood="spark", seed=89),
    dict(id="local-surprise-02", emotion="surprise", title="跳进彩池", artist="电子汽水", album="意外章节",
         tempo=128, root=69, scale="pent_major", mood="spark", seed=97),
    dict(id="local-surprise-03", emotion="surprise", title="门后是海", artist="闪光灯", album="第一次",
         tempo=116, root=65, scale="lydian", mood="spark", seed=101),
    # 厌
    dict(id="local-disgust-01", emotion="disgust", title="金属味的早晨", artist="疏离社", album="过期展览",
         tempo=98, root=51, scale="phrygian", mood="grit", seed=103),
    dict(id="local-disgust-02", emotion="disgust", title="塑料花", artist="冷感", album="橱窗",
         tempo=104, root=58, scale="locrian", mood="grit", seed=107),
    dict(id="local-disgust-03", emotion="disgust", title="反光的鱼", artist="灰阶", album="不合适的场合",
         tempo=90, root=46, scale="minor", mood="grit", seed=109),
    # 中性
    dict(id="local-neutral-01", emotion="neutral", title="午后频谱", artist="白噪音咖啡馆", album="工作日",
         tempo=96, root=60, scale="major", mood="calm", seed=113),
    dict(id="local-neutral-02", emotion="neutral", title="水平线", artist="平衡木", album="室温",
         tempo=88, root=55, scale="dorian", mood="calm", seed=127),
    dict(id="local-neutral-03", emotion="neutral", title="未命名笔记", artist="灰蓝小时", album="间隙",
         tempo=100, root=62, scale="pent_major", mood="calm", seed=131),
]

SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "harm_minor": [0, 2, 3, 5, 7, 8, 11],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11],
    "locrian": [0, 1, 3, 5, 6, 8, 10],
    "pent_major": [0, 2, 4, 7, 9],
    "pent_minor": [0, 3, 5, 7, 10],
}

PROGRESSIONS = {
    "bright": [(0, "maj"), (4, "maj"), (5, "min"), (3, "maj")],
    "drive": [(0, "pow"), (0, "pow"), (5, "pow"), (6, "pow")],
    "soft": [(0, "min"), (5, "maj"), (2, "maj"), (6, "maj")],
    "dark": [(0, "min"), (1, "dim"), (5, "maj"), (0, "min")],
    "spark": [(0, "maj"), (3, "maj"), (4, "maj"), (0, "maj")],
    "grit": [(0, "min"), (6, "maj"), (5, "maj"), (0, "min")],
    "calm": [(0, "maj"), (4, "maj"), (5, "min"), (3, "maj")],
}


def _hz(midi: float) -> float:
    return 440.0 * (2.0 ** ((midi - 69.0) / 12.0))


def _env(n: int, sr: int, a=0.02, d=0.08, s=0.7, r=0.18) -> np.ndarray:
    env = np.ones(n, dtype=np.float32)
    na = max(1, int(a * sr))
    nd = max(1, int(d * sr))
    nr = max(1, int(r * sr))
    if na + nd + nr >= n:
        nr = max(1, n // 4)
        na = max(1, n // 8)
        nd = max(1, n // 8)
    ns = n - na - nd - nr
    env[:na] = np.linspace(0.0, 1.0, na, dtype=np.float32)
    env[na:na + nd] = np.linspace(1.0, s, nd, dtype=np.float32)
    env[na + nd:na + nd + ns] = s
    env[-nr:] = np.linspace(env[-nr] if ns else s, 0.0, nr, dtype=np.float32)
    return env


def _osc(freq: float, n: int, sr: int, kind: str, phase: float = 0.0) -> np.ndarray:
    t = np.arange(n, dtype=np.float32) / sr
    ph = (2.0 * math.pi * freq) * t + phase
    if kind == "triangle":
        return (2.0 / math.pi) * np.arcsin(np.clip(np.sin(ph), -1.0, 1.0))
    if kind == "square":
        return np.sign(np.sin(ph)).astype(np.float32) * 0.7
    if kind == "saw":
        return (2.0 * ((t * freq) % 1.0) - 1.0).astype(np.float32) * 0.6
    return np.sin(ph).astype(np.float32)


def _lowpass(x: np.ndarray, alpha: float = 0.18) -> np.ndarray:
    y = np.zeros_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc = acc + alpha * (float(v) - acc)
        y[i] = acc
    return y


def _place(buf: np.ndarray, start: int, wave: np.ndarray) -> None:
    if start >= len(buf):
        return
    end = min(len(buf), start + len(wave))
    buf[start:end] += wave[: end - start]


def _render_song(spec: dict) -> np.ndarray:
    rng = np.random.default_rng(spec["seed"])
    sr = SR
    n = int(DURATION * sr)
    tempo = spec["tempo"]
    beat = 60.0 / tempo
    bar = beat * 4.0
    scale = SCALES[spec["scale"]]
    root = spec["root"]
    prog = PROGRESSIONS[spec["mood"]]
    mood = spec["mood"]

    mix = np.zeros(n, dtype=np.float32)
    bass = np.zeros(n, dtype=np.float32)
    drums = np.zeros(n, dtype=np.float32)

    lead_kind = {
        "bright": "triangle",
        "drive": "saw",
        "soft": "sine",
        "dark": "sine",
        "spark": "square",
        "grit": "saw",
        "calm": "sine",
    }[mood]
    chord_kind = "triangle" if mood in ("bright", "spark", "calm") else "sine"

    bars = int(DURATION / bar)
    for b in range(max(1, bars)):
        deg, qual = prog[b % len(prog)]
        chord_root = root + (scale[deg % len(scale)] if deg < len(scale) else deg)
        if qual == "maj":
            chord = [chord_root, chord_root + 4, chord_root + 7]
        elif qual == "min":
            chord = [chord_root, chord_root + 3, chord_root + 7]
        elif qual == "dim":
            chord = [chord_root, chord_root + 3, chord_root + 6]
        else:
            chord = [chord_root, chord_root + 7]

        start = int(b * bar * sr)
        length = int(bar * sr)
        length = min(length, n - start)
        if length <= 0:
            break

        # 和弦 pad
        pad = np.zeros(length, dtype=np.float32)
        for m in chord:
            pad += _osc(_hz(m - 12), length, sr, chord_kind, phase=float(rng.random() * 0.4))
            pad += 0.35 * _osc(_hz(m), length, sr, "sine")
        pad /= max(1.0, len(chord))
        pad *= _env(length, sr, a=0.04, d=0.12, s=0.55, r=0.25) * (0.22 if mood != "drive" else 0.16)
        _place(mix, start, pad)

        # 贝斯：根音四分音符
        bass_len = int(beat * sr)
        for q in range(4):
            bs = start + int(q * beat * sr)
            note = chord_root - 24 if q % 2 == 0 else chord_root - 12
            bw = _osc(_hz(note), bass_len, sr, "sine" if mood in ("soft", "calm") else "triangle")
            bw *= _env(bass_len, sr, a=0.01, d=0.08, s=0.5, r=0.12) * 0.42
            _place(bass, bs, bw)

        # 旋律
        steps = 8 if mood in ("bright", "spark", "drive") else 4
        step = bar / steps
        for sidx in range(steps):
            if mood == "soft" and sidx % 2 == 1:
                continue
            if mood == "dark" and rng.random() < 0.35:
                continue
            degree = int(rng.integers(0, len(scale)))
            octv = 12 if rng.random() < 0.7 else 24
            midi = root + scale[degree] + octv
            slen = int(step * sr * (1.6 if mood in ("soft", "calm") else 0.9))
            slen = max(int(0.08 * sr), slen)
            sw = _osc(_hz(midi), slen, sr, lead_kind)
            if mood in ("bright", "spark"):
                sw += 0.25 * _osc(_hz(midi + 12), slen, sr, "sine")
            sw *= _env(slen, sr, a=0.01, d=0.06, s=0.6, r=0.15) * (0.28 if mood != "drive" else 0.22)
            _place(mix, start + int(sidx * step * sr), sw)

        # 鼓
        kick_n = int(0.22 * sr)
        snare_n = int(0.18 * sr)
        hat_n = int(0.06 * sr)
        t = np.arange(kick_n, dtype=np.float32) / sr
        kick = np.sin(2 * math.pi * (110 * np.exp(-t * 18)) * t) * np.exp(-t * 9)
        snare = (
            0.45 * np.sin(2 * math.pi * 180 * np.arange(snare_n) / sr) * np.exp(-np.arange(snare_n) / sr * 14)
            + 0.55 * rng.standard_normal(snare_n).astype(np.float32) * np.exp(-np.arange(snare_n) / sr * 18)
        )
        hat = rng.standard_normal(hat_n).astype(np.float32) * np.exp(-np.arange(hat_n) / sr * 50)

        drum_gain = {"bright": 0.55, "drive": 0.8, "soft": 0.22, "dark": 0.3, "spark": 0.6, "grit": 0.5, "calm": 0.18}[mood]
        for q in range(4):
            _place(drums, start + int(q * beat * sr), kick * drum_gain)
            if mood in ("bright", "drive", "spark", "grit") or q in (1, 3):
                if q in (1, 3):
                    _place(drums, start + int(q * beat * sr), snare * drum_gain * 0.7)
            _place(drums, start + int((q + 0.5) * beat * sr), hat * drum_gain * 0.35)
            if mood == "drive":
                _place(drums, start + int((q + 0.25) * beat * sr), hat * drum_gain * 0.25)

    mix = mix + bass + drums
    # 淡入淡出 + 轻混响（短延迟）
    fade = int(0.25 * sr)
    mix[:fade] *= np.linspace(0, 1, fade)
    mix[-fade:] *= np.linspace(1, 0, fade)
    delay = int(0.18 * sr)
    echo = np.zeros_like(mix)
    echo[delay:] = mix[:-delay] * 0.22
    mix = mix + echo
    mix = np.tanh(mix * 1.15).astype(np.float32)
    peak = float(np.max(np.abs(mix)) + 1e-6)
    mix = mix / peak * 0.9

    # 轻微立体声
    right = np.zeros_like(mix)
    d = int(0.012 * sr)
    right[d:] = mix[:-d] * 0.92
    stereo = np.stack([mix, right], axis=1)
    return stereo


def _write_wav(path: Path, stereo: np.ndarray, sr: int = SR) -> float:
    from scipy.io import wavfile

    pcm = np.clip(stereo, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype(np.int16)
    wavfile.write(str(path), sr, pcm)
    return float(len(pcm) / sr)


def _font(size: int) -> ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size=size)
            except Exception:
                continue
    return ImageFont.load_default()


def _hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def render_cover(spec: dict, path: Path) -> None:
    meta = EMOTIONS[spec["emotion"]]
    c1 = _hex_rgb(meta["color"])
    c2 = _hex_rgb(meta["color2"])
    bg = _hex_rgb(meta["bg"])
    w = h = 640
    img = Image.new("RGB", (w, h), bg)
    px = img.load()
    for y in range(h):
        t = y / (h - 1)
        r = int(bg[0] * (1 - t) + c2[0] * t * 0.55)
        g = int(bg[1] * (1 - t) + c2[1] * t * 0.55)
        b = int(bg[2] * (1 - t) + c1[2] * t * 0.35)
        for x in range(w):
            k = 0.08 * math.sin((x + y) * 0.02 + spec["seed"])
            px[x, y] = (
                max(0, min(255, int(r * (1 + k)))),
                max(0, min(255, int(g * (1 + k)))),
                max(0, min(255, int(b * (1 + k)))),
            )
    draw = ImageDraw.Draw(img, "RGBA")
    mood = spec["mood"]
    cx, cy = w // 2, int(h * 0.42)
    if mood == "bright":
        draw.ellipse((cx - 120, cy - 120, cx + 120, cy + 120), fill=(*c1, 220))
        for i in range(12):
            ang = i / 12 * math.pi * 2
            x2 = cx + math.cos(ang) * 210
            y2 = cy + math.sin(ang) * 210
            draw.line((cx, cy, x2, y2), fill=(*c1, 90), width=6)
    elif mood == "drive":
        for i in range(7):
            x0 = 80 + i * 70
            draw.polygon([(x0, 480), (x0 + 40, 140 + (i % 3) * 30), (x0 + 80, 480)], fill=(*c1, 160))
    elif mood == "soft":
        for i, rad in enumerate((220, 160, 100)):
            draw.ellipse((cx - rad, cy - rad + i * 20, cx + rad, cy + rad + i * 20), outline=(*c1, 140), width=4)
    elif mood == "dark":
        draw.rectangle((0, 0, w, h), fill=(*bg, 40))
        for i in range(9):
            x0 = 70 + i * 60
            draw.line((x0, 80, x0 + 20, 520), fill=(*c1, 70), width=10)
    elif mood == "spark":
        for i in range(18):
            ang = i / 18 * math.pi * 2
            rad = 40 + (i % 5) * 28
            x = cx + math.cos(ang) * 160
            y = cy + math.sin(ang) * 160
            draw.ellipse((x - rad / 6, y - rad / 6, x + rad / 6, y + rad / 6), fill=(*c1, 200))
        draw.ellipse((cx - 70, cy - 70, cx + 70, cy + 70), fill=(*c2, 220))
    elif mood == "grit":
        rng = np.random.default_rng(spec["seed"])
        for _ in range(14):
            x0 = int(rng.integers(40, 500))
            y0 = int(rng.integers(60, 420))
            rw = int(rng.integers(60, 180))
            rh = int(rng.integers(40, 140))
            draw.rounded_rectangle((x0, y0, x0 + rw, y0 + rh), radius=8, outline=(*c1, 140), width=3)
    else:
        for i in range(8):
            y0 = 120 + i * 48
            draw.rectangle((80, y0, 560, y0 + 16), fill=(*c1, 70 + i * 8))

    img = img.filter(ImageFilter.GaussianBlur(radius=0.4))
    draw = ImageDraw.Draw(img)
    title_font = _font(42)
    sub_font = _font(22)
    zh_font = _font(28)
    title = spec["title"]
    # 底部文字带
    draw.rectangle((0, 500, w, h), fill=(8, 8, 10, 255))
    draw.text((36, 512), title, font=title_font, fill=(250, 244, 230, 255))
    draw.text((36, 568), f"{spec['artist']}  ·  {spec['album']}", font=sub_font, fill=(210, 200, 180, 255))
    draw.text((w - 90, 36), meta["zh"], font=zh_font, fill=(*c1, 255))
    img.save(path, "JPEG", quality=86)


def _download_file(urls: list[str], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_err = None
    headers = {"User-Agent": "EmoTune/1.0"}
    for url in urls:
        try:
            logger.info("下载 %s", url)
            with requests.get(url, stream=True, timeout=90, allow_redirects=True, headers=headers) as r:
                r.raise_for_status()
                tmp = dest.with_suffix(dest.suffix + ".part")
                size = 0
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 16):
                        if chunk:
                            f.write(chunk)
                            size += len(chunk)
                if size < 50_000:
                    tmp.unlink(missing_ok=True)
                    last_err = RuntimeError(f"文件过小: {size} bytes from {url}")
                    continue
                tmp.replace(dest)
                logger.info("已保存 %s (%s bytes)", dest.name, size)
                return
        except Exception as exc:
            last_err = exc
            logger.warning("下载失败 %s: %s", url, exc)
    raise RuntimeError(f"无法下载 {dest.name}: {last_err}")


def ensure_models() -> None:
    mapping = {
        YUNET_FILE: MODEL_URLS[YUNET_FILE],
        FER_FILE: MODEL_URLS[FER_FILE],
        HSE_FILE: MODEL_URLS[HSE_FILE],
    }
    for name, urls in mapping.items():
        path = MODEL_DIR / name
        if path.exists() and path.stat().st_size > 50_000:
            continue
        _download_file(urls, path)


_SKIP_ARTISTS = ("kidz bop", "kids bop", "karaoke", "tribute", "piano guys")
_TITLE_NOISE = re.compile(r"[\s,，.。·\-–—_/\\'\"()（）【】\[\]《》〈〉「」『』]+")
_ITUNES_UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}
_ITUNES_SEARCH_BLOCKED = False
_ITUNES_LEGACY_BLOCKED = False
_LOOKUP_PING_ID = "1721456393"
_ARTIST_ID_BY_NAME: dict[str, int] = {}
_ARTIST_SONGS: dict[tuple[int, str], list[dict]] = {}
_CATALOG_TRACK_BY_ARTIST: dict[str, str] = {}
_KNOWN_ARTIST_IDS = {
    "汪苏泷": 657686835,
    "陈慧娴": 42059214,
    "林忆莲": 14862436,
    "dua lipa": 1031397873,
    "the weeknd": 479756766,
    "alanis morissette": 1092859,
    "bruno mars": 278873078,
    "伍佰": 382356207,
    "小潘潘": 1388787667,
    "李昕融": 1634562710,
    "金玟岐": 937130745,
    "王蓉": 1477623093,
    "朴树": 539598007,
    "周杰伦": 300117743,
    "林俊杰": 216635866,
    "王力宏": 117741179,
    "罗志祥": 448253585,
    "maroon 5": 1798556,
    "harry styles": 471260289,
    "ed sheeran": 183313439,
    "赵雷": 937112027,
    "陈粒": 1138469250,
    "五月天": 369211611,
    "beyond": 79668659,
    "崔健": 388335540,
    "linkin park": 148662,
    "michael jackson": 32940,
    "evanescence": 42102393,
    "薛之谦": 160809474,
    "avril lavigne": 459885,
    "张惠妹": 422255649,
    "王菲": 41760704,
    "陈奕迅": 137938148,
    "蔡依林": 152678183,
    "g.e.m. 邓紫棋": 425208570,
    "邓紫棋": 425208570,
    "taylor swift": 159260351,
    "lady gaga": 277293880,
    "bts": 883131348,
    "olivia rodrigo": 979458609,
    "米津玄师": 530814268,
    "yoasobi": 1490256993,
    "ado": 1492604670,
    "周深": 1154054707,
    "华晨宇": 919255386,
    "孙燕姿": 83405200,
    "梁静茹": 531134701,
    "陶喆": 16789930,
    "林宥嘉": 436847316,
    "凤凰传奇": 478745331,
    "张国荣": 41759136,
    "李荣浩": 307674970,
    "汪峰": 166694332,
    "s.h.e": 104129527,
}
_KNOWN_TRACK_IDS = {
    ("学猫叫", "小潘潘"): 1606689096,
    ("你笑起来真好看", "李昕融"): 1652261980,
    ("平凡之路", "朴树"): 1438422297,
    ("那些花儿", "朴树"): 1156006784,
    ("小鸡小鸡", "王蓉"): 951800449,
    ("麦芽糖", "周杰伦"): 1721453716,
    ("Easy On Me", "Adele"): 1590036021,
    ("月牙湾", "飞儿乐团"): 278677307,
    ("异类", "华晨宇"): 1634556073,
    ("害怕", "林俊杰"): 1889764433,
    ("大城小爱", "王力宏"): 1134353955,
    ("美人鱼", "林俊杰"): 1071753633,
    ("豆浆油条", "林俊杰"): 1071753627,
    ("爱笑的眼睛", "林俊杰"): 1071506930,
    ("Sugar", "Maroon 5"): 1422652341,
    ("恋爱达人", "罗志祥"): 806123515,
    ("因你而在", "林俊杰"): 1694849135,
    ("关键词", "林俊杰"): 1871400641,
    ("Somewhere I Belong", "LINKIN PARK"): 528437020,
    ("New Divide", "LINKIN PARK"): 318875933,
    ("From The Inside", "LINKIN PARK"): 528437027,
    ("真的爱你", "Beyond"): 1440803983,
    ("光辉岁月", "Beyond"): 1440803589,
    ("Lost in the Echo", "LINKIN PARK"): 518869935,
    ("Burn It Down", "LINKIN PARK"): 518869937,
    ("Castle of Glass", "LINKIN PARK"): 518869940,
    ("让我留在你身边", "陈奕迅"): 1445291088,
    ("如愿", "王菲"): 1591180619,
    ("倒带", "蔡依林"): 556949926,
    ("倒数", "G.E.M. 邓紫棋"): 1422581998,
    ("多远都要在一起", "G.E.M. 邓紫棋"): 968754055,
    ("未给姐姐递出的信", "赵雷"): 1722413128,
    ("无法长大", "赵雷"): 1722409915,
    ("Payphone", "Maroon 5"): 1440808312,
    ("Beat It", "Michael Jackson"): 273598915,
    ("Dangerous", "Michael Jackson"): 322847216,
    ("Everybody's Fool", "Evanescence"): 1440666118,
    ("人质", "张惠妹"): 201549866,
    ("Tourniquet", "Evanescence"): 1440666296,
    ("Whisper", "Evanescence"): 1440666491,
    ("They Don't Care About Us", "Michael Jackson"): 336644173,
    ("Call Me When You're Sober", "Evanescence"): 1440634107,
    ("最伟大的作品", "周杰伦"): 1721454344,
    ("跨时代", "周杰伦"): 1721449918,
    ("超人不会飞", "周杰伦"): 1721450126,
    ("派对动物", "五月天"): 1158763998,
    ("As It Was", "Harry Styles"): 1615585008,
    ("Watermelon Sugar", "Harry Styles"): 1485802967,
    ("爱的飞行日记", "周杰伦"): 1721450122,
    ("Adore You", "Harry Styles"): 1485802970,
    ("摩天大楼", "薛之谦"): 1787448186,
    ("骆驼", "薛之谦"): 1787509723,
    ("Don't Tell Me", "Avril Lavigne"): 533017349,
    ("病态", "薛之谦"): 1787447853,
    ("Uninvited", "Alanis Morissette"): 329935536,
    ("不是我不明白", "崔健"): 1585626294,
    ("天外来物", "薛之谦"): 1787447448,
    ("野心", "薛之谦"): 1787447721,
    ("Shape of You", "Ed Sheeran"): 1193701392,
    ("我记得", "赵雷"): 1722409792,
    ("鼓楼", "赵雷"): 1722409911,
    ("Thinking Out Loud", "Ed Sheeran"): 858518134,
    ("阿刁", "赵雷"): 1722409910,
    ("我们的时光", "赵雷"): 1722411237,
    ("虚拟", "陈粒"): 1421693767,
    ("七楼", "陈粒"): 1413543381,
    ("Butter", "BTS"): 1597016227,
    ("打上花火", "米津玄师"): 1263790415,
    ("Just Dance", "Lady Gaga"): 1440818653,
    ("Love Story", "Taylor Swift"): 1440924808,
    ("22", "Taylor Swift"): 1440935562,
    ("You Belong With Me", "Taylor Swift"): 1440925035,
    ("粉色海洋", "周杰伦"): 1721454757,
    ("我的秘密", "G.E.M. 邓紫棋"): 6775743679,
    ("当你", "林俊杰"): 1071506932,
    ("Born This Way", "Lady Gaga"): 1440857424,
    ("Paper Rings", "Taylor Swift"): 1468058181,
    ("她的睫毛", "周杰伦"): 1721465383,
    ("Bad Blood", "Taylor Swift"): 1440936028,
    ("Look What You Made Me Do", "Taylor Swift"): 1440934255,
    ("Judas", "Lady Gaga"): 1440857433,
    ("...Ready For It?", "Taylor Swift"): 1440934248,
    ("摩天动物园", "G.E.M. 邓紫棋"): 1491477508,
    ("brutal", "Olivia Rodrigo"): 1560735419,
    ("vampire", "Olivia Rodrigo"): 1694386830,
    ("新世界", "华晨宇"): 1634558476,
    ("The Man", "Taylor Swift"): 1468058176,
    ("Vigilante Shit", "Taylor Swift"): 1650841732,
    ("Government Hooker", "Lady Gaga"): 1440857430,
    ("Heavy Metal Lover", "Lady Gaga"): 1440857994,
    ("可惜没如果", "林俊杰"): 1788007696,
    ("我还想她", "林俊杰"): 1071752122,
    ("All Too Well", "Taylor Swift"): 1589139591,
    ("Shallow", "Lady Gaga"): 1434371887,
    ("Million Reasons", "Lady Gaga"): 1440893897,
    ("Always Remember Us This Way", "Lady Gaga"): 1434372043,
    ("一路向北", "周杰伦"): 1721454134,
    ("枫", "周杰伦"): 1721454117,
    ("很久以后", "G.E.M. 邓紫棋"): 1491477512,
    ("Lemon", "米津玄师"): 1538265741,
    ("菊花台", "周杰伦"): 1721454710,
    ("Back to December", "Taylor Swift"): 1440920489,
    ("Bad Romance", "Lady Gaga"): 1444893703,
    ("Bloody Mary", "Lady Gaga"): 1440857734,
    ("夜に駆ける", "YOASOBI"): 1490256995,
    ("黑武士", "林俊杰"): 1071752116,
    ("Alejandro", "Lady Gaga"): 1476095085,
    ("Wildest Dreams", "Taylor Swift"): 1440936036,
    ("Paparazzi", "Lady Gaga"): 1440818663,
    ("新时代", "Ado"): 1636446946,
    ("Monster", "Lady Gaga"): 1476095086,
    ("KICK BACK", "米津玄师"): 1648272180,
    ("Aura", "Lady Gaga"): 1451767864,
    ("John Wayne", "Lady Gaga"): 1440893797,
    ("Poker Face", "Lady Gaga"): 1440818665,
    ("Applause", "Lady Gaga"): 1451767879,
    ("Cruel Summer", "Taylor Swift"): 1468058171,
    ("Blank Space", "Taylor Swift"): 1440935808,
    ("アイドル", "YOASOBI"): 1679278167,
    ("Telephone", "Lady Gaga"): 1440860312,
    ("ME!", "Taylor Swift"): 1468058706,
    ("Rain On Me", "Lady Gaga"): 1500952424,
    ("Permission to Dance", "BTS"): 1598661406,
    ("唱", "Ado"): 1704093812,
    ("编号89757", "林俊杰"): 1072021765,
    ("Stupid Love", "Lady Gaga"): 1500952423,
    ("We Are Never Ever Getting Back Together", "Taylor Swift"): 1440935564,
    ("Anti-Hero", "Taylor Swift"): 1650841515,
    ("I Knew You Were Trouble", "Taylor Swift"): 1440935349,
    ("差不多姑娘", "G.E.M. 邓紫棋"): 1491477666,
    ("爱情废柴", "周杰伦"): 1721456399,
    ("Perfect Illusion", "Lady Gaga"): 1440893894,
    ("你不是真正的快乐", "五月天"): 1081381268,
    ("You Need To Calm Down", "Taylor Swift"): 1468058704,
    ("うっせぇわ", "Ado"): 1535123742,
    ("借口", "周杰伦"): 1721450038,
    ("traitor", "Olivia Rodrigo"): 1560735421,
    ("get him back!", "Olivia Rodrigo"): 1694386841,
    ("蜗牛", "周杰伦"): 1721449331,
    ("手写的从前", "周杰伦"): 1721458221,
    ("Always Online", "林俊杰"): 1071752119,
    ("Lover", "Taylor Swift"): 1468058173,
    ("Style", "Taylor Swift"): 1440935812,
    ("Enchanted", "Taylor Swift"): 1440920614,
    ("大鱼", "周深"): 1320755350,
    ("第二天堂", "林俊杰"): 1071753625,
    ("听爸爸的话", "周杰伦"): 1721458231,
    ("屋顶", "周杰伦"): 1441633014,
    ("交换余生", "林俊杰"): 1531323101,
    ("Die With A Smile", "Lady Gaga"): 1762656732,
    ("爷爷泡的茶", "周杰伦"): 1721459512,
    ("乌克丽丽", "周杰伦"): 1721467267,
    ("傻笑", "周杰伦"): 1721467258,
    ("翅膀", "林俊杰"): 1071516335,
    ("期待爱", "林俊杰"): 1069795778,
    ("绿光", "孙燕姿"): 297994309,
    ("宁夏", "梁静茹"): 558471479,
    ("不想长大", "S.H.E"): 551276783,
    ("进阶", "林俊杰"): 1689369134,
    ("圣所", "林俊杰"): 1314121437,
    ("春天里", "汪峰"): 1353728570,
    ("灰色轨迹", "Beyond"): 1440803866,
    ("大地", "Beyond"): 1440803562,
    ("龙的传人", "王力宏"): 312514021,
    ("改变自己", "王力宏"): 1691044818,
    ("裂心", "王力宏"): 955720727,
    ("说了再见", "周杰伦"): 1721449919,
    ("白色风车", "周杰伦"): 1721454617,
    ("珊瑚海", "周杰伦"): 1721454126,
    ("一点点", "周杰伦"): 1721456256,
    ("手语", "周杰伦"): 1721467023,
    ("后会无期", "G.E.M. 邓紫棋"): 940087113,
    ("于心有愧", "陈奕迅"): 1443774275,
    ("后来的我们", "五月天"): 1158763996,
    ("断了的弦", "周杰伦"): 1721843420,
    ("爱在西元前", "周杰伦"): 1721454235,
    ("天涯过客", "周杰伦"): 1721457643,
    ("上海一九四三", "周杰伦"): 1721454248,
    ("倩女幽魂", "张国荣"): 1443032248,
    ("化身孤岛的鲸", "周深"): 1545553367,
    ("陀飞轮", "陈奕迅"): 1443717750,
    ("如烟", "五月天"): 1081381275,
    ("公主病", "周杰伦"): 1721455015,
    ("达拉崩吧", "周深"): 1548933064,
    ("月亮之上", "凤凰传奇"): 1740937795,
    ("美人计", "蔡依林"): 532965326,
    ("就是爱", "蔡依林"): 556950083,
    ("心跳", "王力宏"): 1448353714,
    ("好想爱这个世界啊", "华晨宇"): 1634558230,
    ("爱无赦", "蔡依林"): 1725226197,
    ("我不配", "周杰伦"): 1721456020,
    ("对不起", "周杰伦"): 1721454250,
    ("一丝不挂", "陈奕迅"): 1443717740,
    ("沙龙", "陈奕迅"): 1443774319,
    ("戒烟", "李荣浩"): 6772908293,
    ("我知道你很难过", "蔡依林"): 540287933,
    ("成全", "林宥嘉"): 1405541253,
    ("怎么了", "S.H.E"): 572453065,
    ("娘子", "周杰伦"): 1721459225,
    ("大笨钟", "周杰伦"): 1721467264,
    ("达尔文", "林俊杰"): 1669406726,
    ("伟大的渺小", "林俊杰"): 1314121438,
    ("岁月如歌", "陈奕迅"): 542910175,
    ("无条件", "陈奕迅"): 1422674971,
    ("天天", "陶喆"): 905206485,
    ("小手拉大手", "梁静茹"): 1095245184,
}


def _plain_title(text: str) -> str:
    return _TITLE_NOISE.sub("", fold_zh(text))


def _track_id_from_url(url: str) -> str:
    found = re.search(r"[?&]i=(\d+)", url or "")
    return found.group(1) if found else ""


def _index_catalog_seeds(previous: dict[str, dict]) -> None:
    _CATALOG_TRACK_BY_ARTIST.clear()
    for row in previous.values():
        art = fold_zh(row.get("artist") or "")
        tid = _track_id_from_url(row.get("external_url") or "")
        if art and tid and art not in _CATALOG_TRACK_BY_ARTIST:
            _CATALOG_TRACK_BY_ARTIST[art] = tid


def _remember_artist(item: dict) -> None:
    aid = item.get("artistId")
    name = fold_zh(item.get("artistName") or "")
    if aid and name:
        _ARTIST_ID_BY_NAME[name] = int(aid)


def _itunes_get_json(url: str, timeout: float, attempts: int = 2) -> dict | None:
    global _ITUNES_SEARCH_BLOCKED, _ITUNES_LEGACY_BLOCKED
    for attempt in range(max(1, attempts)):
        try:
            r = requests.get(url, timeout=timeout, headers=_ITUNES_UA)
            if r.status_code == 403:
                if "/search?" in url or url.rstrip("/").endswith("/search"):
                    _ITUNES_SEARCH_BLOCKED = True
                if "wsSearch" in url:
                    _ITUNES_LEGACY_BLOCKED = True
                return None
            if r.status_code == 200:
                return r.json()
        except Exception as exc:
            if "wsSearch" in url:
                _ITUNES_LEGACY_BLOCKED = True
            logger.warning("iTunes 请求失败 %s (%s/%s): %s", url[:80], attempt + 1, attempts, exc)
            time.sleep(0.35 * (attempt + 1))
    return None


def itunes_lookup_ids(ids: list[str], country: str = "HK", timeout: float = 6.0) -> list[dict]:
    """用苹果曲目编号批量回源，不走 /search，结果带官方 30 秒试听。"""
    found: list[dict] = []
    seen: set[str] = set()
    clean = []
    for raw in ids:
        tid = str(raw or "").strip()
        if tid.isdigit() and tid not in seen:
            seen.add(tid)
            clean.append(tid)
    for i in range(0, len(clean), 20):
        chunk = ",".join(clean[i : i + 20])
        data = _itunes_get_json(
            f"https://itunes.apple.com/lookup?id={chunk}&country={country}",
            max(1.2, timeout),
            attempts=1,
        )
        for row in (data or {}).get("results") or []:
            if row.get("previewUrl") and row.get("trackId"):
                found.append(row)
        if found and i + 20 >= len(clean):
            break
    return found


def itunes_search_results(
    term: str,
    country: str,
    timeout: float = 8.0,
    limit: int = 12,
    attempts: int = 2,
) -> list[dict]:
    """公开检索：`/search` 被拦时改走商店旧接口，结果同样带 30 秒试听。"""
    encoded = quote(term)
    urls: list[str] = []
    if not _ITUNES_SEARCH_BLOCKED:
        urls.append(
            "https://itunes.apple.com/search"
            f"?term={encoded}&media=music&entity=song&limit={limit}&country={country}"
        )
    if not _ITUNES_LEGACY_BLOCKED:
        urls.append(
            "https://itunes.apple.com/WebObjects/MZStoreServices.woa/ws/wsSearch"
            f"?term={encoded}&media=music&entity=song&limit={limit}&country={country}"
        )
    for url in urls:
        data = _itunes_get_json(url, timeout, attempts)
        if data and data.get("results"):
            return data.get("results") or []
    return []


def _itunes_reachable(timeout: float = 4.0) -> bool:
    data = _itunes_get_json(
        f"https://itunes.apple.com/lookup?id={_LOOKUP_PING_ID}&country=HK",
        timeout,
        attempts=1,
    )
    if data and (data.get("resultCount") or 0) > 0:
        return True
    return bool(itunes_search_results("test", "HK", timeout=timeout, limit=1, attempts=1))


def _score_itunes_item(item: dict, title: str, artist: str) -> int:
    track = item.get("trackName") or ""
    who = item.get("artistName") or ""
    genre = item.get("primaryGenreName") or ""
    if not item.get("previewUrl"):
        return -1
    if is_instrumental(track, who, genre) or is_stock_track(track, who):
        return -1
    blob = fold_zh(f"{track} {who} {genre}")
    if any(skip in blob for skip in _SKIP_ARTISTS):
        return -1
    if "karaoke" in blob or "伴奏" in track:
        return -1
    title_f = _plain_title(title)
    track_f = _plain_title(track)
    if not title_f or not (title_f in track_f or track_f in title_f):
        return -1
    score = 6
    who_f = fold_zh(who)
    who_p = _plain_title(who)
    artist_f = fold_zh(artist)
    artist_p = _plain_title(artist)
    artist_tokens = [t for t in artist_p.replace("/", " ").split() if len(t) >= 2]
    if artist_p and (
        artist_p in who_p
        or who_p in artist_p
        or artist_f in who_f
        or who_f in artist_f
        or any(t in who_p or t in who_f for t in artist_tokens)
    ):
        score += 8
    if who_p == artist_p or who_f == artist_f:
        score += 2
    if "live" in track_f or "现场" in track or "acoustic" in track_f:
        score -= 6
    if "remix" in track_f or "重生版" in track:
        score -= 4
    if "纯享" in track or "合唱" in track:
        score -= 2
    if track_f != title_f:
        score -= 1
    return score


def _name_hit(left: str, right: str) -> bool:
    a = _plain_title(left)
    b = _plain_title(right)
    if not a or not b:
        return False
    return a == b or a in b or b in a


def _artist_id_for(artist: str, timeout: float) -> int | None:
    artist_f = fold_zh(artist)
    artist_p = _plain_title(artist)
    for name, aid in _KNOWN_ARTIST_IDS.items():
        if _name_hit(artist, name):
            _ARTIST_ID_BY_NAME[fold_zh(name)] = int(aid)
            return int(aid)
    for name, aid in _ARTIST_ID_BY_NAME.items():
        if _name_hit(artist, name) or (artist_f and (artist_f in name or name in artist_f)):
            return aid
    tid = ""
    for name, track_id in _CATALOG_TRACK_BY_ARTIST.items():
        if _name_hit(artist, name) or (artist_p and artist_p in _plain_title(name)):
            tid = track_id
            break
    if not tid:
        return None
    data = _itunes_get_json(f"https://itunes.apple.com/lookup?id={tid}&country=HK", timeout, attempts=1)
    item = ((data or {}).get("results") or [None])[0]
    if not item:
        return None
    _remember_artist(item)
    aid = item.get("artistId")
    return int(aid) if aid else None


def _itunes_lookup_id(itunes_id: int | str, timeout: float, countries: tuple[str, ...] = ("HK", "TW", "US")) -> list[dict]:
    rows: list[dict] = []
    seen: set[int] = set()
    for country in countries:
        data = _itunes_get_json(
            f"https://itunes.apple.com/lookup?id={itunes_id}&entity=song&limit=50&country={country}",
            timeout,
            attempts=1,
        )
        for item in (data or {}).get("results") or []:
            tid = item.get("trackId")
            if not item.get("previewUrl") or not item.get("trackName") or not tid or tid in seen:
                continue
            seen.add(tid)
            rows.append(item)
            _remember_artist(item)
        if rows:
            break
        time.sleep(0.2)
    return rows


def _itunes_lookup_via_albums(
    title: str,
    artist: str,
    artist_id: int,
    countries: tuple[str, ...],
    timeout: float,
    limit_albums: int = 8,
) -> dict | None:
    best = None
    best_score = -99
    seen_albums: set[int] = set()
    for country in countries:
        data = _itunes_get_json(
            f"https://itunes.apple.com/lookup?id={artist_id}&entity=album&limit=200&country={country}",
            timeout,
            attempts=1,
        )
        albums = [row for row in (data or {}).get("results") or [] if row.get("collectionId")]
        scanned = 0
        for album in albums:
            cid = int(album.get("collectionId"))
            if cid in seen_albums:
                continue
            seen_albums.add(cid)
            scanned += 1
            if scanned > limit_albums:
                break
            time.sleep(0.22)
            tracks = _itunes_get_json(
                f"https://itunes.apple.com/lookup?id={cid}&entity=song&limit=80&country={country}",
                timeout,
                attempts=1,
            )
            for item in (tracks or {}).get("results") or []:
                score = _score_itunes_item(item, title, artist)
                if score > best_score:
                    best_score = score
                    best = item
            if best_score >= 14:
                return best
        if best_score >= 14:
            return best
    return best if best_score >= 8 else None


def _itunes_artist_songs(artist_id: int, country: str, timeout: float) -> list[dict]:
    key = (int(artist_id), country)
    cached = _ARTIST_SONGS.get(key)
    if cached is not None:
        return cached
    data = _itunes_get_json(
        f"https://itunes.apple.com/lookup?id={artist_id}&entity=song&limit=200&country={country}",
        timeout,
        attempts=1,
    )
    rows = [
        row
        for row in (data or {}).get("results") or []
        if row.get("previewUrl") and row.get("trackName")
    ]
    _ARTIST_SONGS[key] = rows
    if rows:
        _remember_artist(rows[0])
    return rows


def _itunes_lookup_via_artist(
    title: str,
    artist: str,
    countries: tuple[str, ...],
    timeout: float,
) -> dict | None:
    aid = _artist_id_for(artist, timeout)
    if not aid:
        return None
    best = None
    best_score = -99
    for country in countries:
        for item in _itunes_artist_songs(aid, country, timeout):
            score = _score_itunes_item(item, title, artist)
            if score > best_score:
                best_score = score
                best = item
        if best_score >= 14:
            return best
        time.sleep(0.2)
    if best_score >= 8:
        return best
    return _itunes_lookup_via_albums(title, artist, aid, countries, timeout)


def _known_track_match(title: str, artist: str, timeout: float, countries: tuple[str, ...]) -> dict | None:
    title_f = fold_zh(title)
    artist_f = fold_zh(artist)
    for (want_title, want_artist), itunes_id in _KNOWN_TRACK_IDS.items():
        if fold_zh(want_title) != title_f:
            continue
        if not _name_hit(artist, want_artist) and artist_f not in fold_zh(want_artist):
            continue
        rows = _itunes_lookup_id(itunes_id, timeout, countries)
        best = None
        best_score = -99
        for item in rows:
            score = _score_itunes_item(item, title, artist)
            if score > best_score:
                best_score = score
                best = item
        if best and best_score >= 6:
            return best
    return None


def _itunes_lookup(
    query: str,
    title: str,
    artist: str,
    timeout: float = 14,
    attempts: int = 3,
    countries: tuple[str, ...] = ("HK", "TW", "JP", "KR", "SG", "US"),
) -> dict | None:
    """香港商店优先（华语曲目更全），亚洲店补日韩热歌；`/search` 被拦时走旧检索、歌手作品和已知曲目编号。"""
    known = _known_track_match(title, artist, timeout, countries)
    if known:
        _remember_artist(known)
        return known
    best = None
    best_score = -99
    for country in countries:
        rows = itunes_search_results(query, country, timeout=timeout, limit=15, attempts=attempts)
        for item in rows:
            score = _score_itunes_item(item, title, artist)
            if score > best_score:
                best_score = score
                best = item
        if best_score >= 14:
            if best:
                _remember_artist(best)
            return best
        time.sleep(0.15)
    if best_score < 14:
        extra = _itunes_lookup_via_artist(title, artist, countries, timeout)
        if extra:
            extra_score = _score_itunes_item(extra, title, artist)
            if extra_score > best_score:
                best = extra
                best_score = extra_score
    if best and best_score >= 8:
        _remember_artist(best)
        return best
    return None


def _save_url(url: str, dest: Path, min_size: int = 20_000) -> bool:
    for attempt in range(3):
        try:
            with requests.get(url, stream=True, timeout=40, headers={"User-Agent": "Mozilla/5.0"}) as r:
                r.raise_for_status()
                tmp = dest.with_suffix(dest.suffix + ".part")
                size = 0
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 16):
                        if chunk:
                            f.write(chunk)
                            size += len(chunk)
                if size < min_size:
                    tmp.unlink(missing_ok=True)
                    continue
                tmp.replace(dest)
                return True
        except Exception as exc:
            logger.warning("下载失败 %s (%s/3): %s", dest.name, attempt + 1, exc)
            time.sleep(0.6 * (attempt + 1))
    return False


def _bad_vocal_match(artist: str) -> bool:
    blob = (artist or "").lower()
    return any(skip in blob for skip in _SKIP_ARTISTS)


_MOOD_BY_EMO = {
    "happy": dict(mood="bright", tempo=126, root=60, scale="major"),
    "angry": dict(mood="drive", tempo=142, root=52, scale="minor"),
    "sad": dict(mood="soft", tempo=70, root=55, scale="minor"),
    "fear": dict(mood="dark", tempo=86, root=50, scale="phrygian"),
    "surprise": dict(mood="spark", tempo=124, root=65, scale="lydian"),
    "disgust": dict(mood="grit", tempo=98, root=51, scale="phrygian"),
    "neutral": dict(mood="calm", tempo=94, root=60, scale="major"),
}


def _write_local_melody(spec: dict, dest: Path) -> bool:
    """按情绪规则现场生成一段可播放旋律，保证断网时列表不为空。"""
    mood = _MOOD_BY_EMO.get(spec["emotion"]) or _MOOD_BY_EMO["neutral"]
    stereo = _render_song(
        {
            **mood,
            "id": spec["id"],
            "emotion": spec["emotion"],
            "title": spec["title"],
            "artist": "心弦室内乐",
            "seed": abs(hash(spec["id"])) % 10000,
        }
    )
    _write_wav(dest, stereo)
    return dest.exists() and dest.stat().st_size >= 20_000


def ensure_library() -> None:
    """优先使用已缓存的人声试听；缺文件且无网时按规则生成本地旋律。"""
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    COVER_DIR.mkdir(parents=True, exist_ok=True)
    catalog_path = DATA_DIR / "catalog.json"
    previous: dict[str, dict] = {}
    if catalog_path.exists():
        try:
            old = json.loads(catalog_path.read_text(encoding="utf-8"))
            for s in old.get("songs") or []:
                if s.get("id"):
                    previous[s["id"]] = s
        except Exception:
            previous = {}
    _index_catalog_seeds(previous)

    def _ok_file(path: Path, min_size: int = 20_000) -> bool:
        return path.exists() and path.stat().st_size >= min_size

    missing_vocal = [
        spec
        for spec in VOCAL_SONGBOOK
        if not _ok_file(AUDIO_DIR / f"{spec['id']}.m4a")
    ]
    missing = [
        spec
        for spec in missing_vocal
        if not _ok_file(AUDIO_DIR / f"{spec['id']}.wav")
    ]
    allow_net = bool(missing_vocal) and _itunes_reachable()
    if missing_vocal and not allow_net:
        logger.info("离线启动：缺 %s 首人声缓存，将按规则生成本地旋律", len(missing_vocal))
    elif missing_vocal:
        logger.info("补拉 %s 首尚未缓存的人声试听", len(missing_vocal))

    catalog = []
    for spec in VOCAL_SONGBOOK:
        m4a_path = AUDIO_DIR / f"{spec['id']}.m4a"
        wav_path = AUDIO_DIR / f"{spec['id']}.wav"
        cover_path = COVER_DIR / f"{spec['id']}.jpg"
        meta = EMOTIONS[spec["emotion"]]
        prev = previous.get(spec["id"]) or {}
        item = None
        stale = prev.get("kind") == "vocal" and (
            (prev.get("title") and prev.get("title") != spec["title"])
            or (prev.get("artist") and prev.get("artist") != spec["artist"])
        )
        if stale:
            for path in (m4a_path, cover_path):
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
        kind = "vocal"
        mime = "audio/mp4"
        audio_path = m4a_path
        title = spec["title"]
        artist = spec["artist"]
        source_label = "本地曲库 · 歌曲试听"
        need_vocal = stale or not _ok_file(m4a_path) or _bad_vocal_match(prev.get("artist") or "")
        if need_vocal and allow_net:
            logger.info("拉取歌曲试听 %s - %s", spec["title"], spec["artist"])
            title_en = any(ch.isascii() and ch.isalpha() for ch in spec["title"]) and not any(
                "\u4e00" <= ch <= "\u9fff" for ch in spec["title"]
            )
            countries = ("US", "JP", "KR", "HK", "TW", "SG") if title_en else ("HK", "TW", "JP", "KR", "SG", "US")
            item = _itunes_lookup(
                spec["query"], spec["title"], spec["artist"], timeout=8, attempts=2, countries=countries
            )
            if item and _save_url(item["previewUrl"], m4a_path, min_size=20_000):
                need_vocal = False
            elif _ok_file(m4a_path):
                need_vocal = False
            time.sleep(0.35)
        if need_vocal and _ok_file(m4a_path):
            need_vocal = False
        if need_vocal:
            if not _ok_file(wav_path):
                logger.info("现场生成旋律 %s", spec["title"])
                _write_local_melody(spec, wav_path)
            if not _ok_file(wav_path):
                logger.warning("本地旋律生成失败：%s", spec["title"])
                continue
            audio_path = wav_path
            kind = "melody"
            mime = "audio/wav"
            title = f"{spec['title']} · 本地旋律"
            artist = "心弦室内乐"
            source_label = "本地旋律 · 离线可播"
        elif wav_path.exists():
            try:
                wav_path.unlink()
            except OSError:
                pass
        if not _ok_file(cover_path, 1000):
            if item is None and allow_net:
                item = _itunes_lookup(
                    spec["query"], spec["title"], spec["artist"], timeout=3, attempts=1, countries=("HK",)
                )
            art = ""
            if item:
                art = item.get("artworkUrl100") or ""
                art = art.replace("100x100bb", "300x300bb").replace("100x100", "300x300")
            if not art or not _save_url(art, cover_path, min_size=1000):
                render_cover(
                    {
                        **spec,
                        "album": (item or {}).get("collectionName") or spec["title"],
                        "mood": _MOOD_BY_EMO[spec["emotion"]]["mood"],
                        "seed": abs(hash(spec["id"])) % 1000,
                    },
                    cover_path,
                )
        info = item or {}
        catalog.append(
            {
                "id": spec["id"],
                "title": pretty_text(title),
                "artist": pretty_text(artist),
                "album": pretty_text(info.get("collectionName") or prev.get("album") or spec["title"]),
                "emotion": spec["emotion"],
                "genre": meta["genre"],
                "source": "local",
                "source_label": source_label,
                "kind": kind,
                "file": audio_path.name,
                "audio": f"/api/audio/{spec['id']}",
                "cover": f"/static/covers/{cover_path.name}",
                "preview": f"/api/audio/{spec['id']}",
                "external_url": info.get("trackViewUrl") or prev.get("external_url") or "",
                "duration": 30.0 if kind == "vocal" else 14.0,
                "playable": True,
                "downloadable": True,
                "mime": mime,
            }
        )
    if len(catalog) < 532:
        logger.warning("本地曲库不足 532 首（当前 %s）", len(catalog))
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"songs": catalog, "count": len(catalog), "kind": "local"}
    catalog_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    keep = {s["file"] for s in catalog}
    for leftover in list(AUDIO_DIR.glob("vocal-*.m4a")) + list(AUDIO_DIR.glob("vocal-*.wav")) + list(AUDIO_DIR.glob("vocal-*.mp3")) + list(AUDIO_DIR.glob("local-*.wav")):
        if leftover.name not in keep:
            try:
                leftover.unlink()
            except OSError:
                pass
    vocal_n = sum(1 for s in catalog if s.get("kind") == "vocal")
    melody_n = sum(1 for s in catalog if s.get("kind") == "melody")
    logger.info("本地曲库 %s 首（人声试听 %s · 离线旋律 %s）", len(catalog), vocal_n, melody_n)


def ensure_assets() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    COVER_DIR.mkdir(parents=True, exist_ok=True)
    ensure_models()
    ensure_library()
