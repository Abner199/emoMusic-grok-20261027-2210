# -*- coding: utf-8 -*-
"""
情绪歌曲推荐策略。

每一种方式都对应一套经典理论，用七类情绪之间的映射来执行。
同频、修复、先同频再修复是默认三套；其余是环面、唤醒、效价上的变体。
"""
from __future__ import annotations

from typing import Callable

from config import EMOTIONS

EMO_ORDER = ["happy", "angry", "sad", "fear", "surprise", "disgust", "neutral"]

# Russell 1980 / Thayer 1989 效价-唤醒平面上的七点
_VA = {
    "happy": (0.78, 0.70),
    "angry": (-0.62, 0.84),
    "sad": (-0.72, -0.58),
    "fear": (-0.52, 0.58),
    "surprise": (0.32, 0.88),
    "disgust": (-0.58, 0.12),
    "neutral": (0.04, 0.02),
}

ROLE_ZH = {
    "iso": "同频",
    "repair": "修复",
    "bridge": "过渡",
    "contrast": "对比",
    "calm": "降唤醒",
    "uplift": "升效价",
    "amplify": "强化",
    "walk": "回暖",
}


def _meta(eid: str) -> dict:
    return EMOTIONS.get(eid) or EMOTIONS["neutral"]


def _name(eid: str) -> str:
    m = _meta(eid)
    return f"{m['zh']}·{m['name']}"


def repair_of(emotion: str) -> str:
    """心境管理：把负效价或过高唤醒推向更稳、更亮的状态。"""
    return {
        "happy": "happy",
        "angry": "neutral",
        "sad": "happy",
        "fear": "neutral",
        "surprise": "happy",
        "disgust": "happy",
        "neutral": "happy",
    }.get(emotion, "happy")


def contrast_of(emotion: str) -> str:
    """Hevner 环上的对极：用反差释放。"""
    return {
        "happy": "sad",
        "sad": "happy",
        "angry": "happy",
        "fear": "happy",
        "surprise": "sad",
        "disgust": "happy",
        "neutral": "surprise",
    }.get(emotion, "happy")


def calm_of(emotion: str) -> str:
    """Thayer：先降唤醒。高唤醒负情绪落到低唤醒。"""
    return {
        "happy": "neutral",
        "angry": "sad",
        "sad": "sad",
        "fear": "sad",
        "surprise": "neutral",
        "disgust": "sad",
        "neutral": "neutral",
    }.get(emotion, "neutral")


def uplift_of(emotion: str) -> str:
    """近似保持唤醒，抬高效价。"""
    return {
        "happy": "happy",
        "angry": "surprise",
        "sad": "happy",
        "fear": "surprise",
        "surprise": "happy",
        "disgust": "happy",
        "neutral": "happy",
    }.get(emotion, "happy")


def iso_repair_path(emotion: str) -> list[str]:
    """完整 ISO：先贴着当前情绪，再过渡，再到修复目标。"""
    return {
        "happy": ["happy"],
        "surprise": ["surprise", "happy"],
        "angry": ["angry", "neutral", "happy"],
        "fear": ["fear", "neutral", "happy"],
        "disgust": ["disgust", "neutral", "happy"],
        "sad": ["sad", "neutral", "happy"],
        "neutral": ["neutral", "happy"],
    }.get(emotion, [emotion, "happy"])


def circumplex_path(emotion: str) -> list[str]:
    """在效价-唤醒平面上走向喜悦（高正效价、中高唤醒）。"""
    return {
        "happy": ["happy"],
        "surprise": ["surprise", "happy"],
        "angry": ["angry", "surprise", "happy"],
        "fear": ["fear", "surprise", "happy"],
        "disgust": ["disgust", "neutral", "happy"],
        "sad": ["sad", "neutral", "happy"],
        "neutral": ["neutral", "happy"],
    }.get(emotion, [emotion, "happy"])


def _split_counts(total: int, n: int) -> list[int]:
    n = max(1, n)
    base = total // n
    extra = total - base * n
    return [base + (1 if i < extra else 0) for i in range(n)]


def _stage(eid: str, count: int, role: str, rank: str) -> dict:
    meta = _meta(eid)
    return {
        "emotion": eid,
        "count": max(0, int(count)),
        "role": role,
        "role_zh": ROLE_ZH.get(role, role),
        "rank": rank,
        "zh": meta["zh"],
        "name": meta["name"],
    }


def _plan_iso(emotion: str, count: int) -> list[dict]:
    return [_stage(emotion, count, "iso", "face")]


def _plan_repair(emotion: str, count: int) -> list[dict]:
    return [_stage(repair_of(emotion), count, "repair", "target")]


