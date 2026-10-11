# 格式与验证结论

检查日期：2026-10-12。以下是已检查样本和公开源码支持的结论，不是 OMV 官方规范。

## 外壳和压缩格式

Theora 是视频编码，Ogg 是容器。已验证 OMV 文件在 Ogg 外还有固定头和两张索引表。
未发现该批样本的 Ogg payload 需要解密。重命名扩展名无法去掉外壳。

| 偏移 | 字段（little-endian DWORD） |
|---|---|
| 0x00 | 头大小 168 / 0xa8 |
| 0x04 | 版本 0x101 |
| 0x28 | 模式 |
| 0x2c、0x30 | 外层宽高 |
| 0x3c | 帧间隔微秒，可能舍入 |
| 0x40 | 流序号 |
| 0x4c、0x50 | Ogg page 数量、视频帧数量 |

Ogg 起点为 `168 + page_count * 28 + frame_count * 32`。工具按此计算，并校验
Ogg BOS 和 Theora identification。帧率读取 Theora 的有理数，而非舍入的微秒。
此结构可与 [SSSU 的解析源码](https://github.com/Jirehlov/SiglusSceneScriptUtility/blob/9364d8517fab02b5ef68103dc6e16b707967d186/src/siglus_ssu/video.py) 交叉核对。

FFplay 误报 idcin 的 `168x257` 恰好对应前两个字段，之后的 chunk size 错误
来自错误 demuxer，不足以证明资源损坏。

## 三种已验证模式

| 模式 | 样本数 | 解码后的三个 4:4:4 平面 | 重建 |
|---|---:|---|---|
| 0 | 2 | B、G、R | 按 RGB 重排 |
| 1 | 413 | B、G、R + 各平面尾部的 alpha 段 | 重排 RGB、拼接 alpha |
| 2 | 117 | Y、U、V | 按输入范围和矩阵解释 |

mode 1 的可见高度 H，Theora 高度为 `H + ceil(H/3)`。每个平面的前 H 行存颜色，
尾部 `ceil(H/3)` 行依次组成 alpha 的三段，拼接后取前 H 行。
1080 行画面对应 1440 行码流；512 对应 683。额外行当图像显示会产生底部条索。
不能简单把所有高度差都认定为 alpha：36 个 mode 2 文件外层高度 1088，
Theora 可见高度 1080，是块对齐与显示区域的差异。

mode 2 按 BGR 解释会把中性的 U/V=128 当成颜色亮度，产生严重色偏。
默认 full-range BT.601 来自 [Color2.h](https://github.com/xmoezzz/SiglusExtract/blob/5ac65650e8141bb5cabaaf2a5ab55aec0a8d43b8/tools/src/png2theora/png2theora/Color2.h)
的转换系数和实际样本分布；仍提供范围/矩阵覆盖，不声称与所有游戏运行时逐像素一致。

## 重复帧和时长

Theora 的重复帧包可能不生成新的 FFmpeg AVFrame。直接按收到的帧重新编码会
缩短静止画面和片尾。工具以时间戳恢复 CFR，再按 OMV 帧表总帧数补足尾部。
帧表因此属于可信输入的一部分；损坏/不实的帧计数可能产生错误片长。

## 验证范围

验证样本覆盖 LOOPERS PLUS、LUNARiA、Stella of the end、两部 Prima Doll、
Summer Pockets Reflection Blue、anemoi、サヤガタリ等九个安装目录，共 532 文件。

- 532 个头和码流信息通过检查，529 个非空文件首两帧成功重建，另 3 个只有头的占位文件。
- H=1、2、3、4、270、400、512、1080 合成布局覆盖 alpha 非三倍数边界。
- 三种模式的 FFV1 往返逐字节相等：mode 0/1 比较 RGBA（包括隐藏 RGB），mode 2 比较 YUV444；RGBA stdout 同样验证。
- 14 个代表性完整/短输出完成全片解码和帧数时长检查。三段完整 ED 分别为 7073、8053、7185 帧，30fps 下 235.766667、268.433333、239.5 秒。
- 532 文件均只含 Theora 视频，没有内嵌音频。双 Vorbis 合成样本另外验证三种模式的 AAC 输出、MKV 音频包复制、多轨、裁切和禁用音频。

这些属于样本验证结果，**不是 529 部视频全部全长转换**。未对照运行中的游戏，
未验证已卸载的 Harmonia，未覆盖未知版本、加密资源、其他像素抽样或异常多视频流。
公开项目不附带游戏文件、截图或本机绝对路径；CI 使用可重新生成的合成数据。

回归测试位于 `tests/`；实际执行情况见 [VALIDATION.md](../VALIDATION.md)。
