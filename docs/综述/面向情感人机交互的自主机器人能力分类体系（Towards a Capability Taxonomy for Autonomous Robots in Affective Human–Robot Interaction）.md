Y. Sun and T. Wang, "Towards a capability taxonomy for autonomous robots in affective human–robot interaction," _Electronics_, vol. 15, no. 8, Art. no. 1696, Apr. 2026, doi: 10.3390/electronics15081696.


# abstract

> Autonomous robots are increasingly integrated into social contexts, making affective human–robot interaction (HRI) critical for their effectiveness and acceptance. However, existing research remains dispersed across domains and techniques, lacking a unified framework to characterize core robotic capabilities.

自主机器人越来越多地进入社会情境，因此情感人机交互（affective human–robot interaction, affective HRI）对机器人的有效性和被接受程度至关重要。但已有研究分散在不同领域和技术里，缺少一个统一框架来刻画机器人的核心能力。

> To address this gap, we adopt a capability-oriented perspective and conduct a comprehensive literature review, through which we propose a structured taxonomy of capabilities for robots in affective HRI.

为了填补这个空白，作者采用**以能力为导向（capability-oriented）**的视角做了一次全面的文献综述，并在此基础上提出一个结构化的情感 HRI 机器人能力分类体系（taxonomy）。

这个分类体系包括五个核心维度：

| 维度 | 含义 |
|---|---|
| **感知（perception）** | 识别人的内部状态 |
| **策略（strategy）** | 根据人的状态和情境规划回应 |
| **表达（expression）** | 传达机器人的生命感（lifelikeness）和社会临场感（social presence） |
| **可持续性（sustainability）** | 长时间保持有效、可靠的运行 |
| **伦理（ethics）** | 保证行为在伦理约束之内 |

通过把各种研究组织进一个结构化框架，这个分类体系为设计有社交能力的机器人、指导未来研究提供了系统基础。

# 1 Introduction

**① 背景**

> Robots are increasingly deployed in human-centered environments such as education, healthcare, service, companionship, and everyday living, where interaction with humans is frequent, prolonged, and socially situated.

机器人越来越多地部署在以人为中心的环境中，比如教育、医疗、服务、陪伴和日常生活。在这些环境里，和人的互动**频繁、持久，并且处在社会情境中**。在这些情境下，互动往往不只是任务协调，还涉及对情感信号和社交信号的解读与表达。

要有效运作，机器人必须能够：
- 理解人的内部状态；
- 生成符合情境的回应；
- 通过行为传达信息和意图。

做到这些需要一套系统的、与情感 HRI 相关的能力。要系统地理解连贯的、具有情感意识的人机交互需要哪些核心能力，就需要一个统一的视角。但虽然过去十年具体的机器人行为研究进展很大，相关贡献仍然分散在不同的应用领域和技术路线里。

**② 本文做什么**

> To address the lack of a systematic view, we develop a capability-oriented taxonomy that not only organizes existing research but also clarifies the capabilities enabling robots to interact with humans in affective and socially meaningful ways.

为了弥补系统视角的缺失，作者建立了一个以能力为导向的分类体系。它不仅整理已有研究，也说明哪些能力让机器人能以情感上、社交上有意义的方式和人互动。这个分类体系：
- 帮助研究者把自己的工作放到情感 HRI 的整体版图中定位；
- 给系统设计者提供一个参考，用来评估一个机器人系统覆盖了哪些能力、还缺哪些。

**③ 文献来源**

> To ensure a representative and systematic selection of the literature, we conducted a longitudinal survey of the ACM/IEEE International Conference on Human–Robot Interaction (HRI) from 2015 to the present, a venue dedicated exclusively to the HRI field.

为了保证选取的文献有代表性、成体系，作者对 **ACM/IEEE HRI 会议**（专门面向 HRI 领域的会议）从 **2015 年至今**的论文做了纵向调研。以这个会议为主要来源，识别新趋势，建立初步的结构框架；然后有针对性地扩展到其他高影响力的期刊和会议，纳入不同视角，保证结论的普适性。识别出的能力被组织成几个相互关联的类别：

| 类别 | 关注什么 |
|---|---|
| 感知 | 识别和解读人的内部状态，比如情绪和意图 |
| 策略 | 生成自适应的、有情境意识的互动策略 |
| 表达 | 以人能感知、能理解的方式传达机器人的内部状态和社交信号 |
| 可持续性 | 长期互动所需的能力 |
| 伦理 | 按照人类伦理规范行事，并考虑互动和技术使用可能带来的伦理问题 |

**④ 三点贡献**

1. 基于对情感 HRI 的文献综述，提出一个以能力为导向的分类体系，整理情感 HRI 能力、明确各自范围，并给出代表性例子说明它们的实际意义；
2. 提供一个概念框架，帮助研究者把自己的工作放到情感 HRI 的整体版图中；
3. 给设计者提供一个框架，用来评估和指导开发能进行连贯、长期、具有情感意识的互动的机器人。

文章结构：第 2 节回顾相关研究；第 3 节介绍分类体系并详细讨论各能力类别；第 4 节用这个框架分析现有机器人（案例研究）；第 5 节总结并讨论未来方向。

> [!note] 小结
> 第 1 节交代动机：机器人进入**频繁、持久、社会化**的场景，需要一整套情感能力，但研究**很分散**。本文的定位是**以能力为导向的分类体系**，不是做新方法，而是给研究者一张"地图"、给设计者一张"检查清单"。文献主要来自 **ACM/IEEE HRI 会议 2015 年至今**的论文。

# 2 Related Work（相关工作）

很多综述研究过人机交互，既有安全、交流这类一般性话题，也有情绪识别这类情感方面的话题。本节把代表性综述分成一般 HRI 综述和情感/情绪相关综述两类，作为提出能力分类体系的背景。

## 2.1 General HRI Surveys（一般 HRI 综述）

| 方向 | 代表综述 | 内容 |
|---|---|---|
| **领域总览** | Lambert et al. | 十年社交机器人互动研究：研究主题、应用领域、机器人能力 |
| | Youssef et al. | 社交机器人学进展：应用领域、互动模态、机器人平台、评估方法 |
| | Apraiz et al. | 24 篇 HRI 用户体验（UX）评估研究：常评估的因素、测量方法、研究空白 |
| | Ostrowski et al. | 从伦理、公平和正义的角度回顾二十年 HRI 研究，提出包容、负社会责任的机器人设计框架 |
| | Robinson et al. | HRI 和协作中的机器人视觉：应用、方法、数据集、评估方式 |
| **工业 / 协作** | Li et al. | 工业人机协作中的安全方法，分为碰撞前和碰撞后策略 |
| | Rodríguez-Guerra et al. | 安全部署协作机器人的挑战 |
| | Jahanmahin et al. | 面向制造业 HRI 的人类行为建模：感知、预测、控制 |
| **交流** | Bonarini | HRI 中的交流，强调语言通道和物理通道 |
| | Su et al. | 多模态 HRI：语音、视觉、触觉、生物信号的融合 |
| | Nocentini et al. | 社交机器人的行为模型，包括自适应行为和认知架构 |
| **HRI 分类体系** | Tolmeijer et al. | 与信任相关的失败类型（设计、系统、期望、用户失败）及缓解策略 |
| | Onnasch & Roesler | 从人、机器人、互动、情境四方面建立的 HRI 分类体系，便于跨场景比较 |
| | Kim et al. | 机器人自主性的六种形式：操作、意图、共享、非确定性、认知和物理自主 |