def _plan_iso_repair(emotion: str, count: int) -> list[dict]:
    path = iso_repair_path(emotion)
    if len(path) == 1:
        return [_stage(path[0], count, "iso", "face")]
    counts = _split_counts(count, len(path))
    roles = ["iso"] + ["bridge"] * (len(path) - 2) + ["repair"]
    ranks = ["face"] + ["target"] * (len(path) - 1)
    return [_stage(eid, n, role, rank) for eid, n, role, rank in zip(path, counts, roles, ranks) if n]


def _plan_contrast(emotion: str, count: int) -> list[dict]:
    return [_stage(contrast_of(emotion), count, "contrast", "target")]


def _plan_circumplex(emotion: str, count: int) -> list[dict]:
    path = circumplex_path(emotion)
    counts = _split_counts(count, len(path))
    roles = ["iso"] + ["walk"] * (len(path) - 2) + (["repair"] if len(path) > 1 else [])
    if len(path) == 1:
        roles = ["iso"]
    ranks = ["face"] + ["target"] * (len(path) - 1)
    return [_stage(eid, n, role, rank) for eid, n, role, rank in zip(path, counts, roles, ranks) if n]


def _plan_calm(emotion: str, count: int) -> list[dict]:
    return [_stage(calm_of(emotion), count, "calm", "target")]


def _plan_uplift(emotion: str, count: int) -> list[dict]:
    return [_stage(uplift_of(emotion), count, "uplift", "target")]


def _plan_amplify(emotion: str, count: int) -> list[dict]:
    return [_stage(emotion, count, "amplify", "target")]


def _plan_balance(emotion: str, count: int) -> list[dict]:
    a = count // 2
    b = count - a
    return [
        _stage(emotion, a, "iso", "face"),
        _stage(repair_of(emotion), b, "repair", "target"),
    ]


_PLANNERS: dict[str, Callable[[str, int], list[dict]]] = {
    "iso": _plan_iso,
    "repair": _plan_repair,
    "iso-repair": _plan_iso_repair,
    "contrast": _plan_contrast,
    "circumplex": _plan_circumplex,
    "calm": _plan_calm,
    "uplift": _plan_uplift,
    "amplify": _plan_amplify,
    "balance": _plan_balance,
}


