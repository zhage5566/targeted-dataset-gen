import os
from pathlib import Path
import tempfile
import time
import unittest
import gc


@unittest.skipUnless(os.name == "nt", "GUI integration test requires Windows/Tk")
class UiTests(unittest.TestCase):
    def setUp(self):
        # Finalize previous Tk roots on the main thread before starting workers.
        gc.collect()

    def test_ui_and_corpus_language_switches(self):
        import app
        import json
        with tempfile.TemporaryDirectory() as tmp:
            ui = app.App()
            self.addCleanup(ui.destroy)
            ui.withdraw()
            ui.var_ui_language.set('English')
            ui._apply_ui_language()
            self.assertEqual(ui.btn_start['text'],'Generate')
            self.assertIn('Seed corpus import',ui.notebook.tab(ui.notebook.tabs()[2],'text'))
            self.assertTrue(ui.var_scope.get().startswith('Selected'))
            for key,var in ui.industry_vars.items(): var.set(key == 'finance')
            ui._refresh_scenes()
            ui._clear_scenes()
            ui.scene_list.selection_set(next(i for i,s in enumerate(ui.visible_scenes) if s['id'] == 'finance:bank_card:REPORT_LOSS'))
            for key,var in ui.task_vars.items(): var.set(key == 'intent')
            ui.var_data_language.set('en')
            ui.var_label_language.set('en')
            ui.var_history.set(False)
            ui.var_dst.set(str(Path(tmp)/'english.jsonl'))
            ui.var_mb.set('0.02')
            ui._start()
            deadline = time.monotonic()+30
            while ui.result is None and time.monotonic()<deadline:
                ui.update()
                time.sleep(.01)
            self.assertIsNotNone(ui.result,ui.var_status.get())
            row = json.loads(Path(ui.result['dst']).read_text(encoding='utf-8').splitlines()[0])
            self.assertEqual(json.loads(row['messages'][-1]['content'])['intent'],'report a lost bank card')
            self.assertTrue(ui.var_status.get().startswith('Complete'))
            ui.var_ui_language.set('中文')
            ui._apply_ui_language()
            self.assertEqual(ui.btn_start['text'],'开始生成')

    def test_seed_import_and_custom_json_output(self):
        import app
        import json
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'seed.jsonl'
            source.write_text(json.dumps({'q':'请挂失卡尾号1234','a':{'slots':{'card_no':'卡尾号1234'}}}, ensure_ascii=False)+'\n', encoding='utf-8')
            ui = app.App()
            self.addCleanup(ui.destroy)
            ui.withdraw()
            for key, var in ui.industry_vars.items(): var.set(key == 'finance')
            ui._refresh_scenes()
            ui._clear_scenes()
            index = next(i for i,s in enumerate(ui.visible_scenes) if s['id'] == 'finance:bank_card:REPORT_LOSS')
            ui.scene_list.selection_set(index)
            for key,var in ui.task_vars.items(): var.set(key == 'slots')
            ui.var_seed_enabled.set(True)
            ui.var_seed_path.set(str(source))
            ui.var_seed_split.set('all')
            ui.seed_field_vars['input'].set('q')
            ui.seed_field_vars['output'].set('a')
            ui.var_record_format.set('custom')
            ui.var_file_format.set('json')
            ui._sync_format_editor()
            ui.format_editor.delete('1.0','end')
            ui.format_editor.insert('1.0','{"question":"${input}","label":"${answer_json}"}')
            ui.var_dst.set(str(Path(tmp)/'ui.json'))
            ui.var_mb.set('0.03')
            ui.var_history.set(False)
            ui._start()
            deadline = time.monotonic()+30
            while ui.result is None and time.monotonic()<deadline:
                ui.update()
                time.sleep(.01)
            self.assertIsNotNone(ui.result, ui.var_status.get())
            self.assertGreater(ui.result['seed_counts']['augmented'], 0)
            records = json.loads(Path(ui.result['dst']).read_text(encoding='utf-8'))
            self.assertEqual(set(records[0]), {'question','label'})
            self.assertEqual(set(records[0]['label']), {'slots'})

    def test_finance_card_loss_slots_only(self):
        import app
        with tempfile.TemporaryDirectory() as tmp:
            ui = app.App()
            self.addCleanup(ui.destroy)
            ui.withdraw()
            ui.update_idletasks()
            for key, var in ui.industry_vars.items(): var.set(key == "finance")
            ui._refresh_scenes()
            self.assertEqual(len(ui.visible_scenes), 12)
            self.assertEqual(str(ui.task_checks["ecom"]["state"]), "disabled")
            ui._clear_scenes()
            index = next(i for i, s in enumerate(ui.visible_scenes) if s["id"] == "finance:bank_card:REPORT_LOSS")
            ui.scene_list.selection_set(index)
            ui._sync_agent()
            for key, var in ui.task_vars.items(): var.set(key == "slots")
            ui.var_dst.set(str(Path(tmp) / "ui.jsonl"))
            ui.var_mb.set("0.2")
            ui.var_history.set(False)
            ui.var_seed.set("9")
            ui.var_refdate.set("2026-10-09")
            ui._start()
            deadline = time.monotonic() + 30
            while ui.result is None and time.monotonic() < deadline:
                ui.update()
                time.sleep(.01)
            self.assertIsNotNone(ui.result, ui.var_status.get())
            self.assertEqual(set(ui.result["stats"]), {"slots"})
            self.assertEqual(ui.result["scenario_ids"], ["finance:bank_card:REPORT_LOSS"])
            self.assertEqual(str(ui.btn_report["state"]), "normal")

    def test_custom_input_pools_associations_and_output_keys(self):
        import app
        import json
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            ui=app.App(); self.addCleanup(ui.destroy); ui.withdraw()
            ui.var_ui_language.set('English'); ui._apply_ui_language()
            for key,var in ui.industry_vars.items(): var.set(key=='ecom')
            ui._refresh_scenes(); ui._clear_scenes()
            ui.scene_list.selection_set(next(i for i,s in enumerate(ui.visible_scenes) if s['id']=='ecom:logistics:QUERY'))
            for key,var in ui.task_vars.items(): var.set(key=='intent')
            ui.var_templates_enabled.set(True)
            ui.input_template_editor.delete('1.0','end')
            ui.input_template_editor.insert('1.0',(root/'examples/logistics-templates.json').read_text(encoding='utf-8'))
            ui.var_associations_enabled.set(True)
            ui.association_editor.delete('1.0','end')
            ui.association_editor.insert('1.0',(root/'examples/association-rules.json').read_text(encoding='utf-8'))
            ui.var_pool_path.set(str(root/'examples/entity-pools.json'))
            ui.var_record_format.set('custom'); ui._sync_format_editor()
            ui.format_editor.delete('1.0','end'); ui.format_editor.insert('1.0',(root/'examples/format-logistics.json').read_text(encoding='utf-8'))
            ui.var_data_language.set('en'); ui.var_history.set(False)
            ui.var_dst.set(str(Path(tmp)/'custom.jsonl')); ui.var_mb.set('0.01'); ui._start()
            deadline=time.monotonic()+30
            while ui.result is None and time.monotonic()<deadline: ui.update(); time.sleep(.01)
            self.assertIsNotNone(ui.result,ui.var_status.get())
            for row in map(json.loads,Path(ui.result['dst']).read_text(encoding='utf-8').splitlines()):
                self.assertEqual(row['custom_labels']['意图名称'],'track shipment')
                self.assertIn(row['labels']['tracking'],row['text'])
            self.assertTrue(ui.result['utterance_templates']['generated'])
