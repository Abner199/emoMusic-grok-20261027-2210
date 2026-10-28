# 当AI遇见旋律：换电脑配置与启动

品牌 **心弦 EmoTune**。本页写给要把项目拷到另一台 Windows 电脑、从零跑起来的人。固定版本、标签和如何回到某一版，见 [VERSION.md](VERSION.md)。

当前快照：**2026-10-28 09:51** · 标签 `snapshot-20261028-0951` · 仓库 [Abner199/emoMusic-grok-20261027-2210](https://github.com/Abner199/emoMusic-grok-20261027-2210)

## 1. 新电脑需要准备什么

| 项 | 要求 |
| --- | --- |
| 系统 | Windows 10 或 11，64 位 |
| Python | **3.10 或 3.11**（已验证 3.11）。安装时勾选 `Add python.exe to PATH` |
| 浏览器 | Chrome 或 Edge（摄像头、屏幕分享用） |
| 磁盘 | 约 1 GB（代码 + 三个 ONNX + 280 首试听） |
| 网络 | 首次若缺模型会下载；平时可完全离线识别和播本地曲 |
| 摄像头 | 本机摄像头；必须用 `http://127.0.0.1:端口` 打开页面 |

不需要 CUDA、不需要 ffmpeg。装了 ffmpeg 也只是以后给旋律分析用，当前人声试听是 m4a 缓存。

检查 Python：

```bat
python --version
```

应看到 `Python 3.10.x` 或 `3.11.x`。若提示不是内部命令：重新安装 Python 并勾选 PATH，或用 `py -3.11` 代替下面所有 `python`。

## 2. 把项目放到新电脑

任选一种。

### 方式 A：从 GitHub 克隆（推荐）

新电脑安装 [Git](https://git-scm.com/download/win) 后：

```bat
git clone https://github.com/Abner199/emoMusic-grok-20261027-2210.git
cd emoMusic-grok-20261027-2210
git checkout snapshot-20261028-0951
```

`main` 一般已指向最新快照；用标签可以精确回到这一版。

### 方式 B：U 盘 / 网盘拷整个文件夹

把原来电脑上的 `emoMusic` 目录完整复制过去。路径可以含中文，例如：

`E:\F_当AI遇见旋律\Grok20261023_当AI遇见旋律\emoMusic`

OpenCV 读 ONNX 已按内存加载，中文路径可用。

不要只拷 `app.py`。需要整棵目录，尤其是：

- `static/models/` 三个人脸模型
- `static/audio/` 本地试听
- `static/covers/` 封面
- `static/demo/` 演示表情图
- `backend/` `templates/` `tests/`

### 不要拷进 Git、但换电脑时可能要带走的本机数据

这些文件写的是你自己的脸和听歌记录，仓库里故意没有：

| 路径 | 内容 |
| --- | --- |
| `data/history.json` | 情绪足迹索引 |
| `static/history/*.jpg` | 足迹里的人脸截图 |
| `data/prefs.json` | 主题、检测方式等本机偏好 |

要在新电脑接着看旧足迹：把上面三项从旧电脑拷到新项目的同样位置。只克隆仓库会得到空足迹，不影响识别和播放。

## 3. 安装依赖

在项目根目录（能看见 `app.py` 的那一层）：

```bat
python -m pip install -r requirements.txt
```

依赖：`flask`、`opencv-python`、`numpy`、`pillow`、`requests`、`scipy`、`onnxruntime`。

可选（跑界面自检时才要）：

```bat
python -m pip install playwright
python -m playwright install chromium
```

若 `pip` 很慢，可用清华源：

```bat
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 4. 启动

双击 `run.bat`，或：

```bat
python app.py
```

看到类似：

```
心弦 EmoTune  http://0.0.0.0:5000
HSEmotion EfficientNet-B0 已加载
```

用浏览器打开：

**http://127.0.0.1:5000**

网页标题应为：`当AI遇见旋律：从表情感知到智能音乐推荐`。标签页图标是夜金底上的金色弦琴。

### 端口被占用

本机若已有别的「当AI遇见旋律」占着 5000：

```bat
set EMOTUNE_PORT=18765
python app.py
```

然后打开 http://127.0.0.1:18765 。也可以设主机：

```bat
set EMOTUNE_HOST=127.0.0.1
set EMOTUNE_PORT=18765
python app.py
```

### 摄像头打不开

1. 地址必须是 `127.0.0.1` 或 `localhost`，不要用局域网 IP。
2. 浏览器允许此站点使用摄像头。
3. 关掉其他占用摄像头的软件（会议、旧的人脸窗）。
4. 页面上用摄像头下拉框换设备。

### 第一次启动会做什么

`backend/assets.py` 会检查：

- `static/models/face_detection_yunet_2023mar.onnx`
- `static/models/facial_expression_recognition_mobilefacenet_2022july.onnx`
- `static/models/enet_b0_8_best_vgaf.onnx`（HSEmotion，约 16 MB）
- 本地 280 首试听与封面

本快照一般已经带齐，会直接跳过下载。缺文件且能上网时会自动补。完全断网且缺模型时，识别会失败，把旧电脑的 `static/models/` 拷过来即可。

## 5. 核对接好了

```bat
python tests/selfcheck.py
```

关注：示例图 28 张都能识别；「单人精检稳健测试 ≥90%」；说明页含 HSEmotion 与 TTA。

服务已启动时（端口换成你的）：

```bat
set EMOTUNE_BASE=http://127.0.0.1:5000
python tests/test_full_ui.py
```

若本机开了 Clash 等代理，自检里「离线推荐 <1s」或个别在线接口可能变慢，把终端代理关掉再测，或把浏览器设为「绕过 127.0.0.1」。Playwright 测试已加 `--no-proxy-server`。

## 6. 日常使用要点

1. 检测方式默认 **单人精检**（近景一张脸，高精度）。课堂合影再切 **多人远场**。
2. 四种输入：摄像头、照片（JPG/PNG/WEBP）、本地视频、屏幕分享。
3. 「实时捕捉」可持续识曲；「识别此刻」截一帧并关掉实时捕捉。
4. 默认在线曲库；关掉「在线曲库」只用本地 280 首。在线长时间失败会自动切本地。
5. 完整算法说明：http://127.0.0.1:5000/guide

## 7. 从固定版本恢复 / 继续开发

回到这一版：

```bat
git fetch --tags
git checkout snapshot-20261028-0951
python -m pip install -r requirements.txt
python app.py
```

回到上一版（2026-10-27 22:10，本地曲 224 首）：

```bat
git checkout snapshot-20261027-2210
```

在快照上继续改代码：

```bat
git checkout -b dev/continue snapshot-20261028-0951
```

对比当前与本快照：

```bat
git diff snapshot-20261028-0951
```

更完整的标签说明见 [VERSION.md](VERSION.md)。

## 8. 关于 Surge 静态页

识别和播放跑在本机 Flask 上，**Surge 不能跑 Python / ONNX / 摄像头**。

本快照另有一页静态介绍，方便用手机或别人电脑看说明、仓库和启动步骤：

https://emomusic-gt-20261028.surge.sh

那一页不能代替 `python app.py`。真正用摄像头识曲，仍按上面第 4 步在本机启动。

## 9. 常见问题

**页面是旧的标题或旧图标**  
强制刷新：Ctrl+F5。静态资源带 `?v=50`。

**提示缺少人脸检测模型**  
把 `static/models/` 三个 `.onnx` 拷齐，或联网后重新 `python app.py`。

**识别成「未检测到人脸」**  
切到「单人精检」，正对镜头、光线均匀、脸足够大。远景合影请切「多人远场」。

**在线歌一直失败**  
关掉系统代理后再试，或关闭「在线曲库」用本地歌。

**Git 推送不要带上面的足迹文件**  
`.gitignore` 已排除 `data/history.json`、`data/prefs.json`、`static/history/`。不要 `git add -f` 它们。
