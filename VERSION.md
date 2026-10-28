# 心弦 EmoTune 固定版本

仓库始终是 [Abner199/emoMusic-grok-20261027-2210](https://github.com/Abner199/emoMusic-grok-20261027-2210)。下面每一版都有独立 Git 标签，互不覆盖。

换电脑的逐步说明见 [SETUP.md](SETUP.md)。

---

## 当前快照 2026-10-28 09:51

| 项 | 内容 |
| --- | --- |
| 快照时间 | **2026-10-28 09:51**（本地） |
| 仓库 | [Abner199/emoMusic-grok-20261027-2210](https://github.com/Abner199/emoMusic-grok-20261027-2210) |
| Git 标签 | `snapshot-20261028-0951` |
| 发布名 | 心弦 EmoTune 快照 2026-10-28 09:51 |
| 分支 | `main` |
| Surge 介绍页 | https://emomusic-grok-20261028.surge.sh |
| 网页标题 | 当AI遇见旋律：从表情感知到智能音乐推荐 |

本仓库 `main` 指向这一版。克隆后默认已在该版本；用标签可以随时精确回到此刻。

### 这一版相对上一版做了什么

- 网页标题改为「当AI遇见旋律：从表情感知到智能音乐推荐」；标签页图标改为夜金弦琴
- 单人精检：YuNet 近景精修 + MobileFaceNet TTA × HSEmotion EfficientNet-B0 融合（不一致时更信野外模型）+ 多帧平均；本机示例图稳健测试目标 ≥90%
- 可切换「单人精检 / 多人远场」；四种输入：照片、摄像头、本地视频、屏幕
- 九种推荐策略 + 独立说明页 `/guide`；歌名旁标注歌曲自己的情绪标签
- 本地曲库 **280** 首有人声试听（每类 40 首）
- 换电脑教程：SETUP.md，说明页「换电脑」一节

上一版标签 `snapshot-20261027-2210` 仍指向 2026-10-27 22:10 的 224 首快照，不会被冲掉。

### 未写入 Git 的本机数据

这些文件只留在你自己的电脑上，避免把真实人脸和听歌记录传到 GitHub：

- `data/history.json` 情绪足迹索引
- `static/history/*.jpg` 历史人脸截图
- `data/prefs.json` 本机主题偏好

换电脑时若要带走足迹：把上面三个路径连同整个项目文件夹一起拷贝。只克隆本仓库不会带上旧足迹。

### 快速恢复这一版

环境：Windows 10/11，Python 3.10 或 3.11（已验证 3.11），Chrome 或 Edge。逐步说明见 [SETUP.md](SETUP.md)。

```bat
git clone https://github.com/Abner199/emoMusic-grok-20261027-2210.git
cd emoMusic-grok-20261027-2210
git checkout snapshot-20261028-0951
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
git checkout snapshot-20261028-0951
```

2. 拉一条开发分支，不要直接改 `main` 上的快照提交（方便以后对照）：

```bat
git checkout -b dev/continue snapshot-20261028-0951
```

3. 改代码、自检、提交、推送：

```bat
python tests/selfcheck.py
git add -A
git commit -m "说明这次改了什么"
git push -u origin dev/continue
```

注意：`git add -A` 不会提交足迹文件（已在 `.gitignore`）。不要把 `data/history.json` 和 `static/history/` 加进去。

4. 若要把继续开发的成果设为默认分支：在 GitHub 仓库 Settings → Default branch 里改成 `dev/continue`，或合并到 `main`。合并后原来的标签 `snapshot-20261028-0951` 与 `snapshot-20261027-2210` 仍然指向各自快照，不会被冲掉。

### 随时回到这一版

已经在本仓库里继续开发时：

```bat
git fetch --tags
git switch --detach snapshot-20261028-0951
```

只查看、不改代码时用上面这条。若要在快照上再开一条新线：

```bat
git checkout -b recover/20261028 snapshot-20261028-0951
```

对比当前代码和本快照：

```bat
git diff snapshot-20261028-0951
```

### 本机已有项目目录时

若 `E:\F_当AI遇见旋律\Grok20261023_当AI遇见旋律\emoMusic` 还在：

```bat
cd /d E:\F_当AI遇见旋律\Grok20261023_当AI遇见旋律\emoMusic
git status
git checkout snapshot-20261028-0951
python app.py
```

远程地址：

```bat
git remote -v
```

应看到 `origin` 指向 `https://github.com/Abner199/emoMusic-grok-20261027-2210.git`。

### Surge 介绍页

识别服务是本机 Flask，Surge 只托管静态说明：

https://emomusic-grok-20261028.surge.sh

域名规则：`emomusic-grok-版本号.surge.sh`，本版版本号为 `20261028`。

---

## 上一版快照 2026-10-27 22:10（224 首）

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
