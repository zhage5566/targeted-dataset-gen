# 语言、标签值与训练／测试来源隔离

界面语言（中文 / English）、语料语言（zh / en）和标签值语言相互独立。英文生成使用独立英语句式和实体词池，覆盖 68 个业务场景及七类任务；没有进行机器翻译。格式一致性已验证，真实自然度和下游准确率尚未做人工/模型基准评估。

标签值选项：`follow` 跟随语料语言，`zh` 中文，`en` 英文，`canonical` 原有业务编码。GUI 和 CLI 默认 follow；Python API 为兼容原代码默认 canonical，需要显式传 `label_language="follow"`。中文订单取消示例为 domain=订单、intent=取消订单；英文是 domain=order、intent=cancel my order；canonical 保留 order/CANCEL。关联规则可进一步自定义这些词汇。

标准 JSON 的 key 保持稳定（domain / intent / slots / order_id 等）。导入实体值按原文保留，生成实体按语料语言选择词池。编号、日期、金额、工具 API 和协议枚举不作翻译。切换标签值语言不会自动翻译用户原文；完整英语数据应使用英文种子。自定义输出格式的 key 由你自己决定。

## 来源隔离

默认 train，测试侧比例 20%、划分随机种子 42。按显式 group_id 或归一化输入结构分组，将相同来源的实体变体放在同一侧，所有后续扩增继承种子分组。原始文档、用户或对话关联跨多种表达时，建议提供 group_id。系统和任务名不参与结构指纹；已标注槽位、内置实体、编号和数字被归一化。

划分按 SHA-256 和比例确定，同一个索引中已经分配的组不会因为后来修改比例或划分种子而搬到另一侧。默认索引位于当前用户 LOCALAPPDATA/EcomDatasetGen/seed-splits-v1.sqlite3，只保存指纹和归属。不同实验请用不同 `--seed-registry` 路径；需要重建划分时创建新索引，并一并重新生成训练和测试数据。

```powershell
# 两次运行使用完全相同的原始种子与同一个划分索引
python dataset_gen_core.py --dst output/train.jsonl --mb 1 --industries finance --scenarios finance:bank_card:REPORT_LOSS --tasks intent --seed-corpus examples/seed-partition-demo.jsonl --seed-split train --seed-registry output/splits.sqlite3 --seed 42
python dataset_gen_core.py --dst output/test.jsonl --mb 1 --industries finance --scenarios finance:bank_card:REPORT_LOSS --tasks intent --seed-corpus examples/seed-partition-demo.jsonl --seed-split test --seed-registry output/splits.sqlite3 --seed 43
```

train 模式允许通过内置或自定义模板补足，但检查已有另一侧结构指纹。test 模式只使用测试侧种子和受控槽位替换；不使用内置/自定义模板补足。有限来源、去重及结构上限会导致提前保存小于目标的文件，见质量报告 `seed_source_exhausted`。`all` 关闭来源隔离，适合格式演示，不适合声称独立评测。

比例针对来源组，不能保证按样本数恰好达到 20%；小语料可能没有某一侧可用种子。质量报告记录来源组、配置、筛选数量和实际写入指纹。结构指纹不是语义相似模型，无法保证所有近义句、跨语言翻译或相关文档都被自动识别，显式来源分组更可靠。

扩增测试数据适合规则回归、鲁棒性和受控变量测试。即使完成来源隔离，它仍是合成评测集，不替代独立采集和人工审核的真实测试集。
