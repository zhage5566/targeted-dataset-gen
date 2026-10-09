# -*- coding: utf-8 -*-
"""电商客服数据集生成器 v2 桌面界面。"""
import argparse
import math
import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import dataset_gen_core as core
import catalogue as catalogue
from ui_extensions import ImportExportMixin
from ui_language import LanguageUiMixin

TASK_LABELS = [("intent", "意图识别 + 槽位抽取"), ("slots", "独立槽位提取"), ("domain", "业务领域分类"),
               ("dst_user", "状态跟踪 user_state"), ("dst_belief", "状态跟踪 belief_state"),
               ("clarify", "澄清问题生成"), ("ecom", "售后 Agent / 工具调用")]


class App(ImportExportMixin, LanguageUiMixin, tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("定向数据集生成器 v2.1 · 语料种子与自定义格式")
        self.geometry("920x840")
        self.minsize(840, 760)
        self.q = queue.Queue()
        self.stop_event = threading.Event()
        self.worker = self.result = None
        self.closing = False
        self.ui_language = "zh"
        self._ui_original, self._ui_tabs, self._tab_canvases = {}, {}, {}
        self.history_path = str(Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "EcomDatasetGen" / "history-v2.sqlite3")
        self.seed_registry_path = str(Path(self.history_path).with_name("seed-splits-v1.sqlite3"))
        self._build()
        self._apply_ui_language()
        self.bind_all("<MouseWheel>", self._scroll_current_tab, add="+")
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.poll_id = self.after(150, self._poll)

    def destroy(self):
        if getattr(self, "poll_id", None):
            try: self.after_cancel(self.poll_id)
            except tk.TclError: pass
            self.poll_id = None
        super().destroy()

    def _build(self):
        pad = {"padx": 12, "pady": 5}
        ttk.Label(self, text="定向数据集生成器", font=("Microsoft YaHei UI", 16, "bold")).pack(anchor="w", **pad)
        ttk.Label(self, text="选择行业、业务功能与训练任务，生成有针对性的对话数据集", foreground="#425466").pack(anchor="w", padx=12, pady=(0, 8))
        languages = ttk.Frame(self)
        languages.pack(fill="x", padx=12, pady=3)
        self.var_ui_language, self.var_data_language, self.var_label_language = tk.StringVar(value="中文"), tk.StringVar(value="zh"), tk.StringVar(value="follow")
        ttk.Label(languages,text="界面语言").pack(side="left")
        ui_combo = ttk.Combobox(languages,textvariable=self.var_ui_language,values=["中文","English"],state="readonly",width=10)
        ui_combo.pack(side="left",padx=8)
        ui_combo.bind("<<ComboboxSelected>>",lambda e:self._apply_ui_language())
        ttk.Label(languages,text="语料语言").pack(side="left",padx=(12,0))
        ttk.Combobox(languages,textvariable=self.var_data_language,values=["zh","en"],state="readonly",width=7).pack(side="left",padx=8)
        ttk.Label(languages,text="标签值语言").pack(side="left",padx=(12,0))
        ttk.Combobox(languages,textvariable=self.var_label_language,values=["follow","zh","en","canonical"],state="readonly",width=12).pack(side="left",padx=8)
        ttk.Label(self,text="follow 随语料语言；zh 中文值；en 英文值；canonical 保留原枚举。JSON 键名保持固定。",foreground="#617080",wraplength=800).pack(anchor="w",padx=12,pady=2)
        notebook = ttk.Notebook(self)
        self.notebook = notebook
        notebook.pack(fill="x", padx=12, pady=5)
        scope = self._add_scroll_tab(notebook,"  行业与训练方向  ")
        settings = self._add_scroll_tab(notebook,"  输出与质量设置  ")
        industry_box = ttk.LabelFrame(scope, text="1. 选择行业（可多选）")
        industry_box.pack(fill="x", **pad)
        self.industry_vars = {}
        for key, label in catalogue.INDUSTRIES.items():
            var = tk.BooleanVar(value=key == "ecom")
            self.industry_vars[key] = var
            ttk.Checkbutton(industry_box, text=label, variable=var, command=self._refresh_scenes).pack(side="left", padx=12, pady=8)
        scene_box = ttk.LabelFrame(scope, text="2. 选择业务功能（已选项才会生成；Ctrl/Shift 可多选）")
        scene_box.pack(fill="x", **pad)
        scene_frame = ttk.Frame(scene_box)
        scene_frame.pack(fill="x", padx=8, pady=4)
        self.scene_list = tk.Listbox(scene_frame, selectmode="extended", exportselection=False, height=7, font=("Microsoft YaHei UI", 10))
        scrollbar = ttk.Scrollbar(scene_frame, command=self.scene_list.yview)
        self.scene_list.configure(yscrollcommand=scrollbar.set)
        self.scene_list.pack(side="left", fill="x", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.scene_list.bind("<<ListboxSelect>>", lambda event: self._sync_agent())
        scene_buttons = ttk.Frame(scene_box)
        scene_buttons.pack(fill="x", padx=8, pady=3)
        ttk.Button(scene_buttons, text="全选", command=self._all_scenes).pack(side="left", padx=4)
        ttk.Button(scene_buttons, text="清空选择", command=self._clear_scenes).pack(side="left", padx=4)
        self.var_scope = tk.StringVar()
        ttk.Label(scene_buttons, textvariable=self.var_scope, foreground="#425466").pack(side="left", padx=12)
        frm = ttk.LabelFrame(settings, text="输出与随机性")
        frm.pack(fill="x", **pad)
        frm.columnconfigure(1, weight=1)
        ttk.Label(frm, text="输出文件").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        self.var_dst = tk.StringVar(value=core.DST)
        ttk.Entry(frm, textvariable=self.var_dst).grid(row=0, column=1, columnspan=3, sticky="we", padx=6)
        ttk.Button(frm, text="浏览…", command=self._browse).grid(row=0, column=4, padx=8)
        ttk.Label(frm, text="目标大小 (MiB)").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        self.var_mb = tk.StringVar(value="100")
        ttk.Entry(frm, textvariable=self.var_mb, width=12).grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(frm, text="随机种子").grid(row=1, column=2, sticky="e")
        self.var_seed = tk.StringVar(value="")
        ttk.Entry(frm, textvariable=self.var_seed, width=22).grid(row=1, column=3, padx=6)
        ttk.Label(frm, text="留空自动随机", foreground="#617080").grid(row=1, column=4, padx=8)
        ttk.Label(frm, text="相似结构上限").grid(row=2, column=0, sticky="w", padx=8, pady=6)
        self.var_shape = tk.StringVar(value="200")
        ttk.Spinbox(frm, textvariable=self.var_shape, from_=1, to=100000, width=12).grid(row=2, column=1, sticky="w", padx=6)
        self.var_history = tk.BooleanVar(value=True)
        ttk.Checkbutton(frm, text="跨批次去重（使用本机历史索引）", variable=self.var_history).grid(row=2, column=2, columnspan=3, sticky="w", padx=6)
        ttk.Label(frm, text="上限越小，模板重复越少；固定种子 + 同一参考日期 + 关闭跨批次去重可复现数据。", foreground="#617080").grid(row=3, column=0, columnspan=5, sticky="w", padx=8, pady=4)
        self.var_refdate = tk.StringVar(value="")
        ttk.Label(frm, text="参考日期").grid(row=4, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(frm, textvariable=self.var_refdate, width=18).grid(row=4, column=1, sticky="w", padx=6)
        ttk.Label(frm, text="留空为今天，或填写 YYYY-MM-DD", foreground="#617080").grid(row=4, column=2, columnspan=3, sticky="w")
        box = ttk.LabelFrame(scope, text="3. 选择训练任务与配比（按实际字节占比，权重可调整）")
        box.pack(fill="x", **pad)
        self.weight_vars = {}
        self.task_vars, self.task_checks = {}, {}
        for i, (key, label) in enumerate(TASK_LABELS):
            task_var = tk.BooleanVar(value=True)
            self.task_vars[key] = task_var
            check = ttk.Checkbutton(box, text=label, variable=task_var)
            self.task_checks[key] = check
            check.grid(row=i//2, column=(i%2)*2, sticky="w", padx=12, pady=4)
            var = tk.StringVar(value=str(core.DEFAULT_WEIGHTS[key]))
            self.weight_vars[key] = var
            ttk.Entry(box, textvariable=var, width=8).grid(row=i//2, column=(i%2)*2+1, sticky="w", padx=12)
        original = ttk.LabelFrame(settings, text="原始样本（可选，仅混入通过校验的电商售后样本）")
        original.pack(fill="x", **pad)
        self.var_orig = tk.BooleanVar(value=False)
        self.var_src = tk.StringVar(value=core.SRC if Path(core.SRC).exists() else "")
        ttk.Checkbutton(original, text="启用", variable=self.var_orig).pack(side="left", padx=8)
        ttk.Entry(original, textvariable=self.var_src).pack(side="left", fill="x", expand=True, padx=4, pady=6)
        ttk.Button(original, text="选择…", command=self._browse_source).pack(side="left", padx=8)
        self._build_import_export(notebook)
        ttk.Label(scope, text="售后 Agent 仅适用于电商退货、换货、仅退款和售后进度。其他行业支持前六类任务。", foreground="#617080").pack(anchor="w", padx=12, pady=6)
        self._refresh_scenes()
        self.pb = ttk.Progressbar(self, orient="horizontal", mode="determinate")
        self.pb.pack(fill="x", **pad)
        self.var_status = tk.StringVar(value="就绪。建议先生成 100 MiB 检查样本与质量报告。")
        ttk.Label(self, textvariable=self.var_status, wraplength=800).pack(anchor="w", padx=12, pady=2)
        self.log = scrolledtext.ScrolledText(self, height=10, font=("Microsoft YaHei UI", 9), state="disabled")
        bfrm = ttk.Frame(self)
        bfrm.pack(side="bottom", fill="x", **pad)
        self.btn_start = ttk.Button(bfrm, text="开始生成", command=self._start)
        self.btn_start.pack(side="left", padx=4)
        self.btn_stop = ttk.Button(bfrm, text="停止并保存", command=self._stop, state="disabled")
        self.btn_stop.pack(side="left", padx=4)
        self.btn_open = ttk.Button(bfrm, text="打开输出目录", command=self._open_dir, state="disabled")
        self.btn_open.pack(side="left", padx=4)
        self.btn_report = ttk.Button(bfrm, text="查看质量报告", command=self._open_report, state="disabled")
        self.btn_report.pack(side="left", padx=4)
        ttk.Label(self, text="UTF-8 JSONL / JSON / CSV + 质量报告；可导入已标注语料并自定义记录结构。", foreground="#617080").pack(side="bottom", anchor="w", padx=12, pady=(0, 10))
        self.log.pack(fill="both", expand=True, **pad)

    def _refresh_scenes(self):
        selected = [k for k, v in self.industry_vars.items() if v.get()]
        self.visible_scenes = [s for s in catalogue.SCENARIOS if s["industry"] in selected]
        self.scene_list.delete(0, "end")
        for s in self.visible_scenes:
            self.scene_list.insert("end", self._scene_label(s))
        self.scene_list.selection_set(0, "end")
        self._sync_agent()

    def _all_scenes(self):
        self.scene_list.selection_set(0, "end")
        self._sync_agent()

    def _clear_scenes(self):
        self.scene_list.selection_clear(0, "end")
        self._sync_agent()

    def _sync_agent(self):
        scenes = [self.visible_scenes[i] for i in self.scene_list.curselection()]
        supported = any(s["id"] in catalogue.AGENT_SCENES for s in scenes)
        if not supported: self.task_vars["ecom"].set(False)
        self.task_checks["ecom"].configure(state="normal" if supported else "disabled")
        self.var_scope.set(f"Selected {len(scenes)} / {len(self.visible_scenes)} scenarios" if self.ui_language == "en" else f"已选 {len(scenes)} / {len(self.visible_scenes)} 个业务功能")

    def _browse(self):
        extension = "." + self.var_file_format.get()
        path = filedialog.asksaveasfilename(defaultextension=extension, filetypes=[(self.var_file_format.get().upper(), "*" + extension)], initialfile="targeted_dataset_v2" + extension)
        if path: self.var_dst.set(path)

    def _browse_source(self):
        path = filedialog.askopenfilename(filetypes=[("JSONL", "*.jsonl"), ("所有文件", "*.*")])
        if path: self.var_src.set(path)

    def _log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        if int(self.log.index("end-1c").split(".")[0]) > 1000: self.log.delete("1.0", "200.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _start(self):
        if self.worker and self.worker.is_alive(): return
        try:
            dst = self.var_dst.get().strip()
            export_options = self._format_options()
            export_options.update(self._pool_options())
            export_options.update(self._template_options())
            export_options.update(self._association_options())
            seed_options = self._seed_options()
            if not dst or Path(dst).suffix.lower() != "." + export_options["file_format"]:
                raise ValueError("输出扩展名需要与所选文件格式一致")
            protected = {Path(dst).resolve(), Path(dst + ".quality.json").resolve(), Path(dst + ".failed-report.json").resolve()}
            if any(Path(p).resolve() in protected for p in seed_options["seed_paths"]):
                raise ValueError("输出或报告不能覆盖语料种子文件")
            mb = float(self.var_mb.get())
            if not math.isfinite(mb) or mb <= 0 or int(mb*1048576) < 1: raise ValueError("目标大小必须为有限正数")
            seed_text = self.var_seed.get().strip()
            seed = int(seed_text) if seed_text else None
            shape_limit = int(self.var_shape.get())
            if not 1 <= shape_limit <= 100000: raise ValueError("相似结构上限应为 1–100000")
            industries = [k for k, v in self.industry_vars.items() if v.get()]
            scenario_ids = [self.visible_scenes[i]["id"] for i in self.scene_list.curselection()]
            if not industries or not scenario_ids: raise ValueError("请选择至少一个行业及一个业务功能")
            weights = {k: float(v.get()) if self.task_vars[k].get() else 0 for k, v in self.weight_vars.items()}
            if any(not math.isfinite(v) or v < 0 for v in weights.values()) or sum(weights.values()) <= 0: raise ValueError("配比须为有限非负数，至少启用一项")
            ref = self.var_refdate.get().strip() or None
            if ref: core.date.fromisoformat(ref)
            original, src = self.var_orig.get(), self.var_src.get().strip()
            if original and not Path(src).is_file(): raise ValueError("启用原始样本时请选择现有文件")
            if src and Path(src).resolve() == Path(dst).resolve(): raise ValueError("输出不能覆盖原始样本文件")
        except (ValueError, OverflowError) as exc:
            self._warn("参数错误", str(exc))
            return
        if Path(dst).exists() and not self._ask("覆盖确认", "输出文件已存在。生成成功后将替换该文件，是否继续？"): return
        # Tk 变量只在主线程读取，后台线程使用捕获的普通参数。
        kwargs = dict(dst=dst, target_bytes=int(mb*1048576), seed=seed, weights_override=weights,
                      include_original=original, src=src, shape_limit=shape_limit,
                      history_path=self.history_path if self.var_history.get() else None, reference_date=ref,
                      industries=industries, scenario_ids=scenario_ids,
                      **seed_options, **export_options,
                      language=self.var_data_language.get(),
                      progress_cb=lambda written, total, text: self.q.put(("progress", written, text)), stop_event=self.stop_event)
        self.stop_event.clear()
        self.result = None
        self.pb.configure(maximum=mb*1048576, value=0)
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.btn_open.configure(state="disabled")
        self.btn_report.configure(state="disabled")
        self._log(f"Generating: {dst}; target {mb:g} MiB; industries {','.join(industries)}; {len(scenario_ids)} scenarios" if self.ui_language == "en" else f"开始生成：{dst}；目标 {mb:g} MiB；行业 {','.join(catalogue.INDUSTRIES[i] for i in industries)}；业务功能 {len(scenario_ids)} 个")
        def run():
            try:
                result = core.main(**kwargs)
                self.q.put(("done", result, ""))
            except Exception as exc: self.q.put(("error", 0, str(exc)))
        self.worker = threading.Thread(target=run, daemon=False)
        self.worker.start()

    def _stop(self):
        self.stop_event.set()
        self.var_status.set(self._tr("正在停止并保存已生成的数据…"))
        self.btn_stop.configure(state="disabled")

    def _close(self):
        if self.worker and self.worker.is_alive():
            self.closing = True
            self._stop()
            self.var_status.set(self._tr("正在保存，保存完成后关闭窗口…"))
        else: self.destroy()

    def _open_dir(self):
        if self.result: os.startfile(str(Path(self.result["dst"]).parent))

    def _open_report(self):
        if self.result:
            import subprocess
            subprocess.Popen(["notepad.exe", self.result["report_path"]])

    def _poll(self):
        try:
            while True:
                kind, payload, text = self.q.get_nowait()
                if kind in ("seed_preview", "seed_preview_error"):
                    self.btn_start.configure(state="normal")
                    self.btn_stop.configure(state="disabled")
                    if self.closing:
                        self.destroy()
                        return
                    if kind == "seed_preview":
                        summary = f"Seed check: {payload['scanned']} scanned, {payload['valid']} valid. The full file will be reloaded for generation." if self.ui_language == "en" else f"种子预检：扫描 {payload['scanned']} 条，合格 {payload['valid']} 条；完整导入在生成时重新执行。"
                        self.var_status.set(summary)
                        self._log(summary)
                        import json
                        self._show_text("语料种子预检（前 200 条）", json.dumps(payload, ensure_ascii=False, indent=2))
                    else:
                        self.var_status.set("种子预检失败：" + text)
                        self._error("种子预检失败", text)
                    continue
                if kind == "progress":
                    self.pb.configure(value=payload)
                    self.var_status.set(f"{payload/1048576:.1f} / {float(self.pb['maximum'])/1048576:g} MiB")
                    if text: self._log(self._progress_text(text))
                else:
                    self.btn_start.configure(state="normal")
                    self.btn_stop.configure(state="disabled")
                    if kind == "done":
                        self.result = payload
                        self.pb.configure(value=payload["size"])
                        status = '测试种子耗尽，已保存' if payload.get('seed_source_exhausted') else '已停止并保存' if payload['stopped'] else '完成'
                        if self.ui_language == "en":
                            status = 'Seed pool exhausted; saved' if payload.get('seed_source_exhausted') else 'Stopped and saved' if payload['stopped'] else 'Complete'
                        msg = f"{status}: {payload['size']/1048576:.1f} MiB, {sum(payload['stats'].values())} records; {sum(payload['rejected'].values())} filtered" if self.ui_language == "en" else f"{status}：{payload['size']/1048576:.1f} MiB，{sum(payload['stats'].values())} 条；过滤 {sum(payload['rejected'].values())} 条"
                        self.var_status.set(msg)
                        self._log(msg)
                        self._log(f"Random seed: {payload['seed']}; quality report: {payload['report_path']}" if self.ui_language == "en" else f"实际随机种子：{payload['seed']}；质量报告：{payload['report_path']}")
                        if payload.get("seed_corpus"):
                            counts = payload["seed_counts"]
                            self._log(f"Seed originals: {counts.get('original',0)}; augmented: {counts.get('augmented',0)}; byte share: {payload['seed_byte_share']:.1%}" if self.ui_language == "en" else f"语料种子原句 {counts.get('original', 0)} 条，槽位扩增 {counts.get('augmented', 0)} 条；实际字节占比 {payload['seed_byte_share']:.1%}")
                        self.btn_open.configure(state="normal")
                        self.btn_report.configure(state="normal")
                    else:
                        self.var_status.set("生成失败：" + text)
                        self._log("错误：" + text)
                        if not self.closing: self._error("生成失败", text)
                    if self.closing:
                        self.destroy()
                        return
        except queue.Empty: pass
        self.poll_id = self.after(150, self._poll)


def launch():
    App().mainloop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true", help="可执行文件无界面自检")
    parser.add_argument("--dst")
    args = parser.parse_args()
    if args.self_test:
        import tempfile
        import json
        import time
        probe = App()
        probe.withdraw()
        probe.update_idletasks()
        with tempfile.TemporaryDirectory() as tmp:
            path = args.dst or str(Path(tmp) / "smoke.jsonl")
            try:
                result = core.main(path, target_bytes=1048576, seed=42, reference_date="2026-10-09", industries=list(catalogue.INDUSTRIES))
                source = Path(tmp) / "seed.jsonl"
                source.write_text(json.dumps({'input':'请挂失卡尾号1234','output':{'slots':{'card_no':'卡尾号1234'}}}, ensure_ascii=False)+'\n', encoding='utf-8')
                for key, variable in probe.industry_vars.items(): variable.set(key == 'finance')
                probe._refresh_scenes()
                probe._clear_scenes()
                index = next(i for i,s in enumerate(probe.visible_scenes) if s['id'] == 'finance:bank_card:REPORT_LOSS')
                probe.scene_list.selection_set(index)
                for key, variable in probe.task_vars.items(): variable.set(key == 'slots')
                probe.var_seed_enabled.set(True)
                probe.var_seed_path.set(str(source))
                probe.var_seed_split.set('all')
                probe.var_history.set(False)
                probe.var_seed.set('42')
                probe.var_mb.set('0.03')
                probe.var_record_format.set('custom')
                probe.var_file_format.set('csv')
                probe._sync_format_editor()
                probe.format_editor.delete('1.0','end')
                probe.format_editor.insert('1.0','{"text":"${input}","label":"${answer_json}"}')
                probe.var_dst.set(path + '.import.csv')
                probe._start()
                deadline = time.monotonic() + 60
                while probe.result is None and time.monotonic() < deadline:
                    probe.update()
                    time.sleep(.01)
                if probe.result is None or not probe.result['seed_counts'].get('augmented'):
                    raise RuntimeError('Seed import/export UI self-test failed')
                probe.var_ui_language.set('English')
                probe._apply_ui_language()
                english=core.main(path+'.en.jsonl',32768,seed=43,industries=list(catalogue.INDUSTRIES),language='en',label_language='follow')
                if english['language']!='en' or not english['entity_pools']['replacement_draws']:
                    raise RuntimeError('English corpus / expanded pools self-test failed')
                scene='ecom:order:CANCEL'
                sample=core.Generator(2,'2026-10-09',['ecom'],[scene]).generate('intent')
                from data_formats import RecordFormat
                answer=json.loads(RecordFormat('messages',label_language='zh').render(sample)['messages'][-1]['content'])
                if answer['intent']=='CANCEL' or set(answer)!={'domain','intent','slots'}:
                    raise RuntimeError('Localized label values self-test failed')
                logistics='ecom:logistics:QUERY'
                templates={'scenes':{logistics:{'en':[{'text':'Track tracking number ${code}.','variables':{'code':{'slot':'tracking_no','templates':['DEMO-${id}'],'variables':{'id':{'digits':12}}}}}]}}}
                rules={'rules':[{'scene':logistics,'input':{'en':['tracking number','shipment number']},'output':{'en':{'intent':'track shipment','category':'shipment lookup'}}}]}
                custom=core.main(path+'.associated.jsonl',4096,seed=1,industries=['ecom'],scenario_ids=[logistics],language='en',label_language='follow',
                    weights_override={t:int(t=='intent') for t in core.TASKS},utterance_templates=templates,association_rules=rules,
                    record_format='custom',format_schema={'my_input':'${input}','my_label':'${associated.category}','my_entity':'${slots.tracking_no}'})
                first=json.loads(Path(custom['dst']).read_text(encoding='utf-8').splitlines()[0])
                if first['my_label']!='shipment lookup' or first['my_entity'] not in first['my_input']:
                    raise RuntimeError('Custom templates / associations / output keys self-test failed')
                Path(path + ".self-test.txt").write_text(f"PASS v{core.VERSION} bilingual Tk UI + {sum(result['stats'].values())} samples / five industries + seed import/augmentation/custom CSV + English corpus + localized values + expanded pools + custom input templates/associations/output keys", encoding="utf-8")
            finally:
                if probe.worker and probe.worker.is_alive():
                    probe.stop_event.set()
                    probe.worker.join(timeout=60)
                probe.destroy()
    else: launch()
