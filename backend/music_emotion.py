# -*- coding: utf-8 -*-
"""
歌曲旋律 / 曲调情绪识别。

算法（经典、本机、无云端）：
1. Thayer 二维模型（1989）：用速度与能量估计唤醒度 arousal，用调式与频谱亮度估计效价 valence
2. Krumhansl–Kessler 调式相关（1982）：12 音级直方图与大小调剖面求相关，判断大调 / 小调
3. Juslin 声学线索表（2001）：速度、调式、强度、音色 → 离散情绪
4. 能量包络自相关网格搜索 BPM（Scheirer / Ellis 一类经典节奏法）

对能解码的波形（WAV 或 ffmpeg 转出的 PCM）直接抽取特征；
人声 AAC 试听在未装解码器时，用同一套规则分析该情绪的典型旋律骨架，再与 Juslin 表对照。
"""
from __future__ import annotations

import math
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Optional

import numpy as np

from config import AUDIO_DIR, EMOTIONS

EMO_ORDER = ["happy", "angry", "sad", "fear", "surprise", "disgust", "neutral"]

# Krumhansl & Kessler 1982
_KK_MAJOR = np.array(
    [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88],
    dtype=np.float64,
)
_KK_MINOR = np.array(
    [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17],
    dtype=np.float64,
)

# Juslin 2001 / Gabrielsson & Juslin：各情绪典型声学线索
_JUSLIN = {
    "happy": dict(tempo=126.0, mode=1.0, energy=0.72, centroid=0.68),
    "angry": dict(tempo=142.0, mode=-0.88, energy=0.90, centroid=0.52),
    "sad": dict(tempo=66.0, mode=-0.92, energy=0.28, centroid=0.32),
    "fear": dict(tempo=84.0, mode=-0.78, energy=0.42, centroid=0.64),
    "surprise": dict(tempo=128.0, mode=0.50, energy=0.80, centroid=0.82),
    "disgust": dict(tempo=98.0, mode=-0.62, energy=0.55, centroid=0.46),
    "neutral": dict(tempo=96.0, mode=0.12, energy=0.48, centroid=0.50),
}

# Russell 效价-唤醒平面上的七点（再加能量/亮度差，用来分开怒与惧）
_VA = {
    "happy": (0.78, 0.70),
    "angry": (-0.62, 0.84),
    "sad": (-0.72, -0.58),
    "fear": (-0.52, 0.58),
    "surprise": (0.32, 0.88),
    "disgust": (-0.58, 0.12),
    "neutral": (0.04, 0.02),
}

_SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "harm_minor": [0, 2, 3, 5, 7, 8, 11],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11],
    "pent_major": [0, 2, 4, 7, 9],
}

_SKETCH = {
    "happy": dict(tempo=126, root=64, scale="major", kind="triangle"),
    "angry": dict(tempo=142, root=52, scale="minor", kind="saw"),
    "sad": dict(tempo=66, root=55, scale="minor", kind="sine"),
    "fear": dict(tempo=84, root=50, scale="phrygian", kind="sine"),
    "surprise": dict(tempo=128, root=67, scale="lydian", kind="square"),
    "disgust": dict(tempo=98, root=51, scale="phrygian", kind="saw"),
    "neutral": dict(tempo=96, root=60, scale="major", kind="sine"),
}

ALGO_NAME = "Thayer 二维模型 + Krumhansl–Kessler 调式"
ALGO_ID = "thayer-krumhansl-juslin"

_LOCK = threading.Lock()
_CACHE: dict[str, dict] = {}
_PROTO: dict[str, dict] = {}
_SR = 16000


def _softmax(x: np.ndarray, temp: float = 0.22) -> np.ndarray:
    z = np.asarray(x, dtype=np.float64) / max(temp, 1e-6)
    z = z - np.max(z)
    e = np.exp(z)
    return e / np.clip(e.sum(), 1e-12, None)


