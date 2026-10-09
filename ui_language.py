"""English UI strings and scrollable settings pages."""
import tkinter as tk
from tkinter import ttk, messagebox
import re
import catalogue as C
from language_support import EN_ACTIONS

UI_EN = {
 '  输入输出关联  ':'  Input / output associations  ',
 '启用输入词汇与输出标签关联':'Enable input vocabulary / output label associations',
 '例如：快递号 / 运单号 → 物流查询场景 → 中文“查询物流”、英文“track shipment”。规则同时命中不同场景时过滤并报告。':'Example: tracking number → shipment query scene → Chinese / English intent aliases. Conflicting scene matches are filtered and reported.',
 '加载关联规则…':'Load association rules…','保存关联规则…':'Save association rules…','关联配置错误':'Invalid association rules',
 '示例见 examples/association-rules.json 与 logistics-templates.json。关联词汇是显式规则，不会自动猜测未标注语料。canonical 输出保留原标签编码。':'See examples/association-rules.json and logistics-templates.json. Associations use explicit rules; unlabeled data is never automatically labeled. canonical retains original codes.',
 '预览输入与关联规则冲突，请调整模板或所选场景':'Preview conflicts with association rules; adjust the template or selected scenario',
 '  输入模板  ':'  Input templates  ',
 '启用自定义输入模板（意图 / 槽位 / 领域）':'Enable custom utterance templates (intent / slots / domain)',
 '编辑 text 中 ${占位词} 的位置，或用 segments + shuffle 随机调整片段顺序；variables 指定槽位映射和独立词库。':'Move ${placeholder} in text, or use segments + shuffle to randomize segment order. variables maps slots and independent vocabularies.',
 '加载输入模板…':'Load input templates…','保存输入模板…':'Save input templates…',
 '示例见 examples/utterance-templates.json。输出字段名在“自定义数据格式”的 custom JSON 中自由命名、调整层级。模板的业务含义需要自行审核。':'See examples/utterance-templates.json. Set arbitrary output field names and nesting in the custom JSON format editor. Review the business meaning of your templates.',
 '  词池与多样性  ':'  Entity pools and diversity  ',
 '启用内置扩展词池与组合生成':'Enable expanded built-in pools and procedural combinations',
 '自定义词池 JSON':'Custom entity pools JSON','加载词池…':'Load pools…','清空':'Clear','词池配置错误':'Invalid entity pools',
 '支持中英文词表、按业务场景覆盖、组合模板与随机数字/编码；按打乱词表抽样，减少短期重复。':'Use Chinese/English vocabulary, scenario overrides, combination templates and random numbers/codes. Shuffled decks reduce short-term repetition.',
 '示例见 examples/entity-pools.json。词表可持续扩展；组合按需生成，不展开巨大的笛卡尔积。商品/尺码和换货类别组合保留内置约束。':'See examples/entity-pools.json. Extend vocabulary freely; combinations are generated on demand. Product/size and exchange category pairs retain built-in constraints.',
 '扩增不会改变业务意图。自定义词表需要语义审核；随机性和可生成规模不代表真实业务覆盖率。':'Augmentation preserves the intent label. Review custom vocabulary for meaning; diversity and generation capacity do not measure real business coverage.',
 '定向数据集生成器':'Targeted Dataset Generator',
 '选择行业、业务功能与训练任务，生成有针对性的对话数据集':'Choose industries, business scenarios and tasks to generate targeted dialogue data',
 '界面语言':'UI language','语料语言':'Corpus language','标签值语言':'Label value language',
 '  行业与训练方向  ':'  Industries and tasks  ','  输出与质量设置  ':'  Output and quality  ',
 '  语料种子导入  ':'  Seed corpus import  ','  自定义数据格式  ':'  Data format  ',
 '1. 选择行业（可多选）':'1. Select industries (multiple selections allowed)',
 '电商':'E-commerce','金融':'Finance','出行与酒店':'Travel and hotels','通信服务':'Telecom','教育培训':'Education',
 '2. 选择业务功能（已选项才会生成；Ctrl/Shift 可多选）':'2. Select business scenarios (Ctrl/Shift for multiple selections)',
 '全选':'Select all','清空选择':'Clear selection',
 '输出与随机性':'Output and randomness','输出文件':'Output file','浏览…':'Browse…','目标大小 (MiB)':'Target size (MiB)',
 '随机种子':'Random seed','留空自动随机':'Leave empty for a random seed','相似结构上限':'Structure limit',
 '跨批次去重（使用本机历史索引）':'Cross-run deduplication (local history)',
 '上限越小，模板重复越少；固定种子 + 同一参考日期 + 关闭跨批次去重可复现数据。':'Lower limits reduce template repetition. Use the same seed/date and disable history deduplication to reproduce data.',
 '参考日期':'Reference date','留空为今天，或填写 YYYY-MM-DD':'Leave empty for today, or enter YYYY-MM-DD',
 '3. 选择训练任务与配比（按实际字节占比，权重可调整）':'3. Select tasks and weights (based on written bytes)',
 '意图识别 + 槽位抽取':'Intent classification + slots','独立槽位提取':'Slot extraction','业务领域分类':'Domain classification',
 '状态跟踪 user_state':'Dialogue state: user_state','状态跟踪 belief_state':'Dialogue state: belief_state',
 '澄清问题生成':'Clarification questions','售后 Agent / 工具调用':'After-sales agent / tools',
 '原始样本（可选，仅混入通过校验的电商售后样本）':'Legacy samples (optional, validated Chinese after-sales data only)',
 '启用':'Enable','选择…':'Select…',
 '售后 Agent 仅适用于电商退货、换货、仅退款和售后进度。其他行业支持前六类任务。':'The tool agent supports e-commerce returns, exchanges, refunds and request tracking. Other industries support the first six tasks.',
 '开始生成':'Generate','停止并保存':'Stop and save','打开输出目录':'Open output folder','查看质量报告':'View quality report',
 'UTF-8 JSONL / JSON / CSV + 质量报告；可导入已标注语料并自定义记录结构。':'UTF-8 JSONL / JSON / CSV with quality reports; import labeled seeds and customize record layouts.',
 '就绪。建议先生成 100 MiB 检查样本与质量报告。':'Ready. Start with a small dataset and inspect its quality report.',
 '已标注语料（JSONL / JSON / CSV，UTF-8）':'Labeled corpus (JSONL / JSON / CSV, UTF-8)',
 '使用语料种子':'Use seed corpus','选择文件…':'Choose file…','默认训练任务':'Default task','默认业务场景':'Default scenario',
 '记录内 task/scene 优先；意图标签可自动匹配。槽位等任务无场景标注时，请指定场景或只选一个业务功能。':'Record-level task/scene take priority. Intent labels can identify a scenario; other tasks need a scenario or one selected business function.',
 '字段映射（支持 meta.scene 等点路径；messages 与输入/答案二选一）':'Field mapping (dotted keys such as meta.scene; messages or input/answer pairs)',
 '消息列表':'Messages','用户输入':'User input','答案 / 标签':'Answer / label','任务 ID':'Task ID','场景 ID':'Scenario ID','标签模式槽位':'Slots for string labels','来源分组 ID':'Source group ID',
 '每任务种子字节预算上限 (%)':'Seed byte budget per task (%)',
 '替换已标注槽位值扩增（单轮意图 / 槽位）':'Augment labeled slot values (single-turn intent / slots)',
 '预检种子（前 200 条）':'Check seeds (first 200 records)',
 '导入后仍按所选行业、业务功能和任务筛选、校验及去重；无标签文本不会被自动猜测标签。种子不足时由内置生成器补足。':'Imports are scoped, validated and deduplicated. Labels are never guessed. Training mode may use built-in samples; test mode uses test seeds only.',
 '训练／测试种子隔离':'Training / test seed isolation','使用哪一侧种子':'Seed partition','测试侧比例 (%)':'Test fraction (%)','划分种子':'Split seed',
 '按 group_id 或输入结构分组；同组扩增不跨侧。test 模式只使用测试种子，不足时提前保存。':'Groups use group_id or input structure. Descendants stay in the same partition. Test mode saves early if its seed pool is exhausted.',
 '记录结构':'Record layout','文件格式':'File format',
 '选择 custom 后编辑下方 JSON 模板，自定义字段名、层级和固定字段；无需编写代码。':'Select custom to edit JSON field names, nesting and constants. No code is executed.',
 '加载格式模板…':'Load template…','保存格式模板…':'Save template…','预览导出记录':'Preview export',
 '单独使用变量会保留数组/对象类型；放在文字中会转为字符串。CSV 将嵌套值保存为 JSON 字符串。多轮 Alpaca 输入包含完整历史。':'Standalone variables preserve object/array types. Embedded variables become strings. CSV encodes nested values as JSON; Alpaca retains dialogue history.',
 '关闭':'Close','模板错误':'Template error','保存失败':'Save failed','预览失败':'Preview failed','导出格式预览':'Export preview',
 '参数错误':'Invalid settings','生成失败':'Generation failed','覆盖确认':'Confirm overwrite',
 '输出文件已存在。生成成功后将替换该文件，是否继续？':'The output exists and will be replaced after successful generation. Continue?',
 '种子配置错误':'Invalid seed configuration','种子预检失败':'Seed check failed',
 '语料种子预检（前 200 条）':'Seed check (first 200 records)',
 '正在预检前 200 条种子…':'Checking the first 200 seed records…',
 '正在停止并保存已生成的数据…':'Stopping and saving complete records…','正在保存，保存完成后关闭窗口…':'Saving before closing the window…',
 '请选择现有语料种子文件':'Choose an existing seed corpus file',
 '种子预算上限应大于 0 且不超过 100%':'The seed budget must be above 0 and at most 100%',
 '请选择至少一个训练任务':'Select at least one task','请选择至少一个行业及一个业务功能':'Select at least one industry and scenario',
 '输出扩展名需要与所选文件格式一致':'The output extension must match the selected file format',
 '目标大小必须为有限正数':'Target size must be a finite positive number',
 '相似结构上限应为 1–100000':'Structure limit must be between 1 and 100000',
 '输出或报告不能覆盖语料种子文件':'Output and reports cannot overwrite seed files',
 'follow 随语料语言；zh 中文值；en 英文值；canonical 保留原枚举。JSON 键名保持固定。':'follow uses the corpus language; zh = Chinese values; en = English values; canonical = original codes. JSON keys stay fixed.',
 '读取语料种子，检查字段、标签、所选场景及重复输入…':'Reading seeds; checking fields, labels, scope and duplicate inputs…',
 '测试种子比例须大于 0 且小于 100%':'The test fraction must be above 0 and below 100%',
 '输出不能覆盖原始样本文件':'Output cannot overwrite the legacy source file',
 '启用原始样本时请选择现有文件':'Choose an existing file for legacy samples',
 '配比须为有限非负数，至少启用一项':'Weights must be finite and non-negative; enable at least one task',
}


