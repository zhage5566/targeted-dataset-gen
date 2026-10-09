import json
import unittest

import dataset_gen_core as core
from data_formats import RecordFormat
from utterance_templates import UtteranceTemplates

SCENE='ecom:order:CANCEL'


class UtteranceTemplateTests(unittest.TestCase):
    def config(self):
        return {'scenes':{SCENE:{'zh':[{'segments':['请取消订单','订单号${订单}','商品${商品}'],'shuffle':True,'joiner':'；',
            'variables':{'订单':{'slot':'order_id'},'商品':{'slot':'product','values':['咖啡机','台灯']}}}]}}}

    def test_custom_positions_vocabulary_labels_and_output_keys(self):
        g=core.Generator(3,'2026-10-09',['ecom'],[SCENE],utterance_templates=self.config())
        positions=set()
        for _ in range(25):
            sample=g.generate('intent'); core.validate(sample)
            answer=json.loads(sample.answer); text=sample.obj['messages'][1]['content']
            self.assertIn(answer['slots']['product'],['咖啡机','台灯'])
            self.assertEqual(answer['intent'],'CANCEL'); self.assertIn(answer['slots']['order_id'],text)
            positions.add(next(i for i,s in enumerate(text.split('；')) if s=='请取消订单'))
            export=RecordFormat('custom',{'我的输入':'${input}','我的标注':'${answer_json}','来源':'${scene}'},'zh').render(sample)
            self.assertEqual(set(export),{'我的输入','我的标注','来源'})
            self.assertNotEqual(export['我的标注']['intent'],'CANCEL')
        self.assertEqual(positions,{0,1,2})

    def test_missing_extra_or_conflicting_placeholders_are_rejected(self):
        for row in [{'text':'${unknown}','variables':{}},
                    {'text':'cancel','variables':{'x':{'slot':'order_id'}}},
                    {'text':'${a} ${b}','variables':{'a':{'slot':'order_id'},'b':{'slot':'order_id'}}},
                    {'text':'${a}','variables':{'a':{'slot':'bank'}}},
                    {'text':'${a}','variables':{'a':{}}}]:
            with self.assertRaises(ValueError): UtteranceTemplates({'scenes':{SCENE:{'en':[row]}}})

    def test_language_fallback_and_all_three_tasks(self):
        config={'scenes':{SCENE:{'en':[{'text':'Cancel order ${order}.','variables':{'order':{'slot':'order_id'}}}]}}}
        g=core.Generator(3,'2026-10-09',['ecom'],[SCENE],language='en',utterance_templates=config)
        for task in ('intent','slots','domain'):
            sample=g.generate(task); core.validate(sample)
            self.assertTrue(sample.obj['messages'][1]['content'].startswith('Cancel order '))
        zh=core.Generator(3,'2026-10-09',['ecom'],[SCENE],utterance_templates=config)
        sample=zh.generate('intent'); core.validate(sample); self.assertEqual(sample.scene,SCENE)
        self.assertEqual(zh.utterance_templates.draws,0)


if __name__=='__main__': unittest.main()
