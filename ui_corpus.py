"""Offline corpus workbench tab; heavy processing uses the shared worker queue."""
import json
from pathlib import Path
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog

from corpus_catalog import CATALOG
from corpus_workbench import prepare


class CorpusUiMixin:
    def _build_corpus(self, notebook):
        page = self._add_scroll_tab(notebook, '  行业语料工作台  ')
        ttk.Label(page, text='公开语料目录：已整理 / 官方入口，数据与软件分别遵循原许可。', wraplength=790).pack(anchor='w', padx=16, pady=8)
        self.corpus_list = tk.Listbox(page, height=7, exportselection=False)
        self.corpus_list.pack(fill='x', padx=16)
        for item in CATALOG:
            self.corpus_list.insert('end', f"{item['name']} | {item['language']} | {item['industries']} | {item['status']}")
        ttk.Button(page, text='查看来源与使用条件', command=self._corpus_details).pack(anchor='w', padx=16, pady=6)
        root = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
        self.var_corpus_source = tk.StringVar()
        self.var_corpus_out = tk.StringVar(value=str(Path.home()/'Desktop'/'行业语料整理结果'))
        self.var_corpus_adapter = tk.StringVar(value='generic')
        self.var_corpus_cap = tk.StringVar(value='100')
        self.var_corpus_input = tk.StringVar(value='input')
        self.var_corpus_output = tk.StringVar(value='output')
        self.var_corpus_strategy = tk.StringVar(value='random')
        self.var_corpus_export = tk.StringVar(value='none')
        box = ttk.Frame(page); box.pack(fill='x', padx=16, pady=8); box.columnconfigure(1, weight=1)
        for i,(label,var) in enumerate([('原始语料文件或目录',self.var_corpus_source),('新建输出目录',self.var_corpus_out),
                                       ('输入字段',self.var_corpus_input),('答案字段',self.var_corpus_output),('每标签训练种子上限',self.var_corpus_cap)]):
            ttk.Label(box,text=label).grid(row=i,column=0,sticky='w',padx=4,pady=4)
            ttk.Entry(box,textvariable=var).grid(row=i,column=1,sticky='ew',padx=6)
        ttk.Button(box,text='选择文件…',command=self._corpus_file).grid(row=0,column=2,padx=4)
        ttk.Button(box,text='选择目录…',command=self._corpus_dir).grid(row=0,column=3,padx=4)
        ttk.Label(box,text='语料适配器').grid(row=5,column=0,sticky='w',padx=4,pady=5)
        ttk.Combobox(box,textvariable=self.var_corpus_adapter,values=['generic','crosswoz','banking77','clinc150'],state='readonly').grid(row=5,column=1,sticky='ew')
        ttk.Label(box,text='训练种子选取策略').grid(row=6,column=0,sticky='w',padx=4,pady=5)
        ttk.Combobox(box,textvariable=self.var_corpus_strategy,values=['coverage','random'],state='readonly').grid(row=6,column=1,sticky='ew')
        ttk.Label(box,text='兼容导出格式').grid(row=7,column=0,sticky='w',padx=4,pady=5)
        ttk.Combobox(box,textvariable=self.var_corpus_export,values=['none','messages','rasa'],state='readonly').grid(row=7,column=1,sticky='ew')
        ttk.Label(page,text='coverage 优先覆盖不同词面结构；random 为等预算随机对照。保留原始测试集，不用测试标签选择训练种子。',wraplength=790).pack(anchor='w',padx=16,pady=5)
        actions=ttk.Frame(page); actions.pack(fill='x',padx=16,pady=8)
        self.btn_corpus=ttk.Button(actions,text='整理、隔离并导出',command=self._start_corpus); self.btn_corpus.pack(side='left')
        ttk.Button(actions,text='打开中文使用说明',command=lambda:self._corpus_guide(root)).pack(side='left',padx=8)
        ttk.Label(page,text='输出 train / validation / test、均衡训练种子、隔离记录及质量报告。任意行业标签可整理；导入旧生成器仍须映射到其内置场景。',wraplength=790,foreground='#617080').pack(anchor='w',padx=16,pady=5)

    def _corpus_details(self):
        selected=self.corpus_list.curselection()
        if selected:
            item=CATALOG[selected[0]]
            self.var_corpus_adapter.set(item['adapter'])
            self._show_text('行业语料来源',json.dumps(item,ensure_ascii=False,indent=2))

    def _corpus_file(self):
        value=filedialog.askopenfilename(filetypes=[('语料','*.jsonl *.json *.csv')])
        if value: self.var_corpus_source.set(value); self.var_corpus_adapter.set('generic')

    def _corpus_dir(self):
        value=filedialog.askdirectory()
        if value: self.var_corpus_source.set(value)

    def _corpus_guide(self,root):
        path=root/'docs'/'中国用户使用说明.md'
        if path.exists(): self._show_text('中文使用说明',path.read_text(encoding='utf-8-sig'))
        else: self._show_text('中文使用说明','请解压完整离线包，阅读 docs/中国用户使用说明.md。\nhttps://www.modelscope.cn/datasets/zhouyang55666/customer_json/files')

    def _start_corpus(self):
        if self.worker and self.worker.is_alive(): return
        try:
            source=self.var_corpus_source.get().strip()
            if not source: raise ValueError('请选择原始语料')
            options=dict(source=source,destination=self.var_corpus_out.get().strip(),adapter=self.var_corpus_adapter.get(),
                         per_label=int(self.var_corpus_cap.get()),seed=42,
                         fields={'input':self.var_corpus_input.get(),'output':self.var_corpus_output.get()},strategy=self.var_corpus_strategy.get(),export_format=self.var_corpus_export.get())
            if not options['destination']: raise ValueError('请填写输出目录')
        except ValueError as exc: self._error('语料整理失败',str(exc)); return
        self.btn_corpus.configure(state='disabled'); self.btn_start.configure(state='disabled')
        self.var_status.set('正在整理语料 / Preparing corpus...')
        def run():
            try: self.q.put(('corpus_done',prepare(**options),options['destination']))
            except Exception as exc: self.q.put(('corpus_error',None,str(exc)))
        self.worker=threading.Thread(target=run,daemon=True); self.worker.start()

    def _corpus_event(self,kind,payload,text):
        self.btn_corpus.configure(state='normal'); self.btn_start.configure(state='normal')
        if kind=='corpus_done':
            self.var_status.set('语料整理完成 / Corpus ready: '+text)
            self._show_text('语料整理报告',json.dumps(payload,ensure_ascii=False,indent=2))
        else:
            self.var_status.set('语料整理失败 / Corpus preparation failed')
            self._error('语料整理失败',text)
