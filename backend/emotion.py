# -*- coding: utf-8 -*-
"""
人脸检测 + 表情识别。

检测器：OpenCV YuNet（5 点关键点）
识别器：OpenCV Zoo MobileFaceNet FER（7 类，RAF-DB 报告准确率 88.27%）
对齐：与官方 demo 相同的 112×112 相似变换，保证输入分布一致。
"""
from __future__ import annotations

import base64
import logging
import threading
import time
from typing import Optional

import cv2
import numpy as np

from config import (
    EMOTION_CONF_WARN,
    EMOTIONS,
    FACE_SCORE_MIN,
    FER_FILE,
    INDEX_TO_ID,
    MAX_IMAGE_SIDE,
    MODEL_DIR,
    MODEL_LABELS,
    YUNET_FILE,
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


def _softmax(x: np.ndarray) -> np.ndarray:
    z = x.astype(np.float64)
    z = z - np.max(z)
    e = np.exp(z)
    return e / np.clip(e.sum(), 1e-12, None)


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

        # Windows 下 OpenCV C++ 读盘不支持中文路径，改为内存加载
        yunet_buf = np.frombuffer(yunet_path.read_bytes(), dtype=np.uint8).copy()
        fer_buf = np.frombuffer(fer_path.read_bytes(), dtype=np.uint8).copy()
        self.detector = cv2.FaceDetectorYN.create(
            "onnx",
            yunet_buf,
            np.array([], dtype=np.uint8),
            (320, 320),
            0.7,
            0.3,
            5000,
        )
        self.net = cv2.dnn.readNetFromONNX(fer_buf)
        self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        self._haar = None
        self._lock = threading.RLock()
        logger.info("情绪识别模型已加载")

    def _haar_cascade(self):
        if self._haar is None:
            xml = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self._haar = cv2.CascadeClassifier(xml)
        return self._haar

    def detect_faces(self, image_bgr: np.ndarray) -> list[dict]:
        img, scale = resize_for_detect(image_bgr)
        h, w = img.shape[:2]
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(img)
        results = []
        if faces is not None:
            for row in faces:
                row = row.astype(np.float32)
                inv = 1.0 / scale
                x, y, bw, bh = row[:4] * inv
                lm = row[4:14].reshape(5, 2) * inv
                score = float(row[14])
                if score < FACE_SCORE_MIN:
                    continue
                results.append(
                    {
                        "box": [float(x), float(y), float(bw), float(bh)],
                        "landmarks": lm.tolist(),
                        "score": score,
                        "area": float(max(bw, 1.0) * max(bh, 1.0)),
                    }
                )
        if results:
            results.sort(key=lambda f: f["area"], reverse=True)
            return results

        # YuNet 未检出时，Haar 作为兜底，无关键点则走裁剪
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        haar_faces = self._haar_cascade().detectMultiScale(gray, 1.1, 5, minSize=(48, 48))
        for (x, y, bw, bh) in haar_faces:
            inv = 1.0 / scale
            results.append(
                {
                    "box": [float(x) * inv, float(y) * inv, float(bw) * inv, float(bh) * inv],
                    "landmarks": None,
                    "score": 0.6,
                    "area": float(bw * bh) * inv * inv,
                }
            )
        results.sort(key=lambda f: f["area"], reverse=True)
        return results

    def _fer_blob(self, aligned_bgr: np.ndarray) -> np.ndarray:
        """与 OpenCV Zoo official preprocess 保持一致：RGB /255 -0.5 /0.5。"""
        image = cv2.cvtColor(aligned_bgr, cv2.COLOR_BGR2RGB)
        image = image.astype(np.float32) / 255.0
        image = (image - 0.5) / 0.5
        return cv2.dnn.blobFromImage(image)

    def classify_face(self, image_bgr: np.ndarray, face: dict) -> dict:
        if face.get("landmarks"):
            aligned = align_face(image_bgr, np.array(face["landmarks"], dtype=np.float64))
        else:
            aligned = crop_face(image_bgr, face["box"])
        blob = self._fer_blob(aligned)
        self.net.setInput(blob, "data")
        try:
            out = self.net.forward("label")
        except cv2.error:
            out = self.net.forward()
        vec = np.array(out).reshape(-1).astype(np.float64)
        if vec.size > 7:
            vec = vec[:7]
        if vec.size < 7:
            pad = np.zeros(7, dtype=np.float64)
            pad[: vec.size] = vec
            vec = pad
        probs = _softmax(vec)
        order = np.argsort(probs)[::-1]
        scores = []
        for idx in order:
            eid = INDEX_TO_ID[int(idx)]
            meta = EMOTIONS[eid]
            scores.append(
                {
                    "id": eid,
                    "zh": meta["zh"],
                    "name": meta["name"],
                    "prob": float(probs[idx]),
                }
            )
        top = scores[0]
        return {
            "id": top["id"],
            "zh": top["zh"],
            "name": top["name"],
            "english": EMOTIONS[top["id"]]["english"],
            "prob": top["prob"],
            "scores": scores,
            "low_confidence": top["prob"] < EMOTION_CONF_WARN,
            "genre": EMOTIONS[top["id"]]["genre"],
            "copy": EMOTIONS[top["id"]]["copy"],
            "color": EMOTIONS[top["id"]]["color"],
        }

    def predict_bgr(self, image_bgr: np.ndarray, want_crop: bool = True) -> dict:
        with self._lock:
            return self._predict_bgr(image_bgr, want_crop=want_crop)

    def _predict_bgr(self, image_bgr: np.ndarray, want_crop: bool = True) -> dict:
        t0 = time.perf_counter()
        if image_bgr is None or image_bgr.size == 0:
            return {"ok": False, "error": "图像为空", "code": "NO_IMAGE", "elapsed_ms": 0, "faces": []}
        faces = self.detect_faces(image_bgr)
        if not faces:
            elapsed = (time.perf_counter() - t0) * 1000.0
            return {
                "ok": False,
                "error": "未检测到人脸。请正对镜头、保证光线充足，或换一张更清晰的正面照片。",
                "code": "NO_FACE",
                "elapsed_ms": round(elapsed, 1),
                "faces": [],
            }
        primary = faces[0]
        emotion = self.classify_face(image_bgr, primary)
        elapsed = (time.perf_counter() - t0) * 1000.0
        h, w = image_bgr.shape[:2]
        crop = encode_face_crop(image_bgr, primary["box"]) if want_crop else ""
        boxes = [
            {
                "box": [round(v, 1) for v in face["box"]],
                "score": round(float(face["score"]), 3),
                "primary": i == 0,
            }
            for i, face in enumerate(faces[:4])
        ]
        return {
            "ok": True,
            "emotion": emotion,
            "face": {
                "box": [round(v, 1) for v in primary["box"]],
                "score": round(primary["score"], 3),
                "image_size": [int(w), int(h)],
                "crop": crop,
            },
            "faces": boxes,
            "face_count": len(faces),
            "elapsed_ms": round(elapsed, 1),
        }

    def predict_bytes(self, data: bytes, want_crop: bool = True) -> dict:
        img = decode_image(data)
        if img is None:
            return {"ok": False, "error": "无法解析图像，请使用 JPG / PNG / WEBP", "code": "BAD_IMAGE"}
        return self.predict_bgr(img, want_crop=want_crop)

    def predict_many_bytes(self, frames: list[bytes]) -> dict:
        """多帧概率平均，提升摄像头实时识别稳定性。"""
        t0 = time.perf_counter()
        acc = None
        last_ok = None
        last_fail = None
        used = 0
        for data in frames:
            img = decode_image(data)
            if img is None:
                continue
            one = self.predict_bgr(img)
            if not one.get("ok"):
                last_fail = one
                continue
            last_ok = one
            vec = np.zeros(7, dtype=np.float64)
            for item in one["emotion"]["scores"]:
                idx = MODEL_LABELS.index(item["id"])
                vec[idx] = item["prob"]
            acc = vec if acc is None else acc + vec
            used += 1
        if acc is None or last_ok is None:
            fail = last_fail or {"ok": False, "error": "未检测到人脸", "code": "NO_FACE"}
            fail["elapsed_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
            return fail
        acc = acc / float(used)
        order = np.argsort(acc)[::-1]
        scores = []
        for idx in order:
            eid = INDEX_TO_ID[int(idx)]
            meta = EMOTIONS[eid]
            scores.append({"id": eid, "zh": meta["zh"], "name": meta["name"], "prob": float(acc[idx])})
        top = scores[0]
        last_ok["emotion"].update(
            {
                "id": top["id"],
                "zh": top["zh"],
                "name": top["name"],
                "english": EMOTIONS[top["id"]]["english"],
                "prob": top["prob"],
                "scores": scores,
                "low_confidence": top["prob"] < EMOTION_CONF_WARN,
                "genre": EMOTIONS[top["id"]]["genre"],
                "copy": EMOTIONS[top["id"]]["copy"],
                "color": EMOTIONS[top["id"]]["color"],
            }
        )
        last_ok["frames_used"] = used
        last_ok["elapsed_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
        return last_ok


_recognizer: Optional[EmotionRecognizer] = None


def get_recognizer() -> EmotionRecognizer:
    global _recognizer
    if _recognizer is None:
        _recognizer = EmotionRecognizer()
    return _recognizer
