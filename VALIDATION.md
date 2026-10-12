# 验证记录

日期：2026-10-12。Windows x64 / Python 3.12.4 / NumPy 2.5.4；FFmpeg 2026-10-08。

- 28 项 unittest 通过，包括三种模式的 H.264/HEVC/AV1 软件编码、FFV1 无损往返、双音轨、裁切、提取、RGBA 管道、目录处理与防覆盖。
- libx265、libsvtav1、libaom-av1 分别完成三种模式的短片转换、全片解码、帧数/尺寸/音轨检查。
- NVIDIA RTX 4070 Ti SUPER / 驱动 610.88：NVENC H.264、HEVC、AV1 完成三种模式的短片转换；自动选择路径通过。
- QSV H.264、HEVC 完成三种模式的短片转换。QSV AV1、AMF 与 VAAPI 在本机探测为不可用，未声称实际验证其转换；VideoToolbox 需要 macOS 验证。
- 本地 FFmpeg 查找优先级、显式无效路径、auto 不可用时的软件回退、显式编码器不静默回退均有回归测试。
- Theora 输入 `--hwaccel auto` 转换通过，不代表使用了 Theora 硬件解码。

- 0.4.0 Windows x64 单文件程序通过架构/启动检查，以冻结版 CLI 运行当时 21 项测试全部通过。
- 解压发布包并清空 PATH，仅使用程序旁的 ffmpeg.exe/ffprobe.exe：doctor 和真实 1920×1080 OMV 的 HEVC/AV1 NVENC 三帧转换通过。
- Python wheel/sdist 构建与 actionlint 工作流检查通过；发布包附依赖许可证和 SHA-256。

## 0.5.0 补充验证

- 合成媒体、软件编码及 NVENC H.264/HEVC/AV1、QSV H.264/HEVC 回归共 28 项全部通过；冻结版 CLI 运行同一套 28 项也全部通过。
- 未知模式提示、强制解释后平面输出相等、版本/抽样/尺寸限制、报告缺少同意时不创建文件、隐私字段过滤和拒绝覆盖通过。
- 本机 FFmpeg 列出 yuva420p，但 libx265 实际拒绝 alpha 编码：`Loaded libx265 does not support alpha layer encoding.` 新选项正确拒绝转换，不残留目标文件。**本机尚未完成真实 HEVC alpha 成功输出**；透明渐变通过/丢失/空结果分别有模拟回归，具备能力的 FFmpeg 会运行实际往返测试。
- 仅访问 C 盘素材：193 个文件的新增尺寸、裁剪与色彩字段检查通过，colorspace 均为 0。mode 0/1/2 各一个真实样本分别转换 H.264/HEVC/AV1 NVENC 两帧，1920×1080、帧数正确。
- Windows x64 0.5.0 构建、启动、doctor、发布包校验和与文档链接检查通过；二进制包排除 release.md/development.md，源码包排除本地发布备忘。
- 全部 532 文件 colorspace=0 的统计来自既有检查清单；本轮未访问已卸载的 L 盘。

Linux/macOS/ARM64 工作流尚待 GitHub Actions 执行。游戏样本验证范围与局限见 [格式说明](docs/format.md#验证范围)。
