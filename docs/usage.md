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

将 `ffmpeg.exe` 和 `ffprobe.exe` 放在 `omvtool.exe` 同目录即可（macOS/Linux 不带 `.exe`，须可执行）。源码调用也可放在项目根目录或当前工作目录。

查找顺序：显式环境变量 → 程序/启动脚本所在目录 → 源码项目根目录（源码调用）→ 当前工作目录 → PATH。显式变量无效会报错，不会改用别的程序。

可通过环境变量 `OMVTOOL_FFMPEG`、
`OMVTOOL_FFPROBE` 指定各自的完整可执行文件路径，不要在变量值外再加引号。
示例（PowerShell）：

```powershell
$env:OMVTOOL_FFMPEG = 'C:\Tools\ffmpeg\bin\ffmpeg.exe'
$env:OMVTOOL_FFPROBE = 'C:\Tools\ffmpeg\bin\ffprobe.exe'
omvtool doctor
```

`doctor` 检查两个程序、基础编码器和滤镜，列出软件/硬件编码器及输入硬件加速方法；基础依赖缺失返回 1。HEVC/AV1 与硬件编码器为可选功能。`doctor --test-encoders` 会逐个实际编码一帧，并单独检查 libx265 alpha 往返，标记 PASS 或 UNAVAILABLE；可选后端不可用不会使基础诊断失败。单独 `extract` 不需要 FFmpeg。
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
| `--format mp4/ffv1` | mp4 | MP4 / 无损 FFV1 MKV |
| `--codec h264/hevc/av1` | h264 | MP4 视频编码；FFV1 不使用 |
| `--encoder` | software | software、auto、nvenc、qsv、amf、vaapi、videotoolbox 或对应 FFmpeg 编码器名 |
| `--crf` | H.264 16 / HEVC 20 / AV1 28 | 软件质量；H.264/HEVC 0..51，AV1 0..63，越低通常越清晰 |
| `--quality` | 硬件 20 / VideoToolbox 65 | 硬件后端的质量参数，见下表 |
| `--bitrate` | 无 | 目标视频码率，例如 8M；与 crf/quality 互斥 |
| `--preset` | 随编码器 | 编码速度/压缩预设，见下表 |
| `--encode-device` | 驱动默认 | NVENC GPU 序号、QSV 设备或 VAAPI render node |
| `--hwaccel` | none | FFmpeg 输入硬件加速；Theora 通常仍用 CPU |
| `--hwaccel-device` | 无 | FFmpeg 输入加速设备；须同时指定 hwaccel |
| `--start SECONDS` | 0 | 从指定秒开始，须非负有限数 |
| `--frames COUNT` | 全部剩余帧 | 输出帧数上限，须正整数 |
| `--yuv-range full/limited` | full | mode 2 的输入范围；mode 0/1 不使用 |
| `--matrix 601/709` | 601 | mode 2 的输入颜色矩阵；mode 0/1 不使用 |
| `--alpha black/discard/preserve` | black | MP4 的透明处理；FFV1 始终保留 alpha |
| `--force-mode 0/1/2` | 不覆盖 | 强制已知布局，保留版本/抽样/尺寸校验 |
| `--audio auto/copy/none` | auto | 内嵌音频处理方式 |

```console
omvtool convert movie.omv -o movie.mp4
omvtool convert movie.omv -o test.mp4 --start 30 --frames 150 --preset fast
omvtool convert movie.omv -o higher_quality.mp4 --crf 12 --preset slower
omvtool convert effect.omv -o effect.mkv --format ffv1
omvtool convert movie.omv -o alternate.mp4 --yuv-range limited --matrix 709
```

各编码器的质量数字不能直接横向比较，应先用短片段试编码。CRF 0 也仍受 YUV420p
颜色抽样和颜色转换影响；需要逐像素保存请用 FFV1。mode 2 的默认 full/601
来自所检查转换源码及样本，无法替代与具体游戏渲染结果对照。

输出 MP4 使用 BT.709 limited-range YUV420p（保留 alpha 时为 YUVA420p），写入颜色标记和 faststart。
奇数宽高补到偶数以兼容编码器/播放器，最多多一列或一行。FFV1 保持原可见尺寸。
帧率使用 Theora 分子/分母，恢复重复帧并按 OMV 帧表控制总长度。
`--start` 向下取到最近视频帧边界，音频采用相同的实际起点，帧数上限不会超过剩余片长。
为正确处理静止画面的 Theora 重复帧，会从头解码再裁切；大 start 值需要等待前段解码。

## HEVC、AV1 与硬件编码

`--format` 选择输出方案，`--codec` 选择 MP4 中的视频编码。H.264、HEVC、AV1 都使用 `.mp4` 后缀，音频策略相同。HEVC 写入 `hvc1` 标记；播放器仍须支持相应编码。

