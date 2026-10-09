"""Import supervised seed data as data, with field mapping and grounded augmentation."""
from __future__ import annotations

from collections import Counter, defaultdict
import copy
import csv
import hashlib
import json
from pathlib import Path
import random
import re

import catalogue as C
from label_support import canonical_answer, normalize_state

DEFAULT_FIELDS = {'messages': 'messages', 'input': 'input', 'output': 'output',
                  'task': 'task', 'scene': 'scene', 'slots': 'slots', 'group':'group_id'}


def field(record, path):
    """Dotted object keys only; never evaluate field paths as Python expressions."""
    value = record
    if not path:
        return None
    for key in path.split('.'):
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def decoded(value):
    if isinstance(value, str):
        try: return json.loads(value)
        except ValueError: pass
    return value


def iter_records(path):
    """Yield row number, record, parse error; continue after a malformed JSONL row."""
    path = Path(path)
    with path.open(encoding='utf-8-sig', newline='') as f:
        if path.suffix.lower() == '.csv':
            for number, row in enumerate(csv.DictReader(f), 2):
                yield number, row, None
        elif path.suffix.lower() == '.json':
            if path.stat().st_size > 64 * 1048576:
                raise ValueError('JSON 数组种子文件请小于 64 MiB；大语料请转换为流式 JSONL')
            value = json.load(f)
            if isinstance(value, dict) and isinstance(value.get('data'), list): value = value['data']
            if isinstance(value, dict): value = [value]
            if not isinstance(value, list): raise ValueError('JSON 种子文件需要对象、对象数组或 {"data": [...]}')
            for number, row in enumerate(value, 1):
                yield number, row, None
        elif path.suffix.lower() in ('.jsonl', '.ndjson'):
            for number, line in enumerate(f, 1):
                if not line.strip(): continue
                try: yield number, json.loads(line), None
                except ValueError as exc: yield number, None, str(exc)
        else:
            raise ValueError('语料种子支持 .jsonl、.ndjson、.json、.csv 文件')


