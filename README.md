# Targeted Dataset Generator / 定向数据集生成器

面向中英文任务型对话的本地合成数据工具。通过界面选择**行业 → 业务功能 → 训练任务**，生成 UTF-8 数据集和质量报告。支持 Windows 桌面程序与 Python 命令行，不调用外部大模型或网络服务。

**v2.1 新增：语料种子导入与扩增、训练／测试来源隔离、中英文界面及输入输出、可扩展词池、自定义输入模板与占位词位置、多对一输入输出关联、自定义输出字段和标签词汇。**支持 messages / Alpaca / ShareGPT / custom 结构及 JSONL / JSON / CSV。

使用说明：[语料导入与格式](docs/import-export.md) · [语言与种子隔离](docs/languages-and-splits.md) · [词库、模板和多对一关联](docs/templates-pools-associations.md)。

Local bilingual dataset generation with supervised seeds, stable train/test lineage, expandable entity pools, editable utterances, many-to-one lexical associations and custom output keys. No network or model API is required.

Windows 可执行程序和完整便携包见 [Releases](https://github.com/zhage5566/targeted-dataset-gen/releases)。源码中的构建脚本可重新打包程序。

## 快速开始

Windows 用户双击 `TargetedDatasetGen.exe`，无需安装 Python。源码用户使用 Python 3.10+：

```powershell
python app.py
```

1. 在“行业与训练方向”勾选行业。
2. 业务功能列表默认全选；点击“清空选择”，再用 Ctrl/Shift 选择需要的功能。
3. 勾选训练任务，例如只勾“独立槽位提取”；任务权重决定实际输出字节占比。
4. 在“输出与质量设置”指定输出文件和目标大小（JSONL / JSON / CSV），点击“开始生成”。
5. 通过“查看质量报告”检查任务比例、去重数量、场景覆盖和结构重复情况。

界面顶部可独立选择界面语言、语料语言和标签值语言。默认 `follow` 跟随语料语言；`canonical` 保留原始枚举编码。标准结构的键名固定，自定义格式可以自由命名键。已有实体值不自动翻译，英文模式应导入英文种子。

需要使用自己的样本时，打开“语料种子导入”，选择文件并配置输入/答案字段；在“自定义数据格式”选择导出结构，或编辑/加载 JSON 模板。原有整数随机种子仍用于复现，不同于语料种子。

示例：只需要金融银行卡挂失的槽位数据时，勾选“金融”，只选“办理银行卡挂失”，只勾“独立槽位提取”。输出只包含该方向。

停止按钮会保存完整的已生成样本和报告。关闭生成中的窗口也会先停止并保存。输出按完整记录写入，大小可能略超过目标；单位 MiB = 1,048,576 字节。

## 支持范围

| 行业 | 业务示例 |
|---|---|
| 电商 | 订单查询/取消/修改、物流、退换修、退款、发票、优惠券、商品、会员、支付、投诉、账户 |
| 金融 | 账户余额/流水、银行卡挂失/状态、转账进度/限额、还款计划、存款到期、理财赎回、保单/理赔查询 |
| 出行与酒店 | 机票查询/退票、火车票查询/改签、酒店房型/取消预订、网约车订单/投诉 |
| 通信服务 | 套餐查询/变更、话费账单/扣费核查、宽带报修/安装、号码挂失 |
| 教育培训 | 课程内容/价格、报名状态/取消、课表/调课、学习账户登录异常 |

金融采用虚构机构、产品和脱敏账号；这些样本用于信息识别与流程表达，不包含投资建议或真实机构政策。

| 任务 ID | 用途 | Assistant 输出 |
|---|---|---|
| `intent` | 联合意图识别与槽位抽取 | `{"domain":"...","intent":"...","slots":{...}}` |
| `slots` | 独立槽位抽取 | `{"slots":{...}}` |
| `domain` | 业务领域分类 | `{"domain":"..."}` |
| `dst_user` | 多轮用户状态跟踪 | `[{"domain":"...","slot":"...","value":"...","active":true}]` |
| `dst_belief` | 多轮当前有效状态 | `{"领域-槽位":"值"}` |
| `clarify` | 缺失信息澄清 | 只追问尚未提供的字段 |
| `ecom` | 电商售后工具决策 | ReAct 工具调用或客服回复 |

前六项适用于所有行业。`ecom` 仅适用于电商退货、换货、仅退款、售后进度；选择其他业务时界面自动禁用。命令行自动将不适用的 `ecom` 权重归零，其余任务重新归一化；如果没有可用任务则报错。

## 自定义输入、输出及多对一关联

在“输入模板”加载 [物流模板](examples/logistics-templates.json)，修改 `${快递}` / `${tracking}` 的位置和词库；`segments + shuffle` 可随机重排片段。在“输入输出关联”加载 [关联规则](examples/association-rules.json)，把多个输入词绑定到同一业务场景，并定义两种语言的输出值。在“自定义数据格式”加载 [输出模板](examples/format-logistics.json)，自由修改顶层和嵌套 key。

例如，`快递号 / 运单号 / 物流单号 → 查询物流`，`tracking number / shipment number / parcel number → track shipment`。输出可自行命名为 `意图名称`、`action` 或其他 key；`${associated.category}` 读取关联值，`${slots.tracking_no}` 读取已标注实体。缺失字段返回 JSON null。

```powershell
python dataset_gen_core.py --dst output/logistics.jsonl --mb 1 --industries ecom --scenarios ecom:logistics:QUERY --tasks intent --language en --label-language follow --utterance-templates examples/logistics-templates.json --association-rules examples/association-rules.json --record-format custom --format-schema examples/format-logistics.json
```

该命令生成英文输入和英文标签值；改为 `--language zh` 即使用中文输入/输出词汇。JSON key 按同一输出模板保持不变；需要不同 key 时直接编辑模板。自定义输出词汇属于导出层，内部仍使用可校验的业务场景和编码。

## 随机性与质量控制

- **每次自动随机**：种子留空时使用系统熵创建 64 位种子；实际种子写入日志和报告。
- **可复现**：指定相同种子、参考日期、任务/场景/权重/结构上限，并关闭历史去重，数据内容可复现。日期留空时使用运行当天。
- **局部随机源**：每次生成使用独立 `random.Random`，不修改 Python 全局随机状态。
- **可扩展词池**：默认加入商品、品牌、机构、课程等组合池；可导入任意规模的词表（受可用内存限制），通过语言/场景分组及安全组合模板扩展。按需采样，不展开笛卡尔积；词表/模板打乱轮换。编号组合空间很大，但词汇多样性不等于语义多样性。
- **种子隔离**：默认使用训练侧种子；测试模式仅用测试侧种子及其扩增，不调用内置或自定义输入模板补足。稳定分组索引保存指纹和归属。
- **场景覆盖**：按场景随机轮换，组合请求句式、信息顺序、缺失字段、多轮更正/撤回和工具流程节点。
- **输入去重与冲突检测**：在相同任务内比较完整模型输入，规范化大小写、空白、部分标点和称呼。相同输入只保留一次；同输入不同答案被拒绝。
- **结构重复上限**：将动态槽位、编号和数字归一化后，对相同词汇结构设上限。默认 200，可按需求降低。该功能是规则指纹控制，并非语义向量去重；不同措辞仍可能表达相同含义。
- **逐条验证**：检查消息角色、JSON、标签词表、槽位原文证据、产品尺码一致性、最新 DST 值、撤回状态和澄清缺失项。
- **工具流程约束**：订单号必须来自用户；售后创建必须先查订单和政策、通过身份核验、提供所需凭证，且不能重复创建。查询失败不声称成功；退款后的订单不能再次获得退款资格。
- **字节配比**：按照各任务实际写入字节数调度，避免长对话挤占短任务。小文件与最后一条样本会有正常比例误差。
- **文件保护**：先写临时文件，成功或主动停止后替换目标。异常保留 `.partial` 和 `.failed-report.json`，既有目标文件保持原样，历史索引回滚本次记录。

输出数据仍是模板与组合规则驱动的合成数据。格式与一致性通过不代表真实业务效果；用于正式训练前应抽查，并以真实验证集评估。售后 `synthetic-v2` 是模拟工具政策，不能作为真实商家的售后规定。

### 跨批次去重

界面默认开启，历史索引位于 `%LOCALAPPDATA%\EcomDatasetGen\history-v2.sqlite3`。历史索引存储任务名和输入/标签的 SHA-256 指纹，不保存原文。记录在成功或主动停止后提交。

开启后，即使重复使用种子，也会跳过之前生成过的输入，因此输出不会与上一批完全相同。若需要复现或独立实验，请关闭，或在命令行使用另一个 `--history` 路径。

SQLite 索引减少大文件去重时的内存占用；结构计数仍使用内存。非常小的业务范围与严格上限可能没有足够组合填满大目标：连续 20,000 次无法获得新样本时停止并报告错误，请减少目标大小、扩大业务范围或调整上限，不会悄悄放宽质量限制。

### 原始样本混入

默认关闭。开启后只读取与电商售后系统提示词匹配、通过同一格式与工具流程验证且符合所选方向的样本，并执行输入去重。最多占电商 Agent 字节预算的 20%。其他行业不混入电商原始样本。原始行不会作为代码或指令执行。

## 命令行

```powershell
# 列出全部业务场景 ID
python dataset_gen_core.py --list-scenes

# 五个行业，默认任务配比，自动随机种子
python dataset_gen_core.py --dst output/all.jsonl --mb 100 --industries ecom,finance,travel,telecom,education

# 金融银行卡挂失，单独抽取槽位；固定种子与参考日期可复现
python dataset_gen_core.py --dst output/card_slots.jsonl --mb 10 --industries finance --scenarios finance:bank_card:REPORT_LOSS --tasks slots --seed 42 --reference-date 2026-10-09

# 电商退货，意图/状态跟踪/售后决策，开启跨批次去重
python dataset_gen_core.py --dst output/returns.jsonl --mb 100 --industries ecom --scenarios ecom:after_sales:APPLY_RETURN --tasks intent,dst_user,ecom --shape-limit 100 --history output/history.sqlite3
```

`--tasks` 指定的任务采用相等字节权重；不指定时使用默认配比。自定义权重可通过 GUI 或 Python API 传入。

```python
import dataset_gen_core as core

result = core.main(
    dst="output/finance.jsonl", target_bytes=10 * 1048576,
    industries=["finance"], scenario_ids=["finance:transfer:QUERY_PROGRESS"],
    weights_override={task: (70 if task == "intent" else 30 if task == "slots" else 0)
                      for task in core.TASKS},
    seed=42, reference_date="2026-10-09", shape_limit=100,
)
print(result["report_path"])
```

## 数据格式

每行只有 `messages`，没有夹带统计字段；使用常见聊天训练格式：

```json
{"messages":[{"role":"system","content":"任务说明"},{"role":"user","content":"示例银行A的银行卡卡尾号1234丢了，我要挂失"},{"role":"assistant","content":"{\"slots\":{\"bank\":\"示例银行A\",\"card_no\":\"卡尾号1234\"}}"}]}
```

为了兼容原版，Agent 的工具返回保留 `user` 角色及 `工具返回: ` 前缀；真实接口需要 `tool` 角色时，请自行转换并调整系统提示词。质量报告是相邻的 `<文件名>.quality.json`，包含实际种子/日期、行业/场景、行数/字节、配比、拒绝原因和结构统计。

## 开发与贡献

运行时仅使用标准库；GUI 需要 Tkinter。Windows 官方 Python 通常提供 Tkinter；Linux 开发环境可通过发行版软件包安装它，命令行不依赖 GUI。

```powershell
python -m unittest discover -s tests -v
python -m pip install -e .
python -m pip install -r requirements-build.txt
python build.py
```

结构：

```text
app.py                  Tkinter 界面与后台任务
dataset_gen_core.py     抽样、去重、校验、文件输出、CLI
targeting.py            多行业与定向场景生成
catalogue.py            行业、业务、槽位规范与新增场景
scenes.py               电商模板与词表
tests/                  回归与异常路径测试
examples/               小型可读示例与质量报告
validation/             交付版本验证记录
```

扩展行业：在 `catalogue.py` 添加行业/领域、槽位中文名和 `add(...)` 场景；在 `targeting.py:values_for` 添加协调的实体生成规则。新增场景需提供一致的 domain/intent、明确的槽位来源和可测试的缺失信息，避免新增未经工具验证的业务承诺。

欢迎提交问题与补丁。提交前运行测试，说明触发输入、预期行为、实际输出、种子和质量报告。详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

本地交付遵循 MIT 许可证，详见 [LICENSE](LICENSE)。发布数据时，使用者需要确认混入原始样本的使用与再分发权限；程序许可证不自动授予外部数据的许可。

### GitHub CI 配置

仓库中的 `.github/ci-templates/tests.yml` 是 Windows / Python 3.10、3.12、3.13 测试模板。当前上传凭据未授予 GitHub `workflow` 权限，因此模板暂未启用为自动工作流。仓库维护者可在具备相应权限后将它复制到 `.github/workflows/tests.yml`；也可随时运行上述本地测试命令。
