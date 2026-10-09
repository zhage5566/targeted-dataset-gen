import json
from pathlib import Path
import tempfile
import unittest

from association_rules import AssociationRules
import dataset_gen_core as core
from data_formats import RecordFormat

ROOT=Path(__file__).resolve().parents[1]
SCENE='ecom:logistics:QUERY'


class AssociationTests(unittest.TestCase):
    def test_bilingual_inputs_outputs_and_nested_key_renaming(self):
        rules=AssociationRules(ROOT/'examples/association-rules.json')
        schema=json.loads((ROOT/'examples/format-logistics.json').read_text(encoding='utf-8'))
        for language,intent in [('zh','查询物流'),('en','track shipment')]:
            gen=core.Generator(14,'2026-10-09',['ecom'],[SCENE],language=language,utterance_templates=ROOT/'examples/logistics-templates.json')
            sample=gen.generate('intent'); core.validate(sample)
            self.assertTrue(rules.allows(sample)); self.assertEqual(rules.resolve(sample.obj['messages'][1]['content'],language),SCENE)
            out=RecordFormat('custom',schema,'follow',rules).render(sample)
            self.assertEqual(out['labels']['action'],intent)
            self.assertEqual(out['custom_labels']['意图名称'],intent)
            self.assertIn(out['labels']['tracking'],out['text']); self.assertEqual(set(out['labels']),{'business','action','tracking'})
            canonical=RecordFormat('custom',schema,'canonical',rules).render(sample)
            self.assertEqual(canonical['labels']['action'],'QUERY')
        self.assertIsNone(RecordFormat('custom',{'missing':'${slots.order_id}'}).render(sample)['missing'])

    def test_many_inputs_and_many_rules_map_to_one_custom_output(self):
        rules=AssociationRules({'rules':[{'scene':SCENE,'input':{'zh':['快递号','运单号','物流单号']},'output':{'zh':{'我的标签':'查询物流'}}},
            {'scene':SCENE,'input':{'zh':['物流进度']},'output':{'zh':{'我的标签':'查询物流'}}}]})
        gen=core.Generator(1,'2026-10-09',['ecom'],[SCENE])
        for text in ['快递号DEMO-0001在哪','运单号DEMO-0002在哪','物流单号DEMO-0003在哪','物流进度怎么样']:
            sample=gen.single('intent',text,{'domain':'logistics','intent':'QUERY','slots':{}},SCENE)
            core.validate(sample); self.assertTrue(rules.allows(sample))
            out=RecordFormat('custom',{'我定义的key':'${associated.我的标签}'},'zh',rules).render(sample)
            self.assertEqual(out,{'我定义的key':'查询物流'})

    def test_ambiguous_rules_and_scene_mismatch_are_filtered(self):
        rules=AssociationRules({'rules':[{'scene':SCENE,'input':{'en':['tracking number']}},
            {'scene':'ecom:logistics:URGE','input':{'en':['tracking number']}}]})
        with self.assertRaises(ValueError): rules.resolve('My tracking number is DEMO-1234','en')
        gen=core.Generator(3,'2026-10-09',['ecom'],[SCENE],language='en',utterance_templates=ROOT/'examples/logistics-templates.json')
        self.assertFalse(rules.allows(gen.generate('intent')))
        single=AssociationRules({'rules':[{'scene':'ecom:logistics:URGE','input':{'en':['tracking number']}}]})
        self.assertFalse(single.allows(gen.generate('intent')))

    def test_generation_uses_associations_and_reports_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'data.jsonl'
            result=core.main(str(out),8192,seed=5,industries=['ecom'],scenario_ids=[SCENE],language='en',label_language='follow',
                weights_override={t:int(t=='intent') for t in core.TASKS},utterance_templates=ROOT/'examples/logistics-templates.json',association_rules=ROOT/'examples/association-rules.json')
            self.assertGreater(result['association_rules']['matched'],0)
            for line in out.read_text(encoding='utf-8').splitlines():
                self.assertEqual(json.loads(json.loads(line)['messages'][-1]['content'])['intent'],'track shipment')

    def test_import_reverses_configured_label_without_guessing_missing_answer(self):
        from seed_corpus import normalize
        rules=AssociationRules({'rules':[{'scene':SCENE,'input':{'zh':['运单号']},'output':{'zh':{'intent':'查看包裹进程','domain':'包裹服务'}}}]})
        gen=core.Generator(5,'2026-10-09',['ecom'],[SCENE])
        sample=normalize({'input':'查询运单号DEMO-12345678','output':{'domain':'包裹服务','intent':'查看包裹进程','slots':{'tracking_no':'DEMO-12345678'}}}, {},gen.targets,core,'zh',rules)
        self.assertEqual(json.loads(sample.answer)['intent'],'QUERY')
        with self.assertRaises(ValueError): normalize({'input':'查询运单号DEMO-12345678'}, {},gen.targets,core,'zh',rules)


if __name__=='__main__': unittest.main()
