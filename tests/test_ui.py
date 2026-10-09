import os
from pathlib import Path
import tempfile
import time
import unittest


@unittest.skipUnless(os.name == "nt", "GUI integration test requires Windows/Tk")
class UiTests(unittest.TestCase):
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
