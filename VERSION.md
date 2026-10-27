# 心弦 EmoTune 固定版本

| 项 | 内容 |
| --- | --- |
| 快照时间 | **2026-10-27 22:10**（本地） |
| 仓库 | [Abner199/emoMusic-grok-20261027-2210](https://github.com/Abner199/emoMusic-grok-20261027-2210) |
| Git 标签 | `snapshot-20261027-2210` |
| 发布名 | 心弦 EmoTune 快照 2026-10-27 22:10 |
| 分支 | `main` |

本仓库就是这一版的固定快照。克隆后默认已在该版本；用标签可以随时精确回到此刻。

## 这一版做了什么

- 摄像头 / 本地照片识别七类情绪（喜、怒、哀、惧、惊、厌、中性），推荐并自动播放歌曲
- 本地 YuNet + MobileFaceNet FER（RAF-DB 88.27%），断网也能识别
- 本地 224 首按情绪分类的有人声试听（每类 32 首）+ 封面与歌词
- 默认在线曲库（苹果音乐、网易云、咪咕、酷狗、QQ、酷我），失败会提示并切回本地
- 实时捕捉、识别此刻、人脸框与表情文字随情绪变色
- 短暂表情（惊/惧/怒/厌）会锁定歌单，脸松开也不会马上换歌
- **情绪足迹全部保存**：每条含表情图标、真实人脸截图、播放过的歌曲；点选可回放
- 相同情绪再次识别时，尽量换没听过的歌；点足迹回放不计入新的已播记录
- 六种主题：夜金、宣纸、墨青、朱砂、青瓷、月白

## 未写入 Git 的本机数据

这些文件只留在你自己的电脑上，避免把真实人脸和听歌记录传到 GitHub：

- `data/history.json` 情绪足迹索引
- `static/history/*.jpg` 历史人脸截图
- `data/prefs.json` 本机主题偏好

换电脑时若要带走足迹：把上面三个路径连同整个项目文件夹一起拷贝。只克隆本仓库不会带上旧足迹。

## 快速恢复这一版

环境：Windows 10/11，Python 3.10 或 3.11（已验证 3.11），Chrome 或 Edge。

```bat
git clone https://github.com/Abner199/emoMusic-grok-20261027-2210.git
cd emoMusic-grok-20261027-2210
git checkout snapshot-20261027-2210
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

也可双击 `run.bat`。首次启动会准备模型与本地曲库；本快照已包含 ONNX 模型和 224 首 m4a，一般不必再下载。

## 核对这一版还在

```bat
python tests/selfcheck.py
```

服务已启动时（把地址换成你实际端口）：

```bat
set EMOTUNE_BASE=http://127.0.0.1:5000
python tests/test_full_ui.py
```

`test_full_ui.py` 需要本机已安装 Playwright：`python -m pip install playwright` 后执行 `python -m playwright install chromium`。

## 从这一版继续开发

1. 确认当前就在快照标签上：

```bat
git fetch --tags
git checkout snapshot-20261027-2210
```

2. 拉一条开发分支，不要直接改 `main` 上的快照提交（方便以后对照）：

```bat
git checkout -b dev/continue snapshot-20261027-2210
```

3. 改代码、自检、提交、推送：

```bat
python tests/selfcheck.py
git add -A
git commit -m "说明这次改了什么"
git push -u origin dev/continue
```

4. 若要把继续开发的成果设为默认分支：在 GitHub 仓库 Settings → Default branch 里改成 `dev/continue`，或合并到 `main`。合并后原来的标签 `snapshot-20261027-2210` 仍然指向本快照，不会被冲掉。

## 随时回到这一版

已经在本仓库里继续开发时：

```bat
git fetch --tags
git switch --detach snapshot-20261027-2210
```

只查看、不改代码时用上面这条。若要在快照上再开一条新线：

```bat
git checkout -b recover/20261027 snapshot-20261027-2210
```

对比当前代码和本快照：

```bat
git diff snapshot-20261027-2210
```

## 本机已有项目目录时

若 `E:\F_当AI遇见旋律\Grok20261023_当AI遇见旋律\emoMusic` 还在：

```bat
cd /d E:\F_当AI遇见旋律\Grok20261023_当AI遇见旋律\emoMusic
git status
git checkout snapshot-20261027-2210
python app.py
```

远程地址：

```bat
git remote -v
```

应看到 `origin` 指向 `https://github.com/Abner199/emoMusic-grok-20261027-2210.git`。