def normalize(record, config, targets, core, language='zh', associations=None):
    if not isinstance(record, dict): raise ValueError('记录必须为对象')
    fields = dict(DEFAULT_FIELDS)
    fields.update(config.get('fields', {}))
    task = field(record, fields['task']) or config.get('task')
    scene_id = field(record, fields['scene']) or config.get('scene')
    if not scene_id and len(targets) == 1: scene_id = targets[0]['id']
    messages = decoded(field(record, fields['messages']))
    answer = decoded(field(record, fields['output']))
    if messages is not None:
        if not isinstance(messages, list) or len(messages) < 2: raise ValueError('messages 需要至少一组用户/助手消息')
        messages = copy.deepcopy(messages)
        for m in messages:
            if not isinstance(m, dict) or set(m) != {'role', 'content'} or not isinstance(m['content'], str):
                raise ValueError('消息必须具有字符串 role/content')
        if messages[0]['role'] == 'system':
            inferred = next((k for k, v in core.SYS_BY_LANGUAGE[language].items() if v == messages[0]['content']), None)
            if not inferred: raise ValueError('system 提示词不匹配；请改用输入/答案字段导入')
            if task and task != inferred: raise ValueError('指定任务与 system 提示词冲突')
            task = inferred
        answer = decoded(messages[-1]['content'])
    if associations:
        raw_input=field(record,fields['input']) if messages is None else '\n'.join(m['content'] for m in messages if m['role']=='user')
        matched=associations.resolve(raw_input,language) if isinstance(raw_input,str) else None
        if matched and scene_id and matched!=scene_id: raise ValueError('种子场景与输入词汇关联规则冲突')
        scene_id=scene_id or matched
        answer=associations.canonical_answer(answer,scene_id)
    answer = canonical_answer(answer, task)
    if not task:
        if isinstance(answer, dict):
            keys = set(answer)
            if keys == {'domain', 'intent', 'slots'}: task = 'intent'
            elif keys == {'slots'}: task = 'slots'
            elif keys == {'domain'}: task = 'domain'
            elif keys and all('-' in k for k in keys): task = 'dst_belief'
        elif isinstance(answer, list): task = 'dst_user'
    if task not in core.TASKS: raise ValueError('无法识别任务，请指定训练任务')
    scene = C.BY_ID.get(scene_id)
    if scene_id and not scene: raise ValueError('未知业务场景 ID')
    if task == 'intent' and isinstance(answer, str) and not scene:
        matches = [s for s in C.SCENARIOS if s['intent'] == answer]
        if len(matches) == 1: scene = matches[0]
    if task == 'intent' and isinstance(answer, str) and scene:
        answer = {'domain': scene['domain'], 'intent': answer,
                  'slots': decoded(field(record, fields['slots'])) or {}}
    elif task == 'domain' and isinstance(answer, str): answer = {'domain': answer}
    elif task == 'slots' and isinstance(answer, dict) and set(answer) != {'slots'}: answer = {'slots': answer}
    answer = canonical_answer(answer, task)
    if not scene and task == 'intent' and isinstance(answer, dict):
        matches = [s for s in C.SCENARIOS if s['domain'] == answer.get('domain') and s['intent'] == answer.get('intent')]
        if len(matches) == 1: scene = matches[0]
    if not scene: raise ValueError('此任务需要场景标注；请选择一个业务场景或映射 scene 字段')
    answer = normalize_state(answer,task,language)
    if scene['id'] not in {s['id'] for s in targets}: raise ValueError('种子不属于当前行业或所选业务功能')
    if task == 'ecom' and scene['id'] not in C.AGENT_SCENES: raise ValueError('工具任务只适用于售后场景')
    if messages is None:
        user = field(record, fields['input'])
        if not isinstance(user, str) or not user.strip(): raise ValueError('输入字段为空或不是字符串')
        if answer is None: raise ValueError('缺少答案/标签字段')
        if language == 'en' and not re.search('[A-Za-z]',user): raise ValueError('英文语料模式需要英文输入种子，导入不会自动翻译')
        if language == 'zh' and not re.search('[\u4e00-\u9fff]',user): raise ValueError('中文语料模式需要中文输入种子，导入不会自动翻译')
        messages = [{'role': 'user', 'content': user}, {'role': 'assistant', 'content':
                    core.dumps(answer) if not isinstance(answer, str) else answer}]
    if messages[0]['role'] != 'system': messages.insert(0, {'role': 'system', 'content': core.SYS_BY_LANGUAGE[language][task]})
    # Keep canonical serialization for structured answers, including CSV labels.
    if not isinstance(answer, str): messages[-1]['content'] = core.dumps(answer)
    sample = core.Sample(task, {'messages': messages}, (), scene['id'], language)
    if task in ('intent', 'slots'):
        slots = decoded(sample.answer).get('slots', {})
        if not isinstance(slots, dict) or set(slots) - set(C.SLOT_LABELS): raise ValueError('未知槽位名称或槽位结构错误')
        if any(not isinstance(v, str) for v in slots.values()): raise ValueError('槽位值必须是字符串')
        sample.masks = tuple(slots.values())
    if task in ('dst_user', 'dst_belief'):
        state = decoded(sample.answer)
        entries = state if task == 'dst_user' else [
            {'domain': k.split('-', 1)[0], 'slot': k.split('-', 1)[1], 'value': v}
            for k, v in state.items()]
        domain = scene['domain'] if language == 'en' else C.DOMAINS[scene['domain']]
        allowed = set(scene['slots']) | {'intent'} if language == 'en' else {C.SLOT_LABELS[k] for k in scene['slots']} | {'诉求'}
        if any(e['domain'] != domain or e['slot'] not in allowed or
               (e['slot'] == ('intent' if language == 'en' else '诉求') and e['value'] != (scene['intent'] if language == 'en' else scene['action'])) for e in entries):
            raise ValueError('DST 标注与指定业务场景不一致')
    core.validate(sample)
    return sample


