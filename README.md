# Batch Lyric Video Generator for Windows

Windows 11 本地批量 Lyric Video 生成工具。当前版本使用 MoviePy + Pillow 逐帧绘制歌词动画，不使用 FFmpeg `subtitles='xxx.srt'` 作为最终歌词渲染方案。

## 当前视觉目标

还原参考视频《由远而近渐进歌词视频》的字母效果：

- 整组文字稳定向镜头推进
- 无 jitter / shake / wobble / random offset
- 从道路远处消失点的小字淡入，推进到中左大字，再继续放大穿过镜头淡出
- `scale` 典型为 `0.08 → 0.35 → 1.2 → 2.8`
- `opacity` 为 `0 → 100% → 100% → 0`
- 使用 smooth cubic ease-out
- 无弹跳、无旋转、无逐字乱动
- 白色或近白色超粗无衬线大字
- 轻微暗边、轻微阴影、轻微发光
- 不使用彩色渐变
- 不使用卡拉 OK 式粗描边
- 左对齐，画面中上/中左布局

## 字体

默认 `--font auto` 会按顺序寻找：

1. Anton
2. Impact
3. Arial Black
4. Montserrat ExtraBold
5. Microsoft YaHei Bold，主要用于中文回退

英文歌词会自动转大写。中文歌词会自动使用中文粗体回退，避免出现方框。

## 排版

默认：

- `--text-x 0.50`
- `--text-y 0.42`
- 左对齐
- 多行堆叠
- 行距紧
- 每行约 10-14 个英文字符，或 6-10 个中文字

动态歌词从 `text-x=0.50`、`text-y=0.42` 附近开始，模拟道路尽头远处小字；推进过程中会平滑移动到中左区域，不使用底部静态字幕层。

## 安装

```powershell
winget install Gyan.FFmpeg
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 输入

优先读取同名 `.lrc`，不存在时读取 `.txt`：

```text
examples/input/
  song.mp3
  song.lrc
```

或：

```text
examples/input/
  song.mp3
  song.txt
```

## 中英双语歌词

如果存在同名英文翻译文件，会自动启用双语显示：

```text
song.en.txt
song_en.txt
song.en.lrc
```

也可以手动指定：

```powershell
python -m lyric_video_batcher --input examples\input --output outputs --bilingual --english-lyrics "examples\input\song.en.txt" --overwrite
```

显示方式：

```text
给我一次不放开手
GIVE ME ONE CHANCE NOT TO LET GO
```

中文使用原 `.lrc` 或 `.txt` 时间轴。英文翻译按行数与中文歌词对应；如果英文是 `.en.lrc`，会读取英文行内容，但默认仍跟随中文时间轴。SRT 也会同步输出双语两行。

双语参数：

- `--bilingual`：开启双语模式
- `--english-lyrics`：手动指定英文歌词文件
- `--english-scale`：英文相对中文字号，默认 `0.7`
- `--english-color`：英文颜色，默认 `#D8D8D8`
- `--english-uppercase`：英文自动大写，默认开启
- `--no-english-uppercase`：关闭英文自动大写

## 指定背景视频测试命令

当使用 `--background-video` 时，程序只使用该文件，不会随机选择其它背景。

```powershell
python -m lyric_video_batcher --input examples\input --output outputs --background-video "H:\【MV_Backgrounds】\驾驶\雨天驾驶（伤感神器）\wet road driving\wet road driving005.mp4" --animation-style tiktok --zoom-start 0.08 --zoom-end 2.8 --text-x 0.50 --text-y 0.42 --lyric-offset 0 --overwrite
```

双语测试命令：

```powershell
python -m lyric_video_batcher --input examples\input --output outputs --background-video "H:\【MV_Backgrounds】\驾驶\雨天驾驶（伤感神器）\wet road driving\wet road driving005.mp4" --animation-style tiktok --bilingual --english-scale 0.7 --zoom-start 0.08 --zoom-end 2.8 --text-x 0.50 --text-y 0.42 --lyric-offset 0 --overwrite
```

## 其它参数

- `--background-video`：指定单个背景视频
- `--background-folder`：从目录及子目录随机选择 `.mp4`
- `--background-root`：从素材库及子目录随机选择 `.mp4`
- `--animation-style`：`cinematic`、`tiktok`、`trailer`
- `--bilingual`：开启双语模式
- `--english-lyrics`：手动指定英文翻译文件
- `--english-scale`：英文相对字号，默认 `0.7`
- `--english-color`：英文颜色，默认 `#D8D8D8`
- `--stroke-width`：轻微暗边宽度，默认 `1`
- `--font-size`：基础字号，默认 `72`
- `--width` / `--height`：默认 `1080x1920`
- `--fps`：默认 `30`
- `--overwrite`：覆盖已有输出

## 输出

```text
outputs/
  song/
    song_lyrics.srt
    song.mp4
    song_MV_prompt.txt
```