```console
omvtool convert movie.omv -o hevc.mp4 --codec hevc --crf 20 --preset slow
omvtool convert movie.omv -o av1.mp4 --codec av1 --crf 28 --preset 6
omvtool convert movie.omv -o hevc_gpu.mp4 --codec hevc --encoder nvenc --quality 18 --preset p6
omvtool convert movie.omv -o av1_gpu.mp4 --codec av1 --encoder nvenc
omvtool convert movie.omv -o av1_auto.mp4 --codec av1 --encoder auto
omvtool convert movie.omv -o intel.mp4 --codec hevc --encoder qsv
omvtool convert movie.omv -o amd.mp4 --codec hevc --encoder amf --bitrate 8M
omvtool convert movie.omv -o apple.mp4 --codec hevc --encoder videotoolbox --bitrate 8M
omvtool convert movie.omv -o linux.mp4 --codec hevc --encoder vaapi --encode-device /dev/dri/renderD128
```

默认 `--encoder software`：H.264 用 libx264，HEVC 用 libx265，AV1 优先 libsvtav1，缺少时用 libaom-av1。也可指定完整名称，如 `--encoder av1_nvenc` 或 `--encoder libaom-av1`；须与 codec 匹配。

| 后端 | 默认质量/参数 | preset | 设备 |
|---|---|---|---|
| libx264 / libx265 | CRF 16 / 20，越小质量越高 | 默认 slow；ultrafast 到 veryslow | CPU |
| libsvtav1 | CRF 28 | 默认 6；0..13，越大越快，具体范围依本地版本 | CPU |
| libaom-av1 | CRF 28，b:v=0 | 默认 6；0..8，映射 cpu-used | CPU |
| NVENC | VBR CQ 20，b:v=0；quality 0..51，0 为自动 | 默认 p5；p1 最快到 p7 最慢 | encode-device 为非负 GPU 序号 |
| QSV | global_quality 20，越小质量越高，0..51 | 默认 medium；veryfast/faster/fast/medium/slow/slower/veryslow | 可指定 qsv_device，格式取决于平台 |
| AMF | CQP，I/P QP=20，越小质量越高；本工具 0..51 | 可传后端 quality 预设；不指定时采用 FFmpeg 默认 | 驱动默认 |
| VAAPI | CQP，global_quality 20；0..51 | 不使用 preset | 默认 /dev/dri/renderD128；支持 encode-device |
| VideoToolbox | q:v=65，0..100，越大质量越高 | 不使用 preset | 驱动默认；不允许软件回退 |

VideoToolbox 提供 H.264/HEVC，当前工具未配置其 AV1 后端。所有后端都可用 `--bitrate` 切换到目标码率模式；具体码率与文件大小仍受内容、编码器和容器影响。`--quality` 是后端原生参数，既不等于 CRF，也不能跨显卡直接比较。

`--encoder auto` 按平台候选顺序做真实试编码，并检查当前视频尺寸；成功后才选择硬件，无可用设备则使用软件。macOS 尝试 VideoToolbox；其他平台依次尝试 NVENC、QSV、AMF、VAAPI。auto 接受默认参数或 `--bitrate`，要指定 quality/crf/preset/设备请明确选择后端。明确指定后端失败时会报错，不会静默换编码器。测试通过也不能保证长时间编码不会遇到驱动/资源错误；最终编码出错时同样报错。

**硬件解码与编码分别控制。** 输出硬件编码不要求输入硬件解码。常见显卡/FFmpeg 没有 Theora 硬件解码器，故这些 OMV 的解码通常仍由 CPU 完成，mode 0/1 颜色与 alpha 重建也在 CPU 进行。
`--hwaccel auto` 交给 FFmpeg 尝试输入加速并按其策略回退；可显式选 cuda、qsv、d3d11va、dxva2、vaapi、videotoolbox、vulkan，不兼容时可能报错。滤镜使用软件帧，不构成全 GPU 零拷贝管线。FFV1 是软件无损编码，不与 codec/encoder/crf/quality/bitrate/preset/encode-device 组合。

## 透明通道

mode 1 视频将 alpha 存在三个平面的额外行中。普通播放器直接打开提取的
OGV 会把这些行当图像。工具会先重建可见区域和 alpha。

- MP4 默认 `--alpha black`：按透明度合成黑底。
- MP4 `--alpha discard`：丢弃透明度，显示其底层 RGB，透明区域可能出现隐藏颜色。
- MP4 `--alpha preserve`：仅支持 `--codec hevc --encoder software` / `libx265`，须为 mode 1 输入；详见下文。
- FFV1 MKV：mode 0/1 保存 BGRA，其中 mode 1 包括 alpha 和隐藏 RGB；mode 2 保存 YUV444。
- RGBA stdout：始终带 alpha，非透明视频的 alpha 为 255。

播放器对 MKV 中 alpha 的显示方式不同，看到黑底并不代表通道丢失。可通过
FFmpeg 提取 alpha 验证。FFV1 通常比 MP4 大很多，但无需先落地整段 PNG。

