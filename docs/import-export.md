# 导入语料种子与自定义数据格式

v2.1 支持已有输入与答案/标签的监督语料。语料种子是训练样本，不同于控制随机性的整数种子。功能完全在本地运行，不发送文件到外部服务，不执行文件中的代码或指令。

## 图形界面

1. 在“行业与训练方向”选择行业、业务功能和任务。
2. 在“语料种子导入”选择 JSONL、JSON 或 CSV，勾选“使用语料种子”。文件需要 UTF-8，兼容 UTF-8 BOM。
3. 映射“用户输入”和“答案/标签”字段，或者映射 `messages` 列表。支持 `meta.scene` 等对象点路径，不支持数组下标或表达式。
4. 指定默认训练任务/场景，或使用记录内的 `task`/`scene`。记录内标注优先。联合意图标签可自动匹配业务场景；其他任务无场景标注时，需要指定默认场景，或只选择一个业务功能。
5. 点击“预检种子”，查看前 200 条中的合格数量和过滤原因。正式生成会重新读取全文件。
6. 设置种子字节预算上限和是否扩增，再到“自定义数据格式”选择记录结构与文件格式。可预览记录，或加载/保存 JSON 模板。
7. 点击“开始生成”。质量报告会记录种子文件校验值、过滤原因、原句/扩增数量、实际字节比例及导出配置。

每条种子都经过任务、标签、场景与槽位原文证据等检查。场景 ID 是现有目录中的业务 ID，见 `python dataset_gen_core.py --list-scenes`。本版本不自动猜测未标注语料，也不导入目录外的自定义行业/标签。

## 支持的输入

**输入与结构化答案**：

```json
{"question":"请挂失卡尾号1234","answer":{"domain":"bank_card","intent":"REPORT_LOSS","slots":{"card_no":"卡尾号1234"}},"meta":{"scene":"finance:bank_card:REPORT_LOSS"}}
```

将用户输入映射为 `question`，答案映射为 `answer`，场景映射为 `meta.scene`。可直接使用 [示例语料](../examples/seed-corpus.jsonl) 与 [导入配置](../examples/seed-import-config.json)。答案既可为 JSON 对象，也可为 JSON 字符串。

**单独分类标签**：指定任务为 `intent`，提供场景和字符串意图标签，例如 `REPORT_LOSS`。生成器按场景补全 domain，使用可选 slots 字段作为槽位；没有 slots 时为空对象。领域分类 `domain` 接受字符串领域标签；指定 `slots` 任务时，答案可为槽位字典或 `{"slots": {...}}`。

CSV 示例见 [seed-labels.csv](../examples/seed-labels.csv)，其导入配置见 [seed-label-config.json](../examples/seed-label-config.json)。包含逗号、引号或换行的 CSV 字段需按标准 CSV 规则引用。

**messages 数据**：接受 `role/content` 消息列表。如果包含 system，必须与该任务的标准提示词匹配；没有 system 时补上标准提示词。未知 system 会被拒绝，避免丢失重要上下文。多轮 DST 和工具样本需符合本项目原有格式及流程校验；可原句混入，不做自动槽位替换。导出为 Alpaca 或 ShareGPT 后，不保证可直接逆向导入，导入时请保留原始 messages 或输入/答案字段。

JSON 文件接受单个对象、对象数组或 `{"data": [...]}`；单个 JSON 文件最多 64 MiB，大文件建议使用流式 JSONL。JSONL 支持逐行解析并报告损坏行。CSV 使用表头作为字段名。JSON/CSV 嵌套槽位或 messages 字段也可用 JSON 字符串。

## 扩增、预算与去重

原句只混入一次；之后可对单轮 `intent` / `slots` 的明确槽位值做替换，从所选业务的值池采样，并同步更新标签，再执行相同校验和去重。该功能保持种子的表达框架，不自动改写其业务语义。重复或相互包含的槽位值不扩增，避免错误替换；无槽位、DST、澄清与工具样本只使用原句。

预算上限按每项任务的目标字节预算计算，默认 30%；完整记录会造成少量边界误差。上限不是最低保证，有限种子、历史去重和结构上限都可能降低实际比例。训练模式下，种子不足时可由内置或自定义输入模板补足；test 模式仅使用测试侧种子，数量或新组合不足时提前保存，报告 seed_source_exhausted。不会为达到文件大小而跨侧取种子。

相同任务的完整规范化输入只保留一次；相同输入有不同答案时过滤后出现的记录并报告。跨批次去重也适用于种子与扩增样本。导入默认保留最多 10,000 条合格种子，用固定随机源做蓄水池采样；Python/CLI 配置 `max_records` 可调整至 100,000。输入去重指纹仍随有效输入数量增长。

