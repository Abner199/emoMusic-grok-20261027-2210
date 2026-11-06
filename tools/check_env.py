# -*- coding: utf-8 -*-
"""一键检测：当前 Python / conda 环境能不能跑心弦 EmoTune。

用法（在项目根目录）：
    双击 check-env.bat                        自动找 conda 环境 emotune 来检测
    python tools\\check_env.py                 检测“当前激活”的环境
    python tools\\check_env.py --strict        额外要求版本与 requirements-lock.txt 完全一致
    python tools\\check_env.py --no-run        只查包，不加载模型、不跑识别

结果：每项 [通过] / [提醒] / [失败]；有失败时退出码 1，并给出修复命令。
"""
from __future__ import annotations

import importlib
import os
import re
import shutil
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# pip 包名 -> (import 名, 最低版本, 低于此版本才算合格的上限)
REQUIRED = {
    "flask": ("flask", "3.0", "4"),
    "opencv-python": ("cv2", "4.8", "5"),
    "numpy": ("numpy", "1.24", "3"),
    "pillow": ("PIL", "10.0", None),
    "requests": ("requests", "2.31", None),
    "scipy": ("scipy", "1.11", None),
    "onnxruntime": ("onnxruntime", "1.16", "2"),
}
# 装了会冲突或拉 GPU 的包
FORBIDDEN = {
    "onnxruntime-gpu": "GPU 版，会和 CPU 版 onnxruntime 冲突",
    "onnxruntime-directml": "DirectML 版，会和 CPU 版冲突",
    "opencv-python-headless": "和 opencv-python 同时装会互相覆盖 cv2",
    "opencv-contrib-python": "和 opencv-python 同时装会互相覆盖 cv2",
}
MODELS = [
    "face_detection_yunet_2023mar.onnx",
    "facial_expression_recognition_mobilefacenet_2022july.onnx",
    "enet_b0_8_best_vgaf.onnx",
]
MIRROR = "-i https://pypi.tuna.tsinghua.edu.cn/simple"

results: list[tuple[str, str, str]] = []
fixes: list[str] = []


def add(level: str, name: str, detail: str = "", fix: str = "") -> None:
    results.append((level, name, detail))
    tag = {"ok": "[通过]", "warn": "[提醒]", "fail": "[失败]"}[level]
    print(f"{tag} {name}" + (f" — {detail}" if detail else ""), flush=True)
    if fix and fix not in fixes:
        fixes.append(fix)


def ver_tuple(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3]) or (0,)


def dist_version(name: str) -> str | None:
    try:
        from importlib.metadata import version, PackageNotFoundError
    except ImportError:  # pragma: no cover
        return None
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def check_python() -> None:
    v = sys.version_info
    exe = sys.executable
    env = os.environ.get("CONDA_DEFAULT_ENV") or ("emotune" if "emotune" in exe.lower() else "")
    detail = f"{v.major}.{v.minor}.{v.micro}  {exe}"
    if (3, 10) <= (v.major, v.minor) <= (3, 12):
        add("ok", "Python 版本 3.10–3.12", detail)
    else:
        add("fail", "Python 版本 3.10–3.12", detail, "conda create -n emotune python=3.12 pip -y")
    if env:
        add("ok", "conda 环境", env)
    else:
        add("warn", "conda 环境", "当前不是 emotune 环境（用 check-env.bat 或先 conda activate emotune）")
    if sys.maxsize <= 2**32:
        add("fail", "64 位 Python", "当前是 32 位", "重新安装 64 位 Miniconda")


