"""Safe record templates and streaming JSONL / JSON / CSV export."""
from __future__ import annotations

import copy
import csv
import io
import json
import math
import re

import catalogue as C
from label_support import localize_sample

RECORD_FORMATS = ('messages', 'alpaca', 'sharegpt', 'custom')
FILE_FORMATS = ('jsonl', 'json', 'csv')
VARIABLES = {'messages', 'system', 'input', 'output', 'history', 'answer_json',
             'task', 'scene', 'industry', 'domain', 'intent', 'slots','language','seed_group','seed_split','associated'}
TOKEN = re.compile(r'\$\{([^{}]+)\}')
DEFAULT_SCHEMA = {'task': '${task}', 'prompt': '${input}', 'completion': '${output}',
                  'labels': '${answer_json}'}


def json_text(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


class RecordFormat:
    def __init__(self, name='messages', schema=None, label_language='canonical', associations=None):
        if name not in RECORD_FORMATS:
            raise ValueError('未知记录格式: ' + str(name))
        self.name = name
        if label_language not in ('canonical','follow','zh','en'): raise ValueError('标签语言须为 canonical、follow、zh 或 en')
        self.label_language = label_language
        self.associations=associations
        self.schema = copy.deepcopy(schema) if name == 'custom' else None
        if name == 'custom':
            if not isinstance(schema, dict) or not schema:
                raise ValueError('自定义格式必须是非空 JSON 对象')
            self._check(schema)

    def _check(self, value, depth=0):
        if depth > 20:
            raise ValueError('自定义格式嵌套不能超过 20 层')
        if isinstance(value, dict):
            for key, item in value.items():
                if not isinstance(key, str) or not key or '${' in key:
                    raise ValueError('自定义格式的字段名必须是固定的非空字符串')
                self._check(item, depth + 1)
        elif isinstance(value, list):
            for item in value:
                self._check(item, depth + 1)
        elif isinstance(value, str):
            unknown={v for v in TOKEN.findall(value) if v.split('.')[0] not in VARIABLES or
                     ('.' in v and (v.split('.')[0] not in ('slots','answer_json','messages','history','associated') or any(not re.fullmatch(r'\w+',p) for p in v.split('.')[1:])))}
            if unknown:
                raise ValueError('未知格式变量: ' + ', '.join(sorted(unknown)))
            if '${' in TOKEN.sub('', value):
                raise ValueError('格式变量必须写为 ${变量名}')
        elif value is not None and not isinstance(value, (bool, int, float)):
            raise ValueError('自定义格式只能包含 JSON 值')
        elif isinstance(value, float) and not math.isfinite(value):
            raise ValueError('自定义格式不能包含 NaN 或 Infinity')

    def render(self, sample):
        sample = localize_sample(sample, self.label_language)
        if self.associations: sample=self.associations.localize(sample,self.label_language)
        messages = sample.obj['messages']
        if self.name == 'messages':
            return copy.deepcopy(sample.obj)
        if self.name == 'sharegpt':
            roles = {'system': 'system', 'user': 'human', 'assistant': 'gpt'}
            return {'conversations': [{'from': roles[m['role']], 'value': m['content']} for m in messages]}
        history = messages[1:-1]
        text = history[0]['content'] if len(history) == 1 else '\n'.join(
            m['role'] + ': ' + m['content'] for m in history)
        if self.name == 'alpaca':
            return {'instruction': messages[0]['content'], 'input': text, 'output': sample.answer}
        try:
            answer = json.loads(sample.answer)
        except ValueError:
            answer = sample.answer
        scene = C.BY_ID.get(sample.scene, {})
        obj_answer = answer if isinstance(answer, dict) else {}
        policy=sample.language if self.label_language=='follow' else self.label_language
        domain,intent=scene.get('domain',''),scene.get('intent','')
        if domain and policy!='canonical':
            from label_support import DOMAINS_ZH, INTENTS_ZH, INTENTS_EN
            intent=(INTENTS_ZH if policy=='zh' else INTENTS_EN).get((domain,intent),intent)
            domain=DOMAINS_ZH.get(domain,domain) if policy=='zh' else domain.replace('_',' ')
        context = {'messages': messages, 'system': messages[0]['content'], 'input': text,
                   'output': sample.answer, 'history': history, 'answer_json': answer,
                   'task': sample.task, 'scene': sample.scene, 'industry': scene.get('industry', 'ecom' if sample.task == 'ecom' else ''),
                   'domain': obj_answer.get('domain', domain),
                   'intent': obj_answer.get('intent', intent),
                   'slots': obj_answer.get('slots', {})}
        context.update(language=sample.language,seed_group=sample.seed_group,seed_split=sample.seed_split)
        context['associated']=self.associations.aliases(sample,self.label_language) if self.associations else {}
        if self.associations: context.update({k:v for k,v in context['associated'].items() if k in ('domain','intent')})

        def lookup(path):
            pieces=path.split('.')
            value=context[pieces[0]]
            for key in pieces[1:]:
                if isinstance(value,dict): value=value.get(key)
                elif isinstance(value,list) and key.isdigit() and int(key)<len(value): value=value[int(key)]
                else: return None
            return copy.deepcopy(value)

        def expand(value):
            if isinstance(value, dict):
                return {k: expand(v) for k, v in value.items()}
            if isinstance(value, list):
                return [expand(v) for v in value]
            if isinstance(value, str):
                exact = TOKEN.fullmatch(value)
                if exact:
                    return lookup(exact[1])
                return TOKEN.sub(lambda m: lookup(m[1]) if isinstance(lookup(m[1]),str) else json_text(lookup(m[1])),value)
            return value

        return expand(self.schema)


class RecordWriter:
    """Produce bytes without owning a file, so core keeps atomic output handling."""
    def __init__(self, record_format, file_format='jsonl'):
        if file_format not in FILE_FORMATS:
            raise ValueError('文件格式必须为 jsonl、json 或 csv')
        self.format = record_format
        self.file_format = file_format
        self.count = 0
        self.fields = None

    def encode(self, sample):
        record = self.format.render(sample)
        if self.file_format == 'csv':
            fields = list(record)
            if self.fields is not None and self.fields != fields:
                raise ValueError('CSV 的顶层字段必须保持一致')
            buf = io.StringIO(newline='')
            writer = csv.writer(buf, lineterminator='\n')
            if self.fields is None:
                writer.writerow(fields)
            writer.writerow([record[k] if isinstance(record[k], str) else json_text(record[k]) for k in fields])
            blob = buf.getvalue().encode('utf-8')
            self.fields = fields
        else:
            prefix = '' if self.file_format == 'jsonl' else ('[\n' if not self.count else ',\n')
            blob = (prefix + json_text(record) + ('\n' if self.file_format == 'jsonl' else '')).encode('utf-8')
        self.count += 1
        return blob

    def finish(self):
        if self.file_format == 'json':
            return b'\n]\n' if self.count else b'[]\n'
        if self.file_format == 'csv' and not self.count:
            # A stopped empty CSV still has a useful header.
            if self.format.name == 'custom': fields = list(self.format.schema)
            else: fields = {'messages': ['messages'], 'alpaca': ['instruction', 'input', 'output'],
                            'sharegpt': ['conversations']}[self.format.name]
            buf = io.StringIO(newline='')
            csv.writer(buf, lineterminator='\n').writerow(fields)
            return buf.getvalue().encode('utf-8')
        return b''
