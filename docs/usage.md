# 完整使用说明

## 安装与检查

发布包解压后可直接调用其中的 `omvtool`，Windows 为 `omvtool.exe`。
Python 安装方式为项目根目录 `python -m pip install .`；随后可用
`omvtool` 或 `python -m omvtool`，两者使用同一入口。Python 版本须为 3.10+。

```console
omvtool --version
omvtool --help
omvtool convert --help
omvtool doctor
```

FFmpeg/ffprobe 须在 PATH 中。可通过环境变量 `OMVTOOL_FFMPEG`、
`OMVTOOL_FFPROBE` 指定各自的完整可执行文件路径，不要在变量值外再加引号。
示例（PowerShell）：

```powershell
$env:OMVTOOL_FFMPEG = 'C:\Tools\ffmpeg\bin\ffmpeg.exe'
$env:OMVTOOL_FFPROBE = 'C:\Tools\ffmpeg\bin\ffprobe.exe'
omvtool doctor
```

`doctor` 检查两个程序能否启动，以及转换所需解码器、编码器和滤镜；
缺少任一项返回 1。它检查完整功能所需组件，单独 `extract` 不需要 FFmpeg。
不要求 FFmpeg 带 libtheora **编码器**，该编码器仅供开发集成测试生成样本。

## 一般转换

```console
omvtool convert INPUT -o OUTPUT [OPTIONS]
```

INPUT 可以是一个 `.omv` 文件或目录。单文件默认输出 MP4，OUTPUT 须以
`.mp4` 结尾。FFV1 须显式指定 `--format ffv1`，输出以 `.mkv` 结尾。
不根据输出扩展名隐式切换编码器。

| 参数 | 默认值 | 含义 |
|---|---|---|
| `-o, --output` | 必填 | 输出文件或目录 |
| `--format mp4/ffv1` | mp4 | H.264 MP4 / FFV1 MKV |
| `--crf 0..51` | 16 | x264 质量，越小画质/体积通常越高；仅 MP4 |
| `--preset` | slow | x264 速度选项 ultrafast、superfast、veryfast、faster、fast、medium、slow、slower、veryslow；仅 MP4 |
| `--start SECONDS` | 0 | 从指定秒开始，须非负有限数 |
| `--frames COUNT` | 全部剩余帧 | 输出帧数上限，须正整数 |
| `--yuv-range full/limited` | full | mode 2 的输入范围；mode 0/1 不使用 |
| `--matrix 601/709` | 601 | mode 2 的输入颜色矩阵；mode 0/1 不使用 |
| `--alpha black/discard` | black | MP4 的透明处理；FFV1 始终保留 alpha |
| `--audio auto/copy/none` | auto | 内嵌音频处理方式 |

```console
omvtool convert movie.omv -o movie.mp4
omvtool convert movie.omv -o test.mp4 --start 30 --frames 150 --preset fast
omvtool convert movie.omv -o higher_quality.mp4 --crf 12 --preset slower
omvtool convert effect.omv -o effect.mkv --format ffv1
omvtool convert movie.omv -o alternate.mp4 --yuv-range limited --matrix 709
```

CRF 16 是观看和体积之间的默认选择，不是质量保证。CRF 0 也仍受 YUV420p
颜色抽样和颜色转换影响；需要逐像素保存请用 FFV1。mode 2 的默认 full/601
来自所检查转换源码及样本，无法替代与具体游戏渲染结果对照。

输出 MP4 使用 BT.709 limited-range YUV420p，写入颜色标记和 faststart。
奇数宽高补到偶数以兼容 x264/播放器，最多多一列或一行。FFV1 保持原可见尺寸。
帧率使用 Theora 分子/分母，恢复重复帧并按 OMV 帧表控制总长度。
`--start` 向下取到最近视频帧边界，音频采用相同的实际起点，帧数上限不会超过剩余片长。
为正确处理静止画面的 Theora 重复帧，会从头解码再裁切；大 start 值需要等待前段解码。

## 透明通道

mode 1 视频将 alpha 存在三个平面的额外行中。普通播放器直接打开提取的
OGV 会把这些行当图像。工具会先重建可见区域和 alpha。

- MP4 默认 `--alpha black`：按透明度合成黑底。
- MP4 `--alpha discard`：丢弃透明度，显示其底层 RGB，透明区域可能出现隐藏颜色。
- FFV1 MKV：mode 0/1 保存 BGRA，其中 mode 1 包括 alpha 和隐藏 RGB；mode 2 保存 YUV444。
- RGBA stdout：始终带 alpha，非透明视频的 alpha 为 255。

播放器对 MKV 中 alpha 的显示方式不同，看到黑底并不代表通道丢失。可通过
FFmpeg 提取 alpha 验证。FFV1 通常比 MP4 大很多，但无需先落地整段 PNG。

## 音频

只处理 **内嵌 Ogg 音轨**。本机研究样本没有内嵌音频，所以正常输出仅视频。
不会搜索旁边的 BGM、猜测配乐或替代游戏脚本混音。

| `--audio` | MP4 | FFV1/MKV |
|---|---|---|
| auto | 复制已有 AAC，其余转 AAC 256 kb/s/轨 | 复制全部音轨 |
| copy | 尝试复制全部音轨；目标容器不兼容则失败 | 复制全部音轨 |
| none | 不输出音频 | 不输出音频 |

