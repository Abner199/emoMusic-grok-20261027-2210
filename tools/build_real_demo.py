"""生成真人示例照片：static/demo 第 4、5、6 组（22–28 带 -d，29–35 带 -e，36–42 带 -f），每类 3 张。

照片来源（每张都先经本系统识别为对应表情，再挑“好看、表情典型夸张”的）：
- local：CC20261023 项目 dist/static/demo_faces 里的 8 张（Wikimedia Commons，CC BY / CC BY-SA / 公有领域）；
- commons：Wikimedia Commons 文件名；
- unsplash：Unsplash 照片编号（Unsplash License）。
改动：以人脸为中心裁成正方形，缩放到 1024×1024，重新压缩为 JPEG。

    python tools/build_real_demo.py [demo_faces 目录]
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import DEMO_DIR  # noqa: E402

LOCAL_DIR = Path(r"E:\F_当AI遇见旋律\CC20261023_当AI遇见旋律\emoMusic\dist\static\demo_faces")
UA = {"User-Agent": "emoMusic-demo/1.0 (classroom project)"}
SIZE = 1024

# 本地 8 张的出处（摘自 demo_faces/图片来源与授权.txt）
LOCAL_CREDIT = {
    "happy_1_喜.jpg": "The smiling asian princess.jpg | CC BY-SA 2.0 | alex yosifov | https://commons.wikimedia.org/wiki/File:The_smiling_asian_princess.jpg",
    "happy_2_喜.jpg": "Harvest (20181109-FPAC-LSC-1380).jpg | Public domain | USDAgov | https://commons.wikimedia.org/wiki/File:Harvest_(20181109-FPAC-LSC-1380).jpg",
    "happy_3_喜.jpg": "Girl with red envelopes in Chiayi, Taiwan.jpg | CC BY 2.0 | 總統府 | https://commons.wikimedia.org/wiki/File:Girl_with_red_envelopes_in_Chiayi,_Taiwan.jpg",
    "angry_1_怒.jpg": "Angry woman.jpg | CC BY 2.0 | Lara604 | https://commons.wikimedia.org/wiki/File:Angry_woman.jpg",
    "sad_1_哀.jpg": "Cry baby girl 04 (cropped).jpg | CC BY-SA 4.0 | Mostafameraji | https://commons.wikimedia.org/wiki/File:%DA%AF%D8%B1%DB%8C%D9%87_%DA%A9%D8%B1%D8%AF%D9%86_%D8%AF%D8%AE%D8%AA%D8%B1_%D8%A8%DA%86%D9%87_Cry_baby_girl_04_(cropped).jpg",
    "sad_2_哀.jpg": "Cry baby girl 01.jpg | CC BY-SA 4.0 | Mostafameraji | https://commons.wikimedia.org/wiki/File:%DA%AF%D8%B1%DB%8C%D9%87_%DA%A9%D8%B1%D8%AF%D9%86_%D8%AF%D8%AE%D8%AA%D8%B1_%D8%A8%DA%86%D9%87_Cry_baby_girl_01.jpg",
    "surprised_1_惊.jpg": "Kinda Surprised (2417839929).jpg | CC BY-SA 2.0 | Helgi Halldórsson | https://commons.wikimedia.org/wiki/File:Kinda_Surprised_(2417839929).jpg",
    "surprised_2_惊.jpg": "Surprise (42495212).jpeg | CC BY 3.0 | Gigiextremeno | https://commons.wikimedia.org/wiki/File:Surprise_(42495212).jpeg",
}
COMMONS_CREDIT = {
    "Scared Girl.jpg": "CC BY 2.0 | Victor Bezrukov | https://commons.wikimedia.org/wiki/File:Scared_Girl.jpg",
}

# (表情, 汉字, 中文名, [第4组, 第5组, 第6组])，顺序与 01–21 相同；来源写成 "local:文件名" / "commons:文件名" / "unsplash:编号"
PICKS = [
    ("happy", "喜", "喜悦", ["local:happy_1_喜.jpg", "local:happy_3_喜.jpg", "local:happy_2_喜.jpg"]),
    ("angry", "怒", "愤怒", ["local:angry_1_怒.jpg", "unsplash:1611689037241-d8dfe4280f2e", "unsplash:1584970658864-242327da66dc"]),
    ("sad", "哀", "悲伤", ["local:sad_1_哀.jpg", "local:sad_2_哀.jpg", "unsplash:1758600588872-3d340e69650f"]),
    ("fear", "惧", "恐惧", ["unsplash:1758273706205-de3e2f5f5c18", "commons:Scared Girl.jpg", "unsplash:1669627961474-7bff53c5dcb5"]),
    ("surprise", "惊", "惊讶", ["local:surprised_1_惊.jpg", "local:surprised_2_惊.jpg", "unsplash:1780548705016-3bc8f90dbb93"]),
    ("disgust", "厌", "厌恶", ["unsplash:1601412436518-3c690b92b43f", "unsplash:1525527834147-0f4ff3097029", "unsplash:1758600588802-3da6e4f457e6"]),
    ("neutral", "中性", "平静", ["unsplash:1542909168-82c3e7fdca5c", "unsplash:1628501023521-48cece9a6909", "unsplash:1593260853607-d0e0f639bdab"]),
]
GROUPS = [("d", 22), ("e", 29), ("f", 36)]


def load(source: str, local_dir: Path) -> tuple[np.ndarray, str]:
    kind, ref = source.split(":", 1)
    if kind == "local":
        data = (local_dir / ref).read_bytes()
        credit = f"{ref} ← Wikimedia Commons：{LOCAL_CREDIT.get(ref, '')}"
    elif kind == "commons":
        q = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={"action": "query", "titles": "File:" + ref, "prop": "imageinfo", "iiprop": "url", "iiurlwidth": 1600, "format": "json"},
            headers=UA,
            timeout=60,
        ).json()
        info = list(q["query"]["pages"].values())[0]["imageinfo"][0]
        data = requests.get(info.get("thumburl") or info["url"], headers=UA, timeout=120).content
        credit = f"Wikimedia Commons：{ref} | {COMMONS_CREDIT.get(ref, '')}"
    elif kind == "unsplash":
        data = requests.get(f"https://images.unsplash.com/photo-{ref}?fm=jpg&q=90&w=1600", headers=UA, timeout=120).content
        credit = f"Unsplash（Unsplash License）：https://images.unsplash.com/photo-{ref}"
    else:
        raise SystemExit(f"未知来源：{source}")
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise SystemExit(f"读取失败：{source}")
    return img, credit


def face_square(img: np.ndarray) -> np.ndarray:
    from backend.emotion import get_recognizer

    res = get_recognizer().predict_bgr(img, want_crop=False)
    faces = res.get("faces") or []
    h, w = img.shape[:2]
    if faces and faces[0].get("box"):
        x, y, bw, bh = [float(v) for v in faces[0]["box"]]
        cx, cy = x + bw / 2, y + bh * 0.55
        side = max(bw, bh) * 2.4
    else:
        cx, cy, side = w / 2, h / 2, min(w, h)
    side = min(side, w, h)
    x0 = int(round(min(max(cx - side / 2, 0), w - side)))
    y0 = int(round(min(max(cy - side / 2, 0), h - side)))
    crop = img[y0 : y0 + int(side), x0 : x0 + int(side)]
    return cv2.resize(crop, (SIZE, SIZE), interpolation=cv2.INTER_AREA)


def main() -> None:
    from backend.emotion import get_recognizer

    local_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else LOCAL_DIR
    rec = get_recognizer()
    for old in list(DEMO_DIR.glob("*-d.jpg")) + list(DEMO_DIR.glob("*-e.jpg")) + list(DEMO_DIR.glob("*-f.jpg")):
        old.unlink()
    lines = []
    for eid, zh, name, sources in PICKS:
        for g, source in enumerate(sources):
            suffix, start = GROUPS[g]
            num = start + [p[0] for p in PICKS].index(eid)
            img, credit = load(source, local_dir)
            sq = face_square(img)
            emo = (rec.predict_bgr(sq, want_crop=False) or {}).get("emotion") or {}
            if emo.get("id") != eid:
                raise SystemExit(f"{source} 裁剪后识别为 {emo.get('id')}，不是 {eid}，请换一张")
            out = DEMO_DIR / f"{num:02d}-{zh}-{name}-{eid}-{suffix}.jpg"
            ok, buf = cv2.imencode(".jpg", sq, [cv2.IMWRITE_JPEG_QUALITY, 88])
            if not ok:
                raise SystemExit(f"写入失败：{out}")
            out.write_bytes(buf.tobytes())
            line = f"  {out.name}（本系统识别为{name} {emo.get('prob', 0):.0%}）\n      {credit}"
            lines.append((num, line))
            print(line)
    lines.sort()
    (DEMO_DIR / "示例照片来源与授权.txt").write_text(
        "示例照片来源与授权\n\n"
        "01–21（A、B、C 三组，文件名无后缀 / -b / -c）\n"
        "  合成肖像，供演示用（见 命名说明.txt）。\n\n"
        "22–42（文件名带 -d / -e / -f）：真人照片，共 21 张（每类 3 张）\n"
        "  来源：Wikimedia Commons（各张授权见下，CC BY / CC BY-SA / 公有领域）与 Unsplash（Unsplash License）\n"
        "  改动：以人脸为中心裁成正方形，缩放到 1024×1024，重新压缩为 JPEG（tools/build_real_demo.py）。\n"
        "  CC BY-SA 照片裁剪后的版本同样以 CC BY-SA 授权提供。\n"
        "  每张都经本系统识别为对应表情后再人工挑选。\n\n"
        + "\n".join(line for _, line in lines)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
