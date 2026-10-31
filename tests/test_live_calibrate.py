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

    # 课堂演示模式：学生紧张时抿嘴微笑 → 平静；嘴张得不太大的“扮惊讶” → 惊讶；真的笑开仍是喜悦
    from backend.emotion import DEMO_MODE

    token = DEMO_MODE.set(True)
    try:
        shy = {"mouth_w": 0.86, "mouth_drop": 0.45, "mouth_lift": -0.20}
        kid_open = {"mouth_w": 0.84, "mouth_drop": 0.55, "mouth_lift": -0.30}
        big_smile = {"mouth_w": 0.91, "mouth_drop": 0.46, "mouth_lift": -0.18}
        v = calibrate_live_vec(_vec(happy=0.58, neutral=0.32, surprise=0.10), shy)
        chk("演示：抿嘴微笑算平静", v[4] > v[3], v.round(3).tolist())
        v = calibrate_live_vec(_vec(neutral=0.40, surprise=0.36, happy=0.14, fear=0.10), kid_open)
        chk("演示：张口不太大也算惊讶", v[6] > v[4] and v[6] > v[3], v.round(3).tolist())
        v = calibrate_live_vec(_vec(happy=0.70, neutral=0.20, surprise=0.10), big_smile)
        chk("演示：真的笑开仍是喜悦", v[3] > v[4], v.round(3).tolist())
    finally:
        DEMO_MODE.reset(token)
    v = calibrate_live_vec(_vec(happy=0.58, neutral=0.32, surprise=0.10), {"mouth_w": 0.86, "mouth_drop": 0.45, "mouth_lift": -0.20})
    chk("普通模式不受演示规则影响", v[3] > v[4], v.round(3).tolist())

    print("=== 结果 ===")
    if fails:
        print(f"未通过 {fails} 项")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
