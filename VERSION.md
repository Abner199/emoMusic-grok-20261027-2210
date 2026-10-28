# 心弦 EmoTune 固定版本

仓库始终是 [Abner199/emoMusic-grok-20261027-2210](https://github.com/Abner199/emoMusic-grok-20261027-2210)（已公开）。下面每一版都有独立 Git 标签，互不覆盖。

换电脑的逐步说明（conda 环境 `emotune` + Python 3.12 + CPU onnxruntime + 情绪足迹）见 [SETUP.md](SETUP.md)。

---

## 当前快照 2026-10-28 12:52 · 讲座版本

| 项 | 内容 |
| --- | --- |
| 快照时间 | **2026-10-28 12:52**（本地） |
| 用途 | **今天讲座版本系统** |
| 仓库 | [Abner199/emoMusic-grok-20261027-2210](https://github.com/Abner199/emoMusic-grok-20261027-2210)（公开） |
| Git 标签 | `snapshot-20261028-1252` |
| 发布名 | 心弦 EmoTune 讲座快照 2026-10-28 12:52 |
| 分支 | `main` |
| Surge 介绍页 | https://emomusic-grok-20261028-1252.surge.sh |
| Python | **3.12**（conda 新建空环境 `emotune`，已验证 3.12.16） |
| 推理 | **CPU 版** pip 包 `onnxruntime`（不要 GPU / 不要 conda-forge CUDA） |
| 网页标题 | 当AI遇见旋律：从表情感知到智能音乐推荐 |

本仓库 `main` 指向这一版。克隆后默认已在该版本；用标签可以随时精确回到讲座此刻。

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
