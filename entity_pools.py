"""Expandable, language/scenario scoped entity pools; never execute templates."""
import hashlib
import json
from pathlib import Path
import re

import catalogue as C

TOKEN = re.compile(r'\$\{([A-Za-z][A-Za-z0-9_]*)\}')
BUILTIN = {
 'zh': {
  'product': {'templates':['${feature}${item}'], 'variables':{
   'feature':['便携式','家用','桌面','轻量','迷你','节能','多功能','旅行用','可折叠','大容量'],
   'item':['台灯','收纳盒','保温杯','水壶','置物架','充电器','键盘','背包','咖啡机','空气净化器','加湿器','电风扇','行李箱','鼠标','音箱','电饭煲','插线板','支架']}},
  'brand': {'templates':['示例${name}${sector}品牌'], 'variables':{'name':['星河','云帆','青禾','晨光','远山','海风','月湾','林间'], 'sector':['家居','数码','户外','生活']}},
  'company': {'templates':['${name}${sector}有限公司'], 'variables':{'name':['星河','青禾','远山','云帆','海风','晨曦','松林','月湾'], 'sector':['科技','商贸','家居','电子','物流','文化']}},
  'bank': {'templates':['示例银行-${code}'], 'variables':{'code':{'hex':8}}},
  'fund_product': {'templates':['示例${kind}理财-${code}'], 'variables':{'kind':['稳健','成长','灵活','定期'], 'code':{'digits':8}}},
  'hotel_name': {'templates':['示例${name}${kind}酒店'], 'variables':{'name':['星河','云帆','海风','青禾','远山','松林','晨曦'], 'kind':['商务','城市','度假','花园','精品']}},
  'course_name': {'templates':['${subject}${level}'], 'variables':{'subject':['Python编程','数据分析','商务英语','摄影','绘画','书法','项目管理','网页开发','统计学','视频剪辑'], 'level':['基础','入门','进阶','实践','应用']}},
 },
 'en': {
  'product': {'templates':['${feature} ${item}'], 'variables':{'feature':['portable','compact','desktop','lightweight','mini','energy-saving','multipurpose','travel','foldable','large-capacity'], 'item':['lamp','storage box','flask','kettle','shelf','charger','keyboard','backpack','coffee maker','air purifier','humidifier','fan','suitcase','mouse','speaker','rice cooker','power strip','stand']}},
  'brand': {'templates':['Example ${name} ${sector} Brand'], 'variables':{'name':['River','Pine','Cloud','Ocean','Meadow','Moon','Forest','Sunrise'], 'sector':['Home','Digital','Outdoor','Lifestyle']}},
  'company': {'templates':['Example ${name} ${sector} Ltd'], 'variables':{'name':['River','Pine','Cloud','Ocean','Meadow','Forest','Sunrise'], 'sector':['Technology','Trading','Home','Electronics','Logistics','Media']}},
  'bank': {'templates':['Example Bank-${code}'], 'variables':{'code':{'hex':8}}},
  'fund_product': {'templates':['Example ${kind} Fund-${code}'], 'variables':{'kind':['Balanced','Growth','Flexible','Fixed-term'], 'code':{'digits':8}}},
  'hotel_name': {'templates':['Example ${name} ${kind} Hotel'], 'variables':{'name':['River','Pine','Cloud','Ocean','Meadow','Forest'], 'kind':['Business','City','Resort','Garden','Boutique']}},
  'course_name': {'templates':['${subject} ${level}'], 'variables':{'subject':['Python Programming','Data Analysis','Business English','Photography','Drawing','Project Management','Web Development','Statistics','Video Editing'], 'level':['Basics','Introduction','Advanced','Practice','Applications']}},
 }
}


def _variable(spec):
    if isinstance(spec,list) and spec and all(isinstance(v,str) and v and len(v)<=512 and not any(c in v for c in '\r\n\x00') for v in spec):
        return list(dict.fromkeys(spec))
    if isinstance(spec,dict) and len(spec)==1 and next(iter(spec)) in ('hex','digits'):
        n = next(iter(spec.values()))
        if type(n) is int and 1 <= n <= 64: return spec
    if isinstance(spec,dict) and set(spec)<= {'min','max','width'} and {'min','max'}<=set(spec):
        lo,hi,width = spec['min'],spec['max'],spec.get('width',0)
        if all(type(v) is int for v in (lo,hi,width)) and 0<=lo<=hi<=10**18 and 0<=width<=32: return spec
    raise ValueError('词池变量需要非空字符串数组、hex/digits 长度或 min/max/width 整数范围')


def _spec(spec):
    if isinstance(spec,list): spec={'values':spec}
    if not isinstance(spec,dict) or set(spec)-{'values','templates','variables','mode','probability'}:
        raise ValueError('词池条目支持 values/templates/variables/mode/probability')
    result=dict(spec)
    values=result.get('values',[])
    if not isinstance(values,list): raise ValueError('词池 values 必须为字符串数组')
    if values: result['values']=_variable(values)
    elif 'values' in result: raise ValueError('词池 values 不能为空')
    variables=result.get('variables',{})
    if not isinstance(variables,dict) or any(not isinstance(k,str) or not re.fullmatch('[A-Za-z][A-Za-z0-9_]*',k) for k in variables): raise ValueError('词池 variables 必须为对象，名称须为英文字母开头的变量名')
    result['variables']={k:_variable(v) for k,v in variables.items()}
    templates=result.get('templates',[])
    if not isinstance(templates,list) or any(not isinstance(v,str) or not v or len(v)>512 or any(c in v for c in '\r\n\x00') for v in templates):
        raise ValueError('词池 templates 需要非空单行字符串')
    for template in templates:
        if set(TOKEN.findall(template))-set(variables): raise ValueError('词池模板引用了未定义变量')
        if '{' in TOKEN.sub('',template) or '}' in TOKEN.sub('',template): raise ValueError('词池模板只支持 ${变量}，禁止表达式')
    if not values and not templates: raise ValueError('词池条目需要 values 或 templates')
    if result.get('mode','merge') not in ('merge','replace'): raise ValueError('词池 mode 须为 merge 或 replace')
    p=result.get('probability',.75)
    if isinstance(p,bool) or not isinstance(p,(int,float)) or not 0<=p<=1: raise ValueError('词池 probability 须在 0 到 1 之间')
    return result


