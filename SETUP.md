# 当AI遇见旋律：换电脑完整部署说明

品牌 **心弦 EmoTune**。本页写给要把**这一版原样**装到另一台 Windows 电脑、并从零跑起来的人，**包含情绪足迹怎么带走**。固定版本、标签和如何回到某一版，见 [VERSION.md](VERSION.md)。

当前快照：**2026-10-28 10:43** · 标签 `snapshot-20261028-1043` · 仓库 [Abner199/emoMusic-grok-20261027-2210](https://github.com/Abner199/emoMusic-grok-20261027-2210)

静态介绍页（不能跑摄像头）：https://emomusic-grok-20261028-1043.surge.sh

---

## 0. 先弄清两件事

1. **识曲必须在本机跑 Flask。** Surge 只放介绍页，没有 Python、没有 ONNX、没有摄像头。
2. **情绪足迹不进 GitHub。** 仓库里故意没有你的人脸截图和听歌记录。换电脑要「连历史一起原样」，必须把本机数据单独带走，见第 6 节。

克隆仓库 = 代码 + 模型 + 280 首试听 + 演示图。  
克隆仓库 **再** 解入足迹包 = 和旧电脑一样能认出人、能播、能看到以前的足迹。

---

## 1. 新电脑需要准备什么

| 项 | 要求 |
| --- | --- |
| 系统 | Windows 10 或 11，64 位 |
| Python | **3.10 或 3.11**（已验证 3.11）。安装时勾选 `Add python.exe to PATH` |
| Git | 从 GitHub 克隆时需要 [Git for Windows](https://git-scm.com/download/win) |
| 浏览器 | Chrome 或 Edge（摄像头、屏幕分享用） |
| 磁盘 | 约 1 GB（代码 + 三个 ONNX + 280 首试听）；足迹另计 |
| 网络 | 首次若缺模型会下载；平时可完全离线识别和播本地曲 |
| 摄像头 | 本机摄像头；页面必须用 `http://127.0.0.1:端口` 打开 |

不需要 CUDA，不需要 ffmpeg。装了 ffmpeg 也只是以后给旋律分析用，当前人声试听是 m4a 缓存。

检查 Python：

```bat
python --version
```

应看到 `Python 3.10.x` 或 `3.11.x`。若提示不是内部命令：重新安装 Python 并勾选 PATH，或把下面所有 `python` 换成 `py -3.11`。

---

## 2. 把项目放到新电脑

任选一种。**推荐 A（Git 克隆固定标签）**，这样一定是这一版。**方式 B（整夹拷贝）** 会连足迹一起带走，适合 U 盘搬家。

### 方式 A：从 GitHub 克隆这一版（推荐，不含旧足迹）

新电脑安装 Git 后：

```bat
git clone https://github.com/Abner199/emoMusic-grok-20261027-2210.git
cd emoMusic-grok-20261027-2210
git checkout snapshot-20261028-1043
```

`main` 一般已指向最新快照；用标签可以精确钉在这一版，避免以后 `main` 再往前走时你跟丢。

私有仓库：第一次克隆若要登录，用有权限的 GitHub 账号。`gh auth login` 或浏览器登录均可。

### 方式 B：U 盘 / 网盘拷整个文件夹（连历史一起）

把原来电脑上的 `emoMusic` 目录**完整复制**过去。路径可以含中文，例如：

`E:\F_当AI遇见旋律\Grok20261023_当AI遇见旋律\emoMusic`

OpenCV 读 ONNX 已按内存加载，中文路径可用。

不要只拷 `app.py`。需要整棵目录，尤其是：

| 路径 | 作用 |
| --- | --- |
| `app.py` `config.py` `run.bat` | 入口 |
| `backend/` | 识别、推荐、歌词、足迹 |
| `templates/` `static/css/` `static/js/` | 网页 |
| `static/models/` | 三个人脸 ONNX，缺了不能识别 |
| `static/audio/` | 本地 280 首试听 |
| `static/covers/` | 封面 |
| `static/demo/` | 演示表情图 |
| `data/history.json` | **情绪足迹索引（历史）** |
| `static/history/` | **足迹里的人脸截图** |
| `data/prefs.json` | 主题、检测方式等本机偏好 |
| `requirements.txt` | 依赖清单 |

拷完在新电脑项目根目录执行第 3、4 步（依赖 + 启动）。若旧电脑已经装过依赖且你拷的是带 `.venv` 的目录，一般仍建议在新电脑重装一次依赖。

### 方式 C：Git 克隆 + 单独恢复足迹（推荐给「代码用仓库、历史用打包」）

1. 在**旧电脑**项目根目录打包足迹（见第 6 节）。
2. 在**新电脑**按方式 A 克隆并检出 `snapshot-20261028-1043`。
3. 把 `emotune-local-data.zip` 拷到新项目的 `data\` 下，运行解包脚本。
4. 再启动 Flask。

---

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

---

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

用 **Chrome 或 Edge** 打开：

**http://127.0.0.1:5000**

网页标题应为：`当AI遇见旋律：从表情感知到智能音乐推荐`。标签页图标是夜金底上的金色弦琴。

### 端口被占用

本机若已有别的程序占着 5000：

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

1. 地址必须是 `127.0.0.1` 或 `localhost`，不要用局域网 IP，也不要用 `http://电脑名:5000`。
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

---

## 5. 核对接好了

```bat
python tests/selfcheck.py
```

关注：示例图 28 张都能识别；「单人精检稳健测试 ≥90%」；说明页含 HSEmotion 与 TTA；本地曲库 280 首。

服务已启动时（端口换成你的）：

```bat
set EMOTUNE_BASE=http://127.0.0.1:5000
python tests/test_full_ui.py
```

若本机开了 Clash 等代理，自检里「离线推荐 <1s」或个别在线接口可能变慢，把终端代理关掉再测，或把浏览器设为「绕过 127.0.0.1」。Playwright 测试已加 `--no-proxy-server`。

页面上再点一次「历史」：若按第 6 节恢复过足迹，应能看到旧记录、人脸截图和播过的歌。

---

## 6. 情绪足迹（历史记录）怎么原样带走

足迹是**个人数据**，仓库和 Surge 都不会带。位置：

| 路径 | 内容 |
| --- | --- |
| `data/history.json` | 全部识别记录、已播歌曲索引（不截断） |
| `static/history/*.jpg` | 每条足迹对应的人脸截图 |
| `data/prefs.json` | 主题、单人/多人、推荐方式等 |

缺截图时页面仍能列出足迹文字，人脸格子会空。缺 `history.json` 则历史是空的，不影响识别和播放。

### 6.1 整夹拷贝（最省事）

方式 B 已经包含这三项。拷完直接启动即可。

### 6.2 打包脚本（Git 克隆后单独恢复）

**在旧电脑**项目根目录：

```bat
python tools\pack_local_data.py
```

或双击 `tools\pack-local-data.bat`。

会生成 `data\emotune-local-data.zip`（含 `history.json`、`prefs.json`、全部历史人脸图）。把这个 zip 拷到 U 盘或网盘。

**在新电脑**（已经按方式 A 检出本快照、装好依赖）：

1. 把 zip 放到新项目的 `data\emotune-local-data.zip`（或项目根目录同名）。
2. 运行：

```bat
python tools\pack_local_data.py --unpack data\emotune-local-data.zip
```

或双击 `tools\unpack-local-data.bat`。

3. 启动 `python app.py`，浏览器打开页面，点「历史」。

可重复解包：后解的文件覆盖同名文件。建议先停掉 Flask 再解包。

### 6.3 手动拷贝

旧电脑 → 新电脑，保持相对路径不变：

```
旧:  ...\emoMusic\data\history.json
新:  ...\emoMusic\data\history.json

旧:  ...\emoMusic\data\prefs.json
新:  ...\emoMusic\data\prefs.json

旧:  ...\emoMusic\static\history\*.jpg
新:  ...\emoMusic\static\history\
```

目录不存在就新建。不要改 json 里的截图文件名。

### 6.4 不要把足迹推进 Git

`.gitignore` 已排除：

- `data/history.json`
- `data/prefs.json`
- `static/history/`
- `data/emotune-local-data.zip`

不要 `git add -f` 它们。不要把真实人脸传到 GitHub。

---

## 7. 日常使用要点

1. 检测方式默认 **单人精检**（近景一张脸，高精度）。课堂合影再切 **多人远场**。
2. 四种输入：摄像头、照片（JPG/PNG/WEBP）、本地视频、屏幕分享。
3. 「实时捕捉」可持续识曲；「识别此刻」截一帧并关掉实时捕捉。问号上的说明要**把鼠标放到问号上**才出现。
4. 默认在线曲库；关掉「在线曲库」只用本地 280 首。在线长时间失败会自动切本地。
5. 歌词能联网时用官方词并对齐 30 秒试听；断网用本地词。
6. 完整算法说明：http://127.0.0.1:5000/guide

---

## 8. 从固定版本恢复 / 继续开发

回到**这一版**：

```bat
git fetch --tags
git checkout snapshot-20261028-1043
python -m pip install -r requirements.txt
python app.py
```

回到 2026-10-28 09:51（280 首，尚无本版歌词对齐与快速人脸框）：

```bat
git checkout snapshot-20261028-0951
```

回到 2026-10-27 22:10（本地曲 **224** 首）：

```bat
git checkout snapshot-20261027-2210
```

在本快照上继续改代码（不要直接改标签指向的提交）：

```bat
git checkout -b dev/continue snapshot-20261028-1043
```

对比当前与本快照：

```bat
git diff snapshot-20261028-1043
```

更完整的标签说明见 [VERSION.md](VERSION.md)。

---

## 9. 关于 Surge 静态页

识别和播放跑在本机 Flask 上，**Surge 不能跑 Python / ONNX / 摄像头**。

本快照的静态介绍：

https://emomusic-grok-20261028-1043.surge.sh

上一版介绍页仍在：https://emomusic-grok-20261028.surge.sh （对应 `snapshot-20261028-0951`）

那一页不能代替 `python app.py`。真正用摄像头识曲，仍按上面第 4 步在本机启动。

域名规则：`emomusic-grok-版本号.surge.sh`，必须小写。本版版本号为 `20261028-1043`。

---

## 10. 常见问题

**页面是旧的标题、旧图标，或问号说明一直挡在画面上**  
强制刷新：Ctrl+F5。本快照静态资源带 `?v=52`。

**提示缺少人脸检测模型**  
把 `static/models/` 三个 `.onnx` 拷齐，或联网后重新 `python app.py`。

**识别成「未检测到人脸」**  
切到「单人精检」，正对镜头、光线均匀、脸足够大。远景合影请切「多人远场」。

**在线歌一直失败**  
关掉系统代理后再试，或关闭「在线曲库」用本地歌。

**换电脑后历史是空的**  
只克隆了仓库。按第 6 节解包或拷贝 `data/history.json` 与 `static/history/`。

**Git 推送不要带足迹**  
见 6.4。

**旧电脑路径有中文，新电脑没有（或反过来）**  
可以。项目不依赖盘符和中文路径；ONNX 已内存加载。足迹 json 里的截图是相对 `/static/history/...`，换盘符不用改。
