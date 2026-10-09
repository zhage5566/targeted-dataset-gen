"""Explicit lexical associations with canonical scene checks and bilingual aliases."""
import copy
import hashlib
import json
from pathlib import Path
import re

import catalogue as C


class AssociationRules:
    def __init__(self,config=None):
        self.source=None; self.matched=0; self.conflicts=0
        if isinstance(config,(str,Path)):
            path=Path(config).expanduser().resolve(); raw=path.read_bytes()
            config=json.loads(raw.decode('utf-8-sig'))
            self.source={'name':path.name,'sha256':hashlib.sha256(raw).hexdigest()}
        config={} if config is None else config
        if not isinstance(config,dict) or set(config)-{'rules'}: raise ValueError('输入输出关联配置仅支持 rules')
        rows=config.get('rules',[])
        if not isinstance(rows,list): raise ValueError('关联 rules 必须为数组')
        self.rules=[]
        for row in rows:
            if not isinstance(row,dict) or set(row)-{'scene','input','output','match'} or row.get('scene') not in C.BY_ID: raise ValueError('关联规则需要有效 scene、input、output')
            inputs,outputs=row.get('input'),row.get('output',{})
            if not isinstance(inputs,dict) or not inputs or set(inputs)-{'zh','en'}: raise ValueError('关联 input 需要 zh/en 关键词数组')
            if not isinstance(outputs,dict) or set(outputs)-{'zh','en'}: raise ValueError('关联 output 需要 zh/en 标签词汇')
            mode=row.get('match','any')
            if mode not in ('any','all'): raise ValueError('关联 match 须为 any 或 all')
            patterns={}
            for lang,terms in inputs.items():
                if not isinstance(terms,list) or not terms or any(not isinstance(v,str) or not v.strip() or len(v)>256 for v in terms): raise ValueError('关联关键词须为非空字符串数组')
                patterns[lang]=[re.compile((r'(?<!\w)'+re.escape(v.strip())+r'(?!\w)') if lang=='en' else re.escape(v.strip()),re.I) for v in terms]
            for lang,aliases in outputs.items():
                if not isinstance(aliases,dict) or any(not isinstance(k,str) or not k.strip() or '${' in k for k in aliases) or any(not isinstance(v,str) or not v.strip() or len(v)>1024 for v in aliases.values()): raise ValueError('关联 output 可自定义固定字段名及字符串字段值')
            self.rules.append({'scene':row['scene'],'patterns':patterns,'output':copy.deepcopy(outputs),'match':mode})
        # A different canonical class must not export the same intent alias within a domain.
        aliases={}
        for rule in self.rules:
            scene=C.BY_ID[rule['scene']]
            for lang,out in rule['output'].items():
                if 'intent' not in out: continue
                key=(lang,scene['domain'],out['intent'].casefold())
                if key in aliases and aliases[key]!=scene['intent']: raise ValueError('同领域不同意图不能使用同一自定义输出词汇')
                aliases[key]=scene['intent']

    def matches(self,text,language):
        matches=[]
        for rule in self.rules:
            patterns=rule['patterns'].get(language,[])
            if patterns and (all if rule['match']=='all' else any)(p.search(text) for p in patterns): matches.append(rule)
        return matches

    def resolve(self,text,language):
        scenes={r['scene'] for r in self.matches(text,language)}
        if len(scenes)>1: raise ValueError('输入词汇同时命中不同场景的关联规则')
        return next(iter(scenes),None)

    def allows(self,sample):
        if sample.task not in ('intent','slots','domain'): return True
        text='\n'.join(m['content'] for m in sample.obj['messages'][1:-1] if m['role']=='user')
        try: resolved=self.resolve(text,sample.language)
        except ValueError: self.conflicts+=1; return False
        if resolved:
            if resolved!=sample.scene: self.conflicts+=1; return False
            try:
                self.aliases(sample,'zh'); self.aliases(sample,'en')
            except ValueError: self.conflicts+=1; return False
            self.matched+=1
        return True

    def aliases(self,sample,policy):
        if policy=='canonical' or sample.task not in ('intent','slots','domain'): return {}
        text='\n'.join(m['content'] for m in sample.obj['messages'][1:-1] if m['role']=='user')
        language=sample.language if policy=='follow' else policy
        result={}
        for rule in self.matches(text,sample.language):
            if rule['scene']==sample.scene:
                current=rule['output'].get(language,{})
                if any(k in result and result[k]!=v for k,v in current.items()): raise ValueError('相同输入关联了不同的输出词汇')
                result.update(current)
        return result

    def canonical_answer(self,answer,scene_id):
        """Reverse configured labels only; never create labels from unlabeled text."""
        scene=C.BY_ID.get(scene_id)
        if not scene: return answer
        aliases=[a for r in self.rules if r['scene']==scene_id for a in r['output'].values()]
        if isinstance(answer,str):
            if any(answer in [v for k,v in a.items() if k!='domain'] for a in aliases): return scene['intent']
            return answer
        if not isinstance(answer,dict): return answer
        result=copy.deepcopy(answer)
        for key in ('domain','intent'):
            if any(result.get(key)==a.get(key) for a in aliases if key in a): result[key]=scene[key]
        return result

    def localize(self,sample,policy):
        aliases=self.aliases(sample,policy)
        if not aliases or sample.task=='slots': return sample
        answer=json.loads(sample.answer)
        for key,value in aliases.items():
            if key in answer: answer[key]=value
        result=copy.deepcopy(sample)
        result.obj['messages'][-1]['content']=json.dumps(answer,ensure_ascii=False,sort_keys=True,separators=(',',':'))
        return result

    def report(self):
        return {'source':self.source,'rule_count':len(self.rules),'matched':self.matched,'conflicts_filtered':self.conflicts,
                'policy':'explicit keyword matches must agree with canonical scene; ambiguous matches filtered; canonical export retains original codes'}
