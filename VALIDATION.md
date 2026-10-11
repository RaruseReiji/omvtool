# 整理版验证记录

日期：2026-10-12。当前在 Windows x64 / Python 3.12.4 上验证。

- 独立虚拟环境安装（NumPy 2.5.4），`doctor` 检查通过。
- 13 项 unittest 通过，包括 5 项 FFmpeg 集成测试（内部覆盖三模式/多输出组合）。
- 将集成测试入口切换为最终 Windows 冻结版后，同一套 13 项测试再次通过。
- 静止重复帧裁切测试发现 seek 无首帧问题，已改为恢复 CFR 后裁切，并通过回归。

- Windows x64 PyInstaller 6.22.3 单文件构建、PE 架构与子命令启动检查通过，冻结版 doctor 通过。
- 冻结版分别转换三种模式的真实资源，各两帧 FFV1 解码 SHA-256 与研究阶段结果一致。
- 外层 1088 / 可见 1080 的真实 mode 2 样本输出 1920×1080 / 两帧，未被误判 alpha。
- Python wheel 和 sdist 构建通过，源码包未包含媒体、研究证据或私人路径。
- actionlint 1.7.12 检查 GitHub Actions 工作流通过；发布包附依赖许可证和 SHA-256。

本地解释器来自 Anaconda 的 Python，实际 GitHub Actions 使用 setup-python；
Windows 包适合本机先行测试，正式分发应审核 hosted runner 产物。
Linux/macOS/ARM64 工作流已准备，尚未推送到 GitHub 执行。
历史游戏样本验证与局限见 `docs/format.md`，不作为本次 CI 已跑过的结果。
