# -*- coding: utf-8 -*-
"""
人脸检测 + 表情识别。

检测器：OpenCV YuNet（5 点关键点）
识别器：OpenCV Zoo MobileFaceNet FER（7 类，RAF-DB 报告准确率 88.27%）
单人精检再叠加 HSEmotion EfficientNet-B0（AffectNet 野外）+ 翻转/微转 TTA + 多帧平均。
对齐：与官方 demo 相同的 112×112 相似变换，保证输入分布一致。
"""
from __future__ import annotations

import base64
import logging
import os
import threading
import time
from typing import Optional

import cv2
import contextvars

import numpy as np

from collections import defaultdict

from config import (
    DEFAULT_FACE_MODE,
    EMOTION_CONF_WARN,
    EMOTIONS,
    FACE_MAX,
    FACE_MODES,
    FACE_SCORE_MIN,
    FER_FILE,
    HSE_FILE,
    INDEX_TO_ID,
    MAX_IMAGE_SIDE,
    MODEL_DIR,
    MODEL_LABELS,
    YUNET_FILE,
    YUNET_NMS,
    YUNET_SCORE,
)

logger = logging.getLogger("emotune.emotion")

# ArcFace / MobileFaceNet 标准五点，来自 OpenCV Zoo facial_fer_model.py
_STD_POINTS = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype=np.float64,
)

_HSE_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_HSE_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
_HSE8 = ("angry", "contempt", "disgust", "fear", "happy", "neutral", "sad", "surprise")


