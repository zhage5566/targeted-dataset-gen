import csv
import json
from pathlib import Path
import tempfile
import unittest

import catalogue as C
import dataset_gen_core as core
from data_formats import RecordFormat, RecordWriter
from seed_corpus import SeedCorpus

SCENE = 'finance:bank_card:REPORT_LOSS'


class ImportExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def sample(self, value='卡尾号1234'):
        return {'question': '卡丢失了，请挂失' + value,
                'label': {'domain':'bank_card', 'intent':'REPORT_LOSS', 'slots':{'card_no':value}},
                'meta': {'scene': SCENE}}

    def source(self, rows, name='seed.jsonl'):
        path = self.root / name
        path.write_text('\n'.join(core.dumps(row) for row in rows) + '\n', encoding='utf-8')
        return path

    def options(self, source, **kwargs):
        return dict(dst=str(self.root/'result.jsonl'), target_bytes=45000, seed=42,
                    reference_date='2026-10-09', industries=['finance'], scenario_ids=[SCENE],
                    weights_override={k:int(k == 'intent') for k in core.TASKS},
                    seed_paths=[str(source)], seed_config={'fields':{'input':'question','output':'label','scene':'meta.scene'}},
                    seed_split='all',
                    **kwargs)

    def test_grounded_seed_augmentation_and_reproducibility(self):
        source = self.source([self.sample()])
        opts = self.options(source)
        result = core.main(**opts)
        rows = [json.loads(line) for line in Path(result['dst']).read_text(encoding='utf-8').splitlines()]
        self.assertEqual(result['seed_counts']['original'], 1)
        self.assertGreater(result['seed_counts']['augmented'], 5)
        seeded = [r for r in rows if r['messages'][1]['content'].startswith('卡丢失了，请挂失')]
        self.assertGreater(len(seeded), 5)
        for row in rows: core.validate(core.Sample('intent', row, scene=SCENE))
        self.assertEqual(len(rows), len({core.Sample('intent', r).input_key for r in rows}))
        original_bytes = Path(result['dst']).read_bytes()
        opts['dst'] = str(self.root/'repeat.jsonl')
        repeated = core.main(**opts)
        self.assertEqual(original_bytes, Path(repeated['dst']).read_bytes())

    def test_disable_augmentation_uses_original_once_and_falls_back(self):
        result = core.main(**self.options(self.source([self.sample()]), seed_augment=False))
        self.assertEqual(result['seed_counts'], {'original':1})
        self.assertGreater(sum(result['stats'].values()), 1)

    def test_csv_field_mapping_and_string_intent_labels(self):
        source = self.root/'label.csv'
        with source.open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['text','tag','entities'])
            writer.writeheader()
            writer.writerow({'text':'请挂失卡尾号5678','tag':'REPORT_LOSS','entities':json.dumps({'card_no':'卡尾号5678'}, ensure_ascii=False)})
        corpus = SeedCorpus.load([source], {'task':'intent','scene':SCENE,
            'fields':{'input':'text','output':'tag','slots':'entities'}}, [C.BY_ID[SCENE]], ['intent'], core)
        self.assertEqual(corpus.report['retained'], 1)
        sample = corpus.samples['intent'][0]
        self.assertEqual(json.loads(sample.answer)['slots']['card_no'], '卡尾号5678')

    def test_scope_bad_labels_duplicates_and_conflicts_are_reported(self):
        valid = self.sample()
        conflict = self.sample()
        conflict['meta']['scene'] = 'finance:bank_card:QUERY_STATUS'
        conflict['label']['intent'] = 'QUERY_STATUS'
        outside = self.sample()
        outside['meta']['scene'] = 'ecom:order:QUERY'
        bad = self.sample()
        bad['label']['slots']['card_no'] = '卡尾号9999'
        source = self.source([valid, valid, conflict, outside, bad])
        config = {'fields':{'input':'question','output':'label','scene':'meta.scene'}}
        corpus = SeedCorpus.load([source], config,
                                [C.BY_ID[SCENE], C.BY_ID['finance:bank_card:QUERY_STATUS']], ['intent'], core)
        self.assertEqual(corpus.report['valid'], 1)
        self.assertEqual(corpus.report['filtered']['重复输入'], 1)
        self.assertEqual(corpus.report['filtered']['同输入不同答案'], 1)
        self.assertEqual(corpus.report['filtered']['种子不属于当前行业或所选业务功能'], 1)
        self.assertEqual(corpus.report['filtered']['槽位值未出现在话术中'], 1)

    def test_invalid_import_preserves_existing_file(self):
        opts = self.options(self.source([{'question':'无标签'}]))
        target = Path(opts['dst'])
        target.write_bytes(b'keep this file')
        with self.assertRaisesRegex(ValueError, '没有可用语料种子'): core.main(**opts)
        self.assertEqual(target.read_bytes(), b'keep this file')
        opts['dst'] = opts['seed_paths'][0]
        with self.assertRaisesRegex(ValueError, '覆盖语料种子'): core.main(**opts)

    def test_custom_typed_template_and_unknown_variable_rejection(self):
        sample = core.Generator(42, industries=['finance'], scenario_ids=[SCENE]).generate('intent')
        schema = {'dialog':'${messages}', 'label':'${answer_json}', 'about':{'industry':'${industry}'},
                  'description':'task=${task}', 'fixed': True}
        record = RecordFormat('custom', schema).render(sample)
        self.assertIsInstance(record['dialog'], list)
        self.assertIsInstance(record['label'], dict)
        self.assertEqual(record['about']['industry'], 'finance')
        self.assertEqual(record['description'], 'task=intent')
        with self.assertRaisesRegex(ValueError, '未知格式变量'):
            RecordFormat('custom', {'data':"${__import__('os')}"})

    def test_all_containers_preserve_quotes_multiline_and_json_labels(self):
        source = self.source([self.sample()])
        schema = {'text':'${input}', 'answer':'${answer_json}', 'dialog':'${messages}'}
        for kind in ('jsonl','json','csv'):
            opts = self.options(source, record_format='custom', format_schema=schema, file_format=kind)
            opts['dst'] = str(self.root/('output.'+kind))
            result = core.main(**opts)
            path = Path(result['dst'])
            self.assertEqual(path.stat().st_size, result['size'])
            self.assertEqual(sum(result['bytes_by_task'].values()) + result['container_footer_bytes'], result['size'])
            if kind == 'jsonl': rows = [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines()]
            elif kind == 'json': rows = json.loads(path.read_text(encoding='utf-8'))
            else:
                with path.open(encoding='utf-8', newline='') as f: rows = list(csv.DictReader(f))
                for row in rows:
                    row['answer'] = json.loads(row['answer'])
                    row['dialog'] = json.loads(row['dialog'])
            self.assertEqual(len(rows), sum(result['stats'].values()))
            for row in rows:
                self.assertEqual(row['answer']['intent'], 'REPORT_LOSS')
                self.assertIsInstance(row['dialog'], list)
                core.validate(core.Sample('intent', {'messages':row['dialog']}, scene=SCENE))
        quoted = core.Sample('clarify', {'messages':[{'role':'system','content':'system'},
            {'role':'user','content':'含"引号",逗号\n第二行'}, {'role':'assistant','content':'答案\n换行'}]})
        writer = RecordWriter(RecordFormat('alpaca'), 'csv')
        import io
        row = list(csv.DictReader(io.StringIO(writer.encode(quoted).decode('utf-8'))))[0]
        self.assertEqual(row['input'], quoted.obj['messages'][1]['content'])
        self.assertEqual(row['output'], quoted.answer)

    def test_stopped_json_is_valid_even_without_records(self):
        class Stop:
            def is_set(self): return True
        result = core.main(str(self.root/'stopped.json'), 10000, stop_event=Stop(), file_format='json')
        self.assertEqual(json.loads(Path(result['dst']).read_text(encoding='utf-8')), [])
        self.assertTrue(result['stopped'])

    def test_sharegpt_and_alpaca_preserve_multiturn_context(self):
        sample = core.Generator(1).generate('ecom')
        chat = RecordFormat('sharegpt').render(sample)['conversations']
        self.assertEqual(len(chat), len(sample.obj['messages']))
        self.assertEqual(chat[-1]['value'], sample.answer)
        alpaca = RecordFormat('alpaca').render(sample)
        for message in sample.obj['messages'][1:-1]: self.assertIn(message['content'], alpaca['input'])

    def test_history_dedup_applies_across_output_formats(self):
        history = str(self.root/'history.sqlite3')
        opts = self.options(self.source([self.sample()]), history_path=history)
        first = core.main(**opts)
        prompts = {core.Sample('intent', json.loads(row)).input_key for row in Path(first['dst']).read_text(encoding='utf-8').splitlines()}
        opts.update(dst=str(self.root/'other.json'), file_format='json', record_format='custom',
                    format_schema={'messages':'${messages}'})
        second = core.main(**opts)
        rows = json.loads(Path(second['dst']).read_text(encoding='utf-8'))
        self.assertFalse(prompts & {core.Sample('intent', row).input_key for row in rows})
        self.assertGreater(second['dup'], 0)

    def test_dst_scene_mismatch_is_rejected(self):
        gen = core.Generator(3, industries=['ecom'], scenario_ids=['ecom:order:QUERY'])
        row = gen.generate('dst_user').obj
        row['scene'] = SCENE
        corpus = SeedCorpus.load([self.source([row])], {}, [C.BY_ID[SCENE]], ['dst_user'], core)
        self.assertEqual(corpus.report['retained'], 0)
        self.assertIn('DST 标注与指定业务场景不一致', corpus.report['filtered'])


if __name__ == '__main__': unittest.main()
