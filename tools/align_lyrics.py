"""把 30 秒试听与官方 LRC 对齐，写出 data/lyrics_aligned.json。

试听片段从整首歌的哪一秒开始，苹果并不公布。以前靠本机预置的几句“锚点词”去猜，
很多猜错，歌词就整体错位。这里改用语音识别的结果来定位：

1. 先运行 tools/asr_previews.py，用 Whisper 把每段试听转成带时间戳的文字；
2. 再运行本脚本：拿识别文字去匹配官方 LRC 的每一句，取一致性最高的偏移，
   把官方歌词切成试听窗口内的时间轴保存下来。

运行时 backend/lyrics.py 直接读取结果，不需要联网，也不需要 torch。

    python tools/align_lyrics.py [转写目录]
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import lyrics as L  # noqa: E402

ASR_DIR = ROOT / "data" / "asr_previews"
OUT = ROOT / "data" / "lyrics_aligned.json"
PREVIEW_S = 30.0


def _chunks(path: Path) -> list[dict]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    out = []
    for c in raw:
        text = L._norm_text(c.get("text") or "")
        t0 = c.get("t0")
        if t0 is None or len(text) < 3:
            continue
        out.append({"t0": float(t0), "text": text})
    return out


def _line_sim(chunk: str, official: list[dict], i: int) -> float:
    """识别片段可能跨两三句官方歌词，取单句与连句里最像的一种。"""
    best = 0.0
    joined = ""
    for k in range(i, min(i + 3, len(official))):
        joined += L._norm_text(official[k]["text"])
        best = max(best, L._sim(chunk, joined))
    return best


def _score(offset: float, chunks: list[dict], official: list[dict]) -> tuple[float, list[float], int]:
    total = 0.0
    deltas: list[float] = []
    hits = 0
    for c in chunks:
        want = c["t0"] + offset
        best, best_d = 0.0, 0.0
        for i, row in enumerate(official):
            d = float(row["t"]) - want
            if d < -4.0:
                continue
            if d > 4.0:
                break
            s = _line_sim(c["text"], official, i)
            if s > best:
                best, best_d = s, d
        if best >= 0.42:
            hits += 1
            total += best * min(len(c["text"]), 16)
            deltas.append(best_d)
    return total, deltas, hits


def align(chunks: list[dict], official: list[dict]) -> tuple[float, float, int] | None:
    if len(chunks) < 2 or len(official) < 4:
        return None
    cands = set()
    for c in chunks:
        for i, row in enumerate(official):
            if _line_sim(c["text"], official, i) >= 0.45:
                cands.add(round(float(row["t"]) - c["t0"], 1))
    best = None
    for off in sorted(cands):
        if off < -1.0:
            continue
        total, deltas, hits = _score(off, chunks, official)
        if best is None or total > best[0]:
            best = (total, off, deltas, hits)
    if not best or best[3] < 2:
        return None
    total, off, deltas, hits = best
    off = max(0.0, off + statistics.median(deltas))
    weight = sum(min(len(c["text"]), 16) for c in chunks) or 1
    return off, total / weight, hits


def main() -> None:
    asr_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ASR_DIR
    out: dict[str, dict] = {}
    if OUT.exists():
        out = json.loads(OUT.read_text(encoding="utf-8"))
    ok = miss = 0
    for spec in L.VOCAL_SONGBOOK:
        sid = spec["id"]
        path = asr_dir / f"{sid}.m4a.json"
        if not path.exists():
            continue
        chunks = _chunks(path)
        title = L.pretty_text(spec.get("title") or "")
        artist = L.pretty_text(spec.get("artist") or "")
        try:
            official = L._official_lines(title, artist, L._qq_mid_from_id(sid))
        except Exception:
            official = []
        got = align(chunks, official)
        if not got or not (got[1] >= 0.33 or (got[2] >= 3 and got[1] >= 0.22)):
            miss += 1
            out.pop(sid, None)
            print(f"[--] {sid} {title}  未能可靠对齐")
            continue
        off, conf, hits = got
        lines = L._shift_window(official, off, PREVIEW_S)
        if len(lines) < 2:
            miss += 1
            out.pop(sid, None)
            continue
        out[sid] = {"offset": round(off, 2), "conf": round(conf, 3), "hits": hits, "lines": lines}
        ok += 1
        print(f"[ok] {sid} {title}  offset={off:.2f}s conf={conf:.2f} hits={hits}")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"对齐 {ok} 首，未对齐 {miss} 首，共写入 {len(out)} 首 → {OUT}")


if __name__ == "__main__":
    main()