STRATEGIES: dict[str, dict] = {
    "iso": {
        "id": "iso",
        "zh": "同频",
        "name": "同频匹配",
        "classic": "ISO 原则（Altshuler 1948）· 心境一致性（Bower 1981）",
        "theory": (
            "音乐治疗里的 ISO 原则主张：先用与听者当前情绪同频的音乐去贴合、承接，"
            "而不是一上来就用完全相反的曲子硬拉。Bower 的心境一致性记忆也表明，"
            "和当下心情同向的材料更容易被接受。本方式用人脸七维概率与歌曲曲调七维向量做余弦相似度，"
            "只从当前情绪曲库里取歌，档内按匹配分排序。"
        ),
        "blurb": "贴着当前表情，播同一类最贴的歌。",
        "how": "识别到什么情绪，就播这一类里最贴曲调的歌。适合想把此刻情绪听进去、听完整的时候。",
        "when": "默认。想跟着表情走，或做演示对照时选它。",
        "rule": "只取当前情绪曲库；在线未播 → 本地未播 → 已播回绕；档内人脸向量与曲调向量余弦排序。",
    },
    "repair": {
        "id": "repair",
        "zh": "修复",
        "name": "心境修复",
        "classic": "心境管理理论（Zillmann 1988）· 音乐情绪调节 MMIM（Saarikallio 2007 / 2011）",
        "theory": (
            "Zillmann 认为人会选择媒介来结束或减轻不愉快心境；"
            "Saarikallio 把音乐当成青少年最常用的情绪调节工具之一。"
            "悲伤、恐惧、厌恶等负效价表情会映射到喜悦或平静；愤怒先降到平静以卸掉攻击性唤醒。"
            "已经喜悦时维持喜悦（正心情保持）。"
        ),
        "blurb": "不继续泡在负面里，直接播修复目标类。",
        "how": "不播「现在这张脸」的歌，直接播修复目标类的歌。哀→喜，怒/惧→平静，厌/惊→喜。",
        "when": "想把心情托起来、不想继续泡在负面情绪里时选它。",
        "rule": "整份歌单取修复目标情绪曲库，按目标向量与曲调余弦排序。",
    },
    "iso-repair": {
        "id": "iso-repair",
        "zh": "先同频再修复",
        "name": "同频后修复",
        "classic": "完整 ISO 原则（Gaston 1968；Bruscia）· 先匹配再逐步调制",
        "theory": (
            "经典音乐治疗并不主张立刻用快乐音乐去「治」悲伤。"
            "完整 ISO 是：先用同频音乐与当前状态会合，再经由一两级过渡，慢慢走到希望的心情。"
            "这和生理上的节律同步、再调节是一条路。歌单按「同频 → 过渡 → 修复」分段排列，连播时能听出走向。"
        ),
        "blurb": "先同频接住，再过渡，最后走到修复。",
        "how": "前三分之一贴着当前情绪，中间过渡（多为平静），后三分之一走到修复目标。喜悦则全程同频。",
        "when": "想被接住、又希望听着听着好起来。实时捕捉锁定歌单时尤其合适。",
        "rule": "按路径分段取歌并保持顺序；每段内部仍是未播优先 + 余弦排序。",
    },
    "contrast": {
        "id": "contrast",
        "zh": "对比",
        "name": "对极反差",
        "classic": "Hevner 情绪环（1936）对极 · 拮抗过程 · Berlyne 唤醒跳跃",
        "theory": (
            "Hevner 把音乐表情排成环形，对极之间反差最大。"
            "拮抗过程与唤醒跳跃认为：突然转到相反效价，可以造成释放或「哇」的落差。"
            "喜对哀、哀对喜、怒/惧/厌对喜、惊对哀、平静对惊。"
        ),
        "blurb": "整单取对极情绪，听反差。",
        "how": "整份歌单取对极情绪。喜的脸播哭腔，哀的脸播蹦跳。",
        "when": "想要情绪切换的戏剧性，或课堂演示「表情一变、曲子对面」时选它。",
        "rule": "整单取对极曲库，按对极向量余弦排序。",
    },
    "circumplex": {
        "id": "circumplex",
        "zh": "回暖",
        "name": "环面回暖",
        "classic": "Russell 情感环面（1980）· Thayer 二维模型（1989）最短路径",
        "theory": (
            "情绪不必跳跃，可以在效价-唤醒平面上走邻格。"
            "本方式从当前点沿最短路径走向喜悦（高正效价、中高唤醒）："
            "怒/惧先到惊（同样高唤醒、效价抬高），哀/厌先到平静再喜。"
            "歌单按路径分段，听感是逐步亮起来，而不是突然翻面。"
        ),
        "blurb": "在情绪环面上邻格走，慢慢亮起来。",
        "how": "按环面上的邻格分段：例如哀→平静→喜，怒→惊→喜。",
        "when": "不想硬拉，也不想一直停在负面里，想听一段「慢慢好起来」的路线。",
        "rule": "路径各段均分 24 首，段内未播优先 + 余弦排序，播放顺序即路径顺序。",
    },
    "calm": {
        "id": "calm",
        "zh": "降唤醒",
        "name": "先把劲卸掉",
        "classic": "Thayer 心境调节：紧张唤醒先行下降 · 镇静性音乐",
        "theory": (
            "Thayer 区分紧张唤醒和能量唤醒。怒、惧、惊是高唤醒，"
            "若直接上更亮、同样吵的曲子，唤醒下不来。"
            "先用低唤醒音乐（哀或平静）把生理唤起降下来，再谈效价。"
            "这是临床里常用的「先镇静」。"
        ),
        "blurb": "先用低唤醒把劲卸掉。",
        "how": "怒/惧/厌→哀（慢、沉），惊/喜→平静。已经哀或平静则留在低唤醒。",
        "when": "表情很冲、很跳，或自己觉得需要先缓一缓时选它。",
        "rule": "整单取低唤醒目标曲库。",
    },
    "uplift": {
        "id": "uplift",
        "zh": "升效价",
        "name": "平行抬亮",
        "classic": "环面平行移动：唤醒大致不变，效价向正",
        "theory": (
            "不一定先降速。怒和惧本身能量高，可以平移到惊（同样快，但更亮）；"
            "哀则直接 hop 到喜。这是「还想动、但不要继续难受」的一条路。"
        ),
        "blurb": "唤醒差不多，把效价抬亮。",
        "how": "怒/惧→惊，哀/厌/平静/惊→喜。已经喜则保持。",
        "when": "还想听快歌、但不想再听发泄或哭腔时选它。",
        "rule": "整单取更高正效价、唤醒相近的目标曲库。",
    },
    "amplify": {
        "id": "amplify",
        "zh": "强化",
        "name": "把这类情绪听满",
        "classic": "正心情保持（Isen / Zillmann）· 宣泄假设（宣泄证据混杂，仍作可选）",
        "theory": (
            "正性情绪下，人倾向继续选择能维持好心情的材料。"
            "负性情绪下，有人用更强烈的同向音乐去做宣泄。"
            "本方式不换类，只用「该类典型曲调」的独热向量去排序，"
            "让更极端、更典型的歌排在前面。"
        ),
        "blurb": "不换类，把这一类听得更典型。",
        "how": "仍用当前情绪曲库，但按该类原型而不是脸的细分数来排。",
        "when": "喜的时候想更亮；怒、哀的时候想把这类听透再走。",
        "rule": "当前情绪曲库；用该类独热向量与曲调余弦排序。",
    },
    "balance": {
        "id": "balance",
        "zh": "平衡",
        "name": "同频与修复交错",
        "classic": "稳态 / 互补配对：一半承接，一半调节",
        "theory": (
            "不完全同频、也不完全修复。一半歌承接当下，一半歌拉向修复目标，"
            "交错排列，避免单一方向听太久。接近一种简易稳态。"
        ),
        "blurb": "一半同频、一半修复，交错着听。",
        "how": "12 首当前情绪 + 12 首修复目标，播放时交错。",
        "when": "既想被理解，又想被托一把，但不想等后半段才开始修复。",
        "rule": "两段各取一半，再按「同频、修复、同频、修复…」交错输出。",
    },
}