裁切区间同时用于音频，音频长度上限为输出视频时长；不会补出源文件没有的声音。
视频先编码到临时文件，再复用视频码流合入音频，不会二次编码视频。
有音频时短暂存在两个编码后临时文件。音频复制的包边界、AAC 编码延迟等可能使
实际时长与视频存在毫秒级差异，不保证任意音频格式都逐样点裁切。
`inspect --json` 可查看源音轨；合成测试覆盖两条 Vorbis 音轨的转换、复制和裁切。

## 目录批量转换

```console
omvtool convert mov -o converted
omvtool convert mov -o lossless --format ffv1
omvtool extract mov -o original_ogg
omvtool inspect mov --json
```

递归枚举 `.omv`，扩展名大小写不敏感，保持子目录结构。已有目标文件跳过，
允许中断后重跑；零帧占位文件在转换时跳过，但可以 inspect / extract。
单个失败会继续处理其他文件，并最终返回 1。目录没有 OMV 会报错。
不会检查已有目标是否完整；如需重做，请自行移走对应文件。
单文件转换遇到已有目标直接报错，不覆盖源文件或已有产物。
完整产物先写同目录临时文件，再以不覆盖目标的方式发布；需要文件系统支持硬链接
（常规 NTFS、APFS、ext4 支持，FAT/exFAT 或部分网络盘可能不支持）。不支持时会报错，
请将输出放到支持的本地盘；不会退回可能覆盖目标的写法。正常失败会清理临时文件，
断电或强制终止可能留下 `.partial-*` 文件，可在确认进程结束后自行删除。

## 检查与提取

```console
omvtool inspect movie.omv
omvtool inspect movie.omv --json
omvtool extract movie.omv -o movie.ogv
```

inspect 的 JSON 写到 stdout，包含外层/可见尺寸、mode、精确帧率分子分母、
总帧数、payload offset 和音轨；目录结果为数组，失败项包含 `error`。
进度、错误写到 stderr。JSON 中的 path 是输入的绝对路径，分享前请自行脱敏。

extract 逐块复制整个 Ogg payload，包括原始压缩视频和所有内嵌音轨，不改变质量。
它仍校验本工具支持的头和布局。**提取不等于修复特殊平面的显示**：mode 0/1
的 OGV 不能直接当普通 YUV 视频观看。extract 不提供裁切参数。

## 标准二进制管道

```console
omvtool pipe movie.omv --frames 150
```

仅一个输入，stdout 为逐帧紧密排列、8 位 RGBA，无帧头、PNG 包装或时间戳，
每帧 `output_width * output_height * 4` 字节；帧率由 inspect 提供。
`pipe` 支持 start、frames、yuv-range、matrix，始终保留 alpha。**没有音频**，
需要音频时另从原 payload 作为 FFmpeg 第二输入，或直接用 convert。

以下 Unix shell 示例假定 inspect 确认尺寸为 1920×1080、帧率为 30/1；
它丢弃 alpha，并输出仅视频文件：

```sh
omvtool pipe movie.omv | ffmpeg -f rawvideo -pixel_format rgba -video_size 1920x1080 -framerate 30/1 -i pipe:0 -vf 'scale=in_range=full:out_range=limited:out_color_matrix=bt709,pad=ceil(iw/2)*2:ceil(ih/2)*2,format=yuv420p' -c:v libx264 -crf 16 -preset slow -color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709 -n video_only.mp4
```

Windows PowerShell 5.1 等文本管道可能损坏二进制。推荐使用
[Python 子进程示例](../examples/pipe_to_ffmpeg.py)，自动读取尺寸/帧率和映射所有内嵌音轨：

```console
python examples/pipe_to_ffmpeg.py movie.omv custom.mp4
```

该示例需要源码安装环境。可执行版直接使用 `convert` 即可，不依赖 Python。
不要将 `pipe` stdout 混入日志或直接写向交互终端；下游须完整读取或主动终止上游。

## 错误与退出码

| 退出码 | 含义 |
|---|---|
| 0 | 成功；批量允许跳过已有目标/零帧占位 |
| 1 | 输入/依赖/转换失败；批量至少一项失败 |
| 2 | 命令行参数错误（argparse） |
| 130 | 用户 Ctrl+C 中断 |

`idcin`、`168x257` 通常是 FFmpeg 误识别 OMV 外壳。先 inspect，再 convert。
未知模式、非 4:4:4 或 alpha 尺寸不匹配会拒绝转换；请保留完整错误和
inspect 信息用于排查。发布问题时不必上传整部游戏资源。
字幕、章节、附加图片、交错多视频流和动态尺寸变化尚未作为支持目标。

## 从研究版命令迁移

| 研究版 | 整理版 |
|---|---|
| `python omvtool.py input.omv output.mp4` | `omvtool convert input.omv -o output.mp4` |
| `python omvtool.py input.omv output.mkv --format ffv1` | `omvtool convert input.omv -o output.mkv --format ffv1` |
| `python omvtool.py input.omv --format inspect` | `omvtool inspect input.omv --json` |
| `python omvtool.py input.omv --format rgba` | `omvtool pipe input.omv` |
| `python omvtool.py input.omv output.ogv --format ogv` | `omvtool extract input.omv -o output.ogv` |

研究版 inspect 曾向 stderr 打印 JSON；整理版 JSON 规范输出到 stdout。
质量、音频和颜色参数沿用原名称，裁切改为恢复重复帧后向下取帧边界。
