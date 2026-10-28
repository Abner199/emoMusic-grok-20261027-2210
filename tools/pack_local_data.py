# -*- coding: utf-8 -*-
"""把本机情绪足迹和偏好打成 zip，换电脑后解回同样位置。不进 GitHub。"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
HISTORY_DIR = ROOT / "static" / "history"
DEFAULT_ZIP = DATA / "emotune-local-data.zip"

MEMBERS = (
    "data/history.json",
    "data/prefs.json",
)


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def pack(out: Path) -> Path:
    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    n_json = 0
    n_jpg = 0
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        meta = {
            "packed_at": datetime.now().isoformat(timespec="seconds"),
            "root_name": ROOT.name,
            "note": "情绪足迹与本机偏好。解压到项目根目录。不要提交到 GitHub。",
        }
        zf.writestr("emotune-local-meta.json", json.dumps(meta, ensure_ascii=False, indent=2))
        for rel in MEMBERS:
            src = ROOT / rel
            if src.is_file():
                zf.write(src, rel)
                n_json += 1
        if HISTORY_DIR.is_dir():
            for src in sorted(HISTORY_DIR.iterdir()):
                if src.is_file() and src.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                    zf.write(src, _rel(src))
                    n_jpg += 1
    print(f"已打包 {out}")
    print(f"  索引/偏好 {n_json} 个文件，人脸截图 {n_jpg} 张")
    return out


def unpack(src: Path) -> None:
    src = src.resolve()
    if not src.is_file():
        raise SystemExit(f"找不到打包文件：{src}")
    n = 0
    with zipfile.ZipFile(src, "r") as zf:
        names = zf.namelist()
        allowed_prefix = ("data/", "static/history/")
        for name in names:
            norm = name.replace("\\", "/").lstrip("/")
            if norm in {"emotune-local-meta.json"} or norm.endswith("/"):
                continue
            if not any(norm == p or norm.startswith(p) for p in allowed_prefix):
                print(f"跳过意外路径：{norm}")
                continue
            dest = ROOT / Path(*norm.split("/"))
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(zf.read(name))
            n += 1
    print(f"已解到项目根目录 {ROOT}，写入 {n} 个文件")
    print("请重新打开页面或刷新「历史」，足迹应能看到。")


def main() -> int:
    parser = argparse.ArgumentParser(description="打包或恢复本机情绪足迹")
    parser.add_argument("--unpack", metavar="ZIP", help="把 zip 解回项目 data/ 与 static/history/")
    parser.add_argument("--out", metavar="ZIP", help="打包输出路径，默认 data/emotune-local-data.zip")
    args = parser.parse_args()
    if args.unpack:
        unpack(Path(args.unpack))
        return 0
    pack(Path(args.out) if args.out else DEFAULT_ZIP)
    return 0


if __name__ == "__main__":
    sys.exit(main())
