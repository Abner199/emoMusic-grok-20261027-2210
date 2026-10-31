"""开发工具：用 Whisper 把 static/audio/vocal-*.m4a 试听转成带时间戳的文字。

结果写到 data/asr_previews/<文件名>.json，供 tools/align_lyrics.py 对齐歌词。
只在维护曲库时需要；正常运行软件不需要 torch / transformers。

    pip install torch transformers av
    python tools/asr_previews.py            # 单进程
    python tools/asr_previews.py 0 4 6      # 第 0 份 / 共 4 份，6 线程（可开多个进程并行）

已有结果的文件会跳过，可以随时中断续跑。新增歌曲后重跑本脚本和 align_lyrics.py 即可。

    python tools/asr_previews.py --redo vocal-sad-67,vocal-neutral-39   # 只重跑指定的歌（覆盖旧结果）

识别语言按歌名强制：歌名含汉字用中文，否则英文。自动判语言会把中文歌听成泰卢固文、越南文等。
"""
from __future__ import annotations

import json
import os
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "asr_previews"
MODEL = os.environ.get("EMOTUNE_ASR_MODEL", "openai/whisper-small")


def decode(path: Path, sr: int = 16000):
    import av
    import numpy as np

    box = av.open(str(path))
    res = av.AudioResampler(format="s16", layout="mono", rate=sr)
    parts = []
    for frame in box.decode(audio=0):
        for f in res.resample(frame):
            parts.append(f.to_ndarray().ravel())
    return np.concatenate(parts).astype(np.float32) / 32768.0


def song_language(stem: str) -> str:
    sys.path.insert(0, str(ROOT))
    from backend.songbook import VOCAL_SONGBOOK

    for spec in VOCAL_SONGBOOK:
        if spec["id"] == stem:
            text = f"{spec.get('title') or ''}"
            return "zh" if any("一" <= ch <= "鿿" for ch in text) else "en"
    return "zh"


def main() -> None:
    warnings.filterwarnings("ignore")
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
    args = sys.argv[1:]
    redo: set[str] = set()
    if "--redo" in args:
        i = args.index("--redo")
        redo = {x.strip() for x in args[i + 1].split(",") if x.strip()}
        args = args[:i] + args[i + 2 :]
    part = int(args[0]) if len(args) > 0 else 0
    parts = int(args[1]) if len(args) > 1 else 1
    threads = int(args[2]) if len(args) > 2 else max(1, os.cpu_count() or 1)
    import torch
    from transformers import pipeline

    torch.set_num_threads(threads)
    OUT.mkdir(parents=True, exist_ok=True)
    asr = pipeline("automatic-speech-recognition", model=MODEL, device="cpu")
    files = sorted((ROOT / "static" / "audio").glob("vocal-*.m4a"))
    if redo:
        files = [f for f in files if f.stem in redo]
    files = files[part::parts]
    for path in files:
        dst = OUT / f"{path.name}.json"
        if dst.exists() and path.stem not in redo:
            continue
        try:
            r = asr(
                {"raw": decode(path), "sampling_rate": 16000},
                return_timestamps=True,
                generate_kwargs={"task": "transcribe", "language": song_language(path.stem), "no_repeat_ngram_size": 4},
            )
            rows = [{"t0": c["timestamp"][0], "t1": c["timestamp"][1], "text": c["text"]} for c in r["chunks"]]
        except Exception as exc:  # 单首失败不影响其它
            rows = {"error": str(exc)}
        dst.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        print(path.name, flush=True)


if __name__ == "__main__":
    main()