def _norm(v: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.5
    return float(np.clip((v - lo) / (hi - lo), 0.0, 1.0))


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return float(np.clip(np.dot(a, b) / (na * nb), -1.0, 1.0))


def face_vector(scores, emotion_id: str = "neutral") -> np.ndarray:
    vec = np.zeros(len(EMO_ORDER), dtype=np.float64)
    index = {k: i for i, k in enumerate(EMO_ORDER)}
    for item in scores or []:
        if not isinstance(item, dict):
            continue
        key = item.get("id")
        if key in index:
            vec[index[key]] = float(item.get("prob") or 0.0)
    if vec.sum() < 1e-8:
        vec[index.get(emotion_id, index["neutral"])] = 1.0
    s = vec.sum()
    return vec / s if s > 0 else vec


def target_vector(emotion_id: str = "neutral") -> np.ndarray:
    vec = np.zeros(len(EMO_ORDER), dtype=np.float64)
    key = emotion_id if emotion_id in EMO_ORDER else "neutral"
    vec[EMO_ORDER.index(key)] = 1.0
    return vec


def _onset_flux(y: np.ndarray, sr: int, win: int = 1024, hop: int = 256) -> np.ndarray:
    if len(y) < win * 2:
        return np.array([0.0], dtype=np.float64)
    window = np.hanning(win).astype(np.float32)
    frames = []
    for start in range(0, len(y) - win, hop):
        spec = np.abs(np.fft.rfft(y[start : start + win] * window))
        frames.append(spec)
    mag = np.stack(frames)
    diff = np.diff(mag, axis=0)
    flux = np.maximum(0.0, diff).sum(axis=1)
    flux = flux - flux.mean()
    return flux.astype(np.float64)


def _tempo_bpm(y: np.ndarray, sr: int) -> float:
    hop = 256
    win = 1024
    if len(y) < win * 4:
        return 96.0
    env = np.array(
        [float(np.mean(np.square(y[i : i + win]))) for i in range(0, len(y) - win, hop)],
        dtype=np.float64,
    )
    env = np.maximum(env, 0.0)
    env = env - env.mean()
    if env.size < 16 or float(env.std()) < 1e-10:
        return 96.0
    corr = np.correlate(env, env, mode="full")[len(env) - 1 :]
    frame_sr = sr / hop
    best_bpm = 96.0
    best_v = -1.0
    for bpm in range(54, 176, 2):
        lag = frame_sr * 60.0 / bpm
        lo = max(1, int(lag) - 1)
        hi = min(len(corr) - 1, int(lag) + 2)
        if hi <= lo:
            continue
        v = float(np.max(corr[lo:hi]))
        if v > best_v:
            best_v = v
            best_bpm = float(bpm)
    return float(np.clip(best_bpm, 54.0, 176.0))


def _chroma(y: np.ndarray, sr: int, win: int = 2048) -> np.ndarray:
    if len(y) < win:
        win = 1 << max(8, int(math.log2(max(len(y), 32))))
    window = np.hanning(min(win, len(y)))
    spec = np.abs(np.fft.rfft(y[: len(window)] * window))
    freqs = np.fft.rfftfreq(len(window), 1.0 / sr)
    chroma = np.zeros(12, dtype=np.float64)
    for mag, freq in zip(spec[1:], freqs[1:]):
        if freq < 40 or freq > 5000:
            continue
        midi = 69.0 + 12.0 * math.log2(freq / 440.0)
        pc = int(round(midi)) % 12
        chroma[pc] += float(mag)
    s = chroma.sum()
    return chroma / s if s > 0 else chroma


def _mode_from_chroma(chroma: np.ndarray) -> tuple[str, float]:
    def corr(profile: np.ndarray) -> float:
        best = -1.0
        for shift in range(12):
            rot = np.roll(profile, shift)
            best = max(best, _cosine(chroma, rot))
        return best

    maj = corr(_KK_MAJOR)
    minor = corr(_KK_MINOR)
    if maj >= minor:
        return "major", float(maj - minor)
    return "minor", float(maj - minor)


def _rms(y: np.ndarray) -> float:
    if y.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(y, dtype=np.float64))))


