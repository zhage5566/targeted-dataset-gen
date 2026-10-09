"""Import/export controls shared by the desktop UI, without executing templates."""
import json
import math
from pathlib import Path
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

import catalogue as C
import dataset_gen_core as core
from data_formats import DEFAULT_SCHEMA, RecordFormat, RecordWriter
from seed_corpus import DEFAULT_FIELDS, SeedCorpus
from seed_partition import SeedPartition

AUTO = 'auto'


class ImportExportMixin:
    def _build_import_export(self, notebook):
        seeds = self._add_scroll_tab(notebook,'  语料种子导入  ')
        formats = self._add_scroll_tab(notebook,'  自定义数据格式  ')
        pools = self._add_scroll_tab(notebook,'  词池与多样性  ')
        inputs = self._add_scroll_tab(notebook,'  输入模板  ')
        links=self._add_scroll_tab(notebook,'  输入输出关联  ')
        self.var_associations_enabled=tk.BooleanVar(value=False)
        ttk.Checkbutton(links,text='启用输入词汇与输出标签关联',variable=self.var_associations_enabled).pack(anchor='w',padx=20,pady=10)
        ttk.Label(links,text='例如：快递号 / 运单号 → 物流查询场景 → 中文“查询物流”、英文“track shipment”。规则同时命中不同场景时过滤并报告。',wraplength=790,foreground='#617080').pack(anchor='w',padx=20,pady=5)
        self.association_editor=scrolledtext.ScrolledText(links,height=13,font=('Consolas',10))
        self.association_editor.pack(fill='x',padx=20,pady=5)
        self.association_editor.insert('1.0','{"rules": []}')
        link_actions=ttk.Frame(links); link_actions.pack(fill='x',padx=20,pady=8)
        ttk.Button(link_actions,text='加载关联规则…',command=lambda:self._association_file(False)).pack(side='left')
        ttk.Button(link_actions,text='保存关联规则…',command=lambda:self._association_file(True)).pack(side='left',padx=8)
        ttk.Button(link_actions,text='预览导出记录',command=self._preview_format).pack(side='left',padx=8)
        ttk.Label(links,text='示例见 examples/association-rules.json 与 logistics-templates.json。关联词汇是显式规则，不会自动猜测未标注语料。canonical 输出保留原标签编码。',wraplength=790,foreground='#617080').pack(anchor='w',padx=20,pady=5)
        self.var_templates_enabled=tk.BooleanVar(value=False)
        ttk.Checkbutton(inputs,text='启用自定义输入模板（意图 / 槽位 / 领域）',variable=self.var_templates_enabled).pack(anchor='w',padx=20,pady=10)
        ttk.Label(inputs,text='编辑 text 中 ${占位词} 的位置，或用 segments + shuffle 随机调整片段顺序；variables 指定槽位映射和独立词库。',wraplength=790,foreground='#617080').pack(anchor='w',padx=20,pady=5)
        self.input_template_editor=scrolledtext.ScrolledText(inputs,height=13,font=('Consolas',10))
        self.input_template_editor.pack(fill='x',padx=20,pady=5)
        self.input_template_editor.insert('1.0','{"scenes": {}}')
        template_actions=ttk.Frame(inputs); template_actions.pack(fill='x',padx=20,pady=8)
        ttk.Button(template_actions,text='加载输入模板…',command=self._load_input_template).pack(side='left')
        ttk.Button(template_actions,text='保存输入模板…',command=self._save_input_template).pack(side='left',padx=8)
        ttk.Button(template_actions,text='预览导出记录',command=self._preview_format).pack(side='left',padx=8)
        ttk.Label(inputs,text='示例见 examples/utterance-templates.json。输出字段名在“自定义数据格式”的 custom JSON 中自由命名、调整层级。模板的业务含义需要自行审核。',wraplength=790,foreground='#617080').pack(anchor='w',padx=20,pady=5)
        self.var_expanded_pools = tk.BooleanVar(value=True)
        self.var_pool_path = tk.StringVar()
        ttk.Checkbutton(pools,text='启用内置扩展词池与组合生成',variable=self.var_expanded_pools).pack(anchor='w',padx=20,pady=14)
        pool_row=ttk.Frame(pools); pool_row.pack(fill='x',padx=20,pady=8)
        ttk.Label(pool_row,text='自定义词池 JSON').pack(side='left')
        ttk.Entry(pool_row,textvariable=self.var_pool_path).pack(side='left',fill='x',expand=True,padx=8)
        ttk.Button(pool_row,text='加载词池…',command=self._browse_pools).pack(side='left')
        ttk.Button(pool_row,text='清空',command=lambda:self.var_pool_path.set('')).pack(side='left',padx=8)
        ttk.Label(pools,text='支持中英文词表、按业务场景覆盖、组合模板与随机数字/编码；按打乱词表抽样，减少短期重复。',wraplength=790,foreground='#617080').pack(anchor='w',padx=20,pady=8)
        ttk.Label(pools,text='示例见 examples/entity-pools.json。词表可持续扩展；组合按需生成，不展开巨大的笛卡尔积。商品/尺码和换货类别组合保留内置约束。',wraplength=790,foreground='#617080').pack(anchor='w',padx=20,pady=8)
        ttk.Label(pools,text='扩增不会改变业务意图。自定义词表需要语义审核；随机性和可生成规模不代表真实业务覆盖率。',wraplength=790,foreground='#617080').pack(anchor='w',padx=20,pady=8)
        self.var_seed_enabled = tk.BooleanVar(value=False)
        self.var_seed_path = tk.StringVar()
        box = ttk.LabelFrame(seeds, text='已标注语料（JSONL / JSON / CSV，UTF-8）')
        box.pack(fill='x', padx=12, pady=8)
        ttk.Checkbutton(box, text='使用语料种子', variable=self.var_seed_enabled).grid(row=0, column=0, padx=8, pady=6)
        ttk.Entry(box, textvariable=self.var_seed_path).grid(row=0, column=1, sticky='ew', padx=4)
        ttk.Button(box, text='选择文件…', command=self._browse_seed).grid(row=0, column=2, padx=8)
        box.columnconfigure(1, weight=1)
        self.var_seed_task, self.var_seed_scene = tk.StringVar(value=AUTO), tk.StringVar(value=AUTO)
        ttk.Label(box, text='默认训练任务').grid(row=1, column=0, padx=8, pady=5, sticky='w')
        ttk.Combobox(box, textvariable=self.var_seed_task, values=[AUTO] + list(core.TASKS), state='readonly').grid(row=1, column=1, sticky='ew')
        ttk.Label(box, text='默认业务场景').grid(row=2, column=0, padx=8, pady=5, sticky='w')
        ttk.Combobox(box, textvariable=self.var_seed_scene, values=[AUTO] + list(C.BY_ID), state='readonly').grid(row=2, column=1, columnspan=2, padx=(0,8), sticky='ew')
        ttk.Label(box, text='记录内 task/scene 优先；意图标签可自动匹配。槽位等任务无场景标注时，请指定场景或只选一个业务功能。',
                  wraplength=790, foreground='#617080').grid(row=3, column=0, columnspan=3, sticky='w', padx=8, pady=6)
        mapping = ttk.LabelFrame(seeds, text='字段映射（支持 meta.scene 等点路径；messages 与输入/答案二选一）')
        mapping.pack(fill='x', padx=12, pady=5)
        self.seed_field_vars = {}
        labels = {'messages':'消息列表', 'input':'用户输入', 'output':'答案 / 标签', 'task':'任务 ID', 'scene':'场景 ID', 'slots':'标签模式槽位','group':'来源分组 ID'}
        for i, (key, value) in enumerate(DEFAULT_FIELDS.items()):
            variable = tk.StringVar(value=value)
            self.seed_field_vars[key] = variable
            ttk.Label(mapping, text=labels[key]).grid(row=i//2, column=(i%2)*2, padx=8, pady=5, sticky='w')
            ttk.Entry(mapping, textvariable=variable, width=25).grid(row=i//2, column=(i%2)*2+1, padx=8, sticky='ew')
        mapping.columnconfigure(1, weight=1)
        mapping.columnconfigure(3, weight=1)
        opts = ttk.Frame(seeds)
        opts.pack(fill='x', padx=20, pady=8)
        self.var_seed_share = tk.StringVar(value='30')
        self.var_seed_augment = tk.BooleanVar(value=True)
        ttk.Label(opts, text='每任务种子字节预算上限 (%)').pack(side='left')
        ttk.Entry(opts, textvariable=self.var_seed_share, width=7).pack(side='left', padx=8)
        ttk.Checkbutton(opts, text='替换已标注槽位值扩增（单轮意图 / 槽位）', variable=self.var_seed_augment).pack(side='left', padx=8)
        ttk.Button(seeds, text='预检种子（前 200 条）', command=self._preview_seed).pack(anchor='w', padx=20, pady=5)
        partition = ttk.LabelFrame(seeds,text='训练／测试种子隔离')
        partition.pack(fill='x',padx=12,pady=5)
        self.var_seed_split = tk.StringVar(value='train')
        self.var_test_fraction, self.var_split_seed = tk.StringVar(value='20'), tk.StringVar(value='42')
        ttk.Label(partition,text='使用哪一侧种子').grid(row=0,column=0,padx=8,pady=6)
        ttk.Combobox(partition,textvariable=self.var_seed_split,values=['train','test','all'],state='readonly',width=9).grid(row=0,column=1,padx=8)
        ttk.Label(partition,text='测试侧比例 (%)').grid(row=0,column=2,padx=8)
        ttk.Entry(partition,textvariable=self.var_test_fraction,width=6).grid(row=0,column=3,padx=8)
        ttk.Label(partition,text='划分种子').grid(row=0,column=4,padx=8)
        ttk.Entry(partition,textvariable=self.var_split_seed,width=8).grid(row=0,column=5,padx=8)
        ttk.Label(partition,text='按 group_id 或输入结构分组；同组扩增不跨侧。test 模式只使用测试种子，不足时提前保存。',wraplength=790,foreground='#617080').grid(row=1,column=0,columnspan=6,padx=8,pady=6,sticky='w')
        ttk.Label(seeds, text='导入后仍按所选行业、业务功能和任务筛选、校验及去重；无标签文本不会被自动猜测标签。种子不足时由内置生成器补足。',
                  wraplength=790, foreground='#617080').pack(anchor='w', padx=20, pady=5)

        row = ttk.Frame(formats)
        row.pack(fill='x', padx=20, pady=12)
        self.var_record_format = tk.StringVar(value='messages')
        self.var_file_format = tk.StringVar(value='jsonl')
        ttk.Label(row, text='记录结构').pack(side='left')
        record_combo = ttk.Combobox(row, textvariable=self.var_record_format, values=['messages','alpaca','sharegpt','custom'], state='readonly', width=14)
        record_combo.pack(side='left', padx=8)
        record_combo.bind('<<ComboboxSelected>>', lambda e: self._sync_format_editor())
        ttk.Label(row, text='文件格式').pack(side='left', padx=(20,0))
        file_combo = ttk.Combobox(row, textvariable=self.var_file_format, values=['jsonl','json','csv'], state='readonly', width=10)
        file_combo.pack(side='left', padx=8)
        file_combo.bind('<<ComboboxSelected>>', lambda e: self._change_extension())
        ttk.Label(formats, text='选择 custom 后编辑下方 JSON 模板，自定义字段名、层级和固定字段；无需编写代码。', foreground='#425466').pack(anchor='w', padx=20, pady=4)
        self.format_editor = scrolledtext.ScrolledText(formats, height=9, font=('Consolas',10))
        self.format_editor.pack(fill='x', padx=20, pady=5)
        self.format_editor.insert('1.0', json.dumps(DEFAULT_SCHEMA, ensure_ascii=False, indent=2))
        actions = ttk.Frame(formats)
        actions.pack(fill='x', padx=20, pady=5)
        ttk.Button(actions, text='加载格式模板…', command=self._load_format).pack(side='left', padx=(0,8))
        ttk.Button(actions, text='保存格式模板…', command=self._save_format).pack(side='left', padx=8)
        ttk.Button(actions, text='预览导出记录', command=self._preview_format).pack(side='left', padx=8)
        ttk.Label(formats, text='变量：${messages}、${system}、${input}、${output}、${history}、${answer_json}、${task}、${scene}、${industry}、${domain}、${intent}、${slots}、${language}、${seed_group}、${seed_split}',
                  wraplength=790, foreground='#617080').pack(anchor='w', padx=20, pady=5)
        ttk.Label(formats, text='单独使用变量会保留数组/对象类型；放在文字中会转为字符串。CSV 将嵌套值保存为 JSON 字符串。多轮 Alpaca 输入包含完整历史。',
                  wraplength=790, foreground='#617080').pack(anchor='w', padx=20, pady=5)
        self._sync_format_editor()

    def _browse_pools(self):
        path=filedialog.askopenfilename(filetypes=[('JSON','*.json')])
        if not path: return
        try:
            from entity_pools import EntityPools
            EntityPools(path)
            self.var_pool_path.set(path)
        except (ValueError,OSError) as exc: self._warn('词池配置错误',str(exc))

    def _pool_options(self):
        path=self.var_pool_path.get().strip() or None
        from entity_pools import EntityPools
        EntityPools(path,self.var_expanded_pools.get())
        return {'entity_pools':path,'expanded_pools':self.var_expanded_pools.get()}

    def _template_options(self):
        from utterance_templates import UtteranceTemplates
        config=json.loads(self.input_template_editor.get('1.0','end')) if self.var_templates_enabled.get() else None
        UtteranceTemplates(config)
        return {'utterance_templates':config}

    def _association_options(self):
        from association_rules import AssociationRules
        config=json.loads(self.association_editor.get('1.0','end')) if self.var_associations_enabled.get() else None
        AssociationRules(config)
        return {'association_rules':config}

    def _association_file(self,save):
        from association_rules import AssociationRules
        try:
            if save:
                config=json.loads(self.association_editor.get('1.0','end')); AssociationRules(config)
                path=filedialog.asksaveasfilename(defaultextension='.json',filetypes=[('JSON','*.json')])
                if path: Path(path).write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            else:
                path=filedialog.askopenfilename(filetypes=[('JSON','*.json')])
                if not path: return
                config=json.loads(Path(path).read_text(encoding='utf-8-sig')); AssociationRules(config)
                self.association_editor.delete('1.0','end')
                self.association_editor.insert('1.0',json.dumps(config,ensure_ascii=False,indent=2)); self.var_associations_enabled.set(True)
        except (ValueError,OSError) as exc: self._warn('关联配置错误',str(exc))

    def _load_input_template(self):
        path=filedialog.askopenfilename(filetypes=[('JSON','*.json')])
        if not path: return
        try:
            from utterance_templates import UtteranceTemplates
            config=json.loads(Path(path).read_text(encoding='utf-8-sig')); UtteranceTemplates(config)
            self.input_template_editor.delete('1.0','end')
            self.input_template_editor.insert('1.0',json.dumps(config,ensure_ascii=False,indent=2))
            self.var_templates_enabled.set(True)
        except (ValueError,OSError) as exc: self._warn('模板错误',str(exc))

    def _save_input_template(self):
        try:
            from utterance_templates import UtteranceTemplates
            config=json.loads(self.input_template_editor.get('1.0','end')); UtteranceTemplates(config)
            path=filedialog.asksaveasfilename(defaultextension='.json',filetypes=[('JSON','*.json')])
            if path: Path(path).write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        except (ValueError,OSError) as exc: self._warn('模板错误',str(exc))

    def _browse_seed(self):
        path = filedialog.askopenfilename(filetypes=[('语料种子','*.jsonl *.ndjson *.json *.csv'),('所有文件','*.*')])
        if path:
            self.var_seed_path.set(path)
            self.var_seed_enabled.set(True)

    def _seed_options(self, require=False):
        if not self.var_seed_enabled.get() and not require: return {'seed_paths': []}
        path = self.var_seed_path.get().strip()
        if not path or not Path(path).is_file(): raise ValueError('请选择现有语料种子文件')
        share = float(self.var_seed_share.get()) / 100
        if not math.isfinite(share) or not 0 < share <= 1: raise ValueError('种子预算上限应大于 0 且不超过 100%')
        fields = {k: v.get().strip() for k,v in self.seed_field_vars.items()}
        config = {'fields': fields}
        if self.var_seed_task.get() != AUTO: config['task'] = self.var_seed_task.get()
        if self.var_seed_scene.get() != AUTO: config['scene'] = self.var_seed_scene.get()
        fraction = float(self.var_test_fraction.get())/100
        if not math.isfinite(fraction) or not 0 < fraction < 1: raise ValueError('测试种子比例须大于 0 且小于 100%')
        return {'seed_paths':[path], 'seed_config':config, 'seed_share':share, 'seed_augment':self.var_seed_augment.get(),
                'seed_split':self.var_seed_split.get(), 'test_fraction':fraction,'split_seed':int(self.var_split_seed.get()),
                'seed_registry':self.seed_registry_path}

    def _format_options(self):
        name = self.var_record_format.get()
        schema = json.loads(self.format_editor.get('1.0','end')) if name == 'custom' else None
        RecordFormat(name, schema, self.var_label_language.get())
        return {'record_format':name, 'format_schema':schema, 'file_format':self.var_file_format.get(), 'label_language':self.var_label_language.get()}

    def _sync_format_editor(self):
        self.format_editor.configure(state='normal' if self.var_record_format.get() == 'custom' else 'disabled')

    def _change_extension(self):
        if self.var_dst.get().strip():
            self.var_dst.set(str(Path(self.var_dst.get()).with_suffix('.' + self.var_file_format.get())))

    def _load_format(self):
        path = filedialog.askopenfilename(filetypes=[('JSON 模板','*.json')])
        if not path: return
        try:
            schema = json.loads(Path(path).read_text(encoding='utf-8-sig'))
            RecordFormat('custom', schema)
            self.var_record_format.set('custom')
            self._sync_format_editor()
            self.format_editor.delete('1.0','end')
            self.format_editor.insert('1.0', json.dumps(schema, ensure_ascii=False, indent=2))
        except (ValueError, OSError) as exc: self._warn('模板错误', str(exc))

    def _save_format(self):
        try:
            schema = json.loads(self.format_editor.get('1.0','end'))
            RecordFormat('custom', schema)
        except ValueError as exc:
            self._warn('模板错误', str(exc))
            return
        path = filedialog.asksaveasfilename(defaultextension='.json', filetypes=[('JSON 模板','*.json')], initialfile='dataset_format.json')
        if path:
            try: Path(path).write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding='utf-8')
            except OSError as exc: self._error('保存失败', str(exc))

    def _preview_format(self):
        try:
            opts = self._format_options()
            scenes = [self.visible_scenes[i]['id'] for i in self.scene_list.curselection()]
            industries = [k for k,v in self.industry_vars.items() if v.get()]
            gen = core.Generator(42, industries=industries, scenario_ids=scenes, language=self.var_data_language.get(),**self._pool_options(),**self._template_options())
            active = [k for k,v in self.task_vars.items() if v.get() and float(self.weight_vars[k].get()) > 0]
            if not active: raise ValueError('请选择至少一个训练任务')
            sample = gen.generate(active[0])
            core.validate(sample)
            from association_rules import AssociationRules
            associations=AssociationRules(self._association_options()['association_rules'])
            if not associations.allows(sample): raise ValueError('预览输入与关联规则冲突，请调整模板或所选场景')
            writer = RecordWriter(RecordFormat(opts['record_format'], opts['format_schema'],opts['label_language'],associations), opts['file_format'])
            text = (writer.encode(sample) + writer.finish()).decode('utf-8')
            self._show_text('导出格式预览', text)
        except (ValueError, OSError) as exc: self._warn('预览失败', str(exc))

    def _show_text(self, title, text):
        window = tk.Toplevel(self)
        window.title(self._tr(title))
        window.geometry('820x500')
        area = scrolledtext.ScrolledText(window, wrap='word', font=('Consolas',10))
        area.pack(fill='both', expand=True, padx=10, pady=10)
        area.insert('1.0', text)
        area.configure(state='disabled')
        ttk.Button(window, text=self._tr('关闭'), command=window.destroy).pack(pady=(0,10))

    def _preview_seed(self):
        if self.worker and self.worker.is_alive(): return
        try:
            opts = self._seed_options(require=True)
            from association_rules import AssociationRules
            associations=AssociationRules(self._association_options()['association_rules'])
            industries = [k for k,v in self.industry_vars.items() if v.get()]
            scenes = [self.visible_scenes[i]['id'] for i in self.scene_list.curselection()]
            gen = core.Generator(42, industries=industries, scenario_ids=scenes)
            active = [k for k,v in self.task_vars.items() if v.get() and float(self.weight_vars[k].get()) > 0]
            if not active: raise ValueError('请选择至少一个训练任务')
        except ValueError as exc:
            self._warn('种子配置错误', str(exc))
            return
        self.stop_event.clear()
        self.btn_start.configure(state='disabled')
        self.btn_stop.configure(state='normal')
        self.var_status.set(self._tr('正在预检前 200 条种子…'))
        language = self.var_data_language.get()
        def run():
            partition = None
            try:
                partition = SeedPartition(opts['seed_split'],opts['test_fraction'],opts['split_seed'],opts['seed_registry'],readonly=True)
                corpus = SeedCorpus.load(opts['seed_paths'], opts['seed_config'], gen.targets, active, core,
                                         42, self.stop_event, max_scan=200, language=language, partition=partition,associations=associations)
                self.q.put(('seed_preview', corpus.report, ''))
            except Exception as exc: self.q.put(('seed_preview_error', None, str(exc)))
            finally:
                if partition: partition.close()
        self.worker = threading.Thread(target=run, daemon=False)
        self.worker.start()