class LanguageUiMixin:
    def _warn(self,title,text): messagebox.showwarning(self._tr(title),self._progress_text(text))
    def _error(self,title,text): messagebox.showerror(self._tr(title),self._progress_text(text))
    def _ask(self,title,text): return messagebox.askyesno(self._tr(title),self._tr(text))

    def _progress_text(self,text):
        if self.ui_language != 'en': return text
        known = self._tr(text)
        if known != text: return known
        patterns = [
          (r'随机种子：(\d+)；参考日期：([\d-]+)；逐条校验 \+ 输入去重 \+ 结构上限 (\d+)',r'Random seed: \1; reference date: \2; validation + deduplication + structure limit \3'),
          (r'语料种子扫描 (\d+) 条，合格 (\d+) 条，保留 (\d+) 条',r'Seed corpus: \1 scanned, \2 valid, \3 retained'),
          (r'扫描语料种子 (\d+) 条，合格 (\d+) 条',r'Seed corpus: \1 scanned, \2 valid'),
          (r'(\d+(?:\.\d+)?) MB / (\d+) 条；过滤 (\d+) 条；(.+) MB/s',r'\1 MB / \2 records; \3 filtered; \4 MB/s'),
          (r'(完成|已停止并保存)：(\d+) 条，质量报告：(.+)',r'Saved \2 records; quality report: \3'),
        ]
        for pattern,replacement in patterns:
            if re.fullmatch(pattern,text): return re.sub(pattern,replacement,text)
        return text
    def _tr(self,text):
        if getattr(self,'ui_language','zh') == 'zh': return text
        if text in UI_EN: return UI_EN[text]
        if text.startswith('变量：'): return 'Variables: '+text.split('：',1)[1]
        return text

    def _add_scroll_tab(self, notebook, title):
        outer = ttk.Frame(notebook)
        canvas = tk.Canvas(outer, height=440, highlightthickness=0, borderwidth=0)
        scroll = ttk.Scrollbar(outer,orient='vertical',command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side='left',fill='both',expand=True)
        scroll.pack(side='right',fill='y')
        inner = ttk.Frame(canvas)
        item = canvas.create_window(0,0,window=inner,anchor='nw')
        inner.bind('<Configure>',lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e: canvas.itemconfigure(item,width=e.width))
        notebook.add(outer,text=title)
        self._tab_canvases[str(outer)] = canvas
        return inner

    def _scroll_current_tab(self,event):
        widget = self.winfo_containing(event.x_root,event.y_root)
        if isinstance(widget,(tk.Text,tk.Listbox)): return
        canvas = self._tab_canvases.get(self.notebook.select())
        current = widget
        while current is not None:
            if current is canvas:
                canvas.yview_scroll(-int(event.delta/120),'units')
                return
            current = getattr(current,'master',None)

    def _apply_ui_language(self):
        self.ui_language = 'en' if self.var_ui_language.get() == 'English' else 'zh'
        def walk(widget):
            try:
                text = widget.cget('text')
                if text:
                    original = self._ui_original.setdefault(str(widget),str(text))
                    widget.configure(text=self._tr(original))
            except tk.TclError: pass
            for child in widget.winfo_children(): walk(child)
        walk(self)
        for tab in self.notebook.tabs():
            original = self._ui_tabs.setdefault(tab,self.notebook.tab(tab,'text'))
            self.notebook.tab(tab,text=self._tr(original))
        self.title('Targeted Dataset Generator v2.1' if self.ui_language == 'en' else '定向数据集生成器 v2.1 · 中英文与种子隔离')
        selected = self.scene_list.curselection()
        self.scene_list.delete(0,'end')
        for scene in self.visible_scenes: self.scene_list.insert('end',self._scene_label(scene))
        for index in selected: self.scene_list.selection_set(index)
        self._sync_agent()
        if not self.worker or not self.worker.is_alive(): self.var_status.set(self._tr('就绪。建议先生成 100 MiB 检查样本与质量报告。'))

    def _scene_label(self,scene):
        if getattr(self,'ui_language','zh') == 'en':
            return f"{self._tr(C.INDUSTRIES[scene['industry']])} / {scene['domain']} / {EN_ACTIONS[scene['id']]}"
        return f"{C.INDUSTRIES[scene['industry']]} / {C.DOMAINS[scene['domain']]} / {scene['action']}"
