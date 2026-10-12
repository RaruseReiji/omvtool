# 开发与测试

## 环境

```console
python -m venv .venv
# Windows: .venv\Scripts\activate ; Unix: source .venv/bin/activate
python -m pip install -e ".[build]"
python -m unittest discover -s tests -v
```

默认运行不依赖 FFmpeg 的单元测试，集成测试明确标记 skipped。
完整集成测试需要 FFmpeg 的 libtheora/libvorbis 编码器、libx264、libx265、SVT-AV1 或 libaom-av1、FFV1、AAC。

```powershell
$env:OMVTOOL_INTEGRATION = '1'
python -m unittest discover -s tests -v
```

```sh
OMVTOOL_INTEGRATION=1 python -m unittest discover -s tests -v
```

同时设置 `OMVTOOL_TEST_BINARY` 为已构建程序的绝对路径，可让集成测试调用冻结版
CLI；单元测试及 Python 管道示例仍使用已安装的 Python 包。

测试临时生成 Theora + 双 Vorbis 的 Ogg，包装成 OMV 0x101，退出后删除。
不含游戏数据。合成 OMV 的索引项是零填充，仅用来验证本工具读取偏移/帧数与
解码重建路径，不保证能被游戏引擎回放，也不测试索引表回封装。

验证范围：模式/尺寸拒绝、alpha 余数、YUV、截断裸帧、大小写扩展名、参数验证；
三模式 MP4/MKV、多音轨波形、分数帧率、静止重复帧裁切、无损往返、标准 stdout、
原 payload 提取、目录错误继续及禁止覆盖。

## 结构

```text
src/omvtool/
  cli.py          公共 CLI、检查、批量、依赖诊断
  header.py       OMV/Theora 结构读取
  converter.py    平面重建、FFmpeg 流式转换、内嵌音频
  encoding.py     软件/硬件编码参数、实际编码探测
  progress.py     stderr 阶段/帧数/耗时/ETA 进度与 FFmpeg 进度读取
  diagnostics.py  显式同意后的本地结构报告，无网络上传
  runtime.py      外部程序定位、冻结运行时环境处理
tests/            可公开的合成/单元测试
examples/         二进制管道示例
scripts/          原生打包与可执行文件架构检查
docs/             使用、格式、来源、开发、发布说明
```

公共稳定接口为命令行；Python 内部函数还不承诺 API 稳定。
使用 `omvtool --version`、`pyproject.toml`、`src/omvtool/__init__.py` 同步版本。
发布标签必须为 `v` 加包版本，构建脚本会校验。

## 依赖与构建

运行依赖 NumPy，FFmpeg 作为外部进程；不需要 Pillow、Rust 或游戏 DLL。
运行时依赖范围允许 NumPy 1/2，构建工具版本固定，实际安装版本保存在每个发布包
`build-info.json`。这不是依赖完全锁定的可重复字节构建；runner 和 wheel 升级会改变产物。
冻结程序调用 FFmpeg 前清理 PyInstaller 注入的库路径，Windows 清除 DLL 搜索目录。
相关依据见 [PyInstaller 外部程序说明](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html#launching-external-programs-from-the-frozen-application)。

源码包由 setuptools 明确只发现 `src/omvtool`；二进制发布包使用文件白名单，
不打包测试生成媒体、私人路径清单或临时目录。

Python 源码已按 Black 风格排版；生成文件和验证产物由 `.gitignore` 排除。

## 硬件集成测试

设置 `OMVTOOL_HARDWARE_TEST=1` 可启用 GPU 转换测试；通过
`OMVTOOL_HARDWARE_ENCODERS` 指定逗号分隔列表（默认 h264_nvenc,hevc_nvenc,av1_nvenc）。
该列表中的编码器必须实际可用，失败不会被跳过。普通 CI 不要求 GPU，软件
HEVC/AV1 转换和 auto 后端回退逻辑仍会测试。

```powershell
$env:OMVTOOL_INTEGRATION = '1'
$env:OMVTOOL_HARDWARE_TEST = '1'
$env:OMVTOOL_HARDWARE_ENCODERS = 'h264_nvenc,hevc_nvenc,av1_nvenc'
python -m unittest discover -s tests -v
```

HEVC alpha 集成测试按当前 FFmpeg 的实际能力分别验证成功往返或安全拒绝；本机构建若缺少 x265 alpha，不能将失败分支通过说成实际 alpha 编码已通过。单元测试另检查透明度渐变与不透明回退。二进制包只附 usage/format/references；开发说明保留在源码中，docs/release.md 为被忽略的本地发布备忘。

## 提交内容与自动发布

`tests/` 需要提交到远程仓库，CI 在 checkout 后依赖它运行单元和合成媒体测试。
里面只有测试代码，不包含游戏视频或本地测试产物；临时样本由测试运行时生成并清理。
`.gitignore` 已排除 build/dist/release、缓存与媒体文件，二进制发布包不携带 tests，
源码包保留 tests 便于复现验证。不要将整个 tests 目录加入 gitignore。

`.github/workflows/build.yml` 在推送 `v*` 标签后，等待六平台构建、源码打包、
集成测试和最低 Python 版本检查全部通过，再自动发布 GitHub Release，附平台包、
Python 包和校验和。标签必须与包版本一致，例如 v0.6.0；含连字符的标签发布为
prerelease。普通分支 push、PR、手动运行只测试/构建。不会自动提交代码或创建标签。
可先提交并推送代码，再执行 `git tag v0.6.0`、`git push origin v0.6.0`。
无需额外 PAT，release job 使用仓库 GITHUB_TOKEN 的 contents: write 权限。
参考 [gh release create](https://cli.github.com/manual/gh_release_create)。
