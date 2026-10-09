import copy
import json
from pathlib import Path
import re
import tempfile
import unittest

import catalogue as C
import dataset_gen_core as core
from data_formats import RecordFormat
from seed_corpus import normalize, SeedCorpus
from seed_partition import SeedPartition

SCENE = 'finance:bank_card:REPORT_LOSS'


class LanguagesPartitionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_all_english_scenarios_and_tasks_have_no_chinese_text(self):
        for scene in C.SCENARIOS:
            gen = core.Generator(42,'2026-10-09',[scene['industry']],[scene['id']],language='en')
            for task in core.TASKS[:-1]:
                for _ in range(5):
                    sample = gen.generate(task)
                    core.validate(sample)
                    self.assertEqual(sample.scene,scene['id'])
                    self.assertFalse(re.search('[\u4e00-\u9fff]',core.dumps(sample.obj)))
            if scene['id'] in C.AGENT_SCENES:
                for _ in range(100):
                    sample = gen.generate('ecom')
                    core.validate(sample)
                    self.assertFalse(re.search('[\u4e00-\u9fff]',core.dumps(sample.obj)))

    def test_label_values_switch_but_keys_and_entities_stay_fixed(self):
        sample = core.Generator(42,industries=['ecom'],scenario_ids=['ecom:order:CANCEL']).generate('intent')
        original = copy.deepcopy(sample.obj)
        zh = json.loads(RecordFormat(label_language='zh').render(sample)['messages'][-1]['content'])
        en = json.loads(RecordFormat(label_language='en').render(sample)['messages'][-1]['content'])
        code = json.loads(RecordFormat(label_language='canonical').render(sample)['messages'][-1]['content'])
        self.assertEqual(zh['domain'],'订单')
        self.assertEqual(zh['intent'],'取消订单')
        self.assertEqual(en['intent'],'cancel my order')
        self.assertEqual(code['intent'],'CANCEL')
        self.assertEqual(zh['slots'],code['slots'])
        self.assertEqual(en['slots'],code['slots'])
        self.assertEqual(set(zh),set(en))
        self.assertEqual(sample.obj,original)

    def test_localized_labels_reimport_without_losing_grounding(self):
        scene = C.BY_ID[SCENE]
        for language in ('zh','en'):
            gen = core.Generator(9,industries=['finance'],scenario_ids=[SCENE],language=language)
            for task in core.TASKS[:-1]:
                for policy in ('zh','en'):
                    sample = gen.generate(task)
                    row = RecordFormat(label_language=policy).render(sample)
                    row['scene'] = SCENE
                    imported = normalize(row,{},[scene],core,language)
                    core.validate(imported)

    def test_english_seed_augmentation_and_chinese_seed_language_filter(self):
        path = self.root/'en.jsonl'
        path.write_text(json.dumps({'input':'Please report the lost card ending 1234.',
            'output':{'slots':{'card_no':'card ending 1234'}}})+'\n',encoding='utf-8')
        result = core.main(str(self.root/'en-output.json'),50000,seed=42,industries=['finance'],scenario_ids=[SCENE],
            language='en',label_language='en',seed_paths=[path],seed_split='all',
            weights_override={k:int(k == 'slots') for k in core.TASKS})
        self.assertGreater(result['seed_counts']['augmented'],0)
        records = json.loads(Path(result['dst']).read_text(encoding='utf-8'))
        self.assertFalse(re.search('[\u4e00-\u9fff]',core.dumps(records)))
        bad = self.root/'zh.jsonl'
        bad.write_text(json.dumps({'input':'请挂失银行卡','output':{'slots':{}}},ensure_ascii=False),encoding='utf-8')
        corpus = SeedCorpus.load([bad],{},[C.BY_ID[SCENE]],['slots'],core,language='en')
        self.assertEqual(corpus.report['retained'],0)

    def test_train_test_lineages_disjoint_and_test_never_fills_with_builtin_data(self):
        rows = []
        for i in range(40):
            prefix = 'Family'+chr(65+i//26)+chr(65+i%26)
            for n in (i,100+i):
                card = '卡尾号'+f'{n:04d}'
                rows.append({'input':prefix+'：请挂失'+card,'output':{'slots':{'card_no':card}},'group_id':prefix})
        source = self.root/'source.jsonl'
        source.write_text('\n'.join(core.dumps(r) for r in rows)+'\n',encoding='utf-8')
        common = dict(target_bytes=200000,seed=42,industries=['finance'],scenario_ids=[SCENE],
            weights_override={k:int(k == 'slots') for k in core.TASKS},seed_paths=[source],seed_augment=False,
            seed_registry=str(self.root/'partitions.sqlite3'))
        train = core.main(str(self.root/'train.jsonl'),seed_split='train',**common)
        test = core.main(str(self.root/'test.jsonl'),seed_split='test',**common)
        self.assertFalse(set(train['seed_groups_written']) & set(test['seed_groups_written']))
        self.assertTrue(test['seed_source_exhausted'])
        self.assertLess(test['size'],common['target_bytes'])
        self.assertEqual(sum(test['stats'].values()),test['seed_counts']['original'])
        self.assertGreater(test['seed_counts']['original'],0)
        prompts = lambda report: {core.Sample('slots',json.loads(line)).input_key for line in Path(report['dst']).read_text(encoding='utf-8').splitlines()}
        self.assertFalse(prompts(train) & prompts(test))

    def test_assignment_persists_after_ratio_change_and_input_groups_ignore_task(self):
        path = self.root/'registry.sqlite3'
        part = SeedPartition('train',.2,42,path)
        prior = part.assign('a'*64)
        part.close()
        part = SeedPartition('test',.9,999,path)
        self.addCleanup(part.close)
        self.assertEqual(part.assign('a'*64),prior)
        sample = core.Generator(2,industries=['finance'],scenario_ids=[SCENE]).generate('intent')
        other = copy.deepcopy(sample)
        other.task = 'slots'
        other.obj['messages'][0]['content'] = core.SYS['slots']
        self.assertEqual(part.group(sample,core),part.group(other,core))


if __name__ == '__main__': unittest.main()
