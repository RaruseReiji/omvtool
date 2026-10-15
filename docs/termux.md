# Android / Termux

Linux ARM64 发布包面向 glibc GNU/Linux，不能直接用于 Android/Termux。
Android 使用 Bionic；即使 CPU 同为 ARM64，动态加载器和系统库 ABI 也不同。
`cannot execute: required file not found` 可能指 ELF 声明的加载器
`/lib/ld-linux-aarch64.so.1` 不存在，而不是 OMVTool 文件丢失。
不要把 Android 的 linker64 链接成 glibc 加载器来解决这个问题。

`~/storage/downloads` 指向 Android 共享存储，通常挂载为 `noexec`，
`chmod +x` 不能改变挂载限制。源码、虚拟环境与程序应放在 Termux HOME
下，例如 `~/work`；视频可以继续从 Downloads 读取和写回。

## 安装方式

使用 Termux 的 Python、NumPy 和 FFmpeg。新环境可采用：

```sh
pkg install python python-numpy ffmpeg
mkdir -p ~/work/omvtool
cd ~/work/omvtool
python -m venv --system-site-packages .venv
# 下载 Release 中的 py3-none-any.whl 后安装（按实际文件名调整路径）
.venv/bin/python -m pip --require-virtualenv install ~/storage/downloads/siglus_omvtool-0.6.1-py3-none-any.whl
.venv/bin/omvtool doctor
.venv/bin/omvtool convert ~/storage/downloads/movie.omv -o ~/storage/downloads/movie.mp4
```

此方案引用 Termux 全局 NumPy，系统包更新会影响环境。需要独立 Python
包文件时，可在同一 Termux/Python 运行时制作并安装 NumPy 本地 wheel；
这类原生 wheel 不应作为跨设备通用包分发。普通 Linux manylinux NumPy wheel
不能直接替代 Android 版本。

现有 Release 的纯 Python wheel 已适合分发 OMVTool 源码，NumPy/FFmpeg
由 Termux 提供，因此无需额外把 Linux ARM64 包改名为 Termux 包。
独立可执行版需要针对 Android/Bionic 构建，并在 Termux 验证 Python、
NumPy、系统库及 FFmpeg 调用；Ubuntu ARM64 runner 的构建不能承担这项验证。

默认禁止覆盖目标。没有硬链接接口或文件系统不支持硬链接时，工具以排他创建
方式复制已完成的临时文件；复制期间目标可见，异常时删除未完成的目标。
`--overwrite` 使用同目录临时文件替换目标。

## 参考

- [Termux 执行环境](https://github.com/termux/termux-packages/wiki/Termux-execution-environment)
- [PyInstaller 平台构建说明](https://www.pyinstaller.org/en/stable/)
- [Python Android 平台标签](https://packaging.python.org/en/latest/specifications/platform-compatibility-tags/)
