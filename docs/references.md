# 参考来源与工具对比

感谢 xmoezzz、Jirehlov 及相关项目贡献者公开的工具和资料，为 OMV 结构、平面布局和转换流程提供了有用参考；感谢 FFmpeg、Xiph.Org、NumPy 和 PyInstaller 提供的基础工具。

检查日期：2026-10-12。对比依据是仓库文档、指定版本源码和本机样本分析；
未安装运行第三方 GUI 或旧 exe，不据此声称所有现有工具都不可用。

| 工具 | 能力 | 与本工具的区别/检查结论 |
|---|---|---|
| [xmoezzz/omvdecoder](https://github.com/xmoezzz/omvdecoder) | Rust H.264、PNG/JPG、FFmpeg、PXY4M stdout | v0.2.1 部分调整透明高度，但所检代码仍无条件按 BGR 解释平面；未解决 mode 2 色偏。PXY4M 是自定义 PNG 包装，不能作为普通 rawvideo 直接输入 FFmpeg |
| [SiglusExtract / Omv2Avi](https://github.com/xmoezzz/SiglusExtract) | 提取资源、普通 OMV→OGV、透明视频→未压缩 32 位 AVI | 可以重建透明画面，未压缩产物体积大；所检 AVI 代码固定 29.97fps，模式分派未看到 mode 0。项目声明停止新功能开发 |
| [SiglusSceneScriptUtility](https://github.com/Jirehlov/SiglusSceneScriptUtility) | 分析、提取 OGV、回封装 OMV、批量 | 适合外壳/索引操作，不提供本次三模式的完整重建转码链；文档称回封装只保留第一条 Theora，不保留 Vorbis/Opus |
| [SSSU-GUI](https://github.com/yanmuuuu/SiglusSceneScriptUtility-GUI) | 资源浏览、音频工具、OMV 提取后调用播放器 | 图形界面方便，但提取 OGV 并不重建 BGR/alpha 特殊平面 |
| [SiglusEngine / omvCuter.py](https://github.com/hiroshil/SiglusEngine/blob/master/omvCuter.py) | 找到 OggS 后去外壳 | 不重建颜色/alpha；所检脚本一次读完整文件 |
| OMVTool（本项目） | mode 0/1/2 分派、H.264/HEVC/AV1 软件及硬件编码、FFV1、RGBA stdout、精确帧率与重复帧、内嵌音频 | CLI；只支持已验证布局；FFmpeg 为外部依赖，可放程序旁 |

若仅需 OGV 提取或回封装，SSSU 是已有选择。mode 2 提取后可以组合 FFmpeg 进行
颜色解释与转码；mode 0/1 仍需平面重建。在所检查项目中没有找到已验证同时覆盖
本次全部需求的成品，不代表穷尽了整个 GitHub。

## 对应源码

- [omvdecoder v0.2.1 / main.rs](https://github.com/xmoezzz/omvdecoder/blob/63ac06a9c0bb575cae5eaa9ed32241c3c9bbd932/src/main.rs)、[converter](https://github.com/xmoezzz/omvdecoder/tree/63ac06a9c0bb575cae5eaa9ed32241c3c9bbd932/src/converter)：平面重建、输出高度、FFmpeg/PXY4M 路径。本次源码检查，没有运行其潜在越界路径。
- [Omv2Avi.cpp](https://github.com/xmoezzz/SiglusExtract/blob/5ac65650e8141bb5cabaaf2a5ab55aec0a8d43b8/source/SiglusExtract/Omv2Avi/Omv2Avi.cpp)：mode 分派及固定 `dwRate=2997, dwScale=100`。
- [Color2.h](https://github.com/xmoezzz/SiglusExtract/blob/5ac65650e8141bb5cabaaf2a5ab55aec0a8d43b8/tools/src/png2theora/png2theora/Color2.h)：YUV/RGB 系数参考。
- [SSSU video.py](https://github.com/Jirehlov/SiglusSceneScriptUtility/blob/9364d8517fab02b5ef68103dc6e16b707967d186/src/siglus_ssu/video.py)：外层头、page/frame 表结构。
- [SSSU 视频模块说明](https://github.com/Jirehlov/SiglusSceneScriptUtility/blob/main/manual.md#-v----video--work-with-omv-video-files)：提取/分析/回封装语义及音频限制。
- [FFmpeg filters](https://ffmpeg.org/ffmpeg-filters.html)、[protocols / subfile](https://ffmpeg.org/ffmpeg-protocols.html#subfile)：按偏移读取、fps/tpad/scale 等。
- [FFmpeg 编码器说明](https://ffmpeg.org/ffmpeg-codecs.html)、[硬件加速输入选项](https://ffmpeg.org/ffmpeg.html#Advanced-Video-options)：libx265、SVT-AV1、QSV 等和 hwaccel；具体可用参数以本地 `ffmpeg -h encoder=NAME` 为准。
- [FFmpeg 8.0 Changelog](https://github.com/FFmpeg/FFmpeg/blob/n8.0/Changelog)、[libx265 实现](https://github.com/FFmpeg/FFmpeg/blob/n8.0/libavcodec/libx265.c)、[HEVC alpha 解码](https://www.ffmpeg.org/doxygen/8.0/libavcodec_2hevc_2hevcdec_8c_source.html)、[x265 alpha 构建要求](https://x265.readthedocs.io/en/4.1/cli.html#alpha-encode-options)：alpha 层编码、解码及依赖检查。
- [Theora specification](https://www.theora.org/doc/Theora.pdf)：Theora 标识、画面尺寸与有理数帧率。

当日 GitHub API 返回 omvdecoder 的 4 个公开 fork：BaoLyHoseki 与上游相同；
Livscrit、lunaswd 的新增变更为 README/CI；killvxk/omvdecoder-xmoezzz 落后上游。
没有发现相关解码修复。fork 状态会变化，这只是当次可见范围。

第三方软件保留各自许可证，见 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)。

[SiglusEngineOfficialKit](https://codeberg.org/VisualArts/SiglusEngineOfficialKit)
提交 d8d1f3d4b7066eb36ff2439498bedf69c6e967cd 中的 OMVLib 和手册提供了三模式、
alpha 与全范围 YUV 转换的直接核对材料。感谢该套件的整理与分享；样本哈希、
函数地址、取整差异及适用边界见 [OMVLib 核对报告](official-kit-analysis.md)。