> While these works provide valuable frameworks for general HRI, there remains a lack of a systematic taxonomy specifically focused on robot capabilities within the context of affective HRI.

这些工作为一般 HRI 提供了有价值的框架，但还**缺少一个专门聚焦情感 HRI 中机器人能力的系统分类体系**。本文想填补这个空白。

## 2.2 Affective/Emotion-Related HRI Surveys（情感 / 情绪相关的 HRI 综述）

越来越多的综述考察了人机交互中情感和情绪的方面，包括情绪识别、表达和社会情感联结。

| 方向 | 代表综述 | 内容 |
|---|---|---|
| **情绪识别** | Spezialetti et al. | 情绪识别进展：情绪模型、互动模态、分类策略 |
| | **Stock-Homburg** | 二十年来机器人情感生成、人的识别和反应的研究（就是本目录里的上一篇综述） |
| | Cavallo et al. | 机器人怎样用不同感知模态识别并回应人的情绪 |
| | Cerqueira | 72 篇情绪识别和机器人情绪表示研究，强调以用户为中心的评估 |
| **多模态 / 特殊感知** | Ottoni & Filippini et al. | 用于情感计算的热红外成像，强调非侵入性 |
| | Kovács et al. | 非言语交流、手势和用户个性，用来提升机器人表现力和信任 |
| | Zhao et al. | 按输入模态（视觉、语言、生理信号、多模态）给机器人情绪识别模型分类 |
| | Gasteiger et al. | 情感语音中的韵律要素：语调、响度、语速、停顿 |
| | Savery & Weinberg | 1427 篇机器人与情感的文献，分为情绪智力、情绪模型和实现三类 |
| **高层情感** | Mitchell & Jeon | 30 篇 HRI 依恋研究，关注情感联结和心理依恋理论 |
| | Hieida & Nagai | 机器人中的社会情感，把心理学和神经科学的发现连接到机器人的识别、表达和建模 |
| | de Souza et al. | 34 篇 HRI 中信任与可信度的研究 |

> While existing surveys provide valuable overviews of general and affective HRI, they focus on individual dimensions without integrating them into a coherent framework.

已有综述对一般 HRI 和情感 HRI 都提供了有价值的概览，但它们只聚焦**单个维度**，没有整合成一个连贯的框架。本文用统一的能力分类体系补充这些研究。

> [!note] 小结
> 第 2 节把已有综述分成两堆：**一般 HRI**（安全、交流、UX、已有分类体系）和**情感 HRI**（识别、多模态感知、依恋、信任）。共同问题是**各管一块、不成体系**，这就是本文要补的空白。上一篇 Stock-Homburg 综述也被列在"情绪识别"这一类里。

# 3 Taxonomy（分类体系）

> To systematically characterize the capabilities required for autonomous robots in affective human–robot interactions, we propose a taxonomy that organizes these capabilities into five interrelated categories: perception, strategy, expression, sustainability, and ethics.

为了系统地刻画情感人机交互中自主机器人需要的能力，作者提出一个分类体系，把这些能力组织成五个相互关联的类别：**感知、策略、表达、可持续性和伦理**。

**① 设计灵感：感知–规划–行动（SPA）范式**

> Our taxonomy is conceptually inspired by the sense–plan–act (SPA) paradigm, in which a robot first senses its environment, then plans appropriate actions, and finally executes them.

这个分类体系在概念上受**感知–规划–行动（sense–plan–act, SPA）范式**启发：机器人先感知环境，再规划合适的动作，最后执行。SPA 最初是为系统级任务执行提出的，现在已经基本被更一体化或分层的控制架构取代，但它仍然提供了一个有用的概念视角：它强调感知、决策和行动这三种能力，不管底层系统怎么设计，这三者都是必不可少的。

情感人机交互可以看成一种特殊的机器人情境：环境中包括人类伙伴以及他们的内部状态。因此，机器人需要专门针对情感互动的感知、决策和行动能力。

| SPA 阶段 | 对应的能力 | 含义 |
|---|---|---|
| Sense（感知） | **感知（perception）** | 感知人的内部状态 |
| Plan（规划） | **策略（strategy）** | 根据感知到的状态和情境，在内部决策规划合适的回应 |
| Act（行动） | **表达（expression）** | 在互动中通过可观察的动作实现社交和情感行为 |
| （SPA 之外） | **可持续性（sustainability）** | 通过识别错误、恢复错误、持续向人学习，长期保持稳定、自适应的互动 |
| （贯穿全部） | **伦理（ethics）** | 遵守伦理原则，保证情感 HRI 各方面的行为和互动都符合人的价值观 |

**Fig. 1：情感人机交互能力分类体系总览**

```
(a) 分类体系
├── 感知 Perception
│   ├── 情绪识别 Emotion Recognition
│   ├── 认知状态识别 Cognitive State Recognition
│   └── 个性识别 Personality Recognition
├── 策略 Strategy
│   ├── 情境感知与适应 Context Awareness and Adaptation
│   ├── 适应个体差异 Adapting to Individual Differences
│   ├── 适应人的心理状态 Adapting to Human Mental State
│   ├── 适应意外的人类行为 Adapting to Unexpected Human Behaviors
│   └── 心理助手能力 Mental Assistant Capability
├── 表达 Expression
│   ├── 情绪表达 Emotional Expression
│   ├── 认知状态表达 Cognitive State Expression
│   ├── 社交信号表达 Social Signal Expression
│   └── 拟人化 Anthropomorphism · 生命感 Vitality · 礼貌 Politeness · 信任 Trust
├── 可持续性 Sustainability
│   ├── 向人学习 Learning from Human
│   └── 失败处理与恢复 Failure Handling and Recovery
└── 伦理 Ethics
    ├── 隐私保护 Privacy Protection
    ├── 道德意识 Moral Awareness
    ├── 避免欺骗 Deception Avoidance
    └── 避免歧视 Discriminatory Avoidance

(b) 和 SPA 的对应：Sense → Perception，Plan → Strategy，Act → Expression
```

**② 写法说明**

> It is worth noting that many of these capability classes are themselves extensive research areas, each of which could warrant a dedicated survey. Therefore, rather than aiming for exhaustive coverage, we focus on highlighting a small number of representative works for each category.

值得注意的是，很多能力类别本身就是很大的研究领域，每个都值得写一篇专门的综述。所以本文**不追求完整覆盖**，而是每类只挑少数代表性工作，用来说明关键思路和典型方法。

## 3.1 Basic Intelligent Capabilities（基础智能能力）

虽然本文主要关注情感互动和机器人相关的能力，但一组**基础智能能力**仍然是支撑有效人机交互的基础。这些能力支撑机器人在真实世界中感知、行动、可靠运行，从而让更高层的情感和社交行为成为可能。

> In general, such foundational capabilities include, but are not limited to, multimodal perception and information processing, physical manipulation and task execution, autonomous decision-making and control, navigation and environment adaptation, as well as basic communication and coordination mechanisms.

一般来说，基础能力包括但不限于：
- 多模态感知和信息处理；
- 物理操作和任务执行；
- 自主决策和控制；
- 导航和环境适应；
- 基本的交流和协调机制。

此外，机器人的**具身形态（embodiment）和外形**，以及适应不同应用情境和团队配置的能力，也对互动结果有重要影响。

作者把基础智能能力作为一个必要模块放进分类体系，保证结构完整，但**不再细分**。因为本文的主要目标是细化最贴近情感互动的能力，而更一般的机器人功能已经有大量研究和标准化分类（比如 Onnasch & Roesler 的 HRI 分类体系）。

## 3.2 Perception Capability（感知能力）

