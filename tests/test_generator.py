import copy
from contextlib import closing
import json
from pathlib import Path
import random
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import catalogue as C
import dataset_gen_core as core


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def run_dataset(self, name, **kwargs):
        return core.main(str(self.root / (name + ".jsonl")), target_bytes=250000,
                         seed=20261009, reference_date="2026-10-09", **kwargs)

    def prompts(self, report):
        samples = [json.loads(line) for line in Path(report["dst"]).read_text(encoding="utf-8").splitlines()]
        return {core.dumps(s["messages"][:-1]) for s in samples}, samples

    def test_all_industries_and_tasks_pass_validation(self):
        for industry in C.INDUSTRIES:
            gen = core.Generator(123, "2026-10-09", [industry])
            tasks = core.TASKS if industry == "ecom" else core.TASKS[:-1]
            for i in range(3500):
                sample = gen.generate(tasks[i % len(tasks)])
                self.assertTrue(core.validate(sample))
                if sample.task != "ecom":
                    self.assertEqual(C.BY_ID[sample.scene]["industry"], industry)

    def test_scenario_and_slot_only_targeting(self):
        scenario = "finance:bank_card:REPORT_LOSS"
        gen = core.Generator(9, "2026-10-09", ["finance"], [scenario])
        for task in core.TASKS[:-1]:
            for _ in range(100):
                sample = gen.generate(task)
                self.assertEqual(sample.scene, scenario)
                core.validate(sample)
        report = self.run_dataset("finance", industries=["finance"], scenario_ids=[scenario],
                                  weights_override={k: int(k == "slots") for k in core.TASKS})
        _, samples = self.prompts(report)
        self.assertEqual(set(report["stats"]), {"slots"})
        for sample in samples:
            ans = json.loads(sample["messages"][-1]["content"])
            self.assertEqual(set(ans), {"slots"})
            self.assertLessEqual(set(ans["slots"]), {"card_no", "bank"})

    def test_agent_progress_and_original_targeting(self):
        gen = core.Generator(4, "2026-10-09", ["ecom"], ["ecom:after_sales:QUERY_PROGRESS"])
        for _ in range(100):
            sample = gen.generate("ecom")
            core.validate(sample)
            self.assertNotIn("申请退货退款", sample.obj["messages"][1]["content"])
            self.assertFalse(any("Action: create_after_sales_request" in m["content"] for m in sample.obj["messages"]))
        source = self.root / "source.jsonl"
        rows = [gen.generate("ecom").obj for _ in range(20)]
        source.write_text("\n".join(core.dumps(s) for s in rows + rows) + "\ninvalid\n", encoding="utf-8")
        report = self.run_dataset("original", industries=["ecom"], scenario_ids=["ecom:after_sales:QUERY_PROGRESS"],
                                  weights_override={k: int(k == "ecom") for k in core.TASKS},
                                  include_original=True, src=str(source))
        self.assertGreater(report["original_count"], 0)
        prompts, samples = self.prompts(report)
        self.assertEqual(len(prompts), len(samples))

    def test_reproducible_and_isolated_randomness(self):
        random.seed(17)
        before = random.getstate()
        first = self.run_dataset("first")
        second = self.run_dataset("second")
        self.assertEqual(Path(first["dst"]).read_bytes(), Path(second["dst"]).read_bytes())
        self.assertEqual(before, random.getstate())
        a = core.main(str(self.root / "auto1.jsonl"), 10000)
        b = core.main(str(self.root / "auto2.jsonl"), 10000)
        self.assertNotEqual(a["seed"], b["seed"])

    def test_byte_shares_and_utf8_sizes(self):
        report = self.run_dataset("shares")
        self.assertEqual(Path(report["dst"]).stat().st_size, report["size"])
        self.assertEqual(sum(report["bytes_by_task"].values()), report["size"])
        for task, share in report["requested_shares"].items():
            self.assertLess(abs(report["byte_shares"][task] - share), .02)
        prompts, samples = self.prompts(report)
        self.assertEqual(len(prompts), len(samples))

    def test_cross_batch_dedup_with_same_seed(self):
        history = str(self.root / "history.sqlite3")
        a = self.run_dataset("a", history_path=history)
        b = self.run_dataset("b", history_path=history)
        pa, _ = self.prompts(a)
        pb, _ = self.prompts(b)
        self.assertFalse(pa & pb)
        self.assertGreater(b["dup"], 0)

    def test_conflict_and_structure_limit(self):
        def card_sample(number):
            return core.Sample("intent", {"messages": [{"role":"system","content":core.SYS["intent"]},
                               {"role":"user","content":f"卡尾号{number}丢了，我要挂失"},
                               {"role":"assistant","content":core.dumps({"domain":"bank_card","intent":"REPORT_LOSS","slots":{"card_no":f"卡尾号{number}"}})}]}, (f"卡尾号{number}",))
        sample = card_sample("1234")
        db = core.Deduper(str(self.root / "dedup.sqlite3"), 1)
        self.addCleanup(db.close)
        self.assertIsNone(db.accept(sample))
        self.assertEqual(db.accept(sample), "duplicate")
        changed = copy.deepcopy(sample)
        changed.obj["messages"][-1]["content"] = '{"domain":"bank_card","intent":"QUERY_STATUS","slots":{}}'
        self.assertEqual(db.accept(changed), "conflict")
        other = card_sample("5678")
        self.assertEqual(other.shape, sample.shape)
        self.assertEqual(db.accept(other), "structure_limit")

    def test_invalid_labels_and_tool_preconditions_are_rejected(self):
        gen = core.Generator(20, "2026-10-09", ["finance"], ["finance:bank_card:REPORT_LOSS"])
        sample = gen.generate("intent")
        ans = json.loads(sample.answer)
        ans["intent"] = "QUERY_STATUS"
        sample.obj["messages"][-1]["content"] = core.dumps(ans)
        with self.assertRaisesRegex(ValueError, "定向业务"): core.validate(sample)
        sample = gen.generate("slots")
        sample.obj["messages"][-1]["content"] = '{"slots":{"card_no":"凭空编造"}}'
        with self.assertRaisesRegex(ValueError, "话术"): core.validate(sample)
        messages = [{"role": "user", "content": "订单EC-123，我要退货退款，商品破损。"},
                    {"role": "assistant", "content": 'Action: create_after_sales_request\nAction Input: {"order_id":"EC-123","request_type":"return_refund","reason":"damaged"}'}]
        with self.assertRaisesRegex(ValueError, "未经订单核实"): core.validate_ecom([{"role": "system", "content": core.SYS["ecom"]}] + messages)

    def test_dst_latest_value_and_withdrawal(self):
        uc = "用户: 订单的城市是北京。\n用户: 更正一下：订单的城市以上海为准。"
        sample = core.Sample("dst_user", {"messages": [{"role":"system","content":core.SYS["dst_user"]},
                             {"role":"user","content":uc}, {"role":"assistant","content":core.dumps([{"domain":"订单","slot":"城市","value":"北京","active":True}])}]})
        with self.assertRaisesRegex(ValueError, "最新状态"): core.validate(sample)
        sample.obj["messages"][-1]["content"] = core.dumps([{"domain":"订单","slot":"城市","value":"上海","active":True}])
        self.assertTrue(core.validate(sample))
        sample.obj["messages"][1]["content"] += "\n用户: 撤回订单的城市信息，先留空。"
        with self.assertRaisesRegex(ValueError, "最新状态"): core.validate(sample)

    def test_failure_preserves_destination_and_rolls_back_history(self):
        target = self.root / "protected.jsonl"
        target.write_bytes(b"original file")
        history = self.root / "history.sqlite3"
        original = core.Generator.generate
        count = 0
        def fail_after_some(gen, task):
            nonlocal count
            count += 1
            if count == 40: raise RuntimeError("forced failure")
            return original(gen, task)
        with patch.object(core.Generator, "generate", fail_after_some):
            with self.assertRaisesRegex(RuntimeError, "forced failure"):
                core.main(str(target), 1000000, history_path=str(history))
        self.assertEqual(target.read_bytes(), b"original file")
        with closing(sqlite3.connect(history)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM samples").fetchone()[0], 0)
        failure = json.loads(Path(str(target) + ".failed-report.json").read_text(encoding="utf-8"))
        self.assertTrue(Path(failure["partial_path"]).exists())

    def test_stop_saves_complete_jsonl_and_report(self):
        class Stop:
            calls = 0
            def is_set(self):
                self.calls += 1
                return self.calls > 80
        report = self.run_dataset("stop", stop_event=Stop())
        _, samples = self.prompts(report)
        self.assertTrue(report["stopped"])
        self.assertEqual(len(samples), sum(report["stats"].values()))
        self.assertTrue(Path(report["report_path"]).exists())

    def test_invalid_parameters(self):
        for kwargs in [{"industries": []}, {"industries": ["unknown"]}, {"industries": ["finance"], "scenario_ids": ["ecom:order:QUERY"]},
                       {"weights_override": {"intent": float("nan")}}, {"shape_limit": 0}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError): self.run_dataset("invalid", **kwargs)


if __name__ == "__main__": unittest.main()
