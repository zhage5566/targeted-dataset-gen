import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from corpus_workbench import record, clean_records, select_balanced, prepare, iter_source
from corpus_benchmark import evaluate


class WorkbenchTests(unittest.TestCase):
    def row(self,text='查订单',answer='查询',split='train',group='g1'):
        return record(text,answer,source='demo',row_id=text,split=split,group=group)

    def test_conflict_quarantines_all_labels(self):
        clean,bad,report=clean_records([self.row(),self.row(answer='取消')])
        self.assertEqual(clean,[]); self.assertEqual(len(bad),2)
        self.assertEqual(report['quarantine']['conflicting_answers'],2)

    def test_full_lineage_removed_from_train_when_one_turn_leaks(self):
        rows=[self.row(),self.row('后续提问'),self.row(split='test',group='g2')]
        clean,bad,_=clean_records(rows)
        self.assertEqual(len(clean),1); self.assertEqual(clean[0]['split'],'test')
        self.assertEqual(len(bad),2)

    def test_context_disambiguates_answers(self):
        a=self.row('好的','订票'); b=self.row('好的','订酒店',group='g2')
        a['history']=[{'role':'assistant','content':'要订票吗'}]
        b['history']=[{'role':'assistant','content':'要订酒店吗'}]
        clean,bad,_=clean_records([a,b]); self.assertEqual(len(clean),2); self.assertFalse(bad)

    def test_automatic_split_identical_inputs_and_explicit_groups(self):
        rows=[record('ＡＢＣ','yes',source='s',row_id=i) for i in range(20)]
        clean,bad,_=clean_records(rows)
        self.assertEqual(len(clean),1)
        rows=[self.row(str(i),group='shared',split='') for i in range(5)]
        clean,_,_=clean_records(rows); self.assertEqual(len({r['split'] for r in clean}),1)

    def test_selection_balances_and_never_selects_test(self):
        rows=[self.row('订单'+str(i),group=str(i)) for i in range(20)]
        rows += [self.row('不同说法',group='extra'),self.row('测试内容',split='test')]
        selected=select_balanced(rows,2,42)
        self.assertEqual(len(selected),2)
        self.assertIn('不同说法',[r['input'] for r in selected])
        self.assertEqual(selected,select_balanced(list(reversed(rows)),2,42))
        self.assertTrue(all(r['split']=='train' for r in selected))

    def test_prepare_transaction_and_csv_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); src=root/'data.csv'; src.write_text('q,a,split\n你好,问候,train\n再见,结束,test\n',encoding='utf-8-sig')
            out=root/'ready'; report=prepare(src,out,fields={'input':'q','output':'a'})
            self.assertEqual(report['accepted_records'],2)
            self.assertEqual(len(report['provenance'][0]['sha256']),64)
            with self.assertRaises(ValueError): prepare(src,out)
            self.assertTrue((out/'test.jsonl').exists())
            self.assertEqual(json.loads((out/'train.jsonl').read_text(encoding='utf-8'))['split'],'train')
            self.assertEqual(json.loads((out/'test.jsonl').read_text(encoding='utf-8'))['split'],'test')
            self.assertEqual((out/'validation.jsonl').read_text(encoding='utf-8'),'')
            src.write_text('q,a\nmissing,\n',encoding='utf-8')
            with self.assertRaises(ValueError): prepare(src,root/'failed',fields={'input':'q','output':'a'})
            self.assertFalse((root/'failed').exists())

    def test_crosswoz_adapter_retains_dialogue_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            data={'1':{'messages':[{'role':'usr','content':'找酒店','dialog_act':[['Inform','酒店','名称','A']]},
                                  {'role':'sys','content':'要便宜的吗','dialog_act':[]},
                                  {'role':'usr','content':'是的','dialog_act':[['Inform','酒店','价格','便宜']]}]}}
            for split in ('train','val','test'):
                with zipfile.ZipFile(root/(split+'.json.zip'),'w') as z: z.writestr(split+'.json',json.dumps(data))
            rows=list(iter_source(root,'crosswoz'))
            self.assertEqual(len(rows),6); self.assertEqual(len(rows[1]['history']),2)
            self.assertEqual(rows[0]['group_id'],rows[1]['group_id'])
            self.assertEqual(rows[1]['output']['dialogue_acts'][0][3],'便宜')

    def test_classification_baseline_rejects_leakage(self):
        rows=[self.row('hello hello','greet',group='a'),self.row('bye bye','end',group='b')]
        test=[self.row('hello there','greet','test','c'),self.row('bye now','end','test','d')]
        result=evaluate(rows,test); self.assertEqual(result['accuracy'],1.)
        with self.assertRaises(ValueError): evaluate(rows,rows)
        test[0]['history']=[{'role':'user','content':'earlier context'}]
        with self.assertRaises(ValueError): evaluate(rows,test)

    def test_slot_evidence_is_checked(self):
        rows=[self.row('查快递SF123',{'slots':{'tracking_no':'SF123'}}),self.row('查快递',{'slots':{'tracking_no':'NOT-IN-INPUT'}},group='bad')]
        clean,bad,_=clean_records(rows)
        self.assertEqual(len(clean),1); self.assertEqual(bad[0]['quarantine_reason'],'ungrounded_slots')

    def test_rasa_and_messages_preserve_annotations(self):
        from corpus_export import rasa_record,messages_record
        row=self.row('查快递SF123',{'intent':'查询物流','slots':{'tracking_no':'SF123'}})
        label,text=rasa_record(row)
        self.assertEqual(label,'custom__查询物流'); self.assertIn('[SF123]{"entity": "tracking_no"}',text)
        row['history']=[{'role':'assistant','content':'您的问题是'}]
        self.assertEqual(messages_record(row)['messages'][0]['content'],'您的问题是')
        with self.assertRaises(ValueError): rasa_record(row)

    def test_failed_export_is_atomic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/'source.json'
            source.write_text(json.dumps([self.row('换行\n文本')],ensure_ascii=False),encoding='utf-8')
            with self.assertRaises(ValueError): prepare(source,root/'out',export_format='rasa')
            self.assertFalse((root/'out').exists())
            self.assertFalse(list(root.glob('.corpus-*')))

    def test_custom_alias_cannot_overwrite_grounded_slots(self):
        from association_rules import AssociationRules
        from data_formats import RecordFormat
        import dataset_gen_core as core
        scene='ecom:logistics:QUERY'
        gen=core.Generator(1,'2026-10-09',['ecom'],[scene])
        sample=gen.single('intent','查询快递号DEMO1',{'domain':'logistics','intent':'QUERY','slots':{'tracking_no':'DEMO1'}},scene)
        rules=AssociationRules({'rules':[{'scene':scene,'input':{'zh':['快递号']},'output':{'zh':{'slots':'自定义额外字段','intent':'查询物流'}}}]})
        result=RecordFormat('custom',{'answer':'${answer_json}','extra':'${associated.slots}'},'zh',rules).render(sample)
        self.assertEqual(result['answer']['slots'],{'tracking_no':'DEMO1'})
        self.assertEqual(result['extra'],'自定义额外字段')


if __name__=='__main__': unittest.main()