> Perception capability refers to a robot's ability to infer human internal state, including latent cognitive and affective states.

**感知能力**指机器人推断人的内部状态的能力，包括潜在的认知状态和情感状态。在 HRI 中，识别人的内部状态对实现得体的、自适应的互动非常重要。

内部状态包括两类：
- **短暂的心理状态（mental states）**：又分为情感状态（情绪）和认知状态；
- **相对稳定的特质（traits）**。

所以人类内部状态的识别分为三方面：**情绪识别、认知状态识别和特质（个性）识别**。

注意：在 HRI 中识别手势、语音等人类信号也很关键，但这些信号不一定和情感状态有关，所以被归入基础智能能力，这里不详细讨论。

### 3.2.1 Emotional Recognition Capability（情绪识别能力）

> Emotional recognition capability refers to the ability to identify the emotions of interaction subjects accurately.

情绪识别能力指准确识别互动对象情绪的能力。识别人的情绪在互动中很重要，因为情绪状态强烈影响人的行为。通过感知情绪线索，机器人能相应调整回应，让交流更自然、更有同理心。

| 研究 | 方法 | 结果 |
|---|---|---|
| Mohamed et al. | 用**热成像面部图像**自动识别 HRI 中的挫败感（frustration），关注认知负荷和失败引起的挫败 | 关键面部区域的热特征能有效捕捉挫败的生理相关信号，效果和基于 RGB 的面部特征相当 |
| Deng et al. | 基于**条件 GAN** 的面部表情识别框架，联合学习生成式和判别式表示，以减小类内差异 | 通过控制动作单元（AU）并施加循环一致性，把表情和身份等因素解耦，提升了 FER 性能 |
| Mamodiya et al. | **ECRP**：可部署在边缘设备上的 HRI 框架，整合多模态情绪识别、情境编码和基于强化学习的任务规划 | 在资源受限的机器人上实现低延迟的自适应行为 |

### 3.2.2 Cognitive State Estimation Capability（认知状态估计能力）

> Cognitive state estimation capability refers to the ability to infer the internal cognitive states of interaction subjects, such as intentions, attention, or confusion, from observable behavioral signals.

认知状态估计能力指从可观察的行为信号推断互动对象内部认知状态的能力，比如**意图、注意力或困惑**。估计这些状态能让机器人更好地理解人的需求和正在进行的心理过程，从而实现更自适应、更主动的互动。

**意图识别（intent recognition）**

意图识别是认知状态估计的一个重要方面。通过预判用户需求，机器人能主动帮助用户、提高互动效率。

| 研究 | 依据的信号 | 方法与结果 |
|---|---|---|
| Huang & Mutlu | **注视（非言语）** | 预判式控制框架，从注视行为推断协作中人的任务意图：提取注视点特征，用 SVM 分类器提前预测人想要的目标，让机器人能主动规划动作，协作更流畅 |
| Ryoo et al. | **第一人称视频** | 引入起始线索（onset cues）和级联直方图表示，在以机器人为中心的第一人称视频中提前预测人的活动，让机器人能及时回应 |
| Huggins et al. | **文本** | 针对 HRI 意图识别中数据稀缺的问题，提出基于 BERT 的少数据方法；在公开数据集上和 BiLSTM、逻辑回归比较，并在一个识别性格优势的真实社交机器人任务中验证；结果显示完整微调 BERT 很有效 |

**其他认知状态**

除了理解意图，估计其他认知状态对有效互动也很重要：
- **困惑（confusion）**：Li et al. 研究了情境化任务导向人机对话中对话者的困惑。他们分析了情绪、头部姿态、眼睛注视、说话沉默时长和自报的困惑状态等多模态线索，发现这些信号和用户困惑显著相关。检测到困惑后，机器人可以调整对话策略、及时解释。
- **注意力（attention）**：Chakraborty et al. 提出一个基于**视觉注意焦点（visual focus of attention, VFOA）**估计人注意力水平的人机交互系统。它用深度学习模型分析面部特征、眼球运动和注视，让机器人检测用户的注意状态，并发起合适的语言或视觉互动。

### 3.2.3 Personality Recognition Capability（个性识别能力）

> Personality recognition capability refers to the ability to accurately identify the personality traits of interaction subjects. It enables robots to develop personalized strategies tailored to the identified personality.

个性识别能力指准确识别互动对象个性特质的能力。它让机器人能针对识别出的个性制定**个性化策略**，从而提高互动效果和用户满意度，带来更舒适、更投入的体验。

| 研究 | 内容 |
|---|---|
| Celiktutan et al. | 发布 **MHHRI 数据集**，用于研究人–人互动（HHI）和人–机器人互动（HRI）中的个性与投入度，包含多模态记录以及自评和熟人评注 |
| Salam et al. | 研究三方（人–人–机器人）互动中的投入度预测。把自动预测的参与者个性、机器人个性和非言语特征结合起来，比只用非言语特征更能提升个人和群体投入度分类；**外向型**的互动分类效果最好 |
| Shen et al. | 从面对面 HRI 中用户习惯性的视觉和声音行为推断个性特质，用问卷标签训练回归和分类模型，以提升互动质量 |

> [!note] 小结
> **感知 = 推断人的内部状态**，按时间稳定性分三层：
> - **情绪**（短暂、情感性）：热成像识别挫败、GAN 做表情识别、边缘部署的多模态框架；
> - **认知状态**（短暂、认知性）：**意图**（注视 / 第一人称视频 / 文本 BERT）、**困惑**、**注意力**（VFOA）；
> - **个性**（稳定特质）：MHHRI 数据集，个性 + 非言语特征预测投入度。
>
> 注意：手势、语音这类**和情感无关的信号识别**被划到了基础能力里，不算感知能力。

## 3.3 Strategy Capability（策略能力）

> In the classical sense–plan–act (SPA) paradigm, the plan component represents the process through which a robot determines appropriate actions based on perceived information and its internal representation of the environment.

在经典的 SPA 范式里，"规划"部分代表机器人根据感知到的信息和对环境的内部表示来决定合适动作的过程。受此启发，作者把情感人机交互中的**策略能力**看作：机器人根据对情境和人类伙伴的理解，决定应该产生什么互动回应和策略的能力。

**① 核心是适应性（adaptivity）**

如 Fig. 2 所示，这种能力的核心是**适应性**。在互动中，机器人应该能根据多种信息来源调整回应：

| 信息来源 | 说明 |
|---|---|
| 情境信息 | 互动情境可以看成经典机器人架构中**世界模型（world model）**的扩展，加入了物理环境以外的社会相关信息 |
| 人的心理状态 | 人的内部状态也是世界模型的扩展 |
| 个体差异 | 内部状态中较稳定的特质，体现为个体差异，用来指导个性化回应 |
| 意外的人类行为 | 当人的行为偏离预期模式时，机器人也要能恰当应对 |

**② 特殊维度：促进人的心理健康**

除了一般的适应性互动，作者还识别出一个专门的策略维度：**促进人的心理福祉**。越来越多的研究探索机器人怎样主动支持心理健康，或者辅助自闭症谱系障碍、认知衰退等状况的干预。为此作者引入**心理助手能力（mental assistant capability）**，指机器人提供心理支持或促进干预型互动的能力。

**Fig. 2：情感 HRI 中的策略能力**

```
策略 Strategy
├── 适应性 Adaptivity
│   ├── 情境 Context
│   ├── 人的心理状态 Human Mental State
│   ├── 个体差异 Individual Difference
│   └── 意外的人类行为 Unexpected Human Behavior
└── 心理助手 Mental Assistant
    ├── 情感支持 Emotional Support
    └── 特殊支持 Special Support（自闭症、痴呆等）
```

