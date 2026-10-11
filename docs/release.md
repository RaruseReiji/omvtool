# 构建与发布

## 六平台原生构建

`.github/workflows/build.yml` 参考已有 Python 工具工作流的矩阵、Python 架构检查、
PyInstaller 和二进制头验证，新增合成集成测试、源码包、依赖许可证与发布草稿。
PyInstaller 不是交叉编译器，每个目标在自己的 runner 原生构建。

| 目标 | Runner | Python 架构 |
|---|---|---|
| Windows x64 | windows-latest | x64 |
| Windows ARM64 | windows-11-arm | arm64 |
| macOS Intel | macos-15-intel | x64 |
| macOS Apple Silicon | macos-latest | arm64 |
| Linux x64 | ubuntu-24.04 | x64 |
| Linux ARM64 | ubuntu-24.04-arm | arm64 |

每个平台安装 Python 3.13，运行离线测试，构建单文件可执行程序，检查
PE/ELF/Mach-O 架构及 `--version`/帮助启动。独立 Ubuntu job 安装 FFmpeg 并运行
全部合成集成测试；Python 3.10 job 检查声明的最低版本。六平台 job 不都运行媒体集成测试。

Windows ARM64/部分 ARM runner 的可用性受 GitHub 仓库类型和账号方案影响；
公开仓库可用性应以 GitHub 当前说明为准。构建失败不会创建 release。

官方参考：[GitHub runner 列表](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)、
[PyInstaller 手册](https://pyinstaller.org/en/stable/)、
[PyInstaller 用法](https://pyinstaller.org/en/stable/usage.html)。

## 触发方式与产物

- push main/master、pull request、手动 workflow_dispatch：仅测试、构建和上传 Actions artifacts。
- push `v*` 标签：通过所有 job 后创建 **GitHub Release 草稿**，不自动公开。
- 不自动上传 PyPI；Python wheel/sdist 附在 release，暂不填写尚未创建的公开仓库 URL。

每个平台产物为 `omvtool-VERSION-OS-ARCH.zip`（Windows）或 `.tar.gz`（其他），
另附 `.sha256`。包中包括程序、使用文档、MIT、第三方许可证、版本和依赖记录。
统一 release 包括六个平台、Python wheel、sdist、`SHA256SUMS`。不包含 FFmpeg。
Linux 基于 Ubuntu 24.04，不能承诺兼容更老的 glibc；macOS 最低运行版本依赖
实际 Python/NumPy wheel。未做代码签名、macOS notarization 或 Windows 签名。

首次公开应使用这个独立目录建立新仓库，**不要推送旧研究仓库的历史**；
旧历史包括上游 Rust、私人路径和游戏截图。新工程没有关联远程地址。
项目 MIT 是为独立实现准备的许可证方案；发布前可按作者意愿修改署名或许可证。

## 正式发布步骤

1. 检查 README、CHANGELOG、许可证署名和版本；确认将发布的是本独立工程。
2. 创建/关联目标 GitHub 仓库，提交并推送 main；等待六平台 Actions 结果，下载测试目标平台。
3. 更新 `pyproject.toml` 和 `src/omvtool/__init__.py` 到同一版本，提交，再创建相应标签。
4. 例如 `git tag v0.3.0` 后 `git push origin v0.3.0` 将触发构建；本次整理没有执行这些操作。
5. 在 GitHub 审核草稿的产物、SHA256SUMS、说明和兼容范围，然后手动 Publish。

同名 release 已存在时 `gh release create` 会失败，避免不经检查修改已有公开 release；
失败重跑前可删除尚未公开的草稿，或手动补充已审核产物。
默认 GITHUB_TOKEN 仅 contents:read，只有 tag 发布 job 请求 contents:write；
PR 不拿发布权限，不使用 pull_request_target。

## 本地构建

```console
python -m pip install ".[build]"
python -m unittest discover -s tests -v
python scripts/build.py --architecture x64
python -m build
```

ARM64 机器改为 `--architecture arm64`。输出 `dist/omvtool[.exe]`、
`release/` 平台压缩包和校验文件，以及 dist 中的 wheel/sdist。
脚本拒绝在架构不匹配时构建；不支持通过改参数在 x64 主机交叉生成 ARM64。
同版本本地重建前需移动 `build/omvtool-VERSION-OS-ARCH` 暂存目录，脚本不自动删除。
Linux runner 缺 CPython 许可证时，脚本从 Python 官方仓库按当前解释器版本下载 LICENSE；
其余依赖许可证取自本次安装的 distribution，缺失会阻止打包。

校验 Windows 下载包示例：

```powershell
Get-FileHash .\omvtool-0.3.0-windows-x64.zip -Algorithm SHA256
```

macOS/Linux 解压 tar.gz 保留执行权限；若复制过程中丢失，执行 `chmod +x omvtool`。
二进制构建仍需实际目标平台验证，本地 Windows 测试不等于其他五平台已经构建成功。
