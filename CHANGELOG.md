# Changelog

## 0.4.0 — 2026-10-12

- 增加 HEVC、AV1 MP4 输出，软件与硬件编码后端、质量/码率及设备选项。
- 增加编码器实际试编码、auto 硬件选择和 FFmpeg 输入加速参数。
- 支持在程序旁或当前工作目录放置 FFmpeg/ffprobe，无需配置 PATH。
- 完善编码参数、硬件要求、参考来源与致谢文档。

## 0.3.0 — 2026-10-12

- 提供可安装 Python 包和命令行工具。
- 统一 `convert / inspect / extract / pipe / doctor`，stdout 保留给 JSON/二进制数据。
- 保留 mode 0/1/2、alpha、YUV 范围/矩阵、精确帧率、重复帧及多内嵌音轨处理。
- 增加公开文档、合成回归测试、六平台可执行文件构建与 tag 发布草稿流程。