### 3.3.1 Context Awareness and Adaptation（情境感知与适应）

在互动中，机器人应该根据互动对象的状态或任务情境调整互动策略，增强在真实场景中的适应性。

| 研究 | 内容 |
|---|---|
| Hemminghaus & Kopp | 基于**强化学习**的辅助机器人自适应社交行为架构，用 Q-learning 根据用户状态优化低层行为；在 Furhat 机器人的记忆游戏中验证，能有效适应不同用户 |
| Doğan et al. | 一个通过**追问澄清**来消除人机对话中物体指代歧义的交互系统，比重新描述的策略效果更好，提高了互动效率和用户评价 |
| Andriella et al. | 研究 Tiago 机器人在短期真实互动中的自适应辅助能力，机器人能根据用户表现和任务状态动态调整支持，即使在一次性、不受控的场景中也能改善任务结果 |
| Xing et al. | 面向未知环境中由人引导的机器人，提出**自适应阻抗学习**框架，自动调整阻抗参数，在保证物理互动稳定高效的同时减少人的用力 |

### 3.3.2 Adapting to Human Mental State（适应人的心理状态）

> In a human–robot interaction, a robot's ability to respond appropriately to human mental states is crucial for effective collaboration and socially appropriate interaction.

在人机交互中，机器人能否恰当回应人的心理状态，对有效协作和得体的互动非常关键。这包括给出有同理心的回应，以及调整自己的行为来更好地支持人。

| 研究 | 内容 |
|---|---|
| Chen et al. | 儿童–机器人互动中，情感在**细粒度事件**层面比在粗粒度层面更能预测学习效果，尤其是机器人扮演"学生（tutee）"时；这些线索可以用来预判孩子的表现 |
| Unhelkar et al. | **CommPlan**：一个部分可观测马尔可夫决策过程（POMDP）框架，把人的意图显式建模为隐状态，让机器人决定**要不要、什么时候、说什么**（比如分享自己的意图或询问人的意图），以提高协作效率 |
| Devin & Alami | 一个**心智理论（Theory of Mind）**框架，让机器人估计人的心理状态，包括对目标、计划和动作的信念，从而调整共享计划的执行，并在协作中及时、不打扰地提供信息 |

### 3.3.3 Adapting to Individual Differences（适应个体差异）

在人机交互中，用户在个性、偏好和行为倾向上存在很大的个体差异。有效的机器人应该相应调整互动策略，为每个用户定制行为，以提高投入度、互动质量和整体用户体验。

| 研究 | 内容 |
|---|---|
| Ramachandran et al. | 研究机器人辅导儿童时的**个性化休息时机**策略。Nao 机器人监测孩子的表现，提供固定的、基于奖励的或基于重新集中注意力的休息。个性化策略带来更大的学习收益，解题效率和准确率也立即提高 |
| Li et al. | 研究**特质孤独感**的个体差异怎样影响对社交机器人的感知和接受。孤独感越高，正面的拟人化推断（比如温暖、能力）和接受度越低，中介是对礼貌、条理等"人类独有特质"的归因更少 |
| Ligthart et al. | 一种**基于记忆的个性化**策略，用存储的互动历史定制叙事对话，在多次会话的长期儿童–机器人关系中增强连续性、亲近感和持续投入 |

### 3.3.4 Adapting to Unexpected Human Behavior（适应意外的人类行为）

> Given that human behavior is often boundedly rational, robots need to manage actions that are unexpected or suboptimal.

人的行为往往是**有限理性（boundedly rational）**的，所以机器人需要处理意外的或次优的行为。

| 研究 | 内容 |
|---|---|
| Görür et al. | 面向协作机器人的**两阶段 POMDP** 框架，预测人的可用性、动机和能力，推断人真正需要什么帮助；比被动反应式模型的协作效率和互动自然度更高 |
| Kwon et al. | 基于**累积前景理论（Cumulative Prospect Theory）**的风险感知机器人模型，能预判人的次优行为，比"带噪声的理性人"模型支持更安全、更高效的协作 |

### 3.3.5 Mental Assistant Capability（心理助手能力）

> Mental assistant capability refers to a robot's ability to provide targeted and adaptive support based on a user's internal states and situational context.

心理助手能力指机器人根据用户的内部状态和情境提供有针对性的、自适应的支持的能力。它关注理解并回应情感或心理需求，让机器人能提供合适的干预。

**① 情感支持：帮助调节负面情绪**

情感型心理助手能力的一个关键功能，是帮助用户调节和应对负面情绪状态，也就是让机器人能识别、回应并帮助缓解负面情绪。

| 研究 | 内容 |
|---|---|
| Dino et al. | 一个社会辅助机器人，通过结构化对话提供**互联网认知行为疗法（iCBT）**，在患抑郁症的老年人中验证了可行性和接受度 |
| Kitt et al. | 在标准化压力任务中考察社会辅助机器人对儿童心理健康护理的**压力缓冲**作用。没有观察到压力显著降低，但研究揭示了细微的情感反应，并提示对社交焦虑较高的儿童可能有益 |
| Laban et al. | 一种新的长期干预：用社交机器人帮助**非正式照护者**通过自我表露（self-disclosure）应对情绪困扰。多次互动后，照护者自我表露增加、心情改善、孤独感和压力降低 |

**② 特殊支持：自闭症、痴呆等**

对于有社交困难或其他特定状况的人，比如**自闭症谱系障碍（ASD）**或**痴呆**，机器人可以提供有针对性的支持。

| 研究 | 内容 |
|---|---|
| Ramnauth et al. | **ISTAR**：一个居家社交机器人，给患 ASD 的成人提供逼真的职场式打断，通过自主角色扮演训练提高对打断的容忍度，以提升就业能力 |
| Sandygulova et al. | 研究 ASD 严重程度、共患 ADHD、语言能力和年龄等个体差异，怎样影响儿童在多次机器人辅助自闭症治疗中的投入和行为结果 |
| Moharana et al. | 和痴呆照护者共同设计机器人：要么营造快乐的共享时刻，要么减轻情感负担（比如转移重复提问，或者扮演"坏人"），角色随痴呆阶段调整 |
| Cruz-Sandoval et al. | 部署一个自主社交机器人，给痴呆患者提供**九周认知刺激疗法**，激越、妄想、欣快等神经精神症状显著减少 |

> [!note] 小结
> **策略 = 根据人和情境决定怎么回应**，相当于 SPA 里的 Plan：
> - **适应性**的四个来源：**情境**（RL、追问澄清、阻抗自适应）、**心理状态**（POMDP 建模意图、心智理论）、**个体差异**（个性化休息、孤独感、记忆个性化）、**意外行为**（有限理性、累积前景理论）。
> - **心理助手**：**情感支持**（iCBT、压力缓冲、照护者自我表露）+ **特殊支持**（ASD、痴呆）。
> - 常用工具：**强化学习、POMDP、心智理论**；情境和人的内部状态被看作**世界模型的社会化扩展**。

## 3.4 Expression Capability（表达能力）

> In affective human–robot interaction, expression capability refers to a robot's ability to manifest internal states and convey social signals through observable behaviors, thereby determining how these internal states and signals are presented during interaction, while also exhibiting social legibility and naturalness throughout the interaction.

在情感人机交互中，**表达能力**指机器人通过可观察的行为表现内部状态、传达社交信号的能力。它决定了这些内部状态和信号在互动中怎样呈现，同时也要让整个互动**在社交上易读、自然**。这些表达行为不只传递信息，也塑造人对机器人的感知，影响它被感知到的生命感和社会临场感。

