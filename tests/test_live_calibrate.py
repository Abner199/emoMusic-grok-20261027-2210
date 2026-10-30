# -*- coding: utf-8 -*-
"""几何校准：休息脸/说话口型不应锁在惊讶或喜悦。"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.emotion import calibrate_live_vec


def _vec(**kw):
    p = np.zeros(7, dtype=np.float64)
    names = ["angry", "disgust", "fear", "happy", "neutral", "sad", "surprise"]
    for k, v in kw.items():
        p[names.index(k)] = v
    s = p.sum()
    return p / s if s else p


REST = {"mouth_w": 0.80, "mouth_drop": 0.40, "mouth_lift": -0.23, "forehead": 1.05}
OPEN = {"mouth_w": 1.25, "mouth_drop": 0.70, "mouth_lift": -0.20, "forehead": 1.25}
SMILE = {"mouth_w": 0.98, "mouth_drop": 0.36, "mouth_lift": -0.10, "forehead": 1.08}


def main() -> int:
    fails = 0

    def chk(name, cond, detail=""):
        nonlocal fails
        mark = "PASS" if cond else "FAIL"
        print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))
        if not cond:
            fails += 1

    rest_sur = calibrate_live_vec(_vec(surprise=0.55, neutral=0.25, happy=0.20), REST)
    chk("闭嘴惊讶压回平静", rest_sur[4] > rest_sur[6], rest_sur.round(3).tolist())

    keep_sur = calibrate_live_vec(_vec(surprise=0.70, neutral=0.15, fear=0.15), OPEN)
    chk("张口挑眉保留惊讶", keep_sur[6] > keep_sur[4], keep_sur.round(3).tolist())

    rest_hap = calibrate_live_vec(_vec(happy=0.48, neutral=0.35, surprise=0.17), REST)
    chk("无笑意喜悦压回平静", rest_hap[4] > rest_hap[3], rest_hap.round(3).tolist())

    keep_hap = calibrate_live_vec(_vec(happy=0.62, neutral=0.22, surprise=0.16), SMILE)
    chk("拉开上扬保留喜悦", keep_hap[3] > keep_hap[4], keep_hap.round(3).tolist())

    print("=== 结果 ===")
    if fails:
        print(f"未通过 {fails} 项")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
