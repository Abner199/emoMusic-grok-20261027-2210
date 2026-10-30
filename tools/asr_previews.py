"""开发工具：用 Whisper 把 static/audio/vocal-*.m4a 试听转成带时间戳的文字。

结果写到 data/asr_previews/<文件名>.json，供 tools/align_lyrics.py 对齐歌词。
只在维护曲库时需要；正常运行软件不需要 torch / transformers。

    pip install torch transformers av
    python tools/asr_previews.py            # 单进程
    python tools/asr_previews.py 0 4 6      # 第 0 份 / 共 4 份，6 线程（可开多个进程并行）

已有结果的文件会跳过，可以随时中断续跑。新增歌曲后重跑本脚本和 align_lyrics.py 即可。
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


def main() -> None:
    warnings.filterwarnings("ignore")
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
    part = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    parts = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    threads = int(sys.argv[3]) if len(sys.argv) > 3 else max(1, os.cpu_count() or 1)
    import torch
    from transformers import pipeline

    torch.set_num_threads(threads)
    OUT.mkdir(parents=True, exist_ok=True)
    asr = pipeline("automatic-speech-recognition", model=MODEL, device="cpu")
    files = sorted((ROOT / "static" / "audio").glob("vocal-*.m4a"))[part::parts]
    for path in files:
        dst = OUT / f"{path.name}.json"
        if dst.exists():
            continue
        try:
            r = asr(
                {"raw": decode(path), "sampling_rate": 16000},
                return_timestamps=True,
                generate_kwargs={"task": "transcribe", "no_repeat_ngram_size": 4},
            )
            rows = [{"t0": c["timestamp"][0], "t1": c["timestamp"][1], "text": c["text"]} for c in r["chunks"]]
        except Exception as exc:  # 单首失败不影响其它
            rows = {"error": str(exc)}
        dst.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        print(path.name, flush=True)


if __name__ == "__main__":
    main()