def _softmax(x: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    z = x.astype(np.float64)
    t = max(float(temperature), 1e-6)
    z = z / t
    z = z - np.max(z)
    e = np.exp(z)
    return e / np.clip(e.sum(), 1e-12, None)


# YuNet 五点顺序与 ArcFace 对齐点相同：图像左眼、右眼、鼻尖、左嘴角、右嘴角
_YUNET_POINT_META = (
    ("le", "左眼", "p₁", "eye"),
    ("re", "右眼", "p₂", "eye"),
    ("nose", "鼻尖", "p₃", "nose"),
    ("ml", "左嘴角", "p₄", "mouth"),
    ("mr", "右嘴角", "p₅", "mouth"),
)


def landmark_cues(landmarks5, box=None) -> dict:
    """YuNet 五点几何 + 眉区估计，输出可画的关键点和 FACS 线索文字。

    眉毛不是 YuNet 实测点，按瞳距 IOD 在眼上方 0.35×IOD 处估计眉区。
    口型用嘴宽 / IOD 与嘴角上扬（相对眼线）对照 FACS AU12 / AU15 / AU27。
    """
    empty = {"landmarks": [], "points": [], "cues": [], "metrics": {}}
    if landmarks5 is None:
        return empty
    try:
        pts = np.asarray(landmarks5, dtype=np.float64).reshape(-1, 2)
    except Exception:
        return empty
    if pts.shape[0] < 5:
        return empty
    pts = pts[:5]
    le, re, nose, ml, mr = pts
    iod = float(np.linalg.norm(re - le)) + 1e-6
    mouth_w = float(np.linalg.norm(mr - ml)) / iod
    eye_y = 0.5 * (le[1] + re[1])
    mouth_y = 0.5 * (ml[1] + mr[1])
    mouth_lift = (eye_y + 0.82 * iod - mouth_y) / iod
    mouth_drop = (mouth_y - float(nose[1])) / iod
    eye_dx = float(re[0] - le[0])
    eye_dy = float(re[1] - le[1])
    tilt = float(np.degrees(np.arctan2(eye_dy, eye_dx)))
    nrm = float(np.hypot(eye_dx, eye_dy)) + 1e-6
    ux, uy = -eye_dy / nrm, eye_dx / nrm
    if uy > 0:
        ux, uy = -ux, -uy
    brow_off = 0.35 * iod
    side = np.array([eye_dx, eye_dy], dtype=np.float64) / nrm
    up = np.array([ux, uy], dtype=np.float64)
    lb = le + up * brow_off - side * (0.08 * iod)
    rb = re + up * brow_off + side * (0.08 * iod)
    eye_in_box = None
    forehead = None
    if box is not None and len(box) >= 4:
        _bx, by, _bw, bh = [float(v) for v in box[:4]]
        if bh > 1:
            eye_in_box = (eye_y - by) / bh
        forehead = (eye_y - by) / iod

    points = []
    for (pid, zh, symbol, part), (x, y) in zip(_YUNET_POINT_META, pts):
        points.append(
            {
                "id": pid,
                "zh": zh,
                "symbol": symbol,
                "part": part,
                "algo": "YuNet",
                "inferred": False,
                "x": round(float(x), 1),
                "y": round(float(y), 1),
            }
        )
    points.append(
        {
            "id": "lb",
            "zh": "左眉区",
            "symbol": "b₁",
            "part": "brow",
            "algo": "眉区估",
            "inferred": True,
            "x": round(float(lb[0]), 1),
            "y": round(float(lb[1]), 1),
        }
    )
    points.append(
        {
            "id": "rb",
            "zh": "右眉区",
            "symbol": "b₂",
            "part": "brow",
            "algo": "眉区估",
            "inferred": True,
            "x": round(float(rb[0]), 1),
            "y": round(float(rb[1]), 1),
        }
    )

    # 真实正脸的 mouth_lift 中心约 -0.23；宽嘴 + 偏上 → AU12，口鼻距大 → 张口
    if mouth_w >= 0.90 and mouth_lift >= -0.21:
        mouth_text, mouth_sym, mouth_hint = "唇角拉开上扬", "AU12", "喜悦倾向"
    elif mouth_drop >= 0.54 and mouth_w <= 0.82:
        mouth_text, mouth_sym, mouth_hint = "口部下移张开", "AU27≈", "惊讶倾向"
    elif mouth_lift <= -0.29:
        mouth_text, mouth_sym, mouth_hint = "唇角偏低", "AU15", "低落倾向"
    elif mouth_w <= 0.79:
        mouth_text, mouth_sym, mouth_hint = "嘴角偏紧", "w/IOD", "抿嘴"
    else:
        mouth_text, mouth_sym, mouth_hint = "嘴角开合中等", "w/IOD", "口型平稳"
    if abs(tilt) >= 8:
        eye_text, eye_hint = "眼线倾斜", "头部侧倾"
    else:
        eye_text, eye_hint = "眼线水平", "正对镜头"
    if forehead is not None and forehead >= 1.20:
        brow_text, brow_sym, brow_hint = "眉区上提", "AU1/2≈", "挑眉倾向"
    elif forehead is not None and forehead <= 1.00:
        brow_text, brow_sym, brow_hint = "眉区偏低", "AU4≈", "皱眉倾向"
    else:
        brow_text, brow_sym, brow_hint = "眉区平稳", "b₁b₂", "眉形稳定"

    cues = [
        {
            "part": "mouth",
            "zh": "嘴巴",
            "text": mouth_text,
            "hint": mouth_hint,
            "symbol": mouth_sym,
            "algo": "FACS",
            "value": round(mouth_w, 3),
            "lift": round(float(mouth_lift), 3),
            "drop": round(float(mouth_drop), 3),
        },
        {
            "part": "eye",
            "zh": "眼睛",
            "text": eye_text,
            "hint": eye_hint,
            "symbol": "IOD",
            "algo": "YuNet p₁p₂",
            "value": round(iod, 1),
            "tilt": round(tilt, 1),
        },
        {
            "part": "brow",
            "zh": "眉毛",
            "text": brow_text,
            "hint": brow_hint,
            "symbol": brow_sym,
            "algo": "眉区估",
            "value": None if forehead is None else round(float(forehead), 3),
        },
    ]
    return {
        "landmarks": [[round(float(x), 1), round(float(y), 1)] for x, y in pts],
        "points": points,
        "cues": cues,
        "metrics": {
            "iod": round(iod, 1),
            "mouth_w": round(mouth_w, 3),
            "mouth_lift": round(float(mouth_lift), 3),
            "mouth_drop": round(float(mouth_drop), 3),
            "tilt": round(tilt, 1),
            "forehead": None if forehead is None else round(float(forehead), 3),
        },
    }


# 课堂演示模式（网页设置里打开，按请求传入）：孩子扮表情时惊讶张口不够大、平静时忍不住笑
DEMO_MODE: contextvars.ContextVar[bool] = contextvars.ContextVar("emotune_demo_mode", default=False)
# 实时识别快速模式（来源带 -live 时由 app 设置）：单次前向 + HSEmotion 单裁剪，不做 4 向 TTA
FAST_MODE: contextvars.ContextVar[bool] = contextvars.ContextVar("emotune_fast_mode", default=False)
# 由 static/demo 21 张示例量出：喜悦嘴宽 0.89–0.91，平静 0.84–0.87；惊讶张口 0.58–0.69，平静 ≤0.47
DEMO_SMILE_W = 0.88
DEMO_OPEN_DROP = 0.52


def _demo_adjust(vec: np.ndarray, geo: dict) -> np.ndarray:
    """喜悦要真的笑开（嘴宽够）才算；张口够就把平静、喜悦的一部分分给惊讶。"""
    if not geo:
        return vec
    i_hap, i_neu, i_sur = 3, 4, 6
    mouth_w = float(geo.get("mouth_w") or 0.0)
    mouth_drop = float(geo.get("mouth_drop") or 0.0)
    if vec[i_hap] >= 0.12 and mouth_w < DEMO_SMILE_W:
        move = vec[i_hap] * 0.70
        vec[i_hap] -= move
        vec[i_neu] += move
    if mouth_drop >= DEMO_OPEN_DROP:
        move = vec[i_neu] * 0.45 + vec[i_hap] * 0.50
        vec[i_neu] -= vec[i_neu] * 0.45
        vec[i_hap] -= vec[i_hap] * 0.50
        vec[i_sur] += move
    return vec


def calibrate_live_vec(p: np.ndarray, metrics: Optional[dict] = None) -> np.ndarray:
    """把张嘴说话、轻微笑意从惊讶/喜悦拉回平静。

    MobileFaceNet 与 AffectNet 野外模型都容易把休息脸、说话口型判成 surprise / happy。
    用 YuNet 五点几何做否决：没有张口+挑眉不给惊讶，没有拉开上扬不给喜悦。
    标签顺序与 MODEL_LABELS 一致：angry, disgust, fear, happy, neutral, sad, surprise。
    """
    vec = np.asarray(p, dtype=np.float64).reshape(-1)
    if vec.size != 7:
        return vec
    total = float(vec.sum())
    if total <= 0:
        return np.full(7, 1.0 / 7.0)
    vec = vec / total
    geo = metrics or {}
    has_geo = bool(geo)
    mouth_w = float(geo.get("mouth_w") or 0.0)
    mouth_drop = float(geo.get("mouth_drop") or 0.0)
    mouth_lift = float(geo.get("mouth_lift") or 0.0)
    forehead = geo.get("forehead")
    i_sur, i_hap, i_neu, i_fear = 6, 3, 4, 2
    # YuNet 只有嘴角，张口主要看口鼻距；合成惊讶图嘴宽往往仍约 0.80
    open_jaw = mouth_w >= 1.02 or mouth_drop >= 0.475
    clear_smile = mouth_w >= 0.88 and mouth_lift >= -0.22

    if vec[i_sur] >= 0.20:
        margin = float(vec[i_sur] - max(vec[i_neu], vec[i_fear]))
        if has_geo and not open_jaw:
            if margin < 0.18:
                move = vec[i_sur] * 0.70
            elif margin < 0.36:
                move = vec[i_sur] * 0.42
            else:
                move = 0.0
            if move:
                vec[i_sur] -= move
                vec[i_neu] += move * 0.90
                vec[i_fear] += move * 0.10
        elif (not has_geo) and margin < 0.14:
            move = vec[i_sur] * 0.32
            vec[i_sur] -= move
            vec[i_neu] += move

    if vec[i_hap] >= 0.20:
        margin = float(vec[i_hap] - vec[i_neu])
        if has_geo and not clear_smile:
            if margin < 0.14:
                move = vec[i_hap] * 0.52
            elif margin < 0.24:
                move = vec[i_hap] * 0.22
            else:
                move = 0.0
            if move:
                vec[i_hap] -= move
                vec[i_neu] += move
        elif (not has_geo) and margin < 0.12:
            move = vec[i_hap] * 0.28
            vec[i_hap] -= move
            vec[i_neu] += move

    if DEMO_MODE.get():
        vec = _demo_adjust(vec, geo)
    vec = np.clip(vec, 1e-12, None)
    return vec / vec.sum()


def _similarity_from_landmarks(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """非反射相似变换（scale + rotation + translation），对齐官方实现。"""
    src = np.asarray(src, dtype=np.float64).reshape(-1, 2)
    dst = np.asarray(dst, dtype=np.float64).reshape(-1, 2)
    n = src.shape[0]
    x = dst[:, 0:1]
    y = dst[:, 1:2]
    tmp1 = np.hstack([x, y, np.ones((n, 1)), np.zeros((n, 1))])
    tmp2 = np.hstack([y, -x, np.zeros((n, 1)), np.ones((n, 1))])
    X = np.vstack([tmp1, tmp2])
    U = np.vstack([src[:, 0:1], src[:, 1:2]])
    r, _, _, _ = np.linalg.lstsq(X, U, rcond=-1)
    r = np.squeeze(r)
    sc, ss, tx, ty = r
    tinv = np.array([[sc, -ss, 0.0], [ss, sc, 0.0], [tx, ty, 1.0]], dtype=np.float64)
    t = np.linalg.inv(tinv)
    t[:, 2] = np.array([0.0, 0.0, 1.0])
    return t[:, 0:2].T.astype(np.float32)


def align_face(image_bgr: np.ndarray, landmarks5: np.ndarray, size: int = 112) -> np.ndarray:
    src = np.asarray(landmarks5, dtype=np.float64).reshape(5, 2)
    tfm = _similarity_from_landmarks(src, _STD_POINTS)
    return cv2.warpAffine(image_bgr, tfm, (size, size), flags=cv2.INTER_LINEAR)


def encode_face_crop(image_bgr: np.ndarray, box, size: int = 280) -> str:
    """把检出的人脸裁成方图，供界面对照判断结果。"""
    crop = crop_face(image_bgr, box, size=size, margin=0.38)
    ok, buf = cv2.imencode(".jpg", crop, [int(cv2.IMWRITE_JPEG_QUALITY), 84])
    if not ok or buf is None:
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("ascii")


def crop_face(image_bgr: np.ndarray, box, size: int = 112, margin: float = 0.22) -> np.ndarray:
    h, w = image_bgr.shape[:2]
    x, y, bw, bh = [float(v) for v in box]
    cx, cy = x + bw / 2.0, y + bh / 2.0
    side = max(bw, bh) * (1.0 + margin)
    x1 = int(max(0, cx - side / 2.0))
    y1 = int(max(0, cy - side / 2.0))
    x2 = int(min(w, cx + side / 2.0))
    y2 = int(min(h, cy + side / 2.0))
    crop = image_bgr[y1:y2, x1:x2]
    if crop.size == 0:
        crop = image_bgr
    return cv2.resize(crop, (size, size), interpolation=cv2.INTER_LINEAR)


def decode_image(data: bytes) -> Optional[np.ndarray]:
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


def normalize_face_mode(raw: str | None) -> str:
    text = str(raw or "").strip().lower()
    aliases = {
        "solo": "solo",
        "single": "solo",
        "one": "solo",
        "precision": "solo",
        "near": "solo",
        "精检": "solo",
        "单人": "solo",
        "crowd": "crowd",
        "multi": "crowd",
        "far": "crowd",
        "多人": "crowd",
        "远场": "crowd",
        "远景": "crowd",
    }
    return aliases.get(text, DEFAULT_FACE_MODE if text in ("", "auto", "default") else DEFAULT_FACE_MODE)


def face_mode_cfg(raw: str | None) -> dict:
    mode = normalize_face_mode(raw)
    return dict(FACE_MODES.get(mode) or FACE_MODES[DEFAULT_FACE_MODE])


def public_face_modes() -> list[dict]:
    order = ("solo", "crowd")
    out = []
    for key in order:
        item = FACE_MODES.get(key) or {}
        out.append(
            {
                "id": item.get("id") or key,
                "zh": item.get("zh") or "",
                "name": item.get("name") or "",
                "blurb": item.get("blurb") or "",
                "default": key == DEFAULT_FACE_MODE,
            }
        )
    return out


def resize_for_detect(image_bgr: np.ndarray, max_side: int = MAX_IMAGE_SIDE):
    h, w = image_bgr.shape[:2]
    scale = 1.0
    if max(h, w) > max_side:
        scale = max_side / float(max(h, w))
        image_bgr = cv2.resize(
            image_bgr,
            (int(w * scale), int(h * scale)),
            interpolation=cv2.INTER_AREA,
        )
    return image_bgr, scale


class EmotionRecognizer:
    """YuNet 检测 + MobileFaceNet 表情分类，模型在启动时加载一次。"""

    def __init__(self) -> None:
        yunet_path = MODEL_DIR / YUNET_FILE
        fer_path = MODEL_DIR / FER_FILE
        if not yunet_path.exists():
            raise FileNotFoundError(f"缺少人脸检测模型: {yunet_path}")
        if not fer_path.exists():
            raise FileNotFoundError(f"缺少表情识别模型: {fer_path}")

        # 给 OpenCV 留 2 线程，其余给 onnxruntime，避免 CPU 抢核卡顿
        try:
            cv2.setNumThreads(2)
        except Exception:
            pass
        # Windows 下 OpenCV C++ 读盘不支持中文路径，改为内存加载
        yunet_bytes = yunet_path.read_bytes()
        yunet_buf = np.frombuffer(yunet_bytes, dtype=np.uint8).copy()
        tracker_buf = np.frombuffer(yunet_bytes, dtype=np.uint8).copy()
        fer_buf = np.frombuffer(fer_path.read_bytes(), dtype=np.uint8).copy()
        self.detector = cv2.FaceDetectorYN.create(
            "onnx",
            yunet_buf,
            np.array([], dtype=np.uint8),
            (640, 640),
            float(YUNET_SCORE),
            float(YUNET_NMS),
            50,
        )
        # 独立检测器给实时框用，避免和精检抢同一把 YuNet
        self.tracker = cv2.FaceDetectorYN.create(
            "onnx",
            tracker_buf,
            np.array([], dtype=np.uint8),
            (640, 640),
            0.50,
            0.3,
            16,
        )
        self.net = cv2.dnn.readNetFromONNX(fer_buf)
        self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        self._haar = None
        self._clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        self.hse = None
        self.hse_input = "input"
        self._lock = threading.RLock()
        self._track_lock = threading.Lock()
        self._last_track_faces: list[dict] = []
        self._track_ema: Optional[dict] = None
        self._track_n = 0
        self._load_hsemotion()
        logger.info("情绪识别模型已加载")

    def _load_hsemotion(self) -> None:
        hse_path = MODEL_DIR / HSE_FILE
        if not hse_path.exists() or hse_path.stat().st_size < 1_000_000:
            logger.warning("未找到 HSEmotion 模型，单人精检仍用 MobileFaceNet TTA")
            return
        try:
            import onnxruntime as ort

            opts = ort.SessionOptions()
            cpu_n = int(os.cpu_count() or 2)
            opts.intra_op_num_threads = min(4, max(1, cpu_n // 2))
            opts.inter_op_num_threads = 1
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self.hse = ort.InferenceSession(
                str(hse_path),
                sess_options=opts,
                providers=["CPUExecutionProvider"],
            )
            self.hse_input = self.hse.get_inputs()[0].name
            logger.info(
                "HSEmotion EfficientNet-B0 已加载（CPU） available=%s session=%s",
                ort.get_available_providers(),
                self.hse.get_providers(),
            )
        except Exception:
            self.hse = None
            logger.exception("HSEmotion 加载失败，单人精检仍用 MobileFaceNet TTA")

    def _haar_cascade(self):
        if self._haar is None:
            xml = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self._haar = cv2.CascadeClassifier(xml)
        return self._haar

    def _apply_detector(self, cfg: dict) -> None:
        self.detector.setScoreThreshold(float(cfg.get("score") or YUNET_SCORE))
        self.detector.setNMSThreshold(float(cfg.get("nms") or YUNET_NMS))
        top_k = int(cfg.get("top_k") or 50)
        if hasattr(self.detector, "setTopK"):
            self.detector.setTopK(top_k)

    def _parse_yunet(self, faces, inv: float, score_min: float, min_side: float) -> list[dict]:
        results = []
        if faces is None:
            return results
        floor = max(8.0, float(min_side) * 0.45)
        for row in faces:
            row = np.asarray(row, dtype=np.float32).reshape(-1)
            if row.size < 15:
                continue
            x, y, bw, bh = row[:4] * inv
            lm = row[4:14].reshape(5, 2) * inv
            score = float(row[14])
            if score < score_min:
                continue
            if min(float(bw), float(bh)) < floor:
                continue
            results.append(
                {
                    "box": [float(x), float(y), float(bw), float(bh)],
                    "landmarks": lm.tolist(),
                    "score": score,
                    "area": float(max(bw, 1.0) * max(bh, 1.0)),
                }
            )
        return results

    def _yunet_detect(self, img: np.ndarray, inv: float, score_min: float, min_side: float) -> list[dict]:
        h, w = img.shape[:2]
        if h < 12 or w < 12:
            return []
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(img)
        return self._parse_yunet(faces, inv, score_min, min_side)

    def detect_faces(self, image_bgr: np.ndarray, mode: str | None = None) -> list[dict]:
        cfg = face_mode_cfg(mode)
        img, scale = resize_for_detect(image_bgr, int(cfg.get("max_side") or MAX_IMAGE_SIDE))
        inv = 1.0 / scale if scale else 1.0
        score_min = float(cfg.get("score_min") or FACE_SCORE_MIN)
        min_face = float(cfg.get("min_face") or 14)
        self._apply_detector(cfg)
        results = self._yunet_detect(img, inv, score_min, min_face)

        # 单人精检：略降阈值再试一次，仍不用 Haar / 远景放大
        if not results and not cfg.get("upscale") and not cfg.get("haar"):
            loose = dict(cfg)
            loose["score"] = max(0.48, float(cfg.get("score") or 0.62) - 0.14)
            self._apply_detector(loose)
            results = self._yunet_detect(img, inv, max(0.42, score_min - 0.08), min_face)
            self._apply_detector(cfg)

        # 多人远场：一张都没有时放大再检，方便远景小脸
        if not results and cfg.get("upscale"):
            h, w = img.shape[:2]
            long_side = max(h, w)
            if long_side >= 80 and long_side < 1800:
                factor = min(1.85, 1800.0 / float(long_side))
                if factor > 1.2:
                    big = cv2.resize(
                        img,
                        (int(w * factor), int(h * factor)),
                        interpolation=cv2.INTER_CUBIC,
                    )
                    results = self._yunet_detect(big, inv / factor, score_min, min_face)

        if results:
            dual = float(cfg.get("dual_score") or 0.68)
            self.detector.setScoreThreshold(dual)
            tight = self._yunet_detect(img, inv, min(score_min, dual * 0.7), min_face)
            self._apply_detector(cfg)
            for face in results:
                best = None
                best_iou = 0.4
                for other in tight:
                    v = self._box_iou(face["box"], other["box"])
                    if v > best_iou:
                        best_iou = v
                        best = other
                if best:
                    face["box"] = best["box"]
                    face["landmarks"] = best["landmarks"]
                    face["score"] = max(float(face["score"]), float(best["score"]))
                    face["area"] = best["area"]
            results.sort(key=lambda f: (f["area"], f["score"]), reverse=True)
            return self._prune_faces(results, min_face)[: int(cfg.get("face_max") or FACE_MAX)]

        if cfg.get("haar"):
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            haar_faces = self._haar_cascade().detectMultiScale(gray, 1.08, 4, minSize=(18, 18))
            for (x, y, bw, bh) in haar_faces:
                results.append(
                    {
                        "box": [float(x) * inv, float(y) * inv, float(bw) * inv, float(bh) * inv],
                        "landmarks": None,
                        "score": 0.55,
                        "area": float(bw * bh) * inv * inv,
                    }
                )
            results.sort(key=lambda f: f["area"], reverse=True)
            return self._prune_faces(results, min_face)[: int(cfg.get("face_max") or FACE_MAX)]
        return []

    def _prune_faces(self, faces: list[dict], min_face: float = 14) -> list[dict]:
        if not faces:
            return faces
        kept = []
        for face in faces:
            x, y, bw, bh = face["box"]
            if min(bw, bh) < float(min_face):
                continue
            overlap = False
            for other in kept:
                if self._box_iou(face["box"], other["box"]) >= 0.45:
                    overlap = True
                    break
            if not overlap:
                kept.append(face)
        return kept or faces[:1]

    def _box_iou(self, a, b) -> float:
        ax, ay, aw, ah = [float(v) for v in a]
        bx, by, bw, bh = [float(v) for v in b]
        x1, y1 = max(ax, bx), max(ay, by)
        x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
        inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        ua = aw * ah + bw * bh - inter
        return inter / ua if ua > 0 else 0.0

    def _refine_face(self, image_bgr: np.ndarray, face: dict) -> dict:
        """在人脸附近再检一次，对齐关键点，FER 更稳。"""
        h, w = image_bgr.shape[:2]
        x, y, bw, bh = [float(v) for v in face["box"]]
        cx, cy = x + bw / 2.0, y + bh / 2.0
        side = max(bw, bh) * 1.45
        x1 = int(max(0, cx - side / 2.0))
        y1 = int(max(0, cy - side / 2.0))
        x2 = int(min(w, cx + side / 2.0))
        y2 = int(min(h, cy + side / 2.0))
        crop = image_bgr[y1:y2, x1:x2]
        if crop.size == 0:
            return face
        ch, cw = crop.shape[:2]
        target = 320.0
        scale = target / float(max(ch, cw, 1))
        small = cv2.resize(
            crop,
            (max(12, int(cw * scale)), max(12, int(ch * scale))),
            interpolation=cv2.INTER_LINEAR if scale < 1 else cv2.INTER_CUBIC,
        )
        dets = self._yunet_detect(small, 1.0, 0.40, 18.0)
        if not dets:
            return face
        best = max(dets, key=lambda f: f["area"])
        inv = 1.0 / scale
        bx, by, bbw, bbh = best["box"]
        out = dict(face)
        out["box"] = [bx * inv + x1, by * inv + y1, bbw * inv, bbh * inv]
        out["area"] = float(max(bbw * inv, 1.0) * max(bbh * inv, 1.0))
        out["score"] = max(float(face.get("score") or 0.0), float(best.get("score") or 0.0))
        if best.get("landmarks"):
            out["landmarks"] = [[p[0] * inv + x1, p[1] * inv + y1] for p in best["landmarks"]]
        return out

    def _fer_blob(self, aligned_bgr: np.ndarray) -> np.ndarray:
        """与 OpenCV Zoo official preprocess 保持一致：RGB /255 -0.5 /0.5。"""
        image = cv2.cvtColor(aligned_bgr, cv2.COLOR_BGR2RGB)
        image = image.astype(np.float32) / 255.0
        image = (image - 0.5) / 0.5
        return cv2.dnn.blobFromImage(image)

    def _auto_light(self, image_bgr: np.ndarray) -> np.ndarray:
        """过暗或过曝时做轻度 CLAHE，不动正常光照，避免改变 RAF-DB 分布。"""
        if image_bgr is None or image_bgr.size == 0:
            return image_bgr
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        mean = float(gray.mean())
        if 62.0 <= mean <= 188.0:
            return image_bgr
        lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
        l_ch, a_ch, b_ch = cv2.split(lab)
        lab = cv2.merge([self._clahe.apply(l_ch), a_ch, b_ch])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    def _pad7(self, vec: np.ndarray) -> np.ndarray:
        out = np.zeros(7, dtype=np.float64)
        flat = np.asarray(vec, dtype=np.float64).reshape(-1)
        n = min(7, int(flat.size))
        out[:n] = flat[:n]
        return out

    def _mbf_logits(self, aligned_bgr: np.ndarray) -> np.ndarray:
        blob = self._fer_blob(aligned_bgr)
        self.net.setInput(blob, "data")
        try:
            out = self.net.forward("label")
        except cv2.error:
            out = self.net.forward()
        return self._pad7(out)

    def _mbf_tta_logits(self, aligned_bgr: np.ndarray) -> np.ndarray:
        h, w = aligned_bgr.shape[:2]
        views = [aligned_bgr, cv2.flip(aligned_bgr, 1)]
        center = (w * 0.5, h * 0.5)
        for ang in (-7.0, 7.0):
            rot = cv2.getRotationMatrix2D(center, ang, 1.0)
            views.append(
                cv2.warpAffine(
                    aligned_bgr,
                    rot,
                    (w, h),
                    flags=cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_REPLICATE,
                )
            )
        acc = np.zeros(7, dtype=np.float64)
        for view in views:
            acc += self._mbf_logits(view)
        return acc / float(len(views))

    def _hse_probs7(self, face_bgr: np.ndarray) -> Optional[np.ndarray]:
        """AffectNet-8 先 softmax，再把蔑视拆进厌恶与平静。"""
        if self.hse is None or face_bgr is None or face_bgr.size == 0:
            return None
        rgb = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2RGB)
        rgb = cv2.resize(rgb, (224, 224), interpolation=cv2.INTER_LINEAR)
        x = rgb.astype(np.float32) / 255.0
        x = (x - _HSE_MEAN) / _HSE_STD
        x = np.transpose(x, (2, 0, 1))[None]
        raw = self.hse.run(None, {self.hse_input: x})[0]
        logits8 = np.asarray(raw, dtype=np.float64).reshape(-1)
        if logits8.size < 8:
            return None
        p8 = _softmax(logits8)
        vec7 = np.zeros(7, dtype=np.float64)
        # 8: angry contempt disgust fear happy neutral sad surprise
        # 7: angry disgust fear happy neutral sad surprise
        vec7[0] = p8[0]
        vec7[1] = p8[2] + 0.55 * p8[1]
        vec7[2] = p8[3]
        vec7[3] = p8[4]
        vec7[4] = p8[5] + 0.45 * p8[1]
        vec7[5] = p8[6]
        vec7[6] = p8[7]
        total = float(vec7.sum())
        if total <= 0:
            return None
        return vec7 / total

    def _hse_ensemble_probs(self, image_bgr: np.ndarray, face: dict) -> Optional[np.ndarray]:
        if self.hse is None:
            return None
        acc = np.zeros(7, dtype=np.float64)
        n = 0
        for margin in (0.22, 0.34):
            crop = self._auto_light(crop_face(image_bgr, face["box"], size=224, margin=margin))
            for view in (crop, cv2.flip(crop, 1)):
                p = self._hse_probs7(view)
                if p is None:
                    continue
                acc += p
                n += 1
        if n == 0:
            return None
        return acc / float(n)

    def _fuse_probs(self, p_mbf: np.ndarray, p_hse: np.ndarray) -> np.ndarray:
        """两模型一致时加权平均；不一致时野外模型为主，避免 MobileFaceNet 过自信带偏摄像头。"""
        i_m = int(np.argmax(p_mbf))
        i_h = int(np.argmax(p_hse))
        order_m = np.argsort(p_mbf)
        order_h = np.argsort(p_hse)
        margin_m = float(p_mbf[order_m[-1]] - p_mbf[order_m[-2]])
        peak_m = float(p_mbf[i_m])
        hse_top2 = (int(order_h[-1]), int(order_h[-2]))
        if i_m == i_h:
            w_mbf = 0.46 + 0.14 * float(np.clip(margin_m / 0.50, 0.0, 1.0))
        elif i_m in hse_top2 and peak_m >= 0.85:
            w_mbf = 0.55
        elif peak_m >= 0.96 and margin_m >= 0.75:
            w_mbf = 0.68
        else:
            w_mbf = 0.26
        fused = w_mbf * p_mbf + (1.0 - w_mbf) * p_hse
        fused = np.clip(fused, 1e-12, None)
        return fused / fused.sum()

    def _landmark_prior(self, landmarks5: np.ndarray) -> np.ndarray:
        pts = np.asarray(landmarks5, dtype=np.float64).reshape(5, 2)
        le, re, nose, ml, mr = pts
        iod = float(np.linalg.norm(re - le)) + 1e-6
        mouth_w = float(np.linalg.norm(mr - ml)) / iod
        eye_y = 0.5 * (le[1] + re[1])
        mouth_y = 0.5 * (ml[1] + mr[1])
        mouth_lift = (eye_y + 0.82 * iod - mouth_y) / iod
        mouth_drop = (mouth_y - float(nose[1])) / iod
        prior = np.zeros(7, dtype=np.float64)
        if mouth_lift > 0.04 and mouth_w > 0.88:
            prior[3] += 0.08
        if mouth_lift < -0.34:
            prior[5] += 0.07
        if mouth_w > 1.18 and mouth_drop > 0.56:
            prior[6] += 0.07
        return prior

    def classify_face(self, image_bgr: np.ndarray, face: dict, precision: bool = False) -> dict:
        if face.get("landmarks"):
            aligned = align_face(image_bgr, np.array(face["landmarks"], dtype=np.float64))
        else:
            aligned = crop_face(image_bgr, face["box"])
        if precision and FAST_MODE.get():
            aligned = self._auto_light(aligned)
            p = _softmax(self._mbf_logits(aligned), temperature=1.55)
            if self.hse is not None:
                crop = self._auto_light(crop_face(image_bgr, face["box"], size=224, margin=0.28))
                p_hse = self._hse_probs7(crop)
                if p_hse is not None:
                    p = self._fuse_probs(p, p_hse)
        elif precision:
            aligned = self._auto_light(aligned)
            p_mbf = _softmax(self._mbf_tta_logits(aligned), temperature=1.55)
            p = p_mbf
            if self.hse is not None:
                p_hse = self._hse_ensemble_probs(image_bgr, face)
                if p_hse is not None:
                    p = self._fuse_probs(p_mbf, p_hse)
            if face.get("landmarks"):
                order = np.argsort(p)
                margin = float(p[order[-1]] - p[order[-2]])
                if margin < 0.22:
                    prior = self._landmark_prior(np.array(face["landmarks"], dtype=np.float64))
                    p = np.clip(p + prior, 1e-12, None)
                    p = p / p.sum()
        else:
            p = _softmax(self._mbf_logits(aligned))
        metrics = {}
        if face.get("landmarks"):
            metrics = landmark_cues(face["landmarks"], face.get("box")).get("metrics") or {}
        p = calibrate_live_vec(p, metrics)
        scores = self._scores_from_vec(p)
        emo = self._emotion_from_id(scores[0]["id"], scores)
        if precision and len(scores) >= 2:
            margin = float(scores[0]["prob"] - scores[1]["prob"])
            if margin < 0.10:
                emo["low_confidence"] = True
        return emo

    def _ema_track_vec(self, face: dict, p: np.ndarray) -> np.ndarray:
        """实时框跨帧平滑七类概率，减少摄像头微抖换标签。"""
        now = time.perf_counter()
        p = np.asarray(p, dtype=np.float64).reshape(-1)
        if p.size != 7:
            p = self._pad7(p)
        s = float(p.sum())
        p = p / s if s > 0 else np.full(7, 1.0 / 7.0)
        prev = self._track_ema
        if prev is not None:
            iou = self._box_iou(face.get("box") or [0, 0, 0, 0], prev.get("box") or [0, 0, 0, 0])
            dt = now - float(prev.get("t") or 0.0)
            if iou >= 0.32 and dt < 1.2:
                alpha = 0.22 if dt < 0.35 else 0.38
                q = np.asarray(prev.get("p"), dtype=np.float64).reshape(-1)
                if q.size == 7:
                    p = alpha * p + (1.0 - alpha) * q
                    p = np.clip(p, 1e-12, None)
                    p = p / p.sum()
        self._track_ema = {"box": list(face.get("box") or [0, 0, 0, 0]), "p": p.copy(), "t": now}
        return p

    def classify_face_live(self, image_bgr: np.ndarray, face: dict, use_hse: bool = True) -> dict:
        """实时路径：单次 MobileFaceNet + 可选一次 HSEmotion，再做时间平滑。不做 4 向 TTA。"""
        if face.get("landmarks"):
            aligned = align_face(image_bgr, np.array(face["landmarks"], dtype=np.float64))
        else:
            aligned = crop_face(image_bgr, face["box"])
        aligned = self._auto_light(aligned)
        p_mbf = _softmax(self._mbf_logits(aligned), temperature=1.40)
        p = p_mbf
        if use_hse and self.hse is not None:
            crop = self._auto_light(crop_face(image_bgr, face["box"], size=224, margin=0.28))
            p_hse = self._hse_probs7(crop)
            if p_hse is not None:
                p = self._fuse_probs(p_mbf, p_hse)
        p = self._ema_track_vec(face, p)
        metrics = {}
        if face.get("landmarks"):
            metrics = landmark_cues(face["landmarks"], face.get("box")).get("metrics") or {}
        p = calibrate_live_vec(p, metrics)
        if self._track_ema is not None:
            self._track_ema["p"] = p.copy()
        scores = self._scores_from_vec(p)
        return self._emotion_from_id(scores[0]["id"], scores)

    def _scores_from_vec(self, vec: np.ndarray) -> list[dict]:
        order = np.argsort(vec)[::-1]
        scores = []
        for idx in order:
            eid = INDEX_TO_ID[int(idx)]
            meta = EMOTIONS[eid]
            scores.append({"id": eid, "zh": meta["zh"], "name": meta["name"], "prob": float(vec[idx])})
        return scores

    def _emotion_from_id(self, eid: str, scores: list[dict], extra: Optional[dict] = None) -> dict:
        meta = EMOTIONS[eid]
        top = next((s for s in scores if s["id"] == eid), scores[0] if scores else None)
        prob = float(top["prob"]) if top else 0.0
        out = {
            "id": eid,
            "zh": meta["zh"],
            "name": meta["name"],
            "english": meta["english"],
            "prob": prob,
            "scores": scores,
            "low_confidence": prob < EMOTION_CONF_WARN,
            "genre": meta["genre"],
            "copy": meta["copy"],
            "color": meta["color"],
        }
        if extra:
            out.update(extra)
        return out

    def _majority(self, classified: list[dict]) -> tuple[dict, dict, dict]:
        counts: dict[str, int] = defaultdict(int)
        areas: dict[str, float] = defaultdict(float)
        probs: dict[str, float] = defaultdict(float)
        acc = np.zeros(7, dtype=np.float64)
        for item in classified:
            emo = item["emotion"]
            eid = emo["id"]
            counts[eid] += 1
            areas[eid] += float(item.get("area") or 0.0)
            probs[eid] += float(emo.get("prob") or 0.0)
            vec = np.zeros(7, dtype=np.float64)
            for s in emo.get("scores") or []:
                if s.get("id") in MODEL_LABELS:
                    vec[MODEL_LABELS.index(s["id"])] = float(s.get("prob") or 0.0)
            acc += vec
        n = max(1, len(classified))
        acc = acc / float(n)
        winner = max(counts.keys(), key=lambda k: (counts[k], areas[k], probs[k]))
        scores = self._scores_from_vec(acc)
        maj = counts[winner]
        mean_prob = probs[winner] / max(1, maj)
        emotion = self._emotion_from_id(
            winner,
            scores,
            extra={"prob": float(mean_prob), "low_confidence": mean_prob < EMOTION_CONF_WARN},
        )
        majority_faces = [f for f in classified if f["emotion"]["id"] == winner]
        primary = max(majority_faces or classified, key=lambda f: float(f.get("area") or 0.0))
        vote = {
            "id": winner,
            "zh": emotion["zh"],
            "name": emotion["name"],
            "total": len(classified),
            "majority": maj,
            "counts": {k: int(v) for k, v in counts.items()},
        }
        return emotion, vote, primary

    def _public_face(self, item: dict, primary: bool) -> dict:
        emo = item.get("emotion") or {}
        out = {
            "box": [round(float(v), 1) for v in item["box"]],
            "score": round(float(item.get("score") or 0.0), 3),
            "area": round(float(item.get("area") or 0.0), 1),
            "primary": bool(primary),
            "emotion": {
                "id": emo.get("id"),
                "zh": emo.get("zh"),
                "name": emo.get("name"),
                "prob": round(float(emo.get("prob") or 0.0), 4),
                "color": emo.get("color"),
            },
        }
        geo = landmark_cues(item.get("landmarks"), item.get("box"))
        if geo.get("points"):
            out["landmarks"] = geo["landmarks"]
            out["points"] = geo["points"]
            out["cues"] = geo["cues"]
            out["metrics"] = geo["metrics"]
        return out

    def predict_bgr(self, image_bgr: np.ndarray, want_crop: bool = True, mode: str | None = None) -> dict:
        with self._lock:
            return self._predict_bgr(image_bgr, want_crop=want_crop, mode=mode)

    def _predict_bgr(self, image_bgr: np.ndarray, want_crop: bool = True, mode: str | None = None) -> dict:
        t0 = time.perf_counter()
        cfg = face_mode_cfg(mode)
        if image_bgr is None or image_bgr.size == 0:
            return {
                "ok": False,
                "error": "图像为空",
                "code": "NO_IMAGE",
                "elapsed_ms": 0,
                "faces": [],
                "vote": None,
                "face_mode": cfg["id"],
            }
        faces = self.detect_faces(image_bgr, cfg["id"])
        if not faces:
            elapsed = (time.perf_counter() - t0) * 1000.0
            hint = (
                "未检测到清晰近景人脸。请正对镜头、光线均匀；若要检远景或多张脸，请切到「多人远场」。"
                if cfg["id"] == "solo"
                else "未检测到人脸。请正对镜头、保证光线充足，或换一张更清晰的正面照片。"
            )
            return {
                "ok": False,
                "error": hint,
                "code": "NO_FACE",
                "elapsed_ms": round(elapsed, 1),
                "faces": [],
                "vote": None,
                "face_count": 0,
                "face_mode": cfg["id"],
            }
        classified = []
        limit = int(cfg.get("face_max") or FACE_MAX)
        precision = cfg["id"] == "solo"
        for face in faces[:limit]:
            chosen = face
            refined = self._refine_face(image_bgr, face)
            if precision:
                if refined is not face:
                    chosen = refined
                emo = self.classify_face(image_bgr, chosen, precision=True)
            else:
                emo = self.classify_face(image_bgr, face, precision=False)
                if refined is not face:
                    emo_ref = self.classify_face(image_bgr, refined, precision=False)
                    if float(emo_ref.get("prob") or 0) > float(emo.get("prob") or 0):
                        emo = emo_ref
                        chosen = refined
            classified.append({**chosen, "emotion": emo})
        if cfg.get("majority") and len(classified) > 1:
            emotion, vote, primary = self._majority(classified)
        else:
            primary = max(classified, key=lambda f: (float(f.get("area") or 0.0), float(f.get("score") or 0.0)))
            emotion = dict(primary["emotion"])
            vote = {
                "id": emotion["id"],
                "zh": emotion["zh"],
                "name": emotion["name"],
                "total": len(classified),
                "majority": 1,
                "counts": {emotion["id"]: 1},
                "mode": cfg["id"],
            }
        vote["mode"] = cfg["id"]
        elapsed = (time.perf_counter() - t0) * 1000.0
        h, w = image_bgr.shape[:2]
        crop = encode_face_crop(image_bgr, primary["box"]) if want_crop else ""
        boxes = [self._public_face(item, item is primary) for item in classified]
        return {
            "ok": True,
            "emotion": emotion,
            "vote": vote,
            "face": {
                "box": [round(v, 1) for v in primary["box"]],
                "score": round(float(primary["score"]), 3),
                "image_size": [int(w), int(h)],
                "crop": crop,
            },
            "faces": boxes,
            "face_count": len(classified),
            "face_mode": cfg["id"],
            "elapsed_ms": round(elapsed, 1),
        }

    def _detect_faces_fast(self, image_bgr: np.ndarray, mode: str | None = None) -> list[dict]:
        """实时框：缩小图、单次 YuNet，不做精检双阈值 / Haar / 远景放大。"""
        cfg = face_mode_cfg(mode)
        solo = cfg["id"] == "solo"
        max_side = 640 if solo else 800
        img, scale = resize_for_detect(image_bgr, max_side)
        inv = 1.0 / scale if scale else 1.0
        h, w = img.shape[:2]
        if h < 12 or w < 12:
            return []
        score = 0.50 if solo else 0.38
        score_min = 0.42 if solo else 0.30
        min_face = 24.0 if solo else 14.0
        top_k = 8 if solo else 16
        self.tracker.setScoreThreshold(float(score))
        self.tracker.setNMSThreshold(0.3)
        if hasattr(self.tracker, "setTopK"):
            self.tracker.setTopK(int(top_k))
        self.tracker.setInputSize((w, h))
        _, faces = self.tracker.detect(img)
        results = self._parse_yunet(faces, inv, score_min, min_face)
        results.sort(key=lambda f: (f["area"], f["score"]), reverse=True)
        limit = 1 if solo else int(cfg.get("face_max") or FACE_MAX)
        return self._prune_faces(results, min_face)[:limit]

    def _reuse_track_emotion(self, face: dict) -> Optional[dict]:
        best = None
        best_iou = 0.32
        for prev in self._last_track_faces:
            v = self._box_iou(face["box"], prev.get("box") or [0, 0, 0, 0])
            if v > best_iou:
                best_iou = v
                best = prev
        if best and best.get("emotion"):
            return dict(best["emotion"])
        if len(self._last_track_faces) == 1 and self._last_track_faces[0].get("emotion"):
            return dict(self._last_track_faces[0]["emotion"])
        return None

    def predict_track_bgr(self, image_bgr: np.ndarray, mode: str | None = None) -> dict:
        t0 = time.perf_counter()
        cfg = face_mode_cfg(mode)
        empty = {
            "ok": False,
            "elapsed_ms": 0,
            "faces": [],
            "vote": None,
            "face_mode": cfg["id"],
            "track": True,
        }
        if image_bgr is None or image_bgr.size == 0:
            empty.update({"error": "图像为空", "code": "NO_IMAGE"})
            return empty
        with self._track_lock:
            faces = self._detect_faces_fast(image_bgr, cfg["id"])
        if not faces:
            elapsed = (time.perf_counter() - t0) * 1000.0
            hint = (
                "未检测到清晰近景人脸。请正对镜头、光线均匀；若要检远景或多张脸，请切到「多人远场」。"
                if cfg["id"] == "solo"
                else "未检测到人脸。请正对镜头、保证光线充足，或换一张更清晰的正面照片。"
            )
            self._last_track_faces = []
            self._track_ema = None
            empty.update(
                {
                    "error": hint,
                    "code": "NO_FACE",
                    "elapsed_ms": round(elapsed, 1),
                    "face_count": 0,
                }
            )
            return empty
        classified = []
        got_fer = self._lock.acquire(blocking=True, timeout=0.02)
        try:
            now = time.perf_counter()
            ema = self._track_ema
            for face in faces:
                reuse = self._reuse_track_emotion(face)
                stable = False
                if reuse and ema is not None:
                    iou_e = self._box_iou(face["box"], ema.get("box") or [0, 0, 0, 0])
                    if iou_e >= 0.78 and (now - float(ema.get("t") or 0.0)) < 0.13:
                        stable = True
                emo = None
                if got_fer and not stable:
                    self._track_n += 1
                    emo = self.classify_face_live(image_bgr, face, use_hse=(self._track_n % 2 == 1))
                elif reuse:
                    emo = reuse
                    if ema is not None:
                        ema["box"] = list(face["box"])
                        ema["t"] = now
                if emo is None:
                    meta = EMOTIONS["neutral"]
                    emo = {
                        "id": "neutral",
                        "zh": meta["zh"],
                        "name": meta["name"],
                        "prob": 0.0,
                        "color": meta["color"],
                    }
                classified.append({**face, "emotion": emo})
        finally:
            if got_fer:
                self._lock.release()
        if cfg.get("majority") and len(classified) > 1:
            emotion, vote, primary = self._majority(classified)
        else:
            primary = max(classified, key=lambda f: (float(f.get("area") or 0.0), float(f.get("score") or 0.0)))
            emotion = dict(primary["emotion"])
            vote = {
                "id": emotion["id"],
                "zh": emotion["zh"],
                "name": emotion["name"],
                "total": len(classified),
                "majority": 1,
                "counts": {emotion["id"]: 1},
                "mode": cfg["id"],
            }
        vote["mode"] = cfg["id"]
        elapsed = (time.perf_counter() - t0) * 1000.0
        h, w = image_bgr.shape[:2]
        boxes = [self._public_face(item, item is primary) for item in classified]
        self._last_track_faces = classified
        return {
            "ok": True,
            "emotion": emotion,
            "vote": vote,
            "face": {
                "box": [round(v, 1) for v in primary["box"]],
                "score": round(float(primary["score"]), 3),
                "image_size": [int(w), int(h)],
                "crop": "",
            },
            "faces": boxes,
            "face_count": len(classified),
            "face_mode": cfg["id"],
            "elapsed_ms": round(elapsed, 1),
            "track": True,
        }

    def predict_track_bytes(self, data: bytes, mode: str | None = None) -> dict:
        img = decode_image(data)
        if img is None:
            return {
                "ok": False,
                "error": "无法解析图像，请使用 JPG / PNG / WEBP",
                "code": "BAD_IMAGE",
                "track": True,
                "faces": [],
            }
        return self.predict_track_bgr(img, mode=mode)

    def predict_bytes(self, data: bytes, want_crop: bool = True, mode: str | None = None) -> dict:
        img = decode_image(data)
        if img is None:
            return {"ok": False, "error": "无法解析图像，请使用 JPG / PNG / WEBP", "code": "BAD_IMAGE"}
        return self.predict_bgr(img, want_crop=want_crop, mode=mode)

    def predict_many_bytes(self, frames: list[bytes], mode: str | None = None) -> dict:
        """多帧里选最稳的一帧。单人精检看置信度，多人远场看脸数。"""
        t0 = time.perf_counter()
        cfg = face_mode_cfg(mode)
        oks = []
        last_fail = None
        for data in frames:
            img = decode_image(data)
            if img is None:
                continue
            one = self.predict_bgr(img, mode=cfg["id"])
            if not one.get("ok"):
                last_fail = one
                continue
            oks.append(one)
        if not oks:
            fail = last_fail or {"ok": False, "error": "未检测到人脸", "code": "NO_FACE"}
            fail["elapsed_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
            fail["face_mode"] = cfg["id"]
            return fail
        if cfg.get("majority"):
            best = max(
                oks,
                key=lambda r: (
                    int((r.get("vote") or {}).get("total") or r.get("face_count") or 0),
                    float((r.get("emotion") or {}).get("prob") or 0.0),
                ),
            )
        elif len(oks) > 1:
            acc = np.zeros(7, dtype=np.float64)
            for row in oks:
                for item in (row.get("emotion") or {}).get("scores") or []:
                    eid = item.get("id")
                    if eid in MODEL_LABELS:
                        acc[MODEL_LABELS.index(eid)] += float(item.get("prob") or 0.0)
            acc = acc / float(len(oks))
            eid = MODEL_LABELS[int(np.argmax(acc))]
            scores = self._scores_from_vec(acc)
            matched = [row for row in oks if (row.get("emotion") or {}).get("id") == eid] or oks
            best = dict(
                max(
                    matched,
                    key=lambda r: (
                        float((r.get("emotion") or {}).get("prob") or 0.0),
                        float((r.get("face") or {}).get("score") or 0.0),
                    ),
                )
            )
            best["emotion"] = self._emotion_from_id(eid, scores)
            if best.get("vote"):
                best["vote"] = dict(best["vote"])
                best["vote"]["id"] = eid
                best["vote"]["zh"] = best["emotion"]["zh"]
                best["vote"]["name"] = best["emotion"]["name"]
                best["vote"]["counts"] = {eid: 1}
        else:
            best = max(
                oks,
                key=lambda r: (
                    float((r.get("emotion") or {}).get("prob") or 0.0),
                    float((r.get("face") or {}).get("score") or 0.0),
                ),
            )
        best["frames_used"] = len(oks)
        best["elapsed_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
        best["face_mode"] = cfg["id"]
        return best


_recognizer: Optional[EmotionRecognizer] = None


def get_recognizer() -> EmotionRecognizer:
    global _recognizer
    if _recognizer is None:
        _recognizer = EmotionRecognizer()
    return _recognizer
