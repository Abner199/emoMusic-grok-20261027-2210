# 心弦 EmoTune 固定版本

仓库始终是 [Abner199/emoMusic-grok-20261027-2210](https://github.com/Abner199/emoMusic-grok-20261027-2210)（已公开）。下面每一版都有独立 Git 标签，互不覆盖。

换电脑的逐步说明（conda 环境 `emotune` + Python 3.12 + CPU onnxruntime + 情绪足迹）见 [SETUP.md](SETUP.md)。

---

## 当前快照 2026-10-31 08:16 · 歌词对齐 501 首 + 实时检测开关 + 播放控制修复

| 项 | 内容 |
| --- | --- |
| 快照时间 | **2026-10-31 08:16** |
| Git 标签 | `snapshot-20261031-0816` |
| 发布名 | 心弦 EmoTune 快照 2026-10-31 08:16 |
| 分支 | `main` |
| 说明页 | https://emomusic-grok-20261031-0816.surge.sh |
| Python | 3.12（conda 环境 `emotune`），CPU 版 `onnxruntime` |
| 情绪足迹 | 1057 条记录与全部人脸截图，已在仓库里 |
| 部署文档 | [换电脑-整夹复制即用.md](换电脑-整夹复制即用.md)（整夹拷贝）· [SETUP.md](SETUP.md)（完整说明） |

### 这一版相对 `snapshot-20261030-1230` 做了什么

- **歌词对齐 474 → 501 首**：歌词搜索要求歌名相像（修好《日不落》《来自天堂的魔鬼》《差不多姑娘》等拿错词的歌），QQ 搜不到时用网易云补；语音识别按歌名强制中文 / 英文，难识别的歌改用 Whisper medium。剩 31 首多为快嘴说唱，仍用旧方法
- **播放控制**：暂停后不再被实时识别自动恢复；新增 ■ 停止（停歌 + 关实时检测）。识别此刻、上传照片、点歌、回放足迹会恢复播放
- **顶栏「实时检测 开/关」**：关掉后停识别、停人脸框，画面保留
- **摄像头一开默认实时捕捉并自动连播**（本机 `localStorage` 设 `emotune-auto-live=0` 可关）
- **弹出人脸窗**：只剩铺满整窗的实时画面与人脸框，无外框、无按钮、无左上角文字，比例不低于 100%
- **人脸框更跟手**：取样 200ms → 90ms、送检画面 720 → 640、平滑系数 0.22 → 0.38
- **情绪概率条整行显示**，Russell 坐标并排；**声学分析可展开 / 缩小 / 折叠**（默认缩小）
- 新增 `换电脑-整夹复制即用.md`

### 快速恢复这一版（继续开发请从这里开分支）

```bat
git clone https://github.com/Abner199/emoMusic-grok-20261027-2210.git
cd emoMusic-grok-20261027-2210
git checkout snapshot-20261031-0816
git switch -c dev-from-20261031-0816
tools\setup-conda.bat
run.bat
```

浏览器打开 http://127.0.0.1:5000 。本机已有目录：`git fetch --tags && git checkout snapshot-20261031-0816`。

以前的快照标签全部保留，不被覆盖。

---

## 以前的快照 2026-10-30 12:30 · 歌词语音对齐 + 界面重排 + 足迹入库

| 项 | 内容 |
| --- | --- |
| 快照时间 | **2026-10-30 12:30** |
| Git 标签 | `snapshot-20261030-1230` |
| 发布名 | 心弦 EmoTune 快照 2026-10-30 12:30 |
| 分支 | `main` |
| 说明页 | https://emomusic-grok-20261030-1230.surge.sh |
| Python | 3.12（conda 环境 `emotune`），CPU 版 `onnxruntime` |
| 自检 | `selfcheck.py` 与 6 个浏览器测试全部通过 |
| 部署文档 | [SETUP.md](SETUP.md)（换电脑原版还原，含足迹） |

### 这一版相对 `snapshot-20261030-0838` 做了什么

- **歌词准了**：以前靠本地猜的锚点词定位 30 秒试听，常整段错位。现在用 Whisper 把 532 段试听转成文字，再与 QQ 官方 LRC 比对算出起点；474 首写入 `data/lyrics_aligned.json`，断网也准。工具：`tools/asr_previews.py`、`tools/align_lyrics.py`
- 修复切歌时用上一首时长请求歌词；开唱前显示 ♪ 并预告第一句
- **顶栏一行**：摄像头 / 照片 / 视频 / 屏幕、弹出人脸窗、识别此刻都在最上面；删去「情绪识别」标题
- **摄像头默认铺满左区块**（右区块保留），右下角可切默认尺寸、放大缩小；设置 → 画面也可调比例、复原
- **照片直接进入检测区**：选图、拖入、单击/双击示例即在左侧大图上画人脸框、关键点、表情与 AU 标签；双击照片重测
- 界面收紧：顶栏整条、间距更紧、说明文字两行折叠、足迹改自适应网格
- 修复「实时捕捉」问号说明移开后不收起；更新三个过时的浏览器测试
- **情绪足迹入库**：`data/history.json`、`data/prefs.json`、`static/history/`（约 790 条、4757 张人脸图）提交进仓库，克隆即原样还原。仓库公开，这些照片任何人可见

### 快速恢复这一版（继续开发请从这里开分支）

```bat
git clone https://github.com/Abner199/emoMusic-grok-20261027-2210.git
cd emoMusic-grok-20261027-2210
git checkout snapshot-20261030-1230
git switch -c dev-from-20261030-1230
tools\setup-conda.bat
run.bat
```

浏览器打开 http://127.0.0.1:5000 ，点「历史」应看到全部足迹。本机已有目录：`git fetch --tags && git checkout snapshot-20261030-1230`。

以前的快照标签全部保留，不被覆盖。

---

## 以前的快照 2026-10-30 08:38 · 532 首曲库 + 日常/高潮情绪分级

| 项 | 内容 |
| --- | --- |
| 快照时间 | **2026-10-30 08:38** |
| Git 标签 | `snapshot-20261030-0838` |
| 发布名 | 心弦 EmoTune 快照 2026-10-30 08:38 |
| 分支 | `main` |
| Python | 3.12（conda 环境 `emotune`），CPU 版 `onnxruntime` |
| 自检 | `python tests/selfcheck.py` 全部通过 |

### 这一版相对 `snapshot-20261028-1525` 做了什么

- 本地曲库从 280 首扩到 **532 首**（每类 76 首），中文优先，少量网红英文；新增 252 首试听与封面
- 情绪分级：平静、喜悦、悲伤为日常三类，多确认一会儿再换歌；惊讶、恐惧、愤怒、厌恶为高潮四类，认到后立刻锁反差歌单
- 人脸框、此刻情绪、播放器、可视化与语音提示共用同一确认标签；语音提示随此刻节奏播报
- 在线热歌源扩充：苹果热歌榜 / 热播 / 亚洲热歌、网易云与 QQ 热歌榜、Deezer、Audius
- 新增 `static/js/face-draw.js`（人脸框绘制拆分），新增测试 `test_live_calibrate.py`、`test_voice_once.py`

### 快速恢复这一版（继续开发请从这里开分支）

```bat
git clone https://github.com/Abner199/emoMusic-grok-20261027-2210.git
cd emoMusic-grok-20261027-2210
git checkout snapshot-20261030-0838
git switch -c dev-from-20261030
conda create -n emotune python=3.12 pip -y
conda activate emotune
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python tools\verify_cpu.py
python app.py
```

本机已有目录：`git fetch --tags && git checkout snapshot-20261030-0838`，然后 `conda activate emotune`、`python app.py`，打开 http://127.0.0.1:5000 。

以前的快照标签（`snapshot-20261028-1525` 等）全部保留，不被覆盖。

---

## 以前的快照 2026-10-28 15:25 · 小学 40 分钟成功场

**【20261028日  小学40分钟  10月28日下午15:25-16:05】**

这场小学 40 分钟讲座比较成功。本标签把当时实际使用的软件系统固定下来，方便以后直接恢复、继续开发。功能与 `snapshot-20261028-1252` 相同，这一版专门标记这场课。

| 项 | 内容 |
| --- | --- |
| 快照时间 | **2026-10-28 15:25–16:05**（小学 40 分钟） |
| 用途 | **20261028日 小学40分钟 10月28日下午15:25-16:05** |
| 仓库 | [Abner199/emoMusic-grok-20261027-2210](https://github.com/Abner199/emoMusic-grok-20261027-2210)（公开） |
| Git 标签 | `snapshot-20261028-1525` |
| 发布名 | 心弦 EmoTune 20261028 小学40分钟 15:25-16:05 |
| 分支 | `main` |
| 说明页 | https://emomusic-grok-20261028-1252.surge.sh （软件相同） |
| Python | **3.12**（conda 新建空环境 `emotune`，已验证 3.12.16） |
| 推理 | **CPU 版** pip 包 `onnxruntime` |
| 网页标题 | 当AI遇见旋律：从表情感知到智能音乐推荐 |

克隆后用 用标签 `snapshot-20261028-1525` 可以随时精确回到这场小学课用的系统。

上一版 `snapshot-20261028-1252`（讲座准备）、`snapshot-20261028-1105`、`snapshot-20261028-1043`、`snapshot-20261028-0951` 与 `snapshot-20261027-2210`（224 首）仍然保留，**不会被本标签覆盖**。

### 这一版相对上一版做了什么

- 把 **2026-10-28 下午 15:25–16:05 小学 40 分钟成功讲座** 打成独立可恢复版本
- 软件与 12:52 讲座准备版相同：conda `emotune` + Python 3.12 + CPU onnxruntime + 280 首 + 足迹打包
- 现场已跑通：本机 http://127.0.0.1:5000

### 快速恢复这一版（继续开发请从这里开分支）

```bat
git clone https://github.com/Abner199/emoMusic-grok-20261027-2210.git
cd emoMusic-grok-20261027-2210
git checkout snapshot-20261028-1525
conda create -n emotune python=3.12 pip -y
conda activate emotune
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python tools\verify_cpu.py
python app.py
```

也可双击 `tools\setup-conda.bat`，再双击 `run.bat`。浏览器打开 [http://127.0.0.1:5000](http://127.0.0.1:5000)。

本机已有目录：

```bat
cd /d E:\F_当AI遇见旋律\Grok20261023_当AI遇见旋律\emoMusic
git fetch --tags
git checkout snapshot-20261028-1525
conda activate emotune
python app.py
```

### 从这一版继续开发

```bat
git fetch --tags
git checkout snapshot-20261028-1525
git checkout -b dev/continue snapshot-20261028-1525
conda activate emotune
```

随时回到这场小学课用的系统：

```bat
git fetch --tags
git switch --detach snapshot-20261028-1525
conda activate emotune
```

对比当前代码和本快照：

```bat
git diff snapshot-20261028-1525
```

不要把 `data/history.json`、`static/history/`、`data/emotune-local-data.zip` 加进 Git。逐步部署见 [SETUP.md](SETUP.md)。

---

## 上一版快照 2026-10-28 12:52 · 讲座准备版

| 项 | 内容 |
| --- | --- |
| 快照时间 | **2026-10-28 12:52**（本地） |
| 用途 | **今天讲座版本系统** |
| 仓库 | [Abner199/emoMusic-grok-20261027-2210](https://github.com/Abner199/emoMusic-grok-20261027-2210)（公开） |
| Git 标签 | `snapshot-20261028-1252` |
| 发布名 | 心弦 EmoTune 讲座快照 2026-10-28 12:52 |
| 分支 | 当时的 `main` |
| Surge 介绍页 | https://emomusic-grok-20261028-1252.surge.sh |
| Python | **3.12**（conda 新建空环境 `emotune`，已验证 3.12.16） |
| 推理 | **CPU 版** pip 包 `onnxruntime`（不要 GPU / 不要 conda-forge CUDA） |
| 网页标题 | 当AI遇见旋律：从表情感知到智能音乐推荐 |

`snapshot-20261028-1252` 是讲座准备版。该标签本身不移动。小学 40 分钟成功场见 `snapshot-20261028-1525`。

上一版 `snapshot-20261028-1105`、`snapshot-20261028-1043`、`snapshot-20261028-0951` 与更早的 `snapshot-20261027-2210`（224 首）仍然保留，**不会被本标签覆盖**。

### 这一版相对上一版做了什么

- 固定为 **今天讲座版本**：现场演示、换电脑原样部署都以这一标签为准
- **CPU 版 onnxruntime** 打进快照：`requirements.txt` 只写 pip 包 `onnxruntime`；`tools/verify_cpu.py`；启动与自检会核对 `device=CPU`
- 禁止 `conda install onnxruntime`（conda-forge 会拉约 2 GB CUDA）
- `SETUP.md` 按讲座重写：10 分钟清单、必须新建**空**环境 `emotune`、pip 冲突警告怎么处理、足迹怎么原样带走
- 功能与 11:05 相同：官方歌词对齐、快速人脸框、问号悬停说明、足迹打包、本地 280 首、九种推荐、四种输入

MobileFaceNet 在 RAF-DB 上的公开评测仍是 **88.27%**。本机 ≥90% 是示例图稳健测试目标。本机核对：示例图 28/28，稳健 140/140。

### 未写入 Git 的本机数据

- `data/history.json` 情绪足迹索引
- `static/history/*.jpg` 历史人脸截图
- `data/prefs.json` 本机主题偏好
- `data/emotune-local-data.zip` 足迹打包（若生成过）

conda 环境 `emotune` 在用户目录，也不进 GitHub。换电脑要重新 `conda create`。

换电脑带走足迹：整夹拷贝，或旧电脑 `tools\pack-local-data.bat`，新电脑解包。详见 [SETUP.md 第 8 节](SETUP.md)。

### 快速恢复讲座这一版

环境：Windows 10/11，**Miniconda3 / Anaconda3**，conda 环境 `emotune`，**Python 3.12**，Chrome 或 Edge。逐步说明见 [SETUP.md](SETUP.md)。

```bat
git clone https://github.com/Abner199/emoMusic-grok-20261027-2210.git
cd emoMusic-grok-20261027-2210
git checkout snapshot-20261028-1252
conda create -n emotune python=3.12 pip -y
conda activate emotune
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python tools\verify_cpu.py
python app.py
```

也可双击 `tools\setup-conda.bat` 再建环境，再双击 `run.bat`。

浏览器打开 [http://127.0.0.1:5000](http://127.0.0.1:5000)。摄像头必须用这个地址（或 localhost）。

若 5000 已被占用：

```bat
conda activate emotune
set EMOTUNE_PORT=18765
python app.py
```

然后打开 [http://127.0.0.1:18765](http://127.0.0.1:18765)。

启动日志应含 `Python 3.12.x`、conda 环境路径，以及 `onnxruntime CPU … providers=['CPUExecutionProvider']`。本快照已含三个 ONNX 和 280 首 m4a。

恢复旧足迹（可选）：

```bat
conda activate emotune
python tools\pack_local_data.py --unpack data\emotune-local-data.zip
```

### 核对这一版还在

```bat
conda activate emotune
python tests/selfcheck.py
```

服务已启动时：

```bat
set EMOTUNE_BASE=http://127.0.0.1:5000
python tests/test_full_ui.py
```

`test_full_ui.py` 需要 Playwright：`python -m pip install playwright` 后执行 `python -m playwright install chromium`。

### 从这一版继续开发

```bat
git fetch --tags
git checkout snapshot-20261028-1252
git checkout -b dev/continue snapshot-20261028-1252
conda activate emotune
```

改代码、自检、提交、推送：

```bat
python tests/selfcheck.py
git add -A
git commit -m "说明这次改了什么"
git push -u origin dev/continue
```

`git add -A` 不会提交足迹文件。不要把 `data/history.json`、`static/history/`、`data/emotune-local-data.zip` 加进去。conda 环境也不要提交。

合并到 `main` 后，原来的标签 `snapshot-20261028-1252`、`snapshot-20261028-1105`、`snapshot-20261028-1043`、`snapshot-20261028-0951` 与 `snapshot-20261027-2210` 仍然指向各自快照。

随时回到讲座这一版：

```bat
git fetch --tags
git switch --detach snapshot-20261028-1252
conda activate emotune
```

在快照上再开新线：

```bat
git checkout -b recover/20261028-1252 snapshot-20261028-1252
```

对比当前代码和本快照：

```bat
git diff snapshot-20261028-1252
```

### 本机已有项目目录时

```bat
cd /d E:\F_当AI遇见旋律\Grok20261023_当AI遇见旋律\emoMusic
git checkout snapshot-20261028-1252
conda activate emotune
python app.py
```

远程地址应指向 `https://github.com/Abner199/emoMusic-grok-20261027-2210.git`。

### Surge 介绍页

https://emomusic-grok-20261028-1252.surge.sh

域名规则：`emomusic-grok-版本号.surge.sh`，本版版本号为 `20261028-1252`。必须小写。不能跑摄像头。

上一版介绍页仍在：https://emomusic-grok-20261028-1105.surge.sh

---

## 上一版快照 2026-10-28 11:05

| 项 | 内容 |
| --- | --- |
| 快照时间 | **2026-10-28 11:05**（本地） |
| 仓库 | [Abner199/emoMusic-grok-20261027-2210](https://github.com/Abner199/emoMusic-grok-20261027-2210)（公开） |
| Git 标签 | `snapshot-20261028-1105` |
| 发布名 | 心弦 EmoTune 快照 2026-10-28 11:05 |
| 分支 | 当时的 `main` |
| Surge 介绍页 | https://emomusic-grok-20261028-1105.surge.sh |
| Python | **3.12**（conda 新建环境 `emotune`，已验证 3.12.16） |
| 网页标题 | 当AI遇见旋律：从表情感知到智能音乐推荐 |

`snapshot-20261028-1105` 固定 conda `emotune` + Python 3.12 这一版。该标签本身不移动。CPU 版 onnxruntime 已打进后面的讲座快照 `snapshot-20261028-1252`。

上一版 `snapshot-20261028-1043`、`snapshot-20261028-0951` 与更早的 `snapshot-20261027-2210`（224 首）仍然保留，不会被本标签覆盖。

### 这一版相对上一版做了什么

- 仓库改为公开，克隆一般不用登录
- **部署必须用 conda 新建环境 `emotune`，Python 3.12**（不要用系统 Python 全局 pip）
- `environment.yml`、`tools/setup-conda.bat`、`run.bat` 会定位该环境
- `SETUP.md` 按「Miniconda → 克隆 → 建环境 → 装依赖 → 启动 → 带走足迹」重写
- `requirements.txt` 限制 Flask 3.x、OpenCV 4.x（避免误装 OpenCV 5）

功能与 10:43 快照相同：官方歌词对齐、快速人脸框、问号悬停说明、足迹打包、本地 280 首。

MobileFaceNet 在 RAF-DB 上的公开评测仍是 **88.27%**。本机 ≥90% 是示例图稳健测试目标。

### 未写入 Git 的本机数据

- `data/history.json` 情绪足迹索引
- `static/history/*.jpg` 历史人脸截图
- `data/prefs.json` 本机主题偏好
- `data/emotune-local-data.zip` 足迹打包（若生成过）

conda 环境 `emotune` 在用户目录，也不进 GitHub。换电脑要重新 `conda create`。

换电脑带走足迹：整夹拷贝，或旧电脑 `tools\pack-local-data.bat`，新电脑解包。

### 快速恢复这一版

环境：Windows 10/11，**Miniconda3 / Anaconda3**，conda 环境 `emotune`，**Python 3.12**，Chrome 或 Edge。逐步说明见 [SETUP.md](SETUP.md)。

```bat
git clone https://github.com/Abner199/emoMusic-grok-20261027-2210.git
cd emoMusic-grok-20261027-2210
git checkout snapshot-20261028-1105
conda create -n emotune python=3.12 pip -y
conda activate emotune
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python app.py
```

也可双击 `tools\setup-conda.bat` 再建环境，再双击 `run.bat`。

浏览器打开 [http://127.0.0.1:5000](http://127.0.0.1:5000)。摄像头必须用这个地址（或 localhost）。

若 5000 已被占用：

```bat
conda activate emotune
set EMOTUNE_PORT=18765
python app.py
```

然后打开 [http://127.0.0.1:18765](http://127.0.0.1:18765)。

启动日志应含 `Python 3.12.x`、conda 环境路径，以及 `onnxruntime CPU … providers=['CPUExecutionProvider']`。本快照已含三个 ONNX 和 280 首 m4a。

恢复旧足迹（可选）：

```bat
conda activate emotune
python tools\pack_local_data.py --unpack data\emotune-local-data.zip
```

### 核对这一版还在

```bat
conda activate emotune
python tests/selfcheck.py
```

服务已启动时：

```bat
set EMOTUNE_BASE=http://127.0.0.1:5000
python tests/test_full_ui.py
```

`test_full_ui.py` 需要 Playwright：`python -m pip install playwright` 后执行 `python -m playwright install chromium`。

### 从这一版继续开发

```bat
git fetch --tags
git checkout snapshot-20261028-1105
git checkout -b dev/continue snapshot-20261028-1105
conda activate emotune
```

改代码、自检、提交、推送：

```bat
python tests/selfcheck.py
git add -A
git commit -m "说明这次改了什么"
git push -u origin dev/continue
```

`git add -A` 不会提交足迹文件。不要把 `data/history.json`、`static/history/`、`data/emotune-local-data.zip` 加进去。conda 环境也不要提交。

合并到 `main` 后，原来的标签 `snapshot-20261028-1105`、`snapshot-20261028-1043`、`snapshot-20261028-0951` 与 `snapshot-20261027-2210` 仍然指向各自快照。

随时回到这一版：

```bat
git fetch --tags
git switch --detach snapshot-20261028-1105
conda activate emotune
```

在快照上再开新线：

```bat
git checkout -b recover/20261028-1105 snapshot-20261028-1105
```

对比当前代码和本快照：

```bat
git diff snapshot-20261028-1105
```

### 本机已有项目目录时

```bat
cd /d E:\F_当AI遇见旋律\Grok20261023_当AI遇见旋律\emoMusic
git checkout snapshot-20261028-1105
conda activate emotune
python app.py
```

远程地址应指向 `https://github.com/Abner199/emoMusic-grok-20261027-2210.git`。

### Surge 介绍页

https://emomusic-grok-20261028-1105.surge.sh

域名规则：`emomusic-grok-版本号.surge.sh`，本版版本号为 `20261028-1105`。必须小写。不能跑摄像头。

上一版介绍页仍在：https://emomusic-grok-20261028-1043.surge.sh

---

## 上一版快照 2026-10-28 10:43

| 项 | 内容 |
| --- | --- |
| 快照时间 | **2026-10-28 10:43**（本地） |
| 仓库 | [Abner199/emoMusic-grok-20261027-2210](https://github.com/Abner199/emoMusic-grok-20261027-2210) |
| Git 标签 | `snapshot-20261028-1043` |
| 发布名 | 心弦 EmoTune 快照 2026-10-28 10:43 |
| 分支 | `main` |
| Surge 介绍页 | https://emomusic-grok-20261028-1043.surge.sh |
| 网页标题 | 当AI遇见旋律：从表情感知到智能音乐推荐 |

当时仓库尚未改为公开部署路径。本地曲库 **280** 首。Python 文档仍写 3.10/3.11、系统 `pip`，没有 conda 环境 `emotune`。功能上已有官方歌词对齐、快速人脸框和足迹打包。

上一版 `snapshot-20261028-0951` 与更早的 `snapshot-20261027-2210`（224 首）仍然保留。

### 这一版相对上一版做了什么

- 歌词：能联网时用 QQ 官方 LRC，并按 30 秒试听窗口对齐本地锚点（避免副歌窗口对不上）；断网回落到本机词
- 单人人脸框实时性：跟踪走 YuNet 快路径（约 30 毫秒），前端 50 毫秒取帧 + 插值；精检仍走 `/api/recognize`
- 「实时捕捉」旁的说明只在鼠标悬停问号时出现
- 换电脑部署文档 `SETUP.md`：克隆 / 整夹拷贝 / 克隆后再解足迹包 三种方式
- 足迹打包：`tools/pack_local_data.py`、`tools/pack-local-data.bat`、`tools/unpack-local-data.bat`（zip **不进** GitHub）
- 静态资源缓存：CSS `?v=52`，JS `?v=51`

仍包含上一版能力：单人精检本机稳健测试目标 ≥90%、可切多人远场、四种输入、九种推荐策略、本地 **280** 首有人声试听。

MobileFaceNet 在 RAF-DB 上的公开评测仍是 **88.27%**。本机 ≥90% 是示例图稳健测试目标，不是把 RAF-DB 重训到 90%。

### 未写入 Git 的本机数据

这些文件只留在你自己的电脑上，避免把真实人脸和听歌记录传到 GitHub：

- `data/history.json` 情绪足迹索引
- `static/history/*.jpg` 历史人脸截图
- `data/prefs.json` 本机主题偏好
- `data/emotune-local-data.zip` 足迹打包（若生成过）

换电脑时若要带走足迹：

1. 整夹拷贝整个 `emoMusic` 目录；或
2. 在旧电脑运行 `tools\pack-local-data.bat`，把 zip 拷到新电脑 `data\`，再运行 `tools\unpack-local-data.bat`

只克隆本仓库不会带上旧足迹。

### 快速恢复这一版

环境：Windows 10/11；这一版文档写的是系统 Python 3.10/3.11。现在请仍用 conda 环境 `emotune`（Python 3.12）来运行它。逐步说明见当前 [SETUP.md](SETUP.md)。

```bat
git clone https://github.com/Abner199/emoMusic-grok-20261027-2210.git
cd emoMusic-grok-20261027-2210
git checkout snapshot-20261028-1043
python -m pip install -r requirements.txt
python app.py
```

浏览器打开 [http://127.0.0.1:5000](http://127.0.0.1:5000)。摄像头必须用这个地址（或 localhost），不要用局域网 IP。

若 5000 已被其他程序占用：

```bat
set EMOTUNE_PORT=18765
python app.py
```

然后打开 [http://127.0.0.1:18765](http://127.0.0.1:18765)。

也可双击 `run.bat`。首次启动会准备模型与本地曲库；本快照已包含三个 ONNX 和 280 首 m4a，一般不必再下载。

恢复旧足迹（可选）：

```bat
rem 把 emotune-local-data.zip 放到 data\ 后
python tools\pack_local_data.py --unpack data\emotune-local-data.zip
```

### 核对这一版还在

```bat
python tests/selfcheck.py
```

服务已启动时（把地址换成你实际端口）：

```bat
set EMOTUNE_BASE=http://127.0.0.1:5000
python tests/test_full_ui.py
```

`test_full_ui.py` 需要本机已安装 Playwright：`python -m pip install playwright` 后执行 `python -m playwright install chromium`。

### 从这一版继续开发

1. 确认当前就在快照标签上：

```bat
git fetch --tags
git checkout snapshot-20261028-1043
```

2. 拉一条开发分支，不要直接改 `main` 上的快照提交（方便以后对照）：

```bat
git checkout -b dev/continue snapshot-20261028-1043
```

3. 改代码、自检、提交、推送：

```bat
python tests/selfcheck.py
git add -A
git commit -m "说明这次改了什么"
git push -u origin dev/continue
```

注意：`git add -A` 不会提交足迹文件（已在 `.gitignore`）。不要把 `data/history.json`、`static/history/`、`data/emotune-local-data.zip` 加进去。

4. 若要把继续开发的成果设为默认分支：在 GitHub 仓库 Settings → Default branch 里改成 `dev/continue`，或合并到 `main`。合并后原来的标签 `snapshot-20261028-1043`、`snapshot-20261028-0951` 与 `snapshot-20261027-2210` 仍然指向各自快照，不会被冲掉。

### 随时回到这一版

已经在本仓库里继续开发时：

```bat
git fetch --tags
git switch --detach snapshot-20261028-1043
```

只查看、不改代码时用上面这条。若要在快照上再开一条新线：

```bat
git checkout -b recover/20261028-1043 snapshot-20261028-1043
```

对比当前代码和本快照：

```bat
git diff snapshot-20261028-1043
```

### 本机已有项目目录时

若 `E:\F_当AI遇见旋律\Grok20261023_当AI遇见旋律\emoMusic` 还在：

```bat
cd /d E:\F_当AI遇见旋律\Grok20261023_当AI遇见旋律\emoMusic
git status
git checkout snapshot-20261028-1043
python app.py
```

远程地址：

```bat
git remote -v
```

应看到 `origin` 指向 `https://github.com/Abner199/emoMusic-grok-20261027-2210.git`。

### Surge 介绍页

识别服务是本机 Flask，Surge 只托管静态说明：

https://emomusic-grok-20261028-1043.surge.sh

域名规则：`emomusic-grok-版本号.surge.sh`，本版版本号为 `20261028-1043`。必须小写。

上一版介绍页仍在：https://emomusic-grok-20261028.surge.sh （对应 `snapshot-20261028-0951`）。

---

## 上一版快照 2026-10-28 09:51

下面整节保持当时的记录，方便对照。本地曲库这一版已经是 **280** 首（每类 40 首）。当时还没有本版的官方歌词对齐、快速人脸框跟踪和足迹打包脚本。

| 项 | 内容 |
| --- | --- |
| 快照时间 | **2026-10-28 09:51**（本地） |
| 仓库 | [Abner199/emoMusic-grok-20261027-2210](https://github.com/Abner199/emoMusic-grok-20261027-2210) |
| Git 标签 | `snapshot-20261028-0951` |
| 发布名 | 心弦 EmoTune 快照 2026-10-28 09:51 |
| 分支 | 当时的 `main` |
| Surge 介绍页 | https://emomusic-grok-20261028.surge.sh |
| 网页标题 | 当AI遇见旋律：从表情感知到智能音乐推荐 |

### 这一版相对更早一版做了什么

- 网页标题改为「当AI遇见旋律：从表情感知到智能音乐推荐」；标签页图标改为夜金弦琴
- 单人精检：YuNet 近景精修 + MobileFaceNet TTA × HSEmotion EfficientNet-B0 融合（不一致时更信野外模型）+ 多帧平均；本机示例图稳健测试目标 ≥90%
- 可切换「单人精检 / 多人远场」；四种输入：照片、摄像头、本地视频、屏幕
- 九种推荐策略 + 独立说明页 `/guide`；歌名旁标注歌曲自己的情绪标签
- 本地曲库 **280** 首有人声试听（每类 40 首）
- 换电脑教程：SETUP.md，说明页「换电脑」一节

更早一版标签 `snapshot-20261027-2210` 仍指向 2026-10-27 22:10 的 224 首快照，不会被冲掉。

### 快速恢复 09:51 这一版

```bat
git clone https://github.com/Abner199/emoMusic-grok-20261027-2210.git
cd emoMusic-grok-20261027-2210
git checkout snapshot-20261028-0951
python -m pip install -r requirements.txt
python app.py
```

从这一版开新线：

```bat
git checkout -b recover/20261028-0951 snapshot-20261028-0951
```

对比当前与 09:51：

```bat
git diff snapshot-20261028-0951
```

---

## 更早一版快照 2026-10-27 22:10（224 首）

下面整节保持当时的记录，方便对照。本地曲库这一版是 **224 首（每类 32 首）**，不是 280。

| 项 | 内容 |
| --- | --- |
| 快照时间 | **2026-10-27 22:10**（本地） |
| 仓库 | [Abner199/emoMusic-grok-20261027-2210](https://github.com/Abner199/emoMusic-grok-20261027-2210) |
| Git 标签 | `snapshot-20261027-2210` |
| 发布名 | 心弦 EmoTune 快照 2026-10-27 22:10 |
| 分支 | 当时的 `main` |

### 这一版做了什么

- 摄像头 / 本地照片识别七类情绪（喜、怒、哀、惧、惊、厌、中性），推荐并自动播放歌曲
- 本地 YuNet + MobileFaceNet FER（RAF-DB 88.27%），断网也能识别
- 本地 224 首按情绪分类的有人声试听（每类 32 首）+ 封面与歌词
- 默认在线曲库（苹果音乐、网易云、咪咕、酷狗、QQ、酷我），失败会提示并切回本地
- 实时捕捉、识别此刻、人脸框与表情文字随情绪变色
- 短暂表情（惊/惧/怒/厌）会锁定歌单，脸松开也不会马上换歌
- **情绪足迹全部保存**：每条含表情图标、真实人脸截图、播放过的歌曲；点选可回放
- 相同情绪再次识别时，尽量换没听过的歌；点足迹回放不计入新的已播记录
- 六种主题：夜金、宣纸、墨青、朱砂、青瓷、月白

### 快速恢复上一版

```bat
git clone https://github.com/Abner199/emoMusic-grok-20261027-2210.git
cd emoMusic-grok-20261027-2210
git checkout snapshot-20261027-2210
python -m pip install -r requirements.txt
python app.py
```

也可双击 `run.bat`。该快照已包含 ONNX 模型和 224 首 m4a。

从上一版开新线：

```bat
git checkout -b recover/20261027 snapshot-20261027-2210
```

对比当前与上一版：

```bat
git diff snapshot-20261027-2210
```