固定整数种子、参考日期、导入文件内容、配置和导出模板，并关闭历史去重，可复现输出。规则校验不等同于人工语义审核；请先抽查自己导入的标注质量。质量报告记录路径/字段配置等本地运行信息，分享报告前请自行检查是否含私人文件名。

## 输出格式

| 记录结构 | 内容 |
|---|---|
| messages | 保持原版 `{"messages": [...]}` |
| alpaca | instruction 为 system，input 为完整输入历史，output 为末轮答案 |
| sharegpt | conversations 数组，角色转换为 system/human/gpt |
| custom | 按安全 JSON 模板替换变量，自定义字段名、层级和固定值 |

上述结构都可导出为 JSONL、JSON 数组或 CSV。CSV 顶层字段为列，嵌套对象/数组为 JSON 字符串。JSONL 每行一条记录；JSON/CSV 使用标准解析器读取，不能用普通按行计数替代样本数。停止时会保存完整 JSON 数组或 CSV，异常不会覆盖既有目标。

```json
{
  "question": "${input}",
  "answer": "${answer_json}",
  "task": "${task}",
  "messages": "${messages}"
}
```

模板是 JSON 数据，不能使用 Python、Jinja 或 shell 表达式。字段名必须固定，未知变量会报错。单独的 `${messages}`、`${slots}` 等保持对象/数组类型；`"任务=${task}"` 这样的混合文字保留字符串类型。

| 变量 | 值 |
|---|---|
| messages / history | 完整消息列表 / 不含 system 和最终答案的输入历史 |
| system / input / output | 标准提示词 / 单轮用户文本或带角色的多轮历史 / 末轮答案字符串 |
| answer_json | 解析后的 JSON 答案，非 JSON 答案保持字符串 |
| task / scene / industry | 任务 ID / 场景 ID / 行业 ID |
| domain / intent / slots | 按标签值语言和关联规则导出的业务标签 / 意图 / 槽位对象 |
| language / seed_group / seed_split | 语料语言 / 来源分组指纹 / train 或 test；未划分为空 |
| associated | 当前输入命中的自定义关联输出词汇对象 |

标签值可按 follow / zh / en / canonical 配置；DST belief 对象键名保持原生成格式，状态实体值保持原文。电商工具返回继续作为带 `工具返回: ` 前缀的 user 消息；导出结构转换不等于原生工具协议转换。工具流程的 scene 可能是流程标识，domain/intent 不存在时为空。

## 命令行

```powershell
# 导入示例语料，输出 Alpaca JSONL
python dataset_gen_core.py --dst output/seed_alpaca.jsonl --mb 1 --industries finance --scenarios finance:bank_card:REPORT_LOSS --tasks intent --seed-corpus examples/seed-corpus.jsonl --seed-config examples/seed-import-config.json --seed-split all --record-format alpaca --seed 42 --reference-date 2026-10-09

# 自定义记录结构，输出 JSON 数组
python dataset_gen_core.py --dst output/custom.json --mb 1 --industries finance --scenarios finance:bank_card:REPORT_LOSS --tasks intent --seed-corpus examples/seed-corpus.jsonl --seed-config examples/seed-import-config.json --seed-split all --record-format custom --format-schema examples/format-template.json

# CSV 标签导入；关闭扩增，只混入原句并由内置生成器补足
python dataset_gen_core.py --dst output/labels.csv --mb 1 --industries finance --scenarios finance:bank_card:REPORT_LOSS --tasks intent --seed-corpus examples/seed-labels.csv --seed-config examples/seed-label-config.json --seed-split all --no-seed-augment --record-format alpaca
```

`--seed-corpus` 可重复指定多个文件；`--seed-share` 为 0 到 1 之间的上限比例（不含 0）。文件格式默认由扩展名推断，也可用 `--file-format` 显式指定。自定义格式需要 `--record-format custom` 和 `--format-schema`。


上述最小导入演示使用 `--seed-split all`，仅便于查看格式，不启用来源隔离。实验数据应使用 train/test 模式和同一个划分索引，详见 [语言与隔离](languages-and-splits.md)。字段映射中的 `group` 默认指向 `group_id`，可以映射自己的原始文档/对话/用户分组 ID。

输出模板支持安全点路径，如 `${slots.tracking_no}`、`${answer_json.slots.order_id}`、`${associated.category}`、`${history.0.content}`，仅遍历对象键和列表下标，不执行表达式；缺失路径返回 null。可据此重命名任意层级的输出 key。导入自定义标签时，显式关联规则可反向识别配置中的别名；仍必须提供答案/标签，不会自动标注无标签文本。