## 音频

只处理 **内嵌 Ogg 音轨**。源文件无音轨时输出仅视频，有多条音轨时全部保留。
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

## HEVC alpha 的条件

[FFmpeg 8.0 变更记录](https://github.com/FFmpeg/FFmpeg/blob/n8.0/Changelog)
明确增加 libx265 alpha layer encoding。
[编码器源码](https://github.com/FFmpeg/FFmpeg/blob/n8.0/libavcodec/libx265.c)
还要求相应 x265 多层/alpha 能力；[x265 4.1 文档](https://x265.readthedocs.io/en/4.1/cli.html#alpha-encode-options) 指出须在构建时开启 `ENABLE_ALPHA`。版本号新、列出 `yuva420p` 都不能保证能编码。
像素格式选择触发 alpha，无需再手动传 `alpha=1`。

```console
omvtool convert effect.omv -o effect_alpha.mp4 --codec hevc --alpha preserve --crf 18
```

程序先在临时目录用当前编码参数编码一帧透明渐变为 MP4，再用同一 FFmpeg 提取
alpha，检查长度、梯度和误差。试验通过才转换源文件；失败明确报错，不回退到不透明输出。
临时试验不读取游戏画面，不联网，结束后清理。`+yuva420p` 强制像素格式，禁止
FFmpeg 在不支持时悄悄改成无 alpha 格式。非常低的质量也可能因透明度失真而未通过检查。

HEVC alpha 同样有损，RGB 也经过 4:2:0 抽样；逐像素保存 alpha/隐藏 RGB 请用 FFV1。
支持解码 HEVC 不代表能显示其辅助 alpha 层；播放器可能只显示颜色层，须在目标
编辑器/播放环境验证。macOS VideoToolbox 有独立的
[HEVCWithAlpha / alpha_quality 实现](https://github.com/FFmpeg/FFmpeg/blob/n8.0/libavcodec/videotoolboxenc.c)，
当前工具的 preserve 路径限于 libx265，未开放未经本机验证的 VideoToolbox alpha。
NVENC/QSV/AMF/VAAPI、H.264/AV1 和 `--encoder auto` 不接受 preserve，避免自动选择
不支持 alpha 的编码器。已有普通硬件编码仍可使用 black/discard。

## 未知布局诊断与手动覆盖

未来新模式或损坏文件均可能触发报错。工具不自动采集报告、不发送网络请求。
先查看诊断帮助；不带 `--consent` 的命令会解释收集内容并退出，不写文件：

```console
omvtool diagnose --help
omvtool diagnose movie.omv -o report.json
# 阅读说明并同意后，主动重跑：
omvtool diagnose movie.omv -o report.json --consent
```

报告只含工具版本、文件大小、有限的数字头字段及可解析的 Theora 结构。
读取范围为前 168 字节，以及已知外壳能定位时最多 65536 字节的 Ogg 开头；
**不写入路径、文件名、机器信息、原始头字节、注释、文件哈希、视频或音频**。
未知版本的字段只标为 candidate，不能据此认定格式。
源文件只读，已有报告拒绝覆盖。报告不会自动上传。

请自行打开 JSON 检查内容，愿意提交时将它作为附件上传到项目 issue，并手动描述
游戏名/版本、错误现象和执行命令（可删去私人路径）。初步诊断不需要整部视频；
报告未必足以推断全新布局，后续样本共享由用户自行决定。

已确认实际布局与模式标签不符时，可强制解释：

```console
omvtool inspect movie.omv --force-mode 2 --json
omvtool convert movie.omv -o trial.mp4 --force-mode 2 --frames 60
```

convert、pipe、inspect、extract 支持此选项；目录调用对所有文件应用同一覆盖，
因此建议先检查单文件。inspect JSON 同时显示 declared_mode、forced_mode、有效 mode，
stderr 显示警告。extract 仍复制原始 Ogg 数据，不改头、不改平面。
覆盖不会绕过版本、抽样或布局尺寸检查，也不保证颜色解释正确。
输入色彩依据与字段见[格式说明](format.md#源文件实际声明了什么)。

## 错误与退出码

| 退出码 | 含义 |
|---|---|
| 0 | 成功；批量允许跳过已有目标/零帧占位 |
| 1 | 输入/依赖/转换失败；批量至少一项失败 |
| 2 | 命令行参数错误（argparse） |
| 130 | 用户 Ctrl+C 中断 |

`idcin`、`168x257` 通常是 FFmpeg 误识别 OMV 外壳。先 inspect，再 convert。
未知模式、非 4:4:4 或 alpha 尺寸不匹配会拒绝转换，并提示诊断命令；诊断与覆盖方法见上文。
字幕、章节、附加图片、交错多视频流和动态尺寸变化尚未作为支持目标。
