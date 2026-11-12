# 行业语料目录与实际收集范围

本版实际收集三套公开数据，原始带标注记录合计 **87,596** 条，整理后 **87,159** 条。CrossWOZ 的计数单位为带标注用户轮，不是会话数量。BANKING77 和 CLINC150 为单轮输入。未把关联不同标签体系的数据混成一个训练任务。

| 数据 | 语言 | 扫描记录 | 保留记录 | 隔离记录 | 数据许可 |
|---|---|---:|---:|---:|---|
| banking77 | en | 13,083 | 13,071 | 12 | CC-BY-4.0 |
| clinc150 | en | 23,700 | 23,691 | 9 | CC-BY-3.0 |
| crosswoz | zh | 50,813 | 50,397 | 416 | CC-BY-4.0 |


中文覆盖旅游、酒店、餐饮、地铁、出租车；英文覆盖银行、支付及 CLINC 的多个生活与业务领域。电商、医疗、中文金融、教育等另列官方资源入口，**不声称已经收集所有行业**。五行业、68 场景的中文/英文合成示例另见 examples/industry-seeds-zh.jsonl 和 industry-seeds-en.jsonl，明确标记 synthetic=true，不计入上述公开语料。

## 原始来源

- [BANKING77 / PolyAI](https://github.com/PolyAI-LDN/task-specific-datasets)：77 类银行意图，CC BY 4.0。
- [CLINC150 / OOS](https://github.com/clinc/oos-eval)：保留意图、领域外样本与划分，CC BY 3.0。
- [CrossWOZ 的 ConvLab-2 分发版本](https://github.com/thu-coai/ConvLab-2)：中文跨领域多轮对话，README 明确数据 CC BY 4.0。代码 LICENSE 为 Apache-2.0，两者分开保存。

固定版本、逐文件 SHA-256、处理计数见 [manifest](corpus-manifest.json)。本项目不是原始数据作者。

## 官方资源索引（未再分发）

| 行业 | 官方入口 | 适用方向 | 当前状态 |
|---|---|---|---|
| 中文电商 | [JDDC 2.1](https://github.com/hrlinlp/jddc2.1) | 多模态客服 | 官方要求申请 |
| 中文医疗 | [CBLUE](https://github.com/CBLUEbenchmark/CBLUE) | 医疗实体、意图、关系 | 逐任务获取并核对数据条款 |
| 中文金融 | [BBT-FinCUGE](https://github.com/supersymmetry-technologies/BBT-FinCUGE-Applications) | 金融 NLP 基准 | 逐数据集核对许可 |
| 中文教育 | [EduNLP](https://github.com/bigdata-ustc/EduNLP) | 试题表示与分析 | 资源工具入口，不等于客服语料 |
| 通用中文 | [CLUENER2020](https://github.com/CLUEbenchmark/CLUENER2020) | 实体识别 | 需跨度转换及数据条款确认 |

完整语料包在 [ModelScope 的 corpora 目录](https://www.modelscope.cn/datasets/zhouyang55666/customer_json/files)。raw/ 保留上游原文、README 和来源清单；prepared/ 是转换结果；licenses/ 是独立归属与许可；manifest.json 与 SHA256SUMS.txt 可复核。数据下载完成后无需联网使用。

工具只自动验证格式、标签冲突、文本证据与确定性泄漏；这些数据没有经过本项目逐条人工重新标注。中文语料不自动翻译，行业类别也不自动映射到生成器内置场景。详见 [中国用户使用说明](中国用户使用说明.md)。
