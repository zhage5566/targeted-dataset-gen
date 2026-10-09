import json
from pathlib import Path
import tempfile
import unittest

import catalogue as C
import dataset_gen_core as core
from entity_pools import EntityPools
from seed_corpus import normalize, SeedCorpus
from seed_partition import SeedPartition


class EntityPoolTests(unittest.TestCase):
    def test_scoped_language_override_and_shuffle_without_early_repeats(self):
        scene=C.BY_ID['finance:bank_card:REPORT_LOSS']
        config={'pools':{'zh':{'bank':['通用示例银行']}},'scenes':{scene['id']:{'zh':{'bank':{'values':['甲示例银行','乙示例银行','丙示例银行'],'mode':'replace'}}}}}
        gen=core.Generator(17,'2026-10-09',['finance'],[scene['id']],entity_pools=config,expanded_pools=False)
        values=[gen.values_for(scene)['bank'] for _ in range(3)]
        self.assertEqual(set(values),{'甲示例银行','乙示例银行','丙示例银行'})
        english=core.Generator(17,'2026-10-09',['finance'],[scene['id']],language='en',entity_pools=config,expanded_pools=False)
        self.assertNotIn(english.values_for(scene)['bank'],values)

    def test_procedural_large_pool_reproducibility_and_no_materialized_combinations(self):
        config={'pools':{'en':{'bank':{'templates':['Demo ${kind} Bank-${id}'],'variables':{'kind':['A','B','C'],'id':{'hex':16}},'mode':'replace'}}}}
        generators=[core.Generator(7,'2026-10-09',['finance'],language='en',entity_pools=config) for _ in range(2)]
        scene=C.BY_ID['finance:bank_card:REPORT_LOSS']
        runs=[[g.values_for(scene)['bank'] for _ in range(250)] for g in generators]
        self.assertEqual(runs[0],runs[1]); self.assertEqual(len(set(runs[0])),250)
        self.assertLess(sum(len(d) for d in generators[0].entity_pools.decks.values()),100)

    def test_invalid_configuration_and_template_execution_are_rejected(self):
        for spec in [{'templates':['${unknown}']},{'templates':['{x.__class__}']},
                     {'values':[]},{'values':['ok'],'probability':float('nan')},
                     {'templates':['${x}'],'variables':{'x':{'digits':999999}}}]:
            with self.assertRaises(ValueError): EntityPools({'pools':{'en':{'bank':spec}}})
        with self.assertRaises(ValueError): EntityPools({'pools':{'en':{'unknown':['x']}}})

    def test_grounded_custom_seed_augmentation_and_grouping(self):
        scene=C.BY_ID['finance:bank_card:REPORT_LOSS']
        gen=core.Generator(5,'2026-10-09',['finance'],[scene['id']],language='en',expanded_pools=False,
            entity_pools={'pools':{'en':{'bank':{'values':['Example Aurora Bank'],'mode':'replace'}}}})
        original=normalize({'input':'I lost my card at Example Orchid Bank.',
            'output':{'domain':'bank_card','intent':'REPORT_LOSS','slots':{'bank':'Example Orchid Bank'}},'scene':scene['id']}, {},gen.targets,core,'en')
        corpus=SeedCorpus(); corpus.augmentable['intent'].append(original)
        augmented,kind=corpus.next('intent',gen,core)
        core.validate(augmented); self.assertEqual(kind,'augmented')
        self.assertIn('Example Aurora Bank',augmented.obj['messages'][1]['content'])
        p=SeedPartition(); self.addCleanup(p.close)
        self.assertEqual(p.group(original,core),p.group(augmented,core))

    def test_product_size_constraints_and_report_configuration_hash(self):
        config={'pools':{'en':{'product':{'values':['incompatible desk lamp'],'mode':'replace'}}}}
        g=core.Generator(13,'2026-10-09',['ecom'],language='en',entity_pools=config)
        scene=C.BY_ID['ecom:after_sales:APPLY_EXCHANGE']
        for _ in range(40):
            vals=g.english_values(['product','size'],scene)
            self.assertNotEqual(vals['product'],'incompatible desk lamp')
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'pool.json'; path.write_text(json.dumps(config),encoding='utf-8')
            out=Path(temp)/'out.jsonl'
            result=core.main(str(out),4000,seed=13,industries=['finance'],
                weights_override={k:int(k=='intent') for k in core.TASKS},language='en',entity_pools=str(path))
            self.assertEqual(len(result['entity_pools']['source']['sha256']),64)
            self.assertTrue(result['entity_pools']['replacement_draws'])


if __name__=='__main__': unittest.main()
