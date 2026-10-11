# OMVTool

将 **SiglusEngine `.omv`** 流式转换为 MP4 或无损 MKV，正确处理已验证的 BGR、BGR+alpha 和 YUV 三种存储模式，无需中间 PNG。

支持透明度保存、原始 Ogg 提取、标准 RGBA stdout、多内嵌音轨和目录批量转换。它是独立 Python 实现，并非原 `xmoezzz/omvdecoder` 的新版本。当前版本 **0.3.0**。

## 快速开始

需要 FFmpeg 和 ffprobe 在 PATH 中；FFmpeg 应支持 Theora 解码、libx264、FFV1、AAC 及常规视频滤镜。

**可执行文件**：下载与系统/架构相符的发布包，解压后执行 `omvtool`（Windows 为 `omvtool.exe`）。可执行文件包含 Python 和 NumPy，不包含 FFmpeg。未签名的构建可能触发系统提示；macOS 也可能要求在系统设置中允许运行。

**源码安装**：Python 3.10+，在项目目录运行：

```console
python -m pip install .
omvtool doctor
```

```console
# 高质量 H.264 MP4，默认 CRF 16 / slow；自动保留内嵌音频
omvtool convert "movie.omv" -o "movie.mp4"

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
- [构建与发布](docs/release.md)：六平台 CI、发布草稿、校验和及本地构建。
- [English quick start](README.en.md)。

## 支持范围

当前支持 OMV 头大小 `0xa8`、版本 `0x101`，内嵌 Theora 4:4:4，模式 0/1/2。未知布局会报错，不能保证适用于所有 Visual Arts 游戏或所有 OMV 版本；也不处理资源包提取、音频文件自动配乐或加密格式。

研究阶段检查了九个游戏的 532 个文件：529 个非空文件首两帧成功重建；代表性完整视频及三类像素往返测试通过。全部样本没有内嵌音轨；音频功能另用合成的双 Vorbis 音轨样本验证。详见[验证范围](docs/format.md#验证范围)。发布目录和测试不包含游戏素材。

MP4 为有损输出；FFV1 保存的是 Theora **解码后**的像素，不能恢复源编码已经损失的细节。源压缩码流需要用 `extract` 保存。普通 MP4 不保存透明通道，默认合成到黑底。

MIT 许可证仅适用于本项目独立实现；第三方运行库另见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
