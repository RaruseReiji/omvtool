# OMVTool

将 **SiglusEngine `.omv`** 流式转换为 H.264、HEVC、AV1 MP4 或无损 MKV，正确处理 BGR、BGR+alpha 和 YUV 三种存储模式，无需中间 PNG。

支持软件与硬件编码、透明度保存、原始 Ogg 提取、标准 RGBA stdout、多内嵌音轨和目录批量转换。当前版本 **0.5.0**。

## 快速开始

需要 FFmpeg 和 ffprobe。**直接把 `ffmpeg.exe`、`ffprobe.exe` 放到 `omvtool.exe` 旁边即可，无需设置 PATH。** macOS/Linux 使用不带 `.exe` 的程序，并保留执行权限。也支持当前工作目录、PATH 和环境变量指定路径。FFmpeg 的编码器/驱动支持可用 `doctor` 检查。

**可执行文件**：下载与系统/架构相符的发布包，解压后执行 `omvtool`（Windows 为 `omvtool.exe`）。可执行文件包含 Python 和 NumPy，不包含 FFmpeg。未签名的构建可能触发系统提示；macOS 也可能要求在系统设置中允许运行。

**源码安装**：Python 3.10+，在项目目录运行：

```console
python -m pip install .
omvtool doctor
```

```console
# 高质量 H.264 MP4，默认 CRF 16 / slow；自动保留内嵌音频
omvtool convert "movie.omv" -o "movie.mp4"

# HEVC / AV1 软件编码
omvtool convert "movie.omv" -o "hevc.mp4" --codec hevc
omvtool convert "movie.omv" -o "av1.mp4" --codec av1

# NVIDIA 硬件编码；也可用 --encoder auto 自动探测
omvtool convert "movie.omv" -o "av1_gpu.mp4" --codec av1 --encoder nvenc

# 无损保存解码后像素，透明效果保留 alpha
omvtool convert "effect.omv" -o "effect.mkv" --format ffv1

# 递归转换目录，保留相对路径；已有目标和零帧占位文件会跳过
omvtool convert "mov" -o "converted"

# 查看模式、真实尺寸、精确帧率和音轨
omvtool inspect "movie.omv" --json

# 仅剥离外壳，不重编码；特殊 BGR/alpha 视频仍需重建才能正常观看
omvtool extract "movie.omv" -o "movie.ogv"
```

PowerShell 在当前目录运行发布版时，使用 `./omvtool.exe`。源码安装后也可用 `python -m omvtool` 代替 `omvtool`，参数相同。输入、输出路径可包含中文或空格；建议加引号。

## 文档

- [完整使用说明](docs/usage.md)：参数、音频、透明度、批量、质量、管道和常见问题。
- [格式与验证结论](docs/format.md)：OMV 布局、色偏/割裂成因、验证范围。
- [参考来源及工具对比](docs/references.md)：上游源码、相关提取器、差异与限制。
- [开发和测试](docs/development.md)：安装、合成测试、项目结构。
- [English quick start](README.en.md)。

## 支持范围

当前支持 OMV 头大小 `0xa8`、版本 `0x101`，内嵌 Theora 4:4:4，模式 0/1/2。未知布局会报错，不能保证适用于所有 Visual Arts 游戏或所有 OMV 版本；也不处理资源包提取、音频文件自动配乐或加密格式。

检查了九个游戏的 532 个文件：529 个非空文件首两帧成功重建；代表性完整视频及三类像素往返测试通过。全部样本没有内嵌音轨；音频功能另用合成的双 Vorbis 音轨样本验证。详见[验证范围](docs/format.md#验证范围)。发布目录和测试不包含游戏素材。

MP4 为有损输出；FFV1 保存的是 Theora **解码后**的像素，不能恢复源编码已经损失的细节。源压缩码流需要用 `extract` 保存。MP4 默认合成到黑底；HEVC 可通过 `--alpha preserve` 保存透明度，须通过当前 FFmpeg/x265 的实际能力检查。

硬件编码支持 NVENC、QSV、AMF、VAAPI、VideoToolbox，具体取决于 FFmpeg 构建、显卡和驱动。Theora 输入通常由 CPU 解码，颜色/alpha 重建也在 CPU 完成。用 `omvtool doctor --test-encoders` 可实际试编码；编译进 FFmpeg 不等于本机可用。

感谢 [xmoezzz/omvdecoder](https://github.com/xmoezzz/omvdecoder)、[SiglusExtract](https://github.com/xmoezzz/SiglusExtract)、[SiglusSceneScriptUtility](https://github.com/Jirehlov/SiglusSceneScriptUtility) 等项目提供的格式和实现参考，详见[参考来源](docs/references.md)。MIT 许可证；第三方运行库另见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