def _centroid(y: np.ndarray, sr: int) -> float:
    if len(y) < 64:
        return 0.5
    spec = np.abs(np.fft.rfft(y * np.hanning(len(y))))
    freqs = np.fft.rfftfreq(len(y), 1.0 / sr)
    s = spec.sum()
    if s <= 0:
        return 0.5
    c = float(np.sum(freqs * spec) / s)
    return _norm(c, 200.0, 3200.0)


def features_from_pcm(y: np.ndarray, sr: int = _SR) -> dict:
    y = np.asarray(y, dtype=np.float32).reshape(-1)
    peak = float(np.max(np.abs(y))) if y.size else 0.0
    if peak > 1e-6:
        y = y / peak
    tempo = _tempo_bpm(y, sr)
    energy = float(np.clip(_rms(y) * 2.4, 0.0, 1.0))
    centroid = _centroid(y, sr)
    chroma = _chroma(y, sr)
    mode, mode_delta = _mode_from_chroma(chroma)
    mode_sign = 1.0 if mode == "major" else -1.0
    valence = float(np.clip(0.62 * mode_sign + 0.38 * float(np.clip(mode_delta, -1.0, 1.0)), -1.0, 1.0))
    arousal = float(
        np.clip(0.70 * (_norm(tempo, 54, 168) * 2.0 - 1.0) + 0.30 * (energy * 2.0 - 1.0), -1.0, 1.0)
    )
    return {
        "tempo": round(tempo, 1),
        "energy": round(energy, 3),
        "centroid": round(centroid, 3),
        "mode": mode,
        "mode_delta": round(mode_delta, 3),
        "arousal": round(arousal, 3),
        "valence": round(valence, 3),
        "source": "audio",
    }


def _scores_from_va(valence: float, arousal: float, energy: float, centroid: float) -> np.ndarray:
    dist = []
    for emo in EMO_ORDER:
        tv, ta = _VA[emo]
        extra = 0.0
        if emo == "angry":
            extra += (0.9 - energy) ** 2
        if emo == "fear":
            extra += (0.85 - centroid) ** 2 * 0.6
            extra += (energy - 0.45) ** 2 * 0.4
        if emo == "surprise":
            extra += (0.85 - centroid) ** 2 * 0.5
        dist.append((valence - tv) ** 2 + (arousal - ta) ** 2 + extra)
    return _softmax(-np.sqrt(np.array(dist, dtype=np.float64)), temp=0.18)


def scores_from_features(feat: dict) -> dict:
    valence = float(feat.get("valence") or 0.0)
    arousal = float(feat.get("arousal") or 0.0)
    energy = float(feat.get("energy") or 0.5)
    centroid = float(feat.get("centroid") or 0.5)
    vec = _scores_from_va(valence, arousal, energy, centroid)
    top = int(np.argmax(vec))
    emo = EMO_ORDER[top]
    meta = EMOTIONS[emo]
    return {
        **feat,
        "algo": ALGO_NAME,
        "algo_id": ALGO_ID,
        "vector": [round(float(x), 4) for x in vec],
        "emotion": emo,
        "emotion_zh": meta["zh"],
        "emotion_name": meta["name"],
        "tempo_label": f"{int(round(float(feat.get('tempo') or 96)))} 拍/分",
        "mode_zh": "大调" if feat.get("mode") == "major" else "小调",
        "prob": round(float(vec[top]), 3),
    }


def juslin_features(emotion: str) -> dict:
    if emotion not in _JUSLIN:
        emotion = "neutral"
    j = _JUSLIN[emotion]
    mode_sign = 1.0 if j["mode"] >= 0 else -1.0
    valence = float(np.clip(0.62 * mode_sign + 0.38 * float(np.clip(j["mode"], -1.0, 1.0)), -1.0, 1.0))
    arousal = float(
        np.clip(0.70 * (_norm(j["tempo"], 54, 168) * 2.0 - 1.0) + 0.30 * (j["energy"] * 2.0 - 1.0), -1.0, 1.0)
    )
    return {
        "tempo": j["tempo"],
        "energy": j["energy"],
        "centroid": j["centroid"],
        "mode": "major" if j["mode"] >= 0 else "minor",
        "mode_delta": j["mode"],
        "arousal": round(arousal, 3),
        "valence": round(valence, 3),
        "source": "juslin",
    }


