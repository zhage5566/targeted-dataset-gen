"""User-authored utterances with explicit placeholder grounding and stable labels."""
import hashlib
import json
from pathlib import Path
import re

import catalogue as C
from entity_pools import _spec, TOKEN as POOL_TOKEN

TOKEN=re.compile(r'\$\{([^{}\s]+)\}')


class UtteranceTemplates:
    def __init__(self,config=None):
        self.source=None
        if isinstance(config,(str,Path)):
            path=Path(config).expanduser().resolve(); raw=path.read_bytes()
            config=json.loads(raw.decode('utf-8-sig'))
            self.source={'name':path.name,'sha256':hashlib.sha256(raw).hexdigest()}
        config={} if config is None else config
        if not isinstance(config,dict) or set(config)-{'scenes'}: raise ValueError('输入模板配置仅支持 scenes')
        scenes=config.get('scenes',{})
        if not isinstance(scenes,dict) or set(scenes)-set(C.BY_ID): raise ValueError('输入模板含未知业务场景')
        self.scenes={}
        self.draws=0
        for scene,languages in scenes.items():
            if not isinstance(languages,dict) or set(languages)-{'zh','en'}: raise ValueError('输入模板语言须为 zh 或 en')
            self.scenes[scene]={}
            for lang,rows in languages.items():
                if not isinstance(rows,list) or not rows: raise ValueError('每种语言的输入模板须为非空数组')
                self.scenes[scene][lang]=[self._entry(row,C.BY_ID[scene]) for row in rows]

    @staticmethod
    def _entry(row,scene):
        if not isinstance(row,dict) or set(row)-{'text','segments','shuffle','joiner','variables'}: raise ValueError('输入模板支持 text 或 segments、shuffle、joiner、variables')
        if ('text' in row)==('segments' in row): raise ValueError('输入模板 text 与 segments 必须二选一')
        parts=[row['text']] if 'text' in row else row['segments']
        if not isinstance(parts,list) or not 1<=len(parts)<=100 or any(not isinstance(v,str) or not v or len(v)>8192 for v in parts): raise ValueError('输入模板文本/片段必须为非空字符串')
        if type(row.get('shuffle',False)) is not bool: raise ValueError('输入模板 shuffle 需要布尔值')
        if not isinstance(row.get('joiner',' '),str) or len(row.get('joiner',' '))>32: raise ValueError('输入模板 joiner 须为短字符串')
        variables=row.get('variables',{})
        if not isinstance(variables,dict): raise ValueError('输入模板 variables 须为对象')
        used=set(TOKEN.findall('\n'.join(parts)))
        if used!=set(variables): raise ValueError('输入模板占位词与 variables 必须一一对应')
        if any('${' in TOKEN.sub('',part) for part in parts): raise ValueError('输入模板存在损坏的占位词')
        normalized={}; slots=set()
        for name,spec in variables.items():
            if not isinstance(name,str) or not re.fullmatch(r'\w+',name): raise ValueError('输入模板变量名需要字母、汉字、数字或下划线')
            if not isinstance(spec,dict): raise ValueError('输入模板变量须为对象')
            slot=spec.get('slot')
            if slot is not None:
                if slot not in scene['slots'] or slot in slots: raise ValueError('模板槽位须属于该场景，且不能重复映射')
                slots.add(slot)
            pool={k:v for k,v in spec.items() if k!='slot'}
            if not pool and not slot: raise ValueError('不标注的模板变量需要显式词池')
            normalized[name]={'slot':slot,'pool':_spec(pool) if pool else None}
        result=dict(row); result['variables']=normalized
        return result

    def generate(self,gen,task,scene):
        rows=self.scenes.get(scene['id'],{}).get(gen.language)
        if not rows: return None
        row=gen.entity_pools._pick(rows,('input-template',scene['id'],gen.language),gen.rng)
        base=gen.values_for(scene)
        replacements,slots={},{}
        for name,spec in row['variables'].items():
            slot,pool=spec['slot'],spec['pool']
            if pool:
                choices=[('value',v) for v in pool.get('values',[])]+[('template',v) for v in pool.get('templates',[])]
                key=('input-variable',id(row),name)
                kind,value=gen.entity_pools._pick(choices,key,gen.rng)
                if kind=='template': value=POOL_TOKEN.sub(lambda m:gen.entity_pools._value(pool['variables'][m[1]],(key,m[1]),gen.rng),value)
            else: value=base[slot]
            replacements[name]=value
            if slot: slots[slot]=value
        parts=[row['text']] if 'text' in row else list(row['segments'])
        if row.get('shuffle'): gen.rng.shuffle(parts)
        text=row.get('joiner',' ').join(parts)
        text=TOKEN.sub(lambda m:replacements[m[1]],text)
        answer={'domain':scene['domain']} if task=='domain' else {'slots':slots} if task=='slots' else {'domain':scene['domain'],'intent':scene['intent'],'slots':slots}
        self.draws+=1
        return gen.single(task,text,answer,scene['id'])

    def report(self):
        return {'source':self.source,'templates_by_scene':{k:{lang:len(rows) for lang,rows in v.items()} for k,v in self.scenes.items()},'generated':self.draws,
                'tasks':['intent','slots','domain'],'policy':'user-supplied semantics; explicit slot grounding; test seed mode never uses builtin/custom input templates'}


class UtteranceTemplateMixin:
    def __init__(self,*args,utterance_templates=None,**kwargs):
        super().__init__(*args,**kwargs)
        self.utterance_templates=UtteranceTemplates(utterance_templates)

    def choose_scene(self,task):
        pending=getattr(self,'_template_scene_once',None)
        if pending:
            self._template_scene_once=None; self._entity_scene=pending; return pending
        return super().choose_scene(task)

    def intent(self,task):
        if not self.utterance_templates.scenes: return super().intent(task)
        scene=self.choose_scene(task)
        sample=self.utterance_templates.generate(self,task,scene)
        if sample is not None: return sample
        self._template_scene_once=scene
        try: return super().intent(task)
        finally: self._template_scene_once=None
