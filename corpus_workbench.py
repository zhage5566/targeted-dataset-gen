"""Offline, provenance-preserving corpus adapters and auditable seed selection.

Independent implementation; no upstream project source code is bundled.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import random
import re
import shutil
import tempfile
import unicodedata
import zipfile

MAX_BYTES = 256 * 1024 * 1024
MAX_ROWS = 200000
SPLITS = ('train', 'validation', 'test')


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def normalized(text):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', text).casefold()).strip()


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def read_json(path, max_uncompressed=MAX_BYTES):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError('文件超过 256 MiB，请先拆分 / File exceeds 256 MiB')
    if path.suffix.lower() == '.zip':
        with zipfile.ZipFile(path) as archive:
            members = [v for v in archive.infolist() if v.filename.endswith('.json')]
            if len(members) != 1 or members[0].file_size > max_uncompressed:
                raise ValueError(f'ZIP 必须只含一个不超过 {max_uncompressed//1048576} MiB 的 JSON 文件')
            return json.loads(archive.read(members[0]).decode('utf-8-sig'))
    return json.loads(path.read_text(encoding='utf-8-sig'))


def record(text, answer, *, source, row_id, split='', group='', language='zh', industry='', history=None):
    return dict(input=text, output=answer, source=source, source_id=str(row_id),
                split=split, group_id=group or f'{source}:{row_id}', language=language,
                industry=industry, history=history or [], _explicit_group=bool(group))


def iter_source(path, adapter='generic', fields=None):
    """Native labels and official splits are retained, never inferred from keywords."""
    path = Path(path)
    if adapter == 'banking77':
        for split in ('train', 'test'):
            with (path / f'{split}.csv').open(encoding='utf-8-sig', newline='') as handle:
                for i, row in enumerate(csv.DictReader(handle)):
                    yield record(row['text'], row['category'], source='banking77', row_id=f'{split}:{i}',
                                 split=split, language='en', industry='金融')
    elif adapter == 'clinc150':
        data = read_json(path / 'data_full.json')
        domains = read_json(path / 'domains.json')
        lookup = {label: domain for domain, labels in domains.items() for label in labels}
        for split, rows in data.items():
            side = {'val': 'validation', 'oos_val': 'validation', 'oos_train': 'train', 'oos_test': 'test'}.get(split, split)
            if side not in SPLITS:
                raise ValueError(f'未知划分 / Unknown split: {split}')
            for i, (text, label) in enumerate(rows):
                yield record(text, label, source='clinc150', row_id=f'{split}:{i}', split=side,
                             language='en', industry=lookup.get(label, 'out_of_scope'))
    elif adapter == 'crosswoz':
        for name, split in [('train', 'train'), ('val', 'validation'), ('test', 'test')]:
            data = read_json(path / f'{name}.json.zip', max_uncompressed=512*1024*1024)
            for dialogue_id, dialogue in data.items():
                history = []
                for i, turn in enumerate(dialogue['messages']):
                    role = turn['role']; text = turn['content']
                    if role == 'usr':
                        acts = turn['dialog_act']
                        yield record(text, {'dialogue_acts': acts}, source='crosswoz',
                                     row_id=f'{name}:{dialogue_id}:{i}', split=split,
                                     group=f'crosswoz:{dialogue_id}', industry='旅游/酒店/餐饮/交通',
                                     history=list(history))
                    history.append({'role': 'user' if role == 'usr' else 'assistant', 'content': text})
    elif adapter == 'generic':
        mapping = {'input': 'input', 'output': 'output', 'split': 'split', 'group_id': 'group_id',
                   'history': 'history', 'industry': 'industry', 'language': 'language'}
        mapping.update(fields or {})
        if path.stat().st_size > MAX_BYTES:
            raise ValueError('文件超过 256 MiB，请先拆分')
        with path.open(encoding='utf-8-sig', newline='') as handle:
            if path.suffix.lower() == '.csv':
                rows = csv.DictReader(handle)
            elif path.suffix.lower() == '.json':
                rows = json.load(handle)
                if not isinstance(rows, list): raise ValueError('JSON 须为记录数组')
            else:
                rows = (json.loads(line) for line in handle if line.strip())
            for i, row in enumerate(rows):
                if not isinstance(row, dict): raise ValueError(f'第 {i+1} 条不是对象')
                values = {key: row.get(field) for key, field in mapping.items()}
                if values['output'] is None: raise ValueError(f'第 {i+1} 条缺少答案 / Missing answer')
                if path.suffix.lower() == '.csv':
                    for key in ('output', 'history'):
                        if isinstance(values[key], str) and values[key].lstrip().startswith(('{', '[')):
                            values[key] = json.loads(values[key])
                result = record(values['input'], values['output'], source=row.get('source') or path.stem,
                             row_id=row.get('source_id', i), split=values['split'] or '',
                             group=values['group_id'] or '', history=values['history'],
                             language=values['language'] or 'zh', industry=values['industry'] or '自定义')
                for key in ('scene','task','synthetic'):
                    if key in row: result[key] = row[key]
                yield result
    else:
        raise ValueError('不支持的适配器 / Unknown adapter')


def label_key(row):
    answer = row['output']
    if isinstance(answer, dict):
        if 'intent' in answer:
            answer = {'domain': answer.get('domain'), 'intent': answer['intent']}
        elif 'dialogue_acts' in answer:
            answer = sorted({tuple(act[:2]) for act in answer['dialogue_acts']})
        elif 'slots' in answer:
            answer = sorted(answer['slots'])
    return dumps(answer)


def input_key(row):
    return digest(dumps([[(m['role'], normalized(m['content'])) for m in row['history']], normalized(row['input'])]))


def fingerprint(row):
    """Lexical structure, not semantic equivalence. Only used for train selection."""
    text = normalized(row['input'])
    answer = row['output']
    slots = answer.get('slots', {}) if isinstance(answer, dict) else {}
    for value in sorted((v for v in slots.values() if isinstance(v, str)), key=len, reverse=True):
        if value: text = text.replace(normalized(value), '<slot>')
    return re.sub(r'\d+', '#', text)


def select_balanced(rows, per_label=100, seed=42, strategy='coverage'):
    if not 1 <= per_label <= 100000: raise ValueError('每标签数量须为 1..100000')
    if strategy not in ('coverage', 'random'): raise ValueError('未知选取策略')
    groups = defaultdict(list)
    for row in rows:
        if row['split'] == 'train': groups[label_key(row)].append(row)
    rng = random.Random(seed); selected = []
    for label in sorted(groups):
        candidates = sorted(groups[label], key=lambda r: (r['source'], r['source_id']))
        rng.shuffle(candidates)
        if strategy == 'coverage' and len(candidates)>per_label:
            # Greedy weighted lexical coverage under a per-label budget. No test
            # examples or labels participate. Rare train n-grams receive 1/df.
            structures=[fingerprint(r) for r in candidates]
            grams=[tuple(sorted({text[i:i+3] for i in range(max(1,len(text)-2))})) for text in structures]
            frequency=Counter(g for features in grams for g in features)
            weights={g:1/count for g,count in frequency.items()}
            seen_grams=set(); seen_structures=set(); remaining=list(range(len(candidates))); chosen=[]
            for _ in range(per_label):
                def gain(index):
                    score=sum(weights[g] for g in grams[index] if g not in seen_grams)/(max(1,len(grams[index]))**0.5)
                    return (structures[index] not in seen_structures,score)
                best=max(remaining,key=gain)
                chosen.append(candidates[best]); remaining.remove(best)
                seen_grams.update(grams[best]); seen_structures.add(structures[best])
            candidates=chosen
        selected.extend(candidates[:per_label])
    return selected


def clean_records(records, seed=42):
    rows = []; labels = defaultdict(set); sides = defaultdict(set); group_sides = defaultdict(set)
    for row in records:
        if len(rows) >= MAX_ROWS: raise ValueError('最多整理 200000 条，请分批处理')
        if not isinstance(row['input'], str) or not row['input'].strip(): raise ValueError('输入须为非空文本')
        if row['output'] is None or row['output'] == '': raise ValueError('答案不可为空')
        if not isinstance(row['history'], list) or any(not isinstance(m, dict) or m.get('role') not in ('user','assistant','system') or not isinstance(m.get('content'), str) for m in row['history']):
            raise ValueError('history 需要 role/content 消息数组')
        if not isinstance(row['group_id'], str): raise ValueError('group_id 须为字符串')
        row = dict(row); key = input_key(row)
        if not row['split']:
            # Identical normalized inputs without explicit lineage use the same side.
            group = row['group_id'] if row.get('_explicit_group', True) else key
            row['split'] = 'test' if int(digest(f'{seed}:{group}')[:8], 16) % 100 < 20 else 'train'
        row['split'] = {'val': 'validation', 'dev': 'validation'}.get(row['split'], row['split'])
        if row['split'] not in SPLITS: raise ValueError('split 仅支持 train/validation/test')
        row['_key'] = key
        labels[key].add(dumps(row['output'])); sides[key].add(row['split']); group_sides[row['group_id']].add(row['split'])
        rows.append(row)
    held_groups = {r['group_id'] for r in rows if r['split'] == 'train' and any(s != 'train' for s in sides[r['_key']])}
    held_groups |= {g for g, ss in group_sides.items() if 'train' in ss and len(ss) > 1}
    clean = []; quarantine = []; seen = set(); counts = Counter()
    for row in rows:
        row = dict(row); key = row.pop('_key'); row.pop('_explicit_group', None)
        reason = ''
        answer = row['output']
        slots = answer.get('slots') if isinstance(answer, dict) else None
        evidence = '\n'.join([m['content'] for m in row['history']] + [row['input']])
        if slots is not None and (not isinstance(slots,dict) or any(not isinstance(v,str) or not v or v not in evidence for v in slots.values())):
            reason = 'ungrounded_slots'
        elif len(labels[key]) > 1: reason = 'conflicting_answers'
        elif row['split'] == 'train' and row['group_id'] in held_groups: reason = 'train_evaluation_overlap'
        elif (row['split'], key) in seen: reason = 'duplicate_within_split'
        if reason:
            quarantine.append(dict(row, quarantine_reason=reason)); counts[reason] += 1
        else:
            seen.add((row['split'], key)); clean.append(row)
    report = {'input_records': len(rows), 'accepted_records': len(clean), 'quarantine': dict(counts),
              'splits': dict(Counter(r['split'] for r in clean)),
              'labels_per_split': {s: len({label_key(r) for r in clean if r['split'] == s}) for s in SPLITS},
              'exact_cross_split_inputs_before': sum(len(v)>1 for v in sides.values()),
              'policy': 'Original splits retained. Conflicting full-context answers quarantined. Training lineage overlapping evaluation quarantined. No semantic leakage guarantee.'}
    return clean, quarantine, report


def prepare(source, destination, adapter='generic', per_label=100, seed=42, fields=None, strategy='random', export_format='none'):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if destination.exists(): raise ValueError('输出目录已存在，请选择新的目录 / Choose a new directory')
    if source == destination or source in destination.parents: raise ValueError('输出目录不能位于原始语料内部')
    source_files = sorted(p for p in source.rglob('*') if p.is_file()) if source.is_dir() else [source]
    provenance = [{'file': p.relative_to(source).as_posix() if source.is_dir() else p.name,
                   'sha256': file_hash(p), 'bytes': p.stat().st_size} for p in source_files]
    clean, quarantine, report = clean_records(iter_source(source, adapter, fields), seed)
    selected = select_balanced(clean, per_label, seed, strategy)
    report.update(adapter=adapter, random_seed=seed, selection_strategy=strategy, per_label=per_label, export_format=export_format,
                  selected_train_records=len(selected), selected_structures=len({(label_key(r), fingerprint(r)) for r in selected}),
                  provenance=provenance, version='2.2.0')
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.corpus-', dir=destination.parent))
    try:
        for name, records in [(s+'.jsonl', [r for r in clean if r['split']==s]) for s in SPLITS] + [('selected-train.jsonl', selected), ('quarantine.jsonl', quarantine)]:
            with (stage/name).open('w', encoding='utf-8', newline='\n') as handle:
                for row in records: handle.write(dumps(row)+'\n')
        (stage/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        if export_format != 'none':
            from corpus_export import export_records
            for side in SPLITS:
                suffix='messages.jsonl' if export_format=='messages' else 'rasa.yml'
                export_records([r for r in clean if r['split']==side],stage/f'{side}.{suffix}',export_format)
        stage.rename(destination)
    finally:
        if stage.exists(): shutil.rmtree(stage)
    return report


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()


def cli():
    parser = argparse.ArgumentParser(description='离线行业语料整理：原始标签 / 来源追踪 / 冲突隔离 / 均衡种子选取')
    parser.add_argument('--source', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--adapter', choices=['generic','banking77','clinc150','crosswoz'], default='generic')
    parser.add_argument('--per-label', type=int, default=100)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--strategy', choices=['random','coverage'], default='random')
    parser.add_argument('--export-format', choices=['none','messages','rasa'], default='none')
    parser.add_argument('--input-field', default='input'); parser.add_argument('--output-field', default='output')
    args = parser.parse_args()
    report = prepare(args.source, args.out, args.adapter, args.per_label, args.seed,
                     {'input':args.input_field, 'output':args.output_field}, args.strategy, args.export_format)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__': cli()