DEFAULT_STRATEGY = "iso"
STRATEGY_ORDER = [
    "iso",
    "repair",
    "iso-repair",
    "contrast",
    "circumplex",
    "calm",
    "uplift",
    "amplify",
    "balance",
]


def normalize(strategy: str | None) -> str:
    key = (strategy or "").strip().lower().replace("_", "-")
    aliases = {
        "match": "iso",
        "same": "iso",
        "同频": "iso",
        "heal": "repair",
        "fix": "repair",
        "修复": "repair",
        "iso+repair": "iso-repair",
        "iso_repair": "iso-repair",
        "先同频再修复": "iso-repair",
        "opposite": "contrast",
        "对比": "contrast",
        "walk": "circumplex",
        "回暖": "circumplex",
        "镇静": "calm",
        "降唤醒": "calm",
        "升效价": "uplift",
        "强化": "amplify",
        "平衡": "balance",
    }
    key = aliases.get(key, key)
    return key if key in STRATEGIES else DEFAULT_STRATEGY


def plan(emotion: str, strategy: str | None, count: int) -> list[dict]:
    if emotion not in EMOTIONS:
        emotion = "neutral"
    sid = normalize(strategy)
    stages = _PLANNERS[sid](emotion, max(6, int(count)))
    return [s for s in stages if s["count"] > 0]


def involved_emotions(stages: list[dict]) -> list[str]:
    seen: list[str] = []
    for stage in stages:
        eid = stage["emotion"]
        if eid not in seen:
            seen.append(eid)
    return seen


def interleave(parts: list[list[dict]]) -> list[dict]:
    if not parts:
        return []
    if len(parts) == 1:
        return list(parts[0])
    out: list[dict] = []
    idx = [0] * len(parts)
    alive = True
    while alive:
        alive = False
        for i, seq in enumerate(parts):
            if idx[i] < len(seq):
                out.append(seq[idx[i]])
                idx[i] += 1
                alive = True
    return out


def public_item(sid: str) -> dict:
    spec = STRATEGIES[sid]
    demo = {}
    for eid in EMO_ORDER:
        stages = plan(eid, sid, 24)
        demo[eid] = [
            {
                "emotion": s["emotion"],
                "zh": s["zh"],
                "name": s["name"],
                "role": s["role"],
                "role_zh": s["role_zh"],
                "count": s["count"],
            }
            for s in stages
        ]
    return {
        "id": spec["id"],
        "zh": spec["zh"],
        "name": spec["name"],
        "classic": spec["classic"],
        "theory": spec["theory"],
        "how": spec["how"],
        "when": spec["when"],
        "rule": spec["rule"],
        "blurb": spec.get("blurb") or spec["how"],
        "demo": demo,
    }


def public_catalog() -> list[dict]:
    return [public_item(sid) for sid in STRATEGY_ORDER]


def summary(sid: str, emotion: str, stages: list[dict]) -> dict:
    spec = STRATEGIES[normalize(sid)]
    path = " → ".join(f"{s['role_zh']}「{s['name']}」×{s['count']}" for s in stages)
    return {
        "id": spec["id"],
        "zh": spec["zh"],
        "name": spec["name"],
        "classic": spec["classic"],
        "rule": spec["rule"],
        "how": spec["how"],
        "path": path,
        "face": "YuNet + MobileFaceNet FER",
        "music": "Thayer 二维模型 + Krumhansl–Kessler 调式",
        "from": emotion,
        "from_zh": _name(emotion),
    }
