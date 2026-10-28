# -*- coding: utf-8 -*-
"""核对 onnxruntime 是 pip 的 CPU 包，没有 CUDA / DirectML。

官方 CPU wheel 在 Windows 上可能同时列出 AzureExecutionProvider（云推理占位），
只要没有 CUDA / TensorRT / DirectML / ROCm 即视为 CPU 包。
"""
from __future__ import annotations

import sys


GPU_PROVIDERS = (
    "CUDAExecutionProvider",
    "TensorrtExecutionProvider",
    "DmlExecutionProvider",
    "ROCMExecutionProvider",
)


def check() -> tuple[bool, str]:
    try:
        import onnxruntime as ort
    except Exception as exc:
        return False, f"无法导入 onnxruntime：{exc}。请 pip install onnxruntime（CPU 包）"

    providers = list(ort.get_available_providers())
    device = ""
    try:
        device = str(ort.get_device())
    except Exception:
        device = "?"

    gpu = [p for p in providers if p in GPU_PROVIDERS]
    if "CPUExecutionProvider" not in providers:
        return False, f"没有 CPUExecutionProvider：{providers} device={device}"
    if gpu:
        return (
            False,
            "装到了 GPU 版 onnxruntime（"
            + ", ".join(gpu)
            + f"）device={device}。请卸载后改用 CPU 包：\n"
            "  python -m pip uninstall -y onnxruntime-gpu onnxruntime-directml onnxruntime\n"
            "  python -m pip install onnxruntime",
        )
    loc = getattr(ort, "__file__", "")
    return True, f"{ort.__version__} providers={providers} device={device} {loc}"


def main() -> int:
    ok, detail = check()
    print(("PASS" if ok else "FAIL"), "onnxruntime CPU", "—", detail)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
