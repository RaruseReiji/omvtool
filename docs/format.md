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

## 源文件实际声明了什么

OMV 外层声明宽、高、帧间隔、帧数和模式；目前没有确认其独立的范围、矩阵、
原色或传递函数字段。0x34、0x38 的含义尚未确定，不能当成色彩声明。

内嵌 Theora identification packet 另有下列字段。偏移从 `80 74 68 65 6f 72 61`
这个包头起算，整数使用 big-endian；详见 [Theora 规范第 4、6.2 节](https://www.theora.org/doc/Theora.pdf)。

| 字节偏移 | 字段 | inspect JSON |
|---|---|---|
| 7–9 | Theora 版本 | theora_version |
| 10、12（各 2 字节） | 宏块宽高，乘 16 得编码尺寸 | coded_width / coded_height |
| 14、17（各 3 字节） | 可见 picture 宽高 | theora_width / theora_height |
| 20、21 | picture 左下角偏移 | picture_x / picture_y |
| 22、26（各 4 字节） | 精确帧率分子、分母 | fps_num / fps_den |
| 30、33（各 3 字节） | 像素宽高比；任一为零表示未指定 | aspect_num / aspect_den |
| 36 | 色彩枚举：0 未指定、1 Rec.470M、2 Rec.470BG，其余保留 | colorspace |
| 37（3 字节） | 名义码率提示，零可表示未知 | nominal_bitrate |
| 40–41 的 PF 位 | 抽样：0=4:2:0、1 保留、2=4:2:2、3=4:4:4 | pixel_format |

编码区域、Theora 可见区域和重建后游戏画面是三个不同概念。mode 1 的 Theora
可见区域仍包含 alpha 尾行，不能直接作为游戏画面高度。解码器负责 Theora 的
picture 裁剪，工具再重建游戏画面。当前输出采用方形像素（SAR=1），并不自动
还原未验证的非方形像素显示比例；inspect 保留原始比例供检查。

### 为什么默认 full / 601

这批 532 个文件的 `colorspace` 全为 0。Theora identification 没有单独的
full/limited 标志；其已定义 Rec.470 色彩约定使用 BT.601 系数和有限范围，
但这些样本没有声明采用那些约定。mode 0/1 更是借用了三个平面保存 BGR/alpha，
不能用普通 YUV 规则解释。

mode 2 默认采用 full / 601，依据是 SiglusExtract 所附
[Color2.h 的转换实现](https://github.com/xmoezzz/SiglusExtract/blob/5ac65650e8141bb5cabaaf2a5ab55aec0a8d43b8/tools/src/png2theora/png2theora/Color2.h)：
其公式采用接近 BT.601 的系数，没有将 Y 映射到 16–235 的步骤。样本也出现
接近 0–255 的亮度分布。这是源码和样本支持的兼容性选择，**不是文件头声明，
也不是仅凭分辨率推断**；亮度越界本身不能证明 full-range，源码亦不能证明
每个游戏都使用同一生成工具。尚未与所有游戏运行时逐像素比对。

full 将 Y 的 0/255 解释为黑/白，U/V 中点为 128；limited 将 Y 的 16/235
解释为黑/白、色差跨度为 224。矩阵 601 使用 Kr=0.299、Kb=0.114，709 使用
Kr=0.2126、Kb=0.0722。范围选错会改变黑位、白位和对比度，矩阵选错会改变色相。
可显式用 `--yuv-range limited --matrix 709` 等组合测试。两个参数仅影响 mode 2。

MP4 输出的 limited / BT.709 / 4:2:0 是面向常见播放器的输出选择，与输入解释
分开：工具实际做范围和矩阵转换，而非仅改标签。原色/传递函数按常见 SDR 709
写入，输入未指定时仍是工作假设；没有做基于 ICC、HDR 或未知原色的完整色域管理。
HEVC alpha 输出为 YUVA420p；FFV1 mode 2 保留 YUV444 样本，仅按指定范围/矩阵
写标记，RGBA 管道则输出转换后的像素。

## 未来布局与手动覆盖

将来可能出现新的模式编号、外壳版本、抽样或 alpha 打包方式，也可能因资源损坏
出现异常编号。目前没有证据说明下一种模式的具体含义，工具不会根据高度差自动猜测。
未知模式会停止并显示本地诊断命令；报告仅在用户显式 `--consent` 后生成，
不上传文件。报告内容和手动提交步骤见[完整说明](usage.md#未知布局诊断与手动覆盖)。

`--force-mode 0/1/2` 只改变平面的解释方法，不是通用新格式解码器；仍校验已知
版本、Ogg 起点、4:4:4 抽样和相应尺寸。它适合标签与实际布局不符的已确认文件。
错误覆盖可能输出色偏；尤其 mode 0 与 mode 2 尺寸相同，结构校验无法判断颜色是否正确。

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
