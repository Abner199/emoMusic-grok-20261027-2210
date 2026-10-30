# 当AI遇见旋律：换电脑完整部署说明

品牌 **心弦 EmoTune**。本页写给要把**这一版原样**装到另一台 Windows 电脑、并从零跑起来的人。**从这一版起，情绪足迹（历史记录、人脸截图、播过的歌、偏好）已经直接提交进仓库**，克隆下来就和本机一模一样。固定版本、标签和如何回到某一版，见 [VERSION.md](VERSION.md)。

**当前快照：2026-10-30 12:30 · 歌词语音对齐 + 顶栏一行 + 左区块铺满 + 照片直检 + 足迹入库**  
标签 `snapshot-20261030-1230` · 仓库 [Abner199/emoMusic-grok-20261027-2210](https://github.com/Abner199/emoMusic-grok-20261027-2210)（公开）

静态介绍页（不能跑摄像头）：https://emomusic-grok-20261030-1230.surge.sh

**运行方式：conda 新建空环境 `emotune`，Python 3.12。** 不要把依赖装进系统 Python，也不要装进已经有 `datasets` / `fastapi` / `jax` / `kaggle` 的旧环境。推理只用 **CPU 版** `onnxruntime`（pip 包名就是 `onnxruntime`）。

---

## 讲座当天 10 分钟清单

在**已经装好 conda** 的 Windows 上：

```bat
git clone https://github.com/Abner199/emoMusic-grok-20261027-2210.git
cd emoMusic-grok-20261027-2210
git checkout snapshot-20261030-1230
```

双击 `tools\setup-conda.bat`，等它打印 `PASS onnxruntime CPU`。再双击 `run.bat`。

浏览器（Chrome / Edge）打开：

**http://127.0.0.1:5000**

网页标题应为：`当AI遇见旋律：从表情感知到智能音乐推荐`。

演示：切「照片」→ 点选 `static/demo` 里已命名的表情（01 喜 … 07 中性），或开摄像头正对镜头。检测方式默认「单人精检」。

足迹已在仓库里：启动后点「历史」或看页面下方「情绪足迹」，应看到本机调试时留下的全部记录（截至 2026-10-30 约 790 条，含人脸截图与当时播放的歌）。

---

## 0. 先弄清两件事

1. **识曲必须在本机跑 Flask。** Surge 只放介绍页，没有 Python、没有 ONNX、没有摄像头。
2. **情绪足迹已进 GitHub（本版起）。** `data/history.json`、`data/prefs.json`、`static/history/*.jpg` 都提交在仓库里。注意仓库是**公开**的，这些人脸截图任何人都能看到。

克隆仓库 = 代码 + 三个 ONNX + 532 首试听 + 封面 + 演示图 + 474 首对齐歌词 + **全部情绪足迹**。  
克隆后无需再解包，和旧电脑一样能认出人、能播、能看到以前的足迹。

---

## 1. 新电脑需要准备什么

| 项 | 要求 |
| --- | --- |
| 系统 | Windows 10 或 11，64 位 |
| Python | **3.12**（推荐且已验证 3.12.16）。用 conda **新建空环境** 安装，见第 2、4 节 |
| conda | **Miniconda3** 或 Anaconda3（64 位）。环境名固定为 `emotune` |
| Git | 从 GitHub 克隆时需要 [Git for Windows](https://git-scm.com/download/win) |
| 浏览器 | Chrome 或 Edge（摄像头、屏幕分享用） |
| 磁盘 | 约 1.2 GB（代码 + 三个 ONNX + 532 首试听 + 足迹约 80 MB）+ conda 环境约 0.5–1 GB（CPU）；足迹另计 |
| 网络 | 首次创建环境和缺模型时要联网；平时可完全离线识别和播本地曲 |
| 摄像头 | 本机摄像头；页面必须用 `http://127.0.0.1:端口` 打开 |
| GPU | **不需要。** 不要装 CUDA / `onnxruntime-gpu` |

不需要 CUDA，不需要 ffmpeg。装了 ffmpeg 也只是以后给旋律分析用，当前人声试听是 m4a 缓存。不需要管理员权限：conda 环境会建在用户目录。conda-forge 的 `onnxruntime` 会顺带拉约 2 GB CUDA，请不要用它。

### Python 版本

| 版本 | 说明 |
| --- | --- |
| **3.12** | **推荐。** 已在 conda 环境 `emotune` 中验证（本机 3.12.16） |
| 3.11 / 3.10 | 可用，旧快照用过；新电脑请仍建 3.12 |
| 3.13 / 3.14 | 未作为本项目部署路径验证，不要用来还原这一版 |
| 3.9 及以下 | 不要用 |

依赖用 pip 装进 **空的** conda 环境：Flask 3.x、OpenCV 4.x（不要 5）、NumPy 1.24–2.x、Pillow、requests、SciPy、**CPU 版** onnxruntime。`requirements.txt` 已写上限，避免误装 OpenCV 5 或 GPU 版 onnxruntime。

---

## 2. 安装 Miniconda（若还没有 conda）

1. 打开 [Miniconda 安装页](https://docs.conda.io/en/latest/miniconda.html)，下载 **Miniconda3 Windows 64-bit**。
2. 安装时建议：
   - 安装给「Just Me」
   - 可以勾选 **Add Miniconda3 to my PATH environment variable**（方便以后直接用 `conda`）
   - 若没勾 PATH：以后用开始菜单里的 **Anaconda Prompt** 或 **Miniconda Prompt**
3. 装完打开 **Anaconda Prompt**，确认：

```bat
conda --version
```

应看到 `conda 24` 或更高（本机验证时为 25.9.1）。

若提示需要接受频道条款：

```bat
conda tos accept
```

然后再继续。

---

## 3. 把项目放到新电脑

任选一种。**原版还原推荐 A**（Git 克隆固定标签，已含足迹）。**方式 B** 适合没有网络、用 U 盘搬家。仓库已公开，克隆一般不用登录。

### 方式 A：从 GitHub 克隆这一版（已含足迹）

```bat
git clone https://github.com/Abner199/emoMusic-grok-20261027-2210.git
cd emoMusic-grok-20261027-2210
git checkout snapshot-20261030-1230
```

仓库约 700 MB，克隆要几分钟。`main` 一般已指向同一提交；用标签可以精确钉在这一版，以后 `main` 再往前走也不怕。

### 方式 B：U 盘 / 网盘拷整个文件夹（连历史一起）

把原来电脑上的 `emoMusic` 目录**完整复制**过去。路径可以含中文，例如：

`E:\F_当AI遇见旋律\Grok20261023_当AI遇见旋律\emoMusic`

OpenCV 读 ONNX 已按内存加载，中文路径可用。

不要只拷 `app.py`。需要整棵目录，尤其是：

| 路径 | 作用 |
| --- | --- |
| `app.py` `config.py` `run.bat` `environment.yml` | 入口与 conda 环境说明 |
| `backend/` | 识别、推荐、歌词、足迹 |
| `templates/` `static/css/` `static/js/` | 网页 |
| `static/models/` | 三个人脸 ONNX，缺了不能识别 |
| `static/audio/` | 本地 532 首试听 |
| `static/covers/` | 封面 |
| `static/demo/` | 演示表情图（讲座点选用） |
| `data/history.json` | **情绪足迹索引（历史）** |
| `static/history/` | **足迹里的人脸截图** |
| `data/prefs.json` | 主题、检测方式等本机偏好 |
| `requirements.txt` | pip 依赖清单（含 CPU 版 onnxruntime） |
| `tools/setup-conda.bat` | 一键创建 conda 环境 |
| `tools/verify_cpu.py` | 核对 onnxruntime 是 CPU 包 |
| `tools/pack_local_data.py` | 打包 / 解包足迹 |

不要指望拷来的 `.venv` 或别人电脑上的 conda 环境能直接用。新电脑按第 4 节**新建** `emotune`。

### 方式 C：克隆这一版后，再并入更新的足迹

本版标签之后又在旧电脑上产生了新足迹时用：

1. 在**旧电脑**项目根目录打包足迹（见第 8 节）。
2. 在**新电脑**按方式 A 克隆并检出 `snapshot-20261030-1230`。
3. 按第 4、5 节建好 conda 环境。
4. 把 `emotune-local-data.zip` 拷到新项目的 `data\` 下，运行解包脚本。
5. 再启动 Flask，打开页面点「历史」。

---

## 4. 用 conda 新建虚拟环境（必须、必须是空的）

环境名：**`emotune`**。Python：**3.12**。在**项目根目录**（能看见 `app.py` 的那一层）操作。

**不要**在 `base`、系统 Python、或已经装了 `datasets` / `fastapi` / `jax` / `kaggle` 的环境里 `pip install -r requirements.txt`。那样会出现一长串 `dependency resolver` 冲突（缺 `typing_extensions`、`httpx`、`tqdm` 等）。那些包不是本项目的依赖，**不要为了消警告去装它们**。正确做法是新建空的 `emotune`。

### 4.1 一键脚本（推荐）

双击 `tools\setup-conda.bat`。

它会：找到本机 conda → 创建（或复用）环境 `emotune` 且 Python 3.12 → 卸掉 GPU 版 onnxruntime → 用清华源 `pip install -r requirements.txt`（CPU 包）→ 运行 `python tools\verify_cpu.py`，必须 `PASS`。

### 4.2 命令行（Anaconda Prompt）

```bat
cd /d 本项目目录

conda create -n emotune python=3.12 pip -y
conda activate emotune
python --version
```

提示符必须带 `(emotune)`。`python --version` 必须是 `Python 3.12.x`。若不是，先 `conda deactivate` 再激活。

也可用环境文件（效果相同，仍是 3.12 + 同一份 requirements）：

```bat
conda env create -f environment.yml
conda activate emotune
```

若提示环境已存在：

```bat
conda activate emotune
python -m pip install --default-timeout=300 -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python tools\verify_cpu.py
```

### 4.3 确认环境位置

Windows 上常见路径（本机验证为第一种）：

```
%USERPROFILE%\.conda\envs\emotune\python.exe
%USERPROFILE%\miniconda3\envs\emotune\python.exe
%USERPROFILE%\anaconda3\envs\emotune\python.exe
```

`run.bat` 会按这个顺序查找，找到就用它启动，不依赖 PATH 里的系统 Python。

---

## 5. 在该环境里安装依赖

若刚跑过 `tools\setup-conda.bat`，这一步已经做完。

```bat
conda activate emotune
python -m pip install -U pip
python -m pip install --default-timeout=300 -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

清华源失败时去掉 `-i ...` 走官方 PyPI。大包（OpenCV、SciPy）若超时，加上 `--default-timeout=300`。

本项目 **只用 CPU 推理**。请装 pip 包 `onnxruntime`（CPU）。

不要装这些：

- `onnxruntime-gpu`
- `onnxruntime-directml`
- `conda install onnxruntime`（conda-forge 默认拉 CUDA，约 2 GB）

若已经误装 GPU / CUDA 包：

```bat
conda activate emotune
python -m pip uninstall -y onnxruntime-gpu onnxruntime-directml onnxruntime
conda remove -n emotune onnxruntime --yes
python -m pip install --default-timeout=300 "onnxruntime>=1.16,<2"
python tools\verify_cpu.py
```

若 pip 出现 `SSLEOFError` 或超时，多半是系统代理 / Clash TUN。关掉代理后再装，或加上 `--proxy http://127.0.0.1:7890`。

若 pip 一直失败，可先用 conda-forge 装其余包，再只 pip 装 **CPU** onnxruntime：

```bat
conda activate emotune
conda install -c conda-forge flask numpy scipy pillow requests opencv -y
python -m pip uninstall -y onnxruntime-gpu onnxruntime-directml onnxruntime
python -m pip install --default-timeout=300 "onnxruntime>=1.16,<2"
```

装完后核对：

```bat
python -c "import sys,flask,cv2,numpy,onnxruntime as ort; print(sys.version.split()[0], cv2.__version__, numpy.__version__, ort.__version__, ort.get_available_providers(), ort.get_device())"
python tools\verify_cpu.py
```

应看到 **3.12.x**，OpenCV **4.x**，onnxruntime 版本号，device 为 `CPU`，providers 含 `CPUExecutionProvider`，**不含** `CUDAExecutionProvider` / `DmlExecutionProvider`。官方 pip CPU 包在 Windows 上还可能列出 `AzureExecutionProvider`（云推理占位，不是 GPU）。`verify_cpu.py` 打印 `PASS`。

可选（只有跑浏览器自检才要）：

```bat
python -m pip install playwright
python -m playwright install chromium
```

---

## 6. 启动

确认当前就是 `emotune` 之后：

```bat
conda activate emotune
python app.py
```

或直接双击 `run.bat`（会自动用 `emotune` 的 Python）。

启动日志里应有类似：

```
Python 3.12.16  |  C:\Users\你的用户名\.conda\envs\emotune
onnxruntime CPU 1.31.x providers=['CPUExecutionProvider'] device=CPU …
正在准备模型与本地曲库…
打开浏览器访问 http://127.0.0.1:5000
```

若出现 `onnxruntime 不是 CPU 包`，按第 5 节卸掉 GPU 包后重装 `onnxruntime`。

用 **Chrome 或 Edge** 打开：

**http://127.0.0.1:5000**

网页标题应为：`当AI遇见旋律：从表情感知到智能音乐推荐`。标签页图标是夜金底上的金色弦琴。

### 端口被占用

```bat
conda activate emotune
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
- 本地 532 首试听与封面

本快照一般已经带齐，会直接跳过下载。缺文件且能上网时会自动补。完全断网且缺模型时，识别会失败，把旧电脑的 `static/models/` 拷过来即可。

---

## 7. 核对接好了

仍在 `emotune` 里：

```bat
conda activate emotune
python tests/selfcheck.py
```

关注：`onnxruntime 为 pip CPU 包` PASS；示例图 28 张都能识别；「单人精检稳健测试 ≥90%」；说明页含 HSEmotion 与 TTA；本地曲库 532 首。

服务已启动时（端口换成你的）：

```bat
set EMOTUNE_BASE=http://127.0.0.1:5000
python tests/test_full_ui.py
```

若本机开了 Clash 等代理，自检里「离线推荐 <1s」或个别在线接口可能变慢，把终端代理关掉再测，或把浏览器设为「绕过 127.0.0.1」。Playwright 测试已加 `--no-proxy-server`。

页面上再点一次「历史」：若按第 8 节恢复过足迹，应能看到旧记录、人脸截图和播过的歌。

讲座演示建议再点一次照片页的 `01-喜`、`03-哀`、`05-惊`，确认情绪大字和推荐歌单会跟着变。

---

## 8. 情绪足迹（历史记录）怎么原样带走

从 `snapshot-20261030-1230` 起，足迹**已提交进仓库**，克隆或检出该标签就自动带上（Surge 静态页不带）。位置：

| 路径 | 内容 |
| --- | --- |
| `data/history.json` | 全部识别记录、已播歌曲索引（不截断） |
| `static/history/*.jpg` | 每条足迹对应的人脸截图 |
| `data/prefs.json` | 主题、单人/多人、推荐方式等 |

缺截图时页面仍能列出足迹文字，人脸格子会空。缺 `history.json` 则历史是空的，不影响识别和播放。

### 8.1 整夹拷贝（最省事）

方式 A（克隆本标签）和方式 B（整夹拷贝）都已经包含这三项。建好 `emotune` 再启动即可。下面 8.2、8.3 只在要并入**标签之后**新产生的足迹时才需要。

### 8.2 打包脚本（Git 克隆后单独恢复）

**在旧电脑**项目根目录：

```bat
conda activate emotune
python tools\pack_local_data.py
```

或双击 `tools\pack-local-data.bat`。

会生成 `data\emotune-local-data.zip`（含 `history.json`、`prefs.json`、全部历史人脸图）。把这个 zip 拷到 U 盘或网盘。zip 本身不提交（已在 `.gitignore`），解包后的文件可以照常 `git add`。

**在新电脑**（已经按方式 A 检出本快照、建好 `emotune`）：

1. 把 zip 放到新项目的 `data\emotune-local-data.zip`（或项目根目录同名）。
2. 运行：

```bat
conda activate emotune
python tools\pack_local_data.py --unpack data\emotune-local-data.zip
```

或双击 `tools\unpack-local-data.bat`。

3. 启动 `python app.py`，浏览器打开页面，点「历史」。应能看到旧记录、人脸截图、当时播过的歌和歌曲情绪标签。

可重复解包：后解的文件覆盖同名文件。建议先停掉 Flask 再解包。

### 8.3 手动拷贝

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

### 8.4 足迹进 Git 的约定

本版起 `.gitignore` 不再排除 `data/history.json`、`data/prefs.json`、`static/history/`，只排除打包 zip 和 conda 环境。

继续调试后要把新足迹同步到 GitHub：

```bat
git add data/history.json data/prefs.json static/history
git commit -m "同步情绪足迹"
git push
```

仓库是公开的：提交前确认里面的人脸照片可以公开（例如讲座现场有学生入镜时）。若不想公开，把这三行加回 `.gitignore` 并用 8.2 的打包方式私下带走。

---

## 9. 日常使用 / 讲座演示要点

1. 检测方式默认 **单人精检**（近景一张脸，高精度）。课堂合影再切 **多人远场**。
2. 四种输入：摄像头、照片（JPG/PNG/WEBP）、本地视频、屏幕分享。
3. 「实时捕捉」可持续识曲；「识别此刻」截一帧并关掉实时捕捉。问号上的说明要**把鼠标放到问号上**才出现。
4. 默认在线热歌；关掉「在线热歌」只用本地 532 首。在线长时间失败会提示并自动切本地。讲座现场网络不稳时，先关掉「在线热歌」。
5. 本地 532 首里有 474 首歌词已用语音识别对过时间轴（`data/lyrics_aligned.json`），断网也准；其余联网时用官方词按锚点对齐。
8. 顶栏一行：摄像头 / 照片 / 视频 / 屏幕、弹出人脸窗、识别此刻；摄像头默认铺满左区块，右下角可切「默认尺寸」并放大缩小，设置 → 画面也能调。
9. 照片：选图、拖入或单击/双击示例，照片直接显示在左侧检测区并画出人脸框、关键点和表情标签；双击照片重新检测。
6. 完整算法说明：http://127.0.0.1:5000/guide
7. 演示图在 `static/demo/`，文件名已按中文情绪命名（每种三张）。

---

## 10. 从固定版本恢复 / 继续开发

回到**这一版**（`snapshot-20261030-1230`，仍用 conda 环境 `emotune`）：

```bat
git fetch --tags
git checkout snapshot-20261030-1230
conda activate emotune
python -m pip install --default-timeout=300 -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python tools\verify_cpu.py
python app.py
```

若新电脑还没有环境：先 `tools\setup-conda.bat`。

回到 2026-10-28 15:25 小学 40 分钟讲座版：

```bat
git checkout snapshot-20261028-1525
```

回到 2026-10-30 08:38（532 首扩库）：

```bat
git checkout snapshot-20261030-0838
```

回到 2026-10-28 12:52 讲座准备版：

```bat
git checkout snapshot-20261028-1252
```

回到 2026-10-28 11:05（conda 3.12 文档版，CPU 包尚未打进该标签）：

```bat
git checkout snapshot-20261028-1105
```

回到 2026-10-28 10:43：

```bat
git checkout snapshot-20261028-1043
```

回到 2026-10-28 09:51：

```bat
git checkout snapshot-20261028-0951
```

回到 2026-10-27 22:10（本地曲 **224** 首）：

```bat
git checkout snapshot-20261027-2210
```

旧标签也可以在现在的 `emotune`（3.12）里运行；请仍用 conda，不要退回系统 Python。这场小学课请用 `snapshot-20261028-1525`。注意：早于本版的标签里没有足迹文件，检出旧标签后足迹会从工作区消失，切回本版或 `main` 即恢复。

在本快照上继续改代码（不要直接改标签指向的提交）：

```bat
git checkout -b dev/continue snapshot-20261030-1230
conda activate emotune
```

对比当前与本快照：

```bat
git diff snapshot-20261030-1230
```

更完整的标签说明见 [VERSION.md](VERSION.md)。

---

## 11. 关于 Surge 静态页

识别和播放跑在本机 Flask 上，**Surge 不能跑 Python / ONNX / 摄像头**。

本快照的静态介绍：

https://emomusic-grok-20261030-1230.surge.sh

以前的介绍页仍在：https://emomusic-grok-20261028-1252.surge.sh 、https://emomusic-grok-20261028-1105.surge.sh

那一页不能代替 `python app.py`。真正用摄像头识曲，仍按上面第 6 步在本机、conda 环境里启动。

域名规则：`emomusic-grok-版本号.surge.sh`，必须小写。本版版本号为 `20261030-1230`。重新发布：`surge deploy\surge emomusic-grok-20261030-1230.surge.sh`（`deploy\surge\CNAME` 已写好）。

---

## 12. 常见问题

**双击 run.bat 提示未找到 conda 环境 emotune**  
先运行 `tools\setup-conda.bat`，或打开 Anaconda Prompt 执行第 4 节命令。

**conda 不是内部命令**  
用开始菜单打开 **Anaconda Prompt** / **Miniconda Prompt**，或重新安装 Miniconda 并勾选 Add to PATH。

**python --version 显示 3.11 或别的，不是 3.12**  
没有 `conda activate emotune`。激活后提示符应变为 `(emotune)`。`run.bat` 不依赖激活，它直接调用环境里的 `python.exe`。

**创建环境时提示 Terms of Service**

```bat
conda tos accept
```

**pip 很慢或超时**  
使用清华源（第 5 节）。关掉系统代理后再试。

**pip 报 dependency resolver / anyio / datasets / fastapi / jax / kaggle 缺依赖**  
装进了已经很满的旧环境（或 `base`）。不要去补装那些包。新建空环境：

```bat
conda deactivate
conda create -n emotune python=3.12 pip -y
conda activate emotune
python -m pip install --default-timeout=300 -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**提示缺少人脸检测模型**  
把 `static/models/` 三个 `.onnx` 拷齐，或联网后重新 `python app.py`。

**识别成「未检测到人脸」**  
切到「单人精检」，正对镜头、光线均匀、脸足够大。远景合影请切「多人远场」。

**在线歌一直失败**  
关掉系统代理后再试，或关闭「在线热歌」用本地歌。讲座现场建议先关在线。

**换电脑后历史是空的**  
检出的是早于本版的旧标签（旧标签不含足迹）。`git checkout snapshot-20261030-1230` 或 `main` 即可；仍为空则按第 8 节解包。

**重新对齐本地试听歌词（新增歌曲后）**  
`pip install torch transformers av` 后依次运行 `python toolssr_previews.py`、`python toolslign_lyrics.py`。只在维护曲库时需要，正常运行不要装 torch。

**旧电脑路径有中文，新电脑没有（或反过来）**  
可以。项目不依赖盘符和中文路径；ONNX 已内存加载。足迹 json 里的截图是相对 `/static/history/...`，换盘符不用改。

**页面是旧的标题、旧图标，或问号说明一直挡在画面上**  
强制刷新：Ctrl+F5。本快照静态资源带 `?v=73`。
