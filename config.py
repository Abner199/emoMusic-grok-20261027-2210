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
MAX_IMAGE_SIDE = 960

YUNET_FILE = "face_detection_yunet_2023mar.onnx"
FER_FILE = "facial_expression_recognition_mobilefacenet_2022july.onnx"

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
        "color": "#F0C14B",
        "color2": "#FF8A3D",
        "bg": "#2A1F0A",
        "search": ["热爱105度的你 阿肆", "被风吹过的夏天 金莎", "夏日之风 温岚", "Good Time Owl City"],
    },
    "angry": {
        "id": "angry",
        "zh": "怒",
        "name": "愤怒",
        "english": "Angry",
        "hint": "眉头紧锁下压，目光锐利，唇线绷紧",
        "genre": "攻击性摇滚 · 宣泄",
        "copy": "怒是冲的：双截棍、死了都要爱、我管你、霍元甲，用来砸开，不是用来励志。",
        "color": "#E23D3D",
        "color2": "#8B1E1E",
        "bg": "#2A0C0C",
        "search": ["双截棍 周杰伦", "杀破狼 JS", "悟空 戴荃", "One Step Closer LINKIN PARK"],
    },
    "sad": {
        "id": "sad",
        "zh": "哀",
        "name": "悲伤",
        "english": "Sad",
        "hint": "眉头内侧上提，嘴角下垂，目光湿润",
        "genre": "哭腔情歌",
        "copy": "哀是沉的：后来、说散就散、我怀念的、十年，KTV 一放就鼻酸。",
        "color": "#5B8CFF",
        "color2": "#7EC8E3",
        "bg": "#0C1628",
        "search": ["后来 刘若英", "红豆 王菲", "刻在我心底的名字 卢广仲", "Hello Adele"],
    },
    "fear": {
        "id": "fear",
        "zh": "惧",
        "name": "恐惧",
        "english": "Fear",
        "hint": "眉毛上扬并向中间聚拢，上眼睑抬起，嘴唇横向拉开",
        "genre": "暗夜惊悚流行",
        "copy": "惧是发凉的：夜曲、发如雪、四面楚歌、来自天堂的魔鬼，专门走暗的。",
        "color": "#8B6CCF",
        "color2": "#3D2A66",
        "bg": "#160E24",
        "search": ["夜曲 周杰伦", "杀手 林俊杰", "夜半歌声 张国荣", "Haunted Evanescence"],
    },
    "surprise": {
        "id": "surprise",
        "zh": "惊",
        "name": "惊讶",
        "english": "Surprise",
        "hint": "眉毛高高扬起，眼睛睁圆，下颌松开",
        "genre": "突然爆开 · 哇",
        "copy": "惊是跳的：本草纲目、园游会、舞娘、野狼disco，和甜甜的喜不是一路。",
        "color": "#FF6B9D",
        "color2": "#FFC857",
        "bg": "#2A1220",
        "search": ["本草纲目 周杰伦", "火力全开 王力宏", "马德里不思议 蔡依林", "Dynamite BTS"],
    },
    "disgust": {
        "id": "disgust",
        "zh": "厌",
        "name": "厌恶",
        "english": "Disgust",
        "hint": "鼻梁皱起，上唇抬起，眼睛微眯",
        "genre": "嫌弃 · 自嘲 · 刺耳",
        "copy": "厌是皱的：丑八怪、算什么男人、Play我呸、不将就，故意往刺和嫌弃上走。",
        "color": "#3D8B6E",
        "color2": "#C4B45A",
        "bg": "#0E1F18",
        "search": ["丑八怪 薛之谦", "动物世界 薛之谦", "K歌之王 陈奕迅", "Sk8er Boi Avril Lavigne"],
    },
    "neutral": {
        "id": "neutral",
        "zh": "中性",
        "name": "平静",
        "english": "Neutral",
        "hint": "五官放松，嘴唇自然闭合，目光稳定",
        "genre": "平走日常",
        "copy": "中性是稳的：成都、遇见、同桌的你、东风破，不哭不闹也不嗨。",
        "color": "#8B9BB4",
        "color2": "#D5C4A1",
        "bg": "#14161C",
        "search": ["成都 赵雷", "年少有为 李荣浩", "蒲公英的约定 周杰伦", "斑马斑马 宋冬野"],
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

FACE_SCORE_MIN = 0.55
EMOTION_CONF_WARN = 0.38
ONLINE_TIMEOUT = 4.0
RECOMMEND_COUNT = 24
ONLINE_APIS = ("itunes", "netease", "migu", "kugou", "qq", "kuwo")
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
}