**表达能力的三个方面**

| 方面 | 作用 | 包括 |
|---|---|---|
| **感知特征（perceptual characteristics）** | 塑造机器人作为一个社会主体被怎样感知 | 拟人化（anthropomorphism）、生命感（vitality），这是带来"像活物"感觉的两个关键维度 |
| **信息表达（information expression）** | 在互动中传达信息 | 情绪表达、认知状态表达、社交信号表达 |
| **社会互动品质（social interaction qualities）** | 表达行为所传达的社会含义，影响人怎样理解机器人的社交态度 | 礼貌（politeness）、信任（trust） |

**Fig. 3：情感 HRI 中与表达相关的能力**

```
表达 Expression
├── 感知特征 Perceptual Characteristics：拟人化、生命感
├── 信息表达 Information Expression：情绪表达、认知状态表达、社交信号表达
└── 社会互动品质 Social Interaction Qualities：礼貌、信任
```

### 3.4.1 Emotional Expression Capability（情绪表达能力）

> Emotional expression capability encompasses the ability to effectively translate internal affective states into observable external signals.

情绪表达能力指把内部情感状态有效转化为可观察外部信号的能力。它支持自然、有丰富社交性的互动，并影响人在互动中对机器人的感知。情绪可以通过多种模态表达：

| 研究 | 模态 | 发现 |
|---|---|---|
| Velner et al. | **语调** | 像人一样的语调能提高机器人说话的自然度和情绪表现力，但不能提高话轮转换（turn-taking）的流畅度 |
| Hu & Hoffman | **皮肤纹理** | 动态驱动的皮肤纹理（比如鸡皮疙瘩、尖刺）能有效传达特定情绪：**纹理形状表示效价，运动频率表示唤醒度** |
| Pelikan et al. | **动画（Cozmo）** | 分析家庭怎样解读 Cozmo 的情绪展示："开心"动画会推动互动继续，"难过"动画则像一个"**倒带键**"，促使用户重新审视自己之前的动作 |
| Suguitan et al. | **手势** | **MoveAE**：一个做分类的变分自编码器（VAE），通过潜空间运算修改机器人手势的情绪特质，同时保留手势的可识别性 |
| Block et al. | **拥抱 / 触觉** | 设计了一个人体大小的拥抱机器人，用柔软、温暖和自适应的触觉反馈提供有情感支持的拥抱，显著提升了自然度、愉悦度和友好度 |
| Au et al. | **触摸（跨文化）** | 研究机器人中介的情感触摸在美国和日本用户中传达同情的效果，接收者从机器人触摸中感受到的社会支持比从文字中更多 |
| Dobrosovestnova & Hannibal | **矛盾情绪** | 主张在机器人教师中加入**矛盾情绪**，比如老师的失望，把它看成一种基于关怀、增进亲近的教学策略，而不是单纯的负面情感 |

**评估工具**

要系统地研究机器人的情绪表达，需要标准化的评估工具来量化人感知到的情绪有多清晰、多容易区分。Coyne et al. 提出用**日内瓦情绪轮（Geneva Emotion Wheel）**作为评估机器人情绪表现力的系统工具，可以定量分析 HRI 中情绪的区分度和清晰度。

### 3.4.2 Cognitive State Expression Capability（认知状态表达能力）

> Cognitive state expression refers to how robots convey internal mental states—such as attention, intention, or curiosity—through observable behaviors.

认知状态表达指机器人怎样通过可观察的行为传达内部心理状态，比如**注意力、意图或好奇心**。把这些内部认知过程表现出来，人就能更好地感知和理解机器人的状态，从而提高互动的**透明度**和效果。

| 研究 | 内容 |
|---|---|
| Gordon et al. | 孩子和一个**好奇的**社交机器人互动后，表现出更多探索行为和对不确定性的追求，说明好奇心可以在人机交互中被社会性地激发 |
| Zhang et al. | 研究好奇心驱动的、偏离任务的机器人行为怎样影响人的感知。这类行为会被理解为好奇，但会降低被感知到的**能力**，除非附带解释性线索 |
| Aliasghari et al. | 人形机器人的**注视分配**和**手臂动作的流畅度**，显著影响人类老师对它的自信、学习渴望和任务注意力的感知，这些都是学习互动中的关键认知状态 |
| Briggs et al. | 把注意力驱动的认知框架（ARCADIA）和机器人架构（DIARC）整合起来，在物体学习任务中生成动态的、像人一样的注视，反映机器人内部的注意焦点 |

### 3.4.3 Social Signal Expression Capability（社交信号表达能力）

社交信号表达能力让机器人能通过可观察的行为传达社交线索，帮助人理解机器人的动作、理解它的社会角色，并恰当地参与互动。

| 信号 | 研究 | 发现 |
|---|---|---|
| **注视** | Terzioğlu et al. | 受动画原则启发，给协作机器人加上注视和**呼吸**线索，提升了喜爱度、生命感（animacy）和意图传达 |
| | Pereira et al. | 在不同情境下评估一个响应式**共同注意（joint attention）**注视系统，注视行为提升了成人和外部观察者感知到的社会临场感，但对**儿童没有效果** |
| **手势** | de Wit et al. | 机器人用不同的象形手势（iconic gestures）能提高儿童的社交投入，但对第二语言的**词汇学习没有帮助** |
| | Roy et al. | **GPT-Driven Gestures**：一个基于大语言模型（LLM）的框架，能自主生成有表现力的机器人手势，清晰度和人相当，并提升了状态识别 |
| **多模态 / 社会角色** | Song et al. | 用言语线索、注视和外观设计"评价型"和"非评价型"两种机器人角色，影响儿童练习音乐的动机，说明社会角色设定会塑造互动 |
| | Song et al. | 比较操作者的三种临场程度（绿野仙踪式 Wizard of Oz、穿戏服、远程临场）对超市顾客行为的影响，**中等**社会临场感（穿戏服）带来最好的投入和任务表现 |

### 3.4.4 Politeness（礼貌）

> The ability to exhibit politeness refers to a robot's capacity to regulate social norms and interactional appropriateness.

表现礼貌的能力，指机器人调节社会规范和互动得体性的能力，有助于让互动在社交上得体、让用户舒适。

| 研究 | 内容 |
|---|---|
| Kato et al. | 以人类服务人员为模型，设计礼貌的接近行为：只在访客表现出互动意向时才发起互动，减少在公共场所的打扰感 |
| Jackson et al. | 研究机器人和人的性别怎样影响人对机器人**拒绝指令**的感知，发现不服从时的礼貌规范明显受性别匹配和刻板印象影响 |
| Rea et al. | 运动时**不礼貌的**机器人鼓励反而提高了参与者的努力程度和好胜心，尽管喜爱度更低，这挑战了"机器人应该始终礼貌"的假设 |

### 3.4.5 Trust（信任）

> The ability to establish and maintain trust refers to a robot's capacity to influence user confidence in its reliability and competence through its behavior during interaction.

建立和维持信任的能力，指机器人通过互动中的行为，影响用户对其可靠性和能力的信心。

| 研究 | 内容 |
|---|---|
| Natarajan & Gombolay | 对信任和服从影响最大的是机器人的**行为和被感知到的拟人化**，而不是**物理具身**；出错后道歉式的反馈能增加信任和问责感，并减少过度依赖 |
| Herse et al. | 用改编的**信任博弈（Trust Game）**测得的初始行为信任，能显著预测人–智能体协作中用户的决策和任务表现；正确的辅助能让人在困难任务上恢复过来 |