class SeedCorpus:
    def __init__(self):
        self.samples = defaultdict(list)
        self.augmentable = defaultdict(list)
        self.positions = Counter()
        self.report = {'scanned': 0, 'valid': 0, 'retained': 0, 'filtered': {}, 'examples': [], 'files': []}

    @classmethod
    def load(cls, paths, config, targets, active, core, seed=0, stop_event=None, max_scan=None, notify=None, language='zh', partition=None, associations=None):
        if config is not None and not isinstance(config, dict): raise ValueError('种子导入配置必须是 JSON 对象')
        config = dict(config or {})
        if not isinstance(config.get('fields', {}), dict) or any(
                not isinstance(v, str) for v in config.get('fields', {}).values()):
            raise ValueError('字段映射需要字符串字段路径')
        unknown = set(config.get('fields', {})) - set(DEFAULT_FIELDS)
        if unknown: raise ValueError('未知导入字段映射: ' + ','.join(sorted(unknown)))
        if config.get('task') and config['task'] not in core.TASKS: raise ValueError('未知种子任务')
        if config.get('scene') and config['scene'] not in C.BY_ID: raise ValueError('未知种子场景')
        limit = config.get('max_records', 10000)
        if type(limit) is not int or not 1 <= limit <= 100000: raise ValueError('种子内存保留上限须为 1–100000')
        corpus, rejects, seen = cls(), Counter(), {}
        rng = random.Random(int(seed) ^ 0x5EEDC0)
        reservoir = []
        partition_rows, partition_groups = Counter(), {'train':set(),'test':set()}
        for name in paths:
            path = Path(name).expanduser().resolve()
            if not path.is_file(): raise ValueError('种子文件不存在: ' + str(path))
            with path.open('rb') as f:
                sha = hashlib.sha256()
                hashed = 0
                for block in iter(lambda: f.read(1048576), b''):
                    if stop_event is not None and stop_event.is_set(): break
                    sha.update(block)
                    hashed += len(block)
            info = {'name': path.name, 'bytes': path.stat().st_size,
                    'sha256': sha.hexdigest() if hashed == path.stat().st_size else None}
            corpus.report['files'].append(info)
            for number, obj, error in iter_records(path):
                if stop_event is not None and stop_event.is_set(): break
                if max_scan is not None and corpus.report['scanned'] >= max_scan: break
                corpus.report['scanned'] += 1
                try:
                    if error: raise ValueError('JSON 解析错误')
                    sample = normalize(obj, config, targets, core, language,associations)
                    if sample.task not in active: raise ValueError('此种子的训练任务未启用')
                    key = sample.task, sample.input_key
                    answer = core.digest(core.dumps(decoded(sample.answer)))
                    if key in seen:
                        raise ValueError('重复输入' if seen[key] == answer else '同输入不同答案')
                    seen[key] = answer
                    if partition and partition.mode != 'all':
                        group_field = config.get('fields',{}).get('group',DEFAULT_FIELDS['group'])
                        sample.seed_group,sample.seed_split = partition.prepare(sample,core,field(obj,group_field))
                        partition_rows[sample.seed_split] += 1
                        partition_groups[sample.seed_split].add(sample.seed_group)
                        if sample.seed_split != partition.mode:
                            rejects['另一侧划分的种子'] += 1
                            continue
                    corpus.report['valid'] += 1
                    if len(reservoir) < limit: reservoir.append(sample)
                    else:
                        index = rng.randrange(corpus.report['valid'])
                        if index < limit: reservoir[index] = sample
                except (ValueError, KeyError, TypeError, IndexError, AttributeError) as exc:
                    message = str(exc)
                    rejects[message] += 1
                    if len(corpus.report['examples']) < 10:
                        corpus.report['examples'].append({'file': path.name, 'row': number, 'reason': message})
                if notify and corpus.report['scanned'] % 10000 == 0:
                    notify(f"扫描语料种子 {corpus.report['scanned']} 条，合格 {corpus.report['valid']} 条")
        for sample in reservoir:
            corpus.samples[sample.task].append(sample)
            if len(sample.obj['messages']) == 3 and sample.task in ('intent', 'slots'):
                slots = decoded(sample.answer)['slots']
                values = list(slots.values())
                if (values and len(set(values)) == len(values)
                        and not any(a != b and a in b for a in values for b in values)):
                    corpus.augmentable[sample.task].append(sample)
        corpus.report.update(retained=len(reservoir), filtered=dict(rejects),
                             retained_by_task={k:len(v) for k,v in corpus.samples.items()},
                             augmentable_by_task={k:len(v) for k,v in corpus.augmentable.items()})
        if partition:
            corpus.report['partition'] = {'mode':partition.mode,'test_fraction':partition.fraction,'split_seed':partition.seed,
                'registry':partition.path,'rows_by_partition':dict(partition_rows),
                'groups_by_partition':{k:len(v) for k,v in partition_groups.items()},
                'group_fingerprints':{k:sorted(v) for k,v in partition_groups.items()},
                'policy':'explicit group_id or normalized input structure; descendants inherit their source group'}
        return corpus

    def next(self, task, gen, core, augment=True):
        records = self.samples[task]
        index = self.positions[task]
        if index < len(records):
            self.positions[task] += 1
            return copy.deepcopy(records[index]), 'original'
        if not augment or not self.augmentable[task]: return None, None
        original = gen.pick(self.augmentable[task])
        scene = C.BY_ID[original.scene]
        gen._entity_scene = scene
        answer = decoded(original.answer)
        slots = answer['slots']
        gen.values = []
        if gen.language == 'en':
            values = gen.english_values(list(slots),scene)
        elif scene['industry'] == 'ecom':
            values = gen.slot_values(original.obj['messages'][1]['content'], list(slots))
        else:
            pool = gen.values_for(scene)
            if not set(slots) <= set(pool): return None, None
            values = {k: pool[k] for k in slots}
        changes = {v: values[k] for k, v in slots.items()}
        parts = []
        for value in sorted(changes, key=len, reverse=True):
            pattern = re.escape(value)
            if re.fullmatch(r'\d+(?:\.\d+)?', value): pattern = r'(?<!\d)' + pattern + r'(?!\d)'
            parts.append(pattern)
        text = re.sub('|'.join(parts), lambda m: changes[m[0]], original.obj['messages'][1]['content'])
        updated = copy.deepcopy(answer)
        updated['slots'] = values
        sample = gen.single(task, text, updated, original.scene)
        sample.seed_group, sample.seed_split = original.seed_group, original.seed_split
        core.validate(sample)
        return sample, 'augmented'
