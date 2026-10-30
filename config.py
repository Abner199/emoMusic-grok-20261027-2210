# -*- coding: utf-8 -*-
"""全局配置：路径、情绪标签、风格映射、模型与服务参数。"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
TEMPLATE_DIR = ROOT / "templates"
DATA_DIR = ROOT / "data"
MODEL_DIR = STATIC_DIR / "models"
AUDIO_DIR = STATIC_DIR / "audio"
COVER_DIR = STATIC_DIR / "covers"
DEMO_DIR = STATIC_DIR / "demo"
HISTORY_DIR = STATIC_DIR / "history"

DATA_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
COVER_DIR.mkdir(parents=True, exist_ok=True)
DEMO_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_DIR.mkdir(parents=True, exist_ok=True)

SECRET_KEY = "xinxian-emotune-dev-key-change-in-production"
HOST = os.environ.get("EMOTUNE_HOST", "0.0.0.0")
PORT = int(os.environ.get("EMOTUNE_PORT", "5000"))
MAX_CONTENT_MB = 8
MAX_IMAGE_SIDE = 1280

YUNET_FILE = "face_detection_yunet_2023mar.onnx"
FER_FILE = "facial_expression_recognition_mobilefacenet_2022july.onnx"
HSE_FILE = "enet_b0_8_best_vgaf.onnx"

# OpenCV Zoo MobileFaceNet FER 的类别顺序，不可改动
MODEL_LABELS = ["angry", "disgust", "fear", "happy", "neutral", "sad", "surprise"]

EMOTIONS = {
    "happy": {
        "id": "happy",
        "zh": "喜",
        "name": "喜悦",
        "english": "Happy",
        "hint": "嘴角上扬，眼周出现笑纹，面颊抬起",
        "genre": "阳光蹦跳 · 开口就笑",
        "copy": "喜就是亮的：热爱105°C的你、小苹果、暖暖、告白气球，一开口就往上扬。",
        "color": "#FFD400",
        "color2": "#FF9F1A",
        "bg": "#2A2200",
        "search": ["小苹果 筷子兄弟", "热爱105度的你 阿肆", "告白气球 周杰伦", "粉色海洋 周杰伦"],
    },
    "angry": {
        "id": "angry",
        "zh": "怒",
        "name": "愤怒",
        "english": "Angry",
        "hint": "眉头紧锁下压，目光锐利，唇线绷紧",
        "genre": "攻击性摇滚 · 宣泄",
        "copy": "怒是冲的：双截棍、死了都要爱、我管你、霍元甲，用来砸开，不是用来励志。",
        "color": "#E02020",
        "color2": "#9B1212",
        "bg": "#2A0C0C",
        "search": ["双截棍 周杰伦", "摩天动物园 邓紫棋", "新世界 华晨宇", "霍元甲 周杰伦"],
    },
    "sad": {
        "id": "sad",
        "zh": "哀",
        "name": "悲伤",
        "english": "Sad",
        "hint": "眉头内侧上提，嘴角下垂，目光湿润",
        "genre": "哭腔情歌",
        "copy": "哀是沉的：后来、说散就散、我怀念的、十年，KTV 一放就鼻酸。",
        "color": "#4E7390",
        "color2": "#7A9BB0",
        "bg": "#0E1820",
        "search": ["后来 刘若英", "可惜没如果 林俊杰", "说了再见 周杰伦", "十年 陈奕迅"],
    },
    "fear": {
        "id": "fear",
        "zh": "惧",
        "name": "恐惧",
        "english": "Fear",
        "hint": "眉毛上扬并向中间聚拢，上眼睑抬起，嘴唇横向拉开",
        "genre": "暗夜惊悚流行",
        "copy": "惧是发凉的：夜曲、发如雪、四面楚歌、来自天堂的魔鬼，专门走暗的。",
        "color": "#6B2D91",
        "color2": "#3D1860",
        "bg": "#160A20",
        "search": ["夜曲 周杰伦", "黑武士 林俊杰", "来自天堂的魔鬼 邓紫棋", "断了的弦 周杰伦"],
    },
    "surprise": {
        "id": "surprise",
        "zh": "惊",
        "name": "惊讶",
        "english": "Surprise",
        "hint": "眉毛高高扬起，眼睛睁圆，下颌松开",
        "genre": "突然爆开 · 哇",
        "copy": "惊是跳的：本草纲目、园游会、舞娘、野狼disco，和甜甜的喜不是一路。",
        "color": "#FF7A18",
        "color2": "#FFC44D",
        "bg": "#2A1406",
        "search": ["野狼disco 宝石Gem", "本草纲目 周杰伦", "达拉崩吧 周深", "公主病 周杰伦"],
    },
    "disgust": {
        "id": "disgust",
        "zh": "厌",
        "name": "厌恶",
        "english": "Disgust",
        "hint": "鼻梁皱起，上唇抬起，眼睛微眯",
        "genre": "嫌弃 · 自嘲 · 刺耳",
        "copy": "厌是皱的：丑八怪、算什么男人、Play我呸、不将就，故意往刺和嫌弃上走。",
        "color": "#6F7D32",
        "color2": "#A3A04A",
        "bg": "#16180A",
        "search": ["丑八怪 薛之谦", "差不多姑娘 邓紫棋", "我不配 周杰伦", "一丝不挂 陈奕迅"],
    },
    "neutral": {
        "id": "neutral",
        "zh": "中性",
        "name": "平静",
        "english": "Neutral",
        "hint": "五官放松，嘴唇自然闭合，目光稳定",
        "genre": "平走日常",
        "copy": "中性是稳的：成都、遇见、同桌的你、东风破，不哭不闹也不嗨。",
        "color": "#4EC6F5",
        "color2": "#1F8FC4",
        "bg": "#0A1C24",
        "search": ["蜗牛 周杰伦", "晴天 周杰伦", "大鱼 周深", "岁月如歌 陈奕迅"],
    },
}

# 模型输出下标 -> 内部 id
INDEX_TO_ID = {
    0: "angry",
    1: "disgust",
    2: "fear",
    3: "happy",
    4: "neutral",
    5: "sad",
    6: "surprise",
}

FACE_SCORE_MIN = 0.32
FACE_MAX = 16
YUNET_SCORE = 0.42
YUNET_NMS = 0.3
EMOTION_CONF_WARN = 0.38
DEFAULT_FACE_MODE = "solo"
FACE_MODES = {
    "solo": {
        "id": "solo",
        "zh": "单人精检",
        "name": "单人近景精检",
        "blurb": "只取画面里最大、最稳的一张脸，检测阈值更高，不扫远景杂脸。近景用 MobileFaceNet 与 HSEmotion 融合，两模型不一致时更信野外模型，适合自拍、对镜和证件式照片。",
        "score": 0.58,
        "score_min": 0.46,
        "nms": 0.3,
        "top_k": 8,
        "face_max": 1,
        "min_face": 28,
        "max_side": 1280,
        "upscale": False,
        "haar": False,
        "dual_score": 0.80,
        "majority": False,
    },
    "crowd": {
        "id": "crowd",
        "zh": "多人远场",
        "name": "多人与远景",
        "blurb": "同时框出多张脸，包括远景小脸；歌曲按人数最多的情绪来。适合课堂、合影和远镜头。",
        "score": 0.42,
        "score_min": 0.32,
        "nms": 0.3,
        "top_k": 50,
        "face_max": 16,
        "min_face": 14,
        "max_side": 1280,
        "upscale": True,
        "haar": True,
        "dual_score": 0.68,
        "majority": True,
    },
}
ONLINE_TIMEOUT = 4.0
RECOMMEND_COUNT = 24
ONLINE_APIS = (
    "itunes",
    "itunes_chart",
    "apple_hot",
    "apple_asia",
    "netease",
    "netease_hot",
    "migu",
    "kugou",
    "qq",
    "qq_hot",
    "kuwo",
    "deezer",
    "audius",
)
HISTORY_LIMIT = 0  # 0 = keep every footprint; truncation disabled

THEMES = {
    "night": "夜金",
    "paper": "宣纸",
    "ink": "墨青",
    "rouge": "朱砂",
    "celadon": "青瓷",
    "moon": "月白",
}

MODEL_URLS = {
    YUNET_FILE: [
        "https://huggingface.co/opencv/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx",
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    ],
    FER_FILE: [
        "https://huggingface.co/opencv/facial_expression_recognition/resolve/main/facial_expression_recognition_mobilefacenet_2022july.onnx",
        "https://github.com/opencv/opencv_zoo/raw/main/models/facial_expression_recognition/facial_expression_recognition_mobilefacenet_2022july.onnx",
        "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/facial_expression_recognition/facial_expression_recognition_mobilefacenet_2022july.onnx",
    ],
    HSE_FILE: [
        "https://github.com/sb-ai-lab/EmotiEffLib/raw/main/models/affectnet_emotions/onnx/enet_b0_8_best_vgaf.onnx",
        "https://media.githubusercontent.com/media/sb-ai-lab/EmotiEffLib/main/models/affectnet_emotions/onnx/enet_b0_8_best_vgaf.onnx",
        "https://github.com/HSE-asavchenko/face-emotion-recognition/raw/main/models/affectnet_emotions/onnx/enet_b0_8_best_vgaf.onnx",
    ],
}