def check_packages(strict: bool) -> None:
    lock = {}
    lock_file = ROOT / "requirements-lock.txt"
    if lock_file.exists():
        for line in lock_file.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^([A-Za-z0-9_.\-]+)==([^\s#]+)", line.strip())
            if m:
                lock[m.group(1).lower()] = m.group(2)
    for pip_name, (mod, lo, hi) in REQUIRED.items():
        got = dist_version(pip_name)
        if got is None:
            add("fail", f"{pip_name}", "未安装", f"pip install -r requirements.txt {MIRROR}")
            continue
        try:
            importlib.import_module(mod)
        except Exception as exc:
            add("fail", f"{pip_name} {got}", f"已安装但导入失败：{exc}", f"pip install --force-reinstall {pip_name} {MIRROR}")
            continue
        bad = ver_tuple(got) < ver_tuple(lo) or (hi and ver_tuple(got) >= ver_tuple(hi))
        rng = f">={lo}" + (f",<{hi}" if hi else "")
        if bad:
            add("fail", f"{pip_name} {got}", f"需要 {rng}", f'pip install "{pip_name}{rng}" {MIRROR}')
            continue
        want = lock.get(pip_name)
        if want and want != got:
            level = "fail" if strict else "warn"
            add(level, f"{pip_name} {got}", f"满足 {rng}；锁定版本是 {want}",
                f"pip install -r requirements-lock.txt {MIRROR}" if strict else "")
        else:
            add("ok", f"{pip_name} {got}", f"需要 {rng}")
    for name, why in FORBIDDEN.items():
        got = dist_version(name)
        if got and name.startswith("opencv") and got == dist_version("opencv-python"):
            # 同版本并存时 cv2 内容一致，能用；但升级其中一个就会出错
            add("warn", f"多装了 {name} {got}", why + "；目前版本相同能用，建议卸掉",
                f"pip uninstall -y {name} && pip install --force-reinstall opencv-python {MIRROR}")
            continue
        if got:
            add("fail", f"不应安装 {name} {got}", why, f"pip uninstall -y {name} && pip install --force-reinstall {'onnxruntime' if 'onnx' in name else 'opencv-python'} {MIRROR}")


def check_runtime() -> None:
    try:
        from tools.verify_cpu import check as cpu_check

        ok, msg = cpu_check()
        add("ok" if ok else "fail", "onnxruntime 是 CPU 版", msg, "" if ok else f"pip uninstall -y onnxruntime-gpu onnxruntime-directml && pip install --force-reinstall onnxruntime {MIRROR}")
    except Exception as exc:
        add("fail", "onnxruntime 是 CPU 版", str(exc))
    try:
        import cv2

        if hasattr(cv2, "FaceDetectorYN"):
            add("ok", "OpenCV 含 FaceDetectorYN（YuNet 人脸检测）", cv2.__version__)
        else:
            add("fail", "OpenCV 含 FaceDetectorYN", f"{cv2.__version__} 太旧", f'pip install "opencv-python>=4.8,<5" {MIRROR}')
    except Exception:
        pass
    try:
        from backend.music_emotion import ffmpeg_bin

        good = ffmpeg_bin()
    except Exception:
        good = None
    if good:
        add("ok", "ffmpeg（可选）", good)
    elif shutil.which("ffmpeg"):
        add("warn", "ffmpeg（可选）", f"{shutil.which('ffmpeg')} 无法运行（缺 DLL 或入口点）；程序会自动跳过，不影响使用",
            "conda remove -n emotune ffmpeg -y    （或修复：conda install -n emotune -c conda-forge ffmpeg --force-reinstall -y）")
    else:
        add("warn", "ffmpeg（可选）", "没有也能运行；装了能对 mp3/m4a 做旋律分析")


def check_files() -> None:
    mdir = ROOT / "static" / "models"
    for f in MODELS:
        p = mdir / f
        if p.exists() and p.stat().st_size > 50_000:
            add("ok", f"模型 {f}", f"{p.stat().st_size / 1e6:.1f} MB")
        else:
            add("warn", f"模型 {f}", "缺失；首次启动联网时会自动下载")
    for d in ("static/demo", "static/audio", "static/covers", "data"):
        p = ROOT / d
        if p.exists():
            n = sum(1 for _ in p.rglob("*") if _.is_file())
            add("ok", f"目录 {d}", f"{n} 个文件")
        else:
            add("warn", f"目录 {d}", "不存在（首次运行会创建）")
    port = int(os.environ.get("PORT") or 5000)
    with socket.socket() as s:
        s.settimeout(0.3)
        busy = s.connect_ex(("127.0.0.1", port)) == 0
    if busy:
        add("warn", f"端口 {port}", "已被占用（服务可能已在运行；否则先关掉占用的程序）")
    else:
        add("ok", f"端口 {port}", "空闲，可启动")


def check_run() -> None:
    try:
        t0 = time.perf_counter()
        from backend.emotion import get_recognizer

        rec = get_recognizer()
        load = time.perf_counter() - t0
        img = None
        for name in ("happy.jpg", "08-喜-喜悦-happy.jpg"):
            p = ROOT / "static" / "demo" / name
            if p.exists():
                img = p.read_bytes()
                break
        if img is None:
            add("warn", "识别冒烟测试", f"模型加载 {load:.1f} 秒；没有示例照片可测")
            return
        rec.predict_bytes(img, want_crop=False)  # 预热
        t1 = time.perf_counter()
        res = rec.predict_bytes(img, want_crop=False)
        ms = (time.perf_counter() - t1) * 1000
        emo = (res.get("emotion") or {}).get("id")
        t2 = time.perf_counter()
        for _ in range(5):
            rec.predict_track_bytes(img)
        tms = (time.perf_counter() - t2) * 1000 / 5
        if emo == "happy":
            add("ok", "识别冒烟测试", f"示例喜悦照 → {emo}；模型加载 {load:.1f} 秒，识别 {ms:.0f} ms，实时追踪 {tms:.0f} ms/帧")
        else:
            add("fail", "识别冒烟测试", f"示例喜悦照识别成 {emo}（{res.get('error') or ''}）")
        if tms > 150:
            add("warn", "实时追踪速度", f"{tms:.0f} ms/帧偏慢，电脑较旧或后台程序多；可用单人近场模式")
    except Exception as exc:
        add("fail", "识别冒烟测试", f"{type(exc).__name__}: {exc}", f"pip install -r requirements.txt {MIRROR}")


def main() -> int:
    args = set(sys.argv[1:])
    print("心弦 EmoTune 环境检测\n" + "=" * 40)
    check_python()
    check_packages("--strict" in args)
    check_runtime()
    check_files()
    if "--no-run" not in args:
        check_run()
    fails = [r for r in results if r[0] == "fail"]
    warns = [r for r in results if r[0] == "warn"]
    print("=" * 40)
    print(f"通过 {len(results) - len(fails) - len(warns)} 项，提醒 {len(warns)} 项，失败 {len(fails)} 项")
    if fixes and not fails:
        print("\n建议（可选，在 conda activate emotune 后执行）：")
        for f in fixes:
            print("  " + f)
    if fails:
        print("\n修复方法（在已激活 emotune 的命令行里依次执行）：")
        print("  conda activate emotune")
        for f in fixes:
            print("  " + f)
        print("\n修好后再运行一次本检测。")
        return 1
    print("环境满足要求，可以双击 run.bat 启动。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
