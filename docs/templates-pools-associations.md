# 自定义输入模板、占位词库、输出 key 与多对一关联

## 直接使用物流示例

1. 选择电商、查询物流、意图识别任务。
2. “输入模板”加载 `examples/logistics-templates.json` 并启用。可改写 text、移动 `${快递}`，或调整 segments 的位置；shuffle=true 在每条记录中打乱片段顺序。
3. “输入输出关联”加载 `examples/association-rules.json` 并启用。
4. “自定义数据格式”选择 custom，加载 `examples/format-logistics.json`。键名可以自行改为中文、英文或其他固定字符串，包括嵌套 key。
5. 选择语料 zh / en、标签 follow，预览再生成。英文界面可独立切换。

英文示例结果：

```json
{"text":"Track my shipment with tracking number DEMO-123456789012.","labels":{"business":"logistics","action":"track shipment","tracking":"DEMO-123456789012"},"custom_labels":{"意图名称":"track shipment","自定义标签编码":"LOGISTICS_QUERY"}}
```

这里 `text`、`labels`、`business`、`action`、`tracking` 及两个中文 key 都是用户输出模板定义的，可以任意命名。输入值来自占位词库，输出值来自中英文关联规则，并非固定只能使用系统的英文枚举。切换到中文时使用相同 key，值改为中文输入与“查询物流”。

## 输入模板及位置

按 scene ID 和 zh/en 组织模板数组。每个条目二选一：`text` 单段文本，或 `segments` 文本数组。`shuffle` 只打乱片段，不自动改写意义；`joiner` 定义连接符。`${变量名}` 可以放到文本任意位置，变量名支持汉字。一个变量重复出现时取值一致。

`variables` 每个条目可指定 `slot`，例如 tracking_no；没有独立 values/templates 时使用当前场景词池。也可指定自己的 values，或 templates + variables 组合池。未映射 slot 的变量只是表达用词，如“请／麻烦”，不会被错误写入槽位标签。占位词与变量必须对应，不能把不存在于原文的字段写成标签。

```json
{"text":"${礼貌}查一下运单号${编号}","variables":{"礼貌":{"values":["请","麻烦","能否"]},"编号":{"slot":"tracking_no","templates":["DEMO-${id}"],"variables":{"id":{"digits":12}}}}}
```

输入模板目前支持 intent / slots / domain，并绑定现有场景。DST、澄清和工具任务继续使用各自校验流程。模板内的业务含义由作者负责；槽位必须属于绑定场景，重复映射、未声明变量和无原文证据会报错。换货商品类别与商品尺码仍需兼容。

## 多个输入值 → 同一输出值

关联配置的 rules 每条有 scene、input、output、match。input 是两种语言的关键词数组；默认 any 表示任一个词命中，all 表示该语言所有词都需要出现。多个同义词放在同一数组，或多条规则绑定同一 scene 并指定相同 output，均支持多对一。

```json
{"rules":[{"scene":"ecom:logistics:QUERY","input":{"zh":["快递号","运单号","物流单号"],"en":["tracking number","shipment number","parcel number"]},"output":{"zh":{"intent":"查询物流","category":"查询物流","label_code":"物流查询001"},"en":{"intent":"track shipment","category":"track shipment","label_code":"SHIPMENT_QUERY_001"}}}]}
```

output 的键和值可以自行定义。domain/intent 若存在会替换标准答案对应值；其他字段通过 `${associated.category}` / `${associated.label_code}` 等路径引用，或 `${associated}` 整个对象导出。输出模板可以将 category 重命名为 `我的分类`。不会覆盖输入文本等内部变量。

规则命中的 scene 必须与原始标签场景一致；跨场景命中、同一输入命中不同输出值时过滤并记录 `association_conflict`。未命中的输入保留普通标签；如需全体数据都使用自定义词汇，请让每个输入模板都有相应关键词。canonical 输出关闭别名映射并保留原业务编码。关联不等于看到“快递号”就一定理解真实意图，规则应覆盖你要表达的实际查询场景。

导入已标注语料时可以按这些显式别名反向恢复原场景编码，但仍要求输入和答案；没有答案的文本不会自动生成标签。自定义别名、模板和关联配置也应保留在实验版本记录中。

## 持续扩展词池

在“词池与多样性”导入 `examples/entity-pools.json`。全局 pools 按语言定义槽位词库；scenes 下的配置优先于全局池。没有自定义词池的字段可使用内置扩展组合。编号/日期等已有规则生成，普通实体使用词表与受控组合。

每个条目支持 values 字符串数组、templates 字符串数组、variables 组合变量。mode=replace 总使用自定义池，merge 按 probability（默认 0.75）与原池混合。变量可为字符串数组、`{"digits":12}`、`{"hex":16}`，或 `{"min":0,"max":9999,"width":4}`。所有模板只替换 `${变量}`，不执行代码、表达式或联网。

字符串/模板用打乱轮换抽样，组合变量按需采样。16 位十六进制编码有 2^64 种可能，笛卡尔积不会展开存储；重复输入仍被去重。词表条目没有人为数量上限，但加载需要内存；词池无法在物理意义上无限，编号随机也不能替代语言表达多样性。

自定义场景词库和单变量独立词库可以组合使用。商品带尺码或 product2 换货类别时保留原约束池，特定维修/儿童商品话术保留相应类别；不会为了扩池而放松一致性校验。自定义词表应审核拼写、语言与业务含义。

```powershell
python dataset_gen_core.py --dst output/pools.jsonl --mb 1 --industries finance --tasks intent --language en --entity-pools examples/entity-pools.json
```

固定整数种子、日期、词库、输入模板、关联、输出格式及来源划分索引，并关闭历史去重，才能复现同一数据。质量报告记录配置文件校验值、扩池采样次数、模板数量、命中/冲突及输出语言；没有声称真实模型效果。