class EntityPools:
    def __init__(self, config=None, expanded=True):
        self.decks,self.draws,self.choices={},{},{}
        self.expanded=bool(expanded)
        if isinstance(config,(str,Path)):
            path=Path(config).expanduser().resolve()
            raw=path.read_bytes()
            config=json.loads(raw.decode('utf-8-sig'))
            self.source={'name':path.name,'sha256':hashlib.sha256(raw).hexdigest()}
        else: self.source=None
        config={} if config is None else config
        if not isinstance(config,dict) or set(config)-{'pools','scenes'}: raise ValueError('词池配置仅支持 pools 和 scenes')
        self.global_pools=self._languages(config.get('pools',{}))
        scenes=config.get('scenes',{})
        if not isinstance(scenes,dict) or set(scenes)-set(C.BY_ID): raise ValueError('词池含未知业务场景')
        self.scenes={k:self._languages(v) for k,v in scenes.items()}

    @staticmethod
    def _languages(data):
        if not isinstance(data,dict) or set(data)-{'zh','en'}: raise ValueError('词池语言须为 zh 或 en')
        result={}
        for lang,slots in data.items():
            if not isinstance(slots,dict) or set(slots)-set(C.SLOT_LABELS): raise ValueError('词池含未知槽位')
            result[lang]={k:_spec(v) for k,v in slots.items()}
        return result

    def _pick(self,values,key,rng):
        deck=self.decks.get(key)
        if not deck:
            deck=list(range(len(values))); rng.shuffle(deck); self.decks[key]=deck
        return values[deck.pop()]

    def _value(self,spec,key,rng):
        if isinstance(spec,list): return self._pick(spec,key,rng)
        if 'hex' in spec: return f"{rng.getrandbits(spec['hex']*4):0{spec['hex']}X}"
        if 'digits' in spec: return ''.join(rng.choices('0123456789',k=spec['digits']))
        return str(rng.randint(spec['min'],spec['max'])).zfill(spec.get('width',0))

    def apply(self,values,gen,scene=None,template=''):
        result=dict(values)
        lang=gen.language
        for slot in result:
            # Preserve known product/size pairs and the product2 exchange categories.
            if slot in ('product','product2','size') and ('size' in result or 'product2' in result): continue
            # Repair/child-specific templates need their constrained built-in category.
            if slot=='product' and any(w in template for w in ('维修','保修','故障','开不了机','电池续航','适合多大孩子')): continue
            scope=scene['id'] if scene else ''
            scoped=self.scenes.get(scope,{}).get(lang,{})
            spec=scoped.get(slot) or self.global_pools.get(lang,{}).get(slot)
            if not spec and self.expanded: spec=BUILTIN.get(lang,{}).get(slot)
            if not spec: continue
            if spec.get('mode','merge')=='merge' and gen.rng.random()>=spec.get('probability',.75): continue
            key=(scope,lang,slot,id(spec))
            choices=self.choices.get(id(spec))
            if choices is None:
                choices=[('value',v) for v in spec.get('values',[])]+[('template',v) for v in spec.get('templates',[])]
                self.choices[id(spec)]=choices
            kind,value=self._pick(choices,key,gen.rng)
            if kind=='template':
                value=TOKEN.sub(lambda m:self._value(spec['variables'][m[1]],(key,m[1]),gen.rng),value)
            result[slot]=value
            self.draws[slot]=self.draws.get(slot,0)+1
        # Two endpoints must remain distinct, even with single-item custom city pools.
        if 'departure' in result and result.get('destination')==result['departure']: result['destination']=values['destination']
        gen.values.extend(result.values())
        return result

    def report(self):
        return {'expanded':self.expanded,'source':self.source,'custom_slots':{k:sorted(v) for k,v in self.global_pools.items()},
                'custom_scenes':sorted(self.scenes),'replacement_draws':dict(self.draws),
                'sampling':'shuffled decks for vocabulary/templates; procedural variable combinations; no materialized Cartesian product',
                'constraints':'known product/size and exchange category pairs retain built-in pools; supplied vocabulary requires semantic review'}


class EntityPoolMixin:
    def __init__(self,*args,entity_pools=None,expanded_pools=True,**kwargs):
        super().__init__(*args,**kwargs)
        self.entity_pools=EntityPools(entity_pools,expanded_pools)

    def choose_scene(self,task):
        scene=super().choose_scene(task); self._entity_scene=scene; return scene

    def _with_pools(self,method,*args,scene=None,template=''):
        depth=getattr(self,'_pool_depth',0)
        self._pool_depth=depth+1
        try: values=method(*args)
        finally: self._pool_depth=depth
        if depth or not hasattr(self,'entity_pools'): return values
        return self.entity_pools.apply(values,self,scene or getattr(self,'_entity_scene',None),template)

    def slot_values(self,template,slots):
        return self._with_pools(super().slot_values,template,slots,template=template)

    def values_for(self,scene):
        return self._with_pools(super().values_for,scene,scene=scene,template=scene['action'])

    def english_values(self,keys,scene):
        return self._with_pools(super().english_values,keys,scene,scene=scene)