一些关于**信任修复**的研究会在 3.5.2 节"失败处理与恢复"中讨论，因为机器人引起的失败会损害用户信任，需要合适的回应或行动来恢复。

### 3.4.6 Anthropomorphism（拟人化）

拟人化指机器人唤起用户"像人"感知的表达能力。

| 研究 | 内容 |
|---|---|
| Bryant et al. | 研究机器人的性别化和职业性别角色怎样影响人的信任，结论是信任的主要驱动因素是**被感知到的职业能力**，而不是性别特征 |
| Torre et al. | 人更愿意给**被认为是遥控的**机器人让路，并且和高度拟人的机器人保持更近的距离，说明被感知到的自主性和类人程度会影响社会困境中的导航行为 |
| Hover et al. | 分析网上对不同类人程度和性别的机器人的评论，发现**高度像人**的机器人会引发更多负面的、诡异的和性化的反应，**女性外观**的尤其如此，凸显了拟人化设计的风险 |

### 3.4.7 Vitality（生命感）

表现生命感的能力，指机器人唤起用户"它是活的、有生气"的感知的能力。

| 研究 | 内容 |
|---|---|
| Iizawa & Yamanaka | **Face on a Globe**：一个非拟人的球形机器人，用平滑的几何形变和自主转向唤起生命感，同时保留人造感 |
| Löffler et al. | 证明拟动物机器人中也存在**恐怖谷效应**：喜爱度随"像动物的程度"呈 **U 形曲线**，说明人造感和生物真实感之间存在感知上的张力 |

> [!note] 小结
> **表达 = 把内部状态变成人能读懂的外部信号**，相当于 SPA 里的 Act。分三层：
> - **信息表达**：**情绪**（语调、皮肤纹理形状 = V / 频率 = A、Cozmo 动画、VAE 改手势、拥抱、触摸、矛盾情绪；评估工具是**日内瓦情绪轮**）、**认知状态**（好奇、注视、动作流畅度 → 透明度）、**社交信号**（注视 + 呼吸、共同注意、手势、LLM 生成手势、社会角色）。
> - **社会互动品质**：**礼貌**（不礼貌有时反而更能激励人）、**信任**（行为 > 具身，道歉能修复信任）。
> - **感知特征**：**拟人化**（太像人会引发诡异和负面反应）、**生命感**（非拟人形态也能有生命感；拟动物也有恐怖谷）。
> - 反复出现的结论：**效果有边界**，比如对儿童无效、能提高投入但不能提高学习效果、拟人化有风险。

## 3.5 Sustainability Capability（可持续性能力）

> The capability for sustainability refers to the robot's ability to maintain effective and reliable operation over time, including learning from human input, recovering from failures, and progressively improving performance, which is essential for long-term interaction and user trust.

**可持续性能力**指机器人长期保持有效、可靠运行的能力，包括**从人的输入中学习、从失败中恢复、逐步提升表现**，这对长期互动和用户信任都很关键。

概念上，情感 HRI 中的可持续性分为两个互补的方面：

| 方面 | 含义 | 包括 |
|---|---|---|
| **向人学习（learning from human input）** | 根据人的输入获取知识或改进行为，实现持续适应和个性化 | 人的纠正（correction）、人的偏好（preference）、更广义的人类反馈（feedback） |
| **失败处理（failure handling）** | 专指和情感 HRI 相关的能力：以支持有社交意识的互动、维持用户信任的方式检测和应对失败 | **失败检测**：通过观察人对机器人行为的反应来识别错误或意外事件；**失败回应**：包括给出解释、修复人对机器人的看法，以恢复信任 |

**Fig. 4：可持续性能力的层级组织**

```
可持续性 Sustainability
├── 向人学习 Learning from Human
│   ├── 人的纠正 Human Correction
│   ├── 人的偏好 Human Preference
│   └── 人的反馈 Human Feedback
└── 失败处理 Failure Handling
    ├── 基于情感的失败检测 Affective-based Failure Detection
    └── 失败回应 Failure Response
        ├── 解释 Explanation
        └── 修复 Repairing
```

### 3.5.1 Learning from Human Input（从人的输入中学习）

> A critical capability for robots to achieve sustainability in affective HRI is the ability to learn directly from humans.

在情感 HRI 中实现可持续性的一个关键能力，是**直接向人学习**。它让机器人能通过模仿、反馈或示范调整回应、逐步完善情感技能，促成更自然的投入。

**① 从人的纠正中学习**

| 研究 | 内容 |
|---|---|
| Bajcsy et al. | **一次只学一个（one-at-a-time）**的方法：在物理互动中，机器人推断人想纠正的是哪**一个**任务特征，比同时更新所有特征减少了意外的学习 |
| Losey et al. | 让机器人从物理人机交互中在线学习任务目标的框架，把人的物理纠正**看作有信息量的信号**用于实时更新模型，而不是当作要抵消的扰动 |

**② 学习人的偏好**

| 研究 | 内容 |
|---|---|
| Basu et al. | 改进基于比较的奖励学习：在偏好查询之外加上**特征查询**，问用户是哪个特征解释了他的偏好，从而更快、更准地获取人的意图 |
| Chen et al. | **多风格奖励蒸馏（Multi-Style Reward Distillation）**：从异质的人类示范中联合推断一个共享的任务奖励和各人的策略奖励，在模仿学习中把目标和策略偏好解耦 |
| Bobu et al. | **LESS**：一个考虑轨迹相似性的概率人类行为模型，用来更好地推断人的偏好；在连续动作空间中，预测准确度和推断稳健性都优于标准的 Boltzmann 理性模型 |

**③ 从人的反馈中学习**

| 研究 | 内容 |
|---|---|
| McQuillin et al. | 一个自适应的机器人服务员，通过实时的**隐式**（面部情感）或**显式**（语言）用户反馈学习得体的社交行为，在被感知到的社交性和站位得体性上优于固定策略 |
| Moreira et al. | **交互式深度强化学习（IDeepRL）**：用人类或人工训练者的交互反馈加速家用机器人任务的学习，比标准的自主深度强化学习显著减少学习时间和错误 |

**④ 同时利用纠正和反馈**

| 研究 | 内容 |
|---|---|
| Celemin & Kober | 一种交互式模仿学习方法，让机器人根据估计的**认知不确定性（epistemic）和偶然不确定性（aleatoric）**主动请求纠正型或评价型反馈；在自己知识不够时有策略地利用人的输入，从而处理示范歧义、提高数据效率 |
| Chisari et al. | **CEILing** 框架：把纠正型和评价型人类反馈异步地整合进一个随机策略，让机器人学会复杂的操作任务，直接从原始视觉观测训练，真实互动**不到一小时**就能学会 |

**⑤ 向非专家学习**

> To be effective in everyday settings, robots should be able to learn from non-expert users, not just experts.

要在日常环境中有效，机器人应该能向**非专家用户**学习，而不只是向专家学习。

| 研究 | 内容 |
|---|---|
| Van Waveren et al. | 基于**护盾（shield）**的策略修复方法：在机器人失败后，用非专家的纠正反馈来改进动作、替换物体或禁止不安全的行为，提高强化学习的再训练效率 |
| Schrum et al. | **MIND MELD**：一个个性化元学习框架，通过变分嵌入推断各个用户的反馈风格，用来纠正以机器人为中心的模仿学习中次优的人类标签，提升任务表现和用户信任 |

### 3.5.2 Failure Handling and Recovery（失败处理与恢复）

