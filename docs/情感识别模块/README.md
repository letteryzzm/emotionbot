# 情感识别模块（FER / SER / TER）调研与执行方案

> 当前选型见[下一阶段方案：上位机情绪识别与表情标定](../下一阶段方案-上位机情绪识别与标定.md)（2026-11-10）：取消 T5；按实验补充结论采用本地快层、上下文文本模块与 Omni 慢层。以下保留 10 月研究计划，实际实验结果以 [06 实验报告](06-实验报告.md)为准。

> 日期：2026-10-18
> 负责范围：人脸情绪识别（FER）、语音情感识别（SER）、文本情感识别（TER），以及三者的融合
> 上游文档：`../情感计算×脑机接口×机器人调研报告.md`（总调研）、`../复现计划.md`（机器人头 L1–L4 路线，本模块对应 L3 的感知端）
> 代码位置（待建）：`perception/`

## 文档索引

| 文件 | 内容 |
|---|---|
| [01-学习资源.md](01-学习资源.md) | 社区笔记和教程 → 综述 → 关键论文 → 可直接用的开源实现，按 FER / SER / TER / 融合分组，给出阅读顺序 |
| [02-硬件与算力评估.md](02-硬件与算力评估.md) | MacBook Air M4 16GB 能做什么、不能做什么；云 GPU 配置、时长和预算 |
| [03-验收标准.md](03-验收标准.md) | 可量化的验收指标：复现精度、自采数据精度、延迟、鲁棒性、工程质量 |
| [04-最终展示.md](04-最终展示.md) | 展示交付物设计：主流方法对比 benchmark + 实机 live demo + 消融图 |
| [05-后续优化.md](05-后续优化.md) | 做完之后往哪里优化，按收益排序 |
| [06-实验报告.md](06-实验报告.md) | 2026-10-19 云 GPU 测评结果：三代方法 × 三模态、融合、闭源 API 对比，逐条对照验收标准 |
| [07-三模态解构与情绪体系.md](07-三模态解构与情绪体系.md) | 情绪标签体系（Ekman / V-A / PAD / 极性），人脸（类别 / AU / V-A / landmark）、语音（韵律 / 音质 / 频谱）、文本（极性 → ERC）各自怎么拆，以及怎么拼成统一输出 |

## 一页结论

1. **统一标签空间用 7 类**：neutral / happy / sad / angry / surprise / fear / disgust。SenseVoice 的情感标签、DFEW、M3ED 都是这 7 类，天然对齐；AffectNet 多出的 contempt、emotion2vec 多出的 other / unknown 映射为 `other`，不参与 7 类指标。再额外输出 valence / arousal（V/A）两维连续值，作为可选字段。
2. **每个模态都按"三代方法"做对比**，这是展示"熟悉主流方案"的主线：
   - 传统特征 + 浅层分类器（MFCC+SVM、landmark/HOG+SVM、词典/TF-IDF）
   - 自监督或专用预训练模型（emotion2vec+、EmotiEffLib、Chinese RoBERTa 微调）
   - 大模型（SenseVoice 一体化、VLM / Qwen-Omni zero-shot、LLM ERC）
3. **共用评测集是 M3ED**（中文电视剧对话，音频 + 视频 + 文本三模态都有，7 类标签）。单模态再各配一个领域标准集：SER 用 EmoBox 划分的 RAVDESS / CREMA-D / ESD，FER 用 RAF-DB / AffectNet / DFEW，TER 用 M3ED 文本和 CPED。
4. **本地 Mac 足够做全部推理和大部分实验**；只有三件事需要云 GPU：动态 FER 视频模型微调、LLM 的 LoRA 微调（InstructERC 路线）、7B 级全模态模型批量评测。估计总共约 60 卡时（RTX 4090 级别），详见 02。
5. **最终展示 = 一张 benchmark 大表 + 一个实机 demo + 三张消融图**，详见 04。

## 统一输出接口（三个模块都遵守）

```python
@dataclass
class EmotionEstimate:
    modality: Literal["face", "speech", "text", "fused"]
    t_start: float           # 秒，单调时钟
    t_end: float
    probs: dict[str, float]  # 7 类 + "other"，和为 1
    valence: float | None    # [-1, 1]
    arousal: float | None    # [-1, 1]
    confidence: float        # 校准后的置信度，用于融合加权
    extra: dict              # 如 AU、ASR 文本、帧数
```

对齐规则：以 VAD 切出的一句话为时间窗，窗内 FER 帧结果做加权平均（按人脸检测置信度），SER 和 TER 每句一个结果。没有人脸或没有语音时该模态缺失，融合层要能处理缺失。