def render_sketch(emotion: str, seed: int = 7, seconds: float = 4.0, sr: int = _SR) -> np.ndarray:
    """按该情绪的典型速度与音阶合成短旋律，供 DSP 分析。"""
    spec = _SKETCH.get(emotion) or _SKETCH["neutral"]
    n = int(seconds * sr)
    tempo = spec["tempo"]
    beat = 60.0 / tempo
    scale = _SCALES[spec["scale"]]
    root = spec["root"]
    kind = spec["kind"]
    mix = np.zeros(n, dtype=np.float32)
    note_len = beat
    steps = int(seconds / note_len)
    pattern = [0, 2, 4, 5, 4, 2, 0, 4]
    third = 4 if spec["scale"] in {"major", "lydian", "pent_major"} else 3
    for i in range(max(1, steps)):
        deg = pattern[i % len(pattern)]
        midi = root + scale[deg % len(scale)]
        freq = 440.0 * (2.0 ** ((midi - 69.0) / 12.0))
        start = int(i * note_len * sr)
        length = int(note_len * 0.88 * sr)
        if start >= n:
            break
        length = min(length, n - start)
        tt = np.arange(length, dtype=np.float32) / sr
        ph = 2.0 * math.pi * freq * tt
        if kind == "triangle":
            wave = (2.0 / math.pi) * np.arcsin(np.clip(np.sin(ph), -1.0, 1.0))
        elif kind == "square":
            wave = np.sign(np.sin(ph)).astype(np.float32) * 0.65
        elif kind == "saw":
            wave = (2.0 * ((tt * freq) % 1.0) - 1.0).astype(np.float32) * 0.5
        else:
            wave = np.sin(ph).astype(np.float32)
        att = max(8, length // 12)
        rel = max(8, length // 3)
        env = np.ones(length, dtype=np.float32)
        env[:att] = np.linspace(0.0, 1.0, att, dtype=np.float32)
        env[-rel:] = np.linspace(1.0, 0.0, rel, dtype=np.float32)
        mix[start : start + length] += wave * env * 0.42
        third_f = 440.0 * (2.0 ** ((midi + third - 69.0) / 12.0))
        mix[start : start + length] += np.sin(2.0 * math.pi * third_f * tt).astype(np.float32) * env * 0.22
        click_n = min(int(0.012 * sr), length)
        mix[start : start + click_n] += np.linspace(0.35, 0.0, click_n, dtype=np.float32)
    peak = float(np.max(np.abs(mix))) if mix.size else 0.0
    if peak > 1e-6:
        mix = mix / peak * 0.9
    return mix


def _wav_pcm(path: Path, max_seconds: float = 8.0) -> Optional[tuple[np.ndarray, int]]:
    try:
        from scipy.io import wavfile

        sr, data = wavfile.read(str(path))
        y = np.asarray(data, dtype=np.float32)
        if y.ndim > 1:
            y = y.mean(axis=1)
        if np.issubdtype(data.dtype, np.integer):
            y = y / max(1.0, float(np.iinfo(data.dtype).max))
        n = int(max_seconds * sr)
        return y[:n], int(sr)
    except Exception:
        return None


def _ffmpeg_pcm(path: Path, sr: int = _SR, seconds: float = 8.0) -> Optional[tuple[np.ndarray, int]]:
    bin_path = shutil.which("ffmpeg")
    if not bin_path:
        return None
    try:
        cmd = [
            bin_path,
            "-v",
            "error",
            "-i",
            str(path),
            "-t",
            str(seconds),
            "-ac",
            "1",
            "-ar",
            str(sr),
            "-f",
            "s16le",
            "pipe:1",
        ]
        proc = subprocess.run(cmd, capture_output=True, timeout=6)
        raw = proc.stdout or b""
        if len(raw) < sr:
            return None
        y = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        return y, sr
    except Exception:
        return None


def load_pcm(path: Path, seconds: float = 8.0) -> Optional[tuple[np.ndarray, int]]:
    path = Path(path)
    if not path.exists():
        return None
    suffix = path.suffix.lower()
    if suffix in {".wav", ".wave"}:
        return _wav_pcm(path, seconds)
    got = _ffmpeg_pcm(path, _SR, seconds)
    if got:
        return got
    if suffix in {".wav", ".wave"}:
        return _wav_pcm(path, seconds)
    return None


def analyze_pcm(y: np.ndarray, sr: int = _SR) -> dict:
    return scores_from_features(features_from_pcm(y, sr))


def analyze_path(path: Path) -> Optional[dict]:
    loaded = load_pcm(Path(path))
    if not loaded:
        return None
    y, sr = loaded
    return analyze_pcm(y, sr)


def _blend(a: dict, b: dict, w: float) -> dict:
    vec = (1.0 - w) * np.array(a["vector"], dtype=np.float64) + w * np.array(b["vector"], dtype=np.float64)
    s = vec.sum()
    if s > 0:
        vec = vec / s
    top = int(np.argmax(vec))
    emo = EMO_ORDER[top]
    meta = EMOTIONS[emo]
    out = dict(a)
    out.update(
        {
            "vector": [round(float(x), 4) for x in vec],
            "emotion": emo,
            "emotion_zh": meta["zh"],
            "emotion_name": meta["name"],
            "prob": round(float(vec[top]), 3),
            "tempo": round(0.5 * float(a.get("tempo") or 96) + 0.5 * float(b.get("tempo") or 96), 1),
            "valence": round(0.5 * float(a.get("valence") or 0) + 0.5 * float(b.get("valence") or 0), 3),
            "arousal": round(0.5 * float(a.get("arousal") or 0) + 0.5 * float(b.get("arousal") or 0), 3),
            "mode": b.get("mode") or a.get("mode"),
        }
    )
    out["tempo_label"] = f"{int(round(out['tempo']))} 拍/分"
    out["mode_zh"] = "大调" if out.get("mode") == "major" else "小调"
    return out


def describe_song(song: dict, emotion_hint: str = "") -> dict:
    """给一首歌打上曲调情绪向量。结果缓存，推荐时直接用。"""
    emotion = (song.get("emotion") or emotion_hint or "neutral").strip()
    if emotion not in EMOTIONS:
        emotion = "neutral"
    key = str(song.get("id") or song.get("title") or emotion)
    with _LOCK:
        cached = _CACHE.get(key)
        if cached:
            return dict(cached)

    prior = scores_from_features(juslin_features(emotion))
    with _LOCK:
        dsp = _PROTO.get(emotion)
    if dsp is None:
        sketch = render_sketch(emotion, seed=7)
        dsp = analyze_pcm(sketch, _SR)
        dsp["source"] = "prototype"
        with _LOCK:
            _PROTO[emotion] = dsp
    result = _blend(prior, dsp, 0.45)

    name = song.get("file")
    audio_path = AUDIO_DIR / name if name else None
    if audio_path and audio_path.exists():
        measured = analyze_path(audio_path)
        if measured:
            measured["source"] = "audio"
            result = _blend(result, measured, 0.55)

    result["algo"] = ALGO_NAME
    result["algo_id"] = ALGO_ID
    slim = {k: result[k] for k in result if k != "vector"}
    slim["vector"] = result["vector"]
    with _LOCK:
        _CACHE[key] = slim
    return dict(slim)


def match_score(face_vec, song_desc: dict) -> float:
    vec = song_desc.get("vector") or []
    return round(_cosine(np.asarray(face_vec, dtype=np.float64), np.asarray(vec, dtype=np.float64)), 4)


def public_music(desc: dict) -> dict:
    return {
        "algo": desc.get("algo") or ALGO_NAME,
        "tempo": desc.get("tempo"),
        "tempo_label": desc.get("tempo_label"),
        "mode": desc.get("mode"),
        "mode_zh": desc.get("mode_zh"),
        "valence": desc.get("valence"),
        "arousal": desc.get("arousal"),
        "emotion": desc.get("emotion"),
        "emotion_zh": desc.get("emotion_zh"),
        "source": desc.get("source"),
        "prob": desc.get("prob"),
    }