> In the context of affective HRI, failure handling encompasses both the identification of breakdowns via human affective cues and the management of socio-affective errors.

在情感 HRI 中，失败处理既包括通过**人的情感线索**识别故障，也包括处理**社会情感层面的错误**。本节关注那些直接影响情感回路、或者把人的情绪反应当作诊断信号的失败检测与恢复能力。所以纯技术性的容错和诊断机制，如果不直接涉及人的情感维度，不在讨论范围内。

**① 失败检测：把人的反应当作信号**

失败检测让机器人能识别任务执行、互动过程或系统状态中的故障或偏差。及时检测失败，机器人才能保持对任务和环境的连贯认识，更好地应对互动中的意外。在情感人机交互中，**人的反应可以作为识别失败的线索**。

| 研究 | 内容 |
|---|---|
| Trung et al. | 通过对人的**头部和肩部动作**分类来自动检测 HRI 中的错误。用涉及社会规范违反和技术故障的 RGB-D 互动数据，证明人的动作线索能有效指示出错情况，效果随分类器和用户熟悉度而变化 |
| Kontogiorgos et al. | 通过操纵具身形态（像人的机器人 vs 智能音箱）和失败严重程度，研究用户对机器人**对话失败**的行为反应；训练随机森林分类器并和人工标注比较，发现具身形态显著影响用于检测失败的注视和语音线索 |
| Loureiro et al. | 一个检测并分类社会规范违反和技术故障的流程，用机器人自带摄像头监测人的非言语社交信号（面部表情、眼睛注视），再结合机器人的情境日志，实现准确的错误识别 |

**② 失败回应：解释与修复**

在人机交互中，失败不仅影响任务执行，也影响人对机器人的看法。所以机器人能否恰当回应失败，对维持互动质量和正面的用户感知至关重要。

**解释（explanation）**：

| 研究 | 内容 |
|---|---|
| Kwon et al. | 一种基于优化的方法，让机器人生成**表达"做不到"的动作**，传达任务目标和失败原因，提升用户理解、对机器人的感知和协作意愿 |
| Stange & Kopp | 研究社交机器人的自我解释怎样影响人对意外或不受欢迎的有意行为的感知。基于**常识心理学（folk psychology）**的解释提高了可理解性和可接受度，其中**因果解释**最有效 |
| Das et al. | 为非专家用户生成机器人故障恢复的自然语言解释，整合最近的动作历史和环境情境；编码器–解码器模型能自主生成解释并泛化到新环境，在帮助识别故障和解决方案上和手写脚本的方法相当 |

**修复（repairing）人对机器人的看法**：

| 研究 | 内容 |
|---|---|
| Tolmeijer et al. | 提出四种与信任相关的 HRI 失败类型（设计、系统、期望、用户）的分类，以及解释、道歉、培训等相应的缓解策略 |
| Green et al. | **亲和型幽默**改善了旁观者对机器人能力的感知；而对机器人经验较少的用户更喜欢成功的机器人，说明失败回应要考虑人的感知 |
| Van der Hoorn et al. | 在协作失败中**责怪自己**的机器人（尤其当它其实没错时），比责怪人类伙伴的机器人被认为更可信、更友好、更值得以后继续合作 |

> [!note] 小结
> **可持续性 = 长期运行下去**，是 SPA 之外加的一维：
> - **向人学习**：**纠正**（一次学一个特征、把纠正当信号）、**偏好**（特征查询、多风格奖励、LESS）、**反馈**（隐式面部情感 / 显式语言、IDeepRL），以及**纠正 + 反馈**结合（按不确定性主动求助、CEILing 一小时学会），还要能**向非专家学习**（护盾修复、MIND MELD）。
> - **失败处理**：**检测**时把**人的反应当传感器**（头肩动作、注视、面部表情）；**回应**分**解释**（表达"做不到"、因果解释最有效）和**修复**（道歉、幽默、自己背锅反而更可信）。
> - 这一节和机器人学习（模仿学习、RLHF 式偏好学习）联系最紧。

## 3.6 Ethical Capability（伦理能力）

> In affective human–robot interaction, ethical capability is particularly important, as various capabilities in perception, strategy, expression, and sustainability can give rise to ethical concerns.

在情感人机交互中，伦理能力特别重要，因为感知、策略、表达和可持续性方面的各种能力都可能引发伦理问题。所以机器人需要能识别伦理问题，并调节自己的行为避免不合伦理的行动。伦理能力分为四类：**隐私保护、道德意识、避免欺骗和避免歧视**。

### 3.6.1 Privacy Protection Capability（隐私保护能力）

隐私保护能力指机器人恰当处理互动中产生的信息的能力。它通过在情感互动中根据情境管理信息边界，帮助维持用户信任。

| 研究 | 内容 |
|---|---|
| Tang et al. | **CONFIDANT**：一个社交机器人的隐私控制器，用对话元数据（情感倾向、话题、人际关系）推断隐私边界、调控信息分享，显著提升了 HRI 中被感知到的可信度和社会意识 |
| Dorafshanian et al. | 一个面向社交机器人的**差分隐私**库，让非技术用户也能安全地分享统计数据；通过风险阈值和披露影响评估，减轻社交机器人大规模收集个人数据的隐私风险 |
| Aryania et al. | 研究设计透明度怎样影响公共人机交互中的信任和数据分享行为。更高的透明度和对数据敏感性的意识让人在分享数据时更谨慎，但对信任的影响有限 |

### 3.6.2 Moral Awareness Capability（道德意识能力）

道德意识能力让机器人能识别互动中的伦理和规范层面，包括识别和道德相关的情境，并让自己的情感回应符合既定的社会期望。

| 研究 | 内容 |
|---|---|
| Jackson & Williams | 会说话的机器人对**道德上不允许的指令**提出澄清请求时，可能无意中表现出愿意违反规范，从而误传自己的意图、削弱人对这些道德规范的遵守 |
| Wen et al. | 一个以**儒家角色伦理**为基础、让机器人生成"违规回应"的计算框架；结合关系角色和情境的解释，能根据所扮演的社会角色提升信任、理解和被感知到的智能 |

### 3.6.3 Deception Avoidance Capability（避免欺骗能力）

> Deception avoidance capability refers to a robot's ability to maintain appropriate alignment between its expressed behaviors and the expectations it evokes.

避免欺骗能力，指机器人让**自己表现出的行为和它引起的期望保持恰当一致**的能力。在情感人机交互中，这有助于防止情绪表现力或社交线索导致的误解和错位的信任。

| 研究 | 内容 |
|---|---|
| Lacey & Caudwell | 认为家用机器人的"**可爱**"外观是一种**黑暗模式（dark pattern）**：它利用人的情感反应掩盖数据收集行为，削弱了用户的自主性和长期的隐私考量 |
| Winkle et al. | 对社会辅助机器人做伦理风险评估，发现拟人化行为虽然可能有欺骗性，但总体上可以接受且有效，主张**可定制的拟人化**，而不是完全回避 |
| Sharkey & Sharkey | 指出社交机器人中的欺骗可能有意也可能无意，会导致人高估机器人的能力、产生错位的信任；对个人和社会的有害影响需要伦理审查、责任划分和监管框架 |

### 3.6.4 Discriminatory Avoidance Capability（避免歧视能力）

避免歧视能力，指机器人支持在不同个人和社会群体之间**公平互动**的能力。它涉及调节情感感知和行为，以减少偏见、保证在多样的人机交互情境中公平对待。

