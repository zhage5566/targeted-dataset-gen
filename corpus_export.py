"""Interoperability adapters: messages JSONL and Rasa 3.1 NLU YAML (JSON syntax)."""
from collections import defaultdict
import json
import re


def messages_record(row):
    answer=row['output']
    return {'messages':list(row['history'])+[{'role':'user','content':row['input']},
            {'role':'assistant','content':answer if isinstance(answer,str) else json.dumps(answer,ensure_ascii=False)}],
            'metadata':{k:row[k] for k in ('source','source_id','group_id','split','language','industry')}}


def rasa_record(row):
    if row['history']: raise ValueError('Rasa NLU 导出只支持单轮；多轮请选 messages')
    text=row['input']; answer=row['output']
    if '\n' in text or '\r' in text or any(ch in text for ch in '[]\\'):
        raise ValueError('Rasa NLU 输入含换行或标注控制字符，请先清理或改用 messages')
    if isinstance(answer,str): label=answer; slots={}
    elif isinstance(answer,dict) and isinstance(answer.get('intent'),str):
        label=str(answer.get('domain','custom'))+'__'+answer['intent']; slots=answer.get('slots',{})
    else: raise ValueError('Rasa NLU 需要字符串意图或含 intent 的对象')
    if not label.strip(): raise ValueError('Rasa 意图不能为空')
    spans=[]
    if not isinstance(slots,dict): raise ValueError('slots 需要对象')
    for key,value in slots.items():
        if not isinstance(value,str) or not value or text.count(value)!=1:
            raise ValueError('Rasa 槽位值须在当前输入中唯一出现，避免错误跨度')
        start=text.index(value); spans.append((start,start+len(value),key,value))
    spans.sort()
    if any(a[1]>b[0] for a,b in zip(spans,spans[1:])): raise ValueError('Rasa 不支持重叠实体')
    for start,end,key,value in reversed(spans):
        text=text[:start]+'['+value+']'+json.dumps({'entity':key},ensure_ascii=False)+text[end:]
    return label,text


def export_records(records, path, layout):
    if layout=='messages':
        with path.open('w',encoding='utf-8',newline='\n') as handle:
            for row in records: handle.write(json.dumps(messages_record(row),ensure_ascii=False)+'\n')
    elif layout=='rasa':
        grouped=defaultdict(list)
        for row in records:
            label,text=rasa_record(row); grouped[label].append(text)
        # JSON is valid YAML 1.2. Quoted JSON strings avoid YAML injection.
        obj={'version':'3.1','nlu':[{'intent':label,'examples':''.join('- '+text+'\n' for text in grouped[label])} for label in sorted(grouped)]}
        path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    else: raise ValueError('未知兼容导出格式')