| 研究 | 内容 |
|---|---|
| Winkle et al. | 在美国、瑞典和日本样本中证明：**女性外观**的机器人用讲道理的、打破常规的方式回应**性别歧视辱骂**，能显著提升可信度，同时不会强化有害的性别刻板印象 |
| Trainer et al. | 研究 HRI 中的**亲和偏见（affinity bias）**：参与者的信任和队友选择受虚拟形象的性别和肤色影响；即使能力是主要决定因素，被感知到的相似性仍会导致有偏的偏好 |
| Barfield | 研究社交机器人的**包容性设计**，强调照顾不同性别、文化和宗教的用户群体；借鉴社会认同理论，提出促进公平、多样和包容的人机界面指南 |
| Londoño et al. | 综述机器人学习中的**公平性**，识别偏见来源和由此导致的歧视，从技术、伦理和法律角度讨论不公平结果和减轻偏见的策略 |
| Fossa & Sucameli | 研究在对话智能体中有意嵌入**性别线索**的伦理影响，分析这类设计怎样触发社会偏见，并评估减少歧视效应的策略 |

> [!note] 小结
> **伦理 = 给前四类能力加约束**，因为每一类都可能出伦理问题：
> - **隐私**：根据对话情境推断隐私边界（CONFIDANT）、差分隐私、透明度；
> - **道德意识**：对不道德的指令连"澄清"都可能传达错误信号；儒家角色伦理框架；
> - **避免欺骗**：表现出来的行为要和引起的期望一致；"可爱"可能是一种**黑暗模式**；主张**可定制的拟人化**而不是一刀切；
> - **避免歧视**：性别和肤色带来的亲和偏见、包容性设计、学习中的公平性。
> - 和情感最相关的一点：**情绪表现力越强，越容易让人高估机器人、产生错位的信任**。

# 4 Case Study on Existing Robots（现有机器人案例研究）

> In this section, we apply the proposed taxonomy to three representative robots: Optimus, Pepper, and Erica. These robots were selected for their diversity in design and function.

本节把提出的分类体系应用到三个有代表性的机器人上：**Optimus、Pepper 和 Erica**。选它们是因为设计和功能差异大：
- **Optimus**：主要面向物理任务执行的人形机器人，能行走、操作物体、和物理环境互动；
- **Pepper**：为和人互动设计的社交机器人，能力集中在交流、情绪感知和表达行为；
- **Erica**：高度像人的仿真机器人（android），专长是对话互动和表达性交流。

这些机器人的相关信息来自 RobotsGuide 网站（robotsguide.com）上的视频。

## 4.1 Optimus

Optimus 又叫 Tesla Bot，是特斯拉开发的人形机器人，定位是通用机器人助手，目的是替人完成重复、危险或不想做的工作，特别是在工业和日常环境中。它能自主导航、避障和操作物体来辅助完成物理任务。

## 4.2 Pepper

Pepper 是软银机器人公司（SoftBank Robotics）开发的人形机器人，为社交互动而设计。它能通过语音、视觉和触觉感知环境、和人互动，能识别基本情绪，并通过表达行为吸引用户。Pepper 广泛用于零售、公共场所和研究中。

## 4.3 Erica

Erica 是大阪大学、京都大学和国际电气通信基础技术研究所（ATR）的研究者开发的高度逼真的人形仿真机器人，作为研究人机交互的平台。它被设计来支持和人的自然对话：能理解口语，用合成的像人的声音说话，并展示各种面部表情和头部动作来支持社交互动。它被广泛用于研究对话互动和社交机器人的类人临场感。

## 对比：用分类体系分析三个机器人（笔记整理，原文 4.1–4.3 分别叙述）

| 维度 | Optimus | Pepper | Erica |
|---|---|---|---|
| **感知** | 识别人的意图，包括攻击意图和想要某个物体（**认知状态识别**） | 能检测到人不开心（**情绪识别**） | 能识别人的**笑声**（**情绪识别**） |
| **策略** | 对方想要某个物体时把它递过去（**适应人的心理状态**） | 安慰不开心的人（**心理助手能力**）；有人对它粗暴时，能给出合适的反馈安抚对方 | 检测到用户笑后跟着一起笑，表现出社交回应性（**情境感知与适应**） |
| **表达** | 回应人的打招呼（**礼貌**） | 通过眼睛颜色、语调和身体姿态的变化传达信息和情绪（**情绪表达**）；用点头等手势表示认同（**社交信号表达**）；不执行任务时也保持持续、活泼的存在感，而不是静止不动（**生命感**）；被粗暴对待时的安抚回应体现了**礼貌**，也有助于建立**信任** | 高度像人的脸能通过丰富的面部表情和注视传达情绪信息（**情绪表达**、**认知状态表达**）；极其像人的外观体现了很高的**拟人化** |
| **可持续性** | — | — | — |
| **伦理** | — | — | — |

（可持续性和伦理两栏在原文的案例分析中都没有涉及。）

> [!note] 小结
> 案例研究用分类体系当"检查清单"，分析三种定位不同的机器人：
> - **Optimus**（任务型）：情感能力最少，只有意图识别、递东西、打招呼；
> - **Pepper**（社交型）：覆盖最广，感知、策略、表达各个子项都有；
> - **Erica**（拟真型）：强项是**表达**和**拟人化**。
>
> 局限很明显：信息全部来自**宣传视频**，不是系统测试；**可持续性和伦理两维在三个机器人上都没有分析**。这正说明这两维在现有机器人上最难观察、最缺失。

# 5 Conclusions（结论）

> We propose a unified capability taxonomy for autonomous robots in affective human–robot interaction (HRI) to address the dispersion of existing research. The taxonomy is structured around five dimensions—perception, strategy, expression, sustainability, and ethics.

为了解决已有研究分散的问题，作者为情感人机交互中的自主机器人提出了一个统一的能力分类体系，围绕五个维度构建：**感知、策略、表达、可持续性和伦理**。这个分类体系把各种研究组织进一个连贯的框架，为机器人设计和未来研究提供系统的参考。总体上，它的目标是支持开发能和人进行自然、可信、有意义的互动的、有社交能力的机器人。

**局限与未来工作**

> While the current work presents a capability taxonomy that organizes key functions for affective HRI, it remains a conceptual framework.

虽然本文提出的能力分类体系整理了情感 HRI 的关键功能，但它**仍然只是一个概念框架**。未来工作可以：

1. **变成评估标准**：把分类体系扩展成完整的评估标准，不只定义相关类别，还规定每一类的表现评估准则；
2. **变成实现框架**：把这个原则层面的分类体系扩展成更细粒度、面向实现的系统设计和基准测试（benchmarking）框架，从描述性框架走向可操作的评估和设计支持；
3. **刻画能力之间的关系**：引入形式化模型（比如图、层级结构或依赖结构），刻画各项能力之间的相互作用、约束和依赖，为集成系统设计提供更系统的指导；
4. **做真实系统**：长期来看，在这个分类体系的指导下开发真实的机器人系统，并在不同应用领域做实验验证和评估，推动情感 HRI 机器人系统的演进和迭代改进。

> [!note] 小结
> 一句话：本文把情感 HRI 所需的能力按 **SPA 加两维**组织成 **感知 / 策略 / 表达 / 可持续性 / 伦理** 五类、约 20 个子能力，每个子能力配 2–7 篇代表性工作，最后用 Optimus、Pepper、Erica 做演示。
>
> 它的价值是一张**地图和检查清单**；局限是**纯概念框架**：没有评估标准，没有能力之间的依赖关系，案例分析只看宣传视频，每类只列代表作、不追求完整覆盖。
